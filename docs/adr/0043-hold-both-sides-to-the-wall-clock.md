# ADR-0043: Hold both sides to the wall clock — throttle the generated world, and require RTF >= 1.0 on both concurrently

- **Status:** Proposed (corrected 2026-08-29) — **half 1 is implemented, half 2 is not, and
  this record went on saying neither was.** `tools/cite_tools/generate/world.py` sets
  `REAL_TIME_FACTOR = 1.0` and the generated `workspace/src/cite_generated/worlds/cell_a.sdf`
  carries `<real_time_factor>1</real_time_factor>`. See the section
  "Correction — 2026-08-29: half 1 is implemented and measured, and the status line still said
  nothing was", below.
  **The record stays `Proposed` because half 2 is not merely unmeasured — it is unmeasurable
  today.** Promotion needs the *concurrent* measurement of both sides sustaining 1.0, a
  concurrent measurement needs two sides, and nothing has ever brought a pair up
  ([ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)). Nothing in the tree
  measures a real-time factor during a run at all; the figures in the correction below were
  taken by hand, off a published campaign's method, and no CI step or scenario asserts one.
  **When written this record was `Proposed` and nothing was implemented**, and that sentence
  is kept rather than replaced: at `f1f914f` `world.py` set `REAL_TIME_FACTOR = 0.0` and the
  generated world carried `<real_time_factor>0</real_time_factor>`.
- **Date:** 2026-08-29
- **Deciders:** Docs-writer agent, from the requirement derived in §5 of
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md)
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`docs/measurements/2026-08-29-real-time-factor-conditions/`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md),
  charter §4 (P1, P4, P6, P8)

## Correction — 2026-08-29: half 1 is implemented and measured, and the status line still said nothing was

**What was wrong.** *"Nothing implemented"*, together with the two specific facts it rested
on. Both are now false. `94561bf` set `REAL_TIME_FACTOR = 1.0` and regenerated the world, and
left this record untouched. A reader meeting the status line would conclude that the throttle
was still an open proposal and that the tree still free-runs. It does not.

**What is true, established against the tree rather than taken from a report.**

| Claim in the status line | State at this commit | Established by |
|---|---|---|
| "`world.py` sets `REAL_TIME_FACTOR = 0.0`" | **false** — `1.0` | `grep -n 'REAL_TIME_FACTOR = ' tools/cite_tools/generate/world.py` |
| "`cell_a.sdf` carries `<real_time_factor>0</real_time_factor>`" | **false** — `1` | `grep -n real_time_factor workspace/src/cite_generated/worlds/cell_a.sdf` |
| "nothing anywhere measures a real-time factor during a run" | **still true** | `grep -rn real_time_factor workspace/ tools/ tests/` finds the generator, its template and the generated world, and no measurement |
| "let alone two concurrently" | **still true, and blocked** | nothing brings a pair up — ADR-0041's correction |

The constant's comment was rewritten in the same change rather than left contradicting the
value it justifies, and it carries the warning this record needs it to carry: that half 2 is
a requirement on the machine, that nothing measures it, and that Gazebo's own
`real_time_factor` field is not the instrument for it.

**Half 1 was a prediction and is now a result, and the two halves of that result have
different weight.** This record predicted a bounded regression: a throttle is a ceiling, so it
costs nothing below 1.0 and gives back headroom above it. That prediction is borne out, with
one caveat named under the table.

| Condition | Throttled | Unthrottled comparator |
|---|---|---|
| Idle cell | **0.9961** | **1.094** |
| `pick_and_place` | **0.574 / 0.586** | **0.582** |
| `continuous_line` | **0.657 / 0.656** | **0.681** |

**Read the right-hand column's provenance before using it.** `0.582` and `0.681` are
[`2026-08-29-real-time-factor-conditions`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md)'s
published CYCLE and LINE medians, over 3 and 2 runs, with thresholds registered before the
first trial. `1.094` is from the same campaign but from a different table — it is the first
12-CPU window of its CPU curve, an idle cell at full allocation, and **not** its IDLE
condition median, which is 1.060 over six trials. Cite the campaign for any of the three.

**The left-hand column is not a campaign and must not be cited as one.** The three throttled
figures were taken by the change that landed half 1, on one machine, **two runs per
scenario**, with **no thresholds registered in advance** and **no directory under
[`docs/measurements/`](../measurements/README.md)**. They are recorded in `29068d4`'s commit
message and nowhere else. They are the size of the evidence, not a published result, and a
second machine has never been asked.

