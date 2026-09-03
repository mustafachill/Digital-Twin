#!/usr/bin/env python3
"""What the runner and the analyser share: the registered constants, provenance, and the record.

DERIVED FROM two frozen directories, and both are named because the two halves came from
different places:

  * `docs/measurements/2026-09-02-option-f-regions/harness/common.py`, copied at commit
    `ac11d84` -- the `_BatchProgram` / `Predicate` / `SupersededPredicate` front ends, the
    `REPORT` pattern, `TRAVEL_KEYS`, `load_plan`, `travel_from_plan`, `parts_from_plan`,
    `window_m`, `LogCursor`, `TrialWriter` and the "provenance travels on every record"
    shape.
  * `docs/measurements/2026-09-02-scenario-ceilings/harness/common.py`, copied at commit
    `b2fd9ba` -- the TWO-ENDED `snapshot` / `v1` pair, which is what makes V1 a conjunction
    of readings taken at both ends of a block rather than one reading taken at its start.

Both directories are FROZEN (`docs/measurements/README.md`) and nothing in either is edited
from here. **No campaign imports from another**: this is a copy, and the header says so.

WHY ONE MODULE RATHER THAN A COPY PER RUNNER. Inside one campaign a value in two places is
still a value in two places (P1). V1 discards a block, and a discard rule implemented twice
is two rules.

WHAT THIS MODULE MAY NOT DO. It computes no gripper arithmetic. Every number it hands out
comes either from the generated bring-up plan, from `git`, or from one of the two compiled
front ends. `arithmetic.py` is the reference implementation and it is NOT imported here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import time

# ---------------------------------------------------------------------------
# The cell, and the tree the campaign is a property of
# ---------------------------------------------------------------------------

#: The zone and the arm every campaign figure is taken on (`criteria.md` section 5.1).
ZONE = "cell_a"
ARM = "arm_1"
DRIVE_JOINT = f"{ARM}_drive_joint"

#: `criteria.md` V1 and its BASE_COMMIT. Every figure is a property of the tree here.
BASE_COMMIT = "c38a42c"

#: `criteria.md` V12's commit. The superseded predicate is a BUILD of this tree, never a
#: rewrite. Named ONCE here because `superseded_provenance` below and `analyse.py`'s V12
#: both have to compare against it, and a literal typed in two places is the defect P1
#: names. `build_superseded.sh` carries it a third time, in shell, which is recorded as a
#: limitation in `README.md` rather than fixed: the script's copy is what PRODUCES the
#: provenance and this one is what CHECKS it, so the two agreeing is the check.
SUPERSEDED_COMMIT = "4ef2d7c"

#: The fields of `raw/predicate_eval_superseded_provenance.txt` that identify WHICH BUILD
#: produced `holding_S`, and therefore the only fields V12 may be computed from. They are
#: exactly the ones a rebuild of the same commit reproduces: `built_at` is refreshed by
#: `build_superseded.sh` on EVERY build, so a campaign whose blocks were taken across two
#: builds of the identical commit carries two different `built_at` values and one identity.
#: Comparing the whole dictionary would report a complete provenance as a V12 failure.
V12_IDENTITY_KEYS = (
    "worktree_commit",
    "worktree_commit_short",
    "gripper_cpp_sha256",
    "gripper_hpp_sha256",
    "front_end_sha256",
    "binary_sha256",
)

#: `criteria.md` section 0 and V1. FIVE paths, inherited from the 2026-09-02
#: scenario-ceilings campaign for the reason it gives: everything this campaign consumes
#: lives in them. `docs/measurements/` is deliberately NOT watched -- this campaign's own
#: `criteria.md`, harness and raw all land on this branch, so `HEAD` necessarily advances
#: while it runs and pinning it would discard every block including the first.
V1_WATCHED_PATHS = ("model/", "workspace/src/", "tools/", "tests/", "scripts/")

#: `criteria.md` V2. The collision-mesh references the description the rig publishes must
#: carry for the shipped `convex_hull` selection (ADR-0028). The count is the criteria's;
#: the STRING is the one the 2026-09-01 and 2026-09-02 rigs counted, kept so that the
#: campaigns count the same thing.
HULL_COLLISION_REFERENCE = "cite_description/meshes/collision/xarm5/convex_hull"
HULL_COLLISION_REFERENCES_EXPECTED = 13

#: `criteria.md` V13. The backend every generated description declares, asserted BEFORE
#: substitution, and the two plugins this rig substitutes for it. A rig that substitutes
#: for something other than the production backend is measuring a system nobody ships.
PRODUCTION_PLUGIN = "gz_ros2_control/GazeboSimSystem"
FIXTURE_PLUGIN = "cite_test_hardware/JointStopSystem"
MOCK_PLUGIN = "mock_components/GenericSystem"

# ---------------------------------------------------------------------------
# The instruments' own patterns
# ---------------------------------------------------------------------------

#: I2. The skill server's own report line, matched verbatim so that a change to the format
#: breaks this harness loudly instead of returning silence. `skill_server.cpp:2247-2253`.
#: The two widths it carries are `%.1f` and are used for nothing but V4's second clause.
REPORT = re.compile(
    r"gripper: commanded ([-+0-9.]+) mm, reached ([-+0-9.]+) mm, "
    r"stalled=(true|false), reached_goal=(true|false), effort=([-+0-9.]+) -> (holding|empty)"
)

#: I5 and I6 -- the fixture's own two lines, matched verbatim
#: (`joint_stop_system.cpp:189-193` and `:176-181`, read at `HEAD` on 2026-09-03).
STOP_ANNOUNCE = re.compile(r"has reached a declared stop at ([-+0-9.eE]+)")
START_REFUSAL = re.compile(
    r"starts at ([-+0-9.eE]+), outside its declared stops \[([-+0-9.eE]+), ([-+0-9.eE]+)\]")

# ---------------------------------------------------------------------------
# `criteria.md` section 7.0 -- the minimum interesting size and the two tolerances
# ---------------------------------------------------------------------------

#: The MIS for any width. Inherited from the 2026-09-01 campaign's rule R via the
#: 2026-09-02 campaign's section 7.0: the production log line's own `%.1f` resolution.
#: Rule R is what spends it, and rule B never does -- **a bracket is not an MIS**, and
#: section 7.0 says in as many words that a 0.05 mm bracket does not resolve a 0.100 mm
#: difference.
MIS_WIDTH_M = 0.000100

#: The bracket step, which is ADR-0052 section A.10 item 2's own number. `criteria.md`
#: section 5.1's stage 2 grid, and rule B's definition of BRACKETED, are both this.
BRACKET_STEP_MM = 0.05

#: I7's rest tolerance and V4's agreement tolerance, both TIGHTENED here from the
#: inherited 0.001 rad / 0.100 mm for the reason section 7.0 gives: 0.001 rad is 0.1060 mm
#: of width at `edge_lo`, which is TWICE the bracket step, so the inherited rule would
#: admit a trial resting two grid points from the stop it declared. One tenth of the
#: bracket step, expressed in WIDTH so that the criterion is uniform in the quantity the
#: predicate consumes.
REST_TOLERANCE_M = 0.000005
V4_TOLERANCE_M = 0.000005

#: V14's third clause uses the same size for the same reason: at that point the campaign
#: does not know what the predicate consumed.
V14_TOLERANCE_M = 0.000005

#: V7. NOT an exclusion threshold -- no block is discarded for load, because a load
#: threshold chosen after seeing the data is a threshold chosen by the data. A reading
#: above this flags every trial in its block, and every bracket the block contributes to is
#: reported with and without them. Sixteen cores, so this is a quarter of the machine.
V7_LOAD_THRESHOLD = 4.0

# ---------------------------------------------------------------------------
# `criteria.md` section 5 -- the grids, the commands and the inert stop
# ---------------------------------------------------------------------------

#: Stage 1, the coarse grids, in mm. Each span is exactly the interval the 2026-09-02
#: campaign left open at its 2.00 mm grid, and its two endpoints are that campaign's two
#: anchors -- **re-measured here, not inherited**. Built from the step rather than typed
#: out, so that the step is stated once and the grid cannot drift from it.
COARSE_STEP_MM = 0.25
COARSE_SPANS_MM = {"LO": (46.00, 48.00), "HI": (52.00, 54.00)}

#: Stage 2, the fine step. Six stops per refinement, inclusive of both endpoints of the
#: located coarse interval -- which is what 0.25 / 0.05 + 1 comes to, and the refusal in
#: `fine_grid` is what keeps it that way rather than a comment.
FINE_STEP_MM = 0.05

#: `criteria.md` section 5.2. The shipped command every trial in arms LO, HI and CTL
#: sends, and INV's second command. Both are ASSERTED against the plan rather than
#: trusted: `plan_default_grasp_width_m` reads L0's `default_grasp_width_m` as the plan
#: delivers it, and `measure.py` refuses a block whose plan disagrees with the registered
#: value. A campaign commanding a width the model no longer declares would be measuring
#: the window at a command nobody sends.
W_CMD_SHIPPED_M = 0.045
W_CMD_INV_M = 0.040

#: Held fixed for every trial (`criteria.md` section 5.1). Literal, as the criteria states
#: it: -1.0 rad is below the whole travel, so the joint can never meet it, and it brackets
#: the joint's initial position so the fixture's start-outside-the-stops refusal cannot
#: fire.
STOP_LOWER_RAD = -1.0

#: `criteria.md` section 5.1's held-fixed table.
MAX_EFFORT_N = 60.0

#: `criteria.md` section 6. Quiesce between a teardown and the next launch. It is a
#: quiesce for an instrument and not a step of any bring-up sequence -- nothing here waits
#: for a cell to be ready by sleeping (P4); the runner gates on the action servers' own
#: appearance.
QUIESCE_S = 30

#: `criteria.md` section 6's design table, in section 6's registered order. `stops` is
#: what determines the stop list: `coarse` takes the whole coarse grid of the arm, `fine`
#: takes a located coarse interval on the command line, and `given` takes an explicit list
#: (INV's four straddling stops). CTL has no stop at all.
BLOCKS: dict[str, dict] = {
    "LO-C": {"arm": "LO", "stops": "coarse", "repeats": 2, "command_m": W_CMD_SHIPPED_M},
    "HI-C": {"arm": "HI", "stops": "coarse", "repeats": 2, "command_m": W_CMD_SHIPPED_M},
    "LO-F": {"arm": "LO", "stops": "fine", "repeats": 3, "command_m": W_CMD_SHIPPED_M},
    "HI-F": {"arm": "HI", "stops": "fine", "repeats": 3, "command_m": W_CMD_SHIPPED_M},
    "LO-S": {"arm": "LO", "stops": "fine", "repeats": 3, "command_m": W_CMD_SHIPPED_M},
    "INV": {"arm": "INV", "stops": "given", "repeats": 3, "command_m": W_CMD_INV_M},
    "CTL": {"arm": "CTL", "stops": "none", "repeats": 3, "command_m": W_CMD_SHIPPED_M},
}

#: `criteria.md` section 6's order. LO-C and HI-C must complete before any refinement,
#: because a refinement's interval is located by them; INV depends on knowing which stops
#: straddle; CTL is independent and runs last so that a failure in it cannot consume the
#: campaign's time budget.
BLOCK_ORDER = ("LO-C", "HI-C", "LO-F", "HI-F", "LO-S", "INV", "CTL")

#: Which predicate each refinement block refines. Rules B, U and R are **generic in the
#: predicate under refinement** (`criteria.md` section 7.1's second amendment), and this is
#: the table that makes them so rather than a branch repeated in three places.
REFINED_PREDICATE = {"LO-F": "holding_F", "HI-F": "holding_F", "LO-S": "holding_S"}

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
# The grids
# ---------------------------------------------------------------------------
def _mm(value: float) -> float:
    """One grid point, rounded to the hundredth of a millimetre it is defined at.

    The grids are multiples of 0.05 and 0.25 mm, neither of which is representable in
    binary, so an accumulated sum drifts. Rounding at the point of construction keeps a
    grid point comparable with the same grid point built by the analyser -- the records key
    on this value.
    """
    return round(value, 2)


def coarse_grid(arm: str) -> tuple[float, ...]:
    """Stage 1's nine stops for one arm, built from the registered step."""
    low, high = COARSE_SPANS_MM[arm]
    count = int(round((high - low) / COARSE_STEP_MM)) + 1
    return tuple(_mm(low + index * COARSE_STEP_MM) for index in range(count))


