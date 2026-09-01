# ADR-0051: Restate ADR-0028's grasp gate, and bind it to the work-piece width it was measured at

- **Status:** Accepted — **the project owner ratified the restated clause in decision 1 on
  2026-09-01**, which is the promotion condition this record wrote for itself. The clause
  restates ADR-0028's gate; it does not relax it, and ratification changes no threshold,
  ceiling or tolerance anywhere.
  **Ratifying the clause and satisfying it are two acts, and both have now happened, in that
  order and in separate changes** — decision 2 required the promoting change to be separate
  from this record, and it is: [ADR-0028](0028-convex-hull-collision-meshes.md) is `Accepted`
  as of 2026-09-01, `description.collision.select` on
  `model/assets/types/robots/xarm5.yaml` is `convex_hull`, and decision 3's range is enforced
  by `cite_tools.validate.physical._derived_collision_is_within_its_measured_range` rather than
  stated in prose. See ADR-0028's section "Amendment — 2026-09-01: clause 2 is adopted as
  ADR-0051 restates it, and this record is promoted" for the evidence clause by clause.
  **Decision 4's two residuals are open and this status does not close them**, nor does it make
  the campaign under *Evidence* anything other than what it is: **INCONCLUSIVE on its own
  question, by a rule it wrote before it had any data.**
  **[Superseded 2026-09-01, kept for the record:]** *"Proposed — nothing in the tree changes
  with this record, and it promotes nothing. ADR-0028 stays `Proposed`,
  `description.collision.select` on `model/assets/types/robots/xarm5.yaml` stays
  `vendor_meshes`, and no generated artifact, ceiling, tolerance or threshold moves. This
  record makes a promotion possible; it does not make one. That is a separate change, and
  what it has to do is decision 2 below. This record is promoted to `Accepted` when the project
  owner ratifies the restated clause in decision 1."* Until that ratification, ADR-0028's gate
  was the one ADR-0028 carried, corrected on
  2026-09-01 to say that its clause 2 as written cannot be met — see that record's section
  "Correction — 2026-09-01: clause 2 asks for a measurement of a mechanism that does not
  occur", which points here.
- **Date:** 2026-09-01
- **Deciders:** **Project owner**, on the shape: restate the gate rather than relax it, and
  keep promotion in a separate change. **The clause text below is the docs-writer agent's**,
  drafted from the campaign named under *Evidence*, and was owed the owner's ratification —
  the same split [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) records for the
  restatement it made. **That ratification was given on 2026-09-01**, which is what moves this
  record to `Accepted`; the wording of decision 1 is unchanged by it.
- **Related:** [ADR-0028](0028-convex-hull-collision-meshes.md) (whose gate clause 2 this
  record restates; clause 1 is untouched and ADR-0028 is **not** superseded),
  [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) (the precedent for this shape —
  a gate written around a false premise, restated rather than relaxed),
  [ADR-0029](0029-simulated-grasping-by-friction.md) (friction alone holds a grasp, so the
  contact surface *is* the mechanism),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md) (a grasp is evidenced by a stall),
  [ADR-0030](0030-facility-model-describes-the-workpiece.md) (the work-piece is L0 data, which
  is what makes decision 3 checkable),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md), [ADR-0012](0012-large-asset-storage.md),
  [L1](../architecture/L1-description-and-assets.md),
  charter §4 (P5, P6, P7, P8), CLAUDE.md §10.
