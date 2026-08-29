# ADR-0042: Partition Gazebo transport per side, explicitly and never by default

- **Status:** Accepted (corrected 2026-08-29) — **promoted 2026-08-29 by the change that
  implemented it**, on the
  condition this record set for itself: the partition is derived from the zone and the side
  name, emitted into the generated bring-up plan, and a side whose process environment does
  not carry it is refused at bring-up rather than warned about.
  **That last clause held for the launch graph only.** The scenario harness starts a second
  class of gz-transport process that was neither refused nor partitioned, and it failed
  silently; the decision and clauses 1 and 2 stand, the scope claimed for clause 3 did not,
  and both classes are covered now. See the section
  "Correction — 2026-08-29: the refusal was structural for the launch graph only, and a
  second class of Gazebo process was neither refused nor partitioned", below.
  **When written this record was `Proposed` and nothing was implemented**, and that sentence
  is kept rather than replaced: at `f1f914f` nothing in this repository set `GZ_PARTITION`,
  and a grep over the whole tree returned only the campaign's own harness and write-up.
  **What promotion does NOT claim.** Nothing has ever brought two sides up. The partitions
  the generator emits for a `pair` are untested against a running counterpart, because there
  is no counterpart launch yet; what is tested is that they are derived, that they differ,
  that a plan without them is refused, and that every Gazebo-transport process in the one
  launch that exists carries the one the plan names.