def within_a_coarse_span(arm: str, width_mm: float) -> bool:
    """`criteria.md` section 5.1: no stop outside the two coarse spans is ever run."""
    low, high = COARSE_SPANS_MM[arm]
    return low - 1e-9 <= width_mm <= high + 1e-9


def arm_of_stop(width_mm: float) -> str | None:
    """Which arm's span a stop lies in, or `None` if it lies in neither."""
    for arm in COARSE_SPANS_MM:
        if within_a_coarse_span(arm, width_mm):
            return arm
    return None


def fine_grid(arm: str, low_mm: float, high_mm: float) -> tuple[float, ...]:
    """Stage 2's six stops across a LOCATED coarse interval, at the REGISTERED step.

    `criteria.md` section 5.1 draws the distinction this function enforces: *the step is a
    threshold and is registered; the interval is a bracket and is located by the data*.
    So the step is not a parameter, the endpoints are, and the endpoints are refused unless
    they are an ADJACENT PAIR of the arm's own coarse grid.

    THE REFUSALS ARE THE POINT. A refinement over an interval that is not a coarse straddle
    would be a sweep whose extent was decided by its own early readings, which section 5.1
    forbids in as many words.
    """
    grid = coarse_grid(arm)
    low, high = _mm(low_mm), _mm(high_mm)
    pairs = list(zip(grid, grid[1:]))
    if (low, high) not in pairs:
        raise ValueError(
            f"[{low}, {high}] mm is not an adjacent pair of arm {arm}'s coarse grid "
            f"{grid}. criteria.md section 5.1 refines a LOCATED coarse interval and "
            "nothing else, and no stop outside the two coarse spans is run whatever the "
            "coarse grid shows."
        )
    count = int(round((high - low) / FINE_STEP_MM)) + 1
    return tuple(_mm(low + index * FINE_STEP_MM) for index in range(count))


