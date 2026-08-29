# ADR-0041: Build the Phase 2.A virtual counterpart as a second full simulation

- **Status:** Proposed — the split and the target operating mode are the project owner's
  decisions and are recorded here rather than argued; **nothing in this record is
  implemented.** At `f1f914f` nothing in the tree launches a second cell, `cite_twin` does
  not exist and [L5](../architecture/L5-twin-synchronization.md) is marked `DESIGNED`,
  `TwinMode` carries no `command_source` field, and the L0 schema has no `twin:` block.
  Every "will" and "must" below is a commitment, not a description. Promoted to `Accepted`
  by the change that first brings a pair up under bring-up's own control (P7).
- **Date:** 2026-08-29
- **Deciders:** Project owner — the Phase 2.A / 2.B split and the target operating mode.
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
  charter §8 (Phase 2), charter §4 (P1, P2, P5, P7, P8)

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
the physical one after validation. That gap is what the `command_source` decision below
exists to close.

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
is implemented by this record: it does not edit `TwinMode.msg` and it does not edit the L0
schema.**

### Decision 2 — `TwinMode` gains a `command_source` field

A mode says what each side does. It does not say which side a human is driving, and after
the target operating mode above those are two different questions. Without a separate
field, "an operator commands the simulation and the far side follows" is indistinguishable
in the published state from `CLOSED_LOOP`, which is a different thing at a different
maturity level — and the project would either misname its own maturity or invent a sixth
mode for a question that is not a mode.

The field, to be added to
[`cite_interfaces/msg/TwinMode.msg`](../../workspace/src/cite_interfaces/msg/TwinMode.msg)
by a later change:

```
uint8 COMMAND_SOURCE_UNSPECIFIED=0  # not established; nothing may read this as a claim
uint8 COMMAND_SOURCE_VIRTUAL=1      # commands enter at the virtual side; the physical side follows
uint8 COMMAND_SOURCE_PHYSICAL=2     # commands enter at the physical side — pendant, hand-guiding,
                                    # a direct controller — and the virtual side follows
uint8 COMMAND_SOURCE_BOTH=3         # one commander fans the same command out to both sides

uint8 command_source
```

Three properties of that set are load-bearing:

- **`UNSPECIFIED` is zero, so an omitted field is never a claim.** This is the same rule
  that makes `hardware.backend` a required key with no schema default, and the same reason
  [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md) requires a mode to be
  "explicit and gated ... never reachable through a default parameter, an environment
  variable, or a launch-argument default".
- **`VIRTUAL` and `PHYSICAL` name the *role* at the twin boundary, not the implementation.**
  In 2.A the physical role is played by the second simulation; in 2.B by the real cell. The
  field does not change between them, which is the substitution P2 requires.
- **`BOTH` exists for `VALIDATED`**, where ADR-0011 has both sides commanded in parallel and
  the commander is above both. The alternative — leaving that case implicit in the mode —
  was considered and rejected, because it makes the field answerable for four of the five
  modes and undefined for the fifth.

**What this decision does not settle, stated so nobody reads it as settled:** which
`TwinMode` value carries the owner's target mode, and at what level of ADR-0011's maturity
model it sits. `SHADOW` is defined as real → virtual and mapped to the literature's *digital
shadow*; reusing it for the reverse direction on the strength of a `command_source` value
would silently claim level L1 for a flow the literature calls a digital twin, which is
exactly the vocabulary trap ADR-0011 was written to avoid. That is a question for ADR-0011
to be extended or superseded to answer, and it can wait for 2.B, because the direction only
becomes safety-critical when the far side is a real arm.

### Decision 3 — L0 must be able to say that an asset has a counterpart

Which assets are twinned, and what the other side of the boundary is for each, are facts
about the facility. Under ADR-0004 a fact about the facility is L0 data, and under P5 the
code encodes how twinning works and never which assets are twinned. Today L0 cannot express
it at all.

The shape, to be added to the asset-instance schema by a later change, as a sibling of the
existing `hardware:` and `registration:` blocks:

```yaml
twin:
  counterpart: none | virtual
```

- **Required, with no schema default**, for the reason `hardware.backend` is: a default
  would let an asset acquire a counterpart because a key was omitted.
- **Per asset, not per zone.** Charter §8's Phase 2 states that the system runs correctly
  with one physical arm and two simulated ones and gains arms without structural change.
  That is a per-asset property or it is nothing.
- **2.B is then a data change.** It adds a third value — `physical` — and changes the value
  on the assets that have acquired hardware. What a physical counterpart needs alongside it
  (the `registration` block, the hardware opt-in) is 2.B's question and is not decided here.
- **The P1 hazard the implementing change must clear:** `twin.counterpart` must not restate
  `hardware.backend`. They answer different questions — `hardware.backend` says which
  `ros2_control` hardware plugin *this* asset's own instance loads (ADR-0005);
  `twin.counterpart` says whether a second instance of this asset exists on the other side
  of the twin boundary, and what it is. If the implementation finds that one is derivable
  from the other, then one of the two should not exist, and that is the finding rather than
  a coincidence to code around.

## Consequences

### What this gets us

- **2.B is a substitution and not a rewrite.** That is the entire point, and it is the only
  claim in this record that 2.B itself will test.
- **Every mechanism L5 owes gets exercised before hardware arrives**: mode, command routing,
  mirroring, and the divergence monitor, against a counterpart that can genuinely disagree
  with the plant. Registration is the exception — there is nothing to survey.
- **The hardware-facing failure modes have somewhere to be rehearsed.** A counterpart that
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
occupancy — while each side still lost 22 % of its solo rate.** A third of the machine was
idle and did not help. Gazebo's physics loop is serial, so the per-world ceiling is set by
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
- **When ADR-0011 is asked which mode carries the target operating mode**, per Decision 2's
  open question.
- **If a future Gazebo parallelises the physics step**, which the campaign names as the
  condition under which its core-count conclusion changes.
