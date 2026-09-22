#!/usr/bin/env python3
"""`../criteria.md` sections 7 and 10, applied to `raw/`.

DERIVED IN SHAPE FROM `docs/measurements/2026-09-04-following-error/harness/analyse.py`,
copied at commit `601a062`, which took the shape from
`docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py` at `8a35a03`:
**one function per registered rule, the rule prints even when it does not fire,
and a `DEVIATIONS` tuple at module top printed on every run.** Both directories
are FROZEN (`docs/measurements/README.md` rule 2) and nothing in either is
edited from here. Every rule below is this campaign's own.

WRITTEN BEFORE THE FIRST TRIAL, which is the whole point. A rule implemented
after the data has been seen is a rule chosen by the data, and V9 forbids moving
one afterwards: a threshold discovered to be wrong is APPLIED LITERALLY and
recorded as wrong, as a numbered deviation in `ANALYSIS.md`, against data
already collected.

EVERY RULE PRINTS WHETHER OR NOT IT FIRES. A rule that only speaks when it
triggers is a rule nobody can audit, and a reader cannot tell it from a rule
that was never implemented. `None` is a THIRD state and is not `False`: it means
the rule could not be evaluated over the trials that ran, which is a different
sentence from "it was evaluated and was silent".

RULE N IS LOAD-BEARING AND IS IMPLEMENTED AS A GATE, NOT AS A REMARK. If arm A'
does not move the metric, arms A and B have not been shown capable of detecting
a difference, and T1 and T2 print **NOT ADMISSIBLE** rather than passing. It is
the rule `../criteria.md` section 3 registers first because it is the one most
likely to fire.

RULE T IS IMPLEMENTED THE SAME WAY. Every verdict is stated per arm, and T5 --
Q4 -- is the only statement permitted to combine two. T5 refuses to print its
sentence in every combination but one.

WHAT IT DOES NOT DO. It writes no verdict into any decision record, moves no
tolerance, proposes no value and chooses nothing (`../criteria.md` section 0).
It prints what the registered rules say about the trials that ran, and stops.
`ANALYSIS.md` is written from that print, later, by someone else.

**THE PRINT IS THE PRODUCT AND IT IS LONG.** Redirect it to a file; do not pipe
it through `head`. A previous campaign's operator piped a 1034-line report
through `head`, saw 143 lines, and `tee` still reported exit 0.

    python3 docs/measurements/2026-09-22-is-a-run-reproducible/harness/analyse.py \\
        > /tmp/is_a_run_reproducible.txt
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

#: V9 -- where an interpretation had to CHANGE after the data was seen, applied
#: literally to data already collected. **EMPTY, and it is empty because no
#: trial has run.** Nothing may be added here to make a verdict come out
#: differently; an entry is a confession, not a lever.
DEVIATIONS: tuple[tuple[str, str], ...] = ()

#: NOT deviations. These are the places where `../criteria.md`'s wording had to
#: be made CONCRETE before the first trial in order to be executable at all, and
#: they are printed at the top of every run so that the write-up carries them.
#: Each names the clause it makes concrete and the direction the choice leans.
#: **None of them moves a threshold**, and every one of them was fixed before
#: any trial ran.
#:
#: **THE BOUNDARY, AND IT BINDS EVERY ENTRY BELOW.** An interpretation may make
#: a SILENT clause concrete; it may not override a clause that is executable as
#: written, nor change which rows are admitted relative to the literal reading.
#: An unregistered exclusion criterion is precisely what V8 and V9 exist to
#: forbid, and "applied literally" has to mean literally. Where this file has
#: something to say about a row that the registered rule does not exclude on, it
#: says it as a FLAG printed beside the row -- never as a drop.
INTERPRETATIONS: tuple[tuple[str, str], ...] = (
    (
        "V1 scope",
        "V1, verbatim: \"`git rev-parse HEAD` and `git status --porcelain` taken "
        "at **both ends** of every block and written **into the record as "
        "fields**. The analyser drops any row without them. `git merge-base "
        "--is-ancestor 79b1acd HEAD` must succeed.\" **The operative sentence is "
        "about the FIELDS**: *them* is the two readings, so the drop condition is "
        "a row missing a `head` or a `porcelain` at either end. That is executable "
        "as written, and `v1` implements exactly it and nothing more. Read instead "
        "as *the porcelain must be empty*, V1 would drop every row of this "
        "campaign by construction -- the campaign writes its own untracked records "
        "into `raw/` -- but that reading is not what the clause says and it is not "
        "applied. THREE FURTHER CONDITIONS ARE EVALUATED AND PRINTED AS FLAGS ON "
        "THE ROW, AND NONE OF THEM EXCLUDES ANYTHING: HEAD equal at both ends, "
        "`--is-ancestor` true at both ends, and no porcelain entry at either end "
        "touching `model/`, `workspace/`, `tools/`, `tests/`, `scripts/`, "
        "`assets/`, `external/` or `.github/`. They were drop conditions in a "
        "draft of this file; a pre-first-trial review found that made the "
        "implementation stricter than the frozen rule, which is an unregistered "
        "exclusion criterion (V8, V9), and they were demoted to flags. A flagged "
        "row is reported and admitted; `ANALYSIS.md` is where a reader decides "
        "what a flag is worth."
    ),
    (
        "V3 and T3",
        "V3 says two trials with different world hashes are not comparable and are "
        "not compared. T3 REQUIRES comparing arm A' against arm A, and their worlds "
        "differ by construction -- the 1e-6 m offset IS a different world file. V3 "
        "is therefore applied to the comparisons where a hash difference would be "
        "ACCIDENTAL (T1 within arm A, T2 arm B against arm A) and not to T3, where "
        "it is the registered independent variable. Both hashes are printed beside "
        "the T3 verdict so the reader can see exactly which two worlds were "
        "compared."
    ),
    (
        "T3 quantifier",
        "T3 says a 1e-6 m initial offset must move the final position by more than "
        "1e-6 m. Over 2 arm-A' trials and 5 arm-A trials that is 10 pairs and the "
        "rule does not say whether ALL or ANY must exceed it. SENSITIVE is declared "
        "only when EVERY pair does. That is the direction that makes rule N fire "
        "more often, which makes T1 and T2 NOT ADMISSIBLE more often -- the "
        "conservative direction for a reproducibility claim. The minimum, median "
        "and maximum over the pairs are all printed, so the other reading is "
        "recoverable."
    ),
    (
        "the trial's outcome value",
        "`../criteria.md` I2 registers the at-rest rule and T1/T2/T3 compare `the "
        "final position`, without saying which recorded sample that is. It is "
        "`final_position`: the last snapshot `ModelPoses` held when `gz sim` "
        "finished its registered iteration count. The at-rest sample that "
        "satisfied I2 is also on every record, and this file prints the distance "
        "between the two for every trial -- so if the body was still moving at the "
        "end, that is visible rather than assumed away."
    ),
    (
        "arm C's I3 reading",
        "I3 is `the work-piece's position by I1 after the scenario's cycle "
        "assertions have passed`. The harness takes it on the event of "
        "`launch_test` printing its pre-shutdown unittest summary. When that line "
        "is not seen -- a buffered pipe rather than anything about the cell -- the "
        "registered fallback is the last non-None sample of the run, because "
        "`station_cycle.xml` commands no belt and the part is at rest on a "
        "stationary conveyor from the `PlaceAt` until teardown. `i3_source` says "
        "which reading was used on every row and the distance between the two is "
        "printed for every trial."
    ),
)

ARMS = ("A", "B", "Aprime", "C")

#: `../criteria.md` section 6's registered n. V8: no arm is topped up.
REGISTERED_N = {"A": 5, "B": 5, "Aprime": 2, "C": 2}

#: V1's (d) clause. The trees this campaign may not edit (section 0).
PROTECTED_TREES = (
    "model/", "workspace/", "tools/", "tests/", "scripts/",
    "assets/", "external/", ".github/",
)

WIDTH = 92


# ---------------------------------------------------------------------------
# Printing. Copied in shape from the two frozen analysers named in the header.
# ---------------------------------------------------------------------------


def wrap(text: str, indent: str = "    ") -> str:
    return "\n".join(
        textwrap.fill(
            paragraph, width=WIDTH, initial_indent=indent, subsequent_indent=indent
        )
        for paragraph in text.split("\n")
    )


def heading(text: str) -> None:
    print("")
    print("=" * WIDTH)
    print(text)
    print("=" * WIDTH)


def say(name: str, fired: bool | None, text: str) -> None:
    """Print a rule and whether it fired. `None` is a third state."""
    state = {True: "FIRED", False: "did not fire", None: "NOT EVALUABLE"}[fired]
    print(f"\n[{name}] {state}")
    print(wrap(text))


def verdict(name: str, value: str, text: str) -> None:
    print(f"\n[{name}] {value}")
    print(wrap(text))


# ---------------------------------------------------------------------------
# Loading, and the shakedown's three refusals.
# ---------------------------------------------------------------------------


def load_rows(raw: Path) -> tuple[list[dict], list[dict]]:
    """Every campaign record in `raw/`, and every row refused as a shakedown.

    THREE INDEPENDENT REFUSALS, not a convention about which directory the
    operator redirected into -- the 2026-09-03 campaign recorded what a
    directory convention is worth as an exclusion:

      1. `raw/*.json` at the TOP LEVEL only, so no recursive glob can sweep
         `raw/shakedown/` in;
      2. any label beginning `SHAKEDOWN` is skipped wherever it is found;
      3. any row carrying `is_shakedown` is dropped, whatever its file is
         called.
    """
    rows: list[dict] = []
    refused: list[dict] = []
    for path in sorted(raw.glob("*.json")):
        if path.name.endswith(".reader.json"):
            continue
        try:
            row = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            refused.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        row["_file"] = str(path)
        label = str(row.get("label", path.stem))
        if label.startswith("SHAKEDOWN") or row.get("is_shakedown"):
            refused.append(row)
            continue
        rows.append(row)
    return rows, refused


def by_arm(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    for row in rows:
        grouped.setdefault(str(row.get("arm")), []).append(row)
    for arm in grouped:
        grouped[arm].sort(key=lambda r: r.get("trial_index", 0))
    return grouped


# ---------------------------------------------------------------------------
# Validity. `../criteria.md` section 10.
# ---------------------------------------------------------------------------


def porcelain_touches_protected(porcelain: str) -> list[str]:
    """Which protected trees a `git status --porcelain` reading names.

    A READING THAT IS AN ERROR SENTINEL IS NOT A CLEAN TREE. `common.git`
    returns `"<error rc=...>"` when the command failed, and that string has no
    lines beginning with a protected prefix -- so it used to come back as an
    empty hit list and read exactly like a checkout with nothing modified. The
    sentinel is now its own hit, named as one.
    """
    text = porcelain or ""
    if text.startswith("<error"):
        return [f"THE PORCELAIN READING IS AN ERROR SENTINEL, NOT A TREE: {text}"]
    hits = []
    for line in text.splitlines():
        path = line[3:].strip().strip('"')
        # A rename prints `old -> new`; both halves count.
        for candidate in re.split(r"\s+->\s+", path):
            for tree in PROTECTED_TREES:
                if candidate.startswith(tree) and line not in hits:
                    hits.append(line)
    return hits


def v1(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """V1 -- the two git readings, at both ends, applied literally.

    **IT DROPS A ROW FOR ONE THING ONLY**: a missing `head` or `porcelain` at
    either end. That is what the frozen clause says -- *"the analyser drops any
    row without **them**"*, where *them* is the two recorded fields.

    The ancestry clause, HEAD equality across the two ends and the
    protected-tree porcelain filter are all evaluated and PRINTED AS FLAGS. They
    are not drop conditions, because V1 does not make them ones, and an
    exclusion criterion this file invented would be the unregistered exclusion
    V8 and V9 exist to forbid. See INTERPRETATIONS["V1 scope"].
    """
    kept, dropped = [], []
    for row in rows:
        opening, closing = row.get("git_open"), row.get("git_close")
        missing = []
        flags = []
        for end, reading in (("open", opening), ("close", closing)):
            if not reading:
                missing.append(f"the {end} git reading is absent")
                continue
            for field in ("head", "porcelain"):
                if reading.get(field) is None:
                    missing.append(f"the {end} reading has no `{field}` field")
        if opening and closing:
            if opening.get("head") != closing.get("head"):
                flags.append(
                    f"HEAD moved during the trial: {opening.get('head')} -> "
                    f"{closing.get('head')}"
                )
            if not (opening.get("base_commit_is_ancestor")
                    and closing.get("base_commit_is_ancestor")):
                flags.append(
                    f"{common.BASE_COMMIT} is not an ancestor of HEAD at both ends"
                )
            for end, reading in (("open", opening), ("close", closing)):
                hits = porcelain_touches_protected(reading.get("porcelain", ""))
                if hits:
                    flags.append(f"the {end} porcelain names protected tree(s): {hits}")
        row["_v1_present"] = not missing
        row["_v1_missing"] = missing
        row["_v1_flags"] = flags
        (kept if not missing else dropped).append(row)
    flagged = [row for row in kept if row["_v1_flags"]]
    say(
        "V1 the two git readings",
        bool(dropped),
        f"{len(kept)} row(s) kept, {len(dropped)} dropped, {len(flagged)} of the "
        "kept rows FLAGGED. V1, verbatim: `git rev-parse HEAD` and `git status "
        "--porcelain` taken at both ends of every block and written into the "
        "record as fields; THE ANALYSER DROPS ANY ROW WITHOUT THEM; `git "
        f"merge-base --is-ancestor {common.BASE_COMMIT} HEAD` must succeed. A "
        "missing field is the only drop condition, because it is the only one "
        "the clause states. The ancestry clause, HEAD equality and the "
        "protected-tree filter are evaluated and printed below as flags on rows "
        "that remain ADMITTED -- this file does not invent an exclusion "
        "criterion (V8, V9).",
    )
    for row in dropped:
        print(f"    dropped {row.get('label')}: {row['_v1_missing']}")
    for row in flagged:
        print(f"    FLAGGED (admitted) {row.get('label')}: {row['_v1_flags']}")
    if not flagged:
        print("    no kept row carries a V1 flag.")
    return kept, dropped


def v2(rows: list[dict]) -> None:
    """V2 -- the thing that actually ran: the seed, read from an independent source.

    THE PROBE ARMS' READ-BACK IS INDEPENDENT AND ARM C'S IS NOT, and this
    prints the difference rather than presenting both as checks. The probe
    reads `/proc/<pid>/cmdline` -- the kernel's copy of what was EXECed. Arm C
    has no equivalently cheap independent source: `common.SEED_A` is
    `scripts/scenario:90`'s own default, so the printed seed line is identical
    whether or not `CITE_PHYSICS_SEED` crossed the container boundary, and its
    agreement therefore means nothing. `../criteria.md` section 10 opens *"a
    rule that only ever confirms is not a rule"*.
    """
    disagreements = []
    not_independent = []
    for row in rows:
        if row.get("arm") == "C":
            line = row.get("seed_line") or ""
            not_independent.append(
                (row.get("label"), line or "<no seed line>",
                 str(row.get("seed_requested")) in line)
            )
            continue
        if row.get("seed_from_proc") is None:
            disagreements.append(
                (row.get("label"), "no independent read-back",
                 row.get("seed_from_proc_source"))
            )
        elif row.get("seed_from_proc") != row.get("seed_requested"):
            disagreements.append(
                (row.get("label"), row.get("seed_requested"), row.get("seed_from_proc"))
            )
    say(
        "V2 the seed that actually ran",
        bool(disagreements),
        "Each trial records the seed it was given, read back from a source the "
        "harness did not write. Probe arms: `/proc/<pid>/cmdline` of the started "
        "server, compared against the requested value -- an argv list parsed out "
        "of the argv list this harness has just built would only ever confirm. "
        f"{len(disagreements)} probe disagreement(s) or unreadable source(s).",
    )
    for item in disagreements:
        print(f"    {item}")
    print("")
    print(wrap(
        "ARM C'S FIELD IS NOT A PASSED CHECK. The seed line is printed below "
        "with whether the requested value appears in it; the value is "
        "`scripts/scenario`'s own default, so it appears either way. Nothing is "
        "concluded from it."
    ))
    for label, line, appears in not_independent:
        print(f"    {label}: appears_in_line={appears}  {line!r}")
    if not not_independent:
        print("    no arm-C row.")


def world_hash(row: dict) -> str:
    """The SHA-256 of the world file a row's trial launched, whatever its arm.

    The probe arms write their own world and hash the bytes they wrote. Arm C
    launches the INSTALLED generated world, and `read_workpiece.py` hashes it
    through `ros2 pkg prefix cite_generated` -- the same door V-physics uses.
    """
    if row.get("arm") == "C":
        return str(row.get("installed_world_sha256"))
    return str(row.get("world_sha256"))


def v3(rows: list[dict]) -> dict[str, set[str]]:
    """V3 -- the world that actually ran. Returns the hash set per arm.

    ARM C IS INCLUDED, AND WAS NOT UNTIL A PRE-FIRST-TRIAL REVIEW. No arm-C
    record carried a world hash, this rule skipped the arm, and T4 -- the
    comparison V3's own sentence is about -- had no hash guard where T1 and T2
    both have one.
    """
    hashes: dict[str, set[str]] = {}
    for row in rows:
        hashes.setdefault(str(row.get("arm")), set()).add(world_hash(row))
    split = {arm: value for arm, value in hashes.items() if len(value) != 1}
    unhashed = [
        row.get("label") for row in rows if world_hash(row) in ("None", "")
    ]
    say(
        "V3 the world that actually ran",
        bool(split) or bool(unhashed),
        "Each trial records the SHA-256 of the world file it launched. Two trials "
        "with different world hashes are not comparable and are not compared -- "
        "which is enforced in T1, T2 and T4 below. An arm whose own trials do not "
        f"share one hash is reported here. Rows carrying no hash at all: "
        f"{unhashed}.",
    )
    for arm in sorted(hashes):
        print(f"    {arm}: {sorted(hashes[arm])}")
    for row in rows:
        if row.get("arm") == "C":
            print(
                f"    {row.get('label')} installed={row.get('installed_world_sha256')} "
                f"plan={row.get('plan_world_sha256')} "
                f"agree={row.get('world_paths_agree')}"
            )
    return hashes


def v4(rows: list[dict]) -> None:
    """V4 -- subscription as an event, never as a sleep."""
    missing = [
        row.get("label") for row in rows
        if row.get("arm") != "C" and row.get("first_snapshot_wall") is None
    ]
    say(
        "V4 subscription as an event",
        bool(missing),
        "The first snapshot must have arrived before any sample was taken. "
        "Reliable QoS is a promise to MATCHED subscribers only; the match is an "
        "event, never a sleep. A probe row with no `first_snapshot_wall` never "
        f"reached that event. {len(missing)} such row(s): {missing}.",
    )


def v5(rows: list[dict]) -> None:
    """V5 -- one writer, for the length of a block."""
    evidence = []
    for row in rows:
        for end in ("git_open", "git_close"):
            porcelain = (row.get(end) or {}).get("porcelain", "")
            if porcelain_touches_protected(porcelain):
                evidence.append((row.get("label"), end))
    say(
        "V5 one writer",
        bool(evidence),
        "One checkout, one writer, for the length of a block. It is not directly "
        "observable, so what stands for it is V1's own evidence: a protected tree "
        "changing between the two ends of a trial is a second writer. **ROWS SO "
        "AFFECTED ARE FLAGGED BY V1 AND ARE NOT DROPPED BY IT** -- V1's drop "
        "condition is a missing field and nothing else -- so a row listed here is "
        f"a row still in every figure below. {len(evidence)} occurrence(s): "
        f"{evidence}.",
    )


def v6(raw: Path, rows: list[dict]) -> None:
    """V6 -- no rebuild mid-campaign."""
    provenance = raw / "provenance.txt"
    if not provenance.exists():
        say("V6 no rebuild mid-campaign", None, f"{provenance} does not exist.")
        return
    text = provenance.read_text()
    builds = text.count("# ---- ./scripts/build ----")
    starts = [row.get("started_wall") for row in rows if row.get("started_wall")]
    say(
        "V6 no rebuild mid-campaign",
        builds != 1,
        "The workspace is built ONCE, before the first block, and the build is "
        f"recorded in `raw/provenance.txt`. That file carries {builds} build "
        f"block(s) against {len(starts)} trial(s). `run_campaign.sh` refuses to "
        "build again once any record exists; more than one block here means the "
        "campaign was rebuilt under itself and the trials either side of it are "
        "not trials of one install.",
    )


def v7(rows: list[dict]) -> None:
    """V7 -- load is flagged, never excluded."""
    print("\n[V7 load] REPORTED, NEVER EXCLUDED")
    print(
        wrap(
            "A load threshold chosen after seeing the data is a threshold chosen "
            "by the data. No row is excluded on load and no threshold is derived "
            "from it. The one-minute figures at both ends of every trial:"
        )
    )
    for row in rows:
        opening = (row.get("load_open") or [None])[0]
        closing = (row.get("load_close") or [None])[0]
        print(f"    {row.get('label')}: open={opening} close={closing}")


def v8(grouped: dict[str, list[dict]]) -> None:
    """V8 -- n is what it was. No arm is topped up after seeing its numbers."""
    short = {
        arm: (len(grouped.get(arm, [])), n)
        for arm, n in REGISTERED_N.items()
        if len(grouped.get(arm, [])) != n
    }
    say(
        "V8 n is what it was",
        bool(short),
        "No arm is topped up after seeing its numbers. Registered n: "
        f"{REGISTERED_N}. Collected: "
        f"{ {arm: len(grouped.get(arm, [])) for arm in REGISTERED_N} }. An arm "
        "that came up short is REPORTED with the n it reached and is not re-run; "
        f"an arm with more rows than its registered n is a topping-up and is a "
        f"defect of the run. {short}",
    )


def v9() -> None:
    """V9 -- no threshold moves."""
    applied = {
        "T1": common.T1_TOL_M,
        "T2": common.T2_TOL_M,
        "T3": common.T3_TOL_M,
        "T4": common.T4_TOL_M,
        "I2 tolerance": common.AT_REST_TOL_M,
        "I2 gap": common.AT_REST_MIN_GAP_S,
        "I2 ceiling": common.AT_REST_CEILING_S,
        "V11 loss fraction": common.V11_LOSS_FRACTION,
    }
    say(
        "V9 no threshold moves",
        bool(DEVIATIONS),
        "A threshold discovered to be wrong is APPLIED LITERALLY and recorded as "
        "wrong, as a numbered deviation in `ANALYSIS.md`, against data already "
        f"collected. The thresholds this run applied: {applied}. "
        f"{len(DEVIATIONS)} deviation(s) declared.",
    )
    for number, text in DEVIATIONS:
        print(f"\n    Deviation {number}")
        print(wrap(text, indent="        "))


def v10(rows: list[dict]) -> None:
    """V10 -- the partition door."""
    partitions = {
        str(row.get("gz_partition"))
        for row in rows
        if row.get("arm") != "C" and row.get("gz_partition")
    }
    missing = [
        row.get("label") for row in rows
        if row.get("arm") != "C" and not row.get("gz_partition")
    ]
    say(
        "V10 the partition door",
        bool(missing) or len(partitions) > 1,
        "Every Gazebo-transport process goes through `cite_bringup.gz`. An "
        "unpartitioned `gz model --list` reaches no world and EXITS 0, so a probe "
        "that lost its partition would look like a quiet trial. Every probe row "
        "records the partition the environment carried, taken from the plan "
        f"through that door. Partitions seen: {sorted(partitions)}. Rows with "
        f"none: {missing}.",
    )


def v11(grouped: dict[str, list[dict]]) -> dict[str, bool]:
    """V11 -- instrument loss is counted, never quiet. Above 20 %: NOT ADMISSIBLE."""
    over = {}
    print("\n[V11 instrument loss] COUNTED AND REPORTED SEPARATELY")
    print(
        wrap(
            "A trial whose instrument returned nothing is excluded, COUNTED, and "
            "reported separately from every other exclusion -- never recorded as a "
            "trial in which nothing happened. Above 20 % per arm the verdict for "
            "that arm is NOT ADMISSIBLE."
        )
    )
    for arm in ARMS:
        rows = grouped.get(arm, [])
        lost = [row for row in rows if row.get("instrument_loss")]
        fraction = (len(lost) / len(rows)) if rows else None
        over[arm] = bool(fraction is not None and fraction > common.V11_LOSS_FRACTION)
        print(
            f"    {arm}: {len(lost)} loss(es) of {len(rows)} row(s)"
            f"  fraction={fraction}  over_20pct={over[arm]}"
        )
        for row in lost:
            print(f"        {row.get('label')}: {row.get('instrument_loss_reason')}")
    return over


def v_physics(rows: list[dict]) -> None:
    """V-physics -- the probe is the cell's physics."""
    bad = [
        row.get("label") for row in rows
        if row.get("arm") != "C" and not (row.get("v_physics") or {}).get("agree")
    ]
    say(
        "V-physics the probe is the cell's physics",
        bool(bad),
        "Before the first trial the harness compares its probe world's `<physics>` "
        "block against the INSTALLED generated world's, read through `ros2 pkg "
        "prefix cite_generated`, and REFUSES TO RUN if they differ -- otherwise arm "
        "A measures a different simulator from the one the cell runs. A row here "
        f"means a trial ran with the check failing. {len(bad)} such row(s): {bad}.",
    )
    seen = {
        json.dumps((row.get("v_physics") or {}).get("probe_physics"), sort_keys=True)
        for row in rows if row.get("arm") != "C"
    }
    for item in sorted(seen):
        print(f"    probe physics: {item}")


