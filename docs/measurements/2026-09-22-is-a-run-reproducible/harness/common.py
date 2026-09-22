#!/usr/bin/env python3
"""Every registered constant of this campaign, and the mechanism its trials share.

The rig for [`../criteria.md`](../criteria.md). **Read that file first.** Every
threshold, every n, every instrument and every validity rule lives there and is
deliberately not restated here (P1). What this module carries is the machinery,
with the `criteria.md` clause that registers each value named beside it.

DERIVED FROM `docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/trial.py`,
copied at commit `fca1391` -- the commit that file last landed at -- for
`load_average`, for `installed_configuration`'s way of reading the configuration
under test off the INSTALLED artifacts through `ros2 pkg prefix cite_generated`,
and for the one-invocation-one-record shape. That directory is FROZEN
(`docs/measurements/README.md` rule 2) and nothing in it is edited from here.
**No campaign imports from another**; this is a copy, named at its source.

The two-ended `git` reading (V1) is the shape
`docs/measurements/2026-09-04-following-error/harness/common.py` uses, copied in
substance at commit `601a062` for its `analyse.py` sibling and `30d916c` for its
`run_campaign.sh`; that directory is FROZEN too.

WHAT THIS MODULE MAY NOT DO. It moves no threshold, proposes no value and
decides nothing (`../criteria.md` section 0). Where it had to make a choice the
criteria does not settle, the choice is marked **UNSETTLED BY CRITERIA** in the
comment beside it, so that a reader can find every one of them with a grep.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent
CAMPAIGN_DIR = HARNESS_DIR.parent
#: The repository root, resolved from this file's own location rather than from
#: the working directory, so that the harness survives being run from anywhere
#: and survives the relocation the teardown campaign's write-up records.
REPO_ROOT = CAMPAIGN_DIR.parent.parent.parent
RAW = CAMPAIGN_DIR / "raw"

#: `../criteria.md` header. Verified at every block with
#: `git merge-base --is-ancestor`, which must succeed (V1).
BASE_COMMIT = "79b1acd"

#: `../criteria.md` section 5 -- held fixed. One zone, and it is the zone the
#: scenarios drive.
ZONE = "cell_b"

# ---------------------------------------------------------------------------
# The probe world (arms A, B, A'). `../criteria.md` sections 3 and 5.
# ---------------------------------------------------------------------------

PROBE_TEMPLATE = HARNESS_DIR / "probe.sdf.in"

#: The probe world's own name. It is NOT `cell_b`: the probe is a different
#: world in the same partition, and a name collision with a running cell would
#: put two answers on one topic. UNSETTLED BY CRITERIA -- the criteria names no
#: world, and V-container makes a concurrent cell impossible anyway, but a
#: distinct name costs nothing and removes the question.
PROBE_WORLD_NAME = "cite_probe"

#: The body I1 asks about, by name. `ModelPoses.position` returns None for an
#: absent model and None before the first snapshot (`gz.py:189-195`, the hazard
#: I1 registers), so a typo here would read as "the instrument returned
#: nothing" -- which is why the first-snapshot wait below is an EVENT on this
#: exact name and a later None is treated as absence.
PROBE_BODY = "probe_body"

#: Copied from `_workpiece_sdf` in `tests/scenarios/pick_and_place.py` at commit
#: `ee85e39`. `../criteria.md` section 5 holds the probe body's mass, inertia
#: and friction equal to the part the cell carries.
PROBE_SIDE_M = 0.05
PROBE_MASS_KG = 0.2
PROBE_INERTIA = PROBE_MASS_KG * (PROBE_SIDE_M * PROBE_SIDE_M * 2.0) / 12.0
PROBE_MU = 1.0

#: The initial pose of the probe body: x, y, z, roll, pitch, yaw. It is a
#: parameter of the harness and not a literal in the SDF because arm A' differs
#: from arm A in exactly this and in nothing else (`../criteria.md` section 3).
#:
#: UNSETTLED BY CRITERIA. The criteria requires "a height and a non-axis-aligned
#: orientation so that it falls, tumbles and settles" and fixes no numbers. This
#: is the choice, and the reasoning is recorded so it can be argued with rather
#: than guessed at:
#:
#: - 0.5 m of drop is 0.319 s of free fall at 9.8 m/s^2, reaching 3.13 m/s. The
#:   fall itself is the deterministic part; what amplifies a 1e-6 m difference
#:   is the IMPACT, and impact speed is what decides how much.
#: - The three rotations are mutually prime-ish and none is a multiple of a
#:   quarter turn, so the box meets the ground on a CORNER rather than on an
#:   edge or a face. A corner contact is the most sensitive of the three: the
#:   lever arm from the contact point to the centre of mass decides the
#:   resulting rotation, and a 1e-6 m shift of the body moves that lever arm.
#: - mu 1.0 on both surfaces means the corner PIVOTS rather than slides, which
#:   converts the impact into a tumble instead of a skid.
#:
#: Whether that is enough sensitivity is arm A's control question, not an
#: assumption: T3 measures it, and rule N fires if it is not.
PROBE_POSE: dict[str, float] = {
    "x": 0.0,
    "y": 0.0,
    "z": 0.5,
    "roll": 0.6,
    "pitch": 0.7,
    "yaw": 0.8,
}

#: `../criteria.md` T3 -- the sensitivity control's perturbation, in x.
PERTURBATION_M = 1e-6

#: How many physics iterations one probe trial runs. `max_step_size` is 0.001 s
#: and `real_time_factor` is 1, so this is 15.0 s of simulated time and about
#: 15 s of wall clock on a host that keeps up -- which a two-model world with no
#: ROS in it does comfortably.
#:
#: UNSETTLED BY CRITERIA, and it is an implementation choice that STRENGTHENS I2
#: rather than replacing it: every trial stops at the same SIMULATED time, so
#: the final reading is not taken at a wall-clock instant that drifts between
#: trials. **It does not replace the at-rest rule.** I2 is registered in
#: `../criteria.md` section 4, it is evaluated on every trial, and its verdict
#: is on every record whatever this number is.
#:
#: Why 15000. The free fall is 0.319 s; a corner impact with zero restitution
#: (SDFormat's default) and mu 1.0 settles within about a second of pivoting, so
#: the body is down well inside 3 s. I2 needs two samples at least 1.0 s apart,
#: found by a 0.2 s poll, so rest is DETECTED by about 4 s in the worst case
#: that the settle takes the whole 3 s. That leaves over 11 s of margin, which
#: is four times the settle it is covering. A trial that has not reached rest by
#: the 120 s ceiling is an instrument loss under V11 whatever this number is,
#: and shortening it could only turn a slow settle into a loss -- so the margin
#: is deliberately generous rather than tuned.
PROBE_ITERATIONS = 15000

#: Arm A's and arm A's-prime seed, and arm C's. `scripts/scenario:90` exports
#: `20260824` by default, so using it here means arm A and arm C are asking
#: about the same seed value rather than about two.
#: UNSETTLED BY CRITERIA -- section 3 says "the same seed every trial" and names
#: no value.
SEED_A = 20260824

#: Arm B's five seeds, one per trial, each different from `SEED_A` and from each
#: other (`../criteria.md` section 3: "a different seed per trial").
#: UNSETTLED BY CRITERIA -- no values are named there. They are consecutive and
#: adjacent to `SEED_A` on purpose: a seed is an opaque input to
#: `gz::math::Rand::Seed` and nothing here claims that near values behave alike,
#: but a reader can see at a glance that all six are distinct.
SEEDS_B: tuple[int, ...] = (20260825, 20260826, 20260827, 20260828, 20260829)

# ---------------------------------------------------------------------------
# Instrument I2, and the ceilings. `../criteria.md` section 4.
# ---------------------------------------------------------------------------

#: I2: two samples at least this far apart in WALL clock.
AT_REST_MIN_GAP_S = 1.0
#: I2: whose every coordinate agrees to less than this.
AT_REST_TOL_M = 1e-9
#: I2: a trial that does not reach rest inside this wall ceiling is an
#: INSTRUMENT LOSS under V11 -- never a quiet trial.
AT_REST_CEILING_S = 120.0
#: How often the position is polled while looking for rest. Not a threshold and
#: not registered: it is the resolution of the search, and it only ever delays
#: the moment rest is detected. UNSETTLED BY CRITERIA.
POLL_PERIOD_S = 0.2

#: How long the harness waits for the FIRST snapshot after the server is
#: started, before calling the trial an instrument loss (V4, V11, and section
#: 5.3: "a trial that never reached readiness is not a quiet trial"). A ceiling
#: on a hang, not a schedule -- the wait ends on the first snapshot.
FIRST_SNAPSHOT_CEILING_S = 120.0

#: How long the harness waits for `gz sim` to finish its iterations and exit.
#: A hang detector. UNSETTLED BY CRITERIA.
SERVER_EXIT_CEILING_S = 300.0

#: How long a process is given to stop after SIGINT before it is killed.
STOP_GRACE_S = 60.0

# ---------------------------------------------------------------------------
# Arm C. `../criteria.md` sections 3 and 4 (I3).
# ---------------------------------------------------------------------------

SCENARIO_NAME = "pick_and_place"

#: The line `launch_test` prints when the PRE-SHUTDOWN tests -- the cycle
#: assertions -- have finished and before the launch is shut down. I3 says "the
#: work-piece's position by I1 AFTER the scenario's cycle assertions have passed
#: and BEFORE teardown", and this is the only event in the scenario's own output
#: that separates those two.
CYCLE_DONE_MARKER = re.compile(r"Ran \d+ tests? in [0-9.]+s")

#: `scripts/scenario`'s three verdict strings, matched whole. The prefix hazard
#: CLAUDE.md section 2 records for `grep -c "Scenario 'bringup' passed"` applies
#: here too: `passed` is a prefix of `passed its cycle assertions`.
VERDICT_LINE = re.compile(r"Scenario '[a-z_]+'[^\n]*")

#: V-planner. `scripts/scenario:188-190` names both strings; `skill_server.cpp`
#: emits them at lines 2098 and 2112 (read at `6c66cb9`). A trial in which OMPL
#: answered any motion is FLAGGED and reported separately, never dropped and
#: never pooled.
PLANNER_FALLBACK = "planner fallback:"
PLANNER_FALLBACK_DECLINED = "planner fallback declined:"

#: How long arm C's reader keeps sampling before giving up, if nothing ends it.
#: The scenario's own ceilings are 300 s of bring-up plus 420 s of cycle
#: (`tests/scenarios/pick_and_place.py`), so this is those plus room for a
#: teardown. It bounds a hang and sequences nothing.
CELL_CEILING_S = 1500.0

#: How often arm C's reader samples the work-piece. UNSETTLED BY CRITERIA.
CELL_SAMPLE_PERIOD_S = 0.5

# ---------------------------------------------------------------------------
# Thresholds, restated here ONLY so that `analyse.py` has one place to read them
# from. Each names its `../criteria.md` row; none of them may differ from it.
# ---------------------------------------------------------------------------

T1_TOL_M = 1e-9  # T1: arm A's pairwise coordinate differences
T2_TOL_M = 1e-9  # T2: arm B against arm A
T3_TOL_M = 1e-6  # T3: arm A' must move the final position by MORE than this
T4_TOL_M = 1e-6  # T4: arm C's two positions
V11_LOSS_FRACTION = 0.20  # V11: above this per arm, the verdict is NOT ADMISSIBLE


# ---------------------------------------------------------------------------
# Provenance: V1, V7, I4.
# ---------------------------------------------------------------------------


def git(*args: str) -> str:
    """Run a git command in this checkout and return its stripped stdout."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:  # noqa: BLE001 - provenance, never control flow
        return f"<error {type(exc).__name__}: {exc}>"
    if result.returncode != 0 and not result.stdout:
        return f"<error rc={result.returncode}: {result.stderr.strip()}>"
    return result.stdout.strip()


