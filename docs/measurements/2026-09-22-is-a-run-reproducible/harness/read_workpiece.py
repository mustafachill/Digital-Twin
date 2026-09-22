#!/usr/bin/env python3
"""Arm C's instrument: where the work-piece is, read by I1, beside a running cell.

Runs INSIDE the container, in its OWN container, alongside the one
`./scripts/scenario` re-executed itself into. It is started by `trial_cell.py`
and it writes one JSON file, which that trial's record absorbs.

WHY A SECOND PROCESS AT ALL. `../criteria.md` I3 asks for "the work-piece's
position by I1 after the scenario's cycle assertions have passed and before
teardown". `tests/scenarios/pick_and_place.py` reads that position with
`gz model -m ... -p` and prints it only inside a FAILURE message, so a passing
run states it nowhere; and the scenario is frozen tree that this campaign may
not touch (`../criteria.md` section 0). The only door left is to hold the same
subscription `continuous_line.py:882` holds -- `cite_bringup.gz.ModelPoses`,
which is instrument I1 -- from beside the run.

**THE SAME INSTRUMENT AS ARMS A/B/A', WHICH IS THE POINT.** Q4 is answerable
only as the difference between two arms (`../criteria.md` section 1), and a
difference measured with two different instruments is a difference between the
instruments. `gz model -p` prints six decimal places; `ModelPoses` parses
protobuf doubles.

HOW IT KNOWS WHEN. It tails the scenario's own console log, which
`trial_cell.py` writes on the host through a pty so that the launch_test
output is line-buffered rather than arriving in one block at exit. Two events
matter and both are read from that file rather than waited out:

  - `Ran N tests in X s` -- `launch_test` prints the PRE-SHUTDOWN unittest
    summary before it shuts the launch down, so this is the boundary I3 names.
  - `Scenario '<name>' ...` -- `scripts/scenario`'s own verdict, after which
    there is nothing left to read.

WHAT IT RECORDS, and this is registered here BEFORE any trial so that no
reading is chosen after the data:

  - `triggered_position`: I1 at the moment the cycle-done marker was seen, with
    the model still in the world.
  - `last_seen_position`: the last non-None sample of the whole run.
  - `i3_position`: `triggered_position` when it exists, otherwise
    `last_seen_position`, with `i3_source` saying which. The fallback is
    registered rather than discovered because the marker can be missed for a
    reason that has nothing to do with the cell -- a buffered pipe -- and
    because `station_cycle.xml` commands no belt, so the part is at rest on a
    stationary conveyor from the `PlaceAt` until teardown. `analyse.py` prints
    the distance between the two readings for every trial, so a trial where
    that assumption failed is visible rather than assumed away.
  - `fallback_tail`: the spread of the trailing samples, recorded ONLY on the
    rows that took the fallback -- because those are exactly the rows on which
    `triggered_vs_last_max_delta_m` is `None` and the at-rest assumption above
    is therefore checked by nothing else.
  - `installed_world_sha256` and `plan_world_sha256`: V3 for arm C. Two trials
    with different world hashes are not comparable and are not compared, and
    T4 is the comparison V3 was written for.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import sys
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

_STOP = {"now": False}

#: How many trailing samples the at-rest cross-check spreads over when the
#: REGISTERED FALLBACK reading is used. UNSETTLED BY CRITERIA, and it enters no
#: rule: it is a reported number.
#:
#: Why it exists. `triggered_vs_last_max_delta_m` is the distance between the
#: two readings, and it is `None` in exactly the case the fallback was taken --
#: there is no triggered reading to difference. So the one trial where the "the
#: part is at rest from the `PlaceAt` until teardown" assumption most needs
#: checking is the one where nothing checked it. This spreads the last N
#: samples instead, so the assumption is MEASURED on that row rather than
#: asserted. At `CELL_SAMPLE_PERIOD_S` of 0.5 s, ten samples is about 5 s.
FALLBACK_SPREAD_SAMPLES = 10


def max_coordinate_spread(positions: list[list[float]]) -> float | None:
    """The largest |delta| over every coordinate of every pair. Never rounded."""
    worst = None
    for index, first in enumerate(positions):
        for second in positions[index + 1:]:
            for a, b in zip(first, second, strict=True):
                delta = abs(a - b)
                worst = delta if worst is None else max(worst, delta)
    return worst


def _stop(_signum: int, _frame: object) -> None:
    _STOP["now"] = True


def world_name(world: Path) -> str:
    """The `<world name=...>` of a generated world. Plain XML; no simulator."""
    root = ElementTree.parse(world).getroot()
    element = root.find("world")
    if element is None or not element.get("name"):
        raise RuntimeError(f"{world} declares no named <world>")
    return str(element.get("name"))


def workpiece_name(world: Path) -> str:
    """The one model name the belts carry AND the beams watch.

    Reused from `tests/scenarios/_cell.py:carried_models` rather than copied:
    it is repository source, not another campaign's frozen harness, and the
    derivation is the one the scenario itself uses to name the part it spawns.
    """
    sys.path.insert(0, str(common.REPO_ROOT / "tests" / "scenarios"))
    from _cell import carried_models  # noqa: PLC0415

    names = sorted(carried_models(world))
    if len(names) != 1:
        raise RuntimeError(
            f"{world} declares {names} as both carried and watched; arm C reads one part "
            "and this rig does not choose between several"
        )
    return names[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", default=common.ZONE)
    parser.add_argument("--log", required=True, help="the scenario console log to tail")
    parser.add_argument("--out", required=True, help="where to write this reader's JSON")
    parser.add_argument("--ceiling", type=float, default=common.CELL_CEILING_S)
    arguments = parser.parse_args()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    record: dict = {
        "zone": arguments.zone,
        "log": arguments.log,
        "started_wall": time.time(),
        # I4's `gz sim --help` and `uname -m` fields, read HERE rather than on
        # the host side of this trial: the host has no `gz`, and the question
        # I4 asks is about the environment the simulator ran in.
        "container_host_facts": common.host_facts(),
        "instrument_loss": False,
        "instrument_loss_reason": None,
    }

    def seal(code: int) -> int:
        record["ended_wall"] = time.time()
        common.write_record(Path(arguments.out), record)
        return code

    gz = common.import_gz()
    plan = gz.plan_for(arguments.zone)
    world = Path(plan.world)
    record["world_file"] = str(world)

    # ---- V3, arm C's half --------------------------------------------------
    # "Each trial records the SHA-256 of the world file it launched. Two trials
    # with different world hashes are not comparable and are not compared." No
    # arm-C record carried a hash at all until this was added, so V3 skipped the
    # arm and T4 -- the comparison V3 was written for -- had no hash guard where
    # T1 and T2 both have one.
    #
    # BOTH PATHS ARE HASHED AND COMPARED. `installed_world_path` asks
    # `ros2 pkg prefix cite_generated` the question V-physics asks of the probe
    # arms, and `plan.world` is what the launch actually hands `gz sim`. They
    # should be the same file; recording one and assuming the other is how this
    # repository has published figures from a build that was not the build being
    # described.
    try:
        installed = common.installed_world_path(arguments.zone)
        record["installed_world_path"] = str(installed)
        record["installed_world_sha256"] = common.sha256_text(installed.read_text())
    except Exception as exc:  # noqa: BLE001 - provenance, reported not raised
        record["installed_world_path"] = None
        record["installed_world_sha256"] = None
        record["installed_world_error"] = f"{type(exc).__name__}: {exc}"
    try:
        record["plan_world_sha256"] = common.sha256_text(world.read_text())
    except OSError as exc:
        record["plan_world_sha256"] = None
        record["plan_world_error"] = f"{type(exc).__name__}: {exc}"
    record["world_paths_agree"] = bool(
        record.get("installed_world_sha256")
        and record["installed_world_sha256"] == record.get("plan_world_sha256")
    )

    try:
        record["world"] = world_name(world)
        record["workpiece"] = workpiece_name(world)
    except Exception as exc:  # noqa: BLE001 - an instrument that could not be aimed
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = f"could not name the world or the part: {exc}"
        return seal(2)

    try:
        poses = gz.ModelPoses(zone=arguments.zone, world=record["world"])
    except Exception as exc:  # noqa: BLE001
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = f"ModelPoses did not subscribe: {exc}"
        return seal(3)
    record["pose_topic"] = poses.topic
    record["gz_partition"] = gz.gz_environment(plan)["GZ_PARTITION"]

    samples: list[dict] = []
    triggered: dict | None = None
    verdict_lines: list[str] = []
    terminal_verdict: str | None = None
    log_path = Path(arguments.log)
    consumed = 0
    # A LINE SPLIT ACROSS TWO POLLS IS CARRIED, NOT DROPPED. `read()` returns
    # whatever the writer has flushed, which ends mid-line as often as not, and
    # `tell()` then advances past that fragment -- so a marker straddling a poll
    # boundary was consumed as two halves and matched by neither. The host-side
    # pump in `trial_cell.py` already keeps a running buffer for exactly this
    # reason; this is the same guard on the reading side. The fragment is held
    # here and prepended to the next read.
    pending = ""
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    deadline = time.monotonic() + arguments.ceiling

    try:
        while True:
            now = time.time()
            position = poses.position(record["workpiece"])
            if position is not None:
                samples.append({"wall": now, "position": list(position)})

            # The log, read incrementally. It is written by the host side of
            # this trial and shared through the /workspace mount.
            if log_path.exists():
                with log_path.open("r", errors="replace") as handle:
                    handle.seek(consumed)
                    fresh = handle.read()
                    consumed = handle.tell()
                chunks = (pending + fresh).split("\n")
                pending = chunks.pop()
                for raw in chunks:
                    line = ansi.sub("", raw).rstrip("\r")
                    if triggered is None and common.CYCLE_DONE_MARKER.search(line):
                        # I3's boundary, taken as an EVENT the moment it is
                        # read, not at the next poll.
                        at = poses.position(record["workpiece"])
                        triggered = {
                            "wall": time.time(),
                            "position": list(at) if at is not None else None,
                            "marker_line": line.strip(),
                        }
                    match = common.VERDICT_LINE.search(line)
                    if match and f"'{common.SCENARIO_NAME}'" in match.group(0):
                        seen = match.group(0).strip()
                        verdict_lines.append(seen)
                        # ONLY A TERMINAL VERDICT ENDS THE READ, and the LAST
                        # one is the verdict of record -- which is what
                        # `trial_cell.py` takes. This used to break on the FIRST
                        # line of verdict SHAPE, and on the advisory branch that
                        # is `scripts/scenario:220`'s warning rather than the
                        # verdict: the two records then carried two different
                        # strings for the same field.
                        if common.VERDICT_TERMINAL.fullmatch(seen):
                            terminal_verdict = seen

            if terminal_verdict is not None:
                break
            if _STOP["now"]:
                record["stopped_by_signal"] = True
                break
            if time.monotonic() > deadline:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    f"the reader's {arguments.ceiling:g} s ceiling expired with no "
                    "scenario verdict in the log"
                )
                break
            time.sleep(common.CELL_SAMPLE_PERIOD_S)
    finally:
        poses.close()

    record["samples"] = samples
    record["n_samples"] = len(samples)
    record["verdict_lines"] = verdict_lines
    record["verdict_line"] = terminal_verdict or (
        verdict_lines[-1] if verdict_lines else None
    )
    record["verdict_is_terminal"] = terminal_verdict is not None
    record["triggered"] = triggered
    record["triggered_position"] = (triggered or {}).get("position")
    last = samples[-1] if samples else None
    record["last_seen_position"] = last["position"] if last else None
    record["last_seen_wall"] = last["wall"] if last else None

    if record["triggered_position"] is not None:
        record["i3_position"] = record["triggered_position"]
        record["i3_source"] = "triggered"
    elif record["last_seen_position"] is not None:
        record["i3_position"] = record["last_seen_position"]
        record["i3_source"] = "last_seen"
    else:
        record["i3_position"] = None
        record["i3_source"] = None
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = (
            (record["instrument_loss_reason"] or "")
            + "; I1 returned no position for the work-piece at any point in the run"
        ).lstrip("; ")

    record["triggered_vs_last_max_delta_m"] = None
    record["fallback_tail"] = None
    if record["triggered_position"] and record["last_seen_position"]:
        record["triggered_vs_last_max_delta_m"] = max(
            abs(a - b)
            for a, b in zip(
                record["triggered_position"], record["last_seen_position"], strict=True
            )
        )
    elif samples:
        # THE ASSUMPTION IS CHECKED HERE OR NOWHERE. The registered fallback
        # rests on `station_cycle.xml` commanding no belt, so the part is at
        # rest from the `PlaceAt` until teardown -- and the number that would
        # have shown otherwise, the triggered-against-last distance, does not
        # exist on exactly the rows that took the fallback. The spread of the
        # trailing samples stands in for it. It is REPORTED and enters no rule.
        tail = samples[-FALLBACK_SPREAD_SAMPLES:]
        record["fallback_tail"] = {
            "n_samples": len(tail),
            "wall_span_s": (tail[-1]["wall"] - tail[0]["wall"]) if len(tail) > 1 else None,
            "max_coordinate_spread_m": max_coordinate_spread(
                [sample["position"] for sample in tail]
            ),
            "requested_samples": FALLBACK_SPREAD_SAMPLES,
        }

    print(json.dumps({k: record[k] for k in ("i3_position", "i3_source", "n_samples")}))
    return seal(0)


if __name__ == "__main__":
    sys.exit(main())
