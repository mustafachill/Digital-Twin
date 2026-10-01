# Bring-up

- **Status:** `PARTIAL` — the simulated path below works and is what `./scripts/scenario bringup`
  drives. Of the last two stages of the step-4 sequence, **twin sync is started by the paired
  bring-up and by nothing else** — `cite_twin` is started by `./scripts/sim --pair`
  ([ADR-0057](../adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md)) and appears in
  no launch file and no scenario, so a solo bring-up starts no L5; it refuses a zone that
  declares one side, and `cell_b`, the one zone L0 declares, is paired since 2026-09-18
  ([ADR-0059](../adr/0059-pair-cell-b-and-leave-cell-a-single.md)) — and **orchestration is not
  in the main tree**: the line coordinator, the detection server and `line:=true` left it on
  2026-10-01 ([ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)). The three-arm line is run from
  [`../../projects/01-three-arm-event-driven-line/`](../../projects/01-three-arm-event-driven-line/README.md).
  The physical path is Phase 2 and has never been run.
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
          → MoveIt → skills → twin sync → orchestration
```

The last two stages are the target sequence: a solo bring-up stops at skills, twin sync is the
pair supervisor's (below), and orchestration is not in the main tree.

**If a step fails:** bring-up stops with a diagnosis naming the step. It does not continue
degraded — that is the point of lifecycle sequencing.

### 5. Verify

```bash
ros2 control list_controllers          # all active
ros2 topic hz /cite/cell_b/picker/joint_states
ros2 action list | grep cite           # skill servers present
# /cite/twin/mode has NO publisher in this bring-up: cite_twin is not started
# by it, and needs a zone declaring `twin: {sides: pair}` to start at all.
```

The simulation-fidelity aids cross into ROS through one `ros_gz_bridge` process:

```bash
ros2 node list | grep gz_bridge                                 # exactly one
ros2 topic echo /cite/cell_b/infeed_beam/detection_level        # a beam's raw level, std_msgs/Bool
ros2 topic pub --once /cite/cell_b/transfer_belt/command \
    std_msgs/msg/Float64 "{data: 0.15}"                         # the belt, by hand
