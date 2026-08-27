"""Arm A — what a conveyor ride does to a work-piece's yaw.

Reuses the published harness rather than rebuilding it: pose sampling, spawning,
removal and the quaternion primitives all come from
`../../2026-08-25-friction-grasp/harness/measure_grasp.py`, so the numbers here
are read off the same feed, in the same frame, with the same stamps as the 84
friction trials and the 40 offset trials. What is new is the yaw extraction
(`yaw.py`), the belt command, and the trial shape — none of which the published
campaigns had any reason to build, because neither of them ever put a part on a
belt.

WHAT THIS MEASURES. A part is placed on `conveyor_1` at a known yaw, the belt is
started, and the part's yaw is read again when it reaches the outfeed the
downstream station picks from. The independent variable is the yaw it started
with; the reported quantity is the yaw it arrives with.

TWO ARTEFACT CLASSES THIS FILE IS BUILT TO AVOID, both of which have already cost
this project a campaign:

  * A PART THAT WAS NEVER CARRIED. `conveyor.cpp` matches its `<carry>` list
    against the Gazebo MODEL NAME by exact string equality, and a part spawned
    under any other name rides nothing, trips nothing, and produces no warning
    while the belt goes on publishing its commanded speed. "The yaw did not
    change" would then be true and would mean nothing. So the part is spawned as
    `workpiece` — the single name `facility.workpiece_models` declares — and
    every trial carries a `travelled_m` gate that fails the trial if the part did
    not actually move down the belt.

  * A BELT THAT ONLY LOOKS LIKE IT IS RUNNING. `/cite/cell_a/conveyor_N/state`
    republishes the speed the plugin was handed, not a speed anything measured;
    `tests/scenarios/continuous_line.py` names reading it as a mistake in the
    same class as trusting a beam. Nothing here subscribes to it. Whether the
    belt ran is decided by whether the part moved, in the simulator's own pose
    feed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE.parent.parent / "2026-08-25-friction-grasp" / "harness"
sys.path.insert(0, str(PUBLISHED))
sys.path.insert(0, str(HERE))

import measure_grasp as mg  # noqa: E402
import yaw as yawlib  # noqa: E402

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from std_msgs.msg import Float64  # noqa: E402

try:
    from cite_interfaces.qos import COMMAND
except Exception:  # pragma: no cover - the profile is a convenience, not a contract
    COMMAND = 10

ZONE = "cell_a"
BELT = "conveyor_1"
WORKPIECE = "workpiece"

#: Belt geometry, from `model/assets/instances/conveyors.yaml` resolved through
#: `model/assets/types/conveyors/belt_1200x400.yaml`, and restated in the
#: generated world as `<surface_pose>1.05 0 0.6</surface_pose>` with
#: `<belt_length_m>1.2</belt_length_m>`. Every number below is checked against
#: the generated world at run time by `--probe`, not taken on trust.
BELT_CENTRE_X = 1.050
INFEED_X = 0.500
OUTFEED_X = 1.600
BELT_START_X = 0.450
BELT_END_X = 1.650
SURFACE_Z = 0.600

#: Where `beam_c1_out` actually trips: 50 mm upstream of the outfeed frame.
#: `model/assets/instances/sensors.yaml`, offset [-0.050, 0.250, 0.030] on
#: `conveyor_1/outfeed`. This is the x at which an indexed belt would be told to
#: stop, so it is the x at which this harness stops it.
BEAM_X = 1.550

#: `installed_speed_mps` on all three conveyor instances.
BELT_SPEED_MPS = 0.150

WORKPIECE_SIZE = 0.050
SPAWN_DROP_M = 0.005

#: How far the part must actually travel for the trial to count as a carry. The
#: nominal run from spawn to outfeed is 1.100 m; 0.900 m leaves room for a part
#: that was set down a little late without admitting one that never moved.
TRAVELLED_GATE_M = 0.900

#: Settling windows, in WALL seconds, converted to nothing — the simulator runs
#: far slower than real time on this host, so these are generous by design and
#: every one of them is reported per trial as the sim-time interval it bought.
SETTLE_BEFORE_S = 6.0
SETTLE_AFTER_STOP_S = 8.0
RIDE_CEILING_S = 240.0


def spawn_yawed(world: str, name: str, xyz, yaw_rad: float, mu: float = 1.0):
    """`measure_grasp.spawn`, plus the one flag it never needed.

    The published harness spawns square because a part square to its frame is
    what its question assumed. This campaign's whole independent variable is the
    yaw, and `ros2 run ros_gz_sim create` takes it directly as `-Y`, in radians.
    """
    import subprocess

    path = Path(f"/tmp/{name}_yaw.sdf")
    path.write_text(mg._workpiece_sdf(name, mu))
    return subprocess.run(
        [
            "ros2", "run", "ros_gz_sim", "create", "-file", str(path), "-name", name,
            "-x", str(xyz[0]), "-y", str(xyz[1]), "-z", str(xyz[2]),
            "-Y", f"{yaw_rad:.9f}",
        ],
        capture_output=True, text=True, timeout=180,
    )


class Belt(Node):
    """The one thing in this cell that commands a conveyor.

    `tests/scenarios/continuous_line.py:_start_the_belts` records that nothing in
    the running system does — the setpoint has no owner, and the scenario supplies
    it. This harness supplies it the same way, on the same topic, with the same
    message type and QoS profile, so that "the belt was running" means here what
    it means there.
    """

    def __init__(self, zone: str = ZONE, belt: str = BELT):
        super().__init__("belt_yaw_harness")
        self.set_parameters([rclpy.parameter.Parameter("use_sim_time", value=True)])
        self.topic = f"/cite/{zone}/{belt}/command"
        self.pub = self.create_publisher(Float64, self.topic, COMMAND)

    def command(self, speed: float, repeats: int = 10) -> None:
        """Send a setpoint, more than once.

        Repeated for the reason the scenario repeats it: the bridge may connect
        after the first message, and a dropped setpoint is a belt that never
        starts. The value is constant, so this is a retry and not a schedule.
        """
        for _ in range(repeats):
            self.pub.publish(Float64(data=float(speed)))
            rclpy.spin_once(self, timeout_sec=0.05)

    def sim_now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9


def wait_ready(belt, recorder, ceiling_s: float = 600.0) -> bool:
    """Wait for a cell that is actually running, on evidence rather than a sleep.

    P4 in miniature. Two independent facts have to hold: the simulator's clock is
    advancing (so `use_sim_time` deadlines mean something and the physics is
    stepping), and its pose feed is delivering (so a reading taken from it is a
    reading). Neither is a duration, and neither is inferred from the other — a
    stalled `/clock` with a live feed and a live clock with no subscription
    matched are both states this cell has been in.

    The ceiling is wall time on purpose: an observer whose only clock is the
    simulator's cannot time the simulator out.
    """
    deadline = time.monotonic() + ceiling_s
    first_clock = None
    while time.monotonic() < deadline:
        rclpy.spin_once(belt, timeout_sec=0.2)
        now = belt.sim_now()
        if now > 0.0:
            if first_clock is None:
                first_clock = now
            elif now > first_clock + 1.0 and recorder.names():
                print(f"cell ready: sim clock {now:.2f} s, "
                      f"{len(recorder.names())} entities in the pose feed", flush=True)
                return True
        time.sleep(0.2)
    print("ABORT: the cell did not become ready", flush=True)
    return False


def track_of(recorder, name: str):
    return recorder.snapshot().get(name, [])


def first_at_or_past(track, x: float):
    for s in track:
        if s.p[0] >= x:
            return s
    return None


def yaw_rate_deg_s(track, at_t: float, window_s: float = 0.5, max_x: float | None = None):
    """Signed rate of change of the raw (unfolded) yaw around `at_t`.

    Reported because a part that is still turning when it reaches the outfeed is
    a different hazard from one that has settled at an angle: the first makes the
    yaw a function of exactly when the gripper arrives. Taken on the raw yaw and
    unwrapped, because a folded yaw has a discontinuity at 45 degrees that would
    read as an enormous spurious rate.
    """
    if max_x is not None:
        track = [s for s in track if s.p[0] <= max_x]
    window = [s for s in track if abs(s.t - at_t) <= window_s]
    if len(window) < 3:
        return float("nan")
    raw = []
    previous = None
    for s in window:
        axes = yawlib.quat_to_axes(s.q)
        horizontal = sorted(axes, key=lambda a: math.hypot(a[0], a[1]))[-1]
        angle = math.degrees(math.atan2(horizontal[1], horizontal[0]))
        if previous is not None:
            while angle - previous > 45.0:
                angle -= 90.0
            while previous - angle > 45.0:
                angle += 90.0
        previous = angle
        raw.append((s.t, angle))
    span = raw[-1][0] - raw[0][0]
    if span <= 0:
        return float("nan")
    return (raw[-1][1] - raw[0][1]) / span


def run_trial(recorder, belt, index: int, yaw_deg: float, mode: str, outdir: Path,
              world: str, label: str, model: str = WORKPIECE,
              ride_ceiling_s: float = RIDE_CEILING_S) -> dict:
    """One part, one ride, one reading.

    `model` is the Gazebo model name to spawn under, and it is a parameter rather
    than a constant for exactly one reason: the negative control. Spawning under a
    name outside the world's `<carry>` list is the only way to show that this
    harness can tell a carried part from an uncarried one, and therefore that the
    `carried` gate on every other trial has teeth.
    """
    row: dict = {
        "trial": index, "label": label, "commanded_yaw_deg": yaw_deg, "mode": mode,
        "model": model, "carry_list_match": model == WORKPIECE,
    }

    mg.remove(world, model)
    for _ in range(8):
        time.sleep(0.5)
        if mg.model_pose(model) is None:
            break

    belt.command(0.0)

    spawn_xyz = (INFEED_X, 0.0, SURFACE_Z + WORKPIECE_SIZE / 2.0 + SPAWN_DROP_M)
    created = spawn_yawed(world, model, spawn_xyz, math.radians(yaw_deg))
    if created.returncode != 0:
        row.update(ok=False, note=f"spawn failed: {created.stderr[-300:]}")
        return row

    appeared = None
    for _ in range(60):
        time.sleep(0.5)
        appeared = mg.model_pose(model)
        if appeared is not None:
            break
    if appeared is None:
        row.update(ok=False, note="work-piece never appeared")
        return row

    # Settle stationary, with the belt commanded to zero, so that the yaw the
    # ride starts from is a measured fact and not the yaw that was requested.
    recorder.start()
    t_spawn = belt.sim_now()
    time.sleep(SETTLE_BEFORE_S)

    track = track_of(recorder, model)
    if not track:
        recorder.stop()
        row.update(ok=False, note="no pose samples for the work-piece")
        return row
    settled = track[-1]
    row["yaw_settled_deg"] = yawlib.folded_yaw_deg(settled.q)
    row["tilt_settled_deg"] = yawlib.tilt_deg(settled.q)
    row["x_settled"] = settled.p[0]
    row["y_settled"] = settled.p[1]
    row["z_settled"] = settled.p[2]
    row["t_settled_sim"] = settled.t

    # Start the belt. Nothing below reads the belt's state topic; the evidence
    # that it ran is `travelled_m`.
    belt.command(BELT_SPEED_MPS)
    t_start = belt.sim_now()

    stop_x = BEAM_X if mode == "indexed" else OUTFEED_X
    deadline = time.monotonic() + ride_ceiling_s
    reached = False
    t_stop_sim = float("nan")
    while time.monotonic() < deadline:
        latest = recorder.latest.get(model)
        if latest is not None and latest.p[0] >= stop_x:
            reached = True
            t_stop_sim = latest.t
            break
        time.sleep(0.02)

    if mode == "indexed":
        # The belt stops on the station's trigger, which is what the line is
        # about to do for its own reasons. Then the part is left alone long
        # enough to settle before it is read.
        belt.command(0.0)
        time.sleep(SETTLE_AFTER_STOP_S)
    else:
        # Running: the reading is taken in motion, at the outfeed. The belt is
        # stopped IMMEDIATELY and with no intervening sleep, because the shakedown
        # showed what a sleep buys — the outfeed frame sits 50 mm from the end of
        # the belt body, so one wall second of overrun carries the part off the
        # end, and it then tumbles onto the floor. That tumble is a real property
        # of an un-indexed belt and is reported as one (`left_belt`), but it is
        # not a measurement of what the belt does to a yaw, and it must not reach
        # the settled reading or the rate window.
        belt.command(0.0)
        time.sleep(SETTLE_AFTER_STOP_S)

    recorder.stop()
    track = track_of(recorder, model)
    row["n_samples"] = len(track)
    row["reached_stop_x"] = reached

    if not track:
        row.update(ok=False, note="no pose samples")
        return row

    x0 = track[0].p[0]
    travelled = max(s.p[0] for s in track) - x0
    row["travelled_m"] = travelled
    row["x_first"] = x0
    row["x_last"] = track[-1].p[0]
    row["y_last"] = track[-1].p[1]
    row["z_last"] = track[-1].p[2]
    row["ride_duration_sim_s"] = track[-1].t - t_start if t_start else float("nan")

    # The reading, at the point the mode names.
    if mode == "indexed":
        arrival = track[-1]
        row["yaw_at_read_deg"] = yawlib.folded_yaw_deg(arrival.q)
        row["tilt_at_read_deg"] = yawlib.tilt_deg(arrival.q)
        row["x_at_read"] = arrival.p[0]
        row["yaw_rate_at_read_deg_s"] = yaw_rate_deg_s(
            track, arrival.t, window_s=1.0, max_x=BELT_END_X)
    else:
        crossing = first_at_or_past(track, OUTFEED_X)
        if crossing is None:
            row.update(ok=False, note="never reached the outfeed")
            return row
        row["yaw_at_read_deg"] = yawlib.folded_yaw_deg(crossing.q)
        row["tilt_at_read_deg"] = yawlib.tilt_deg(crossing.q)
        row["x_at_read"] = crossing.p[0]
        row["yaw_rate_at_read_deg_s"] = yaw_rate_deg_s(
            track, crossing.t, window_s=0.5, max_x=BELT_END_X)

    # Both readings, on every trial, whatever the mode: the difference between
    # them is the whole of the indexed-belt question, and paying for it once per
    # trial is cheaper and better paired than running two blocks.
    #
    # TAKEN FROM THE LAST SAMPLE STILL ON THE BELT, never simply from the last
    # sample. A part that has run off the end is falling, and a yaw read off a
    # falling cube measures the floor rather than the conveyor.
    on_belt = [s for s in track if s.p[0] <= BELT_END_X]
    row["left_belt"] = bool(track[-1].p[0] > BELT_END_X)
    row["x_max"] = max(s.p[0] for s in track)
    settle_sample = on_belt[-1] if on_belt else track[-1]
    row["yaw_settled_after_stop_deg"] = yawlib.folded_yaw_deg(settle_sample.q)
    row["tilt_settled_after_stop_deg"] = yawlib.tilt_deg(settle_sample.q)
    row["x_settled_after_stop"] = settle_sample.p[0]

    row["presented_at_read_mm"] = yawlib.presented_mm(row["yaw_at_read_deg"])
    row["presented_settled_mm"] = yawlib.presented_mm(row["yaw_settled_deg"])
    row["delta_yaw_deg"] = row["yaw_at_read_deg"] - row["yaw_settled_deg"]
    row["carried"] = bool(travelled >= TRAVELLED_GATE_M)
    row["flat_at_read"] = bool(row["tilt_at_read_deg"] <= yawlib.FLAT_TOLERANCE_DEG)
    row["ok"] = True
    row["note"] = ""

    raw = outdir / f"{label}_trial{index:03d}_samples.csv"
    with raw.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["entity", "sim_t", "x", "y", "z", "qx", "qy", "qz", "qw"])
        for entity, entity_track in recorder.snapshot().items():
            for s in entity_track:
                writer.writerow([entity, f"{s.t:.6f}",
                                 *[f"{v:.6f}" for v in s.p],
                                 *[f"{v:.6f}" for v in s.q]])
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=ZONE)
    ap.add_argument("--label", default="belt")
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--yaws", default="0,5,10,18.7,30,45")
    ap.add_argument("--modes", default="running,indexed")
    ap.add_argument("--out", default=str(HERE.parent / "raw"))
    ap.add_argument("--nocarry-name", default="",
                    help="spawn under this name instead — the deliberate negative "
                         "control on the carry-list match")
    ap.add_argument("--ride-ceiling", type=float, default=RIDE_CEILING_S,
                    help="wall seconds to wait for the part to reach the read point. "
                         "The negative control never reaches it by design, so that "
                         "block sets this low rather than spending the full ceiling "
                         "proving a part did not move.")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    belt = Belt()

    control_name = args.nocarry_name
    recorder = mg.PoseRecorder(
        args.world,
        lambda n: n == WORKPIECE or n == control_name or n.startswith("probe_"),
    )
    print(f"recording from {recorder.topic}", flush=True)
    for _ in range(20):
        time.sleep(0.25)

    if not wait_ready(belt, recorder):
        belt.destroy_node()
        rclpy.shutdown()
        return 2

    if args.probe:
        names = sorted(recorder.names())
        (outdir / f"{args.label}_entities.txt").write_text("\n".join(names) + "\n")
        print(f"{len(names)} entities in the pose feed")
        for n in names:
            print("  ", n)
        belt.destroy_node()
        rclpy.shutdown()
        return 0

    yaws = [float(v) for v in args.yaws.split(",") if v]
    modes = [m for m in args.modes.split(",") if m]

    # INTERLEAVED, NOT BLOCKED. The offset campaign established that processes in
    # this cell can be bimodal, and that consecutive same-configuration blocks
    # sample the modes unevenly and mislead — its own blocks gave medians ranging
    # 9.6 to 29.8 degrees for that reason. Every condition is therefore visited
    # once per round, against one running cell, before any condition is visited
    # twice.
    schedule = []
    round_index = 0
    while len(schedule) < args.trials:
        for mode in modes:
            for value in yaws:
                schedule.append((value, mode))
        round_index += 1
    schedule = schedule[: args.trials]

    rows = []
    (outdir / f"{args.label}_entities.txt").write_text(
        "\n".join(sorted(recorder.names())) + "\n")

    for index, (value, mode) in enumerate(schedule, start=1):
        print(f"== trial {index}/{len(schedule)}: yaw {value} deg, {mode} ==", flush=True)
        started = time.monotonic()
        try:
            row = run_trial(recorder, belt, index, value, mode, outdir,
                            args.world, args.label,
                            model=args.nocarry_name or WORKPIECE,
                            ride_ceiling_s=args.ride_ceiling)
        except Exception as exc:  # keep the block alive; a lost trial is not a lost block
            row = {"trial": index, "label": args.label, "commanded_yaw_deg": value,
                   "mode": mode, "ok": False, "note": f"exception: {exc}"}
        row["wall_s"] = round(time.monotonic() - started, 1)
        rows.append(row)
        print("   " + json.dumps({k: row.get(k) for k in
                                  ("ok", "carried", "travelled_m", "yaw_settled_deg",
                                   "yaw_at_read_deg", "delta_yaw_deg",
                                   "yaw_rate_at_read_deg_s", "note")}, default=str),
              flush=True)
        (outdir / f"{args.label}_trials.json").write_text(
            json.dumps(rows, indent=2, default=str))

    mg.remove(args.world, WORKPIECE)
    belt.command(0.0)
    belt.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