**What they do support, stated no more strongly than that, and with the one place the
agreement is imperfect named.** Under load the throttled figures sit on top of the
unthrottled ones: the cycle's 0.574 / 0.586 straddles the campaign's 0.582 median, one run
inside its 0.578 - 0.607 range and one 0.004 below it. The line's 0.657 / 0.656 is **below**
the campaign's 0.670 - 0.692 range, by about 2 %, and it is not honest to call that identical
— with two runs against two and no pre-registered band, it is also not a difference this
evidence can attribute to the throttle rather than to the host. The mechanism is not in doubt
either way: under load this cell runs at roughly 0.58 and 0.67, far below the 1.0 ceiling, so a
ceiling has nothing to bind on there — which is this record's own argument, not an inference
from the table. What the table adds is that the idle row is where the ceiling does bind, and
that it binds by the expected amount: 1.094 free-running, 0.9961 held. So on this host **the
throttle binds only where the cell has spare capacity, and is at or near a no-op under
load**. **It says nothing about half 2**, which is a claim about two sides sustaining 1.0 and
not about one side not being slowed.

**What survives, and it is the whole decision.** Both halves stand. Half 1 is a ceiling and
half 2 is the capacity requirement, and neither substitutes for the other — the measurement
above is a demonstration that half 1 is cheap here, not evidence that half 2 is met. No
scenario wall-clock ceiling was changed and none needed to be, which is what the audit
sequencing in *What this costs us* asked for.

**How the error survived.** The implementing change reasoned correctly that this record could
not be promoted, and wrongly that a record staying `Proposed` therefore needed no edit. The
status block was carrying two claims at once — *not binding yet* and *not built yet* — and
only the first survived. The transferable part is that **half an implemented decision is the
worst state for a status line to be stale in**: a reader checking whether the world is
throttled would have read "nothing implemented", trusted it, and either re-done the work or
written a document around a `0` that has not been in the tree since `94561bf`.

## Context

### Nothing throttles anything today

**[Corrected 2026-08-29 — see the Correction section above.]** **The heading and the
paragraph below describe the tree at `f1f914f`. Since `94561bf` the generated world declares
`1` and the generator's comment justifying `0` has been replaced. They are left as written
because the argument the rest of this section builds needs the starting state.**

The generated world sets `real_time_factor` to `0`, which in Gazebo means unthrottled: the
server steps as fast as it can. The generator states the reason in the constant's own
comment — scenarios are graded on outcomes and wall-clock bounds rather than on matching real
time, and throttling would only make them slower.

> **Verified 2026-08-29.** In the SDFormat 1.9 specification the generated world declares,
> `physics/real_time_factor` is a `double` described as *"target simulation speedup factor,
> defined by ratio of simulation time to real-time"*, **with a default of `1.0`** —
> <https://github.com/gazebosim/sdformat/blob/sdf13/sdf/1.9/physics.sdf>. So the generator is
> overriding the specification's own default in order to free-run, and half 1 of the decision
> below is a return to it. That `0` in particular means unthrottled is Gazebo Sim's
> behaviour rather than a statement in the specification; the campaign observed it directly,
> measuring a solo cell above 1.0 (RTF 1.097, and 1.663 with hulls) while the world declared
> `0`.

That reasoning is sound for **one** simulation graded on outcomes. It does not survive a
second simulation that has to agree with the first about what time it is.

### Two sides in one window, running at visibly different rates, with no fault anywhere

The campaign's `PAIR_1` ran the two sides at **0.888 and 0.698** in the same wall-clock
window — a **27 % rate difference between the plant and its counterpart**, from two
identically configured cells on the same L0 model, the same solver and the same host, with
nothing wrong on either side. That is the pair to cite: no defect produced it and no defect
would have to.

Two free-running simulations therefore have sim clocks that separate immediately and without
bound. [L5](../architecture/L5-twin-synchronization.md)'s *Time* section already says a mixed
time base "produces divergence numbers that look plausible and mean nothing"; the campaign
measured it.

### Why this is not comparable to a latency figure, worked with the campaign's numbers

A transport latency is bounded and stationary. A clock deficit is neither: at real-time
factor `r`, a simulator's clock falls behind the wall clock at `(1 - r)` seconds per second,
and that deficit **accumulates without bound**.

Put the campaign's two measurements against each other:

- measured paired real-time factor, **`r = 0.866`** → deficit `1 - 0.866 = 0.134` s per second,
  i.e. **134 ms of lag for every second of operation**;
- measured p99 one-way mirroring latency across the domain boundary, **3.131 ms**
  (20,000 samples at 150 Hz, wall-clock stamps, one host clock).

