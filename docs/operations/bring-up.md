# Bring-up

- **Status:** `PARTIAL` — the simulated path below works and is what `./scripts/scenario bringup`
  drives. Of the last two stages of the step-4 sequence, **twin sync is not started by any
  bring-up** — `cite_twin` now exists, and nothing in `simulation.launch.py`, `./scripts/sim`
  or any scenario starts it; it also refuses to start against the shipped model, which
  declares one side — and **orchestration is off by default**: the line coordinator
  starts only with `line:=true`, because it takes exclusive hold of every arm's skills, so a
  default bring-up leaves the arms free for an operator or a scenario. The physical path is
  Phase 2 and has never been run.
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
./scripts/sim --headless line:=true    # and let L4 drive every station
```

**`line:=true` hands the cell over.** The coordinator claims each arm's skill server, and a
skill server admits one goal at a time, so anything else that sends a goal — an operator, a
diagnostic, a scenario — is refused by a server that is busy. Bring the line up this way only
when you mean to watch it run.

**Expect:** bring-up proceeds through the ordered sequence, each step gated on the previous
one reporting active:

```
simulator → descriptions → controller manager → controllers
          → MoveIt → skills → twin sync → orchestration
```

**If a step fails:** bring-up stops with a diagnosis naming the step. It does not continue
degraded — that is the point of lifecycle sequencing.

### 5. Verify

```bash
ros2 control list_controllers          # all active
ros2 topic hz /cite/cell_a/arm_1/joint_states
ros2 action list | grep cite           # skill servers present
# /cite/twin/mode has NO publisher in this bring-up: cite_twin is not started
# by it, and needs a zone declaring `twin: {sides: pair}` to start at all.
```

The simulation-fidelity aids cross into ROS through one `ros_gz_bridge` process, and the
beams are what start a station:

```bash
ros2 node list | grep gz_bridge                             # exactly one
ros2 topic echo /cite/cell_a/beam_pick/detection_level      # the raw level, std_msgs/Bool
ros2 topic echo /cite/cell_a/beam_pick/detection            # the typed DetectionEvent
ros2 topic pub --once /cite/cell_a/conveyor_1/command \
    std_msgs/msg/Float64 "{data: 0.15}"                     # only with the line NOT running
```

**If a beam's level ticks and its `detection` topic is silent:** the detection server is not
running or is watching a different name. The two are deliberately different topics — the raw
`gz.msgs.Boolean` is landed on `…/detection_level` and only `cite_skills`' detection server
publishes the typed event on `…/detection`.

**Do not command a belt by hand while the line is running.** L4 owns that setpoint
([ADR-0032](../adr/0032-index-the-belt.md)); a second publisher fights it, and a belt running
under a part a station is reaching for puts the part on the floor.

**If the belts never start and nothing reports an error:** check the log for
`line_orchestrator` announcing that it re-sent a setpoint to a subscriber that appeared after
the belt was last commanded. The start-up command is published from the same callback that
creates the publishers, when no subscriber has been matched yet — **reliable QoS is a promise
to *matched* subscribers, so that first message is delivered to nobody** however long the
bridge has been up. Delivery depends on the matched-subscriber event, which is where to look
if an RMW other than the default is in use. This failed silently for ten commits and the
symptom was a line that simply never moved; the measurement is in the 2026-08-27 correction
on [ADR-0032](../adr/0032-index-the-belt.md).

**If a controller is inactive:** check that its joint names match the description
(`./scripts/validate-model`). The spawner error names the spawner, not the mismatch — this
is the single most time-consuming false trail in ROS 2 controller bring-up.

**If a topic exists but `hz` reports nothing:** suspect QoS before anything else. See
[`../interfaces/qos-profiles.md`](../interfaces/qos-profiles.md).

## Twin pair — Phase 2.A

> **The zone must declare it.** `./scripts/sim --pair` refuses an untwinned zone rather than
> inventing a second side: whether a zone runs as a pair is an L0 fact, `model/facility/zones.yaml`
> ships `twin: {sides: single}`, and the shipped model is not paired.

```bash
./scripts/sim --pair                   # implies headless; both sides, under the supervisor
./scripts/sim --pair line:=true        # and let L4 drive every station, on both sides
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
[plant] [INFO] [launch.user]: CITE_SIDE_READY side=plant zone=cell_a
[counterpart] [INFO] [launch.user]: CITE_SIDE_READY side=counterpart zone=cell_a
[pair] both sides announced readiness; the pair is up
```

**Neither side waits for the other.** They are joined, never sequenced
([ADR-0047](../adr/0047-two-independent-launches-joined-not-sequenced.md)); the order those
two lines arrive in says nothing and carries no meaning.

**The console is two labelled streams.** Every line is prefixed with the side it came from.
That is a real ergonomic cost of running a pair and there is no single-stream form of it.

### Reaching one side

A shell is on the plant's domain by default — `./scripts/doctor` prints it — so a bare
`ros2 topic list` addresses the plant and finds nothing of the counterpart. To address the
other side, resolve its domain from the plan rather than adding one by hand:

```bash
./scripts/enter dev python3 -c '
import os
from cite_bringup.plan import default_plan_path, domain_base, load, resolve_domain_id
plan = load(default_plan_path())
for side in plan.sides:
    print(side.name, resolve_domain_id(plan, side.name, domain_base(os.environ)),
          side.gz_partition)'
```

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
  publishes `DivergenceMetrics` per asset, but no bring-up starts it, it refuses a
  single-sided zone, and `valid` is false in every sample it can produce — one of the
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
  deficit** measured with it in force. Neither of ADR-0049's two thresholds is set and nothing
  in the tree measures either quantity, so the floor is **not met** under either shape. The
  paired figure measured by hand on 2026-08-30 is in ADR-0043's correction of that date; it was
  taken with the throttle in force, so it is a real shortfall and not a capacity number. In
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