- **Evidence:**
  [`docs/measurements/2026-09-01-hull-grasp/`](../measurements/2026-09-01-hull-grasp/ANALYSIS.md)
  — 47 trials, thresholds registered before the first trial, machine named, **verdict
  INCONCLUSIVE by its own pre-registered rule S**; and
  [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  for the separate capacity question. **Their figures are cited and not copied** (P1); read
  them rather than taking a number from here.

## Context

### The gate as it stands, and the premise it was written around

ADR-0028's amended promotion gate has two clauses. Clause 1 — the first hull, its L0 binding,
the asset provenance and the extended validator — was satisfied on 2026-08-31 and is not in
question here. Clause 2 requires *"the friction-grasp campaign … re-run against hull collision
geometry and its result published"*, and its 2026-08-31 correction sharpened what that re-run
had to report: a translation along the jaw axis, a pitch about the finger-pivot axis, and a
contact-patch length against a predicted growth from 37 mm to 44 mm.

Those three quantities are not arbitrary. They are the observable consequences of a **stated
mechanism**: that the convex hull ramps across each pad's own 2.0 mm relief step, adding two
inclined wedges which contact the part's flat face at a slope and push it along the approach
axis. ADR-0028 wrote that mechanism down precisely so that a re-run could be designed against
it, having just discovered that the mechanism it had believed in before — a hull filling the
space between the fingers — does not exist.

### The campaign ran, and the mechanism does not occur either

The re-run is published. It is a 47-trial A/B on the shipped three-arm cell, `vendor_meshes`
against `convex_hull`, in four blocks, with every threshold, resolution rule and validity rule
committed before the first trial and its machine named.

**Its verdict is INCONCLUSIVE, by its own rule S**, which was registered in advance and says
that a campaign which cannot see the mechanism the static geometry claims is there has **not
tested the prediction**, so its silence about the grasp may not be read as "no change". Rule S
fired, and what it obliged the write-up to report next is the finding:

- The hull's wedges are recessed **0.41 mm of aperture behind the pad plane, on the same rigid
  link**. That number is arithmetic on **ADR-0028's own audit** — its pad aperture of 44.99 mm
  against its worst-case shoulder aperture of 45.40 mm — and needs none of the campaign's
  apparatus.
- The campaign measures the same clearance independently, from the running cell at the settled
  hold, at **0.42 mm**. The two agree to 0.01 mm.
- Because both surfaces belong to one rigid link, that recess does not vary with aperture. **A
  flat face resting on the pad is clear of the wedges whatever the jaws are commanded to do.**

So the audit ADR-0028 published is confirmed and the inference it drew from it is not. Its
sentence *"both shoulders lie inside the part's envelope"* compares the shoulder against the
part's **width** at the **commanded** 45 mm aperture — a configuration a gripper holding a
50 mm rigid part never occupies, because the part stalls the jaws at a measured **~50.0 mm**.
The comparison that decides contact is the shoulder against the **pad plane**.

**A gate written around a premise that turned out false cannot be met by measuring harder.**
That is the same situation ADR-0049 found in ADR-0043's half 2 — a requirement no machine could
pass, for a reason belonging to the requirement rather than to any machine — and it took the
same route this record takes: restate, do not relax.

### What the evidence does support, stated at its own strength

- **The outcomes are indistinguishable, and the hull is never the worse arm.** Pick, hold and
  place complete in every trial of both arms; nothing was flung; slip above 5 mm appears in
  five vendor trials and in none on hulls; the campaign's only outright `trial_success` failure
  is a **vendor** trial.
- **None of that clears the effect size registered in advance.** The campaign says so of
  itself, in terms, and declines to promote a sub-threshold difference because its direction is
  convenient. **The honest statement is "no distinguishable difference at this n", never "hulls
  grasp better".** Nothing in this record may be cited for the second.
- **One metric was DETECTED and it is a control**, not the prediction: the jaws stall
  5.6 mrad earlier on hulls. It survives the block rule. It is unexplained. See decision 4.
- **The instrument was not blind.** Its resolution was established from two shakedown trials
  *before* any threshold was set — the pad reads 37.50 mm long to 0.02 mm, a flat pad's normal
  reads flat to about 1e-3 against a predicted wedge slope of ~0.22. This is a null with a
  known noise floor.

### The capacity case is settled separately, and it is why this matters now

On the same machine, measured as capacity with the world's throttle lifted, a **pair** of cells
sits at **1.194** on hulls and **0.898** on vendor meshes against the floor of 1.0 that
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) sets and ADR-0049 restates. **Hulls are
therefore not an optimisation on this machine; they are the difference between meeting that
floor and not.** That campaign measured cost and never correctness — it says so itself — and
this record does not use it as grasp evidence. What it establishes is that leaving ADR-0028
blocked on an unmeetable clause has a price.

### The part of the evidence that is narrow, and is the reason this record exists

The clearance argument above is established **over an interval, not in general**:

> A 50 mm rigid part stalls the jaws at a measured ~50.0 mm, and the wedges begin 0.41 mm of
> aperture behind the pad plane. So the part never reaches them.

That is a statement about *this* part width. The campaign registers the limit itself, in as many
words: a **narrower** part would let the pads close further and **could** bring the wedges into
contact, and it tested none. Two things move together at a narrower width and the campaign
separated neither: the drive closes further, and the linkage L0 declares moves the pad plane
along the tool axis as it does — 29.86 mm proximal of `link_tcp` fully open against 18.58 mm at
the 45 mm default width (`model/assets/types/end_effectors/xarm_parallel_gripper.yaml`). Whether
the shoulders then touch is **unverified**, and this record does not reconstruct an answer the
campaign declined to give.

**A validity range that a future reader has to reconstruct is a range nobody will apply.** The
project has been here before: ADR-0028's own filled-inter-finger-gap sentence propagated into
three other files and was believed for six days.

## Options considered

### Option A — leave clause 2 exactly as written
Rejected. It asks for a measurement of a mechanism the geometry says cannot occur, so it can
never be satisfied by evidence, and ADR-0028 stays blocked on a non-event while a measured
capacity shortfall goes unpaid. Worse, an unmeetable clause invites the two failures this
project keeps paying for: reading an INCONCLUSIVE campaign as a pass because nothing bad
happened, or re-running until a rule is loosened enough to produce one.

