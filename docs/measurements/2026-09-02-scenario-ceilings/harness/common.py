#!/usr/bin/env python3
"""What the runner and the analyser share: provenance, the console parser, the record.

DERIVED IN SHAPE FROM
`docs/measurements/2026-09-02-option-f-regions/harness/common.py`, copied at commit
`ac11d84` -- the "provenance travels on every record", `_git`, `host_facts` and
`TrialWriter` shapes are that file's. The `bash -c` isolation read comes from
`run_campaign.sh` in the same directory at commit `62051df`. Both are FROZEN
(`docs/measurements/README.md`) and nothing in either is edited from here.

WHY ONE MODULE RATHER THAN TWO COPIES. Inside one campaign a value in two places is
still a value in two places (P1). The runner evaluates the validity flags where the block
is taken and the analyser reads them off the record; they must agree on the field names,
on the regex that finds a record, and on the five paths V1 watches, or the two halves of
this campaign disagree about what was measured.

WHAT THIS MODULE MAY NOT DO. It computes no margin, applies no band and drops no record.
Every rule in `criteria.md` section 7 lives in `analyse.py`, which is written before the
first trial for exactly that reason.

NOTHING HERE EDITS THE TREE. `criteria.md` section 0 forbids editing `model/`,
`workspace/src/`, `tools/`, `tests/` and `scripts/`, and V1 discards any block taken while
one of those five differs from the base commit. This module reads them and writes only
under this campaign's own `raw/`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

#: `criteria.md` V1. Every figure is a property of the tree at this commit.
BASE_COMMIT = "c38a42c"

#: `criteria.md` section 0 and V1. FIVE paths, not three. All nine `*_CEILING_S`
#: declarations and every `_emit_timing` call site are under `tests/scenarios/`, and
#: `scripts/` holds I2's verdict strings and the `cite_project_name` this file derives the
#: container name from. Watching only the first three would leave `v1_clean` true while a
#: ceiling value, a `what` string or a spin quantum changed mid-campaign, which is the one
#: thing the rule exists to prevent.
V1_WATCHED_PATHS = ("model/", "workspace/src/", "tools/", "tests/", "scripts/")

#: I1. Anchored on the payload, NEVER a fixed slice after `startswith`. CPython's `print`
#: issues `file.write(payload)` and then `file.write(end)`, and the emitting test runs on a
#: thread that shares `sys.stdout` with the launch service, so a foreign write can land
#: between the two (`criteria.md` threat 6). A search for the JSON object survives a
#: prefix that arrived with something else glued to its front; a slice does not.
TIMING_RE = re.compile(r"CITE_TIMING (\{.*\})")

#: How a line is recognised as a `CITE_TIMING` line AT ALL, for rule G's denominator. A
#: line carrying the marker but not parsing is mangled; the ratio of the two is what rule
#: G's 5 % is taken over.
TIMING_MARKER = "CITE_TIMING"

#: `criteria.md` section 2.3. The exact key set, asserted by
#: `tests/scenarios/guards/test_timing_records.py`. A record parsing to any other key set
#: is mangled under rule G -- it is not silently accepted with the extra keys ignored,
#: because a record with a key this campaign has never seen is a record from an emitter
#: this campaign has not read.
TIMING_KEYS = frozenset(
    {"scenario", "test", "what", "ceiling_s", "elapsed_s", "spins", "monotonic_s"}
)

#: Colour is stripped before any verdict match. `scripts/_lib.sh` emits SGR sequences when
#: stdout is a TTY, and the campaign captures through a pipe where it does not -- but the
#: capture also carries the launch service's own output, which is not `_lib.sh`'s and does
#: colour itself. Matching on a stripped copy makes the instrument independent of that.
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
RAW = CAMPAIGN / "raw"

#: The three scenarios, in the order `criteria.md` section 3 names them.
SCENARIOS = ("bringup", "pick_and_place", "continuous_line")

#: `criteria.md` section 3. FULL is the container unconstrained; the rest are
#: `docker update --cpus`. The value is what is handed to `--cpus`; `None` means no limit
#: is applied at all, which is not the same act as applying `--cpus 0`.
CONDITIONS: dict[str, float | None] = {"FULL": None, "C4": 4.0, "C2": 2.0, "C1": 1.0}

#: `criteria.md` V6. A loaded run whose limit landed later than this into the container's
#: life is DISCARDED and reported: part of its bring-up ran unconstrained, and bring-up is
#: one of the intervals under measurement.
V6_LIMIT_DELAY_CEILING_S = 10.0

#: `criteria.md` V7. Not an exclusion threshold -- no run is discarded for load. A run
#: above it is FLAGGED, and every margin it contributes to is reported with and without
#: it. Sixteen cores, so this is a quarter of the machine.
V7_LOAD_FLAG = 4.0

#: `criteria.md` V2. What the RUNNING cell must read back for the run to count. The
#: collision selection is `convex_hull` (ADR-0028) and the world carries ADR-0043's
#: throttle. Both are read off the running cell rather than off the tree, which is the
#: difference between "the tree declares it" and "the cell that produced these numbers ran
#: on it".
HULL_COLLISION_REFERENCE = "meshes/collision/xarm5/convex_hull"
WORLD_THROTTLE_ELEMENT = "<real_time_factor>1</real_time_factor>"

#: Where V2's two readings are taken from, inside the container. The description comes off
#: the running node; the world is the INSTALLED copy the cell loaded, which lives in a
#: named volume and is therefore unreachable from the host.
DESCRIPTION_NODE = "/cite/cell_a/arm_1/description_publisher"
INSTALLED_WORLD = (
    "/workspace/workspace/install/cite_generated/share/cite_generated/worlds/cell_a.sdf"
)

#: `criteria.md` rule Q, section 7.1's table, read from the emitters at `c38a42c`. The
#: quantum is a property of the EMITTING SITE and not of the run, which is why it can be
#: registered before any trial. Keyed by (scenario, exact `what`) where the `what` is
#: fixed text, and by a compiled pattern where it carries run-time text.
#:
#: 0.5 s is the default: `_spin_until` and `_await_future` both spin on a 0.5 s quantum and
#: most predicates return immediately. The entries below are the sites that do not.
_QUANTUM_DEFAULT_S = 0.5
_QUANTUM_RULES: tuple[tuple[str, re.Pattern[str], float], ...] = (
    # `bringup`'s four `wait_for_service` / `wait_for_server` waits: the predicate itself
    # blocks for 0.5 s, on top of the 0.5 s spin.
    ("bringup", re.compile(r"^/cite/cell_a/arm_\d+/controller_manager to appear$"), 1.0),
    ("bringup", re.compile(r"^/cite/cell_a/arm_\d+/arm_\d+_gripper_controller/gripper_cmd$"), 1.0),
    (
        "bringup",
        re.compile(
            r"^/cite/cell_a/arm_\d+/arm_\d+_joint_trajectory_controller/"
            r"follow_joint_trajectory$"
        ),
        1.0,
    ),
    ("bringup", re.compile(r"^the arm_\d+ skill server$"), 1.0),
    # The largest quantum in the tree: `active` calls `spin_until_future_complete` with a
    # 10.0 s timeout. Rule A drops this wait for an unrelated reason, so it reaches no
    # margin -- it is registered here so that the drop is visible rather than looking like
    # an omission (`criteria.md` threat 5).
    ("bringup", re.compile(r"^arm_\d+'s controllers to be active$"), 10.5),
    # `pick_and_place`'s skill-server wait: `wait_for_server(timeout_sec=1.0)`.
    (
        "pick_and_place",
        re.compile(r"^the skill server, and therefore the whole stack beneath it$"),
        1.5,
    ),
    # `pick_and_place._run_cycle` spins on that file's own `SAMPLE_PERIOD_S = 2.0`.
    ("pick_and_place", re.compile(r"^the station cycle to run to completion$"), 2.0),
)


def poll_quantum_s(scenario: str, what: str) -> float:
    """Rule Q's `q` for one record's emitting site.

    Registered from the emitters' source and never from the data. `q` is subtracted from
    the MAXIMUM only, never from a median or an IQR: the margin is defined on the maximum,
    and `ceiling / (max - q)` is an upper bound on the true margin rather than a corrected
    distribution.
    """
    for site, pattern, quantum in _QUANTUM_RULES:
        if site == scenario and pattern.match(what):
            return quantum
    return _QUANTUM_DEFAULT_S


# ---------------------------------------------------------------------------
# I1 and rule G -- the console parser
# ---------------------------------------------------------------------------
def parse_timing(console: str) -> dict:
    """Every `CITE_TIMING` record in a captured console, and every mangled one.

    Rule G: a line carrying the marker but failing `json.loads` on the regex group, or
    parsing to a key set other than the seven, is COUNTED AND REPORTED. It is never
    silently dropped -- a parser that discards what it cannot read reports a clean run
    over a console it did not understand.

    The denominator rule G's 5 % is taken over is `marker_lines`: every line carrying the
    marker at all, whether or not it parsed. Counting only the ones that parsed would make
    the ratio smaller exactly when it should be larger.
    """
    records: list[dict] = []
    mangled: list[str] = []
    marker_lines = 0
    for line in console.splitlines():
        if TIMING_MARKER not in line:
            continue
        marker_lines += 1
        match = TIMING_RE.search(line)
        if match is None:
            mangled.append(line)
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            mangled.append(line)
            continue
        if not isinstance(payload, dict) or frozenset(payload) != TIMING_KEYS:
            mangled.append(line)
            continue
        records.append(payload)
    return {
        "records": records,
        "mangled": mangled,
        "mangled_count": len(mangled),
        "marker_lines": marker_lines,
        # Rule G's own discard, evaluated here so that it travels with the run rather than
        # being re-derived by a reader. A run above the fraction is discarded because at
        # that point the campaign does not know what it is missing.
        "mangled_fraction": (len(mangled) / marker_lines) if marker_lines else 0.0,
        "g_ok": marker_lines == 0 or (len(mangled) / marker_lines) <= 0.05,
    }


def verdict_of(console: str, scenario: str) -> dict:
    """I2 -- `scripts/scenario`'s own verdict line, never the exit code.

    Three states, not two. `scripts/scenario` prints `passed` only when `launch_test`
    itself exited 0, which it cannot do while a post-shutdown assertion is failing; it
    prints `passed its cycle assertions` on the advisory branch; and `failed -- ...`
    otherwise. This campaign passes no `--teardown-advisory`, so the middle string should
    never appear -- it is matched anyway, because an instrument that cannot see a state is
    an instrument that reports the wrong one when it happens.

    `absent` is its own answer and is NOT a failure: it means the run produced no verdict
    line at all, which rule P treats as a trial that produced nothing rather than as a
    trial that failed.
    """
    plain = ANSI_RE.sub("", console)
    name = re.escape(scenario)
    if re.search(rf"Scenario '{name}' passed its cycle assertions", plain):
        state = "cycle_only"
    elif re.search(rf"Scenario '{name}' passed", plain):
        state = "passed"
    elif re.search(rf"Scenario '{name}' failed", plain):
        state = "failed"
    else:
        state = "absent"
    line = ""
    for candidate in plain.splitlines():
        if f"Scenario '{scenario}'" in candidate:
            line = candidate.strip()
    return {"verdict": state, "verdict_line": line}


# ---------------------------------------------------------------------------
# V1 -- the code that ran, read at BOTH ends of every run
# ---------------------------------------------------------------------------
def repo_root() -> Path:
    """The repository this harness is published inside.

    Resolved from this file's own location, not from the working directory: the campaign
    directory is four levels down and the runner is invoked from the repository root.
    """
    return HERE.parents[3]


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return f"<git {' '.join(arguments)} failed rc={result.returncode}: {result.stderr.strip()}>"
    return result.stdout.rstrip("\n")


def snapshot(root: Path | None = None) -> dict:
    """I6, ONE reading. V1 needs two of these and conjoins them.

    `docs/measurements/` is deliberately not watched: this campaign's own `criteria.md`,
    harness and raw all land on this branch, so `HEAD` necessarily advances while the
    campaign runs and pinning it would discard every block including the first.
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
    }