def git_snapshot() -> dict:
    """V1, one end of it: HEAD, the porcelain status, and the ancestry check.

    Taken at BOTH ends of every block and written into the record as fields; the
    analyser drops any row without them. `base_commit_is_ancestor` is
    `git merge-base --is-ancestor 79b1acd HEAD`, which `../criteria.md` requires
    to succeed.
    """
    ancestor = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"],
        capture_output=True, text=True, timeout=120,
    )
    return {
        "head": git("rev-parse", "HEAD"),
        "porcelain": git("status", "--porcelain"),
        "base_commit": BASE_COMMIT,
        "base_commit_is_ancestor": ancestor.returncode == 0,
    }


def load_average() -> list[float]:
    """V7: load is FLAGGED, never excluded.

    Copied from `2026-08-31-capacity-and-clock-deficit/harness/trial.py` at
    `fca1391`. A load threshold chosen after seeing the data is a threshold
    chosen by the data, so this value enters no rule -- it is reported.
    """
    try:
        return list(os.getloadavg())
    except OSError:
        return []


def command_output(argv: list[str], timeout: float = 120.0) -> str:
    """Run a command for its output, for the record. Never control flow."""
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - provenance
        return f"<error {type(exc).__name__}: {exc}>"
    return (result.stdout + result.stderr).strip()