def on_a_fine_grid(width_mm: float) -> bool:
    """Whether a stop is a point of some coarse interval's fine grid, in its own arm."""
    arm = arm_of_stop(width_mm)
    if arm is None:
        return False
    low, _ = COARSE_SPANS_MM[arm]
    steps = (_mm(width_mm) - low) / FINE_STEP_MM
    return abs(steps - round(steps)) < 1e-6


# ---------------------------------------------------------------------------
# V1, V2 and I8 -- the code, the model and the description that actually ran
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


def model_hash(root: Path | None = None) -> dict:
    """The MODEL_HASH of the generated tree, and of the INSTALLED package if there is one.

    Two readings rather than one, because they answer different questions. The source
    tree's says which model the repository describes; the installed one says which model
    the rig that is about to run was built from. A block taken against a stale install is a
    block about a cell nobody committed, and the pair is what makes that visible.
    """
    root = root or repo_root()
    source = root / "workspace" / "src" / "cite_generated" / "MODEL_HASH"
    installed = root / "workspace" / "install" / "cite_generated" / "share" / \
        "cite_generated" / "MODEL_HASH"
    return {
        "source": source.read_text().strip() if source.exists() else None,
        "installed": installed.read_text().strip() if installed.exists() else None,
    }


def snapshot(root: Path | None = None) -> dict:
    """I8, ONE reading. V1 needs two of these and conjoins them.

    Copied in shape from the 2026-09-02 scenario-ceilings campaign, whose `criteria.md`
    this campaign's V1 is inherited from verbatim.
    """
    root = root or repo_root()
    diff = _git(root, "diff", "--name-only", f"{BASE_COMMIT}..HEAD", "--", *V1_WATCHED_PATHS)
    dirty = _git(root, "status", "--porcelain", "--", *V1_WATCHED_PATHS)
    return {
        "at": time.time(),
        "head": _git(root, "rev-parse", "HEAD"),
        "git_status_porcelain": _git(root, "status", "--porcelain"),
        "watched_diff_against_base": diff,
        "watched_worktree_dirty": dirty,
        "clean": diff == "" and dirty == "",
        "model_hash": model_hash(root),
        # V1 deliberately does not watch `docs/`, so the FROZEN `criteria.md` this campaign
        # is a property of lies OUTSIDE every path V1 reads -- and V9 says nothing in it
        # changes once the first trial has run. This hash is the only instrument that could
        # notice one that did. It is taken HERE, in the snapshot, so that it travels at BOTH
        # ENDS of every cycle and an edit landing mid-block is visible the way a watched-path
        # edit is. It gates nothing: `analyse.py` prints it as a rule and V9 is what the
        # finding would belong to.
        "criteria_sha256": sha256(HERE.parent / "criteria.md"),
    }


