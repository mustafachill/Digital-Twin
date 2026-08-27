# Results — what yaw does a work-piece carry when it reaches a downstream outfeed?

Read [`criteria.md`](criteria.md) first. It was written and saved before any scored trial
ran and states every threshold used below.

- **Date:** 2026-08-26
- **Branch / commit:** `feature/phase-1` at `7f2d8f9`, main checkout
- **Isolation:** `COMPOSE_PROJECT_NAME=cite_yawbelt`, `ROS_DOMAIN_ID=89`, own build and
  install volumes, built from scratch (19 packages, exit 0)
- **Environment check:** `./scripts/doctor` — 22 passed, 0 failed, 2 skipped (`ros 2`
  native, expected on macOS), 1 warned (shared volumes on the default project, not this
  one). Both declared patches verified **present** in `workspace/src/external/xarm_ros2`.
- **Rig:** the full cell — `cell_a`, all three arms, nine controllers, three `move_group`s,
  brought up by the shipped `cite_bringup/launch/simulation.launch.py` headless. Not a
  reduced one-arm rig.
- **74 scored trials** in five blocks. Raw per-sample poses and the analysis output are in
  [`raw/`](raw/), the harness in [`harness/`](harness/).

## Headline

| Arm | n | What it asked | Answer |
|---|---|---|---|
| **A** belt transfer | 36 | Does a conveyor ride change a part's yaw? | **No — by nothing at all.** Median abs delta **0.0000 deg**, largest single value 1.8e-08 deg, across 0–45 deg and both belt modes |
| **B** negative control | 3 | Does the `carried` gate discriminate? | **Yes.** A part outside the `<carry>` list travelled **0.0000 m** while the belt was commanded at 0.150 m/s |
| **D** shipped path | 12 | What yaw actually arrives at the outfeed? | Median **0.71 deg**, p95 3.03, **max 10.62 deg**. Presented across the jaws: max **58.35 mm** |
| **C** grasp boundary | 23 | Up to what yaw can the gripper pick? | **23/23 succeeded at every yaw from 0 to 30 deg.** Pooled Wilson 95% [0.857, 1.000] |
| **post-hoc** | 23 | Why? | **The gripper squares the part up as it closes.** Carried yaw 0.01–0.17 deg whatever it started at |

**The plain answer: a conveyor ride makes a downstream pick no safer and no less safe,
because it changes nothing. The pick is safe anyway, and for a reason neither ADR-0031 nor
this campaign's own hypotheses anticipated — the jaws are a self-aligning fixture.**

## Verdicts against the pre-registered thresholds

### G — gates. All pass.

- **G1 — the part was carried.** 36/36. `travelled_m` min 1.052, median 1.079, max 1.105 m
  against a 0.900 m gate and a 1.100 m nominal run.
- **G2 — the gate has teeth. PASS, and this is the load-bearing one.** Three trials spawned
  as `probe_nocarry` — a name outside the world's `<carry>workpiece</carry>` — moved
  **0.0000 m** in 3/3 while the belt was commanded at its installed 0.150 m/s. So "the yaw
  did not change" in Arm A is not the artefact of a part that was never carried. The two
  populations are separated by 1.05 m of travel, not by a judgement call.
- **G3 — flat.** 36/36 within 5 deg of flat at the read.
- **G4 — still on the belt.** 36/36.
- **G5 — the input was actually set.** Median `|yaw_settled - commanded|` = **0.0000 deg** at
  every one of the six levels. The part settles at exactly the yaw it was spawned at.
- **G6 — Arm C got a grasp to measure.** `Pick` returned SUCCESS in 23/23, at every level.
  No trial was lost to a planner that could not reach the part.

### H1 — does a conveyor ride change the yaw? **It preserves it. PASS.**

