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

V-PLANNER. The run log is scanned for `planner fallback:` and
`planner fallback declined:` (`scripts/scenario:188-190`). A trial in which
OMPL answered any motion is FLAGGED on the record and reported separately by
`analyse.py`. It is NEVER dropped and never pooled with a Pilz-only trial.
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
    # V2 in arm C's shape: the value is set here and read back off the record
    # of what was set, and `scripts/scenario` prints the seed it used on every
    # run -- which `analyse.py` cross-checks against this field.
    environment["CITE_PHYSICS_SEED"] = str(arguments.seed)

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
    record["wall_duration_s"] = time.time() - record["started_wall"]

    verdicts = [
        match.group(0).strip()
        for match in common.VERDICT_LINE.finditer(log)
        if f"'{common.SCENARIO_NAME}'" in match.group(0)
    ]
    record["verdict_lines"] = verdicts
    record["verdict_line"] = verdicts[-1] if verdicts else None
    ran = common.CYCLE_DONE_MARKER.findall(log)
    record["unittest_summaries"] = ran
    record["seed_line"] = next(
        (line.strip() for line in log.splitlines() if "reaches 'gz sim --seed'" in line),
        None,
    )

    # V-planner, counted rather than judged.
    declined = log.count(common.PLANNER_FALLBACK_DECLINED)
    total = log.count(common.PLANNER_FALLBACK)
    record["planner_fallback_declined_count"] = declined
    # `planner fallback declined:` contains `planner fallback` but not
    # `planner fallback:` -- the colon is what separates them. Counted
    # separately anyway, and both reported, because a prefix that matches two
    # strings is how this repository has miscounted a verdict before.
    record["planner_fallback_count"] = total
    record["ompl_answered_a_motion"] = total > 0

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