```

The beams still stand in `cell_b`'s world and their levels are still bridged, but **nothing in
the main tree reads them**: the detection server that turned a level into a typed event on
`…/detection` left with the line (ADR-0069). The topic names are the plan's — read
`workspace/src/cite_generated/bringup/cell_b_plan.yaml` rather than this block.

**If a belt setpoint seems never to arrive:** reliable QoS is a promise to *matched*
subscribers, so a setpoint published before the bridge's subscriber matched is delivered to
nobody, however long the bridge has been up. The line's belt owner failed this way silently for
ten commits; the measurement is in the 2026-08-27 correction on
[ADR-0032](../adr/0032-index-the-belt.md), and the rule is in
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
> up from a clean checkout. It said `cell_a` was shipped `single` and refused until that zone
> left L0 on 2026-10-01 (ADR-0069).
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

### Running the fixed program on the pair

The cell's default cycle is the **real xArm 5's own program**
([ADR-0067](../adr/0067-the-real-program-drives-the-twin-on-a-track.md), which continues
[ADR-0066](../adr/0066-run-the-cell-from-a-fixed-program.md)). Its steps are not written in
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
./scripts/program                     # bring the pair up without the line, start each side's
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

`python3 -m cite_bringup.program` puts no part on the table and runs no belt; supplying one
part per cycle is the caller's job, which is why `./scripts/program` runs it one cycle at a
time. It refuses to start on an arm whose `RobotState` says it holds a part, because the program
opens the gripper before it closes it. `--via twin` (the default) first asks for `VALIDATED`; in
`SIM` the boundary refuses every goal. Any step that does not succeed stops the program, and so
does Ctrl-C: the goal in flight is cancelled, the track is held where it stands, and the exit
status is non-zero. `./scripts/scenario program_cycle` checks one cycle on the plant.

**Open, and recorded in ADR-0067:** the track has no hardware path; a mode change while the
carriages are moving drops later track commands and sends no stop, so each side finishes the
point it already has; and through the twin the counterpart's track position and custody are
not read back.

**The beam-triggered line is not in the main tree** ([ADR-0069](../adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)). It ran single-sided on `cell_a`,
and never on `cell_b` after ADR-0067, whose transfer station declares no place frame because the
belt's infeed is out of reach at track position 0. The previous behaviour — taught poses and a timed
belt run through the twin (ADR-0066) — is kept runnable in
[`../../projects/02-fixed-program-pair/`](../../projects/02-fixed-program-pair/README.md), and
the three-arm line in
[`../../projects/01-three-arm-event-driven-line/`](../../projects/01-three-arm-event-driven-line/README.md).

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
  publishes `DivergenceMetrics` per asset, but only `./scripts/sim --pair` starts it, it
  refuses a single-sided zone, and `valid` is false in every sample it can produce — one of the
  conjunction's terms is each side's clock deficit within a bound
  [ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md) leaves unset, measured by
  nothing ([ADR-0050](../adr/0050-what-crosses-the-twin-boundary.md) decision 3). Mirroring in
  the sense L5 owns it — physical state driving the virtual side — is not implemented at all,
  and ADR-0041's open questions are still open.
- **Real-time factor is not a bring-up condition.** ADR-0043's half 2 puts a real-time floor on
  both sides and **nothing in bring-up measures it**, so a side can be up, slow, and
  indistinguishable from a healthy one here. **Do not cite half 2's original wording as the
  requirement**: it was restated on 2026-08-31 by
  [ADR-0049](../adr/0049-measure-the-real-time-floor-as-capacity.md) as a **capacity** floor of
  1.0 measured with the world's throttle lifted, plus a bound on the **accumulated clock
  deficit** measured with it in force. Neither of ADR-0049's two thresholds is set, and nothing
  in `workspace/`, `tools/`, `tests/` or `scripts/` measures either quantity during a run, so
  the floor is **not met** under either shape and nothing in bring-up would notice. The
  paired figure measured by hand on 2026-08-30 is in ADR-0043's correction of that date; it was
  taken with the throttle in force, so it is a real shortfall and not a capacity number. A
  capacity number now exists, for a named machine, in
  [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md);
  it was taken by that campaign's own frozen harness, which nothing here starts. In
  either shape, **a pair that comes up is not a pair that is keeping time.**

## Physical cell — Phase 2

> **Not valid yet.** No hardware interface exists. This is the designed procedure, recorded
> so that Phase 2 implements against it rather than inventing it under time pressure.

### Preconditions — all of them, every time

1. Risk assessment current. **Not a software artifact.**
2. Physical E-stop tested this session, latency verified.
3. Cell clear, confirmed by a person looking at it.
4. Registration current — see [calibration-and-registration.md](calibration-and-registration.md).
5. A human at the stop, watching.

### Sequence

```bash
export CITE_ALLOW_HARDWARE=1        # deliberate, never in a shell profile
./scripts/enter hardware
./scripts/sim --mode real           # `--mode` is not implemented yet — Phase 2
```

**Expect:** the hardware interface connects; controllers activate with the arm stationary;
mode reports `REAL`.
**If the arm moves during bring-up:** E-stop immediately. Motion during bring-up is a
defect, never expected, and is a Critical safety finding.

### First motion, always

Reduced speed. A human on the stop. A single short motion before anything else.

## Shutdown

```
Ctrl-C   # the launch handles ordered shutdown
```

**Expect:** orchestration stops accepting work, in-flight skills cancel cleanly,
controllers deactivate with the robot in a safe state, no orphaned processes.

**Verify:**
```bash
pgrep -fl "gz sim|ros2|controller_manager"    # expect nothing
```

**If processes remain:** kill them before the next bring-up. An orphaned `gz sim` holds
ports and names, and the next bring-up fails pointing nowhere near the cause.