def v1(start: dict, end: dict) -> dict:
    """V1 -- the conjunction, evaluated where the block was taken.

    A run lasts minutes. A single snapshot at the start would leave the flag true for the
    whole run while an edit landed inside it, and V10's promise that a concurrent writer
    flips the flag would be prose ahead of the mechanism. Two readings, conjoined; and a
    run whose two readings DISAGREE is reported as an edit that landed mid-run, which is a
    different finding from a run that was dirty throughout.
    """
    return {
        "start": start,
        "end": end,
        "v1_clean": bool(start["clean"] and end["clean"]),
        "disagreed_mid_run": start["clean"] != end["clean"],
        "head_moved_mid_run": start["head"] != end["head"],
        "base_commit": BASE_COMMIT,
        "watched_paths": list(V1_WATCHED_PATHS),
    }


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# I5 and section 9 -- the host
# ---------------------------------------------------------------------------
def host_load() -> dict:
    """I5, taken ON THE HOST.

    `criteria.md` section 9 demonstrates that on this host a container's `/proc/loadavg`
    reading IS the host's -- the file is not namespaced on native Linux and there is no
    `lxcfs` in the way. This runner is host-side anyway, so the reading needs no such
    argument; the key says where it came from because the 2026-08-31 capacity campaign
    applied a validity rule that read a Docker Desktop VM's load instead.
    """
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:  # pragma: no cover - not every platform has it
        one = five = fifteen = float("nan")
    return {
        "load_1m": one,
        "load_5m": five,
        "load_15m": fifteen,
        "load_read_from": "/proc/loadavg on the host",
        "uptime": _run(["uptime"]).strip(),
        "wall_clock_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def host_facts() -> dict:
    """Section 9's machine block, recorded per run rather than asserted once."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "host_cpu_count": os.cpu_count(),
        "docker_version": _run(["docker", "--version"]).strip(),
        "image_id": _run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", "cite-digital-twin:dev"]
        ).strip(),
    }


def _run(argv: list[str], timeout: float = 120.0) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"<{' '.join(argv)} failed: {exc}>"
    return result.stdout if result.returncode == 0 else f"<rc={result.returncode}> {result.stderr}"


# ---------------------------------------------------------------------------
# Isolation, I4 and I7 -- the container
# ---------------------------------------------------------------------------
def isolation(root: Path | None = None) -> dict:
    """`COMPOSE_PROJECT_NAME` and `ROS_DOMAIN_ID`, DERIVED and never typed in.

    Section 4.4: the 2026-08-29 harness hard-codes its own checkout's compose project name
    and therefore finds nothing from a different checkout. This reads it from
    `scripts/_lib.sh`, which is where `cite_project_name` lives, so the value cannot drift
    from the one `./scripts/scenario` will use.

    UNDER BASH, BY ABSOLUTE PATH. `_lib.sh` computes `REPO_ROOT` from `${BASH_SOURCE[0]}`,
    which no other shell sets; sourcing it from anything else derives a project name and a
    domain that are both wrong and look exactly as plausible as the right ones. That is
    the failure the option-f campaign spent a comment on, and it is not repeated here.
    """
    root = root or repo_root()
    script = (
        '. "$1/scripts/_lib.sh" >/dev/null 2>&1\n'
        'printf "%s\\n%s\\n%s\\n" "${COMPOSE_PROJECT_NAME:-<unset>}" '
        '"${ROS_DOMAIN_ID:-<unset>}" "${CITE_PROJECT_SOURCE:-<unset>}"\n'
    )
    out = _run(["bash", "-c", script, "_", str(root)])
    parts = (out.splitlines() + ["<unset>", "<unset>", "<unset>"])[:3]
    return {
        "compose_project_name": parts[0],
        "ros_domain_id": parts[1],
        "compose_project_source": parts[2],
        "derived_from": "scripts/_lib.sh cite_project_name, sourced under bash",
    }


def find_container(project: str) -> str:
    """The scenario's container, matched on the compose project's own naming.

    `scripts/_lib.sh` runs a scenario with `compose run --rm dev` when no dev service is
    up, and `compose exec` when one is; both produce a container whose name starts with
    the project name and the service. An empty string means none was found, which the
    caller must treat as a fact rather than as a reason to guess.
    """
    out = _run(
        ["docker", "ps", "--filter", f"name={project}-dev", "--format", "{{.ID}}"]
    )
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("<"):
            return line
    return ""


def container_started_at(cid: str) -> str:
    return _run(["docker", "inspect", "--format", "{{.State.StartedAt}}", cid]).strip()


def cpu_allocation(cid: str) -> dict:
    """I4 -- the allocation that was ACTUALLY in force, read two ways.

    Not `nproc` and not `.HostConfig.CpuQuota`: `criteria.md` section 9 measures that
    neither moves when the limit does. `nproc` reports `sched_getaffinity`, which a CFS
    quota does not touch, and `docker inspect` leaves `CpuQuota` at 0 while moving
    `NanoCpus`. A harness reading either concludes "no limit" on a limited container.
    """
    inside = _run(["docker", "exec", cid, "cat", "/sys/fs/cgroup/cpu.max"]).strip()
    outside = _run(
        ["docker", "inspect", "--format", "{{.HostConfig.NanoCpus}}", cid]
    ).strip()
    return {
        "cgroup_cpu_max_inside": inside,
        "host_config_nano_cpus": outside,
        "read_at": time.time(),
    }


def running_configuration(cid: str) -> dict:
    """I7 and V2 -- read back from the RUNNING cell, not from the tree.

    Two readings. The description comes off the node the launch graph started, which is
    the only place a collision selection nobody committed could appear. The world is the
    INSTALLED copy the cell loaded, which lives in a named volume and so cannot be read
    from the host at all.

    A reading that failed is recorded as failed. `v2_ok` is a conjunction of two positive
    findings, never of two absences: an empty answer counts zero hull references as
    readily as a vendor-mesh description does, and "no vendor mesh found" must not be
    reachable by not looking.
    """
    prelude = (
        ". /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash >/dev/null 2>&1; "
        ". /workspace/workspace/install/setup.bash >/dev/null 2>&1; "
    )
    description = _run(
        [
            "docker",
            "exec",
            cid,
            "bash",
            "-lc",
            prelude + f"ros2 param get {DESCRIPTION_NODE} robot_description",
        ],
        timeout=180.0,
    )
    world = _run(["docker", "exec", cid, "cat", INSTALLED_WORLD], timeout=120.0)
    hulls = description.count(HULL_COLLISION_REFERENCE)
    throttled = WORLD_THROTTLE_ELEMENT in "".join(world.split())
    return {
        "hull_collision_refs": hulls,
        "description_chars": len(description),
        "description_read_ok": "robot_description" in description or hulls > 0,
        "world_throttle_declared": throttled,
        "world_read_ok": "<sdf" in world,
        "read_at": time.time(),
        "v2_ok": hulls > 0 and throttled,
    }


# ---------------------------------------------------------------------------
# V5 -- one cell, no survivors
# ---------------------------------------------------------------------------
def survivors() -> dict:
    """V5 -- what was still running when this run started, and what it left behind.

    Reported rather than quietly cleaned before the fact: a survivor from a predecessor
    invalidates the run that meets it, and a harness that kills it first has destroyed the
    evidence of its own invalidity. On native Linux the host's process table shows the
    container's processes, so `pgrep` sees them; the container count is taken as well
    because the two can disagree.
    """
    # `pgrep` exits 1 when nothing matches, which `_run` renders as an `<rc=1>` marker.
    # Counting that marker as a process reported a survivor on every clean host and would
    # have discarded the whole campaign under V5. The distinction between "no match" and
    # "failed to look" is the one that matters, so it is made explicitly here rather than
    # by filtering the marker out of the text afterwards.
    try:
        found = subprocess.run(
            ["pgrep", "-af", "gz sim"], capture_output=True, text=True, timeout=60
        )
        lines = (
            [line for line in found.stdout.splitlines() if line.strip()]
            if found.returncode == 0
            else []
        )
        looked = found.returncode in (0, 1)
    except (OSError, subprocess.SubprocessError):
        lines = []
        looked = False
    names = _run(["docker", "ps", "--format", "{{.Names}}"])
    cite = [line for line in names.splitlines() if line.startswith("cite-")]
    return {
        "gz_sim_processes": lines,
        "gz_sim_count": len(lines),
        # "nothing was found" and "the search did not run" are different answers, and V5
        # may not be satisfied by the second. A run whose search failed carries
        # `looked_ok: false` and the analyser can see that it was never really checked.
        "looked_ok": looked,
        "cite_containers": cite,
        "cite_container_count": len(cite),
    }


def clear_survivors() -> str:
    """Kill what the teardown did not, AFTER the survivor reading has been taken."""
    return _run(["pkill", "-9", "-f", "gz sim"]) + _run(["pkill", "-9", "-f", "ruby.*gz"])


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class RunWriter:
    """One JSON object per run, written whole at the end and once more on the way.

    `criteria.md` section 6 lists what every run records; this is that list as a file. The
    validity flags are computed HERE, where the run was taken, and travel ON the record:
    `analyse.py` reads them and must never re-derive them from a tree that has since
    moved. Not a note in a README, not a check at the end -- a field.
    """

    def __init__(self, out: Path, label: str) -> None:
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.label = label
        self.path = self.out / f"{label}.json"
        self.console_path = self.out / f"{label}.log"

    def write(self, document: dict) -> Path:
        self.path.write_text(json.dumps(document, indent=2, default=str))
        return self.path
