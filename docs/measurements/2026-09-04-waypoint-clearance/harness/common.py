#!/usr/bin/env python3
"""What the recorder, the compute stage and the analyser share: registered constants,
provenance, and the record.

DERIVED IN SHAPE FROM ONE FROZEN DIRECTORY, named because the shape is not this campaign's
invention:

  * `docs/measurements/2026-09-04-following-error/harness/common.py`, copied at commit
    `0712272`, the commit that file last landed at -- the two-ended `snapshot` / `v1` pair,
    `manifest_vendor_sha`, `vendor_pin`, `model_hash`, `host_load`, `host_facts`, `v7`,
    `running_geometry`, `wilson`, the `TrialWriter` / `seal` / `complete` shape, and the
    "provenance travels on every record" rule.

That directory is FROZEN (`docs/measurements/README.md` rule 2) and nothing in it is edited
from here. **No campaign imports from another**: this is a copy, and this header says so.

WHY ONE MODULE RATHER THAN A COPY PER STAGE. Inside one campaign a value in two places is
still a value in two places (P1). V1 discards a block, and a discard rule implemented twice
is two rules.

WHAT THIS MODULE MAY NOT DO. It sets no threshold of its own. Every number below is quoted
from `criteria.md` with the section that registers it, or is read from the tree at run time.
Nothing here is derived from data, because there is no data when this file is written.

THE TWO-ENDED READING, AND WHY THE ROWS ARE SEALED RATHER THAN STAMPED. `criteria.md` V1
requires `v1_clean` to be the CONJUNCTION of two `git` readings taken at both ends of the
block, and requires the flag to travel ON the record. A block runs three scenarios over many
minutes and its rows are written as trajectories arrive, so the closing reading does not
exist yet when a row is written. `RecordWriter.seal` reconciles those two facts: every row
carries `v1_clean = None` until the closing reading is taken -- at the end of the block, or
as the FIRST act of the abort path -- and is then rewritten with the conjunction. A harness
that died without sealing leaves rows carrying `None`, which `analyse.py` drops and reports
as a lost block, exactly as V1 registers.

THIS MODULE IMPORTS NO ROS AND NO `yaml` AT MODULE LEVEL. `analyse.py` and `compute.py` run
on a host that has neither ROS nor a sourced workspace (REPRO1 requires a second interpreter),
and the recorder runs inside the container. The one YAML reader below imports `yaml` lazily
and falls back to a hand parser for the two generated files this campaign reads, so the
compute stage cannot be blocked by a missing host dependency.
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
    the campaign directory is four levels down and the stages are invoked from the
    repository root on the host and from `/workspace` in the container.
    """
    return HERE.parents[3]


# ---------------------------------------------------------------------------
# The cell, and the tree the campaign is a property of
# ---------------------------------------------------------------------------

#: `criteria.md` section 5.3. One zone, three arms, headless.
ZONE = "cell_a"
ARMS = ("arm_1", "arm_2", "arm_3")

#: `criteria.md` section 3. The three captures, in the fixed order section 6 registers, each
#: with the `./scripts/scenario` name that produces it. **Rule T**: the captures are not each
#: other's evidence and every verdict is stated per capture.
CAPTURES: tuple[tuple[str, str], ...] = (
    ("BRINGUP", "bringup"),
    ("PICKPLACE", "pick_and_place"),
    ("LINE", "continuous_line"),
)
CAPTURE_NAMES = tuple(name for name, _ in CAPTURES)

#: `criteria.md` preamble. Every figure is a property of the tree at this commit.
BASE_COMMIT = "c38a42c"

#: `criteria.md` V1. The seven watched paths, conjoined at both ends of every block.
#: `docs/measurements/` is deliberately absent: this campaign's own criteria, harness and raw
#: all land on this branch, so `HEAD` necessarily advances while it runs.
V1_WATCHED_PATHS = (
    "model/",
    "workspace/src/",
    "tools/",
    "tests/",
    "scripts/",
    "assets/",
    "external/",
)

#: `criteria.md` preamble and V1's second clause. The vendor half is one of the two
#: geometries this campaign measures, so a moved pin does not merely change the cell -- it
#: changes the comparison.
VENDOR_CHECKOUT = "workspace/src/external/xarm_ros2"
VENDOR_MANIFEST = "external/cite.repos"
VENDOR_MANIFEST_KEY = "external/xarm_ros2"

