# cite_skills

L3: the robot-agnostic capability servers. Skills are the vocabulary the system speaks about
work — `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer` — and they are the only thing a layer
above is allowed to call. The beam-driven `Detect` skill and its server left the main tree with
the event-driven line ([ADR-0069](../../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md));
they run in `projects/01`.

C++ because every skill sits on a motion path, and
[`cross-cutting-safety.md`](../../../docs/architecture/cross-cutting-safety.md) requires
simulation-only code to be audited as if it were hardware code.

**Goals are in task space, never joint space.** A joint-space goal in the *interface* would
leak the robot's kinematics upward and break the promise that swapping an xArm 5 for a
different arm changes nothing above this line. Inside a skill it is the opposite: a Cartesian
pose goal is never handed to the planner — the pose is resolved, IK is solved on that exact
pose, and the planner is given the resulting joint configuration
([ADR-0026](../../../docs/adr/0026-joint-space-goals-on-under-six-dof-arms.md)), because a
pose goal is satisfied by random draws from inside its tolerance and on an arm with fewer
than six degrees of freedom almost every draw is unreachable.

## What is here

One executable.

| Executable | Scope | Serves |
|---|---|---|
| `skill_server` | one per arm, in that arm's namespace | `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer` |

Headers under `include/cite_skills/` hold the parts that are pure arithmetic or pure state:
approach and retreat geometry, the gripper linkage, the pose-goal sequencing rule, the
one-goal-at-a-time gate and the motion-end classifier. They are private to this package.

## Interfaces

Every action name arrives as a generated parameter. **Nothing in this package concatenates a
topic, an action or a frame name**, and a server refuses to start rather than guess. In
`cell_b` the names are `/cite/cell_b/picker/{move_to,grasp,pick,place,transfer}`, all from
`cell_b_plan.yaml`.

The action shapes are in `cite_interfaces` and are not restated here (P1); read them with
`ros2 interface show`.

Each `skill_server` publishes one topic of its own: `cite_interfaces/RobotState` on
`<namespace>/state`, carrying what this arm holds and which skill is running, on the `LATCHED`
profile and only when one of those changes (ADR-0065). The name is **relative**, like every
action beside it, so it resolves against the namespace the launch gave the node and is not
assembled anywhere. `gripper_holding` is `holding_ || custody_unknown_`, because custody has
three states and the field has two and unknown falls on the side that makes a consumer
escalate (ADR-0046). `joint_positions_rad`, `joint_velocities_rad_s`, `tool_pose`,
`held_workpiece_id` and `state` are left at their defaults with the reason in
`publish_state`'s own comment — this node holds no `/joint_states` subscription and is told no
work-piece id, and inventing either would be a value in a second place. **It is not a
simulation aid**: it publishes identically on both backends, and what reads it in simulation
is a bridge one layer up.

## Contracts these servers keep

- **One arm executes one skill at a time.** Five action servers share one `MoveGroupInterface`,
  which is not thread-safe and whose target, start state and scaling factors are per-object. A
  second goal accepted while one is in flight can plan to the target the first just installed,
  and the arm executes it. A second goal is **rejected**, not queued — which means a caller
  that abandons a goal must cancel it.
- **Cancellation is implemented, not just accepted.** Every skill checks for it, stops the arm
  and the gripper, and waits for the cancel to reach the goal handle before reporting. Covering
  only the happy path is a review finding at this layer.
- **Every deadline is a failure deadline.** Nothing waits for one in order to proceed. The poll
  periods (`kCancelPollPeriod`) are how often a future is looked at, not a guess at how long
  anything takes.
- **A result says what was measured.** `MoveTo.position_error_m` is `NaN` when no Cartesian
  target was requested, because there is nothing to measure against; `0.0` would be a standing
  claim of perfect accuracy, which P8 forbids.

## What it deliberately does not do

- **It does not talk to another skill.** A handoff is split (ADR-0024): `Transfer` takes a pose
  and an **opaque** rendezvous token, never a peer's identity, and never learns whether
  anything is on the other side. L4 owns ownership.
