# ADR-0028: Generate convex-hull collision meshes as project assets, bound through L0

- **Status:** Accepted (amended 2026-08-29 and 2026-09-01; corrected 2026-08-29, 2026-08-31 and
  twice on 2026-09-01) — **promoted on 2026-09-01, against the clause
  [ADR-0051](0051-restate-the-hull-grasp-gate.md) restates, by the change that moved
  `description.collision.select` to `convex_hull`.**
  **The campaign that satisfied clause 2a returned INCONCLUSIVE on its own question**, by a
  rule it registered before its first trial, and that sentence travels with the promotion:
  what carries 2c is a *geometric* clearance argument obtained twice by independent means, not
  a null result. **Read "Amendment — 2026-09-01: clause 2 is adopted as ADR-0051 restates it,
  and this record is promoted" first** — it is the newest section, it states the evidence clause
  by clause with the strength of each, and it lists the four things promotion does **not**
  establish, chief among them that the self-collision matrix is still the vendor's and that no
  work-piece narrower than the promoted range has ever been tested.
  **Everything below the amendment is left exactly as it stood**, including the sentence that
  the status stays `Proposed` and the shipped default stays on the vendor's meshes; both were
  true when written and neither is now.
  **[Replaced 2026-09-01, kept for the record:]** *"Proposed — implemented and not promoted,
  which is the amended gate working exactly as it was written to."* All four parts of the
  Decision are in the tree as of
  2026-08-31; the sentence above them, "decided in principle, nothing implemented", is
  superseded and is corrected in place below.
  **Corrected twice on 2026-09-01. The newer correction is the one to read first: clause 2 of
  the promotion gate, as written, cannot be met** — it asks for the consequences of a mechanism
  the campaign it demanded has measured not to occur, and the wedges it predicted sit 0.41 mm of
  aperture behind the pad plane on the same rigid link. **The decision stands entire, clause 1
  is untouched, the status does not move and the shipped default is still the vendor's meshes.**
  **[Amended 2026-09-01, later the same day — the status and the default both moved; see the
  amendment section named above. The rest of this paragraph stands.]**
  Clause 2 is restated — not relaxed — by
  [ADR-0051](0051-restate-the-hull-grasp-gate.md), which also makes the range of work-piece
  widths the finding covers binding on L0. See the section "Correction — 2026-09-01: clause 2
  asks for a measurement of a mechanism that does not occur", immediately after this block, and
  **read it before citing any gate clause or any gripper prediction below.**
  **The older 2026-09-01 correction: the implementation note's speed conclusion does not
  stand.** Its
  *"hulls move it materially and do not reach 1.0"* was read off a **throttled** measurement,
  which could not have exceeded 1.0 whatever the machine did; measured as capacity on the same
  machine, the hull pair clears the floor. **The decision, the gate and the shipped default are
  untouched** — clause 2 is still the friction-grasp re-run, that campaign measured cost and
  never correctness, and **nothing about hulls is cleared to ship by it.** See the section
  "Correction — 2026-09-01: the implementation note's speed conclusion was read off the wrong
  quantity", immediately after this block. **The shipped default is still the vendor's
  meshes**, and it stays there until clause 2 of the promotion gate is satisfied — see the
  section "Implementation note — 2026-08-31" for what landed and what promotion still needs.
  **Read "Correction — 2026-08-31: the gripper risk is real and it is not a filled
  inter-finger gap" before designing that measurement**: this record's stated hypothesis for
  it was wrong, and a re-run aimed at the sentence it used to carry would pass without asking
  the question. **[Corrected 2026-09-01 (the newer of the two corrections) — that measurement
  has since been designed against the 2026-08-31 hypothesis and run, and that hypothesis is
  wrong too. Read the newest correction section, named above, before reading this line as
  standing guidance.]**
  **[Replaced 2026-08-31, kept for the record:]** *"decided in principle, nothing
  implemented. No hull exists: `assets/` contains only `README.md` and `manifest.yaml`, no
  `assets/meshes/` directory has been created, and the L0 schema has no field through which a
  collision mesh could be bound to a vendor-described type. Promoted to `Accepted` by the
  change that lands the first hull and its binding (P7)."*
  **[Amended 2026-08-29: that condition is necessary and is no longer
  sufficient — see the amendment section named below.]**
  **Amended 2026-08-29, and the amendment tightens the promotion condition rather than the
  decision.** The re-measurement this record demanded now exists and supports it: it is the
  campaign
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  whose §3.1 lands in the pre-registered band *"material but not dominant"* and whose §5
  shows a pair missing real time with vendor meshes and meeting it with hulls.
  **The status does not move, for a reason this record already contains:** the campaign
  measured cost and never correctness, and this record's own warning about the gripper is
  still untested — and that warning was itself wrong about the mechanism until the correction
  of 2026-08-31 below. What promotion now additionally requires is in the
  section named "Amendment — 2026-08-29: the re-measurement landed, and the promotion gate
  is stated", below.
  **Corrected on the same day, for a different claim.** The decision stands entire and so
  does every argument for it. What does not stand is the *form* of one supporting figure: the
  Context section states real-time factor on the development host as **0.14**, flatly, with no
  condition and no machine. See the section named "Correction — 2026-08-29: the 0.14 real-time
  factor is stated as a fact and carries no condition", immediately after this block, **and
  its settlement note of the same day** — the figure does reproduce on a host of this class,
  under a condition (about one CPU core) that no record stated, and **collision geometry is
  not that condition.** **The urgency the figure was cited for survives the correction** — it
  is re-established by the campaign, on figures the campaign did register, and no longer rests
  on 0.14 at all.
