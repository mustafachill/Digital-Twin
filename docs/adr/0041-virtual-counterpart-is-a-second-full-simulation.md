# ADR-0041: Build the Phase 2.A virtual counterpart as a second full simulation

- **Status:** Proposed — the split and the target operating mode are the project owner's
  decisions and are recorded here rather than argued; **nothing in this record is
  implemented.** At `f1f914f` nothing in the tree launches a second cell, `cite_twin` does
  not exist and [L5](../architecture/L5-twin-synchronization.md) is marked `DESIGNED`,
  `TwinMode` carries five modes and no sixth, the L0 schema has no `twin:` block and
  `hardware.backend` is a scalar with no side index.
  Every "will" and "must" below is a commitment, not a description. Promoted to `Accepted`
  by the change that first brings a pair up under bring-up's own control (P7).
- **Date:** 2026-08-29
- **Deciders:** Project owner — the Phase 2.A / 2.B split, the target operating mode, and
  the decision to express it as a sixth `TwinMode` constant reachable in 2.A (Decision 2).
  Recorded by the docs-writer agent from
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  which was run to size the decision before the design fixed its shape.
- **Related:** [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0010](0010-typed-ros-interfaces.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  charter §2 (maturity levels), charter §8 (Phase 2), charter §4 (P1, P2, P5, P7, P8)

## Context

### Phase 2 was one phase and is now two

Charter §8's Phase 2 pairs the simulated cell with physical hardware, and its exit criterion
is a physical xArm 5 driving its virtual twin live, the same skill code executing unmodified
on both sides, and a quantified fidelity error defended with data. No physical arm exists in
this project today, so the whole phase is gated on hardware arriving.

The project owner has split it:

- **2.A** — the plant is paired with a **virtual counterpart**: a second simulation standing
  in for the hardware, modelled *as if it were physical*.
- **2.B** — the stand-in is replaced by the real cell.

**The Phase 2 exit criterion is unchanged. 2.A does not weaken it**, and nothing 2.A
produces closes any clause of it. The three-arm cell stays three-armed, and 2.A builds on it
rather than beside it.

### The target operating mode is stated, and it is not the one the mode table has

The owner's target: **the simulation is what a person commands, and commanding it moves the
other side.** Someone looking at the simulated cell is thereby controlling the cell on the
far side of the twin boundary. That is a statement about *where an operator's command
enters*, and [ADR-0011](0011-twin-maturity-model-and-modes.md)'s mode table does not have a
column for it — its rows say what each side *does*, and the only row carrying a
virtual-to-physical direction is `CLOSED_LOOP`, which is about the virtual side *gating*
the physical one after validation. That gap is what Decision 2 below closes, and it
closes it with a sixth mode rather than with a field beside the mode — read that
decision for why the field was tried first and then refused.

### Planning is not bound by this machine

The owner's instruction, recorded because it governs how the cost figures below are read:
the design runs on the right machine when it needs to run, not on this development host.
Machine requirements are stated as requirements on the target machine — that is
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s job — and never as a reason to
shrink the design. The campaign was written under the same rule and registered it before the
first trial (`criteria.md` §0): the development host is a macOS laptop in a Docker Desktop
Linux VM with no GPU passthrough, and an absolute real-time factor measured on it transfers
to nothing.

### Nobody knew what a second simulation costs

That is why the campaign exists. Its findings are cited throughout and are deliberately not
copied around (P1); the ones that change this decision rather than merely pricing it are in
*Consequences*.

## Options considered

### Option A — a kinematic echo: `robot_state_publisher` fed mirrored joint state

The cheapest counterpart that shows something. The campaign built exactly this and measured
it (`ANALYSIS.md` §4.1): three `robot_state_publisher` on the virtual domain, an in-process
relay across the domain boundary, **0.0865 cores and 0.0794 GiB**, carrying the plant's full
rate with nothing dropped by the rig's own count.

Rejected **as 2.A's counterpart**, and only for that role. It presents none of what hardware
presents. There is no controller manager, no controller to activate or fail to activate, no
`FollowJointTrajectory` action to abort, no execution-side tolerance to violate
([ADR-0036](0036-execution-side-trajectory-tolerances.md)), no joint state that can disagree
with what was commanded — because it *is* what was commanded, echoed. Every interface 2.A
would build against it is an interface 2.B has to break.

### Option B — replay a recorded trajectory on the counterpart

The counterpart plays back what the plant executed. Rejected for a sharper reason than
Option A: a counterpart that cannot diverge gives the divergence instrument nothing to
measure. The one thing 2.A is for — exercising the mechanism that will later measure
fidelity — is precisely what a replay cannot exercise.

### Option C — a complete second simulation of the cell

The counterpart is the same thing the plant is: the generated world, the generated
descriptions, `gz_ros2_control` with the same controllers, the same skill servers, from the
same L0 model. Chosen.

## Decision

**In Phase 2.A the virtual counterpart is a complete second simulation of the cell** — not
an abstraction, not a kinematic echo, not a replayed trajectory.

**The reason is P2, and it is the whole argument.** 2.B replaces that side with hardware.
Whatever the plant talks to across the twin boundary in 2.A must be the same shape as what
hardware will present in 2.B, or 2.A builds an interface that 2.B has to break. A cheaper
counterpart would make 2.A pass and 2.B start over.

Two further decisions follow from the target operating mode and from P1/P5, and are
specified here so that the changes implementing them have a record to work from. **Neither
is implemented by this record: it does not edit `TwinMode.msg`, it does not edit the L0
schema, and it edits neither ADR-0011 nor the charter.**

### Decision 2 — `TwinMode` gains a sixth mode for the virtual-led flow

A mode says what each side does and which way commands travel between them. ADR-0011's five
modes carry four flows, and none of them is the owner's target. `SIM` and `REAL` each idle
one side, so neither carries a flow between the sides at all. `SHADOW` and `VALIDATED` are
*defined* by an information flow **from** the physical side. `CLOSED_LOOP` has the right
direction and is defined by the validation gate in front of it, which this flow does not
have. So the target operating mode — **an operator commands the simulated side, the far side
follows and actuates, and nothing mirrors back** — has no value in the published state.

**The project owner's decision is to add it as a mode, and to make it reachable in 2.A.**
The constant, to be added to
[`cite_interfaces/msg/TwinMode.msg`](../../workspace/src/cite_interfaces/msg/TwinMode.msg)
by a later change:

```
uint8 MODE_VIRTUAL_LEAD=5   # virtual commanded; the far side follows and actuates.
                            # No validation gate in front of it — that is CLOSED_LOOP.
                            # No reverse flow behind it — that is SHADOW.
```

The name states the direction and claims nothing else. It deliberately does not reuse
`Mirror`, which charter v1.2 retired from this project's vocabulary, and it does not reuse
`SHADOW`, which ADR-0011 maps to real → virtual and to the literature's *digital shadow*.

**Why a mode and not a field.** An earlier draft of this record proposed a `command_source`
enum published alongside `mode`, on the reasoning that "which side a human drives" is a
different question from "what each side does". Architecture review took the cross product and
the reasoning does not survive it. Over five modes and four `command_source` values, **five
cells are consistent and forced** — `SIM`→`VIRTUAL`, `REAL`/`SHADOW`/`CLOSED_LOOP`→`PHYSICAL`,
`VALIDATED`→`BOTH` — **ten contradict the mode outright**, and the remaining five are the
`UNSPECIFIED` column, which carries no information by construction. A field whose every legal
value is already determined by the field beside it is a value in two places (P1). And it would
not have worked even so: **no `(mode, command_source)` pair expresses the target flow.** The
only cell in which commands enter at the virtual side is `SIM`+`VIRTUAL`, and `SIM` has the
far side *idle* rather than following. The field would also have been unsettable through the
audited path — `SetMode.srv` carries `mode`, `reason` and `force` and nothing else, so
`command_source` would have had to be set outside the gated transition that
[`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md) requires.

**What gates the mode is not the phase — it is whether the far side is real.** In 2.A the
counterpart is a simulation, so entering the mode can move nothing physical, and 2.A gets to
exercise command routing before any hardware exists, which is the thing 2.A is for. When the
far side becomes physical, the mode binds to the refusal **already in the tree** rather than
to a second gate: `require_hardware_opt_in` in
[`cite_bringup/cite_bringup/plan.py`](../../workspace/src/cite_bringup/cite_bringup/plan.py)
refuses to start a plan naming a non-`sim` backend unless `CITE_ALLOW_HARDWARE` is set to
exactly `1`, and `cite_bringup/test/test_plan.py` tests the refusal, the opt-in, and that no
other value counts as one. Under Decision 3 below the counterpart side appears in the
generated plan as its own controller manager, so a physical far side puts a non-`sim` backend
in front of that function unchanged, with no new gate and no second definition of what an
opt-in is.

**The residual is stated rather than hidden.** That gate is a bring-up refusal, not a
`SetMode` refusal, so what it buys today is that the stack could not have started.
`SetMode.srv`'s own header already records this and commits the L5 server that eventually
implements it to applying the same check at the transition. That commitment is now
load-bearing for this mode. It is the existing one, and this record adds nothing to it.

**It is not a maturity claim, and it moves none.** Charter §2 and ADR-0011 define L3 as
virtual → real **with the behaviour validated in simulation first**; this mode has the
direction and not the gate, so it is not L3 and no document may cite it as L3. In 2.A there is
no physical side at all, so the level is unchanged at L0 — see *What 2.A cannot claim* below,
which stays true word for word after this decision.

**It extends two protected documents, and this record extends neither of them itself.**
ADR-0011's five-mode set and charter §8's Phase 2 scope sentence, which names four modes, both
predate this mode; charter §2 places virtual → real at maturity L3 and charter §8 places L3 in
Phase 5, so the *direction* is being pulled forward into Phase 2 while the *gate* that defines
L3 is not. **The Phase 2 exit criterion is untouched, and this mode closes no clause of it.**
Amending ADR-0011 and the charter is named under *What we will have to revisit*; the charter
changes only by explicit owner decision with a version bump (charter §12).

**The implementing change owes the interface baseline.** Adding a constant is additive at the
wire level, but `cite_interfaces/test/interfaces.baseline` enumerates every constant of every
interface, so the regeneration is a conscious, reviewed step rather than a silent one. That is
what the baseline is for.

### Decision 3 — one backend selection per (asset, side), with "twinned" derived rather than declared

An earlier draft of this record proposed a `twin: {counterpart: none | virtual}` block on each
asset instance, as a sibling of `hardware:`. **Architecture review rejected it, the rejection
is correct, and the reasoning is the decision** — so it is recorded rather than quietly
replaced.

`hardware.backend` is a scalar with **no side index**. It says which `ros2_control` hardware
plugin *this instance* loads (ADR-0005), and in a twin pair *this instance* exists on both
sides and loads a different plugin on each. The moment an asset is twinned, `hardware.backend`
therefore has no well-defined referent, and a parallel `twin.counterpart` field does not supply
one — it crosses with the scalar to give one situation two encodings:

| `hardware.backend` | `twin.counterpart` | what it was meant to say |
|---|---|---|
| `sim` | `none` | one simulated side — Phase 1 as it stands |
| `real` | `none` | one physical side, no twin |
| `sim` | `physical` | one simulated side and one physical side |
| `real` | `virtual` | **the same thing again** |
| `sim` | `virtual` | two simulated sides — 2.A |

Rows 3 and 4 are one physical situation written two ways. That is the P1 failure the rejected
draft's own hazard note warned about, and the note's own instruction applies: *"if the
implementation finds that one is derivable from the other, then one of the two should not
exist."* `twin.counterpart` is the one that should not exist.

**The decision: a backend is selected per (asset, side), the two sides are named, and an asset
is twinned exactly when a second side is present.** Two facts, at two scopes, because they are
two different facts.

**1. Whether a zone runs as a pair is a zone fact, and it is written once.**

```yaml
# model/facility/, on the zone. Required, with no default.
twin:
  sides: single | pair
```

`single` is Phase 1 as it stands. `pair` covers 2.A **and** 2.B: this line does not change
when the counterpart becomes physical.

**2. What each side of an asset loads is an asset fact, and it is written per asset.**

```yaml
hardware:
  backend: sim              # unchanged. Required, with no default. The plant side.
  counterpart_backend: real # OPTIONAL, and written only where the two sides differ.
                            # Absent means: the same backend as `backend`.
```

The two side names are **`plant`** and **`counterpart`**, defined structurally rather than by
who is commanding: `plant` is the side the untwinned model already describes — the side that
exists whether or not the twin does, and that every Phase 1 artifact, scenario and script
already addresses — and `counterpart` is the side that exists only where the zone is a `pair`.
Nothing in that naming moves when `TwinMode` moves, which is the property Decision 2 needs it
to have, and it is why the side index is not `virtual`/`physical`: those are backends, and a
2.A pair has two simulated sides.

**How each requirement is met, one by one:**

- **No churn on the existing instances** — every one of them, whatever
  `./scripts/validate-model` reports the count to be. `hardware.backend` is untouched, in the schema
  and in every file under `model/assets/instances/`. There is no `none` sentinel, because a
  sentinel is a way of making an untwinned asset declare that it is untwinned. An untwinned
  asset says nothing — and, as the next points show, neither does a 2.A one.
- **2.B remains a data change**, and a smaller one than the rejected shape: `counterpart_backend:
  real` on the arm that acquired hardware. The other two arms and every belt, beam and fixture
  are unchanged, which is exactly charter §8's "one physical arm and two simulated ones".
- **The per-asset grain is justified for 2.B and is *not* justified for 2.A**, which is the
  whole reason the zone-level fact exists. In 2.A the counterpart is *a complete second
  simulation of the cell* — the Decision above — so its world contains every asset whether or
  not anyone wanted that asset twinned, and "arm_1 is paired but conveyor_1 is not" has no
  meaning there. Writing `counterpart: virtual` on every instance would have been one
  deployment fact written fifteen times, which is P1 at a different granularity. Under this
  shape **2.A writes nothing on any instance**: the zone says `pair`, `counterpart_backend` is
  absent everywhere, and both sides are `sim` because the plant is. The only thing ever written
  per asset is a side that *differs* from the plant, and that is a genuine per-asset fact.
- **The zone-level key is required with no default, and the churn it costs is one line in one
  file.** That is the price of not having a second machine appear because a key was omitted —
  the same reasoning that makes `hardware.backend` required, quoted in the schema itself. The
  objection that an untwinned thing should not have to declare itself untwinned bites at asset
  scope, where the declaration is repeated fifteen times; at zone scope it is written once,
  which is what moving it there was for.
- **Yes, generators read it, and that is decided rather than left to the implementer.**
  `hardware.backend` is already read by `tools/cite_tools/generate/control.py`, which derives
  `use_sim_time` from it, and by `tools/cite_tools/generate/bringup.py`, which emits
  `controller_managers[].backend` into the bring-up plan. Both new fields join them:
  `twin.sides: pair` makes the generator emit a second side — its controller managers, its
  world, its node names and its Gazebo partition
  ([ADR-0042](0042-partition-gazebo-transport-per-side.md)) — and `counterpart_backend` chooses
  that side's plugin.

  **The consequence, stated because it is the awkward one:** under
  [ADR-0021](0021-generated-artifacts-are-committed.md) `cite_generated/` is committed and
  hashed, so turning pairing on produces a source diff and a new `MODEL_HASH`. That is
  accepted, and it rests on one thing that has to hold: **pairing is not a runtime mode.** The
  runtime knob is `TwinMode`, gated through `SetMode.srv`, and it regenerates nothing —
  Decision 2 is precisely the thing that changes without a commit. `twin.sides` changes what
  the facility model *describes*, in the same class as adding a fourth arm, and this project
  already pays a commit for that. The alternative — deriving the second side's plan in launch
  code — puts the shape of a bring-up plan into Python, which is the generated launch graph
  `CLAUDE.md` §4 prohibits, and P5 puts values in data.
  **The reopening trigger is named:** if anyone proposes a launch argument or an environment
  variable that turns pairing on without regenerating, that is a value in two places and it
  must be argued here rather than added — the same ground [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s
  Option C was rejected on.
- **The default direction is the safe one, which is why `counterpart_backend` may have a
  fallback at all when `backend` may not.** The schema records why `hardware.backend` is
  required with no default: it "is the field that decides whether a command reaches a physical
  arm". Falling back to the value of `backend` preserves that property exactly — **no omitted
  key can produce a non-`sim` value anywhere**, because the value it falls back to is itself
  required and explicit. A counterpart becomes physical only by someone writing it, and then
  the bring-up refusal named in Decision 2 fires on it unchanged.
- **Placement, answered rather than defended.** Half of the rejected block did not belong in L0
  and is gone. What remains splits cleanly. `counterpart_backend` is the same *kind* of fact as
  `hardware.backend` — which plugin drives a thing, ADR-0005's boundary — and stays in L0
  without argument. `twin.sides` is the harder one, and the honest answer is the review's:
  **it is a fact about the modelled deployment, not about the building.** The building has one
  `arm_1`. It is placed in L0 anyway because it changes what is generated and under ADR-0004
  everything generated comes from L0; the only other homes available are a launch argument or
  an environment variable, and `cross-cutting-safety.md` bars both for this class of value.
  That does stretch ADR-0004's wording — "the single source of truth for every physical and
  topological fact" — and the honest consequence is that **ADR-0004 may need amending to say
  that L0 describes the modelled system rather than only the building.** That is listed under
  *What we will have to revisit* rather than done here.

**What this record still does not settle**, stated so nobody reads it as settled: whether
`{backend: real, counterpart_backend: sim}` — a physical plant with a simulated counterpart —
is a deployment this project will ever run. It is expressible, and under the structural
definition of `plant` above it is a *different* deployment from `{sim, real}` rather than a
second encoding of it. 2.B as scoped does not need it. If both encodings are ever found
describing one deployment, that is a finding and not a coincidence to code around.

## Consequences

### What this gets us

- **2.B is a substitution and not a rewrite.** That is the entire point, and it is the only
  claim in this record that 2.B itself will test.
- **Every mechanism L5 owes gets exercised before hardware arrives**: mode, command routing,
  mirroring, and the divergence monitor, against a counterpart that can genuinely disagree
  with the plant. Registration is the exception — there is nothing to survey.
  **Command routing is exercised as a mode**, which is what makes that claim true rather
  than aspirational: 2.A routes on `TwinMode` through `SetMode.srv`, inside the gated,
  observable transition path `cross-cutting-safety.md` requires, and not through a second
  field set beside it (Decision 2).- **The hardware-facing failure modes have somewhere to be rehearsed.** A counterpart that
  is a full `ros2_control` stack can fail to activate a controller, abort a trajectory, and
  violate a tolerance. An echo cannot do any of those, so a system built against an echo
  would meet all three for the first time with a real arm in the room.

### What this costs us — the measured part, reported exactly as the campaign licenses it

**The pre-registered ratio is INCONCLUSIVE and is not interpreted here.** The campaign's
validity rule V2, registered before the first trial, refuses the ratio if the SOLO repeats'
own range exceeds 25 % of their median. It was **30.9 %**, so **V2 fired**. For the record
the headline figures would have been `R = 1.270` and `R' = 1.268`, and the campaign declines
to read them against its own bands. So does this record. The variance was not scatter: one
block of four runs was about 30 % slow across all of them, the cause was not established,
and the campaign refused to discard it.

**Reported beside the refusal, and labelled as what it is:** the campaign's Deviation 1
recomputes the same two ratios *within* each block, over data already collected, with no run
repeated. That is not a pre-registered figure.

| Deviation-1 figure | Median | Range across the five blocks |
|---|---|---|
| Per-world slowdown `R` | **1.282** | 1.235 to 1.590 |
| Aggregate throughput `R'` | **1.552** | 1.261 to 1.589 |

The campaign's own honest reading is that **a second world costs about a quarter to a third
of a world, not a whole one** — sub-linear. Read the campaign for it; do not read the medians
above without the range beside them, and do not turn an inconclusive primary result into a
clean number by quoting the deviation alone.

Memory and coexistence are not the constraint: two cells ran at **1.133 GiB and 1.132 GiB**
per container against a 7.653 GiB limit, with no OOM kill and no restart, and each side's
ROS graph contained **44 nodes and 93 topics**, the same as a solo cell, with zero foreign
nodes.

### The penalty is not core starvation, so "buy more cores" is not the mitigation

During a pair the two containers drew **411 % and 408 % of a CPU — 8.2 of 12 cores, 68 %
occupancy — while neither side reached its solo rate**, by the Deviation-1 margin in the
table above, which is not a pre-registered figure and must not be read without the range
beside it. A third of the machine was idle and did not help. Gazebo's physics loop is serial, so the per-world ceiling is set by
single-thread throughput and by whatever the two loops contend for below the core; the
campaign states plainly that it cannot separate memory bandwidth from last-level cache and
did not try.

The mitigation the evidence actually supports is the hull question —
[ADR-0028](0028-convex-hull-collision-meshes.md)'s collision geometry, and the requirement
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) derives from it. That is where the
pairing cost is bought back, and it is bought with geometry rather than with hardware.

### A real fork, named rather than picked

A physics-free counterpart costs a fraction of a full one, and the difference is not
marginal. From the campaign's Q4: **`F = 0.0865 / 3.81 = 0.023`**, in its registered band
`F < 0.1`, whose pre-written reading is that *`SHADOW` and `VALIDATED` want different virtual
implementations, and L5 should say so before either is written.* It is 44x cheaper in CPU and
14x cheaper in memory — and the figure that decides it is what the plant did while each ran:
**1.107 with a shadow side attached, against a solo median of 1.097 and a paired 0.864.**

So: **a `SHADOW` counterpart costs the plant nothing measurable, and a `VALIDATED` one costs
it materially.**

**This record does not pick one, and no later document may cite it as having picked one.**
2.A builds the full counterpart **because 2.B demands it** — that is the decision above and
it is not weakened by the cost. A cheaper `SHADOW` path is a legitimate later optimisation
with a measured basis, and it is an **open question for L5**: whether the mode decides
whether a simulator is instantiated at all, as a property of the mode rather than something
left to whoever writes the launch graph. The campaign is explicit that this is *not* an
argument for two codebases. It is a parallel-abstraction risk found before it was built,
which is what it was worth measuring for.

### What 2.A cannot claim

**No number produced in 2.A is a fidelity result, and none may be published as one under
P8.**

Both sides of a 2.A pair run the same L0 model, the same generated description, the same
controllers and the same physics solver. There is no reality on either side of the boundary.
Divergence measured between them is therefore **instrument, solver and scheduling noise** —
it is not a reality gap, and it does not become one by being plotted.

The campaign already shows the size of the artefact: two identically configured cells ran at
**0.888 and 0.698 in the same wall-clock window with no fault anywhere.** A divergence metric
computed across that pair would have reported a large, growing, entirely instrumental
number, and nothing in the system would have contradicted it. That measurement is
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s reason to exist.

It follows directly from ADR-0011's definitions, and not merely as a caution, that **2.A does
not reach maturity level L1 or L2.** Both are defined by an information flow from the
physical, and 2.A has no physical. 2.A remains at level L0, *virtual model*, however many of
L5's mechanisms it exercises.

**What 2.A does buy is the mechanism.** It validates the thing that will measure fidelity —
the mode machinery, the command routing, the mirroring path, the monitor and its metric.
**2.B produces the first fidelity measurement**, and until 2.B there is no such measurement
in this project. A 2.A divergence plot is a test of the instrument, and anyone presenting one
must label it as one.

**Nor does the sixth mode move any of this.** `MODE_VIRTUAL_LEAD` carries the direction
L3 is defined by and not the validation gate charter §2 and ADR-0011 put in that
definition, and in 2.A there is no physical side for the direction to reach. A mode is a
statement about where commands enter and where they land. It is never a maturity claim,
and nothing in this project may cite the mode's existence as one.

### What else this costs us

- **A second cell to bring up, tear down and keep identical**, and every scenario, script and
  CI step that assumes one cell has to learn about two.
- **Two new classes of defect that only exist because there are two sides**, both of which
  needed their own decision: silent cross-talk on the Gazebo transport
  ([ADR-0042](0042-partition-gazebo-transport-per-side.md)) and two sim clocks that separate
  without bound ([ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)).
- **A target machine that this development host is not**, which ADR-0043 states as a
  requirement.
- **The cheaper counterpart is deliberately not taken**, and it is measurably cheaper. That
  is a real cost accepted for a reason (P2), and it should be re-argued rather than assumed
  if the reason ever stops applying.

### What we will have to revisit

- **When the `SHADOW` fork is decided.** L5 owes an answer to whether the mode decides that a
  simulator is instantiated at all. This record names the question; it does not answer it.
- **When 2.B lands.** The counterpart is replaced by hardware and this record's central claim
  — that the shape of what the plant talks to did not change — is testable for the first
  time. If anything in the L5 interface has to change at that point, this decision failed at
  exactly the thing it was made for, and that must be written down rather than absorbed.
- **When the inconclusive ratio is re-measured**, on a target machine, with thresholds
  registered in advance. Nothing above is a reproduction claim.
- **When ADR-0011 and charter §8 are amended for the sixth mode.** ADR-0011's five-mode set
  and charter §8's Phase 2 scope sentence, which names four modes, both predate
  `MODE_VIRTUAL_LEAD` and both have to name it. Neither is edited by this record: the
  charter is protected and changes only by explicit owner decision with a version bump
  (charter §12), and ADR-0011 takes an amendment rather than a supersession because its
  five levels, their literature mapping and its commitment are all untouched.
- **When `twin.sides` tests ADR-0004's wording.** Decision 3 places in L0 a fact about the
  modelled deployment rather than about the building, which is not what ADR-0004 says L0
  is for. Either that record is amended to say L0 describes the modelled system, or a
  better home is found for the one key. Do not settle it by leaving the two documents
  disagreeing.
- **If a future Gazebo parallelises the physics step**, which the campaign names as the
  condition under which its core-count conclusion changes.
