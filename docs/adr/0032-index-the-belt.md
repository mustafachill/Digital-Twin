# ADR-0032: Index the belt — stop it on the trigger that starts a station, restart it on `CompleteHandoff`

- **Status:** Accepted (corrected 2026-08-26 and 2026-08-27) — **the decision stands and is
  implemented.** L4 owns the belt setpoint, stops the belt on the `DetectionEvent`
  transition and restarts it on `CompleteHandoff`.
  **The 2026-08-27 correction is the one to read first.** L4 owned the setpoint from
  2026-08-26 and *delivered* it to nobody: `run_all()`'s message reached zero matched
  subscribers and a test harness was starting the belts instead. See the section
  "Correction — 2026-08-27: the setpoint had an owner and no delivery, and a harness was
  covering for it", immediately after this block. It also withdraws two figures the
  2026-08-26 correction declared unaffected, and retires a consequence that said nothing
  asserted this decision.
  The 2026-08-26 correction stands as written. What it corrected is one *consequence*:
  "the piece is stationary at the pick point" was false as written, and the piece parked
  short of it. See the section "Correction — 2026-08-26: the piece stopped short of the pick
  point, and the beam is why", immediately after this block. The **open question** left in
  *What we will have to revisit* — restart at `CompleteHandoff` or at `PickAt` — is
  **closed** in favour of `CompleteHandoff`; the update on that bullet gives the reasoning.
  **The original status text follows, unchanged**, because it was true when written and the
  order it records is part of the record: *Accepted — **decided, not yet implemented.**
  Nothing in the running system commands a conveyor at this commit, and this record is the
  decision rather than a description of one. It is the first record on this branch written
  in the order charter
  §12 asks for; [ADR-0030](0030-facility-model-describes-the-workpiece.md) and
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md) were both written
  after their implementations and say so on their face. Stated because P7 makes the order
  part of the record, not a detail of it.*
- **Date:** 2026-08-26
- **Deciders:** Project owner
- **Related:** [ADR-0003](0003-gazebo-harmonic.md) (why the conveyor plugin is ours),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0024](0024-handoff-split-between-l3-and-l4.md) (whose four protocol leaves this
  keys on), [ADR-0027](0027-pilz-planning-pipeline.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md) (untouched by
  this, and itself unresolved — see the costs below; **as of 2026-08-26 it is resolved and
  corrected**, and the update in that cost bullet says how),
  [L1](../architecture/L1-description-and-assets.md),
  [L4](../architecture/L4-orchestration.md), charter §4 (P2, P4, P8)

## Correction — 2026-08-27: the setpoint had an owner and no delivery, and a harness was covering for it

**Two corrections now sit on this record. The newest is placed first**, so that a reader
meets the most recent state before the older one; the 2026-08-26 correction follows
unchanged. The convention is recorded in [`README.md`](README.md).

The decision is unchanged, again: a belt still stops on a `DetectionEvent` transition and
still restarts on `CompleteHandoff`. What is corrected here is the **claim that giving the
setpoint an owner had given it a writer**, and two figures the earlier correction said its
own change did not touch.

### 1. The owner published, and nothing received it

> **The belt setpoint gets an owner at L4**, closing the gap
> `tests/scenarios/continuous_line.py::_start_the_belts` currently reports. A scenario stops
> supplying a value the running system does not have.

The owner landed. The delivery did not, and for the ten commits that followed, this record
said the gap was closed while the belts were still being started by the scenario.

`ConveyorIndex` creates its publishers inside `line_orchestrator`'s topology callback and
`run_all()` publishes from that same callback, a tree construction later. **Reliable QoS is
a promise to subscribers a publisher has already been *matched* with**, and matching is a
discovery event that has not happened at that instant, so the message is delivered to
nobody — however long the bridge has been up, and however reliable the profile. Reliability
does not buy delivery to a subscriber that does not yet exist to the publisher; it buys
retransmission to one that does.

**What was measured, and by whom.** With the scenario's own publisher removed, a subscriber
that had been up for a hundred seconds received nothing for the following three hundred.
That is the fixing agent's measurement on one machine on 2026-08-27, reported here once. It
is not a campaign and no thresholds were registered in advance. What settles it is already
in the tree as an assertion rather than a number: `test_conveyor_index.cpp` orders its two
delivery cases the way production runs — index, command, subscribe — and both fail without
the fix.