def v_container(raw: Path, rows: list[dict]) -> None:
    """V-container -- no live container before a block."""
    provenance = raw / "provenance.txt"
    text = provenance.read_text() if provenance.exists() else "<absent>"
    print("\n[V-container] REPORTED; THE REFUSAL IS IN `run_campaign.sh`")
    print(
        wrap(
            "`docker ps` is empty before every block. CLAUDE.md section 2 records "
            "that a run taken while a `dev` container is up is not a reading of "
            "this repository: `exec_in_container` reuses it with `compose exec`, "
            "which does not run the image's entrypoint, and nothing of ours "
            "executes at all. `run_campaign.sh` REFUSES rather than warns; what is "
            "printed here is what each record and the provenance saw."
        )
    )
    block = re.search(r"docker_ps_at_start<<EOF\n(.*?)\nEOF", text, re.DOTALL)
    print(f"    provenance docker_ps_at_start: {block.group(1)!r} " if block else
          "    provenance docker_ps_at_start: <not recorded>")
    for row in rows:
        seen = row.get("docker_ps") or row.get("docker_ps_open")
        print(f"    {row.get('label')}: {seen!r}")


def v_planner(grouped: dict[str, list[dict]]) -> list[dict]:
    """V-planner -- arm C flags the fallback. Flagged, never dropped."""
    rows = grouped.get("C", [])
    flagged = [row for row in rows if row.get("ompl_answered_a_motion")]
    say(
        "V-planner arm C flags the fallback",
        bool(flagged),
        "A trial in which OMPL answered any motion is FLAGGED and reported "
        "separately, because an unseedable planner would confound Q3 with a "
        "question this campaign is not asking. It is NOT silently pooled with a "
        f"Pilz-only trial and it is NOT dropped. {len(flagged)} of {len(rows)} "
        "arm-C trial(s) flagged.\n"
        "THE COUNT IS RESTRICTED AND THE RAW WHOLE-LOG COUNT IS PRINTED BESIDE "
        "IT. `scripts/scenario:189-190` prints both marker strings itself, in its "
        "pre-run advice block, so a whole-log count of either is at least 1 on "
        "every run and would flag every trial. The flag is computed from lines "
        "the skill server emitted, after the cell's output starts; the raw "
        "figures below are the defective instrument, kept visible. This is the "
        "same defect class CLAUDE.md section 2 records for a whole-log grep "
        "counting a verdict string out of a commit body echoed by CI.",
    )
    for row in rows:
        print(
            f"    {row.get('label')}: fallback={row.get('planner_fallback_count')} "
            f"declined={row.get('planner_fallback_declined_count')} "
            f"flagged={bool(row.get('ompl_answered_a_motion'))}"
        )
        print(
            f"        raw whole-log: fallback="
            f"{row.get('planner_fallback_count_raw_whole_log')} "
            f"declined={row.get('planner_fallback_declined_count_raw_whole_log')}"
            f"   region-unprefixed fallback="
            f"{row.get('planner_fallback_count_region_unprefixed')}"
        )
        print(
            f"        anchor={row.get('planner_scan_anchor')!r} "
            f"region={row.get('planner_scan_region_chars')} of "
            f"{row.get('planner_scan_log_chars')} chars"
        )
    return flagged