def host_facts() -> dict:
    """I4's per-block fields that are not git and not load."""
    help_text = command_output(["gz", "sim", "--help"])
    return {
        "uname_m": command_output(["uname", "-m"]),
        "uname_a": command_output(["uname", "-a"]),
        "gz_sim_version": command_output(["gz", "sim", "--version"]),
        # I4: "`gz sim --help` lists `--seed`". Recorded as the answer to that
        # question rather than as the whole help text.
        "gz_help_lists_seed": "--seed" in help_text,
        "gz_help_lists_iterations": "--iterations" in help_text,
        "python": sys.version,
    }


def docker_ps() -> str:
    """V-container: what `docker ps` says. Recorded; the refusal is in the shell.

    Inside the container there is no docker socket, so this returns an error
    string there and `run_campaign.sh` -- which runs on the host -- is where the
    check that REFUSES lives. Recorded at both places rather than at one,
    because a field that is only ever absent is a field nobody checks.
    """
    return command_output(["docker", "ps", "--format", "{{.Names}} {{.Image}}"], timeout=60)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# V-physics, and building the probe world.
# ---------------------------------------------------------------------------

_PHYSICS_BLOCK = re.compile(r"<physics\b.*?</physics>", re.DOTALL)
_XML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def physics_block(world_text: str) -> str | None:
    """The raw `<physics>...</physics>` substring of an SDF document, or None.

    COMMENTS ARE STRIPPED FIRST, and that is not tidiness. Both documents this
    is run over carry long header comments, and `probe.sdf.in`'s says the word
    `<physics>` while explaining that the block below it is a verbatim copy. A
    regex over the raw text matched THAT, so V-physics compared a paragraph of
    prose against the cell's real block, failed to parse it, and would have
    refused every trial for a reason that had nothing to do with the physics.
    Found before the first trial, by running the comparison on a document that
    was known to agree.
    """
    stripped = _XML_COMMENT.sub("", world_text)
    match = _PHYSICS_BLOCK.search(stripped)
    return match.group(0) if match else None