| spawn yaw | n (running / indexed) | settled | at read | median abs delta | p95 | presented |
|---|---|---|---|---|---|---|
| 0 deg | 3 / 3 | 0.000 | 0.000 | 0.0000 | 0.0000 | 50.00 mm |
| 5 deg | 3 / 3 | 5.000 | 5.000 | 0.0000 | 0.0000 | 54.17 mm |
| 10 deg | 3 / 3 | 10.000 | 10.000 | 0.0000 | 0.0000 | 57.92 mm |
| 18.7 deg | 3 / 3 | 18.700 | 18.700 | 0.0000 | 0.0000 | 63.39 mm |
| 30 deg | 3 / 3 | 30.000 | 30.000 | 0.0000 | 0.0000 | 68.30 mm |
| 45 deg | 3 / 3 | 45.000 | 45.000 | 0.0000 | 0.0000 | 70.71 mm |

Pooled: n=36, median abs delta **0.0000 deg**, p95 0.0000, max 0.0000. Signed median
-0.0000 deg, bootstrap 95% CI **[-0.00000, -0.00000] deg**.

The threshold for "preserves" was median <= 2.0 deg and p95 <= 5.0 deg. The measurement does
not merely pass it — it comes in at the limit of double precision. The largest single
abs delta anywhere in 36 trials is **1.8e-08 degrees**.

**This is a stronger result than "the belt does not narrow the yaw", and the strength is
the point.** A belt that narrowed yaw by even a degree per metre would show up here as a
few hundredths of a degree of drift. There is no drift. Transport is *exactly* kinematic:
`conveyor.cpp` writes `LinearVelocityCmd`, `SetLinearVelocity` makes Physics ignore
wrenches on the carried link for the step, and nothing anywhere in `cite_simulation` writes
an angular velocity. The prediction the two earlier agents made from reading the plugin is
confirmed to eight decimal places.

**Both of this campaign's own competing hypotheses are refuted.** The belt does not narrow
the yaw by settling, and it does not widen it by leaving a spin undamped — see H2.

### H2 — is the part still turning when it arrives? **Settled. PASS.**

n=36, median abs yaw rate **0.0000 deg/s**, max 0.0000 deg/s. Turning faster than 1.0 deg/s
in **0/36**, Wilson 95% **[0.000, 0.096]**.

The widening mechanism this campaign was built to catch does not fire, and H5 shows why: a
release leaves no spin to be left undamped in the first place.

### H3 — does stopping the belt change the answer? **No. Explicitly, and this was asked for.**

- **Paired, within trial:** median abs difference between the reading in motion and the
  reading after the belt stops = **0.0000 deg**, max 0.0000, n=36.
- **Across modes:** running delta median -0.0000 deg (n=18), indexed delta median
  -0.0000 deg (n=18), two-sided permutation **p = 0.7417** (100 000 permutations,
  seed 20260825).

**Indexing the belt does not change this answer.** A part sampled in motion and the same
part sampled after the belt has stopped and it has settled read identically. The decision to
index the belt is a good one for its own reason — the pick window on a running belt is
0.667 s — but it neither helps nor hurts the orientation question, and no part of the
handoff argument should be built on it.

One thing indexing *does* change, observed rather than pre-registered: **an un-indexed belt
throws the part on the floor.** The outfeed frame at x = 1.600 sits 50 mm from the end of
the belt body at x = 1.650. In the shakedown, a part read in motion and left running for one
further wall second reached x = 1.709, tipped (tilt 23.5 deg) and fell 0.6 m. That is the
0.667 s window as a physical event rather than as an arithmetic one.

### H5 — what the shipped path actually delivers (Arm D, 12 trials)

`arm_1` picks a **square** part off `table_pick`, places it on `conveyor_1`'s infeed, the
belt runs, and the yaw is read at the outfeed. No yaw is commanded anywhere; the residual is
produced by an actual grasp.

| | median | p95 | max |
|---|---|---|---|
| yaw **as deposited** on the belt | 0.711 deg | 3.030 | **10.615 deg** |
| yaw **at the outfeed** | 0.711 deg | 3.030 | **10.615 deg** |
| presented across the jaws at the outfeed | 50.62 mm | — | **58.35 mm** |
| ride contribution abs delta | 0.0000 deg | — | 0.0000 deg |

