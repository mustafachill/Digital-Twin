# Criteria — what real-time factor this cell actually achieves, and under what condition

- **Campaign:** `2026-08-29-real-time-factor-conditions`
- **Written:** 2026-08-29, **before the first trial ran.** Frozen at the commit that
  introduces this file (campaign convention, [`../README.md`](../README.md)).
- **Question this exists to answer:** three places in this repository carry a real-time
  factor of "about 0.14" for the simulated cell — `tests/scenarios/bringup.py`,
  `tests/scenarios/pick_and_place.py`, `tests/scenarios/continuous_line.py`,
  [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md) and
  [CLAUDE.md section 2](../../../CLAUDE.md). **None of them names a machine, a scene, a
  load, or a measurement method.** The
  [second-world campaign](../2026-08-28-second-world-cost/ANALYSIS.md) incidentally
  measured an idle cell on this host at RTF **1.097**, a factor of 7.8 away, and
  deliberately did not overwrite the record — it reported that the figure needs
  re-measuring with its condition stated. This is that measurement.
- **Related:** [ADR-0028](../../adr/0028-convex-hull-collision-meshes.md),
  [L2](../../architecture/L2-control-and-hal.md),
  [`2026-08-28-second-world-cost`](../2026-08-28-second-world-cost/ANALYSIS.md),
  charter section 4 (P7, P8).

---

## 0. The rule this campaign is written under

The second-world campaign's section 0 rule is **adopted verbatim and extended**, because
this campaign is in the awkward position of deliberately publishing absolutes.

**The development host is not the target machine.** It is a macOS arm64 laptop running
Docker Desktop's Linux VM, with no GPU passthrough and with the whole ROS stack executing
in an emulation-adjacent environment. An absolute real-time factor measured here is a fact
about this laptop.

The extension, which is this campaign's entire reason to exist:

> **An absolute real-time factor may be published here as a fact about a named condition on
> a named machine, and never as a property of "the cell".** Every number below is required
> to carry its machine, its scene, its load and its sampling method. A figure that loses any
> of the four becomes the thing this campaign was created to correct, and reproduces the
> defect one commit later.

**Nothing here derives a requirement.** Requirements come from ratios, and the second-world
campaign already derived them. This campaign corrects a record.

---

## 1. Conditions, declared before the runs

- Host: macOS Darwin 25.5.0, **arm64**, Docker Desktop 28.5.1, Linux VM with **12 CPUs and
  7.653 GiB** as reported by `docker info`. Re-recorded per trial in `raw/host.txt`.
- All measurements **headless** (`./scripts/sim --headless`). `scripts/sim` refuses GUI on
  macOS, so **nothing in this campaign bears on GUI or rendering cost.** That is registered
  as unmeasured in section 7 rather than estimated — and it remains a live candidate
  explanation for the recorded figure that this campaign **cannot test**.
- **Unrelated containers are running and are NOT stopped**, which is a deliberate deviation
  from the second-world campaign, which stopped them. Two reasons: another agent is working
  in this repository concurrently, and the containers are the project owner's own services.
  Measured at campaign start: **15 containers, 6.59 % CPU summed, ~2.0 GiB resident**
  (`docker stats --no-stream`). `docker stats` and host `uptime` are captured **before and
  after every trial** and stored in `raw/`, so contamination is quantified rather than
  assumed absent. **If the idle figure lands near the second-world campaign's 1.097, that is
  also evidence that a background load of this size is not material**; if it lands well
  below, the background stack is a confound and the campaign says so.
- One cell at a time. No paired workload, by instruction: parallel builds have exhausted
  this host's disk twice. Free space is checked before the campaign and after every fifth
  trial; a trial is not started below **20 GiB** free in the VM.
- `gz sim` processes are checked for and killed after every trial; a trial that finds a
  survivor from the previous one is **discarded**, not adjusted.
- Scenarios in this cell are **not deterministic**
  ([cross-cutting-testing](../../architecture/cross-cutting-testing.md), ADR-0027). Every
  figure below is a distribution over repeats, never a reproduction claim.

---

## 2. The measurement method, pinned before any number exists

Question 4 of this campaign's brief asks how RTF should be measured here so that the next
person gets the same answer. That has to be decided **before** measuring, or the method is
chosen by the data. It is:

**RTF is `Δ sim_time / Δ real_time` between the first and last `WorldStatistics` sample of a
stated window**, both fields read from Gazebo's own `/world/cell_a/stats` topic via
`gz topic -e`. This is the definition rather than a filter's output.

