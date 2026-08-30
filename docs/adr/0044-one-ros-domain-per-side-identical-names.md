# ADR-0044: Give each side of a twin pair its own ROS domain, and keep both sides' names byte-identical

- **Status:** Proposed (corrected 2026-08-30) — **clause 4 is built, a pair has come up on two
  domains, and this record went on saying nothing in it was implemented.** See the section
  "Correction — 2026-08-30: clause 4 is built and a pair has come up; the promotion condition
  is still not met", below.
  **The record stays `Proposed`, and for one named reason rather than for want of a pair.**
  The promotion condition in this block requires, in addition to the launch-graph test, *"the
  ROS analogue of `tests/scenarios/guards/test_gz_calls_carry_the_partition.py`"* — a source
  scan over `tests/` that fails when a harness enters a ROS graph other than through one stated
  door. **That guard does not exist**, and the three bare `rclpy.init()` call sites this block
  names below are still bare. The condition was written that way on purpose, so it is honoured
  as written.
  **When written this record was `Proposed` and nothing was implemented**, and that sentence is
  kept rather than replaced. At `29068d4`:
  `ROS_DOMAIN_ID` is one value for the whole checkout, derived from the checkout path by
  `cite_domain_id` in [`scripts/_lib.sh`](../../scripts/_lib.sh) and handed to the container
  by [`infra/docker/docker-compose.yml`](../../infra/docker/docker-compose.yml).
  `git grep -n ROS_DOMAIN_ID -- scripts infra workspace/src tools` returns **34 hits in 13
  files** at `c4c16e0`, and **not one of them gives a second side a second
  domain**: they are that derivation, its `doctor` check, its self-test, the value the
  scenario runner prints, and comments recording that the variable does **not** isolate Gazebo
  transport.
  **`git grep` rather than `grep -r`, because the two do not agree and only one of them is a
  fact about the commit.** A plain `grep -rn ROS_DOMAIN_ID scripts/ infra/ workspace/src/ tools/`
  returns 34 in 13 on a clean checkout and **39 hits in 18 files** on a checkout that has been
  built and bootstrapped, because it also reads `__pycache__` and the `workspace/src/external/`
  packages `./scripts/bootstrap` imports from `external/cite.repos` — neither of which is
  tracked. Both numbers are right and they count different things; the tracked-file count is
  the one that reproduces from a checkout of this SHA on any machine, which is the only kind of
  number this repository lets a document state.
  The one place that sets a distinct domain is
  `cite_runtime/test/test_shutdown_under_signal.py`, which puts a test's own child process on
  a domain of its own — test isolation, not a side.
  The generated plan's `sides:` list carries a `gz_partition` per side and
  **no domain** (`workspace/src/cite_generated/bringup/cell_a_plan.yaml`); `model/facility/zones.yaml`
  declares `twin.sides: single`, so the list has one entry; `cite_bringup.gz.gz_environment`
  takes `plan.sides[0]` and says in its own docstring that "bringing a counterpart up is a
  separate launch and is not built yet" **[Corrected 2026-08-30 — see the Correction section
  above.]**; and `cite_twin` does not exist.
  Every "will" and "must" below is a commitment, not a description.
  **Promoted to `Accepted` by the change that first brings two sides up on two domains under
  bring-up's own control, with a test that a side's processes carry the domain the plan
  resolves for them** (P7). Nothing weaker promotes it: this record's whole content is a claim
  about two graphs, and one graph cannot evidence it.
  **The promotion condition covers both classes of ROS process this repository starts, and
  saying so here rather than only in clause 2 is deliberate.** ADR-0042's correction is
  precisely a promotion taken on a condition that read as though it covered everything and
  reached the launch graph only; a future agent satisfies the sentence it finds in a status
  line, so the scope belongs in the sentence. The second class is not hypothetical and is not
  hidden: **`tests/scenarios/bringup.py:120`, `tests/scenarios/pick_and_place.py:218` and
  `tests/scenarios/continuous_line.py:495` each call a bare `rclpy.init()`**, which takes
  whatever `ROS_DOMAIN_ID` the invoking shell happens to carry — today the plant's, correctly
  and by accident, and under a pair whichever side the developer's shell was last in. So this
  record is **not** promoted by a launch-graph test alone. It requires, in addition:
  - a run-time check on the launch path, of the same shape as the partition's — the environment
    a side's processes are actually handed, read back from the processes themselves;
  - the **ROS analogue of `tests/scenarios/guards/test_gz_calls_carry_the_partition.py`**: a
    source scan over `tests/` that fails when a harness enters a ROS graph other than through
    the one stated door, counting the call sites it found so that a rewrite moves a number
    instead of producing silence.
  A test that enumerates its subjects answers only for the subjects it enumerates. The question
  "what else joins a ROS graph?" has to be asked of the tree, and the second bullet is what asks
  it.
