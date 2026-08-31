# ADR-0028: Generate convex-hull collision meshes as project assets, bound through L0

- **Status:** Proposed — **implemented and not promoted, which is the amended gate working
  exactly as it was written to.** All four parts of the Decision are in the tree as of
  2026-08-31; the sentence above them, "decided in principle, nothing implemented", is
  superseded and is corrected in place below. **The shipped default is still the vendor's
  meshes**, and it stays there until clause 2 of the promotion gate is satisfied — see the
  section "Implementation note — 2026-08-31" for what landed and what promotion still needs.
  **Read "Correction — 2026-08-31: the gripper risk is real and it is not a filled
  inter-finger gap" before designing that measurement**: this record's stated hypothesis for
  it was wrong, and a re-run aimed at the sentence it used to carry would pass without asking
  the question.
  **[Superseded 2026-08-31, kept for the record:]** *"decided in principle, nothing
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
  [L1](../architecture/L1-description-and-assets.md), [`../../assets/README.md`](../../assets/README.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  CLAUDE.md §10, charter §4 (P1, P5, P8)

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

**Hulls move it materially and do not reach 1.0.** The gain is about **1.10x** per side, which
is below the 1.25-2.0 band the second-world campaign's `G` fell in for a solo cell — a
different quantity on a different host, and not a contradiction, but not a confirmation
either. **The finding that matters is the negative one: [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s
requirement that both sides sustain 1.0 concurrently is still NOT met**, on this host, with
hulls. That record's 2026-08-30 correction predicted 1.162/1.173 from the campaign's figures;
this host does not reach it. No ceiling, tolerance or `real_time_factor` was touched.

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
  1.2–1.9 mm deeper.
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

**This correction promotes nothing.** The status stays `Proposed`, the shipped default stays
`vendor_meshes`, and clause 2 remains unsatisfied.

## Residuals recorded 2026-08-31, and deliberately not fixed here

A geometry audit and a code review of the implementing change found the hulls themselves
correct, reproducible, structurally sound and reaching only collision geometry. What follows
is what they found wrong or unmeasured **around** them. The blocking items are fixed and
recorded in their own sections above; these are the ones recorded rather than built, each with
what would settle it.

**Every measurement below is the audit's**, taken on 2026-08-31 from the committed hulls, the
pinned vendor meshes and the generated artifacts. **One measurement, one machine, no
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
