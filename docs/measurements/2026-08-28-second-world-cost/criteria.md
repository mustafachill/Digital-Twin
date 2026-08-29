# Criteria — what a second simulation costs, and whether two can coexist

- **Campaign:** `2026-08-28-second-world-cost`
- **Written:** 2026-08-28, **before the first trial ran.** Frozen at the commit that
  introduces this file (campaign convention, `../README.md`).
- **Question this exists to answer:** Phase 2.A will run the plant and its virtual
  counterpart as two independent simulations. Nobody knows what the second one costs, or
  whether two can coexist on one host at all. An architect's design is blocked on that.
- **Related:** [L5](../../architecture/L5-twin-synchronization.md),
  [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  [ADR-0011](../../adr/0011-twin-maturity-model-and-modes.md),
  charter section 4 (P7, P8)

---

## 0. The rule this campaign is written under, and it governs every number below

**The development host is not the target machine.** It is a macOS laptop running Docker
Desktop's Linux VM with no GPU passthrough, and the project owner has said so. An absolute
real-time factor measured here is a fact about this laptop and transfers to nothing.

So every result in this campaign is filed under exactly one of three headings, and the
heading decides what may be done with it:

| Heading | What it is | How far it transfers |
|---|---|---|
| **FUNCTIONAL** | a yes/no about whether a mechanism works | **completely.** Two processes either interfere or they do not, and that does not depend on clock speed |
| **RATIO** | a cost expressed relative to another cost measured in the same conditions | **well.** The constant of proportionality cancels; what survives is the shape of the scaling |
| **DOMINANCE** | which component consumes the resource | **well.** Which term is largest is a property of the workload, not of the machine, unless the machine changes the term's nature — and where it might, this campaign says so |

**An absolute real-time factor may appear in this campaign as context. It may not appear as
a conclusion, a limit, or a requirement.** A write-up that states "the host achieves RTF x,
therefore the target must ..." has broken this rule. Requirements are derived from ratios.

This rule is registered here so that it cannot be relaxed after seeing the data.

---

## 1. Conditions, declared before the runs

- Host: macOS (Darwin 25.5.0), Docker Desktop Linux VM, **12 CPUs, 7.65 GiB** as reported
  by `docker info`. Recorded again in `raw/host.txt` at run time.
- All measurements headless (`gz sim -s`). **No measurement in this campaign bears on GUI
  or rendering cost**; `scripts/sim` refuses GUI on macOS and nothing here substitutes for
  that. Stated as unmeasured in section 8 rather than estimated.
- The host runs unrelated containers (a Supabase stack, ~1.16 GiB resident, ~3.5 % CPU,
  measured before the campaign). **They are stopped for the measurement window and
  restarted afterwards**, and `raw/host.txt` records the state. A measurement taken beside
  them would be partly a measurement of them.
- Commit and branch recorded in `raw/host.txt`.
- Scenarios in this cell are **not deterministic**
  ([cross-cutting-testing](../../architecture/cross-cutting-testing.md), ADR-0027). Every
  figure below is a rate or a distribution over repeats, never a reproduction claim.

### Interleaving

Per the campaign convention's last rule, **conditions alternate; they are not run in
blocks.** Any A/B in this campaign is run A,B,A,B,... so that drift in the host's thermal
or scheduling state cannot land entirely on one arm.

---

## 2. Q1 — Coexistence (FUNCTIONAL)

Two full cells, each `./scripts/sim --headless` over the generated `cell_a` world, started
from the same checkout with **distinct `ROS_DOMAIN_ID`**, in two containers on one host.

| # | Question | Instrument | Threshold |
|---|---|---|---|
| Q1.1 | Do both run at once? | both `gz sim` servers publish `WorldStatistics` continuously for the whole sampling window; neither process exits | **PASS** = no exit and no gap > 5 s in either stats stream |
| Q1.2 | Does either ROS graph contain the other's nodes? | `ros2 node list` and `ros2 topic list` in each domain, compared against the solo baseline set | **PASS** = zero foreign nodes and zero foreign topics. One is a FAIL |
| Q1.3 | Do the two `/clock` publications stay separate? | `ros2 topic info /clock --verbose` in each domain | **PASS** = exactly one publisher per domain. Two is the documented "cell with two clocks" defect and a FAIL |
| Q1.4 | Does `ROS_DOMAIN_ID` isolate **Gazebo transport**? | `gz topic --list` from a shell attached to each instance; then a crossing test — command one cell's belt on the Gazebo transport and observe whether the other cell's belt responds | **PASS** = disjoint topic sets and no crossing. **FAIL** = either instance sees the other's world topics, or a command crosses |
| Q1.5 | Does the host admit two cells at all? | `docker stats` sampled through the window; peak memory summed against the VM limit | **PASS** = no OOM kill and no container restart. Peak memory reported as a fraction of the limit |

**Q1.4 is registered as the one most likely to fail, and the prediction is recorded here so
that confirming it is not a hindsight claim.** `ROS_DOMAIN_ID` is a DDS concept. `gz sim`,
the belt plugin and the beam plugin speak Gazebo transport, which has its own discovery and
its own partitioning (`GZ_PARTITION`). Nothing in this repository sets `GZ_PARTITION` — a
grep over `scripts/`, `infra/`, `workspace/src/cite_bringup`, `workspace/src/cite_simulation`,
`tests/` and `docs/` on 2026-08-28 returned nothing. If Q1.4 fails, the follow-up is
mandatory and is registered now: **re-run with a distinct `GZ_PARTITION` per instance and
record whether that, and only that, restores isolation.**

**Decision rule D1.** If Q1.4 fails under domain separation alone, then Phase 2.A must
partition Gazebo transport explicitly, and that is a **FUNCTIONAL finding that stands
regardless of every performance number in this campaign.** It is reported first.

---

## 3. Q2 — What the second world costs, as a ratio (RATIO)

**Metric.** Real-time factor of one cell, read from Gazebo's own statistics
(`gz topic -e -t /world/cell_a/stats`, field `real_time_factor`), sampled over a fixed
**120 s** window that begins only after the cell has reported every controller active. The
simulator's own number is used rather than a derived one, so that nothing in this
repository's instrumentation sits in the measurement path.

**Conditions**, alternating:

- **SOLO** — one cell running, nothing else.
- **PAIR** — two cells running; cell A and cell B each sampled.

**Primary figure**

```
R  = median RTF(SOLO) / median RTF(cell A in PAIR)                    per-world slowdown
R' = median RTF(SOLO) / median( RTF(A in PAIR), RTF(B in PAIR) )      aggregate
```

**Repeats:** at least **4** alternating SOLO/PAIR blocks. Report median and full range. A
single pair is not a result.

**Pre-registered interpretation bands for R:**

| Band | Reading |
|---|---|
| R <= 1.3 | the second world is close to free; contention is not the binding constraint |
| 1.3 < R <= 2.2 | roughly linear in the number of worlds; the target budget is about 2x one world |
| R > 2.2 | **worse than linear** — a shared resource saturates, and two worlds on one machine is a design risk that more cores may not fix |

**Validity rule V2.** If the SOLO repeats' own range exceeds **25 %** of their median, the
ratio for that block set is reported **INCONCLUSIVE**: the measurement's own noise is
comparable to the effect it is meant to size. This rule fires before any interpretation.

---

## 4. Q3 — What dominates the step (DOMINANCE)

### Q3.1 — The collision-geometry A/B, the highest-value single result here

[ADR-0028](../../adr/0028-convex-hull-collision-meshes.md) has been `Proposed`
since 2026-08-25 and decides that twelve links per arm should stop colliding against their
rendering mesh. It records that the claim it improves real-time factor **is earned by
re-measuring, not by asserting**. This is that measurement.

**Conditions**, on the identical full cell, alternating:

- **V (vendor)** — collision meshes exactly as shipped.
- **H (hull)** — every one of those collision meshes replaced by its **convex hull**,
  computed by this campaign's harness from the same STL. Headless, so no rendering path is
  affected; the substitution changes collision geometry and nothing else that runs.

**Metric:** RTF over the same 120 s window, plus `/cite/cell_a/arm_1/joint_states`
frequency against the **150 Hz** the model configures. Triangle counts before and after are
recorded by the harness rather than quoted from ADR-0028.

**Repeats:** at least **3** alternating V/H pairs.

**Primary figure:** `G = median RTF(H) / median RTF(V)`.

**Decision rule D3, registered before the first trial:**

| Band | Reading |
|---|---|
| G >= 2.0 | **collision geometry dominates.** ADR-0028 is the lever; recommend promoting it and deriving the Phase 2 requirement from the hull condition |
| 1.25 <= G < 2.0 | collision geometry is **material but not dominant.** Hulls help; something else also has to move |
| G < 1.25 | **collision geometry does not dominate.** ADR-0028 will not buy real-time factor, its own "if 0.14 does not move materially" clause fires, and this campaign must say so plainly even though it contradicts the record's expectation |

**This rule is written to be able to disappoint the ADR.** A campaign that can only confirm
is not a campaign.

### Q3.2 — Where the rest of the cost sits

Ablation on the same instrument, reported as shares rather than absolutes:

- the generated world **with no arms spawned** and no control stack;
- the full cell;
- the full cell with **physics paused** through Gazebo's own world-control service, which
  leaves the server, its plugins and the bridge running.

The reportable figure is the share of the step attributable to the arms, and whether the
non-physics part of the server is a rounding error or not.

### Q3.3 — Whatever the installed Harmonic exposes

Record which profiling instrument the installed Gazebo actually offers, and whether it
produced anything. **If it is not compiled in, that is the answer and it is reported as
one** — not as "profiling was impossible".

Registered limitation: `perf` does not work under Docker Desktop's kernel. If native
profiling is the only way to answer something, this campaign says so and hands it back for
a Linux run rather than substituting a guess.

---

## 5. Q4 — Is a physics-free virtual side viable? (RATIO)

In `SHADOW` ([L5](../../architecture/L5-twin-synchronization.md)) the virtual counterpart
only has to *display* mirrored joint state. That needs `robot_state_publisher` and no
simulator at all. If it is a small fraction of a full second world, the architecture is
facing a choice between two virtual implementations — a parallel-abstraction risk worth
knowing about **before** it is built.

**Conditions:**

- **FULL** — the virtual side is a complete second cell (the PAIR condition's cell B).
- **RSP** — the virtual side is `robot_state_publisher` per arm and nothing else: no
  `gz sim`, no controller manager, no `move_group`, fed by mirrored `joint_states`.

**Metric:** CPU-seconds consumed per wall-clock second, summed over the virtual side's
processes, and peak resident memory. Sampled over the same 120 s window.

**Primary figure:** `F = CPU(RSP) / CPU(FULL)`.

| Band | Reading |
|---|---|
| F < 0.1 | the two differ by an order of magnitude. `SHADOW` and `VALIDATED` want **different virtual implementations**, and L5 should say so before either is written |
| 0.1 <= F <= 0.5 | a real saving, not an order of magnitude. Worth a mode switch, not worth two architectures |
| F > 0.5 | the distinction does not pay for itself; one implementation |

---

## 6. Q5 — What mirroring costs (RATIO, and one absolute that is defensible)

L5's failure-mode table names **"mirroring lag treated as divergence"** — the model blamed
for a network problem — and `DivergenceMetrics` has **no latency field** today. Whether
that risk is real starts with what the transport costs when nothing is wrong.

**Rig:** one process holding two `rclpy` contexts on two `ROS_DOMAIN_ID`s, relaying
`sensor_msgs/JointState` from A to B. Publisher, relay and subscriber are on one host and
therefore on one wall clock, so a one-way latency is meaningful without clock
synchronisation. Stamps are **wall clock**, deliberately, not sim time: the quantity is
transport delay, and a sim-time stamp would measure the simulator instead.

**Metric:** one-way latency, publish instant to receive instant. p50 / p95 / p99 / max over
at least **20,000** samples at the cell's configured **150 Hz**. Plus the relay's own CPU.

**Pre-registered threshold, and why this one:** one control period is
`1/150 s = 6.667 ms`. At that delay mirroring lag is the same size as a control cycle, and
a joint-position divergence computed against the mirror is dominated by transport rather
than by any difference between model and plant — which is exactly the failure L5 names.

| Band | Reading |
|---|---|
| p99 < 1 ms | the failure mode is **not transport-borne on one host**. It becomes a lab-network question, which this campaign does not measure |
| 1 ms <= p99 < 6.667 ms | visible, sub-cycle, bounded. `DivergenceMetrics` should carry a latency field so the two can be told apart |
| p99 >= 6.667 ms | the failure mode is **real at rest**, before a network is involved. Latency is not optional in the metric |

---

## 7. What this campaign will produce

A **stated requirement for the target machine**, derived from the ratios in Q2, Q3 and Q4
and from the latency in Q5 — never from this host's absolute real-time factor. The
derivation is written out with the assumptions it rests on named, so that it can be
disagreed with by argument rather than by re-running.

---

## 8. Registered as unmeasured before the campaign starts

Listed now so that silence later is not mistaken for absence of the question.

- **GPU and display cost.** The operator sees the simulation and commits from it, so a
  GPU-backed display is in the command path rather than a convenience. Every run here is
  headless on a machine that refuses GUI, so **nothing in this campaign bears on it.** It
  is a separate unknown and needs a Linux workstation with a GPU.
- **Whether the target machine's core count changes which term dominates.** A ratio
  measured on 12 vCPUs is a ratio at 12 vCPUs. Where a result depends on saturation rather
  than on work, the write-up says so.
- **Anything about physical hardware.** The layout is `PROVISIONAL` and no physical arm
  exists in this measurement, per the campaign convention's third rule.
- **Whether the hull condition is *correct*.** Q3.1 measures what a hull costs, not what it
  breaks. ADR-0028 records that a convex hull fills the gripper's concavity, and this
  campaign does not test a grasp under hulls. A speed result is not a licence to ship one.

## 9. Deviations from this document

Recorded in the write-up as numbered deviations, applied to data already collected. No
threshold above is moved after the first trial.
