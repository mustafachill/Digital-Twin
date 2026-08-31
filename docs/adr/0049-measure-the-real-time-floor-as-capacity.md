# ADR-0049: Keep the real-time floor and measure it as capacity, not as a throttled rate

- **Status:** Proposed — **nothing in this record is implemented, and the tree state it is
  written against is this.** `workspace/src/cite_generated/worlds/cell_a.sdf` carries
  `<real_time_factor>1</real_time_factor>` (ADR-0043 half 1, landed at `94561bf`);
  `model/facility/zones.yaml` declares `twin: {sides: single}`, so no pair comes up on a clean
  checkout; and **nothing in the tree measures a real-time factor or a clock deficit during a
  run** — `grep -rn real_time_factor workspace/src tools tests scripts` on 2026-08-31 reaches
  the generator, its template, two world files and two generator tests, and no measurement.
  **This record is promoted to `Accepted` when all three hold**: the instrument decision 5
  names exists; a campaign under [`docs/measurements/`](../measurements/README.md) has run the
  matrix in *What we will have to revisit* item 1 with thresholds registered before its first
  trial and its machine named; and the two thresholds this record deliberately declines to set
  — the capacity margin above 1.0, and the operating deficit bound — have been set by that
  campaign or by the record it forces. **Promotion is not a claim that the requirement is met.**
  It is a claim that the requirement is checkable, which today it is not.