So the belts in every `continuous_line` run before 2026-08-27 were started by
`_start_the_belts`, a harness publishing the same setpoint ten times over a second. **The
redundant writer this ADR asked to remove was the only writer that worked.** The task that
found it was the removal of that redundancy as a two-writer hazard; the hazard was real and
so was the dependency.

**The fix is an event, not a retry (P4).** A subscriber matching is treated as what it is —
an event — and the belt's *current* commanded setpoint is sent then, so a bridge that
restarts mid-run learns where the belt is rather than where it started. `run_all()`'s
immediate publish is kept, so an RMW that does not deliver the matched event degrades to
the previous behaviour rather than to something worse. Nothing waits for a duration.

### 2. `_start_the_belts` no longer exists

Both places this record names it are stale. `tests/scenarios/continuous_line.py` now
**reads** the command topics and asserts a non-zero setpoint equal to each drive's
`installed_speed_mps`, so the absence of `run_all()` is a scenario failure rather than an
invisible one. The gap this ADR described is genuinely closed as of 2026-08-27 — one day and
ten commits after this record said it was.

One reference is deliberately left uncorrected:
`docs/measurements/2026-08-26-conveyor-yaw-transfer/harness/belt_yaw.py` cites the function
in a docstring. A published campaign's `harness/` is the code that produced its `raw/`, and
editing it makes it no longer that. It is annotated in that campaign's `ANALYSIS.md`
instead.

### 3. The window arithmetic was beam-derived after all

The 2026-08-26 correction added this note to the Context:

> The window arithmetic is unaffected: the transit times below come from the belt's length
> and speed, not from where the beam sits.

That is wrong, and it is wrong about the very numbers it was protecting. Both come from
where the beam sits:

- **0.333 s before the pick point** is 0.050 m (the old upstream mounting) ÷ 0.150 m/s.
- **0.667 s to leave the carry volume** is 0.100 m (that mounting to the belt's geometric
  end) ÷ 0.150 m/s.

Recomputed from the generated artifacts at this commit — `cell_a_static_tf.yaml` puts
`cell_a__beam_c1_out__beam` at x = 1.627 and `cell_a__conveyor_1__outfeed` at x = 1.600;
`cell_a.sdf` gives `conveyor_1` a `surface_pose` at x = 1.05 with `belt_length_m` 1.2, so
the carry volume spans x ∈ [0.45, 1.65] and `conveyor.cpp` tests the model's **origin**
against it:

- A part breaks the beam's upstream face when its own centre is on x = 1.600. **The margin
  before the pick point is 0 s, not 0.333 s** — the instant of the edge *is* the instant the
  part is where it is wanted. That is not a regression; it is what deriving the stand-off
  from the part was for, and `conveyor_index.hpp` states it as "there is no travel time to
  spend".
- The origin leaves the carry volume after 0.050 m of further travel: **0.333 s, not
  0.667 s.**

The argument the figures served is untouched and is strengthened. Sub-second against a 106
to 119 s cycle was already two orders of magnitude short; zero seconds is shorter. Option A
— buy time by moving the beam — is refuted by the belt's length regardless of either
number.

### 4. "Nothing asserts any of this yet" is retired

That consequence was true when written and is not now. `test_conveyor_index.cpp` drives real
`DetectionEvent` messages through real topics and asserts which edge stops which belt, that
a level is not an edge, that the opposite edge does not stop it, that a belt feeding no
actor is never stopped, and that the speed coming back out is the model's; `continuous_line`
asserts that every declared belt is commanded to its installed speed by L4 and by nothing
else. **The narrower half of that bullet still holds**: no *scenario* checks that a belt
stops on a trigger or restarts on a handoff. The scenario checks the start only.

### What survives

The decision, entirely, and every cost below it. Indexing still touches timing and not
orientation; the belt is still commanded open-loop with nothing publishing `ConveyorState`;
`buffer_capacity` still means capacity rather than concurrency on an indexed edge. Nothing
in the corrections above changes which belt stops, when, or why.

