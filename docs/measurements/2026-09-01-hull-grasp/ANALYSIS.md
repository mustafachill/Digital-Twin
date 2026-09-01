# Analysis — does convex-hull collision geometry change the grasp?

Read [`criteria.md`](criteria.md) first. It was committed at `b690c41`, **before the first
campaign trial ran**, and every threshold, validity rule and decision rule used below is
transcribed from it. Its sha256 is
`2b30bfc25ac5869a0ce59ca0ca32f9e49f71d724d480596c6419390ee02646d0`.

- **Date:** 2026-09-01
- **Branch / commit:** `measure/hull-grasp`, off `main` at `d79a856`
- **Trials:** **47** — 24 `vendor_meshes`, 23 `convex_hull`, in four blocks of twelve,
  `VENDOR HULL VENDOR HULL`
- **The record this answers:** [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  promotion gate clause 2

## Verdict

> **INCONCLUSIVE on Q0, by the campaign's own rule S**, which fired.
>
> Neither M3 (contact-patch length) nor M4 (contact normal) was DETECTED, and rule S —
> written before the first trial — says that a campaign which cannot see the mechanism the
> static geometry says is there has **not tested the prediction**, so its silence about the
> grasp may not be read as "no change".
>
> **What rule S obliged the campaign to report next is the substantive finding**, and it is
> the answer to why nothing was detected: **the hull's wedges never touch the part.** They
> are recessed **0.41 mm behind the pad plane on the same rigid link**, measured
> independently here at **0.42 mm**, so a flat face resting on the pad is clear of them at
> **any** aperture. ADR-0028's correction of 2026-08-31 predicted its effect from a static
> audit taken **at the commanded 45 mm aperture, which a gripper holding a 50 mm part never
> reaches** — the measured pad-face separation at the hold is **49.98 mm (vendor) /
> 50.01 mm (hull)**.
>
> **The grasp outcomes are indistinguishable, and where they differ the hull is the better
> arm, never the worse.** Pick, hold and place succeeded in 24/24 vendor and 23/23 hull
> trials; nothing was flung in either; the single `trial_success` failure in the campaign is
> a **vendor** trial. **No pre-registered metric was DETECTED as worse under hulls.**
>
> **One thing is DETECTED, and it is a control:** the hull stalls the drive joint
> **5.6 mrad earlier** — `q_at_stall` 0.4165 → 0.4085 rad, `p = 2.2e-4`, surviving the
> block rule V4. The jaws stop marginally wider on hulls.
>
> **This campaign promotes nothing.** ADR-0028 stays `Proposed`, the shipped selection
> stays `vendor_meshes`, and both are unchanged in the tree at this commit.

## 1. The machine, and what it threatens

`criteria.md` §9 names it: Apple **M4 Pro**, 12 cores, 24 GiB, macOS 25.5.0; Docker Desktop
allocated **12 CPUs / 7.65 GiB**; `COMPOSE_PROJECT_NAME=cite-digital-twin-3748020299`,
`ROS_DOMAIN_ID=99`, own volumes; `./scripts/doctor` 25 passed, 0 failed, 1 skipped.

**The host was not quiet and could not be made quiet.** 1-minute load average at each
block's start, after a 60 s quiesce: **VENDOR_B1 3.64, HULL_B1 5.72, VENDOR_B2 7.75,
HULL_B2 5.82** on 12 cores. It is not systematically confounded with geometry — the vendor
blocks bracket the hull blocks on both sides.

**Every metric here is a function of simulation state in simulation time**, as `criteria.md`
§9 argued in advance: pose-feed stamps, contact-sensor stamps and the drive joint's own
position. Host load moved wall time — a trial took **46.6 s** median on vendor and
**37.8 s** on hull — and that figure is reported as context only. **No capacity claim is
made from it**; the campaign that owns that question is
[`2026-08-31-capacity-and-clock-deficit/`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md).

Free disk was **16 GiB** at the start of the session and was raised to **63 GiB** by
removing 81 stale Docker volumes belonging to worktrees that no longer exist (44 GB) and
11 GB of unused build cache; 31 GiB was still free when the last block ended.

**No `gz sim` process and no cell container survived any block, and that is checked rather
than assumed.** The driver sweeps after each block and reports what is left: **11
containers**, every time, all of them the unrelated Supabase stack named in §9 of
`criteria.md` — the sweep's filter for `cite` and `docker-dev` names printed nothing on any
of the three occasions it ran. It did not run after the fourth block, which was killed
(§2); the host was checked by hand instead and carried no `gz sim` and no cell container.

## 2. Deviations, both recorded rather than repaired

**Deviation 1 — the hull arm has 23 trials, not 24, and the cause is not the system under
test.** The orchestrating tool killed the campaign's background process during trial 11 of
`HULL_B2`, leaving that block with 11 complete trials. `criteria.md` V6 says every rate is
reported over the trials that actually ran and **no arm is topped up to match the other**,
so the missing trial was not re-run — a twelfth hull trial added after the totals were
visible is a trial chosen by the totals. `HULL_B2`'s own harness wrote each of the 11
completely. The kill also pre-empted the driver's closing `git checkout`, so the scratch
flip was reverted by hand immediately afterwards; `./scripts/validate-model` then reported
the model valid and `git status` showed no modification outside this directory.

**Deviation 2 — V5 excluded two trials from M1 and M2, and only two, both in `HULL_B2`.**
`body_move_mm` — how far the gripper body itself moved over the closure window — was
**12.04 mm and 28.38 mm** in `HULL_B2` trials 9 and 10, against a median of **0.28 mm
(hull) / 0.42 mm (vendor)** and a V5 ceiling of 2.0 mm. Both have closure windows of 0.97 s
and 1.44 s against a 0.48–0.57 s median, so first contact was registered while the arm was
still descending. The rule excluded them from M1 and M2 exactly as written. They remain in
every carry metric, which does not depend on that window.

**No other trial was excluded.** V3's frame residual — the angle between the triad's `ey`
and the measured pad-to-pad direction — was **0.304° in every one of the 47 trials**,
against a 5° ceiling.

**V2 held in all four blocks.** Each block read the description the **running** cell
published: `hull_collision_refs` **13** in both hull blocks and **0** in both vendor blocks.
No block was discarded.

**Deviation 3 — one of this campaign's own checks silently did nothing, and it is recorded
rather than quietly fixed.** `run_block.sh` also greps the *generated* xacro before launch,
as a cheap pre-flight beside V2's runtime check. It names
`cite_generated/`**`descriptions`**`/cell_a_arm_1.urdf.xacro`; the directory is
`cite_generated/`**`description`**`/`. The grep therefore reported *no such file* in all four
blocks and its output file carries only the label it was handed —
`raw/logs/<LABEL>_geometry.txt` contains `declared_geometry=...` and nothing else. **It is
the harness, so it is frozen and stays wrong** (`../README.md`); a stale reference inside a
published harness is a fact about the measurement, and a corrected one is a claim about code
that never ran. **Nothing rests on it**: V2's evidence is `raw/<LABEL>_geometry.json`, read
from the running cell's `robot_description`, and that check fired correctly in every block.
The transferable part is the one this repository keeps paying for — **a check that cannot
fail is indistinguishable from a check that passes**, and this one would have looked like
corroboration if V2 had not existed beside it.

## 3. The A/B, every pre-registered metric

Medians over the pooled trials of each arm; `HL shift` is the Hodges-Lehmann median of
pairwise differences, hull minus vendor; `p` is a two-sided Mann-Whitney U; `MIS` and the
verdict rules are `criteria.md` §7. Produced by `harness/analyse.py`; the machine-readable
form is `raw/analysis.json`.

| metric | family | vendor | hull | HL shift | p | vendor IQR | MIS | verdict |
|---|---|---|---|---|---|---|---|---|
| `patch_len_left_mm_median` | M3 | 37.4994 | 36.3015 | −0.5700 | 8.7e-02 | 0.144 | 2.0 | not detected |
| `patch_len_right_mm_median` | M3 | 37.4997 | 29.0945 | −1.9992 | 1.8e-01 | 3.577 | 2.0 | **UNRESOLVED (R)** |
| `normal_approach_component_max` | M4 | 0.0026 | 0.0058 | +0.0019 | 3.7e-03 | 0.0032 | 0.02 | not detected |
| `normal_approach_component_median` | M4 | 0.0023 | 0.0054 | +0.0022 | 3.4e-03 | 0.0033 | 0.02 | not detected |
| `d_approach_mm` | M1 | 0.2370 | 0.1917 | −0.0408 | 1.3e-03 | 0.034 | 0.20 | not detected |
| `d_close_mm` | M1 | 0.5269 | 0.1257 | −0.2286 | 1.5e-02 | 0.134 | 0.20 | not detected |
| `d_pivot_mm` | M1 | −0.1216 | −0.0924 | +0.0228 | 7.4e-02 | 0.035 | 0.20 | not detected |
| `pitch_pivot_deg` | M2 | 0.1809 | 0.0088 | −0.0781 | 4.9e-02 | 0.192 | 0.50 | not detected |
| `roll_close_deg` | M2 | 0.0476 | 0.0273 | −0.0075 | 1.4e-01 | 0.021 | 0.50 | not detected |
| `yaw_approach_deg` | M2 | 0.0044 | 0.0003 | −0.0243 | 2.6e-03 | 0.030 | 0.50 | not detected |
| `twist_max_deg` | C1 | 2.2247 | 0.4367 | −1.5194 | 1.2e-04 | 4.799 | 5.0 | not detected |
| `carry_rot_world_vertical_deg` | C2 | 0.0219 | 0.0039 | −0.0139 | 2.6e-03 | 0.096 | 2.0 | not detected |
| `q_at_stall_rad` | C4 | 0.4165 | 0.4085 | **−0.0056** | **2.2e-04** | 0.0032 | 0.005 | **DETECTED** |
| `pad_separation_mm_mean` | C4 | 101.7310 | 101.8604 | +0.1187 | 4.6e-04 | 0.114 | 0.5 | not detected |
| `slip_max_mm` | C3 | 2.8115 | 1.5064 | −1.2223 | 1.8e-05 | 1.201 | 2.0 | not detected |
| `place_err_m` | C3 | 0.0016 | 0.0009 | −0.0005 | 3.0e-03 | 0.0030 | 0.010 | not detected |
| `lift_m` | C3 | 0.1195 | 0.1196 | +0.0000 | 5.9e-01 | 0.0003 | 0.010 | not detected |
| `v_max_mps` | C3 | 0.2253 | 0.2730 | +0.0378 | 2.8e-03 | 0.058 | 0.050 | **UNRESOLVED (R)** |

**Read the `p` column against the MIS column, not on its own.** Eleven of the eighteen
metrics separate at `p < 0.01`, and **only one of them separates by as much as the size
registered in advance as interesting.** That is what a pre-registered effect size is for:
with n = 47 this instrument distinguishes differences it was written to call negligible.

**Two rules refused a metric, and both did so where it was inconvenient.** R disqualified
`patch_len_right_mm_median`, which carries the largest raw difference in the table
(−8.4 mm on medians), because the **vendor** arm's own IQR on it is 3.58 mm — larger than
the 2.0 mm the difference had to clear. V4 refuses it independently: the two **vendor**
blocks differ by 4.15 mm on that metric and the two **hull** blocks by 7.50 mm, both larger
than the between-geometry shift. `v_max_mps` is refused by R for the same reason.

## 4. Rule S fired, and what it obliged the campaign to report

`criteria.md` §7.4: if neither M3 nor M4 is DETECTED the verdict on Q0 is **INCONCLUSIVE
and not "no change"**, and the write-up must report the stall aperture and the patch's `ez`
extent against the wedges' own `ez` positions. From `harness/mechanism.py`:

| | vendor | hull |
|---|---|---|
| pad-face separation at the hold | **49.979 mm** | **50.014 mm** |
| left-pad contact reaches | z = 134.02 … 171.51 mm | z = 134.60 … 171.41 mm |
| right-pad contact reaches | z = 134.38 … 171.87 mm | z = 134.23 … **163.24** mm |
| \|n·ez\| over the hold, max | 0.0026 | 0.0058 |

**The jaws stall on the part at ~50.0 mm, not at the commanded 44.99 mm.** Every relief
feature is on the same rigid link as the pad, so it moves out with it. At the aperture the
gripper actually reaches, the hull's closest wedge — the z = 134 shoulder, ADR-0028's
worst case — has a surface aperture of **50.42 mm against a 50 mm part: clear by
0.42 mm.** The other two are clear by 1.30 mm and 2.68 mm. **None of the three touches.**

**The same conclusion follows from ADR-0028's own two numbers without any of this
apparatus, which is why it is worth stating twice.** The record measures the pad aperture
at **44.99 mm** and the z = 134 shoulder at **45.40 mm** on the hull. 45.40 > 44.99, so on
the hull that shoulder is still **0.41 mm of aperture recessed behind the pad plane**, and
the two surfaces belong to one rigid link. A flat face in contact with the pad is therefore
0.41 mm clear of the wedge **at every aperture**, whatever the command. This campaign
measures that clearance independently at **0.42 mm**; the two agree to 0.01 mm.

**So the error in ADR-0028's correction is an inference, not a measurement.** Its geometry
audit is confirmed. What does not follow from it is the sentence *"both shoulders lie inside
the part's envelope"*: that compares the shoulder's aperture against the part's **width**,
at the **commanded** 45 mm — a configuration a gripper holding a 50 mm rigid part cannot
occupy. The comparison that decides contact is the shoulder against the **pad plane**, and
the record's own figures already answer it.

**The instrument could have seen the effect had it been there.** `criteria.md` §4 registered
the resolution from two shakedown trials before any threshold was set: the pad reads as
**37.50 mm long to 0.02 mm**, and a flat pad's normal reads as flat to ~1e-3 against a
predicted wedge slope of ~0.22. The hull did move \|n·ez\| by a factor of **2.2**, at
`p = 3.4e-3` — a real signal, and **1/100 of the prediction**, which is what "the wedges do
not touch" looks like from the normal's side. This is a null with a known noise floor, not
a null from a blind instrument.

## 5. What did change, stated with its verdict attached

### 5.1 The jaws stop marginally wider on hulls — the one DETECTED metric

`q_at_stall_rad` **0.4165 → 0.4085**, a shift of **−5.6 mrad** at `p = 2.2e-4`, with a
vendor IQR of 3.2 mrad against a 5 mrad MIS. V4 clears it: the within-geometry block spread
is **0.9 mrad** against a between-geometry shift of 5.6 mrad. `pad_separation_mm_mean`
moves **+0.119 mm** and the pad-face separation **+0.035 mm**, both in the same direction
and both below their own thresholds.

**All three agree in sign: the hull brings something into contact fractionally sooner.**
The three magnitudes are not reconciled here and the campaign does not claim a mechanism
for them — see §7.

### 5.2 The contact patch got **shorter**, not longer, and the campaign cannot call it

ADR-0028 predicted **37 → ~44 mm**. Measured, on the shorter of the two pads:
**37.12 mm (vendor) → 28.20 mm (hull)**, and the loss is at the **distal** end — the right
pad's contact `z` maximum falls from 171.87 mm to 163.24 mm. **The sign of the prediction is
wrong**, which is consistent with §4: a convex hull cannot add material inside the envelope
of the pad plane, which is the innermost surface, and can only ramp *away* from it toward
the relief steps.

**This is reported as an observation and is not a detection.** R and V4 both refuse it, and
they are right to: the vendor arm is itself two-state on this metric. **8 of 24 vendor
trials** have a pad contacting over less than 30 mm, the shortest at 3.01 mm, against
**14 of 23** hull trials. Post-hoc, and labelled as post-hoc because `criteria.md` never
registered it, that rate difference is Fisher `p = 0.082` — not significant, on a metric
chosen after seeing the data, and it is recorded here only so that the next campaign knows
where to look. The pad-to-pad asymmetry \|left − right\| has a median of **0.33 mm on
vendor and 7.71 mm on hull**.

### 5.3 Every carry-quality metric moved in the hull's favour, and none by enough to call

| | vendor | hull |
|---|---|---|
| `trial_success` | **23/24** (Wilson 95 % LB 0.798) | **23/23** (Wilson 95 % LB 0.857) |
| pick / hold / place reported success | 24/24 | 23/23 |
| T2: `slip_max > 5 mm` | **5/24** | **0/23** |
| T2: `slip_rate > 0` | 24/24 | 23/23 |
| T4: flung | 0 | 0 |
| `slip_max_mm`, median | 2.81 | 1.51 |
| `twist_max_deg`, median | 2.22 | 0.44 |
| C5: non-zero `Pick`/`Place` result codes | none | none |

**The campaign's only `trial_success` failure is a vendor trial** — `VENDOR_B2` trial 10,
which failed `held_through_transport` with a `slip_max` of **30.27 mm**, past the friction
campaign's 25 mm out-of-jaws bound, while still reporting holding and placing to 2.5 mm.
Under T1 as written, **the vendor arm fails and the hull arm passes.** Fisher's exact test
on 23/24 against 23/23 gives `p = 1.0`; **one trial is not a rate**, and this is reported
as the direction the single failure happened to fall, not as a result.

**T2's slip half separates cleanly and is still not DETECTED.** No hull trial exceeded 5 mm
where five vendor trials did, but the HL shift on `slip_max_mm` is −1.22 mm against a 2.0 mm
MIS. `slip_rate` is positive in **47 of 47** trials, both arms, which reproduces the friction
campaign's finding that the displacement grows monotonically through the carry and stops
only when the arm stops.

**Nothing here says hulls improve the grasp.** Every one of these differences is below the
size registered in advance as worth acting on, and the campaign does not get to promote a
sub-threshold difference because its direction is convenient.

### 5.4 C5 — the outer-knuckle throat

The narrowed throat (67.6 → 40.4 mm, 60 mm below the part) produced **no planning effect**:
no non-zero result code from `MoveTo`, `Pick` or `Place` in any of the 47 trials, on either
geometry. `criteria.md` §8 registered in advance that **47 trials of one motion pattern is
not a test of that**, and this clean result must not be cited as one.

## 6. The direct answer

**Does hull geometry change the grasp?**

On the evidence here: **it does not change any outcome this cell reacts to, and the campaign
is formally inconclusive about the mechanism because the mechanism does not occur.** The
part is picked, held and placed identically; the pads contact it along the same plane, with
the contact normal's component along the approach axis staying below **0.006** on both
geometries against a wedge slope of ~0.22; the jaws stop 5.6 mrad earlier and 0.12 mm wider;
the contact band along the pad is shorter and more asymmetric by an amount the campaign's
own rules refuse to call.

**The specific risk ADR-0028 named — two inclined wedges inside the part's envelope pushing
it along the approach axis — was not observed, and the geometry says it cannot be.** The
wedges sit 0.41 mm behind the pad plane on the same link.

## 7. What was not measured, and what would settle it

- **Whether a hulled link other than the two pads touches the part.** The harness filtered
  the contact record to finger contacts at write time, so the campaign's raw cannot say
  whether a hulled knuckle contacts the work-piece — which is one candidate explanation for
  §5.1's earlier stall. **Settled by:** one block with the contact filter widened to every
  collision pair involving the work-piece.
- **Why the jaws stall 5.6 mrad earlier.** Detected, and unexplained. The three related
  figures (5.6 mrad, +0.119 mm at the link origins, +0.035 mm at the pad faces) agree in
  sign and are not reconciled in magnitude here. **Settled by:** the static audit re-run at
  the **achieved** pad-face separation of ~50.0 mm rather than at the commanded 44.99 mm,
  which is also what would explain §5.2.
- **Why the contact patch loses its distal end on one pad.** Observed at 171.87 → 163.24 mm
  and not explained. **Settled by:** the same re-run of the audit, reporting where the
  hull's surface departs from the pad plane as a function of `z`.
- **Any timestep but the shipped 0.001 s.** The friction campaign found grasp *quality*
  varies by a factor of 24 across a 4x timestep change. **Every figure here is at one
  timestep**, and none of it says how a hull behaves at another.
- **Any arm but `arm_1`, any part but the 50 mm cube, any grasp but the 45 mm command.**
  §4 and §5.2 both turn on where the part's face sits relative to the relief steps, so a
  part of a different width is a different question — and a **narrower** part would let the
  pads close further and could bring the wedges into contact. That is the case this campaign
  most plainly does not cover.
- **The self-collision matrix.** ADR-0028 records that hulls narrow the reachable
  configuration space by 1.9 % against a matrix computed for vendor geometry. C5 saw
  nothing; §5.4 says why that is not evidence.
- **Two hull trials' closure window**, excluded by V5 (§2). Whether they represent a real
  hull behaviour or an artefact of first-contact detection during descent is unestablished.
- **The physical arm.** This measures the simulator. The layout is `PROVISIONAL` and the
  physical scan is Phase 3.

## 8. What this is evidence for, and what it is not

**It is clause 2 of ADR-0028's promotion gate, executed**: the friction-grasp campaign
re-run against hull collision geometry, with the three quantities that record's correction
names, published with its thresholds registered first.

**It does not promote ADR-0028 and may not be cited as doing so.** The record's status and
the shipped `select: vendor_meshes` are untouched at this commit; `./scripts/validate-model`
reports the model valid and the tree carries no flip. Whether an INCONCLUSIVE verdict with
no measured harm satisfies a gate whose question was *"does the hull change the grasp"* is a
decision for whoever owns that record, taken on this evidence — not a finding of it.

**Two things here bear on the record's text rather than its status**, and both are stated in
§4: its geometry audit is confirmed, and the inference it drew from that audit — that the
shoulders lie inside the part's envelope — does not follow, because the audit's aperture is
the commanded one and not the achieved one.

**One machine, 47 trials, one timestep, one part.** Nothing here is a claim about CI, about
x86_64, or about any other host.

## 9. Provenance — the branch is shared, and two commits on it are not this campaign's

`measure/hull-grasp` was branched from `main` at `d79a856`, and **two documentation commits
by a concurrent agent working in the same checkout landed on it** before this campaign's
first commit: `79bb040` and `7997d04`, which amend `CLAUDE.md`, four ADRs including
[ADR-0028](../../adr/0028-convex-hull-collision-meshes.md), and
`docs/operations/bring-up.md`. They are recorded here rather than moved: they are another
agent's work, this campaign does not own `docs/adr/` or `CLAUDE.md`, and rewriting a shared
branch's history to tidy a provenance note would be the more destructive act. **Whoever
merges this branch is merging them too and should know that.**

**They do not reach the measurement.** Both commits are documentation only — no `model/`,
no generator, no `workspace/src/`, no scenario. And the ADR-0028 amendment among them is
about the capacity campaign; it says in as many words that the promotion gate is untouched
and clause 2 is still the friction-grasp re-run, which is what this campaign executed.

The two commits this campaign owns are `b690c41` (criteria and harness, before the first
trial) and `9824a0c` (data and this write-up). Together they touch this directory and one
line-block of `../README.md`, and nothing else.

## 10. Reproducing it

    docs/measurements/2026-09-01-hull-grasp/harness/run_campaign.sh 2 12
    .venv/bin/python docs/measurements/2026-09-01-hull-grasp/harness/analyse.py
    .venv/bin/python docs/measurements/2026-09-01-hull-grasp/harness/mechanism.py

`analyse.py` transcribes `criteria.md` §7 and §10 and was written while the first vendor
block ran, before any hull trial existed. `mechanism.py` is **post-hoc** and says so in its
own docstring: it answers the question rule S obliges the write-up to answer and sets no
threshold and changes no verdict.

`raw/` is pruned for size and the pruning is recorded in
[`raw/README.md`](raw/README.md). Nothing a figure above depends on was removed.