- **Date:** 2026-08-31
- **Deciders:** Docs-writer agent, from the four measurements named in *Context*. **The clause
  that refuses to relax the floor is not this agent's** — it is the project owner's standing
  instruction recorded in [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  that machine requirements are stated as requirements and never shrunk to fit a development
  host. Everything else here is owed the owner's ratification.
- **Related:** [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) (whose half 2 this record
  restates; half 1 is untouched),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md),
  [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md) (which answers decision 3's "where that
  value rides, and what it is called"),
  [L5](../architecture/L5-twin-synchronization.md),
  [`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`docs/measurements/2026-08-29-real-time-factor-conditions/`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md),
  charter §4 (P2, P6, P7, P8), charter §8 (Phase 2).
  **This record changes no clause of charter §8's Phase 2 exit criterion**, which is a
  physical arm driving its twin with a defended fidelity number and does not mention
  real-time factor; read there rather than taking it from here.

## Context

### The requirement, and the four measurements that bear on it

[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md) has two halves. Half 1 — the generated
world declares `real_time_factor` `1.0` — is implemented. Half 2 requires **both sides of a
pair to sustain a measured real-time factor of at least 1.0, concurrently**, and it is not
met.

Four measurements bear on it. **Their figures are held where they were taken and are cited
rather than copied** (P1); what belongs here is their strength, which is the same in all four.

| Where the figures are | What it measured |
|---|---|
| [`2026-08-28-second-world-cost`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md) §5 | a pair, vendor meshes and hull meshes, unthrottled, on the campaign host |
| [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s 2026-08-30 correction | the first paired bring-up, vendor meshes, throttle in the world, four 60 s windows |
| [ADR-0028](0028-convex-hull-collision-meshes.md)'s implementation note | a pair, both geometries, throttle in the world, two 120 s windows per condition, both sides sampled concurrently |
| [`2026-08-29-real-time-factor-conditions`](../measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md) | a solo cell against CPU allocation, throttled and unthrottled |

**Only the first and last are campaigns.** The two ADR-held sets have **no thresholds
registered in advance**, **no directory under [`docs/measurements/`](../measurements/README.md)**,
one machine each, and were taken by the implementing agent of the change that produced them
and not re-taken by review. Every record that holds them says so. **No decision below rests on
either of them alone**, and where one is load-bearing it is named as such.

The shape of the result: the paired vendor figure is short of 1.0 by roughly an eighth, on
both hosts and with and without the throttle. Hulls — the lever the campaign named for closing
the gap — moved a pair by about **1.35x** on the campaign host, enough to clear 1.0, and by
about **1.10x** on the host of the two later sets, not enough. Both gains are ratios computed
here from the two sources' own tables; the tables are theirs.

### The requirement cannot be satisfied as written, and that is a property of the requirement

This is the finding that decides the record, and it is not about any host.

**Verified in upstream source on 2026-08-31**, in `src/SimulationRunner.cc` of `gz-sim`, which
is Gazebo Harmonic's simulation library (Harmonic is Gazebo's eighth named release and ships
`gz-sim` 8 — <https://github.com/gazebosim/gz-harmonic>). Read at branch `gz-sim8` and at tag
`gz-sim8_8.0.0`, both ends of the release series, because **the installed patch version was
not determined** — `infra/docker/Dockerfile` installs the `gz-harmonic` metapackage from apt
and pins no version.

- The declared factor becomes a period: `updatePeriod = stepSize / desiredRtf`, and
  `desiredRtf < 1e-9` sets `updatePeriod` to zero. That is the source-level confirmation of
  something ADR-0043 could only record as observed: `real_time_factor 0` means unthrottled.
- Simulated time advances by exactly `stepSize` per iteration, and an iteration never begins
  sooner than `updatePeriod` after the previous one. **So `d(sim)/d(real)` is bounded above by
  the declared factor by construction**, and reaches it only if no step ever overruns.
- **An overrun is not recovered.** At `8.0.0` the next deadline is anchored to the start of
  the previous step (`prevUpdateRealTime + updatePeriod`), so a step that runs long loses that
  time permanently. On the current branch the deadline advances on a grid
  (`nextUpdateTime += updatePeriod`), which absorbs a backlog of up to one period and then
  **discards it** (`if (nextUpdateTime < now) nextUpdateTime = now + updatePeriod`). The two
  variants differ in how much they tolerate and agree on what they never do, which is bank
  time.

The consequence is arithmetic. Under half 1, a measured real-time factor is capped at 1.0 and
falls below it by the sum of the run's overruns. **A machine with any amount of spare capacity
measures just under 1.0; a machine with vast spare capacity measures just under 1.0.** ADR-0043's
own throttled idle row is below 1.0 while its unthrottled comparator for the same cell is above
it — read that table there.

So "both sides sustain a **measured** real-time factor of at least 1.0" is, with half 1 in
force, a test that no machine passes and that returns almost the same answer for an adequate
machine and an over-provisioned one. **Part of "the requirement is not met" is the requirement's
shape.** Only part: a paired vendor figure short of 1.0 by an eighth is far outside anything a
throttle loss explains, and the machine is genuinely short.

### The clock-deficit argument stands, and it forbids less than it looks like it forbids

ADR-0043's argument — at rate `r` a side falls behind wall clock by `(1 - r)` per second, the
deficit **accumulates without bound**, and at the measured paired rate it overtakes the measured
p99 mirroring latency after about 23 ms of wall time — is not weakened by anything above, and
nothing in this record replaces it. It is the reason the floor stays.

But it has a consequence that record does not draw. **A throttle approaches 1.0 from below and
never from above.** So at *any* hardware budget the throttled deficit is positive and still
accumulates without bound; what a faster machine buys is a smaller accumulation rate, not a
bound. The argument therefore forbids operating **materially** below real time, and it cannot be
discharged by a machine "hitting 1.0", because under half 1 nothing can.

And under the loop read above, **the deficit is a sum of discrete overrun events, not a steady
rate.** Its distribution is the quantity, and a mean real-time factor over a window hides it.
Nothing has measured that distribution.

### The evidence cannot size a target machine

ADR-0043 states the requirement as one on the target machine and derives, from the campaign,
that without hulls a machine needs at least 1.16x the campaign host's per-core throughput. That
derivation assumes host speed is one scalar that multiplies every condition. **The second host
does not behave that way.**

Computed here from the two sources' tables, both sides, paired:

- the two hosts' **vendor** figures agree to within about **2 %**;
- the two hosts' **hull** figures differ by a factor of about **1.23**.

A single per-core-throughput scalar cannot produce both. Whatever separates the two hosts is
not a property that multiplies both geometries, so **a purchase sized on that ratio would be
sized against a model this evidence does not support.**

Three explanations are open and none is tested:

1. **The throttle.** The campaign's hull pair ran unthrottled; the later one ran with half 1 in
   the world. This is a real confound and it is one variable. It is also, on the arithmetic
   above, an unlikely *whole* explanation: throttle loss is small when a cell has headroom, and
   it would have to account for a fifth of the rate.
2. **The vendor condition is bound by something the hull condition is not.** 98,292 triangles
   against 9,810 is also a memory-footprint difference, and the campaign measured the hull cell
   using materially less resident memory. If the vendor pair is limited by memory bandwidth or
   last-level cache — which is exactly the contention below the core the campaign identified and
   said it could not separate — then both hosts hit the same wall in that condition and differ
   only where the working set fits. **If this is right, the target machine is specified by its
   memory subsystem and not by per-core throughput or core count**, which is a different
   purchase from the one ADR-0043 describes. It is a hypothesis with an arithmetic motive and no
   measurement.
3. **The two hosts are one machine.** ADR-0043's correction says "a different host, as the
   implementing agent reports it". **No document in this tree names the machine behind any of
   these figures.** If the campaign host and the later host are the same machine, the vendor
   agreement is trivial and the hull disagreement is a change over time — a different geometry
   pipeline, a different container allocation, the throttle — and the entire cross-host reading
   above dissolves.

Item 3 is settled by writing one line down, and it was not written down.

### What is known about where the cost is, and why the obvious answers are not available

The campaign's ablation attributes the step: the arms dominate it, collision geometry is about a
third of the whole, and the majority of the arms' cost survives hulls. Read it there. The
campaign itself says the surviving majority is articulated-body dynamics **plus** three
`gz_ros2_control` controller managers stepping inside the same process, and that it did not
separate the two — the profiler the installed Gazebo would need is not enabled in that build.

Two consequences for the answers that would otherwise be reached for first:

- **"Buy more cores" is not available.** The campaign measured the pairing penalty at 68 % core
  occupancy: a third of the machine was idle and did not help.
- **"This host is below the stated floor" is not available either.** The campaign's floor is at
  least 12 cores, and the host these measurements were taken on meets it.

## Options considered

### Option A — wait for the target machine, as ADR-0043 item 1 already says

The record's own answer, and the one the owner's standing instruction points at. Rejected **as
the whole answer**, on three counts, none of which is "the host should decide the design": the
campaign's own machine floor is met here, so the requirement does not name a machine anyone
could go and buy; the purchase ratio rests on the scalar model the cross-host arithmetic above
does not support; and the campaign is explicit that cores are not the lever. It survives as a
*later* option — see item 2 in *What we will have to revisit* — and is not rejected on its
merits, only on being unactionable today.

### Option B — replace the absolute floor with a bound on the divergence between the two sides' clocks

The shape closest to what a twin's divergence metric actually consumes, which is why it deserves
a serious answer rather than a dismissal.

Rejected on the same ground ADR-0043 rejected its own Option B, moved from mechanism to metric.
Slaving one clock to the other was refused because it makes the divergence metric structurally
blind to the fault it most needs to see; **a requirement written only on the difference between
the two clocks is blind to the same fault without needing the mechanism** — two sides drifting
together satisfy it perfectly. And it does not survive 2.B. There the far side is a physical arm
whose clock *is* the wall clock and carries no adjustment, so a bound on the difference is a
bound on the simulated side's absolute deficit whether it is written that way or not. A
requirement that has to be rewritten the day hardware arrives is the thing ADR-0041 and ADR-0047
each refused for bring-up, applied to time.

### Option C — keep the shape and lower the number: require some `r` below 1.0

Rejected because the clock-deficit argument gives no non-arbitrary place to put the number.
Below 1.0 the deficit accumulates without bound at every value, so any threshold is a statement
about how long a run may last before the deficit dominates transport — which is a different
requirement wearing this one's clothes, and it should be written as that if it is wanted. Choosing
the figure today would mean choosing it from four measurements, two of which are not campaigns,
on one or two machines nobody has identified.

### Option D — promote hulls and declare the gap closed

Not available, and it is worth stating why so that nobody reaches for it. On the host of the
later measurements hulls do not reach 1.0 at all. Independently of that,
[ADR-0028](0028-convex-hull-collision-meshes.md) forbids exactly this move: clause 2 of its
promotion gate is the friction-grasp campaign re-run under hull geometry, that campaign has not
been run, and the record says in terms that no status may move on a real-time-factor figure
alone. This record touches neither the gate nor the shipped default.

### Option E — buy the rate back by lowering the simulation's own rates

Lower the physics step rate, or the 150 Hz the controller managers step at. Genuinely
attractive, because if the controller managers are a large share of the surviving cost this is
free money. Rejected **now**, not in principle: nothing has attributed the surviving cost between
dynamics and the controller managers, so this is tuning against an unmeasured cause; and it
trades a fidelity quantity for a speed one at an exchange rate nobody has measured. It becomes a
candidate the moment item 3 of *What we will have to revisit* has an answer, and it needs its own
record when it does.

### Option F — split the requirement into capacity and operating deficit

Chosen.

## Decision

**ADR-0043's half 2 is restated, not relaxed. Half 1 is untouched and ADR-0043 is not
superseded.** The floor stays at 1.0 and moves to the quantity a machine can actually be
measured and bought against.

1. **Two requirements replace one.**
   - **Capacity floor.** Both sides of a pair, sampled concurrently, must exceed a real-time
     factor of 1.0 **with the world's throttle lifted**, under the workload the pair will run.
     This is the requirement on the machine. The 1.0 is not relaxed.
   - **Operating deficit.** With the throttle in force, each side's accumulated clock deficit —
     wall time elapsed minus simulated time elapsed over a stated window — is measured, and is
     bounded.
   The first is what half 2 was always trying to say; the second is the quantity the
   clock-deficit argument is actually about, and it is a sum in seconds rather than a ratio,
   because a sum is directly comparable to a latency and composes across a run.
2. **Neither threshold is set here.** The capacity margin above 1.0 is not zero — the campaign's
   own rule that an idle margin is not a work allowance says so, and the throttle loss
   established above adds to it — and this record does not know how large it is. The deficit
   bound is a statement about what a divergence measurement can tolerate, which is L5's
   question and unanswered. **Naming either figure now would be deciding what a campaign will
   find.**
3. **Phase 2.A is not blocked by an unmet requirement. What is gated is the reading of a
   number, not the work.** L5's mechanism continues to be built. **A divergence number published
   without the per-side clock deficit of the window it was taken in is not a P8 metric**, and a
   divergence sample taken while a side's deficit exceeded the bound is not valid — the same
   shape as the rule already in `DivergenceMetrics.msg`'s header, extended from "the mode makes
   divergence undefined" to "the clock does". **Where that value rides, and what it is called,
   is L5's and is not decided here.**
4. **Nothing is bought, tuned, promoted or widened on this evidence.** Explicitly: no machine is
   specified for purchase; no scenario wall-clock ceiling is changed, and none may be widened to
   absorb a real-time factor ([`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md));
   ADR-0028 is not promoted and the shipped collision geometry stays vendor; the generated world
   keeps `real_time_factor` `1.0`; `twin: {sides: single}` stays; and **half 2 in either shape
   remains outside bring-up**, exactly as [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md)
   clause 4 states — a side may still be up, slow, and indistinguishable from a healthy one.