#: `criteria.md` V2. 13 collision-mesh references under the hull root, which is
#: `find assets/meshes/collision/xarm5/convex_hull -name '*.stl' | wc -l`. The meshes sit in
#: three nested directories, so counting that directory's own entries reads 3 and is a
#: different quantity.
HULL_COLLISION_REFERENCE = "cite_description/meshes/collision/xarm5/convex_hull"
HULL_COLLISION_REFERENCES_EXPECTED = 13

#: `criteria.md` section 2.3. The two roots the compute stage substitutes between. The
#: relative path below the root is identical in both sets, which is the property that makes
#: an offline substitution exact -- and it is CHECKED rather than assumed (`mesh_sets`).
HULL_ROOT = "assets/meshes/collision/xarm5/convex_hull"
VENDOR_ROOT = "workspace/src/external/xarm_ros2/xarm_description/meshes"
GEOMETRIES = ("hull", "vendor")

#: `criteria.md` V3. The backend that actually ran.
PRODUCTION_PLUGIN = "gz_ros2_control/GazeboSimSystem"
FIXTURE_PLUGIN = "cite_test_hardware/JointStopSystem"
MOCK_PLUGIN = "mock_components/GenericSystem"

# ---------------------------------------------------------------------------
# The capture door
# ---------------------------------------------------------------------------

#: `criteria.md` section 2.1. `DisplayMotionPath`'s `display_path_topic` default, resolved
#: into each arm's own namespace. The harness RESOLVES the name from the running graph and
#: records what it found; this is the expectation a mismatch is reported against.
DISPLAY_TOPIC = "display_planned_path"


def arm_namespace(arm: str) -> str:
    """`/cite/<zone>/<asset_id>` -- CLAUDE.md section 8, and `simulation.launch.py`."""
    return f"/cite/{ZONE}/{arm}"


def display_topic(arm: str) -> str:
    return f"{arm_namespace(arm)}/{DISPLAY_TOPIC}"


# ---------------------------------------------------------------------------
# `criteria.md` section 7.0 -- every registered size, with the row that registers it
# ---------------------------------------------------------------------------

#: The close-approach band: the smallest dimension of any object in the generated planning
#: scene (section 2.2). Also `STEP_HIGH`, the step that could traverse the thinnest object.
CLOSE_BAND_M = 0.040
STEP_HIGH_M = 0.040

#: Half `STEP_HIGH`. The factor of two is a judgement and section 7.0 records it as one.
STEP_MID_M = 0.020

#: The numerical floor on a hull-versus-vendor difference. The hull's vertex set is a subset
#: of its source's, bit-identical, so a difference below this is double-precision arithmetic
#: and not geometry.
DIFF_FLOOR_M = 1e-9

#: TUNNEL1's interpolation target and its ceiling. One twentieth of the thinnest object's
#: thickness -- the twentieth is a judgement -- and a bound on the compute, not on the
#: physics. Every interval that hits the ceiling is counted and its achieved sub-step stated.
SUB_STEP_M = 0.002
SUB_CEILING = 200

#: The broad-phase cutoff. 12.5x `CLOSE_BAND`, and the bound it is applied to is identical
#: under both geometries (section 2.3), so censoring is symmetric. Rule M.
CENSOR_M = 0.500

#: FK1's agreement tolerance -- four orders of magnitude below `CLOSE_BAND`. A judgement.
FK_TOLERANCE_M = 1e-6
FK_TOLERANCE_RAD = 1e-6

#: REPRO1's cross-interpreter tolerance. A judgement, six orders below `DIFF_FLOOR`'s scale.
REPRO_TOLERANCE_M = 1e-12

#: Rule C's trajectory floor: fewer than two waypoints is no interval at all.
MIN_WAYPOINTS = 2

#: Rule C's instrument-loss ceiling, stated over I5's PUBLISHED count.
LOSS_CEILING_SHARE = 0.20

#: V7's load flag, on 16 cores. It FLAGS and never excludes.
V7_LOAD_THRESHOLD = 4.0

#: V5's scene-agreement tolerance. Section 7.0 registers that it is expected to fire under
#: one accounting choice and NOT under the one this harness makes (see `static_transforms`).
V5_TOLERANCE_M = 1e-9