- **It does not branch on being in simulation.** There is no `if simulation` here or below it.
- **It does not implement a straight-line Cartesian path.** `MoveTo` with `cartesian_path`
  returns `NOT_IMPLEMENTED` rather than silently planning a joint-space move. A straight line
  is a continuum of poses, and on this arm almost none of the interpolated poses has an IK
  solution; a caller asking for a line along a surface and receiving an arbitrary joint path
  would be receiving a different, possibly colliding, motion.
- **The named configurations are `home` and the arm's program poses**, and nothing else.
  `home` comes from the L0 model; the program poses come from the robot's Blockly program,
  read when the plan is generated and delivered as the plan's `poses_rad`
  ([ADR-0067](../../../docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md)). This line
  said "the only named configuration is `home`" until 2026-10-01.

## Limitations that are known, and how each is known

**A grasp holds a position, not an orientation.** Correcting the grasp-plane offset took
rotations above 20° from 60% of trials to none and left a residual. **That residual, up to
18.71°, is a *roll* about the pad-to-pad axis — it is not a yaw**, and it must not be put into
anything only a yaw can enter. The figures and their axes live in
[`docs/measurements/`](../../../docs/measurements/README.md) and are not copied here.
`Transfer` states the bound in its result `detail` on every success, because a caveat nobody
reads is a caveat that does not exist. Per
[ADR-0029](../../../docs/adr/0029-simulated-grasping-by-friction.md) a scenario may assert
where a part ends up and **may not assert how it is held**.

**`Transfer`'s two-party hold returns `NOT_IMPLEMENTED`.** A goal with a non-zero
`hold_timeout` asks the arm to hold at the handoff pose until a peer takes the work-piece, and
**no typed channel exists for L4 to signal that release**. The caller is told so in a code it
can branch on, *before the arm moves* — parking a loaded arm at a rendezvous it can never
complete is a worse failure than refusing. What is deliberately **not** done is a bounded wait
that expires and reports `TIMEOUT`: that is the contract's own defined outcome and would look
entirely correct while nothing was ever listening, which is v1's handoff exactly. Send
`hold_timeout = 0` for a conveyor-mediated transfer, where the confirmation happened before
the goal was sent.

**`Transfer` has a server and no caller.** Nothing in the main tree issues an arm-to-arm
handoff; the line that refused one at plan time
([ADR-0031](../../../docs/adr/0031-refuse-direct-handoff-without-orientation-certainty.md))
runs only in `projects/01`.

## How to run it

The server is started by `cite_bringup` with all its parameters generated:

```bash
./scripts/sim --headless
ros2 action list | grep cite
```

Running one by hand means supplying every parameter the plan carries — the planning group, the
tip link, the gripper action, the home configuration, the gripper linkage — and the server
refuses to start without the names. Use the launch.

## How it fails

| Symptom | Cause |
|---|---|
| the server starts, loads its model, and advertises nothing | `move_group` is not running in this arm's namespace. `MoveGroupInterface::Options` carries its own namespace and does **not** inherit the node's |
| `parameter 'X' is empty` | the generated plan did not deliver it. Guessing would put this arm's actions somewhere nothing looks |
| `planning group 'X' has no kinematics solver` | `robot_description_kinematics` never arrived. Every motion is planned to an IK solution, so without a solver the node can advertise skills and never move one |
| `home_rad has N values but planning group has M` | the home configuration and the generated SRDF came from different sources |
| a goal is rejected with "still holds this arm" | another goal is in flight. The caller that abandoned the earlier one has to cancel it |
| `Pick` fails with `EXECUTION_FAILED` and an empty-grasp message | the jaws closed on nothing. A grasp is evidenced by *failing* to reach the commanded width |
| a `Pick` warns that no grasp width reached the node | `grasp_width_m` was 0 and no `gripper_default_grasp_width_m` was delivered, so the gripper closes against its effort limit. The end-effector type declares one and the plan carries it |
| `Pick` or `Grasp` returns `TIMEOUT` "the gripper's controller never reported a result" | the controller did not terminate the goal within `gripper_result_timeout_s` of THIS NODE'S clock (ADR-0045). A cancel has been **sent** for it and not awaited, so whether it was served is unknown. **It is not a report about the jaws** — the arm may be holding the work-piece, and the detail says so; nothing may recover from it as an empty gripper |
| `Pick`, `Place` or `Transfer` returns `PRECONDITION_FAILED` "WHETHER IT IS HOLDING ANYTHING IS UNESTABLISHED" | the latch below. The last gripper command ended without an answer, so this server refuses every skill whose next physical act assumes a known gripper. Send a `Grasp` to establish what the jaws hold; that is the only thing that clears it |
| `Place`/`Transfer` returns `EXECUTION_FAILED` "commanded the jaws fully open and they still read as holding the part" | the release was commanded and did not happen. `GripperActionController` SUCCEEDS a command it has declared stalled, so `result.code` cannot see this and `release_jaws` confirms the outcome with `gripper_is_holding` instead. **The arm has not moved and must not be made to**: retreating from here carries the part off the place pose and drops it wherever the retreat reached — measured at **39 mm above the belt**, 74.68 mm apart between two sides of a pair ([ADR-0063](../../../docs/adr/0063-the-drive-joint-may-not-be-clamped.md)). `still_holding` is true and the custody latch below is set, so this escalates rather than being retried. **Operator action:** the jaws are left commanded FULLY OPEN at the configured effort and that command persists — the detail string says so — so free the part with that in mind, then send a `Grasp` to re-establish what the gripper holds |
| `Place`/`Transfer` returns `PRECONDITION_FAILED` "not holding anything" | refused rather than mimed — the failure would otherwise surface at the receiving station, which is much harder to attribute |
| `Transfer` returns `PRECONDITION_FAILED` "no rendezvous token" | L4 issues one for every handoff it has negotiated, so an empty token is a caller that skipped the two-party confirmation |

