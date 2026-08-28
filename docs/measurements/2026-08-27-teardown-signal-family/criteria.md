# Pre-registration: does breaking the SkillServer reference cycle change the signal-death rate?

Written **before** the first trial of either arm. 2026-08-27, one machine
(aarch64, Docker Desktop on macOS), one checkout with its own build volumes.

## Question

Does `move_group_.reset()` in `SkillServer::shutdown()` — which breaks the
demonstrated `SkillServer <-> MoveGroupInterface` reference cycle — change the
rate at which `skill_server` exits on a signal at teardown?

## Vehicle

`./scripts/scenario bringup`. Chosen over `continuous_line` because it costs
~42 s against ~480 s, brings up the same processes (3 `move_group`, 3
`skill_server`, `parameter_bridge`, `gz`, the `cite_facility` nodes), and runs
the same strict teardown assertion, in which **only** `move_group` at -11 is
exempt. Each run yields **3** `skill_server` teardowns.

## Sample size and why

The only observation of `skill_server` at -11 is 1 event in a 3-run
`continuous_line` set = 3 runs x 3 servers = **9 teardowns**, so the point
estimate is q ~= 0.11 per teardown, with a 95% interval running from about
0.003 to 0.48. That interval is the reason a single clean run proves nothing.

**N = 30 runs per arm = 90 `skill_server` teardowns per arm.** If the true
pre-fix rate is the q ~= 0.11 point estimate, the probability of seeing zero
events in 90 teardowns is 0.89^90 ~= 3e-5. So a pre-fix count of zero is strong
evidence that **this rig does not reproduce the defect**, not evidence that the
defect is absent.

## Decision rules, fixed in advance

1. If the **pre-fix** arm records 0 `skill_server` signal deaths in 90
   teardowns, the experiment is **INCONCLUSIVE for `skill_server`**. It will be
   reported as "the rig does not reproduce it", and no claim will be made that
   the fix removes it. A clean post-fix arm will **not** be reported as a pass.
2. Only if the pre-fix arm records >= 1 event does the post-fix arm carry any
   information about the rate.
3. Counts for `move_group`, `parameter_bridge` and `gz` are recorded as
   secondary outcomes for classification, not as the primary question.

## Co-primary, deterministic, and independent of any rate

Already observed 1/1 in each direction on the `cite_skills` launch rig, and to
be re-verified:

| Observable | Cycle present | Cycle broken |
|---|---|---|
| `node.use_count()` at end of `main` | 9 | 1 |
| `~SkillServer` runs | no | yes |
| `class_loader` "SEVERE WARNING ... objects created by this loader exist in the heap" | present | absent |

This is the discriminator a P6 regression test can rest on, because it is a
state, not a rate.