# ---------------------------------------------------------------------------
# The measured quantity.
# ---------------------------------------------------------------------------


def outcome(row: dict) -> list[float] | None:
    """The trial's outcome value. See INTERPRETATIONS."""
    if row.get("arm") == "C":
        return row.get("i3_position")
    return row.get("final_position")


def healthy(rows: list[dict]) -> list[dict]:
    """Section 5.3's healthy trials: admitted, not an instrument loss, with a value."""
    return [
        row for row in rows
        if not row.get("instrument_loss") and outcome(row) is not None
    ]


def coordinate_spread(positions: list[list[float]]) -> float | None:
    """The largest |delta| over every coordinate of every pair. Never rounded."""
    worst = None
    for first, second in itertools.combinations(positions, 2):
        for a, b in zip(first, second, strict=True):
            delta = abs(a - b)
            worst = delta if worst is None else max(worst, delta)
    return worst


def cross_spread(left: list[list[float]], right: list[list[float]]) -> list[float]:
    """Every pair's largest coordinate |delta|, across two sets."""
    return [
        max(abs(a - b) for a, b in zip(first, second, strict=True))
        for first in left
        for second in right
    ]


def sample_motion(row: dict) -> tuple[int | None, float | None, float | None]:
    """Distinct sampled positions, the wall time of the LAST change, and the
    gap between that change and the last sample taken.

    WHY THIS IS PRINTED. I2 compares two samples a registered gap apart and
    calls them rest when they agree. It cannot tell a body at rest from a
    FROZEN SUBSCRIPTION: `ModelPoses` keeps only its newest snapshot and returns
    it forever, and `position()` discards the `Pose_V` header stamp, so a
    publisher that stopped and a body that stopped read identically. **I2 is
    registered and is applied literally; this changes nothing about it.** What
    it adds is the two numbers that make a frozen tail visible -- a trial whose
    last change is far behind its last sample was reading a snapshot nobody
    refreshed, and a reader can see that rather than having to trust it.
    """
    samples = row.get("samples") or []
    positions = [tuple(sample.get("position") or ()) for sample in samples]
    if not positions:
        return None, None, None
    distinct = len(set(positions))
    last_change_wall = samples[0].get("wall")
    for index in range(1, len(positions)):
        if positions[index] != positions[index - 1]:
            last_change_wall = samples[index].get("wall")
    last_wall = samples[-1].get("wall")
    quiet = None
    if isinstance(last_wall, (int, float)) and isinstance(last_change_wall, (int, float)):
        quiet = last_wall - last_change_wall
    return distinct, last_change_wall, quiet


