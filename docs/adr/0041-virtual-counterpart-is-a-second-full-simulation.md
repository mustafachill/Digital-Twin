# ADR-0041: Build the Phase 2.A virtual counterpart as a second full simulation

- **Status:** Accepted (corrected 2026-08-29 and 2026-08-30) — **promoted 2026-08-30 by the
  change that first brought a pair up under bring-up's own control** (`b3b7b66`), which is the
  condition this record set for itself. `./scripts/sim --pair` starts two independent
  `ros2 launch` processes through `cite_bringup.pair`, each running the whole of
  `simulation.launch.py` on its own ROS domain and in its own Gazebo partition — so the
  counterpart is a complete second simulation by construction rather than by intent, which is
  Decision 1. **A second correction sits above the first**; see the section
  "Correction — 2026-08-30: a pair has come up, Decision 1 is built, and this record is
  promoted", below, for what promotion does and does not claim.
  The split and the target operating mode are
  the project owner's decisions and are recorded here rather than argued. **Decision 2 and
  Decision 3 are both built, and this record went on saying nothing in it was.**
  `MODE_VIRTUAL_LEAD=5` is in `TwinMode.msg` with the interface baseline regenerated, and L0
  carries `twin.sides` on the zone and an optional `hardware.counterpart_backend` on the
  instance, with `backend: real` refused under `sides: pair`. See the section
  "Correction — 2026-08-29: Decisions 2 and 3 are implemented, and the status line still said
  nothing was", below.
  **The record stays `Proposed`, and that is a finding rather than an oversight.** It is
  promoted by the change that first brings a pair up under bring-up's own control (P7), and
  **nothing has ever brought a pair up.** The Decision itself — that the 2.A counterpart is a
  complete second simulation — is entirely unbuilt. What Decisions 2 and 3 bought is
  vocabulary and schema: a mode nothing routes on, and a field that makes a pair
  *expressible*. **[Corrected 2026-08-30 — see the Correction section above.]**
  **When written this record was `Proposed` and nothing was implemented**, and that sentence
  is kept rather than replaced: at `f1f914f` nothing in the tree launched a second cell,
  `cite_twin` did not exist and [L5](../architecture/L5-twin-synchronization.md) was marked
  `DESIGNED`, `TwinMode` carried five modes and no sixth, the L0 schema had no `twin:` block
  and `hardware.backend` was a scalar with no side index. **Three of those six clauses still
  hold**: nothing launches a second cell, `cite_twin` does not exist, and L5 is still
  `DESIGNED`. **[Corrected 2026-08-30 — two of the three still hold; a second cell is
  launched. See the Correction section above.]**
  Every "will" and "must" below is a commitment rather than a description, **except where
  either correction section marks one as met.**
- **Date:** 2026-08-29
- **Deciders:** Project owner — the Phase 2.A / 2.B split, the target operating mode, and
  the decision to express it as a sixth `TwinMode` constant reachable in 2.A (Decision 2).
  Recorded by the docs-writer agent from
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  which was run to size the decision before the design fixed its shape.
- **Related:** [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md) (the pair that promoted
  this record),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) (which narrows Decision 3
  until the generator emits per-side artifacts),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0010](0010-typed-ros-interfaces.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md) (the L5 design this record's open
  questions were left for),
  [L5](../architecture/L5-twin-synchronization.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  charter §2 (maturity levels), charter §8 (Phase 2), charter §4 (P1, P2, P5, P7, P8)

## Correction — 2026-08-30: a pair has come up, Decision 1 is built, and this record is promoted

**What was wrong.** Three claims, all in the status block, all falsified by `b3b7b66`:
*"nothing has ever brought a pair up"*; *"the Decision itself — that the 2.A counterpart is a
complete second simulation — is entirely unbuilt"*; and, in the list of clauses said to survive
from the original block, *"nothing launches a second cell"*. The other two clauses in that list
still hold: `cite_twin` does not exist (`ls workspace/src`) and
[L5](../architecture/L5-twin-synchronization.md) is still `DESIGNED`.

**What is true, established against the tree rather than taken from a report.** The counterpart
is not a second thing that had to be built — it is `simulation.launch.py` given
`side:=counterpart`, so it is the same complete cell in a different environment. That is held
in the tree by `test_the_counterpart_takes_the_other_partition_and_the_other_domain`
(`cite_bringup/test/test_simulation_launch.py`), which asserts the counterpart's Gazebo
processes carry the counterpart's partition while every name the launch builds stays the plant's
byte for byte, and by `test_the_counterpart_started_on_the_plants_domain_refuses` beside it.
What was **observed rather than tested** is the pair itself: the implementing agent of `b3b7b66`
reports three runs on one machine, with 22 Gazebo topics per partition under byte-identical
names, 41 nodes per domain, and `/clock` carrying one publisher on each domain where a merged
graph would show two. **Review did not re-take it and no test covers it.**

**Why this promotes the record.** The condition was *"the change that first brings a pair up
under bring-up's own control"*, and the phrase excluded the one prior instance: the
[second-world-cost](../measurements/2026-08-28-second-world-cost/ANALYSIS.md) campaign brought
two cells up from a shell script of its own. `./scripts/sim --pair` is bring-up's own —
`cite_bringup.pair` reads the generated plan, resolves each side's domain through
`resolve_domain_id`, and starts the project's own launch twice
([ADR-0047](0047-two-independent-launches-joined-not-sequenced.md), promoted on the same
change). Options A and B — a kinematic echo and a replayed trajectory — are not merely still
rejected; the tree now contains the thing that was chosen instead of them.

**What promotion does NOT claim.**
- **Nothing automated brings a pair up.** The evidence for the run is three hand-taken runs on
  one machine. ADR-0047's status block carries the same residual and names what would close it.
- **The counterpart is byte-identical to the plant, and that is a gap rather than a design.**
  The generator emits one artifact set and hands it to both sides, so "modelled as if it were
  physical" is not what exists today. That is
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md)'s clause 2, still
  unimplemented, and its clause 1 refusal is not built either.