### Option B — declare clause 2 satisfied by the campaign, leaving the words alone
Rejected. The campaign's own pre-registered rule refuses to answer the question clause 2 asks,
and a gate declared satisfied by a campaign that says it did not test the prediction is exactly
the *"green A/B that never asked the question"* ADR-0028 warned about when it wrote the clause.
It also carries no validity range, so the next work-piece would silently inherit an evidence
claim it is outside.

### Option C — relax clause 2 to "no measured harm under hulls"
Rejected. It converts a question about a mechanism into acceptance of a null, and **a null is
not a pass** — the campaign's rules R and S exist for precisely that, and both were written
before any hull trial ran. It would also let a metric the campaign's own resolution rule
refused count as reassurance.

### Option D — widen the campaign now: re-run at a narrower part before promoting
Rejected **as the gate**, kept as a precondition. It is a good measurement, and it is not what
promotion needs: this facility declares one work-piece, a 50 mm cube, and blocking promotion on
evidence at a width the line does not handle prices a hypothetical ahead of a measured capacity
shortfall. The narrow-part question belongs to the change that declares a narrow part —
decision 3.

### Option E — restate clause 2 as evidence clauses plus a binding validity range
Chosen.

## Decision

**ADR-0028's promotion gate clause 2 is restated, not relaxed. Clause 1 is untouched, ADR-0028
is not superseded, and nothing is promoted, bought, tuned or widened by this record.** The
question clause 2 was written to force — *does hull collision geometry change how this cell
holds a part?* — is not withdrawn. What changes is that the clause now asks for evidence that
can exist, and carries the range over which that evidence holds.

### 1. Clause 2, restated. This is the wording that replaces it

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

**Against that wording, on the evidence named under *Evidence*: 2a is satisfied; 2b is
satisfied at n = 24 vendor and 23 hull, on one machine, at one timestep, with one part and one
arm; 2c is satisfied — 0.41 mm from ADR-0028's own audit, 0.42 mm from the campaign's runtime
measurement, agreeing to 0.01 mm — over the range in decision 3; 2d is what the promoting change
must carry.** This record does not assert the conclusion of that assessment as a promotion:
decision 2.

### 2. Promotion is a separate change, and this record is not it

ADR-0028's status does not move here, and the shipped `select: vendor_meshes` does not move
here. The change that promotes must, at minimum: adopt the restated clause into ADR-0028 as an
amendment; move the status with the evidence named clause by clause; flip `select`; make
`_vendor_collision_is_declared`'s WARNING on a vendor-mesh selection an error unconditionally
rather than only under `--strict`, which ADR-0028's implementation note already requires of the
change that moves the default; and carry the range of decision 3. **It must also state what promotion
does not establish** — the self-collision matrix is still the vendor's, computed against vendor
geometry, and `end_tool` is still the one link where the hull trades fidelity for 0.09 % of the
saving. Both are ADR-0028's residuals and neither is closed by anything here.

### 3. The range is stated in the geometry, and declaring a narrower part reopens the clause

**The range.** The clearance argument holds for a rigid work-piece with a flat grasped face
whose width stalls the jaws at a pad-face separation no smaller than the ~50.0 mm the campaign
measured — this facility's 50 mm cube, `body.size_m` `[0.050, 0.050, 0.050]` in
`model/assets/types/workpieces/workpiece.yaml`. Within it, no further trial is needed for the
geometry: the wedge-to-pad recess is a property of one rigid link and does not vary with
aperture, which is why the argument does not depend on the commanded width.

**The threshold.** `narrowest_workpiece_m` below **0.050 m** — the narrowest horizontal extent
across the declared work-piece models, which `cite_tools.validate.physical` already computes for
`default-grasp-width-never-closes` — is outside the range.

**What must be measured before a narrower part ships against a derived collision set**, in this
order:

1. **The static audit, re-run at that part's achieved stall aperture and pad-plane
   registration**, reporting the shoulder-to-pad-plane clearance as a function of height along
   the pad. This is the same re-run residual (a) below needs, and it is cheap.
2. **If that clearance does not hold**, the A/B of 2a re-run at that width, with the
   contact-patch and contact-normal instruments pre-registered as before.

**How it binds.** This is a precondition on the L0 declaration, not advice to a reader. The
mechanical form of it — and the implementing change's call, not this record's — is one rule in
`cite_tools.validate.physical` beside `_default_grasp_width_can_close`, reading
`_narrowest_workpiece_width_m` and `description.collision.select`, that fails when a derived set
is bound and the narrowest declared work-piece is below the range this record states.
**If that rule is not written, the precondition is prose**, and prose preconditions in this
repository have a measured survival record: ADR-0028's own false sentence about the inter-finger
gap reached three other files before anyone measured it.