- **Date:** 2026-08-29
- **Deciders:** Project owner — that the two sides carry identical names and are separated by
  domain, argued from P2. The argument was checked rather than accepted (see *Context*), the
  rejected alternatives and everything under *What this record does not decide* are the
  docs-writer agent's, and the evidence is
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md).
  **Revised 2026-08-29 after architecture review, still `Proposed` and still unimplemented.**
  The review found the decision sound and found that five clauses deferred choices that would
  have been improvised at implementation time. Those choices are now made in the record: the
  odd-base domain allocation and the three places its bound lives (clause 4), the explicit
  `CITE_DOMAIN_BASE` channel and the single resolver that make the plant's refusal something
  other than `env == env + 0` (clause 4), the classification of a launch-process supervisor
  (clause 3), L7 (clause 3), and a promotion condition that names the harness class rather than
  repeating ADR-0042's scope error (status line). The review also supplied Option D and the
  first of the two ADR-0021 arguments in clause 4, both of which strengthen the decision rather
  than qualify it, and the re-reading of the Q5 table in *Context*. **No claim in this record was
  weakened to close a finding.**
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) (Decision 3,
  and the second-side emission bullet this record unblocks),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md) (which answers this
  record's deferral and implements clause 4 alongside it),
  [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md),
  [`qos-profiles.md`](../interfaces/qos-profiles.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §8 and §10, charter §4 (P1, P2, P5, P7) and §8

## Correction — 2026-08-30: clause 4 is built and a pair has come up; the promotion condition is still not met

**What was wrong.** Two things, and they fail in opposite directions.

1. *"Nothing in this record is implemented."* False since `d046320` and `b83163f`. Clause 4's
   refusal exists, both sides of a pair have started on their own domains, and a reader taking
   the status line at face value would have concluded that `require_domain`,
   `CITE_DOMAIN_BASE` and `resolve_domain_id` were still open work.
2. *"`cite_bringup.gz.gz_environment` takes `plan.sides[0]` and says in its own docstring that
   'bringing a counterpart up is a separate launch and is not built yet'."* **That sentence is
   no longer in `gz.py`** — `grep -n "not built yet" workspace/src/cite_bringup/cite_bringup/gz.py`
   returns nothing — and the function is addressed by side name rather than by index. This
   record quotes it **twice**, in this block and in *Context*, and both quotations are now
   citations of text that does not exist. A quotation is a claim about another file and goes
   stale exactly as a count does.

**What is true, established against the tree rather than taken from a report.**

| Claim in the status block | State at this commit | Established by |
|---|---|---|
| "the generated plan carries no domain offset" | **false** — every side carries one | `grep -n -A4 'sides:' workspace/src/cite_generated/bringup/cell_a_plan.yaml` |
| "`CITE_DOMAIN_BASE` appears nowhere" | **false** — it is the base's own channel | `grep -rn CITE_DOMAIN_BASE scripts workspace/src/cite_bringup` |
| "nothing refuses a side that is not on its own domain" | **false** — `require_domain` does, at the launch boundary | `grep -n 'def require_domain' workspace/src/cite_bringup/cite_bringup/plan.py` |
| "`gz.py` says a counterpart bring-up is not built yet" | **false** — the sentence is gone and the launch exists | `grep -n 'not built yet' workspace/src/cite_bringup/cite_bringup/gz.py` |
| "`cite_twin` does not exist" | **still true** | `ls workspace/src` |

**What holds clause 4 now.** `require_domain(plan, side, environ)` refuses a side whose process
environment does not carry the domain the plan resolves for it, in the same place and manner as
`require_gz_partition`; `resolve_domain_id` is the single addition of base and offset and is
where the `1..101` band is enforced; and the base arrives on `CITE_DOMAIN_BASE` rather than
being read back out of `ROS_DOMAIN_ID`, which is what stops the plant's half reducing to
`env == env + 0`. That last point is held by a test of its own —
`test_an_unset_base_is_refused_rather_than_read_from_the_ambient_domain` in
`cite_bringup/test/test_plan.py` — and the refusal is held at the launch boundary by
`test_a_side_on_a_domain_that_is_not_its_own_refuses_to_start`,
`test_a_side_started_without_a_base_refuses_to_start` and
`test_the_counterpart_started_on_the_plants_domain_refuses` in `test_simulation_launch.py`.
**The first of the two additional promotion bullets is therefore met**: the check is a run-time
refusal on the launch path, of the same shape as the partition's.

**What has been observed once, and at what strength.** The implementing agent of `b3b7b66`
reports a pair up three times on one machine, with `/clock` carrying **one** publisher on each
domain where a merged graph would show two, and **41 nodes per domain with every name this
project forms present once on each** — which is clause 1 and clause 4 demonstrated together.
**Review did not re-take it, no test covers it and no CI step runs it**, and the committed model
declares `twin: {sides: single}`, so the run is not reproducible from a clean checkout without an
L0 edit that moves `MODEL_HASH`. Three runs on one machine is the size of that evidence.

**Why this record still stays `Proposed`, in its own words.** The promotion condition in the
status block does not stop at a launch-graph test. It names a second class of process — a
harness that calls `rclpy.init()` and takes whatever `ROS_DOMAIN_ID` the invoking shell carries
— and requires *"a source scan over `tests/` that fails when a harness enters a ROS graph other
than through the one stated door, counting the call sites it found so that a rewrite moves a
number instead of producing silence."* At this commit:

- `ls tests/scenarios/guards/` holds four guards and **none of them is that one**;
- `grep -n rclpy.init tests/scenarios/*.py` still returns three bare calls, at
  `bringup.py:120`, `pick_and_place.py:218` and `continuous_line.py:502`;
- and **no stated door exists for a harness to enter a ROS graph through**, so the guard cannot
  be written before something is built for it to point at.

The line numbers are worth noting on their own: the status block cites `continuous_line.py:495`
and the call is now at **502**. Nothing moved the call; the file grew above it. **A line citation
is a claim with an expiry date**, which is the same lesson `9233766` recorded one commit before
the pair landed.

**What survives.** Every clause of the decision, unchanged. Clauses 1, 2 and 4 are now built and
exercised; clause 3 is untested because L5 does not exist; clause 5's operator rule holds and
`./scripts/sim --pair` is the one command that addresses both sides rather than the plant.

**How the error survived.** The change that implemented clause 4 was reviewed against
[ADR-0047](0047-two-independent-launches-joined-not-sequenced.md), which is the record that
*needed* clause 4, and this record was read as a dependency rather than as a document with a
status. That is the same shape as ADR-0041's and ADR-0043's corrections: **a record is falsified
by the branch that satisfies it, and the branch's own reviewers are looking at the record it
satisfies.** The transferable part is that a status block quoting another file's text owes that
quote a grep, exactly as a count owes a command.

## Context

### The gap, stated exactly

[ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) Decision 3 says that
`twin.sides: pair` makes the generator emit "a second side — its controller managers, its
world, its node names and its Gazebo partition". Three of those four now have a home. The
world is generated per zone and throttled ([ADR-0043](0043-hold-both-sides-to-the-wall-clock.md));
the partition is derived from the zone and the side and emitted into the plan
([ADR-0042](0042-partition-gazebo-transport-per-side.md)); the controller managers are already
one per asset in the plan. **"Its node names" is the one that is not decided anywhere**, and
it is the one that decides the other three, because a node name that collides is a node that
does not come up.

So nothing can emit a second side until this is settled, and charter §12 requires the record
before the implementation rather than after it.

### P2 fixes the names, and once they are fixed they cannot share a graph

Charter §4's P2 is not a preference about style. It reads: *"Topic names, action names,
controller names, joint names, and frame names are identical. The only thing that changes is
which hardware plugin `ros2_control` loads."* In 2.B the counterpart *is* the physical cell —
ADR-0041's Decision 3 makes that a one-line data change, `counterpart_backend: real` on the
asset that acquired hardware. Whatever names the counterpart presents in 2.A are therefore the
names hardware must present in 2.B.

[`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md) rule 2 already states
the consequence in the strongest available terms: *"Simulation and hardware use identical
names. Not similar. Identical. There is no `_sim` suffix, no separate namespace, no
'simulation variant' of a controller name."*

Two consequences follow, and the second is the whole decision:

1. Both sides of a pair present the same set of fully-qualified names — `/cite/cell_a/arm_1/joint_states`,
   `arm_1_joint_trajectory_controller`, `cell_a__conveyor_1__infeed`, all of it.
2. **A ROS graph cannot hold two of them.** Two nodes with the same fully-qualified name in
   one graph is a name collision; two publishers of one `/clock` is the defect the campaign
   registered as a FAIL condition before it ran (`criteria.md` Q1.3), and CLAUDE.md §10's
   TF rule — one publisher per transform — is violated twice over by two identical frame trees.

### The tree has exactly one domain, and it is a per-checkout allocation

`scripts/_lib.sh` derives `ROS_DOMAIN_ID` from the absolute path of the checkout — `cksum`
modulo 101, plus one — and exports it; `docker-compose.yml` passes the host's value into every
container so that the container's different path cannot re-derive a different number; an
explicit value in the environment always wins; `./scripts/doctor` fails the check when the
value is `0`. The comment there records what it was bought with: everything used to default to
domain 0, two cells on one host discovered each other's nodes, and a scenario run took 421 s
instead of 105 s.

That mechanism gives **one domain per checkout**. A pair needs two, and *where the second one
comes from* is part of this decision rather than a detail left to whoever writes the launch.

### What was measured, and what the measurement does and does not cover

[`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md)
ran two complete cells from **one checkout** — therefore the same generated tree and
byte-identical names — on **distinct `ROS_DOMAIN_ID`s**, and asked whether either graph
contained the other's nodes.

- **Q1.2, PASS.** Each side of every pair held the same node and topic counts as a solo cell,
  the only set differences being ROS's own address-suffixed names. **The counts are the
  campaign's and are not restated here** (P1): read the Q1.2 row of its `ANALYSIS.md`. What
  this record needs from that row is the *equality*, not the two integers.
- **Q1.3, PASS.** `ros2 topic info /clock --verbose` reported exactly one publisher per domain.

**That arm ran in two containers, and the confound has to be said out loud.** Q1.2 and Q1.3
were taken with two variables differing at once — two domains *and* two network namespaces —
and the campaign's own headline finding is precisely that in that arm something other than the
domain was doing the isolating on the Gazebo transport (ADR-0042). So the paired-cell result
is consistent with this decision and does not on its own establish that the domain is what
separated the ROS graphs.

**The unconfounded evidence is the mirroring rig, and it is the strongest single thing in
this record.** Q5's harness
([`harness/mirror_latency.py`](../measurements/2026-08-28-second-world-cost/harness/mirror_latency.py))
is **one process**, on one host, in one network namespace, holding two `rclpy` contexts
initialised with `domain_id=41` and `domain_id=87`, publishing and subscribing on **the same
topic string on both** — `TOPIC = "/cite/cell_a/arm_1/joint_states"`, `MIRROR_TOPIC = TOPIC`.
`raw/mirror_latency.json` records:

| Quantity | Value | What it rules out | Strength |
|---|---|---|---|
| `published` / `crossed.n` / `same_domain.n` | **20000 / 20000 / 20000** | no message arrived twice, so nothing leaked around the relay | **decisive** |
| `matched_at_start.pub_a_subscribers` | **2** | domain A's publisher matched its two domain-A subscribers and, at that instant, **not** the identically-named domain-B one | corroborating |
| `matched_at_start.pub_b_subscribers` | **1** | likewise in the other direction, at that instant | corroborating |

**Row 1 is doing all the work, and the ordering of this table was changed to say so.** The
counts are exact over the whole run: 20,000 published, 20,000 arriving across the boundary,
20,000 arriving on the near side, and **no message counted twice**. Had the two domains ever
matched each other — at the start, or a minute in — a message would have arrived both through
the relay and directly, and `crossed.n` or `same_domain.n` would exceed `published`. It
covers the full duration and it is arithmetic rather than a sample.

**Rows 2 and 3 are weaker than they look and are presented as corroboration only.**
`matched_at_start` is sampled immediately after a wait loop that breaks on a *threshold* —
`harness/mirror_latency.py` waits until `pub_a.get_subscription_count() >= 2 and
pub_b.get_subscription_count() >= 1`, then records the counts on the next two lines. A
cross-domain subscriber that matched a moment after that break would still have been recorded
as 2 and 1. The rows say a cross-domain match had not happened *by then*; they cannot say it
never happened. Row 1 is what says that.

So, on row 1: two publishers on one fully-qualified topic name, in one process and one network
namespace, exchanged nothing for the length of a 20,000-message run; every message that reached
the far side reached it through the relay written to carry it. **That is the decision,
demonstrated: identical names, separated by domain, spanned deliberately by one component.** The
rig was built to price mirroring, not to test isolation, which is why the isolation result is a
by-product rather than a pre-registered finding — and it is the reason this record cites the rig
rather than the paired cells.

The rig also priced the span, and the figures belong to the campaign rather than here: read
§4.2 for the one-way latency across the boundary and the relay's own CPU cost. The finding
worth carrying into a design discussion is not a latency at all — it is
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s, that at the measured paired real-time
factor the clock deficit overtakes the p99 crossing latency within the first few tens of
milliseconds of a run. **The crossing figure and the wall-clock figure it is compared against
are both derived in ADR-0043 and are deliberately not copied here**: `r` is a property of a
machine nobody has chosen yet (ADR-0043), and a number re-measured in one document and stale in
two is the failure P1 exists to prevent. The conclusion is what this record needs, and the
conclusion is robust to the arithmetic: **the domain boundary is not what will make mirroring
late.**

### Upstream says the same thing, and the alternative isolation does not work here

> **Verified 2026-08-29 against the primary source.** The ROS 2 Jazzy documentation states
> that *"ROS 2 nodes on different domains cannot"* communicate, and that *"domain IDs 0-101
> and 215-232 can be safely used without colliding with ephemeral ports"* on Linux —
> `source/Concepts/Intermediate/About-Domain-ID.rst` on the `jazzy` branch of
> <https://github.com/ros2/ros2_documentation>. (The rendered page at `docs.ros.org` refused
> automated fetches on that date; the branch source is the same text and is the primary
> source for it.)

**The domain is not the *only* mechanism that partitions a ROS graph, and the claim that it is
does not survive checking.** ROS 2 also exposes `ROS_AUTOMATIC_DISCOVERY_RANGE` and
`ROS_STATIC_PEERS`. It fails as an alternative here for a reason that is in the upstream
tutorial's own table rather than in an opinion:

> **Verified 2026-08-29.** `source/Tutorials/Advanced/Improved-Dynamic-Discovery.rst`, same
> branch: `LOCALHOST` *"means a node will only try to discover other nodes on the same
> machine"*, and `OFF` *"means the node won't discover any other nodes, even on the same
> machine"*. Its same-host table gives `O` — discovered and communicating — for every
> combination of `LOCALHOST` and `SUBNET`, and `X` for every row or column in which either
> node is `OFF`, **including the columns with a static peer configured.**

So on one host the only setting that separates two sides is `OFF`, and `OFF` also separates a
side from its own operator tooling, its own `ros2 topic echo`, and its own recorder. It cannot
express "these two graphs are separate from each other and each is reachable by its own
tools", which is exactly what a twin pair needs. The domain can.

## Options considered

### Option A — one graph, both sides distinguished by a side prefix or namespace

`/cite/plant/cell_a/arm_1/...` and `/cite/counterpart/cell_a/arm_1/...`, or the same idea as a
node namespace. It is the obvious first thought, it needs no new environment variable, and it
would let one `ros2 topic list` show the whole pair — which is a real benefit and the reason
this option is stated rather than dismissed.

**Rejected, and the project owner's reading that it breaks P2 outright is confirmed rather
than assumed.** The check that decides it is 2.B, not 2.A. Under ADR-0041 Decision 3 the
counterpart becomes physical by one data change, so under this option the *physical* cell would
present `/cite/counterpart/cell_a/arm_1/joint_states` while the same arm driven in Phase 1
presents `/cite/cell_a/arm_1/joint_states`. Code that commanded the simulated cell would not
command the physical cell unmodified. That is charter §4's P2 verbatim, and P2 names its own
violation the highest-severity defect in the project.

It fails three further tests, any one of which is sufficient:

- **It rewrites a stated rule.** `naming-and-namespaces.md` rule 2 forbids a separate namespace
  for a variant of the same thing, in as many words. Adopting this option means editing that
  rule to say the opposite, and the rule is there because P2 is made of names.
- **It changes every name in the system to express a deployment fact.** ADR-0041 Decision 3
  argues at length that whether a zone is paired is one fact written once, and rejected writing
  it on fifteen instances as "P1 at a different granularity". Writing it into every topic,
  action, controller and frame name is the same objection two orders of magnitude larger.
- **It does not even isolate what most needs isolating.** Gazebo transport is not ROS naming;
  ADR-0042 measured that two servers in one container cross regardless, and its Option C —
  renaming one side's topics — was already rejected on the same P1/P2 grounds and on its own
  terms, because it does not namespace the world-control services.

**The one escape, closed here rather than left for 2.B.** The reply this refutation attracts is:
*P2 is about source, and the consumer's source is unmodified — only its launch remappings
change, so a remapped consumer does command the physical cell "unmodified".* It is a serious
reading of P2 and it fails on the mechanism, three times over:

- **Frame ids are message content, not names, and nothing remaps content.** A `PoseStamped`
  carries `header.frame_id` as a string in the payload; a planning scene, a TF broadcast and a
  MoveIt goal all carry frame ids the same way. ROS 2 has no facility for rewriting them —
  `tf_prefix` was **removed** from ROS 2 for exactly this reason, so the mechanism this escape
  needs is one upstream deliberately deleted. A prefixed counterpart therefore publishes
  `counterpart/arm_1_link_base` *inside* its messages, and every consumer that names a frame has
  to name a different one per side. That is a source change, not a launch change.
- **Half the names P2 enumerates are not topic names at all.** P2 names controller names and
  joint names; controller names are keys in a controller manager's parameters, SRDF group and
  link names are parameters loaded by `move_group`, and MoveIt's controller list is a parameter
  file. Remapping acts on topic, service and action names. **No remapping mechanism reaches a
  parameter**, so under this option the counterpart's controller and SRDF names either differ —
  and every consumer that names one changes — or they do not, and the option has not actually
  separated the two sides.
- **It relocates the P2 violation rather than removing it.** Even for the names remapping *can*
  reach, "unmodified" now means "modified everywhere it is launched". The launch graph is
  generated from L0 (P1, ADR-0021), so this is a per-side branch in the generator and a second
  form of every name in the generated tree — which is the objection two bullets above, arriving
  again by another road.

**If this refutation is ever itself refuted, stop.** The whole record rests on it: if someone
shows that a prefixed counterpart can become physical in 2.B without any consumer changing —
including its frame ids and its parameters — then Option A is cheaper than this decision and
this decision should be withdrawn rather than patched.

**A note for the DDS-literate reader, who will propose a fourth mechanism.** DDS vendors expose
partitions of their own — Fast DDS's `<partition>` element in its XML profiles is the one that
gets suggested — and they look like exactly the thing wanted here. They are not, on two counts.
A DDS partition scopes **endpoint matching**, not participant discovery: both sides' nodes still
join one graph and still carry one fully-qualified node name each, so the collision clause 1's
consequence 2 describes is untouched and `ros2 node list` still has to name two things the same.
And it is **single-vendor** configuration in a project whose `doctor` prints
`RMW_IMPLEMENTATION` as a variable (`scripts/doctor:99`), so it would be isolation that stops
existing the day somebody sets that variable — the same "isolation nobody can name" objection
Option C is rejected on.

### Option B — one graph, the plant unprefixed and the counterpart prefixed

Asymmetric, and it deserves its own paragraph because it looks like the cheap escape from
Option A: the plant keeps every existing name, nothing in Phase 1 moves, and only the
counterpart is renamed. Rejected on three counts.

- **It makes "which side am I" a property of the name.** L5 has to address both sides; under
  this option the same operation reads a different string depending on which side it is aimed
  at, so L5 carries a branch that the naming scheme should have removed. A name that encodes
  which of two interchangeable things it belongs to is the opposite of interchangeable.
- **It renames a whole cell the day the sides swap.** In 2.B the *counterpart* is the physical
  side, so every physical name would carry the prefix; ADR-0041's Decision-3 refusal of
  `backend: real` under `twin.sides: pair` exists precisely to stop the two encodings of one
  physical situation from both being expressible, and this option reintroduces the same
  ambiguity in the naming layer instead of the schema.
- **It violates rule 5 of `naming-and-namespaces.md`** — an asset ID is stable for the life of
  the asset, because renaming invalidates every recording, trend and historical comparison.

### Option C — separate containers, or separate hosts, and no explicit mechanism at all

It is what kept the campaign's pairs apart on the ROS side, it works today, and it costs
nothing to keep doing.

**Rejected on ADR-0042's precedent, and the precedent is this repository's own scar.** That
record rejected exactly this reasoning for the Gazebo transport: it is a property of one
deployment, stated nowhere, tested by nothing, and it fails silently the first time somebody
runs both sides in one container to watch them together — the most likely thing anyone
debugging a twin pair will do. Two containers on one host with default discovery ranges is a
`SUBNET`/`SUBNET` pair by the table quoted above, so whether the graphs cross would depend on
the container network's multicast behaviour rather than on anything anyone decided. Isolation
nobody can name is isolation nobody can review.

Note that this option is not *wrong* about the world — separate hosts really do isolate. It is
rejected as a **decision**, in the same words ADR-0042 used.

### Option D — the counterpart presents no ROS graph at all, so there is nothing to separate

The sharpest attack on this record, and the only one that comes from outside the framing every
other option shares. All of A, B and C assume the problem is *how to separate two ROS graphs
that carry one set of names*. This one denies the premise: **a 2.A counterpart does not need a
ROS graph.** Let it be a physics process that L5 drives through a private, non-ROS channel —
Gazebo transport, which ADR-0042 already partitions per side, or a direct in-process stepping
API. No ROS endpoints means no name collision, no second domain, no allocation problem, no
`101 + 1 = 102` edge, and clause 4 of this decision disappears entirely. It is cheaper than the
chosen option on every axis this record has counted so far, and it is not obviously wrong.

**Rejected, and it dies on 2.B rather than on 2.A.** ADR-0041 Decision 3 makes the counterpart
physical by one data change, `counterpart_backend: real`. **A physical cell necessarily presents
a ROS graph** — it is `ros2_control` with a different hardware plugin (ADR-0005), `move_group`,
controllers and joint states, carrying by P2 the identical names the plant carries. So under
this option:

- **2.A → 2.B stops being a data change and becomes a redesign.** Everything L5 learned to speak
  to a counterpart — the channel, the message shapes, the addressing — is thrown away on the day
  the counterpart becomes hardware, and the collision problem this record solves arrives then
  anyway, unsolved, at the point in the project where being wrong is most expensive. ADR-0041's
  Decision 3 is worth exactly as much as the one-line change it promises.
- **The 2.A rehearsal would never exercise the interface 2.B uses.** The entire value of a
  virtual counterpart is that it is a rehearsal for a real one. A counterpart reached over a
  channel hardware cannot offer is a rehearsal for nothing: the first time anyone drives the
  interface that matters, it is attached to an arm that can hit something.

So the option is cheap in 2.A and pays for it in 2.B with the one thing ADR-0041 was designed
to buy. **This is the strongest argument in the record for the chosen option**, because it is
the only one that survives dropping the assumption that both sides are ROS graphs — the
counterpart is a ROS graph carrying identical names not because that is convenient in
simulation, but because in 2.B it is not a choice.

### Option E — one ROS domain per side, byte-identical names on both

Chosen.

## Decision

**Each side of a twin pair runs in its own `ROS_DOMAIN_ID`. Both sides carry byte-identical
names — nodes, topics, services, actions, controllers, joints and frames. L5 is the only
component with endpoints in both domains.**

Five clauses. The first three are the decision; the last two exist because a decision that does
not say where its values come from and who is allowed to cross gets those answers improvised.

### 1. Names are identical, and nothing marks a side inside a name

There is no side prefix, no side namespace, no `_plant`/`_counterpart` suffix, and no second
form of any frame id. `naming-and-namespaces.md` is unchanged by this record, which is the
point: a decision about twinning that required editing the naming rules would be a decision
against P2.

The side identity lives **outside** the graph — in the environment of the processes that make
up a side — and is therefore invisible to every consumer, which is what makes a consumer
portable between the two sides and, in 2.B, between simulation and hardware.

### 2. `ROS_DOMAIN_ID` and `GZ_PARTITION` are two independent isolations, and neither substitutes for the other

ADR-0042 established one half of this by measurement: `ROS_DOMAIN_ID` does **not** isolate
Gazebo transport — two servers in one container on separate domains produced two publishers on
one world's stats topic and two subscribers on one belt's command topic. **The converse is
equally true and is stated here so that nobody has to discover it the same way:
`GZ_PARTITION` does not isolate the ROS graph.** It is a gz-transport namespace; `move_group`,
the controller managers, the skill servers, the facility servers and the L4 coordinator speak
DDS and have never heard of it. A pair partitioned but not domain-separated is a pair whose
Gazebo transports are clean and whose ROS graphs collide on every name they own.

**The rule for anyone adding a process to either side, stated once:**

> A process belonging to a side is started with **both** `ROS_DOMAIN_ID` and `GZ_PARTITION`
> set, both resolved from the **same side identity**, obtained from the **same place** — the
> side's entry in the generated bring-up plan. A process that carries one and not the other is
> a bring-up failure, not a warning.

That "same place" is not decoration. ADR-0042's correction records what happened when one
class of process was started outside the one door that sets this environment: seven Gazebo
commands with a bare inherited environment, none refused, none partitioned, each failing
silently — and one of them, `gz model --list`, **exiting 0 having reached no world at all**.
The door exists now, `cite_bringup/cite_bringup/gz.py`, with a source-scan guard over `tests/`.
The domain belongs behind the same door, for the same reason, and the guard's question — *what
else starts one of these?* — has to be asked of the tree again for ROS processes, because the
answer for Gazebo processes does not transfer.

### 3. L5 is the only cross-domain component, and it is a cross-domain component by definition

L5 has to see both sides: it owns mode, command routing, mirroring and the divergence monitor
([L5](../architecture/L5-twin-synchronization.md)), and every one of those is a statement about
two sides at once. So L5 is not merely permitted to hold endpoints in both domains — **being
the thing that spans them is what L5 is**, and this record is where that becomes a stated
architectural property rather than an implementation accident.

**Anything else in the running system that observes both sides is a defect**, in the same class
as a layer reaching upward (CLAUDE.md §5): it puts twin-boundary knowledge into a component
whose interface says it has none, and it is invisible in review because a second
`ROS_DOMAIN_ID` is one line of environment.

**Three carve-outs, stated so they are not read as loopholes.**

- **A test harness is not part of the running system.** A scenario that asserts something about
  a pair has to observe both sides; that is legitimate, and it must go through **one stated
  door** the way every Gazebo call now does, so that the set of cross-domain observers is a
  list somebody can read rather than a grep nobody runs.
- **A supervisor of the two launch processes is not an observer of either graph, and it is not
  L5.** The *Consequences* section below establishes that a paired bring-up is two launch
  processes and that something above both must sequence them. That something has to know both
  sides reached a state, which by the rule above looks like a cross-domain observer and would
  therefore be a defect — a reading that would leave this record forbidding the only shape it
  leaves available. **It is carved out, and the carve-out has a boundary rather than being an
  exception.** What a supervisor may observe is **launch processes and their exit status** —
  operating-system facts, on neither domain. It holds no ROS context, creates no node,
  subscribes to no topic and calls no service on either side; a supervisor that opens an
  `rclpy` context to check whether a node came up has left the carve-out and is a defect
  under the rule. It is not L5 for the same reason it is allowed: L5 is defined by having
  endpoints in both domains and deciding what crosses, and a process supervisor has endpoints
  in neither and decides nothing about ROS traffic. It sits beside the layer stack, where
  `./scripts/sim` and `./scripts/scenario` already sit.
- **A recorder is not exempt, it is unresolved.** L6 records both sides' telemetry, which is a
  cross-domain observation by any reading of the rule above. Whether L6 records per side and
  merges later, or receives everything through L5, is **not decided here** — see *What this
  record does not decide*. Until it is, an L6 process holding two domains is a finding to raise
  rather than a pattern to copy.

**L7 is decided, and it is decided rather than left unmentioned on purpose.** An operator HMI
showing the plant beside the counterpart is a both-sides observer by exactly the reading that
makes L6 a question, and a record that marked L6 unresolved while saying nothing about L7 would
read as though L7 were settled — settled the permissive way, by silence. It is not permitted:
**L7 reads L5's published state and holds no second domain.** A display of divergence is a
display of something L5 computed; the comparison is L5's work, not the HMI's, and an HMI that
opened a second context to fetch the counterpart's joint states itself would be computing the
twin's central quantity in the presentation layer. The rule is the ordinary layer rule (CLAUDE.md
§5) rather than a new one — L7 depends on L5 — and L5 already owns the divergence monitor, so
this clause creates no work. It exists so that "L7 was not mentioned" is never available as an
argument.