- **Source:** Gazebo's `WorldStatistics`, not any instrument of this repository's, so that
  nothing we wrote sits in the measurement path.
- **The `real_time_factor` field is recorded alongside and is not the headline.** It is a
  smoothed instantaneous estimate. Its median, min and max over the same window are stored,
  precisely so this campaign can report whether the two methods disagree — one of the
  candidate explanations for the recorded figure.
- **Warm-up:** the window opens only after **every arm's controller manager reports at least
  three active controllers**, plus a further **30 s**. Readiness is an observed state, never
  an elapsed time (P4).
- **Window:** **120 s**, the second-world campaign's window, chosen so the two campaigns'
  idle figures are directly comparable.
- **Sampling is continuous from launch**, not only during the window. The full series is
  kept, so a window over any other interval — bring-up in particular — can be cut from the
  same run without spending another one.
- **`joint_states` frequency** is measured on `/cite/cell_a/arm_1/joint_states` two ways in
  the same window: `ros2 topic hz --window 200`, and an independent message count over a
  fixed wall interval by a subscriber with a **keep-last-1000** queue. Both are reported.
  If they disagree, that disagreement is a finding about the instrument.

---

## 3. Q1 — What is the RTF of this cell, by condition? (ABSOLUTE, per section 0's rule)

Three conditions, each reported separately with its own spread. **There is no headline
number for "the cell".**

| Condition | What runs | Repeats |
|---|---|---|
| **IDLE** | `./scripts/sim --headless`, brought up, nothing commanded, arms holding pose | **>= 5** |
| **CYCLE** | `./scripts/scenario pick_and_place` — one arm planning, moving, grasping | **>= 3** |
| **LINE** | `./scripts/scenario continuous_line` — three arms, belts, beams | **>= 2** |
| **BRINGUP** | the interval from `gz sim` first publishing statistics to every controller active — **cut from the IDLE runs' own series, costing no extra trial** | = IDLE repeats |

**Reported for each:** median, full range, n. **A single run is not a measurement** and no
condition with n = 1 gets a verdict.

**Validity rule V1**, adopted from the second-world campaign, which fired there: if a
condition's repeats span a range greater than **25 %** of their median, that condition's
figure is reported as **NOISY** and its median is quoted only with the range beside it. It
is not silently averaged into a comparison.

**LINE may not run.** `continuous_line` is `continue-on-error` in CI and failed its cycle in
the only run ever taken off a developer machine (CLAUDE.md section 2). **The RTF measurement
does not depend on the scenario passing** — a run that brings the cell up and drives arms
yields a valid RTF window even if the scenario's own assertions fail — and the write-up
reports the scenario verdict separately from the RTF. If the cell does not come up at all,
LINE is reported as **not measured**.

---

## 4. Q2 — Can 0.14 be reproduced at all? (the question that decides what the record says)

**Definition, fixed now:** the recorded figure is **reproduced** under a condition if that
condition's **median window RTF falls in [0.11, 0.17]** — 0.14 +/- 20 %, a band wide enough
that a genuine match is not rejected on scatter and narrow enough that "much slower" does
not count as a match.

### The candidate conditions, registered before testing, in the order they will be tried

| # | Candidate | How it is tested | Cost |
|---|---|---|---|
| C1 | **Bring-up transient** — the figure was taken while the cell was still starting | cut the bring-up interval out of every IDLE run's continuous series | free |
| C2 | **Load** — taken while an arm was planning and moving | the CYCLE and LINE conditions of Q1 | free |
| C3 | **A smaller CPU allocation** — Docker Desktop's default is far below 12 CPUs, and the figure predates any record of this host's allocation | `docker update --cpus N` against the running cell's container, at N = 2 and N = 4, sampling a fresh 120 s window at each | 1-2 trials |
| C4 | **Sampling artefact** — instantaneous `real_time_factor` versus the window delta, and short `ros2 topic hz` windows versus a counted rate | already recorded in every trial by section 2's method | free |
| C5 | **A different scene or tree state** — the figure entered the tree at `47681f6` on 2026-08-24 | inspect what that commit changed; **rebuilding that commit is out of budget and is registered here as a bounded gap** rather than attempted | inspection only |
| C6 | **GUI / rendering in the command path** | **cannot be tested on this host at all** — `scripts/sim` refuses GUI on macOS. Registered as unmeasured, section 7 | not possible |

### The arithmetic hypothesis, registered now so that confirming it is not hindsight

