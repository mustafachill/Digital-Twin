#!/usr/bin/env python3
"""AR arm — the two shipped derivations of one policy, on the same inputs.

`criteria.md` Q3 and D4. ADR-0052 section 5 records that the factor 2.0 is written in two
places, in two languages, each derived independently, neither reading the other, and that
they are **not even the same arithmetic**:

  * `cite_skills::gripper_width_tolerance_m` LINEARISES -- `|d(opening)/dq| * tolerance` --
    and is evaluated at the position the joint REACHED;
  * `cite_tools.validate.physical._grasp_discrimination_margin_m` takes an exact FINITE
    DIFFERENCE over `2 * goal_tolerance` of drive travel, at the position that was
    COMMANDED.

So the disagreement has TWO components and ADR-0052 reports only the first. This module
measures both, separately, and reports the total -- which is what the two production
implementations actually differ by.

Neither side is reimplemented here. The C++ side is `predicate_eval`, which compiles the
shipped `gripper.cpp`; the Python side is the shipped validator function, imported.

Runs on the HOST (it needs `.venv` and `cite_tools`) but shells into the container for
`predicate_eval`. Run it through `run_ar.sh`, which routes both halves.

    python3 measure_ar.py --out ../raw
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from cite_tools.model import loader  # noqa: E402
from cite_tools.validate import physical  # noqa: E402

END_EFFECTOR_ID = "xarm_parallel_gripper"

#: The commanded widths swept, in metres. `criteria.md` 5.3: 20.0 to 85.0 mm in 0.25 mm
#: steps, plus the four FN commands, the shipped default, and the validator's own ceiling.
#: Written as a function rather than a literal so that the registered rule is the code.
def swept_widths_m() -> list[float]:
    steps = [round(0.020 + i * 0.00025, 6) for i in range(int((0.085 - 0.020) / 0.00025) + 1)]
    named = [0.042, 0.045, 0.047, 0.048, 0.04786]
    return sorted(set(steps) | set(named))


def travel_from_plan(plan_path: Path) -> dict[str, float]:
    """The ten travel parameters, read from the GENERATED BRING-UP PLAN.

    Not from L0 directly and not from `predicate_eval`'s compiled defaults. The plan is
    what reaches the skill server (`cite_bringup.plan.GRIPPER_KEYS`), so it is what the
    predicate runs on in production. The header's defaults happen to equal these today,
    and `plan.py`'s own comment records that the server once ran on them by accident --
    "it worked, and it worked only because two copies agreed". A campaign that read the
    defaults would inherit that accident.
    """
    import yaml

    document = yaml.safe_load(plan_path.read_text())
    managers = document["plan"]["controller_managers"]
    entry = next(m for m in managers if m["asset"] == "arm_1")
    flat = {key: value for key, value in entry.items() if key.startswith("gripper_")}
    return {
        "open_position": float(flat["gripper_open_position"]),
        "closed_position": float(flat["gripper_closed_position"]),
        "drive_pivot_y_m": float(flat["gripper_drive_pivot_y_m"]),
        "drive_pivot_z_m": float(flat["gripper_drive_pivot_z_m"]),
        "finger_offset_y_m": float(flat["gripper_finger_offset_y_m"]),
        "finger_offset_z_m": float(flat["gripper_finger_offset_z_m"]),
        "pad_inset_m": float(flat["gripper_pad_inset_m"]),
        "tip_link_z_m": float(flat["gripper_tip_link_z_m"]),
        "pad_face_centre_z_m": float(flat["gripper_pad_face_centre_z_m"]),
        "goal_tolerance": float(flat["gripper_goal_tolerance_rad"]),
    }


class Cpp:
    """A batch conversation with `predicate_eval`, held open for the whole sweep."""

    def __init__(self, executable: list[str], travel: dict[str, float]) -> None:
        flags = [f"--{key}={value!r}" for key, value in travel.items()]
        self.command = executable + flags
        self.process = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1,
        )

    def ask(self, request: str) -> str:
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(request + "\n")
        self.process.stdin.flush()
        answer = self.process.stdout.readline()
        if not answer:
            raise RuntimeError(f"predicate_eval died answering {request!r}")
        return answer.strip()

    def width(self, q: float) -> float:
        return float(self.ask(f"width {q!r}"))

    def position(self, width_m: float) -> float:
        return float(self.ask(f"position {width_m!r}"))

    def tolerance(self, q: float) -> float:
        return float(self.ask(f"tolerance {q!r}"))

    def holding(self, commanded_m: float, q: float, stalled: bool, reached_goal: bool) -> bool:
        return self.ask(
            f"holding {commanded_m!r} {q!r} {int(stalled)} {int(reached_goal)}"
        ) == "1"

    def close(self) -> None:
        assert self.process.stdin
        self.process.stdin.close()
        self.process.wait(timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / ".." / "raw"))
    parser.add_argument(
        "--eval", default="", help="how to invoke predicate_eval; blank means through ./scripts/enter"
    )
    arguments = parser.parse_args()
    out = Path(arguments.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    plan_path = ROOT / "workspace" / "src" / "cite_generated" / "bringup" / "cell_a_plan.yaml"
    travel = travel_from_plan(plan_path)

    executable = arguments.eval.split() if arguments.eval else [
        str(Path(__file__).resolve().parent / "predicate_eval")
    ]
    cpp = Cpp(executable, travel)

    # The shipped validator side, on the shipped model.
    model = loader.load(ROOT / "model")
    asset_type = next(t for t in model.types if t.id == END_EFFECTOR_ID)
    grasp = asset_type.grasp
    assert grasp is not None, f"{END_EFFECTOR_ID} declares no grasp block"

    # Two independent reads of `goal_tolerance`, which is the value both derivations size
    # themselves from. If the plan and the validator's own reader disagree, every figure
    # below is about two different policies and the disagreement is not the one being
    # measured. Refuse rather than report.
    validator_tolerance = physical._gripper_goal_tolerance(asset_type)
    assert validator_tolerance == travel["goal_tolerance"], (
        f"the plan carries goal_tolerance={travel['goal_tolerance']} and the validator "
        f"reads {validator_tolerance} off the same model"
    )

    rows = []
    for width_m in swept_widths_m():
        q_cmd = cpp.position(width_m)
        cpp_at_cmd = 2.0 * cpp.tolerance(q_cmd)
        val_at_cmd = physical._grasp_discrimination_margin_m(asset_type, grasp, width_m)

        # The band edge, found by bisection on the SHIPPED predicate rather than on any
        # formula: the smallest reached width at which `gripper_is_holding` flips true.
        lo, hi = width_m, cpp.width(grasp.open_position)
        if not cpp.holding(width_m, cpp.position(hi), True, False):
            edge = math.nan
        else:
            for _ in range(60):
                mid = (lo + hi) / 2.0
                if cpp.holding(width_m, cpp.position(mid), True, False):
                    hi = mid
                else:
                    lo = mid
            edge = hi

        rows.append(
            {
                "w_cmd_m": width_m,
                "q_cmd_rad": q_cmd,
                "cpp_threshold_at_cmd_m": cpp_at_cmd,
                "validator_threshold_at_cmd_m": val_at_cmd,
                "linearisation_term_m": (val_at_cmd - cpp_at_cmd)
                if val_at_cmd is not None else None,
                "band_edge_reached_m": edge,
                "band_width_m": edge - width_m if edge == edge else None,
            }
        )

    # The EVALUATION-POINT term, which is the component ADR-0052 does not report. It is a
    # property of a (command, stall) pair rather than of a command, so it is computed over
    # the grid of the four FN commands crossed with a range of plausible stall widths --
    # and, in `analyse.py`, over the stalls the FN arm actually produced.
    evaluation_rows = []
    for w_cmd in (0.042, 0.045, 0.047, 0.048):
        val_at_cmd = physical._grasp_discrimination_margin_m(asset_type, grasp, w_cmd)
        for w_reached_mm in [round(x * 0.1, 4) for x in range(480, 505)]:
            w_reached = w_reached_mm / 1000.0
            if w_reached <= w_cmd:
                continue
            q_reached = cpp.position(w_reached)
            cpp_at_reached = 2.0 * cpp.tolerance(q_reached)
            evaluation_rows.append(
                {
                    "w_cmd_m": w_cmd,
                    "w_reached_m": w_reached,
                    "cpp_threshold_at_reached_m": cpp_at_reached,
                    "validator_threshold_at_cmd_m": val_at_cmd,
                    "total_disagreement_m": val_at_cmd - cpp_at_reached,
                    "cpp_holding": cpp.holding(w_cmd, q_reached, True, False),
                    "validator_would_hold": (w_reached - w_cmd) > val_at_cmd,
                }
            )

    # criteria.md 6.3: the sweep is run twice in one invocation and required to be
    # bit-identical, which is what makes "deterministic, no repeats needed" a check
    # rather than an assumption.
    repeat = []
    for width_m in swept_widths_m():
        q_cmd = cpp.position(width_m)
        repeat.append((2.0 * cpp.tolerance(q_cmd),
                       physical._grasp_discrimination_margin_m(asset_type, grasp, width_m)))
    identical = all(
        repeat[i][0] == rows[i]["cpp_threshold_at_cmd_m"]
        and repeat[i][1] == rows[i]["validator_threshold_at_cmd_m"]
        for i in range(len(rows))
    )

    cpp.close()

    document = {
        "arm": "AR",
        "travel_from_plan": travel,
        "validator_goal_tolerance": validator_tolerance,
        "predicate_eval_command": cpp.command,
        "second_pass_bit_identical": identical,
        "n_swept": len(rows),
        "sweep": rows,
        "evaluation_point_grid": evaluation_rows,
    }
    (out / "AR_arithmetic.json").write_text(json.dumps(document, indent=2))
    print(f"wrote {out / 'AR_arithmetic.json'}: {len(rows)} swept widths, "
          f"{len(evaluation_rows)} evaluation-point rows, "
          f"second pass bit-identical: {identical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