**How L5 spans the boundary is deferred, and the candidates are named rather than left to be
rediscovered.** Two exist:

- **One process, two contexts.** `rclpy.init(context=..., domain_id=N)` per side — demonstrated
  in this repository by the campaign's Q5 rig, carrying 20,000 messages across two domains
  with no losses by its own count. The C++ equivalent is `rclcpp::InitOptions::set_domain_id`.
  > **Verified 2026-08-29:** `set_domain_id(size_t domain_id)`, `get_domain_id()` and
  > `use_default_domain_id()` are declared in `rclcpp/init_options.hpp` in the Jazzy image —
  > `docker run --rm ros:jazzy-ros-base-noble grep -n domain_id /opt/ros/jazzy/include/rclcpp/rclcpp/init_options.hpp`.
- **`domain_bridge`.** An upstream ROS 2 package whose stated purpose is to bridge ROS
  communication between domain IDs.
  > **Verified 2026-08-29:** `ros-jazzy-domain-bridge` resolves in the Jazzy image, candidate
  > `0.5.0-5noble.20260612.125528` from `packages.ros.org/ros2/ubuntu noble/main`, via
  > `docker run --rm ros:jazzy-ros-base-noble apt-cache policy ros-jazzy-domain-bridge`. Its
  > design document (`doc/design.md`) names topics, services and actions as objectives, while
  > its README describes the configuration-file, CLI and launch path in terms of topics only.
  > **Whether its service and action support is sufficient for anything L5 needs is unverified
  > here**, and reading the two documents does not settle it.

