# Bring-up

- **Status:** `DESIGNED` — the simulated path is buildable once Phase 1.C lands; the physical path is Phase 2.
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
./scripts/sim              # GUI, Linux only
./scripts/sim --headless   # anywhere
```

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
