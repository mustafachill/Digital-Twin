# ADR-0032: Index the belt — stop it on the trigger that starts a station, restart it on `CompleteHandoff`

- **Status:** Accepted (corrected 2026-08-26) — **the decision stands and is now
  implemented.** L4 owns the belt setpoint, stops the belt on the `DetectionEvent`
  transition and restarts it on `CompleteHandoff`. What is corrected is one *consequence*:
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

- `model/assets/instances/sensors.yaml` places each outfeed beam at `xyz_m: [-0.050, 0.250,
  0.030]` in its belt's `outfeed` frame — **0.050 m upstream of the pick point**.
- `model/assets/types/conveyors/belt_1200x400.yaml` makes the belt **1.200 m** long and
  insets `outfeed` **0.050 m** from its end, so the pick point is 0.050 m short of the
  geometry and the beam is **0.100 m** short of it.
- `workspace/src/cite_generated/worlds/cell_a.sdf` gives the plugin
  `<belt_length_m>1.2</belt_length_m>`, and `conveyor.cpp` builds the carry volume as a box
  of that full length centred on `<surface_pose>`. The carry volume therefore ends at the
  belt's geometric end, 0.100 m past the beam.
- `model/assets/instances/conveyors.yaml` declares `installed_speed_mps: 0.150` on all
  three drives.

So a work-piece crosses the beam **0.333 s** before it reaches the pick point and leaves the
carry volume **0.667 s** after crossing it. Against that, the pick-and-place cycle measured
on the development host is **106 to 119 s**.

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