def positions_table(name: str, rows: list[dict]) -> None:
    print(f"\n    {name}, at full double precision:")
    for row in rows:
        value = outcome(row)
        if row.get("arm") != "C":
            extra = (
                f"  at_rest={row.get('at_rest', {}).get('reached')}"
                f"  final_vs_at_rest={row.get('final_vs_at_rest_max_delta_m')}"
                f"  iters_done={row.get('server_ran_to_completion')}"
            )
        else:
            # The per-trial V-planner flag is stated BESIDE the position
            # it belongs to, because V-planner's paragraph is elsewhere in this
            # print and a reader comparing two positions needs to know which of
            # them OMPL touched without scrolling.
            extra = (
                f"  i3_source={row.get('i3_source')}"
                f"  trig_vs_last={row.get('triggered_vs_last_max_delta_m')}"
                f"  V-planner_flagged={bool(row.get('ompl_answered_a_motion'))}"
                f"  cycle_s={row.get('scenario_cycle_seconds')}"
                f"  harness_wall_s={row.get('wall_duration_s')}"
            )
        print(f"      {row.get('label')}  seed={row.get('seed_requested')}  {value!r}{extra}")
        if row.get("arm") != "C":
            # THE LOADED INITIAL POSE, PRINTED BESIDE THE OUTCOME. Arm A'
            # is the only arm whose job is to MOVE the metric and its
            # perturbation is the only thing that makes T3 mean anything; if the
            # 1e-6 m offset failed to load, T3 would read INSENSITIVE, rule N
            # would fire, and the campaign would publish a rigorous-looking
            # UNRESOLVED for an INSTRUMENT FAILURE. A first position whose x is
            # at the 1e-17 level is an unperturbed world; a live perturbation is
            # eleven orders larger and unmistakable at this precision.
            print(
                f"        first_position={row.get('first_position')!r}"
                f"  x_offset_requested={row.get('x_offset_m')!r}"
            )
            distinct, last_change, quiet = sample_motion(row)
            print(
                f"        distinct sampled positions={distinct}"
                f"  last change at wall={last_change!r}"
                f"  quiet for {quiet!r} s before the last sample"
            )
        elif row.get("triggered_vs_last_max_delta_m") is None:
            # `trig_vs_last` is None exactly when the registered fallback
            # was used, which is the one case where the "the part is at rest
            # from the PlaceAt until teardown" assumption is checked by nothing
            # else. The tail spread stands in for it.
            print(
                f"        FALLBACK READING USED; trailing-sample spread instead: "
                f"{row.get('fallback_tail')!r}"
            )