#: FK1's sample size. A judgement; FK1 is a CONJUNCTION over the sample, so one disagreement
#: is the result and the size bounds only how much of the set the check reaches.
FK1_SAMPLE = 200

#: FK1's sample seed, registered here so that the draw is reproducible from the record.
FK1_SEED = 20260904

#: Rule C-i's door ceiling. A constant this tree already ships: `BRING_UP_CEILING_S = 240.0`
#: (`tests/scenarios/bringup.py:94`). A bound on waiting and never a schedule -- the door
#: opening is an event (V4, V13, P4) and nothing sleeps on it.
DOOR_CEILING_S = 240.0

#: Rule R's minimum interesting size, per metric (section 7.0). TUNNEL1 is a binary
#: observation and has no spread, so rule R does not apply to it.
RULE_R_SIZES = {
    "DELTA1": DIFF_FLOOR_M,
    "MARGIN1": SUB_STEP_M,
    "STEP1": SUB_STEP_M,
    "TUNNEL1": None,
}

#: `criteria.md` section 2.0 and section 4.1 reading (a). RECORDED per trajectory and never
#: enforced: this campaign does not re-run the tree's own assertion as its evidence.
SAMPLING_TIME_S = 0.1

#: `criteria.md` section 5.4 and GRIP1. The drive joint's declared range, and the five
#: `<mimic>` followers that move with it at multiplier 1 and offset 0.
GRIPPER_RANGE_RAD = (0.0, 0.85)

#: `criteria.md` section 2.2.1. The standing pair: every arm is bolted to a body that is also
#: a planning-scene object, and the two overlap by about 132 nm at EVERY configuration under
#: BOTH geometries. Excluded from every aggregate BY NAME and by nothing else -- no distance
#: threshold drops it, and no tolerance anywhere is widened to make it disappear.
STANDING_PAIRS = {f"{arm}_link_base": f"pedestal_{arm.split('_')[1]}" for arm in ARMS}


def is_standing_pair(link: str, obj: str) -> bool:
    """`criteria.md` section 2.2.1, decision 3: BY NAME and by nothing else."""
    return STANDING_PAIRS.get(link) == obj


#: `criteria.md` section 2.1 reading (c) -- THE attribution. The two descriptions are
#: distinct string literals in MoveIt 2.12.4 and nothing else produces these lines.
PLANNER_LINE = re.compile(r"Calling Planner '([^']+)'")
PIPELINE_OF = {"Pilz Industrial Motion Planner": "pilz", "OMPL": "ompl"}

#: I5 -- how many trajectories the pipeline PUBLISHED. `DisplayMotionPath::getDescription()`
#: returns the same literal in both pipelines, so this counts publications across both
#: together and never says which produced one (section 2.1).
DISPLAY_ADAPTER_LINE = re.compile(
    r"Calling PlanningResponseAdapter 'DisplayMotionPath'"
)

#: I6 -- how many `ValidateSolution` refused, with the code. REFUSE1.
VALIDATE_REFUSAL_LINE = re.compile(
    r"PlanningResponseAdapter 'ValidateSolution' failed with error code\s*(\S+)"
)

#: I2 reading (b) -- a CORROBORATION, scraped with its timestamp.
FALLBACK_LINE = re.compile(r"planner fallback: (\S+) found no path, retrying with (\S+)")

#: I9 -- the scenario's own verdict line. `scripts/scenario` prints one of three strings and
#: THE STEP CONCLUSION IS NEVER USED.
SCENARIO_VERDICT_LINE = re.compile(r"Scenario '([^']+)' (.*)")

#: A launch log carries every process's output. Attribution of a log line to an arm is by the
#: launch process prefix; where it cannot be resolved, rule C-ii's equality is stated over the
#: BLOCK TOTAL and `ANALYSIS.md` says so.
ARM_PREFIX = re.compile(r"\[cite\.[^.\]]*\.(arm_\d+)[.\]]")


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
    ROS-less host cannot satisfy.
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

    Both halves are POSITIVE readings: `matches` is false when either is missing, so "no
    disagreement found" is never reachable by not looking.
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

    Two readings rather than one: the source tree's says which model the repository
    describes, the installed one says which model the rig that is about to run was built
    from. A block taken against a stale install is a block about a cell nobody committed.
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
        # one that did. It is taken HERE so that it travels at BOTH ENDS of every block. It
        # gates nothing: `analyse.py` prints it as a rule and V9 is what a finding belongs to.
        "criteria_sha256": sha256(HERE.parent / "criteria.md"),
    }


