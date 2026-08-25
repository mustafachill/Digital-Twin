# L6 — Data and telemetry

- **Status:** `DESIGNED` — nothing built, and `cite_telemetry` does not exist. Phase 4,
  with recording used earlier as test evidence. The state messages this layer would record
  (`RobotState`, `LineState`, `ConveyorState`, `SafetyState`) are defined and frozen against
  the contract baseline; no node publishes them.
- **Related:** [ADR-0010](../adr/0010-typed-ros-interfaces.md), [L5](L5-twin-synchronization.md), [L7](L7-presentation.md)

## Responsibility

L6 turns a running system into a record that can be queried, replayed, and trended, and
defines the boundary at which this project's data meets the outside world.

## Owns

- The telemetry schema: what is recorded, at what rate, with what identity.
- Recording — `rosbag2` with MCAP storage.
- The historian: long-term time-series storage, retention, and query.
- Replay of a recorded run into the simulator.
- External protocol bridges (OPC UA, MQTT) — **deferred**, but the boundary is defined here.

## Does not own

- Producing the data. Every metric originates in the layer that owns it; L6 records.
- Displaying it — L7.
- Deciding anything from it. Analysis is a consumer, not this layer.

## Interfaces

**Consumes:** typed messages from every layer — joint and controller state (L2), skill
results (L3), line and throughput state (L4), divergence and mode (L5).

**Exposes:** recorded bags, a historian query interface, replay control, and the external
integration boundary.

## Design

### Recording is test evidence before it is a data platform

Long before the historian exists, `rosbag2` recording earns its place: the `tester` agent
captures a bag as evidence for any time-dependent finding. "The handoff failed" is an
assertion; a bag showing the exact message sequence is evidence.

MCAP is the storage format — efficient, self-describing, and readable by external tooling
including Foxglove. Because every interface is typed
([ADR-0010](../adr/0010-typed-ros-interfaces.md)), a bag recorded today is still
interpretable years from now without the code that produced it. A bag full of stringified
dicts would not be.

### Every record carries its context

A measurement without context is not comparable to any other measurement. Every recording
is stamped with:

| Field | Why |
|---|---|
| Facility model version | A run against yesterday's layout is not comparable to today's |
| Software version | Behaviour changes between commits |
| Operating mode | An L1 run and an L2 run mean different things |
| Physics seed (simulation) | Reproducibility |
| Registration transform (hardware) | Divergence is meaningless without it |

This is the mechanism that makes "compare this week's cycle time to last month's" a valid
question rather than a misleading one.

### Two storage tiers

| Tier | Holds | Horizon |
|---|---|---|
| Bags (MCAP) | Full-fidelity recordings of specific runs | Selective; kept for runs that matter |
| Historian | Downsampled continuous metrics — throughput, cycle time, divergence, faults | Long, continuous |

Full-fidelity recording of everything, forever, is not affordable and is not useful.
Trends need the historian; diagnosis needs the bag from the run in question.

### Replay closes the loop

A recorded run can be replayed into the simulator. This is what makes "why did the line
stop on Tuesday" answerable at all, and it is a prerequisite for the L4-level predictive
work in Phase 5 — a what-if engine is a replay engine with modified inputs.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Untyped data recorded | Bag is uninterpretable later | [ADR-0010](../adr/0010-typed-ros-interfaces.md); `reviewer` |
| Missing context stamps | Recordings compared that are not comparable | Schema requirement; replay validation |
| Recording load perturbing the system | Cycle time changes when recording is on | `performance-engineer` |
| Unbounded retention | Disk exhaustion, eventually mid-run | Retention policy; monitoring |
| Historian downsampling hiding transients | A fault visible in the bag is invisible in the trend | Documented downsampling; bag-first diagnosis |
| Replay diverging from the original run | Replay conclusions are wrong | Determinism check against the original |

## Open questions

- **Which historian.** InfluxDB and TimescaleDB are both plausible. Deferred to Phase 4;
  the telemetry schema is designed so the choice does not leak upward.
- **Retention policy.** Cannot be set sensibly before real data volumes are known.
- **Whether replay drives the twin or only the simulator.** Replaying into a `SHADOW`-mode
  twin would allow comparing a past physical run against today's model — valuable for
  detecting model drift, and non-trivial.
- **Where the external protocol boundary sits.** Whether OPC UA exposes L4 line state
  directly or a curated subset. A curated subset is almost certainly right, but it needs an
  ADR when the integration is real.