- **No fidelity number, and 2.A produces none** — both sides run the same L0 model and the same
  solver, so agreement between them is agreement of a thing with itself. Charter §8 scopes this.
- **L5 is untouched.** Nothing mirrors, nothing measures divergence, `SetMode` has no server and
  `MODE_VIRTUAL_LEAD` still routes nothing. Every open question this record left for L5 is open.
- **The machine does not hold the pair to real time.**
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s half 2 has now been measured on a pair
  and is **not met**; its 2026-08-30 correction carries the figures and this record does not
  copy them.
- **The shipped model is `single`.** `model/facility/zones.yaml` declares `twin: {sides: single}`,
  so a pair requires an L0 edit that moves `MODEL_HASH`. This record makes a pair the decided
  shape; it does not make the repository paired.

**How the error survived.** The same way the 2026-08-29 one did, one layer up: the branch that
falsified this record was reviewed against [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md)
and [ADR-0044](0044-one-ros-domain-per-side-identical-names.md), the records it was written from,
and this one was read as background. **A record is falsified by the branch that satisfies it, and
that branch's reviewers are looking at a different record.** The check that would have caught it
is mechanical and cheap: grep the tree for the sentence the change makes false — here,
"has ever brought a pair up", which stood in **four ADRs and twice in `CLAUDE.md`**, six
occurrences at the commit before this correction. Two of the six are only found by a search that
tolerates a line wrap, which is the usual reason a stale sentence survives a grep.

## Correction — 2026-08-29: Decisions 2 and 3 are implemented, and the status line still said nothing was

**What was wrong.** One sentence, and it is the first thing a reader of this record meets:
*"nothing in this record is implemented."* It was true when written and it stopped being true
at `de39e66` and `94561bf`, which implemented Decisions 2 and 3 and left this record
untouched. A reader taking the status line at face value would conclude that
`MODE_VIRTUAL_LEAD` and `twin.sides` do not exist and that adding them was still open work.
Both are in the tree, tested, and load-bearing for other documents.

**What is true, established against the tree rather than taken from a report.** Each claim
with the command that shows it:

| Claim in the status line | State at this commit | Established by |
|---|---|---|
| "`TwinMode` carries five modes and no sixth" | **false** — six | `cat workspace/src/cite_interfaces/msg/TwinMode.msg` |
| "the L0 schema has no `twin:` block" | **false** — `twin` is a required zone key | `grep -n twin model/schema/zones.schema.json model/facility/zones.yaml` |
| "`hardware.backend` is a scalar with no side index" | **false** — an optional `counterpart_backend` sits beside it | `grep -rn counterpart_backend model/schema/asset_instances.schema.json` |
| "nothing in the tree launches a second cell" | **still true** | `grep -rn 'counterpart\|sides' workspace/src/cite_bringup/launch/` returns nothing |
| "`cite_twin` does not exist" and "L5 is marked `DESIGNED`" | **still true** | `ls workspace/src/`; `head -3 docs/architecture/L5-twin-synchronization.md` |

