# What a second simulation costs, and whether two can coexist

- **Status:** answered for the FUNCTIONAL and DOMINANCE questions; the headline RATIO
  is **INCONCLUSIVE by this campaign's own validity rule V2**, and is reported beside a
  paired-block figure that is labelled as the deviation it is.
- **Campaign:** `2026-08-28-second-world-cost`. Thresholds in
  [`criteria.md`](criteria.md), written before the first trial and frozen at commit
  `57ffd20`. Deviation 6 records exactly when that commit landed relative to the runs.
- **Data:** [`raw/`](raw). Harness and reproduction command: [`harness/`](harness/README.md).
- **Related:** [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  [L5](../../architecture/L5-twin-synchronization.md),
  [ADR-0011](../../adr/0011-twin-maturity-model-and-modes.md)
- **Conditions:** commit `a8f1e3d`, branch `worktree-agent-a0d19ad1ef96bb655`, macOS
  Darwin 25.5.0 on arm64, Docker Desktop 28.5.1 with **12 CPUs and 7.653 GiB**. Every
  unrelated container on the machine was stopped for the whole measurement window and
  restarted afterwards; `raw/host.txt` records an empty `docker ps` at the start.
- **Runs:** 5 SOLO, 5 PAIR (10 cells), 5 HULL, 1 PAIRHULL (2 cells), 1 PAIRGZ (2 cells),
  1 SHADOW pair, 1 world ablation, 2 Gazebo-transport crossing arms, 1 cross-container
  crossing probe, 1 latency rig of 20,000 samples. One further
  SOLO attempt failed bring-up and is kept as `raw/ABORTED_SOLO_3.json`; see
  *Threats to validity*.

---

## 0. Read this before any number below

**The development host is not the target machine.** `criteria.md` section 0 registered
that before the data existed, and it governs the whole write-up: every result is filed as
**FUNCTIONAL**, **RATIO** or **DOMINANCE**, and **an absolute real-time factor appears here
only as context.** No requirement in section 5 is derived from one.

Two absolutes are quoted anyway, in one place, because a reader needs the scale to judge
the ratios — and because one of them contradicts a figure this repository already carries.
See *An absolute, and a contradiction* at the end of section 3.

---

## 1. FUNCTIONAL — can two simulations coexist?

**Yes, and the thing that makes it work is not the thing the repository thinks it is.**

| # | Question | Verdict | Evidence |
|---|---|---|---|
| Q1.1 | Do two cells run at once? | **PASS** | 12 cells across 6 paired runs all reached every controller active; no process exited; the largest gap in either statistics stream was **0.24 s** against a 5 s threshold |
| Q1.2 | Does either ROS graph contain the other's nodes? | **PASS** | 44 nodes and 93 topics in a solo cell; **44 and 93** on each side of every pair. The only set differences are ROS's own address-suffixed names (`transform_listener_impl_*`, `move_group_private_*`) |
| Q1.3 | Do the two `/clock` publications stay separate? | **PASS** | `ros2 topic info /clock --verbose` reports **Publisher count: 1** on each domain |
| Q1.4 | Does `ROS_DOMAIN_ID` isolate **Gazebo transport**? | **NO — and the campaign predicted this before running it** | see below |
| Q1.5 | Does the host admit two cells? | **PASS** | **1.133 GiB and 1.132 GiB** per container during a pair, against a 7.653 GiB limit — 30 % of it. No OOM kill, no restart |

### Q1.4 is the finding, and it is the one that transfers completely

`criteria.md` registered the prediction before the first run: `ROS_DOMAIN_ID` is a DDS
concept, `gz sim` and the belt and beam plugins speak Gazebo transport, and **nothing in
this repository sets `GZ_PARTITION`**. Three conditions were measured
(`raw/gz_crossing.json`, `raw/gz_containers_*.txt`), each by publisher and subscriber count
on the world's own topics:

| Condition | Publishers of `/world/cell_a/stats` | Subscribers of `/cite/cell_a/conveyor_1/command` |
|---|---|---|
| two servers, **one container**, no `GZ_PARTITION` | **2** | **2** |
| two servers, **two containers**, no `GZ_PARTITION` | 1 each | 1 each |
| two servers, one container, **distinct `GZ_PARTITION`** | 1 each | 1 each |

Read the first row carefully. Two belt plugins subscribed to **one** command topic: a
single `ConveyorIndex` setpoint would have started **both** cells' belts, with nothing
anywhere reporting an error. And two publishers of one world's statistics is the
Gazebo-transport form of the defect this project already knows by name.

**What isolated the PAIR runs was the container's hostname, not `ROS_DOMAIN_ID`.**
gz-transport derives its default partition from the host name, each container has a
distinct one, and that is the entire mechanism. It is invisible, undocumented here, and
depends on a deployment choice — the moment Phase 2.A puts the plant and the virtual side
in one container, one `docker run --network host`, or one bare-metal host, the isolation
is gone and the failure is silent.

**Decision rule D1 fires: Phase 2.A must set `GZ_PARTITION` explicitly, per side.** It
costs nothing measurable — `PAIRGZ_1` brought both cells fully up with distinct partitions
at RTF **0.872** and **0.877**, indistinguishable from the same pair without them (0.863,
0.869). This is a FUNCTIONAL result and it stands regardless of every performance figure
below.

### A second FUNCTIONAL finding nobody asked for, and it matters more than the ratio

**The two sides of a pair do not run at the same rate, and nothing throttles either.**

The generated world sets `real_time_factor` to `0`, which means unthrottled: the server
steps as fast as it can. Measured consequences:

- a solo cell runs **faster** than real time (RTF 1.097 median) and, with hull collision
  meshes, at **1.663**;
- in `PAIR_1` the two sides ran at **0.888** and **0.698** in the same window — a **27 %
  rate difference between the plant and its counterpart**, in one wall-clock window, with
  no fault anywhere.

Two independent simulations that free-run therefore have sim clocks that separate
immediately and without bound. [L5](../../architecture/L5-twin-synchronization.md)'s
*Time* section already says a mixed time base "produces divergence numbers that look
plausible and mean nothing"; this measures it. Section 5 derives the requirement from it,
because it turns out to dominate the mirroring-lag question by a factor of about fifty.

---

## 2. RATIO — what the second world costs

### The pre-registered figure is refused by the pre-registered rule

Five SOLO repeats: **1.097, 0.780, 1.097, 1.108, 1.119**. Their range is **30.9 %** of
their median, against validity rule V2's **25 %** ceiling.

**V2 fires. The ratio-of-medians figure for Q2 is reported INCONCLUSIVE**, exactly as
registered, and is not interpreted against the bands. For the record, it would have been
`R = 1.270` and `R' = 1.268`.

The variance is not scatter. It is one block: every measurement taken in block 2 — SOLO,
both PAIR sides and HULL — is depressed by roughly 30 % relative to blocks 1, 3, 4 and 5,
and block 2's SOLO used **more** CPU (4.11 cores) for **less** simulated time than block
4's (3.83 cores). That is a host that was slower for a while, not a cell that behaved
differently. The cause was not established, and the campaign refuses to discard the block.

### Deviation 1 — the same two ratios, computed within a block

**Not pre-registered. Reported beside the refusal, not instead of it.** Because a block's
SOLO, PAIR and HULL runs are taken within minutes of each other, a drift in the host's
state between blocks cancels in a within-block ratio and lands entirely on a
ratio of medians. `harness/paired.py` computes it over data already collected; no run was
repeated to obtain it.

| Block | SOLO | PAIR A | PAIR B | HULL | R = SOLO/A | aggregate | G = HULL/SOLO |
|---|---|---|---|---|---|---|---|
| 1 | 1.097 | 0.888 | 0.698 | 1.330 | 1.235 | 1.446 | 1.213 |
| 2 | 0.780 | 0.491 | 0.494 | 1.016 | 1.590 | 1.261 | 1.302 |
| 3 | 1.097 | 0.867 | 0.875 | 1.684 | 1.265 | 1.589 | 1.536 |
| 4 | 1.108 | 0.864 | 0.869 | 1.663 | 1.282 | 1.565 | 1.501 |
| 5 | 1.119 | 0.863 | 0.873 | 1.670 | 1.296 | 1.552 | 1.493 |

- **Per-world slowdown R: median 1.282, range 1.235 to 1.590.**
- **Aggregate throughput: median 1.552, range 1.261 to 1.589** — two worlds together
  deliver about **1.55x** the simulated time per real second that one world does.

Read against `criteria.md`'s bands, the median sits on the boundary between "close to free"
(R <= 1.3) and "roughly linear" (1.3 < R <= 2.2), and four of the five blocks are below
1.3. **The honest reading is that a second world costs about a quarter to a third of a
world, not a whole one** — sub-linear, because the second world reuses cache-cold work the
first has already warmed and because neither saturates the machine.

### The second world is not limited by cores, and that is the part that transfers

During a pair the two containers drew **411 % and 408 % of a CPU** — **8.2 of 12 cores,
68 % occupancy** — while each side still lost 22 % of its solo rate. **A third of the
machine was idle and did not help.** Gazebo's physics loop is serial, so the per-world
ceiling is set by single-thread throughput and by whatever the two loops contend for below
the core — memory bandwidth or last-level cache. This campaign cannot separate those two,
and says so.

The consequence for a target machine is stated in section 5 and is the opposite of the
obvious one: **buying cores will not buy back the 28 %.**

---

## 3. DOMINANCE — what consumes the step

### 3.1 The collision-geometry A/B: ADR-0028 is worth doing and will not, by itself, be enough

The harness recomputed the geometry rather than quoting it, and **reproduced ADR-0028's
count exactly**: the twelve links per arm whose collision geometry is their visual mesh
carry **98,292 triangles**, and their convex hulls carry **9,810** — a **10.0x**
reduction (`raw/hulls/hull_manifest.json`; the manifest lists 13 files and 100,888
triangles because it also hulls `xarm5/visual/link5.stl`, whose collision proxy is the
vendor's 260-triangle `end_tool.stl` and which is therefore visual only, and unrendered in
a headless run).

**Primary figure G = RTF(hull) / RTF(vendor):**

- ratio of medians, as pre-registered: **G = 1.516**
- median of the per-block ratios (Deviation 1): **G = 1.493**, range **1.213 to 1.536**

Both fall in the same pre-registered band.

> **Decision rule D3, band `1.25 <= G < 2.0`: collision geometry is a material but not
> dominant contributor. Hulls help; something else also has to move.**

The ablation says how much else. Expressed as real seconds needed per simulated second,
which adds where real-time factors do not:

| Condition | RTF | real s per simulated s |
|---|---|---|
| the generated world alone — ground plane, three belt plugins, four beam plugins, **no arms, no controllers, no ROS** | 11.379 | 0.0879 |
| the full cell, vendor collision meshes | 1.097 | 0.9117 |
| the full cell, hull collision meshes | 1.663 | 0.6013 |

From which:

- **the three arms are 90.4 % of the step.** The world's own furniture is a twentieth of it.
- **collision geometry is 37.7 % of the arms' cost and 34.0 % of the whole step.**
- **the remaining 62 % of the arms' cost survives hulls**, and is articulated-body dynamics
  plus three `gz_ros2_control` controller managers stepping at 150 Hz inside the same
  process.
- the server with physics **paused** costs **0.128 cores** against **1.84** running the
  world alone: the non-physics part of the simulator is about 7 % of it, and is not where
  the money is.

Two corroborating readings, both from `raw/SOLO_*.json` and `raw/HULL_*.json`:

- `gz sim` is **52.7 %** of a full vendor cell's CPU and **41.7 %** of a hull cell's — the
  arithmetic of a simulator that got cheaper while everything above it did more work.
- a hull cell's resident memory is **1.48 GiB** against **1.76 GiB** — the meshes cost
  memory as well as time.

**So ADR-0028 should be promoted, and this campaign is the re-measurement its own
"no status improves on the strength of this record" clause demanded.** It buys about
**1.5x** real-time factor and about 0.28 GiB per arm-set. It does **not** make the arms
cheap; it removes a third of the step and leaves two thirds standing. Anyone citing this
result must also cite section 8: the campaign measured what a hull *costs*, never what it
*breaks*, and ADR-0028's own warning about the gripper's filled concavity is untested here.

### 3.2 What the installed Gazebo exposes, asked and answered

`libgz-common5-profiler.so` **is present** in the image
(`/usr/lib/aarch64-linux-gnu/libgz-common5-profiler.so.5.9.0`), and **nothing in the
shipped `gz sim` turns it on**: `gz sim --help` offers no profiling option and no
`GZ_PROFILER*` variable is honoured by the Debian build. `perf` is not installed, and
would not work under Docker Desktop's kernel if it were.

That is the answer, not an excuse. The dominance figures above come from **ablation on the
real cell**, which is stronger evidence than a profile would have been: it measures the
system this project ships rather than attributing samples inside one process. Where a
symbol-level attribution is genuinely needed — to say *which* part of the surviving 62 % is
articulated-body dynamics and which is the controller managers — that needs `callgrind`, or
`perf` on a native Linux host, and is listed in section 8 as unmeasured.

### An absolute, and a contradiction

Two absolutes, quoted once, as context and never as a conclusion.

An **idle** three-arm cell on this host, after bring-up, holding home pose, runs at
**RTF 1.097** and publishes `joint_states` at **158 Hz** against the 150 Hz the model
configures. (Above 150 because the sim is unthrottled: 150 Hz of *simulated* time at RTF
1.097 is 165 Hz of wall time. The hull condition, at RTF 1.663, publishes at **238 Hz**.)

`tests/scenarios/bringup.py` records, and ADR-0028 and CLAUDE.md section 2 both repeat,
that "measured real-time factor on the macOS development host is about 0.14 —
`joint_states` arrives at roughly 21 Hz against a configured 150 Hz". **That does not
reproduce here, and the gap is a factor of 7.8.** The two halves of the recorded figure are
internally consistent with each other, so whatever produced them was a genuinely much
slower configuration — a different Mac, a different Docker CPU allocation, or a condition
other than idle, and **the record does not say which**.

This campaign does not replace that number, because it did not measure the same thing. It
reports that **the figure in the tree carries no condition and no machine, and every
wall-clock ceiling in the scenario suite is justified against it.** Re-measuring it with
its condition written down is cheap and is worth someone's afternoon (P7).

---

## 4. RATIO — a physics-free virtual side, and what mirroring costs

### 4.1 Q4: the two virtual sides differ by a factor of forty-four

`SHADOW` needs the virtual counterpart only to *display* mirrored joint state, which is
`robot_state_publisher` and no simulator. Built exactly that way — three
`robot_state_publisher` on the virtual domain and one in-process relay across the domain
boundary — and measured over the same 120 s window beside a running plant cell
(`raw/SHADOW_1_shadow.json`):

| Virtual side | CPU | resident memory | plant's RTF while it ran |
|---|---|---|---|
| a full second cell (PAIR, side B) | **3.81 cores** | **1.132 GiB** | 0.869 |
| `robot_state_publisher` only | **0.0865 cores** | **0.0794 GiB** | **1.107** |

It relayed **18,973 messages per arm** in the window — 158 Hz, the plant's full rate, with
nothing dropped by the rig's own count.

> **F = 0.0865 / 3.81 = 0.023.** Registered band **F < 0.1**: *the two differ by an order
> of magnitude. `SHADOW` and `VALIDATED` want different virtual implementations, and L5
> should say so before either is written.*

It is 44x cheaper in CPU and 14x cheaper in memory, and — the figure that decides it — the
plant ran at **1.107** with a shadow side attached, against a solo median of **1.097** and
a paired **0.864**. **A `SHADOW` virtual side costs the plant nothing measurable. A
`VALIDATED` one costs it 22 %.**

This is a parallel-abstraction risk found before it was built, which is what it was worth
measuring for. It is **not** an argument for two codebases: the honest reading is that the
*mode* decides whether a simulator is instantiated at all, and L5's mode table should carry
that as a property of the mode rather than leaving it to whoever writes the launch graph.

### 4.2 Q5: transport latency is real, bounded, and is not the problem

`raw/mirror_latency.json`, 20,000 samples at 150 Hz, wall-clock stamps, one process, one
host clock, reliable QoS matching `joint_state_broadcaster`'s:

| Path | p50 | p95 | p99 | max |
|---|---|---|---|---|
| one hop, same domain | 0.339 ms | 1.140 ms | 1.496 ms | 17.58 ms |
| **source, relay, mirror — across the domain boundary** | **0.983 ms** | **2.344 ms** | **3.131 ms** | **20.86 ms** |

Crossing the boundary adds **0.644 ms at p50**. The relay rig cost **0.224 cores** to carry
one arm at 150 Hz.

> Registered band **1 ms <= p99 < 6.667 ms**: *visible, sub-cycle, bounded.
> `DivergenceMetrics` should carry a latency field so the two can be told apart.*

That recommendation stands — the field should exist, because L5's failure mode is real in
principle and because the **max of 20.86 ms is three control periods**, so the tail is not
negligible even when the percentiles are.

**But the percentile is not the story, and section 5 is where that matters.** At the paired
real-time factor of 0.87, each side's simulated clock falls behind the wall clock by
**130 ms for every second that passes** — about **forty times** the p99 transport latency,
and unlike the transport it **accumulates**. On this host, in this configuration,
*mirroring lag is dominated by the real-time-factor deficit and not by the network at all.*

---

## 5. The derived requirement for the target machine

Derived from the ratios above and from one condition, never from this host's absolute
real-time factor. The derivation is written out so that it can be disagreed with by
argument rather than by re-running.

### The condition, and why it is this one

**Both sides must sustain a real-time factor of at least 1.0, concurrently.**

The justification is section 4.2's arithmetic and not a preference. At real-time factor
`r`, a simulator's clock falls behind the wall clock at `(1 - r)` seconds per second, and
that deficit **accumulates without bound**. At the measured paired value of `r = 0.866`
that is **134 ms of lag for every second of operation** — and it passes the p99 transport
latency of **3.131 ms** after **23 ms** of wall time. Everything after that first
twenty-three milliseconds, mirroring lag is the real-time-factor deficit and nothing else.

So "a rate at which mirroring lag does not dominate divergence" has exactly one answer:
**`r >= 1` on both sides, with both throttled so that neither runs ahead either.** The
generated world sets `real_time_factor` to `0`, so nothing is throttled today, and a pair
was measured running at 0.888 and 0.698 in the same window. Capacity alone is not enough;
the throttle has to exist as well.

### What the target must provide, in ratios to this host

The requirement was measured rather than extrapolated: `PAIRHULL_1` ran two full cells at
once with hull collision meshes.

| Two cells at once | per-world RTF | cores of 12 | memory |
|---|---|---|---|
| vendor collision meshes | **0.864, 0.869** — fails the condition by 13 % | 8.2 (68 %) | 2.27 GiB |
| **hull collision meshes** | **1.162, 1.173** — meets it with 17 % margin | 9.3 (78 %) | 1.72 GiB |

1. **Serial throughput is the binding requirement, and cores are not.** With ADR-0028's
   hulls, a machine with **this host's per-core throughput** already runs two worlds above
   real time. Without them it needs **at least 1.16x** this host's per-core throughput to
   reach 1.0 at all, with no margin left. The pairing penalty of about 28 % appeared at
   68 % core occupancy — **a third of the machine was idle and did not help** — so it is
   contention below the core, and **more cores will not buy it back.**
2. **Cores: at least 12, and treat that as a floor.** Two hull-condition cells drew 9.3.
   The operator's GUI is not in that figure and is unmeasured.
3. **Memory is not the constraint.** Two hull cells: 1.72 GiB. **8 GiB is comfortable**;
   the 7.653 GiB this campaign ran in was never close to the limit.
4. **Gazebo transport must be partitioned per side** (section 1). This is free and is not
   negotiable if the two sides may ever share a container, a host network namespace, or a
   bare-metal host.
5. **The 17 % margin is not a work allowance.** Every cell measured here was **idle**,
   holding home pose after bring-up. Motion, planning, contact and grasp all cost more and
   **none of it was measured**. A machine sized at exactly this margin will not hold RTF 1.0
   through a `continuous_line` run, and this campaign cannot say by how much it will miss.

### The single highest-value action this campaign supports

**Promote ADR-0028 and generate the hulls.** It is the difference between a pair that
misses the condition by 13 % and a pair that meets it by 17 %, on the same machine, with
nothing bought. It also lowers the requirement on the target machine by 1.16x — which is a
hardware budget, spent once, that a mesh pipeline removes.

### What the requirement rests on

- Two idle cells, five interleaved blocks for the single-cell figures and **one** paired
  hull run. The paired hull figure is a single measurement and is labelled as one.
- One host, one architecture (arm64), one container runtime.
- A serial physics loop. If a future Gazebo parallelises the step, item 1 changes and this
  requirement should be re-derived rather than adjusted.
- Idle cells throughout. See item 5 and section 8.

---

## 6. Deviations from `criteria.md`

1. **Within-block ratios (section 2).** `criteria.md` registered R and G as ratios of
   medians across repeats, and registered validity rule V2 to refuse them if the SOLO
   repeats' range exceeded 25 % of their median. **V2 fired and is reported as firing.**
   The within-block ratios are computed by `harness/paired.py` over data already collected,
   are reported beside the refusal rather than instead of it, and no run was repeated to
   obtain them. The two figures agree to within 1 % for R and 2 % for G, which is why the
   deviation changes no conclusion.
2. **Five blocks instead of four.** `criteria.md` asked for at least four SOLO/PAIR blocks
   and at least three V/H pairs. Five of each were run after V2 fired at three, on the
   principle that the answer to variance is more samples rather than a moved threshold. The
   spread did not narrow; V2 still fires at five.
3. **One hull-condition pair, added after the sequence.** Section 5's requirement would
   otherwise have multiplied the single-cell hull gain by the pairing penalty. It is one
   run, run by `harness/run_hull_pair.sh`, which composes phases the frozen
   `run_campaign.sh` already exposes and edits nothing.
4. **`SOLO` doubles as the `V` arm of Q3.1.** They are the same condition measured the
   same way, so running both would be running one thing twice under two names. Declared in
   `harness/sequence.sh`.
5. **Q3.2's paused-physics arm produced no real-time factor**, because a paused server
   stops publishing world statistics and the window needs two samples. Its **CPU** figure
   (0.128 cores) is valid and is what section 3.1 uses; the RTF cell is `null` in
   `raw/world_only.json` and is not quoted anywhere.
6. **`criteria.md` was committed after two rig-validation runs**, not before them. `SMOKE`
   and `SMOKEPAIR` ran at a 20 s window to shake out the harness; they are published in
   `raw/` and are excluded from every figure by label. No threshold was written or changed
   after any of it. Recording this rather than quietly meeting the letter of the rule.
7. **One character-level correction to the frozen `criteria.md`.** Its two links to
   ADR-0028 named a file that does not exist, and `./scripts/lint`'s documentation-link
   check refused them. Only the path was corrected. **No threshold, band, rule or
   interpretation in that file was touched**, and `git log -p` on it shows exactly that.

## 7. Threats to validity

- **One aborted bring-up, kept.** `raw/ABORTED_SOLO_3.json`: `arm_3` never activated a
  controller and the launch aborted before `arm_2`'s planning scene. It is the failure mode
  CLAUDE.md section 2 records for `bringup`, it is preserved rather than deleted, and the
  replacement run is `SOLO_3`. **1 in 12 solo bring-ups failed** in this campaign, which is
  a count and not a rate.
- **Block 2 is 30 % slow across all four of its runs and the cause was not established.**
  It is included in every figure. The within-block ratios are the campaign's response to
  it, not its concealment.
- **Idle cells only.** No arm moved, nothing was planned, nothing was grasped. This
  measures the cost of *existing*, which is the floor.
- **Docker Desktop on macOS/arm64.** A Linux VM with no GPU passthrough. Whether the
  virtualisation boundary contributes to the pairing penalty is unmeasured and could be
  settled on a native Linux host.
- **The pairing penalty's mechanism is not identified.** Memory bandwidth and last-level
  cache are both consistent with 28 % at 68 % occupancy, and this campaign cannot separate
  them.
- **`gz topic -e` is in the measurement path** for the real-time factor, and its own cost
  is inside the `cpu_cores` figures. It is identical across every condition, so it cancels
  in a ratio; it inflates the absolutes slightly.
- **The mirroring rig prints `terminate called without an active exception`** at process
  exit, after its results are written. A teardown artefact in the rig, not in the data.

## 8. Registered as unmeasured, and still unmeasured

Everything `criteria.md` section 8 listed, unchanged, plus what the runs added:

- **GPU and display cost — completely unmeasured.** The operator sees the simulation and
  commits from it, so a GPU-backed display is in the command path rather than a
  convenience, and `scripts/sim` refuses GUI on macOS. **Nothing in this campaign bears on
  it.** It needs a Linux workstation with a GPU, and the question it must answer is not
  "does RViz run" but what a rendering client costs the *simulator* it is attached to.
- **What a hull breaks.** Q3.1 measured what a hull costs. ADR-0028 records that a convex
  hull fills the gripper's concavity, and **no grasp was attempted under hulls here.** A
  speed result is not a licence to ship one; promoting ADR-0028 needs the friction-grasp
  campaign re-run against hull geometry.
- **The surviving 62 %.** Section 3.1 attributes it to articulated-body dynamics plus three
  controller managers, from ablation. Splitting it needs `callgrind` inside the container or
  `perf` on native Linux.
- **Anything under load.** See section 7.
- **Whether the target's core count changes which term dominates.** A ratio at 12 vCPUs.
- **Anything about physical hardware.** The layout is `PROVISIONAL`, and the campaign
  convention's third rule applies: this measures the simulator.
