#!/usr/bin/env python3
"""One probe trial -- arm A, arm B or arm A' -- as one JSON record.

Runs INSIDE the container. One invocation produces one record in the output
directory, and every arm-A/B/A' figure this campaign reports comes from one of
those records (`../criteria.md` section 6, the shape copied from
`docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/trial.py` at
commit `fca1391`; that directory is FROZEN and nothing in it is edited here).

WHAT THIS TRIAL IS. `gz sim -s -r --iterations N --seed S <probe world>` with
NO ROS in it at all -- no launch, no controller manager, no move_group, no
skill server, no bridge. One body, declared in the world, off equilibrium at
step 0. That absence is the arm: arm A asks whether the physics engine
reproduces when nothing asynchronous is touching it, and a process spawning the
body would be exactly the thing arm C is for.

THE PARTITION. Every Gazebo-transport process here goes through
`cite_bringup.gz` and nothing else (`../criteria.md` V10, ADR-0042,
CLAUDE.md section 10). The server is started with
`gz.process_environment(gz.plan_for("cell_b"))` and the reader is
`gz.ModelPoses`, which takes the same partition through the same door -- which
is what puts the probe and the instrument in the same transport. An
unpartitioned `gz model --list` reaches no world and EXITS 0, so getting this
wrong would look like a quiet trial.

THE INSTRUMENT IS AN EVENT AND NEVER A SLEEP (V4). `ModelPoses.position`
returns None both before the first snapshot and for an absent model
(`gz.py:189-195`), and the two must not be confused: this file waits for the
FIRST snapshot as an event, and only after that does a None mean absence.

WHAT IS AN INSTRUMENT LOSS (V11, section 5.3). A trial that never reached a
first snapshot, or never reached rest under I2 inside the 120 s ceiling, is an
instrument loss -- recorded as such, counted, and NEVER recorded as a trial in
which nothing happened. It is written to a record all the same, with
`instrument_loss` true and the reason stated, because a trial that produced no
file is a trial nobody can count.

    python3 trial_probe.py --arm A --index 1 --seed 20260824 --x-offset 0.0 \\
        --out /workspace/docs/measurements/2026-09-22-is-a-run-reproducible/raw
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

ARMS = ("A", "B", "Aprime")


def seed_from_argv(argv: list[str]) -> int | None:
    """V2 -- the seed THE COMMAND LINE carries, not the one we meant to pass.

    Read back off the argv that was launched, so that a record states what ran.
    """
    for index, token in enumerate(argv):
        if token == "--seed" and index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except ValueError:
                return None
    return None


def agree(first: tuple, second: tuple, tolerance: float) -> bool:
    """I2's comparison: EVERY coordinate agrees to less than ``tolerance``."""
    return all(abs(a - b) < tolerance for a, b in zip(first, second, strict=True))