### How the error survived

**A publisher with no subscriber fails silently and looks identical to one with nothing to
say.** ADR-0032 reasoned about ownership — who decides the setpoint — and treated delivery
as plumbing already proven, in a bullet that said so in as many words: "What was missing was
the decision, not the plumbing." The plumbing was missing too, in the one place a decision
record does not look.

It survived a second layer as well. The scenario that would have caught it was *also* the
thing compensating for it, so removing the compensation and asserting the behaviour had to
happen in the same change or neither would have shown anything. **A test that supplies a
value the system under test is supposed to supply cannot report that the system does not.**
When a harness fills a gap, the record of that gap has to name the harness — this one did —
*and* the closing change has to delete the harness's version in the same commit that adds
the system's. Here they were ten commits apart on this branch, and the interval read as working.

The third error is smaller and the same shape: a correction that moved a geometric constant
asserted, without recomputing, that the arithmetic downstream of it was independent. Two
divisions would have shown otherwise. **A correction is not exempt from being checked.**

## Correction — 2026-08-26: the piece stopped short of the pick point, and the beam is why

The decision is unchanged: the belt still stops on a `DetectionEvent` transition and still
restarts on `CompleteHandoff`. What is corrected is a **consequence written before the
implementation existed** — a prediction about where the piece would come to rest.

### What was written

> The pick window stops being a race. The piece is stationary **at the pick point** for as
> long as the station needs.

### What was true when it was implemented

The stopping worked and the position did not. With indexing in place the piece was held
motionless on the belt at pick height — the beam stayed blocked for hundreds of seconds
against under one second before, and the furthest and last samples were identical, so it did
not creep. But it stopped **0.069 m short** of `conveyor_1/outfeed`, at x = 1.531 against a
pick point at x = 1.600, on four runs out of four, and `arm_2` closed on air: `commanded
45.0 mm, reached 46.0 mm, stalled=false`. `continuous_line` stopped at milestone 4 of 10.

The cause was not in this decision. It was in the sensor the decision keys on. The break-beam
plugin tested the work-piece's **model origin** against a box, so `blocked` first fired with
the cube's *centre* short of the beam plane rather than with its *leading edge* at it — a
part-centre window, not a light beam. The same defect had already been recorded from the
other direction, as a beam that misses a part taller than 100 mm or shorter than 20 mm.
They were one bug.

**[Unverified in this record.]** The 0.069 m, the x = 1.531, the four-run count and the
`Pick` message are reported from the implementing agent's runs and are **not** a published
campaign. They are stated once, here. What would settle them is a campaign directory under
[`../measurements/`](../measurements/README.md) with thresholds written before the trials.
The frame coordinates are read from the model and need no campaign.

### What is true now

The beam intersects the segment with the part's real collision shapes, read from the
simulator, and an indexing beam's **stand-off is derived rather than authored**: it is
mounted with its upstream face on the leading-edge plane of a correctly parked part, half a
part length plus half a beam width downstream of the point the part must stop on. For
`beam_c1_out` that moves the beam frame from x = 1.550 to **x = 1.627** — `conveyor_1/outfeed`
at 1.600 plus a derived 0.027 m — so a part whose leading edge breaks the beam comes to rest
with its centre on the outfeed frame. `model/assets/instances/sensors.yaml` now carries a
**zero** along-belt component for every indexing beam and `cite_tools.validate.geometric`
refuses a non-zero one, so a fitted constant cannot come back. The reasoning, the options and
what it costs are in [ADR-0033](0033-derive-the-index-standoff-from-the-workpiece.md).

Fixing the extents test did **not** by itself fix where the part parked, and the record
should say so: a leading-edge break stops the part *earlier*, so at the old mounting the
shortfall would have grown from 0.069 m to about 0.077 m. Getting the physics right created
the need for the derivation rather than removing it.

### What survives

All of it. Both ends of the decision remain events, nothing sleeps, the setpoint still has
its owner at L4, and every cost listed below still holds — including that this touches timing
and not orientation. The corrected sentence is a *prediction about geometry* made in a record
about *control*, and it is the only thing withdrawn.

