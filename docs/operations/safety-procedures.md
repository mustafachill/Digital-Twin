# Safety procedures

- **Status:** `DESIGNED` — **no procedure here is valid until Phase 2 hardware integration is complete and independently reviewed.**
  The physical counterpart's software chain is built
  ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)) and has never moved the
  arm. [`bring-up.md`](bring-up.md)'s *Physical cell* section is how it is run.
- **Related:** [`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md), [`../reference/standards.md`](../reference/standards.md)

## Read this first

> **This document covers software procedure. It is not a safety certification, and it does
> not substitute for a risk assessment, physical guarding, or a safety-rated controller.**

Certified functional safety for a robot cell is a hardware and process matter governed by
ISO 10218-1/-2:2025. It is outside this repository (charter §3.2). If the physical
cell has not been risk-assessed and guarded, **no software procedure makes it safe to
operate**, and nothing in this document should be read as suggesting otherwise.

## The rule that governs everything

**Nothing in this repository commands physical hardware unless `CITE_ALLOW_HARDWARE=1` is
set deliberately, in the current shell or in the repository-root `.env`.**

Never set it in a shell profile, a Dockerfile, a launch default, or CI. It exists so that
reaching hardware requires a conscious act; set there, it would arm commands and machines
nobody chose to arm. **`.env` is allowed, by owner decision (2026-10-06):** `./scripts/program`,
`./scripts/sim --pair` and `./scripts/enter hardware` read it there when the shell does not set
it (the shell wins, even when it sets it empty), and say so when `.env` arms them. `.env` is
read fail closed: only one plain `CITE_ALLOW_HARDWARE=1` line arms; any other line naming the
key (`export …`, spaces around `=`, the key twice, an unrecognised value) is read as `0`, with
a warning naming its line number. A `1` in `.env` keeps every physical bring-up from this
checkout armed — remove it when you are not working at the cell. Test, scenario, lint, build
and CI never read it from `.env` — except when run inside `./scripts/enter hardware`, which
carries the resolved value. Every container command carries the value the
command resolved, so a container left running from an earlier session cannot carry it over.

**When it binds.** It binds:
- at the shell, for `./scripts/enter hardware`;
- at bring-up, for the physical side's own launch;
- at every mode transition that commands a physical side, in the twin boundary.

Bring-up alone does not move the arm. The physical side comes up *held*, its deadman keeping
the vendor stopped. It enables the arm only once the twin boundary's heartbeat is healthy, and
the program then waits for the boundary to report the side ready. What each guard does, and
what none of them covers, is in
[`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)'s Status block. None of
it is the safety layer that document designs, and none of it replaces the hardware E-stop.

## Before any physical motion

Every session. Not once per week.

1. **Risk assessment current** for the cell in its present configuration. If the layout
   changed, it is not current.
2. **Physical E-stop tested.** Press it. Confirm the arms stop. Measure the latency if it
   has not been measured recently.
3. **Cell clear**, confirmed by a person with eyes on it — not by a sensor, not by
   assumption.
4. **Registration current** — the real cell's frame tied to the model's, by
   [calibration-and-registration.md](calibration-and-registration.md) (Phase 2, charter §8;
   not built yet). A drifted registration means the robot's model of where things are is wrong.
   **Owner decision (2026-10-06):** registration is not required before the program's
   joint-space motion, supervised, with the hardware E-stop tested and in hand
   ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)). It is required
   before any Cartesian motion, any claim on the physical side that depends on the planning
   scene, and any divergence number.
5. **A human at the stop**, watching, for the whole session.
6. **Reduced speed** for the first execution of any motion that has not run on this
   hardware before.
7. **On the physical counterpart** ([bring-up.md](bring-up.md), "Physical cell"): the track
   is homed and its motor enabled by the operator; the physical carriage stands where the
   plant's does; the run is started through `./scripts/program` with an explicit
   `--speed-scale`; and the operator's go-ahead is given only when the program has read the
   twin in SIM.

## First execution of any new motion

1. Run it in `SIM` first. Every time. There is no motion so simple it is not worth ten
   seconds in simulation.