- **Date:** 2026-08-25
- **Deciders:** Project owner, on the real-time-factor measurement from the Phase 1.C review wave
- **Related:** [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0012](0012-large-asset-storage.md), [ADR-0020](0020-facility-model-conventions.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) (added by the 2026-08-29 amendment),
  [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) (added by the 2026-09-01
  correction, which is where the throttled reading of this record's speed figures is fixed),
  [L1](../architecture/L1-description-and-assets.md), [`../../assets/README.md`](../../assets/README.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md),
  CLAUDE.md §10, charter §4 (P1, P5, P8),
  [ADR-0051](0051-restate-the-hull-grasp-gate.md) (which restates the promotion gate's clause 2;
  added by the second 2026-09-01 correction),
  [`docs/measurements/2026-09-01-hull-grasp/`](../measurements/2026-09-01-hull-grasp/ANALYSIS.md)
  (the clause 2 campaign, added by the same correction)

## Amendment — 2026-09-01: clause 2 is adopted as ADR-0051 restates it, and this record is promoted

**This is an amendment, not a correction, and it is the newest section on this record. The
three corrections and the earlier amendment below are left exactly as they stand** — including
the two corrections dated the same day, which sit immediately after this section and which a
reader should meet next. **Nothing in this record was measured false here.** What changes is
one clause of the promotion gate, adopted from another record, and the status that clause
governs.

### The clause, adopted verbatim

ADR-0051 restates this record's gate clause 2 rather than relaxing it. **Its decision 1 is the
wording, and it is quoted here as a single block** so that this record's gate is readable
without a second hop, and quoted rather than paraphrased so that there is one text and not two
(P1). Where they could ever disagree, **ADR-0051's copy is the original**.

> **Clause 2 (restated by ADR-0051).** ADR-0028 moves to `Accepted` only when, in addition to
> clause 1, all four of the following hold.
>
> **2a — the A/B exists and is published.** The friction-grasp campaign has been re-run against
> hull collision geometry on the shipped cell, published under
> [`docs/measurements/`](../measurements/README.md), with its thresholds registered before its
> first trial, its machine named, and the three quantities ADR-0028's correction of 2026-08-31
> requires reported per trial.
>
> **2b — no registered grasp metric is worse under hulls.** In that campaign, no pre-registered
> metric is DETECTED in the hull's disfavour at its own registered effect size, and its
> repetition and flung rules hold on the hull arm. A metric the campaign's own resolution rules
> refuse is evidence for neither side and does not satisfy this clause; neither does a
> difference below the size registered in advance as interesting, **in either direction**.
>
> **2c — where the predicted mechanism did not occur, its absence is geometric, independently
> obtained, and bounded.** The record states from the geometry why the mechanism does not occur,
> by two computations that do not share an instrument, and states the interval of work-piece
> widths over which the statement holds. An absence inferred only from a null result does not
> satisfy this clause.
>
> **2d — the validity range is declared here and binds L0.** Promotion carries the range of
> 2c with it. A work-piece narrower than that range may not ship against a derived collision set
> until 2a - 2c have been answered at its width; declaring one reopens clause 2.

**Clause 1 is untouched** and was satisfied on 2026-08-31; see the implementation note below.
**The question clause 2 was written to force is not withdrawn** — *does hull collision geometry
change how this cell holds a part?* — and the restatement exists because the clause as written
asked for the consequences of a mechanism the campaign measured not to occur, which is the
correction immediately below this section.

### Status: `Accepted`, clause by clause, with the strength of each

The evidence is
[`docs/measurements/2026-09-01-hull-grasp/`](../measurements/2026-09-01-hull-grasp/ANALYSIS.md),
whose figures are **cited and not copied** (P1). Read it rather than taking a number from here.

- **2a — satisfied.** The campaign exists, is published with its `criteria.md` committed before
  its first trial, names its machine, and reports all three quantities the correction of
  2026-08-31 demanded, per trial. **Its verdict on its own question is INCONCLUSIVE**, by a rule
  it registered in advance, and that is not a defect in it: rule S fired because the mechanism
  those three instruments were chosen to detect does not occur. **This record is promoted on a
  campaign that returned INCONCLUSIVE, and that sentence must travel with the promotion.**
- **2b — satisfied**, at **n = 24 vendor and 23 hull**, on **one machine**, at **one physics
  timestep**, with **one part** and **one arm**. No pre-registered metric was DETECTED in the
  hull's disfavour; the repetition and flung rules held on the hull arm. **This is not a claim
  that hulls grasp better.** Every outcome difference the campaign measured is below the effect
  size it registered in advance, in the hull's favour or not, and it declined to call any of
  them. **The honest statement is "no distinguishable difference at this n".**
- **2c — satisfied, over the range in ADR-0051 decision 3.** Two computations that share no
  instrument agree to **0.01 mm**: the arithmetic on this record's own geometry audit of
  2026-08-31, and the campaign's independent measurement from the running cell at the settled
  hold. Because both surfaces belong to **one rigid link**, the recess does not vary with
  aperture, so the absence is geometric rather than inferred from a null.
- **2d — carried by the change that lands this amendment.** `description.collision.select` on
  `model/assets/types/robots/xarm5.yaml` is `convex_hull`; the generated descriptions, the model
  hash and the generated `package.xml` move with it and nothing else does; and the range is
  enforced rather than written down —
  `cite_tools.validate.physical._derived_collision_is_within_its_measured_range` refuses a model
  that binds a derived set while declaring a work-piece narrower than the range, as an **ERROR**.
  The same change makes `_vendor_collision_is_declared`'s vendor-mesh finding an ERROR
  unconditionally, which that rule's own docstring required of the change that moves the default.

### What promotion does not establish

**Four things stay open, and `Accepted` closes none of them.** They are listed here rather than
left in the sections below so that nobody has to assemble them.

- **The self-collision matrix is still the vendor's, and it was computed against vendor
  geometry.** A convex hull is never smaller than what it replaces, so the matrix a promoted
  hull runs against is a function of a different collision set. The measured narrowing is in
  "Promoting hulls means the self-collision matrix no longer matches its geometry" below, and
  **that section is now describing the shipped state rather than a hypothetical.** Nothing in
  this repository checks the pairing.
- **`end_tool` is the one link where the hull trades fidelity for almost nothing.** It closes a
  through-feature and adds volume in exchange for **0.09 %** of the triangle reduction — the
  figure is this record's own, under "`end_tool` is the one link where the hull is worse", and
  it is not restated here. It is a candidate for the per-link exception this record foresees,
  `CollisionSpec` cannot express one, and shipping hulls ships this trade.
- **The 5.6 mrad earlier stall is DETECTED, is a control, and is unexplained.** It is the one
  metric the campaign detected at its registered effect size and it survived the block rule. The
  campaign was not looking there. ADR-0051 decision 4 names what would settle it; nothing here
  does.
  **[Added 2026-09-01: the leading candidate is now DISFAVOURED and not eliminated.]** The
  candidate ADR-0051 decision 4 names first — some hulled link other than the two pads touching
  the part — was tested against static geometry by the safety audit of that date, and it does
  not survive well: across the full drive stroke against a 50 x 50 mm face the closest non-pad
  link stays **5.04 - 5.16 mm** clear and the hull moves that by **≤ 0.001 mm**; the pad's own
  contact surface is unchanged at triangle level (22 faces, 1098.1 mm², same plane, both
  geometries); and tilting the face 2° to 40° keeps first contact at the pad's distal edge on
  both. **This is static geometry, not a run**, and the residual is not explained — nobody may
  write that it is. The observation that would settle it is unchanged: one block with the
  contact filter widened to every collision pair involving the work-piece.
- **The narrow-part case is untested.** No work-piece narrower than the range has been run
  against a derived set, and two things move together at a narrower width that the campaign
  separated neither of. That is why 2d is a refusal in the validator and not a sentence in a
  file.

### The interim self-collision check this record named is built, in a different shape

**Added 2026-09-01 by the review of the promoting change**, after a safety audit measured the
half nobody had. This record's residuals section names an interim measure — *"a check that
fails when a derived set is selected while the SRDF's matrix names the vendor's"* — and it now
exists, **keyed on an L0 declaration rather than on the selection alone.** The reasoning is
recorded because the first answer to this was to decline it, and the reason that answer was
wrong is the useful part.

**Why not the shape this record named.** Written that way the check fails on the shipped
configuration the moment it exists: a derived set *is* selected and the SRDF's matrix *is* the
vendor's, so it has no passing state to move towards. That is a **blocker**, not an interim
measure — either carried on every run, which is the state ADR-0051's rule exists to avoid, or
reverted. **But declining it left the residual with the largest measured effect guarded by
nothing**, while the narrow-part residual — which has no measurement at all — got a validator
rule in the same change. That asymmetry is what settled it.

**The shape that works is this record's own decision 4, applied a second time.** Decision 4
closed an identical structural hole for collision *meshes*: a vendor description is invoked and
never ingested, so no rule may open a vendor file, and the rule that would have caught the
defect returned an empty list for exactly the links where it occurs. The fix was to make **L0
declare what the vendor does**. So:

`model/assets/types/robots/xarm5.yaml` now carries `planning.vendor_self_collision_matrix`,
naming the collision set the vendor's matrix was audited against and the audit's figures, and
`cite_tools.validate.physical._vendor_self_collision_matrix_is_acknowledged` fails a model that
binds a derived set, invokes the vendor's SRDF macro, and **carries no acknowledgement — or one
audited against a different set.** The state becomes *declarable* instead of either silent or
unshippable, and changing either side reopens it. It is a guard, not a fix: it checks that a
human wrote the mismatch down, and it verifies no figure in the declaration.

**The sizing, which is what the declaration carries**, read from the generated SRDF and the
vendor macro by the model-validator review, and — for the second half — measured by the safety
audit of 2026-09-01:

- **78** geometry-bearing link pairs on the arm: **34** the vendor's macro leaves **enabled**,
  **44** it **disables**.
- The enabled half is covered by this record's own configuration sampling: **9 of 484** (1.9 %)
  newly self-colliding under hulls.
- **The disabled half had never been measured, and it is the half MoveIt never checks.** Four
  pairs interpenetrate under hulls where the vendor metal is 1.57 to 31.77 mm apart:
  `left_inner_knuckle`/`left_outer_knuckle` (**100 %** of 200 sampled configurations),
  `left_outer_knuckle`/`xarm_gripper_base_link` (**100 %**), `link3`/`link5` (7.1 % of 2025),
  `link2`/`link5` (1.0 % of 2744), `link2`/`link4` (0.25 %). The right-side gripper pairs
  mirror the left by construction.
- **No pair carries `reason="Always"`**, and a hull contains the mesh it replaces, so "a pair
  that always collided no longer touches" **cannot occur**. The asymmetry runs one way: a hull
  can make a disabled pair touch, never the reverse.

**The runtime consequence today, and the one that is one edit away.** The 44 disabled pairs
have **no effect on the running cell**: MoveIt's allowed collision matrix excludes them from
planning, and Gazebo computes no same-model self-contacts — `grep -rn self_collide` returns
nothing anywhere relevant and SDFormat defaults it false. **That default is the only thing
holding it.** Setting `<self_collide>true</self_collide>` is an ordinary fidelity improvement
nothing here argues against, and under hulls it would put permanent contact between the gripper
linkage from the instant the model spawns — the drive joint stalls, `gripper_is_holding`
reports an empty grasp on every pick, and the hardware backend does none of that, which makes
it a **P2 divergence with the simulation as the broken half.** `cite_tools.generate` now
refuses to emit that combination. The interpenetration is measured and exhaustive over the
sampled stroke; **the consequence is reasoned from SDFormat's documented semantics and has not
been observed on a running cell**, and must not be written up as though it had.

**The obvious next step is not obviously right.** Regenerating the matrix from the *selected*
geometry would disable pairs on the strength of hull material that does not exist. On this arm
nothing is lost, because the always-interpenetrating hull pairs are the gripper linkage the
vendor already disables and whose real gap is 1.57 mm — **but that is a measured fact about
this robot, not a property of hulls**, and it is recorded here because until 2026-09-01 the
tree did not carry it. Re-deriving the matrix per selected set, as a generated artifact,
remains owed its own record.

**Also done, and smaller.** The generated SRDF's own header now says the pairing is broken, in
the file a MoveIt debugger opens first (`tools/cite_tools/templates/moveit/srdf.xacro.j2`, and
the same sentence on `PlanningSpec`). It used to read *"the self-collision matrix, which is a
property of the vendor's geometry rather than of our facility"* — a pairing that stopped
holding on 2026-09-01.

### The hull adds no clearance, in any external direction

**Added 2026-09-01, and it is here because the opposite is the natural inference.** "Twelve
links per arm now collide against a proper collision shape" reads as "the arm is fatter, so it
stops sooner". It is not.

Measured by the safety audit over **20,000 random directions on all thirteen hulls: the hull's
support function exceeds its source's by +0.000000 mm.** Every gram of added material is inside
a concavity. An object approaching a link convexly from outside therefore contacts it at
exactly the same distance as before.

Two consequences to carry:

- **ADR-0027's sampling residual is completely unaffected.** `ValidateSolution` checks
  trajectory waypoints and interpolates nothing between them at a 0.1 s step, so a tool point
  above 0.40 m/s can step past the 40 mm beam housings in the generated planning scene.
  Tunnelling is an approach from outside; the hull narrows that window by nothing.
- **Hulls may never be cited as margin in a safety case.** What they buy is simulation capacity
  and contact fidelity, not clearance.

**What is still unmeasured** is environment clearance at the cell's actual working poses. At
`home` and `hold-up` every hull-to-scene clearance is identical to the vendor's to 0.00 mm, and
per link a hull can eat at most its own concavity depth — 14.07 mm at the gripper base,
21.76 mm at `link4`, 60 - 62 mm at `link2`/`link3`. Static geometry cannot settle it; the cheap
settlement is to replay the trajectories the existing scenarios produce and report per-waypoint
minimum link-to-object distance under both geometries.

**And every figure behind 2b is one machine at one `max_step_size`.** That constant is a
generator constant, ADR-0029's friction campaign found grasp behaviour strongly sensitive to it
across a 4x change, and **Phase 3's physics retune reopens 2b** — ADR-0051 decision 5, carried
here because a promoted record is where people stop reading.

## Correction — 2026-09-01: clause 2 asks for a measurement of a mechanism that does not occur

**This is the second correction dated 2026-09-01 and the newest on this record. The other
three are left exactly as they stand**, and the one immediately below this section is today's
other one — the implementation note's speed conclusion. **No status moves here, nothing is
promoted, and the shipped `select: vendor_meshes` is untouched.** What replaces the clause is
[ADR-0051](0051-restate-the-hull-grasp-gate.md), which **restates it rather than relaxing it**
and is `Proposed`.

**What was wrong.** Two claims, both in the correction of 2026-08-31, and the second of them
became a promotion condition:

- the inference *"both shoulders lie inside the part's envelope"*. It compares the shoulder's
  aperture against the part's **width**, at the **commanded** 45 mm — a configuration a gripper
  holding a 50 mm rigid part never occupies. The comparison that decides contact is the shoulder
  against the **pad plane**;
- the prediction built on it — two inclined wedges contacting the part's flat face at a slope,
  hence a net translation, possibly a pitch about the finger-pivot axis, and a contact patch
  growing from 37 mm to 44 mm. **Measured, none of it happens**, and the patch got *shorter*,
  not longer.

**So clause 2 of the promotion gate, as written, cannot be met.** It asks a campaign to report
the consequences of a mechanism that does not occur, and no amount of measuring produces them.

**What is true, measured**, from
[`docs/measurements/2026-09-01-hull-grasp/`](../measurements/2026-09-01-hull-grasp/ANALYSIS.md)
— 47 trials, thresholds registered before the first trial, machine named, figures **cited and
not copied** (P1):

- The hull's wedges are recessed **0.41 mm of aperture behind the pad plane, on the same rigid
  link.** That is arithmetic on **this record's own two audit numbers** — 45.40 mm at the
  z = 134 shoulder against 44.99 mm at the pad — and needs none of the campaign's apparatus. The
  campaign measures the same clearance independently at **0.42 mm**; the two agree to 0.01 mm.
- Because both surfaces belong to one rigid link, that recess does not vary with aperture, so a
  flat face resting on the pad is clear of the wedges **at any aperture**. The jaws stall on a
  50 mm rigid part at a measured **~50.0 mm**, not at the commanded 44.99 mm.
- **The campaign's verdict is INCONCLUSIVE**, by its own rule S, registered before its first
  trial. It must be cited as that. A campaign that cannot see the mechanism has not tested the
  prediction, and its silence about the grasp is not a pass.

**What survives, plainly.** **The decision stands entire, all four parts**, and clause 1 of the
gate is untouched. **The geometry audit of 2026-08-31 is confirmed** — its aperture figures are
right, and they are what makes the clearance computable. **The question clause 2 was written to
force is not withdrawn**: ADR-0051's restatement keeps it and asks for evidence that can exist.
And this record's statement of its own principal risk — *"a part that is held slightly
elsewhere, not a part that is not held"* — is neither confirmed nor refuted in general: it was
not observed at the 50 mm width, and **no narrower work-piece has been tested**, which is the
validity range ADR-0051 makes binding.

**What this does not claim.** It does **not** promote this record and may not be cited as doing
so. Every grasp-outcome difference the campaign measured is **below the effect size registered
in advance**, in the hull's favour or not, and the campaign refused to call any of them; the
honest statement is *no distinguishable difference at that n*, never *hulls grasp better*. The
one metric it DETECTED is a **control** — the jaws stall 5.6 mrad earlier on hulls — and it is
**unexplained**. Both residuals, and what would settle them, are ADR-0051 decision 4.

**How the error survived.** This record caught one false gripper mechanism on 2026-08-31 and
replaced it, the same day, with a second one derived the same way: from a static audit taken at
a **commanded** configuration, with no step asking whether the system ever occupies it. The
audit's numbers were never wrong; both errors were in what was compared against what — first a
hull against the wrong space, then a shoulder against the part's width instead of against the
pad plane. Then the gate was written against the new mechanism, so an unobserved prediction
became a promotion condition, and the only thing that could have caught it was the campaign that
eventually did. The transferable part is two sentences: **an audit taken at a commanded value
must state whether the machine ever reaches that value**, and **a promotion gate must not be
written against a mechanism nothing has yet observed** — name the measurement, as this record's
own 2026-08-29 amendment says, but not the mechanism's fingerprint.

## Correction — 2026-09-01: the implementation note's speed conclusion was read off the wrong quantity

**Three correction sections and one amendment now sit in this record; this is the newest and
the others are left exactly as they stand.** **No status moves here, and this section may not
be read as clearing hulls to ship** — see "What this does not do", below, before citing it.

**What was wrong.** The implementation note's *"Hulls move it materially and do not reach
1.0"*, its *"about 1.10x per side"* gain, and its closing comparison against ADR-0043's
predicted 1.162/1.173. Every figure in the table those sentences read — the row clustering at
**0.949** — was taken with the generated world's throttle in force, and under that throttle a
measured real-time factor is **capped at the declared 1.0 by construction**
([ADR-0049](0049-measure-the-real-time-floor-as-capacity.md), read in upstream `gz-sim`
source). A measurement that cannot exceed 1.0 was compared against 1.0 and reported as failing
to reach it.

**What is true, measured.** The campaign ADR-0049 asked for —
[`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md),
24 trials, a 2x2 of both geometries by both throttle states, both sides of every pair sampled
in one window, thresholds registered before the first trial and its machine named — measured
the same lever on the same machine as **capacity**, with the throttle lifted. **The hull pair
clears the 1.0 floor and the vendor pair does not.** The figures, the margins and the
block-paired hull gains at each throttle setting are that campaign's and are cited rather than
copied (P1); read its §3, §4 and §6 rather than taking a number from this paragraph.

**This is ADR-0049's cap effect caught changing a record's conclusion**, which is exactly the
failure that record derived from source and predicted would be sitting in existing figures.
Two things it costs this record specifically: the *"1.10x on this host against 1.35x on the
campaign host"* discrepancy that ADR-0049 reasoned around is reproduced whole on one machine
at two throttle settings, so it needs no second host; and ADR-0043's predicted margin, recorded
here and in that record as not reproducing, does reproduce once the quantity is the one the
prediction was about.

**Three things the campaign says about its own figures, carried here because a reader who
cites it should meet them at the same time.**

- **Every capacity figure it reports is a lower bound.** Its `criteria.md` §8 measured the
  host's contention *before* the first trial — of the order of 1.5 - 2 cores busy on a 12-core
  machine with nothing of the campaign running — and recorded that it could not be made quiet.
  That direction cannot manufacture headroom.
- **One validity rule was found to read the wrong load and was applied literally anyway.** V6
  reads the container VM's load average, not the macOS host's, so it tested how far the
  previous trial's teardown had drained; it excluded 4 of 24 trials. The unexcluded medians
  are **larger in every case** and no conclusion changes sign (its Deviation 1).
- **It measured cost, and never correctness.** Its §9 says so in terms.

### What this does not do

**It promotes nothing, and the promotion gate is untouched.** Clause 2 of the amended gate —
the friction-grasp campaign
([`../measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md))
re-run against hull geometry, against its already-written thresholds, reporting the three
quantities the 2026-08-31 gripper correction names — is unsatisfied, and this campaign is not
it and does not bear on it. The status stays `Proposed`, the shipped default stays on the
vendor meshes, and **no document may read this section as evidence that hulls are safe for
this cell.**