**Decision 2 is met in full, including the two debts this record named for its implementer.**
The constant is in `cite_interfaces/msg/TwinMode.msg` with the wording this record specified
plus the maturity and danger caveats; `cite_interfaces/test/interfaces.baseline` carries
`uint8 MODE_VIRTUAL_LEAD=5`, so the baseline regeneration this record called *"a conscious,
reviewed step rather than a silent one"* was taken. The three dangerous-transition lists were
re-decided rather than left naming two transitions —
[`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md),
[`L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md) and
`SetMode.srv`'s header each now name entry to `VIRTUAL_LEAD` against a real far side as the
third, and each states that the refusal behind it binds at bring-up rather than at the
transition. [ADR-0011](0011-twin-maturity-model-and-modes.md) took the amendment this
record said it would need.

**Decision 3 is met in full, all three clauses.** `model/facility/zones.yaml` carries
`twin: {sides: single}`, required with no default in `model/schema/zones.schema.json`;
`hardware.counterpart_backend` is optional on an instance and falls back to `backend` at
load, so writing it where it agrees and omitting it are one model and one `MODEL_HASH`; and
the refusal is `physical-plant-on-paired-zone` in
`tools/cite_tools/validate/referential.py`, which is a cross-document rule and therefore lives
in the referential validator rather than in the schema. Every existing instance is untouched,
as this record required — ask `./scripts/validate-model` for the count rather than this
sentence.

**What survives, and it is most of the record.** The Decision — that the 2.A counterpart is a
complete second simulation — is untouched and unbuilt. Every argument for it stands, the
measured costs stand as the campaign licenses them, and *What 2.A cannot claim* stands word
for word: 2.A is still at maturity level L0 and no number it produces is a fidelity result.

**What `twin.sides: pair` actually does today, stated because the correction must not read as
a promotion.** `pair` is consumed by exactly one generator — `tools/cite_tools/generate/`
contains one reader of it, `bringup.py` — and it emits two things: a second entry in the
generated plan's `sides:` block carrying the counterpart's Gazebo partition, and a
`counterpart_backend` on each controller manager. **It emits no second world, no second
controller manager, no second set of node names and no second launch.** `cite_bringup/gz.py`
takes `plan.sides[0]` and runs the plant. So the pair is expressible, hashed and validated,
and it has never been brought up. That is the promotion condition, and it is not close.
**[Corrected 2026-08-30 — the pair has since been brought up and this record is promoted; see
the 2026-08-30 Correction section above. An earlier correction is not exempt from being
corrected.]**

**How the error survived.** The implementing change knew this record's status was right — its
own commit message says *"ADR-0041 and ADR-0043 stay Proposed, since nothing brings a pair
up"* — and drew the wrong conclusion from it: that a record which stays `Proposed` needs no
edit. But the status block asserted two independent things, *this is not binding yet* and
*none of this exists yet*, and only the first was still true. Nothing checks the second.
`./scripts/doctor` verifies that every ADR is indexed and that every referenced ADR exists;
no instrument in this repository reads an ADR's prose against the tree, and none can. The
transferable part is narrow and mechanical: **a status block that names specific absences at
a specific commit is a claim with an expiry date, and the change that falsifies one of those
absences is the change that owes the edit** — whether or not it also promotes the record.

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
by a later change: **[Corrected 2026-08-29 — see the Correction section above.]** **That
change is `de39e66`; the constant is in the file, carrying this wording plus the maturity and
danger caveats the paragraphs below require. Read `TwinMode.msg` for the text that is binding — the block here is what was
specified, not what shipped.**

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

