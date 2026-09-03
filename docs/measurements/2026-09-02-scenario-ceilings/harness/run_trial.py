#!/usr/bin/env python3
"""One run: capture the console, hold the allocation, and record what was true at both ends.

DERIVED FROM the FROZEN 2026-08-29 harness, copied at commit `4e4313b`:
`run_trial.sh` for the "record the host state, run, clean up, record again" shape and the
survivor check, and `cpu_limit_trial.sh` for the `docker update --cpus` mechanism and the
`docker ps --filter` that finds the container. Neither original is edited
(`docs/measurements/README.md`, rule 2).

TWO DELIBERATE DEPARTURES FROM THE ORIGINALS, both registered in `criteria.md`:

  1. The compose project name is DERIVED from `cite_project_name` in `scripts/_lib.sh`
     rather than hard-coded. That harness's own README records that all three of its CPU
     scripts hard-code one checkout's name and therefore find nothing from another.
     Section 4.4.
  2. THE LIMIT IS APPLIED FOR THE WHOLE RUN, INCLUDING BRING-UP. `cpu_limit_trial.sh`
     squeezes AFTER bring-up on purpose -- its quantity of interest is the steady-state
     step cost. Here bring-up is one of the intervals under measurement, so the limit goes
     on as soon as the container exists, the delay is recorded, and V6 discards a run
     whose delay exceeds ten seconds.

WHY THIS RUNS ON THE HOST AND NOT IN THE CONTAINER. `docker update` and `docker inspect`
are host-side, I5 and I6 are host-side, and `criteria.md` I3 requires the campaign to
capture its own console -- `scripts/scenario` passes `--junit-xml` and nothing else, and
`launch_testing`'s junit writer emits no `system-out`. A trial whose output was not
redirected has produced nothing (rule P).

WHAT IT DOES NOT DO. It computes no margin and applies no band; it records. Every rule in
`criteria.md` section 7 lives in `analyse.py`.

    docs/measurements/2026-09-02-scenario-ceilings/harness/run_trial.py \
        --label FULL_bringup_1 --condition FULL --scenario bringup
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import common

#: How long the watcher looks for the container before giving up. It is not a sequencing
#: sleep (P4): nothing waits on it, the run proceeds either way, and a watcher that never
#: found a container leaves that fact on the record for V6 and V2 to spend.
CONTAINER_SEARCH_CEILING_S = 300.0

#: How long the watcher keeps asking the running cell for I7 before recording that it
#: could not. Bring-up under `--cpus 1` is the slow case this has to survive; a reading
#: that never arrived is recorded as never arrived and V2 then discards the run.
CONFIGURATION_READ_CEILING_S = 900.0

#: Between two polls of the CONTAINER SEARCH. A poll interval, not a settling time. It is
#: cheap: one `docker ps` on the host, touching nothing inside the cgroup.
POLL_S = 2.0

#: Between two attempts at I7, and DELIBERATELY MUCH LARGER THAN `POLL_S`.
#:
#: THE READING PERTURBS THE INTERVAL IT MEASURES. Each attempt runs
#: `docker exec ... bash -lc '. setup.bash; . install/setup.bash; ros2 param get ...'`
#: INSIDE THE CGROUP UNDER MEASUREMENT: two `setup.bash` chains over a 23-package
#: workspace and a full `rclpy` node, every two seconds. At FULL that is noise. At C1 it
#: is a substantial fraction of the entire one-CPU budget, spent DURING COLD BRING-UP --
#: which is the headline interval for two `BRING_UP_CEILING_S` cells and for rule A's
#: single `bringup` record, and Q-B is the half of #30 this campaign exists to answer.
#: The reading only has to succeed ONCE and `CONFIGURATION_READ_CEILING_S` is 900 s, so
#: there is no reason for it to be frequent.
CONFIGURATION_POLL_S = 30.0

#: How long the watcher waits for the scenario's OWN first milestone before reading I7
#: anyway. NOT a settling time and not a sequencing sleep (P4): the wait ends on an EVENT
#: -- the first `CITE_TIMING` line the scenario prints, which means a wait completed and
#: therefore that the stack the reading needs is up -- and this is only the bound on how
#: long that event is waited for. It is bounded rather than unbounded so that V2 still
#: FAILS CLOSED: a run whose cell never comes up emits no milestone, and the reading has
#: to be attempted and recorded as failed rather than skipped, because a missing reading
#: and a failed one must not be the same record.
CONFIGURATION_GATE_CEILING_S = 300.0

#: How often I4 is re-read WHILE the run is live. It has to be re-read at all because
#: `scripts/_lib.sh` starts the scenario with `compose run --rm`, so the container is
#: REMOVED the instant `./scripts/scenario` exits and every `docker` call after that reads
#: "No such container". The shakedown found this: I4's second reading and V6's
#: end-of-run confirmation are both structurally unobtainable after the fact. So the
#: watcher samples throughout and keeps the LAST reading it got, with how long before the
#: exit it was taken; the failed post-exit attempt is recorded beside it rather than
#: hidden, so the record cannot be mistaken for one taken after the process ended.
I4_SAMPLE_PERIOD_S = 10.0


class Watcher(threading.Thread):
    """Applies the allocation, then reads I4 and I7 off the running cell.

    A THREAD RATHER THAN A SEQUENCE, because both readings have to be taken WHILE the
    scenario runs and the scenario is what this process is waiting on. It touches nothing
    the scenario owns: it reads `docker`, it applies one `docker update`, and it writes
    into its own dictionary.
    """

    def __init__(self, project: str, condition: str) -> None:
        super().__init__(daemon=True)
        self.project = project
        self.condition = condition
        self.cpus = common.CONDITIONS[condition]
        self.found: dict = {
            "container_id": "",
            "container_started_at": "",
            "container_seen_at": None,
            "limit_applied_at": None,
            "limit_delay_s": None,
            "limit_command": None,
            "cpu_after_apply": None,
            "cpu_last_live": None,
            "cpu_last_live_at": None,
            "cpu_samples": 0,
            "container_env": None,
            "configuration": None,
            "configuration_gate": None,
        }
        # `_halt` and NOT `_stop`. `threading.Thread._stop` is an INTERNAL METHOD that
        # `join()` and `is_alive()` call through `_wait_for_tstate_lock`, so an attribute
        # of that name shadows it and `watcher.join()` raises
        # `TypeError: 'Event' object is not callable`. Nothing here joins today and the
        # thread is a daemon, so it is inert -- which is exactly why it is renamed now,
        # before this rig is frozen, rather than left as a trap for whoever next adds a
        # join to it.
        self._halt = threading.Event()
        # Set by the console reader on the scenario's first `CITE_TIMING` line. The I7
        # readback waits on it rather than starting from container start, so that the
        # `ros2 param get` does not compete with cold bring-up for the one CPU C1 gives
        # the whole cell.
        self._first_record = threading.Event()

    def stop(self) -> None:
        self._halt.set()

    def note_first_record(self) -> None:
        """One `CITE_TIMING` line has been seen on the scenario's console."""
        self._first_record.set()

    def run(self) -> None:  # pragma: no cover - exercised by the shakedown, not by pytest
        deadline = time.time() + CONTAINER_SEARCH_CEILING_S
        cid = ""
        while time.time() < deadline and not self._halt.is_set():
            cid = common.find_container(self.project)
            if cid:
                break
            time.sleep(POLL_S)
        if not cid:
            return
        self.found["container_id"] = cid
        self.found["container_seen_at"] = time.time()
        started = common.container_started_at(cid)
        self.found["container_started_at"] = started

        if self.cpus is not None:
            # V6's delay is measured from the container's OWN start time, not from when
            # this loop happened to notice it. The two differ by the poll interval and by
            # however long `docker ps` took, and V6 is a statement about how much of
            # bring-up ran unconstrained.
            applied = common.CONDITIONS[self.condition]
            result = subprocess.run(
                ["docker", "update", "--cpus", str(applied), cid],
                capture_output=True,
                text=True,
            )
            now = time.time()
            self.found["limit_applied_at"] = now
            self.found["limit_command"] = {
                "argv": f"docker update --cpus {applied} {cid}",
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            }
            self.found["limit_delay_s"] = _delay_since(started, now)
        # I4 immediately after application -- and at FULL too, because "no limit was
        # applied" is a reading that has to be taken rather than assumed.
        self.found["cpu_after_apply"] = common.cpu_allocation(cid)
        self._sample_cpu(cid)

        # Section 5: the CITE_ variables IN FORCE, read from the process that actually
        # ran rather than from this shell. `scripts/_lib.sh` forwards every CITE_-prefixed
        # host variable into the container AND `scripts/scenario` exports its own default
        # seed after the host has been read, so the host environment is not the authority
        # on either. The shakedown recorded a null seed for exactly that reason.
        self.found["container_env"] = _container_cite_env(cid)

        # THE GATE. Wait for the scenario's own first milestone before asking the cell
        # anything: by then a wait has completed, so the node I7 reads from is up and the
        # first attempt normally succeeds outright. I4 keeps sampling throughout -- a
        # `docker exec cat` of one cgroup file, which is not what costs anything here.
        gate_started = time.time()
        gate_deadline = gate_started + CONFIGURATION_GATE_CEILING_S
        while (
            not self._first_record.is_set()
            and not self._halt.is_set()
            and time.time() < gate_deadline
        ):
            self._sample_cpu(cid)
            self._first_record.wait(I4_SAMPLE_PERIOD_S)
        self.found["configuration_gate"] = {
            "first_record_seen": self._first_record.is_set(),
            "waited_s": round(time.time() - gate_started, 3),
            "gate_ceiling_s": CONFIGURATION_GATE_CEILING_S,
            "poll_period_s": CONFIGURATION_POLL_S,
            "note": (
                "I7 is read after the scenario's first CITE_TIMING line, not from "
                "container start, because the reading runs inside the cgroup under "
                "measurement. If first_record_seen is false the gate expired and the "
                "reading was attempted anyway, so V2 still fails closed."
            ),
        }

        deadline = time.time() + CONFIGURATION_READ_CEILING_S
        while time.time() < deadline and not self._halt.is_set():
            configuration = common.running_configuration(cid)
            self.found["configuration"] = configuration
            if configuration["description_read_ok"] and configuration["world_read_ok"]:
                break
            self._sample_cpu(cid)
            # `self._halt.wait`, not `time.sleep`: at a 30 s period a sleeping watcher
            # would outlive the run it is watching by up to half a minute.
            self._halt.wait(CONFIGURATION_POLL_S)

        # Keep sampling I4 until the run ends. The last successful sample is what I4's
        # "again at the end of the run" and V6's end-of-run confirmation can mean here,
        # and the record says how long before the exit it was taken so that a reader can
        # judge it rather than take it on trust.
        while not self._halt.is_set():
            self._sample_cpu(cid)
            self._halt.wait(I4_SAMPLE_PERIOD_S)

    def _sample_cpu(self, cid: str) -> None:
        """One I4 reading, kept only if it actually read something.

        A reading that came back as a `docker` error is NOT stored as the last live one:
        that is how "the container is gone" would otherwise be recorded as "the limit was
        not in force", which is a different and much worse claim.
        """
        reading = common.cpu_allocation(cid)
        self.found["cpu_samples"] += 1
        if not reading["cgroup_cpu_max_inside"].startswith("<"):
            self.found["cpu_last_live"] = reading
            self.found["cpu_last_live_at"] = reading["read_at"]


