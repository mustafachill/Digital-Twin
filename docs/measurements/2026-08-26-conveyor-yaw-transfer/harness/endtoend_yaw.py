"""Arm D — the shipped path, end to end: pick, place onto the belt, ride, read.

Arm A places a part on the belt at a chosen yaw and asks what the belt does to
it. That isolates the belt, which is what it is for, and it deliberately leaves
out the two things a real handoff also contains: the residual yaw a grasp leaves
in the part, and whatever angular velocity a release imparts to it.

THIS ARM PUTS THEM BACK. `arm_1` picks a square part off `table_pick` and places
it on `conveyor_1`'s infeed — which is what `measure_grasp.py` has always done,
because `PLACE_FRAME` in the published harness is already
`cell_a__conveyor_1__infeed`. Then the belt runs and the part's yaw is read at
the outfeed, where the downstream station picks from.

So this measures the user's question directly: **what yaw does a work-piece
actually carry when it reaches a downstream outfeed?** — with the grasp residual
included rather than assumed, and with no yaw commanded anywhere.

IT IS ALSO THE ONLY ARM THAT CAN TEST THE SPIN MECHANISM. `conveyor.cpp` writes
`LinearVelocityCmd` and never touches angular velocity, and `SetLinearVelocity`
makes Physics ignore wrenches on the carried link for the step. If a release
leaves the part turning, nothing on the belt obviously stops it. A part the
harness sets down by hand has no spin to damp, so Arm A cannot see this and this
arm can.
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
import belt_yaw as by  # noqa: E402
import yaw as yawlib  # noqa: E402

import rclpy  # noqa: E402
from std_msgs.msg import Float64  # noqa: E402

try:
    from cite_interfaces.qos import COMMAND
except Exception:  # pragma: no cover
    COMMAND = 10

#: See `yaw_grasp_block.GRASP_HEIGHT_M` for why this is 0.025 and not the
#: published harness's 0.030.
GRASP_HEIGHT_M = 0.025


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=by.ZONE)
    ap.add_argument("--label", default="endtoend")
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--modes", default="running,indexed")
    ap.add_argument("--spawn-yaw", type=float, default=0.0,
                    help="yaw the part is fed to the cell at; 0 is the realistic "
                         "case, since parts arrive square from outside the cell")
    ap.add_argument("--grasp-height", type=float, default=GRASP_HEIGHT_M)
    ap.add_argument("--out", default=str(HERE.parent / "raw"))
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    mg.GRASP_HEIGHT_M = args.grasp_height

    rclpy.init()
    driver = mg.Driver(args.world)
    belt_pub = driver.create_publisher(
        Float64, f"/cite/{by.ZONE}/{by.BELT}/command", COMMAND)

    def belt(speed: float) -> None:
        for _ in range(10):
            belt_pub.publish(Float64(data=float(speed)))
            time.sleep(0.02)

    driver.start_spinning()
    pick_xyz = driver.resolve(mg.PICK_FRAME)
    place_xyz = driver.resolve(mg.PLACE_FRAME)
    print(f"pick  {mg.PICK_FRAME} at {pick_xyz}", flush=True)
    print(f"place {mg.PLACE_FRAME} at {place_xyz}", flush=True)
    print("waiting for the whole stack to be up and matched...", flush=True)
    driver.await_stack()
    print("stack ready", flush=True)

    recorder = mg.PoseRecorder(
        args.world,
        lambda n: n == by.WORKPIECE or n in (mg.ARM_MODEL, mg.PAD_LINK, mg.PAD_LINK_R),
    )
    for _ in range(20):
        time.sleep(0.25)
    (outdir / f"{args.label}_entities.txt").write_text(
        "\n".join(sorted(recorder.names())) + "\n")

    modes = [m for m in args.modes.split(",") if m]
    rows = []

    for index in range(1, args.trials + 1):
        mode = modes[(index - 1) % len(modes)]
        print(f"\n=== trial {index}/{args.trials}  mode={mode} ===", flush=True)
        row: dict = {"trial": index, "label": args.label, "mode": mode,
                     "model": by.WORKPIECE, "spawn_yaw_deg": args.spawn_yaw,
                     "commanded_grasp_height_m": args.grasp_height}
        started = time.monotonic()
        driver.grasp_time = None
        driver.release_time = None
        driver.drive_q = []

        belt(0.0)
        mg.remove(args.world, by.WORKPIECE)
        for _ in range(8):
            time.sleep(0.5)
            if mg.model_pose(by.WORKPIECE) is None:
                break

        spawn_xyz = (pick_xyz[0], pick_xyz[1],
                     pick_xyz[2] + by.WORKPIECE_SIZE / 2.0 + by.SPAWN_DROP_M)
        created = by.spawn_yawed(args.world, by.WORKPIECE, spawn_xyz,
                                 math.radians(args.spawn_yaw))
        if created.returncode != 0:
            row.update(ok=False, note=f"spawn failed: {created.stderr[-300:]}")
            rows.append(row)
            continue

        appeared = None
        for _ in range(60):
            time.sleep(0.5)
            appeared = mg.model_pose(by.WORKPIECE)
            if appeared is not None:
                break
        if appeared is None:
            row.update(ok=False, note="work-piece never appeared")
            rows.append(row)
            continue
        for _ in range(8):
            time.sleep(0.5)

        recorder.start()
        try:
            row["homed"] = driver.go_home()
            pick = driver.do_pick(by.WORKPIECE)
            row["pick_succeeded"] = bool(pick and pick.result.code == 0) if pick else False
            # `holding` is a TOP-LEVEL field of the Pick result beside
            # `ResultCode result`, not a member of it (`Pick.action` lines 13-14).
            # The first run of this arm read `pick.result.holding`, which is
            # absent, so `getattr` returned its default and the column recorded
            # False on twelve trials that were all holding. Fixed here; the
            # affected block is reported as not carrying this field rather than
            # as having measured it false.
            row["pick_reported_holding"] = bool(pick.holding) if pick else False
            place = driver.do_place()
            row["place_succeeded"] = bool(place and place.result.code == 0) if place else False
        except Exception as exc:
            row.update(ok=False, note=f"cycle raised: {exc}")
            recorder.stop()
            rows.append(row)
            continue

        # Let the released part settle on the belt before its yaw is read. This
        # is the INPUT to the belt, and it is the number ADR-0029's residual is
        # supposed to describe.
        time.sleep(6.0)
        track = recorder.snapshot().get(by.WORKPIECE, [])
        if not track:
            row.update(ok=False, note="no pose samples for the work-piece")
            recorder.stop()
            rows.append(row)
            continue

        deposited = track[-1]
        row["yaw_deposited_deg"] = yawlib.folded_yaw_deg(deposited.q)
        row["tilt_deposited_deg"] = yawlib.tilt_deg(deposited.q)
        row["x_deposited"] = deposited.p[0]
        row["y_deposited"] = deposited.p[1]
        row["z_deposited"] = deposited.p[2]
        row["on_belt_after_place"] = bool(
            by.BELT_START_X <= deposited.p[0] <= by.BELT_END_X
            and abs(deposited.p[1]) <= 0.200
            and deposited.p[2] > by.SURFACE_Z)
        row["yaw_rate_deposited_deg_s"] = by.yaw_rate_deg_s(
            track, deposited.t, window_s=1.0, max_x=by.BELT_END_X)

        if not row["on_belt_after_place"]:
            row.update(ok=False, note="the place did not put the part on the belt")
            recorder.stop()
            rows.append(row)
            _dump(recorder, outdir, args.label, index)
            continue

        x_before_ride = deposited.p[0]
        belt(by.BELT_SPEED_MPS)
        stop_x = by.BEAM_X if mode == "indexed" else by.OUTFEED_X
        deadline = time.monotonic() + by.RIDE_CEILING_S
        reached = False
        while time.monotonic() < deadline:
            latest = recorder.latest.get(by.WORKPIECE)
            if latest is not None and latest.p[0] >= stop_x:
                reached = True
                break
            time.sleep(0.02)
        belt(0.0)
        row["reached_stop_x"] = reached
        time.sleep(by.SETTLE_AFTER_STOP_S)

        recorder.stop()
        track = recorder.snapshot().get(by.WORKPIECE, [])
        ride = [s for s in track if s.t >= deposited.t]
        row["n_samples"] = len(track)
        row["travelled_m"] = (max(s.p[0] for s in ride) - x_before_ride) if ride else 0.0
        row["carried"] = bool(row["travelled_m"] >= 0.700)

        target = by.OUTFEED_X if mode == "running" else stop_x
        crossing = by.first_at_or_past(ride, target)
        if crossing is None:
            row.update(ok=False, note="never reached the read point")
            rows.append(row)
            _dump(recorder, outdir, args.label, index)
            continue

        row["yaw_at_read_deg"] = yawlib.folded_yaw_deg(crossing.q)
        row["tilt_at_read_deg"] = yawlib.tilt_deg(crossing.q)
        row["x_at_read"] = crossing.p[0]
        row["yaw_rate_at_read_deg_s"] = by.yaw_rate_deg_s(
            ride, crossing.t, window_s=0.5, max_x=by.BELT_END_X)

        on_belt = [s for s in ride if s.p[0] <= by.BELT_END_X]
        settle_sample = on_belt[-1] if on_belt else crossing
        row["yaw_settled_after_stop_deg"] = yawlib.folded_yaw_deg(settle_sample.q)
        row["left_belt"] = bool(ride[-1].p[0] > by.BELT_END_X)
        row["delta_yaw_deg"] = row["yaw_at_read_deg"] - row["yaw_deposited_deg"]
        row["presented_at_read_mm"] = yawlib.presented_mm(row["yaw_at_read_deg"])
        row["presented_deposited_mm"] = yawlib.presented_mm(row["yaw_deposited_deg"])
        row["flat_at_read"] = bool(row["tilt_at_read_deg"] <= yawlib.FLAT_TOLERANCE_DEG)
        row["ok"] = True
        row["note"] = ""
        row["wall_s"] = round(time.monotonic() - started, 1)

        _dump(recorder, outdir, args.label, index)
        rows.append(row)
        print("   " + json.dumps({k: row.get(k) for k in
                                  ("ok", "pick_succeeded", "carried",
                                   "yaw_deposited_deg", "yaw_at_read_deg",
                                   "delta_yaw_deg", "yaw_rate_at_read_deg_s",
                                   "presented_at_read_mm", "note")}, default=str),
              flush=True)
        (outdir / f"{args.label}_trials.json").write_text(
            json.dumps(rows, indent=2, default=str))

    (outdir / f"{args.label}_trials.json").write_text(json.dumps(rows, indent=2, default=str))
    belt(0.0)
    mg.remove(args.world, by.WORKPIECE)
    driver.destroy_node()
    rclpy.shutdown()
    return 0


def _dump(recorder, outdir: Path, label: str, index: int) -> None:
    raw = outdir / f"{label}_trial{index:03d}_samples.csv"
    with raw.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["entity", "sim_t", "x", "y", "z", "qx", "qy", "qz", "qw"])
        for entity, track in recorder.snapshot().items():
            for s in track:
                writer.writerow([entity, f"{s.t:.6f}",
                                 *[f"{v:.6f}" for v in s.p],
                                 *[f"{v:.6f}" for v in s.q]])


if __name__ == "__main__":
    raise SystemExit(main())