**The criterion for choosing, so that the choice is not made by whoever writes the code first:**
a bridge *copies*; it cannot refuse, transform, timestamp or gate. Take `domain_bridge` only
for traffic that L5 merely needs on the other side unchanged, and only after its coverage of the
entity type in question — topic, service or action — has been verified rather than assumed;
`MoveTo` and `Pick` are actions and `SetMode` is a service, so a mirroring design that puts any
of those across the boundary must settle that first. Take contexts-in-one-process wherever L5
must *decide* something about what crosses, which command routing and the divergence monitor
both do by construction.

### 4. Where the domain value comes from

**The plant's domain is the checkout's existing `ROS_DOMAIN_ID`, unchanged. The plan states each
side's offset from it, derived from the side identity in the one place names are formed. The
absolute value is resolved at bring-up as base plus offset.**

This deliberately does **not** follow ADR-0042's shape exactly, and the difference is argued
rather than glossed. That record emits the partition's *literal value* into the generated plan,
on the grounds that a partition is a **name** — the same class as the node names, topic names
and description paths the plan already carries. A domain ID is not a name. It is a **host-scoped
resource allocation**, closer to a TCP port: it must not collide with anything else on the
machine or the lab network, which is a fact about a deployment and not a fact about the
facility. **Emitting an absolute domain into `cite_generated/` fails two ways, not one, and the
first is fatal on its own.**