5. **An instrument is owed, and three constraints on it are decided here.** Nothing in the tree
   measures either quantity, so neither requirement can be checked at all today. Whatever
   measures them must: reach each side's world statistics through `cite_bringup/gz.py` and no
   other door, carrying that side's `GZ_PARTITION` ([ADR-0042](0042-partition-gazebo-transport-per-side.md));
   compute `d(sim)/d(real)` over a stated window and **never** read Gazebo's own
   `real_time_factor` field, which the real-time-factor-conditions campaign measured
   over-reporting under starvation; and address a side **by name**, never by position
   (ADR-0047). Its package is not chosen here.
6. **Every real-time figure published from this record onwards names its machine and its
   throttle state.** Both are missing from the existing sets, and their absence is what makes
   the cross-host comparison above unresolvable rather than merely weak.

## Consequences

### What this gets us

- **A requirement that can be checked.** Under half 1 as written, no machine could ever pass
  half 2, and a passing measurement would have been a measurement error. That is now visible
  instead of latent.
- **Something a machine can be bought against.** Capacity is measurable, comparable between
  hosts and monotone in host speed. A throttled rate is none of the three.
- **P8 survives an unmet requirement.** Divergence numbers stay publishable in 2.A and stay
  unreadable as fidelity, which is what charter §8 already says of 2.A; what decision 3 adds is
  that they cannot be read without the term that dominates them.