2. Run it in `SHADOW` if the arm is available — the physical arm moves, the model follows,
   and you see the divergence.
3. Reduced speed on hardware.
4. Full speed only after a clean reduced-speed run.

Under [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md) the same code runs in both
places, so step 1 is genuinely predictive. That is the entire point of the architecture,
and skipping it discards the benefit the project was built to provide.

### `VIRTUAL_LEAD` collapses step 1, and you have to restore it deliberately

**The ladder above works because running in `SIM` and running on hardware are different
operator acts.** You start a different thing, and the difference is visible to you at the
moment you do it. Step 1 protects you because you cannot perform it by accident when you
meant step 3.

`VIRTUAL_LEAD` removes that difference **by construction**. You command the simulated cell
and the far side follows and actuates: same scene, same gesture, same command path. The
only thing deciding whether an arm moves in the room is a per-(asset, side) backend fact
one layer down, which nothing in front of you shows
([ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 2).
**In Phase 2.B nothing on the operator's side changes shape — and that is precisely what
ADR-0041 says Phase 2.A exists to guarantee.** The guarantee and the hazard are the same
property, so do not expect a later change to remove the one and keep the other.

When the mode in force is `VIRTUAL_LEAD`:

1. **Establish the rehearsal by checking the far side's backend, not by your own gesture.**
   "I ran it in simulation" says nothing until you know which side the command reached.
   Read the backend. Do not infer it from what you did.
2. A facility-wide `SetMode(VIRTUAL_LEAD)` — `TwinMode`'s `asset_id` empty — asks that
   question of **every** asset at once. With one physical arm and two simulated ones, two
   arms answering "simulated" is not an answer for the third; see
   [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md).
3. Steps 3 and 4 above are unchanged, and they apply the moment any far side is real.

## During operation

| Observation | Action |
|---|---|
| Unexpected motion, of any size | **E-stop.** Diagnose before resuming. |
| Divergence rising | Stop. Suspect registration drift or a model error. |
| A controller reports an error | Stop. Do not clear and resume. |
| Anyone enters the cell | Stop. Motion resumes only when the cell is clear again. |
| Anything you cannot explain | Stop. An unexplained event is an undiagnosed fault. |

## After a fault

**A fault requires a deliberate reset. The system will not resume by itself, and you should
not make it.**

1. Do not clear the fault until you know its cause.
2. Record the state: bag, logs, what the operator saw.
3. Diagnose. Automatic resumption after an unexplained fault is a Critical design defect
   — if you find the system doing it, report it as one.
4. Reset deliberately.
5. Reduced speed on the first motion after a fault.

**On the physical counterpart.** A deadman trip latches: the arm is held stopped and stays
stopped. Re-sent stops keep undoing anyone else's re-enable until an operator resets the
deadman on purpose; the sequence is in `workspace/src/cite_hardware/README.md`. A vendor error
is never cleared by this software: the controller's own `clean_error` is the operator's
decision, after diagnosis.

## Held payloads on fault

The design must state what happens to a grasped work-piece on E-stop, power loss, or
controller failure. **Both possible behaviours are hazards:**

- *Drops the part* — falling object, damaged work-piece, possible injury below.
- *Cannot be released* — trapped part, and potentially a trapped person.

Neither is wrong in the abstract. Not having chosen is wrong. Whoever operates the cell
must know which behaviour it has before they need to know.

**On the physical xArm gripper, this has not been chosen.** As built, on a deadman trip the
jaws finish their last command, because the vendor's gripper action ignores cancel. What the
gripper does on E-stop or power loss is not established. Do not run with a part a fall would
make dangerous until it is.

## For software contributors who will never touch the robot

You still write code that moves it.

- Assume anything you write will run on hardware. Under
  [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md) it can, via a one-line
  configuration change.
- Never add a test fixture, mock, or debug flag that disables a limit or skips the safety
  layer where the hardware path could reach it. That is a Critical finding regardless of
  whether any current configuration reaches it.
- If a change touches motion, control, or mode, expect `safety-auditor` to trace it. Make
  its job easy: keep command paths explicit.