def v1(start: dict, end: dict) -> dict:
    """V1 -- the CONJUNCTION, evaluated where the block was taken.

    A block is a cycle over an arm's stops and lasts many minutes. A single snapshot at its
    start would leave the flag true for the whole block while an edit landed inside it, and
    V10's promise that a concurrent writer flips the flag would be prose ahead of the
    mechanism. Two readings, conjoined; and a block whose two readings DISAGREE is reported
    as an edit that landed mid-block, which is a different finding from a block that was
    dirty throughout.
    """
    return {
        "start": start,
        "end": end,
        "v1_clean": bool(start["clean"] and end["clean"]),
        "disagreed_mid_block": start["clean"] != end["clean"],
        "head_moved_mid_block": start["head"] != end["head"],
        "base_commit": BASE_COMMIT,
        "watched_paths": list(V1_WATCHED_PATHS),
        "criteria_sha256": sha256(HERE.parent / "criteria.md"),
    }


def host_load() -> dict:
    """I9, read from `/proc/loadavg` INSIDE the container.

    `criteria.md` section 9 demonstrates that on this host a container's reading IS the
    host's -- the file is not namespaced on native Linux and there is no `lxcfs` in the
    way, and that campaign took two readings seconds apart from inside and outside a
    container of this image and they agreed to the hundredth. The key nevertheless names
    where the reading was taken, because the 2026-08-31 capacity campaign applied a
    validity rule that read a Docker Desktop VM's load rather than the host's.
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
                          "demonstrates that on this host that is the host's own reading",
        "cpu_count": os.cpu_count(),
        "wall_clock_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def host_facts() -> dict:
    """Section 9's machine block, recorded per block rather than asserted once."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "gz_partition": os.environ.get("GZ_PARTITION"),
        "note": "there is no Gazebo-transport process in this rig, so GZ_PARTITION is "
                "recorded as an environment fact and binds nothing (criteria.md 4.2)",
    }


def v7(load: dict) -> bool:
    """Whether any of a reading's three load averages exceeds V7's 4.0."""
    return any(
        isinstance(load.get(key), (int, float)) and not math.isnan(load[key])
        and load[key] > V7_LOAD_THRESHOLD
        for key in ("load_1m", "load_5m", "load_15m")
    )


def running_geometry(namespace: str, timeout_s: float = 300.0) -> dict:
    """V2 and V13, off the description the RUNNING rig publishes.

    Off the running node and not off the file the harness wrote, which is the difference
    between "the harness substituted hulls" and "the rig that produced these numbers
    published them". `v2_ok` and the plugin counts are conjunctions of POSITIVE findings,
    never of two absences: an empty answer counts zero hull references as readily as a
    vendor-mesh description does, and "no production plugin found" must not be reachable by
    not looking.
    """
    running = subprocess.run(
        ["ros2", "param", "get", f"{namespace}/description_publisher", "robot_description"],
        capture_output=True, text=True, timeout=timeout_s,
    ).stdout
    hulls = running.count(HULL_COLLISION_REFERENCE)
    return {
        "read_from": f"{namespace}/description_publisher robot_description",
        "hull_collision_refs": hulls,
        "vendor_visual_refs": running.count("xarm_description/meshes/xarm5/visual"),
        "description_chars": len(running),
        "v2_ok": len(running) > 0 and hulls == HULL_COLLISION_REFERENCES_EXPECTED,
        "production_plugin_refs": running.count(PRODUCTION_PLUGIN),
        "fixture_plugin_refs": running.count(FIXTURE_PLUGIN),
        "mock_plugin_refs": running.count(MOCK_PLUGIN),
    }


