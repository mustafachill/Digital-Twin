# Bring-up

- **Status:** `PARTIAL` — the simulated path below works and is what `./scripts/scenario bringup`
  drives. A solo bring-up stops at the skills; **twin sync** (`cite_twin`) is started by the
  pair supervisor under `./scripts/sim --pair` and `./scripts/program`
  ([ADR-0057](../adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md)), on the paired
  zone `cell_b`, and appears in no launch file and no scenario. The physical counterpart's path
  is built ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)) and has never
  been run against the arm.
- **Related:** [`../architecture/cross-cutting-lifecycle.md`](../architecture/cross-cutting-lifecycle.md)

## Simulated cell

### 1. Verify the environment

```bash
./scripts/doctor
```

**Expect:** failures none; skips only for things the current phase has not built.
**If not:** fix before continuing. A bring-up on a broken environment produces failures
that point at the wrong layer entirely.

### 2. Build

```bash
./scripts/build
```

**Expect:** completion, and `workspace/install/setup.bash` present.
**If not:** `./scripts/clean && ./scripts/bootstrap && ./scripts/build`. A stale colcon
build explains a surprising share of inexplicable failures.

### 3. Validate the model

```bash
./scripts/validate-model
```

**Expect:** valid, with no findings.
**If not:** do not proceed. Everything downstream is generated from the model; a bring-up
against an invalid model debugs the wrong thing.

### 4. Launch

```bash
./scripts/sim                          # GUI, Linux only
./scripts/sim --headless               # anywhere
```

`--zone` may be left out because L0 declares exactly one zone, `cell_b`; the default is derived
in `cite_bringup/zones.py`, and the flag becomes required again the day a second zone is
declared (ADR-0069 decision 5).

A windowed run opens with the camera already framing the whole zone from the customer side,
across the line from the arm; the pose is generated from L0 into `worlds/<zone>_gui.config`,
and the view can still be moved by hand.

**Expect:** bring-up proceeds through the ordered sequence, each step gated on the previous
one reporting active:

```
simulator → descriptions → controller manager → controllers
          → MoveIt → skills → twin sync
```

A solo bring-up stops at skills; twin sync is the pair supervisor's (below).

**If a step fails:** bring-up stops with a diagnosis naming the step. It does not continue
degraded — that is the point of lifecycle sequencing.

### 5. Verify

```bash
ros2 control list_controllers          # all active
ros2 topic hz /cite/cell_b/picker/joint_states
ros2 action list | grep cite           # skill servers present
# /cite/twin/mode has NO publisher in this bring-up: cite_twin is started
# only by the pair supervisor (./scripts/sim --pair, ./scripts/program).
```

The simulation-fidelity aids cross into ROS through one `ros_gz_bridge` process:

```bash
ros2 node list | grep gz_bridge                                 # exactly one
ros2 topic echo /cite/cell_b/infeed_beam/detection_level        # a beam's raw level, std_msgs/Bool
ros2 topic pub --once /cite/cell_b/transfer_belt/command \
    std_msgs/msg/Float64 "{data: 0.15}"                         # the belt, by hand
```

The beams stand in `cell_b`'s world and their levels are bridged, but **nothing in the main
tree reads them**. The topic names are the plan's — read
`workspace/src/cite_generated/bringup/cell_b_plan.yaml` rather than this block.

**If a belt setpoint seems never to arrive:** reliable QoS is a promise to *matched*
subscribers, so a setpoint published before the bridge's subscriber matched is delivered to
nobody, however long the bridge has been up. The rule is in
[`../interfaces/qos-profiles.md`](../interfaces/qos-profiles.md).

**If a controller is inactive:** check that its joint names match the description
(`./scripts/validate-model`). The spawner error names the spawner, not the mismatch — this
is the single most time-consuming false trail in ROS 2 controller bring-up.

**If a topic exists but `hz` reports nothing:** suspect QoS before anything else. See
[`../interfaces/qos-profiles.md`](../interfaces/qos-profiles.md).

## Twin pair — Phase 2.A