- **It breaks `./scripts/validate-model` everywhere except the machine that committed.** The
  generated tree is committed and hashed, and ADR-0021 requires a fresh generator run to be
  **byte-identical** to what is on disk — `validate-model` diffs it and regenerates under a
  second interpreter and a different hash seed to prove it. An absolute domain derived from the
  checkout path would differ in every clone, so the diff would fail in every clone but the one
  where the value was written, and would fail in CI. That is not a trade-off; it is a breach of
  the requirement, and it disqualifies the option before the second argument is reached.
- **Derived from the *model* instead, it collides.** Making it path-independent restores
  byte-identity and destroys the isolation: two checkouts of the same commit generate the same
  absolute domain and discover each other, which is the exact defect `cite_domain_id`'s comment
  records as having cost a scenario run four times its runtime.

The two failures are jointly exhaustive over the ways an absolute value could be derived — from
the deployment, or from the model — which is why the offset is the only shape left.

What *is* a fact about the modelled system is **which side this is**, and the offset is a
function of nothing else. So:

- **`plant` is offset 0 and `counterpart` is offset 1.** Plant at zero is not arbitrary: it
  makes an untwinned zone's resolved domain identical to today's, so nothing in Phase 1 moves,
  and `./scripts/enter` from a checkout still lands on the side every existing script addresses.
