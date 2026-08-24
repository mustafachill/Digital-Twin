# Recording and replay

- **Status:** `DESIGNED` — recording is usable as soon as there is something to record; the historian is Phase 4.
- **Related:** [`../architecture/L6-data-and-telemetry.md`](../architecture/L6-data-and-telemetry.md)

## Why record

Three distinct reasons, and they want different things:

| Reason | Wants |
|---|---|
| **Test evidence** | Full fidelity, short, kept only while the finding is open |
| **Diagnosis** | Full fidelity of one specific run, kept until resolved |
| **Trending** | Downsampled, continuous, kept for a long time |

The first two are bags. The third is the historian. Trying to serve all three from one
mechanism produces something that serves none.

## Recording a run

```bash
ros2 bag record -s mcap -o runs/$(date +%Y%m%d-%H%M%S) \
  /cite/cell_a/arm_1/joint_states \
  /cite/line/state \
  /cite/twin/divergence \
  /cite/twin/mode
```

MCAP, not the default storage: efficient, self-describing, and readable by Foxglove and by
external tooling.

**Record deliberately.** Recording every topic at full rate perturbs the system it is
observing — cycle time changes when recording is on, and then the recording is of a
different system than the one you meant to study.

## Every recording carries its context

A measurement without context is not comparable to any other measurement. Record, alongside
the bag:

| Field | Why it matters |
|---|---|
| Facility model version | A run against yesterday's layout is not comparable to today's |
| Software version (commit) | Behaviour changes between commits |
| Operating mode | An L1 run and an L2 run mean different things |
| Physics seed (simulation) | Reproducibility |
| Registration transform (hardware) | Divergence is meaningless without it |

This is what makes "compare this week's cycle time to last month's" a valid question rather
than a misleading one.

## As test evidence

The `tester` agent captures a bag for any time-dependent finding. "The handoff failed" is
an assertion; a bag showing the exact message sequence and timing is evidence, and it is
what lets `fixer` find the cause rather than guess at it.

Keep these only while the finding is open. They are working artifacts, not archives.

## Replay

```bash
ros2 bag play runs/20260824-143000 --clock
```

Replay drives the simulator from recorded data, which is what makes "why did the line stop
on Tuesday" answerable at all.

**Verify replay determinism** before drawing conclusions from it: replay the same bag twice
and confirm the same outcome. If replay diverges from the original run, the divergence is
itself the finding — something in the system depends on state the bag does not capture.

## Trending — Phase 4

The historian holds downsampled continuous metrics: throughput, cycle time, divergence,
fault rate. Long horizon, low fidelity.

Diagnose from the bag; trend from the historian. **Downsampling hides transients**, so a
fault visible in a bag can be invisible in a trend. When they disagree, the bag is right.

## Failure modes

| Failure | How it shows | What to do |
|---|---|---|
| Recording perturbs the system | Cycle time differs with recording on | Record fewer topics; measure the overhead |
| Missing context | Runs compared that are not comparable | Stamp context at record time |
| Unbounded retention | Disk fills, eventually mid-run | Retention policy; monitoring |
| Replay diverges from the original | Conclusions drawn from replay are wrong | Investigate — this is a finding, not noise |
| Recorded untyped data | Bag uninterpretable later | [ADR-0010](../adr/0010-typed-ros-interfaces.md) |
