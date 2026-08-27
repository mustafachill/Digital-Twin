# Criteria — what yaw does a work-piece carry when it reaches a downstream outfeed?

**Written and saved before any scored trial of this campaign ran.** Recorded here so
that the thresholds can be seen to have preceded the numbers (P8). Nothing in this file
may be edited once the first scored trial has run; disagreements with it are recorded in
`ANALYSIS.md` as numbered deviations, with the reason.

- **Date opened:** 2026-08-26
- **Branch / commit under measurement:** `feature/phase-1` at `7f2d8f9`, main checkout
- **Isolation:** own `COMPOSE_PROJECT_NAME`, own build and install volumes, built from
  scratch (19 packages)
- **Predecessors:** [`../2026-08-25-friction-grasp/`](../2026-08-25-friction-grasp/) (84
  trials) and [`../2026-08-25-grasp-plane-offset/`](../2026-08-25-grasp-plane-offset/) (40
  trials). Read both first. This campaign reuses their harness for pose sampling,
  spawning, removal and the quaternion primitives, so its readings are taken off the same
  feed, in the same frame, with the same stamps, and are directly comparable.

## The question, and why it is open

[ADR-0031](../../adr/0031-refuse-direct-handoff-without-orientation-certainty.md) refuses a
direct arm-to-arm handoff and permits a conveyor-mediated one. **The refusal is sound. The
permission is not yet evidenced**, and the justification it was given has been shown false.

The ADR argued that in the conveyor case the receiving station "re-observes it with
`Detect`, whose `Detection.pose` is a full pose — the uncertainty is *measured away*". No
detector in this cell can do that. The only pose sensor in the model is a through-beam,
which reports occupancy; `Detect` now says so explicitly by leaving `Detection.pose`
unobserved (`cite_skills`, commit `ca59e97`). Before that correction the claim was still
false, because the pose the beam returned carried the beam housing's own constant
`rpy (0,0,0)` — ADR-0029's residual was being "measured away" by a hard-coded identity.

The obvious physical replacement for that argument has also been questioned. Two agents
observed that `belt_1200x400` declares one box body and **no rail, fence or funnel**, and
that `cite_simulation/src/conveyor.cpp` carries a part by writing `LinearVelocityCmd` — a
pure translation. Their conclusion was that a part released at some yaw arrives at that
same yaw, so the belt removes nothing.

**That conclusion is a prediction, not a measurement, and this campaign exists because it
may be wrong in either direction.** Two mechanisms it does not account for:

- **The belt may WIDEN the distribution, not preserve it.** `conveyor.cpp` writes
  `LinearVelocityCmd` and never touches angular velocity — `grep` for `AngularVelocity`
  over `cite_simulation/` returns nothing. Gazebo's `SetLinearVelocity` makes Physics
  ignore wrenches on that link for the step. A part deposited with residual *spin* may
  therefore keep spinning down the belt with nothing to damp it, and arrive at a yaw that
  depends on when the gripper happens to reach it rather than on the yaw it was released
  at.
- **The belt may NARROW it.** The part is not welded to the belt: it rests on a collision
  box, is dropped onto it by a `Place`, and settles under contact. Settling on a flat
  plane can square a part up, and the plugin's velocity override does not obviously prevent
  that.

Neither can be settled by reading the plugin. Both are measured here.

**And 18.7° is not the threshold.** It is the largest residual observed in a different
campaign, not a limit. Where the boundary actually falls — the yaw past which a gripper
commanded to a nominal orientation can no longer pick the part — is measured here as its
own arm, because the verdict is a comparison between two distributions and this campaign
would otherwise be measuring only one of them.

## The metric, and why it is new code

A 50 mm cube rotated by θ about the vertical presents `50·(cos θ + sin θ)` mm across a
pair of jaws closing horizontally. That is the quantity ADR-0031 computes, and
`harness/yaw.py` restates it as code so that the ADR's arithmetic and this campaign's
threshold cannot drift apart.