# ---------------------------------------------------------------------------
# `../criteria.md` section 7 -- the decision rules.
# ---------------------------------------------------------------------------


def t3(grouped: dict[str, list[dict]], hashes: dict[str, set[str]]) -> str:
    """T3 -- the control. Arm A' against arm A. RUN FIRST, because rule N gates."""
    a_rows = healthy(grouped.get("A", []))
    p_rows = healthy(grouped.get("Aprime", []))
    positions_table("arm A final positions", a_rows)
    positions_table("arm A' final positions", p_rows)
    print(
        f"\n    world hashes: A={sorted(hashes.get('A', []))} "
        f"A'={sorted(hashes.get('Aprime', []))}"
    )
    if not a_rows or not p_rows:
        verdict(
            "T3 the control",
            "NOT EVALUABLE",
            "Arm A or arm A' contributed no healthy trial, so the metric has not "
            "been shown capable of detecting a difference and it has not been shown "
            "incapable either. This is a THIRD state and is not INSENSITIVE.",
        )
        return "NOT EVALUABLE"
    deltas = sorted(cross_spread(p_rows_positions(p_rows), p_rows_positions(a_rows)))
    every = all(delta > common.T3_TOL_M for delta in deltas)
    result = "SENSITIVE" if every else "INSENSITIVE"
    ratios = [delta / common.PERTURBATION_M for delta in deltas]
    verdict(
        "T3 the control",
        result,
        f"A {common.PERTURBATION_M:g} m initial offset in x must move the final "
        f"position by more than {common.T3_TOL_M:g} m for the metric to be "
        f"SENSITIVE. Over {len(deltas)} A'-against-A pairs the largest coordinate "
        f"|delta| is: min={deltas[0]!r} median={deltas[len(deltas) // 2]!r} "
        f"max={deltas[-1]!r}. SENSITIVE is declared only when EVERY pair exceeds "
        "the threshold (see INTERPRETATIONS). "
        + (
            "The metric can move, so arms A and B have been shown capable of "
            "detecting a difference and rule N does not fire."
            if every
            else "RULE N FIRES. A null is never a clearance: arms A and B have NOT "
            "been shown capable of detecting a difference, their agreement "
            "evidences nothing, and T1 and T2 below are NOT ADMISSIBLE rather "
            "than passing."
        ),
    )
    print(f"    all {len(deltas)} pairwise maxima: {deltas!r}")
    print("")
    print(wrap(
        "THE RATIO delta / perturbation, PAIR BY PAIR. **A RATIO AT OR NEAR "
        "1.000000 IS PASS-THROUGH AND NOT SENSITIVITY.** The threshold T3 "
        "compares against is the perturbation's own value, and the probe world's "
        "ground plane is infinite and centred, so the dynamics are "
        "translation-equivariant in x: a system that AMPLIFIES NOTHING returns "
        "exactly 1e-6 m, and the verdict then turns on the last bits of the base "
        "coordinate rather than on any property of the solver. **T3 IS FROZEN AND "
        "IS APPLIED LITERALLY (V9)** -- the threshold is not moved and this "
        "instrument does not change the verdict. If the ratios land at 1.0, that "
        "is a NUMBERED DEVIATION for `ANALYSIS.md`, applied to data already "
        "collected, and NOT a re-run. A ratio far above 1 is amplification; a "
        "ratio far below 1 is a metric that damped the perturbation away."
    ))
    for delta, ratio in zip(deltas, ratios, strict=True):
        print(f"      delta={delta!r}  delta/perturbation={ratio!r}")
    return result


