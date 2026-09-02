#!/usr/bin/env python3
"""What all four arms share: provenance, the two predicate front ends, and the record.

DERIVED FROM the frozen 2026-09-01 rig -- the `Predicate`, `travel_from_plan` and
`LogCursor` shapes and the `REPORT` pattern come from
`docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fp.py` and
`measure_fn.py`, both copied at commit `eeaf903`. That directory is FROZEN
(`docs/measurements/README.md`) and nothing in it is edited from here.

WHY ONE MODULE RATHER THAN FOUR COPIES. The 2026-09-01 campaign copied its `Predicate`
into both of its runners, which is what a frozen harness forces on a campaign that
publishes twice. Inside ONE campaign a value in two places is still a value in two places
(P1), and this campaign has four runners, three of which bring the same cell up. The
provenance block especially: V1 discards a block, and a discard rule implemented four
times is four rules.

WHAT THIS MODULE MAY NOT DO. It computes no gripper arithmetic. Every number it hands out
comes either from the generated bring-up plan, from `git`, or from one of the two compiled
front ends. `arithmetic.py` is the reference implementation and it is not imported here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

#: The zone and the arm every campaign figure is taken on (`criteria.md` section 5.1).
ZONE = "cell_a"
ARM = "arm_1"
DRIVE_JOINT = f"{ARM}_drive_joint"

#: `criteria.md` V1. The campaign measures the branch as it stands at this commit; a block
#: whose `git diff BASE..HEAD -- model/ workspace/src/ tools/` is non-empty is DISCARDED,
#: not relabelled. `docs/measurements/` may advance and nothing else may.
BASE_COMMIT = "d3eeac4"
V1_WATCHED_PATHS = ("model/", "workspace/src/", "tools/")

#: `criteria.md` V2. The collision-mesh references the running description must carry for
#: the shipped `convex_hull` selection. The count is the criteria's; the STRING is the one
#: the 2026-09-01 rig counted and is kept so the two campaigns count the same thing.
HULL_COLLISION_REFERENCE = "cite_description/meshes/collision/xarm5/convex_hull"
HULL_COLLISION_REFERENCES_EXPECTED = 13

#: `criteria.md` V7. Arm B substitutes a fixture INTO the description and asserts the
#: production plugin before it does. Arm A may not be run on any mock backend at all
#: (section 5.1), and until 2026-09-02 nothing asserted that: the block checked only the
#: hull count. The same two strings are named here so that both halves of V7 count the
#: same thing (P1), and `running_geometry` reads them off the description the RUNNING cell
#: publishes -- which is the only place a mock could appear without anyone editing L0.
PRODUCTION_HARDWARE_PLUGIN = "gz_ros2_control/GazeboSimSystem"
MOCK_HARDWARE_PLUGIN = "mock_components/GenericSystem"

#: I2. The skill server's own report line, matched verbatim so that a change to the format
#: breaks this harness loudly instead of returning silence. `skill_server.cpp:2248-2255`.
REPORT = re.compile(
    r"gripper: commanded ([-+0-9.]+) mm, reached ([-+0-9.]+) mm, "
    r"stalled=(true|false), reached_goal=(true|false), effort=([-+0-9.]+) -> (holding|empty)"
)

#: The ten travel keys the skill server receives, plus the two ADR-0052 adds. Named here
#: once; every arm's record carries the dictionary this builds, so a figure can be
#: recomputed from the record alone.
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

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "raw"


def repo_root() -> Path:
    """The repository this harness is published inside.

    Resolved from this file's own location rather than from the working directory,
    because the campaign directory is four levels down and the runners are invoked from
    the repository root on the host and from `/workspace` in the container.
    """
    return HERE.parents[3]


# ---------------------------------------------------------------------------
# V1 and V2 -- the code and the geometry that actually ran
# ---------------------------------------------------------------------------
def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return f"<git {' '.join(arguments)} failed rc={result.returncode}: {result.stderr.strip()}>"
    return result.stdout.rstrip("\n")


def model_hash(root: Path) -> dict:
    """The MODEL_HASH of the generated tree, and of the INSTALLED package if there is one.

    Two readings rather than one, because they answer different questions. The source
    tree's says which model the repository describes; the installed one says which model
    the cell that is about to run was built from. A block taken against a stale install is
    a block about a cell nobody committed, and the pair is what makes that visible.
    """
    source = root / "workspace" / "src" / "cite_generated" / "MODEL_HASH"
    installed = root / "workspace" / "install" / "cite_generated" / "share" / \
        "cite_generated" / "MODEL_HASH"
    return {
        "source": source.read_text().strip() if source.exists() else None,
        "installed": installed.read_text().strip() if installed.exists() else None,
    }


def provenance(root: Path | None = None) -> dict:
    """`criteria.md` V1, as a dictionary every trial record carries.

    `v1_clean` is the rule, evaluated here rather than left to the write-up: the three
    watched paths must be identical to the base commit AND unmodified in the working
    tree. `docs/measurements/` is deliberately not watched -- this campaign's own
    `criteria.md`, harness and raw all land on the same branch, so `HEAD` necessarily
    advances while it runs, and pinning `HEAD` would discard every block including the
    first.
    """
    root = root or repo_root()
    head = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain")
    diff = _git(root, "diff", "--name-only", f"{BASE_COMMIT}..HEAD", "--", *V1_WATCHED_PATHS)
    dirty = _git(root, "status", "--porcelain", "--", *V1_WATCHED_PATHS)
    return {
        "head": head,
        "base_commit": BASE_COMMIT,
        "git_status_porcelain": status,
        "watched_diff_against_base": diff,
        "watched_worktree_dirty": dirty,
        "v1_clean": diff == "" and dirty == "",
        "model_hash": model_hash(root),
        "criteria_sha256": _sha256(HERE.parent / "criteria.md"),
    }


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def host_facts() -> dict:
    """What section 9 requires recorded per block, read from inside the container.

    The load averages are recorded because host load moves how long a trial takes, and
    V6 is what spends them. They are NOT recorded because any width quantity depends on
    them: every width here is a function of simulation state sampled in simulation time.

    THESE ARE THE CONTAINER'S LOAD AVERAGES AND NOT THE HOST'S, and the keys say so.
    `os.getloadavg()` inside a Linux container on macOS reads `/proc/loadavg` in Docker
    Desktop's Linux VM, whose run queue is the VM's and whose core count is the VM's
    allocation -- not the twelve cores of the `Mac16,8` section 9 names. The 2026-08-31
    capacity campaign applied a validity rule that read exactly this wrong quantity, and
    the keys were named `load_*` there too. Naming them for what they measure is the fix;
    a figure that needs the HOST's load has to be taken on the host, and `run_campaign.sh`
    is the half of this harness that runs there.
    """
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:  # pragma: no cover - not every platform has it
        one = five = fifteen = float("nan")
    return {
        "container_load_1m": one,
        "container_load_5m": five,
        "container_load_15m": fifteen,
        "load_read_from": "/proc/loadavg inside the container (Docker Desktop's Linux "
                          "VM), NOT the macOS host criteria.md section 9 names",
        "container_cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "wall_clock_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "gz_partition": os.environ.get("GZ_PARTITION"),
    }


def running_geometry(namespace: str, timeout_s: float = 300.0) -> dict:
    """V2 -- count collision-mesh references in the description the RUNNING cell publishes.

    Off the running node and not off the model file, which is the difference between
    "the tree declares hulls" and "the cell that produced these numbers ran on hulls".
    """
    running = subprocess.run(
        ["ros2", "param", "get", f"{namespace}/description_publisher", "robot_description"],
        capture_output=True, text=True, timeout=timeout_s,
    ).stdout
    hulls = running.count(HULL_COLLISION_REFERENCE)
    # V7, off the SAME fetch. The description is already here, so counting the hardware
    # plugin costs nothing and closes the hole Arm A had: a mock backend fabricates a
    # stall on a ramping joint after exactly `stall_timeout`, which is the one failure
    # mode Arm A's whole question turns on, and the hull count would not have noticed it.
    production = running.count(PRODUCTION_HARDWARE_PLUGIN)
    mock = running.count(MOCK_HARDWARE_PLUGIN)
    return {
        "hull_collision_refs": hulls,
        "vendor_visual_refs": running.count("xarm_description/meshes/xarm5/visual"),
        "description_chars": len(running),
        "v2_ok": hulls == HULL_COLLISION_REFERENCES_EXPECTED,
        "production_hardware_plugin_refs": production,
        "mock_hardware_plugin_refs": mock,
        # Both clauses, because either one alone can be satisfied by an empty answer: a
        # `ros2 param get` that returned nothing counts zero mocks as readily as zero
        # production plugins, and "no mock found" must not be reachable by not looking.
        "v7_ok": production > 0 and mock == 0,
    }


# ---------------------------------------------------------------------------
# The two compiled front ends
# ---------------------------------------------------------------------------
class _BatchProgram:
    """A line-oriented conversation with a compiled front end.

    Held open for the length of a block rather than started per question: the campaign
    asks a few thousand of these, and a process launch per question would make the
    instrument the expensive part.
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
    """The SHIPPED arithmetic at `d3eeac4`, through `predicate_eval`.

    `holding` here is the shipped predicate evaluated on inputs the harness supplies. It
    is NOT where `holding_F` comes from: `criteria.md` section 3 requires every reported
    verdict to be read off the running node, out of `Grasp.Result.holding`. This is the
    instrument for I6, for the derived widths, and for the sweep arithmetic.
    """

    def __init__(self, executable: Path, travel: dict, parts: dict) -> None:
        super().__init__(executable, {**travel, **parts})

    def width(self, q: float) -> float:
        return float(self.ask(f"width {q!r}"))

    def position(self, width_m: float) -> float:
        return float(self.ask(f"position {width_m!r}"))

    def tolerance(self, q: float) -> float:
        return float(self.ask(f"tolerance {q!r}"))

    def pad_offset(self, q: float) -> float:
        return float(self.ask(f"padoffset {q!r}"))

    def margin(self, width_m: float) -> float:
        return float(self.ask(f"margin {width_m!r}"))

    def max_width(self) -> float:
        return float(self.ask("maxwidth"))

    def holding(self, commanded_m: float, q: float, stalled: bool, reached_goal: bool) -> bool:
        return self.ask(
            f"holding {commanded_m!r} {q!r} {int(stalled)} {int(reached_goal)}") == "1"

    def resolve(self, requested_m: float, default_m: float) -> tuple[str, float]:
        """I6 -- `resolve_grasp_width`'s own verdict on a width a caller may ask for."""
        source, width = self.ask(f"resolve {requested_m!r} {default_m!r}").split()
        return source, float(width)

    def describe(self) -> dict:
        return {"travel": self.ask("travel"), "parts": self.ask("parts")}


