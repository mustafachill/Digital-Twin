#!/usr/bin/env python3
"""One block: one cell bring-up, three cycles, four arms, fourteen trials a cycle.

DERIVED IN SHAPE FROM `docs/measurements/2026-09-03-stall-band-flip/harness/measure.py`,
copied at commit `a8b83fb` -- the commit that file last landed at -- the block/cycle loop,
the `TrialWriter` header, the abort path that takes V1's closing reading before anything
else, and the "one runner, one block" split between this file and `run_cell_block.sh`. That
directory is FROZEN (`docs/measurements/README.md` rule 2) and nothing in it is edited here.

WHAT THIS FILE DECIDES, AND WHAT IT DOES NOT. It decides nothing in section 7. It sends the
registered goals in the registered order, records what came back, and computes -- WHERE THE
BLOCK IS TAKEN, on the unrounded samples -- every validity flag and every per-trial quantity
section 7's rules are applied to. `analyse.py` reads those off the record and applies the
thresholds. Splitting it the other way would have the analyser asking a tree that has since
moved.

THE ORDER IS REGISTERED (`criteria.md` section 6) AND IS NOT A CONVENIENCE. A block is one
bring-up; within it a cycle visits CRUISE, FAST, CARRY, CONC in that order; the repeats are
successive cycles. So no arm occupies a contiguous stretch of any block and no arm owns a
bring-up -- which is `../README.md`'s "interleave, do not block", and what makes an order
effect visible as a cycle effect (V6).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import cell  # noqa: E402

import rclpy  # noqa: E402
from action_msgs.msg import GoalStatus  # noqa: E402

#: `criteria.md` section 3. CRUISE and CONC ask for the configured default by sending zero,
#: which `MoveTo.action` defines as "use the configured default"; FAST asks for the
#: description's full limits. CARRY sends no scaling at all -- `Pick` and `Place` apply
#: their own, `apply_scaling(0.0, 0.0)`, which is the same 0.35/0.35.
SCALING = {
    "CRUISE": (0.0, 0.0),
    "FAST": (1.0, 1.0),
    "CONC": (0.0, 0.0),
}

#: V4's ceiling. The subscription must report a matched publisher AND a received message
#: BEFORE the block's first goal; this bounds how long the harness waits for that event
#: before reporting the block undeliverable. It is a ceiling on an EVENT, not a sleep: the
#: loop below exits the instant both conditions hold (P4).
V4_CEILING_S = 300.0

#: `criteria.md` section 10 -- the shakedown's label. It replaces the block name so that a
#: file under `raw/shakedown/` cannot be read as a campaign block's, and it travels on every
#: row as `is_shakedown` besides.
SHAKEDOWN_LABEL = "SHAKEDOWN"


def healthy(record: dict) -> dict:
    """`criteria.md` section 5.3, applied to one goal's two symbols.

    BOTH have to say so: the `action_msgs/GoalStatus` value is `STATUS_SUCCEEDED` AND the
    payload's `ResultCode` is `SUCCESS`, which is 0. The two are coupled on this server, so
    requiring both costs nothing -- and a DISAGREEMENT between them is a defect, reported in
    full and never resolved by reading one of the two.
    """
    status_ok = record.get("status") == GoalStatus.STATUS_SUCCEEDED
    code_ok = record.get("result_code") == 0
    return {
        "status_succeeded": status_ok,
        "result_code_success": code_ok,
        "healthy": bool(status_ok and code_ok),
        "symbols_disagree": status_ok != code_ok,
    }


def classify_unhealthy(record: dict, i3: dict) -> str:
    """The category an unhealthy trial is counted under (`criteria.md` section 5.3).

    THE TOLERANCE CATEGORY IS NOT AN EXCLUSION. A trial that failed with a path- or
    goal-tolerance violation, seen on ANY of I3's three readings, is the headline finding and
    is never excluded -- so it is named here first, and `measure.py` marks it
    `tolerance_event` so that no later reading of "healthy" can filter it out. An exclusion
    rule that removed the event the campaign exists to detect would manufacture the silence
    it is trying to measure.
    """
    if i3.get("i3_any_log_event"):
        return "tolerance_event"
    if record.get("accepted") is False:
        return "refused"
    if record.get("timed_out"):
        return "timeout"
    if record.get("error"):
        return "harness_error"
    if record.get("result_code") is None:
        return "no_result"
    return f"result_code_{record.get('result_code')}"


def run_trial(
    driver: cell.Driver,
    writer: common.TrialWriter,
    cursor: common.LogCursor,
    context: dict,
    client,
    goal,
) -> dict:
    """One L3 goal, its samples, its I3 readings, and every quantity section 7 needs."""
    cursor.mark()
    outcome = driver.run_goal(client, goal)
    record = outcome["goal"]
    samples = outcome["samples"]
    # ATTRIBUTED TO arm_1 AND TO NOTHING ELSE. Under CONC three arms log into this one file,
    # and the 2026-09-04 shakedown caught a genuine arm_3 path-tolerance violation being
    # recorded against arm_1's trial -- QUIET1 = FIRED, the campaign's headline, manufactured
    # out of a load arm (rule T). `common.scrape_i3` is where the attribution lives.
    i3 = cursor.settle(common.ARM)

    joints = list(context["controller_settings"]["joints"])
    summary = common.summarise_trial(samples, joints)
    window = (
        (summary["window_first_index"], summary["window_last_index"])
        if summary["window_present"]
        else None
    )
    settle = common.goal_settle(samples, window)

    peak = summary.get("peak")
    peak_t = peak["sim_t"] if peak else None
    verdict = healthy(record)

    row = {
        **context,
        "goal": record,
        "i3a_status": record.get("status"),
        "i3a_result_code": record.get("result_code"),
        "i3a_detail": record.get("detail"),
        **i3,
        **verdict,
        "unhealthy_category": None if verdict["healthy"] else classify_unhealthy(record, i3),
        # A tolerance event is the campaign's headline whether or not the trial was healthy.
        # It is carried as its own field so that no reading of "healthy" can filter it away
        # (section 5.3's THE ONE EXCEPTION).
        "tolerance_event": bool(i3.get("i3_any_log_event")),
        "summary": summary,
        "goal_settle": settle,
        # V5's second clause: the peak sample's feedback against the nearest independent
        # `/joint_states` reading. REPORTED and EXCLUDING NOTHING.
        "v5_second_clause": {
            "peak_feedback_positions": peak["feedback_positions"] if peak else None,
            "nearest_joint_state": driver.joints.nearest(peak_t, joints),
        },
    }
    return writer.add(row)


#: Where the arm is put before each registered goal set. `criteria.md` section 3 registers
#: CRUISE, FAST and CONC as `home -> above pick -> above place -> home`, and section 6 puts
#: those sets back to back. **The 2026-09-04 shakedown showed what that costs.** CRUISE ends at
#: `home` and FAST then opens with `home`, so FAST's first goal asks the arm to go where it
#: already is: 14 samples, a peak of exactly 0.0, and an instrument loss under rule L clauses
#: L-i and L-iii. That is **one FAST trial in four, by construction** -- 25 % against rule L's
#: 20 % ceiling -- so FAST, the arm PRED3's uncomfortable prediction is about, would have been
#: NOT ADMISSIBLE before the campaign began.
#:
#: **And it broke the controlled comparison section 3 registers.** CONC's control is CRUISE and
#: `arm_1 does the identical thing in both`; as the rig stood, CRUISE's first goal was
#: home-to-home while CONC's was conveyor-to-home, so the control and the treatment did not
#: begin from the same place.
#:
#: The repositioning is a `MoveTo` to 0.10 m above `conveyor_1`'s infeed at default scaling --
#: the registered set's own third waypoint, so it introduces no pose this campaign was not
#: already sending the arm to. **It is NOT a trial** (section 5.3: a trial is one L3 goal of a
#: registered set) and it is written to `<label>_setup.json`, which no glob over
#: `*_trials.json` can reach.
REPOSITION_FRAME_OFFSET_M = cell.APPROACH_M


def reposition(driver: cell.Driver, writer: common.TrialWriter, cycle: int, arm: str) -> dict:
    """Put the arm at the repositioning pose. NOT a trial; see `REPOSITION_FRAME_OFFSET_M`."""
    goal = driver.frame_goal(
        common.PLACE_FRAME, REPOSITION_FRAME_OFFSET_M, 0.0, 0.0
    )
    outcome = driver.run_goal(driver.move_to, goal)
    record = outcome["goal"]
    written = writer.add_setup(
        {
            "kind": "reposition",
            "before_arm": arm,
            "cycle": cycle,
            "frame": common.PLACE_FRAME,
            "z_m": REPOSITION_FRAME_OFFSET_M,
            "goal": record,
            "samples_discarded": len(outcome["samples"]),
            "why": "criteria.md section 3's goal sets are sent back to back, so a set opening "
                   "with `home` after a set ending at `home` is a no-op; this makes every "
                   "registered goal a real motion and gives CONC and CRUISE the same starting "
                   "pose. It is not a trial and enters no distribution.",
        }
    )
    print(f"  [ setup  c{cycle} before {arm}] reposition -> "
          f"{common.PLACE_FRAME}+{REPOSITION_FRAME_OFFSET_M}m "
          f"status={record.get('status')} code={record.get('result_code')}")
    return written


#: V4's sibling for CONC. How long the harness waits for BOTH load arms to have had a goal
#: accepted before arm_1's first CONC goal. An EVENT with a ceiling, never a sleep (P4): the
#: wait ends the instant both have one.
LOAD_LIVENESS_CEILING_S = 120.0


def wait_for_load(load_arms: list, ceiling_s: float = LOAD_LIVENESS_CEILING_S) -> dict:
    """Both load arms are actually loading before arm_1's first CONC goal is sent.

    `criteria.md` section 3 makes `load_active` a statement about arm_1's whole moving window,
    and the 2026-09-04 shakedown showed the rig sending arm_1's first CONC goal while arm_2 was
    still PLANNING its first: `goals_sent 1, goals_accepted 0`, coverage 0.0, and a
    `load_active` of false that was the harness's starting order rather than the load
    condition. This does not close the gaps BETWEEN a load arm's goals -- those are real, they
    are published as `covered_fraction`, and no threshold here moves because of them.
    """
    started = time.monotonic()
    end = started + ceiling_s
    while time.monotonic() < end:
        if all(arm.snapshot()["goals_accepted"] > 0 for arm in load_arms):
            break
        time.sleep(0.2)
    return {
        "waited_s": time.monotonic() - started,
        "ceiling_s": ceiling_s,
        "accepted": {
            arm.snapshot()["arm"]: arm.snapshot()["goals_accepted"] for arm in load_arms
        },
        "all_live": all(arm.snapshot()["goals_accepted"] > 0 for arm in load_arms),
    }


def wait_for_delivery(driver: cell.Driver, ceiling_s: float) -> dict:
    """V4 -- the subscription matched AND received, BEFORE the block's first goal.

    Reliable QoS is a promise to MATCHED subscribers, and a subscription created and
    immediately used reaches nobody (CLAUDE.md section 10). Treated as an EVENT and never as
    a sleep: this returns the instant both conditions hold.

    BOTH CONDITIONS ARE POSITIVE FINDINGS. A matched publisher with no message delivered is
    the QoS mismatch this campaign's central hazard is made of, and it is exactly as fatal to
    a quietness claim as no publisher at all.
    """
    started = time.monotonic()
    end = started + ceiling_s
    publishers: list[dict] = []
    while time.monotonic() < end:
        publishers = driver.states.matched_publishers()
        if publishers and driver.states.received > 0:
            break
        time.sleep(0.2)
    publishers = driver.states.matched_publishers() or publishers
    received = driver.states.received
    return {
        "topic": driver.states.topic,
        "waited_s": time.monotonic() - started,
        "ceiling_s": ceiling_s,
        "matched_publishers": publishers,
        "matched_publisher_count": len(publishers),
        "messages_received_before_first_goal": received,
        "joint_states_received_before_first_goal": driver.joints.received,
        "subscription": driver.states.summarise()["subscription_qos"],
        "v4_ok": bool(publishers) and received > 0,
    }


def i9_reading(driver: cell.Driver, label: str) -> dict:
    """I9 -- the simulated-to-wall clock ratio, FOR CONTEXT ONLY. It enters no verdict.

    Computed from I1's own header stamps against the wall clock, never from Gazebo's
    `real_time_factor` field, which the 2026-08-29 campaign established over-reports under
    starvation. That finding is cited and not copied (rule H).
    """
    return {
        "at": label,
        "sim_stamp": driver.states.last_stamp,
        "wall_monotonic": time.monotonic(),
        "messages_received": driver.states.received,
    }


def i9_ratio(start: dict, end: dict) -> dict:
    sim = None
    if start["sim_stamp"] is not None and end["sim_stamp"] is not None:
        sim = end["sim_stamp"] - start["sim_stamp"]
    wall = end["wall_monotonic"] - start["wall_monotonic"]
    return {
        "start": start,
        "end": end,
        "sim_span_s": sim,
        "wall_span_s": wall,
        "ratio": (sim / wall) if (sim is not None and wall and wall > 0) else None,
        "note": "context only; criteria.md I9 -- this enters no verdict in section 7, and "
                "Gazebo's own real_time_factor field is never quoted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="the raw/ directory to write into")
    parser.add_argument("--block", required=True, help="B1, B2, B3 -- or SHAKEDOWN")
    parser.add_argument("--sim-log", required=True, help="the launch log I3 is scraped from")
    parser.add_argument(
        "--cycles",
        type=int,
        default=3,
        help="cycles per block; criteria.md section 6 registers 3 for a campaign block",
    )
    parser.add_argument(
        "--shakedown",
        action="store_true",
        help="criteria.md section 10 -- ONE run per harness, published under raw/shakedown/, "
             "excluded from every figure in section 7, and it may not set or adjust any "
             "threshold",
    )
    arguments = parser.parse_args()

    label = SHAKEDOWN_LABEL if arguments.shakedown else arguments.block
    out = Path(arguments.out)
    cursor = common.LogCursor(Path(arguments.sim_log))

    start_snapshot = common.snapshot()
    start_load = common.host_load()
    print(f"== {label}: V1 opening reading, clean={start_snapshot['clean']} ==")
    print(f"   vendor pin: {json.dumps(start_snapshot['vendor_pin'])}")
    print(f"   load: {start_load['load_1m']:.2f} {start_load['load_5m']:.2f} "
          f"{start_load['load_15m']:.2f}")

    rclpy.init()
    driver = cell.Driver(common.LOAD_ARMS)
    driver.start_spinning()

    writer = None
    load_arms: list[cell.LoadArm] = []
    workpiece = None
    exit_code = 0
    try:
        v13 = driver.await_stack()
        print(f"== V13: every L3 server answered; waits {v13['server_wait_s']} ==")

        settings = common.controller_settings(common.ARM)
        if not settings["agrees_with_registration"]:
            # NOT an abort. V9 forbids moving a threshold; a generated value that has moved
            # since registration is a FINDING for `ANALYSIS.md`, carried on every record.
            print("== WARNING: the generated controller configuration no longer matches "
                  "what criteria.md section 2.1 registered; it is recorded and applied as "
                  "registered ==")

        arm_station = common.station_frames(common.ARM_STATION)
        if (arm_station["pick_frame"], arm_station["place_frame"]) != (
            common.PICK_FRAME,
            common.PLACE_FRAME,
        ):
            raise RuntimeError(
                "the generated topology no longer gives station_transfer_1 the two frames "
                f"criteria.md section 5.2 registers: {arm_station}"
            )
        load_frames = {
            arm: common.station_frames(common.LOAD_STATIONS[arm])
            for arm in common.LOAD_ARMS
        }

        geometry = common.running_geometry(driver.namespace_)
        print(f"== V2/V3: {json.dumps(geometry)} ==")

        v4 = wait_for_delivery(driver, V4_CEILING_S)
        print(f"== V4: matched={v4['matched_publisher_count']} "
              f"received={v4['messages_received_before_first_goal']} "
              f"after {v4['waited_s']:.1f}s ==")
        print(f"   publisher QoS: {json.dumps(v4['matched_publishers'])}")

        topics = cell.gz_topics()
        print(f"== V12: {len(topics)} Gazebo topics reached through cite_bringup.gz ==")

        header = {
            "label": label,
            "block": arguments.block,
            "is_shakedown": bool(arguments.shakedown),
            "cycles": arguments.cycles,
            "criteria_sha256": start_snapshot["criteria_sha256"],
            "base_commit": common.BASE_COMMIT,
            "v1_start": start_snapshot,
            "load_start": start_load,
            "v7_start": common.v7(start_load),
            "v13": v13,
            "v2": {key: geometry[key] for key in (
                "read_from", "read_returncode", "read_ok", "description_chars",
                "hull_collision_refs", "vendor_visual_refs", "v2_ok")},
            "v3": {key: geometry[key] for key in (
                "production_plugin_refs", "fixture_plugin_refs", "mock_plugin_refs",
                "v3_ok")},
            "v4": v4,
            "v12_gz_topics": topics,
            "v12_gz_topic_count": len(topics),
            "controller_settings": settings,
            "registered_settings": {
                "trajectory_tolerance_rad": common.DECLARED_TRAJECTORY_TOLERANCE_RAD,
                "goal_tolerance_rad": common.DECLARED_GOAL_TOLERANCE_RAD,
                "goal_time_s": common.DECLARED_GOAL_TIME_S,
                "update_rate_hz": common.DECLARED_UPDATE_RATE_HZ,
                "k_per_s": common.K_PER_S,
                "error_per_speed_s": common.ERROR_PER_SPEED_S,
            },
            "station_frames": {"arm_1": arm_station, **load_frames},
            "model_hash": start_snapshot["model_hash"],
            "host": common.host_facts(),
            "state_recorder": driver.states.summarise(),
            "joint_state_recorder": driver.joints.summarise(),
        }
        writer = common.TrialWriter(out, label, header)

        pick_xyz = driver.resolve(common.PICK_FRAME)
        i9_start = i9_reading(driver, "block start")

        load_arms = [
            cell.LoadArm(driver, arm, load_frames[arm]) for arm in common.LOAD_ARMS
        ]

        scheduled = arguments.cycles * 14
        trial = 0
        for cycle in range(1, arguments.cycles + 1):
            print(f"\n===== {label} cycle {cycle}/{arguments.cycles} =====")

            # -- CRUISE and FAST: the identical goal set at two scalings ------------
            for arm in ("CRUISE", "FAST"):
                reposition(driver, writer, cycle, arm)
                velocity, acceleration = SCALING[arm]
                goals = [
                    ("home", driver.home_goal(velocity, acceleration)),
                    ("above_pick", driver.frame_goal(
                        common.PICK_FRAME, cell.APPROACH_M, velocity, acceleration)),
                    ("above_place", driver.frame_goal(
                        common.PLACE_FRAME, cell.APPROACH_M, velocity, acceleration)),
                    ("home", driver.home_goal(velocity, acceleration)),
                ]
                for index, (what, goal) in enumerate(goals):
                    trial += 1
                    row = run_trial(
                        driver, writer, cursor,
                        {
                            "trial": trial,
                            "cycle": cycle,
                            "arm": arm,
                            "goal_index": index,
                            "goal_kind": what,
                            "velocity_scaling": velocity,
                            "acceleration_scaling": acceleration,
                            "controller_settings": settings,
                            "load_active": None,
                            "load": None,
                        },
                        driver.move_to, goal,
                    )
                    report(row)

            # -- CARRY: a work-piece, one Pick and one Place -----------------------
            # `criteria.md` section 6: spawned at the start of each CARRY CYCLE and removed
            # at the end of that cycle -- before the `Pick` and after the `Place` -- so no
            # cycle inherits the previous cycle's part.
            reposition(driver, writer, cycle, "CARRY")
            workpiece = f"following_error_{label}_c{cycle}"
            cell.remove(common.ZONE, workpiece)
            created = cell.spawn(workpiece, cell.spawn_pose(pick_xyz))
            appeared = None
            if created.returncode == 0:
                for _ in range(60):
                    appeared = cell.model_pose(workpiece)
                    if appeared is not None:
                        break
                    time.sleep(0.5)
            carry_context = {
                "workpiece": workpiece,
                "workpiece_spawn_returncode": created.returncode,
                "workpiece_appeared": appeared is not None,
            }
            for index, (what, client, goal) in enumerate(
                (
                    ("pick", driver.pick, driver.pick_goal(workpiece)),
                    ("place", driver.place, driver.place_goal(common.PLACE_FRAME)),
                )
            ):
                trial += 1
                row = run_trial(
                    driver, writer, cursor,
                    {
                        "trial": trial,
                        "cycle": cycle,
                        "arm": "CARRY",
                        "goal_index": index,
                        "goal_kind": what,
                        "velocity_scaling": None,
                        "acceleration_scaling": None,
                        "scaling_note": "Pick and Place apply their own, "
                                        "apply_scaling(0.0, 0.0)",
                        "controller_settings": settings,
                        "load_active": None,
                        "load": None,
                        **carry_context,
                    },
                    client, goal,
                )
                report(row)
            cell.remove(common.ZONE, workpiece)
            workpiece = None

            # -- CONC: CRUISE's goal set unchanged, with two load arms running ------
            reposition(driver, writer, cycle, "CONC")
            velocity, acceleration = SCALING["CONC"]
            for arm in load_arms:
                arm.start()
            try:
                liveness = wait_for_load(load_arms)
                print(f"  [ setup  c{cycle} before CONC] load arms live={liveness['all_live']} "
                      f"after {liveness['waited_s']:.1f}s accepted={liveness['accepted']}")
                writer.add_setup({"kind": "load_liveness", "cycle": cycle, **liveness})
                goals = [
                    ("home", driver.home_goal(velocity, acceleration)),
                    ("above_pick", driver.frame_goal(
                        common.PICK_FRAME, cell.APPROACH_M, velocity, acceleration)),
                    ("above_place", driver.frame_goal(
                        common.PLACE_FRAME, cell.APPROACH_M, velocity, acceleration)),
                    ("home", driver.home_goal(velocity, acceleration)),
                ]
                for index, (what, goal) in enumerate(goals):
                    trial += 1
                    row = run_trial(
                        driver, writer, cursor,
                        {
                            "trial": trial,
                            "cycle": cycle,
                            "arm": "CONC",
                            "goal_index": index,
                            "goal_kind": what,
                            "velocity_scaling": velocity,
                            "acceleration_scaling": acceleration,
                            "controller_settings": settings,
                            "load_active": None,
                            "load": None,
                        },
                        driver.move_to, goal,
                    )
                    stamp_load(row, writer, load_arms)
                    report(row)
            finally:
                for arm in load_arms:
                    arm.stop()

        i9_end = i9_reading(driver, "block end")
        ratio = i9_ratio(i9_start, i9_end)
        print(f"\n== I9 (context only): {json.dumps(ratio)} ==")

        end_snapshot = common.snapshot()
        end_load = common.host_load()
        flags = writer.seal(end_snapshot, end_load, "the block ran to the end of its schedule")
        writer.complete(scheduled, {"i9": ratio, "load_end": end_load})
        print(f"== V1 closing reading: v1_clean={flags['v1_clean']} "
              f"disagreed_mid_block={flags['disagreed_mid_block']} ==")
        print(f"== {label}: {len(writer.rows)} of {scheduled} trials written ==")

    except BaseException as error:  # noqa: BLE001 -- the abort path must run for anything
        exit_code = 3
        print(f"\n## {label} ABORTED: {error!r}", file=sys.stderr)
        if writer is not None:
            # V1's own sentence: the closing reading is taken AT THE ABORT, as the FIRST act
            # of the abort path, so that V8's promise -- a block ending early is reported
            # with the n it reached -- does not silently lose every row it had.
            try:
                flags = writer.seal(
                    common.snapshot(), common.host_load(), f"the block aborted: {error!r}"
                )
                print(f"## V1 closing reading taken at the abort: "
                      f"v1_clean={flags['v1_clean']}", file=sys.stderr)
            except BaseException as sealing:  # noqa: BLE001
                print(f"## the closing reading itself failed: {sealing!r}", file=sys.stderr)
        raise
    finally:
        for arm in load_arms:
            try:
                arm.stop(join_s=10.0)
            except BaseException:  # noqa: BLE001, S110
                pass
        if workpiece is not None:
            try:
                cell.remove(common.ZONE, workpiece)
            except BaseException:  # noqa: BLE001, S110
                pass
        try:
            driver.destroy_node()
        except BaseException:  # noqa: BLE001, S110
            pass
        try:
            rclpy.shutdown()
        except BaseException:  # noqa: BLE001, S110
            pass

    return exit_code


def stamp_load(row: dict, writer: common.TrialWriter, load_arms: list) -> None:
    """CONC's `load_active`, computed where the block is taken and put ON the record.

    `criteria.md` section 3: true iff BOTH load arms had an accepted, unfinished `MoveTo`
    goal for the whole of arm_1's MOVING WINDOW. The window is in the controller's own
    simulated clock and so are the load arms' intervals, so the two are comparable without a
    wall clock entering anywhere (V14).

    A CONC TRIAL WITHOUT IT IS NOT AN INSTRUMENT LOSS -- arm_1's samples are still arm_1's,
    and LIVE1, QUIET1 and BAND1 use them. It is simply not a sample of the load condition,
    and CONC1 reports the count.
    """
    summary = row["summary"]
    snapshots = [arm.snapshot() for arm in load_arms]
    if not summary["window_present"]:
        row["load"] = {
            "arms": snapshots,
            "reason": "the trial has no moving window, so there is nothing for the load to "
                      "have covered",
        }
        row["load_active"] = False
        writer.flush()
        return

    # The window's edges in the CONTROLLER'S OWN CLOCK, read straight off the summary, which
    # carries them absolute. They are NOT reconstructed from `sim_t_first` plus `t_series`:
    # `sim_t_first` is the TRIAL's first sample and `t_series` is relative to the WINDOW's,
    # and those are two different instants -- a trial opens while the controller is still
    # holding position.
    window_start = summary["window_sim_t_first"]
    window_end = summary["window_sim_t_last"]
    if window_start is None or window_end is None:
        row["load"] = {"arms": snapshots, "reason": "the window has no samples"}
        row["load_active"] = False
        writer.flush()
        return

    per_arm = []
    for snapshot in snapshots:
        intervals = [tuple(pair) for pair in snapshot["intervals"]]
        per_arm.append(
            {
                **snapshot,
                "covers_window": cell.covers(intervals, window_start, window_end),
                "covered_fraction": cell.covered_fraction(
                    intervals, window_start, window_end
                ),
            }
        )
    row["load"] = {
        "window_start_sim_t": window_start,
        "window_end_sim_t": window_end,
        "arms": per_arm,
    }
    row["load_active"] = all(entry["covers_window"] for entry in per_arm)
    writer.flush()


def report(row: dict) -> None:
    """One line per trial, so that a running block is legible without opening the JSON."""
    summary = row["summary"]
    peak = summary.get("max_abs_error_rad")
    speed = summary.get("v_peak_feedback_rad_s")
    print(
        f"  [{row['arm']:>6} c{row['cycle']} t{row['trial']:>3} {row['goal_kind']:>11}] "
        f"healthy={row['healthy']} status={row.get('i3a_status')} "
        f"code={row.get('i3a_result_code')} "
        f"n={summary.get('window_samples')} "
        f"rate={summary.get('window_rate_per_sim_s')} "
        f"peak={peak} v_peak={speed} "
        f"L={summary.get('rule_l_admissible')} "
        f"i3={row.get('tolerance_event')}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