### How the error survived

It was written as a consequence of the decision when it was in fact a consequence of the
sensor. "Stationary at the pick point" bundles two claims — that the piece stops, and that it
stops *there* — and the ADR only reasoned about the first. The second silently depended on
the break-beam plugin reporting a part where a photo-eye would, which nothing in this
repository asserted and which was already known to be false in the vertical axis. **A record
written before implementation is allowed to predict; it is not allowed to predict in the same
sentence that it decides**, because a reader cannot then tell which half was weighed.

## Context

The line in `cell_a` is sensor-driven by construction: a station acts because a beam
reported a work-piece, never because a duration elapsed. `AwaitTrigger` waits on a typed
`DetectionEvent` stream — the message carries `state` and `previous_state` so a consumer
reads a transition rather than a level — and the station that the trigger starts then picks
from a frame on the belt that beam watches.

**A station cannot pick from a running belt, and the window is arithmetic on the L0 model
rather than an estimate.** Every figure below is resolved from `model/` at this commit:
**[Note 2026-08-26 — the beam placements below are no longer what the model says. An
indexing beam's along-belt offset is now zero in `sensors.yaml` and its stand-off is derived;
see the Correction section above and ADR-0033. The window arithmetic is unaffected: the
transit times below come from the belt's length and speed, not from where the beam sits.]**
**[Corrected 2026-08-27 — see the Correction section "the setpoint had an owner and no
delivery, and a harness was covering for it" above. The last sentence of the note is false:
both transit times below are derived from where the beam sits. They are 0 s and 0.333 s at
this commit, not 0.333 s and 0.667 s.]**

- `model/assets/instances/sensors.yaml` places each outfeed beam at `xyz_m: [-0.050, 0.250,
  0.030]` in its belt's `outfeed` frame — **0.050 m upstream of the pick point**.
  **[Corrected 2026-08-26 — see the Correction sections above. The along-belt component is
  `0.000` and the beam frame resolves to x = 1.627, which is 0.027 m *downstream* of the
  pick point at x = 1.600 and derived from the work-piece rather than authored.]**
- `model/assets/types/conveyors/belt_1200x400.yaml` makes the belt **1.200 m** long and
  insets `outfeed` **0.050 m** from its end, so the pick point is 0.050 m short of the
  geometry and the beam is **0.100 m** short of it.
  **[Corrected 2026-08-27 — the belt length and the outfeed inset stand. The beam is not
  0.100 m short of the belt's end; it is 0.023 m short of it, at x = 1.627 against a carry
  volume ending at x = 1.650.]**
- `workspace/src/cite_generated/worlds/cell_a.sdf` gives the plugin
  `<belt_length_m>1.2</belt_length_m>`, and `conveyor.cpp` builds the carry volume as a box
  of that full length centred on `<surface_pose>`. The carry volume therefore ends at the
  belt's geometric end, 0.100 m past the beam.
  **[Corrected 2026-08-27 — the carry volume still ends at the belt's geometric end,
  x = 1.650. It is 0.023 m past the beam, not 0.100 m.]**
- `model/assets/instances/conveyors.yaml` declares `installed_speed_mps: 0.150` on all
  three drives.

So a work-piece crosses the beam **0.333 s** before it reaches the pick point and leaves the
carry volume **0.667 s** after crossing it. Against that, the pick-and-place cycle measured
on the development host is **106 to 119 s**.
**[Corrected 2026-08-27 — see the 2026-08-27 Correction section above. Both times are
withdrawn. A part now breaks the beam at the instant its centre is on the pick point, so the
margin is **0 s**, and it leaves the carry volume **0.333 s** later. The cycle range stands
and so does the conclusion: the window was already two orders of magnitude too short.]**

**It was observed failing, not inferred to fail.** In four consecutive `continuous_line`
runs the piece rode off the end before `arm_2` arrived and came to rest on the floor at
`(1.912, 0.028, 0.025)` — 0.262 m beyond `conveyor_1`'s end at x = 1.650, at the resting
height of a 50 mm cube — and `Pick` reported `nothing was picked up: commanded 45.0 mm,
reached 46.0 mm, stalled=false`, which is a gripper closing on air.

**[Unverified in this record.]** The 106–119 s cycle range, the four-run count, the resting
coordinate and the `Pick` message are reported from those runs and are **not** a published
campaign: `docs/measurements/` holds two campaigns at this commit and neither is this one.
They are stated once, here, and not repeated below. What settles them is a campaign
directory under `docs/measurements/` with its thresholds written before the trials, per the
rules in [`../measurements/README.md`](../measurements/README.md). The geometric figures
above need no campaign — they are read from the model.

**Nothing owns the belt setpoint today.** `line_orchestrator` plans, arbitrates, tracks
custody and calls skills, and commands no belt; `model/assets/instances/conveyors.yaml`
says in as many words that the runtime setpoint is L4's decision and does not belong in the
model. The gap is currently filled by the test:
`tests/scenarios/continuous_line.py::_start_the_belts` publishes one constant per belt for
the whole run and documents itself as a gap rather than a boundary. So the decision below is
not only about timing; it gives the setpoint an owner.
**[Corrected 2026-08-27 — see the 2026-08-27 Correction section above. This was true when
written and stayed true for the ten commits between this decision being implemented and 2026-08-27, which is the
part worth knowing. `_start_the_belts` no longer exists: the scenario reads the command
topics and asserts that L4 commanded every belt to its installed speed.]**

**The decision is forced now** because the sensor-driven three-arm line is the Phase 1.D
claim, and the belt is the only thing between a station's trigger and its pick.

## Options considered

### Option A — Move the beam, or otherwise buy time with geometry
Place the trigger further upstream so the station has longer to arrive.

Rejected on the belt's own dimensions. The **whole** belt is 1.200 m at 0.150 m/s = **8 s**
of transit. There is no placement of a beam on a 1.2 m belt that yields a 100 s window; the
same window would need a belt roughly 7.5× slower or roughly 60 m long. Neither is a
facility this cell can be.

### Option B — An accumulating end stop
Let pieces queue against a physical stop at the outfeed and slip under a still-running belt,
which is what a real accumulating conveyor does.

Rejected because the simulator cannot represent it and the fix that would make it appear to
work is prohibited.

- `belt_1200x400` declares **one box body and no rail**: its `description.body` is a single
  `box` of `1.200 x 0.400 x 0.600`, visual and collision alike. There is nothing for a piece
  to rest against, and adding one is L0 work that would change the collision geometry every
  arm plans around.
- `conveyor.cpp` carries a piece by writing a `LinearVelocityCmd` on the carried model's
  canonical link **every step**, for as long as the model's origin is inside the carry
  volume. A commanded velocity is not a driving force: a piece pressed against a stop would
  still be commanded forward at belt speed rather than resting on it. The plugin's own
  header states the boundary — transport there is kinematic, not frictional, and "no claim
  about belt handling, accumulation pressure or singulation can rest on this plugin".
- A stop that existed only in simulation, or a plugin special case that held pieces the
  hardware would not hold, breaks **P2** outright. That is the highest-severity defect
  class in this project and not available as a workaround.

### Option C — Make the cycle fast enough to fit the window
Take the speed-ups already decided or proposed: Pilz point-to-point planning
([ADR-0027](0027-pilz-planning-pipeline.md)), convex-hull collision meshes
([ADR-0028](0028-convex-hull-collision-meshes.md)), and a better real-time factor than the
0.14 the development host manages.

Rejected as a *solution*, kept as improvements. The gap between a sub-second window and a
100 s cycle is a factor of roughly 160. Every one of these makes indexing cheaper; none of
them, alone or together, closes a two-order-of-magnitude window.

### Option D — Index the belt. Chosen.

## Decision

**A belt stops when the station it feeds is triggered, and restarts when that station
reports `CompleteHandoff`.**

The belt in question is derived from the topology, not named: it is the `via_asset_id` of
the inbound edge of a station **that has a robot actor**, which is the same derivation
`line_orchestrator` already uses to build a station's subtree. The actor condition is
load-bearing. `station_accumulation` is a sink with a trigger (`beam_c3_out`) and no actor,
so it has no `CompleteHandoff` to restart on; a rule that keyed on the trigger alone would
stop `conveyor_3` for ever. Under this rule `conveyor_1` and `conveyor_2` index and
`conveyor_3` runs continuously.

Both ends are events: a `DetectionEvent` transition in, an
[ADR-0024](0024-handoff-split-between-l3-and-l4.md) protocol leaf out. Nothing sleeps and
nothing guesses a duration, so **P4** holds. A physical belt driven by a VFD stops and
starts on the same two events with the same commands, so **P2** holds and the hardware path
needs no second mechanism.

## Consequences

### What this gets us
- The pick window stops being a race. The piece is stationary at the pick point for as long
  as the station needs, which is what makes a ~110 s cycle compatible with a 1.2 m belt.
  **[Corrected 2026-08-26 — see the Correction section above. The piece stopped; it stopped
  0.069 m short of the pick point. It parks on the pick point only since the break beam
  began testing the part's body and the index stand-off was derived from it.]**
- **The belt setpoint gets an owner at L4**, closing the gap
  `tests/scenarios/continuous_line.py::_start_the_belts` currently reports. A scenario stops
  supplying a value the running system does not have.
  **[Corrected 2026-08-27 — see the 2026-08-27 Correction section above. The owner arrived;
  the delivery did not. `run_all()` published to zero matched subscribers, so the scenario
  went on being the only thing that started a belt until the matched-subscriber event was
  added. The gap closed on 2026-08-27, not on 2026-08-26.]**
- **No new interface, and no new value in a second place.**
  `cite_generated/bringup/cell_a_plan.yaml` already carries `command_topic`, `state_topic`
  and `installed_speed_mps` per conveyor, all resolved from L0;
  `simulation.launch.py::_bridge_topics` already bridges the command ROS→Gazebo and the
  state Gazebo→ROS; and `_line_parameters` already passes per-asset names to
  `line_orchestrator` as parallel arrays, which is the shape the conveyor names would use.
  What was missing was the decision, not the plumbing.
- The rule is one predicate over the topology, so it is uniform across stations and there is
  no per-belt special case to keep in step.

### What this costs us
- **The line becomes an *indexed* line, not a continuous one.** Throughput falls to one
  cycle per station per piece. That is a change in what this cell *is*, not a tuning
  parameter.
- **`buffer_capacity` changes meaning, and it is an L0 concept.** `StationEdge.buffer_capacity`
  is documented as "how many this link may hold before the upstream station must wait", and
  `model/topology/flow.yaml` declares `buffer: 4` on both belt-mediated edges. A stopped
  belt stops **every** piece on it, so the effective concurrency of an indexed edge is
  **1**, whatever the edge declares. The declared number remains a true statement of how
  many pieces the link could physically hold; it stops being a statement of how many can be
  in flight. **A reader of `model/topology/flow.yaml` will otherwise take `4` at face
  value.** The accumulation edge's `buffer: 12` is unaffected, because `conveyor_3` does not
  index.
- **A belt that is stopped for most of every cycle is a poor model of a conveyor.** This
  compounds a fidelity limit already recorded in `conveyor.cpp`: transport there is
  kinematic. No claim about belt handling, singulation or accumulation can be taken from
  this line, and indexing moves it further from one that could support such a claim.
- **The belt is now on the line's critical path.** A belt that fails to stop, or fails to
  restart, is a stalled line rather than a slow one, and `ConveyorState` — which exists in
  `cite_interfaces` to make commanded and measured speed disagree visibly — is published by
  nothing at this commit. The bridge carries a bare `std_msgs/Float64` in each direction.
- **This touches timing and nothing else. It does not touch orientation, and it does not
  rescue [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md).** ADR-0031
  *refused* direct arm-to-arm handoff and *permitted* conveyor-mediated handoff, on the
  ground that the receiving station re-observes the piece with `Detect`, "whose
  `Detection.pose` is a full pose", so the yaw uncertainty is measured away. **That
  justification does not hold at this commit.** The only pose sensor in the model is a
  through beam; `cite_skills/src/detection_server.cpp` now leaves `Detection.pose` unset —
  empty `frame_id`, NaN position — and says on the SUCCESS path that a through-beam "reports
  nothing at all about how the work-piece is turned" (commit `ca59e97`). Nor does the belt
  re-seat the piece: one box body, no rail, and a `LinearVelocityCmd` written to the
  canonical link is pure translation, so a piece's yaw arrives as it left. The residual
  rotation is the one measured in
  [`../measurements/2026-08-25-grasp-plane-offset/`](../measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md);
  the figure is not restated here (P1). A measurement to settle whether ADR-0031's
  permission survives is **reported as running and is not in the tree at this commit**
  — *[unverified]*. Indexing solves timing. **A reader must not come away thinking it
  solves orientation.**
  **[Update 2026-08-26 — that campaign has since landed, at
  [`../measurements/2026-08-26-conveyor-yaw-transfer/`](../measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md),
  and the `[unverified]` marker above is resolved rather than corrected. Every claim in this
  bullet is upheld: nothing re-observes the part, and the belt transfers a yaw unchanged.
  ADR-0031's permission survives on a different ground — the receiving gripper — and its
  record is corrected accordingly. This bullet's warning is also now measured directly:
  paired within trial, the median difference between a yaw read in motion and one read after
  the belt stops is 0.0000° at permutation p = 0.7417. **Indexing changes the orientation
  answer by nothing.**]**
- **Nothing asserts any of this yet.** No scenario checks that a belt stops on a trigger or
  restarts on a handoff, and until one does, this decision is a decision and not a
  capability (P6, P7).
  **[Corrected 2026-08-27 — see the 2026-08-27 Correction section above. The first sentence
  is retired: `test_conveyor_index.cpp` asserts which edge stops which belt, and which belt
  is left running, through real topics. The second sentence still holds — the scenario
  asserts only that the belts were *started*, and no scenario asserts the stop or the
  restart.]**

### What we will have to revisit
- **If accumulation becomes representable** — an L0 rail plus a plugin that carries by
  friction rather than by commanded velocity — reopen this. That, and only that, is what
  would restore `buffer_capacity`'s meaning as concurrency rather than as capacity.
- **If the cycle time falls by two orders of magnitude**, from ADR-0027, ADR-0028 and a
  better real-time factor together, the window arithmetic in the Context should be redone
  against the measured cycle rather than assumed still to hold. A partial improvement does
  not lift this; a 160× one would.
- **Whether the restart belongs at `CompleteHandoff` or earlier.** The piece is off the
  inbound belt as soon as `PickAt` succeeds, and `line_station.xml` already releases the
  inbound buffer claim at that point for exactly that reason. Restarting there would recover
  most of the lost throughput. It was not chosen here and it was not weighed here; it is an
  open question, not a rejected option.
  **[Closed 2026-08-26, in favour of `CompleteHandoff`.** Three reasons, none of them
  throughput. **First**, releasing the inbound buffer claim at `PickAt` is *slot
  bookkeeping* — it says a slot is free — and not a statement about motion; reading it as
  permission to move a belt reads one concept as another. **Second**, the throughput it
  would recover is not there to recover: an indexed edge's effective concurrency is **1**
  whatever the edge declares, which is the cost bullet above, so restarting earlier admits
  no second piece to the belt sooner. **Third**, `CompleteHandoff` is the first point at
  which the station is accountable for **nothing** on that belt; before it, a failure path
  can still leave a piece there, and a belt running under a piece a failed station has not
  taken puts that piece on the floor. `line_station.xml` places `ResumeBelt` immediately
  after `CompleteHandoff` and deliberately not in the recovery branch. This closes the
  question rather than measuring it: **no scenario compares the two placements**, and the
  throughput each would give is unmeasured.]**
- **Whether the physical belts can be indexed at all.** That they are VFD-driven and can be
  started and stopped on command is the assumption **P2** rests on for this decision, and it
  is *[unverified]* — no drive on the physical line has been inspected. The layout is
  `PROVISIONAL` and the physical survey is Phase 3 (charter §8). If a physical belt turns
  out to be a fixed-speed drive, this decision does not transfer and the sim and hardware
  paths would diverge, which is the defect this ADR claims to avoid.
