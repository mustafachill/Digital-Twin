# ADR-0073: Validate in simulation, then run the twin — one request

- **Status:** Proposed
- **Date:** 2026-10-09
- **Deciders:** Project owner (decision of 2026-10-09: one button runs the program on the
  simulation first and, only if it passes, on the simulation and the real arm together)
- **Related:** [ADR-0072](0072-the-operator-chooses-where-the-signal-goes.md) (targets),
  [ADR-0071](0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md) (console),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)

## Context

ADR-0072 lets the operator run the real program on the simulation, on the real arm, or on both.
Doing "simulation first, then the real cell" takes several manual steps today: choose
Simulation, Start program, check the result, choose Twin, Home, then Start program again.
Virtual-commissioning tools offer this as one flow (validate in simulation, then commission).
The project owner asked for it as one button.

Two facts constrain the design:

- **No fidelity number exists** (`DivergenceMetrics.valid` is false by construction; CLAUDE.md
  §2). A cycle that completes in simulation is not evidence that the physical cycle is safe. It
  only shows that the program, the poses and the planner agree in the model.
- **The twin target carries every physical gate:** the operator's go-ahead read in `SIM`, the
  speed floor, the mode hold, the carriage-stationary check, and the return to `SIM`. A combined
  request must not weaken any of them.

## Decision

1. **One action, `ValidateThenRun`, on the console.**
   - **Goal:** `speed_scale` and `cycles`, both explicit, never defaulted.
   - **Feedback:** the phase (validating or running), the cycle and the step.
   - **Result:** success, a detail, and which phase ended the request.
2. **Phase 1 runs on the simulation alone.** It is a Simulation-target run (`SIM`, the plant
   alone) of one cycle at the requested scale. If it fails or is stopped, the request ends
   there and nothing reaches the physical side.
3. **Phase 2 runs on the twin.** It starts only if phase 1 completed in this same request.
   - It is a Twin-target run at the same scale, with every Twin gate unchanged.
   - Before it, both sides are measured at the program's start. A side that is away is refused:
     the console does not home on its own between phases (ADR-0037). The operator homes and
     presses again.
   - The operator's go-ahead is asked as for any Twin run, naming the target and the physical
     side.
4. **Validation does not carry over.** The phase 1 pass is valid only for the phase 2 that
   immediately follows it, in the same request, at the same scale, with no change of mode in
   between. A separate Twin Start program is not "validated" by an earlier Simulation run.
5. **Honest labelling.**
   - The panel shows the outcome as "passed in simulation", never as "safe", "verified" or
     "validated for the real cell".
   - The phase 2 prompt says plainly that the simulation pass is not evidence of physical
     safety.
6. **Offered only when both sides run.** `ValidateThenRun` is offered only when Twin is among
   the available targets. On a plant-only deployment it is refused, and the panel disables it.

## Consequences

### What this gets us
- The commissioning-style flow becomes one press: the model runs the program first, and the real
  cell follows only after it completes there.
- It needs no new gate. Every physical safeguard is the Twin run's own.

### What this costs us
- A third motion request on the console, with its own phases, refusals and tests.
- A "passed in simulation" that an operator may read as more than it is. The labelling decision
  above is the only guard until a fidelity number exists.
- Phase 1 moves the plant arm. If phase 1 leaves the plant away from the start, phase 2 is
  refused and the operator must home.

### What we will have to revisit
- **When `DivergenceMetrics` can be valid:** whether a fidelity threshold should gate phase 2.
- **When Pause and Step exist:** how they apply across the two phases.