**Neither published harness extracts a yaw, and their rotation measure is the wrong one
here.** `measure_grasp.py`'s `twist_max_deg` is a total rotation angle of the part relative
to the *pads* — exactly right for a part already held between two pads, and undefined for a
part lying on a belt with no gripper near it. What decides a downstream pick is yaw about
the **world vertical**, because the jaws close horizontally.

**The fold is the part that is genuinely new.** The published twist folds only the
quaternion double cover, mapping to `[0°, 180°]`. A 50 mm cube's four side faces are
physically indistinguishable, so a yaw of 89° presents exactly what a yaw of 1° presents.
The published campaigns never saw a rotation past 34.3°, so it never mattered to them; this
campaign deliberately spawns parts at 45°, so it does. Reported yaw is therefore folded by
the cube's 4-fold symmetry into `[0°, 45°]`, where it is monotonic in presented width:

| folded yaw | 0° | 5° | 10° | 18.7° | 30° | 45° |
|---|---|---|---|---|---|---|
| presented across the jaws | 50.00 mm | 54.17 mm | 57.92 mm | **63.39 mm** | 68.30 mm | 70.71 mm |

63.39 mm at 18.7° reproduces ADR-0031's own figure, which is the check that the two agree.

## The rig, and what is held fixed

| Quantity | Value | Where it comes from |
|---|---|---|
| Cell | `cell_a`, all three arms, nine controllers, three `move_group`s, `cite_bringup/launch/simulation.launch.py` headless | **not** a reduced one-arm rig, deliberately — a previous agent found a reduced rig systematically more favourable and had to retake everything |
| Work-piece | 50 mm cube, 0.2 kg, `mu = mu2 = 1.0` | published harness `_workpiece_sdf`, unchanged |
| Spawned model name | **`workpiece`** | `facility.workpiece_models`; the belt's `<carry>` list matches this by exact string equality |
| Belt | `conveyor_1`, `installed_speed_mps` 0.150, `direction: forward` (+x) | L0 `conveyors.yaml` |
| Belt geometry | body x ∈ [0.450, 1.650], infeed x = 0.500, outfeed x = 1.600 | `belt_1200x400.yaml` resolved at the instance pose |
| Beam trip | x = 1.550, 50 mm upstream of the outfeed | `sensors.yaml`, `beam_c1_out` |
| Commanded grasp width | 0.045 m | `default_grasp_width_m`, L0 |
| Gripper fully open | 88.93 mm | L0 axial map — wide enough to enclose 70.71 mm, so no yaw in range is excluded by stroke |
| `max_step_size` | 0.001 s, as shipped | generated world; **no deviation from the shipped configuration in any block** |

No production code is edited to run any block. Every lever is a harness argument.

## Amendment, and exactly when it was made

**Amended once, after a two-trial mechanical shakedown and before the first scored
trial.** The shakedown existed to prove the procedure executes — that a part spawned at a
yaw settles at it, that the belt carries a part named `workpiece`, and that the pose feed
delivers. It found two harness faults and was thrown away; no scored trial had run, so the
rules above are not yet in force and this is an amendment rather than a threshold moved by
data.

What the shakedown changed:

1. **Arm D was added** (below). The shakedown showed the host affords roughly 21 s of wall
   clock per belt trial rather than the several minutes budgeted, which makes the shipped
   end-to-end path affordable. It is the arm that most directly answers the question, and
   it is the only one that can test the spin mechanism at all — a part the harness sets
   down by hand has no spin to damp.
2. **Two harness faults were fixed.** The outfeed frame sits 50 mm from the end of the belt
   body, so a part read in motion and not stopped instantly runs off the end and tumbles
   onto the floor. That tumble was reaching the settled reading and the rate window. Both
   are now taken only from samples still on the belt, and the running mode stops the belt
   at the crossing with no intervening sleep.

Nothing in the thresholds below was changed, and no scored trial had been run when this was
written.

**One declared configuration choice, for Arms C and D.** The published harness's
`GRASP_HEIGHT_M` is 0.030; this campaign sends **0.025**. That is fidelity to the shipped
line, not a change to it. The published value was correct against the skill server of its
day, which planned the tip link straight to `object_pose` and so needed the harness to
pre-compensate. The server at the commit under measurement offsets onto the pad plane
itself from the end effector's declared linkage, and `PickAt` now sends
`workpiece_height_m` = 0.025, "where the object is". Sending 0.030 would stack the old
pre-compensation on the new one, park the pads 5 mm high, and reintroduce exactly the lever
arm the offset campaign measured out.

