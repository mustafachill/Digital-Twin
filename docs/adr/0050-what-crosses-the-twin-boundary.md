# ADR-0050: Cross the twin boundary in L5's own memory, and say when a divergence number may be believed

- **Status:** Proposed — **nothing in this record is implemented, and the tree state it is
  written against is this.** Established against the checkout rather than taken from another
  document:

  | Claim | Established by |
  |---|---|
  | `cite_twin` does not exist; `workspace/src` holds ten packages and none of them is it | `ls workspace/src` |
  | Nothing publishes or subscribes `DivergenceMetrics`, and nothing serves `SetMode` | `git grep -n 'DivergenceMetrics\|SetMode' -- workspace tools tests scripts` reaches the definitions, the `CMakeLists.txt` entries, `interfaces.baseline`, `cite_interfaces/README.md`'s own **"nothing — L5 does not exist"** row, and one test docstring — no endpoint of any kind |
  | [L5](../architecture/L5-twin-synchronization.md) is `DESIGNED` | `head -3 docs/architecture/L5-twin-synchronization.md` |
  | The shipped model is not paired | `model/facility/zones.yaml:22-23` declares `twin: {sides: single}` |
  | `/cite/twin/` is reserved for this layer and has no publisher | [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md) lines 8-9 and 118 |

  So every "will", "must" and "may not" below is a commitment rather than a description.
  **Promoted to `Accepted`** by the change that first computes a `DivergenceMetrics` from two
  sides under decision 3's rule, with all three of: a test that `valid` is false in every mode
  this record says it is false in, and true in none of them by default; a test that no L5
  endpoint republishes any message onto a side under a name that side already owns (decision 1,
  clause 3); and the interface change decision 5 names, taken consciously with
  `cite_interfaces/test/interfaces.baseline` regenerated and the reason in the commit message.
  **Promotion is not a claim that any number is a fidelity number** — see *What this record
  does not claim*, which is a permanent clause and not a status caveat.
- **Date:** 2026-08-31
- **Deciders:** Docs-writer agent, from the three deferrals that name L5 by name:
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s `SHADOW` fork,
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md)'s *"the mirroring mechanism"* and
  *"the divergence metric"*, and [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md)
  decision 3's *"where that value rides, and what it is called, is L5's"*. **The clauses that
  refuse to weaken P8 are not this agent's** — they are charter §4 and
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s *What 2.A cannot claim*,
  restated in force here because this is the record most likely to be misread as making the twin
  real. Everything else is owed the project owner's ratification.