def v1(start: dict, end: dict) -> dict:
    """V1 -- the CONJUNCTION, evaluated where the block was taken.

    A block is one container session running three scenarios and lasts many minutes. A single
    snapshot at its start would leave the flag true while an edit landed inside it, and V10's
    promise that a concurrent writer flips the flag would be prose ahead of the mechanism.
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
    is not namespaced on native Linux and there is no `lxcfs` in the way. The key nevertheless
    names where the reading was taken, because the 2026-08-31 capacity campaign applied a
    validity rule that read a virtual machine's load rather than the host's.
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

    `GZ_PARTITION` is recorded and is NOT a binding on this harness: V12 registers that the
    harness constructs no Gazebo environment of its own and makes no `gz` call at all. The
    scenarios start their own Gazebo processes through the shipped launch, which carries the
    partition (ADR-0042). Recording it is how a reader checks that claim rather than trusting
    it.
    """
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "gz_partition": os.environ.get("GZ_PARTITION"),
        "rmw_implementation": os.environ.get("RMW_IMPLEMENTATION"),
        "cite_environment": {
            key: value for key, value in sorted(os.environ.items())
            if key.startswith("CITE_")
        },
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
    """V2, V3 and I3, off the description the RUNNING node publishes.

    Off the running node and not off the file on disk, which is the difference between "the
    repository ships hulls" and "the cell that produced these numbers was built from them".
    `v2_ok` and `v3_ok` are conjunctions of POSITIVE findings, never of two absences: an
    empty answer counts zero hull references as readily as a vendor-mesh description does,
    and "no mock plugin found" must not be reachable by not looking.

    THE 2026-09-03 CAMPAIGN LOST EIGHTEEN TRIALS HERE. One trial of eighteen read the
    description back as zero characters and the block-level discard took the rest with it, so
    `description_chars` is published on every block record and `read_ok` is separate from
    `v2_ok`: a rig that could not read is a different finding from a cell built wrongly.

    THE TEXT ITSELF IS RETURNED, and that is this campaign's own addition rather than the
    frozen ancestor's. The compute stage's forward kinematics (I11) is computed from THIS
    description -- the one that actually ran -- and not from a fresh `xacro` expansion, so
    the URDF has to travel on the record like every other validity reading (V1's "computed
    where the block is taken, travels ON the record").
    """
    result = subprocess.run(
        ["ros2", "param", "get", f"{namespace}/description_publisher", "robot_description"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    running = result.stdout
    # `ros2 param get` prints `String value is: <xml>`; the XML itself starts at the first
    # `<?xml` or `<robot`. Sliced rather than split, because the description contains newlines.
    start = min(
        (index for index in (running.find("<?xml"), running.find("<robot")) if index >= 0),
        default=-1,
    )
    urdf = running[start:] if start >= 0 else ""
    hulls = urdf.count(HULL_COLLISION_REFERENCE)
    production = urdf.count(PRODUCTION_PLUGIN)
    return {
        "read_from": f"{namespace}/description_publisher robot_description",
        "read_returncode": result.returncode,
        "read_ok": len(urdf) > 0,
        "description_chars": len(urdf),
        "description_sha256": hashlib.sha256(urdf.encode()).hexdigest() if urdf else None,
        "hull_collision_refs": hulls,
        "vendor_visual_refs": urdf.count("xarm_description/meshes/xarm5/visual"),
        "v2_ok": len(urdf) > 0 and hulls == HULL_COLLISION_REFERENCES_EXPECTED,
        "production_plugin_refs": production,
        "fixture_plugin_refs": urdf.count(FIXTURE_PLUGIN),
        "mock_plugin_refs": urdf.count(MOCK_PLUGIN),
        "v3_ok": (
            len(urdf) > 0
            and production > 0
            and urdf.count(FIXTURE_PLUGIN) == 0
            and urdf.count(MOCK_PLUGIN) == 0
        ),
        "urdf": urdf,
    }


# ---------------------------------------------------------------------------
# The generated configuration this campaign was registered against
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> dict:
    """Read a generated YAML file.

    `yaml` is imported lazily. The compute stage and the analyser run on a host interpreter
    that need not carry it, and every generated file this campaign reads is also reachable
    off the block record, so a missing `yaml` is a loud failure at the one call site that
    needs it rather than an import error in every stage.
    """
    import yaml  # noqa: PLC0415 - deliberately lazy; see the docstring

    return yaml.safe_load(path.read_text()) or {}


def generated_dir(root: Path | None = None) -> Path:
    """The generated tree in the SOURCE checkout.

    Deliberately the source tree and not the installed share directory: the compute stage
    runs on the host with nothing sourced, and V1 watches `workspace/src/`, so the file this
    reads is the file the two-ended reading proves did not move.
    """
    return (root or repo_root()) / "workspace" / "src" / "cite_generated"


def planning_scene_file(root: Path | None = None) -> dict:
    """`criteria.md` section 2.2 -- the scene as the GENERATOR writes it.

    V5's cross-check and nothing else. **The distances are computed against I4's read-back**,
    not against this file, so that no frame convention of this file has to be trusted.
    """
    document = _load_yaml(generated_dir(root) / "moveit" / f"{ZONE}_planning_scene.yaml")
    scene = document["planning_scene"]
    return {
        "frame_id": scene["frame_id"],
        "objects": {
            body["id"]: {
                "type": body["type"],
                "frame_id": body["frame_id"],
                "primitive": body["primitive"]["type"],
                "dimensions_m": list(body["primitive"]["dimensions_m"]),
                "xyz_m": list(body["pose"]["xyz_m"]),
                "rpy_rad": list(body["pose"]["rpy_rad"]),
            }
            for body in scene["collision_objects"]
        },
    }


def static_transforms(root: Path | None = None) -> dict:
    """The generated static transform table, as `parent/child -> (xyz, rpy)`.

    **V5's registered accounting choice lives here.** Section 7.0's V5 row and V5 itself
    record that the generated `cite_world -> arm_N_mount` yaw is `1.570796327`, which is
    `pi/2` truncated by 2.051035e-10 rad, and that applying `pi/2` instead would displace
    three of the 36 (arm, object) pairs by more than V5's 1e-9 m. This harness uses **the
    generated value**, which is the value `move_group` itself was given, so the round trip
    cancels to double precision. Nothing here rounds it, and nothing substitutes `pi/2`.
    """
    document = _load_yaml(generated_dir(root) / "frames" / f"{ZONE}_static_tf.yaml")
    rows = document["static_transforms"] if isinstance(document, dict) else document
    return {
        f"{row['parent']}|{row['child']}": {
            "parent": row["parent"],
            "child": row["child"],
            "xyz_m": [float(value) for value in row["xyz_m"]],
            "rpy_rad": [float(value) for value in row["rpy_rad"]],
        }
        for row in rows
    }


def plan_arm(arm: str, root: Path | None = None) -> dict:
    """The arm's entry in the generated bring-up plan -- group, base link and TIP LINK.

    STEP1's quantity is the position of `arm_N_link_tcp`, which is the `tip_link` the
    generated plan hands the skill server (`cell_a_plan.yaml`, `skill_server.cpp:559`). It is
    READ here rather than written down, because a value in two places is the defect P1 names.
    """
    plan = _load_yaml(generated_dir(root) / "bringup" / f"{ZONE}_plan.yaml")
    for manager in plan["plan"]["controller_managers"]:
        if manager["asset"] == arm:
            moveit = manager["moveit"]
            return {
                "asset": arm,
                "namespace": manager.get("namespace", arm_namespace(arm)),
                "description": manager["description"],
                "group": moveit["group"],
                "base_link": moveit["base_link"],
                "tip_link": moveit["tip_link"],
                "home_rad": [float(value) for value in moveit["home_rad"]],
                "srdf": moveit["srdf"],
                "kinematics": moveit["kinematics"],
                "planning_pipelines": moveit["planning_pipelines"],
                "joint_limits": moveit["joint_limits"],
                "cartesian_limits": moveit["cartesian_limits"],
                "controllers": moveit["controllers"],
            }
    raise AssertionError(f"the generated plan has no entry for {arm}")


# ---------------------------------------------------------------------------
# Log scraping -- I2(c), I5, I6, I9
# ---------------------------------------------------------------------------
def scrape_capture_log(text: str) -> dict:
    """I5, I6, I2(b), I2(c) and I9 from one capture's captured output.

    Every count is a POSITIVE reading of a line the pipeline emits, so an empty log reads as
    zero published and zero refused -- which rule C-ii turns into a shortfall, and never into
    a quiet cell.
    """
    published = DISPLAY_ADAPTER_LINE.findall(text)
    refusals = VALIDATE_REFUSAL_LINE.findall(text)
    planners: list[dict] = []
    for line in text.splitlines():
        match = PLANNER_LINE.search(line)
        if match:
            arm = ARM_PREFIX.search(line)
            planners.append(
                {
                    "description": match.group(1),
                    "pipeline": PIPELINE_OF.get(match.group(1)),
                    "arm": arm.group(1) if arm else None,
                    "line": line[:400],
                }
            )
    fallbacks = [
        {"from": a, "to": b} for a, b in (FALLBACK_LINE.search(line).groups()
                                          for line in text.splitlines()
                                          if FALLBACK_LINE.search(line))
    ]
    verdicts = [
        {"scenario": scenario, "rest": rest[:200]}
        for scenario, rest in SCENARIO_VERDICT_LINE.findall(text)
    ]
    return {
        # I5 -- the count of publications, ACROSS BOTH PIPELINES together. Section 2.1:
        # `DisplayMotionPath::getDescription()` returns the same literal in both, so this
        # never says which pipeline produced one.
        "i5_published": len(published),
        # I6 -- REFUSE1, by code.
        "i6_refusals": len(refusals),
        "i6_codes": sorted(set(refusals)),
        # I2(c) -- THE attribution, in log order, with the arm where the prefix resolves it.
        "i2c_planner_calls": planners,
        "i2c_by_pipeline": {
            "pilz": sum(1 for row in planners if row["pipeline"] == "pilz"),
            "ompl": sum(1 for row in planners if row["pipeline"] == "ompl"),
            "unattributed": sum(1 for row in planners if row["pipeline"] is None),
        },
        # I2(b) -- a CORROBORATION.
        "i2b_fallbacks": fallbacks,
        # I9 -- the scenario's own verdict LINE. The step conclusion is never used.
        "i9_verdict_lines": verdicts,
        "log_chars": len(text),
    }


# ---------------------------------------------------------------------------
# Small statistics
# ---------------------------------------------------------------------------
def _percentile(sorted_values: list[float], percent: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * (percent / 100.0)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def percentile(values, percent: float) -> float | None:
    return _percentile(sorted(float(value) for value in values), percent)


def distribution(values) -> dict:
    """min / median / p95 / p99 / max plus n -- the shape section 7.2 and 7.3 ask for."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"n": 0, "min": None, "median": None, "p95": None, "p99": None, "max": None}
    return {
        "n": len(ordered),
        "min": ordered[0],
        "median": _percentile(ordered, 50.0),
        "p95": _percentile(ordered, 95.0),
        "p99": _percentile(ordered, 99.0),
        "max": ordered[-1],
    }


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """V8's Wilson 95 % interval, for the counts that are proportions."""
    if trials <= 0:
        return None
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    spread = (
        z
        * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0.0, centre - spread), min(1.0, centre + spread)


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------
class RecordWriter:
    """One JSON array of captured trajectories per block, rewritten and SEALED at the end.

    Rewritten rather than appended, so that a block killed part-way leaves a file that
    parses. V8 -- every count is reported over what was actually captured -- depends on the
    partial file being readable, and a truncated last object would lose the whole block.

    `seal` is V1's closing reading, and it is the reason a row is not final when it is
    written: `v1_clean` is the conjunction of two `git` readings taken at both ends of the
    block, and the closing one does not exist while the block is running. Every row carries
    `v1_clean = None` until `seal` rewrites it. A harness that DIED without sealing leaves
    `None` on every row, `analyse.py` drops them, and V1 reports the block as lost with the
    trajectory count it would have contributed -- which is exactly what V1 registers.
    """

    def __init__(self, out: Path, label: str, header: dict) -> None:
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "logs").mkdir(exist_ok=True)
        self.label = label
        self.header = header
        self.rows: list[dict] = []
        self.captures: list[dict] = []
        self.path = self.out / f"{label}_trajectories.json"
        self.sealed = False
        (self.out / f"{label}_header.json").write_text(
            json.dumps(header, indent=2, default=str)
        )

    def add(self, row: dict) -> dict:
        # The header's block-level facts travel ON EVERY RECORD and not only in the header. A
        # record lifted out of this file into a table is a record that has left its header
        # behind, and V1, V2, V3, V4, V7, V12 and V14 are block rules whose evidence must not
        # be separable from the numbers they validate. `criteria.md` V1 says it in as many
        # words: not a note in a README, a field.
        #
        # V2, V3, V4 and V5 are read PER CAPTURE and not once per block, and that is forced
        # by the design rather than chosen: `criteria.md` rule C-i records that each scenario
        # starts its OWN `move_group` inside its own process and every run owns its own cell,
        # so there is no single description, no single scene and no single matched publisher a
        # block could read once. The caller passes the reading taken from the cell that
        # produced THIS trajectory; the header's value is a fallback and never an override.
        carried = {
            key: row.get(key, self.header.get(key))
            for key in ("v2", "v3", "v4", "v5", "v12_gz_calls", "v13", "v14")
        }
        row = {
            **row,
            **carried,
            "label": self.label,
            "block": self.label,
            "base_commit": BASE_COMMIT,
            "v7_start": self.header.get("v7_start"),
            "model_hash": self.header.get("model_hash"),
            # Filled by `seal`. Present from the start so that a reader of a partial file
            # sees the field and its `None`, rather than inferring an absence from a missing
            # key.
            "v1_clean": None,
            "v1": None,
            "v7_end": None,
            "v7_any": None,
            # `criteria.md` section 10: THE SHAKEDOWN IS NOT DATA. It travels on the record so
            # that the exclusion is a FIELD the analyser drops on, and not a property of which
            # directory the operator happened to redirect the run into.
            "is_shakedown": bool(self.header.get("is_shakedown")),
        }
        self.rows.append(row)
        self.flush()
        return row

    def add_capture(self, record: dict) -> dict:
        """One capture's own record: its log scrape, its verdict, its exit status, its window.

        Kept in a file of its own rather than in the trajectory stream, because a capture is
        not a trajectory and rule C-ii's shortfall is stated per capture over I5's published
        count -- a quantity no trajectory row can carry.
        """
        self.captures.append(
            {
                **record,
                "label": self.label,
                "block": self.label,
                "is_shakedown": bool(self.header.get("is_shakedown")),
                "v1_clean": None,
            }
        )
        (self.out / f"{self.label}_captures.json").write_text(
            json.dumps(self.captures, indent=2, default=str)
        )
        return record

    def seal(self, end_snapshot: dict, end_load: dict, why: str) -> dict:
        """V1's closing reading, applied to every row this block wrote.

        Called at the end of a complete block AND as the first act of the abort path, which is
        what stops V1 and V8 contradicting each other: V8 promises that a block ending early
        is reported with the n it reached, and without a closing reading taken at the abort
        those rows would carry no flag and be dropped.
        """
        flags = v1(self.header["v1_start"], end_snapshot)
        v7_start = bool(self.header.get("v7_start"))
        v7_end = v7(end_load)
        for row in self.rows:
            row["v1"] = flags
            row["v1_clean"] = flags["v1_clean"]
            row["v7_end"] = v7_end
            row["v7_any"] = v7_start or v7_end
        for capture in self.captures:
            capture["v1_clean"] = flags["v1_clean"]
            capture["v7_any"] = v7_start or v7_end
        self.sealed = True
        self.flush()
        (self.out / f"{self.label}_captures.json").write_text(
            json.dumps(self.captures, indent=2, default=str)
        )
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
                    "captures": len(self.captures),
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

        A block that ABORTS part-way leaves `<label>_trajectories.json` behind exactly as a
        finished one does, and `run_campaign.sh` skips a block whose trajectory file exists so
        that a resumed campaign never tops a capture up (V8). Without a marker those two
        states are indistinguishable, so an aborted block would be silently treated as DONE.
        """
        (self.out / f"{self.label}_complete.json").write_text(
            json.dumps(
                {
                    "label": self.label,
                    "captures_scheduled": scheduled,
                    "captures_run": len(self.captures),
                    "trajectories_written": len(self.rows),
                    "sealed": self.sealed,
                    "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    **(extra or {}),
                },
                indent=2,
                default=str,
            )
        )
