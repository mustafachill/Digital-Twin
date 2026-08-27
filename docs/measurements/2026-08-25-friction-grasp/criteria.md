# Criteria — is a friction grasp in cell_a repeatable enough to build a scenario on?

**Written before any data was collected.** Recorded here so that the thresholds can be
seen to have preceded the numbers (P8). Nothing in this file may be edited once the first
trial has run; disagreements with it are recorded in `results.md` as deviations, with the
reason.

- **Date opened:** 2026-08-25
- **Branch / commit under measurement:** `feature/phase-1` at `dc68ab8`
- **Question:** ADR-0023 rejected friction-based grasping on the grounds that it is
  unreliable and *timestep-sensitive*. Is that true of this cell? The answer decides
  whether ADR-0023 is repaired or reversed.

## What is being varied, and what is held fixed

**The single lever that makes the measurement about friction at all:** the work-piece is
spawned under a model name that is *not* in the grasp plugin's `<graspable>` list
(`<graspable>workpiece</graspable>`, generated into every arm's description). The plugin
loads, runs, and never fires. Nothing else about the cell changes — same plugin, same
description, same controllers. Any lift observed is therefore produced by friction.

Held fixed unless named as a variable:

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, `./scripts/sim --headless` | not a reduced rig, deliberately |
| Work-piece | 50 mm cube, 0.2 kg, `mu = mu2 = 1.0` | copied from `tests/scenarios/pick_and_place.py` |
| Commanded grasp width | 0.045 m | `default_grasp_width_m`, L0 |
| `max_effort` | 60.0 N | L0 |
| `stall_velocity_threshold` | **0.05** rad/s | see deviation note below |
| `stall_timeout` | 0.3 s | L0 |
| `goal_tolerance` | 0.01 rad | L0 |
| `max_step_size` | 0.001 s | `STEP_SIZE_S`, world generator — **varied in T3** |

**Declared deviation from the shipped tree.** `stall_velocity_threshold` is 0.001 rad/s as
generated. It is set to 0.05 for every trial here, on instruction and because 0.001 is
below the achievable creep of the drive joint, so the gripper action hangs rather than
answering. A `fixer` is landing 0.05 in parallel. This is applied at L0 and regenerated,
never by hand-editing a generated artifact, and reverted afterwards.

## Per-trial measurements

A trial is one spawn, one approach, one close, one lift, one carry, one place, one release.

| Symbol | Definition |
|---|---|
| `z_rest` | work-piece z after it settles on the pick surface, before the arm moves |
| `t_grasp` | first sample after the gripper action returns with `stalled = true` |
| `z_max` | greatest work-piece z observed between `t_grasp` and release |
| `slip(t)` | ‖p_wp/tool(t) − p_wp/tool(t_grasp)‖ — work-piece position expressed in the gripper's tool frame, relative to where it sat at the instant of grasp |
| `slip_max` | max of `slip(t)` over the carry window |
| `slip_rate` | least-squares slope of `slip(t)` over the carry window, in mm/s |
| `v_max` | greatest work-piece speed observed over the whole trial |
| `place_err` | horizontal distance from the final resting position to the place frame |

## Per-trial verdicts

- `grasp_acquired` — the gripper action returned `stalled = true`, **and** the work-piece
  moved less than 10 mm horizontally between `z_rest` and `t_grasp` (it was gripped, not
  shoved aside).
- `lift_achieved` — `z_max − z_rest > 0.05` m. Same threshold the shipped scenario uses.
- `held_through_transport` — the work-piece z never returns below `z_rest + 0.03` m at any
  point between the first time it exceeds `z_rest + 0.05` m and the release command. This
  is what catches a part that is lifted and then dropped mid-carry, which `z_max` alone
  cannot see.
- `flung` — `v_max > 1.0` m/s at any sample, **or** the work-piece comes to rest more than
  0.5 m from the place frame.
- `placed` — `place_err < 0.10` m. Same threshold the shipped scenario uses.
- **`trial_success`** = `grasp_acquired ∧ lift_achieved ∧ held_through_transport ∧ placed ∧ ¬flung`.

## Thresholds — the decision rule

Stated as pass/fail *before* the numbers, so that the conclusion is read off rather than
argued to.

- **T1 — repetition at the shipped timestep.** `trial_success` must hold in **every** trial
  at `max_step_size = 0.001`. One failure in N is a fail: a scenario gate that goes red
  once in ten trains people to re-run until green, which
  `docs/architecture/cross-cutting-testing.md` names as worse than no test. N is decided by
  what the host affords and is **reported as the number it actually was**, together with
  the Wilson 95% lower bound on the success rate, so a small N cannot be dressed up as a
  determinism claim.
- **T2 — slip.** `slip_max ≤ 5 mm` in every trial, **and** `slip_rate` must not be
  significantly positive. Both halves are required: ADR-0023's named failure is the part
  *slowly sliding out*, and a carry short enough to hide a creep is not evidence that the
  creep is absent. 5 mm is chosen because it is well inside the 100 mm place tolerance —
  so slip at this level cannot flip a scenario assertion — while still being a tenth of the
  part's 50 mm width.
- **T3 — timestep sensitivity.** The trial protocol is run at
  `max_step_size ∈ {0.0005, 0.001, 0.002}`. ADR-0023's central objection is **upheld** if
  either: any timestep yields a `trial_success` rate below 100% while another yields 100%,
  or median `slip_max` differs by more than a factor of 2 across timesteps. It is **not
  supported** if all three give 100% success with comparable slip.
- **T4 — flung.** A single `flung` trial at any setting is a hard fail of friction
  grasping, with no rate argument. Being thrown across the cell is not a tail risk one
  budgets for in a test gate.
- **T5 — solver iterations and friction coefficient.** Varied only if cheap. Reported as
  whether `trial_success` and `slip_max` change. A null result here is a finding: ADR-0023
  names these as dependencies, and their not mattering is worth recording.

## What each outcome means for ADR-0023

| Outcome | Reading |
|---|---|
| T1 ∧ T2 ∧ T3-not-supported ∧ T4 | **Reverse.** The plugin, its L0 schema and the two-mechanism confusion can be deleted. |
| T3 upheld, or T2 fails, or T4 fails | **Keep, and reshape the trigger.** Noting that keeping is not cheap: the settled condition needs pad contact sensors that do not exist. |
| T1 holds but T3 upheld | **Third answer.** Friction works *at a pinned timestep*. Report as such rather than forcing it into either box. |

## Honesty bounds fixed in advance

- This measures the **simulator**, not the cell. ADR-0023's cost note applies in reverse
  too: nothing here evidences that a friction grasp is mechanically sound on the physical
  xArm. The layout is `PROVISIONAL` and the physical scan is Phase 3.
- Planning is unseeded (ADR-0006) and `CITE_PHYSICS_SEED` reaches nothing (ADR-0027), so
  trials are **not** replicates of one another under a fixed seed. They are independent
  samples from the same configuration. Every rate reported here is a rate over samples,
  never a determinism claim.
- Real-time factor on this host is ~0.14. Wall-clock ceilings are not results.
