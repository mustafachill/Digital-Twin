#!/usr/bin/env python3
"""Arm D -- the false-negative side, on the IMPLEMENTED predicate.

`criteria.md` Q-D, section 5.4, threshold D1, rule M. ADR-0052 section A.10 item 2's
first bullet: over N grasps on the declared part, what is the distribution of the distance
from `w_reached` to the window's narrow edge, and what is its minimum?

THREE THINGS ARE MEASURED HERE AND THEY GO THROUGH TWO DOORS, WHICH IS ITSELF A FINDING:

  * `45.0 mm` -- the shipped default -- through `Pick`. The production path, and the width
    L4's `PickAt` port default sends.
  * `48.0 mm` -- above the validator's ceiling -- through `Grasp`. `Pick` cannot reach it
    on this branch: `resolve_grasp_width` refuses it before anything moves, and
    `execute_grasp` applies no such refusal, so `Grasp` is the only door left.
  * `48.0 mm` through `Pick`, three trials, run ANYWAY to record the refusal itself --
    the result code, the detail string, and that no motion occurred. A reported quantity,
    not a verdict (`criteria.md` section 5.4).

HOW THE PART GETS BETWEEN THE PADS FOR THE `Grasp` DOOR, stated plainly because the
criteria does not say and the rig forces a choice. `Grasp` does not move the arm, so the
harness drives the shipped `MoveTo` to the pose `Pick` would have planned -- the pick frame
offset along the tool axis by the SHIPPED `gripper_pad_plane_offset_m` at the drive angle
the commanded width asks for, read through `predicate_eval` and never recomputed here --
and then closes. That is a FRESH close on a part the jaws have not touched, which is what
D1 needs; re-closing on a part already held after a `Pick` would have been a re-close, and
its stall would carry the first close's penetration. The target pose and the pose actually
reached are both in every record, and the 45.0 mm trials record `Pick.Result.grasp_pose`,
so the two routes can be compared rather than assumed equal.

WHAT THIS DOES NOT MEASURE. Whether the stall distribution moves with the commanded width
(ADR-0052 section A.9.1). That is the 2026-09-01 campaign's D2, reported INCONCLUSIVE by
two of its own rules and stated there to be about 25x too small. THIS CAMPAIGN IS SMALLER
ON THAT QUESTION, NOT LARGER, and any appearance of an answer to it here is an artefact of
n (`criteria.md` section 8).

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fn.py`
(commit `eeaf903`). That directory is frozen and nothing in it is edited from here.

Runs INSIDE the container, against a cell `run_cell_block.sh` has already brought up.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
from common import ARM, ZONE  # noqa: E402

import cell  # noqa: E402
import rclpy  # noqa: E402
from cite_interfaces.msg import ResultCode  # noqa: E402

#: `criteria.md` section 5.4. The shipped default, and the one command above the
#: validator's ceiling that section A.10 item 2 requires.
WIDTH_PICK_M = 0.045
WIDTH_ABOVE_CEILING_M = 0.048

RELEASE_MARGIN_M = 0.005


def _schedule(pairs: int, refusals: int) -> list[str]:
    """Interleaved, not blocked: the two conditions alternate within the block.

    The refusal trials come FIRST and are not interleaved with anything, because they
    command no motion at all -- putting them between two grasps would be putting a
    no-operation between two grasps and calling it a control.
    """
    plan = ["refusal"] * refusals
    for _ in range(pairs):
        plan.append("pick45")
        plan.append("grasp48")
    return plan


def main() -> int:  # noqa: C901 - one trial loop with three branches, kept in one place
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sim-log", required=True)
    parser.add_argument("--pairs", type=int, default=4,
                        help="45.0/48.0 pairs in this block; criteria.md section 6 is 4")
    parser.add_argument("--refusals", type=int, default=0,
                        help="Pick-at-48.0 refusal trials; three in total, in one block")
    parser.add_argument("--world", default=ZONE)
    parser.add_argument("--shakedown", action="store_true")
    parser.add_argument(
        "--eval", default=str(Path(__file__).resolve().parent / "predicate_eval"))
    parser.add_argument(
        "--eval-superseded",
        default=str(Path(__file__).resolve().parent / "predicate_eval_superseded"))
    arguments = parser.parse_args()

    out = Path(arguments.out)
    document, manager = common.load_plan()
    travel = common.travel_from_plan(manager)
    parts = common.parts_from_plan(document)
    edge_lo, edge_hi = common.window_m(travel, parts)
    default_width_m = float(manager.gripper["gripper_default_grasp_width_m"])

    predicate = common.Predicate(Path(arguments.eval), travel, parts)
    superseded_path = Path(arguments.eval_superseded)
    superseded = (
        common.SupersededPredicate(superseded_path, travel)
        if superseded_path.exists() else None
    )
    cursor = common.LogCursor(Path(arguments.sim_log))

    geometry = common.running_geometry(f"/cite/{ZONE}/{ARM}")
    pad_offset_48 = predicate.pad_offset(predicate.position(WIDTH_ABOVE_CEILING_M))
    pad_offset_45 = predicate.pad_offset(predicate.position(WIDTH_PICK_M))
    release_m = predicate.max_width() - RELEASE_MARGIN_M

    header = {
        "arm": "D",
        "question": "criteria.md Q-D -- the false-negative side, on the implemented predicate",
        "provenance": common.provenance(),
        "host": common.host_facts(),
        "geometry": geometry,
        "travel": travel,
        "parts": parts,
        "window_m": {"edge_lo": edge_lo, "edge_hi": edge_hi},
        "default_grasp_width_m": default_width_m,
        "widths_m": {"pick": WIDTH_PICK_M, "above_ceiling": WIDTH_ABOVE_CEILING_M},
        "pad_plane_offset_m": {"at_45": pad_offset_45, "at_48": pad_offset_48},
        "release_width_m": release_m,
        "i6": {
            "at_45": predicate.resolve(WIDTH_PICK_M, default_width_m),
            "at_48": predicate.resolve(WIDTH_ABOVE_CEILING_M, default_width_m),
        },
        "predicate_eval": predicate.describe(),
        "superseded": common.superseded_provenance(),
    }
    writer = common.TrialWriter(out, arguments.label, header)

    if not geometry["v2_ok"]:
        print(f"ABORT: V2 -- the running description is not the shipped hulls ({geometry}).")
        return 3
    if not header["provenance"]["v1_clean"]:
        print("WARNING: V1 is NOT clean for this block; criteria.md V1 discards it.")

    schedule = _schedule(arguments.pairs, arguments.refusals)
    if arguments.shakedown:
        schedule = ["refusal", "pick45", "grasp48"]

    rclpy.init()
    driver = cell.Driver("option_f_arm_d_harness")
    driver.start_spinning()
    driver.await_stack()
    pick_xyz = driver.resolve(cell.PICK_FRAME)
    print(f"pick frame at {pick_xyz}")

    for index, condition in enumerate(schedule, start=1):
        name = f"ofr_part_{arguments.label}_{index:03d}"
        started = time.monotonic()
        driver.drive_q = []
        driver.closing_time = None
        driver.grasp_time = None
        row: dict = {
            "trial": index,
            "arm": "D",
            "condition": condition,
            "model": name,
            "pick_frame_xyz": pick_xyz,
        }
        recorder = None
        try:
            if condition == "refusal":
                # No work-piece, no motion: `resolve_grasp_width` refuses before the
                # first physical act, which is opening the jaws. The refusal IS the
                # measurement.
                before = driver.last_joint_state
                cursor.mark()
                result = driver.do_pick(f"{name}_absent", WIDTH_ABOVE_CEILING_M)
                after = driver.last_joint_state
                row.update(
                    {
                        "commanded_width_m": WIDTH_ABOVE_CEILING_M,
                        "door": "Pick",
                        "pick_answered": result is not None,
                        "pick_result_code": int(result.result.code) if result else None,
                        "pick_detail": result.result.detail if result else None,
                        "pick_precondition_failed": bool(
                            result is not None
                            and result.result.code == ResultCode.PRECONDITION_FAILED),
                        "joint_state_before": before,
                        "joint_state_after": after,
                        "gripper_reports_during": cursor.collect(),
                        "reached_grasping_phase": driver.closing_time is not None,
                    }
                )
                if before and after and before["name"] == after["name"]:
                    row["max_joint_movement_rad"] = max(
                        abs(a - b) for a, b in zip(after["position"], before["position"]))
                row["ok"] = True
                writer.add(row)
                print(f"[{index}/{len(schedule)}] refusal code="
                      f"{row.get('pick_result_code')} moved="
                      f"{row.get('max_joint_movement_rad')}")
                continue

            width_m = WIDTH_PICK_M if condition == "pick45" else WIDTH_ABOVE_CEILING_M
            row["commanded_width_m"] = width_m
            row["door"] = "Pick" if condition == "pick45" else "Grasp"

            driver.go_home()
            cell.remove(arguments.world, name)
            spawn_xyz = (pick_xyz[0], pick_xyz[1],
                         pick_xyz[2] + cell.WORKPIECE_SIZE_M / 2.0 + cell.SPAWN_DROP_M)
            created = cell.spawn(name, spawn_xyz, yaw_rad=0.0)
            if created.returncode != 0:
                raise RuntimeError(f"spawn failed: {created.stderr[-300:]}")
            appeared = None
            for _ in range(60):
                appeared = cell.model_pose(name)
                if appeared is not None:
                    break
                time.sleep(0.5)
            if appeared is None:
                raise RuntimeError("the work-piece never appeared")
            row["spawn_pose"] = appeared
            time.sleep(5.0)
            recorder = cell.ContactRecorder(arguments.world, name)
            time.sleep(1.0)

            if condition == "pick45":
                cursor.mark()
                result = driver.do_pick(name, width_m)
                row["i2_reports"] = cursor.collect()
                row.update(
                    {
                        "pick_answered": result is not None,
                        "pick_result_code": int(result.result.code) if result else None,
                        "pick_detail": result.result.detail if result else None,
                        "pick_reported_holding": bool(result.holding) if result else None,
                        "reached_grasping_phase": driver.closing_time is not None,
                        "reached_retreating_phase": driver.grasp_time is not None,
                    }
                )
                stall_boundary = driver.grasp_time
                # I1 -- a typed, full-precision read of the predicate's own inputs and
                # output. A DIFFERENT EVENT from the close above: it re-closes on the
                # jaws as they stand, which is the only way `Grasp.Result` can be read
                # for a trial whose door is `Pick`.
                cursor.mark()
                confirm = driver.do_grasp(width_m, expect_object=True)
                row["i1_event"] = ("a second close, on the jaws as they stand after the "
                                   "Pick -- not the close the Pick reported")
                row["i1_reports"] = cursor.collect()
                row.update(cell.grasp_result_fields(confirm, "i1"))
                if confirm is not None:
                    row["holding_F"] = bool(confirm.holding)
            else:
                # The `Grasp` door. Reach the part with the shipped `MoveTo`, at the pose
                # `Pick` would have planned for this width.
                pad_offset = predicate.pad_offset(predicate.position(width_m))
                grasp_z = cell.GRASP_HEIGHT_M - pad_offset
                row["moveto_target_z_m"] = {
                    "approach": grasp_z + cell.APPROACH_M, "grasp": grasp_z}
                cursor.mark()
                driver.do_grasp(release_m, expect_object=False)
                row["open_reports"] = cursor.collect()
                approach = driver.move_to_frame_offset(
                    cell.PICK_FRAME, grasp_z + cell.APPROACH_M)
                row["approach_code"] = int(approach.result.code) if approach else None
                descend = driver.move_to_frame_offset(cell.PICK_FRAME, grasp_z)
                row["descend_code"] = int(descend.result.code) if descend else None
                if descend is None or descend.result.code != ResultCode.SUCCESS:
                    raise RuntimeError(
                        f"the arm never reached the grasp pose: {row['descend_code']}")
                row["reached_pose"] = {
                    "frame": descend.reached.header.frame_id,
                    "x": descend.reached.pose.position.x,
                    "y": descend.reached.pose.position.y,
                    "z": descend.reached.pose.position.z,
                    "position_error_m": float(descend.position_error_m),
                }
                cursor.mark()
                driver.closing_time = driver.sim_now()
                result = driver.do_grasp(width_m, expect_object=True)
                stall_boundary = driver.sim_now()
                row["i2_reports"] = cursor.collect()
                row.update(cell.grasp_result_fields(result, "i1"))
                if result is not None:
                    row["holding_F"] = bool(result.holding)

            reports = row.get("i2_reports") or []
            row["stalled"] = reports[-1]["stalled"] if reports else None
            row["reached_goal"] = reports[-1]["reached_goal"] if reports else None

            # I3 -- the drive joint at the stall, at full precision.
            q = cell.q_at(driver, stall_boundary)
            row["i3_q_at_stall_rad"] = q
            row["i3_drive_samples"] = len(driver.drive_q)
            if q is not None:
                row["i3_reached_width_m"] = predicate.width(q)
                row["d_narrow_m"] = row["i3_reached_width_m"] - edge_lo
                row["d_wide_m"] = edge_hi - row["i3_reached_width_m"]
            row.update(common.v4(
                row.get("i1_reached_width_m"), row.get("i3_reached_width_m"),
                row.get("i2_reports")))
            row["i3_window_trace"] = cell.window_trace(
                driver, driver.closing_time, stall_boundary)

            # I4 (V3) -- was a part between the pads while the jaws stalled?
            row.update(recorder.summarise(
                since=None if driver.closing_time is None else driver.closing_time - 1.0))
            row["v3_contact_witnessed"] = bool(row.get("finger_contact_points_max"))

            if superseded is not None and q is not None and row["stalled"] is not None:
                row["holding_S"] = superseded.holding(
                    width_m, q, bool(row["stalled"]), bool(row["reached_goal"]))
                row["holding_S_provenance"] = header["superseded"]
            else:
                row["holding_S"] = None
                row["holding_S_provenance"] = {"available": False}

            # Put the part down and let go, whatever happened, so the next trial starts
            # from an open gripper and an empty world.
            cursor.mark()
            driver.do_grasp(release_m, expect_object=False)
            row["release_reports"] = cursor.collect()
            row["ok"] = True
        except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    trial {index} failed: {exc}")
        finally:
            try:
                cell.remove(arguments.world, name)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2.0)

        row["wall_s"] = round(time.monotonic() - started, 1)
        writer.add(row)
        print(
            f"[{index}/{len(schedule)}] {condition} w_cmd={row['commanded_width_m'] * 1000:.1f} "
            f"w_reached={row.get('i3_reached_width_m')} holding_F={row.get('holding_F')} "
            f"contact={row.get('finger_contact_points_max')} ({row['wall_s']}s)"
        )

    try:
        driver.go_home()
    except Exception:  # noqa: BLE001
        pass
    (out / f"{arguments.label}_header.json").write_text(
        json.dumps(header, indent=2, default=str))
    driver.destroy_node()
    rclpy.shutdown()
    predicate.close()
    if superseded is not None:
        superseded.close()
    print(f"wrote {writer.path}: {len(writer.rows)} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