**It does not establish that any requirement passes, either.** ADR-0049 keeps the 1.0 floor
and **sets neither of its two thresholds**; the capacity margin above 1.0 is reserved by its
decision 2 and is not set here. Every cell in the campaign is **idle at home pose**, and an
idle margin is not a work allowance. So "the hull pair measured above 1.0 on this machine,
idle" is the whole of the claim.

**How the error survived.** The note asked *"how fast does a hull cell run?"* and answered it
correctly with an instrument whose ceiling was the very number it then compared against. What
it never asked is what a **passing** measurement would have looked like — the question
ADR-0043's 2026-08-31 correction had, on the same day, named as the only way to tell a
requirement nothing can pass from a machine that keeps failing one. That lesson was written
into the record that raised it and nowhere else, so the figures already sitting in *this*
record, taken with the capped instrument and compared against the cap, were never re-read
against it. The transferable part: **when one record establishes that an instrument is
capped, every figure anywhere that was taken with that instrument and compared against the cap
is stale that same day** — the fix belongs in a grep across the tree, not in the record that
made the discovery.

## Correction — 2026-08-29: the 0.14 real-time factor is stated as a fact and carries no condition

**What is wrong is the claim's form, not necessarily its number.** The Context section below
says *"Real-time factor on the development host is **0.14**"* — present tense, a machine class
rather than a machine, and no statement of what the cell was doing at the time. Read as
written it is a reproducible property of anyone's development host. It is not one.

The campaign [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md)
measured an idle three-arm cell on a host of that class and **could not reproduce it**; its
*"An absolute, and a contradiction"* section records the gap as a factor of **7.8** and states
plainly that **the figure in the tree carries no condition and no machine**. The campaign is
equally plain that it **does not replace the number**, because it did not measure the same
thing: the two halves of the recorded figure — the real-time factor and the `joint_states`
rate — are internally consistent with each other, so whatever produced them was a genuinely
much slower configuration. A different Mac, a different Docker CPU allocation, or a cell that
was not idle. **The record does not say which, and neither does this correction.**