- **Related:** [ADR-0011](0011-twin-maturity-model-and-modes.md) (the mode set, and the maturity
  ladder whose L1/L2 rows decision 3 reads a flow off),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) (Decisions 2 and 3, and the
  fork it named and refused to pick),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) (which refused to slave one side's clock
  to the other — the reason decision 3's pairing key is the wall clock),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) (clause 3, which makes L5 the only
  cross-domain component, and the transport candidates it named with a criterion),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md) (clause 2's boundary, which
  this record uses to refuse a mode that instantiates),
  [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) (decision 3, which gates the
  reading of a divergence number),
  [ADR-0027](0027-pilz-planning-pipeline.md) (whose stated non-result is decision 2's sharpest
  hazard),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md),
  [ADR-0010](0010-typed-ros-interfaces.md), [ADR-0025](0025-qos-profiles-in-cite-interfaces.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md),
  [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md),
  [`qos-profiles.md`](../interfaces/qos-profiles.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  charter §4 (P1, P2, P3, P7, P8, P9), charter §8 (Phase 2)

## Context

### What is already fixed, and is cited rather than re-argued

Four records close four questions this one would otherwise have had to open, and none of them
is reopened here (P1 — read them there):

- **Both sides carry byte-identical names and are separated by `ROS_DOMAIN_ID`**, and **L5 is
  the only component with endpoints in both domains** — anything else in the running system that
  observes both sides is a defect ([ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  clauses 1 and 3).
- **The pair is joined, not sequenced.** Neither side's bring-up depends on the other's state,
  and the thing that joins them observes processes and holds no ROS context
  ([ADR-0047](0047-two-independent-launches-joined-not-sequenced.md)).
- **2.A produces no fidelity measurement.** Both sides run the same L0 model and the same solver
  ([ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)).
- **The reading of a divergence number is gated on a real-time question that is open**, and the
  work continues while the reading does not
  ([ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) decision 3).

### One derivation this record needs, and it is a derivation rather than a new choice

`TwinMode`'s rows are written in terms of a **physical** side and a **virtual** side. The tree's
side names are **`plant`** and **`counterpart`**, defined structurally
([ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 3). Nothing has
ever said which maps to which, and every clause below depends on it.

It follows from a refusal already in the schema. ADR-0041 Decision 3's third clause refuses
`hardware.backend: real` on a zone declaring `twin.sides: pair` — the refusal is
`physical-plant-on-paired-zone` in `tools/cite_tools/validate/referential.py`. **So on a paired
zone the plant is always `sim`, and a physical side, if one exists, is always the counterpart.**

> **The mode table's "physical" side is the `counterpart`; its "virtual" side is the `plant`.**

This is not a preference and it is not reversible by anything short of reopening that refusal.
It also agrees with the two records that already assume it:
[ADR-0044](0044-one-ros-domain-per-side-identical-names.md) clause 5 puts the operator on the
plant's domain, and ADR-0041 Decision 2's target mode is an operator commanding the simulated
side while the far side actuates.

**One consequence has to be met head-on rather than discovered later:** in `SHADOW` the side
that *follows* is the virtual side, and the virtual side is the **plant** — the full Phase 1
cell, the side every scenario and script addresses. Decision 4 is where that lands.

### What was measured about crossing a boundary

[`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md)
priced the crossing (its Q5) and priced a physics-free following side (its Q4). **Its figures
are held there and are not copied here** (P1). What this record takes from it is three shapes:

- **The rig that priced the crossing is the mechanism this record chooses.**
  [`harness/mirror_latency.py`](../measurements/2026-08-28-second-world-cost/harness/mirror_latency.py)
  is one process holding two `rclpy` contexts at two domain ids, publishing and subscribing on
  **one topic string on both** — `TOPIC = "/cite/cell_a/arm_1/joint_states"`,
  `MIRROR_TOPIC = TOPIC`. It ran in this repository, on one host, in one network namespace, and
  its message counts are exact: nothing arrived twice. It is a demonstration that identical
  names in one process do not leak between contexts, and it is a demonstration that one process
  can carry the plant's own joint-state rate across the boundary.
- **The crossing is not what will make mirroring late.** The campaign's own reading, restated by
  ADR-0043 and ADR-0049, is that the real-time deficit overtakes the crossing latency within the
  first tens of milliseconds of a run and then accumulates. **The transport is the cheap term.**
- **The rig relays a topic and decides nothing.** It copies `JointState` from one context to a
  publisher on the other. Every question below — which mode, which direction, is this sample
  paired, is it valid — is a question it never asks. That is the gap between what was measured
  and what L5 is.

### The metric's own header answers a question this record was asked to decide

`cite_interfaces/msg/DivergenceMetrics.msg` states a rule — *"`valid` is false whenever the mode
makes divergence undefined, and when it is false the fields are zero"* — and then names
`SHADOW` and `VALIDATED` as the modes it is meaningful in, twice saying the list is partial and
filing `VIRTUAL_LEAD` as an open L5 question. [L5](../architecture/L5-twin-synchronization.md)
files the same question. `tools/tests/test_twin_mode_enumerations.py`'s docstring records that no
parser reaches that file and that **what would settle it is L5 answering, not a regular
expression**. This record is that answer.

### What exists to answer it with, and what does not

Nothing measures a real-time factor or a clock deficit during a run
([ADR-0049](0049-measure-the-real-time-floor-as-capacity.md)'s status block establishes it), the
deficit bound is deliberately unset there, and no divergence threshold can be set before
hardware exists (L5's own open question). **A record that waited for those would decide nothing
and would leave the message's comment deciding the architecture by exclusion.** So this record
decides the *shape* of the answer — what the number is, and the conjunction that has to hold
before it may be read — and lets the missing terms make it unreadable by construction rather
than by discipline.

## Options considered

### For the mechanism

#### Option A — `domain_bridge` on its configuration path

An upstream package whose stated purpose is bridging ROS communication between domain ids, run
as `domain_bridge <config.yaml>`, with the topics to carry named in data. It needs no code at
all, and ADR-0044 verified that `ros-jazzy-domain-bridge` resolves in the Jazzy image.

**Rejected, and the coverage question ADR-0044 left open is answered rather than assumed.**

> **Verified 2026-08-31 against the installed package, not the README.**
> `docker run --rm ros:jazzy-ros-base-noble` with `apt-get install -y ros-jazzy-domain-bridge`
> installs `0.5.0-5noble.20260612.125528`. In that install:
> - `/opt/ros/jazzy/include/domain_bridge/domain_bridge_config.hpp` defines
>   `struct DomainBridgeConfig` with exactly two members — `DomainBridgeOptions options` and
>   `std::vector<std::pair<TopicBridge, TopicBridgeOptions>> topics`. **There is no service or
>   action member**, so the YAML/CLI path carries topics and nothing else. The shipped
>   `share/domain_bridge/examples/example_bridge_config.yaml` agrees: its keys are `name`,
>   `from_domain`, `to_domain` and `topics`, and there is no key for any other entity type.
> - `domain_bridge.hpp` declares `bridge_topic()` non-template, and `bridge_service()` as
>   `template<typename ServiceT>`, implemented in `service_bridge_impl.inc`. **Service bridging
>   is a compile-time C++ API, not a configuration entry.**
> - Excluding `rosidl`-generated headers, `grep -rn -i action` over
>   `/opt/ros/jazzy/include/domain_bridge/` returns **no** action-bridging declaration. **A
>   survey of the installed headers on this date found no action support**; this is what the
>   survey found, not a proof that none can be built.

L3's contract is six actions — `MoveTo`, `Pick`, `Place`, `Transfer`, `Grasp`, `Detect` — and
`SetMode` is a service. So the entity types L5 must carry across are precisely the two this path
does not carry.

#### Option B — `domain_bridge` as a library, with `bridge_service<ServiceT>` for services

Same package, linked rather than configured, so that services are reachable. It removes Option
A's coverage objection for services and leaves the action one standing.

**Rejected on ADR-0044's own criterion, which is stronger than the coverage question and is why
that criterion was written:** *a bridge copies; it cannot refuse, transform, timestamp or gate.*
Every one of those four verbs is load-bearing below. `SetMode` must be **refused** against a real
far side (`cross-cutting-safety.md`, `SetMode.srv`'s header). A mirrored sample must be
**timestamped on arrival**, because that stamp is the term that separates a slow network from a
wrong model (decision 3). Command routing must **gate** on mode, which is the whole of decision
2. A component that copies is a component that has already answered "yes" to every question L5
exists to ask.

There is also a naming consequence that disqualifies the copy on its own, and it is Option C's
subject.

#### Option C — a bridge in either direction, with a remap to avoid the collision

Both sides carry byte-identical names (ADR-0044 clause 1). So a bridge carrying the
counterpart's `/cite/cell_a/arm_1/joint_states` into the plant's domain publishes onto **the
topic the plant's own `joint_state_broadcaster` owns** — a second publisher of a name that
already has one, feeding every consumer on that side a mixture of two cells. `domain_bridge`
offers `remap:`, so the escape exists: land it as some second name.

**Rejected.** The remap is the second form of a name that ADR-0044 Option A was rejected for
introducing, arriving by another road and inside the one component that is supposed to make the
two sides interchangeable. And it hands a mirrored stream to consumers that never asked for one:
anything on the plant subscribing to the remapped name is a second cross-domain observer wearing
a local name, which is the defect ADR-0044 clause 3 names.

The clause that survives from this option is decision 1's third: **nothing is republished across
the boundary at all.**

#### Option D — two single-domain processes joined by a private channel

One process per side, each holding one context, exchanging over a private channel between
themselves. It keeps every process on one domain, which is a real property: nothing has to reason
about which context a call is on.

**Rejected on P3.** The private channel is an interface — the twin's most important one — and it
is not a `.msg`, `.srv` or `.action` in an interface package, so `ros2 interface show` cannot
discover it and nothing can regression-check it. It also just moves the decision: the two halves
must agree about mode, pairing and validity, so the deciding is now split across a boundary
nobody can inspect, and the failure mode is two halves in different modes.

#### Option E — one process, two contexts, deciding in the middle

Chosen.

### For the metric

#### Option F — close the question the way the header's list implies

Read `DivergenceMetrics.msg`'s *"meaningful in SHADOW and VALIDATED"* as the answer: valid in
those two, invalid elsewhere, `VIRTUAL_LEAD` excluded because it is not in the list.

**Rejected, and the file itself rejects it** — it says twice that the list is an illustration and
a partial one, and instructs a reader not to read it as having answered by exclusion. It is also
wrong on `SHADOW`, for the reason decision 3 gives, and being wrong in a comment that no test
reaches is exactly how it would have survived.

#### Option G — leave it open, as three documents currently do

Defensible while nothing implements L5. **Rejected because the tree forces it now**: the first
change that writes a monitor must put a boolean in a field, and if this record does not decide
it, that change decides it — in code, in a `Proposed`-status vacuum, with the message's
conservative default as cover.

#### Option H — decide each mode on its merits, one row at a time

**Rejected because a per-row answer does not survive a seventh mode**, and this project has
already added a sixth. A rule that decides rows the author has not seen is what the message's own
header asks for in as many words.

#### Option I — one rule about where each side's state came from

Chosen. Decision 3.

## Decision

Five clauses. The first four are the questions the deferrals named; the fifth is what they cost
the typed contract.

### 1. L5 is one process per zone holding one ROS context per side, and nothing is republished across the boundary

**The mechanism is contexts in one process.** In Python
`rclpy.init(context=..., domain_id=N)` per side; in C++ `rclcpp::InitOptions::set_domain_id`,
which ADR-0044 verified is declared in the Jazzy image. The domain for each side is obtained from
ADR-0044 clause 4's single resolver — base plus the plan's stated offset — **by side name and
never by list position**, and L5 recomputes that arithmetic nowhere.

Three sub-clauses, because a mechanism that does not say what it refuses is a mechanism that will
be extended by whoever needs one more thing.

**1a. `domain_bridge` is not used, and the door is left open on a stated condition.** It is
refused for everything L5 does today, on Option B's criterion rather than on its coverage. If a
future need is genuinely a *copy* of a *topic* onto a name **no side already owns**, its topic
path is verified above and it may be taken with an argument. Its service path costs a compile-time
type and its action support was not found; either of those changing is a reason to re-read this,
not a reason to assume.

**1b. What crosses the boundary crosses in L5's own memory.** A message arriving on one side's
context is consumed by L5. It is not forwarded to a publisher on the other side's context, under
its own name or any other, in any mode. **The only things L5 publishes on a side are its own
products** — mode, divergence, twin health — under `/cite/twin/...`, the scope
[`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md) already reserves for this
layer, and **commands, in the one mode that has a command flow** (decision 2).

**1c. One TF buffer per side, keyed by side.** Both sides broadcast identical frame ids
(ADR-0044 clause 1 and its cost list). Feeding both trees into one buffer produces a tree whose
transforms silently come from either cell. Any pose L5 computes names the side it was computed
on.

**Where L5's own outputs are published: the plant's domain.** `TwinMode` and `DivergenceMetrics`
go to the side the operator is on (ADR-0044 clause 5), and `SetMode` is served there. They are
**not** also published on the counterpart's domain, because no component on either side routes on
mode — L5 is the only thing that does, by clause 3 of ADR-0044 — so a second publication would be
one value in two graphs for no reader. **Reopening condition:** 2.B, where the counterpart is a
physical cell that an engineer may be standing next to, working on that domain. Decide it then,
with a reader named.

**QoS is declared, and a subscriber match is an event.** L5's cross-domain subscriptions take the
profile the publisher offers — the mirroring rig matched `joint_state_broadcaster`'s deliberately,
and an easier profile measures a transport this project does not use. L5's own publishers follow
[`qos-profiles.md`](../interfaces/qos-profiles.md): `LATCHED` for mode, `STATE` for divergence.
**Nothing L5 publishes is sent from the callback that created the publisher** (CLAUDE.md §10 —
this project has already lost a belt setpoint to that exact defect).

### 2. What crosses, per mode — and in `VIRTUAL_LEAD` it is the goal and never the motion

With the plant as the virtual side and the counterpart as the physical one (*Context*):

| Mode | plant → counterpart | counterpart → plant | Both sides evaluate the same command? |
|---|---|---|---|
| `SIM` | nothing | nothing | no — the counterpart is idle |
| `REAL` | nothing | nothing | no — the plant is idle |
| `SHADOW` | nothing | **state**, consumed by L5 | no — the plant's state is *derived from* the counterpart's |
| `VALIDATED` | **the goal**, if it entered on the plant | **state**, consumed by L5 | **yes** |
| `CLOSED_LOOP` | **the goal**, after a gate this record does not define | state | not decided — see below |
| `VIRTUAL_LEAD` | **the goal** | **nothing** | yes, and no operand comes back |

**The command that crosses is an L3 goal, at the action boundary, and nothing below L3 ever
crosses.** No trajectory, no joint command, no controller setpoint. Three reasons, in order of
force:

- **2.B.** The far side becomes hardware by one data change, and hardware's entry point in this
  project is the same typed L3 action server on the same name (P2, P9). A design that streamed a
  trajectory would be a design 2.B has to break, which is the test ADR-0044 and ADR-0047 each
  used to kill their cheapest option.
- **Layering.** L5 routes and observes; L2 executes (L5's *Does not own*). A trajectory crossing
  the boundary makes L5 a control path.
- **The clock.** At any real-time factor below 1.0 a side's clock falls behind wall clock without
  bound ([ADR-0049](0049-measure-the-real-time-floor-as-capacity.md)). A far side driven from the
  near side's *motion* would be executing an arbitrarily old stream, and in 2.B that far side is
  an arm in a room. A goal has no such property: it is evaluated when it arrives.

**In `VIRTUAL_LEAD` the operator's command enters L5 and not the plant's skill server.** It
cannot enter the plant's skill server and be observed there: both sides carry identical names, so
L5 cannot serve `/cite/cell_a/arm_1/move_to` beside the plant's own server, and reading another
server's goals is not something the action protocol offers. So the mode's own words — *where an
operator's command enters* — are made true by an endpoint under `/cite/twin/`, and L5 dispatches
to the plant's L3 and the counterpart's L3. It does **not** gate the far side on the near side's
outcome: that gate is what `CLOSED_LOOP` is, and this mode is defined as being without it.

**The hazard this creates is named here rather than found later.** Both sides plan the goal
independently, through their own `move_group`. [ADR-0027](0027-pilz-planning-pipeline.md)
establishes that an identical request returns a byte-identical trajectory **from one
`move_group`**, and records that *same seed, same trajectory across runs* is **not** established.
**So the operator watching the plant is not, on this evidence, watching the path the far arm will
take** — only the endpoint it will reach. Against a real far side that is a property of the mode
and not a defect in it, and it is one more reason entry to `VIRTUAL_LEAD` against a real far side
sits on the three-transition list in
[`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md). The alternative — cross the
*planned trajectory* so both sides execute one path — buys path identity and pays for it by
bypassing the far side's own collision gate against its own planning scene, and by putting a
`FollowJointTrajectory` client in L5. **It is not taken here.** It is the option to re-argue if
path identity is ever required, and it needs its own record.

**The action's own result and feedback path is not a reverse state flow.** An action client
receives them by construction; that is the forward call returning, not a mirror. It carries no
joint state and cannot supply the metric's second operand. Nobody may cite it as reopening
decision 3 for `VIRTUAL_LEAD`.

**`/clock` never crosses, in any mode.** ADR-0043 refused slaving one side's clock to the other's,
and decision 3's pairing key depends on that refusal holding.

### 3. A divergence number is a comparison of two independently evaluated states, and `valid` is a conjunction

**The rule, which decides every mode including modes added after this record:**

> A divergence sample is defined only when the two states being compared were produced by
> **independent evaluation of the same command** over the same interval. If either side's state
> was derived from the other side's state, the comparison measures the derivation.

And the conjunction. `valid` is true only when **all** hold:

1. **The mode defines the comparison** — the rule above, applied to the mode in force.
2. **Both operands were present and paired within a stated window**, on the **wall clock**. The
   pairing key is wall clock and not either sim clock, because the two sim clocks are independent
   and separate without bound (ADR-0043, ADR-0049), and because in 2.B the far side's clock *is*
   the wall clock.
3. **Both sides' clock deficit over that window was measured and is within the bound**
   [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) decision 1 leaves unset. This is
   that record's decision 3 made structural: a term with no instrument makes `valid` false, so
   the gate is arithmetic rather than a warning in prose.
4. **Both sides report the same `model_version`.** The field already exists and already says a
   comparison across model versions is not valid.
5. **The two frames correspond.** In 2.A both sides are generated from one L0 model, so the
   correspondence is identity and this term is trivially met — **and it stops being trivial in
   2.B**, where it is the registration transform, which does not exist and whose survey charter §8
   puts in Phase 3.

Applying the rule, mode by mode, in the values a monitor writes:

- **`SIM`, `REAL` — `valid` false.** One side is idle; there is no second evaluation.
- **`SHADOW` — `valid` false, and this contradicts the message's own header.** In `SHADOW` the
  virtual side *follows the physical side's state*: its state is derived from the other's, so by
  the rule the comparison measures the mirror and the follower's own tracking law, entangled, and
  not the model. **ADR-0011's level table says the same thing and nobody read it that way**: its
  L1 *Shadow* row is `real → virtual`, and *"divergence measured"* appears one row down, at L2
  *Validated*, as the refinement that distinguishes them. A metric that were meaningful in
  `SHADOW` would collapse that distinction. What `SHADOW` **does** produce is the mirror's own
  timing, which is a real quantity and is published as the condition terms in decision 5 — the
  campaign's Q5 recommendation, arriving as the mode's product rather than as a caveat.
- **`VALIDATED` — `valid` may be true**, and it is the only mode in which it may be true today.
  Both sides receive the same goal and each evaluates it; the reverse state flow supplies the
  second operand.
- **`VIRTUAL_LEAD` — `valid` false, and the reason is structural rather than semantic.** Both
  sides do evaluate the same goal, so term 1's *rule* is satisfied — and the mode is **defined**
  by there being no reverse flow (`TwinMode.msg`: *"No reverse flow behind it — that is
  SHADOW"*). **The metric's second operand does not exist.** The number is not undefined in
  principle; it is uncomputable in this mode by the mode's own definition. **L5 may not quietly
  open a reverse state flow to make it computable.** `VIRTUAL_LEAD` plus a reverse state flow is
  a mode the published set does not contain, and adding one is an argument in the mode set —
  ADR-0011 and ADR-0041 Decision 2 are the precedent — never a decision taken inside a monitor.
- **`CLOSED_LOOP` — not decided here; the default rule governs, so `valid` is false.** Its flow
  is `VIRTUAL_LEAD`'s plus a gate, and **what that gate checks is an open question that L5's own
  document files for Phase 5 and says deserves its own ADR**. A validity answer that depends on
  an undefined gate would be an answer to a different question.

**One more clause, decided rather than defaulted:** `DivergenceMetrics.asset_id` is **never
empty**. There is no facility-level divergence number. Validity is per asset — term 3 is per
side, and whether a far side is physical at all is a per-`(asset, side)` fact (ADR-0041 Decision
3) — so an aggregate would average numbers whose terms differ. This closes L5's open question
*"with one real arm and two simulated, what does a facility-level divergence number even mean"*
in the direction that document guessed, with a reason rather than a default. Note the asymmetry
with `TwinMode`, whose `asset_id` **is** empty for facility scope: a mode is a facility fact and
a divergence sample is not.

### 4. The mode does not decide whether a simulator exists, and the `SHADOW` fork stays open — restated

**Decided: instantiation is a bring-up fact and mode is a runtime knob, so no `SetMode` call ever
starts or stops a simulator.** Three independent reasons, any one sufficient:

- ADR-0041 Decision 3 states the test that classifies a field: *if changing it requires a
  regeneration to take effect, it describes the system; if a service call flips it, it runs the
  system.* A counterpart's shape is generated (its world, its controller managers, its plan
  entry). Mode is the service call. They are on opposite sides of that line.
- **L5 may not start processes.** ADR-0047 clause 2 gives process supervision to a component that
  holds no ROS context and is explicitly not L5, and defines L5 by *deciding what crosses*.
- ADR-0047 clause 1 makes each side's bring-up independent of the other's state. A mode that
  instantiated a side would make one side's existence depend on a runtime decision taken by a
  component downstream of both.

**Not decided: whether a deployment whose only mode is `SHADOW` ships a physics-free following
side.** ADR-0041 named this fork on measured grounds, refused to pick, and forbade any later
document from citing it as having picked. This record does not pick either — and it **restates
the fork, because the way it is usually stated has the sides the wrong way round**:

> The cheap side in `SHADOW` is the side that **follows**, and by the derivation in *Context* the
> following side is the **plant** — the full Phase 1 cell, the operator's side, the side every
> scenario addresses. It is not the counterpart.

The campaign's Q4 rig measured a full cell leading and an echo following, which is the right
*cost* comparison and does not depend on what the two sides are called; ADR-0041's gloss on it
speaks of "a `SHADOW` counterpart", which under the tree's own side naming is the leading side.
**The cost figure survives the correction and the architectural reading does not**: what the
measurement licenses is *"a following side needs no physics"*, and in this deployment that
sentence is a proposal to shrink the plant.

**Why it cannot be decided in 2.A at all.** `SHADOW` is defined by an information flow from the
physical side (ADR-0011), and 2.A has no physical side. A simulation shadowing a simulation is
not the mode being rehearsed. **The evidence that decides this fork is 2.B's**, and it is the
first deployment in which `SHADOW` means anything.

**What L5 owes now so the fork stays cheap:** the far side's shape must be a fact L5 can *read*
at start-up, so that `SetMode` can **refuse** a mode the running deployment cannot support —
rather than accepting it and producing an invalid metric forever. Where that fact lives is L0's
question and touches [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md)'s
unimplemented clause 2; the natural home is beside `counterpart_backend` in the generated plan,
and this record names the requirement without choosing the spelling.

### 5. What this costs the typed contract, stated as an obligation on the implementing change

**This record edits no interface**, because an ADR precedes implementation (charter §12) and
because a message describing behaviour no code has is the false attestation P7 exists to prevent.
The change that implements decision 3 owes four things:

**5a. A correction to `DivergenceMetrics.msg`'s header**, removing `SHADOW` from the modes the
metric is said to be meaningful in and recording the decision above and its reason. **This does
not move `interfaces.baseline`**: that baseline stores field and constant lines with comments
stripped — `cite_interfaces/test/test_interface_contract.py`'s own docstring says *"reformatting a
definition or rewriting its comments does not fail this test"* — which is exactly why the wrong
sentence could sit there unguarded.

**5b. The condition terms, as fields, which do move the baseline.** A sample must carry the terms
that decide its own validity, for the same reason `model_version` is already on it: a recording
outlives the tree it was taken from, and L6 records this. Specified, not shipped — the spelling is
the implementing change's:

```
float64 plant_sample_age_s        # wall-clock age of the plant's operand at the
float64 counterpart_sample_age_s  # comparison instant, and the counterpart's
float64 plant_clock_deficit_s     # wall time minus simulated time, per side,
float64 counterpart_clock_deficit_s   # over window_s (ADR-0049 decision 1)
float64 window_s                  # the window the deficits were measured over
bool far_side_physical            # whether this asset's far side actuates hardware
```

**These ages are not the one-way transport latency the campaign measured, and must never be
labelled as one.** That quantity needs a common source clock; the two sides do not have one, and
ADR-0043 refused to give them one. What L5 can measure is when each operand arrived at L5 by its
own host clock, and the difference between the two ages is the wall-clock skew of the pair — which
is the quantity that separates L5's *"mirroring lag treated as divergence"* failure row from a
model error.

**5c. A refinement of the header's zeroing rule.** *"When it is false the fields are zero"* must
apply to the six comparison fields and **not** to the condition terms. An invalid sample whose
terms are also zeroed is indistinguishable from a dead publisher, and the terms are how a reader
learns **which conjunct failed**.

**5d. A `string TOPIC` constant on `TwinMode` and on `DivergenceMetrics`.** `LineState` and
`LineTopology` already carry theirs, so the name exists once and a consumer reads it off the
message. `/cite/twin/mode` and `/cite/twin/divergence` are today written in prose in
[`bring-up.md`](../operations/bring-up.md) and
[`recording-and-replay.md`](../operations/recording-and-replay.md) and nowhere in the contract —
one value in two documents, waiting for a third.

## What this record does not claim

**No number produced in Phase 2.A is a fidelity result, and none may be published as one under
P8.** This is ADR-0041's clause, in force here unweakened, and it is restated because this is the
record a reader is most likely to mistake for the twin becoming real.

- **`valid` does not mean "true of reality". It means the arithmetic was defined and its terms
  were measured in this window.** Whether a defined number is a *fidelity* number is a separate
  predicate, answered by `far_side_physical`, and in 2.A its answer is always **no**: both sides
  run the same L0 model, the same generated description, the same controllers and the same
  solver, so what is being compared is a thing with itself. A 2.A divergence plot is a test of the
  instrument, and anyone presenting one must label it as one.
- **Nothing here moves a maturity level.** 2.A has no physical side, so it is level L0 whatever
  mode is in force, and the existence of a mode is never a level (ADR-0011's amendment).
- **No number is readable today at all**, and that is structural rather than rhetorical: term 3
  of the conjunction has no instrument in the tree and no bound, so `valid` cannot be true until
  ADR-0049's decision 5 instrument exists and its bound is set. **A monitor built to this record
  and run tomorrow publishes samples that are all invalid, each carrying the term that failed.**
  That is the intended behaviour, not a defect to be worked around by relaxing a term.
- **Nothing above is a measurement.** The only figures this record rests on are the campaign's,
  cited and not copied, and it takes no new ones.
- **`./scripts/lint` and `./scripts/doctor` passing on this change says nothing about L5.** They
  check that documents lint and that ADRs are indexed and referenced.

## Consequences

### What this gets us

- **The three deferrals that named L5 by name are answered**, and each answer is checkable
  against a test rather than a promise.
- **The 2.A shape survives 2.B.** Nothing in decision 1 or decision 2 assumes the far side is
  simulated: a goal crossing to an L3 action server is the same call whether that server drives
  `gz_ros2_control` or a physical arm.
- **P8 is enforced by arithmetic instead of by review.** The gate ADR-0049 stated in prose becomes
  a conjunct of a published boolean, and a sample that cannot support a claim says so in its own
  fields.
- **A wrong sentence in an unguarded comment is retired with a reason**, and the reason —
  ADR-0011's own ladder puts *divergence measured* at L2 — was in the tree the whole time.
- **The mode set is protected from being extended by a monitor.** The one edit that would have
  made `VIRTUAL_LEAD`'s metric computable is named in advance as a seventh mode.

### What this costs us

- **Six new fields on a frozen interface**, and the conscious baseline regeneration that goes with
  them. That is the price of a sample that can be read after the fact; it is paid once and it is
  reviewable, which is what the baseline is for.
- **L5 is a component that must be right about which context it is on, in every call.** The
  compiler and the interpreter will not help. The mitigation is that there is exactly one such
  component, by ADR-0044 clause 3 — and the cost of that mitigation is that L5 concentrates the
  whole class of defect in one place.
- **`SHADOW` ends 2.A with no implementation and no evidence.** Decision 4 declines the fork and
  decision 3 removes the mode's fidelity reading, so the first deployment that wants `SHADOW`
  meets both questions at once, in 2.B, next to hardware.
- **`VIRTUAL_LEAD` has an operator endpoint that does not exist yet**, and the plant's skill
  servers keep their own callers, so for a while there are two ways to command an arm. Nothing in
  this record stops an operator commanding the plant directly while the mode says the twin is
  leading; **what would stop it is a check nobody has designed**, and it is named as an open
  question below rather than asserted as covered.
- **A divergence monitor that publishes nothing readable for the whole of 2.A** is a difficult
  thing to defend to somebody who wanted a graph. It is the honest state, and the alternative is a
  graph nobody may cite.
- **`CLOSED_LOOP` is left with a default rather than a decision**, so a Phase 5 record has to
  return here.

### What we will have to revisit

- **When ADR-0049's instrument exists and its deficit bound is set.** Term 3 becomes satisfiable
  and the first `valid=true` sample becomes possible. That is the moment to re-read this record's
  claim that the gate is structural, because it stops being free.
- **When 2.B lands.** `far_side_physical` becomes true for one asset; registration stops being
  identity; `SHADOW` becomes meaningful; the fork of decision 4 becomes decidable on evidence; and
  the mode-to-side derivation in *Context* is tested for the first time. **If any consumer has to
  change at that point, decision 2's central claim failed and that must be written down rather
  than absorbed.**
- **If path identity is ever required in `VIRTUAL_LEAD`** — the rejected trajectory-crossing
  option, which needs its own record and an argument about the far side's collision gate.
- **If ADR-0027 ever establishes cross-run trajectory determinism**, which would shrink decision
  2's named hazard without removing it.
- **If `domain_bridge` gains an action path, or a copy-only topic need appears on a name no side
  owns.** Clause 1a is the door; the verification above is dated and names its package version.
- **When L6 begins.** How a pair is recorded is ADR-0044 clause 3's unresolved carve-out and this
  record does not touch it — but decision 5b's fields exist because L6 will record them.
- **If a zone ever runs more than two sides.** Decision 3's condition terms are named per side and
  a third side re-opens both the message and the pairing.

## What this record does not decide

- **What `CLOSED_LOOP`'s validation gate checks.** L5 files it for Phase 5 with its own ADR; the
  default keeps `valid` false until then.
- **Divergence thresholds.** What error is acceptable is empirical and needs hardware — L5's own
  open question, untouched.
- **Registration.** The transform, its survey and its re-verification are Phase 3 work; this
  record only names it as term 5 of the conjunction.
- **Whether the far side's backend belongs on `TwinMode`.** L5 files that separately, as an
  operator-visibility question; decision 5b puts the far side's backend on the *divergence
  sample* and answers nothing about the mode topic.
- **What stops an operator commanding the plant directly while `VIRTUAL_LEAD` is in force.** Named
  as a cost above; no mechanism is proposed here.
- **`cite_twin`'s language, node count and lifecycle shape.** ADR-0019 governs the language
  choice; nothing here needs it settled, and the campaign's rig cost is a Python data point on one
  arm rather than a design.
- **Whether a paired scenario exists, and what it would assert** — ADR-0047 left it open and this
  record adds nothing to it.
- **How L6 records a pair** — ADR-0044 clause 3's third carve-out, still unresolved.