Spin as deposited: median 0.0000 deg/s, **0/12** above 1.0 deg/s, Wilson [0.000, 0.243].
Spin at the outfeed: 0/12. **The release leaves the part with no measurable angular
velocity**, which is why H2 is a null and not a widening.

Per trial the arrival yaw is the deposited yaw to eight decimal places in all twelve. Ten of
twelve deposited below 3 deg; one at 3.03 and one at 10.62.

**On ADR-0029's 18.7 deg.** This campaign measures its own residual rather than inheriting
that number, and gets a **maximum of 10.62 deg over 12 trials** where ADR-0029 records up to
18.7. The two are not in conflict and the difference is not evidence of anything: 12 trials
cannot bound a maximum that 40 trials found, and the grasp-plane correction has landed in
the L3 server since (`skill_server.cpp` now offsets onto the pad plane from the end
effector's declared linkage), which is exactly the change that took rotations above 20 deg
from 12/20 to 0/20. **The larger of the two figures is the one a decision should use**, and
nothing here supersedes ADR-0029.
**[Corrected 2026-08-26 — see "Correction, 2026-08-26" below: the two figures are not the
same quantity, ADR-0029's being a roll about the pad-to-pad axis rather than a yaw. Using
the larger remains the conservative choice and the verdict is unaffected.]**

### H4 — where does the grasp boundary fall? (Arm C, 23 trials)

`grasp_ok` = `lift_m > 0.05` **and** `held_through_transport` **and** `place_err_m <= 0.05`,
every term read from Gazebo's own pose feed. **Not** `pick_reported_holding`, which
criteria.md pre-registered as unusable because at every yaw in range the part presents at
least 50.00 mm against jaws commanded to 45 mm, so it is true by construction. It was indeed
true in 23/23 and discriminated nothing, as predicted.

| spawn yaw | presented | n | grasp_ok | rate | Wilson 95% |
|---|---|---|---|---|---|
| 0 deg | 50.00 mm | 5 | 5/5 | 1.00 | [0.566, 1.000] |
| 5 deg | 54.17 mm | 4 | 4/4 | 1.00 | [0.510, 1.000] |
| 10 deg | 57.92 mm | 4 | 4/4 | 1.00 | [0.510, 1.000] |
| 15 deg | 61.24 mm | 4 | 4/4 | 1.00 | [0.510, 1.000] |
| 20 deg | 64.09 mm | 3 | 3/3 | 1.00 | [0.438, 1.000] |
| 30 deg | 68.30 mm | 3 | 3/3 | 1.00 | [0.438, 1.000] |

Fisher exact against the 0 deg cell: p = 1.00000 at every level.

- **theta_safe: UNDETERMINED at the per-level rule, and the reason is n, not the gripper.**
  With every trial a success the Wilson lower bound is `n/(n+3.8416)`, a statement about
  sample size. Clearing 0.80 needs n >= 16 in a single cell; the largest cell here is 5. The
  pre-registered per-level rule is **underpowered** and is reported as undetermined rather
  than as a failure.
- **theta_fail: none of the tested levels.** No level's upper bound comes near 0.50.
- **Pooled**, which the uniform mechanism below licenses and which is stated as a pooled claim:
  - 0–30 deg, all levels: **23/23, Wilson 95% [0.857, 1.000]**
  - 5–30 deg, yawed only: **18/18, Wilson 95% [0.824, 1.000]**

**No boundary was found anywhere in the tested range.** The sweep was designed expecting one
between 10 and 20 deg; there is none up to 30 deg, which is 68.30 mm presented against 45 mm
commanded — comfortably past the 63.39 mm that ADR-0031 argues would cam out.

### Post-hoc — why there is no boundary: the gripper squares the part up

**Not pre-registered.** It is an analysis of a mechanism over data already collected, and it
is reported because it changes what the H4 rate *means*.

A square held at two opposite corners by flat parallel jaws is in unstable equilibrium: the
contact normals miss the centre, so squeezing produces a couple that rotates the part until
a face lies flat on each pad. That is what happens.

| spawn yaw | n | median folded yaw **during the carry** | median stall width | width predicted if the part had kept its yaw |
|---|---|---|---|---|
| 0 deg | 5 | 0.17 deg | 49.64 mm | 50.00 mm |
| 5 deg | 4 | 0.06 deg | 49.88 mm | 54.17 mm |
| 10 deg | 4 | 0.02 deg | 49.85 mm | 57.92 mm |
| 15 deg | 4 | 0.01 deg | 49.37 mm | 61.24 mm |
| 20 deg | 3 | 0.01 deg | 49.77 mm | 64.09 mm |
| 30 deg | 3 | 0.03 deg | 49.96 mm | 68.30 mm |

**Two independent witnesses, from two different subsystems, agree.**

- **The physics pose feed:** a part spawned at 30 deg is *carried* at 0.03 deg. It rotated
  29.97 deg during closure.
- **The joint state:** `q_at_stall_rad` through the L0 axial map puts the jaws at
  **48.8–49.96 mm** at every level. A part still at 30 deg would have stopped them at
  68.30 mm. The jaws close 18 mm further than a rotated part would allow, which they cannot
  do unless the part turned.

These come from different places — Gazebo's pose stream and `/joint_states` — so their
agreement is evidence rather than one number restated.

**This is what the published campaigns were already measuring without naming it.** The
friction campaign's `twist_max_deg` — up to 34.3 deg, "the work-piece rotates between the
jaws" — is this rotation seen through a metric that could not tell alignment from
disturbance. In this campaign `twist_max_deg` tracks the spawn yaw (0.77 deg at 0, 20.15 at
10, 16.71 at 20): it is largely the part *coming into* alignment, not being knocked out of it.
**[Corrected 2026-08-26 — see "Correction, 2026-08-26" below. The first sentence does not
hold: the published campaigns fed the cell square, and their rotation is about a different
axis. The rest of this paragraph is this campaign's own data and stands.]**

**It also means the gripper does not deliver a square part.** The part is carried square and
released with a residual — 0.02 to 5.86 deg across Arm C, 0.11 to 10.62 across Arm D. The
alignment happens on closure and is partly given back on release.

## The verdict

The pre-registered rule compares **theta_arrive**, the upper end of what arrives at the
outfeed, against **theta_safe**.

- **theta_arrive = 10.62 deg** measured here over 12 end-to-end trials; **18.7 deg** if
  ADR-0029's larger published maximum is used, which it should be.
- **theta_safe** was not established at the per-level rule for want of n, but the pooled
  result is **23/23 successful picks over 0–30 deg, Wilson lower bound 0.857**, and 30 deg is
  well past 18.7.

theta_arrive sits inside the whole tested range, at either figure. By the pre-registered table:

> **Conveyor-mediated handoff is safe on physical grounds.**

**But the reason in ADR-0031 is still wrong, and this campaign does not rescue it.** The ADR
permits the conveyor case because the part is "re-observed with `Detect`... the uncertainty
is measured away". Nothing re-observes anything: `Detect` returns no pose, the belt changes
no yaw, and this campaign confirms both. The permission survives on a completely different
ground — **the receiving gripper tolerates the yaw, because closing on it removes it.**

**And that ground is not specific to conveyors.** If the jaws square the part up, they do so
whoever is holding it. The measured basis for permitting the conveyor case does not, on its
own, distinguish the direct arm-to-arm case — which ADR-0031 refuses. **The refusal may
still be right; this campaign did not test it**, because a direct handoff has a second
gripper holding the part while the first closes, and a part clamped by one gripper cannot
rotate into alignment with the other. That is a different experiment and it is named in
*Not measured* below. **The refusal should not be lifted on the strength of this campaign.**

### Is it close?

**No.** This is not a marginal result in either direction. The belt's effect is zero to eight
decimal places, and the grasp succeeded 23 times out of 23 at yaws up to 60% beyond the worst
residual ever published for this cell. The one place the answer *is* thin is n per level in
Arm C, and that is stated above rather than smoothed over.

## Deviations from `criteria.md`

1. **Arm D was added, and two harness faults fixed, after a two-trial shakedown and before
   any scored trial.** Recorded in `criteria.md` itself as an amendment, with the shakedown
   thrown away. No threshold was changed.
2. **Arm C ran as two blocks (7 + 16) against two separate cells, not one.** The first block
   was interrupted at trial 7 of 36 and the second died on a `ros_gz_sim create` timeout at
   trial 17 of 18. Every row carries `block` so the pooling can be undone. Interleaving is
   preserved *within* each block — the yaw cycles per trial index — so no condition is
   confined to one cell.
3. **Arm D does not report `pick_reported_holding`, because the harness read it from the
   wrong field.** `holding` is a top-level field of the `Pick` result beside
   `ResultCode result`, not a member of it; the first version read `pick.result.holding`,
   `getattr` returned its default, and twelve trials that were all holding recorded `False`.
   Fixed in `endtoend_yaw.py`. The block is reported as **not carrying that field** rather
   than as having measured it false. That the gripper was holding is evidenced instead by
   `Place` succeeding with `require_holding=True` and by the part physically arriving on the
   belt in 12/12.
4. **Both Arm C blocks' `*_trials.json` were reconstructed from the harness's own stdout**,
   because `measure_grasp.main` writes that file only after its loop completes and neither
   block completed. The per-trial rows are the harness's own JSON, unmodified, plus
   `commanded_yaw_deg` recomputed from the trial index by the same rule the shim used, and
   `recovered_from_stdout: true`. The per-sample CSVs, which every metric is derived from,
   were written per trial and are untouched.
5. **`GRASP_HEIGHT_M` is 0.025, not the published harness's 0.030.** Declared in
   `criteria.md` before any trial ran, with the reason: the L3 server now applies the
   pad-plane offset itself, so 0.030 would stack the harness's old pre-compensation on the
   server's new one.

## Correction, 2026-08-26 — the published campaigns were not measuring this

Written after publication, in the documentation pass that corrected
[ADR-0031](../../adr/0031-refuse-direct-handoff-without-orientation-certainty.md) from this
campaign. Nothing above it is rewritten and **no verdict changes**; the two sentences that
reach into the earlier campaigns are marked where they stand.

**What was written.** That the squaring-up "is what the published campaigns were already
measuring without naming it", and that the friction campaign's `twist_max_deg` of up to
34.3 deg is this alignment rotation seen through a metric that could not tell alignment from
disturbance.

**What is true.** The metric genuinely cannot tell the two apart — that half is right, and it
is why this campaign measures yaw about the world vertical instead. But the published
campaigns were not measuring alignment, for two reasons that are checkable in their own
directories:

1. **They fed the cell square.** `measure_grasp.spawn` calls `ros_gz_sim create` with `-x -y
   -z` and no orientation, so the work-piece is spawned axis-aligned; `table_pick/surface`
   carries `rpy_rad [0, 0, 0]` in `cite_generated/frames/cell_a_static_tf.yaml`, and the jaws
   close along world ±Y onto a face. There was no yaw to remove — the same condition as this
   campaign's own 0 deg cell, which twists 0.77 deg.
2. **Their rotation is about the wrong axis to be an alignment.** Re-analysed on 2026-08-26
   with this repository's own `2026-08-25-friction-grasp/harness/axis_check.py` maths, over all
   72 carries in the `step0p001`, `step0p0005`, `paired` and `paired2` blocks: the net carry
   rotation lies along the **pad-to-pad axis**, which is horizontal, at |cos| >= 0.9776 in
   every trial; its component about the world vertical never exceeds **0.49 deg**; and the
   part's folded yaw about the world vertical never leaves **0.00–0.84 deg** anywhere in any
   carry. The trial that produced the published 18.71 deg is a roll of 18.71 deg about that
   horizontal axis with a vertical component of 0.01 deg. Squaring-up is a rotation about the
   **vertical**; these are rolls between the pads.

   *Method, so that this can be checked rather than trusted.* `axis_check.py` cannot be
   imported on a host without ROS — it pulls in `measure_grasp`, which imports `rclpy` — so
   its arithmetic was re-implemented and run against the committed `*_samples.csv` and
   `*_trials.json` in the two campaign directories, with `arm_1`'s model pose taken from
   `axis_check.py` unchanged. For each trial: the net carry rotation is
   `quat_inv(q_first) · q_last` over the carry window, its axis compared with the
   left-pad-to-right-pad vector in the world; the folded yaw is the ZYX yaw of the
   work-piece quaternion reduced by the cube's 4-fold symmetry, taken at every sample in the
   carry. **This is a re-analysis of published data, not a new campaign**, and it registered
   no thresholds in advance.

**What this changes here.** Nothing in the four arms, the verdict, or the post-hoc mechanism:
every one of those is measured on this campaign's own trials, which *were* spawned yawed. What
it removes is a claim about somebody else's data.

**One knock-on, in H5.** That section compares this campaign's deposited yaw against
ADR-0029's 18.7 deg and recommends "the larger of the two figures is the one a decision should
use". The two are not the same quantity — one is a yaw about the vertical, the other a roll
about the pad-to-pad axis — so they should not be compared as though they were. The
recommendation is nonetheless the conservative one and the verdict is unaffected: 18.7 is the
larger number, and theta_arrive sits inside the tested range at either figure.

**How the error survived.** It was an inference across campaigns, drawn from a magnitude
without its axis, and it was drawn in the direction that made a new mechanism explain more
than it had been measured to explain. `twist_max_deg` is a scalar; the axis was established
once in the friction campaign and lives in one sentence of its prose; and a scalar travels
between documents far more easily than the condition that gives it meaning. The general
lesson is the one this campaign already states about its own metric — **an angle without an
axis is not a measurement of anything** — applied to the campaign that quoted it.

## Note, 2026-08-27 — the harness cites a function that no longer exists, and it is not edited

`harness/belt_yaw.py`'s `Belt` docstring says:

> `tests/scenarios/continuous_line.py:_start_the_belts` records that nothing in the running
> system does — the setpoint has no owner, and the scenario supplies it. This harness
> supplies it the same way, on the same topic, with the same message type and QoS profile,
> so that "the belt was running" means here what it means there.

That function no longer exists. ADR-0032 gave the setpoint an owner in L4, and on 2026-08-27
that owner was made to actually deliver — see the 2026-08-27 correction on
[ADR-0032](../../adr/0032-index-the-belt.md). `continuous_line` now reads the command topics
instead of writing them.

**The file is not edited, and this note is the correction instead.** `harness/` is the code
that produced `raw/`; changing it makes it no longer that, and this campaign's `criteria.md`
is frozen. A reader who wants to know what was executed to produce the numbers above must be
able to read it as executed. The rule is now written down in
[`../README.md`](../README.md).

**It changes nothing in this campaign, and it sharpens one thing.** The harness commanded the
belt itself and said so; no result here depended on L4 commanding it, and the campaign never
claimed otherwise. What is now known is *why* the docstring's description was right: the
docstring on `command()` explains its `repeats: int = 10` as "repeated for the reason the
scenario repeats it: the bridge may connect after the first message, and a dropped setpoint
is a belt that never starts." That diagnosis was correct and understated: what a message
misses is not only a bridge that has not connected but any subscriber a reliable publisher
has not yet been *matched* with, which is why L4's own belt command reached nobody however
long the bridge had been up. This harness was right to publish, and right for a reason
nobody knew at the time.

## Threats to validity

- **This measures the simulator, not the cell.** Nothing here evidences behaviour on the
  physical xArm. The layout is `PROVISIONAL` and the physical scan is Phase 3 (charter §8).
- **The squaring-up result is the most simulator-dependent thing in this campaign, and it is
  the one the verdict now rests on.** It is a rigid-body contact result from DART with
  `mu = mu2 = 1.0` on the part and no friction declared on either the pads or the table. A
  real gripper with compliant pads, a real part with chamfers or burrs, and real surface
  friction may align less willingly or not at all. **Phase 2 must re-measure this before any
  handoff is built on it**, and it should be treated as the campaign's single largest
  sim/real divergence risk rather than as a settled mechanism.
- **Arm C measures the grasp boundary at `table_pick`, not on the belt.** The gripper
  geometry is what is under test and does not change between stations, but the contacting
  surface does. Neither the table nor the belt declares a friction block, so Gazebo's
  defaults apply to both — that is an argument, not a measurement.
- **Arm A measures `conveyor_1` only.** All three belts are the same type at the same speed
  with identical plugin configuration, so the result is expected to transfer; that
  expectation is not tested.
- **n per level in Arm C is 3–5.** Enough to find no boundary; not enough to certify a rate
  at any single level. Stated in the analysis output as a power statement.
- Planning is unseeded (ADR-0006) and `CITE_PHYSICS_SEED` reaches nothing (ADR-0027), so
  trials are independent samples, not replicates. Every rate is a rate over samples.
- Real-time factor on this host varied over the campaign — Arm A ran at roughly 21 s of wall
  clock per trial and one Arm C trial took 100 s. Wall-clock figures are diagnostics, never
  results; every reported quantity is in simulation time or is dimensionless.

## Not measured, and needed before the record is rewritten

- **The direct arm-to-arm case.** A part clamped by a giving gripper cannot rotate into
  alignment with a receiving one, so the mechanism that makes the conveyor case safe is
  precisely the mechanism a direct handoff denies. ADR-0031's refusal is untouched by this
  campaign and should stay.
- **What a `Place` deposits at a yaw other than square.** Arm D feeds the cell square, which
  is the realistic case for the first station. What the *second* station deposits after
  picking an already-yawed part is one more grasp cycle further on and was not run.
- **Whether the residual accumulates over a three-station line.** Each station squares the
  part up and gives some back on release. Whether that converges or drifts over the
  `continuous_line` ladder is a question this campaign's method could answer and did not.

## Reproducing

From the repository root, on a machine where `./scripts/doctor` exits 0:

```
COMPOSE_PROJECT_NAME=<yours> ROS_DOMAIN_ID=<yours> ./scripts/enter dev \
  bash /workspace/docs/measurements/2026-08-26-conveyor-yaw-transfer/harness/run_block.sh \
       <harness.py> <label> <trials> [harness args...]
```

The five blocks reported above, in the order they were run:

```
run_block.sh belt_yaw.py        belt      36 --yaws 0,5,10,18.7,30,45 --modes running,indexed
run_block.sh belt_yaw.py        nocarry    3 --yaws 20 --modes running \
                                             --nocarry-name probe_nocarry --ride-ceiling 45
run_block.sh endtoend_yaw.py    endtoend  12 --modes running,indexed
run_block.sh yaw_grasp_block.py graspyaw  36 --yaws 0,5,10,15,20,30    # interrupted at 7
run_block.sh yaw_grasp_block.py graspyaw2 18 --yaws 0,5,10,15,20,30    # ended at 16
```

Then, in the container:

```
python3 harness/analyse_yaw.py        # gates, H1-H5, pooled intervals, power statement
python3 harness/grasp_alignment.py    # the post-hoc alignment analysis
```

Both write what `raw/analysis_output.txt` contains. Every figure in this document is derived
from `raw/`; nothing is transcribed by hand.