**No number is substituted here, deliberately.** A campaign is re-measuring the development
host's real-time factor with its condition written down, and this record must not front-run
it. Until that lands, the correct way to cite the figure is *"0.14 was recorded, under a
condition nobody wrote down, and does not reproduce"* — never *"the development host runs at
0.14"*.

**What survives, and it is the part the decision rested on.** The urgency this record claimed
is not weakened. It is now carried by figures the campaign *did* register: collision geometry
is a material contributor on a pre-registered A/B (`G` in the band `1.25 <= G < 2.0`), the
geometry counts in the Context section were independently recomputed and reproduced exactly,
and a pair of cells misses real time with vendor meshes and meets it with hulls. **The
decision, all four parts of it, and the amendment's promotion gate are untouched.** So is the
observation that every wall-clock ceiling in the scenario suite was chosen against 0.14 —
that is a fact about how the ceilings were written, and it stays true whatever the figure was.

**This qualification travels with the number.** It applies wherever 0.14 appears in this
record, including the two places that use it as a re-measurement baseline; those read
correctly as "the figure recorded in the tree", not as a measured property of a machine.

**How the error survived review.** The figure entered as an observation on one machine on one
day and was written down as a present-tense property of "the development host" — one sentence,
no condition, no date, no machine. From there it was quoted into `CLAUDE.md` and into
`tests/scenarios/bringup.py`, where it became load-bearing for every wall-clock ceiling in the
suite, and each quotation made it look better attested than it was. Nobody could have
challenged it by reading, because the sentence contained nothing to challenge: **a measurement
with no condition attached cannot be contradicted, only re-taken.** The transferable rule is
the one this project already applies to campaign results and had not yet applied to a figure
in prose — state who measured it, on what machine, doing what, and over how many runs, or do
not state it.

### Settled the same day: the figure reproduces, under a condition, and the condition is CPU

**The campaign this section was waiting for has landed and it answers the paragraph above
rather than replacing it:**
[`docs/measurements/2026-08-29-real-time-factor-conditions/`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md).
Its pre-registered verdict is **CONDITIONAL, not "does not reproduce"**. The recorded pair —
the real-time factor and the `joint_states` rate — reproduces on a host of this class, **both
halves together and by two independent instruments, when the cell is confined to about one CPU
core.** Unconfined, that host idles slightly above real time. Bring-up and load were tested as
candidates and rejected.

**The three guesses this section offered are not all closed.** "A different Docker CPU
allocation" is confirmed as *sufficient*; "a cell that was not idle" is measured and rejected;
and whether the recorded figure actually came from an allocation or from contention on a shared
host is registered by the campaign as unestablished and unestablishable from here. The figures
are cited, not copied (P1); the one place in the tree that states the figure **with** its
condition is [`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md) under
"Wall-clock ceilings".

**The citation form prescribed above is superseded.** Cite it as *"0.14 was recorded, and
reproduces on that host confined to about one CPU core"*. *"The development host runs at
0.14"* stays as wrong as it was.

**What this changes in this record is one attribution, and it is this record's own.** The
Context section below heads the figure *"The measurement that gives it urgency"*. **Collision
geometry is not why that host reached 0.14 — a one-core allocation is**, so the figure is not
evidence for hulls and never was, and the heading now says so. The same applies to the
*"What we will have to revisit"* clause *"if 0.14 does not move materially, the bottleneck is
elsewhere"*: it must be read against the **second-world campaign's** measured hull effect,
which the amendment below already reports against its pre-registered band, and never against
this figure. Nothing else moves. **The decision, all four of its parts, the status and the
promotion gate are untouched** — the case for hulls rests on the second-world campaign's
measured cost of collision geometry and on its pair of cells that misses real time with vendor
meshes and meets it with hulls, both of them cited in the amendment below.

## Amendment — 2026-08-29: the re-measurement landed, and the promotion gate is stated

**This is an amendment, not a correction.** Nothing in this record was measured false, and
the correction above does not contradict that: what it repairs is the *form* of one figure —
stated flatly, with no condition and no machine — and not the truth of any claim this
amendment rests on. The two sections are about different things and both stand. Two
things changed around this record: the re-measurement the record itself demanded was carried out and
supports the decision, and one clause of the status block — the condition for promotion — is
tightened as a result. The decision is untouched: collision geometry for vendor-described
links is a convex hull, generated as a project asset from the vendor's visual mesh and bound
to the robot type in L0.

### The re-measurement this record demanded

The Decision section ends: *"No status improves on the strength of this record ... the claim
that this improves real-time factor is earned by re-measuring RTF and `joint_states`
frequency against the 0.14 / ~21 Hz baseline, not by asserting that hulls are faster."*

That re-measurement is
[`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
whose Q3.1 is a pre-registered A/B on this exact substitution. It is **cited and not restated**
(P1); read it rather than this summary. Four of its results bear on this record:

- **The geometry count in the Context section above is confirmed by independent
  recomputation.** The campaign's harness recomputed the hulls from the same STLs rather than
  quoting this record, and reproduced its numbers exactly: **98,292 triangles** across the
  twelve links, **9,810** in their hulls, a **10.0x** reduction.
- **`G = RTF(hull) / RTF(vendor)` fell in the pre-registered band `1.25 <= G < 2.0`**, on both
  the ratio-of-medians figure the campaign registered and the within-block figure it reports
  beside it. The band's reading, written before the first trial, is *"collision geometry is a
  material but not dominant contributor. Hulls help; something else also has to move."* The
  campaign's decision rule was deliberately written so that it could disappoint this record,
  and it did not — but neither did it promote hulls to the cause of the problem.
- **The ablation says how much else there is.** Collision geometry is a third of the whole
  step; the arms dominate it; and the majority of the arms' cost survives hulls. This record's
  *"What we will have to revisit"* clause — *"if 0.14 does not move materially, the bottleneck
  is elsewhere"* — therefore fires **partly**: the figure moves materially, and the bottleneck
  is also still elsewhere. Both halves are true and the record must not be cited for only one.
- **The strongest evidence yet, and it is a Phase 2 result rather than a Phase 1 one.** With
  vendor collision meshes a *pair* of cells misses real time; with hulls the same pair on the
  same machine, in the same run design, meets it. That is the difference between failing and
  meeting the condition
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) sets, bought with geometry rather than
  with hardware. **It is one run**, and the campaign labels it as one.

### What the campaign does not license

**It measured what a hull costs. It never measured what a hull breaks.**

That limit was registered in `criteria.md` §8 *before* the first trial and repeated unchanged
in the write-up afterwards: **no grasp was attempted under hull geometry.** This record's
*"What we will have to revisit"* already names the case — the gripper fingers are the links
whose exact geometry decides whether a part fits, and they are the links a convex hull
approximates worst — and it remains untested. Grasping in this cell is held by friction alone
with no simulation aid ([ADR-0029](0029-simulated-grasping-by-friction.md)), so the contact
surface *is* the mechanism, and a real-time-factor result cannot say anything about it.

**A speed result is not a licence to ship geometry.**

### The promotion gate, stated so that whoever lands the first hull cannot miss it

The status block said promotion follows "the change that lands the first hull and its
binding". **That is necessary and is not sufficient.** ADR-0028 moves to `Accepted` only when
**both** hold:

1. **The first hull and its L0 binding exist**, as the status block already required — the
   `tools/` pipeline stage, the asset with provenance in `assets/manifest.yaml`, the L0 field,
   and `_collision_is_not_a_visual_mesh` extended to the `xacro_macro` provider. All four
   parts of the Decision, not the first one.