> **The zone must declare it.** `./scripts/sim --pair` refuses an untwinned zone rather than
> inventing a second side: whether a zone runs as a pair is an L0 fact.
> `model/facility/zones.yaml` ships one zone, `cell_b`, as `twin: {sides: pair}`
> ([ADR-0059](../adr/0059-pair-cell-b-and-leave-cell-a-single.md)), so the command below comes
> up from a clean checkout.
>
> **The counterpart is the physical arm** ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)).
> Without `CITE_ALLOW_HARDWARE=1` the commands below are refused and nothing physical starts:
> `./scripts/program` before it brings anything up, naming the physical side and the opt-in;
> `./scripts/sim --pair` at the counterpart side. With it they drive the real arm. Read *Physical cell — Phase 2.B*
> below first.
>
> **A declaration is not a gate.** Nothing automated brings a pair up: no scenario and no CI
> step does, and what CI drives on `cell_b` is the plant alone (`bringup` twice and
> `program_cycle`).

```bash
./scripts/sim --pair             # both sides, under the supervisor
./scripts/sim --pair --headless  # the same, with no windows
./scripts/sim --zone cell_b --pair --headless  # naming the zone, which only a second zone would require
```

**Launch arguments keep the `key:=value` spelling they have without `--pair`.** A pair takes
fewer of them than one side does, and one it will not take is `side:=` — which side a launch
is, is the supervisor's to decide. An argument a pair does not take is named rather than
ignored.

**What comes up.** Two complete cells, each one exactly the launch above given a different
environment: its own `GZ_PARTITION` and its own `ROS_DOMAIN_ID`, both resolved from the
generated plan. **Every name is byte-identical on both sides** — nodes, topics, actions,
controllers, joints, frames — which is the point
([ADR-0044](../adr/0044-one-ros-domain-per-side-identical-names.md), clause 1) and is why the
side lives in the environment rather than in a name.

**Expect** each side to reach the end of its own gate chain and announce itself, and then one
line saying the pair is up:

```
[plant] [INFO] [launch.user]: CITE_SIDE_READY side=plant zone=cell_b
[counterpart] [INFO] [launch.user]: CITE_SIDE_READY side=counterpart zone=cell_b
[pair] both sides announced readiness; the pair is up
```

**Neither side waits for the other.** They are joined, never sequenced
([ADR-0047](../adr/0047-two-independent-launches-joined-not-sequenced.md)); the order those
two lines arrive in says nothing and carries no meaning.

**The console is two labelled streams.** Every line is prefixed with the side it came from.
That is a real ergonomic cost of running a pair and there is no single-stream form of it.

### Running the real program on the pair

The cell's cycle is the **real xArm 5's own program**
([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md)). Its steps are not written in
Python: `model/programs/xarm5_real_demo.blockly.xml`, the robot's exported UFACTORY Studio
program, is named by the arm's `configuration.program` in L0, read strictly by
`cite_tools.model.blockly` when the plan is generated, and arrives in the bring-up plan's
`programs:` block. `cite_bringup/program/from_plan.py` maps each step onto a `MoveTo` to a named
pose at the program's velocity scaling, a `Grasp` to a width, a dwell in the cell's clock, or a
move of the linear track's carriage. The program is sent once through the twin boundary, so
both arms and both tracks follow it.

**The belt is not part of the program.** The real program has no belt block, so each side's
belt is started on that side's own domain by `python3 -m cite_bringup.program.belt`, never
through the twin boundary.

```bash
./scripts/program                     # bring the pair up, start each side's
                                      # belt on that side, one box per side, one cycle through
                                      # the twin, report where the boxes ended, tear down
./scripts/program --headless --cycles 3
```

Or by hand, on a pair that is already up (`./scripts/sim --pair`):

```bash
./scripts/enter dev python3 -m cite_bringup.program.belt --zone cell_b                # every side's belt at its installed speed
./scripts/enter dev python3 -m cite_bringup.program.belt --zone cell_b --side counterpart --stop
./scripts/enter dev python3 -m cite_bringup.program --zone cell_b --dry-run           # print the steps
./scripts/enter dev python3 -m cite_bringup.program --zone cell_b --cycles 1          # via the twin
./scripts/enter dev python3 -m cite_bringup.program --zone cell_b --via plant         # the plant alone
```