- **The offset is formed in `tools/cite_tools/model/ids.py`**, beside `ids.partition`, from the
  same `SIDES` tuple — so the two isolations of clause 2 are derived from one side identity in
  one file, and a third isolation added later has an obvious home.
- **It is emitted into the plan's `sides:` entry, beside `gz_partition`**, so that both
  isolations appear together in one reviewable diff and are checked by
  `./scripts/validate-model` like every other generated value. The offset is emitted rather
  than left implicit in list order: ADR-0042 made the partition explicit for the same reason,
  and positional meaning is not reviewable.
- **The base travels explicitly, in `CITE_DOMAIN_BASE`.** `scripts/_lib.sh` exports it beside
  the `CITE_DOMAIN_SOURCE` it already exports (`scripts/_lib.sh:92-100`), and
  `docker-compose.yml` passes it across exactly as it passes `ROS_DOMAIN_ID`. This is not
  redundancy with `ROS_DOMAIN_ID` and the next bullet is why.
- **Bring-up refuses**, in the same manner and the same place as the partition: a side whose
  process environment does not carry the domain the plan resolves for it does not start.
  Symmetry with clause 2 is the requirement — one refusal covering both variables, so that
  carrying one and not the other is impossible rather than merely discouraged.
  **The plant's half of that refusal is a tautology unless the base is carried separately, and
  this is the failure this record most nearly repeated.** `GZ_PARTITION`'s refusal has teeth
  because the plan carries a **literal** to compare the environment against. A domain is
  `base + offset`, so a refusal has to obtain the base from somewhere; the only place bring-up
  could read it without `CITE_DOMAIN_BASE` is `ROS_DOMAIN_ID` in its own environment — which
  **for the plant, at offset 0, is the value under test.** The check would reduce to
  `env == env + 0`, which passes for every possible value, including a wrong one. Only the
  counterpart's half would have had teeth, and a green refusal would have been read as covering
  both sides. **That is the shape of ADR-0042's promotion error exactly** — a refusal believed
  to cover a class it did not — and it is caught here, before implementation, only because the
  arithmetic was written out. With `CITE_DOMAIN_BASE` the plant's refusal compares two
  independently sourced values and can fail.
- **One resolver, named, and every consumer reads its output.** The resolution
  `base + offset → absolute domain` is written **once**, in `cite_bringup`, beside the plan
  loader that already answers the same question for the partition: one function taking the plan,
  a side and the base, returning the side's domain. The launch graph, the refusal, `doctor`'s
  report, `./scripts/enter`'s counterpart flag and any scenario that addresses a pair call it;
  **none of them recomputes `base + offset`**, because a second copy of that arithmetic is a
  value in two places (P1) and the two copies disagree the first time the allocation changes —
  which the very next bullet changes. Shell callers reach the resolver the way
  [`docs/operations/troubleshooting.md`](../operations/troubleshooting.md) already reaches
  `gz_partition`, by asking Python for the plan's answer rather than reimplementing it in `sh`.
  **The tree already shows what the alternative costs**: `cite_domain_id`'s range bound exists
  in three places today, and the third is an independent reimplementation that has drifted out
  of the obligation list of every document that mentions the first. See the next bullet.

**The allocation changes, and the new one is decided here rather than left as an obligation.**
A checkout now claims **two domains instead of one**, and the range has to hold both. An earlier
draft of this record said only that the allocation "has to be narrowed or wrapped" and left the
choice to the implementer. That was wrong twice: **one of the two remedies is already refused by
a check in this tree**, and the other has a consequence the same paragraph was worrying about.

- **Wrapping is dead on arrival.** `cite_domain_id` returns 1..101, so base 101 plus offset 1 is
  102, outside the `0-101` band the ROS 2 documentation names as safe on Linux (quoted in
  *Context*). Wrapping 102 to 0 lands on the ecosystem-wide default — and `scripts/doctor:93`
  **fails the run** when `ROS_DOMAIN_ID` is 0, deliberately, because domain 0 is the shared
  default this whole mechanism exists to escape. A wrap would produce a counterpart that
  `doctor` is already written to reject.
- **Narrowing alone is legal and still bad.** Taking `cksum % 50 + 1` keeps both values in range
  but halves the space to 50 buckets while leaving *four* ways two checkouts can overlap —
  plant/plant, plant/counterpart, counterpart/plant, counterpart/counterpart — so it roughly
  triples the collision surface rather than doubling it, and it leaves intact the direction this
  paragraph calls the more confusing one: this checkout's counterpart landing on another
  checkout's plant.

**Decided: the base is allocated on odd numbers, and the offset makes the counterpart even.**

```
plant       = 2 * (cksum(checkout path) % 50) + 1      # 1, 3, 5, ... 99
counterpart = plant + 1                                # 2, 4, 6, ... 100
```

The properties, in the order they matter:

- **Plants are odd and counterparts are even, so the confusing direction becomes structurally
  impossible.** No counterpart can ever equal any plant, on any host, for any pair of checkout
  paths — not "rare", not "unlikely", *impossible by parity*. The only remaining overlap is two
  checkouts drawing the same base, which collides both sides together and is the ordinary
  same-domain case developers already recognise.
- **The `101 + 1 = 102` edge is gone** and both values sit inside 1..100, strictly within the
  safe band, with domain 0 unreachable — so `doctor:93` keeps its meaning instead of being
  worked around.
- **Clause 4's whole shape survives unchanged.** `plant + 0` and `plant + 1` is still literally
  `base + offset`; the plan still carries offsets 0 and 1; the resolver is still one addition.
  **Only the derivation of the base changes, and only in `cite_domain_id`** — a one-line change
  to the modulus and the doubling, not a redesign.
- **The honest cost: 50 possible bases where there were 101.** Two checkouts on one host now
  collide with probability about 1 in 50 rather than 1 in 101 — a genuine doubling, accepted,
  and unavoidable for any scheme that gives a checkout two domains. Compared against the
  alternative actually available, plain narrowing, it is **three times better**, because parity
  removes three of the four overlap cases. Collisions remain undetected either way; the
  instrument that would detect one is named at the end of this clause.