# ---------------------------------------------------------------------------
# The two compiled front ends
# ---------------------------------------------------------------------------
class _BatchProgram:
    """A line-oriented conversation with a compiled front end.

    Held open for the length of a block rather than started per question: a launch per
    question would make the instrument the expensive part.
    """

    def __init__(self, executable: Path, arguments: dict[str, float]) -> None:
        self.executable = Path(executable)
        self.command = [str(self.executable)] + [f"--{k}={v!r}" for k, v in arguments.items()]
        self.process = subprocess.Popen(
            self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1
        )

    def ask(self, request: str) -> str:
        self.process.stdin.write(request + "\n")
        self.process.stdin.flush()
        answer = self.process.stdout.readline()
        if not answer:
            raise RuntimeError(f"{self.executable.name} died answering {request!r}")
        return answer.strip()

    def close(self) -> None:
        try:
            self.process.stdin.close()
            self.process.wait(timeout=30)
        except Exception:  # noqa: BLE001 - a dead front end is not a trial failure
            pass


class Predicate(_BatchProgram):
    """The SHIPPED arithmetic at `c38a42c`, through `predicate_eval`.

    `holding` here is the shipped predicate evaluated on inputs the harness supplies. It is
    NOT where `holding_F` comes from: `criteria.md` section 3 requires every reported
    verdict to be read off the running node, out of `Grasp.Result.holding`. This is the
    instrument for the stop conversion, for I3's and I7's widths, and for the section 2
    cross-check.
    """

    def __init__(self, executable: Path, travel: dict, parts: dict) -> None:
        super().__init__(executable, {**travel, **parts})

    def width(self, q: float) -> float:
        return float(self.ask(f"width {q!r}"))

    def position(self, width_m: float) -> float:
        return float(self.ask(f"position {width_m!r}"))

    def tolerance(self, q: float) -> float:
        return float(self.ask(f"tolerance {q!r}"))

    def margin(self, width_m: float) -> float:
        return float(self.ask(f"margin {width_m!r}"))

    def max_width(self) -> float:
        return float(self.ask("maxwidth"))

    def min_width(self) -> float:
        return float(self.ask("minwidth"))

    def holding(self, commanded_m: float, q: float, stalled: bool, reached_goal: bool) -> bool:
        return self.ask(
            f"holding {commanded_m!r} {q!r} {int(stalled)} {int(reached_goal)}") == "1"

    def resolve(self, requested_m: float, default_m: float) -> tuple[str, float]:
        source, width = self.ask(f"resolve {requested_m!r} {default_m!r}").split()
        return source, float(width)

    def describe(self) -> dict:
        return {"travel": self.ask("travel"), "parts": self.ask("parts")}


class SupersededPredicate(_BatchProgram):
    """The predicate at `4ef2d7c`, through a BUILD of that commit (`criteria.md` V12).

    Never a reimplementation. `build_superseded.sh` records the worktree commit and the
    binary's sha256 in `raw/provenance.txt`; a trial without that provenance reports
    `holding_F` alone, which is what `available` is read for.
    """

    def __init__(self, executable: Path, travel: dict) -> None:
        # The superseded `GripperTravel` has no bands, and its front end REFUSES an unknown
        # key rather than ignoring it -- so the two are filtered out here rather than
        # silently accepted, which is the behaviour that would let a band reach a predicate
        # that has no place to put it.
        super().__init__(
            executable,
            {k: v for k, v in travel.items()
             if k not in ("stall_band_narrow_m", "stall_band_wide_m")},
        )

    def holding(self, commanded_m: float, q: float, stalled: bool, reached_goal: bool) -> bool:
        return self.ask(
            f"holding {commanded_m!r} {q!r} {int(stalled)} {int(reached_goal)}") == "1"

    def width(self, q: float) -> float:
        return float(self.ask(f"width {q!r}"))

    def position(self, width_m: float) -> float:
        return float(self.ask(f"position {width_m!r}"))

    def tolerance(self, q: float) -> float:
        return float(self.ask(f"tolerance {q!r}"))


def superseded_flip_m(superseded: SupersededPredicate, commanded_m: float) -> float:
    """`criteria.md` section 2.2's floor, solved on the SUPERSEDED BUILD's own answer.

    Bisection on `holding_S` itself, with `stalled` true and `reached_goal` false, so the
    quantity is the flip of the shipped superseded predicate and not of a restatement of
    its inequality. The bracket is the linkage's: the command, where the margin is zero and
    the verdict is certainly false, and 60 mm, above every stop in either arm and inside
    the linkage's reach.

    ADMITTED INTO FLOOR1 ONLY BECAUSE IT IS COMPUTED HERE. Rule H forbids differencing any
    MEASURED figure of another campaign against anything in this one; ADR-0052 section A.6's
    47.1215 mm is such a figure, and it is named beside this value as an agreement and
    enters no arithmetic.
    """
    low, high = commanded_m, 0.060

    def satisfied(width_m: float) -> bool:
        return superseded.holding(commanded_m, superseded.position(width_m), True, False)

    if satisfied(low) or not satisfied(high):
        raise RuntimeError(
            "the superseded predicate does not change verdict over "
            f"[{low}, {high}] m, so there is no floor to solve for here"
        )
    for _ in range(80):
        middle = (low + high) / 2.0
        if satisfied(middle):
            high = middle
        else:
            low = middle
    return (low + high) / 2.0


