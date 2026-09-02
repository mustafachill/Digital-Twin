#!/usr/bin/env python3
"""Arm C -- the wide edge, reached through the part's YAW.

`criteria.md` Q-C, section 5.3, threshold C1, rules S-C and W. ADR-0052 section A.6
records that no observed grasp came within 2.1 mm of the wide edge and that any positive
value there is unevidenced; nothing in this repository has ever exercised it.

A 50 mm square yawed by theta presents `50 * (cos theta + sin theta)` across the pads,
which crosses the wide edge at theta > 2.803 degrees on the shipped model. So the lever is
the yaw.

A YAW IS NOT A ROLL. Every angle in this file is a yaw ABOUT THE WORLD VERTICAL, recorded
with its axis, and no figure from the grasp-plane offset campaign -- whose 18.7 degrees is
a ROLL about the pad-to-pad axis -- may be substituted for one.
`docs/measurements/README.md` carries that lesson; this arm is where it would be lost.

I5 SAMPLES THE YAW AT THE STALL AND NOT ONLY AT THE SPAWN, and that is registered rather
than chosen afterwards: the conveyor-yaw campaign found THE JAWS SQUARE THE PART UP AS
THEY CLOSE, so the presented width is what the geometry offers and not necessarily what
the pads meet. A C1 of NOT CROSSED caused by squaring is a different finding from one
caused by the edge being far away, and the yaw at the stall is the instrument that
separates them.

HOW THE PART IS REACHED. `Grasp` does not move the arm, so the harness drives the shipped
`MoveTo` to the pose `Pick` would have planned for this width -- the pick frame offset
along the tool axis by the SHIPPED `gripper_pad_plane_offset_m`, read through
`predicate_eval` and never recomputed here -- and then closes with `expect_object=true`,
which is the production path (`criteria.md` I1). The close ends the trial: nothing
retreats, so the pose probe taken immediately afterwards is a reading of a part that has
not been carried anywhere.

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fn.py`
(commit `eeaf903`). That directory is frozen and nothing in it is edited from here.

Runs INSIDE the container, against a cell `run_cell_block.sh` has already brought up.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
from common import ARM, ZONE  # noqa: E402

import cell  # noqa: E402
import rclpy  # noqa: E402
from cite_interfaces.msg import ResultCode  # noqa: E402

#: `criteria.md` section 5.3, in degrees, in the order they are cycled. 0 is the control;
#: 3.0 is the first setpoint past the 2.803 degree crossing section 2.2 computes; 12 spans
#: past the conveyor-yaw campaign's measured residual.
YAW_SETPOINTS_DEG = (0.0, 1.5, 3.0, 4.5, 6.0, 8.0, 10.0, 12.0)

#: The shipped default. Held fixed: the lever in this arm is the yaw, not the command.
WIDTH_M = 0.045

RELEASE_MARGIN_M = 0.005


def presented_width_m(side_m: float, yaw_rad: float) -> float:
    """`criteria.md` section 2.2's arithmetic, for the record only.

    Geometry of a square against parallel pads, and not a property of the predicate --
    which is why it may live here while the predicate may not.
    """
    return side_m * (abs(math.cos(yaw_rad)) + abs(math.sin(yaw_rad)))


def main() -> int:  # noqa: C901 - one trial loop, kept in one place
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sim-log", required=True)
    parser.add_argument("--cycles", type=int, default=2,
                        help="complete passes over the yaw setpoints in this block")
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
    pad_offset = predicate.pad_offset(predicate.position(WIDTH_M))
    grasp_z = cell.GRASP_HEIGHT_M - pad_offset
    release_m = predicate.max_width() - RELEASE_MARGIN_M

    header = {
        "arm": "C",
        "question": "criteria.md Q-C -- the wide edge, via the part's yaw about the world "
                    "vertical",
        "provenance": common.provenance(),
        "host": common.host_facts(),
        "geometry": geometry,
        "travel": travel,
        "parts": parts,
        "window_m": {"edge_lo": edge_lo, "edge_hi": edge_hi},
        "commanded_width_m": WIDTH_M,
        "i6": predicate.resolve(WIDTH_M, default_width_m),
        "pad_plane_offset_m": pad_offset,
        "grasp_z_in_pick_frame_m": grasp_z,
        "release_width_m": release_m,
        "yaw_setpoints_deg": list(YAW_SETPOINTS_DEG),
        "yaw_axis": "the world vertical, and no other",
        "workpiece_side_m": cell.WORKPIECE_SIZE_M,
        "predicate_eval": predicate.describe(),
        "superseded": common.superseded_provenance(),
    }
    writer = common.TrialWriter(out, arguments.label, header)

    if not geometry["v2_ok"]:
        print(f"ABORT: V2 -- the running description is not the shipped hulls ({geometry}).")
        return 3
    if not header["provenance"]["v1_clean"]:
        print("WARNING: V1 is NOT clean for this block; criteria.md V1 discards it.")

    schedule = [(cycle, yaw) for cycle in range(arguments.cycles)
                for yaw in YAW_SETPOINTS_DEG]
    if arguments.shakedown:
        schedule = [(0, 0.0), (0, 12.0)]

    rclpy.init()
    driver = cell.Driver("option_f_arm_c_harness")
    driver.start_spinning()
    driver.await_stack()
    pick_xyz = driver.resolve(cell.PICK_FRAME)
    print(f"pick frame at {pick_xyz}; grasp z in that frame {grasp_z * 1000:.2f} mm")

    for index, (cycle, yaw_deg) in enumerate(schedule, start=1):
        name = f"ofr_part_{arguments.label}_{index:03d}"
        yaw_rad = math.radians(yaw_deg)
        started = time.monotonic()
        driver.drive_q = []
        driver.closing_time = None
        driver.grasp_time = None
        row: dict = {
            "trial": index,
            "cycle": cycle,
            "arm": "C",
            "condition": "control" if yaw_deg == 0.0 else "yawed",
            "yaw_setpoint_deg": yaw_deg,
            "yaw_setpoint_rad": yaw_rad,
            "yaw_axis": "the world vertical",
            "commanded_width_m": WIDTH_M,
            "presented_width_at_setpoint_m": presented_width_m(
                cell.WORKPIECE_SIZE_M, yaw_rad),
            "model": name,
        }
        recorder = None
        poses = None
        try:
            driver.go_home()
            cell.remove(arguments.world, name)
            spawn_xyz = (pick_xyz[0], pick_xyz[1],
                         pick_xyz[2] + cell.WORKPIECE_SIZE_M / 2.0 + cell.SPAWN_DROP_M)
            created = cell.spawn(name, spawn_xyz, yaw_rad=yaw_rad)
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
            time.sleep(5.0)
            recorder = cell.ContactRecorder(arguments.world, name)
            poses = cell.PoseRecorder(arguments.world, name)
            time.sleep(1.0)

            settled = cell.model_pose(name)
            row["spawn_probe_pose"] = appeared
            row["settled_probe_pose"] = settled
            row["yaw_at_spawn_rad"] = (settled or appeared or {}).get("yaw_rad")

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
            result = driver.do_grasp(WIDTH_M, expect_object=True)
            stall_boundary = driver.sim_now()
            row["i2_reports"] = cursor.await_report()
            row["i2_report_missing"] = not row["i2_reports"]
            row.update(cell.grasp_result_fields(result, "i1"))
            if result is not None:
                row["holding_F"] = bool(result.holding)

            reports = row["i2_reports"]
            row["stalled"] = reports[-1]["stalled"] if reports else None
            row["reached_goal"] = reports[-1]["reached_goal"] if reports else None

            q = cell.q_at(driver, stall_boundary)
            row["i3_q_at_stall_rad"] = q
            row["i3_drive_samples"] = len(driver.drive_q)
            if q is not None:
                row["i3_reached_width_m"] = predicate.width(q)

            # THE DECISION QUANTITIES COME FROM I1, which `criteria.md` section 2.1
            # defines as `w_reached` -- "the width the predicate consumes" -- and section
            # 4.1 names as `Grasp.Result.reached_width_m`. I3 is the same quantity read
            # INDEPENDENTLY of the skill server, which is a cross-check (V4) and not the
            # decision quantity; this harness had the two the wrong way round until
            # 2026-09-02. In this arm the joint is stalled on the part and the two agree
            # to about 0.03 mm, so it moves no number here -- but `d_wide` is what C1 is
            # decided on and rule W measures, and a decision quantity read off the
            # cross-check instrument is wrong whether or not it happens to agree.
            i1_reached = row.get("i1_reached_width_m")
            row["w_reached_source"] = "I1 (Grasp.Result.reached_width_m)"
            if i1_reached is not None:
                row["d_narrow_m"] = i1_reached - edge_lo
                row["d_wide_m"] = edge_hi - i1_reached
            if row.get("i3_reached_width_m") is not None:
                row["d_narrow_i3_m"] = row["i3_reached_width_m"] - edge_lo
                row["d_wide_i3_m"] = edge_hi - row["i3_reached_width_m"]
            row.update(common.v4(
                row.get("i1_reached_width_m"), row.get("i3_reached_width_m"),
                row.get("i2_reports")))
            row["i3_window_trace"] = cell.window_trace(
                driver, driver.closing_time, stall_boundary)

            # I4 (V3), and rule S-C's own instrument.
            row.update(recorder.summarise(since=driver.closing_time - 1.0))
            row["v3_contact_witnessed"] = bool(row.get("finger_contact_points_max"))

            # I5 -- the yaw AT THE STALL, off the pose stream, plus a probe afterwards.
            row.update(poses.summarise())
            first_contact = row.get("first_finger_contact_t")
            at_contact = poses.at_or_before(first_contact)
            at_stall = poses.at_or_before(stall_boundary)
            row["yaw_at_first_contact_rad"] = at_contact.yaw_rad if at_contact else None
            row["yaw_at_stall_rad"] = at_stall.yaw_rad if at_stall else None
            row["pose_at_stall"] = (
                {"x": at_stall.x, "y": at_stall.y, "z": at_stall.z, "t": at_stall.t}
                if at_stall else None)
            after = cell.model_pose(name)
            row["probe_after_close"] = after
            row["yaw_after_close_probe_rad"] = (after or {}).get("yaw_rad")
            for key in ("yaw_at_stall_rad", "yaw_after_close_probe_rad"):
                value = row.get(key)
                row[key.replace("_rad", "_deg")] = (
                    math.degrees(value) if value is not None else None)
            if row.get("yaw_at_stall_rad") is not None:
                row["presented_width_at_stall_m"] = presented_width_m(
                    cell.WORKPIECE_SIZE_M, row["yaw_at_stall_rad"])

            if superseded is not None and q is not None and row["stalled"] is not None:
                row["holding_S"] = superseded.holding(
                    WIDTH_M, q, bool(row["stalled"]), bool(row["reached_goal"]))
                row["holding_S_provenance"] = header["superseded"]
            else:
                row["holding_S"] = None
                row["holding_S_provenance"] = {"available": False}

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
            f"[{index}/{len(schedule)}] yaw={yaw_deg:.1f} deg "
            f"stall_yaw={row.get('yaw_at_stall_deg')} "
            f"w_reached(I1)={row.get('i1_reached_width_m')} "
            f"holding_F={row.get('holding_F')} d_wide={row.get('d_wide_m')} "
            f"({row['wall_s']}s)"
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