- **`./scripts/_selftest.sh`'s existing fixtures survive.** Its "two checkouts get different
  domains" assertion compares `/home/dev/twin` and `/home/dev/twin-review`; under the new
  derivation they resolve to plants **51** and **7**, still distinct, so that assertion does not
  have to be re-fixtured. (Checked directly, and worth reporting because it is the cost above
  made concrete rather than a new defect: among the eight fixed paths this file's fixtures use,
  `/home/dev/twin-review` and `/d/e/f` both resolve to plant **7** — one collision in eight
  samples, which is what a 1-in-50 rate looks like at this sample size. The selftest compares
  neither of those against the other, so nothing in it breaks.)
- **Every checkout's domain changes on the day this lands.** A cell launched before the change
  and a shell entered after it are on different domains, and the shell will find an empty graph.
  It is a one-time transition, it affects no committed artifact, and it is worth a line in the
  implementing change's commit message.

**The bound lives in three places, not one, and only one of them was on this record's obligation
list.** Verified individually at `c4c16e0`:

| Where | What it holds | What the change owes it |
|---|---|---|
| `scripts/_lib.sh:89` | `printf '%s' "$(( sum % 101 + 1 ))"` — the derivation itself | the new arithmetic |
| `scripts/_selftest.sh:291-300` | a loop asserting `1 <= domain <= 101` over seven fixture paths | assert the *pair* is in range and that the base is odd — the property, not just the bound |
| `workspace/src/cite_runtime/test/test_shutdown_under_signal.py:102-106` | **an independent reimplementation** — `candidate = os.getpid() % 101 + 1`, with its own copy of the ephemeral-port comment at lines 98-100 | see below; this one is a correctness bug under a pair, not just a stale constant |

That third entry is the one that matters and the reason this table exists. It is not a caller of
`cite_domain_id`; it is a second implementation of the same rule, which is why it drifted out of
sight. It picks a private domain for a test's child processes and **avoids exactly one value** —
the ambient `ROS_DOMAIN_ID`, stepping once if it collides. Under a pair there are **two** domains
a test must avoid, and the one it does not know about is the counterpart's: a test whose pid
happens to land there joins a live counterpart's graph, on a domain where every node runs
`use_sim_time` — which is precisely the failure its own docstring (lines 29-36) says the private
domain exists to prevent, arriving through the door it left open. **The implementing change must
make that picker avoid the whole set the plan resolves, not the ambient value**, and it should
reach the answer through the resolver rather than growing a third copy of the arithmetic.

**One further obligation, unchanged:** `./scripts/doctor` reports one domain and would report
only the plant's. It should report every side the plan declares, or say plainly that it does
not.

Nothing in the tree can detect a collision between two checkouts today; the instrument that
would is the campaign's Q1.2 — compare the node and topic set on a domain against the expected
set and report anything foreign. That is a check, not a decision, and it is named here so the
gap is on the record.

### 5. The operator's tooling has a side, and the side is the plant

A person running `ros2 topic echo`, RViz, `rqt` or a recorder sits in one domain and sees one
side. **That domain is the plant's**, by default and without a flag.

It is the plant's for a structural reason and not for convenience. ADR-0041 Decision 3 defines
`plant` as the side the untwinned model already describes and that every Phase 1 artifact,
scenario and script already addresses, and its target operating mode — `MODE_VIRTUAL_LEAD`,
now in `TwinMode.msg` — is *an operator commands the simulated side and the far side follows
and actuates*. In 2.B the far side is the hardware, carried by `counterpart_backend: real`. So
the side a person commands and the side a person watches is the plant in both phases, and the
per-checkout domain that `./scripts/sim`, `./scripts/enter` and `./scripts/scenario` already
share is the plant's domain with nothing to change.

**Reaching the counterpart is therefore deliberate and explicit**, which is the same property
mode transitions have for the same reason. The implementing change owes a way to do it — a flag
on `./scripts/enter` is the obvious shape — and owes it before anyone needs to debug a
counterpart, not after.

## Consequences

### What this gets us

- **P2 survives 2.B untouched.** Nothing a consumer sees changes when the counterpart becomes
  physical: same topic, same action, same controller, same frame. That is the entire reason for
  the decision and it is the one thing 2.B will test for real.
- **The isolation is a stated, derived property with a name**, in the same class as the Gazebo
  partition and derived from the same side identity — rather than a consequence of how many
  containers somebody happened to run.
- **Deployment freedom.** One container, two containers, one bare-metal host or a shared network
  namespace behave the same, which matters because the target machine is not this development
  host and has not been chosen (ADR-0043).
- **The span becomes a single, reviewable place.** "Who can see both sides" has one answer, so a
  second answer appearing in a diff is visible as a defect instead of looking like plumbing.

### What this costs us

- **`ros2 topic list` in one domain shows one side, and the failure is silence rather than an
  error.** This is the same shape as the cost ADR-0042 accepted and it is stated in the same
  place for the same reason. A `ros2 topic echo` aimed at a topic on the other side does not
  fail; it waits, indefinitely, exactly as a wrong QoS profile does
  ([`qos-profiles.md`](../interfaces/qos-profiles.md)) and exactly as an unpartitioned
  `gz model --list` exits 0 having reached no world. **The correct instinct on an empty or
  short `ros2 node list` during a paired run is to check which domain the shell is in before
  suspecting anything about the cell.**
  What a developer runs instead: `./scripts/enter` from the checkout, which lands on the plant;
  `echo $ROS_DOMAIN_ID` compared against the plan's `sides:` before believing an empty list; and
  the counterpart's domain explicitly when it is the counterpart they mean. **The implementing
  change owes [`docs/operations/troubleshooting.md`](../operations/troubleshooting.md) an entry
  next to the Gazebo-partition one**, and owes `docs/onboarding/getting-started.md`'s
  `ROS_DOMAIN_ID` section a sentence, since that section currently describes one domain per
  developer.
