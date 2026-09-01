# ADR-0045: Measure the gripper deadline in the clock the gripper runs on, and declare it in L0

- **Status:** Proposed, corrected 2026-08-30 — see the **Correction — 2026-08-30** section
  below. **Every decision stands**; what was false is a consequence describing the cancel as an
  outcome rather than as a send, and what was missing is that a served cancel removes the grip
  force with unmeasured consequences for the part. Written before the implementation, which is
  what
  [CLAUDE.md §12](../../CLAUDE.md) asks for. **Nothing in this record was built at `b8a6c10`**;
  every "will" below was a commitment and not a description.
  **Decisions 1 to 6 are implemented on branch `feat/close-the-gripper-deadline-dead-end`,
  which is under review and not merged.** The status stays `Proposed` for that reason and for
  a second one this record is unusually clear about: its own verification table ends by saying
  that what would show the fix works is a `continuous_line` run on a CI runner in which the
  gripper fails to answer, **and that a run in which it answers quickly shows nothing at all**.
  No such run exists. What the branch adds is evidence of the MECHANISM, not of the outcome:
  `cite_bringup/test/test_gripper_deadline_launch.py` holds simulated time still while several
  times the deadline passes in wall time and requires the wait to survive it, then advances
  simulated time past the declared value and requires the wait to end, the goal to be
  cancelled, and the report to say custody is unestablished. That test fails against the code
  this record replaces. It does not make the record `Accepted`.
  **One thing named here as owed its own record still has none:** the
  `cite_skills::gripper_is_holding` margin defect in the last section below is untouched by
  the branch, exactly as decision 5's neighbouring paragraph asks.
  **[Overtaken 2026-09-01 — the sentence above is kept as written and is no longer true of
  the tree.]** That record is
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), `Proposed`, and it
  **chooses nothing**: it states the defect as a band, weighs six options and leaves the
  choice to the project owner. It reproduces this record's arithmetic exactly and adds two
  things this record did not have — the 46.6 mm example describes a *declared work-piece*,
  which `default-grasp-width-never-closes` already refuses at validate time, and the defect
  has never been observed firing in any run anyone has looked at. **The defect itself is
  still untouched**, and the clause above stays true of this record's own branch.
- **Date:** 2026-08-29
- **Deciders:** Docs-writer agent, from the project owner's root-cause investigation of the
  three `continuous_line` CI cycle failures recorded in [CLAUDE.md §2](../../CLAUDE.md)
- **Related:** [ADR-0022](0022-gripper-as-ros2-control-controller.md) (**its evidence path is
  a constraint on this record, not a subject of it**),
  [ADR-0029](0029-simulated-grasping-by-friction.md),
  [ADR-0036](0036-execution-side-trajectory-tolerances.md),
  [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) (**the L4 half of the
  same failure; this record ends at the L3 boundary**),
  [L2](../architecture/L2-control-and-hal.md), [L3](../architecture/L3-capabilities.md),
  charter §4 (P1, P2, P4, P5, P7)

## Correction — 2026-08-30: the cancel is a send, not an outcome, and the grip force is what it costs

**Every decision stands.** The deadline is still measured in the node's clock, still declared
in L0, still narrowed to "the controller has not terminated this goal", and the goal is still
cancelled on expiry. What was wrong is how this record described that cancel, and what was
missing is what a served cancel does to the part.

### The false claim

The first consequences list says: *"A controller goal that is given up on is also cancelled,
so the gripper stops being commanded by a goal nobody holds."* That states an outcome, and the
implementation can only state an act.

`async_cancel_goal` is **sent and deliberately not awaited** — on the one path where the
controller is by definition not answering — so **two things can happen and neither is
observed**:

- **It is never served.** The goal stays live and the controller goes on commanding the closed
  position at the configured effort, which is exactly the condition the bullet claims to have
  removed.
