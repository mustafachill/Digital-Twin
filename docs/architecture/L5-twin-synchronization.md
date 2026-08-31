# L5 — Twin synchronization

- **Status:** `PARTIAL` — `cite_twin` exists and implements
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md); **nothing has ever run it against
  a pair.**
  **Built:** one process per zone holding one `rclpy` context per side
  (`cite_twin/twin_boundary.py`), a `SetMode` server that applies the hardware opt-in **at the
  transition** and publishes `TwinMode` latched on `/cite/twin/mode`, an action server per arm
  per skill under `/cite/twin/...` that dispatches the L3 **goal** to each side's own server
  in the modes ADR-0050's table gives a command flow, and a per-asset `DivergenceMetrics`
  publisher on `/cite/twin/divergence`. Each rule is held by a test in that package, and a
  launch test drives the node itself.
  **Not built, and read this before believing the line above.** **No bring-up starts it** —
  not `simulation.launch.py`, not `./scripts/sim`, not any scenario — and it **refuses to
  start against the shipped model**, which declares `twin: {sides: single}`. So no goal has
  crossed the boundary and no operand has ever arrived, in any run or any test; what is
  evidenced is the decision each rule makes, not the crossing. **State mirroring is not
  implemented at all** — the monitor consumes each side's joint state and nothing follows
  anything. Registration is Phase 3: every asset instance in L0 carries a `registration`
  block, `unregistered` for all three arms.
  **`valid` is false in every sample the package can produce**, by construction, and that is
  the deliverable rather than a defect — see *Divergence measurement is the point* below.
- **Related:** [ADR-0011](../adr/0011-twin-maturity-model-and-modes.md) (amended 2026-08-29), [ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md), [ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md), [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md), [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [standards-alignment.md](standards-alignment.md)

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
**All three are now refused at the point of transition by the L5 mode server, and no
deployment anyone has run starts that server.** `require_hardware_opt_in` and
`CITE_ALLOW_HARDWARE` bind at bring-up, so what they buy is that the stack could not have
started with a physical backend; `cite_twin` calls **the same function** when a transition
places physical actuation under an authority that was not previously commanding it, and
`force` cannot skip it. It is one refusal in one server and it is not the safety layer. See
[cross-cutting-safety.md](cross-cutting-safety.md), which carries the same three and states
what that refusal does and does not amount to.

### What crosses the boundary

Decided in [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) and deliberately not
restated here (P1), and implemented in `cite_twin` — with the caveat in this document's
status bullet, which is that no goal has crossed in any run. The four things a reader of
this document needs to know it says, each with the clause that carries it:

- **L5 is one process per zone holding one ROS context per side**, and **nothing is
  republished across the boundary** — what crosses, crosses in L5's own memory. `domain_bridge`
  is refused for everything L5 does today, on the criterion
  [ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md) clause 3 set: a bridge
  copies, and cannot refuse, transform, timestamp or gate.
- **The command that crosses is an L3 goal**, at the action boundary. Nothing below L3 ever
  crosses — no trajectory, no controller setpoint — and `/clock` never crosses in any mode.
- **In `VIRTUAL_LEAD` the operator's command enters L5**, under `/cite/twin/`, and is
  dispatched to both sides' L3. Both sides then plan independently, so the operator is not on
  present evidence watching the path the far arm will take; ADR-0050 carries the argument and
  the rejected alternative.
- **Which side is which is a derivation, not a choice.** On a paired zone the plant is always
  `sim`, so the mode table's *physical* side is the `counterpart` and its *virtual* side is the
  `plant`.

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

**A published number is not a readable one, and the difference is decided in
[ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md).** A divergence sample compares two
states that were **independently evaluated from the same command**; `valid` is a conjunction
over the mode, the pairing window, both sides' clock deficit
([ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md)), the model version and the
frame correspondence, so a term with no instrument makes it false. Read that record before
computing or interpreting one; it also states that `asset_id` is never empty, because there is
no facility-level divergence number.

**In the tree, `valid` is false in every sample and the clock-deficit term is why.** Nothing
measures a clock deficit and ADR-0049 leaves its bound unset, so `cite_twin` publishes
**self-describing invalid samples** rather than nothing: the six comparison fields are zeroed
by the message's own rule, and the six condition terms are not, because they are how a reader
learns which conjunct failed. Its `test_divergence.py` asserts that `valid` is false *for that
named term*, so a change which makes it true has to confront the term rather than flip a
boolean. **Four of the six comparison fields are additionally not computed at all** — TCP pose
error needs one TF buffer per side and forward kinematics, and the two timing terms need L4
line state from both sides — and while `valid` is false for every sample their zero is
indistinguishable from the rule's zero.

**Nothing above is a fidelity measurement.** Both sides of a Phase 2.A pair run the same L0
model and the same solver, so what a sample would compare is a thing with itself;
`far_side_physical` is the field that answers whether a number could ever be one, and in 2.A
it is false for every asset (P8, [ADR-0041](../adr/0041-virtual-counterpart-is-a-second-full-simulation.md)).

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

**The correspondence is decided:** two paired samples are paired on the **wall clock**, never
on either side's simulated clock, and each side's clock deficit over the window rides with the
sample ([ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 3, from
[ADR-0043](../adr/0043-hold-both-sides-to-the-wall-clock.md)'s refusal to slave one side's
clock to the other's and
[ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md)'s deficit argument).

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
- **Mirroring transport across a lab network.** The *mechanism* is decided —
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) clause 1, one process holding a
  context per side — and it was decided against a measurement taken on **one host**
  ([`2026-08-28-second-world-cost`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  its Q5). What is still open is 2.B's question: whether a physical cell on the far side of a
  lab network needs its own QoS and latency budget, which nothing has measured.
- **What `CLOSED_LOOP` validation actually checks** before permitting physical execution.
  This is the crux of L3-level maturity and deserves its own ADR when Phase 5 approaches.
- ~~**Whether divergence is defined under `VIRTUAL_LEAD`.**~~ **Decided** by
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 3: `valid` is false, and
  the reason is structural rather than semantic — the mode is *defined* by there being no
  reverse flow, so the metric's second operand does not exist. That record also removes
  `SHADOW` from the modes the metric is meaningful in, against `DivergenceMetrics.msg`'s own
  header, and puts the obligation to correct that header on the implementing change. **The
  message still carries the superseded sentence at this commit.**
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
  **One half of this is now decided and the other half is not.**
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 5 puts the far side's
  backend on the **divergence sample**, so a recording says whether it was taken against
  hardware. Whether it also belongs beside the **mode**, which is what an operator watches, is
  untouched by that record and stays open here.
- ~~**Multiple physical assets, partially twinned.**~~ **Decided** by
  [ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 3, in the direction this
  question guessed and with a reason: per-asset metrics, no aggregate, `asset_id` never empty.
  Validity is per asset because whether a far side actuates hardware is a per-`(asset, side)`
  fact, so an aggregate would average numbers whose terms differ.