**And the residual is exactly why the safety document has to be re-decided rather than
merely extended.** [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)
line 98 reads *"`SIM` → `REAL` and entry to `CLOSED_LOOP` are the two most dangerous state
changes in the system"*, and the same sentence is in
[`L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md) line 55 and in
`SetMode.srv`'s header. Against a real far side this mode is **`CLOSED_LOOP` minus the
gate, aimed at the same arm** — so on those documents' own criterion it is a third such
transition, and arguably ahead of one of the two. Because the opt-in binds at bring-up and
not at the transition, the list is currently the only place a reader would learn to treat
the transition as dangerous at all. **The implementing change owes that sentence a
revision, in all three places.** This record does not make it: the mode does not exist yet,
and a safety document naming a constant no interface defines would be the same false
attestation P7 exists to prevent. **[Corrected 2026-08-29 — see the Correction section
above.]** **The mode exists and the revision was made: `cross-cutting-safety.md`, `L5-twin-synchronization.md` and `SetMode.srv`'s header each
name a third dangerous transition, and each states that the refusal behind it binds at
bring-up rather than at the transition.**

**It is not a maturity claim, and it moves none.** L3 is virtual → real **with the behaviour
validated in simulation first**; this mode has the direction and not the gate, so it is not
L3 and no document may cite it as L3.
**Where that definition of L3 lives is worth being exact about, because ADR-0011's own level
table does not carry it.** That table's L3 row gives the data flow — `virtual → real` — and
nothing else, so on ADR-0011 alone this argument does not close. It closes on charter §2,
whose L3 row reads *"Behaviour is validated in simulation and then commands the physical
system"*, and on
[`L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md)'s mode table, whose
`CLOSED_LOOP` row is *"commanded after virtual validation gates it"* against level L3. Two
documents, one of them not protected. **If either is ever read as putting the direction alone
at L3, this record's central claim fails and must be re-argued rather than repeated.**
In 2.A there is
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
what the baseline is for. **[2026-08-29: paid. `cite_interfaces/test/interfaces.baseline`
carries `uint8 MODE_VIRTUAL_LEAD=5`.]**

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

**The decision: a backend is selected per (asset, side), the two sides are named, an asset is
twinned exactly when a second side is present, and a paired zone may not have a physical
plant.** Two facts, at two scopes, because they are two different facts — and then one
refusal, because the cross product leaves a cell alive that nobody wants.

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

  **The test that decides which side of that line a field falls on, stated once so it can be
  reused:** *if changing it requires a regeneration to take effect, it **describes** the
  system; if a service call flips it, it **runs** the system.* `twin.sides` is the first;
  `TwinMode` is the second. And `twin.sides` is not a new class of field — `hardware.backend`
  is **already** an L0 field that generators read and that already produces a committed
  `cite_generated/` diff whenever it changes. `twin.sides` is the same class of fact one
  scope up, so the commit it costs is a cost this project already pays and has already
  accepted, not a new one introduced here.
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

**A third clause, and it closes a door rather than opening one: `backend: real` is refused
while `twin.sides: pair`.**

The rejected draft's cross product left one cell alive that this record has to dispose of:
`{backend: real, counterpart_backend: sim}` — a physical *plant* with a simulated
counterpart, against `{backend: sim, counterpart_backend: real}` for the same two machines.

**They are genuinely different, and the reason is in the generator rather than in the naming.**
An earlier draft of this clause argued the difference from the definition of `plant` above —
that it is the side the untwinned model already describes. That argument is circular and is
withdrawn: it identifies a side by which field holds it, so it relabels the two encodings
without excluding either. What actually separates them is that **they emit different committed
generated trees**, at two call sites that both branch on this one field:

- `tools/cite_tools/generate/bringup.py:346` sets `hosted_by` to `simulator` for a `sim`
  backend and to `ros2_control_node` otherwise. Its own comment states the consequence: a
  simulated backend's controller manager is created **inside the Gazebo process**, so there is
  no separate process to wait on, while a real one runs its own node. So the two encodings
  disagree about which side has a process to sequence bring-up against.
- `tools/cite_tools/generate/control.py:234` derives `use_sim_time` from the same field, so
  they disagree about which side's controllers run on simulated time.

Add [ADR-0042](0042-partition-gazebo-transport-per-side.md)'s zero-server clause and they also
disagree about which side starts a `gz sim` at all. Those are different bring-up plans,
different controller configurations and a different `MODEL_HASH`; `./scripts/validate-model`
would diff them. **That is the evidence, and it is what the claim needed** — a definition
cannot do this work and should not have been asked to.

**Being different is not being wanted, and this one is refused.** Under encoding B the plant
*is* the hardware, and `plant` is by construction the side that `./scripts/sim`, all three
scenarios and every Phase 1 artifact already address. So `backend: real` under
`twin.sides: pair` would silently point the whole existing test suite at a physical cell,
behind the same single opt-in that guards the far less alarming encoding — and the opt-in is a
bring-up refusal rather than a per-command one (Decision 2). It also buys nothing: charter §8's
Phase 2 is scoped as one physical arm and two simulated ones, which **is** encoding A by
construction, and encoding A is also what `MODE_VIRTUAL_LEAD` describes.