- **One `ros2 launch` process cannot *lifecycle-sequence* both sides, so a paired bring-up is
  two launches.** The verb matters and the earlier draft of this bullet overstated it. A launch
  process can perfectly well **start** a process on another domain: adding `ROS_DOMAIN_ID` to an
  existing `additional_env=` is one line, and it is already the idiom at four call sites in
  `simulation.launch.py` (lines 275, 349, 422 and 479, which carry `additional_env=gz_env`).
  The counterpart's processes would come up. What a launch process cannot do is **drive a
  managed node through its lifecycle transitions on a domain other than its own**, and that is
  what this repository's bring-up is made of. Verified rather than assumed:
  > **Verified 2026-08-29 in upstream source, `jazzy` branch of <https://github.com/ros2/launch_ros>.**
  > `launch_ros/ros_adapters.py`'s `ROSAdapter.start()` creates **one** `rclpy.Context` and one
  > node — `rclpy.create_node('launch_ros_{}'.format(os.getpid()), context=self.__ros_context)`
  > — and `get_ros_adapter()` keeps one adapter per launch context.
  > `launch_ros/utilities/lifecycle_event_manager.py`'s `setup_lifecycle_manager` calls
  > `get_ros_node(context)` and creates both the `transition_event` subscription and the
  > `ChangeState` client **on that node**.
  >
  > **Re-verified 2026-08-29 against the installed package rather than the branch**, which is
  > the stronger check because it is the code that would actually run:
  > `docker run --rm ros:jazzy-ros-base-noble sed -n '74,80p' /opt/ros/jazzy/lib/python3.12/site-packages/launch_ros/utilities/lifecycle_event_manager.py`.

  This repository's bring-up is built on exactly that mechanism: `simulation.launch.py`'s
  `_managed()` drives every managed node through `EmitEvent(ChangeState)` and gates the next
  stage on `OnStateTransition`, which is what makes bring-up event-driven rather than timed
  (P4). A launch process therefore drives lifecycle nodes on **its own domain only**, and a
  second side needs its own launch process with its own `ROS_DOMAIN_ID`, sequenced by something
  above both. `gz.py`'s docstring already anticipates this — "bringing a counterpart up is a
  separate launch and is not built yet" — and this record is what makes that the decided shape
  rather than an implementation note. **[Corrected 2026-08-30 — see the Correction section
  above: that sentence is no longer in `gz.py`, and the separate launch it anticipated is
  built.]**

  **The one-line shortcut fails silently and indefinitely, and naming that is the whole point of
  this bullet.** Because the counterpart's processes *do* come up under `additional_env=`, the
  shortcut looks like it works right up until the first managed transition. What happens then,
  read from the same installed file:

  > `_call_change_state` opens with
  > `while not self.__rclpy_change_state_client.wait_for_service(timeout_sec=1.0):`, and the
  > body of that loop contains **only** a `context.is_shutdown` test. There is **no log line on
  > the waiting path** — not at any level, not once, not throttled. The single warning
  > ("Abandoning wait for the ... service, due to shutdown") is emitted when launch is already
  > shutting down.

  The client lives on the launch node, on the launch process's domain; the counterpart's
  `change_state` service lives on the counterpart's. They never match. So bring-up **hangs at
  the first managed transition, forever, in complete silence** — no error, no warning, no
  timeout, and a process list showing every expected process alive and healthy. Nothing
  distinguishes it from a node that is merely slow to configure.

  **That failure mode is named here because it is the canonical provocation for a
  `TimerAction`.** A silent hang at a lifecycle transition, in a repository whose lifecycle
  chain is the thing that makes P4 real (CLAUDE.md §3, §4), is exactly the situation in which
  somebody reaches for a sleep — and a sleep would make the symptom intermittent instead of
  removing it, because the service is never coming. **The hang is not a timing problem and no
  amount of waiting fixes it; the client is on the wrong domain.** The correct shape is two
  launch processes, each sequencing its own side. **What sequences the two, and how a failure on
  one side stops the other, is not decided here and must not be answered with a sleep.**
- **A cross-domain component sees two frame trees whose frame ids are identical.** That follows
  directly from clause 1: both sides broadcast `cell_a__conveyor_1__infeed` and
  `arm_1_link_base`. The two trees must therefore never be fed into one TF buffer — one buffer
  per side, keyed by side — and any cross-domain component that resolves a frame must say which
  side it meant. CLAUDE.md §10's "one publisher per transform" is not violated by the pair,
  because the two publishers are in two graphs; it *would* be violated the moment something
  merges them.
- **Two domains per checkout, drawn from half as many bases, with no detector.** Stated in full
  under Decision clause 4, which decides the odd-base allocation, retires the `101 + 1 = 102`
  edge, and lists the three places the old bound lives.
- **Every place that assumes one domain has to learn about two** — `doctor`, `_lib.sh`, the
  compose environment, `./scripts/enter`, **`cite_bringup/cite_bringup/gz.py:109`, which resolves
  the side as `plan.sides[0]`**, **`docs/operations/troubleshooting.md:216`, which tells a
  developer to read `sides[0].gz_partition`**, **the private-domain picker at
  `workspace/src/cite_runtime/test/test_shutdown_under_signal.py:102-106`**, and any scenario
  that asserts across a pair. The two `sides[0]` sites deserve their own sentence, because they
  are an inconsistency inside this decision rather than merely work it creates: **clause 4
  refuses positional meaning for the offset — "positional meaning is not reviewable" — while the
  tree already takes the *side itself* positionally**, in the very module clause 2 designates as
  the single door. `gz.py`'s docstring is honest about it ("when it is, it takes the second entry
  of the same list rather than a second rule"), which makes it a known shortcut rather than a
  bug, but a plan whose `sides:` list is addressed by index is one reordering away from a cell
  bringing up the counterpart's environment while calling it the plant. Whatever this record's
  resolver takes as its side argument, it should be the side's **identity**, and `gz.py` should
  ask for the plant by name.
  **The list as a whole** is the ROS-side twin of the cost ADR-0042 paid on the Gazebo side, and
  ADR-0042's correction is
  the evidence that this list is the dangerous part of a decision like this one: the cost
  section was written correctly and then read as though it were a checklist that somebody had
  worked through. **It is not one. Whoever promotes this record has to establish, against the
  tree, that each item was paid.**
- **A refusal at bring-up will stop somebody's run on a machine where nothing was ever going to
  collide.** Deliberate, and the same trade ADR-0042 took: the alternative is a rule that binds
  only when someone remembers it.

### What we will have to revisit

- **If the mirroring design needs a service or an action across the boundary.** The candidate
  choice in clause 3 was deferred with a criterion, and this is the condition that forces it:
  `domain_bridge`'s coverage of the entity type must be verified before it is chosen, and this
  record verified only that the package resolves.
- **When L6 begins, and the recorder's relationship to the boundary has to be settled.** Named
  as unresolved in clause 3 rather than decided.
- **When 2.B lands.** The counterpart becomes physical and this record's central claim — that no
  consumer changed — becomes testable for the first time. If any consumer has to change, this
  decision failed at the one thing it was made for, and that must be written down rather than
  absorbed.
- **If a physical cell must sit on a lab domain that is not this checkout's base plus one.**
  `docker-compose.yml` already records the case for the `hardware` service: a lab network where
  other machines are on a known domain wants an explicit value, not a derived one. Clause 4's
  derivation must not become a reason to renumber a physical cell; the escape is the existing
  one — an explicit `ROS_DOMAIN_ID` wins — but how that interacts with a *plan-stated* offset is
  not worked out here, and 2.B is where it will bite.
- **If a zone ever runs more than two sides.** "Offset 0 and offset 1" is written against
  ADR-0041's two, and `ids.SIDES` has two members. A third side needs the allocation **rethought
  rather than extended**, and clause 4's choice sharpens that rather than softening it: the
  odd-base scheme buys its central property — no side of one checkout can ever land on another
  checkout's plant — from the fact that a pair is exactly two wide, so `base + 2` is odd again
  and lands squarely back in plant space. A third side would have to re-derive the stride and
  the modulus together, and would draw from fewer than 33 bases.

## What this record does not decide

Named explicitly so that a later reader does not mistake this for the L5 design, which it is
not.

- **The mirroring mechanism.** What crosses the boundary, in which direction, at what rate, in
  what message, and how it is triggered. This record settles only that whatever crosses, crosses
  in L5, and names the two transport candidates with the criterion for choosing between them.
- **The divergence metric.** What is computed, against what reference, and whether `valid` is
  even true under `MODE_VIRTUAL_LEAD` — which [L5](../architecture/L5-twin-synchronization.md)
  lists as an open question and which nothing here closes. ADR-0041 is also explicit that **no
  number produced in 2.A is a fidelity result**, and separating the sides by domain does not
  change that by one word.
- **Whether `SHADOW` needs a full second simulation at all.** ADR-0041 leaves that fork open on
  measured grounds and states that no later document may cite it as having picked one. This
  record does not pick one either: it is about how two sides are separated *if* two sides are
  instantiated, and it is equally true of a counterpart that is three `robot_state_publisher`.
- **What sequences the two launch processes**, and how a failure on one side stops the other.
  Clause 3 decides *what such a sequencer is allowed to be* — a supervisor of launch processes
  and exit status, on neither domain, not L5 — and the *Consequences* section names the silent
  hang that awaits anyone who tries to avoid needing one. Neither settles what it is or where it
  lives.
- **How L6 records a pair**, per clause 3's third carve-out.