The deficit passes the p99 latency after

```
0.003131 s / 0.134 s per s  =  0.0234 s  ->  23 ms of wall time
```

**Everything after that first twenty-three milliseconds, mirroring lag is the real-time-factor
deficit and nothing else.** After one second it is about forty times the p99. The campaign
reaches the same figure by the same arithmetic and it is reproduced here rather than
asserted.

The conclusion to carry: **once a side cannot hold real time, mirroring latency stops being
the quantity that matters.** The clock deficit dominates it, and no amount of transport
tuning helps. L5's failure-mode table names *"mirroring lag treated as divergence"* — and on
this evidence the dominant term in mirroring lag is not the network at all.

The latency figure keeps its own recommendation, which is the campaign's and not this
record's: p99 landed in the registered band `1 ms <= p99 < 6.667 ms`, so `DivergenceMetrics`
should carry a latency field, and the **max of 20.86 ms is three control periods**, so the
tail is not negligible even where the percentiles are.

## Options considered

### Option A — leave both unthrottled and correct for the clock difference in the metric

Compute each side's offset and subtract it. Rejected on two counts. The correction is
unbounded and needs a shared time base to compute, which is the thing that is missing; and it
makes every divergence number depend on an estimate rather than on a measurement, which is
what P8 refuses. L5 already names the outcome: a mixed time base produces plausible numbers
that mean nothing.

### Option B — throttle only the counterpart, slaving its clock to the plant's

The cheapest thing that would make 2.A's numbers look good, which is why it is the option
worth stating. Rejected. It makes the counterpart's rate a function of the plant's, so a
plant that stalls drags the counterpart down with it and the pair reports agreement while
both are wrong — the divergence metric would be structurally unable to see the one fault it
most needs to see. And it does not survive 2.B: a real arm cannot be slaved to a simulator's
clock, and the wall clock is the only clock both sides can ever share.

### Option C — a per-run override, so solo scenarios keep running unthrottled

Genuinely attractive, because the whole cost of this decision is scenario wall-clock time.
Rejected: an override that can be set per run can be set on one side of a pair and not the
other, which re-creates exactly the divergence this decision exists to remove, and it puts
the value in two places (P1). If CI time later forces the question, reopen it deliberately —
see *What we will have to revisit*.

### Option D — throttle both to real time, and require both to sustain it

Chosen.

## Decision

**Neither side runs free. Both are held to the wall clock.** Two halves, and both are
required:

1. **The generated world declares a real-time factor of `1.0`**, replacing today's `0`. It
   stays generated and is never hand-edited (ADR-0021, ADR-0004), so the value exists once
   and is identical on both sides by construction.
2. **Both sides must sustain a measured real-time factor of at least 1.0, concurrently.**
   This is a requirement on the machine, checked by measurement, not a setting.

The two halves do different work and neither substitutes for the other. **Half 1 is a
ceiling, not a floor**: the specification calls it a *target* speedup factor, so it bounds
how fast a server may run and cannot make a slow one faster. What it buys is that a side with
headroom does not run ahead. **Half 2 is the capacity requirement**, and only measurement
answers it. The campaign states the pairing
exactly: capacity alone is not enough; the throttle has to exist as well.

### What the target machine must provide

Stated as requirements on the machine 2.A runs on. The development host is not that machine
and its inability to meet these is a fact about a laptop, not a reason to shrink the design
([ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)). Every figure below is
the campaign's; read it there rather than trusting the summary.

1. **Serial throughput is the binding requirement, and cores are not.** With
   [ADR-0028](0028-convex-hull-collision-meshes.md)'s hull collision meshes, a machine with
   the campaign host's per-core throughput already runs two worlds above real time; without
   them it needs **at least 1.16x** that per-core throughput to reach 1.0 at all, with no
   margin left. The pairing penalty appeared at **68 % core occupancy** — a third of the
   machine idle and not helping — so it is contention below the core and **more cores will
   not buy it back.**
2. **Cores: at least 12, and treat that as a floor.** Two hull-condition cells drew 9.3. The
   operator's GUI is not in that figure and is **completely unmeasured** — every run in the
   campaign was headless on a machine that refuses GUI.
3. **Memory is not the constraint.** Two hull cells used **1.72 GiB**. 8 GiB is comfortable;
   the 7.653 GiB the campaign ran in was never close to its limit.
4. **The measured margin is not a work allowance.** Every cell in the campaign was **idle**,
   holding home pose after bring-up. Motion, planning, contact and grasp all cost more and
   **none of it was measured.** A machine sized at exactly the measured margin will not hold
   RTF 1.0 through a `continuous_line` run, and the campaign cannot say by how much it will
   miss.