## The four arms

### Arm A — the belt's yaw transfer function

A part is spawned on `conveyor_1` at the infeed at a known yaw, allowed to settle with the
belt stopped, the belt is started, and the part's yaw is read again at the outfeed.

- **Independent variable:** spawn yaw ∈ {0, 5, 10, 18.7, 30, 45}°. 18.7° is included so
  the campaign has a point directly comparable with ADR-0029's residual; 45° is the
  symmetry extreme.
- **Second variable:** belt mode ∈ {`running`, `indexed`}. `running` reads the yaw in
  motion as the part crosses the outfeed. `indexed` stops the belt when the part reaches
  the beam, lets it settle, and reads it stationary — the belt the line is about to become.
- **Interleaved, not blocked.** Every one of the twelve conditions is visited once per
  round, against one running cell, before any is visited twice. The offset campaign
  established that processes in this cell can be bimodal and that consecutive
  same-configuration blocks sample the modes unevenly: its own blocks gave medians ranging
  9.6° to 29.8° for that reason.
- **Target n:** 24 scored trials (2 rounds), plus the negative control below. Reported as
  the number it actually was.

### Arm B — the negative control on the carry mechanism

Trials spawned under a model name **outside** the world's `<carry>` list, otherwise
identical.

This exists because of a mistake already made on this project: a part spawned under a name
the belt does not match rides nothing, trips nothing, and produces no warning, while the
belt goes on publishing its commanded speed. "The yaw did not change" would then be true
and would mean nothing. **This control is what gives the `carried` gate on every Arm A
trial its discriminating power** — it is a control designed to fire, not one that could
not have fired.

### Arm C — where the grasp boundary actually falls

A part is spawned at a known yaw and picked by an arm commanded to a **nominal** gripper
orientation, which is what the shipped line does: `PickAt`'s `pose` port is empty in this
cell and the frame fallback carries the station frame's yaw
(`skill_nodes.hpp`, "THIS PORT IS EMPTY IN THIS CELL, AND THE FALLBACK IS THE NORMAL PATH").

- **Independent variable:** spawn yaw ∈ {0, 5, 10, 15, 20, 30}°, interleaved.
- **Rig:** `arm_1` picking from `table_pick/surface` — **the published campaigns' exact
  configuration**, so that yaw is the single new lever and the 0° cell is directly
  comparable with their 68/68. Both the table and the belt are scene boxes that declare no
  friction, so the contacting surfaces are the same pairing; this is a named threat to
  validity rather than an assumption (see below).
- **Target n:** 24–30 trials. Reported as the number it actually was.

### Arm D — the shipped path, end to end

`arm_1` picks a **square** part off `table_pick` and places it on `conveyor_1`'s infeed,
which is what the published harness already does — its `PLACE_FRAME` is
`cell_a__conveyor_1__infeed`. The belt then runs and the yaw is read at the outfeed.

This is the question as asked, with nothing assumed: the grasp residual is produced by an
actual grasp rather than taken from another campaign, and no yaw is commanded anywhere.

- **Fed square (spawn yaw 0°)**, because that is the realistic case: parts arrive at the
  cell from outside it, and it is the *grasp* that is supposed to introduce the yaw.
- **Both belt modes**, interleaved.
- Three readings per trial: `yaw_deposited` (what the release left on the belt),
  `yaw_at_read` (what arrives at the outfeed), and the yaw rate at each.
- **Target n:** 12 trials. Reported as the number it actually was.

## The outcome measure for Arm C, and the artefact it is chosen to avoid

**`pick_reported_holding` is NOT the outcome, and pre-registering that is the point.**

At every yaw in range the part presents at least 50.00 mm across jaws commanded to 45 mm,
and `cite_skills::gripper_is_holding` calls a grasp anything that stalls more than about
2.11 mm wide of its command. So `pick_reported_holding` is true **by construction at every
yaw** and can discriminate nothing. Reading it as the outcome would be the same class of
mistake as reading a belt's `state` topic, which republishes the command it was handed: a
signal that discriminates only because it is a software servo's opinion rather than a
measurement.