### 4. Two residuals stay open, and promotion does not close either

- **The 5.6 mrad earlier stall.** The one metric the campaign DETECTED at its registered effect
  size, surviving the block rule, and **unexplained**. Two related figures move with it in sign
  and are not reconciled in magnitude. It is a **control**, which is what makes it awkward: the
  campaign was not looking there. **What would settle it:** the campaign's own suggestion — the
  static audit re-run at the **achieved** ~50.0 mm pad separation rather than the commanded
  44.99 mm — and, for the competing explanation that some other hulled link touches the part,
  one block with the contact filter widened to every collision pair involving the work-piece.
- **A check in the campaign's harness that could not fail.** Its pre-flight grep names
  `cite_generated/descriptions/`; the directory is `cite_generated/description/`. It therefore
  reported nothing in all four blocks. The campaign recorded it and **correctly did not fix it**
  — a published harness is frozen, and a repaired one is a claim about code that never ran. Its
  own words are worth carrying: **a check that cannot fail is indistinguishable from one that
  passes.** What the geometry claim actually rests on is the campaign's runtime validity rule,
  which read the description the running cell published and fired correctly in every block.

### 5. What every figure in clause 2 is conditioned on, carried with the clause

One machine, one arm, one part, one grasp command, **one physics timestep**, in simulation. The
friction campaign ADR-0029 rests on found grasp behaviour strongly timestep-sensitive across a
4x change in `max_step_size` — and note ADR-0029's correction of 2026-08-26, that its factor of
24.5 is the **probability of entering the high-twist mode** moving and not a magnitude scaling.
`max_step_size` is a generator constant. **Any change to it reopens 2b**, and Phase 3's physics
retune is named in ADR-0028 as a thing that will want to change it.

**Nothing in this record is a fidelity claim** (P8), and the campaign it rests on is cited as
what it is: **INCONCLUSIVE on its own question, by a rule it wrote before it had any data.**

## Consequences

### What this gets us

- **A gate that evidence can satisfy.** Clause 2 as written could not be met by any campaign,
  because it asked for the consequences of a mechanism that does not occur. That is now visible
  in the record rather than latent in a re-run somebody would eventually loosen.
- **The absence of the mechanism is now a claim with a range**, rather than a paragraph in a
  campaign's §7 that a future reader has to find. The range is the load-bearing half: the
  finding is about a 50 mm part, and it never said anything about a narrower one.
- **The narrow-part question is attached to the act that raises it** — declaring a narrower
  work-piece — instead of to a reader's diligence.
- **The two residuals survive promotion.** A gate satisfied is normally where open questions go
  to die; these are named in the clause's own record with what would settle them.

### What this costs us

- **A record between the decision and its evidence.** ADR-0028's gate is now stated in two
  places: its own text, corrected to say clause 2 cannot be met as written, and here. That is
  a duplication risk (P1), and it is why ADR-0028 takes a correction pointing here rather than a
  rewritten clause, and why the wording above is a single quotable block.
- **A precondition that is prose until someone writes the rule.** Decision 3 names the rule and
  does not write it, so between this record and that change the range binds only whoever reads
  it.
- **Promotion becomes possible while two questions are open.** The earlier stall is unexplained
  and the narrow-part case is untested. Both are recorded as open rather than resolved, and
  anyone who dislikes promoting on that basis is disagreeing with decision 1's 2b, which is
  where the argument belongs.
- **The evidence is one machine deep.** 2b is satisfied by a single campaign on one host at one
  timestep. Nothing here is a claim about CI, about x86_64, or about any other machine, and a
  promoting change inherits that limit rather than escaping it.

### What we will have to revisit

- **When the static audit is re-run at the achieved aperture.** It is the settlement path for
  the earlier stall, for the shortened contact patch the campaign observed and its own rules
  refused to call, and for the first step of any narrow-part case. One re-run answers three
  questions, which is why it is first.
- **When a work-piece narrower than 0.050 m is declared.** Decision 3 fires. If it fires often,
  the answer is likely the per-link exception ADR-0028 already foresees for the fingers — a
  primitive rather than a mesh — and `CollisionSpec` cannot express it.
- **When `max_step_size` changes**, for Phase 3's physics retune or any other reason. Decision 5.
- **If a hulled link other than the two pads is found to contact the work-piece.** The campaign
  filtered its contact record to finger contacts at write time, so its raw data cannot answer
  this, and it is one of the two candidate explanations for the earlier stall.
- **When the self-collision matrix is derived from the selected geometry.** Until then a
  promoted hull runs against a matrix computed for a different collision set — ADR-0028's
  residual, unchanged by anything here, and one the promoting change has to state rather than
  inherit quietly.
