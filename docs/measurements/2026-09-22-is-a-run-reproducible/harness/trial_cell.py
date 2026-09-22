#!/usr/bin/env python3
"""One arm-C trial: the whole cell, one seed, one `pick_and_place` run.

Runs ON THE HOST. `./scripts/scenario` re-executes itself into the container
(`_lib.sh:require_ros_env`), and the reader that holds instrument I1 runs in a
container of its own, so the process that has to see both of them is a host
process. One invocation produces one JSON record (`../criteria.md` section 6).

WHAT IT RUNS. `./scripts/scenario pick_and_place --zone cell_b` with
`CITE_PHYSICS_SEED` set to the campaign's one seed value -- which is what
`scripts/scenario:90` would have defaulted to anyway, set explicitly so that
the record states it rather than inheriting it.

THE CONTAINER TRAP, AND WHY THE ORDER BELOW IS THE ORDER. `_lib.sh`'s
`exec_in_container` uses `compose exec` when the `dev` SERVICE IS ALREADY UP
and `compose run --rm` otherwise, and `docker exec` does not run the image's
entrypoint -- so a command attached to a pre-existing container gets no
`/opt/ros/jazzy/setup.bash` and no overlay. CLAUDE.md section 2 records a whole
`./scripts/test` reading lost to exactly that. Therefore:

  1. the scenario is started FIRST, while `docker ps` is empty (V-container),
     so it takes the `compose run --rm` branch and gets the entrypoint;
  2. the reader is started AFTER, and NOT through `./scripts/enter` -- it calls
     `compose run --rm` directly, so that whatever the scenario's container
     does to `compose ps --services --status running` cannot route the reader
     onto the broken branch either.

THE PTY, AND WHY. `launch_test` is Python writing to whatever
`./scripts/scenario` hands it. Attached to a PIPE its stdout is block-buffered
and the pre-shutdown unittest summary -- the boundary I3 names -- can arrive
after the run is over, which would make the reader's trigger useless.
`exec_in_container` forwards only `CITE_*` and `ROS_DOMAIN_ID`, so
`PYTHONUNBUFFERED` cannot be handed across. A pty can: `docker compose run`
allocates a terminal when its stdin is one, and Python line-buffers to a
terminal. The fallback is a plain pipe, recorded on the record as
`pty` false -- and the reader's registered fallback reading covers it.

V-PLANNER, AND THE REGION THE SCAN IS RESTRICTED TO. The run log is scanned for
the skill server's own `planner fallback:` and `planner fallback declined:`
lines. **`scripts/scenario:189-190` prints both strings itself**, in its pre-run
advice block, so a whole-log count of either returns at least 1 on every run and
would have flagged every arm-C trial. The scan is restricted to the region after
the cell's output starts and requires the emitting logger's prefix; the raw
whole-log counts go onto the record beside the restricted ones so the difference
is visible. `common.planner_counts` holds all of it (P1), with the reasoning and
the CLAUDE.md section 2 precedent beside the patterns. A flagged trial is NEVER
dropped and never pooled with a Pilz-only trial.

V2 FOR ARM C IS NOT AN INDEPENDENT READ-BACK, AND THE RECORD SAYS SO. The seed
is handed across as `CITE_PHYSICS_SEED` and `scripts/scenario:186` prints the
value it used -- but `common.SEED_A` is `scripts/scenario:90`'s OWN default, so
that line reads `Seed 20260824 ...` whether or not the variable crossed the
boundary. There is no cheap independent source on this side, and a field that
looks like a passed check when nothing was checked is worse than an absent one,
so the record carries `seed_readback_is_independent: false` and the reason.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import pty
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

#: Printed by `scripts/scenario:171` once it is inside the container and about
#: to run `launch_test`. Waiting on it is how this trial knows the scenario has
#: claimed its container before the reader asks for one.
ENTERED_MARKER = re.compile(r"Running scenario '[a-z_]+' against zone")

#: Where the campaign lives inside the container.
IN_CONTAINER = "/workspace/docs/measurements/2026-09-22-is-a-run-reproducible"

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def start_reader(log_in_container: str, out_in_container: str) -> subprocess.Popen:
    """Start `read_workpiece.py` in its OWN fresh container.

    `compose run --rm` explicitly, through `_lib.sh`'s own `compose` function so
    that the project name and the compose file are derived once (P1) -- and read
    UNDER BASH by absolute path, because `_lib.sh` computes `REPO_ROOT` from
    `${BASH_SOURCE[0]}`, which no other shell sets. The
    `2026-09-04-following-error` campaign's `run_campaign.sh` records what a
    wrongly derived project name costs; this is the same guard.
    """
    inner = (
        f"python3 {IN_CONTAINER}/harness/read_workpiece.py "
        f"--zone {common.ZONE} --log {log_in_container} --out {out_in_container}"
    )
    script = (
        f'. "{common.REPO_ROOT}/scripts/_lib.sh" >/dev/null 2>&1; '
        f'compose run --rm -T dev bash -lc {shell_quote(inner)}'
    )
    return subprocess.Popen(
        ["bash", "-c", script],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )


def shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def in_container_path(host_path: Path) -> str:
    """The same file as the container sees it. `../..:/workspace` in compose."""
    return "/workspace/" + str(host_path.resolve().relative_to(common.REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--seed", type=int, default=common.SEED_A)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default=None)
    parser.add_argument("--ceiling", type=float, default=common.CELL_CEILING_S)
    arguments = parser.parse_args()

    out_dir = Path(arguments.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = arguments.label or common.label_for("C", arguments.index)
    record_path = out_dir / f"{label}.json"
    if record_path.exists():
        print(f"{label}: skipped, {record_path} exists", flush=True)
        return 0

    console_path = out_dir / f"{label}.console"
    reader_path = out_dir / f"{label}.reader.json"

    record: dict = {
        "campaign": "2026-09-22-is-a-run-reproducible",
        "label": label,
        "arm": "C",
        "trial_index": arguments.index,
        "seed_requested": arguments.seed,
        "zone": common.ZONE,
        "scenario": common.SCENARIO_NAME,
        "git_open": common.git_snapshot(),
        "load_open": common.load_average(),
        "host": common.host_facts(),
        "docker_ps_open": common.docker_ps(),
        "console": str(console_path),
        "started_wall": time.time(),
        "instrument_loss": False,
        "instrument_loss_reason": None,
    }

    def seal(code: int) -> int:
        record["git_close"] = common.git_snapshot()
        record["load_close"] = common.load_average()
        record["docker_ps_close"] = common.docker_ps()
        record["ended_wall"] = time.time()
        record["exit_code"] = code
        common.write_record(record_path, record)
        print(
            f"{label}: verdict={record.get('verdict_line')!r} "
            f"i3={record.get('i3_position')} "
            f"ompl={record.get('planner_fallback_count')}",
            flush=True,
        )
        return code

    argv = [
        str(common.REPO_ROOT / "scripts" / "scenario"),
        common.SCENARIO_NAME,
        "--zone", common.ZONE,
    ]
    record["argv"] = argv
    environment = dict(os.environ)
    environment["CITE_PHYSICS_SEED"] = str(arguments.seed)
    # V2 in arm C's shape, stated as what it is. `scripts/scenario:186` prints
    # the seed it used, and `analyse.py` checks the requested value appears in
    # that line -- but `common.SEED_A` IS `scripts/scenario:90`'s own default,
    # so the printed line is identical whether or not this variable crossed the
    # container boundary. That check can therefore only ever confirm, which is
    # the thing `../criteria.md` section 10 opens by forbidding. The probe arms
    # read their seed back off `/proc/<pid>/cmdline`; there is no equivalently
    # cheap independent source here, so this is RECORDED rather than dressed up.
    record["seed_readback_is_independent"] = False
    record["seed_readback_note"] = (
        "arm C's seed read-back is not independent: CITE_PHYSICS_SEED is set to "
        "the same value `scripts/scenario:90` defaults to, so the printed seed "
        "line agrees whether or not the variable crossed the container boundary. "
        "No conclusion may be drawn from its agreement."
    )

    console = console_path.open("w")
    try:
        master, slave = pty.openpty()
        record["pty"] = True
    except OSError as exc:
        master = slave = -1
        record["pty"] = False
        record["pty_error"] = f"{type(exc).__name__}: {exc}"

    if record["pty"]:
        scenario = subprocess.Popen(
            argv, stdin=slave, stdout=slave, stderr=slave,
            env=environment, start_new_session=True,
        )
        os.close(slave)
        source = os.fdopen(master, "rb", buffering=0)
    else:
        scenario = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=environment, start_new_session=True, bufsize=0,
        )
        source = scenario.stdout  # type: ignore[assignment]

    record["scenario_pid"] = scenario.pid
    entered = threading.Event()

    def pump() -> None:
        """Copy the scenario's output into the console log, flushing each read.

        Flushed per read and not per line: the reader in the other container is
        tailing this file, and an unflushed buffer here would reintroduce
        exactly the delay the pty was opened to remove.

        The entry marker is searched over a running buffer rather than by
        re-reading the file, which would be quadratic in the length of a run
        that can print tens of thousands of lines.
        """
        seen = ""
        while True:
            try:
                chunk = source.read(4096)
            except OSError as exc:
                # A pty master reads EIO when the last slave closes. That is
                # the end of the stream, not a fault.
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            try:
                console.write(text)
                console.flush()
            except ValueError:
                # The main thread closed the log because this thread's join
                # timed out while it was blocked in `read`. One more chunk
                # arriving after that is the end of the run, not a fault, and
                # an unhandled exception on a daemon thread would print a
                # traceback that reads like a failure of the trial.
                break
            if not entered.is_set():
                seen = (seen + ANSI.sub("", text))[-8192:]
                if ENTERED_MARKER.search(seen):
                    entered.set()

    pumping = threading.Thread(target=pump, daemon=True)
    pumping.start()

    reader: subprocess.Popen | None = None
    try:
        # The reader is started on the EVENT of the scenario having entered its
        # container, not after an interval (P4). If the scenario dies first,
        # there is nothing to read beside.
        deadline = time.monotonic() + arguments.ceiling
        while not entered.is_set():
            if scenario.poll() is not None:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    f"the scenario exited with {scenario.poll()} before it announced "
                    "that it was running; nothing was ever read beside it"
                )
                break
            if time.monotonic() > deadline:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    f"the scenario did not announce a run within {arguments.ceiling:g} s"
                )
                break
            time.sleep(0.25)

        if entered.is_set():
            record["reader_started_wall"] = time.time()
            reader = start_reader(
                in_container_path(console_path), in_container_path(reader_path)
            )

        while scenario.poll() is None and time.monotonic() < deadline:
            time.sleep(0.5)
        if scenario.poll() is None:
            record["instrument_loss"] = True
            record["instrument_loss_reason"] = (
                f"the scenario had not returned after {arguments.ceiling:g} s"
            )
            try:
                os.killpg(scenario.pid, signal.SIGINT)
                scenario.wait(timeout=common.STOP_GRACE_S)
            except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
                try:
                    os.killpg(scenario.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        record["scenario_exit_status"] = scenario.poll()
    finally:
        pumping.join(timeout=30.0)
        console.close()
        if reader is not None:
            # The reader ends itself on the scenario's verdict line; this is the
            # bound on that, not the mechanism for it.
            try:
                reader.wait(timeout=60.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(reader.pid, signal.SIGTERM)
                    reader.wait(timeout=60.0)
                except (subprocess.TimeoutExpired, ProcessLookupError, PermissionError):
                    try:
                        os.killpg(reader.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
            record["reader_exit_status"] = reader.poll()
            record["reader_stdout"] = (reader.stdout.read() if reader.stdout else "")[-4000:]

    # ---- I3, from the reader's own record ---------------------------------
    if reader_path.exists():
        reading = json.loads(reader_path.read_text())
        record["reader"] = reading
        record["i3_position"] = reading.get("i3_position")
        record["i3_source"] = reading.get("i3_source")
        record["triggered_position"] = reading.get("triggered_position")
        record["last_seen_position"] = reading.get("last_seen_position")
        record["triggered_vs_last_max_delta_m"] = reading.get("triggered_vs_last_max_delta_m")
        record["fallback_tail"] = reading.get("fallback_tail")
        # V3 for arm C, lifted onto the trial record so that `analyse.py` reads
        # one shape per row rather than reaching into the reader's own file.
        record["installed_world_sha256"] = reading.get("installed_world_sha256")
        record["plan_world_sha256"] = reading.get("plan_world_sha256")
        record["world_paths_agree"] = reading.get("world_paths_agree")
        record["reader_verdict_line"] = reading.get("verdict_line")
        if reading.get("instrument_loss"):
            record["instrument_loss"] = True
            record["instrument_loss_reason"] = (
                (record["instrument_loss_reason"] or "")
                + f"; reader: {reading.get('instrument_loss_reason')}"
            ).lstrip("; ")
    else:
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = (
            (record["instrument_loss_reason"] or "")
            + "; the reader wrote no record, so I1 was never read beside this run"
        ).lstrip("; ")

    # ---- I3's other three fields, from the log ----------------------------
    log = ANSI.sub("", console_path.read_text(errors="replace"))
    # THE HARNESS'S OWN WALL CLOCK, AND IT IS NOT WHAT T4 QUOTES. It is taken
    # after the `finally` block above, which waits on the reader with two 60 s
    # bounds of its own, so it carries up to about two minutes of the rig's
    # teardown. It stays on the record as a separate field; the duration T4
    # quotes is `scenario_cycle_seconds` below, which the scenario measured.
    record["wall_duration_s"] = time.time() - record["started_wall"]

    verdicts, verdict_line = common.terminal_verdict(log)
    record["verdict_lines"] = verdicts
    record["verdict_line"] = verdict_line
    # The reader reads the same file for the same string; if the two disagree,
    # one of them was looking at a truncated log and the row says so rather than
    # carrying two answers to one question.
    record["verdict_lines_agree"] = (
        record.get("reader_verdict_line") is None
        or record["reader_verdict_line"] == verdict_line
    )
    ran = common.CYCLE_DONE_MARKER.findall(log)
    record["unittest_summaries"] = ran
    # The scenario's OWN duration. `launch_test` prints one summary for
    # the pre-shutdown tests and one for the post-shutdown tests; the first is
    # the boundary I3 names and is the leg T4 compares, so it is the one quoted.
    seconds = [float(value) for value in common.CYCLE_DONE_SECONDS.findall(log)]
    record["scenario_reported_seconds"] = seconds
    record["scenario_cycle_seconds"] = seconds[0] if seconds else None
    record["seed_line"] = next(
        (line.strip() for line in log.splitlines() if "reaches 'gz sim --seed'" in line),
        None,
    )

    # V-planner, counted rather than judged, and counted over the region the
    # CELL wrote rather than over the whole console -- `scripts/scenario` prints
    # both marker strings itself. See `common.planner_counts`.
    record.update(common.planner_counts(log))
    record["ompl_answered_a_motion"] = record["planner_fallback_count"] > 0

    if record["verdict_line"] is None:
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = (
            (record["instrument_loss_reason"] or "")
            + "; the scenario printed no verdict line (section 5.3)"
        ).lstrip("; ")

    record["verdict"] = "INSTRUMENT_LOSS" if record["instrument_loss"] else "COLLECTED"
    return seal(0 if not record["instrument_loss"] else 5)


if __name__ == "__main__":
    sys.exit(main())