`grasp_ok` for a trial is therefore ALL of, every one read from the simulator's own pose
feed:

- `lift_m > 0.05` — the part actually left the surface;
- `held_through_transport` — it was still with the pads at release;
- `place_err_m ≤ 0.05` — it arrived where it was sent.

Computed by the published `recompute.metrics` over the saved pose traces, so the three
campaigns' numbers mean the same thing.

## Thresholds — the decision rule

Stated as pass/fail *before* the numbers, so that the conclusion is read off rather than
argued to.

### G — is the block a valid measurement at all?

Checked first. A trial failing any of these is reported as **void**, not as a result.

- **G1 — the part was carried.** `travelled_m ≥ 0.900` in every scored Arm A trial. The
  nominal run is 1.100 m.
- **G2 — the gate has teeth.** The Arm B control must show `travelled_m` below 0.050 m. If
  a part outside the carry list travels anyway, `carried` discriminates nothing and the
  whole of Arm A is void.
- **G3 — a yaw describes the part at all.** `tilt ≤ 5.0°` at the read. A part that has
  tipped onto an edge presents a diagonal, not a face, and is reported in its own bucket
  rather than folded into the yaw distribution.
- **G4 — it is still on the belt.** At the read, `0.450 ≤ x ≤ 1.650` and `|y| ≤ 0.200`.
- **G5 — the independent variable was actually set.** Median
  `|yaw_settled − commanded_yaw| ≤ 2.0°` at every level. If the part does not settle at the
  yaw it was spawned at, the input was not what the trial says it was.
- **G6 — Arm C got a grasp to measure.** `Pick` returns SUCCESS and the arm homed in every
  trial; a trial where the planner found no solution is void, not a failed grasp. Reported
  separately, because "could not reach it" and "could not hold it" are different answers.

### H1 — does a conveyor ride change the yaw?

Per level and pooled, on `Δ = yaw_at_read − yaw_settled`.

- **Preserves** if median `|Δ| ≤ 2.0°` **and** the 95th percentile of `|Δ| ≤ 5.0°`.
- **Narrows** if median `yaw_at_read` is at least 20% below median `yaw_settled` at the
  levels ≥ 10°.
- **Widens** if median `|Δ| > 5.0°`, or if the interquartile spread of `yaw_at_read` at any
  level exceeds that of `yaw_settled` by more than 3.0°.

2.0° is chosen because it is below the 5° flatness tolerance and an order of magnitude
below the 18.7° residual the permission would have to remove; a change that small over a
1.1 m ride is mechanically negligible and cannot rescue a handoff.

Reported with a bootstrap 95% CI on the median of `Δ`, so that a null result states what it
excludes rather than merely failing to reject.

### H2 — is the part still turning when it arrives?

- **Settled** if median `|yaw_rate_at_read| ≤ 1.0 °/s`.
- **Still turning** if `|yaw_rate_at_read| > 1.0 °/s` in more than 25% of trials.

This is registered as a separate outcome because it changes what the answer is *for*. The
pick window on a running belt is 0.667 s (0.100 m from the beam to the belt's end at
0.150 m/s). A part turning at 10 °/s accumulates 6.7° of additional uncertainty inside that
window alone, which would make the arrival yaw a function of gripper arrival time rather
than a property of the part.

### H3 — does stopping the belt change the answer?

The user has taken the decision to index the belt for an unrelated reason. Whether that
changes this answer is pre-registered rather than discovered.

Two comparisons, one paired within trial and one across modes:

- **Paired:** `yaw_at_read` against `yaw_settled_after_stop` on the same trial.
- **Across modes:** the `running` and `indexed` distributions of `yaw_at_read`.

- **Stopping changes it** if the median paired difference exceeds 2.0°, or if the two
  mode distributions differ at permutation `p < 0.01` (two-sided, 100 000 permutations,
  fixed seed — the published `analyse.py` functions, unchanged).
- **No difference** otherwise, reported with the bootstrap CI on the median difference.