def canonical_physics(block: str | None) -> dict | None:
    """A whitespace-independent, order-independent form of a `<physics>` block.

    UNSETTLED BY CRITERIA. V-physics says the harness "compares its probe
    world's `<physics>` block against the installed generated world's ... and
    refuses to run if they differ", and does not say what *differ* means. Two
    readings were available: byte equality of the raw substring, and equality of
    what the block SAYS. Byte equality would fire on indentation, which is not a
    physics difference and would make the rule fire for a reason that is not the
    one it exists for; this takes the second reading. **Both raw strings go onto
    every record**, so a reader who wants the byte comparison has the bytes.
    """
    if block is None:
        return None
    try:
        element = ElementTree.fromstring(block)
    except ElementTree.ParseError as exc:
        return {"parse_error": f"{type(exc).__name__}: {exc}"}
    children = {}
    for child in element:
        children[child.tag] = (child.text or "").strip()
    return {
        "tag": element.tag,
        "attrib": dict(sorted(element.attrib.items())),
        "children": dict(sorted(children.items())),
    }


def installed_world_path(zone: str = ZONE) -> Path:
    """Where the INSTALLED generated world for ``zone`` is.

    Off `ros2 pkg prefix cite_generated`, the way
    `2026-08-31-capacity-and-clock-deficit/harness/trial.py:64-80` does it at
    `fca1391`, and NOT off `workspace/src/`. The question V-physics asks is what
    the running cell would load, and this repository has twice published figures
    produced by a build that was not the build being described.
    """
    prefix = subprocess.run(
        ["ros2", "pkg", "prefix", "cite_generated"],
        capture_output=True, text=True, timeout=120,
    ).stdout.strip()
    if not prefix:
        raise RuntimeError(
            "`ros2 pkg prefix cite_generated` printed nothing. V-physics reads the "
            "INSTALLED world, so an unbuilt or unsourced workspace is a refusal and "
            "not a fallback to workspace/src/."
        )
    return Path(prefix) / "share" / "cite_generated" / "worlds" / f"{zone}.sdf"