class SupersededPredicate(_BatchProgram):
    """The predicate at `4ef2d7c`, through a BUILD of that commit (`criteria.md` V10).

    Never a reimplementation. `build_superseded.sh` records the worktree commit and the
    binary's sha256 in `raw/provenance.txt`; a trial without that provenance reports
    `holding_F` alone, which is what `available` is read for.
    """

    def __init__(self, executable: Path, travel: dict) -> None:
        # The superseded `GripperTravel` has no bands, and its front end REFUSES an
        # unknown key rather than ignoring it -- so the two are filtered out here rather
        # than silently accepted, which is the behaviour that would let a band reach a
        # predicate that has no place to put it.
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


def superseded_provenance() -> dict:
    """What V10 asks for, read back out of `raw/` so a record can carry it."""
    path = RAW / "predicate_eval_superseded_provenance.txt"
    if not path.exists():
        return {"available": False}
    fields = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    fields["available"] = fields.get("worktree_commit_short") == "4ef2d7c" and \
        bool(fields.get("binary_sha256"))
    return fields


# ---------------------------------------------------------------------------
# The plan, read once
# ---------------------------------------------------------------------------
def load_plan():
    """The generated bring-up plan and `arm_1`'s controller-manager entry."""
    from cite_bringup import plan as bringup_plan

    document = bringup_plan.load(bringup_plan.default_plan_path(ZONE))
    manager = next(entry for entry in document.controller_managers if entry.asset == ARM)
    return document, manager