### H4 — where does the grasp boundary fall?

`grasp_ok` rate by spawn yaw, with Wilson 95% intervals, and Fisher exact between the 0°
cell and each other level — the same statistics the two published campaigns used.

- **θ_safe** := the largest tested yaw whose Wilson 95% **lower** bound on `grasp_ok` is
  ≥ 0.80.
- **θ_fail** := the smallest tested yaw whose Wilson 95% **upper** bound on `grasp_ok` is
  ≤ 0.50.

Both are reported as the tested levels they are, with the interval, and never interpolated
between levels as though the sweep were continuous.

### H5 — what does the shipped path actually deliver? (Arm D)

- **The grasp residual, as deposited.** Median and maximum `yaw_deposited`, reported
  against ADR-0029's published "up to 18.7°". This campaign does not assume that number;
  it measures its own and says whether the two agree.
- **What arrives.** Median and maximum `yaw_at_read`, and the maximum `presented_at_read_mm`.
- **The ride's contribution**, `Δ = yaw_at_read − yaw_deposited`, against the same
  thresholds as H1: preserved at median `|Δ| ≤ 2.0°`, widened above 5.0°.
- **Does the release leave the part spinning?** `|yaw_rate_deposited| > 1.0 °/s` in more
  than 25% of trials says yes, and if it does, whether that spin has decayed by the read is
  the whole of the widening question.

Arm D is registered as the arm the **verdict is taken from** where it and Arm A disagree,
because it is the only one containing every term the real handoff contains. Arm A's job is
to explain *why* Arm D reads as it does.

### The verdict — combining the arms

Let **θ_arrive** be the upper end of the yaw distribution this campaign measures at the
outfeed, given the input distribution the line actually produces (ADR-0029's residual, up
to 18.7°).

| Condition | Verdict |
|---|---|
| θ_arrive < θ_safe | Conveyor-mediated handoff is **safe on physical grounds**. ADR-0031's permission stands and its justification can be rewritten honestly around this campaign instead of around a detector that does not exist. |
| θ_arrive > θ_fail | **No handoff is safe in Phase 1**, conveyor-mediated or direct. That has to be written down deliberately rather than discovered by a dropped part. |
| otherwise | **Close.** Reported as close, with both intervals, and not resolved by this campaign. |

**"Close" is a permitted outcome and will be reported as one.** A verdict manufactured out
of an overlapping pair of intervals would be worth less than the honest statement that the
two options need choosing between on other grounds.

## Honesty bounds fixed in advance

- This measures the **simulator**, not the cell. Nothing here evidences behaviour on the
  physical xArm. The layout is `PROVISIONAL` and the physical scan is Phase 3 (charter §8).
- Planning is unseeded (ADR-0006) and `CITE_PHYSICS_SEED` reaches nothing (ADR-0027), so
  trials are **not** replicates under a fixed seed. They are independent samples from the
  same configuration, and every rate is a rate over samples, never a determinism claim.
- Every pose is read from **Gazebo's own pose feed, never from TF**, and no belt `state`
  topic is subscribed anywhere in this harness. This is the published harness's design and
  the reason for it is unchanged: TF and the state topic both report what was commanded.
- **Arm C measures the grasp boundary at `table_pick`, not on the belt.** The gripper
  geometry is what is under test and it does not change between stations, but the
  contacting surface does. Both are scene boxes that declare no friction block, so Gazebo's
  defaults apply to both equally — that is the argument, and it is an argument, not a
  measurement. Named here as the campaign's main threat to validity.
- **Arm A measures `conveyor_1` only.** All three belts are the same type at the same
  speed with identical plugin configuration, so the result is expected to transfer; that
  expectation is not tested.
- The campaign measures a part **placed on the belt by the harness**, not one released by a
  gripper. It therefore characterises what the belt does to a yaw, and it does not measure
  what yaw a `Place` deposits. Where the input distribution is needed for the verdict,
  ADR-0029's published residual is used and cited as another campaign's number.
- Real-time factor on this host is well below 1. Wall-clock ceilings are not results, and
  every settling window is reported as the sim-time interval it actually bought.
