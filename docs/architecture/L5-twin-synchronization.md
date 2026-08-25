# L5 — Twin synchronization

- **Status:** `DESIGNED` — no node implements any of this, and `cite_twin` does not exist.
  Phase 2. The typed interfaces are in place and frozen against the contract baseline —
  `TwinMode`, `SetMode`, `DivergenceMetrics`, `ModelVersion` — and every asset instance in
  L0 carries a `registration` block, currently `unregistered` for all three arms. Nothing
  consumes any of it.
- **Related:** [ADR-0011](../adr/0011-twin-maturity-model-and-modes.md), [ADR-0005](../adr/0005-ros2-control-sim-real-boundary.md), [standards-alignment.md](standards-alignment.md)

## Responsibility

**This is the layer that makes the system a twin rather than a simulation.** It owns the
relationship between the physical cell and its model: which direction information flows,
how the two coordinate frames correspond, and — most importantly — how far apart they are.

## Owns

- The operating **mode** of the system.
- State mirroring: physical → virtual.
- Command routing: which mode sends what to which side.
- **Calibration and registration** — the correspondence between the real cell's coordinate
  frame and the model's.
- The **twin monitor**: continuous divergence measurement and publication.

## Does not own

- Control. L5 routes and observes; L2 executes.
- Deciding what work to do — L4.
- Storing history. L5 publishes metrics; L6 records them.

## Interfaces

**Consumes:** joint and controller state from L2 on both paths; L4 line state for
event-level comparison.

**Exposes:** current mode, mode-transition service, divergence metrics, registration
transform, and twin health.

## Design

### Operating modes

| Mode | Physical | Virtual | Level |
|---|---|---|---|
| `SIM` | idle | commanded | L0 |
| `REAL` | commanded | idle | — |
| `SHADOW` | commanded | follows physical state | L1 |
| `VALIDATED` | commanded | commanded in parallel; divergence measured; virtual does not actuate | L2 |
| `CLOSED_LOOP` | commanded after virtual validation gates it | validates first | L3 |

Mode is **explicit, observable at runtime, and gated.** It is never reachable by a default
parameter, an environment variable, or a launch-argument default. A system that can enter
`REAL` because someone forgot to pass an argument is a system that will.

`safety-auditor` audits every transition. `SIM` → `REAL` and entry to `CLOSED_LOOP` are the
two that matter most.

### Divergence measurement is the point

P8: *the twin measures itself.* An unmeasured claim of fidelity is not a claim.

| Metric | What it catches |
|---|---|
| Joint position RMSE | Kinematic and control-tracking mismatch |
| TCP pose error | Accumulated kinematic error where it actually matters |
| Velocity profile deviation | Dynamics and inertia modelling errors |
| Cycle-time delta | Systematic timing and throughput mismatch |
| Event-timing deviation | Sensor and orchestration mismatch |

Each is published continuously, recorded by L6, and trended by L7. **"Our twin is
accurate" is not a sentence this project is allowed to write without a number next to it.**

### Registration is what makes measurements transferable

Without registration the model is a nice picture. With it, a measurement in the model
predicts a measurement in the building.

Registration establishes the transform between the surveyed physical origin and the model
origin, ties scanned geometry ([L1](L1-description-and-assets.md)) to that frame, and is
**re-verified**, not assumed permanent — floors settle, fixtures get bumped, robots get
remounted. A drifted registration presents as a slowly growing divergence with no software
cause, and is one of the harder faults to diagnose without this metric.

### Time

Mirroring across two clocks is meaningless without a shared time base. Simulation uses
`use_sim_time`; hardware uses wall time; comparing them requires an explicit, documented
correspondence and clock synchronisation (NTP at minimum) on the physical side. A mixed
time base produces divergence numbers that look plausible and mean nothing.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Mode reachable by default | Real arm moves during what someone thought was a simulation | `safety-auditor` — Critical |
| Registration drift | Divergence grows with no software change | Trend monitoring; periodic re-survey |
| Clock skew | Divergence metrics plausible but wrong | Explicit time-base check in the monitor |
| Mirroring lag treated as divergence | Model blamed for a network problem | Latency measured and reported separately |
| Divergence published but never watched | The twin is "accurate" because nobody looked | L7 trending; alert thresholds |
| Fidelity claimed without a metric | The project's core claim becomes unfounded | P8; review |

## Open questions

- **Divergence thresholds.** What error is acceptable is an empirical question that needs
  real hardware. Until Phase 2 we can only build the measurement, not set the bound.
- **Mirroring transport.** Whether physical state reaches the virtual model over plain ROS
  2 across the lab network, or needs a dedicated bridge with its own QoS and latency
  budget.
- **What `CLOSED_LOOP` validation actually checks** before permitting physical execution.
  This is the crux of L3-level maturity and deserves its own ADR when Phase 5 approaches.
- **Multiple physical assets, partially twinned.** With one real arm and two simulated,
  what does a facility-level divergence number even mean? Probably per-asset metrics with
  no aggregate — but it needs deciding rather than defaulting.
