# L5 — Twin synchronization

- **Status:** `DESIGNED` — no node implements any of this, and `cite_twin` does not exist.
  Phase 2. The typed interfaces are in place and frozen against the contract baseline —
  `TwinMode`, `SetMode`, `DivergenceMetrics`, `ModelVersion` — and every asset instance in
  L0 carries a `registration` block, currently `unregistered` for all three arms. Nothing
  consumes any of it.
- **Related:** [ADR-0011](../adr/0011-twin-maturity-model-and-modes.md) (amended 2026-08-29), [ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md), [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [standards-alignment.md](standards-alignment.md)

## Responsibility

**This is the layer that makes the system a twin rather than a simulation.** It owns the
relationship between the physical cell and its model: which direction information flows,
how the two coordinate frames correspond, and — most importantly — how far apart they are.

## Owns

- The operating **mode** of the system.
- State mirroring: physical → virtual.
- Command routing: which mode sends what to which side.
- **Calibration and registration** — the correspondence between the real cell's coordinate
  frame and the model's.
- The **twin monitor**: continuous divergence measurement and publication.

## Does not own

- Control. L5 routes and observes; L2 executes.
- Deciding what work to do — L4.
- Storing history. L5 publishes metrics; L6 records them.

## Interfaces

**Consumes:** joint and controller state from L2 on both paths; L4 line state for
event-level comparison.

**Exposes:** current mode, mode-transition service, divergence metrics, registration
transform, and twin health.

## Design

### Operating modes

| Mode | Physical | Virtual | Level |
|---|---|---|---|
| `SIM` | idle | commanded | L0 |
| `REAL` | commanded | idle | — |
| `SHADOW` | commanded | follows physical state | L1 |
| `VALIDATED` | commanded | commanded in parallel; divergence measured; virtual does not actuate | L2 |
| `CLOSED_LOOP` | commanded after virtual validation gates it | validates first | L3 |
| `VIRTUAL_LEAD` | follows the virtual side and actuates; nothing gates it first | commanded — this is where an operator's command enters | — |

**`VIRTUAL_LEAD`'s empty Level cell is the claim, not an omission.** It carries L3's
*direction* — virtual → real — without the *validation gate* that defines L3 in charter §2
and in the `CLOSED_LOOP` row above. A mode says where commands enter and where they land; a
level says where information flows from and what was proven before it did, and the two are
not the same axis. **Nothing in this project may cite this mode's existence as a maturity
claim** ([ADR-0011](../adr/0011-twin-maturity-model-and-modes.md), amended 2026-08-29;
[ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 2, which
carries the reasoning and the rejected alternative). In Phase 2.A the far side is a second
simulation rather than hardware, so the level is L0 whichever mode is in force.

**Two documents carry the gate. Five define an L3, and the gap between those numbers is
what nearly falsified the argument.** Charter §2 and the `CLOSED_LOOP` row above are the two
that name the validation gate, and ADR-0011's amendment and ADR-0041 Decision 2 both rest on
exactly those two. **Neither record surveyed the other three, and all three defined L3 by
data flow alone:** [`docs/onboarding/glossary.md`](../onboarding/glossary.md), which said
*"gates **or** commands"* while its own opening claims that when it conflicts with any other
use in the repository, **it** wins; [`standards-alignment.md`](standards-alignment.md),
whose table classifies on Kritzinger's flow-automation axis; and ADR-0011's own level table,
which that record already names as not closing the argument. The first two were corrected on
2026-08-29 and now cite charter §2 instead of paraphrasing it.

**The conclusion held; the inventory did not** — so what a later change owes this argument is
a re-count, not a re-reading. `grep -rn 'Closed loop\|CLOSED_LOOP' docs
what-we-are-doing.md` is the instrument; it also returns `CLOSED_LOOP` as a mode name and
"closed loop" in ADR-0038 and ADR-0039 meaning an L4 control-flow dead end, so the hits are
sorted by hand rather than counted. Every hit that defines the **level** must either carry
the gate or say which axis it is classifying on. If one is ever left carrying the direction
alone, ADR-0011's amendment fails and this mode has to be re-argued.

**Two of those sentences are now held mechanically, and an editor moving either cell should
know it before moving it.** [`tools/tests/test_twin_mode_enumerations.py`](../../tools/tests/test_twin_mode_enumerations.py)
asserts that the `CLOSED_LOOP` row above still reads *"commanded after virtual validation
gates it"* against level `L3`, that `VIRTUAL_LEAD`'s Level cell is still exactly the em-dash,
and that charter §2's L3 row still carries *"validated in simulation and then commands"*. It
also parses the mode set out of `TwinMode.msg` and requires the table above, the glossary's,
charter §3.1's scope row, charter §5's mode table,
[`docs/interfaces/README.md`](../interfaces/README.md)'s quoted constant block and the frozen
interface baseline to name exactly those modes and no others. **It does not re-do the survey
above** — it holds the conclusion, not the inventory — and the sites it deliberately cannot
see, `DivergenceMetrics.msg` chief among them, are listed in its docstring.

Mode is **explicit, observable at runtime, and gated.** It is never reachable by a default
parameter, an environment variable, or a launch-argument default. A system that can enter
`REAL` because someone forgot to pass an argument is a system that will.

`safety-auditor` audits every transition. `SIM` → `REAL`, entry to `CLOSED_LOOP`, and entry
to `VIRTUAL_LEAD` **against a real far side** are the three that matter most. **The
criterion the three share is stated once, in
[cross-cutting-safety.md](cross-cutting-safety.md)** — a transition qualifies when it places
physical actuation under an authority that was not previously commanding it — and this list
cites it rather than restating it, so that a fourth candidate can be judged against a
criterion instead of compared to these three.
**None of the three is refused at the point of transition today.**
`require_hardware_opt_in` and `CITE_ALLOW_HARDWARE` bind at bring-up, so what they buy is
that the stack could not have started with a physical backend; `SetMode.srv`'s header
commits the L5 server that will eventually serve this transition to applying the same check
there, and no such server exists. See
[cross-cutting-safety.md](cross-cutting-safety.md), which carries the same three and the
same residual.

### Divergence measurement is the point

P8: *the twin measures itself.* An unmeasured claim of fidelity is not a claim.

| Metric | What it catches |
|---|---|
| Joint position RMSE | Kinematic and control-tracking mismatch |
| TCP pose error | Accumulated kinematic error where it actually matters |
| Velocity profile deviation | Dynamics and inertia modelling errors |
| Cycle-time delta | Systematic timing and throughput mismatch |
| Event-timing deviation | Sensor and orchestration mismatch |

Each is published continuously, recorded by L6, and trended by L7. **"Our twin is
accurate" is not a sentence this project is allowed to write without a number next to it.**

### Registration is what makes measurements transferable

Without registration the model is a nice picture. With it, a measurement in the model
predicts a measurement in the building.

Registration establishes the transform between the surveyed physical origin and the model
origin, ties scanned geometry ([L1](L1-description-and-assets.md)) to that frame, and is
**re-verified**, not assumed permanent — floors settle, fixtures get bumped, robots get
remounted. A drifted registration presents as a slowly growing divergence with no software
cause, and is one of the harder faults to diagnose without this metric.

### Time

Mirroring across two clocks is meaningless without a shared time base. Simulation uses
`use_sim_time`; hardware uses wall time; comparing them requires an explicit, documented
correspondence and clock synchronisation (NTP at minimum) on the physical side. A mixed
time base produces divergence numbers that look plausible and mean nothing.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Mode reachable by default | Real arm moves during what someone thought was a simulation | `safety-auditor` — Critical |
| Registration drift | Divergence grows with no software change | Trend monitoring; periodic re-survey |
| Clock skew | Divergence metrics plausible but wrong | Explicit time-base check in the monitor |
| Mirroring lag treated as divergence | Model blamed for a network problem | Latency measured and reported separately |
| Divergence published but never watched | The twin is "accurate" because nobody looked | L7 trending; alert thresholds |
| Fidelity claimed without a metric | The project's core claim becomes unfounded | P8; review |

## Open questions

- **Divergence thresholds.** What error is acceptable is an empirical question that needs
  real hardware. Until Phase 2 we can only build the measurement, not set the bound.
- **Mirroring transport.** Whether physical state reaches the virtual model over plain ROS
  2 across the lab network, or needs a dedicated bridge with its own QoS and latency
  budget.
- **What `CLOSED_LOOP` validation actually checks** before permitting physical execution.
  This is the crux of L3-level maturity and deserves its own ADR when Phase 5 approaches.
- **Whether divergence is defined under `VIRTUAL_LEAD`.** Both sides move, so the metric is
  in principle computable — but nothing mirrors back, and `DivergenceMetrics.msg` enumerates
  `SHADOW` and `VALIDATED` as modes it is meaningful in without claiming the list is
  complete. Whether `valid` is true in this mode is undecided; ADR-0041 does not decide it
  and neither does this document. Until it is decided, the message's general rule governs —
  `valid` is false whenever the mode makes divergence undefined — and that rule answers the
  question conservatively rather than pre-empting it.
- **Whether the far side's backend should be observable alongside the mode.** The other two
  dangerous transitions are self-identifying from the requested value alone: `REAL` and
  `CLOSED_LOOP` mean physical actuation whoever asks. **`VIRTUAL_LEAD` does not.** Its
  danger condition is *against a real far side*, which is a per-(asset, side) backend fact,
  and `TwinMode` carries no such field — so an operator watching `/cite/twin/mode` cannot
  tell "the arm is driving a second simulation" from "the arm is about to move a physical
  arm". This is filed, not decided: whether the backend belongs on `TwinMode`, on a separate
  topic, or nowhere is open. What is **not** open is that the `SetMode` server, when it
  exists, must resolve the far side's backend per asset before it decides the transition —
  and for a facility-wide request that means every asset. See
  [cross-cutting-safety.md](cross-cutting-safety.md) and `SetMode.srv`'s header.
- **Multiple physical assets, partially twinned.** With one real arm and two simulated,
  what does a facility-level divergence number even mean? Probably per-asset metrics with
  no aggregate — but it needs deciding rather than defaulting.