def superseded_provenance() -> dict:
    """What V12 asks for, read back out of `raw/` so a record can carry it."""
    path = RAW / "predicate_eval_superseded_provenance.txt"
    if not path.exists():
        return {"available": False}
    fields: dict = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    fields["available"] = fields.get("worktree_commit_short") == SUPERSEDED_COMMIT and \
        bool(fields.get("binary_sha256"))
    return fields


def v12_identity(superseded: dict | None) -> tuple:
    """The invariant half of V12's provenance, as a comparable tuple.

    V12 asks for the `4ef2d7c` worktree commit and the sha256 of the binary that produced
    `holding_S`. It does NOT ask when the binary was built, and `built_at` is refreshed by
    `build_superseded.sh` on every build -- so comparing the whole provenance dictionary
    across blocks reports a campaign with COMPLETE provenance as a V12 failure the moment a
    second build of the identical commit happens. This is the subset that identifies the
    build, and it is what V12 is computed from.
    """
    superseded = superseded or {}
    return tuple(superseded.get(key) for key in V12_IDENTITY_KEYS)


# ---------------------------------------------------------------------------
# The plan, read once
# ---------------------------------------------------------------------------

#: The travel keys the skill server receives, under the plan's own names. Named here once;
#: every record carries the dictionary this builds, so a figure can be recomputed from the
#: record alone.
TRAVEL_KEYS = (
    ("open_position", "gripper_open_position"),
    ("closed_position", "gripper_closed_position"),
    ("drive_pivot_y_m", "gripper_drive_pivot_y_m"),
    ("drive_pivot_z_m", "gripper_drive_pivot_z_m"),
    ("finger_offset_y_m", "gripper_finger_offset_y_m"),
    ("finger_offset_z_m", "gripper_finger_offset_z_m"),
    ("pad_inset_m", "gripper_pad_inset_m"),
    ("tip_link_z_m", "gripper_tip_link_z_m"),
    ("pad_face_centre_z_m", "gripper_pad_face_centre_z_m"),
    ("goal_tolerance", "gripper_goal_tolerance_rad"),
    ("stall_band_narrow_m", "gripper_stall_band_narrow_m"),
    ("stall_band_wide_m", "gripper_stall_band_wide_m"),
)


def load_plan():
    """The generated bring-up plan and `arm_1`'s controller-manager entry."""
    from cite_bringup import plan as bringup_plan

    document = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
    manager = next(entry for entry in document.controller_managers if entry.asset == ARM)
    return document, manager


def travel_from_plan(manager) -> dict:
    """The twelve travel parameters AS THE SKILL SERVER RECEIVES THEM, from the plan."""
    keys = manager.gripper
    return {name: float(keys[source]) for name, source in TRAVEL_KEYS}


def parts_from_plan(document) -> dict:
    """The facility's declared part interval, from the plan's own facility block.

    Refused rather than defaulted when the plan states none. A default here would be a
    width the model never stated, applied inside the predicate this campaign measures.
    """
    if document.workpieces is None:
        raise RuntimeError(
            "the generated plan states no `workpieces:` block, so option F has no window "
            "and there is nothing for this campaign to measure. Run "
            "./scripts/validate-model --write, then ./scripts/build."
        )
    return {
        "narrowest_m": float(document.workpieces.narrowest_width_m),
        "widest_m": float(document.workpieces.widest_width_m),
    }


def controller_settings(manager) -> dict:
    """The gripper controller's own settings, from the GENERATED controller configuration.

    Read for one purpose only: P6's registered rest position is `stall_timeout` times
    `max_drive_rate_rad_s`, and a campaign that typed either number in would be predicting
    against a constant nobody delivers. `stall_timeout` lives in the controller
    configuration the rig hands `ros2_control_node` unmodified; `max_drive_rate_rad_s`
    comes to L3 through the plan's gripper block.
    """
    import yaml
    from cite_bringup import plan as bringup_plan

    path = bringup_plan.resolve_uri(manager.parameters)
    document = yaml.safe_load(Path(path).read_text())
    found: dict = {}
    for node, body in (document or {}).items():
        parameters = (body or {}).get("ros__parameters") or {}
        for key in ("stall_timeout", "stall_velocity_threshold", "goal_tolerance",
                    "max_effort", "joint"):
            if key in parameters:
                found.setdefault(key, parameters[key])
                found.setdefault(f"{key}_from", node)
    return {
        "read_from": str(path),
        "stall_timeout_s": found.get("stall_timeout"),
        "stall_velocity_threshold": found.get("stall_velocity_threshold"),
        "controller_goal_tolerance_rad": found.get("goal_tolerance"),
        "declared_on": found.get("stall_timeout_from"),
        "max_drive_rate_rad_s": float(manager.gripper["gripper_max_drive_rate_rad_s"]),
    }


