#!/usr/bin/env python3
"""I8 -- the manifest of records a run should emit, written BEFORE the first trial.

ORIGINAL TO THIS CAMPAIGN. Nothing here is copied from another harness; the earlier
campaigns had no per-milestone record to count. The idea that a presence check is not
enough comes from `criteria.md` threat 12, which is this campaign's own.

WHY THIS FILE EXISTS AT ALL. `criteria.md` threat 10: deleting an `_emit_timing` call
passes the whole test suite. The guard at `tests/scenarios/guards/test_timing_records.py`
calls the emitter directly, so it proves what the writer writes and not that any
particular wait calls it -- its own docstring says "a wait that stops calling
`_emit_timing` is invisible here". A silently missing record must be detected as an ABSENT
EXPECTED KEY and never read as a zero, which is rule E.

WHY EVERY ENTRY CARRIES A COUNT AND NOT ONLY A PATTERN. Threat 12: one `what` pattern
stands for many records. `piece {n}: {milestone}` covers `WORKPIECES x len(ladder)`
records, and ONE SURVIVING LEG SATISFIES THE PATTERN -- so a presence-only check reports
nothing absent while a `LEG_CEILING_S` margin rests on 2 of 30 legs with no rule saying
so. Every entry is therefore reported `k of n`, and rule E requires that `k of n` to sit
in the same table cell as any margin computed from it.

EVERY COUNT BELOW IS DERIVED FROM SOURCE, NOT FROM A RUN. `criteria.md` section 11 is
explicit that no figure from the three pre-campaign scenario runs may appear anywhere in
this campaign; the counts here come from the emitters' own loops at `c38a42c`, from
`ARMS`, from `WORKPIECES` and from the generated topology, and would be the same numbers
if no scenario had ever been run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import yaml

#: The zone and the arms the emitters loop over, read from `tests/scenarios/bringup.py`
#: at `c38a42c` (`ZONE = "cell_a"`, `ARMS = ("arm_1", "arm_2", "arm_3")`).
ZONE = "cell_a"
ARM_COUNT = 3

#: `tests/scenarios/continuous_line.py:100` reads this from the environment, and
#: `scripts/_lib.sh` forwards every `CITE_`-prefixed host variable into the container. The
#: campaign runs it UNSET, so the default applies -- and the value in force is read from
#: the environment and recorded per run rather than assumed from this line
#: (`criteria.md` section 5).
DEFAULT_WORKPIECES = 3

#: The generated topology this campaign measures against. V1 forbids editing `model/`, so
#: it cannot move while the campaign runs; it is read rather than restated because the
#: ladder's length and the frame set are properties of the model and not of this file (P1).
TOPOLOGY = Path("workspace/src/cite_generated/topology/cell_a_flow.yaml")

#: The fallback, used only when the generated topology cannot be read. Derived by hand
#: from the same file on 2026-09-02, before the first trial, and stated so that a reader
#: can check the derivation without running anything: `flow_order` yields
#: infeed -> transfer_1 -> transfer_2 -> transfer_3 -> accumulation; the source
#: contributes nothing; each of the three transfer stations contributes `sensed`,
#: `lifted` and `on_link`; the sink contributes one `arrived`. 3 x 3 + 1 = 10.
#: The distinct frames `_resolve_envelope` places are the six non-empty milestone frames
#: plus one surface frame per belt, and the topology names three belts. 6 + 3 = 9.
DECLARED_LADDER_LENGTH = 10
DECLARED_CONTINUOUS_LINE_FRAMES = 9


@dataclass(frozen=True)
class Expected:
    """One (scenario, what-pattern, ceiling_s, expected_count) quadruple, plus its why.

    `ceiling_s` is part of the KEY and not decoration. `a transform from cite_world to
    {frame}` is emitted by all three scenarios under two ceiling names carrying two values
    -- 30.0 in `bringup` and 300.0 in the other two -- and a manifest keyed on the pattern
    alone would pool three intervals under one ceiling (`criteria.md` threat 11).
    """

    scenario: str
    ceiling_name: str
    ceiling_s: float
    pattern: re.Pattern[str]
    count: int
    why: str

    @property
    def key(self) -> tuple[str, str, float]:
        return (self.scenario, self.pattern.pattern, self.ceiling_s)

    def matches(self, record: dict) -> bool:
        """A record belongs to this entry only if BOTH the pattern and the ceiling agree.

        Reading `ceiling_s` off the record rather than inferring it from the `what` is
        `criteria.md` section 2.3's rule, and it is the whole reason the same transform
        string can appear three times in this manifest without pooling.
        """
        return (
            record.get("scenario") == self.scenario
            and float(record.get("ceiling_s", -1.0)) == self.ceiling_s
            and bool(self.pattern.match(str(record.get("what", ""))))
        )


def _ladder(root: Path) -> dict:
    """The ladder's length and the frame count, from the generated topology.

    Re-derived here rather than imported from `tests/scenarios/continuous_line.py`,
    because that module imports `launch_testing` and `rclpy` and this analyser runs on the
    host with neither. The derivation is the same one, restated in the docstring above and
    cross-checked at analysis time against the milestone descriptions the records
    themselves carry -- so a disagreement between this file and the emitter is REPORTED
    rather than silently believed.

    A topology that cannot be read falls back to the declared constants, and the record
    says which route was taken. It is not an error: `criteria.md` V1 pins the model, so
    the two agree by construction while the campaign is valid.
    """
    path = root / TOPOLOGY
    try:
        topology = yaml.safe_load(path.read_text())["topology"]
    except (OSError, KeyError, yaml.YAMLError):
        return {
            "source": "declared",
            "ladder_length": DECLARED_LADDER_LENGTH,
            "frames": DECLARED_CONTINUOUS_LINE_FRAMES,
            "note": f"{path} could not be read; the section 2.1 derivation is used",
        }
    stations = {station["id"]: station for station in topology["stations"]}
    order = [station for station in topology["stations"] if not station.get("upstream")]
    chain: list[dict] = []
    station = order[0] if order else None
    while station is not None:
        chain.append(station)
        downstream = station.get("downstream") or []
        station = stations[downstream[0]] if len(downstream) == 1 else None

    def via(upstream: str, downstream: str) -> str:
        for edge in topology["edges"]:
            if edge["from"] == upstream and edge["to"] == downstream:
                return edge.get("via") or ""
        return ""

    length = 0
    frames: set[str] = set()
    belts: set[str] = set()
    for index, entry in enumerate(chain):
        topic = (entry.get("trigger") or {}).get("topic", "")
        if not entry.get("actor"):
            if index and topic:
                length += 1
            continue
        if topic:
            length += 1
        length += 2
        frames.add(entry["pick_frame"])
        frames.add(entry["place_frame"])
        downstream = (entry.get("downstream") or [""])[0]
        link = via(entry["id"], downstream)
        if link:
            belts.add(link)
    return {
        "source": "generated topology",
        "ladder_length": length,
        # `_resolve_envelope` places every non-empty milestone frame and one surface frame
        # per belt it rides, and `_resolve` caches, so the record count is the size of the
        # union rather than the number of calls.
        "frames": len(frames) + len(belts),
        "note": str(path),
    }


def manifest(root: Path, workpieces: int = DEFAULT_WORKPIECES) -> tuple[list[Expected], dict]:
    """The whole manifest, and the derivation it rests on.

    `workpieces` is passed in rather than read here: `continuous_line` takes it from the
    environment at run time, the runner records the value that was actually in force, and
    a manifest that assumed the default would report a wrong `n` for a run that did not
    use it.
    """
    ladder = _ladder(root)
    arm = r"arm_[1-3]"
    entries = [
        # ---- bringup ----------------------------------------------------------
        Expected(
            "bringup",
            "BRING_UP_CEILING_S",
            240.0,
            re.compile(rf"^/cite/{ZONE}/{arm}/controller_manager to appear$"),
            ARM_COUNT,
            "test_every_controller_reaches_active loops over ARMS",
        ),
        Expected(
            "bringup",
            "BRING_UP_CEILING_S",
            240.0,
            re.compile(rf"^{arm}'s controllers to be active$"),
            ARM_COUNT,
            "the same loop, one per arm",
        ),
        Expected(
            "bringup",
            "BRING_UP_CEILING_S",
            240.0,
            re.compile(rf"^/cite/{ZONE}/arm_1/arm_1_gripper_controller/gripper_cmd$"),
            1,
            "test_the_gripper_linkage_is_actually_coupled, ARMS[0] only",
        ),
        Expected(
            "bringup",
            "BRING_UP_CEILING_S",
            240.0,
            re.compile(
                rf"^/cite/{ZONE}/arm_1/arm_1_joint_trajectory_controller/"
                rf"follow_joint_trajectory$"
            ),
            1,
            "test_a_trajectory_executes, ARMS[0] only",
        ),
        Expected(
            "bringup",
            "BRING_UP_CEILING_S",
            240.0,
            re.compile(r"^the arm_1 skill server$"),
            1,
            "test_a_skill_moves_the_arm_to_its_home_configuration -- rule A's only "
            "contributing what",
        ),
        Expected(
            "bringup",
            "DELIVERY_CEILING_S",
            30.0,
            re.compile(rf"^a message on /cite/{ZONE}/{arm}/joint_states$"),
            2 * ARM_COUNT,
            "TWO test methods each loop over ARMS and emit the identical what: "
            "test_joint_states_are_actually_delivered and "
            "test_no_joint_name_is_shared_between_arms",
        ),
        Expected(
            "bringup",
            "DELIVERY_CEILING_S",
            30.0,
            re.compile(rf"^a joint state after the gripper closed on /cite/{ZONE}/arm_1/joint_states$"),
            1,
            "test_the_gripper_linkage_is_actually_coupled",
        ),
        Expected(
            "bringup",
            "DELIVERY_CEILING_S",
            30.0,
            re.compile(r"^the model version$"),
            1,
            "test_the_facility_publishes_its_model_version",
        ),
        Expected(
            "bringup",
            "DELIVERY_CEILING_S",
            30.0,
            re.compile(r"^a transform from cite_world to \S+$"),
            4,
            "test_station_frames_resolve_against_the_world loops over four named frames. "
            "The identical what appears in the other two scenarios under a DIFFERENT "
            "ceiling, which is why ceiling_s is part of the key",
        ),
        Expected(
            "bringup",
            "TRAJECTORY_CEILING_S",
            60.0,
            re.compile(r"^the gripper goal to be accepted$"),
            1,
            "_await_future in test_the_gripper_linkage_is_actually_coupled",
        ),
        Expected(
            "bringup",
            "TRAJECTORY_CEILING_S",
            60.0,
            re.compile(r"^the gripper to report a result$"),
            1,
            "the same test",
        ),
        Expected(
            "bringup",
            "TRAJECTORY_CEILING_S",
            60.0,
            re.compile(r"^the trajectory goal to be accepted$"),
            1,
            "_await_future in test_a_trajectory_executes",
        ),
        Expected(
            "bringup",
            "TRAJECTORY_CEILING_S",
            60.0,
            re.compile(r"^the trajectory to return a result$"),
            1,
            "the same test",
        ),
        Expected(
            "bringup",
            "TRAJECTORY_CEILING_S",
            60.0,
            re.compile(r"^the MoveTo goal to be accepted$"),
            1,
            "_await_future in test_a_skill_moves_the_arm_to_its_home_configuration",
        ),
        Expected(
            "bringup",
            "SKILL_CEILING_S",
            120.0,
            re.compile(r"^MoveTo to return a result$"),
            1,
            "the file's ONLY SKILL_CEILING_S call site, on ARMS[0]. A band here can rest "
            "on n = 1 per run and section 7.2 requires that to be printed",
        ),
        # ---- pick_and_place ---------------------------------------------------
        Expected(
            "pick_and_place",
            "BRING_UP_CEILING_S",
            300.0,
            re.compile(r"^the skill server, and therefore the whole stack beneath it$"),
            1,
            "the COLD bring-up wait. Section 7.2 reports it separately from the warm "
            "transform lookups under the same ceiling, and the cold one is the headline",
        ),
        Expected(
            "pick_and_place",
            "BRING_UP_CEILING_S",
            300.0,
            re.compile(r"^a transform from cite_world to \S+$"),
            2,
            "_resolve is called for PICK_FRAME and PLACE_FRAME. WARM: the stack is "
            "already up by then",
        ),
        Expected(
            "pick_and_place",
            "SETTLE_CEILING_S",
            60.0,
            re.compile(r"^the work-piece to settle$"),
            1,
            "the seventh ceiling. Its predicate shells out to `gz model -p`, so PR3 "
            "predicts every instance is discarded by rule Z",
        ),
        Expected(
            "pick_and_place",
            "CYCLE_CEILING_S",
            420.0,
            re.compile(r"^the station cycle to run to completion$"),
            1,
            "_run_cycle's only emit. Rule X admits it only from runs whose verdict passed",
        ),
        # ---- continuous_line --------------------------------------------------
        Expected(
            "continuous_line",
            "BRING_UP_CEILING_S",
            300.0,
            re.compile(r"^the first LineState, and so the line coordinator and the stack below it$"),
            1,
            "the COLD bring-up wait, reported separately from the warm ones",
        ),
        Expected(
            "continuous_line",
            "BRING_UP_CEILING_S",
            300.0,
            re.compile(r"^L4 to command every belt to a non-zero setpoint \(ADR-0032\)"),
            1,
            "one wait over every conveyor at once",
        ),
        Expected(
            "continuous_line",
            "BRING_UP_CEILING_S",
            300.0,
            re.compile(r"^a transform from cite_world to \S+$"),
            ladder["frames"],
            "_resolve_envelope places every ladder frame and every belt surface once; "
            "_resolve caches, so the count is the size of the union",
        ),
        Expected(
            "continuous_line",
            "LEG_CEILING_S",
            420.0,
            re.compile(r"^the work-piece '\S+' to settle on the pick surface$"),
            workpieces,
            "one per piece fed. NOT a leg: section 2.3 excludes it from the margin",
        ),
        Expected(
            "continuous_line",
            "LEG_CEILING_S",
            420.0,
            re.compile(r"^the work-piece '\S+' to leave the simulator$"),
            workpieces,
            "one per piece removed. NOT a leg: section 2.3 excludes it from the margin",
        ),
        Expected(
            "continuous_line",
            "LEG_CEILING_S",
            420.0,
            re.compile(r"^piece \d+: "),
            workpieces * ladder["ladder_length"],
            "THE ONLY LEG. One record per piece per milestone. Threat 12: one surviving "
            "leg satisfies the pattern, so this entry is what makes partial loss visible",
        ),
    ]
    derivation = {
        "workpieces": workpieces,
        "arm_count": ARM_COUNT,
        "ladder": ladder,
        "entries": len(entries),
        "records_at_full_completion": sum(entry.count for entry in entries),
    }
    return entries, derivation


#: `criteria.md` rule A. The one `what` in `bringup.py` that contributes to that file's
#: `BRING_UP_CEILING_S` margin, and the test whose alphabetical primacy the rule assumes.
#: If the observed first test is not this one, rule A's premise has failed and the ceiling
#: is reported NOT ASSESSED under D3 rather than silently re-keyed.
RULE_A_WHAT = "the arm_1 skill server"
RULE_A_FIRST_TEST = "test_a_skill_moves_the_arm_to_its_home_configuration"

#: Section 2.3. `LEG_CEILING_S` is used in three places and only one of them is a leg.
#: Keyed on the `what` PREFIX, which is what the criteria registers.
LEG_WHAT_PREFIX = "piece "

#: Section 7.2. The two ceilings whose emitters have a single call site, so a band can
#: rest on n = 1 and must be printed saying so.
SINGLE_SITE_CEILINGS = (
    ("bringup", "SKILL_CEILING_S"),
    ("pick_and_place", "CYCLE_CEILING_S"),
)

#: Section 7.2. The cold bring-up `what` in each of the two scenarios whose
#: `BRING_UP_CEILING_S` also covers warm transform lookups. The headline verdict for those
#: ceilings is the COLD one; the warm line is published beside it and never softens it.
COLD_BRING_UP_WHAT = {
    "pick_and_place": "the skill server, and therefore the whole stack beneath it",
    "continuous_line": (
        "the first LineState, and so the line coordinator and the stack below it"
    ),
}
