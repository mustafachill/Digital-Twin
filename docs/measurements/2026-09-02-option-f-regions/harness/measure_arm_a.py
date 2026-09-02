#!/usr/bin/env python3
"""Arm A -- genuine free air on the PRODUCTION backend, across the commanded width.

`criteria.md` Q-A, section 5.1, thresholds A1 / A1a / A1b, rules N-A and R-A.

WHY THE LEVER IS THE COMMAND AND WHY NEITHER SUBSTITUTE RIG WILL DO. The 2026-09-01
campaign ran all thirty-nine of its false-positive trials at ONE commanded width, so the
command was never a lever there. It also established that `mock_components/GenericSystem`
fabricates a stall on a ramping joint after exactly `stall_timeout`, which is "a property
of mock hardware's dead velocity channel, not of the shipped backend" and may not be
counted as evidence about the production system in either direction -- so this arm runs on
the shipped cell, and `criteria.md` V7 discards a block that finds a mock. A synthetic
stop is refused too, for a different reason: under option F the verdict is a function of
`w_reached` alone, and a `JointStopSystem` stop PINS `w_reached` independently of the
command, so a stop-sweep rig cannot answer whether the verdict moves with the command. It
has to be the controller's own settle.

NOTHING IS BETWEEN THE PADS AND NO WORK-PIECE IS SPAWNED AT ALL.

I4 CANNOT EXIST IN THIS ARM, AND THAT IS RECORDED RATHER THAN PAPERED OVER. `criteria.md`
I4 is "a passive `gz.msgs.Contacts` sensor ON THE WORK-PIECE", whose job here is inverted:
it must witness NO contact. There is no work-piece to carry it. So V3's Arm A clause is
discharged by its SECOND half -- no work-piece exists in the world -- read through
`cite_bringup.gz` from the world itself, per trial, and every record says so in as many
words. A vacuous witness is not a witness, and this file will not report one as if it
were.

DERIVED FROM `docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fn.py`
(commit `eeaf903`) for the driver, the log cursor and the block shape. That directory is
frozen and nothing in it is edited from here.

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

#: `criteria.md` section 5.1 -- the registered coarse grid across the permitted range, at
#: 0.25 mm, in the order it is cycled. The shipped default (45.0) and the three named
#: points (46.5, 47.0, 47.5) and the largest grid point below the permitted ceiling
#: (47.85) are all already in it, which is why there is one list and not two.
COARSE_WIDTHS_MM = (
    45.00, 45.25, 45.50, 45.75, 46.00, 46.25, 46.50, 46.75,
    47.00, 47.25, 47.50, 47.75, 47.85,
)

#: The registered refinement STEP. The step is a threshold and is fixed here; the
#: INTERVAL is a bracket and is located by the coarse data, which is bracketing and not a
#: threshold chosen by the data (`criteria.md` section 5.1).
REFINE_STEP_MM = 0.05
REFINE_REPEATS = 3

#: How the jaws are returned to a known state between trials. Wide open, so every close
#: starts from the same place and the settle is the controller's own rather than a
#: function of where the previous trial left the joint.
RELEASE_MARGIN_M = 0.005


def _release_width(predicate: common.Predicate) -> float:
    return predicate.max_width() - RELEASE_MARGIN_M


def _schedule(cycles: int, refine: tuple[float, float] | None) -> list[tuple[int, float]]:
    if refine is None:
        return [(cycle, w) for cycle in range(cycles) for w in COARSE_WIDTHS_MM]
    low, high = refine
    points: list[float] = []
    steps = int(round((high - low) / REFINE_STEP_MM))
    for step in range(steps + 1):
        points.append(round(low + step * REFINE_STEP_MM, 4))
    return [(cycle, w) for cycle in range(REFINE_REPEATS) for w in points]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sim-log", required=True)
    parser.add_argument("--cycles", type=int, default=2,
                        help="complete passes over the coarse grid in this block")
    parser.add_argument("--refine-low-mm", type=float, default=None)
    parser.add_argument("--refine-high-mm", type=float, default=None)
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
    header = {
        "arm": "A",
        "question": "criteria.md Q-A -- free air on the production backend, across w_cmd",
        "provenance": common.provenance(),
        "host": common.host_facts(),
        "geometry": geometry,
        "travel": travel,
        "parts": parts,
        "window_m": {"edge_lo": edge_lo, "edge_hi": edge_hi},
        "default_grasp_width_m": default_width_m,
        "predicate_eval": predicate.describe(),
        "superseded": common.superseded_provenance(),
        "contact_witness": "criteria.md I4 is a sensor ON THE WORK-PIECE and this arm "
                           "spawns none, so I4 does not exist here. V3's Arm A clause is "
                           "discharged by its second half -- no work-piece in the world -- "
                           "read per trial from the world itself. A vacuous witness is "
                           "not a witness.",
        "gz_topics": [],
    }
    writer = common.TrialWriter(out, arguments.label, header)

    if not geometry["v2_ok"]:
        print("ABORT: the running description does not carry the shipped hull geometry "
              f"({geometry}). criteria.md V2 discards this block.")
        return 3
    # V7's Arm A clause: "Arm A may not be run on any mock backend (section 5.1); a block
    # that finds one is discarded, not reinterpreted." Until 2026-09-02 nothing here
    # asserted it -- the block checked the hull count and nothing else, so a mock backend
    # would have been measured and reported as the production one. That is not a
    # hypothetical failure for THIS arm: the 2026-09-01 campaign established that
    # `mock_components/GenericSystem` FABRICATES a stall on a ramping joint after exactly
    # `stall_timeout`, and a fabricated stall in free air is precisely the observation A1
    # would report as REPRODUCED.
    if not geometry["v7_ok"]:
        print("ABORT: criteria.md V7 -- the running description does not declare the "
              f"production backend, or declares a mock ({geometry}). Arm A may not be run "
              "on any mock backend; this block is DISCARDED, not reinterpreted.")
        return 3
    if not header["provenance"]["v1_clean"]:
        print("WARNING: V1 is NOT clean for this block; criteria.md V1 discards it.")

    refine = None
    if arguments.refine_low_mm is not None and arguments.refine_high_mm is not None:
        refine = (arguments.refine_low_mm, arguments.refine_high_mm)
    schedule = _schedule(arguments.cycles, refine)
    if arguments.shakedown:
        schedule = [(0, 45.00), (0, 47.85)]

    rclpy.init()
    driver = cell.Driver("option_f_arm_a_harness")
    driver.start_spinning()
    driver.await_stack()

    release_m = _release_width(predicate)
    header["release_width_m"] = release_m
    header["gz_topics"] = cell.gz_topics()
    writer.header = header
    (out / f"{arguments.label}_header.json").write_text(
        json.dumps(header, indent=2, default=str))

    homed = driver.go_home()
    print(f"homed: {homed}; release width {release_m * 1000:.2f} mm")

    for index, (cycle, width_mm) in enumerate(schedule, start=1):
        width_m = width_mm / 1000.0
        started = time.monotonic()
        driver.drive_q = []
        row: dict = {
            "trial": index,
            "cycle": cycle,
            "arm": "A",
            "condition": "refine" if refine else "coarse",
            "commanded_width_mm": width_mm,
            "commanded_width_m": width_m,
            "homed_at_block_start": homed,
        }
        # I6 -- whether this is a width a caller may ask for, from the SHIPPED function.
        # The permitted range is never taken from the 47.8769 mm in section 2.
        source, resolved = predicate.resolve(width_m, default_width_m)
        row["i6_source"] = source
        row["i6_resolved_width_m"] = resolved
        row["i6_margin_m"] = predicate.margin(width_m)
        row["i6_headroom_m"] = parts["narrowest_m"] - width_m - row["i6_margin_m"]

        try:
            # V3, first clause: no work-piece exists in the world at all. Read from the
            # world through `cite_bringup.gz`, because an unpartitioned probe returns an
            # empty list having reached no world and exits 0 -- which is the answer this
            # check wants, arrived at by not looking.
            models = cell.models_in_world()
            row["models_in_world"] = models
            # Deliberately broad. A leftover part from ANY campaign is still a part
            # between the pads, and a check that only recognised this campaign's own
            # naming would report a clean free-air trial with someone else's cube on
            # the table.
            row["v3_no_workpiece"] = not any(
                any(token in name.lower() for token in ("part", "piece", "workpiece"))
                for name in models)
            row["contact_witness"] = header["contact_witness"]
            row["finger_contact_points_max"] = None

            # Open first, so every close starts from the same place.
            cursor.mark()
            driver.do_grasp(release_m, expect_object=False)
            row["release_reports"] = cursor.collect()

            cursor.mark()
            opened_at = driver.sim_now()
            result = driver.do_grasp(width_m, expect_object=False)
            closed_at = driver.sim_now()
            # I2, WAITED FOR. The line is written by the skill server's process after it
            # sends the result, so sampling once here can miss a flush -- and an absent
            # line used to be indistinguishable from a measured `stalled=false`, which is
            # the exact boolean A1a counts. See `LogCursor.await_report`.
            row["i2_reports"] = cursor.await_report()
            row["i2_report_missing"] = not row["i2_reports"]
            row.update(cell.grasp_result_fields(result, "i1"))
            if result is None:
                raise RuntimeError("the skill server rejected or never answered the Grasp")

            row["holding_F"] = bool(result.holding)
            # I2's two booleans, which no result message carries. Exact WHEN PRESENT --
            # `None` here means the instrument produced no reading on this trial and the
            # trial is excluded from A1a, never counted as `false`.
            reports = row["i2_reports"]
            row["stalled"] = reports[-1]["stalled"] if reports else None
            row["reached_goal"] = reports[-1]["reached_goal"] if reports else None

            # I3 -- the drive joint's own sample, independently of the skill server.
            q = cell.q_at(driver, closed_at)
            row["i3_q_at_stall_rad"] = q
            row["i3_drive_samples"] = len(driver.drive_q)
            row["closing_window_sim_s"] = [opened_at, closed_at]
            if q is not None:
                row["i3_reached_width_m"] = predicate.width(q)

            # ---------------------------------------------------------------------
            # THE DECISION QUANTITIES, AND WHICH INSTRUMENT THEY COME FROM.
            #
            # `criteria.md` section 2.1 defines `w_reached` as "gripper_width_for(
            # reached_position), THE WIDTH THE PREDICATE CONSUMES", and section 4.1 makes
            # that I1 -- `Grasp.Result.reached_width_m`. I3 is the SAME quantity read
            # independently of the skill server, which section 4.1 provides as a
            # cross-check and which V4 is the rule over.
            #
            # This harness computed `d_narrow`, `d_wide` and A1b from I3 until 2026-09-02,
            # which inverted the two. In arms B, C and D the joint is stalled and they
            # agree to about 0.03 mm, so it changed nothing there. IN ARM A IT CHANGES THE
            # ANSWER: the joint is still ramping at the I3 instant, the two readings sit
            # ~0.57-0.61 mm apart in the shakedown, and the commanded width at which
            # `w_reached` crosses `edge_lo` moves from ~46.57 mm (I1, INSIDE the 46.554-
            # 46.766 mm bracket section 2.2 registered) to ~47.19 mm (I3, outside it) --
            # so the choice of instrument alone decides whether predictions P1 and P2 are
            # confirmed or refuted.
            #
            # `skill_server.cpp:2229-2236` is what settles it rather than this argument:
            # `outcome.reached_width_m` and `outcome.holding` are computed from the SAME
            # `wrapped.result->position`, so I1 is definitionally the value the predicate
            # consumed. The I3-derived pair is published beside it under its own keys --
            # V4 needs it, and the deviation has to be showable rather than asserted.
            # ---------------------------------------------------------------------
            i1_reached = row.get("i1_reached_width_m")
            row["w_reached_source"] = "I1 (Grasp.Result.reached_width_m)"
            if i1_reached is not None:
                row["d_narrow_m"] = i1_reached - edge_lo
                row["d_wide_m"] = edge_hi - i1_reached
                # A1b, on the width alone and independently of A1a's flags. This is the
                # clause that tests `gripper.hpp`'s sentence "It falls below it at every
                # command", and it is answered whatever the flags say.
                row["a1b_inside_window"] = edge_lo < i1_reached < edge_hi
            if row.get("i3_reached_width_m") is not None:
                row["d_narrow_i3_m"] = row["i3_reached_width_m"] - edge_lo
                row["d_wide_i3_m"] = edge_hi - row["i3_reached_width_m"]
                row["a1b_inside_window_i3"] = (
                    edge_lo < row["i3_reached_width_m"] < edge_hi)

            # V4, both halves, and the trace that explains an exclusion.
            row.update(common.v4(
                row.get("i1_reached_width_m"), row.get("i3_reached_width_m"),
                row.get("i2_reports")))
            row["i3_window_trace"] = cell.window_trace(driver, opened_at, closed_at)

            if superseded is not None and q is not None and row["stalled"] is not None:
                row["holding_S"] = superseded.holding(
                    width_m, q, bool(row["stalled"]), bool(row["reached_goal"]))
                row["holding_S_provenance"] = header["superseded"]
            else:
                row["holding_S"] = None
                row["holding_S_provenance"] = {"available": False}
            row["ok"] = True
        except Exception as exc:  # noqa: BLE001 -- a failed trial is a recorded trial
            row.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            print(f"    trial {index} failed: {exc}")

        row["wall_s"] = round(time.monotonic() - started, 1)
        writer.add(row)
        print(
            f"[{index}/{len(schedule)}] w_cmd={width_mm:.2f} mm I6={row.get('i6_source')} "
            f"w_reached(I1)={row.get('i1_reached_width_m')} "
            f"holding_F={row.get('holding_F')} "
            f"stalled={row.get('stalled')} reached_goal={row.get('reached_goal')} "
            f"({row['wall_s']}s)"
        )

    try:
        driver.do_grasp(release_m, expect_object=False)
    except Exception:  # noqa: BLE001
        pass
    driver.destroy_node()
    rclpy.shutdown()
    predicate.close()
    if superseded is not None:
        superseded.close()
    print(f"wrote {writer.path}: {len(writer.rows)} trials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