- **The record stops carrying an explanation it cannot support.** "This host is not the target
  machine" is no longer offered as the reason, because the campaign's floor is met here.

### What this costs us

- **Two measurements where there was one**, and every real-time campaign now runs both throttle
  states, roughly doubling its run count.
- **An instrument that does not exist**, whose home this record deliberately does not choose —
  so the next change has to make that choice with this record's three constraints and no more
  guidance than that.
- **A requirement with a hole in it.** With neither threshold set, nothing can be shown to
  *pass* today; only to fail. That is honest and it is uncomfortable, and it means half 2 is
  unmet under the new shape as well as the old.
- **An interface conversation started and not finished.** Decision 3 gives `DivergenceMetrics`
  a second reason to be invalid, in a message whose own header says the rule is about modes.
  That message is a typed contract with a frozen baseline (P3), and this record does not change
  it.
- **The machine question is deferred, and 2.A pays for the deferral if the answer is bad.** If
  no achievable capacity brings the operating deficit under whatever bound L5 needs, then 2.A's
  divergence instrument cannot be validated on this architecture at all, and that is found out
  later than it might have been.

### What we will have to revisit

Four measurements, in the order their cost and their information content puts them. **None of
their answers is predicted here.**

1. **The 2x2, and it is the cheapest thing on this list.** Both collision geometries by both
   throttle states, one named machine, both sides of a pair sampled concurrently, thresholds
   registered before the first trial, published under
   [`docs/measurements/`](../measurements/README.md). It removes the throttle as a confound from
   every figure this record had to reason around, gives this host its first *capacity* number,
   and says whether the hull gain transfers. Until it exists, no host-to-host comparison in the
   record is clean.