def worst(first: tuple, second: tuple) -> float:
    return max(abs(a - b) for a, b in zip(first, second, strict=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--x-offset", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", default=None)
    parser.add_argument("--iterations", type=int, default=common.PROBE_ITERATIONS)
    # `../criteria.md` section 6 permits EXACTLY ONE shakedown, published under
    # `raw/shakedown/`, excluded from every figure, and forbidden from setting
    # or adjusting any threshold. The flag puts `is_shakedown` on the record so
    # that the exclusion is a property of the row and not of the directory the
    # operator happened to redirect into -- the 2026-09-03 campaign recorded
    # what a directory convention is worth as an exclusion.
    parser.add_argument("--shakedown", action="store_true")
    arguments = parser.parse_args()

    out_dir = Path(arguments.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = arguments.label or common.label_for(arguments.arm, arguments.index)
    record_path = out_dir / f"{label}.json"
    if record_path.exists():
        # V8, and resumability. A trial whose record exists is skipped rather
        # than re-run; no arm is ever topped up.
        print(f"{label}: skipped, {record_path} exists", flush=True)
        return 0

    record: dict = {
        "campaign": "2026-09-22-is-a-run-reproducible",
        "label": label,
        "arm": arguments.arm,
        "is_shakedown": bool(arguments.shakedown),
        "trial_index": arguments.index,
        "seed_requested": arguments.seed,
        "x_offset_m": arguments.x_offset,
        "iterations_requested": arguments.iterations,
        "zone": common.ZONE,
        "probe_world_name": common.PROBE_WORLD_NAME,
        "probe_body": common.PROBE_BODY,
        "probe_pose_nominal": common.PROBE_POSE,
        "at_rest_rule": {
            "min_gap_s": common.AT_REST_MIN_GAP_S,
            "tolerance_m": common.AT_REST_TOL_M,
            "ceiling_s": common.AT_REST_CEILING_S,
        },
        # V1, the opening reading. The closing one is taken at the end, on
        # every path including the failure paths.
        "git_open": common.git_snapshot(),
        "load_open": common.load_average(),
        "host": common.host_facts(),
        "docker_ps": common.docker_ps(),
        "started_wall": time.time(),
        "instrument_loss": False,
        "instrument_loss_reason": None,
    }

    def seal(exit_code: int) -> int:
        record["git_close"] = common.git_snapshot()
        record["load_close"] = common.load_average()
        record["ended_wall"] = time.time()
        record["exit_code"] = exit_code
        common.write_record(record_path, record)
        print(
            f"{label}: loss={record['instrument_loss']} "
            f"final={record.get('final_position')} "
            f"at_rest={record.get('at_rest', {}).get('reached')}",
            flush=True,
        )
        return exit_code

    # ---- the world, and V3 -------------------------------------------------
    world_text = common.build_probe_world(arguments.x_offset)
    world_path = out_dir / f"{label}.world.sdf"
    world_path.write_text(world_text)
    record["world_path"] = str(world_path)
    record["world_sha256"] = common.sha256_text(world_text)

    # ---- V-physics, BEFORE the server is started ---------------------------
    # "Otherwise arm A measures a different simulator from the one the cell
    # runs." This REFUSES; it does not warn.
    physics = common.physics_agreement(world_text)
    record["v_physics"] = physics
    if not physics.get("agree"):
        record["verdict"] = "REFUSED"
        record["refusal"] = (
            "V-physics: the probe world's <physics> block does not match the INSTALLED "
            "generated world's. The probe would measure a different simulator from the "
            "one the cell runs. Nothing here may be edited to make this pass -- if the "
            "generated world moved, that is the finding."
        )
        return seal(3)

    gz = common.import_gz()

    # ---- the reader, subscribed BEFORE the server starts (V4) --------------
    try:
        poses = gz.ModelPoses(zone=common.ZONE, world=common.PROBE_WORLD_NAME)
    except Exception as exc:  # noqa: BLE001 - an instrument that did not open
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = f"ModelPoses did not subscribe: {exc}"
        record["verdict"] = "INSTRUMENT_LOSS"
        return seal(4)
    record["pose_topic"] = poses.topic

    environment = gz.process_environment(gz.plan_for(common.ZONE))
    record["gz_partition"] = environment.get("GZ_PARTITION")

    argv = [
        "gz", "sim",
        "-s", "-r",
        "--iterations", str(arguments.iterations),
        "--seed", str(arguments.seed),
        str(world_path),
    ]
    record["argv"] = argv
    # V2: read back off the command line that was launched.
    record["seed_from_argv"] = seed_from_argv(argv)
    record["seed_matches_request"] = record["seed_from_argv"] == arguments.seed

    console = out_dir.joinpath(f"{label}.console").open("w")
    server = subprocess.Popen(
        argv,
        stdout=console, stderr=subprocess.STDOUT,
        env=environment, start_new_session=True,
    )
    record["server_pid"] = server.pid
    launched_wall = time.time()
    record["server_launched_wall"] = launched_wall

    try:
        # ---- V4: the first snapshot is an EVENT ----------------------------
        first = None
        deadline = time.monotonic() + common.FIRST_SNAPSHOT_CEILING_S
        while first is None:
            first = poses.position(common.PROBE_BODY)
            if first is not None:
                break
            if server.poll() is not None:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    f"gz sim exited with {server.poll()} before any snapshot arrived; "
                    "the trial never reached readiness (section 5.3)"
                )
                break
            if time.monotonic() > deadline:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    f"no first snapshot on {poses.topic} within "
                    f"{common.FIRST_SNAPSHOT_CEILING_S:g} s (V4, V11)"
                )
                break
            time.sleep(common.POLL_PERIOD_S)

        if first is not None:
            record["first_snapshot_wall"] = time.time()
            record["first_snapshot_after_s"] = record["first_snapshot_wall"] - launched_wall
            record["first_position"] = list(first)

            # ---- I2: the at-rest rule, applied literally -------------------
            samples: list[dict] = []
            at_rest: dict = {
                "reached": False,
                "reason": None,
                "closest_pair_max_delta_m": None,
            }
            deadline = time.monotonic() + common.AT_REST_CEILING_S
            closest: float | None = None
            while True:
                now = time.time()
                alive = server.poll() is None
                position = poses.position(common.PROBE_BODY)
                if position is not None:
                    samples.append(
                        {"wall": now, "position": list(position), "server_alive": alive}
                    )
                    # The tightest window that is still at least the registered
                    # gap: the NEWEST earlier sample at least 1.0 s back.
                    partner = None
                    for candidate in reversed(samples[:-1]):
                        if now - candidate["wall"] >= common.AT_REST_MIN_GAP_S:
                            partner = candidate
                            break
                    if partner is not None:
                        delta = worst(tuple(partner["position"]), position)
                        closest = delta if closest is None else min(closest, delta)
                        # Both readings must have been taken while the server
                        # was still stepping. A dead server republishes nothing
                        # and `ModelPoses` keeps its newest snapshot, so two
                        # samples taken after it exited agree TRIVIALLY -- that
                        # is a stale instrument, not a body at rest.
                        if (
                            delta < common.AT_REST_TOL_M
                            and alive
                            and partner["server_alive"]
                        ):
                            at_rest = {
                                "reached": True,
                                "reason": None,
                                "sample_a": partner,
                                "sample_b": samples[-1],
                                "gap_s": now - partner["wall"],
                                "max_delta_m": delta,
                                "closest_pair_max_delta_m": closest,
                            }
                            break
                if server.poll() is not None and not at_rest["reached"]:
                    at_rest["reason"] = (
                        f"gz sim exited with {server.poll()} before two samples "
                        f"{common.AT_REST_MIN_GAP_S:g} s apart agreed to "
                        f"{common.AT_REST_TOL_M:g} m"
                    )
                    at_rest["closest_pair_max_delta_m"] = closest
                    break
                if time.monotonic() > deadline:
                    at_rest["reason"] = (
                        f"the body did not reach rest within the registered "
                        f"{common.AT_REST_CEILING_S:g} s ceiling (I2)"
                    )
                    at_rest["closest_pair_max_delta_m"] = closest
                    break
                time.sleep(common.POLL_PERIOD_S)

            record["at_rest"] = at_rest
            record["samples"] = samples
            if not at_rest["reached"]:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = f"I2: {at_rest['reason']}"

            # ---- let the iterations finish, then read the final position ---
            exit_deadline = time.monotonic() + common.SERVER_EXIT_CEILING_S
            while server.poll() is None and time.monotonic() < exit_deadline:
                position = poses.position(common.PROBE_BODY)
                if position is not None:
                    samples.append(
                        {"wall": time.time(), "position": list(position), "server_alive": True}
                    )
                time.sleep(common.POLL_PERIOD_S)
            record["server_ran_to_completion"] = server.poll() == 0
            record["server_exit_status"] = server.poll()

            final = poses.position(common.PROBE_BODY)
            record["final_position"] = list(final) if final is not None else None
            record["final_read_wall"] = time.time()
            if final is None:
                record["instrument_loss"] = True
                record["instrument_loss_reason"] = (
                    (record["instrument_loss_reason"] or "")
                    + "; the body was absent from the newest snapshot at the final read"
                ).lstrip("; ")
            elif at_rest["reached"]:
                record["final_agrees_with_at_rest"] = agree(
                    tuple(at_rest["sample_b"]["position"]), final, common.AT_REST_TOL_M
                )
                record["final_vs_at_rest_max_delta_m"] = worst(
                    tuple(at_rest["sample_b"]["position"]), final
                )
    except Exception as exc:  # noqa: BLE001 - a trial that died is a trial to count
        # A trial that raised must still leave a record. V11 counts instrument
        # losses and reports them separately from every other exclusion, and a
        # trial that wrote no file at all is a trial nobody can count.
        record["instrument_loss"] = True
        record["instrument_loss_reason"] = (
            f"the trial raised {type(exc).__name__}: {exc}"
        )
    finally:
        poses.close()
        if server.poll() is None:
            try:
                server.send_signal(signal.SIGINT)
                server.wait(timeout=common.STOP_GRACE_S)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(server.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        try:
            os.killpg(server.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        console.close()

    record["verdict"] = "INSTRUMENT_LOSS" if record["instrument_loss"] else "COLLECTED"
    return seal(0 if not record["instrument_loss"] else 5)


if __name__ == "__main__":
    sys.exit(main())