def travel_from_plan(manager) -> dict:
    """The twelve travel parameters as the SKILL SERVER receives them, from the plan."""
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


def window_m(travel: dict, parts: dict) -> tuple[float, float]:
    """F's window, computed from the same four statements the running node is given.

    `criteria.md` section 2.1 states it as [47.615, 52.385] mm on the shipped model. That
    number is NOT used: it is derived here from the plan, so that if L0 moves this
    harness follows it rather than measuring against a literal (P1).
    """
    return (
        parts["narrowest_m"] - travel["stall_band_narrow_m"],
        parts["widest_m"] + travel["stall_band_wide_m"],
    )


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class TrialWriter:
    """One JSON array per arm-block, rewritten after every trial.

    Rewritten rather than appended, so that a block killed part-way leaves a file that
    parses. V8 -- every count is reported over the trials that actually ran -- depends on
    the partial file being readable, and a truncated last object would lose the whole
    block instead of the last trial.
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
        # The provenance travels ON EVERY RECORD and not only in the header. A record
        # lifted out of this file into a table is a record that has left its header
        # behind, and V1 is a per-block rule whose evidence must not be separable from
        # the numbers it validates.
        #
        # The window and the declared part interval travel with it for the same reason
        # and one more: they are the reference every width in the record is judged
        # against, and an analyser that had to supply them would be supplying a fifth
        # copy of four L0 statements (P1).
        # V2 and V7 are BLOCK properties and were only ever in the header, so an
        # analyser reading `raw/*_trials.json` could not apply them and said it did.
        # They ride here for the same reason the provenance does: a rule that discards
        # a block must not be separable from the numbers it discards. `None` means the
        # rig does not have the quantity -- Arm B brings no cell up and reads no running
        # description -- and is NOT the same answer as `False`.
        geometry = self.header.get("geometry") or {}
        row = {
            **row,
            "provenance": self.header["provenance"],
            "label": self.label,
            "window_m": self.header.get("window_m"),
            "parts": self.header.get("parts"),
            "v2_ok": geometry.get("v2_ok"),
            "v7_ok": geometry.get("v7_ok"),
        }
        self.rows.append(row)
        self.flush()
        return row

    def flush(self) -> None:
        self.path.write_text(json.dumps(self.rows, indent=2, default=str))


#: `criteria.md` V4's tolerance: the two width instruments must agree to 0.100 mm.
V4_TOLERANCE_M = 0.0001

#: How long I2's report line is waited for before it is recorded as MISSING. It is a
#: ceiling on an instrument's read, not a settling time: the line is already written by
#: the time the action result arrives in every observed case, and this only covers the
#: flush. A trial that exhausts it is excluded and reported, never counted as `false`.
I2_REPORT_CEILING_S = 5.0


def v4(i1_reached_m: float | None, i3_reached_m: float | None,
       reports: list[dict] | None, unevaluable_reason: str | None = None) -> dict:
    """`criteria.md` V4, BOTH halves, evaluated per trial where the data was taken.

    The rule has two clauses and this evaluates both: the two instruments agree to
    0.100 mm, and both round to the I2 log line's `%.1f`. A trial exceeding it is
    EXCLUDED from the distribution and REPORTED -- never absorbed, and never answered by
    widening the tolerance (V9: a threshold discovered to be wrong is applied literally
    and recorded as wrong).

    WHAT IT WILL DO IN FREE AIR, said here before the first trial rather than discovered
    in the analysis. I1 is the position the controller reported at the instant it ENDED
    the goal, and `GripperActionController` ends one as soon as `|error| < goal_tolerance`
    -- so in free air the joint is still MOVING when that happens, and keeps closing
    towards the command afterwards. I3 is "the last sample at or before the result
    arrives", which is later. The two therefore read a moving joint at two different
    instants, and the gap is bounded by roughly one `goal_tolerance` of width, which on
    this linkage is about ten times V4's tolerance. Against a STALLED joint -- arms B, C
    and D -- they read a joint that is not moving and agree closely. So V4 is expected to
    fire across Arm A for a structural reason and not for a defect, and `i3_window_trace`
    is published on every record so that the write-up can say so with the numbers rather
    than by assertion.
    """
    result: dict = {"v4_tolerance_m": V4_TOLERANCE_M}
    if unevaluable_reason is not None:
        # UNEVALUABLE IS NOT FAILED, and the difference decides whether a trial is in
        # the distribution. V4 excludes a trial "exceeding" its tolerance; a trial for
        # which one of the two instruments DOES NOT EXIST has not exceeded anything, and
        # dropping it would answer a missing instrument by discarding the data the
        # instrument was never needed for. `analyse.py` reports these separately and
        # keeps them in the distribution; a trial that HAS both instruments and fails the
        # comparison is still dropped, literally, as V9 requires.
        result["v4_ok"] = None
        result["v4_evaluable"] = False
        result["v4_unevaluable_reason"] = unevaluable_reason
        return result
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
    coarse = reports[-1]["reached_mm"] if reports else None
    result["v4_i2_reached_mm"] = coarse
    if coarse is None:
        result["v4_rounds_to_i2"] = None
    else:
        result["v4_rounds_to_i2"] = (
            round(i1_reached_m * 1000.0, 1) == coarse
            and round(i3_reached_m * 1000.0, 1) == coarse
        )
    result["v4_ok"] = bool(
        result["v4_within_tolerance"] and result["v4_rounds_to_i2"])
    return result


class LogCursor:
    """I2 -- read the server's report lines for ONE action, not for the whole block.

    Copied from `2026-09-01-grasp-discrimination/harness/measure_fn.py` at `eeaf903`.
    The block log accumulates a line per close and a trial issues several, so attributing
    them by position in the file would break the first time a retry inserted one; each
    action's segment is bracketed by the file's size before and after it.
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
        found = []
        for match in REPORT.finditer(self.text()):
            found.append(
                {
                    "commanded_mm": float(match.group(1)),
                    "reached_mm": float(match.group(2)),
                    "stalled": match.group(3) == "true",
                    "reached_goal": match.group(4) == "true",
                    "effort_n": float(match.group(5)),
                    "verdict": match.group(6),
                }
            )
        return found

    def await_report(self, ceiling_s: float = I2_REPORT_CEILING_S) -> list[dict]:
        """I2, waited for rather than sampled once -- and reported missing if it never came.

        WHY THIS IS NOT A TIMING WORKAROUND. The report line is written by ANOTHER
        process, to a file, after it sends the action result; the harness reads the result
        first, so at that instant the line legitimately may not have been flushed yet.
        Sampling once and moving on turned that race into a DATUM: `collect()` returned
        an empty list, the runner wrote `stalled = None`, and `analyse.py` counted it with
        `sum(1 for r in at if r.get("stalled"))`, which cannot tell an absent reading from
        a measured `false`. A1a -- the clause that decides WHICH of option F's two gates
        rejected free air -- is a count of exactly that boolean, so a dropped line would
        have read as evidence for the flags rejecting, which is the answer the arm exists
        to test.

        This waits a BOUNDED interval for the instrument to produce its reading and, if it
        does not, says so on the record (`i2_report_missing`) so the trial is excluded
        rather than counted. It sequences nothing and no cell waits on it (P4).
        """
        end = time.monotonic() + ceiling_s
        found = self.collect()
        while not found and time.monotonic() < end:
            time.sleep(0.05)
            found = self.collect()
        return found
