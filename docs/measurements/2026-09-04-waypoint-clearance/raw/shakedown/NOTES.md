# The one permitted shakedown — what it proved, what it broke, and what it leaves open

**THIS IS NOT DATA.** [`../../criteria.md`](../../criteria.md) section 10 permits one shakedown
run per stage, published here, **excluded from every figure in section 7**, and it **may not be
used to set or adjust any threshold**. Nothing in this directory may appear in `ANALYSIS.md` as
a figure. No threshold was moved and `criteria.md` was not touched — section 10's own sentence
is that if the shakedown reveals a defect, **the harness is fixed and that file is not**.

- **Taken:** 2026-09-04, on the machine `criteria.md` section 9 names, at `3081d99`.
- **What ran:** `run_cell_block.sh SHAKEDOWN --shakedown --captures BRINGUP` — one capture, not
  three, because a shakedown proves a chain and does not sample anything.
- **What it produced:** one `bringup` run, 94 s; **one** trajectory captured on `arm_1`, 62
  waypoints; I5 logged 1 publication and 1 was received, so rule C-ii's equality held exactly.
  `v1_clean = True` at both ends, the vendor pin held, V2 read 13 hull collision-mesh
  references on all three arms, V3 found `gz_ros2_control/GazeboSimSystem` and neither fixture
  nor mock plugin.
- **The scenario's own verdict was `failed — 1 teardown assertion(s) failed`.** Per
  `criteria.md` section 3 that does not gate a capture: the cycle planned and published, and
  the trajectory is one this cell produced. It is recorded here for completeness and it is not
  a finding of this campaign.

## Four defects, all in the harness, all fixed

**1 — I4 was read before bring-up had applied the planning scene. This is the one that would
have corrupted the campaign.** The scene came back with **zero objects on all three arms**, and
every distance the compute stage produces is a distance to a scene object — so the whole
measurement would have been a measurement against an empty world. It is not a property of the
cell: the block's own log shows `loaded 12 collision object(s) for zone 'cell_a' in cite_world`
for each arm, about **30 s after** `move_group` began answering, and the first `Calling Planner`
line comes later still. The harness read I4 at the instant the door opened, 2–10 s in.
**Worse than losing the block, it would have looked like a validity finding**: V5 discards a
block whose read-back is empty, so a harness reading too early would have discarded every block
for a defect of its own. *Fixed:* I4 is re-read every 5 s while the scene is empty, the **last
non-empty** read travels on the record, and the attempt count and the instant of the first
non-empty read travel with it.

**2 — V14 could never be evaluated.** `cite_bringup.plan.resolve_domain_id` takes
`(plan, side, base)` and the harness called it with `(zone, side)`, so every record carried
`v14_ok: null` and the rule that catches a recorder on the wrong domain — **the failure that
produces a complete, empty, plausible capture** — was structurally inert. *Fixed:* the
generated plan is loaded from the installed share directory and `domain_base(environ)` supplies
the base, so the addition `base + offset` is still written in exactly the one place ADR-0044
clause 4 requires and is not recomputed here.

**3 — the topic-resolution reading could not tell a topic from a publisher.** The header
printed `expected_all_present: true` for all three `display_planned_path` topics **before any
scenario had started**, off a graph holding nothing but the recorder's own three subscriptions.
Harmless to V4, which reads `get_publishers_info_by_topic`, but as a header field it is a claim
that a cell exists when none does. *Fixed:* `publisher_count_by_topic` is recorded beside the
names, with a note saying which of the two means anything.

**4 — V4's door reading is a snapshot of a graph mid-discovery.** `arm_1` matched at 2.4 s with
**one** publisher; `arm_2` and `arm_3` matched at 5.8 s with **three** — against section 2.1's
registered expectation of **two** per arm, one per pipeline. The three endpoints are one
`move_group` each time, two `VOLATILE` and one `TRANSIENT_LOCAL`. Whether the settled count is
two, three, or time-dependent is **not established here and is not this shakedown's business**;
what was wrong is that the harness recorded only the first-match instant. *Fixed:* a **settled**
reading is taken at the end of every capture and travels alongside the first-match one. Neither
replaces the other, and V4 is stated over the settled count with the first-match count beside
it.