- **Date:** 2026-08-29
- **Deciders:** Docs-writer agent, on decision rule **D1** of
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  which was registered before the first trial and fired.
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0003](0003-gazebo-harmonic.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0009](0009-docker-primary-environment.md),
  [ADR-0032](0032-index-the-belt.md),
  [L1](../architecture/L1-description-and-assets.md),
  [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §8 and §10, charter §4 (P1, P2, P7)

## Correction — 2026-08-29: the refusal was structural for the launch graph only, and a second class of Gazebo process was neither refused nor partitioned

**What was wrong.** This record was promoted to `Accepted` on the condition, stated in its
own status line, that "a side whose process environment does not carry it is refused at
bring-up rather than warned about". Bring-up does refuse, and correctly — but **that
guarantee reaches only the processes the launch graph starts.** A second class of
gz-transport process exists and was outside it: the scenario harness starts its own. At the
moment of promotion `grep -rn GZ_PARTITION tests/` returned **zero hits**, and
`tests/scenarios/pick_and_place.py` and `tests/scenarios/continuous_line.py` between them
started seven Gazebo commands — two `ros2 run ros_gz_sim create` spawns, two `gz model -p`
pose reads, two `gz model --list` diagnostics and one `gz service` removal — every one of
them with a bare inherited environment. None was refused. None was partitioned. Each failed
silently, which is precisely the outcome this record exists to prevent.

**How it presented, and what was measured.** `pick_and_place` and `continuous_line` both hung
at their work-piece spawn: `subprocess.TimeoutExpired` on `ros2 run ros_gz_sim create` after
120 s, reproduced 3 runs of 3, with `pick_and_place` a blocking CI step. A controlled A/B
against one live cell, one variable, taken twice — by the tester who found it and again by
the fixer on `cb51c80` — settles the mechanism:

| Command, against a running cell | Result |
|---|---|
| `ros2 run ros_gz_sim create -file …` (no partition) | `TimeoutExpired`, 45 s, nothing spawned |
| the same, with `GZ_PARTITION=cite/cell_a/plant` | `Entity creation successful`, rc=0, 0.5 s |
| `gz model --list` (no partition) | `Service call to [/gazebo/worlds] timed out`, **rc=0** |
| the same, with the partition | the five models of the world, rc=0 |

Read the third row before the second. `gz model --list` **exits 0** having reached no world
at all. Had only the spawn been fixed, the scenarios would have stopped hanging and started
passing vacuously: the pose reads are how both of them verify that a work-piece physically
moved, and unpartitioned they answer nothing while reporting success.

**What survives, unchanged.** The decision. Option D is still the right one and every
argument for it stands: `ROS_DOMAIN_ID` does not isolate Gazebo transport, the container
hostname is an accident rather than a design, and a hand-typed partition is a value in two
places. Decision clauses 1 and 2 are also unchanged and were never in doubt — the partition
is derived from L0, emitted into the generated plan, checked by `./scripts/validate-model`,
and bring-up refuses a launch environment that does not carry it. **What was wrong was the
scope claimed for clause 3, not the decision.**

**What now covers the second class.** Two mechanisms, and they are deliberately different
kinds of structural, because the two paths can be held to different things:

- **One door.** `cite_bringup/cite_bringup/gz.py` is the single statement of what environment
  a Gazebo-transport process is given. `gz_environment` moved there out of
  `simulation.launch.py`, so the launch graph and the harness now ask the same function; the
  harness reaches it through `run(argv, zone=…, timeout=…)`, which derives the partition from
  the generated plan through `ids.partition`'s emitted value and never types one. Unit-tested
  in `cite_bringup/test/test_gz.py`.
- **A gate, not care.** `tests/scenarios/guards/test_gz_calls_carry_the_partition.py` parses
  every Python file under `tests/` and fails if any call passes an argument vector beginning
  with a Gazebo-transport command to anything other than that door. It reads the list of such
  commands out of `gz.py` rather than keeping a second copy, and it is mutation-checked
  against a crafted call that goes around the helper.

**The residual, stated rather than left to be found.** The two are not equally strong and
saying so is the point. The launch path refuses **at run time**, on the environment it is
about to hand over. The harness path is gated **at source-scan time**, and it cannot refuse
at run time, because a harness process has no bring-up to refuse it. An argv assembled at
run time, or a command passed as a shell string, is invisible to that scan; neither exists in
`tests/` today, and the guard counts the call sites it did find so that a rewrite into that
shape moves a number instead of producing silence. Two further paths are outside both
mechanisms and are named here so nobody re-derives them: the published campaign harnesses
under `docs/measurements/` run `gz topic -e` unpartitioned and, being records, are not
rewritten — anyone re-running one on this branch gets an empty stream; and the developer
running a Gazebo command by hand is served only by documentation, in this package's README
and in `docs/operations/troubleshooting.md`, exactly as this record's cost section said they
would have to be.

**Does it stay `Accepted`? Yes — argued against the promotion condition rather than assumed.**
The condition had three clauses; two were met at promotion and remain met, and the third was
met for one of the two classes of Gazebo process this repository starts. It is now met for
both, each with a test, which is what `Accepted` means here. Reverting to `Proposed` would
be the wrong record: it would say the derivation and the emission are unbuilt, and they are
built, committed and diffed on every `./scripts/validate-model`. Superseding would be wrong
for the reason `docs/adr/README.md` gives — the decision is not what turned out wrong, a
supporting claim about its reach was. What is not claimed, then or now: nothing has ever
brought two sides up.

**How the error survived, which is the part that transfers.** It was not overlooked. This
record's own cost section names it — "every path that starts or attaches to a Gazebo process
has to carry it — `scripts/sim`, `scripts/scenario`, the launch graph, and anything a
developer runs by hand" — and even says the campaign's harness had to set the partition on
every probe for that reason. The cost was written down, and then the promotion was taken
without checking that anything had paid it. **A cost section is not a checklist and was read
as though it were one.** What let it through is that the evidence offered for promotion was
the launch graph's own test — six processes, verified from `/proc/<pid>/environ`, every run —
and that test is exhaustive over the set it enumerates and silent about the set it does not.
A test that enumerates its subjects can only ever answer for the subjects it enumerates; the
question "what else starts one of these?" has to be asked of the tree, not of the test. It
now is, by a check that reads the tree.

## Context

### The failure, first: `ROS_DOMAIN_ID` does not isolate Gazebo transport

The campaign put **two `gz sim` servers in one container on separate ROS domains** and
counted publishers and subscribers on the world's own topics
(`ANALYSIS.md` §1, `raw/gz_crossing.json`):

| Condition | Publishers of `/world/cell_a/stats` | Subscribers of `/cite/cell_a/conveyor_1/command` |
|---|---|---|
| two servers, **one container**, no `GZ_PARTITION` | **2** | **2** |
| two servers, **two containers**, no `GZ_PARTITION` | 1 each | 1 each |
| two servers, one container, **distinct `GZ_PARTITION`** | 1 each | 1 each |

Read the first row in the terms it actually means. Two belt plugins subscribed to **one**
command topic, so **one `ConveyorIndex` setpoint would have started both cells' belts** —
with nothing logged, nothing raised, and nothing to see. And two publishers of one world's
statistics is the Gazebo-transport form of a defect this project already refuses by name on
the ROS side, where the campaign's Q1.3 requires exactly one `/clock` publisher per domain.

**The prediction was registered before the run, so confirming it is not hindsight.**
`criteria.md` §2 records that `ROS_DOMAIN_ID` is a DDS concept, that `gz sim` and the belt
and beam plugins speak Gazebo transport with its own discovery and its own partitioning, and
that nothing in this repository set `GZ_PARTITION`. It named Q1.4 as the question most likely
to fail and registered the follow-up in advance.

### Every instrument this project has reported isolation at the same moment

This is the part that makes it an ADR rather than a code comment. In the same paired runs:

- each side's ROS graph held **44 nodes and 93 topics**, identical to a solo cell, with zero
  foreign nodes and zero foreign topics (Q1.2, **PASS**);
- `ros2 topic info /clock --verbose` reported **exactly one publisher per domain** (Q1.3,
  **PASS**).

So the ROS graph was clean while the Gazebo transport was crossed. Everything this project
knows how to check said the two cells were separate, and the crossing was below all of it.

### What actually isolated the runs was the container hostname

gz-transport's default partition is `<HOSTNAME>:<USERNAME>` — the hostname of the machine and
the name of the user launching the node. Each container gets a distinct hostname and both ran
as the same user, so the hostname is the only term that differed, and **that is the entire
mechanism that kept the campaign's paired runs apart.**

> **Verified 2026-08-29, in two independent ways.** *Upstream:* the Gazebo Transport
> environment-variable reference states that the default value of `GZ_PARTITION` is
> "`<HOSTNAME>:<USERNAME>` where `<HOSTNAME>` is the hostname of the current machine and
> `<USERNAME>` is the name of the user launching the node" —
> <https://gazebosim.org/api/transport/13/envvars.html>. That is the right version of the
> reference: gz-transport **13** is the release in the Gazebo Harmonic collection, per the
> upstream version table at
> <https://github.com/gazebosim/docs/blob/master/tools/versions.md>. *Behavioural:* the
> campaign's two-container arm records `GZ_PARTITION=<unset>` alongside two distinct
> container hostnames and one publisher each
> (`raw/gz_containers_A.txt`, `raw/gz_containers_B.txt`).

That is not a design. It is undocumented in this repository, it is invisible at runtime, and
**it evaporates the moment the two sides share a container, a `--network host` namespace, or
a bare-metal host** — which is exactly what a single-machine Phase 2.A is
([ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)). Isolation that depends
on an unstated deployment accident is isolation nobody can rely on and nobody can review.

### The P2 stake, and why the check has to be structural

This is a class of defect in which the simulation and the real cell behave differently for a
reason that has nothing to do with either of them, and it fails silently. **On hardware there
is no partition to get wrong**: a physical belt is a drive on a fieldbus and there is no
gz-transport anywhere in the command path. So 2.A can carry a bug that 2.B cannot reproduce,
and a defect that exists on only one side of the sim/real boundary is precisely the one that
running both sides will never find.

The project has been here once already at the transport layer, on the same belt topic:
`CLAUDE.md` §10 records a belt setpoint that was never once delivered and stayed hidden for
ten commits because nothing in the system could observe whether it had been. The shape is
identical — a transport-level fact with no observer — and the response has to be a check that
runs whether or not anyone thinks to look.

## Options considered

### Option A — rely on `ROS_DOMAIN_ID`

The status quo assumption, and the one the repository's own scripts imply by setting a domain
per instance and nothing else. Rejected because it was **measured not to work**: the table
above is what two domains bought on the Gazebo transport, which is nothing.

### Option B — rely on separate containers

It is what kept the campaign's pairs apart, it works today, and it costs nothing to keep
doing. Rejected as a *decision*, though not as a fact: it is a property of one deployment,
stated nowhere, tested by nothing, and it fails silently the first time somebody runs both
sides in one container to watch them together — which is the most likely thing anyone
debugging a twin pair will do. Adopting it would mean writing down "do not ever share a
container" as a rule whose violation produces no error.

### Option C — give the counterpart different topic names

Rename the counterpart's world and its asset topics so the two sides cannot collide. Rejected
on P1 and P2 together. Topic and frame names are generated from the L0 model and are
identical in simulation and on hardware by rule (`CLAUDE.md` §8, ADR-0004); renaming one
side's topics to obtain isolation makes the two sides *not* interchangeable, which is the
defect this decision exists to prevent. It also fails on its own terms — it does not
namespace the world-control services, and it would make the counterpart's names differ from
the hardware's in 2.B.

### Option D — set `GZ_PARTITION` explicitly, per side

Chosen.

## Decision

**`GZ_PARTITION` is set explicitly for every side of a twin pair, derived rather than typed
by hand, and never defaulted. A side that comes up without one is a bring-up failure, not a
warning.**

Three parts, and all three are required for the decision to mean anything:

1. **Derived from the zone and the side name, and emitted into the generated bring-up
   plan.** Both terms are L0 facts under
   [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)'s Decision 3: the zone
   declares whether it runs `single` or as a `pair`, and the sides of a pair are named
   `plant` and `counterpart` — structurally, by which side the untwinned model already
   describes, and *not* by which side is being commanded. That last point is what makes the
   partition safe to derive: a name that moved with `TwinMode` would change the transport
   partition when an operator changed mode, which is the silent cross-talk this record
   exists to remove. A `pair` in zone `cell_a` therefore yields exactly two partitions, one
   per side, generated by the same mechanism that produces every other name in this system
   (`CLAUDE.md` §8, ADR-0004). A hand-typed partition is a value that exists in two places
   (P1) and is one typo away from re-creating the exact defect measured above, with the same
   silence.

   **Emitted, not computed at launch, and the choice is argued rather than assumed.** P5 puts
   mechanism in code and values in data, and a partition is a *name* — the same class as the
   node names, topic names and description paths the plan already carries. Emitting it means
   it is reviewable in a diff and is checked by `./scripts/validate-model`, which is how this
   project catches a generated name that drifted; computing it inside launch would put the
   rule in Python where nothing diffs it and no reviewer sees the result. The cost is stated:
   because a `single` zone still has one side, the plan gains a partition line even where
   nothing is twinned, so **the change that implements this lands a `cite_generated/` diff
   and a new `MODEL_HASH`** ([ADR-0021](0021-generated-artifacts-are-committed.md)). That is
   the right trade: a partition that appears only when someone pairs a cell would be untested
   on every run that does not.
2. **Never defaulted.** Bring-up **refuses** to start a side whose partition is unset, in the
   same place and the same manner as the hardware opt-in it already enforces —
   `cite_bringup/cite_bringup/plan.py::require_hardware_opt_in`, which refuses a plan naming
   a non-`sim` backend unless `CITE_ALLOW_HARDWARE=1` is set. A warning would be read once
   and then never again, and what it guards against produces no symptom.
   Because the generator emits the partition, the refusal is sharper than "a partition is
   unset": what bring-up checks is that **the environment of the process it is about to start
   carries the partition the plan names**. A stale generated tree is caught earlier, by
   `./scripts/validate-model`; this catches the launch path that dropped the value on its way
   into the process, which is the failure that actually happens.
3. **Structural, not conventional.** The refusal lives in code with a test, because the
   defect is invisible at runtime and because it cannot occur at all on the 2.B side, so no
   amount of running the real cell will surface it.
   **[Corrected 2026-08-29 — see the Correction section above.]**

**The cost was measured and is nil.** `PAIRGZ_1` brought both cells fully up with distinct
partitions at RTF **0.872** and **0.877**, against **0.863** and **0.869** for the same pair
without them — indistinguishable. This is a FUNCTIONAL result under the campaign's own
classification, which means it transfers completely: two processes either interfere or they
do not, and that does not depend on the speed of the machine.

## Consequences

### What this gets us

- **The isolation becomes a stated property with a name**, instead of an accident of the
  deployment that nobody wrote down.
- **Deployment freedom.** One container, two containers, a shared network namespace or bare
  metal all behave the same. That matters because the target machine is not this development
  host and the deployment has not been chosen.
  **[Corrected 2026-08-29 — see the Correction section above.]** True of the processes the
  launch graph starts. The scenario harness's own processes behaved the same everywhere for
  the opposite reason — they carried no partition anywhere — and reached the world nowhere.
- **A whole class of silent cross-talk removed before anything is built on top of it.** The
  campaign found it before there was a line to be confused by it; the same defect discovered
  during a `continuous_line` run would have presented as a belt that started for no reason.

### What this costs us

- **One more variable in the bring-up contract**, which is one more place to be wrong.
  Deriving it and refusing without it narrows that, but does not remove it.
- **Every path that starts or attaches to a Gazebo process has to carry it** — `scripts/sim`,
  `scripts/scenario`, the launch graph, and anything a developer runs by hand. Concretely: a
  developer who attaches `gz topic -e` to a running side without setting the matching
  partition will get an empty list rather than an error. **This decision makes a command that
  works today fail silently in the other direction**, and that is a real ergonomic cost, not
  a theoretical one. The campaign's own harness had to set the partition on every probe for
  exactly this reason. Whatever implements this owes the operator documentation a line about
  it.
- **A refusal at bring-up will stop someone's run on a machine where nothing was ever going
  to cross.** That is deliberate: the alternative is a rule that only binds when someone
  remembers it.

### What we will have to revisit

- **If one side ever needs more than one Gazebo server**, the derivation needs a third term
  and the "per side" wording stops being sufficient.
- **If upstream gz-transport changes its default partition.** The decision survives — an
  explicit value does not care what the default is — but the argument about the hostname
  accident would need re-checking against the version actually installed.
- **When 2.B lands, and the temptation is to delete this.** Do not. Charter §8's Phase 2
  states that the system runs correctly with one physical arm and two simulated ones, so a
  partially-twinned cell still runs a Gazebo server on the physical side as well as on the
  virtual one. The number of servers goes down, not to one.
- **When a side runs no Gazebo server at all, the refusal must not fire on it.** A fully
  hardware side — every asset on that side driven by a non-`sim` backend — starts no `gz sim`
  and no belt or beam plugin, so there is no gz-transport participant to partition and
  demanding a partition would refuse a correct configuration. The condition is on the side
  *starting a Gazebo server*, not on the side existing, and it is derivable from the same L0
  data the partition is: under ADR-0041's Decision 3 the plan already states each side's
  backend per asset. This case does not exist today and cannot be tested today, which is why
  it is a revisit rather than a clause of the Decision.