**The gripper result deadline is an L0 value, measured in this node's clock**
([ADR-0045](../../../docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md)).
It was `constexpr std::chrono::seconds kGripperResultWait{20}` compared against
`steady_clock` — the host's wall clock — while everything it supervised ran in simulation
time, so on a loaded runner it bought about four simulated seconds and expired while the
gripper was still moving. It is now `gripper_result_timeout_s`, declared on the L0
end-effector type, delivered by the generated plan, and compared against `now()`, which
follows `use_sim_time`. **No number for it exists in this package**: the parameter's
compiled default is `0.0`, a sentinel, and an arm with a gripper action refuses to configure
without a delivered value rather than falling back on a copy that happens to agree.

**What an expiry means is narrower than it looks, and the narrowing is the decision.**
`GripperActionController` restarts its stall search on every control cycle above
`stall_velocity_threshold`, so the time it takes to declare a stall has no upper bound and no
deadline could cap it. The only thing this can honestly mean is *the controller has not
terminated this goal*. So on expiry the server **sends a cancel** for the outstanding
`GripperCommand` — otherwise the controller goes on commanding a closed position at the
configured effort for a goal nobody holds — and it **does not report an empty gripper**.
`Pick.Result.holding` is a `bool` and cannot say "unknown"; the honest statement is in the
`ResultCode.detail` and in an error log naming the work-piece, and `holding_` is left
unwritten in either direction. The cost is stated where it is paid, in `command_gripper`: a
deadline in simulation time never expires if simulation time stops, and `now()` is only as
fresh as the last `/clock` the executor delivered.

**The cancel is a send, not an outcome, and from the part's point of view it is the cost
rather than the win.** It is sent and deliberately not awaited — this is the path on which
the controller is not answering — so it may never be served; and if it is served late,
`check_for_success` can have terminated the goal successfully in between, leaving
`cancel_callback`'s guard unmatched and `set_hold_position()` unrun. Those two outcomes leave
the jaws in **opposite** states, so nothing here may say the goal *was* cancelled. When it
**is** served, `set_hold_position()` writes the measured jaw position as the command, the
position error that was generating grip force goes to zero, and the jaws keep their width and
lose their squeeze. ADR-0029 removed the attachment plugin, so friction alone holds the part:
**whether a friction grasp survives a served cancel is unmeasured**, and ADR-0045's
consequences name the measurement that would settle it. The launch test's fake gripper
**accepts** every cancel, so it evidences the send and can evidence nothing about any of this.

