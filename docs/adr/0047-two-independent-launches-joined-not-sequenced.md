# ADR-0047: Bring a pair up as two independent launches, joined by a supervisor that sees only processes

- **Status:** Accepted (corrected 2026-09-01) — **the decision and all four clauses stand; one
  citation inside them does not.** Clause 4's closing sentence, the *What we will have to
  revisit* item that repeats it, and the fourth bullet of *What promotion does NOT claim*
  below all name ADR-0043's half 2 — *both sides sustaining a real-time factor of 1.0* — as the
  requirement, and [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s status line now says
  not to cite that wording. **The observation those sentences make is unchanged**, and it was
  re-checked in code on 2026-09-01: nothing in the paired bring-up path measures either of the
  two quantities [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) restates half 2
  as, so a side may still be up, slow, and indistinguishable from a healthy one here. Nothing
  about a pair is re-graded, and no evidence is added or withdrawn. See the section
  "Correction — 2026-09-01: clause 4 cites a requirement whose wording has been retired, and
  the observation it makes survives it", below.

  **Promoted 2026-08-30 by the change that first brought two sides up
  under one supervisor** (`b3b7b66`), on the three conditions this record set for itself and on
  nothing else. They are not of equal strength, and the difference is the first thing a reader
  needs.

  | Condition, as this record worded it | What holds it |
  |---|---|
  | *a run in which both sides announce readiness and the supervisor reports the pair up* | **Three runs on one machine, reported by the implementing agent of `b3b7b66` in that commit's message. Not re-taken by review. No test and no CI step covers it.** |
  | *a test that a side which fails to announce ends the pair with a non-zero status naming that side* | `test_a_side_that_exits_before_announcing_ends_the_pair` — a side exits 7, the pair exits 1 reporting `plant exited 7` and `stopping counterpart` — with `test_a_side_that_never_announces_and_never_exits_fires_the_ceiling` for the last row of clause 4's table |
  | *a structural test that the supervisor's import graph does not reach `rclpy`* | `test_the_supervisors_import_graph_does_not_reach_a_ros_client_library`, kept honest by `test_the_walk_follows_a_first_party_import_out_of_this_package`, which asserts the walk still reaches `rclpy` through `cite_runtime` so that a narrowed walk fails there instead of turning the check green |

  **The first condition asks for a run and not for a test, and that was deliberate.** This
  record's own *Consequences* state that the existing scenario mechanism cannot host a pair —
  `launch_test` with `IncludeLaunchDescription` puts the launch in the test process, which holds
  one context on one domain — and its *What this record does not decide* leaves open whether a
  paired scenario exists at all. A condition demanding an automated paired run would have been
  unsatisfiable by construction. **It is honoured as written, and its weakness is named here
  rather than absorbed:** three runs on one machine, by the agent that wrote the code, is the
  size of that evidence.

  **What promotion does NOT claim.**
  - **Nothing automated brings a pair up.** A regression in the witness, the token, the gate it
    hangs on, or either side's bring-up would not fail CI. The residual closes when a paired
    harness exists — the shape this record declines to design — and until then the run has to be
    taken by hand.
  - **The shipped model is not paired.** `model/facility/zones.yaml` declares
    `twin: {sides: single}`, so `./scripts/sim --pair` refuses on a clean checkout rather than
    inventing a second side. Reproducing the run means editing L0 and regenerating, which moves
    `MODEL_HASH`. The pair is a mechanism the repository can run, not a configuration it ships.
  - **Nothing here is a fidelity claim, and 2.A produces none** — both sides run the same L0
    model and the same solver.
  - **Real-time factor is still not a bring-up condition**, exactly as clause 4 says. It has
    since been measured on a pair and the requirement is **not met**; the figures and their
    provenance are [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s 2026-08-30 correction
    and are deliberately not copied here.
  - **Two hazards are recorded in `cite_bringup/pair.py` rather than fixed**, both by the change
    that landed: a `Queue.put` from a signal handler can deadlock the supervisor against
    `_join`'s own `events.get`, with the ceiling unable to fire because the stuck call is what
    enforces it (never observed; the repair is a self-pipe and a reader thread); and
    `READY_CEILING_S` is stated rather than derived, so if a side's own gate ceilings ever sum
    past it, the pair reports the ceiling for a side that was about to fail with a better
    diagnosis.

  **The ceiling has fired once on a real cause, which is worth recording.** The first paired
  attempt did not join: `install(PROGRAMS)` does not set the executable bit under a symlink
  install, launch reports a failure to exec on its own logger without emitting `ProcessExited`,
  so no gate fired and nothing downstream noticed. The only mechanism that reported it was clause
  4's last row — *this side never announced readiness and never exited*. That row was written for
  a hypothetical and met a real one on its first outing.

  **When written this record was `Proposed` and nothing was implemented**, and that block is kept
  rather than replaced. At `5c2990f`:
  - `model/facility/zones.yaml:23` declares `twin.sides: single`, so the committed model
    describes one side.
  - **`twin.sides: pair` emits only the counterpart's partition and each asset's backend**,
    and that was re-established against this commit rather than taken from
    [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md): the model was copied
    to a scratch directory with `sides:` changed to `pair`, both models were generated through
    `cite_tools.generate.generate` into separate directories, and the two trees were diffed.
    **34 artifacts in each, and the whole difference is three kinds of line** — a second
    `sides:` entry (`name: counterpart`, `gz_partition: cite/cell_a/counterpart`), one
    `counterpart_backend: sim` per controller manager, and a changed `MODEL_HASH`. No second
    world, no second launch, no second controller manager, no second set of names.
  - **Bring-up has exactly one production reader of a side**, `cite_bringup/gz.py:109`
    (`plant: Side = plan.sides[0]`), and it takes the first. Nothing in the launch graph or
    the plan loader reads a second side.
  - `scripts/sim:49` `exec`s **one** `ros2 launch`. There is no pair entry point, no
    supervisor module, and no readiness announcement anywhere in `cite_bringup`.
  - **[ADR-0044](0044-one-ros-domain-per-side-identical-names.md) clause 4 is also
    unimplemented**, and this record is blocked behind it: the generated plan carries no
    domain offset (`grep -i domain workspace/src/cite_generated/bringup/cell_a_plan.yaml`
    returns two comment lines and no value), and `CITE_DOMAIN_BASE` appears nowhere in
    `scripts`, `workspace` or `tools`. A supervisor cannot resolve a side's domain until that
    lands, so the implementation order is fixed: ADR-0044 clause 4, then this.

  Every "will" and "must" below was a commitment rather than a description **when this record
  was written; the four clauses are now built, and the table at the top of this block is what
  holds each of them.**
  **Promoted to `Accepted` by the change that first brings two sides up under one supervisor**,
  with all three of: a run in which both sides announce readiness and the supervisor reports
  the pair up; a test that a side which fails to announce ends the pair with a non-zero status
  naming that side; and a structural test that the supervisor's import graph does not reach
  `rclpy`. **One side is not evidence for any of them** — this record's whole content is a
  claim about two processes.
- **Date:** 2026-08-30
- **Deciders:** Docs-writer agent, on the deferral
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) states under *What this record
  does not decide* — "what sequences the two launch processes, and how a failure on one side
  stops the other".
- **Related:** [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) (clause 3 and its
  supervisor carve-out; clause 4, which this depends on),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) (which restates ADR-0043's
  half 2, and whose decision 4 cites clause 4 below — added by the 2026-09-01 correction),
  [ADR-0038](0038-stop-the-line-without-ending-the-process.md),
  [`cross-cutting-lifecycle.md`](../architecture/cross-cutting-lifecycle.md),
  [`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  (added by the 2026-09-01 correction),
  [`../../CLAUDE.md`](../../CLAUDE.md) §7, charter §4 (P4, P6, P7)

## Correction — 2026-09-01: clause 4 cites a requirement whose wording has been retired, and the observation it makes survives it

**This is the first correction on this record. No status moves, no clause changes, and nothing
here is evidence about a pair.** What is wrong is a **citation**, not a finding: clause 4's
closing sentence, the *What we will have to revisit* item that repeats it, and the fourth
bullet of *What promotion does NOT claim* in the status block all point a reader at ADR-0043
half 2's wording — *both sides sustaining a real-time factor of 1.0* — which
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s status line now says not to cite as the
requirement.

### 1. What clause 4 meant, and that part stands entire

The sentence is an observation about **this record's own scope**. It says that no bring-up
condition on either side checks how fast that side is running, so a side that is up and slow
announces readiness exactly as a healthy one does, and the supervisor grades the pair without
ever having asked. **That is still what the code does** — re-read for this correction and
tabulated in section 3. The intent survives intact; only the name of the quantity the clause
declines to check has moved underneath it.

### 2. The quantity was restated, not relaxed

[ADR-0049](0049-measure-the-real-time-floor-as-capacity.md) keeps the 1.0 floor and puts it on
two quantities: **capacity**, both sides sampled concurrently with the generated world's
throttle lifted, and the accumulated **clock deficit** in seconds, sampled with that throttle
in force. The reason half 2's wording had to go is structural rather than editorial — ADR-0043
half 1 puts `real_time_factor` `1.0` into the generated world, SDFormat's factor is a ceiling,
and a rate measured under a ceiling is capped at it by construction, so half 2 as worded is a
test no machine passes and an adequate machine answers it much as an over-provisioned one
does. That mechanism is read in upstream source in ADR-0049 and is not restated here (P1).

The campaign that measured both quantities is
[`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
— both geometries by both throttle states, both sides of every pair sampled in one window,
thresholds registered before the first trial, on a **named** machine. **Its figures are cited
and not copied**; read its §3 - §6 for them, and note its own rule that every capacity figure
it reports is a lower bound. Two things about it change how the sentences below should be read:
**ADR-0049 sets neither of its two thresholds**, so the requirement is unmet under the new
shape as well as the old, and **ADR-0049 is itself `Proposed`** — the project owner ratified
its decision on 2026-08-31, and ratification is not promotion.

### 3. Is the observation still true under the new wording? Yes, and it was checked in code

Read on 2026-09-01, first in the paired bring-up path and then in the tree at large.

| Where such a check would have to live | What is there |
|---|---|
| `cite_bringup/readiness_witness.py` | Waits for every skill and detection action server the plan names to answer, under a wall-clock deadline whose expiry is a failure, and for nothing else. Its docstring already bars a performance figure from readiness and already names ADR-0049's two quantities. |
| `cite_bringup/pair.py` | `_verdict` prints `ready=` and `status=` per side and grades the pair on those two facts alone. `READY_CEILING_S` is a ceiling on a failure whose comment says it may never be widened to absorb a slow host, and names ADR-0049 as the record that finding belongs to. |
| `cite_bringup/plan.py` | No field for either quantity. The generated plan states each side's partition and domain offset, not its speed. |
| The tree at large | `grep -rn real_time_factor workspace/src tools tests scripts` reaches the world generator, its template, two world files and two test files. **No measurement of either quantity during a run, anywhere.** |

**So the clause's warning still stands under the new wording**: a side can be up, slow, and
indistinguishable from a healthy one at the point this supervisor reports.

**What has changed is that this is now a decision rather than an omission.** ADR-0049
decision 4 keeps half 2 **in either shape** outside bring-up, and cites this record's clause 4
for it. Making readiness depend on a performance figure would turn a slow host into a bring-up
failure, which is the opposite of what a ceiling on a failure means.

**One thing moved since, and it is not in bring-up.** L5 exists: `cite_twin`'s divergence
monitor names each side's accumulated clock deficit as a term of a sample's validity, with the
bound deliberately unset and **no instrument to fill the term** — `clock_deficit_s` is `None`
on every operand, and the package's own paired launch test asserts the sample is invalid for
exactly that reason. **The quantity now has a consumer and still has no producer.** Nothing in
bring-up reads it, and nothing there changes what this supervisor may observe.

### 4. How the error survived

The sentence was true when it was written, and nobody re-read it when the record it cites
retired the wording. **A citation ages exactly like a count, and nothing in this repository
treats it that way.** The one instrument that exists,
`tools/tests/test_superseded_real_time_requirement.py`, was built to keep half 2's wording out
of *source* and exempts Markdown on purpose — a record has to be able to quote what it corrects
— so no check was ever going to point at this paragraph, and none should. What found it was
someone reading the decision text against ADR-0043's status line. The transferable part: when a
record you cite gains a correction, every sentence that cites it is inside that correction's
blast radius, and only a reader can walk it.

## Decision

**A twin pair is two independent launches. Neither waits for the other, because neither needs
anything from the other. They are *joined*, not *sequenced*.**

The word ADR-0044 deferred was "sequences", and the answer to it is that **nothing sequences
them, because there is no order to impose.** What is needed is much weaker: something that
knows when both are up, and that ends the pair when one is not.

Four clauses.

### 1. No process on either side waits on the other side's state

Each side's launch is exactly today's `simulation.launch.py`, given that side's environment,
gating on that side's own events as it does now. It does not know a counterpart exists.

This is not a concession to the domain boundary — it is the property that makes the boundary
affordable. A design in which the plant's bring-up waits for the counterpart's would have to
be **unbuilt** in 2.B, where the counterpart is the physical cell and no launch can sequence a
machine that is powered on by hand. It is the same 2.B test that killed ADR-0044's Options A
and D, applied to bring-up order.

### 2. The join is owned by a pair supervisor, and ADR-0044's carve-out is committed to

ADR-0044 clause 3 sketched a carve-out for "a supervisor of the two launch processes" and did
not commit to it. **It is committed to here, with a boundary that classifies a design rather
than describing an intention.**

The pair supervisor is a plain process — not a ROS node, not a launch file, not L5. It lives
in `cite_bringup`, beside the plan loader and `gz.py`, because that package already owns the
plan, the per-side environment and the refusals, and because a second construction of a side's
environment is a value in two places (P1).

**It may:** start and stop operating-system processes; read their exit status; read the
standard output of processes it started; read the generated plan and resolve each side's
domain and partition through ADR-0044 clause 4's single resolver; own files it created.

**It may not:** import `rclpy` or `rclcpp`, or create any context, node, publisher,
subscription, client, service or action endpoint on either domain; set `ROS_DOMAIN_ID` or
`GZ_PARTITION` **in its own** environment in order to reach a side (it sets them in a child's);
decide anything about what crosses between the sides — that is L5's definition and this
supervisor is not L5.

**The membership test, for a design nobody anticipated:** if both sides' DDS and both Gazebo
transports were removed from the machine, the supervisor's own code would still run unchanged,
because it never speaks either. **The check that enforces it** is structural and of the same
shape as ADR-0042's source-scan guard: a test asserting that the supervisor module's import
graph does not reach `rclpy`. A promise that a component holds no context is not reviewable; an
import test is.

### 3. "A side is up" is announced by that side, computed inside that side, and read as process output

The supervisor never asks a graph a question. **The side answers, on its own standard output,
and the supervisor reads its own child's pipe.**

- The side's launch ends its existing gate chain with a **readiness witness**: a process
  started in the side's own environment — therefore on the side's own domain — that blocks on
  a condition and exits, exactly as `ros_gz_sim create` and the controller-manager spawner
  already do. Its exit is consumed by the existing `_gate` helper
  (`simulation.launch.py:1077`), whose last link today is labelled `"the skill servers"`
  (`simulation.launch.py:227`). A witness that cannot satisfy its condition fails the launch
  with a diagnosis, like every other link.
- On that gate, and **nowhere else in the file**, the launch emits one fixed token line. The
  token is defined once, in `cite_bringup`, and imported by both the emitter and the reader;
  two string literals would be the same defect in miniature.
- The supervisor's readiness fact is that token arriving on that side's pipe. It is strictly
  stronger than liveness — a process that has not crashed has not reached the end of a gate
  chain — and it is not a timer: a blocking read on a pipe has no interval.

**Standard output rather than a ready file, and the reason is in this repository's own rig.**
The second-world-cost campaign joined its two cells with ready files, and its `phase_pair`
had to `rm -f` them before every run
([`harness/run_campaign.sh`](../measurements/2026-08-28-second-world-cost/harness/run_campaign.sh)).
**A stale ready file is a false join** — it reports a side up that was never started. A pipe
has no state to go stale, cannot be written by anything but the child, and needs no polling
interval.

### 4. A side that ends, ends the pair — and a pair that never joins fails on a ceiling

`_fatal_on_exit` (`simulation.launch.py:1098`) already states this rule one level down: a
process dying mid-run tears the launch down rather than leaving a cell that answers some
interfaces and not others. **A half-pair is exactly that, one level up**, and a scenario
asserting against a pair could pass on the plant alone.

| What happens | What the supervisor does |
|---|---|
| A side's launch exits before announcing readiness | Stop the other side. Exit non-zero, naming **which** side and its status. |
| Both exit before announcing | The same, reporting **both** statuses — not only the first. |
| A side exits after both announced | The same. The pair ends. |
| Neither announces and neither exits | The ceiling fires: stop both, exit non-zero, and say *"this side never announced readiness and never exited"* rather than "timeout". |

**The ceiling is a ceiling on a failure, never a schedule** — the distinction
`simulation.launch.py`'s own docstring draws, and the only shape of waiting P4 permits. Nothing
proceeds when it expires. It exists because the last row is real: ADR-0044 records the silent,
indefinite hang that awaits a mis-wired cross-domain lifecycle client, and without a ceiling the
supervisor would inherit that silence instead of converting it into a diagnosis. **The ceiling
must never be widened to absorb a slow host** — see
[`cross-cutting-testing.md`](../architecture/cross-cutting-testing.md).

**Per-side refusals fail on one side only, by design.** ADR-0042's partition refusal and the
hardware opt-in both fire before a side runs anything, so they arrive as row 1 and the report
must name the side. ADR-0043's half 2 — both sides sustaining real-time factor 1.0 — is **not**
a bring-up condition and nothing measures it, so a side can be up, slow, and indistinguishable
from a healthy one here. **[Corrected 2026-09-01 — see the Correction section above. The
quantity is now ADR-0049's capacity and clock deficit; the observation stands, re-checked in
code.]**

## Context

### What ADR-0044 fixed, and the one word it left open

ADR-0044 established from upstream source that a `ros2 launch` process holds one
`rclpy.Context`, that the lifecycle event manager's `transition_event` subscription and
`ChangeState` client both live on the node in it, and therefore that **one launch cannot
lifecycle-sequence a node on another domain** — while it *can* start one, whereupon bring-up
hangs at the first managed transition, forever, with no log line. That mechanism is read there
and is deliberately not restated (P1).

What it concluded was that a paired bring-up is two launch processes "sequenced by something
above both", and what it deferred was what that something is. **This record's first job was to
check the premise in that phrase, and the premise does not hold.**

### The two sides have no ordering relation, and this was the question worth attacking

Enumerated against the tree at `5c2990f`, candidate by candidate:

- **The bring-up plan.** The only two things a `pair` adds are the counterpart's own
  `gz_partition` and a `counterpart_backend` per controller manager (re-established by the
  regeneration in the status block). Both are statements about *that* side's own environment
  and its own plugin. **Neither is a fact any gate on the other side reads** — and bring-up has
  one production reader of a side at all, `gz.py:109`.
- **The launch graph.** Every gate in `simulation.launch.py` is an event produced by a process
  that launch itself started: a spawner exiting, a lifecycle transition, a scene loader
  finishing. None of them names a side.
- **`/clock`.** One per side, per domain. ADR-0043 **rejected** slaving the counterpart's clock
  to the plant's (its Option B) and holds both to the wall clock instead, so the design already
  forbids the one clock dependency that could have existed.
- **The L4 coordinator.** It derives its stations from that side's topology and commands that
  side's arms. It is per side, inside a side.
- **The mirroring path and the divergence monitor.** These are L5, which does not exist
  (`cite_twin` is not in the tree; [L5](../architecture/L5-twin-synchronization.md) is
  `DESIGNED`). L5 is not a member of either side — it is a consumer **downstream of both**, so
  it creates an ordering between *the pair* and *L5*, not between the two sides.
- **A scenario harness.** It needs to know when both are ready. That is a readiness question,
  not an ordering one.

**This is an enumeration at a commit, not a proof.** It says that a search of the plan, the
launch graph and the layer documents on 2026-08-30 found no fact about one side that any gate
on the other side reads. If someone finds one, this record's clause 1 is what fails.

### Two sides have already been brought up this way, and nothing sequenced them

The second-world-cost campaign ran two complete cells concurrently, each through
`./scripts/sim`, each on its own domain
([`harness/run_campaign.sh`](../measurements/2026-08-28-second-world-cost/harness/run_campaign.sh),
`phase_pair`). Both were started **at once**, in the background, with no ordering between them
and no side waiting on the other.

Two details of that rig are the reason this record can be short:

- **Each side decided its own readiness inside its own domain.**
  [`harness/cell_run.py`](../measurements/2026-08-28-second-world-cost/harness/cell_run.py)
  polls every arm's controller manager for active controllers, under a ceiling that **fails**,
  and its own comment states why it is not a sleep: a fixed wait would sample a different part
  of bring-up on a loaded host than on an idle one. That process ran in the side's environment,
  so it observed one domain — its own.
- **What crossed between the sides was a file, and it gated the *measurement*, not the
  bring-up.** The supervising shell function waited for both ready files and then wrote a start
  gate so that both sampled the same window. No side's bring-up ever waited on the other's.

Read the campaign for its figures; nothing here restates them. What it supplies is the shape:
independent bring-ups, per-side readiness computed on the side, and a join above.

### Where this leaves P4

P4 is charter §4's requirement that startup is driven by lifecycle states and events, never by
sleeping for a guessed duration, and ADR-0044 was explicit that its deferral must not be
answered with a sleep. **The answer here contains no wait between the sides at all** — the two
bring-ups overlap in time and neither blocks on the other — and the one place the supervisor
does wait, it waits on a pipe until data arrives, under a deadline whose expiry is a failure.
The provocation ADR-0044 named, a `TimerAction` bridging a silent cross-domain hang, has
nothing to attach to: there is no cross-domain transition to sequence.

## Options considered

### Option A — no owner at all: two shells, pure independence

The sharpest attack on this record, and it is half right. If the sides need no sequencing, why
does anything sit above them? Start two launches, in two terminals or two CI steps, and let the
pair be ready when both are.

**Accepted in substance, rejected as a design.** What it lacks is an answer to *who asks*.
Nothing computes "the pair is up", so every consumer — a scenario, a later L5 launcher, an
operator — invents its own answer, and they will not agree; and nothing stops a half-pair, so a
paired scenario could assert against the plant alone and pass. It is also not a CI step: a pair
whose readiness is "a developer looked at two terminals" cannot be run headlessly. This is
ADR-0042's precedent applied to readiness rather than to isolation — *isolation nobody can name
is isolation nobody can review* — and the answer is the same: give it a name and one place.

The concession is real and shapes the decision: what survives is a **join and a lifetime owner**,
not a sequencer, which is a much smaller thing than ADR-0044 anticipated.

### Option B — L5 sequences the sides

Superficially attractive: ADR-0044 clause 3 makes L5 the one component with endpoints in both
domains, so it is the only thing in the running system entitled to know both sides' states.

**Rejected on two independent counts.** It inverts a dependency — L5 spans two graphs, so it
cannot be the thing that creates them; it would have to exist before its own subjects, and
today it does not exist at all. And it dies on 2.B: L5 cannot start a physical cell. Process
supervision is also not what L5 is for; clause 3 defines L5 by *deciding what crosses*, and
starting an operating-system process decides nothing about ROS traffic.

### Option C — a third `ros2 launch` that starts the other two

The closest rejected option, and the one that deserves care, because a parent launch would
reuse machinery this project already trusts: `ExecuteProcess` with `additional_env=`,
`OnProcessExit` for the failure rule, `OnProcessIO` to match a readiness token, and launch's own
shutdown propagation.

**It also does not necessarily acquire a ROS context, and saying so is the honest version of
this rejection.**
> **Verified 2026-08-30** against the installed package in the Jazzy image —
> `docker run --rm ros:jazzy-ros-base-noble` reading
> `/opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/ros_adapters.py`. `get_ros_adapter`
> creates the `ROSAdapter` **lazily**, only if it is called, and the four callers in the
> installed tree are `utilities/lifecycle_event_manager.py`, `actions/ros_timer.py`,
> `actions/load_composable_nodes.py` and `actions/set_use_sim_time.py`. A launch description
> using only `ExecuteProcess` therefore creates no context and no node.

So the option is not rejected on a false premise. **It is rejected because that property is one
line from being lost, invisibly.** The first `LifecycleNode`, `SetUseSimTime`, `RosTimer` or
composable-node load added to the parent creates a context on whatever domain the parent
inherited — one side's — and nothing in a diff says so. Worse, a parent launch makes the
mistake ADR-0044 warns about *natural*: sequencing a counterpart's managed node from the parent
is a plausible-looking edit that hangs forever in silence. **A supervisor that cannot import
`rclpy` cannot express that mistake**, and clause 2's import test is what makes "cannot" a fact
rather than a habit. If someone later demonstrates a parent launch held to the same import
constraint by the same kind of test, this option is reasonable and this record should be
revisited rather than worked around.

### Option D — one side's launch starts the other

One line: add `ROS_DOMAIN_ID` to an existing `additional_env=`, which is already the idiom at
four call sites in `simulation.launch.py`.

**Rejected, and it is the trap rather than an option.** ADR-0044 verified that the
counterpart's processes do come up this way and that bring-up then hangs at the first managed
transition with no log line at any level, because the `ChangeState` client is on the wrong
domain. It also violates clause 1 on its own terms — it makes one side's bring-up structurally
dependent on the other's — and it cannot survive 2.B, where the far side is not a process
anybody starts.

### Option E — two independent launches, joined by a process-level supervisor

Chosen.

## Consequences

### What this gets us

- **The deferral closes without a mechanism.** The thing ADR-0044 expected to design does not
  exist, because the ordering it was to enforce does not exist. What is left is a join and a
  failure rule.
- **The 2.A shape survives 2.B.** A supervisor that starts launches and reads exit status does
  not care that one side's `ros2_control` loaded a real hardware plugin. Nothing about the join
  assumes the far side is simulated.
- **"Who can see both sides" keeps one answer.** ADR-0044 clause 3's rule is intact: the
  supervisor observes processes, not graphs, and the import test makes that checkable rather
  than declared.
- **A pair failure is a diagnosis instead of a hang**, including the specific silent hang
  ADR-0044 names.

### What this costs us

- **A new door, in a project that has been bitten by exactly this.** ADR-0042's correction is
  the precedent: a guarantee that covered the launch graph and not the second class of process
  that also started Gazebo. Whoever adds another way to start a side owes the same question —
  *what else starts one of these?* — asked of the tree rather than of a test.
- **The existing scenario mechanism cannot host a pair.** `tests/scenarios/bringup.py` runs the
  cell through `launch_test` with `IncludeLaunchDescription`, which puts the launch in the test
  process; by ADR-0044's constraint that process has one context on one domain, so two sides
  cannot be included there. A paired scenario is structurally a different shape — it drives the
  supervisor as a subprocess and observes both sides as a harness, under ADR-0044 clause 3's
  first carve-out and through one stated door.
- **The console changes.** The supervisor owns both sides' output, so it must forward and label
  it; a developer loses the plain single-launch console they have today and gets two interleaved
  streams. That is a real ergonomic cost, and the operator documentation owes an entry.
- **Readiness is only as strong as the witness, and today's chain does not have one.** The last
  gate label at `simulation.launch.py:227` is `"the skill servers"`, and it fires when they are
  *started*, not when they are serving. A witness is new work on the side path, and it is worth
  saying that it improves the solo bring-up too: today nothing announces that a single cell
  finished coming up either.
- **Two of everything at teardown.** A pair runs two Gazebo servers, two bridges, two of every
  node, so a run's exposure to the teardown signal family is not a solo run's. The campaign for
  that family is
  [`docs/measurements/2026-08-27-teardown-signal-family/`](../measurements/2026-08-27-teardown-signal-family/results.md);
  its primary result is INCONCLUSIVE and nothing here should be read as predicting a paired rate.
- **One more entry point.** If the supervisor is reached by a new command, `CLAUDE.md` §7's
  table is part of the implementing change.
- **Ordering with ADR-0044.** Clause 4's plan-stated offset, `CITE_DOMAIN_BASE` and the single
  resolver must land first. This record cannot be implemented before them.

### What we will have to revisit

- **When L5 exists.** Whether the supervisor starts it after the join, and whether an L5 fault
  ends the pair. ADR-0038 pulls the other way — it records that ending a process to report a
  fault takes the evidence of the fault with it — and clause 4's rule was written for bring-up,
  not for a running twin. Decide it then, with that tension named.
- **When 2.B lands.** A physical side is not started by anybody and cannot be torn down by the
  supervisor. The readiness announcement still works — it comes from the hardware-side launch —
  but clause 4's "stop the other side" means something different when the other side is a
  powered machine.
- **If the witness proves too weak.** The condition that would reopen this is a pair that
  announced readiness and then could not accept a goal.
- **When something measures real-time factor during a run.** ADR-0043's half 2 is a per-side
  condition that this record explicitly does not police. Whether one side falling below 1.0 is a
  pair-level failure is a decision nobody can take until it is measurable.
  **[Corrected 2026-09-01 — see the Correction section above. Half 2's wording is retired and
  ADR-0049 carries the requirement as capacity plus a clock-deficit bound; the quantities have
  since been measured by a campaign, and what is still absent is an instrument that measures
  either one *during a run*, which is what this item is waiting for.]**
- **If a zone ever runs more than two sides.** The join generalises to N; ADR-0044 clause 4's
  domain allocation does not, and it is the binding constraint.

## What this record does not decide

- **L5's design** — the mirroring mechanism and the divergence metric remain ADR-0041's and
  ADR-0044's open questions, untouched here.
- **The spelling of the entry point** — a flag on `./scripts/sim` or a command of its own.
- **Whether a paired scenario exists yet**, and what it would assert.
- **How L6 records a pair** — ADR-0044 clause 3's third carve-out, still unresolved.