- **It is served too late to do anything.** `check_for_success` ends a goal by calling
  `setSucceeded` (or `setAborted`) and then `rt_active_goal_.writeFromNonRT(...)` with an
  empty handle. `cancel_callback`'s guard is `if (active_goal && active_goal->gh_ ==
  goal_handle)`, so once that write has happened the guard does not match and
  `set_hold_position()` **never runs** — and the goal ends as **SUCCEEDED** while L3 reports
  `TIMEOUT`.

**Those two leave the plant in opposite states**, full squeeze retained versus released, and
one sentence was asserting one of them for both. The `ResultCode.detail` said "the goal has
been cancelled" and now says a cancel has been **sent** and not awaited; `cite_skills/README.md`
says the same. **The launch test cannot catch this and must not be cited as if it could**: its
fake gripper accepts every cancel immediately, so what it evidences is the send.

### What a served cancel does to the part, which this record did not say at all

Read from the installed header rather than inferred —
`/opt/ros/jazzy/include/gripper_action_controller/gripper_controllers/gripper_action_controller_impl.hpp`,
in this project's container on 2026-08-30, which is the same file the `jazzy` branch carries.
`cancel_callback` (`:123-145`) calls `set_hold_position()` (`:147-153`), and that writes the
**measured** joint position into `command_struct_.position_`, leaving `max_effort_` at the
controller's configured maximum. So it is the position ERROR that collapses, not the effort
ceiling. Under `gz_ros2_control` a position command interface is a P-law producing a velocity
command, so **before** the cancel a sustained closing command against a blocked joint *is* the
grip force, and **after** it that command goes to about zero. The jaws keep their width and
resist being forced open; **the squeeze is gone.**

[ADR-0029](0029-simulated-grasping-by-friction.md) removed the attachment plugin, so friction
alone holds the part. **Whether a friction grasp survives a served cancel is unmeasured**, and
nothing in this repository has looked. It is not a premise of any decision here and must not be
smoothed over anywhere.

**The measurement that would settle it:** force an expiry with a part in the jaws — the
`docker update --cpus` reproduction in the Context section produces one on demand — and sample
the work-piece's pose for the following minute. If it moves, the cancel drops parts, and the
answer is not to stop cancelling but to decide what L3 should command instead of nothing.

**Nothing here argues against cancelling.** Leaving a goal live means the controller squeezes
indefinitely for a goal nobody holds, which is worse and is unbounded. This is the cost of the
right decision, recorded beside the L0 value where the next reader will meet it.

### The residual asked the wrong question

The old residual — *"nothing in this repository asserts what `GripperActionController` does
with a cancel"* — is answered above, from upstream source. The question that is still open is
the next one: **what does honouring it do to the grip force**, which is the measurement named
above. And on hardware the residual is a different shape again: the physical gripper is driven
through the vendor SDK's service layer and there is **no `GripperCommand` action server at
all**, so neither `cancel_callback` nor `set_hold_position` exists there. What the deadline
means transfers (P2); what the cancel does does not, and nothing has yet decided what the
hardware path cancels.

### The other gripper timeout is reachable in the cell, and it was observed

Decision 1 leaves `kGripperServerWait` and `kGripperAcceptWait` in `steady_clock`, on the
grounds that both bound *discovery* rather than plant behaviour. That reasoning stands. What
was not anticipated is that the acceptance wait expires **while the controller is executing
the goal**, and one `continuous_line` run on the reviewing machine on 2026-08-30 did exactly
that. The controller logged *"Received & accepted new action goal"*, then `rclcpp_action`
logged *"Failed to send goal response … (timeout): client will not receive response"*, and
ten wall seconds later L3 reported the acceptance timeout. **The goal reached the plant and
the acknowledgement did not.**

So `command_gripper`'s acceptance branch is a second entrance to unknown custody, not merely a
discovery failure, and it is why the latch is set there as well: *an unacknowledged goal is
not an ungiven one*. The old text on that branch — "the gripper never accepted the command" —
was false in the one run that produced it.

**One run, on one machine, under load, with no thresholds registered in advance and no
`docs/measurements/` directory.** Two other runs the same afternoon did not reproduce it: one
failed before a part was in the world at all (`ros_gz_sim create` timed out at 120 s) and one
carried three work-pieces end to end with every grasp stalling on the part. Nothing here is a
rate, and nothing here says whether the acceptance wait should move — moving it would be
Option A's mistake on a different constant.

### One more way the deadline's clock can stall

The cost list names two — a dead simulator and a stalled `/clock`. There is a third and it is
this node's own: `now()` is only as fresh as the last `/clock` message this node's executor
delivered, and the same executor serves that subscription and the callbacks that complete the
result future. A callback group that stops serving `/clock` freezes this deadline exactly as a
stopped simulator would, and from inside `command_gripper` the two are indistinguishable. Same
condition, third cause; the liveness condition the cost list asks for would have to cover it.

### How the error survived

The bullet was written about the decision rather than about the code, at a point when neither
existed — this record was written before its implementation, which is what CLAUDE.md §12 asks
for. "Cancel the goal" is what was decided; "the goal is cancelled" is what got written down,
and the gap between an act and its outcome is invisible until someone asks who confirms it.
The same gap is the one `ConveyorIndex` records about belts — commanded is not confirmed — and
it was not carried across to the gripper. The assertion that now holds the line is in
`test_gripper_deadline_launch.py`, which requires the detail to say **SENT** and forbids it
from saying the goal *was* cancelled.

## The decision, in one line

The gripper result deadline stops being a wall-clock `constexpr` in C++: it is measured in
the **node's own clock** — the clock the gripper, its controller and its stall timer already
run on — it is **declared on the L0 end-effector type** rather than compiled in, and its
meaning narrows to *"the controller never answered"* rather than *"the gripper was slow"*.

## Widening the constant is not a fix, and that framing is the record

The obvious response to a 20 s deadline that expired at 20.009 s, 20.025 s and 20.048 s is a
larger number. It is the wrong response, for two independent reasons, and both have to fail
before any candidate below is worth reading.

**It is the wrong clock.** `kGripperResultWait` is compared against
`std::chrono::steady_clock::now()` (`skill_server.cpp:1845`, `:1857`) — the host's wall
clock. It supervises a process that runs entirely in simulation time: the controller's
`stall_timeout` is counted from the controller manager's clock, and at the real-time factors
CI actually achieves, 20 s of wall clock buys on the order of 4 s of simulation time.
Widening the number changes how many seconds of the wrong clock are spent.

**It bounds a quantity that has no upper bound.** What the deadline is asked to bound is *how
long `GripperActionController` takes to declare a stall under contact chatter*, and that rule
has no maximum. `check_for_success` resets `last_movement_time_` on **every** control cycle
in which `|velocity| > stall_velocity_threshold`, so a joint that intermittently exceeds the
threshold while pressed against a part can defer the stall declaration indefinitely. A
constant that bounds an unbounded quantity is the same defect at every value.

Both are charter violations by name. It is a timing guess where an event is available (**P4**)
and a value in code that describes a thing rather than a mechanism (**P5**).

## Context

### What is true today, read from source at `b8a6c10`

- `constexpr std::chrono::seconds kGripperResultWait{20}` is declared at
  `workspace/src/cite_skills/src/skill_server.cpp:101`, beside `kGripperServerWait{10}` and
  `kGripperAcceptWait{10}`. It reaches no ROS parameter: the node declares its parameters at
  `:165-295`, including `current_state_timeout_s` and `tf_timeout_s` (`:284-285`), and none
  of them is this.
- It is applied at `skill_server.cpp:1845` as
  `std::chrono::steady_clock::now() + kGripperResultWait`, tested at `:1857`, inside a loop
  that polls the result future every `kCancelPollPeriod` (20 ms) so that a cancellation of
  the *outer* skill goal can reach the gripper. On expiry the loop breaks and `:1868-1871`
  returns `ResultCode::TIMEOUT` with the detail *"the gripper never reported a result"*.
- **The skill server runs on simulation time.** `_skill_parameters` in
  `cite_bringup/launch/simulation.launch.py` sets `"use_sim_time": True` at `:952`, and the
  node already measures every skill's own duration with the node clock — `now()` at `:747`,
  `:898`, `:1036`, `:1194`. The gripper wait is the outlier. So is `kCancelHandshake`
  (`:723-724`), which is the same construction on a different quantity and is **not** in
  scope here.
- `TIMEOUT` is `ResultCode` 6 (`cite_interfaces/msg/ResultCode.msg`), and L4 answers it with
  `Recovery::RETRY_SAME` (`recovery_policy.hpp:140-142`, where it shares a branch with
  `EXECUTION_FAILED`).
- **`Pick` returns the timeout without setting `holding_`.** `skill_server.cpp:1002-1006`
  calls `command_gripper` and returns on any non-`SUCCESS` code; `result->holding` and the
  server's `holding_` member are set only at `:1011-1012`, after a grasp that both succeeded
  and reported holding. The `Pick` result therefore states `holding = false` — a field whose
  own comment reserves it for what L4 should record as held — on a path where L3 observed
  nothing about the gripper at all.
- **Nothing cancels the underlying `GripperCommand` goal on expiry.**
  `gripper_client_->async_cancel_goal` is called only from the `cancelled(handle)` branch at
  `:1853-1856`, which fires when the *outer* skill goal is cancelled. A deadline that expires
  with no outer cancellation leaves the controller's goal live, still commanding the closed
  position at the configured effort.
- **A retry's first physical act is another gripper command.** `Pick` opens the jaws before
  approaching (`skill_server.cpp:937-944`), through the same `command_gripper` and the same
  deadline.

### The terminating rule, read upstream rather than inferred

`position_controllers/GripperActionController::check_for_success` ends a goal in exactly two
ways and in no others — fetched from `ros-controls/ros2_controllers`, branch `jazzy`,
`gripper_controllers/include/gripper_controllers/gripper_action_controller_impl.hpp`, on
2026-08-29:

```
if      |error| < goal_tolerance                     -> reached_goal, succeed
else if |velocity| > stall_velocity_threshold        -> last_movement_time_ = time
else if (time - last_movement_time_) > stall_timeout -> stalled, succeed (allow_stalling)
```

The generated configuration is `stall_velocity_threshold: 0.05` and `stall_timeout: 0.3`
(`cite_generated/control/cell_a_arm_1_controllers.yaml:42-43`), both declared once on the L0
end-effector type (`model/assets/types/end_effectors/xarm_parallel_gripper.yaml:342-343`),
whose comment at `:279-308` already writes the mechanism out and gives the measured window
the value sits in. `time` is the controller manager's clock, which is simulation time in this
cell. **This record does not touch either value** — see decision 5.

### The distribution the cap sits inside, and the excursions that produce it

From the investigation, over all six CI runs that have driven `continuous_line`, measured
from gripper goal acceptance to result:

| Motion | n | median | max | sd |
|---|---|---|---|---|
| Contact-free full-stroke OPEN | 42 | 2.35 s | 2.55 s | 0.23 |
| CLOSE on the part | 42 | 5.38 s | **16.95 s** | **3.81** |

Plus **three closes that never returned**, so **3 of 45 attempts (6.7%) exceeded 20 s**. The
20 s cap is not outside this distribution; it is inside its tail.

Why the close time varies: after the jaws stopped advancing, **13 of 96 recorded samples
exceeded 0.05 rad/s, peaking at 0.274** — contact chatter, each excursion resetting
`last_movement_time_`. Re-running the controller's rule over the recorded trace predicted the
observed result line **to 6 ms**, which is what makes this a mechanism rather than a
correlation.

**Delivery is ruled out by control, not by argument.** Open and close share one action server,
one client, one executor and one transport, and differ only in which branch of
`check_for_success` ends them. sd 0.23 against sd 3.81, over the same 42 grasps.

**Load is a standing condition and not the discriminator.** The contact-free open is a fixed
motion and therefore a clock probe: per-run median 2.251 / 2.201 / 2.352 s in the three
*failing* runs and 2.352 / 2.353 / 2.251 s in the three *passing* ones. A low real-time factor
is what makes 20 s of wall clock buy so little simulation time in CI; it is not what separated
the six runs.

**Reproduced three times, including on demand.** `docker update --cpus=0.5` applied at the
instant the close goal was accepted produced 20.061 s of wall clock to code 6 — during which
simulation time advanced 2.2 s and the drive joint was **still moving** at the deadline —
followed downstream by the CI signature verbatim.

**None of the figures in this section was re-measured for this record**, and none has a
directory in [`docs/measurements/`](../measurements/README.md). They are the investigation's,
recorded with their provenance rather than restated as facts of the repository.

### What makes it fatal is downstream, and it is deliberately not decided here

`TIMEOUT` maps to `RETRY_SAME`, the recover branch is
`RecoverFromFailure → ReleaseStationClaims → MoveToHome`
(`cite_orchestration/trees/line_station.xml:248-263`), and `MoveToHome` carries the part —
which L3 never said it was holding — off the beam the station is about to wait on again. That
is L4's dead end and it is
[ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)'s subject. What belongs
here is only the L3 half: the report that says `holding = false` about a gripper nobody
observed, and the controller goal nobody cancelled.

## Options considered

### Option A — Widen `kGripperResultWait`

The smallest diff, and the first thing anybody will try. Rejected on both grounds in the
framing section above: it is the wrong clock, and it bounds an unbounded quantity. It would
also have "worked" for the three observed runs, which is exactly what makes it dangerous — the
next starved runner moves the distribution again, and nothing in the tree would record that
the number had been chosen against three samples.

### Option B — Express the deadline in the node's clock

Compare `now()` — the node clock, which follows `use_sim_time` — against a deadline in the
same units the controller's `stall_timeout` is counted in. The poll loop that already exists
needs no new structure: it polls the future every 20 ms and can test an `rclcpp::Time`
deadline in the same iteration.

**Chosen**, as half of the decision. It makes the deadline a statement about the plant rather
than about the host, so a starved runner no longer shortens it.

### Option C — Declare the value on the L0 end-effector type

The route already exists and carries exactly this kind of value: the gripper's goal tolerance
and its drive rate travel from the end-effector type into the generated bring-up plan
(`cite_generated/bringup/cell_a_plan.yaml:103`, `:122`) and arrive as skill-server parameters
through `_skill_parameters`, whose docstring records what it cost when four gripper keys were
written out by hand instead.

**Chosen**, as the other half. A timeout that describes how a particular end-effector behaves
is configuration, and configuration lives in L0 (P5).

### Option D — Stop depending on the controller's stall declaration

The strongest-shaped option, and it is not chosen now. `Grasp` could subscribe to the drive
joint on `/joint_states`, watch where the jaws came to rest, and decide *"they stopped at a
width consistent with a part"* without waiting for the action result at all — an event rather
than a deadline, and therefore the P4-clean answer.

**Rejected for now, on two grounds.** It makes L3 a **second author** for a fact
[ADR-0022](0022-gripper-as-ros2-control-controller.md) assigned to the controller — *"a stall
is reported, not interpreted"* — and a second author for a value with one meaning is the
defect P1 names. And it does not remove the need for a bound: a subscriber waiting for a joint
to stop moving needs its own answer to "and if it never does". It is recorded here as the
direction, not as a rejected idea, and decision 3 is shaped so that taking it later does not
require unpicking this one.

### Option E — Retune `stall_velocity_threshold` against the measured contact noise

0.05 rad/s sits inside a window the L0 comment records as measured — floor ~0.025 rad/s from
observed contact creep, ceiling ~0.16 rad/s from a free-air stroke — and the observed chatter
peaked at 0.274 rad/s, above the ceiling. So the excursions are not evidence that the value is
wrong; they are evidence that the window may have been measured on a quieter contact than CI
produces.

**Rejected as part of this change, and the reason is P2.** It is an L0 end-effector value. It
changes the generated controller configuration for every arm, it is asserted by
`tools/tests/test_gripper_stall_threshold.py` as a window rather than as a number, and
[ADR-0022](0022-gripper-as-ros2-control-controller.md)'s evidence path
(`stalled=true, reached_goal=false -> holding`) is built on it. Moving it needs a campaign with
thresholds registered in advance, not an edit inside a timeout fix.

## Decision

### 1. The deadline is measured in the node's clock

The gripper result wait is bounded by a deadline in the skill server's own `rclcpp::Clock` —
simulation time in the cell, wall clock on hardware, which is in both cases the clock the
controller's stall timer runs on. `std::chrono::steady_clock` disappears from this path.

The poll on the result future stays a wall-clock poll, because that is what
`std::future::wait_for` takes and what makes the cancellation path work. **The poll period is
not the deadline.** One is how often the loop looks up; the other is when it gives up.

### 2. The value is declared on the L0 end-effector type

`kGripperResultWait` is deleted. The bound arrives as a skill-server parameter carried by the
generated bring-up plan, from a key on the end-effector type, by the route the gripper's goal
tolerance already takes. No number for it exists in `cite_skills`.

**It is an end-effector property and not an arm property**, because what it bounds is a
behaviour of the gripper's controller.

### 3. Its meaning narrows: it bounds the controller not answering, not the gripper being slow

This is the part that survives a future in which Option D is taken.

Because the stall search has no upper bound, **no value of this deadline can mean "too
slow"**. The only thing it can honestly mean is *the controller has not terminated this goal,
and L3 is no longer willing to hold the station open waiting for it*. The declared value is
therefore sized from the controller's own rule and stated as such where it is declared: it
must exceed `stall_timeout` by a margin large enough that an ordinary contact stall is never
cut short, and beyond that its exact size carries no claim.

**A consequence that must be written where the value is declared:** an expiry is a report
about the *controller*, not about the *grasp*. Nothing may read it as "the gripper is empty",
and decision 4 is what stops the code doing so.

### 4. On expiry, L3 cancels the goal and does not assert a fact it did not observe

Two things, and the second is the one that reached CI.

**Cancel.** The outstanding `GripperCommand` goal is cancelled when the deadline expires, so
the controller stops holding a closed position at maximum effort for a goal nobody is waiting
on. Today it is left running (`skill_server.cpp:1853-1856` cancels only on an outer
cancellation).

**Do not claim an empty gripper.** `Pick` may not report `holding = false` on a path where it
observed nothing about the gripper. `Pick.Result.holding` is a `bool` and cannot say
*unknown*, so the honest report is made where it can be: the `ResultCode` stays `TIMEOUT` —
accurate, the gripper genuinely never reported a result — its `detail` says that custody is
unestablished, and **no code path treats a `TIMEOUT` from `command_gripper` as evidence of an
empty gripper**. Widening `Pick.Result` to carry a third custody state is a typed-contract
change (P3) and is **not** taken here: no consumer reads that field today — a grep over
`cite_orchestration` on 2026-08-29 found no reader — so adding a state would be a contract
change with no consumer, and the consumer that needs it is the one
[ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) decides.

**Added 2026-08-30, in review: "no code path treats it as an empty gripper" had no enforcement,
and now has one.** As written, that clause was a rule about future code with nothing holding
it — and the code it was written against already broke it three ways. `Place` refuses with
*"the gripper is not holding anything"*, `Transfer` refuses with *"this arm is not holding
anything"*, and `Transfer.Result.still_holding` reports `false`, all three read off a
`holding_` this decision deliberately leaves unwritten. **Leaving a `bool` unwritten is not
silence; it reads as `false` to every consumer.** Worse, `Pick` read no custody state at all,
and `Pick`'s first physical act is to open the jaws — on a **public** action any client may
send. The only thing preventing that was ADR-0046's coordinator rule, which is a layer above
the layer that owns the fact and covers only the line.

The third state the message contract cannot carry is therefore carried **inside L3**: a
`custody_unknown_` latch, set on either `command_gripper` timeout and cleared only where a
result actually arrives. While it is set, `Pick`, `Place` and `Transfer` refuse with
`PRECONDITION_FAILED` and a detail naming the unestablished custody. `Grasp` is deliberately
**not** refused — it is the skill that commands the gripper and reports what came back, so it
is the way out of the state and the only thing that clears the latch. **The deferral above is
unchanged**: `Pick.Result` gains no field, `ResultCode` gains no value, and no typed contract
moves. `cite_bringup/test/test_gripper_deadline_launch.py` drives a real timeout and then
requires a `Pick` and a `Place` to be refused.

### 5. `stall_velocity_threshold` is not touched, and this record is not a licence to touch it

Option E's reasoning, restated as a decision so that nobody reads this change as having
settled the threshold. It stays at 0.05 rad/s. Moving it is an L0 change that reaches the
hardware path (P2) and it needs a published campaign.

### 6. ADR-0022's evidence path is unchanged

`stalled=true, reached_goal=false` remains what evidences a grasp,
`cite_skills::gripper_is_holding` remains the discriminator, and the controller remains the
sole author of "the gripper stalled". Nothing in decisions 1-5 changes what a successful grasp
looks like; they change only what happens when no answer arrives at all.

## Consequences

### What this gets us

- The deadline stops being a function of how fast the host is. The same cell on a starved
  runner and on an idle workstation waits the same number of *simulated* seconds.
- One fewer compiled constant describing a piece of equipment, and one more value with a
  single home in L0 (P1, P5).
- A controller goal that is given up on is also cancelled, so the gripper stops being
  commanded by a goal nobody holds.
  **[Corrected 2026-08-30 — see the Correction section above.]**
- The report stops asserting an empty gripper it never observed, which is the L3 half of the
  silence that produced three CI failures.

### What this costs us

- **A deadline in simulation time never expires if simulation time stops.** If Gazebo dies or
  `/clock` stalls, the wait becomes unbounded and the goal hangs until the launch tears the
  process down. That is a real regression against a wall-clock bound, accepted because a hung
  goal under a dead simulator is a condition the launch already handles (`_fatal_on_exit`) and
  because the alternative is the defect this record exists for. **The condition that would
  change it:** if a hang under a stopped clock is ever observed as the proximate cause of a
  failure, this decision needs a liveness condition on the clock — an event, not a second
  timeout.
- **One more L0 key on the end-effector type**, and one more parameter the skill server
  declares, for a quantity that is not a physical dimension of the gripper. It is the first
  value on that type that describes its *controller's* behaviour rather than its geometry.
- **The number will still look arbitrary**, because decision 3 says it carries no claim beyond
  exceeding `stall_timeout`. Whoever finds it in their way is meant to take Option D, and this
  record is the only thing that says so.
- **It removes a symptom and not the cause.** The gripper will still take 17 s to declare a
  stall under chatter, and a line whose station budget is tight will still be late. What
  changes is that lateness stops being reported as a failed pick.
- **Cancelling the gripper goal is a new path with no test today**, and nothing in this
  repository asserts what `GripperActionController` does with a cancel. A cancel the controller
  does not honour leaves the same held command with a different name on it.
  **[Corrected 2026-08-30 — see the Correction section above. The question is answered and it
  was the wrong question.]**

### What we will have to revisit

- **When Option D is built**, decisions 1-3 collapse into it: an observation of the drive joint
  replaces the deadline, and the L0 key is deleted with it rather than kept "just in case".
- **If a stalled `/clock` ever hangs a grasp**, decision 1 gains a liveness condition.
- **When `stall_velocity_threshold` is re-measured against CI-grade contact noise**, decision 5
  is what is being reopened, and it wants a `docs/measurements/` directory.
- **When a consumer needs custody typed rather than in prose**, decision 4's deferred interface
  change is what to take, and
  [ADR-0046](0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md) is the record that will
  name the consumer.

## What is explicitly unmeasured, and stays that way until someone measures it

Three things the investigation did **not** establish. None may be smoothed over in any
document, and none is a premise of any decision above.

1. **Why CI's close distribution has a long tail that the investigating host did not reproduce
   at comparable speed.** CI produced closes from 3.2 s to 17 s with three over 20 s; the local
   host, throttled to a comparable real-time factor, did not. **The measurement that would
   settle it:** record `/cite/cell_a/arm_*/joint_states` through a full `continuous_line` run
   **on the CI runner**, and compare the excursion rate above `stall_velocity_threshold` and
   the stall-search duration against the local traces.
2. **Whether the `arm_1` concentration is real.** Three of three timeouts fell in 17 `arm_1`
   attempts and none in 28 attempts across arms 2 and 3; Fisher's exact test gives
   approximately 0.05 at n=3, which is a hint and not a result. The candidate difference is
   that `arm_1` grasps off a static table while the other two grasp off a stopped belt link.
3. **Whether the controller ever declared the stall after the client gave up.** The client
   stops listening at the deadline, and nothing in the recorded data says what the controller
   did next.

## A separate defect, found in the same investigation, owed its own record

**[2026-09-01: that record is now written —
[ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md). It is `Proposed`, it
chooses nothing, and it corrects the reading of the example below: 46.6 mm as a *declared
work-piece* is a model `default-grasp-width-never-closes` already refuses. Nothing in this
section is rewritten.]**

**It is not folded into this one and must not be.** `cite_skills::gripper_is_holding`
(`gripper.cpp:106-117`) requires the reached width to exceed the commanded width by more than
**twice** the linkage's own width tolerance at that drive angle. Against a commanded 45.0 mm,
a genuine 46.6 mm stall gives a margin of 1.6 mm and a 2x threshold of 2.12 mm — **so a real
grasp is reported empty.** Recomputed for this record from the L0 linkage dimensions
(`drive_pivot_y_m 0.035`, `pad_inset_m 0.026`, `finger_offset_y_m 0.035465`,
`finger_offset_z_m 0.042039`, `goal_tolerance 0.01`) and the functions in `gripper.cpp`, and
it reproduces exactly.

That reaches the same L4 dead end by a different entry — `Pick` returns `EXECUTION_FAILED`
with an empty-grasp description (`skill_server.cpp:1007-1010`) while the part is in the jaws.
It is a different defect with a different fix, in a function this record does not touch, and it
needs its own decision on its own evidence.

## How the claims here were verified

In the style of [`toolchain.md`](../reference/toolchain.md). Everything was checked on
**2026-08-29** against the worktree at `b8a6c10` unless stated.

| Claim | How | Result |
|---|---|---|
| `kGripperResultWait` is 20 s and is a `constexpr` in C++ | Read `skill_server.cpp:98-101` | Exact: `constexpr std::chrono::seconds kGripperResultWait{20}` at `:101`, beside two other gripper constants |
| It is compared against the wall clock | Read `skill_server.cpp:1845`, `:1857` | Exact: `std::chrono::steady_clock::now() + kGripperResultWait`, tested with `steady_clock::now() >= deadline` |
| No ROS parameter exposes it | Read every `declare_parameter` call, `skill_server.cpp:165-295` | `current_state_timeout_s` and `tf_timeout_s` exist at `:284-285`; nothing for the gripper wait |
| The skill server runs on simulation time | Read `_skill_parameters`, `simulation.launch.py:921-956` | `"use_sim_time": True` at `:952`, delivered with every other skill parameter |
| The node already measures durations with its own clock | Read `skill_server.cpp:747`, `:898`, `:1036`, `:1194` | Each takes `now()` at entry and reports `now() - started`. The gripper wait and `kCancelHandshake` (`:723-724`) are the only `steady_clock` users |
| `Pick` returns the gripper timeout without setting `holding_` | Read `skill_server.cpp:1002-1012` | Exact. `command_gripper` at `:1002`, unconditional return on any non-`SUCCESS` code at `:1003-1006`; `result->holding` and `holding_` set at `:1011-1012` only |
| Nothing cancels the gripper goal on expiry | Read `skill_server.cpp:1845-1871` | `async_cancel_goal` is reached only from the `cancelled(handle)` branch at `:1853-1856`. The deadline branch at `:1857-1859` breaks the loop and `:1868-1871` returns `TIMEOUT` |
| No consumer reads `Pick.Result.holding` | Grepped `workspace/src/cite_orchestration` for `.holding` and `->holding` | No occurrence. **A survey of that package on this date, not a proof about the system** |
| `TIMEOUT` is code 6 and maps to `RETRY_SAME` | Read `cite_interfaces/msg/ResultCode.msg` and `recovery_policy.hpp:140-142` | `uint8 TIMEOUT=6`; the case falls through with `EXECUTION_FAILED` to `return Recovery::RETRY_SAME` |
| `Pick`'s first physical act is opening the gripper | Read `skill_server.cpp:937-944` | Exact, with the stated collision reason, and through the same `command_gripper` and the same deadline |
| The recover branch is `RecoverFromFailure`, `ReleaseStationClaims`, `MoveToHome` | Read `cite_orchestration/trees/line_station.xml:248-263` | Exact, in one `<Sequence name="recover">` |
| The controller's terminating rule, and the name of the function | Fetched `ros-controls/ros2_controllers`, branch `jazzy`, `gripper_controllers/include/gripper_controllers/gripper_action_controller_impl.hpp` | **Verified.** The function is `check_for_success`; the three branches are as quoted, and `last_movement_time_ = time` is reached on every cycle above the threshold. The L0 comment at `xarm_parallel_gripper.yaml:280-282` calls it `checkForSuccess` at `:166-189` — a stale name for the right function, not corrected by this record |
| The stall parameters and where they are declared | Read `cite_generated/control/cell_a_arm_1_controllers.yaml:42-43` and `model/assets/types/end_effectors/xarm_parallel_gripper.yaml:342-343` | `stall_velocity_threshold: 0.05`, `stall_timeout: 0.3`, generated from the one L0 declaration |
| The measured window 0.05 sits in, and that the observed chatter exceeded its ceiling | Read `xarm_parallel_gripper.yaml:296-316`; compared against the investigation's 0.274 rad/s peak | Window recorded as floor ~0.025, ceiling ~0.160 rad/s. The observed peak is above the ceiling. **The window was not re-measured here** |
| An L0 end-effector value already reaches L3 through the generated plan | Read `cite_generated/bringup/cell_a_plan.yaml:98-128` and `_skill_parameters` | `gripper_goal_tolerance_rad: 0.01` at `:103` and `gripper_max_drive_rate_rad_s: 1.0` at `:122`, both spread into the skill server's parameters |
| The 2x margin calls a real 46.6 mm grasp empty | Recomputed from `gripper.cpp:82-117` and the L0 linkage dimensions, in an independent script | **Reproduces.** Margin 1.6 mm against a 2x threshold of 2.1244 mm, so `gripper_is_holding` returns false |
| Every timing figure, the six-run distribution, the excursion counts and the `docker update` reproduction | **Not re-measured.** Taken from the project owner's investigation | **Reported, not measured here.** No `docs/measurements/` directory, no thresholds registered in advance. The mechanisms they rest on are checkable and were checked; the run data is one investigation's |
| That any of this fixes the CI failure | **Not verified. Nothing here is built** | **Unverified.** It is what the implementation's first `continuous_line` runs on a CI runner would have to show, and a run in which the gripper answers quickly cannot show it at all |