The pair that fixes the numbers behind item 1 — vendor meshes at **0.864 / 0.869**, missing
the condition; hulls at **1.162 / 1.173**, meeting it — is **one run**, run on the same
machine with the same design, and the campaign labels it as one. Item 1 rests on a single
measurement and should be re-taken on the target machine.

## Consequences

### What this gets us

- **Two sim clocks that agree with the wall clock, and therefore with each other.** That is
  the precondition for any divergence number meaning anything, and without it 2.A's
  instrument would report the artefact instead of the quantity.
- **Mirroring latency becomes the quantity it was measured as** — sub-cycle, bounded, worth a
  field in `DivergenceMetrics` — instead of being buried under a term forty times its size.
- **The same decision hardware forces, taken early.** A real arm runs at 1.0 by definition, so
  in 2.B the wall clock is the only shared clock available. Throttling the simulation to 1.0
  is what P2 asks for at the clock.
- **A side that cannot hold real time becomes a stated failure** rather than an unexplained
  divergence trend with no software cause.

### What this costs us

- **Every scenario gets slower on any machine where a cell today free-runs above 1.0.** The
  campaign measured a solo cell at **RTF 1.097** with vendor meshes and **1.663** with hulls;
  a ceiling of 1.0 gives all of that headroom back in wall time. This is precisely the cost
  the generator's existing comment names, and this decision accepts it.
  **[2026-08-29: measured on this host, and much smaller than the campaign's idle figures
  imply. Under load the cost is at most a couple of percent of real-time factor and may be
  none — this host runs the loaded scenarios far below 1.0, where a ceiling has nothing to
  bind on. See the table in the Correction section above, and read its provenance note before
  quoting either column.]**
- **Every wall-clock ceiling in the scenario suite is justified against a real-time factor**
  (`tests/scenarios/bringup.py`, quoted in ADR-0028), so the change that lands this must
  revisit them rather than discovering them by timeout. **Ask
  `grep -rn '^[A-Z_]*CEILING_S = ' tests/scenarios/` for the list rather than trusting this
  sentence** — at this commit it returns **six names in eight declarations**, across three
  files. `BRING_UP_CEILING_S`, `DELIVERY_CEILING_S`, `TRAJECTORY_CEILING_S` and
  `SKILL_CEILING_S` in `tests/scenarios/bringup.py`; `BRING_UP_CEILING_S` and
  `CYCLE_CEILING_S` in `tests/scenarios/pick_and_place.py`; `BRING_UP_CEILING_S` and
  `LEG_CEILING_S` in `tests/scenarios/continuous_line.py`. **`BRING_UP_CEILING_S` is three
  constants wearing one name** — it is declared separately in each file and does not carry
  the same value in all three — so it is revisited three times, not once. All four in
  `bringup.py` sit under one comment block, and that block is where the 0.14 figure is
  recorded in the tree, so they are the four whose stated basis the correction to
  [ADR-0028](0028-convex-hull-collision-meshes.md) bears on directly.
- **The regression is bounded, and the bound is small enough to state.** A throttle is a
  *ceiling*, so on a machine already below 1.0 it changes nothing at all and no ceiling moves.
  Where a machine free-runs above 1.0, wall time grows by exactly the factor it was
  free-running at, so the growth is bounded by that machine's own free-running real-time
  factor. **The largest this project has ever observed is 1.663**, on the campaign host, idle,
  under hull collision geometry; with the vendor meshes the scenarios actually run today it
  was 1.097. Both are the campaign's figures and neither is a prediction for another machine —
  but the shape of the answer is settled: a scenario cannot become more than its host's
  free-running factor slower, and cannot become slower at all below 1.0.
- **This must not land while the ceiling audit is in flight.** A campaign is auditing the
  scenario wall-clock ceilings as this is written. Throttling changes the quantity that
  campaign is measuring, so landing half 1 mid-campaign invalidates its baseline and the
  audit would have to start again. The sequencing is: the audit completes, then the throttle
  lands, then the ceilings are re-derived against 1.0. Not the other order, and not both at
  once. **[2026-08-29: that campaign has published —
  [`2026-08-29-real-time-factor-conditions`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md).
  It changed no ceiling and found none too tight or too loose, so the first step of the
  sequencing above is done and its §3 table is the baseline to re-derive against.]**
  **[2026-08-29, later: the throttle has since landed at `94561bf` and no ceiling was
  changed — `grep -rn '^[A-Z_]*CEILING_S = ' tests/scenarios/` still returns the same six
  names in eight declarations at the same values. The re-derivation this bullet asks for was
  an audit that found nothing to move, and the measurement in the Correction section above is
  why: under load this host is nowhere near the ceiling the throttle imposes.]**
