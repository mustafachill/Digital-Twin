#!/usr/bin/env python3
"""What the runner and the analyser share: the registered constants, provenance, and the record.

DERIVED FROM two frozen directories, and both are named because the two halves came from
different places:

  * `docs/measurements/2026-09-03-stall-band-flip/harness/common.py`, copied at commit
    `8a35a03`, the commit that file last landed at -- the two-ended `snapshot` / `v1` pair,
    `model_hash`, `host_load`, `host_facts`, `v7`, `running_geometry`, `TrialWriter`,
    `LogCursor`, `wilson`, and the
    "provenance travels on every record" shape.
  * `docs/measurements/2026-09-02-option-f-regions/harness/common.py`, copied at commit
    `ac11d84` -- the `LogCursor` bracketing pattern that campaign in turn inherited, and
    the `repo_root` resolution from this file's own location.

Both directories are FROZEN (`docs/measurements/README.md` rule 2) and nothing in either is
edited from here. **No campaign imports from another**: this is a copy, and the header says
so.

WHY ONE MODULE RATHER THAN A COPY PER RUNNER. Inside one campaign a value in two places is
still a value in two places (P1). V1 discards a block, and a discard rule implemented twice
is two rules.

WHAT THIS MODULE MAY NOT DO. It sets no threshold of its own. Every number below is quoted
from `criteria.md` with the section that registers it, or is read from the tree at run time.
Nothing here is derived from data, because there is no data when this file is written.

THE TWO-ENDED READING, AND WHY THE ROWS ARE SEALED RATHER THAN STAMPED. `criteria.md` V1
requires `v1_clean` to be the CONJUNCTION of two `git` readings taken at both ends of the
block, and requires the flag to travel ON the record. A block lasts many minutes and its
rows are written as its trials finish, so the closing reading does not exist yet when a row
is written. `TrialWriter.seal` is what reconciles those two facts: every row carries
`v1_clean = None` until the closing reading is taken -- at the end of the block, or as the
FIRST act of the abort path -- and is then rewritten with the conjunction. A harness that
died without sealing leaves rows carrying `None`, which `analyse.py` drops and reports as a
lost block, exactly as V1 registers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"


def repo_root() -> Path:
    """The repository this harness is published inside.

    Resolved from this file's own location rather than from the working directory, because
    the campaign directory is four levels down and the runners are invoked from the
    repository root on the host and from `/workspace` in the container.
    """
    return HERE.parents[3]


# ---------------------------------------------------------------------------
# The cell, and the tree the campaign is a property of
# ---------------------------------------------------------------------------

#: `criteria.md` section 5.2. The zone, and the arm every decision quantity is taken on.
ZONE = "cell_a"
ARM = "arm_1"

#: `criteria.md` section 3. CONC's load arms. They are LOAD and no verdict is stated about
#: them (rule T), so they are named apart from `ARM` and never mixed into it.
LOAD_ARMS = ("arm_2", "arm_3")

#: `criteria.md` section 3's amendment, quoting `cite_generated/topology/cell_a_flow.yaml`.
#: The load motion is CRUISE's shape on each load arm's OWN frames, because the shipped
#: `MoveTo` refuses every named configuration but `home` and the first registration of this
#: campaign asked for `hold-up`. Read from the generated topology at run time rather than
#: written here -- these are the station frames, and a value in two places is the defect P1
#: names. This tuple names only WHICH station belongs to which arm.
LOAD_STATIONS = {"arm_2": "station_transfer_2", "arm_3": "station_transfer_3"}

#: `criteria.md` section 5.2. Arm CRUISE's, FAST's and CONC's two goal frames, and CARRY's
#: pick and place frames. `station_transfer_1` is arm_1's station in the generated topology;
#: the two frames are read back from it at run time and asserted against these, so that a
#: topology edit is a loud failure rather than a silently different motion.
PICK_FRAME = "cell_a__table_pick__surface"
PLACE_FRAME = "cell_a__conveyor_1__infeed"
ARM_STATION = "station_transfer_1"

#: `criteria.md` preamble and V1. Every figure is a property of the tree at this commit.
BASE_COMMIT = "c38a42c"

#: `criteria.md` V1, as amended on 2026-09-04 before any trial: SEVEN paths, not five.
#: `docs/measurements/` is deliberately NOT watched -- this campaign's own `criteria.md`,
#: harness and raw all land on this branch, so `HEAD` necessarily advances while it runs and
#: pinning it would discard every block including the first.
V1_WATCHED_PATHS = (
    "model/",
    "workspace/src/",
    "tools/",
    "tests/",
    "scripts/",
    "assets/",
    "external/",
)

#: `criteria.md` preamble and V1. The vendor half of the tree is gitignored and holds no
#: tracked file, so no `git diff` over it can ever report anything; it is pinned by SHA
#: instead. The SHA is READ FROM `external/cite.repos` rather than written here, because
#: that manifest is where the pin lives (P1) and a literal typed here would be a second
#: copy that could disagree with it silently.
VENDOR_CHECKOUT = "workspace/src/external/xarm_ros2"
VENDOR_MANIFEST = "external/cite.repos"
VENDOR_MANIFEST_KEY = "external/xarm_ros2"

#: `criteria.md` V2. The collision-mesh reference the description the rig publishes must
#: carry, and how many of them, for the shipped `convex_hull` selection (ADR-0028). The
#: count is the criteria's; the STRING is the one the 2026-09-01, 2026-09-02 and 2026-09-03
#: rigs counted, kept so that the campaigns count the same thing.
HULL_COLLISION_REFERENCE = "cite_description/meshes/collision/xarm5/convex_hull"
HULL_COLLISION_REFERENCES_EXPECTED = 13

#: `criteria.md` V3 -- THE MOST IMPORTANT RULE IN THIS CAMPAIGN. Mock hardware mirrors
#: commands into states and produces a following error of exactly zero, so a rig that
#: silently ran on it would produce a perfect, perfectly meaningless silence. The two
#: substitutes are named so that finding one is a POSITIVE reading rather than the absence
#: of the production plugin.
PRODUCTION_PLUGIN = "gz_ros2_control/GazeboSimSystem"
FIXTURE_PLUGIN = "cite_test_hardware/JointStopSystem"
MOCK_PLUGIN = "mock_components/GenericSystem"

# ---------------------------------------------------------------------------
# I1 and I2 -- the decision quantity's topic, and the QoS the subscription declares
# ---------------------------------------------------------------------------

#: `criteria.md` I1. The controller's own `state_error_` buffer, published at the end of
#: every `update()`.
def controller_state_topic(arm: str) -> str:
    return f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller/controller_state"


def joint_states_topic(arm: str) -> str:
    """`criteria.md` I4 -- the joint positions from a SECOND publisher."""
    return f"/cite/{ZONE}/{arm}/joint_states"


#: `criteria.md` section 2.1, read from the generated controller configuration. Declared
#: here as the value this campaign was registered against; `controller_settings` below reads
#: the same quantities off the shipped file at run time and `measure.py` records BOTH, so a
#: generated value that has moved since registration is visible on every record instead of
#: being assumed.
DECLARED_TRAJECTORY_TOLERANCE_RAD = 1.0
DECLARED_GOAL_TOLERANCE_RAD = 0.01
DECLARED_GOAL_TIME_S = 0.5
DECLARED_UPDATE_RATE_HZ = 150.0

#: `criteria.md` section 2.2. The plant's rate constant, the controller manager's rate, and
#: the coefficient that turns a joint speed into a steady-state REPORTED error. The
#: coefficient is `1/k - 1/R` and NOT `1/k`: the controller samples the command one
#: `update_period_` ahead of the reference the error is measured against, and omitting that
#: term made every peak this campaign registered 10 % high until 2026-09-04.
PLUGIN_GAIN = 0.1
K_PER_S = PLUGIN_GAIN * DECLARED_UPDATE_RATE_HZ
R_HZ = DECLARED_UPDATE_RATE_HZ
ERROR_PER_SPEED_S = (1.0 / K_PER_S) - (1.0 / R_HZ)

#: `criteria.md` section 7.3 -- one sample interval, the resolution below which a measured
#: settle carries no information.
SAMPLE_INTERVAL_S = 1.0 / R_HZ

# ---------------------------------------------------------------------------
# `criteria.md` section 7.0 -- every registered size, with the section that registers it
# ---------------------------------------------------------------------------

#: ADR-0036's own criterion, "at least an order of magnitude below
#: `trajectory_tolerance_rad`", against the declared 1.0 rad. BAND1's line.
PATH_TOLERANCE_LINE_RAD = 0.100

#: Half the declared `goal_time`. GOAL1's line.
GOAL_SETTLE_LINE_S = 0.25

#: Half the declared per-joint `goal` tolerance. The minimum interesting difference for any
#: following error, spent by CONC1 and by rule R.
MIS_RAD = 0.005

#: Rule X's stress speed: `0.100 / (1/k - 1/R)`, DERIVED and not chosen. Recomputed here
#: from the two constants above rather than typed, so that it cannot disagree with them.
STRESS_SPEED_RAD_S = PATH_TOLERANCE_LINE_RAD / ERROR_PER_SPEED_S

#: V5's identity tolerance. An arithmetic identity on one message in double precision.
V5_IDENTITY_RAD = 1e-9

#: Rule L's four clauses.
L_I_MIN_SAMPLES = 100
L_II_MIN_RATE_PER_SIM_S = 20.0
L_III_NONZERO_ERROR_RAD = 0.001
L_IV_CONSISTENCY_SHARE = 0.99

#: Rule L's instrument-loss ceiling, a judgement and recorded as one.
L_LOSS_CEILING_SHARE = 0.20

#: V7's load flag: one quarter of the core count. It FLAGS and never excludes.
V7_LOAD_THRESHOLD = 4.0

#: Rule D's agreement band, as a fraction of `v_peak * (1/k - 1/R)`.
RULE_D_BAND = 0.25

# ---------------------------------------------------------------------------
# I3 -- the three readings, and the patterns that carry (b) and (c)
# ---------------------------------------------------------------------------

#: I3(b). `tolerances.hpp:319`, on the logger `tolerances`. It fires for BOTH checks and so
#: reports an event WITHOUT NAMING WHICH -- and, in this cell, WITHOUT NAMING WHOSE. All three
#: controller managers live inside the `gz` process and share one `tolerances` logger, whose
#: line carries no arm at all: `[gz-1] [ERROR] [ts] [tolerances]: State tolerances failed for
#: joint 4:`. The shakedown of 2026-09-04 observed arm_3 violating its path tolerance while
#: arm_1 was mid-goal under CONC, and an unattributed scrape recorded that as arm_1's event --
#: which is the campaign's HEADLINE verdict, manufactured out of a load arm. `scrape_i3` below
#: is what attributes it.
TOLERANCE_EVENT_LINE = re.compile(r"State tolerances failed for joint (\d+)")

#: I3(c), the discriminating lines. The first two are the controller's own warnings
#: (`joint_trajectory_controller.cpp:469` and `:504`/`:516`); the third is move_group's
#: (`follow_joint_trajectory_controller_handle.cpp:240-242`), which renders the code.
PATH_ABORT = re.compile(r"Aborted due to state tolerance violation")
GOAL_TIME_ABORT = re.compile(r"Aborted due to goal_time_tolerance exceeding by\s*([-+0-9.eE]*)")
MOVEIT_ABORT = re.compile(
    r"Controller '([^']*)' failed with error (PATH_TOLERANCE_VIOLATED|GOAL_TOLERANCE_VIOLATED)"
)

#: Which arm a controller line belongs to. The trajectory controller logs under its own fully
#: qualified node name, `cite.<zone>.<arm>.<arm>_joint_trajectory_controller`, and that is the
#: only thing in the launch log that says WHOSE an abort is.
CONTROLLER_LOGGER = re.compile(r"\[cite\.[^.\]]+\.(arm_\d+)\.arm_\d+_joint_trajectory_controller\]")

#: How many lines after an I3(b) line the attributing controller warning is looked for.
#: `check_state_tolerance_per_joint` emits the header line, then one `Position Error:` line per
#: violating joint, and the caller then emits its own warning on the controller's logger --
#: within the same `update()` and therefore within a handful of interleaved log lines. Eight
#: admits every arrangement the shakedown produced without reaching the next event. A line the
#: window does not attribute is recorded as UNATTRIBUTED and is never silently assigned.
I3B_ATTRIBUTION_WINDOW_LINES = 8

#: How much of a goal's log segment is published when any of the above fires. Bounded so
#: that one noisy trial cannot make a block's raw file unreadable, and generous enough that
#: the whole error trace `criteria.md` section 5.3 demands is inside it.
LOG_SEGMENT_CAP_CHARS = 20000


def scrape_i3(text: str, arm: str) -> dict:
    """I3(b) and I3(c) over one goal's segment of the block log, ATTRIBUTED TO ONE ARM.

    Returns a POSITIVE finding or an explicit absence, never a silence.

    **WHY ATTRIBUTION IS THE WHOLE OF THIS FUNCTION, and it is a shakedown finding.** Under
    CONC three arms are commanded at once and every one of them logs into the same launch log.
    The 2026-09-04 shakedown caught `arm_3` violating its own path tolerance -- a real event,
    `Position Error: -1.071717, Position Tolerance: 1.000000` -- while `arm_1` was mid-goal,
    and an unattributed scrape recorded it against `arm_1`'s trial. That is QUIET1 = FIRED, the
    campaign's headline verdict, manufactured out of a load arm about which rule T says no
    verdict is stated at all.

    **I3(c) is attributable and is filtered.** Both controller warnings carry the arm in their
    logger name and move_group's carries the controller's name.

    **I3(b) is NOT attributable on its own line** -- the `tolerances` logger is shared by every
    controller manager in the `gz` process and its line names no arm. It is attributed by the
    controller warning that follows it within `I3B_ATTRIBUTION_WINDOW_LINES`, which is the
    caller that emitted it. An event the window cannot attribute is counted as
    **unattributed** and is treated as POSSIBLY THIS ARM'S: it sets `i3_any_log_event`, so it
    can only make a QUIET claim harder and never easier.

    Everything belonging to another arm is kept in `i3_other_arm_events` rather than dropped --
    reported, and not a finding about this arm (rule T).
    """
    lines = text.splitlines()
    controller = f"{arm}_joint_trajectory_controller"

    def line_arm(line: str) -> str | None:
        match = CONTROLLER_LOGGER.search(line)
        return match.group(1) if match else None

    b_this: list[int] = []
    b_other: list[dict] = []
    b_unattributed: list[int] = []
    for index, line in enumerate(lines):
        match = TOLERANCE_EVENT_LINE.search(line)
        if not match:
            continue
        joint = int(match.group(1))
        owner = None
        for offset in range(1, I3B_ATTRIBUTION_WINDOW_LINES + 1):
            if index + offset >= len(lines):
                break
            candidate = lines[index + offset]
            if PATH_ABORT.search(candidate) or GOAL_TIME_ABORT.search(candidate):
                owner = line_arm(candidate)
                break
        if owner == arm:
            b_this.append(joint)
        elif owner is None:
            b_unattributed.append(joint)
        else:
            b_other.append({"arm": owner, "joint": joint})

    path_aborts = [line for line in lines if PATH_ABORT.search(line) and line_arm(line) == arm]
    goal_time = [
        {"arm": arm, "by_seconds": GOAL_TIME_ABORT.search(line).group(1)}
        for line in lines
        if GOAL_TIME_ABORT.search(line) and line_arm(line) == arm
    ]
    moveit: list[dict] = []
    moveit_other: list[dict] = []
    for line in lines:
        match = MOVEIT_ABORT.search(line)
        if not match:
            continue
        entry = {"controller": match.group(1), "code": match.group(2)}
        (moveit if match.group(1) == controller else moveit_other).append(entry)

    other = {
        "i3b_events": b_other,
        "i3c_path_aborts": [
            line_arm(line)
            for line in lines
            if PATH_ABORT.search(line) and line_arm(line) not in (arm, None)
        ],
        "i3c_moveit_aborts": moveit_other,
    }
    any_other = bool(other["i3b_events"] or other["i3c_path_aborts"] or moveit_other)

    fired = bool(b_this or b_unattributed or path_aborts or goal_time or moveit)
    return {
        "i3_arm": arm,
        "i3b_tolerance_event_joints": b_this,
        "i3b_tolerance_events": len(b_this),
        "i3b_unattributed_joints": b_unattributed,
        "i3b_unattributed": len(b_unattributed),
        "i3c_path_aborts": len(path_aborts),
        "i3c_goal_time_aborts": goal_time,
        "i3c_moveit_aborts": moveit,
        "i3_any_log_event": fired,
        # Rule T. Another arm's event is REPORTED and is not a finding about this one.
        "i3_other_arm_events": other if any_other else None,
        # Published only when something fired for THIS arm, because it is the trace section 5.3
        # requires beside the event and is otherwise a copy of the whole launch log.
        "i3_log_segment": text[-LOG_SEGMENT_CAP_CHARS:] if fired else None,
    }


# ---------------------------------------------------------------------------
# V1, V2, V3 and I7 -- the code, the model and the description that actually ran
# ---------------------------------------------------------------------------
def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return f"<git {' '.join(arguments)} failed rc={result.returncode}: {result.stderr.strip()}>"
    return result.stdout.rstrip("\n")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_vendor_sha(root: Path | None = None) -> str | None:
    """The SHA `external/cite.repos` pins for `xarm_ros2`, read out of the manifest.

    Read rather than written, because the manifest is where the pin lives (P1). Parsed with
    a regular expression rather than with `yaml`, so that this module carries no import a
    ROS-less host cannot satisfy: `analyse.py` runs anywhere and reads this same field off
    the records it is checking.
    """
    root = root or repo_root()
    path = root / VENDOR_MANIFEST
    if not path.exists():
        return None
    text = path.read_text()
    index = text.find(VENDOR_MANIFEST_KEY + ":")
    if index < 0:
        return None
    match = re.search(r"version:\s*([0-9a-f]{40})", text[index:])
    return match.group(1) if match else None


def vendor_pin(root: Path | None = None) -> dict:
    """V1's second clause -- the vendor tree is pinned by SHA and cannot be watched by diff.

    That tree is where `velocity="3.14"` lives, and section 2.2's two peak predictions are
    computed from it. Both halves are POSITIVE readings: `matches` is false when either is
    missing, so "no disagreement found" is never reachable by not looking.
    """
    root = root or repo_root()
    pinned = manifest_vendor_sha(root)
    checkout = root / VENDOR_CHECKOUT
    imported = _git(checkout, "rev-parse", "HEAD") if checkout.exists() else None
    return {
        "manifest": VENDOR_MANIFEST,
        "pinned_sha": pinned,
        "imported_sha": imported,
        "imported_from": str(checkout),
        "matches": bool(pinned) and bool(imported) and pinned == imported,
    }


def model_hash(root: Path | None = None) -> dict:
    """The MODEL_HASH of the generated tree, and of the INSTALLED package if there is one.

    Two readings rather than one, because they answer different questions. The source tree's
    says which model the repository describes; the installed one says which model the rig
    that is about to run was built from. A block taken against a stale install is a block
    about a cell nobody committed, and the pair is what makes that visible.
    """
    root = root or repo_root()
    source = root / "workspace" / "src" / "cite_generated" / "MODEL_HASH"
    installed = (
        root / "workspace" / "install" / "cite_generated" / "share" / "cite_generated"
        / "MODEL_HASH"
    )
    return {
        "source": source.read_text().strip() if source.exists() else None,
        "installed": installed.read_text().strip() if installed.exists() else None,
    }


def snapshot(root: Path | None = None) -> dict:
    """I7, ONE reading. V1 needs two of these and conjoins them."""
    root = root or repo_root()
    diff = _git(root, "diff", "--name-only", f"{BASE_COMMIT}..HEAD", "--", *V1_WATCHED_PATHS)
    dirty = _git(root, "status", "--porcelain", "--", *V1_WATCHED_PATHS)
    pin = vendor_pin(root)
    return {
        "at": time.time(),
        "head": _git(root, "rev-parse", "HEAD"),
        "git_status_porcelain": _git(root, "status", "--porcelain"),
        "watched_diff_against_base": diff,
        "watched_worktree_dirty": dirty,
        "vendor_pin": pin,
        "clean": diff == "" and dirty == "" and pin["matches"],
        "model_hash": model_hash(root),
        # V1 deliberately does not watch `docs/`, so the `criteria.md` this campaign is a
        # property of lies OUTSIDE every path V1 reads -- and V9 says nothing in it changes
        # once the first trial has run. This hash is the only instrument that could notice
        # one that did. It is taken HERE so that it travels at BOTH ENDS of every block and
        # an edit landing mid-block is visible the way a watched-path edit is. It gates
        # nothing: `analyse.py` prints it as a rule and V9 is what a finding would belong to.
        "criteria_sha256": sha256(HERE.parent / "criteria.md"),
    }


def v1(start: dict, end: dict) -> dict:
    """V1 -- the CONJUNCTION, evaluated where the block was taken.

    A block is one cell bring-up and lasts many minutes. A single snapshot at its start
    would leave the flag true for the whole block while an edit landed inside it, and V10's
    promise that a concurrent writer flips the flag would be prose ahead of the mechanism.
    Two readings, conjoined; and a block whose two readings DISAGREE is reported as an edit
    that landed mid-block, which is a different finding from a block that was dirty
    throughout.
    """
    return {
        "start": start,
        "end": end,
        "v1_clean": bool(start["clean"] and end["clean"]),
        "disagreed_mid_block": start["clean"] != end["clean"],
        "head_moved_mid_block": start["head"] != end["head"],
        "vendor_pin_held": bool(
            start["vendor_pin"]["matches"] and end["vendor_pin"]["matches"]
        ),
        "base_commit": BASE_COMMIT,
        "watched_paths": list(V1_WATCHED_PATHS),
        "criteria_sha256": sha256(HERE.parent / "criteria.md"),
    }


def host_load() -> dict:
    """I8, read from `/proc/loadavg` INSIDE the container.

    `criteria.md` section 9 records why a container's reading is the host's here -- the file
    is not namespaced on native Linux and there is no `lxcfs` in the way. The key
    nevertheless names where the reading was taken, because the 2026-08-31 capacity campaign
    applied a validity rule that read a virtual machine's load rather than the host's.
    """
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:  # pragma: no cover - not every platform has it
        one = five = fifteen = float("nan")
    return {
        "load_1m": one,
        "load_5m": five,
        "load_15m": fifteen,
        "load_read_from": "/proc/loadavg inside the container; criteria.md section 9 "
                          "records why that is the host's own reading on this host",
        "cpu_count": os.cpu_count(),
        "wall_clock_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def host_facts() -> dict:
    """Section 9's machine block, recorded per block rather than asserted once.

    `GZ_PARTITION` is a real binding here and not a formality: unlike the campaign this one
    inherits its rules from, THIS RIG BRINGS GAZEBO UP, so V12 is live and the partition the
    harness process carries is evidence about which world its probes reached.
    """
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "gz_partition": os.environ.get("GZ_PARTITION"),
    }


def v7(load: dict) -> bool:
    """Whether any of a reading's three load averages exceeds V7's 4.0."""
    return any(
        isinstance(load.get(key), (int, float))
        and not math.isnan(load[key])
        and load[key] > V7_LOAD_THRESHOLD
        for key in ("load_1m", "load_5m", "load_15m")
    )


def running_geometry(namespace: str, timeout_s: float = 300.0) -> dict:
    """V2 and V3, off the description the RUNNING node publishes.

    Off the running node and not off the file on disk, which is the difference between "the
    repository ships hulls" and "the cell that produced these numbers was built from them".
    `v2_ok` and `v3_ok` are conjunctions of POSITIVE findings, never of two absences: an
    empty answer counts zero hull references as readily as a vendor-mesh description does,
    and "no mock plugin found" must not be reachable by not looking.

    THE 2026-09-03 CAMPAIGN LOST EIGHTEEN TRIALS HERE. One trial of eighteen read the
    description back as zero characters and the block-level discard took the rest with it,
    so `description_chars` is published on every block record and `read_ok` is separate from
    `v2_ok`: a rig that could not read is a different finding from a cell built wrongly.
    """
    result = subprocess.run(
        ["ros2", "param", "get", f"{namespace}/description_publisher", "robot_description"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    running = result.stdout
    hulls = running.count(HULL_COLLISION_REFERENCE)
    production = running.count(PRODUCTION_PLUGIN)
    return {
        "read_from": f"{namespace}/description_publisher robot_description",
        "read_returncode": result.returncode,
        "read_ok": len(running) > 0,
        "description_chars": len(running),
        "hull_collision_refs": hulls,
        "vendor_visual_refs": running.count("xarm_description/meshes/xarm5/visual"),
        "v2_ok": len(running) > 0 and hulls == HULL_COLLISION_REFERENCES_EXPECTED,
        "production_plugin_refs": production,
        "fixture_plugin_refs": running.count(FIXTURE_PLUGIN),
        "mock_plugin_refs": running.count(MOCK_PLUGIN),
        "v3_ok": (
            len(running) > 0
            and production > 0
            and running.count(FIXTURE_PLUGIN) == 0
            and running.count(MOCK_PLUGIN) == 0
        ),
    }


# ---------------------------------------------------------------------------
# The generated configuration this campaign was registered against
# ---------------------------------------------------------------------------
def controller_settings(arm: str) -> dict:
    """Section 2.1's declared values, READ OFF the generated file the cell loads.

    Recorded on every block beside the constants this module declares, so that a generated
    value which has moved since registration is visible on the record. It gates nothing --
    V9 forbids moving a threshold, and a disagreement here is a finding for `ANALYSIS.md`,
    not a licence to re-register.
    """
    import yaml  # local: `analyse.py` runs on a host that need not have it

    from ament_index_python.packages import get_package_share_directory

    generated = Path(get_package_share_directory("cite_generated"))
    path = generated / "control" / f"{ZONE}_{arm}_controllers.yaml"
    document = yaml.safe_load(path.read_text())
    manager = document[f"/cite/{ZONE}/{arm}/controller_manager"]["ros__parameters"]
    controller = document[f"/cite/{ZONE}/{arm}/{arm}_joint_trajectory_controller"][
        "ros__parameters"
    ]
    constraints = controller.get("constraints", {})
    joints = list(controller["joints"])
    return {
        "read_from": str(path),
        "joints": joints,
        "update_rate_hz": manager.get("update_rate"),
        "command_interfaces": list(controller.get("command_interfaces", [])),
        "state_interfaces": list(controller.get("state_interfaces", [])),
        "goal_time_s": constraints.get("goal_time"),
        "stopped_velocity_tolerance": constraints.get("stopped_velocity_tolerance"),
        "trajectory_tolerance_rad": {
            joint: constraints.get(joint, {}).get("trajectory") for joint in joints
        },
        "goal_tolerance_rad": {
            joint: constraints.get(joint, {}).get("goal") for joint in joints
        },
        "agrees_with_registration": (
            manager.get("update_rate") == DECLARED_UPDATE_RATE_HZ
            and constraints.get("goal_time") == DECLARED_GOAL_TIME_S
            and all(
                constraints.get(joint, {}).get("trajectory")
                == DECLARED_TRAJECTORY_TOLERANCE_RAD
                and constraints.get(joint, {}).get("goal") == DECLARED_GOAL_TOLERANCE_RAD
                for joint in joints
            )
        ),
    }


def station_frames(station: str) -> dict:
    """One station's pick and place frames, out of the generated topology.

    `criteria.md` section 3's amendment names `cell_a_flow.yaml` as the source of the load
    arms' frames precisely so that they are the frames those arms reach in the shipped line
    rather than this campaign's invention. Read, not written (P1).
    """
    import yaml

    from ament_index_python.packages import get_package_share_directory

    generated = Path(get_package_share_directory("cite_generated"))
    path = generated / "topology" / f"{ZONE}_flow.yaml"
    document = yaml.safe_load(path.read_text())
    topology = document["topology"]
    for entry in topology.get("stations", []):
        if entry.get("id") == station:
            return {
                "station": station,
                "read_from": str(path),
                "pick_frame": entry.get("pick_frame"),
                "place_frame": entry.get("place_frame"),
                # The generated key is `actor`, and it is the ARM this station drives. Named
                # here rather than assumed, because a station whose actor is null is a source
                # or a sink and has no frames to reach at all.
                "actor": entry.get("actor"),
            }
    raise KeyError(f"{station} is not a station of the generated {ZONE} topology")


# ---------------------------------------------------------------------------
# Rule L, V5 and V14 -- computed WHERE THE BLOCK IS TAKEN, on unrounded samples
# ---------------------------------------------------------------------------
#: How many decimal places the published per-sample arrays carry. NOT a threshold and
#: nothing in section 7 is compared against it: V5's 1e-9 identity, rule L's four clauses
#: and every peak are computed HERE, on the unrounded doubles, and their outcomes travel on
#: the record. The rounding exists so that a block's raw file is readable, and 1e-9 rad is
#: six orders of magnitude below rule L-iii's own 0.001 rad floor.
PUBLISH_DECIMALS = 9


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), PUBLISH_DECIMALS)


def moving_window(samples: list[dict]) -> tuple[int, int] | None:
    """`criteria.md` section 7.1's DOMAIN, defined on fields of the recorded message.

    The contiguous run from the FIRST sample with `max_j |reference.velocities[j]| > 0` to
    the LAST with the same, both inclusive. `reference.velocities` is zero while the
    controller holds position, which is what makes both edges observable rather than
    inferred, and a sample whose `reference.velocities` is EMPTY counts as not moving.

    Returns `None` for a trial with no moving sample at all -- which is an empty moving
    window and fails L-i, and is a different statement from a window of length zero.
    """
    indices = [
        index
        for index, sample in enumerate(samples)
        if sample["reference_velocities"]
        and max(abs(v) for v in sample["reference_velocities"]) > 0.0
    ]
    if not indices:
        return None
    return indices[0], indices[-1]


def v5_sample(sample: dict) -> bool:
    """V5 -- `error == reference - feedback`, an exact identity in double precision.

    A sample whose three arrays are not all the same non-zero length cannot satisfy an
    identity over them and is a violation, not an abstention: a malformed record is exactly
    what this rule exists to catch.
    """
    error = sample["error_positions"]
    reference = sample["reference_positions"]
    feedback = sample["feedback_positions"]
    if not error or len(error) != len(reference) or len(error) != len(feedback):
        return False
    return all(
        abs(error[i] - (reference[i] - feedback[i])) <= V5_IDENTITY_RAD
        for i in range(len(error))
    )


def summarise_trial(samples: list[dict], joints: list[str]) -> dict:
    """Every quantity rule L, rule D, rule M, BAND1, GOAL1 and X1 are computed from.

    COMPUTED HERE, WHERE THE BLOCK IS TAKEN, on the unrounded doubles, and travelling on the
    record. `analyse.py` reads these off the row and applies section 7's registered
    thresholds to them; it re-derives none of them from a tree that has since moved.

    The four rule-L clauses are returned as the RAW QUANTITY as well as the flag -- the
    achieved rate whatever it is (L-ii's own sentence), the largest error seen, the share of
    samples satisfying V5 -- so that the write-up can report what a loss was, and not only
    that there was one.
    """
    window = moving_window(samples)
    n_total = len(samples)
    v5_flags = [v5_sample(sample) for sample in samples]
    v5_share = (sum(v5_flags) / n_total) if n_total else 0.0

    # V14 -- one clock, and stamps that do not go backwards. A trial whose samples carry a
    # non-monotonic stamp is excluded and reported; this is where that is decided.
    stamps = [sample["t"] for sample in samples]
    monotonic = all(b >= a for a, b in zip(stamps, stamps[1:]))

    result: dict = {
        "joints": joints,
        "samples_total": n_total,
        "sim_t_first": _round(stamps[0]) if stamps else None,
        "sim_t_last": _round(stamps[-1]) if stamps else None,
        "v5_samples_ok": int(sum(v5_flags)),
        "v5_share": v5_share,
        "v14_stamps_monotonic": monotonic,
        "window_present": window is not None,
    }

    if window is None:
        result.update(
            {
                "window_first_index": None,
                "window_last_index": None,
                "window_sim_t_first": None,
                "window_sim_t_last": None,
                "window_samples": 0,
                "window_sim_span_s": None,
                "window_rate_per_sim_s": None,
                "max_abs_error_rad": None,
                "peak": None,
                "v_peak_feedback_rad_s": None,
                "v_peak_reference_rad_s": None,
                "per_joint": None,
                "abs_error_series": [],
                "t_series": [],
                "feedback_speed_series": [],
                "reference_speed_series": [],
                "l_i": False,
                "l_ii": False,
                "l_iii": False,
                "l_iv": False,
                "l_iv_peak_ok": None,
                "rule_l_admissible": False,
                "rule_l_failed": ["L-i (no moving sample at all)"],
            }
        )
        return result

    first, last = window
    inside = samples[first : last + 1]
    inside_v5 = v5_flags[first : last + 1]
    n_window = len(inside)
    span = inside[-1]["t"] - inside[0]["t"]
    # A window of one sample has a span of zero; a rate is then undefined rather than
    # infinite, and an undefined rate fails L-ii. It is not silently treated as a pass.
    rate = (n_window / span) if span > 0 else None

    abs_series = [[abs(v) for v in sample["error_positions"]] for sample in inside]
    per_sample_max = [max(row) if row else 0.0 for row in abs_series]
    peak_index = max(range(n_window), key=lambda i: per_sample_max[i])
    peak_sample = inside[peak_index]
    peak_joint = int(
        max(
            range(len(abs_series[peak_index])),
            key=lambda j: abs_series[peak_index][j],
        )
    )

    fb_speed = [
        max((abs(v) for v in sample["feedback_velocities"]), default=0.0)
        for sample in inside
    ]
    ref_speed = [
        max((abs(v) for v in sample["reference_velocities"]), default=0.0)
        for sample in inside
    ]

    n_joints = len(joints)
    per_joint = []
    for j in range(n_joints):
        column = sorted(row[j] for row in abs_series if len(row) > j)
        per_joint.append(
            {
                "joint": joints[j],
                "n": len(column),
                "min": _round(column[0]) if column else None,
                "median": _round(_percentile(column, 50.0)),
                "p95": _round(_percentile(column, 95.0)),
                "p99": _round(_percentile(column, 99.0)),
                "max": _round(column[-1]) if column else None,
            }
        )

    # L-i counts messages carrying `error.positions` of length 5 -- the length the generated
    # configuration declares, read from it rather than written here.
    well_formed = sum(1 for row in abs_series if len(row) == n_joints)
    l_i = well_formed >= L_I_MIN_SAMPLES
    l_ii = rate is not None and rate >= L_II_MIN_RATE_PER_SIM_S
    # L-iii is over the TRIAL, not over the window: "at least one sample in the trial".
    l_iii = any(
        max((abs(v) for v in sample["error_positions"]), default=0.0)
        >= L_III_NONZERO_ERROR_RAD
        for sample in samples
    )
    peak_ok = bool(inside_v5[peak_index])
    l_iv = v5_share >= L_IV_CONSISTENCY_SHARE and peak_ok

    failed = []
    if not l_i:
        failed.append(f"L-i ({well_formed} well-formed of {L_I_MIN_SAMPLES})")
    if not l_ii:
        failed.append(f"L-ii (rate {rate})")
    if not l_iii:
        failed.append("L-iii (no sample reached 0.001 rad)")
    if not l_iv:
        failed.append(f"L-iv (v5 share {v5_share:.4f}, peak ok {peak_ok})")

    result.update(
        {
            "window_first_index": first,
            "window_last_index": last,
            # The window's own edges, in the controller's simulated clock and ABSOLUTE.
            # `t_series` below is relative to the window's first sample, so a caller that
            # needed the absolute edges used to reconstruct them from `sim_t_first`, which is
            # the TRIAL's first sample and not the window's. CONC's `load_active` is
            # computed against these two, and the two are not the same instant.
            "window_sim_t_first": _round(inside[0]["t"]),
            "window_sim_t_last": _round(inside[-1]["t"]),
            "window_samples": n_window,
            "window_well_formed_samples": well_formed,
            "window_sim_span_s": _round(span),
            "window_rate_per_sim_s": _round(rate),
            "max_abs_error_rad": _round(per_sample_max[peak_index]),
            "peak": {
                "index_in_window": peak_index,
                "sim_t": _round(peak_sample["t"]),
                "joint_index": peak_joint,
                "joint": joints[peak_joint] if peak_joint < n_joints else None,
                "abs_error_rad": _round(abs_series[peak_index][peak_joint]),
                "error_positions": [_round(v) for v in peak_sample["error_positions"]],
                "reference_positions": [
                    _round(v) for v in peak_sample["reference_positions"]
                ],
                "reference_velocities": [
                    _round(v) for v in peak_sample["reference_velocities"]
                ],
                "feedback_positions": [
                    _round(v) for v in peak_sample["feedback_positions"]
                ],
                "feedback_velocities": [
                    _round(v) for v in peak_sample["feedback_velocities"]
                ],
                "v5_ok": peak_ok,
            },
            "v_peak_feedback_rad_s": _round(max(fb_speed) if fb_speed else None),
            "v_peak_reference_rad_s": _round(max(ref_speed) if ref_speed else None),
            "per_joint": per_joint,
            # The published series, rounded for readability only. Every decision above was
            # taken on the unrounded doubles.
            "t_series": [_round(sample["t"] - inside[0]["t"]) for sample in inside],
            "abs_error_series": [[_round(v) for v in row] for row in abs_series],
            "feedback_speed_series": [_round(v) for v in fb_speed],
            "reference_speed_series": [_round(v) for v in ref_speed],
            "l_i": l_i,
            "l_ii": l_ii,
            "l_iii": l_iii,
            "l_iv": l_iv,
            "l_iv_peak_ok": peak_ok,
            "rule_l_admissible": bool(l_i and l_ii and l_iii and l_iv),
            "rule_l_failed": failed,
        }
    )
    return result


def goal_settle(samples: list[dict], window: tuple[int, int] | None) -> dict:
    """GOAL1's settle, over section 7.1's GOAL WINDOW.

    The goal window opens at the first sample AFTER the moving window's last and closes at
    the trial's last sample. The settle is the interval from that opening to the first
    sample with `max_j |error_j| <= 0.01 rad`, in the controller's own simulated clock.

    A settle of `None` with `already_inside` true is the case section 7.3 predicts and
    registers as UNINFORMATIVE: the reference has decelerated to zero by the last trajectory
    point, so the error is already inside the goal tolerance before the window opens. It is
    reported in the rule-N shape and is not evidence that anything was exercised.
    """
    if window is None:
        return {
            "goal_window_samples": 0,
            "settle_s": None,
            "already_inside": None,
            "reason": "no moving window, so no goal window",
        }
    after = samples[window[1] + 1 :]
    if not after:
        return {
            "goal_window_samples": 0,
            "settle_s": None,
            "already_inside": None,
            "reason": "the trial's last sample is the moving window's last, so the goal "
                      "window is empty and no settle can be measured",
        }
    opened = after[0]["t"]
    inside_at_open = (
        max((abs(v) for v in after[0]["error_positions"]), default=0.0)
        <= DECLARED_GOAL_TOLERANCE_RAD
    )
    for sample in after:
        if (
            max((abs(v) for v in sample["error_positions"]), default=0.0)
            <= DECLARED_GOAL_TOLERANCE_RAD
        ):
            return {
                "goal_window_samples": len(after),
                "goal_window_span_s": _round(after[-1]["t"] - opened),
                "settle_s": _round(sample["t"] - opened),
                "already_inside": inside_at_open,
                "reason": None,
            }
    return {
        "goal_window_samples": len(after),
        "goal_window_span_s": _round(after[-1]["t"] - opened),
        "settle_s": None,
        "already_inside": inside_at_open,
        "reason": "the goal window ended with the error still outside the goal tolerance",
    }


def _percentile(sorted_values: list[float], percent: float) -> float | None:
    """Linear-interpolation percentile over an ALREADY SORTED list.

    Stated once and used by both the runner's per-trial summary and the analyser's pooled
    distribution, so that "the p95" means one thing in this campaign (P1).
    """
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (percent / 100.0) * (len(sorted_values) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return sorted_values[low]
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def percentile(values: list[float], percent: float) -> float | None:
    return _percentile(sorted(values), percent)


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """V8's interval. Copied from the 2026-09-03 campaign's `common.py` at `8a35a03`."""
    if trials <= 0:
        return None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    spread = (
        z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    )
    return max(0.0, centre - spread), min(1.0, centre + spread)


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class TrialWriter:
    """One JSON array per block, rewritten after every trial and SEALED at the end.

    Rewritten rather than appended, so that a block killed part-way leaves a file that
    parses. V8 -- every count is reported over the trials that actually ran -- depends on
    the partial file being readable, and a truncated last object would lose the whole block
    instead of the last trial.

    `seal` is V1's closing reading, and it is the reason a row is not final when it is
    written: `v1_clean` is the conjunction of two `git` readings taken at both ends of the
    block, and the closing one does not exist while the block is running. Every row carries
    `v1_clean = None` until `seal` rewrites it. A harness that DIED without sealing leaves
    `None` on every row, `analyse.py` drops them, and V1 reports the block as lost with the
    trial count it would have contributed -- which is exactly what V1 registers.
    """

    def __init__(self, out: Path, label: str, header: dict) -> None:
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "logs").mkdir(exist_ok=True)
        self.label = label
        self.header = header
        self.rows: list[dict] = []
        self.setup: list[dict] = []
        self.path = self.out / f"{label}_trials.json"
        self.sealed = False
        (self.out / f"{label}_header.json").write_text(
            json.dumps(header, indent=2, default=str)
        )

    def add(self, row: dict) -> dict:
        # The header's block-level facts travel ON EVERY RECORD and not only in the header.
        # A record lifted out of this file into a table is a record that has left its header
        # behind, and V1, V2, V3, V4 and V7 are block rules whose evidence must not be
        # separable from the numbers they validate. `criteria.md` V1 says it in as many
        # words: not a note in a README, a field.
        row = {
            **row,
            "label": self.label,
            "block": self.label,
            "base_commit": BASE_COMMIT,
            "v2": self.header.get("v2"),
            "v3": self.header.get("v3"),
            "v4": self.header.get("v4"),
            "v7_start": self.header.get("v7_start"),
            "v13": self.header.get("v13"),
            "controller_settings": self.header.get("controller_settings"),
            "model_hash": self.header.get("model_hash"),
            # Filled by `seal`. Present from the start so that a reader of a partial file
            # sees the field and its `None`, rather than inferring an absence from a missing
            # key.
            "v1_clean": None,
            "v1": None,
            "v7_end": None,
            "v7_any": None,
            # `criteria.md` section 10: THE SHAKEDOWN IS NOT DATA. It travels on the record
            # so that the exclusion is a FIELD the analyser drops on, and not a property of
            # which directory the operator happened to redirect the run into.
            "is_shakedown": bool(self.header.get("is_shakedown")),
        }
        self.rows.append(row)
        self.flush()
        return row

    def add_setup(self, record: dict) -> dict:
        """A NON-TRIAL motion, written to `<label>_setup.json` and never to the trial stream.

        `criteria.md` section 5.3 defines a trial as one L3 goal of a registered arm's goal
        set. The repositioning move the 2026-09-04 shakedown showed to be necessary is not one
        of those, so it is kept in a file of its own: a record that cannot be swept into a
        distribution by a glob, and that a reader can nevertheless audit.
        """
        self.setup.append({**record, "label": self.label, "block": self.label,
                           "is_shakedown": bool(self.header.get("is_shakedown"))})
        (self.out / f"{self.label}_setup.json").write_text(
            json.dumps(self.setup, indent=2, default=str)
        )
        return record

    def seal(self, end_snapshot: dict, end_load: dict, why: str) -> dict:
        """V1's closing reading, applied to every row this block wrote.

        Called at the end of a complete block AND as the first act of the abort path, which
        is what stops V1 and V8 contradicting each other: V8 promises that a block ending
        early is reported with the n it reached, and without a closing reading taken at the
        abort those rows would carry no flag and be dropped.
        """
        flags = v1(self.header["v1_start"], end_snapshot)
        v7_start = bool(self.header.get("v7_start"))
        v7_end = v7(end_load)
        for row in self.rows:
            row["v1"] = flags
            row["v1_clean"] = flags["v1_clean"]
            row["v7_end"] = v7_end
            row["v7_any"] = v7_start or v7_end
        self.sealed = True
        self.flush()
        (self.out / f"{self.label}_sealed.json").write_text(
            json.dumps(
                {
                    "label": self.label,
                    "sealed_because": why,
                    "v1": flags,
                    "load_end": end_load,
                    "v7_start": v7_start,
                    "v7_end": v7_end,
                    "rows": len(self.rows),
                    "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                indent=2,
                default=str,
            )
        )
        return flags

    def flush(self) -> None:
        self.path.write_text(json.dumps(self.rows, indent=2, default=str))

    def complete(self, scheduled: int, extra: dict | None = None) -> None:
        """Mark the block as having run to the end of its schedule.

        A block that ABORTS part-way leaves `<label>_trials.json` behind exactly as a
        finished one does, and `run_campaign.sh` skips a block whose trials file exists so
        that a resumed campaign never tops a condition up (V8). Without a marker those two
        states are indistinguishable, so an aborted block would be silently treated as DONE.
        """
        (self.out / f"{self.label}_complete.json").write_text(
            json.dumps(
                {
                    "label": self.label,
                    "trials_scheduled": scheduled,
                    "trials_written": len(self.rows),
                    "sealed": self.sealed,
                    "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    **(extra or {}),
                },
                indent=2,
                default=str,
            )
        )


class LogCursor:
    """I3(b) and I3(c) -- read the launch log for ONE goal, not for the whole block.

    Copied from `docs/measurements/2026-09-03-stall-band-flip/harness/common.py` at
    `8a35a03`, itself copied from the 2026-09-02 rig. The block log accumulates lines from
    every process the launch started, and attributing them by position in the file would
    break the first time an extra one appeared; each goal's segment is bracketed by the
    file's size before and after it.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.offset = 0

    def mark(self) -> None:
        self.offset = self.path.stat().st_size if self.path.exists() else 0

    def text(self) -> str:
        if not self.path.exists():
            return ""
        with self.path.open("r", errors="replace") as handle:
            handle.seek(self.offset)
            return handle.read()

    def collect(self, arm: str) -> dict:
        return scrape_i3(self.text(), arm)

    def settle(self, arm: str, seconds: float = 1.0) -> dict:
        """I3, waited for a BOUNDED interval rather than sampled once.

        The controller and move_group write to this file from other processes, after they
        answer the action; at the instant the harness reads the result those lines may
        legitimately not have been flushed. Sampling once turns that race into a datum --
        `i3_any_log_event` recorded false for a goal that did fire -- and a record that
        stores booleans cannot tell an unflushed reading from a measured absence.

        It sequences nothing and no cell waits on it (P4). It is bounded, and what it
        publishes is what the file held when the bound expired.
        """
        end = time.monotonic() + seconds
        found = self.collect(arm)
        while not found["i3_any_log_event"] and time.monotonic() < end:
            time.sleep(0.1)
            found = self.collect(arm)
        return found