def _container_cite_env(cid: str) -> dict:
    """Every `CITE_`-prefixed variable in the container that ran the scenario."""
    out = subprocess.run(
        ["docker", "exec", cid, "env"], capture_output=True, text=True, timeout=60
    )
    if out.returncode != 0:
        return {"read_ok": False, "error": out.stderr.strip()}
    values = {}
    for line in out.stdout.splitlines():
        name, _, value = line.partition("=")
        if name.startswith("CITE_") or name == "ROS_DOMAIN_ID":
            values[name] = value
    return {"read_ok": True, **values}


#: `docker inspect` reports RFC 3339 with NANOSECOND precision, which `datetime` will not
#: parse: it accepts three or six fractional digits and nothing else. The fraction is cut
#: to six digits before parsing rather than the whole string being re-formatted, so the
#: zone offset survives untouched.
_RFC3339 = re.compile(r"^(?P<stamp>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(?P<fraction>\d+))?"
                      r"(?P<zone>Z|[+-]\d\d:?\d\d)?$")


def _delay_since(started_at: str, now: float) -> float | None:
    """Seconds between the container's start and a wall-clock instant.

    V6 measures its delay from the container's OWN start time, not from when the watcher
    noticed it. A value that cannot be parsed returns `None`, which V6 treats as NOT
    ESTABLISHED and never as "within the ceiling" -- an unparsed timestamp must not buy a
    run its validity.
    """
    match = _RFC3339.match(started_at.strip())
    if match is None:
        return None
    fraction = (match.group("fraction") or "0")[:6].ljust(6, "0")
    zone = match.group("zone") or "Z"
    text = f"{match.group('stamp')}.{fraction}{'+00:00' if zone == 'Z' else zone}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return now - parsed.timestamp()


