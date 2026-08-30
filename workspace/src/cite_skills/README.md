# cite_skills

L3: the robot-agnostic capability servers. Skills are the vocabulary the system speaks about
work — `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer`, `Detect` — and they are the only thing
L4 is allowed to call.

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

Two executables.

| Executable | Scope | Serves |
|---|---|---|
| `skill_server` | one per arm, in that arm's namespace | `MoveTo`, `Grasp`, `Pick`, `Place`, `Transfer` |
| `detection_server` | **one per zone**, in a zone-scope namespace | `Detect`, plus one `DetectionEvent` publisher per beam |

`Detect` is separate on purpose. It commands no motion, needs neither the planner nor the
gripper, and belongs to a zone's sensors rather than to one arm — three arms each serving it
would give the question "did the piece pass beam 2" three answers.

Headers under `include/cite_skills/` hold the parts that are pure arithmetic or pure state:
approach and retreat geometry, the gripper linkage, the pose-goal sequencing rule, the
one-goal-at-a-time gate, the beam edge detector, and the unobserved-pose convention. They are
exported, so L4 can include them — a downward dependency, which CLAUDE.md §5 permits.

## Interfaces

Every action name arrives as a generated parameter. **Nothing in this package concatenates a
topic, an action or a frame name**, and a server refuses to start rather than guess. In
`cell_a` the names are `/cite/cell_a/<arm>/{move_to,grasp,pick,place,transfer}` and
`/cite/cell_a/detection/detect`, all from `cell_a_plan.yaml`.

The action shapes are in `cite_interfaces` and are not restated here (P1); read them with
`ros2 interface show`.

`detection_server` subscribes to each beam's bridged `std_msgs/Bool` level and publishes a
`cite_interfaces/DetectionEvent` per beam on the `EVENT` profile. The raw level and the typed
event are two different interfaces on two different topics — see
[`cite_bringup`](../cite_bringup/README.md) for why.

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
  A physical through-beam delivers a level exactly as the simulated one does, and this is the
  single place either becomes a `DetectionEvent`.
- **It does not report a pose a break beam cannot know** — see the limitations below.
- **It does not implement a straight-line Cartesian path.** `MoveTo` with `cartesian_path`
  returns `NOT_IMPLEMENTED` rather than silently planning a joint-space move. A straight line
  is a continuum of poses, and on this arm almost none of the interpolated poses has an IK
  solution; a caller asking for a line along a surface and receiving an arbitrary joint path
  would be receiving a different, possibly colliding, motion.
- **The only named configuration is `home`**, and it comes from the L0 model.

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

**`Transfer` has a server and no caller.** Today's L0 topology is conveyor-mediated, and L4
refuses a direct arm-to-arm edge at plan time
([ADR-0031](../../../docs/adr/0031-refuse-direct-handoff-without-orientation-certainty.md)).

**`Detect` reports occupancy, not position.** A through-beam knows something crossed it; it
does not know where along the beam, and nothing about how that something is turned. So
`Detection.pose` is marked **explicitly unobserved** — empty `frame_id`, zero stamp, NaN in
every component — by `cite_skills::mark_pose_unobserved`, and `workpiece_id` and
`workpiece_type` are left empty for the same reason. This is not "the pose is uncertain":
`Detection` has no covariance and no field separating a measured axis from an inferred one, so
reporting a constrained pose without the shape of its uncertainty would put a number that
looks measured back into the field. `observation.hpp` names the three fields `Detection` would
need before that changes. Read `pose_is_observed` rather than re-deriving the test.

That field used to be filled in — with the *sensor's own mounting pose*. For `beam_c1_out`
that is 0.250 m across the belt from the point a station picks at, and `station_transfer_1`'s
resulting pick was 0.7267 m from `arm_1` against a 0.700 m envelope, so it failed with "no IK
solution from any of 8 seeds" and never reached a grasp. This is the case ADR-0031's
correction section calls out: **a field's existence is not evidence that anything fills it.**

**A `workpiece_type` filter returns `NOT_IMPLEMENTED`.** A through-beam cannot tell a
work-piece from a hand. Filtering would mean either ignoring the filter or inventing the type
from the goal — the caller's assumption handed back as a reading.

**A region with no sensor in it returns `SUCCESS` with an empty list and says so in `detail`.**
"No sensor watches here" and "nothing is here" are different facts and a caller cannot tell
them apart from an empty list alone.

**A beam mounted 0.030 m above the belt cannot see a part shorter than about 30 mm.** That
bound is real and holds identically on hardware. `beam-cannot-see-workpiece` in
`cite_tools.validate.geometric` rejects that pairing in the model rather than leaving it to be
found at run time. There is no upper bound.

## How to run it

Both servers are started by `cite_bringup` with all their parameters generated:

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
| `Place`/`Transfer` returns `PRECONDITION_FAILED` "not holding anything" | refused rather than mimed — the failure would otherwise surface at the receiving station, which is much harder to attribute |
| `Transfer` returns `PRECONDITION_FAILED` "no rendezvous token" | L4 issues one for every handoff it has negotiated, so an empty token is a caller that skipped the two-party confirmation |
| `Detect` returns `PRECONDITION_FAILED` on a zero-sized region | a default-constructed goal has one, and an empty result from it would read as "nothing is on the belt" — a wrong answer that looks exactly like a right one |
| `Detect` times out waiting for a sensor | the bridge is not delivering. The grace period exists so a `Detect` issued just after start-up does not fail for want of a sample about to arrive; expiry is a diagnosis, not an empty belt |

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
`Place`'s `require_holding` test, `Transfer`'s refusal, `Transfer.Result.still_holding` — so
silence is not neutrality, it is the same wrong claim one layer down. While the latch is set,
`Pick`, `Place` and `Transfer` all refuse with `PRECONDITION_FAILED` naming the unestablished
custody. **`Grasp` is deliberately not refused**: it is the skill that commands the gripper
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
failed. `cite_orchestration/recovery_policy.hpp` ESCALATEs `UNREACHABLE` and retries
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
| `test_detection` | level to edge, including the first-sample case: a work-piece already in the beam must not be reported as an arrival nobody saw |
| `test_observation` | the unobserved-pose convention, as a rule a consumer branches on |
| `test_skill_contract.py` | launch test: goal exclusion, a cancel that reaches the gripper, and a reachable pose that is planned to rather than refused. `move_group` runs; there are no controllers, so execution always fails — which is what separates "the planner produced a trajectory" from "the trajectory ran" |
| `test_detection_contract.py` | launch test: a level on the plan's topic becomes a typed event and a typed detection, driven by a plain ROS publisher |
| `test_downstream_include.py` | whether another package can reach these headers **from the install space**. Every other test reaches them through the source tree, which is the one path a consumer does not have — so all of them passed while `observation.hpp` was unreachable from outside the package |

`test_detection_contract.py` used to say "the bridge does not exist yet". It does, in
`cite_bringup`, and the docstring now says what that test does and does not prove about it:
the rig drives the ROS side by hand and is unchanged, so a Gazebo boolean actually arriving is
`tests/scenarios/continuous_line.py`'s to show and not this file's.