- **How much slower, on this project's own development host, is not known** — and that is a
  gap in the tree rather than in this record. The tree records RTF **0.14** with
  `joint_states` at roughly 21 Hz; the campaign measured **1.097** and 158 Hz on an idle cell
  and could not reproduce 0.14, a factor of 7.8. Its *"An absolute, and a contradiction"*
  section records that the figure in the tree carries **no condition and no machine**, so
  neither number can be used to predict what throttling costs here. Re-measuring it with its
  condition written down is the campaign's own recommendation and it is cheap.
  **[2026-08-29, and this bullet's premise no longer holds: that re-measurement is
  [`2026-08-29-real-time-factor-conditions`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md),
  which reproduced 0.14 with its condition — the cell confined to about one CPU core — and
  measured the same host unconfined. So the two figures do not contradict each other and both
  are usable: at a full allocation this host free-runs above 1.0 and the bound stated two
  bullets above applies to it; at one core it is far below 1.0, where a throttle is a ceiling
  and costs nothing. Cite that campaign for either figure rather than this bullet.]**
  **[2026-08-29, later: and the question this bullet opens — how much slower throttling makes
  this host — now has an answer taken directly rather than predicted. It is in the Correction
  section above, with the weight of two runs per scenario on one machine and no thresholds
  registered in advance.]**
- **A new requirement that something has to check.** "Both sides sustain >= 1.0 concurrently"
  is a claim about a running pair, and nothing measures it today. Under P6 and P8 the
  requirement is not met until a scenario or a CI step answers it, and this record is not that
  check. **[2026-08-29: still true, and now the sole reason this record is not promoted. Note
  that it is blocked rather than merely outstanding — there is no running pair to measure.]**
- **Throttling does not make a slow machine fast.** On a machine below 1.0, half 1 changes
  nothing at all and half 2 simply fails. That is the intended behaviour — the failure is
  stated instead of silently producing plausible numbers — but nobody should read the
  throttle as a fix.

### What we will have to revisit

- **When the target machine exists.** Re-derive the requirement rather than adjusting it; that
  is the campaign's own instruction, and every figure above is a ratio taken at 12 vCPUs on
  one architecture under one container runtime.
- **If a future Gazebo parallelises the physics step.** The campaign names this as the
  condition under which item 1 changes, because the whole argument rests on a serial physics
  loop.
- **If CI wall-clock time becomes the binding constraint.** Option C is the thing to reopen,
  and it must be reopened deliberately, with the answer written down — not by adding an
  environment variable to make a slow job finish.
- **When something measures RTF under load.** Every figure here is from an idle cell, and item
  4 is the reason this list is not the last word.
- **If the friction-grasp re-run says that hulls break the grasp.** Item 1 above rests on
  [ADR-0028](0028-convex-hull-collision-meshes.md), and that record's 2026-08-29 amendment
  gates its own promotion on a measurement that **can fail**: the friction-grasp campaign must
  be re-run under hull collision geometry, and no grasp has ever been attempted under one. A
  convex hull fills the space between the gripper fingers, and grasping in this cell is held
  by friction alone ([ADR-0029](0029-simulated-grasping-by-friction.md)), so the contact
  surface *is* the mechanism. **If that re-run fails, the only demonstrated path to "both
  sides sustain 1.0" on a machine of the campaign host's class is gone** — the pair meeting
  the condition met it with hulls, and the same pair with vendor meshes missed it.
  Two fallbacks, named now so that the answer is not improvised then:
  1. **Per-link geometry for the fingers, hulls everywhere else.** This is ADR-0028's own
     stated answer to the concavity biting — *"per-link geometry for the fingers, not
     abandoning hulls elsewhere"* — and the fingers are a small fraction of the twelve links
     the reduction comes from, so most of the speed should survive. **Should** is the right
     word: nothing has measured a mixed-geometry cell, and this fallback is a plan rather than
     a result.
  2. **A faster machine.** Without hulls the requirement in item 1 is at least 1.16x the
     campaign host's per-core throughput, reaching 1.0 with no margin — and item 4 says a
     machine sized at no margin will not hold 1.0 through a working run. So this fallback is a
     hardware budget with an unmeasured top-up, not a substitution.
  If neither is available, **this record's requirement still stands and 2.A waits for a
  machine that meets it.** The requirement is not relaxed to fit the host; that is
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s standing instruction.