## One more class of defect, found before the shakedown and recorded with it

Running `analyse.py` against an **empty** directory made five verdicts read reassuringly where
nothing had been measured: `FLIP1 = NONE`, `VALID1 = CONSISTENT`, `REFUSE1 = 0`, and `DELTA1`,
`MARGIN1`, `STEP1` and `TUNNEL1` all `NOT ADMISSIBLE` — which claims rule C's loss ceiling
fired, when in truth nothing had been captured at all. **A reassuring answer produced by
evaluating nothing is the exact failure `criteria.md` section 7.1 exists to prevent.** All
seven now return `NOT EVALUABLE`, which is a **third state** and is not `did not fire`. No
threshold moved; the verdict enumerations are `criteria.md`'s own and none gained or lost a
member.

## What the shakedown proved, end to end

| Link in the chain | Evidence |
|---|---|
| cell up, three arms | the domain guard passed, the launch came up, three `move_group` nodes answered |
| the door opened | matched publishers on all three arms within 6 s of a 240 s ceiling |
| a trajectory was captured | one `DisplayTrajectory` on `arm_1`, 62 waypoints, all 15 model joints supplied between the message and `trajectory_start` |
| provenance travels on the record | `v1_clean`, V2, V3, V4, V12, V13, V14 all present on the row; the block sealed at the end |
| both mesh sets load and agree where they must | 13 collision links; **9,992** hull triangles against **98,552** vendor; worst AABB-corner residual **0.0 m** and worst origin-radius residual **0.0 m** — section 2.3's property, verified rather than assumed |
| forward kinematics | 62 waypoints placed, all six gripper links carried by the `<mimic>` coupling |
| distances under both sets | 50 of 156 pairs evaluated, 106 censored by rule M |
| the standing pair behaves as section 2.2.1 registers | `(arm_1_link_base, pedestal_1)` penetrating at **all 62** waypoints under **both** sets, reported as its own row and in no aggregate |
| containment holds | the largest `d_hull − d_vendor` over every evaluated triple was **−1.1e-16 m**, far inside `DIFF_FLOOR`; rule E did not fire |
| V5 | scene agreement **exact at 0.0 m** under the registered accounting — the generated static transform's own yaw, not `pi/2` |
| the analyser prints | every registered rule printed, on the shakedown and on an empty directory |

**The distance half of that table was produced by
`compute.py --diagnostic-scene-from-generated-file`, which is NOT a campaign path**, because
defect 1 left the read-back empty and section 10 grants no second capture shakedown. It is
labelled NOT DATA at every step, writes `SHAKEDOWN_diagnostic.json`, and `analyse.py` does not
read that file. It exists so that the distance computation does not ship unexercised.

## What it leaves open — the residual this rig carries into its first block

1. **The committed harness is not the harness that ran.** Four fixes landed after the one
   permitted capture shakedown and **none of them is exercised**: the I4 re-read, the V14
   resolver, the settled publisher reading and the topic note. **This is the largest risk this
   rig carries**, and the first campaign block is where it is discovered. The fix most likely to
   matter is defect 1's, and its failure mode is loud rather than silent — an empty read-back
   discards the block under V5 and `analyse.py` reports it.
2. **Only `BRINGUP` was captured.** `PICKPLACE` and `LINE` have never been driven through this
   harness. `LINE` is the longest and most varied capture and it starts three arms; nothing
   here evidences that the recorder attributes its trajectories correctly across three arms at
   once, and nothing evidences the wall clock of a `LINE` compute.
3. **The compute stage's wall clock is measured on one 62-waypoint trajectory** — 76 s, about
   1.2 s per waypoint. A `LINE` capture is a different order of magnitude and the campaign's
   total should be budgeted in hours, not minutes.
4. **REPRO1 has never been evaluated.** The three-run protocol has not been executed; the
   analyser reports it `NOT EVALUABLE`, which is the honest third state and not a pass.
5. **The one captured trajectory's maximum tool step was 0.0192 m.** That number is **not
   data**, may not be compared against `STEP_MID`, and may not be read as evidence for or
   against PRED4. It is recorded here only because a reader of this directory will see it in
   the JSON and should know it has been noticed and refused.