2. **The friction-grasp campaign has been re-run against hull collision geometry and its
   result published** —
   [`docs/measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md)
   is the campaign to repeat, and the question it must answer is whether the hull geometry
   changes grasp behaviour. Its thresholds are already written down, which is what makes the
   comparison meaningful.
   **[Corrected 2026-09-01 — see the newest Correction section above. This clause, as sharpened
   by the 2026-08-31 correction, cannot be met: it asks for the consequences of a mechanism the
   re-run measured not to occur. The re-run exists and is published; the clause that replaces
   this one is [ADR-0051](0051-restate-the-hull-grasp-gate.md) decision 1, which restates it
   rather than relaxing it and adds the range of work-piece widths the finding covers. **The
   question above is not withdrawn** and the amendment's own lesson — a promotion condition
   names the measurement, not the commit — stands.]**

Until both hold, hulls may be generated, measured and reviewed, and this record stays
`Proposed`. **No document may cite the speed result as having settled this decision**, and no
change may promote the status on the strength of a real-time-factor figure alone.

### How this needed amending at all

The part that transfers: this record set its own promotion condition in terms of the *work*
(landing a hull and its binding) while stating its principal risk in terms of an *unmeasured
behaviour* (what the hull does to the grasp). Those are not the same test, and a condition written
against the work would have been satisfied by a change that never asked the question the
record itself raised. A promotion condition has to name the measurement, not the commit.

## Implementation note — 2026-08-31: all four parts landed, the default did not move

**Clause 1 of the promotion gate is satisfied and clause 2 is not, so the status stays
`Proposed`.** That is the amendment above working as written: the change that landed the
hulls is not the change that may promote this record.

### What is in the tree

- **Decision 1, the pipeline.** `cite_tools.meshes` plus `cite-model hulls`, host-agnostic,
  unit-tested. Without `--write` it re-derives every declared mesh from the vendor file and
  compares byte for byte, so a hull that has gone stale against a vendor bump is a failure
  rather than a silence. `scipy` is a new dependency in layer 3 of `requirements/README.md`.
- **Decision 2, the assets.** Thirteen hulls under
  `assets/meshes/collision/xarm5/convex_hull/`, each with the digest of the vendor file it
  came from, that file's pinned commit and its own digest, in a machine-written `derived:`
  region of `assets/manifest.yaml`. A new ament package, `cite_description` — charter §7's
  L1 package, created for the first thing that needed it — installs `assets/meshes` so the
  URIs resolve.
- **Decision 3, the L0 binding.** `DescriptionSpec.collision` declares the available sets and
  which one is bound; the generator emits the root as the *vendor macro parameter the model
  names*, exactly as every other vendor argument is bound. It is **per robot type**, and the
  per-link exception this record foresees for the gripper fingers is deliberately not
  attempted: that exception is *a primitive instead of a mesh*, which is a different
  mechanism, not a finer granularity of this one.
- **Decision 4, the validator.** `validate.physical._vendor_collision_is_declared` reads that
  declaration. A vendor description that declares nothing is an ERROR; one that declares the
  vendor's own meshes is a WARNING. **WARNING is a compromise and it is recorded as one:** the
  shipped state is deliberately still the vendor's meshes, and an ERROR would fail
  `./scripts/validate-model` on a state this record requires the project to stay in until
  clause 2 is met. `--strict` makes it an error today, and the change that moves the default
  must make it one unconditionally.
- **The vendor patch this needed.** `external/patches/03-xarm_ros2-collision-mesh-root.patch`.
  The vendor's `mesh_path` roots visuals and collisions together and is a property rather than
  a parameter, so there was no caller-facing way to say where collision geometry lives. The
  patch adds one parameter, defaulted to empty, and empty means "with the visuals" — so every
  other caller in the vendor tree expands unchanged.

### The geometry, and where it disagrees with the campaign by two triangles

The count reproduces: **98,292 vendor triangles across the twelve rendering meshes**, exactly
as the Context section states and as the second-world campaign independently recomputed. The
hulls come to **9,812** rather than the campaign's 9,810 — a **10.02x** reduction. The two
triangles are not a discrepancy to resolve: they are the different, and deliberately
stricter, canonicalisation this pipeline applies to make the output reproducible on a second
machine. The thirteenth mesh, the vendor's own `end_tool` collision proxy, goes 260 -> 180 —
**80 triangles, which is 0.09 % of the reduction, in exchange for +6.0 % volume and a closed
through-feature. It is the one link where this trade goes the wrong way**, and the numbers are
under "Residuals recorded 2026-08-31" below.

### What reproducibility cost, because the record asked for byte-identity

Decision 1 requires "a regenerated hull is byte-identical or the change is real". Reaching
that took three canonicalisations and **the third was only visible across machines**: with the
input and the output sorted, three of the thirteen meshes still hashed differently on macOS
and in the Linux container under the *same pinned scipy*. Identical hull vertex sets,
identical face counts, different diagonals across the flat faces. Each facet is therefore
re-triangulated by the pipeline rather than taken as Qhull cut it. The residual that remains
is coarser and is stated in the module: Qhull could still *merge* facets differently between
versions.
**[Corrected 2026-08-31 on both halves.** "Across machines" and "the two platforms measured"
mean macOS/arm64 and the Linux container **on one CPU architecture**; x86_64 is untested and
this branch has never run in CI. And the module named Qhull's residual while omitting its own
bearing-ordering one, whose measured margin is now recorded there. See "Residuals recorded
2026-08-31" below.**]**

### The speed figures, and their strength

**These are not a campaign.** One machine, no thresholds registered in advance, no directory
in `docs/measurements/`, taken by the implementing agent of this change. They are recorded
here for the same reason ADR-0043's are, and must be cited with their strength or not at all.

A **pair** was measured the way the second-world campaign measures one — `d(sim)/d(real)` from
each side's own `/world/cell_a/stats`, both sides sampled concurrently in one 120 s wall
window, never Gazebo's `real_time_factor` field. Two windows per condition:

| condition | plant | counterpart |
|---|---|---|
| vendor meshes | 0.8655, 0.8495 | 0.8697, 0.8541 |
| convex hulls | 0.9497, 0.9488 | 0.9490, 0.9492 |

**Hulls move it materially and do not reach 1.0.** **[Corrected 2026-09-01 — see the
Correction section above. Every figure in the table is throttled, so it could not have
exceeded 1.0 whatever the machine did; read as capacity, the same lever on the same machine
clears the floor.]** The gain is about **1.10x** per side, which
is below the 1.25-2.0 band the second-world campaign's `G` fell in for a solo cell — a
different quantity on a different host, and not a contradiction, but not a confirmation
either. **[Corrected 2026-09-01 — the 1.10x is the *throttled* gain, and the capacity gain on
this machine is larger; see the Correction section above.]** **The finding that matters is the negative one: [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s
requirement that both sides sustain 1.0 concurrently is still NOT met**, on this host, with
hulls. That record's 2026-08-30 correction predicted 1.162/1.173 from the campaign's figures;
this host does not reach it. **[Corrected 2026-09-01 — both sentences are read off the
throttled table above. The capacity measurement exceeds that prediction; what remains true is
that nothing here establishes a *pass*, for the reasons the Correction section gives.]** No ceiling, tolerance or `real_time_factor` was touched.

### That the hulls actually render, which is a different question from that they are fast

Verified at runtime rather than by reading the generator. With `select: convex_hull` the
description published on a **running** cell's `robot_description` carries **13 collision mesh
references, all under `cite_description`, and 13 visual references, all still under
`xarm_description`** — so the substitution reached the collision geometry and nothing else. A
pair came up on hulls, both sides announcing readiness, and `./scripts/scenario bringup`
passes against them.

### Corrected 2026-08-31: the substituted root did not resolve the way the vendor's does

`generate/description.py` emitted `file://$(find <package>)/<root>` unconditionally, and the
root it substitutes for does not: `xarm_device_macro.xacro` sets `mesh_path` to
`file://$(find xarm_description)/meshes` for a Gazebo plugin and to
`package://xarm_description/meshes` for anything else. So with a derived set selected and
`backend: real`, one description came out with **`package://` visuals and `file://`
collisions** — the collision half an absolute path into the generating machine's install
prefix, which is unportable, and which is the half a planner uses. It was right on `sim`,
where every scenario runs, and wrong on `real`, where nothing runs yet; that is why nothing
saw it.

The scheme is now L0 data — `description.collision.root_uri_scheme`, one entry per declared
backend, **required whenever a derived set is declared and with no default**, so that
flipping `select` is still one field and adding a backend is a decision rather than an
omission. Deriving it in the generator was the alternative and was rejected: it would put the
vendor's three Gazebo plugin class strings into a generator whose entire knowledge of the
vendor package is meant to be model data (`DescriptionSpec`'s docstring).

Two things follow that are not this record's own. Patch 03's header claimed *"the only
asymmetry is the vendor's own"* — true of the patch, false of the system, and corrected in
place. And the L0 change moves `MODEL_HASH`; no other generated artifact moves, because the
shipped selection still emits no collision argument at all.

### What promotion still needs, stated so it cannot be mistaken for done

**[Corrected 2026-09-01 — see the newest Correction section above. The re-run this section asks
for has been run and published, and it establishes that clause 2 as written cannot be met.
What promotion needs today is the restated clause,
[ADR-0051](0051-restate-the-hull-grasp-gate.md) decision 1, and that record's decision 2 says
what the promoting change has to do. The two paragraphs below are left as they stand.]**

**Only clause 2 of the amended gate**, unchanged: the friction-grasp campaign
([`../measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md))
re-run against hull geometry, with its already-written thresholds, and its result published.
**Do not design that re-run from this section alone.** The hypothesis it would have been aimed
at was wrong: read "Correction — 2026-08-31: the gripper risk is real and it is not a filled
inter-finger gap" below, which names the three quantities the re-run has to report and why
neither of the campaign's two published residuals is one of them.
Both geometries now exist and are selectable by one field, which is what that A/B needs.
**[Corrected 2026-08-31: "one field" was not true when this was written.** The generated
`package.xml` derived its dependencies from `description.package` and `planning.srdf_package`
only, so a selection that emitted `$(find cite_description)` into every arm description left
the generated package declaring nothing about it — the invariant `generate/package.py`'s own
docstring states, violated by decision 3. `cite-model`'s dependency derivation now follows
the selected set, and `tools/tests/test_collision_binding.py` asserts both directions: the
dependency appears when the set is bound and stays away when it is merely declared. Flipping
the field is now genuinely the whole change.**]

**Nothing in this section is evidence for it.** No grasp was attempted under hull geometry by
the change that wrote this, deliberately: a casual opinion about grasp quality from an
incidental run would poison a campaign whose thresholds are pre-registered. The speed figures
above are a cost measurement and say nothing about what the hull does to the grasp, which is
this record's own principal risk — and which this record described wrongly until the
correction of 2026-08-31 below.

## Correction — 2026-08-31: the gripper risk is real and it is not a filled inter-finger gap

**This record said in three places that a convex hull "fills the space between the fingers".
It does not, and the sentence has to go because it is the hypothesis clause 2 of the
promotion gate would be tested against.** The three places were this record's own
Consequences bullet under *"What this costs us"*, the same claim restated in
`model/assets/types/robots/xarm5.yaml`, and `CollisionSpec`'s docstring in
`tools/cite_tools/model/schema.py`; a fourth restatement, in
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s revisit list, is corrected with them.
All four now point here.

**Why it was wrong, structurally.** Each link is hulled independently — the L0 set names
thirteen mesh files and `./scripts/hulls` derives one hull per file. `left_finger` and
`right_finger` are two of them, so the space between the fingers is the space between two
separate collision bodies, and no per-link hull can occupy it. Filling it would take a hull
over the *assembly*, which this pipeline never computes.

### What the hull actually changes, measured

Geometry audit of 2026-08-31, taken from the committed hulls and the pinned vendor meshes.
**This is a static measurement of shape, not a campaign and not a simulation run: no grasp
was attempted, and nothing here is evidence about grasp quality.** There is no directory in
[`docs/measurements/`](../measurements/README.md) behind it, and no threshold was registered
in advance. Distances are along the jaw axis; `z` is height in the same frame the audit read
the meshes in.

- **The jaw aperture at the pads is unchanged.** At the shipped 45 mm command it is
  **44.99 mm on both geometries over the entire 37 mm pad**, identical to 0.01 mm. The pad
  plane, the first contact and its normal are the same on both.
- **Each pad's own relief shoulders change, and they are inside the part.** The vendor finger
  steps back 2.0 mm just proximal and just distal of the pad; the hull ramps across both
  steps instead. Aperture goes **48.99 → 46.28 mm at z = 132**, **48.99 → 45.40 mm at
  z = 134** and **48.99 → 47.66 mm at z = 173**. The 50 mm work-piece spans z ≈ 128.4–178.4,
  so both shoulders lie inside the part's envelope *in both geometries* — the hull's are
  1.2–1.9 mm deeper. **[Corrected 2026-09-01 — see the newest Correction section above. The
  aperture figures are confirmed; the sentence after them does not follow from them. It
  compares the shoulder against the part's width at the *commanded* 45 mm, and the jaws stall
  on this part at ~50.0 mm. Compared against the *pad plane*, which is what decides contact,
  the z = 134 shoulder is 0.41 mm of aperture clear at every aperture.]**
- **The outer-knuckle hook narrows**, z = 55–68 mm, throat **67.6 → 40.4 mm**. That is 60 mm
  below the part and below a pinch the vendor already has, so it is a planning effect and not
  a grasp effect.

### The prediction, stated so that a re-run can be designed against it

The hull adds two inclined wedges, at the proximal and the distal end of each pad, which
contact the part's flat face at a slope. Inclined contact against a flat face carries a force
component **along the approach axis**; the two wedges push in opposite directions and are not
symmetric in length. So:

- expect a **small net translation of the part along the jaw axis during closure**;
- possibly a **pitch about the finger-pivot axis**;
- an **effective contact patch growing from 37 mm to 44 mm**.

**[Corrected 2026-09-01 — see the newest Correction section above. The whole of this
prediction, including the paragraph above the three bullets, is measured false for a 50 mm
part: the wedges never contact it, no bullet was detected at its registered effect size, and
the contact patch got *shorter*. The wedges are real; the contact is not.]**

**Nothing here predicts a failed grasp.** The pad still makes first contact, at the same
width, everywhere along it. The risk this record should have been naming is a part that is
held slightly *elsewhere*, not a part that is not held.

### What clause 2 of the promotion gate must measure

This is the reason the sentence mattered rather than being pedantry. **A re-run designed to
look for a filled inter-finger gap would find no difference and read as a clean pass** — a
green A/B that never asked the question, which is worse than a red one.

The friction-grasp campaign's two published residuals are a **roll** about the pad-to-pad
axis (18.7°) and a **yaw** about the world vertical (10.62°), and **neither is the quantity
predicted above.** A re-run under hull geometry must therefore additionally report, per
trial:

1. **translation of the part along the jaw axis** between first contact and the settled hold;
2. **pitch about the finger-pivot axis**, which is a third axis and not either published one;
3. **contact-patch length along the pad**, against the 37 → 44 mm prediction.

Its existing thresholds still apply to the quantities they were written for. These three have
no pre-registered threshold and must get one *before* the first trial, exactly as that
campaign's own rule requires.

**[Corrected 2026-09-01 — see the newest Correction section above. This section's instruction
was followed exactly: the campaign registered thresholds for all three quantities before its
first trial and reported all three. What it found is that the mechanism they were chosen to
detect does not occur, so the three quantities are the right instruments aimed at a
non-event. That is why clause 2 as written cannot be met, and it is
[ADR-0051](0051-restate-the-hull-grasp-gate.md) that restates it.]**

**This correction promotes nothing.** The status stays `Proposed`, the shipped default stays
`vendor_meshes`, and clause 2 remains unsatisfied.

## Residuals recorded 2026-08-31, and deliberately not fixed here

A geometry audit and a code review of the implementing change found the hulls themselves
correct, reproducible, structurally sound and reaching only collision geometry. What follows
is what they found wrong or unmeasured **around** them. The blocking items are fixed and
recorded in their own sections above; these are the ones recorded rather than built, each with
what would settle it.

**Every *measurement* below is the audit's**, taken on 2026-08-31 from the committed hulls, the
pinned vendor meshes and the generated artifacts. The *reproductions* — the two-message state
below, the patch-ordering conflict, `meshes.build`'s missing caller and the permutation test
surviving its own canonicalisation — were each re-run by the change that wrote this section
rather than carried over, and say so where they appear. **One measurement, one machine, no
thresholds registered in advance and no directory in
[`docs/measurements/`](../measurements/README.md).** They are static geometry, never a running
cell, and none of them is evidence about grasp behaviour.

### The determinism residual is stated against an axis nothing has tested

`cite_tools.meshes` says the facet-merging residual *"did not occur across the two platforms
measured"*. **Those two platforms are macOS/arm64 and the Linux container on the same host —
two operating systems and one CPU architecture.** CI is x86_64 and this branch has never run
there, so the axis on which floating-point results most plausibly differ is the one with no
observation on it at all. The claim is not wrong; it is narrower than it reads, and the module
now says so.

**The module also named only Qhull's facet merging and omitted a residual of its own.** `_fan`
orders a facet's vertices by their bearing about the facet centroid, so two vertices at the
same bearing to within floating-point error would swap and the file would change. That is now
measured rather than argued: across **all 19,471 consecutive-bearing gaps in all 13 hulls the
tightest is 1.77e-8 rad**, about **8x10^7 ULPs**, with **zero exact ties**. So the margin is
large — which is a reason to expect stability, not a proof of it, and it is a property of
*these thirteen meshes* that a vendor bump can change. Both residuals are now in the module's
docstring.

**What would settle it:** one `./scripts/hulls` run on x86_64. It is one CI step and it does
not exist.

### `end_tool` is the one link where the hull is worse, and it is now measured

This record said the `end_tool` effect was unmeasured. It is not, and the numbers matter
because they point the other way from every other link.

| | |
|---|---|
| volume added by the hull | **+7.42 cm^3**, **+6.0 %** |
| peripheral fill depth | median **6.4 mm**, maximum **~18.9 mm** |
| feature closed | a **~75 mm** through-feature |
| triangles saved | **80**, which is **0.09 %** of the total reduction |

**Everywhere else in the set a rendering mesh is traded for a hull. Here a hand-made vendor
collision proxy is** — 260 triangles the vendor authored *as* collision geometry — and it buys
0.09 % of the saving. It is the one link where the exchange is fidelity for almost nothing.

**So `end_tool` is a second candidate for the per-link exception this record already foresees
for the fingers, and it is a stronger one on cost-benefit while being a different case in
kind.** The fingers' case is that the hull changes how a part is held (see the correction of
2026-08-31); `end_tool`'s is that the hull closes a through-feature and saves nothing worth
having. The mechanism ADR-0028 names for the exception — a primitive, or several hulls for one
link — fits both, and `CollisionSpec` cannot express either, which is stated in its docstring
and is unchanged.

**What would settle it:** the exception itself, which is the change that would also have to
decide whether an unhulled member of a set is expressible at all. Selecting `vendor_meshes`
for `end_tool` alone is not available today: the binding substitutes a *root*, wholesale.

### Promoting hulls means the self-collision matrix no longer matches its geometry

The generated SRDF invokes the **vendor's** self-collision matrix, and that matrix was computed
against **vendor** geometry. A convex hull is never smaller than what it replaces, so pairs the
vendor disabled as never-colliding can collide once hulls are selected, and the planner then
refuses configurations it used to accept.

Measured over **484 configurations and the 34 pairs the vendor's matrix does not disable**:

| vendor clearance | configurations that become hull-colliding |
|---|---|
| any gap above 2 mm | **9 of 484 (1.9 %)** |
| above 10 mm | **2 of 484** |
| above 20 mm | **0 of 484** |

**Home is clear on both geometries.** So this is a small, real narrowing of the reachable
configuration space concentrated where the vendor geometry was already close — not a broken
arm, and not nothing.

**The transferable part is not the percentage.** It is that **a self-collision matrix is a
function of the geometry it was computed for**, and selecting a different collision geometry
silently invalidates that function. Nothing in this repository checks the pairing. Promoting
hulls therefore means either regenerating the matrix against hull geometry — which is a
`moveit_setup_assistant` output the project does not generate today — or accepting a matrix
computed for a different robot.

**What would settle it:** a matrix derived from the selected geometry, in the generator, so
that the two cannot disagree; and, until then, a check that fails when a derived set is
selected while the SRDF's matrix names the vendor's.

### An un-bootstrapped checkout is told to run the command that would erase the region

`cite-model hulls` skips a set whose `source_root` does not exist, so `entries` comes back
empty, so `manifest.replace(text, [])` differs from the committed file. The check form
therefore emits **two** messages on the ordinary state of a fresh clone: the correct one —
*"the vendor meshes are not in this checkout … Run ./scripts/bootstrap"* — and then

> `assets/manifest.yaml's derived region does not match the meshes on disk — run
> cite-model hulls --write`

**Nothing is lost, and that is not the same as the message being harmless.** `--write` refuses,
because the `problems` guard precedes the write; reproduced on 2026-08-31 against a temp repo
root carrying `model/`, `assets/` and `external/cite.repos` and no `workspace/src/external`,
where both messages appear, `--write` exits 1, and the manifest is byte-unchanged. What is
wrong is that **the second message points at an action that would destroy the thing it names**,
and it fires on the normal state of a checkout nobody has bootstrapped — which is the first
state a new contributor is in.

**The fix is to skip the region comparison when any set was skipped**, so that a missing vendor
tree produces one message about the vendor tree and no claim about the manifest at all. It is
deliberately not made here: it is a change to the command's control flow, and this change is
already the one that put that command into a gate.
**[Fixed 2026-08-31 — see the correction below.]**

Note for whoever takes it: **the remedy string also names `cite-model hulls --write`**, which
after 2026-08-31 is no longer the entry point CLAUDE.md §7 points anyone at — `./scripts/hulls`
is. Both belong to the same edit. The string was left exactly as it stands so that "R-09
recorded, not fixed" means what it says. **[Fixed 2026-08-31 — see the correction below.]**

#### Correction — 2026-08-31: R-09 is fixed, and it was broader than this section wrote it

**The cause named above is one of two, and the section stated the narrower one as if it were
the whole.** It says the set is skipped *"whose `source_root` does not exist"*, which is the
route that `continue`s before `_hull_set` is called. A set is skipped by a second route as
well: `_hull_set` raising `MeshError`, which happens when a declared mesh is absent from a
vendor package that *is* present, when an STL cannot be parsed, and when **`scipy` is missing
from the interpreter** — `cite_tools.meshes.convex_hull` imports it at call time and raises
that same exception when it is not there.

**That second route was reproduced**, on a stale checkout carrying the vendor tree where
`scipy` was absent: the same wrong second message, from a different cause, on a machine that
*had* been bootstrapped. So the diagnosis in the section — "the ordinary state of a fresh
clone" — understates the reach: the bad message follows from *a declared set produced no
entry*, and the missing vendor tree is only its most common reason.

**What was changed**, in `tools/cite_tools/cli.py`:

- The command records the sets that produced no entry, by name, at **both** skip routes.
- The region comparison is skipped when that list is non-empty — for any reason, not for the
  vendor-tree reason — and the run instead prints a note that the region **went unchecked**,
  naming the skipped sets. The skip keeps its own error and its own remedy; the manifest is
  no longer spoken about at all.
- The note says *"do not run `--write` to make it agree"* in as many words, because the
  message this replaces did the opposite.
- `--write` now refuses on the skip itself as well as on `problems`. It already refused, and
  it refused **by coincidence** — every skip happens to file a problem. What stands between a
  skipped set and a region rewritten with that set deleted from it should not be a coincidence
  between two lists.
- The remedy string on the surviving comparison now names `./scripts/hulls --write`, with the
  two other places that named the old entry point as an instruction:
  `tools/tests/test_hulls_match_the_vendor.py` and the `scipy` pin's comment in
  `requirements/tools.txt`. **The generated manifest's own `tool:` field and `BEGIN` marker
  still read `cite-model hulls`** and are deliberately untouched — they are machine-written
  provenance, and rewriting them means a `--write` run against the vendor tree.

**What it is checked by**, `tools/tests/test_hulls_skipped_set_message.py`: both skip routes,
each asserting the region complaint is absent and the note present; that no remedy naming
`--write` is offered; and that `--write` refuses leaving the manifest byte-identical. Three of
the four fail against the pre-fix command and pass after it. The fourth — that `--write`
refuses — passed before the change as well, and is recorded here as documenting existing
behaviour rather than as evidence of a fix.

**The anti-vacuous half was run, after the vendor tree was imported.** A guard that suppresses
a comparison and a guard that deleted one look identical from the passing side, so the file
also asserts that a corrupted derived region is still caught and still names `./scripts/hulls
--write`. That test is `skipif`-guarded on `workspace/src/external/`, and it **skipped on the
first pass and passed once `./scripts/bootstrap` had imported the vendor source** — with
`./scripts/hulls` itself then reporting `1 set(s), 13 mesh(es) match the vendor` on an
unmodified checkout. So the comparison is shown still firing, and is not merely believed to.

### The schema generalises to a second vendor and the tool does not

Decision 3 requires the binding be usable by a description other than this one, and the
**schema** honours it: `CollisionSpec` and `CollisionMeshSet` name no vendor anywhere —
`source_package` and `source_root` are the only provenance they carry, and both are ordinary
model data.

**The tool hard-codes `xarm_ros2` in three places**, all in `tools/cite_tools/cli.py`:

| line | what it does |
|---|---|
| `_vendor_share` | resolves `workspace/src/external/`**`xarm_ros2`**`/<source_package>` |
| `_hull_set` | writes `"repo": "external/xarm_ros2"` into the manifest entry |
| `_hull_set` | calls `pinned_version(repo_root, "xarm_ros2")` |

So a second vendor's set is looked for under `xarm_ros2/` and fails with *"the vendor meshes
are not in this checkout"* — a message that is true of the path it names and false about the
world, which is the worst kind. The two adjacent lines are the sharper half: `pinned_version`'s
own docstring refuses to restate the pin, *"the thing `external/cite.repos` exists to be the
only one of (ADR-0008, P1)"*, and is then handed which repository it is by a literal. The check
added the same day already reads `entry["source"]["repo"]` out of the manifest rather than a
constant, so **the test generalises and the writer does not.**

**Of the two available shapes, `source_repo` on `CollisionMeshSet` is the one to take.**
Resolving the repository from `external/cite.repos` by matching `source_package` sounds tidier
and is worse: `cite.repos` lists repositories and not the packages inside them, so the match
would have to scan the imported tree — which is absent in exactly the failure case above, and
which would make the checkout's layout a second source of truth about provenance. A
`source_repo` field sits beside `source_package` and `source_root`, is model data like every
other vendor fact in this block (`root_arg`, `root_uri_scheme`), needs no tree to resolve, and
is checkable against `cite.repos` by the test that already exists.

### Four things about the pipeline's own tests, recorded and not fixed

None of these is a defect in a hull. Each is a gate that proves less than it appears to.

- **The tested hull-writing loop is dead; the live one is untested.** `meshes.build` has unit
  tests and **no production caller** — `grep` finds it in `tools/tests/test_meshes.py` and
  nowhere else. What `./scripts/hulls --write` actually runs is `cli._hull_set`, which nothing
  automated exercises. Two write paths, and the tests are on the one that is not used.
- **`test_a_permuted_input_gives_the_same_bytes` passes with the canonicalisation removed.**
  Verified: replacing `np.unique(triangles.reshape(-1, 3), axis=0)` in `convex_hull` with the
  raw reshape leaves that test green, and the **only** test that fails is
  `test_hulls_match_the_vendor.py::test_re_deriving_reproduces_the_committed_bytes` — which is
  `@needs_vendor` and skips on a host without the import, the job most contributors run. The
  new `./scripts/hulls` step in `lint` catches it too and is gated on the same condition, so
  it adds a caller rather than a platform.
- **Nothing checks that the declared mesh list stays exhaustive.** The list in L0 is exhaustive
  today and the binding substitutes a root wholesale, so a vendor bump that adds a
  collision-bearing link — or an L0 change that pushes `model_num` to 1305 or above, which
  moves the vendor's own `collision_dir` — leaves references resolving to nothing. Gazebo warns
  and simulates a body with no collision geometry; nothing fails.
- **`cite_description`'s admission test is prose where its cited precedent is mechanical.** It
  says what belongs in the package in a `package.xml` comment. The precedent it names enforces
  its equivalent in code.

**What would settle each:** a test that calls the live write path; a host-runnable permutation
guard; a check that the declared list equals the collision references in the expanded
description, which is the only statement of exhaustiveness that cannot go stale; and an
admission check that runs.

## Context

### The failure CLAUDE.md names by name is in the tree

CLAUDE.md §10 lists it as a standing review checkpoint: *"wrong inertia tensors and dense
visual meshes reused as collision geometry make a simulation run confidently and wrongly."*
That is what the three arms are running today.

Traced through the vendor description on 2026-08-25. `model/assets/types/robots/xarm5.yaml`
sets `mesh_suffix: stl` and `model1300: false`, so `model_num` resolves to `-1`
(`xarm_description/urdf/common/common.link.xacro`), and the selector at the top of
`urdf/xarm5/xarm5.urdf.xacro` takes its `unless` branch:

```xml
<xacro:unless value="${mesh_suffix == 'dae' or (model_num >= 1305 and model_num != 1380)}">
  <xacro:property name="visual_dir"    value="xarm5/visual"/>
  <xacro:property name="collision_dir" value="xarm5/visual"/>
```

`collision_dir` **is** `visual_dir`. The gripper does the same thing unconditionally:
`xarm_gripper.urdf.xacro` passes the identical `mesh_filename` to `common_link_visual` and
`common_link_collision` on all seven of its links.

Counted from the checked-out vendor meshes (binary STL triangle count read from the header,
`workspace/src/external/xarm_ros2/xarm_description/meshes/`):

| | triangles |
|---|---|
| `xarm5/visual/link2.stl` — the worst single link | **26,118** |
| `gripper/xarm/base_link.stl` | 24,227 |
| all **12** links per arm whose collision mesh is their visual mesh | **98,292** |
| across three arms | **294,876** |
| `end_tool/collision/end_tool.stl` — the one link that has a real collision mesh, `link5` | 260 |

Three links per arm carry no geometry at all — `link_eef`, `link_tcp`, and the
`arm_N_mount` link the generator emits — leaving thirteen with geometry. Of those,
**twelve** collide against a rendering mesh and one, `link5`, against a 260-triangle proxy.

### The measurement this record was written from, which is not the measurement that gives it urgency

**[Corrected 2026-08-29 — heading included; see the Correction section above and its
settlement note.]** This record was written from a real-time factor of **0.14** on the
development host, with `/cite/cell_a/arm_1/joint_states` at roughly **21 Hz** against the
**150 Hz** the model configures (`xarm5.yaml: control.update_rate_hz: 150`, generated into
`cite_generated/control/cell_a_arm_*_controllers.yaml` as `update_rate: 150`). That pair is
**a fact about that host confined to about one CPU core** and **not about collision geometry**,
so it is not what gives this record its urgency and this heading used to claim it was. What
does is the second-world campaign's measured cost of collision geometry, cited in the
amendment above. The recorded figure is also in the tree at `tests/scenarios/bringup.py`,
where every wall-clock ceiling in the bring-up scenario is justified against it — those
ceilings are wall clock, so that dependence is real and is unaffected by the correction.

That is the load context in which `move_group` overran launch's **5 s** SIGINT default and
was killed mid-teardown, recording `-15` — the truncation rather than whatever the process
was actually doing. The deadline has since been raised to 45 s SIGTERM / 60 s SIGKILL
(`cite_bringup/launch/simulation.launch.py`, `TEARDOWN_SIGTERM_S`/`TEARDOWN_SIGKILL_S`), so
the symptom is gone. **The load that produced it is not.**

Under [ADR-0027](0027-pilz-planning-pipeline.md) this stops being only a performance
concern. A planner that fails on collision rather than routing around it makes the fidelity
of every collision surface load-bearing, and a 26,118-triangle hull of a rendering mesh is
not a fidelity improvement over a convex hull — it is the same shape with concavities the
solver must resolve, at two orders of magnitude more contact pairs.

### The validator that cannot fire

`cite_tools.validate.physical._collision_is_not_a_visual_mesh` is documented in its own
docstring as *"the single most consequential rule in L1, checked mechanically."* Its first
two lines are:

```python
body = asset_type.description.body
if body is None:
    return []
```

`description.body` is populated only for the bodies **we** author — conveyors, tables,
pedestals. Every vendor-described type sets `provider: xacro_macro` and leaves `body` unset,
so the check returns an empty list for it. **The rule can never fire on any vendor
description**, which is to say it cannot fire on the only links where the failure it names
actually occurs. It has been passing for as long as it has existed, and it is passing now.

### Why this is not a one-line flag change

The vendor does ship a decimated collision set, but only for one variant: under
`meshes/`, `xarm5_1305/` contains both `visual/` and `collision/`, while `xarm5/` contains
`visual/` alone. Reaching the decimated set means selecting `xarm5_1305` — a *different
robot variant*, with different kinematics parameters and a different inertial file, chosen
by `model_num >= 1305`. Changing which arm we model in order to obtain better collision
geometry would be a silent change to what the twin claims to represent, which is exactly
what P8 exists to prevent.

## Options considered

### Option A — Leave it, and buy real-time factor elsewhere
Raise ceilings, run on faster hardware, reduce the physics rate.

Rejected. It treats a fidelity defect as a scheduling problem. Contact behaviour computed
against a rendering mesh is not merely slow, it is wrong in a way nobody can explain at the
point it surfaces — which is CLAUDE.md §10's word for it, "confidently and wrongly" — and
under ADR-0027 wrong collision surfaces become refused motions rather than slow ones.

### Option B — Switch the model to the `xarm5_1305` variant
Set `model1300`/`robot_sn` so the vendor's `collision_dir` resolves to `xarm5_1305/collision`.

Rejected. It changes which physical arm the model describes in order to obtain a mesh. The
1305 variant carries its own kinematics and inertial parameters, so the twin would silently
represent hardware CITE does not have, and every measurement taken from it would be against
the wrong arm. The layout is already `PROVISIONAL` (CLAUDE.md §2); adding a second
unacknowledged divergence from reality is not acceptable.

### Option C — Replace collision geometry with primitives
Boxes and cylinders per link, authored by hand.

Rejected as the general answer, though it remains right for individual links. A primitive
per link is a hand-written approximation of vendor geometry, which means a value that exists
in two places (P1) and drifts on the first vendor upgrade. It is also strictly less accurate
than a hull for the links that matter, without being meaningfully cheaper.

### Option D — Generate convex hulls as project assets, bound through the L0 robot type
Compute a convex hull per link from the vendor visual mesh, store the result under
`assets/meshes/` with provenance in `assets/manifest.yaml` (ADR-0012), and bind it to the
type in `model/assets/types/robots/xarm5.yaml`. Chosen.

The hull is **derived** from the vendor mesh rather than authored, so it is reproducible and
regenerable on a vendor upgrade — P1 holds because the source of the shape is still the
vendor file. The binding lives in L0, so which mesh a link collides with is data, and a new
robot type is a model change and not a code change (P5, P9).

## Decision

**Collision geometry for vendor-described links is a convex hull, generated as a project
asset from the vendor's visual mesh and bound to the robot type in the L0 model.**

Four parts, and all four are required for the decision to mean anything:

1. **Hull generation is a `tools/` pipeline stage**, host-agnostic like the rest of L0
   (ADR-0013), reproducible, and covered by unit tests. Its output is deterministic for a
   given input mesh, so a regenerated hull is byte-identical or the change is real.
2. **Hulls are stored as project assets** under `assets/meshes/`, with provenance and
   checksums in `assets/manifest.yaml`, per ADR-0012 and `assets/README.md`. They are
   derived, not vendored third-party source, so ADR-0008 is not engaged.
3. **The binding is L0 data.** The robot type gains a field expressing "this link's
   collision geometry is this mesh". The L0 schema has no such field today —
   `DescriptionSpec` offers `fixed_args`, `bound_args` and `body`, none of which express a
   per-link collision override for a `xacro_macro` provider — so adding it is part of this
   work, and it must be added in a form that a *different* vendor description could also use.
4. **`_collision_is_not_a_visual_mesh` is extended to the `xacro_macro` provider**, so that
   the rule fires on the links it was written for. A validator that cannot fail on the case
   it names is worse than no validator, because its silence has been read as evidence.

**No status improves on the strength of this record.** L1 stays as it is marked until a
hull exists and a measurement shows what it bought. Under P8 the claim that this improves
real-time factor is earned by re-measuring RTF and `joint_states` frequency against the
0.14 / ~21 Hz baseline, not by asserting that hulls are faster.

## Consequences

### What this gets us
- Contact geometry that a physics solver can actually evaluate, in place of 98,292 triangles
  per arm of rendering detail — the failure CLAUDE.md §10 names, removed at its cause.
- Headroom on the measurement that currently governs every wall-clock ceiling in the
  scenario suite. **[Corrected 2026-08-29: the ceilings were chosen against RTF 0.14, but not
  *because of* collision geometry — that figure is the development host confined to about one
  CPU core. See the Correction section's settlement note.]** They remain the reason a slow
  machine and a hung machine look alike today, and hulls buy real headroom against that on the
  second-world campaign's figures.
- A collision surface fit for a planner that refuses rather than searches (ADR-0027).
- A validator that fires on vendor descriptions, which is the majority of the links in the
  cell and all of the ones that move.
- A pipeline the facility scan will need anyway in Phase 3, built once, on geometry small
  enough to debug.

### What this costs us
- **A new asset class to produce, store and keep in step with the vendor.** A vendor upgrade
  that changes a mesh now requires regenerating hulls, and a stale hull is a collision shape
  that does not match the arm — a failure that looks like a planner bug.
- **A convex hull is not the true shape.** Concavities within a link are filled, and any
  pocket in a single link that a real part could enter becomes solid. For the gripper in
  particular this is likely to be wrong in a way that matters, and per-link exceptions
  (primitives, or multiple hulls for one link) will be needed. That is a genuine loss of
  fidelity traded for a genuine gain in solvability, and it must be stated wherever a
  contact measurement is published (P8).
  **[Corrected 2026-08-31: this bullet said "the space between the gripper fingers" becomes
  solid. It does not — each link is hulled separately, so that space lies between two
  collision bodies. What the hull does change at the gripper is measured in the section
  "Correction — 2026-08-31: the gripper risk is real and it is not a filled inter-finger
  gap", which also states what the re-run has to measure instead.]**
- **An L0 schema change**, which is a versioned contract with generated artifacts behind it
  (ADR-0021). Every generated file that references a collision mesh changes with it.
- **Build and pipeline time**, plus a new dependency for hull computation that
  `requirements/README.md` has to place in exactly one of the four layers.

### What we will have to revisit
- **When the gripper's hulled relief shoulders produce a wrong grasp.** The fingers are the
  links whose exact geometry decides how a part is held, and they are the links a convex hull
  approximates worst. If it bites, the answer is per-link geometry for the fingers, not
  abandoning hulls elsewhere. **[Corrected 2026-08-31: this bullet said "filled concavity",
  meaning the gap between the fingers, and that mechanism does not occur. The one that does
  is the pair of inclined wedges the hull adds at each pad's own relief steps — see the
  correction section named above. `end_tool` is now a second candidate for this same
  exception, for a different reason; see the note under the implementation note.]**
  **[Corrected again 2026-09-01 — see the newest Correction section above. The wedges exist and
  do not touch a 50 mm part, so neither stated mechanism has been observed to produce a wrong
  grasp. The condition in this bullet stands unchanged as a condition; what is withdrawn is the
  claim that the wedges are the mechanism that would trigger it. A **narrower** work-piece is
  the untested case, and [ADR-0051](0051-restate-the-hull-grasp-gate.md) decision 3 makes
  declaring one a precondition rather than a surprise.]**
- **When the RTF re-measurement lands.** If 0.14 does not move materially, the bottleneck is
  elsewhere — three controller managers at 150 Hz, or the physics step itself — and this
  record must not be cited as having fixed it. **[2026-08-29: two campaigns have landed and
  this clause must not be evaluated against 0.14 at all. Read it against the second-world
  campaign's measured hull effect, reported against its pre-registered band in the amendment
  above; the 0.14 figure is a starved-CPU condition and collision geometry cannot move it.]**
- **When the Phase 3 facility scan arrives.** Scanned geometry is far heavier than any of
  this, and the decimation and level-of-detail policy in `assets/README.md` will need to say
  how a scanned collision representation is produced. This pipeline should be the one that
  does it, or the project has two.
- **If a future vendor description ships usable collision meshes for the variant we model.**
  Then the binding added here points at the vendor's file instead of ours, which is the same
  mechanism and no schema change.
