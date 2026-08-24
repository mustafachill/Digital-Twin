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

**Two honest qualifications about today's state.** The guard is
`require_explicit_hardware_opt_in()` in `scripts/_lib.sh`; **no script calls it yet**, so
the rule currently holds only because nothing in the repository can command an arm at all.
And `./scripts/enter hardware` opens a privileged container with host networking and `/dev`
passthrough **after printing a warning, without checking the variable** — so it reaches the
lab network whether or not the variable is set. Both must be closed before the first Phase 2
motion, and neither is a reason to treat the rule as optional in the meantime.

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