On a pair with a physical side, `./scripts/program` is the supported entry point; do not use
the module as a shortcut. It enforces the same rules (an explicit `--speed-scale`, and the
operator's go-ahead read from its terminal), but `./scripts/program` is what places, checks and
tears down around it.

`python3 -m cite_bringup.program` puts no part on the table and runs no belt; supplying one
part per cycle is the caller's job, which is why `./scripts/program` runs it one cycle at a
time. It refuses to start on an arm whose `RobotState` says it holds a part, because the program
opens the gripper before it closes it. `--via twin` (the default) takes `--target twin|real|sim`
(default `twin`) and asks for the target's mode: `VALIDATED` for twin, `REAL` for the real arm,
none for the simulation. Since ADR-0072, `SIM` routes every goal to the plant alone and `REAL` to
the counterpart alone. Any step that does not succeed stops the program, and so
does Ctrl-C: the goal in flight is cancelled, the track is held where it stands, and the exit
status is non-zero. `./scripts/scenario program_cycle` checks one cycle on the plant.

**Open, and recorded in ADR-0067:** a mode change while the carriages are moving drops later
track commands and sends no stop, so each side finishes the point it already has; and through
the twin the counterpart's custody is not read back. Since ADR-0070, a Ctrl-C holds each
carriage where it stands (a stop on the physical one), and the program waits for the
counterpart's carriage to arrive too (`TrackArrived`).

Past milestones are not run from here: each runs from its own folder under `projects/`, for
example `projects/01-three-arm-event-driven-line/run` — see
[`../../projects/README.md`](../../projects/README.md).

### Operating the pair from the Gazebo window

[ADR-0071](../adr/0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md) adds an
operator panel to the plant side's Gazebo window.

```bash
./scripts/console                          # the simulation alone: plant, boundary, console
CITE_ALLOW_HARDWARE=1 ./scripts/console    # both sides: the simulation and the physical arm
```

**The hardware opt-in decides which sides start**
([ADR-0072](../adr/0072-the-operator-chooses-where-the-signal-goes.md)). Without it the plant
starts alone and prints `real arm not started: CITE_ALLOW_HARDWARE is not 1; simulation target
only`; the boundary opens nothing on the counterpart's domain and refuses every mode but `SIM`,
even with `force`. With it both sides start, as before. The panel shows in the top-right corner of
the plant's 3D view. **Nothing moves until a button is pressed.**

**The target selector** chooses where the signal goes: **Simulation** (`SIM`, the plant alone),
**Real arm** (`REAL`, the physical counterpart alone) or **Twin** (`VALIDATED`, both). Only the
targets the running deployment can serve are offered, and nothing is preselected: Home and Start
program stay disabled until a target is chosen, and the choice is cleared whenever the offered set
or the console changes. The target is sent with every Home and Start program. Each side's "at the
program's start" is shown and measured separately; switching target leaves each side where the
last run left it, and a Twin run needs a Twin Home first after any single-side run that moved one
side.

| Button | What it does | Enabled when |
|---|---|---|
| **Start robot** | On a physical side: holds the twin in SIM at the boundary, asks the operator to confirm the cell is clear (the track may home and move to its start), then initializes the arm as UFACTORY Studio does. On an all-simulated pair it only checks custody. | No request is running (the server also refuses while a terminal program client is on the graph) |
| **Home** | Measures the target's sides against the program's start. If one is away, it asks the operator to confirm (when the target includes the real arm) and brings them there, then measures again. | The robot is started, the console is READY and a target is chosen |
| **Start program** | Measures the target's sides again, then runs N cycles of the real program on the target. When the target includes the real arm, each cycle first asks the operator to place the part by hand; a Simulation run places its part itself and asks nobody anything. | As Home, and every side of the target is at the start |
| **Stop** | Cancels the request in flight, holds each carriage where it stands and asks the twin back to SIM. If the twin cannot return to SIM, the console shows FAULT, and Stop then asks for SIM again. | A request is running, or FAULT with the twin out of SIM on a physical pair |

**The speed selector** preselects 1.0, the program's own speed, and also offers 0.5, 0.25 and 0.1.
A choice below the physical side's floor is disabled when the target includes the real arm. The scale is sent with every Home and every
Start program, and the server never assumes one.

**The confirmation panel** shows the server's exact prompt, which names the target and the physical
sides it will move. The server asks only after holding the
twin in SIM at the boundary and the physical carriage as
stationary, so nothing is forwarded to the physical side while a person is in the cell. While a run
is in progress the console holds the twin's mode (`/cite/twin/hold_mode`): another client's mode
change is refused until the run returns to SIM and releases it. Confirm
answers the prompt; Stop withdraws the request.

**Stop is a software stop on the command path, not an E-stop.** The xArm controller's hardware
E-stop is the only real stop ([`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md)).
Stop does not stop a gripper motion already in progress on the physical arm (ADR-0070 item 4).
After a Stop or a failure nothing homes on its own (ADR-0037). The arms must be homed again before
Start program is accepted.

**One operator surface per pair.** `./scripts/program` never starts a console. While a console
serves the pair, `./scripts/home` and `python3 -m cite_bringup.program` refuse and point at the
panel. The console in turn refuses Start robot, Home and Start program while a terminal program
client (`fixed_program`) is on the graph; Stop and the return to SIM are never refused. Both checks
depend on DDS discovery, so they are advisory and not an interlock (open-work #100). A refused
request's reason appears in the panel's last-error line.

**Run through the console so far:** on the simulation alone (`./scripts/sim --pair --console`
without the opt-in, 2026-10-09), Home and one full cycle of the real program, all 22 steps, then a
Stop mid-cycle that held the arm and required a new Home. **Not yet run:** the Real arm and Twin
targets on the physical arm; the first is the supervised physical run. **The panel has no
`--speed-scale` argument and preselects 1.0:** before the first Home, select **0.1×** in the speed
selector, with the owner at the hardware E-stop, as in "First motion, always: two stages".

### Reaching one side

A shell is on the plant's domain by default — `./scripts/doctor` prints it — so a bare
`ros2 topic list` addresses the plant and finds nothing of the counterpart. To address the
other side, resolve its domain from the plan rather than adding one by hand:

```bash
ZONE=cell_b   # the one zone L0 declares
./scripts/enter dev python3 -c '
import os, sys
from cite_bringup.plan import default_plan_path, domain_base, load, resolve_domain_id
plan = load(default_plan_path(sys.argv[1]))
for side in plan.sides:
    print(side.name, resolve_domain_id(plan, side.name, domain_base(os.environ)),
          side.gz_partition)' "$ZONE"
```

> The zone is an ARGUMENT and not an environment variable, and the reason is in
> `workspace/src/cite_bringup/README.md` under "What this costs you at a terminal":
> `export CITE_ZONE=...` on the host never reaches the container.

Then `ROS_DOMAIN_ID=<that> ros2 node list`, and `GZ_PARTITION=<that> gz topic -l` for the
Gazebo half. **Both are needed and neither substitutes for the other**: a shell with the right
domain and the wrong partition sees the ROS graph and an empty Gazebo transport.

### How a pair fails

A launch that refuses (`BRING-UP FAILED: ...`) exits non-zero, and one interrupted by Ctrl-C or
by the pair supervisor stopping it leaves its exit status as `launch` gives it, with no
`BRING-UP FAILED` line for the interrupt ([ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)).

| What you see | What it means |
|---|---|
| `[pair] X exited N` before any readiness | that side's bring-up failed. Its own diagnosis is above, in that side's stream |
| `[pair] X never announced readiness and never exited` | the ceiling. Not a slow side: every bring-up step either completes or fails, so a side in neither state is waiting on something that will not arrive |
| `[pair] X announced readiness as 'Y'` | that launch was given the wrong `side:=`. The pair is not what it says it is |
| a side ends after the pair is up | the pair ends. A half-pair answers some interfaces and not others, and anything asserting against a pair could pass on one side alone |

**A pair is not a fidelity measurement, and 2.A produces none.** Both sides run the same L0
model and the same solver, so any agreement between them is agreement of a thing with itself.
2.A is the instrument (charter §8).

### What is not built

- **No paired scenario.** ADR-0047 records why the existing mechanism cannot host one —
  `launch_test` with `IncludeLaunchDescription` puts the launch in the test process, which
  holds one context on one domain — and defers what one would look like. `./scripts/scenario`
  addresses the plant.
- **No mirroring, and a divergence metric nothing can read.** `cite_twin` exists and
  publishes `DivergenceMetrics` per asset, only the pair supervisor starts it, and `valid` is
  false in every sample it can produce — one of the
  conjunction's terms is each side's clock deficit within a bound
  [ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md) leaves unset, measured by
  nothing ([ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 3). Mirroring in
  the sense L5 owns it — physical state driving the virtual side — is not implemented at all,
  and ADR-0041's open questions are still open.
- **Real-time factor is not a bring-up condition.** ADR-0043 puts a real-time floor on both
  sides, restated by [ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md) as a
  **capacity** floor of 1.0 measured with the world's throttle lifted plus a bound on the
  **accumulated clock deficit**. Neither threshold is set and nothing in bring-up measures
  either quantity, so a side can be up, slow, and indistinguishable from a healthy one here.
  **A pair that comes up is not a pair that is keeping time.**

## Physical cell — Phase 2.B

> **Built, never run against the arm.** The physical counterpart's side
> ([ADR-0070](../adr/0070-the-physical-arm-is-cell-b-s-counterpart.md)) is tested only
> against fake vendor services. The first run is supervised, at reduced speed, with a person at
> the hardware E-stop. Read [safety-procedures.md](safety-procedures.md) first.

### Preconditions — all of them, every time

1. Risk assessment current. **Not a software artifact.**
2. Physical E-stop tested this session, latency verified.
3. Cell clear, confirmed by a person looking at it.
4. The arm's address in your local, gitignored `.env` as `CITE_XARM_IP` (an IPv4 or IPv6
   address; never committed, never in L0). `.env.example` names the key.
5. A human at the stop, watching.
6. **The physical track is homed and enabled by the operator.** The vendor refuses a move on a
   track that has not found its zero (`on_zero`), and the track adapter never enables the motor
   itself (`auto_enable` is false in L0).
7. **The physical carriage stands where the plant's does**, within the track's goal tolerance.
   The program checks this before it asks you into the cell. It first waits, up to the
   readiness ceiling, until the twin hears the physical carriage's position fresh; a carriage
   never heard in that time refuses the run before the prompt (check the physical side, do not
   enter). A physical carriage heard standing elsewhere refuses the run, naming the position to
   home it to, from outside the cell. If it is heard elsewhere only after you pressed Enter, the twin refuses `VALIDATED`
   for good and the program stops at once; it waits only for what clears by itself (the
   deadman, the arm's enable, fresh state).

Registration ([calibration-and-registration.md](calibration-and-registration.md)) ties the real
cell's frame to the model's. **It is not built.** By owner decision (2026-10-06) it is not
required before the program's joint-space motion, supervised, with the hardware E-stop tested
and in hand; it is required before any Cartesian motion, any claim on the physical side that
depends on the planning scene, and any divergence number
([safety-procedures.md](safety-procedures.md), item 4).

### Sequence

From an **interactive terminal**, because the program asks for input:

```bash
CITE_ALLOW_HARDWARE=1 ./scripts/program --headless --speed-scale 0.1
```

The opt-in is read from the shell first, then from the repository-root `.env`, and is `0` when
neither sets it; `1` in `.env` arms every physical bring-up from this checkout. On a physical side,
`--speed-scale` is required, and it is checked before anything starts. It also has a floor:
below it, the program's slowest track slide would be slower than the track adapter can carry
out. The floor is derived, not declared: `cite_bringup.program.sides.minimum_speed_scale` asks
the adapter's own rule (`cite_hardware.mapping.slowest_speed_mps`) with its generated
parameters.

**What happens:**
1. The plant (Gazebo) and the physical side come up.
2. The physical side starts its deadman first, then the vendor driver, and holds the arm
   stopped. **Its readiness token means held, not enabled.**
3. The twin boundary starts, and its heartbeat makes the deadman healthy. The deadman then
   enables the arm. The program waits until the boundary reports the side ready, with the arm
   enabled and fresh state.
4. Before each run the program reads the twin's mode. Only once it reads SIM does it ask you
   to place the part on the physical table by hand and press Enter; anything else refuses
   without asking. **The arm is enabled and still while you do.** At the end of each run the
   program puts the twin back in SIM; if that fails, the run fails and the cycle loop ends. No
   box is spawned and no belt runs on the physical side.
5. A track step first asks every side whether its carriage is already at the target. If the
   plant's is and the physical one is not, the step fails and tells you to home that carriage;
   the physical carriage is never left unchecked. A track step also fails if the twin is in a
   mode that forwards no track command (for example SIM mid-run), rather than counting as
   arrived.
6. Before the first cycle, and in `./scripts/home`, the physical arm is initialized first,
   every time. Initializing is what you would do in UFACTORY Studio (`InitializeAsset`, served
   by `cite_hardware`'s initializer from values generated out of L0): the track motor and the
   gripper are enabled, the track is homed only if it has not found its zero, and the carriage
   is brought to the program's first track target at L0's `initialize_speed_mps` only if it is
   not there (a track on its zero has found its zero; it need not stand at it). The homing and
   that move move the carriage, behind the deadman's gate. Ctrl-C or SIGTERM during the
   initialization sends the vendor's track stop before the program exits. Then the start is
   measured: every arm joint within the arm's goal tolerance of the program's `reset` pose and
   every carriage within the track's goal tolerance of 0 m, on every side; a physical side
   counts only with fresh positions. If every side is there, nothing more moves. Otherwise both
   sides are homed through the twin in VALIDATED with `SetMode.homing`, and the start is
   measured again. Any failure stops with where each side stands; nothing is retried. On a pair
   that is already up, `./scripts/home --speed-scale 0.1` does the same without restarting
   anything.
7. One cycle of the real program then runs on both arms, at the scale you gave.
8. On the physical side a close expecting a part is executed, not judged (owner decision
   2026-10-06, ADR-0070): it succeeds once the gripper command completes, the reached width is
   logged, and only a relay refusal, vendor abort or timeout fails the step.
9. Likewise an arm motion on the physical side that ends at the trajectory's last point succeeds
   even if the controller did not report the goal met (owner decision 2026-10-06, ADR-0070);
   the classification is logged, and every other abort, timeout or cancel still fails the step.

**If the arm moves when nothing is commanded:** E-stop immediately. That is a defect and a
Critical safety finding.
**Ctrl-C** cancels the goal in flight on both sides and holds each carriage where it stands.
The supervisor then stops the boundary first, so the deadman trips and stops the arm, and then
brings each side down.
**After a deadman trip** the trip latches, and the arm stays stopped until an operator
deliberately resets it. The recovery sequence is in `workspace/src/cite_hardware/README.md`.
Restarting the whole run is also a reset.

### First motion, always: two stages

Reduced speed and a human on the stop, in both stages.

1. **Observation, no program.** Bring the pair up and command nothing:

   ```bash
   CITE_ALLOW_HARDWARE=1 ./scripts/sim --pair --headless
   ```

   Watch the deadman reach HEALTHY with `arm_enabled`, the vendor deactivate and then
   reactivate the arm's controllers (the joint-state broadcaster included), and the physical
   track's position being published. The arm should not move. Then Ctrl-C.
2. **One cycle.** Only after stage 1 showed nothing unexpected:

   ```bash
   CITE_ALLOW_HARDWARE=1 ./scripts/program --headless --speed-scale 0.1 --cycles 1
   ```

Raise the scale only after a run that showed nothing unexpected.

### First full physical cycles (2026-10-08)

On `main` at `0ceb80d`, supervised, owner at the hardware E-stop, over the lab Wi-Fi:

- **What made the difference** was initializing the linear track as the operator does in
  UFACTORY Studio (`InitializeAsset`: motor and gripper enabled, homed when it has not found its
  zero) and bringing both arms to the program's start before the cycle (measure, home if away,
  measure again). Before it, track moves were refused by the vendor (code 82, not on zero).
- **`--speed-scale 0.1`:** initialize, home, then all 22 steps on both arms: pick, track to
  650 mm with the part, place, track back, arm to zero. The run before it stopped on C31 at
  the descent to the part; the owner traced it to a misplaced part (real contact), so the
  controller was right.
- **`--speed-scale 1.0` (the program's own speed):** initialize (already at the start, no
  homing move) and all 22 steps on both arms.

### First physical runs (2026-10-06)

Supervised, owner at the hardware E-stop, `--speed-scale 0.1`, over the lab Wi-Fi. Observations,
not a campaign:

- **Observation bring-up (`./scripts/sim --pair`)**: the deadman held the arm at STOP, the hold
  gate passed, the boundary's heartbeat made the deadman HEALTHY and the arm was enabled; the
  physical joint states matched the receive-only read of 2026-10-05. Teardown tripped the
  deadman and stopped the arm.
- **The hold gate's single STOP was lost once** (sent before its client matched); fixed by
  waiting for the match and re-sending (commit `6e7a733`).
- **One signal drove both arms**: the real program's first ten steps ran on the physical arm
  and in Gazebo together (track to 0 mm confirmed on both sides, two joint moves, gripper open,
  descend). The physical gripper closed on the real box at a reported 62.8 mm, outside the
  Gazebo-tuned accept band; by owner decision (ADR-0070) the physical side's grip and arm
  arrival are executed, not judged.
- **Later runs stopped on the xArm's own collision detection** (`C31: Collision Caused Abnormal
  Joint Current`) about two seconds into the first move, with no reported contact. The open
  question is the cause: real contact, or the 150 Hz servo stream over Wi-Fi (the control loop
  reads late about once a second). Recorded in [`../open-work.md`](../open-work.md) #98.
- **Subsequent paired attempt at `--speed-scale 0.1 --cycles 1` (2026-10-06)**, before the
  physical arm was initialized and homed by the program (commits `5fd724c`, `2cec2a1`): after the operator
  confirmed session checks and no motion during observation bring-up, steps 1–12 completed
  through the twin boundary. Step 13, the track transfer to 650 mm, repeatedly returned vendor
  code 82 on the physical side: the track adapter of that run re-sent the refused segment on
  every position poll, and a refusal now ends the move and stops the carriage instead
  (`cite_hardware/track_adapter.py`). The pinned SDK calls this `LINEAR_MOTOR_NOT_INIT`: its track
  status read succeeded but `on_zero` was not set. Position zero alone did not establish
  homing readiness. The run was cancelled with Ctrl-C; the program confirmed SIM, stopped the
  simulated belt and brought the pair down. No full cycle completed and no homing or reset was
  commanded. The physical grip command reported 62.5 mm; the operator confirmed that the
  arm picked up and lifted the part and still held it after shutdown. The original log is
  `workspace/log/program/pair.9XfsGM.log` in the
  container log volume. Both sides showed the known MoveIt teardown crash (#96).

### Step 1 of the 2.B plan: reading the arm without moving it (2026-10-05)

Before any software spoke to the arm, its joint angles were read **receive-only** from the
controller's report port (TCP 30001). No vendor driver ran and no byte was sent; the read
succeeded. The vendor driver was not used for this, because it is not read-only:
- its initialisation calls `clean_error` when it sees a servo error;
- its destructor writes `set_mode(POSE)`.

What the vendor driver offers, read from its source at the pinned `xarm_ros2`:
- **The track** is not a `ros2_control` joint. It is driven only through `xarm_api` services
  (`set_linear_motor_pos`, `get_linear_motor_pos`, `set_linear_motor_stop`, …), each off unless
  enabled.
- **The gripper** is not a `ros2_control` joint on the physical plugin either. It is the
  vendor's `GripperCommand` action, in drive-joint units, plus `get_gripper_position` in
  pulses.

These are the same calls the program's `set_line_track` and `gripper_set` blocks make on the
controller. ADR-0070 is built on them.

## Shutdown

```
Ctrl-C   # the launch handles ordered shutdown
```

**Expect:** a running program's goal in flight is cancelled, in-flight skills cancel cleanly,
controllers deactivate with the robot in a safe state, no orphaned processes.

**Verify:**
```bash
pgrep -fl "gz sim|ros2|controller_manager"    # expect nothing
```

**If processes remain:** kill them before the next bring-up. An orphaned `gz sim` holds
ports and names, and the next bring-up fails pointing nowhere near the cause.