def physics_agreement(probe_world_text: str, zone: str = ZONE) -> dict:
    """V-physics, evaluated. The caller REFUSES TO RUN when `agree` is false.

    Returns the two raw blocks, the two canonical forms and the verdict, so the
    record carries the evidence and not only the answer.
    """
    record: dict = {"zone": zone}
    try:
        installed = installed_world_path(zone)
        record["installed_world"] = str(installed)
        installed_text = installed.read_text()
    except Exception as exc:  # noqa: BLE001 - reported, then refused on
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["agree"] = False
        return record
    installed_block = physics_block(installed_text)
    probe_block = physics_block(probe_world_text)
    record["installed_physics_raw"] = installed_block
    record["probe_physics_raw"] = probe_block
    record["installed_physics"] = canonical_physics(installed_block)
    record["probe_physics"] = canonical_physics(probe_block)
    record["installed_world_sha256"] = sha256_text(installed_text)
    record["agree"] = (
        record["installed_physics"] is not None
        and record["installed_physics"] == record["probe_physics"]
    )
    return record


def build_probe_world(x_offset: float) -> str:
    """The probe world as text, with ``x_offset`` added to the body's x.

    The offset is the ONE thing arm A' varies (`../criteria.md` section 3). It is
    formatted with `repr`, which round-trips a double, so the world file states
    exactly the number this process computed.
    """
    pose = dict(PROBE_POSE)
    pose["x"] = pose["x"] + x_offset
    text = PROBE_TEMPLATE.read_text()
    substitutions = {
        "@WORLD_NAME@": PROBE_WORLD_NAME,
        "@BODY_NAME@": PROBE_BODY,
        "@X@": repr(pose["x"]),
        "@Y@": repr(pose["y"]),
        "@Z@": repr(pose["z"]),
        "@ROLL@": repr(pose["roll"]),
        "@PITCH@": repr(pose["pitch"]),
        "@YAW@": repr(pose["yaw"]),
        "@MASS@": repr(PROBE_MASS_KG),
        "@INERTIA@": repr(PROBE_INERTIA),
        "@SIDE@": repr(PROBE_SIDE_M),
    }
    for token, value in substitutions.items():
        text = text.replace(token, value)
    leftover = re.findall(r"@[A-Z_]+@", text)
    if leftover:
        raise RuntimeError(f"probe.sdf.in has unsubstituted tokens: {sorted(set(leftover))}")
    return text


# ---------------------------------------------------------------------------
# Records.
# ---------------------------------------------------------------------------


def import_gz():
    """Import `cite_bringup.gz`, the ONE door to Gazebo transport (V10).

    ADR-0042 and CLAUDE.md section 10: every process that speaks the Gazebo
    transport carries the `GZ_PARTITION` the generated plan names, and one that
    does not discovers a world that is not there WITHOUT FAILING. This harness
    builds that environment nowhere; it asks this module.
    """
    try:
        from cite_bringup import gz
    except ImportError:
        sys.path.insert(0, str(REPO_ROOT / "workspace" / "src" / "cite_bringup"))
        from cite_bringup import gz  # noqa: F811
    return gz


def write_record(path: Path, record: dict) -> None:
    """One invocation, one trial, one JSON record (`../criteria.md` section 6).

    Written to a temporary name and renamed, so that a record which exists is a
    record that is complete -- which is what makes `run_campaign.sh`'s skip
    (V8, resumability) safe to trust.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(record, indent=1, sort_keys=False))
    temporary.replace(path)


def label_for(arm: str, index: int) -> str:
    """The record name. A re-run skips a trial whose record exists (V8)."""
    return f"{arm}_{index:02d}"