def plan_default_grasp_width_m(manager) -> float:
    """L0's `default_grasp_width_m`, as the plan delivers it to L3."""
    return float(manager.gripper["gripper_default_grasp_width_m"])


def window_m(travel: dict, parts: dict) -> tuple[float, float]:
    """F's window, computed from the same four statements the running node is given.

    `criteria.md` section 2.2 states it as 47.6150 / 52.3850 mm on the shipped model. Those
    numbers are NOT used: the window is derived here from the plan, so that if L0 moves this
    harness follows it rather than measuring against a literal (P1). Rule D is what fires if
    the measured bracket and the derived edge disagree.
    """
    return (
        parts["narrowest_m"] - travel["stall_band_narrow_m"],
        parts["widest_m"] + travel["stall_band_wide_m"],
    )


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class TrialWriter:
    """One JSON array per block, rewritten after every trial.

    Rewritten rather than appended, so that a block killed part-way leaves a file that
    parses. V8 -- every count is reported over the trials that actually ran -- depends on
    the partial file being readable, and a truncated last object would lose the whole block
    instead of the last trial.
    """

    def __init__(self, out: Path, label: str, header: dict) -> None:
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "logs").mkdir(exist_ok=True)
        self.label = label
        self.header = header
        self.rows: list[dict] = []
        self.path = self.out / f"{label}_trials.json"
        (self.out / f"{label}_header.json").write_text(
            json.dumps(header, indent=2, default=str))

    def add(self, row: dict) -> dict:
        # The header's block-level facts travel ON EVERY RECORD and not only in the header.
        # A record lifted out of this file into a table is a record that has left its
        # header behind, and V1, V2 and V12 are block rules whose evidence must not be
        # separable from the numbers they validate. `criteria.md` V1 says it in as many
        # words: not a note in a README, a field.
        row = {
            **row,
            "label": self.label,
            "block": self.label,
            "window_m": self.header.get("window_m"),
            "parts": self.header.get("parts"),
            "travel": self.header.get("travel"),
            "floor_m": self.header.get("floor_m"),
            "superseded": self.header.get("superseded"),
            "p6": self.header.get("p6"),
            # `criteria.md` section 10: the shakedown IS NOT DATA. It travels on the record
            # so that the exclusion is a FIELD the analyser drops on, and not a property of
            # which directory the operator happened to redirect the run into.
            "is_shakedown": bool(self.header.get("is_shakedown")),
        }
        self.rows.append(row)
        self.flush()
        return row

    def flush(self) -> None:
        self.path.write_text(json.dumps(self.rows, indent=2, default=str))

    def complete(self, scheduled: int) -> None:
        """Mark the block as having run to the end of its schedule.

        A block that ABORTS part-way leaves `<label>_trials.json` behind exactly as a
        finished one does, and `run_campaign.sh` skips a block whose trials file exists so
        that a resumed campaign never tops a condition up (V8). Without a marker those two
        states are indistinguishable, so an aborted block would be silently treated as
        DONE. This file is written only after the last trial of the schedule, so its
        ABSENCE beside a trials file means `partial`, which `run_campaign.sh` reports
        rather than skips silently. V8: n is what it was.
        """
        (self.out / f"{self.label}_complete.json").write_text(json.dumps({
            "label": self.label,
            "trials_scheduled": scheduled,
            "trials_written": len(self.rows),
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, indent=2))


class LogCursor:
    """I2 -- read the server's report lines for ONE action, not for the whole block.

    Copied from `2026-09-02-option-f-regions/harness/common.py` at `ac11d84`, itself copied
    from the 2026-09-01 rig. The block log accumulates a line per close and a trial issues
    more than one action, so attributing them by position in the file would break the first
    time an extra one appeared; each action's segment is bracketed by the file's size
    before and after it.
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

    def collect(self) -> list[dict]:
        return [
            {
                "commanded_mm": float(match.group(1)),
                "reached_mm": float(match.group(2)),
                "stalled": match.group(3) == "true",
                "reached_goal": match.group(4) == "true",
                "effort_n": float(match.group(5)),
                "verdict": match.group(6),
            }
            for match in REPORT.finditer(self.text())
        ]

    def await_report(self, ceiling_s: float = 5.0) -> list[dict]:
        """I2, waited for rather than sampled once -- and reported missing if it never came.

        WHY THIS IS NOT A TIMING WORKAROUND. The report line is written by ANOTHER process,
        to a file, after it sends the action result; the harness reads the result first, so
        at that instant the line legitimately may not have been flushed yet. Sampling once
        and moving on turns that race into a DATUM -- `stalled` recorded as `None`, and a
        record that stores booleans cannot tell an absent reading from a measured `false`.
        **V14 is the rule this feeds**, and V14 exists because without it the only rule that
        would notice such a trial is V4, which would attribute it to a WIDTH disagreement
        between two instruments that in fact agreed.

        This waits a BOUNDED interval for the instrument to produce its reading and, if it
        does not, says so on the record so the trial is excluded rather than counted. It
        sequences nothing and no cell waits on it (P4).
        """
        end = time.monotonic() + ceiling_s
        found = self.collect()
        while not found and time.monotonic() < end:
            time.sleep(0.05)
            found = self.collect()
        return found


# ---------------------------------------------------------------------------
# The validity rules that are evaluated WHERE THE BLOCK IS TAKEN
# ---------------------------------------------------------------------------
def v4(i1_reached_m: float | None, i3_reached_m: float | None,
       reports: list[dict] | None) -> dict:
    """V4, BOTH clauses, evaluated per trial where the data was taken.

    The two width instruments agree to 0.005 mm, and both round to the I2 log line's
    `%.1f`. A trial exceeding it is EXCLUDED from every bracket and REPORTED -- never
    absorbed, and never answered by widening the tolerance (V9: a threshold discovered to
    be wrong is applied literally and recorded as wrong).

    UNEVALUABLE IS NOT FAILED. A trial for which one of the two instruments does not exist
    has not exceeded anything; it is recorded as unevaluable and V14 or V5 is what excludes
    it, if anything does. Dropping it here would answer a missing instrument by discarding
    the data the instrument was never needed for.
    """
    result: dict = {"v4_tolerance_m": V4_TOLERANCE_M}
    if i1_reached_m is None or i3_reached_m is None:
        result["v4_ok"] = None
        result["v4_evaluable"] = False
        result["v4_unevaluable_reason"] = (
            "one of the two width instruments produced no reading on this trial")
        return result
    result["v4_evaluable"] = True
    delta = i1_reached_m - i3_reached_m
    result["v4_delta_m"] = delta
    result["v4_within_tolerance"] = abs(delta) <= V4_TOLERANCE_M
    # `reports[0]`, NOT `reports[-1]`. V14 reads `reports[0]`, and so does `measure.py`
    # when it lifts `stalled` and `reached_goal` onto the record -- so the DECISION
    # quantities all name I2's first line for this grasp. V4 named the last one. The two
    # are the same line today, because `execute_grasp` issues exactly one
    # `command_gripper` (`skill_server.cpp`) and `LogCursor` brackets one action's segment,
    # so nothing changes here. Two rules indexing the same event differently is how they
    # stop naming the same event: if a second line ever appeared, V4 would have validated
    # the width against a line the verdict did not come from.
    coarse = reports[0]["reached_mm"] if reports else None
    result["v4_i2_reached_mm"] = coarse
    if coarse is None:
        result["v4_rounds_to_i2"] = None
    else:
        result["v4_rounds_to_i2"] = (
            round(i1_reached_m * 1000.0, 1) == coarse
            and round(i3_reached_m * 1000.0, 1) == coarse
        )
    result["v4_ok"] = bool(result["v4_within_tolerance"] and result["v4_rounds_to_i2"])
    return result


def v14(reports: list[dict] | None, controller: dict | None,
        i1_reached_m: float | None, i4_width_m: float | None) -> dict:
    """V14 -- the log line is an instrument, and a missing one is a LOSS and not a `false`.

    Three clauses, all registered:

      1. a trial with no I2 line for its grasp is excluded and reported as an instrument
         loss, counted separately from V4's and V5's exclusions and NEVER recorded as a
         measured `false`;
      2. I4's two booleans must agree with I2's;
      3. `gripper_width_for(I4.position)` must be within 0.005 mm of I1's `reached_width_m`.

    THE RESIDUAL IS RECORDED RATHER THAN CLOSED, and `criteria.md` V14 states it: I4 is a
    SECOND `GripperCommand` against a joint already resting on the stop, so it is a second
    event, and its agreement with the first is what this rule CHECKS rather than what it
    assumes.
    """
    result: dict = {"v14_tolerance_m": V14_TOLERANCE_M}
    if not reports:
        result.update({
            "v14_ok": False,
            "v14_reason": "no I2 report line was read for this trial's grasp; the two "
                          "booleans are ABSENT and absent is not false",
            "v14_instrument_loss": True,
        })
        return result
    result["v14_instrument_loss"] = False
    if controller is None:
        result.update({
            "v14_ok": False,
            "v14_reason": "I4 produced no answer, so I2's booleans are unchecked",
        })
        return result
    booleans_agree = (
        bool(controller["stalled"]) == bool(reports[0]["stalled"])
        and bool(controller["reached_goal"]) == bool(reports[0]["reached_goal"])
    )
    result["v14_booleans_agree"] = booleans_agree
    if i1_reached_m is None or i4_width_m is None:
        result["v14_width_delta_m"] = None
        result["v14_widths_agree"] = None
        result["v14_ok"] = False
        result["v14_reason"] = "one of I1's and I4's widths is missing"
        return result
    delta = i4_width_m - i1_reached_m
    result["v14_width_delta_m"] = delta
    result["v14_widths_agree"] = abs(delta) <= V14_TOLERANCE_M
    result["v14_ok"] = bool(booleans_agree and result["v14_widths_agree"])
    if not result["v14_ok"]:
        result["v14_reason"] = (
            "I4 disagrees with I2 or with I1, so the campaign does not know what the "
            "predicate consumed"
        )
    return result


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """V8's 95 % interval on a proportion. `None` when there is nothing to bound."""
    if trials <= 0:
        return None
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return (max(0.0, centre - spread), min(1.0, centre + spread))