2. **The same 2x2 on the campaign host — or the one line that says the two hosts are the same
   machine.** This is what decides whether ADR-0043's per-core-throughput model holds and
   whether hypothesis 2 in *Context* — a memory-bound vendor condition — is worth pursuing.
   **Nothing may be bought before it has an answer**, because the two candidate answers point at
   different hardware.
3. **Attribute the cost that survives hulls.** The campaign left the majority of the arms' cost
   split between articulated-body dynamics and three controller managers stepping at 150 Hz
   inside `gz sim`, and could not separate them with the profiler that build exposes. Ablation on
   the real cell can: a pair with the controller managers absent against one with them present;
   arms with joints fixed against articulated; one arm against three; and the physics step rate
   varied. If the controller managers turn out to dominate, **the lever is a rate and not a
   machine** — that is Option E, and it needs its own record and a fidelity argument, not a
   tuning commit.
4. **The deficit's distribution over a long run, not its mean.** The loop read above makes the
   deficit a sum of discrete overruns, so a mean real-time factor over a window is the wrong
   summary of it. This is the measurement that sets the bound in decision 1.

And two conditions under which the reading of the source above stops holding:

- **If a future Gazebo parallelises the physics step**, which the campaign already names as the
  condition that changes its core-count conclusion.
- **If the throttle loop's schedule handling changes again.** It already differs between
  `gz-sim8_8.0.0` and the current `gz-sim8` branch, in how much backlog it absorbs before
  discarding it. The installed patch version was not determined for this record, and the next
  change that depends on the loop's behaviour should determine it rather than inherit this
  caveat.