def p_rows_positions(rows: list[dict]) -> list[list[float]]:
    return [outcome(row) for row in rows if outcome(row) is not None]  # type: ignore[misc]


def t1(grouped: dict[str, list[dict]], sensitivity: str, hashes: dict[str, set[str]],
       loss_over: dict[str, bool]) -> str:
    """T1 -- Q1. Is the physics engine reproducible?"""
    rows = healthy(grouped.get("A", []))
    if sensitivity != "SENSITIVE":
        verdict(
            "T1 Q1 is the physics engine reproducible",
            "NOT ADMISSIBLE",
            f"RULE N. T3 reads {sensitivity}, so the metric has not been shown "
            "capable of detecting a difference and arm A's agreement -- whatever it "
            "is -- evidences nothing. The measured figure is printed below for the "
            "record and IS NOT A VERDICT.",
        )
    if loss_over.get("A"):
        verdict(
            "T1 Q1",
            "NOT ADMISSIBLE",
            "V11: arm A's instrument-loss fraction is above 20 %.",
        )
    if len(rows) < 2:
        verdict(
            "T1 Q1", "NOT EVALUABLE",
            f"Arm A contributed {len(rows)} healthy trial(s); a pairwise comparison "
            "needs two.",
        )
        return "NOT EVALUABLE"
    if len(hashes.get("A", set())) != 1:
        verdict(
            "T1 Q1", "NOT EVALUABLE",
            "V3: arm A's trials do not share one world hash, so they are not "
            f"comparable and are not compared. {sorted(hashes.get('A', []))}",
        )
        return "NOT EVALUABLE"
    worst = coordinate_spread(p_rows_positions(rows))
    reproducible = worst is not None and worst < common.T1_TOL_M
    result = "REPRODUCIBLE AT 1e-9 m" if reproducible else "NOT REPRODUCIBLE"
    if sensitivity != "SENSITIVE" or loss_over.get("A"):
        result = "NOT ADMISSIBLE"
    verdict(
        "T1 Q1 is the physics engine reproducible",
        result,
        f"Over arm A's {len(rows)} healthy trials every pairwise coordinate "
        f"difference must be below {common.T1_TOL_M:g} m. The maximum |delta| is "
        f"{worst!r} m, printed and NEVER ROUNDED AWAY. The resolution is named in "
        "the verdict: agreement here is INDISTINGUISHABLE AT 1e-9 m, never "
        "IDENTICAL -- the instrument bounds the claim. 1e-9 m is a judgement, "
        "chosen an order below the perturbation T3 uses and far below anything "
        "physically meaningful for a 50 mm box; it is not a derivation.",
    )
    return result


