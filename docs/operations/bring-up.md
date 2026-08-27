# Bring-up

- **Status:** `PARTIAL` — the simulated path below works and is what `./scripts/scenario bringup`
  drives. Of the last two stages of the step-4 sequence, **twin sync does not exist** (there
  is no `cite_twin` package) and **orchestration is off by default**: the line coordinator
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
ros2 topic echo /cite/twin/mode --once # expect SIM
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

**If a controller is inactive:** check that its joint names match the description
(`./scripts/validate-model`). The spawner error names the spawner, not the mismatch — this
is the single most time-consuming false trail in ROS 2 controller bring-up.

**If a topic exists but `hz` reports nothing:** suspect QoS before anything else. See
[`../interfaces/qos-profiles.md`](../interfaces/qos-profiles.md).

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