**So the schema refuses it:** a zone declaring `twin.sides: pair` may not contain an asset
whose `hardware.backend` is anything but `sim`. A physical machine on a paired zone is a
`counterpart_backend`. This costs nothing today — no instance in the model has ever named a
non-`sim` backend — and it is a clause of this decision rather than a revisit item, because a
configuration nobody wants is cheapest to remove before anything can produce it. **2.B may
reopen it**, with an argument and a reason, which is a different thing from leaving it
expressible by omission.

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
  field set beside it (Decision 2).
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
  **[2026-08-31: half answered, and the half that is answered is a refusal.
  [ADR-0050](0050-what-crosses-the-twin-boundary.md) decision 4 decides that the **mode never
  instantiates anything** — instantiation is a bring-up fact and mode is a runtime knob, on
  this record's own test — and leaves the fork itself open, restating it: the cheap side in
  `SHADOW` is the side that *follows*, which under Decision 3's side naming is the **plant**
  and not the counterpart.]**
- **When 2.B lands.** The counterpart is replaced by hardware and this record's central claim
  — that the shape of what the plant talks to did not change — is testable for the first
  time. If anything in the L5 interface has to change at that point, this decision failed at
  exactly the thing it was made for, and that must be written down rather than absorbed.
- **When the inconclusive ratio is re-measured**, on a target machine, with thresholds
  registered in advance. Nothing above is a reproduction claim.
- **When the mode set is extended, in every place it is written down — and it is written
  down in more places than anyone would guess.** `grep -rn CLOSED_LOOP docs
  workspace/src/cite_interfaces what-we-are-doing.md` finds them, and that command is the
  instrument rather than this list. At this commit it reaches **nine enumerations of the
  mode set**:
  `cite_interfaces/msg/TwinMode.msg`, the definition itself;
  `cite_interfaces/test/interfaces.baseline`, the frozen contract;
  [`docs/interfaces/README.md`](../interfaces/README.md), which copies the constant block
  verbatim as its worked example of an enumeration;
  [`L5-twin-synchronization.md`](../architecture/L5-twin-synchronization.md)'s five-row mode
  table, which also carries the level each mode sits at;
  [`docs/onboarding/glossary.md`](../onboarding/glossary.md)'s mode table;
  [ADR-0011](0011-twin-maturity-model-and-modes.md), amended by this change and the only one
  of the nine already done; and **three separate places in the charter** — §3.1's scope
  table, §5's L5 mode table, and §8's Phase 2 scope sentence.
  **[Corrected 2026-08-29 — see the Correction section above.]** **All nine are done, as of
  charter v1.9 — this bullet is now a record of what the sixth mode cost rather than a list
  of open work.** It is left in
  place because the seventh mode will pay it again.
  **Plus three dangerous-transition lists, which need a decision and not a paste** —
  `cross-cutting-safety.md` line 98, `L5-twin-synchronization.md` line 55, and
  `SetMode.srv`'s header — for the reason given beside Decision 2's gating paragraph.
  The charter is protected and changes only by explicit owner decision with a version bump
  (charter §12); ADR-0011 took an amendment rather than a supersession because its five
  levels, their literature mapping and its commitment are all untouched.
  **That one enumeration needs twelve locations in nine files to agree is itself a finding**,
  and it is P1's shape at the level of prose: a set defined once in `TwinMode.msg` and
  re-typed everywhere else cannot be kept true by care.
  **[Corrected 2026-08-29 — see the Correction section above.]** **Twelve is an undercount,
  and the grep named above is why: charter v1.9 records a thirteenth location,
  `DivergenceMetrics.msg`, which constrains the mode set in prose naming no constant and is
  therefore invisible to a `CLOSED_LOOP` grep, and a fourteenth in a file already counted.
  The instrument this bullet recommends does not find every site it is recommended for.**
  Nothing in `./scripts/lint` checks it, and nothing in this record proposes that it should — but whoever adds the seventh mode
  should read this bullet before deciding that by hand is good enough.
- **When `twin.sides` tests ADR-0004's wording, which must be *before or with* the schema
  change and never after.** Decision 3 places in L0 a fact about the modelled deployment
  rather than about the building, which is not what ADR-0004 says L0 is for. Either that
  record is amended to say L0 describes the modelled system, or a better home is found for
  the one key. The sequencing is not a preference: ADR-0004 is `Accepted`, so violating it
  is an `ESCALATE` rather than a review finding, and while this record is `Proposed` no
  violation exists — **the change that lands the schema is the change that creates one.** So
  the amendment ships in that commit or ahead of it. Do not settle it by leaving the two
  documents disagreeing, and do not settle it afterwards.
  **[2026-08-29: settled, and in the required order. `94561bf` landed the schema and amended
  ADR-0004 in the same commit; its index row reads `Accepted (amended 2026-08-29)`.]**
- **If a future Gazebo parallelises the physics step**, which the campaign names as the
  condition under which its core-count conclusion changes.