def t2(grouped: dict[str, list[dict]], sensitivity: str, hashes: dict[str, set[str]],
       loss_over: dict[str, bool]) -> str:
    """T2 -- Q2. Does `gz sim --seed` change a physical outcome?"""
    a_rows = healthy(grouped.get("A", []))
    b_rows = healthy(grouped.get("B", []))
    positions_table("arm B final positions", b_rows)
    if not a_rows or not b_rows:
        verdict("T2 Q2", "NOT EVALUABLE", "One of arms A and B contributed no healthy trial.")
        return "NOT EVALUABLE"
    if hashes.get("A") != hashes.get("B"):
        verdict(
            "T2 Q2", "NOT EVALUABLE",
            "V3: arms A and B did not run the same world file, so they are not "
            f"comparable and are not compared. A={sorted(hashes.get('A', []))} "
            f"B={sorted(hashes.get('B', []))}",
        )
        return "NOT EVALUABLE"
    deltas = sorted(cross_spread(p_rows_positions(b_rows), p_rows_positions(a_rows)))
    within_b = coordinate_spread(p_rows_positions(b_rows))
    # THE WITHIN-A SPREAD IS PRINTED BESIDE IT, and it is the number a reader
    # needs to discount a T2 positive. A cross-arm difference above the
    # threshold means "the seed reaches a physical outcome" only if arm A --
    # five trials at ONE seed -- agreed with itself below it. If arm A's own
    # spread is the same size, what T2 measured is arm A failing to reproduce,
    # which is T1's question and not T2's.
    within_a = coordinate_spread(p_rows_positions(a_rows))
    reaches = deltas[-1] > common.T2_TOL_M
    result = (
        "THE SEED REACHES A PHYSICAL OUTCOME" if reaches else "NO EFFECT DETECTED"
    )
    if sensitivity != "SENSITIVE" or loss_over.get("B") or loss_over.get("A"):
        result = "NOT ADMISSIBLE"
    verdict(
        "T2 Q2 does `gz sim --seed` change a physical outcome",
        result,
        f"Arm B's set compared against arm A's: {len(deltas)} pairs, largest "
        f"coordinate |delta| max={deltas[-1]!r} min={deltas[0]!r}; within arm B "
        f"the spread is {within_b!r} and WITHIN ARM A -- five trials at ONE seed "
        f"-- it is {within_a!r}. A cross-arm difference no larger than arm A's "
        "own spread is arm A failing to reproduce, which is T1's question and "
        f"not this one. Any difference above {common.T2_TOL_M:g} m "
        "means the seed reaches a physical outcome and ADR-0027:480 is wrong on "
        "this host. No difference means NO EFFECT DETECTED, which is NOT the "
        "sentence \"the seed does nothing\" and may not be written as one unless "
        f"T3 reads SENSITIVE -- T3 reads {sensitivity}."
        + (
            ""
            if sensitivity == "SENSITIVE"
            else " RULE N FIRES: this verdict is NOT ADMISSIBLE."
        ),
    )
    print(f"    all {len(deltas)} pairwise maxima: {deltas!r}")
    return result


def t4(grouped: dict[str, list[dict]], loss_over: dict[str, bool],
       flagged: list[dict], hashes: dict[str, set[str]]) -> str:
    """T4 -- Q3. Is a run of the whole cell reproducible?"""
    rows = healthy(grouped.get("C", []))
    positions_table("arm C work-piece positions", rows)
    for row in grouped.get("C", []):
        print(
            f"      {row.get('label')} verdict line: {row.get('verdict_line')!r}"
            f"  reader agrees={row.get('verdict_lines_agree')}"
        )
    if len(rows) < 2:
        verdict(
            "T4 Q3", "NOT EVALUABLE",
            f"Arm C contributed {len(rows)} healthy trial(s); Q3 asks for the same "
            "thing twice.",
        )
        return "NOT EVALUABLE"
    if loss_over.get("C"):
        verdict("T4 Q3", "NOT ADMISSIBLE", "V11: arm C's loss fraction is above 20 %.")
        return "NOT ADMISSIBLE"
    # V3, THE GUARD T1 AND T2 BOTH HAVE AND THIS ONE DID NOT. "Two trials with
    # different world hashes are not comparable and are not compared." T4 is
    # the comparison that clause is about: two runs of the whole cell, which
    # load the installed generated world rather than one this harness wrote.
    if len(hashes.get("C", set())) != 1 or "None" in hashes.get("C", set()):
        verdict(
            "T4 Q3", "NOT EVALUABLE",
            "V3: arm C's trials do not share one world hash, or a trial recorded "
            "none, so they are not comparable and are not compared. "
            f"{sorted(hashes.get('C', []))}",
        )
        return "NOT EVALUABLE"
    positions = p_rows_positions(rows)
    worst = coordinate_spread(positions)
    # T4 QUOTES THE SCENARIO'S OWN DURATION. `wall_duration_s` is taken
    # after a `finally` block that waits on the reader with two 60 s bounds, so
    # it includes up to about two minutes of the rig's teardown and is not a
    # measurement of the run. Both are printed; only one is quoted.
    durations = [row.get("scenario_cycle_seconds") for row in rows]
    harness_walls = [row.get("wall_duration_s") for row in rows]
    reproduces = worst is not None and worst < common.T4_TOL_M
    result = "THE CELL REPRODUCES" if reproduces else "THE CELL DOES NOT REPRODUCE"
    spread = (
        max(durations) - min(durations)
        if durations and all(isinstance(d, (int, float)) for d in durations) else None
    )
    flagged_labels = [row.get("label") for row in flagged]
    verdict(
        "T4 Q3 is a run of the whole cell reproducible",
        result,
        f"Arm C's work-piece positions must agree to better than "
        f"{common.T4_TOL_M:g} m. The largest coordinate |delta| is {worst!r} m. "
        f"Durations, as the scenario itself measured them (`Ran N tests in Xs`): "
        f"{durations!r}; their difference is {spread!r} s. REPORTED AS TWO VALUES "
        "OVER TWO RUNS AND NEVER AS A RATE. The harness's own wall figures are "
        f"{harness_walls!r} s and are NOT what is quoted here -- they are taken "
        "after the reader teardown and carry up to about two minutes of it. The "
        f"{common.T4_TOL_M:g} m is three orders below the 50 mm part and is a "
        "judgement."
        + (
            f" V-PLANNER: {len(flagged_labels)} of these trials is flagged -- "
            f"{flagged_labels} -- meaning OMPL answered at least one motion in it. "
            "THE |delta| ABOVE WAS COMPUTED OVER BOTH TRIALS TOGETHER, so a "
            "flagged trial is inside this verdict; which trials carry the flag is "
            "stated per row in the table above and in V-planner's own block. "
            "V-planner drops nothing, and this sentence says what happened rather "
            "than that the flagged trial was held out."
            if flagged_labels
            else " V-PLANNER: no arm-C trial is flagged, so no OMPL motion is "
            "inside this verdict."
        ),
    )
    return result


