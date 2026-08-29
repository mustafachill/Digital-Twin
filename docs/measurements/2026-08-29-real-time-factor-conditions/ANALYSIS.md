# What real-time factor this cell actually achieves, and under what condition

- **Status:** answered. **The recorded 0.14 is CONDITIONAL, not wrong** — it reproduces on
  this host, both halves of it together, under a condition the record never stated. Decision
  rule D2's first row fires.
- **Campaign:** `2026-08-29-real-time-factor-conditions`. Thresholds in
  [`criteria.md`](criteria.md), written and hashed **before the first trial**;
  [`raw/FREEZE.txt`](raw/FREEZE.txt) carries the SHA-256 of `criteria.md` and of every
  harness file at that instant, with the timestamp and the repository HEAD.
- **Data:** [`raw/`](raw). Harness and reproduction commands:
  [`harness/`](harness/README.md).
- **Related:** [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  [ADR-0032](../../adr/0032-index-the-belt.md),
  [L2](../../architecture/L2-control-and-hal.md),
  [`2026-08-28-second-world-cost`](../2026-08-28-second-world-cost/ANALYSIS.md), which found
  the discrepancy and declined to overwrite the record.
- **Conditions:** commit `f1f914f`, branch `main`, workspace built in this checkout
  immediately before the first trial (21 packages, 9 min 46 s). Host: **Apple M4 Pro,
  12 cores, 24 GiB, macOS 26.5.2 (Darwin 25.5.0), arm64**; Docker Desktop 28.5.1 Linux VM
  with **12 CPUs and 7.653 GiB**. The container image is **`arm64/linux` and the container
  reports `aarch64` with 12 processors** — see *A correction to the brief* below.
  The project owner's unrelated containers were **left running** and measured per trial
  (**15 containers, 4.4-9.6 % CPU summed, ~2.0 GiB**); `raw/*.host.txt` records the state
  before and after every trial. Headless throughout.
- **Runs:** 8 idle cells (6 IDLE + 2 EARLY), 3 `pick_and_place`, 2 `continuous_line`,
  2 `bringup`, and 3 CPU-constrained cells covering 12 / 4 / 2 / 1 / 0.5 allocated CPUs.
  **18 cells in total, one at a time.** No trial found a survivor from the previous one.

---

## 0. Read this before any number below

`criteria.md` section 0 registered, before the data existed, that **this campaign publishes
absolutes and every one of them must carry its machine, its scene, its load and its
sampling method.** That rule is the whole point: the figure being corrected here is not
wrong so much as **unattributable**, and a replacement figure with the same defect would be
no better.

So: **there is no headline real-time factor for "the cell" in this document.** There are
four conditions and a CPU curve, and the number you want depends on which one you are in.

---

## 1. Q1 — what this cell achieves, by condition

Window RTF is `delta(sim_time) / delta(real_time)` over the stated window, from Gazebo's own
`WorldStatistics`. Method fixed in `criteria.md` section 2 before the runs.

| Condition | What was running | n | median RTF | range | spread |
|---|---|---|---|---|---|
| **IDLE** | cell up, nothing commanded, 120 s window after a 30 s warm-up | 6 | **1.060** | 0.819 - 1.107 | 27.2 % — **NOISY by rule V1** |
| **IDLE**, excluding the first trial after a build | as above | 5 | **1.065** | 1.030 - 1.107 | 7.2 % |
| **EARLY** | idle, window opened at readiness with **no** warm-up | 2 | **1.100** | 1.097 - 1.103 | 0.6 % |
| **CYCLE** | `pick_and_place` — one arm planning, moving, grasping | 3 | **0.582** | 0.578 - 0.607 | 5.0 % |
| **LINE** | `continuous_line` — three arms, belts, beams | 2 | **0.681** | 0.670 - 0.692 | 3.2 % |
| **BRING-UP** | launch to every arm's controllers active, cut from **all 18 runs** | 18 | **1.071** | 0.896 - 1.114 | 20.3 % |

`joint_states` on the three arms, in the same windows, measured two ways
(`ros2 topic hz --window 200` and a keep-last-1000 counting subscriber):
**148 - 161 Hz** on every idle trial but one, against the 150 Hz L0 configures. Above 150
because the world is unthrottled and the sim runs faster than real time, exactly as the
second-world campaign explained.

### What this immediately settles

- **The cell is not slow on this machine.** Idle it runs slightly faster than real time.
- **Bring-up is not the slow phase.** At 1.071 median across all eighteen runs, the physics
  during bring-up is indistinguishable from idle. **Candidate C1 is rejected.**
- **Load costs about 40 %, not a factor of seven.** A single-arm cycle takes the cell from
  1.06 to 0.58; the three-arm line sits at 0.68, *above* the single-arm cycle, because much
  of the line's wall time is belt transport rather than planning.
- **Rule V1 fires on IDLE and on nothing else.** The 27.2 % spread is one trial: `IDLE_1`,
  at 0.819, run within a minute of a 21-package build finishing, with background containers
  at 9.6 % CPU against 4.4-5.1 % later. Removing it leaves 7.2 %. That is **one observation
  with a plausible story and no replication**, and it is reported as such — not as a
  cold-cache effect this campaign established. The second-world campaign saw the same
  signature: one block depressed ~30 % with no established cause. **Two campaigns now agree
  that this host occasionally gives back a quarter to a third of its throughput, and neither
  has established why.** Note the size: a quarter, not a factor of 7.8.

---

## 2. Q2 — is 0.14 wrong, or was it conditional?

## **Conditional. It reproduces here, at about one CPU core, and both halves reproduce together.**

`criteria.md` section 4 fixed the band before any data: a condition reproduces the figure if
its **median window RTF falls in [0.11, 0.17]**.

The candidates were tried in the registered order. Three were free, cut from runs that were
happening anyway; one cost trials; one is inspection; one is untestable here.

| # | Candidate | Result | Verdict |
|---|---|---|---|
| C1 | bring-up transient | 1.071 median over 18 runs | **rejected** |
| C2 | under load | 0.582 (cycle), 0.681 (line) | **rejected** — nowhere near the band |
| C3 | a smaller CPU allocation | **see the curve below** | **REPRODUCED** |
| C4 | a sampling artefact | see section 4 — real, large, and in the **opposite** direction | **rejected as the cause, kept as a finding** |
| C5 | the tree at `47681f6` | inspection only, by registration | **plausible, untested** |
| C6 | GUI / rendering | untestable here — and see the argument below | **excluded by argument, not by measurement** |

### The CPU curve, which is the answer

One cell, brought up at the full allocation and then squeezed with `docker update --cpus`
while it ran, sampling continuously so each allocation's 120 s window is cut from one run.
Two independent trials (`CPULIMIT_1`, `CPULOW_1`) overlap at 2 CPUs and agree.

| allocated CPUs | window RTF | what Gazebo's own `real_time_factor` field said |
|---|---|---|
| 12 | **1.094**, 1.107, 1.107, 1.089 | 1.097, 1.108, 1.113, 1.097 |
| 4 | **1.025** | 1.098 |
| 2 | **0.478**, **0.471** | 1.045, 1.048 |
| **1** | **0.167**, **0.159** | 0.694, 0.692 |
| 0.5 | **0.039** | 0.147 |

**0.167 and 0.159 are inside the pre-registered band.** Decision rule D2's first row fires:
**CONDITIONAL**, and the missing thing is the condition.

### Both halves of the recorded figure reproduce, together, in one trial

The record is a *pair*: "real-time factor about 0.14 — `joint_states` arrives at roughly
21 Hz against a configured 150 Hz". A third trial (`CPURATE_1`) applied the 1-CPU limit
**before** the measurement window opened, so the rate was measured under the constraint
rather than beside it:

| | recorded in the tree | measured at 1 CPU (`CPURATE_1`) |
|---|---|---|
| window RTF | ~0.14 | **0.159** |
| `joint_states`, arm_1 / arm_2 / arm_3 | ~21 Hz | **23.9 / 23.3 / 23.2 Hz** (`ros2 topic hz`) |
| the same, counted independently | — | **22.5 / 23.1 / 22.2 Hz** |

The same cell before the limit was applied, in the same run: RTF **1.089**.

**That is the finding.** The recorded figure describes this cell with about one core of CPU
available to it. It is a real state of this machine, it was never written down, and
everything built on the number inherited the omission.

### The arithmetic hypothesis is neither confirmed nor refuted, and that is the honest answer

`criteria.md` registered, before the data, that `21 / 150 = 0.14` **exactly**, so the pair
may be one measurement divided by 150 rather than two. The data cannot separate the two
possibilities, and now says why: **at 1 CPU the measured pair is 0.159 and ~23 Hz, and
23 / 150 = 0.153.** The two quantities genuinely track each other to within the noise, so
their consistency is not evidence that only one was taken. The hypothesis is retired as
undecidable rather than answered — which is a better outcome than the confirmation it was
written to be capable of.

### What one CPU means in practice, and why it is not an exotic condition

An idle cell on this host **uses 4.15 - 4.41 cores** (n = 6, from `/proc` inside the
container). So a 1-CPU allocation gives it under a quarter of what it asks for. Two
mechanisms produce that state and this campaign cannot tell them apart:

- **an explicit allocation** — Docker Desktop's CPU setting, whose historical value on this
  machine is not recorded anywhere;
- **contention** — the cell getting one core's worth because something else holds the rest.
  This project has run parallel builds across multiple agent worktrees and has exhausted
  this host's disk twice doing it. A 21-package `colcon` build beside a running cell is
  exactly the shape of load that would do it.

**Which of the two produced the recorded figure is not established and cannot be from
here.** What can be said is that the number is reachable on this host today, by either
route.

### The degradation is worse than linear below two cores

- 12 -> 4 cores: RTF barely moves (1.094 -> 1.025) — **four cores is enough**, consistent
  with the cell's measured 4.3-core appetite.
- 4 -> 2: RTF 1.025 -> 0.475, roughly proportional.
- 2 -> 1: 0.475 -> 0.163, a factor of 2.9 for half the CPU.
- 1 -> 0.5: 0.163 -> 0.039, a factor of 4.2 for half the CPU.

Below about two cores the cell loses more throughput than the CPU it loses. The mechanism is
**not established here** — starved ROS executors and physics contending for the same core is
the obvious candidate, and this campaign did not instrument it. Registered as unmeasured.

### C6, excluded by argument rather than by measurement

GUI cost cannot be measured on this host: `scripts/sim` refuses GUI on macOS. But the guard
that refuses it was added in `83c0546` at **18:33 on 2026-08-24**, and the figure entered the
tree in `47681f6` at **22:33 the same day**. A GUI run through the project's entry point was
therefore already impossible on the machine the record names when the record was written.
That is an argument, not a measurement, and GPU/display cost on a Linux workstation remains
genuinely unmeasured.

### C5, what the tree looked like when the figure was written

Inspection only, by registration. `47681f6` is the commit that **anchored the scene to the
world**; its own message records that before it, `gz sdf -p` produced "a 315.75 kg free body
for the cell and three free arm roots". The same commit added the comment carrying the
figure. The tree at that moment also still contained the contact-triggered grasp attachment
plugin, removed later in `c7245fe`.

So a measurement taken during that commit's work could have been taken against a cell whose
scene was unanchored. **This is a plausible second condition and it is untested** — rebuilding
and running a five-day-old tree was out of budget and `criteria.md` said so in advance. It
does not compete with the CPU result, which reproduces the figure exactly; it is recorded
because "the machine was starved" and "the scene was falling over" are different corrections
to the record and only one of them has evidence.

---

## 3. Q3 — the ceilings that depend on the figure

**This campaign changed nothing.** Every ceiling below is reported, with the margin
`M = ceiling / slowest measured instance of the interval it bounds`, against the bands fixed
in `criteria.md` section 5: `M < 1.5` too tight, `1.5 <= M <= 10` appropriate, `M > 10` too
loose. Rule D3 applies: an interval this campaign did not measure is **not assessed**, never
"fine".

**First, a structural point that survives every number here:** the scenario observer nodes
deliberately do **not** set `use_sim_time` — `continuous_line.Sample`'s docstring gives the
reason, and it is a good one. So every ceiling below is **wall clock**, and every one of them
scales inversely with real-time factor. That is what makes the figure load-bearing.

| File | Ceiling | Value | Interval it bounds | Slowest measured | M | Verdict |
|---|---|---|---|---|---|---|
| `bringup.py` | `BRING_UP_CEILING_S` | 240 s | every arm's controllers active | **35.1 s** (n=18) | 6.8 | APPROPRIATE |
| `bringup.py` | `DELIVERY_CEILING_S` | 30 s | one message on a subscribed topic | not measured individually | - | **not assessed** |
| `bringup.py` | `TRAJECTORY_CEILING_S` | 60 s | a `JointTrajectory` goal accepted, then its result | not measured individually | - | **not assessed** |
| `bringup.py` | `SKILL_CEILING_S` | 120 s | one skill action result | **17.7 s** (proxy, n=3) | 6.8 | APPROPRIATE |
| `pick_and_place.py` | `BRING_UP_CEILING_S` | 300 s | controllers active, then servers | **30.4 s** (n=3) | 9.9 | APPROPRIATE, borderline |
| `pick_and_place.py` | `CYCLE_CEILING_S` | 420 s | the coordinator process, start to exit | **60.9 s** skill span; **92.5 s** whole test (n=3) | 6.9 / 4.5 | APPROPRIATE |
| `continuous_line.py` | `BRING_UP_CEILING_S` | 300 s | as above | **34.4 s** (n=2) | 8.7 | APPROPRIATE |
| `continuous_line.py` | `LEG_CEILING_S` | 420 s | one milestone of the ladder | **109.6 s** (proxy, n=2) | 3.8 | APPROPRIATE, on a proxy |

**One bound covers three of `bringup.py`'s four ceilings at once.** The whole `bringup`
scenario — all eight of its tests, including the controller wait, the trajectory goal, the
skill goal and every delivery check — completed in **39.7 s and 32.4 s** in two runs, both
passing. No single interval it bounds can have exceeded that total. It is a bound and not a
measurement of any one of them, so rule D3 still reports `DELIVERY_CEILING_S` and
`TRAJECTORY_CEILING_S` as not assessed — but the suite that exercises all four ceilings
finishes in **a sixth of the smallest of them.**

Two proxies are used and named as such. `SKILL_CEILING_S`'s is the longest interval between
consecutive `Planning request accepted` lines in a cycle (17.2 / 17.7 / 17.2 s across three
runs — the transfer move). `LEG_CEILING_S`'s is the longest interval between consecutive
beam edges in a line run (109.6 s and 69.2 s). Per-milestone timings are not printed by the
scenario and were not instrumented, so the true longest leg is bounded but not measured.

### **No ceiling is too tight and none is too loose. That is not the interesting part.**

The interesting part is what the margins become in the condition the ceilings were *written*
for. Scaling the measured intervals by the ratio of real-time factors (0.582 measured under
cycle load, against 0.159 measured at 1 CPU — a factor of 3.7):

| Ceiling | M at full CPU | M at 1 CPU | M at 0.5 CPU |
|---|---|---|---|
| `pick_and_place.CYCLE_CEILING_S` | 4.5 | **~1.2** | **~0.3 — would fail** |
| `bringup.SKILL_CEILING_S` | 6.8 | **~1.8** | ~0.5 |
| `continuous_line.LEG_CEILING_S` | 3.8 | ~1.0 | fails |

**So `CYCLE_CEILING_S = 420 s` is not a generous ceiling that happens to be large. It is a
ceiling sized precisely for the starved condition, and in that condition it has almost no
margin at all.** The comment in `pick_and_place.py` says as much without knowing it: a cycle
"observed at 315-420 s here, which is the whole of `CYCLE_CEILING_S`".

That is the answer to the brief's suspicion that a wrong figure explains a class of flaky
runs. **It does, and not in the direction expected.** The ceilings are right; what is wrong
is that nothing in the tree says the condition they were sized for is a starved machine, so
a run that times out on `CYCLE_CEILING_S` looks like a hang and is far more likely to be a
host with one core to spare. The scenarios' own failure messages already hedge — "on a host
whose real-time factor is well below 1.0 this is as likely to mean 'slow' as 'hung'" — and
this campaign turns that hedge into a number: **below about 1.2 cores, `pick_and_place` will
start timing out, and nothing will be broken.**

---

## 4. Q4 — how to measure real-time factor here

The method was fixed before the data (`criteria.md` section 2) and it survives contact with
it. What the data adds is **which instruments to distrust, and by how much.**

### Use `delta(sim_time) / delta(real_time)` from `WorldStatistics`, over a stated window

Both fields come from the same message. `real_time` tracks wall clock exactly — measured
`real_time / wall = 1.000` in every segment of both CPU trials — so the ratio is the
definition, not an estimate.

### Do not use Gazebo's own `real_time_factor` field on a contended host

It is a smoothed estimate and **it does not degrade with the thing it reports**:

| condition | true window RTF | the `real_time_factor` field | over-report |
|---|---|---|---|
| 12 CPUs | 1.094 | 1.097 | 1.00x |
| 4 CPUs | 1.025 | 1.098 | 1.07x |
| 2 CPUs | 0.478 | 1.045 | **2.19x** |
| 1 CPU | 0.167 | 0.694 | **4.15x** |
| 0.5 CPU | 0.039 | 0.147 | **3.77x** |

The two numbers **inside the same message** disagree by a factor of four. The distribution is
not bursty — at 2 CPUs the field's 10th and 90th percentiles are 0.881 and 1.179 — so this is
not a sampling window artefact that averaging fixes. **The mechanism is not established
here** and is registered as unmeasured.

Note the direction. A reader trusting the field on a starved host gets a number that is **too
high**, so this cannot be how 0.14 was produced. It is, however, exactly how a starved host
gets mistaken for a healthy one — and note the last row: **at 0.5 CPU the field reads 0.147**
while the cell is actually at 0.039. A number very close to the recorded one is printed by a
Gazebo running at a twenty-fifth of real time.

### `ros2 topic hz` is fine at steady state and lies while it converges

Against the counting subscriber, on 24 arm-measurements at full allocation, the two agree
within a few per cent. But `ros2 topic hz`'s **first** reported averages are low and climb:
54.1 -> 81.5 -> 127.3 -> ... -> 148 in `IDLE_1`, and 151.7 -> 158.8 in the well-behaved
`EARLY_1`. Reading the first line it prints can understate the rate by a factor of nearly
three on a loaded host. Both instruments are published for every trial for this reason.

### Warm up, but not for the reason you would guess

EARLY (window opened at readiness, no warm-up) measured **1.100**, marginally *above* IDLE's
1.060 with a 30 s warm-up. The warm-up buys nothing measurable here, and the campaign keeps
it only because it was registered. **What does matter is that the measurement stays out of
the window**, which this campaign's own harness failed to do — see Deviation 1.

### The recommended recipe, in one place

> Bring the cell up headless. Wait for every arm's controller manager to report its
> controllers active — an observed state, never a sleep. Sample
> `gz topic -e -t /world/<zone>/stats` for **120 s** and report
> `delta(sim_time) / delta(real_time)` between the first and last sample. **Run no other
> instrument inside that window.** Repeat at least five times and publish the median and the
> full range. State: the machine, its core count and its allocation, what else was running,
> the scene, and what the cell was doing. Any of those omitted, and the number is the one
> this campaign had to re-measure.

---

## 5. What the six records should say

**This campaign is read-only on source and changed none of them.** The brief named three
places; there are **six**, plus one test fixture that merely quotes the string.

| File | What it says now | What it should say |
|---|---|---|
| `tests/scenarios/bringup.py:85-88` | "Measured real-time factor on the macOS development host is about 0.14 — `joint_states` arrives at roughly 21 Hz" | the same figure **with its condition**: this cell confined to about one CPU core. At a full allocation the same host idles at 1.06 and this ceiling's margin is 6.8x |
| `tests/scenarios/pick_and_place.py:62-66` | as above, plus "a cycle that takes 110 s there has been observed at 315-420 s here" | the 315-420 s observation is **consistent with the 1-CPU condition** and should be labelled with it. The cycle measured 60.9 s of skill activity and 92.5 s end to end at a full allocation |
| `tests/scenarios/continuous_line.py:115-119, 171-176` | "the development host's measured real-time factor of 0.14", used to justify `LEG_CEILING_S` and the 0.5 s sample period | the sample-period arithmetic is **unaffected** — it is a floor argument and a higher RTF only gives it more samples. The ceiling justification needs the condition |
| `docs/adr/0028-...:57, 166, 174, 202` | "Real-time factor on the development host is **0.14**", called "the measurement that gives it urgency", with a re-measurement clause | **the urgency claim is the one that has to change.** Collision geometry is not why this host runs at 0.14; a one-core allocation is. The ADR's own "if 0.14 does not move materially" clause should be read against the second-world campaign's measured **1.5x from hulls**, not against this figure |
| `docs/adr/0032-...:352` | "a better real-time factor than the 0.14 the development host manages" | **the decision is unaffected** — it rejected Option C on a factor-of-160 gap. Only the parenthetical figure is wrong-as-stated |
| `docs/architecture/L2-...:74` | "**Not held:** the configured rate. The model asks for 150 Hz; `joint_states` was measured at roughly 21 Hz at a real-time factor of 0.14" | **this is the most misleading of the six**, because it records a *capability gap* that does not exist. At a full allocation `joint_states` runs at **148-161 Hz**, above the configured 150, because the world is unthrottled. The rate is held |
| `CLAUDE.md:349` | "Real-time factor on the development host is 0.14" | the condition, and a link here. It sits in a bullet about collision meshes, which is precisely the attribution the number does not support |

**One further thing every one of them should stop doing (P1):** restating the figure. Six
copies is how a number outlives its condition. Cite this directory.

**`docs/measurements/README.md` needs a row for this campaign.** This campaign did not add
it, being confined to its own directory.

---

## 6. A correction to the brief that commissioned this

The task described this host as running "Linux containers under emulation-adjacent
conditions". **It is not emulated.** `docker image inspect` reports the image as
`arm64/linux`, and the container reports `aarch64` with 12 processors and the full ARMv8
feature set. This is native aarch64 in Apple's Virtualization.framework VM on an M4 Pro.
That matters both ways: it removes emulation from the list of explanations for a low
real-time factor, and it means the 1.06 idle figure is not flattered by anything.

---

## 7. Deviations from `criteria.md`

Numbered, applied to data already collected. No threshold was moved.

1. **The declared window contained the campaign's own instruments.** `rtf_probe.py` measures
   the two `joint_states` rates at the start of the window and then sleeps out the
   remainder; on three arms that took ~150 s, so the whole 120 s window was instrumented.
   The cost is measurable: in `IDLE_1` the uninstrumented warm-up interval read **0.954** and
   the instrumented window **0.819**. Consequences, in order: the window figures are
   internally comparable because every trial paid the same cost; the IDLE median of 1.060 is
   therefore a **slight underestimate** of a genuinely idle cell; and the recipe in section 4
   says to keep instruments out of the window because of this. The harness was **not**
   changed after the first trial ran.
2. **`cpu_limit_trial.sh` was corrected before it ever ran.** Its readiness poll called
   `scripts/enter` in a loop, which starts a container per poll and would have loaded the
   host it exists to characterise. It produced no data in its original form; the replacement
   is a fixed wait, justified in the script's own comment. Recorded because the campaign
   convention freezes a harness once it has produced data, and the honest report is that this
   one had not.
3. **Two follow-up scripts were added after data existed**, as separate files rather than as
   edits: `cpu_limit_trial_low.sh` (allocations below 2 CPUs, forced by `CPULIMIT_1`'s own
   result) and `cpu_limit_rates.sh` (the `joint_states` half under the reproducing
   constraint). Neither touches an existing harness file or an existing raw record.
4. **An additional window is cut in analysis** — launch to readiness, for the BRING-UP
   condition. `criteria.md` section 3 registered this condition and section 2 registered that
   the continuous series makes such cuts possible, so this is the plan working, not a change
   to it.
5. **CPU and memory figures are absent for the CYCLE, LINE and BRINGUP conditions.** In
   scenario mode the probe's closing `/proc` snapshot is taken after the scenario has already
   torn the cell down, so the deltas describe an empty container. The analyser prints
   0.01 cores and 0.10 GiB for those rows; **both are artefacts and neither is a measurement.**
   The CPU appetite quoted in section 2 comes from the IDLE runs only.
6. **`criteria.md` was frozen by hash rather than by commit.** The campaign convention says
   "frozen at the commit that introduces this file"; this campaign had no mandate to commit,
   so `raw/FREEZE.txt` records the SHA-256 of `criteria.md` and every harness file, the UTC
   timestamp, and the repository HEAD, all taken before the first trial started.

---

## 8. Threats to validity

- **One machine, one day.** Everything here is this M4 Pro. The CPU *curve* transfers better
  than any point on it, and even the curve is a curve at 12 available cores.
- **The background stack was left running.** Quantified per trial (4.4-9.6 % CPU) and
  deliberately not stopped, unlike the second-world campaign. The idle median landing at
  1.060 against that campaign's 1.097 **with the stack stopped** suggests the contamination
  is small — but the two campaigns differ in that and in this campaign's in-window
  instrumentation (Deviation 1), so the comparison is indicative, not clean.
- **`docker update --cpus` is a cgroup quota, not fewer cores.** A quota throttles a process
  that would otherwise use more; a machine with fewer physical cores behaves differently in
  cache and scheduling. The curve is a curve in *available CPU time*, which is the quantity
  contention also takes away, so it is the right variable for the question — but it is not a
  simulation of a smaller machine.
- **Another agent was working in this repository throughout.** Its worktree is separate and
  no cite container other than this campaign's was ever seen running, but the host was
  shared. `raw/*.host.txt` is the record.
- **The `IDLE_1` outlier is unexplained**, and this campaign refuses to discard it. The
  quoted median includes it.
- **The proxies in section 3 are proxies.** `SKILL_CEILING_S` and `LEG_CEILING_S` are assessed
  against intervals derived from log timestamps, not against the intervals the code actually
  times. They are consistent across runs, which is why they are usable, and they are not the
  same quantity.
- **Scenario verdicts are incidental here and are not a campaign result.** For the record:
  `pick_and_place` 3/3 cycles passed and 2/3 passed teardown (`CYCLE_2` failed on
  `parameter_bridge` exiting `-4`, which belongs to the family the
  [teardown campaign](../2026-08-27-teardown-signal-family/results.md) left inconclusive);
  `continuous_line` passed cycle and teardown **2 of 2**; `bringup` passed **2 of 2**. No thresholds were registered for
  any of that and it must not be read as a rate.

---

## 9. Registered as unmeasured, and still unmeasured

- **GPU and display cost.** Untestable on this host, as registered. Needs a Linux
  workstation. C6 is excluded for the *recorded* figure by the argument in section 2, which
  is not the same as measuring it.
- **The machine that produced the recorded figure.** Not identified by any record, and this
  campaign could not identify it.
- **The tree at `47681f6`.** Inspected, not run.
- **Why Gazebo's `real_time_factor` field over-reports under CPU starvation.** Measured,
  unexplained.
- **Why the cell degrades faster than linearly below two cores.** Measured, unexplained. A
  callgrind or a native-Linux `perf` run would attribute it; `perf` does not work under
  Docker Desktop's kernel and that is a hand-back, not an impossibility.
- **Whether the recorded figure came from an explicit Docker allocation or from
  contention.** Both reach it; nothing distinguishes them from here.
- **`DELIVERY_CEILING_S` and `TRAJECTORY_CEILING_S`.** Their intervals were not instrumented,
  so rule D3 reports them as not assessed.
- **Anything about physical hardware.** No physical arm is in this measurement; the layout is
  `PROVISIONAL`.