**`21 / 150 = 0.14` exactly.** The two halves of the recorded figure — "RTF about 0.14" and
"`joint_states` at roughly 21 Hz against a configured 150 Hz" — are therefore not
necessarily two measurements. They are consistent with **one** measurement of a publication
rate, with the RTF *derived* from it by division.

That matters because the derivation has a known failure mode that this campaign can test:
`ros2 topic hz` measures what a Python subscriber *receives*, which on a saturated host is a
lower bound on what was published. If the derived reading is what happened, then the
recorded figure is not a measurement of the physics step at all, and no amount of measuring
the physics step will reproduce it.

**Decision rule D2, fixed before the data:**

| Outcome | What the campaign concludes |
|---|---|
| Some condition in C1-C5 lands in **[0.11, 0.17]** | **CONDITIONAL.** The figure is right and the *condition* is the missing thing. The three records must gain that condition, and the ceilings justified against it are justified |
| No condition lands in the band, and the idle figure replicates near the second-world campaign's | **NOT REPRODUCED.** The records carry a figure that this machine does not produce under any condition tried, and must say so — naming what was tried, per P7 |
| Conditions land on both sides but none inside | **PARTIAL.** Report the bracketing conditions and refuse a single replacement number |

**Rule D2b.** "Not reproduced" is **not** "wrong". A figure that this host cannot reproduce
in 2026-08 may have been correct on the machine and tree that produced it in 2026-08-24.
The campaign is permitted to conclude that the figure is **unattributable** — no machine, no
method, no condition recorded — and that is a different and weaker claim than "false". The
write-up must use whichever it earned.

---

## 5. Q3 — Which wall-clock ceilings depend on the figure, and are any wrong?

**This campaign is read-only on source and changes no ceiling.** It enumerates them and
reports.

Every ceiling in `tests/scenarios/` whose comment cites the 0.14 figure is listed with: its
value, what it was assumed to cover, and the **measured** duration of the thing it bounds,
taken from this campaign's own runs.

**The margin figure:** `M = ceiling / measured duration of the bounded interval`, using the
**slowest** observed instance of that interval, not the median.

**Pre-registered interpretation bands for M:**

| Band | Reading |
|---|---|
| M < 1.5 | **TOO TIGHT.** Ordinary variation will hit it; this ceiling is a flake source |
| 1.5 <= M <= 10 | **APPROPRIATE.** Catches a hang, tolerates a slow run |
| M > 10 | **TOO LOOSE.** A regression an order of magnitude in size would still pass. A ceiling that can no longer fail is not a check |

**Rule D3.** A ceiling is reported as `UNAFFECTED` only if its comment does not cite the
figure **and** its bounded interval was measured here. A ceiling whose interval this
campaign did not measure is reported as **not assessed** — never as fine.

---

## 6. Q4 — How should RTF be measured here?

Answered by section 2, which is a decision made before the data. What section 2 cannot
decide in advance is whether the methods **disagree**, and that is the reportable result:
the window delta, the smoothed `real_time_factor` field, `ros2 topic hz`, and a counted
message rate are all recorded in every trial, and the write-up publishes the spread between
them.

**Pre-registered reading:** if the four methods on one idle run span more than **20 %** of
their mean, then **method alone can account for a large discrepancy between two honest
observers**, and that becomes this campaign's primary recommendation regardless of what
Q2 concludes.

---

## 7. Registered as unmeasured before the campaign starts

Named now so that silence later is not mistaken for absence of the question.

- **GUI and rendering cost.** Untestable on this host — `scripts/sim` refuses GUI on macOS.
  It stays a live candidate explanation for the recorded figure and this campaign **cannot**
  eliminate it. Needs a Linux workstation.
- **Any machine other than this one.** Including the machine that produced the recorded
  figure, whose identity is not in the record.
- **The tree as it stood at `47681f6`** (2026-08-24), where the figure entered. Rebuilding
  and running a five-day-old tree is out of this campaign's budget; C5 is an inspection of
  what changed, not a measurement of what it cost.
- **Whether the physical cell behaves this way.** No physical arm exists in this
  measurement; the layout is `PROVISIONAL`.
- **Thermal state.** The host is a laptop and was not thermally controlled. The
  second-world campaign found one whole block depressed ~30 % with no established cause;
  if this campaign sees the same, it reports it and does not explain it.

## 8. Deviations from this document

Recorded in the write-up as numbered deviations, applied to data already collected. No
threshold above is moved after the first trial.