**And the report is not the only thing that changes on a timeout: a custody-unknown latch is
set, and L3 acts on it itself.** `holding_` unwritten reads as `false` to every consumer —
`Place`'s `require_holding` test, `Transfer`'s refusal, and until this branch the
`still_holding` field of both results — so silence is not neutrality, it is the same wrong
claim one layer down. While the latch is set, `Pick`, `Place` and `Transfer` all refuse with
`PRECONDITION_FAILED` naming the unestablished custody.

**The refusal alone left one of those consumers wrong, and it was the machine-readable one.**
Both refusals leave through the same `finish` lambda every other exit uses, and that lambda
filled `still_holding` from `holding_` — so a refusal whose `detail` said custody was
UNESTABLISHED carried a boolean beside it saying the arm was empty, on the one exit that
exists to say nobody knows. `still_holding_now()` is what those lambdas read now: holding, or
custody unknown.

**The release step participates in that same field, and it is the one place the latch is set
without a missing answer.** A `Place` or `Transfer` whose release is commanded and not
confirmed leaves through the same lambda with `still_holding` true, because `release_jaws`
latches custody-unknown on its give-up exit: the controller answered, so what is unknown is
not whether it spoke but **what is between the pads** — the jaws read as holding something
this node has no record of taking, and a caller that passed `require_holding=false` would
otherwise be handed `still_holding` false beside a detail saying the part was not released.
`Grasp` is the way out of this latch exactly as it is out of the other. **`holding_` itself is still never written on this path** — unknown custody
is reported, not resolved — and the direction is the one in `Place.action`: unknown falls on
the side that escalates, never on the side that opens a gripper. **`Grasp` is deliberately not refused**: it is the skill that commands the gripper
and reports what came back, so it is the way out, and a result arriving is what clears the
latch. The interlock is here rather than in L4 because `pick` is a **public action** whose
first physical act is to open the jaws — ADR-0046's coordinator rule keeps the line out of
this state and can keep nothing else out.

**Every gripper key the plan delivers is now declared here.**
`gripper_max_drive_rate_rad_s` was the twelfth of `cite_bringup`'s `GRIPPER_KEYS` and was
declared by nothing, so rclcpp accepted the override and dropped it without a word — the
same shape as the `gripper_max_width_m` defect that `plan.py` documents as fixed. It is
declared now and this node does not act on it: the rate bounds the drive joint, a joint is
bounded in its description, and the same L0 value reaches the gripper as an argument to the
generated `*.urdf.xacro`. `cite_bringup`'s
`test_every_gripper_key_is_one_the_skill_server_declares` reads this file's
`declare_parameter` calls, so a key that is delivered and declared nowhere fails a unit test
rather than going quiet.

**An unreachable pose is reported as `UNREACHABLE`.** It used to be reported as
`PLANNING_FAILED`, through a local `kUnreachable` alias written while `ResultCode.msg`
carried no constant for reachability. The constant landed; the alias did not move; nothing
failed. The line's recovery policy (now in `projects/01`) ESCALATEd `UNREACHABLE` and retried
`PLANNING_FAILED`, so the drift spent a station's whole retry budget resending a pose no IK
branch can reach. The constant is now named at the one place that produces it, and
`test_skill_contract.py::test_3b_an_unreachable_pose_is_reported_as_unreachable` sends a pose
2.5 m out and asserts the code that comes back.

## Tests

```bash
./scripts/test --packages-select cite_skills
```

Two levels, because the defects live at both. The unit tests need no simulator, no planner and
no waiting.

| Test | What it proves |
|---|---|
| `test_approach` | approach and retreat geometry — pure arithmetic |
| `test_pose_goal` | ADR-0026's rule as sequencing: solve IK on the exact pose, plan to the joint configuration, try more than one seed before calling a pose unreachable |
| `test_gripper` | metres against the drive joint's own units, where the pad face sits on the tool axis, and what a `Pick` closes to with the width unset |
| `test_grasp_pose` | the composition of the two — the sign and the axis, both free to be wrong in a way that reads as plausible and moves the arm 37 mm the wrong way |
| `test_exclusive_goal` | one arm, one goal — with threads, not with a comment |
| `test_skill_contract.py` | launch test: goal exclusion, a cancel that reaches the gripper, and a reachable pose that is planned to rather than refused. `move_group` runs; there are no controllers, so execution always fails — which is what separates "the planner produced a trajectory" from "the trajectory ran" |