def run(label: str, condition: str, scenario: str, out: Path) -> int:
    root = common.repo_root()
    writer = common.RunWriter(out, label)
    isolation = common.isolation(root)
    project = isolation["compose_project_name"]

    before_survivors = common.survivors()
    start_snapshot = common.snapshot(root)
    load_before = common.host_load()

    print(f"[trial] {label} condition={condition} scenario={scenario}")
    print(f"[trial] project={project} domain={isolation['ros_domain_id']}")
    print(f"[trial] survivors before: {before_survivors['gz_sim_count']} gz sim process(es)")

    watcher = Watcher(project, condition)
    watcher.start()

    started_wall = time.time()
    console_lines: list[str] = []
    process = subprocess.Popen(
        [str(root / "scripts" / "scenario"), scenario],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    # I3: the campaign captures its own console. Written line by line rather than at the
    # end, so a run killed part-way still leaves what it had said -- rule P is about
    # having the console, and a buffer lost with the process is a console nobody has.
    with writer.console_path.open("w") as sink:
        assert process.stdout is not None
        for line in process.stdout:
            console_lines.append(line)
            sink.write(line)
            sink.flush()
            sys.stdout.write(line)
            # The event the I7 gate waits on. A `CITE_TIMING` line means one of the
            # scenario's own waits completed, so the stack the reading needs is up. The
            # marker constant is `common`'s, so the reader and the parser cannot drift.
            if common.TIMING_MARKER in line:
                watcher.note_first_record()
    returncode = process.wait()
    ended_wall = time.time()
    watcher.stop()

    cid = watcher.found["container_id"]
    # Both readings are kept. `cpu_at_end` is the honest post-exit attempt and normally
    # says the container is gone -- `compose run --rm` removes it as `./scripts/scenario`
    # exits -- and `cpu_last_live` is the last one taken while the run was live, which is
    # the only end-of-run reading this container's lifetime permits. Recording only the
    # second would look like a reading taken after the process ended; recording only the
    # first would report every run as unconfirmed.
    cpu_at_end = common.cpu_allocation(cid) if cid else None
    cpu_last_live = watcher.found["cpu_last_live"]
    end_snapshot = common.snapshot(root)
    load_after = common.host_load()

    # The reading is taken BEFORE anything is cleared. A harness that kills a survivor
    # first has destroyed the evidence of its own invalidity (V5).
    after_survivors = common.survivors()
    # THE RELEASE IS ATTEMPTED AND READ BACK, NEVER ASSUMED. The shakedown measured
    # `docker update --cpus 0` returning 0 on Docker 29.7.2 and leaving `cpu.max` at
    # `200000 100000` -- it releases nothing and says nothing. What actually isolates one
    # run's allocation from the next is that `scripts/_lib.sh` starts the scenario with
    # `compose run --rm`, so the container is DESTROYED at the end of every run. That
    # holds only while no `dev` service is already up: with one running, `_lib.sh` uses
    # `compose exec` instead, the container survives, and a quota this harness could not
    # release would silently apply to the next run. So the attempt is recorded with its
    # read-back, and `v6_ok` below refuses a FULL run that found a quota in force.
    release = None
    if cid:
        attempt = subprocess.run(
            ["docker", "update", "--cpus", "0", cid], capture_output=True, text=True
        )
        read_back = common.cpu_allocation(cid)
        release = {
            "returncode": attempt.returncode,
            "stderr": attempt.stderr.strip(),
            "read_back": read_back,
            "container_still_exists": not read_back["cgroup_cpu_max_inside"].startswith("<"),
            "released": read_back["cgroup_cpu_max_inside"].split()[0:1] == ["max"],
        }
    common.clear_survivors()

    console = "".join(console_lines)
    parsed = common.parse_timing(console)
    verdict = common.verdict_of(console, scenario)
    validity = _validity(
        condition=condition,
        v1=common.v1(start_snapshot, end_snapshot),
        watcher=watcher.found,
        cpu_last_live=cpu_last_live,
        load_before=load_before,
        survivors_before=before_survivors,
        parsed=parsed,
        verdict=verdict,
    )

    document = {
        "label": label,
        "condition": condition,
        "scenario": scenario,
        "started_wall_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_wall)),
        "ended_wall_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ended_wall)),
        "duration_s": round(ended_wall - started_wall, 3),
        "scenario_returncode": returncode,
        "verdict": verdict,
        "isolation": isolation,
        "host_facts": common.host_facts(),
        "load_before": load_before,
        "load_after": load_after,
        "i4_after_apply": watcher.found["cpu_after_apply"],
        "i4_last_live": cpu_last_live,
        "i4_last_live_before_exit_s": (
            round(ended_wall - watcher.found["cpu_last_live_at"], 3)
            if watcher.found["cpu_last_live_at"]
            else None
        ),
        "i4_samples": watcher.found["cpu_samples"],
        "i4_post_exit_attempt": cpu_at_end,
        "i4_release_attempt": release,
        "i6": common.v1(start_snapshot, end_snapshot),
        "i7": watcher.found["configuration"],
        "i7_gate": watcher.found["configuration_gate"],
        "container": {
            "id": cid,
            "cite_environment_in_force": watcher.found["container_env"],
            "started_at": watcher.found["container_started_at"],
            "seen_at": watcher.found["container_seen_at"],
            "limit_applied_at": watcher.found["limit_applied_at"],
            "limit_delay_s": watcher.found["limit_delay_s"],
            "limit_command": watcher.found["limit_command"],
        },
        "survivors_before": before_survivors,
        "survivors_after": after_survivors,
        "environment": {
            # Section 5: the value IN FORCE, read from the environment and never assumed
            # from a table row. `scripts/_lib.sh` forwards every CITE_-prefixed host
            # variable into the container, so one set in an unrelated shell would silently
            # change the leg count and the expected record count of threat 12.
            "CITE_LINE_WORKPIECES": os.environ.get("CITE_LINE_WORKPIECES"),
            "CITE_ENV": os.environ.get("CITE_ENV"),
            "host_shell_note": "what this shell exported; NOT the value in force",
            # `scripts/scenario` exports its own default seed AFTER reading the host, so
            # the host shell's value is null on every ordinary run and is not the seed
            # that reached `gz sim --seed`. The scenario prints the value it used on
            # every run, so it is read from the captured console (I3) instead.
            "CITE_PHYSICS_SEED_in_force": _seed_from_console(console),
        },
        "criteria_sha256": common.sha256(common.CAMPAIGN / "criteria.md"),
        "instrument": {
            "timing_regex": common.TIMING_RE.pattern,
            "marker_lines": parsed["marker_lines"],
            "records": len(parsed["records"]),
            "mangled_count": parsed["mangled_count"],
            "mangled_fraction": parsed["mangled_fraction"],
            # Rule G: the raw text of up to three, so the write-up can quote them.
            "mangled_sample": parsed["mangled"][:3],
        },
        "validity": validity,
        # Every record carries the run's validity flags. A record lifted out of this file
        # into a table is a record that has left its header behind, and V1, V2, V3 and V6
        # are per-run rules whose evidence must not be separable from the numbers they
        # validate.
        "records": [
            {**record, "label": label, "condition": condition, **validity, **verdict}
            for record in parsed["records"]
        ],
    }
    path = writer.write(document)
    print(f"[trial] {label} rc={returncode} verdict={verdict['verdict']} "
          f"records={len(parsed['records'])} mangled={parsed['mangled_count']}")
    print(f"[trial] wrote {path}")
    return returncode


_SEED_LINE = re.compile(r"Seed (\S+) reaches 'gz sim --seed' only")


def _seed_from_console(console: str) -> str | None:
    """The seed that actually reached Gazebo, read off `scripts/scenario`'s own warning.

    A condition recorded per run, and never a reproducibility claim: `gz sim --seed` seeds
    `gz::math::Rand` and NOT the physics solver, and the OMPL fallback is unseeded and
    unseedable. `criteria.md` section 1 is explicit that nothing here is a determinism
    claim.
    """
    match = _SEED_LINE.search(common.ANSI_RE.sub("", console))
    return match.group(1) if match else None


def _validity(
    *,
    condition: str,
    v1: dict,
    watcher: dict,
    cpu_last_live: dict | None,
    load_before: dict,
    survivors_before: dict,
    parsed: dict,
    verdict: dict,
) -> dict:
    """`criteria.md` section 10, evaluated HERE and travelling on every record.

    Each flag is one rule and says which. `analyse.py` reads them; it must not re-derive
    any of them from a tree that has since moved, which is V1's own instruction.

    `v6_ok` is True at FULL by construction and the key says so: FULL applies no limit, so
    there is no delay to bound. That is not the same statement as "the limit was in force"
    and it is not written as if it were -- and at FULL it is still REFUSED when no I4
    reading ever came back from a live container, because "no quota was in force" and "we
    never managed to look" are different answers.
    """
    configuration = watcher.get("configuration") or {}
    delay = watcher.get("limit_delay_s")
    if condition == "FULL":
        v6_ok = True
        v6_note = "FULL applies no limit; there is no application delay to bound"
    elif delay is None:
        v6_ok = False
        v6_note = "the container start time could not be parsed, so the delay is not established"
    else:
        v6_ok = delay <= common.V6_LIMIT_DELAY_CEILING_S
        v6_note = f"limit applied {delay:.1f} s into the container's life"
    limit_held = None
    if condition == "FULL" and cpu_last_live is not None:
        # FULL is a READING and not an absence of action. A container that came up with a
        # quota already in force -- a leftover from a previous run this harness could not
        # release, on a host where the `dev` service was already up -- is not the
        # condition the table says it is, and its margin belongs to no cell.
        unconstrained = cpu_last_live["cgroup_cpu_max_inside"].split()[0:1] == ["max"]
        if not unconstrained:
            v6_ok = False
            v6_note = (
                "FULL, but the running container read "
                f"cpu.max={cpu_last_live['cgroup_cpu_max_inside']!r}: a quota was in "
                "force, so this run is not the FULL condition"
            )
    if condition != "FULL" and cpu_last_live is not None:
        # V6's second half: the limit confirmed both after application and at the END.
        # A run whose cgroup file read `max 100000` at the end ran part of itself
        # unconstrained whatever the application said. "At the end" is the last reading
        # taken while the container still existed; see `I4_SAMPLE_PERIOD_S`. A run for
        # which no live reading survives leaves this `None`, which is NOT ESTABLISHED and
        # is not read as confirmation.
        limit_held = cpu_last_live["cgroup_cpu_max_inside"].split()[0:1] != ["max"]
    if condition != "FULL" and cpu_last_live is None:
        # NOT ESTABLISHED is not confirmation. A loaded run for which no live I4 reading
        # survived cannot show that its allocation was in force at the end, and V6 asks
        # for exactly that. The docstring above says so; without this branch the
        # conjunction below turned `None` into a pass.
        v6_ok = False
        v6_note = (
            "the limit was never confirmed on a live container, so V6's end-of-run "
            "clause is NOT ESTABLISHED and is not read as satisfied"
        )
    if condition == "FULL" and cpu_last_live is None:
        # THE SAME RULE AT FULL, AND IT IS NOT SYMMETRY FOR ITS OWN SAKE. The residual-
        # quota check above is guarded by `cpu_last_live is not None`, so without this
        # branch a FULL run that NEVER SUCCEEDED IN LOOKING concluded "the container was
        # unconstrained" from having never looked -- silence read as a pass, which is the
        # same family of defect as the `v6_ok` the shakedown caught.
        #
        # IT IS NOT COVERED TRANSITIVELY, AND THERE IS A RECORDED COUNTEREXAMPLE.
        # The argument for leaving it was that no live I4 reading implies the container
        # was unreachable, which would leave I7 unread and V2 discard the run first. The
        # shakedown record disproves it: `raw/shakedown/SHAKEDOWN_bringup.json` carries
        # `v2_ok: true` -- 13 hull references off the running description publisher and
        # the throttle in the installed world -- beside `i4_last_live: null`, at FULL,
        # with `v6_ok: true`. The two readings go through the same `docker exec` but they
        # are not the same call: I7 reads a running node, I4 reads
        # `/sys/fs/cgroup/cpu.max`, and a container that does not expose that path fails
        # I4 deterministically while answering I7 perfectly. V2 does not cover V6.
        v6_ok = False
        v6_note = (
            "FULL, and no I4 reading ever came back from a live container: whether a "
            "quota was in force is NOT ESTABLISHED, and an unconstrained container may "
            "not be concluded from having never looked"
        )
    return {
        "v1_clean": v1["v1_clean"],
        "v1_disagreed_mid_run": v1["disagreed_mid_run"],
        "v2_ok": configuration.get("v2_ok"),
        "v3_verdict": verdict["verdict"],
        # BOTH clauses. "nothing was found" and "the search did not run" are
        # different answers, and V5 may not be satisfied by the second: a run whose
        # survivor search failed has not been checked for survivors at all.
        "v5_ok": bool(
            survivors_before["gz_sim_count"] == 0 and survivors_before["looked_ok"]
        ),
        "v6_ok": bool(v6_ok and (limit_held is not False)),
        "v6_note": v6_note,
        "v6_limit_held_at_end": limit_held,
        "v7_load_flag": bool(load_before["load_1m"] > common.V7_LOAD_FLAG),
        "v7_load_1m": load_before["load_1m"],
        "g_ok": parsed["g_ok"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--condition", required=True, choices=sorted(common.CONDITIONS))
    parser.add_argument("--scenario", required=True, choices=common.SCENARIOS)
    parser.add_argument("--out", default=str(common.RAW))
    arguments = parser.parse_args()
    out = Path(arguments.out)
    if (out / f"{arguments.label}.json").exists():
        # V8: n is what it was. A collected run is never silently re-run over the top of
        # itself, because that tops a condition up without saying so.
        print(f"[trial] {arguments.label} already collected; refusing to overwrite it (V8)")
        return 0
    return run(arguments.label, arguments.condition, arguments.scenario, out)


if __name__ == "__main__":
    sys.exit(main())
