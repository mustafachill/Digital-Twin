# Safety procedures

- **Status:** `DESIGNED` — **no procedure here is valid until Phase 2 hardware integration is complete and independently reviewed.**
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
set deliberately in the current shell.**

Never set it in a shell profile, a Dockerfile, a launch default, or CI. It exists so that
reaching hardware requires a conscious act, and putting it in a profile destroys the only
protection it provides.

**The honest qualification about today's state is about *when* the rule binds, not
whether anything enforces it.** Two guards do, and both are covered by tests; their names,
locations and coverage are in
[`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)'s Status bullet and are
not repeated here. What that bullet does not say, and what an operator needs: **both refuse
before the stack starts — one at the shell, one at bring-up — and neither refuses a mode
transition.** No server implements `SetMode` yet (CLAUDE.md §2), so nothing in the
repository refuses one. That gap must be closed before the first Phase 2 motion, and it is
not a reason to treat the rule as optional in the meantime.

## Before any physical motion

Every session. Not once per week.

1. **Risk assessment current** for the cell in its present configuration. If the layout
   changed, it is not current.
2. **Physical E-stop tested.** Press it. Confirm the arms stop. Measure the latency if it
   has not been measured recently.
3. **Cell clear**, confirmed by a person with eyes on it — not by a sensor, not by
   assumption.
4. **Registration current** — [calibration-and-registration.md](calibration-and-registration.md).
   A drifted registration means the robot's model of where things are is wrong.
5. **A human at the stop**, watching, for the whole session.
6. **Reduced speed** for the first execution of any motion that has not run on this
   hardware before.

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

## Held payloads on fault

The design must state what happens to a grasped work-piece on E-stop, power loss, or
controller failure. **Both possible behaviours are hazards:**

- *Drops the part* — falling object, damaged work-piece, possible injury below.
- *Cannot be released* — trapped part, and potentially a trapped person.

Neither is wrong in the abstract. Not having chosen is wrong. Whoever operates the cell
must know which behaviour it has before they need to know.

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