def t5(t1_result: str, t3_result: str, t4_result: str) -> None:
    """T5 -- Q4. The only statement permitted to combine two arms (rule T)."""
    permitted = (
        t1_result == "REPRODUCIBLE AT 1e-9 m"
        and t3_result == "SENSITIVE"
        and t4_result == "THE CELL DOES NOT REPRODUCE"
    )
    if permitted:
        verdict(
            "T5 Q4 where does the irreproducibility enter",
            "THE REGISTERED SENTENCE IS PERMITTED",
            "T1 reads REPRODUCIBLE, T3 reads SENSITIVE and T4 reads DOES NOT "
            "REPRODUCE, which is the ONE combination `../criteria.md` T5 permits. "
            "The sentence is therefore written, and it is the only statement in "
            "this campaign that combines two arms (rule T):\n\n"
            "    \"the irreproducibility is in the asynchronous coupling and not "
            "in the solver\"\n\n"
            "It is a statement about this host, this commit and these trials, and "
            "about nothing else (section 11).",
        )
        return
    verdict(
        "T5 Q4 where does the irreproducibility enter",
        "UNRESOLVED",
        "The sentence \"the irreproducibility is in the asynchronous coupling and "
        "not in the solver\" may be written ONLY when T1 reads REPRODUCIBLE and T3 "
        "reads SENSITIVE and T4 reads DOES NOT REPRODUCE. THAT IS NOT THE "
        f"COMBINATION THIS CAMPAIGN GOT: T1={t1_result!r}, T3={t3_result!r}, "
        f"T4={t4_result!r}. The campaign states the combination it got and answers "
        "Q4 UNRESOLVED. Nothing here may be written as a weaker version of the "
        "permitted sentence.",
    )


def t6(raw: Path) -> None:
    """T6 -- section 2's gap. Arm S. Reported; no pass/fail."""
    scan = raw / "symbol_scan.txt"
    print("\n[T6 arm S the symbol scan] REPORTED; NO PASS/FAIL")
    print(
        wrap(
            "Arm S's output, with its command, its library list and `uname -m`. It "
            "is an INSTRUMENT BEING WRITTEN DOWN, not a hypothesis being tested, "
            "and it cannot by itself confirm or refute T2: a fixed-step rigid-body "
            "integrator can be perfectly deterministic while drawing from no RNG at "
            "all, and an undefined `rand` symbol is a link against libc rather than "
            "a call site. Printed in full, whatever it says."
        )
    )
    if not scan.exists():
        print(f"\n    {scan} does not exist; arm S has not been run.")
        return
    print("")
    for line in scan.read_text(errors="replace").splitlines():
        print(f"    {line}")


def predictions(t1_result: str, t2_result: str, t4_result: str) -> None:
    """Section 11: the prediction in section 2 is scored, INCLUDING where it is wrong."""
    rows = (
        ("arm A reproduces", "REPRODUCIBLE AT 1e-9 m", t1_result),
        ("arm B shows no effect", "NO EFFECT DETECTED", t2_result),
        ("arm C does not reproduce", "THE CELL DOES NOT REPRODUCE", t4_result),
    )
    heading("THE PREDICTION, SCORED")
    print(
        wrap(
            "`../criteria.md` section 2 wrote a prediction before any trial and "
            "section 11 requires it to be scored INCLUDING WHERE IT IS WRONG. \"If "
            "that is not what we see, the reading above is wrong and the campaign "
            "says so.\" A campaign that only ever confirms its own reading is not a "
            "measurement."
        )
    )
    for what, predicted, measured in rows:
        mark = "as predicted" if predicted == measured else "NOT AS PREDICTED"
        print(f"\n    {what}")
        print(f"        predicted: {predicted}")
        print(f"        measured:  {measured}   -> {mark}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default=str(common.RAW))
    arguments = parser.parse_args()
    raw = Path(arguments.raw)

    heading("docs/measurements/2026-09-22-is-a-run-reproducible")
    print(
        wrap(
            "Is a run of this cell reproducible at all, and where does the "
            "irreproducibility enter? `../criteria.md` sections 7 and 10, applied "
            "to `raw/`. THIS CAMPAIGN DECIDES NOTHING (section 0): no record is "
            "corrected on this evidence here, no tolerance or ceiling anywhere in "
            "the repository moves on it, nothing here is a fidelity claim, and "
            "nothing here proposes a fix."
        )
    )
    print("")
    print(wrap("RULE T -- the arms are not each other's evidence. Every verdict "
               "below is stated per arm; T5 is the only statement permitted to "
               "combine two."))
    print("")
    print(wrap("RULE N -- a null is never a clearance. If arm A' does not move the "
               "metric, T1 and T2 are NOT ADMISSIBLE rather than passing. It is "
               "implemented as a gate in `t1` and `t2` below, not as a remark."))

    heading("DEVIATIONS")
    if not DEVIATIONS:
        print(wrap("None declared."))
    for number, text in DEVIATIONS:
        print(f"\n    Deviation {number}")
        print(wrap(text, indent="        "))

    heading("INTERPRETATIONS -- fixed before the first trial, moving no threshold")
    for name, text in INTERPRETATIONS:
        print(f"\n    {name}")
        print(wrap(text, indent="        "))

    rows, refused = load_rows(raw)
    heading("WHAT WAS READ")
    print(f"    raw: {raw}")
    print(f"    campaign rows: {len(rows)}")
    print(f"    refused as shakedown or unreadable: {len(refused)}")
    for row in refused:
        print(f"        {row.get('label') or row.get('file')}  "
              f"is_shakedown={row.get('is_shakedown')}")

    heading("VALIDITY -- `../criteria.md` section 10, every rule printing either way")
    kept, _dropped = v1(rows)
    v2(kept)
    hashes = v3(kept)
    v4(kept)
    v5(kept)
    v6(raw, kept)
    v7(kept)
    grouped = by_arm(kept)
    v8(grouped)
    v9()
    v10(kept)
    loss_over = v11(grouped)
    v_physics(kept)
    v_container(raw, kept)
    flagged = v_planner(grouped)

    heading("THE CONTROL FIRST -- T3, because rule N gates T1 and T2 on it")
    t3_result = t3(grouped, hashes)

    heading("T1 -- Q1")
    t1_result = t1(grouped, t3_result, hashes, loss_over)

    heading("T2 -- Q2")
    t2_result = t2(grouped, t3_result, hashes, loss_over)

    heading("T4 -- Q3")
    t4_result = t4(grouped, loss_over, flagged, hashes)

    heading("T5 -- Q4")
    t5(t1_result, t3_result, t4_result)

    heading("T6 -- arm S")
    t6(raw)

    predictions(t1_result, t2_result, t4_result)

    heading("HONESTY BOUNDS -- section 11, restated beside the verdicts")
    print(wrap(
        "A null is not a clearance, and a null is not a pass: \"no difference "
        "detected at 1e-9 m\" is not \"identical\", and the resolution is written "
        "beside every agreement above. Every count here is a count over the trials "
        "that ran -- not a rate. Five trials on one machine at one commit is five "
        "trials on one machine at one commit. Nothing here may be cited as "
        "evidence about the physical cell, about `cell_a`, about a pair, or about "
        "any host but the one `../criteria.md` section 9 names."
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
