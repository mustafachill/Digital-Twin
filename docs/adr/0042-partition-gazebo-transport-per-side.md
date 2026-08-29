# ADR-0042: Partition Gazebo transport per side, explicitly and never by default

- **Status:** Proposed — **nothing implemented.** At `f1f914f` nothing in this repository
  sets `GZ_PARTITION`: a grep over the whole tree returns only the campaign's own harness
  and write-up. Promoted to `Accepted` by the change that derives a partition per side and
  makes a missing one a bring-up failure (P7).
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

1. **Derived.** The partition is computed from facts bring-up already holds — the zone and
   the side's role at the twin boundary — by the same mechanism that produces every other
   name in this system (`CLAUDE.md` §8, ADR-0004). A hand-typed partition is a value that
   exists in two places (P1) and is one typo away from re-creating the exact defect measured
   above, with the same silence.
2. **Never defaulted.** Bring-up **refuses** to start a side whose partition is unset, in the
   same place and the same manner as the hardware opt-in it already enforces —
   `cite_bringup/cite_bringup/plan.py::require_hardware_opt_in`, which refuses a plan naming
   a non-`sim` backend unless `CITE_ALLOW_HARDWARE=1` is set. A warning would be read once
   and then never again, and what it guards against produces no symptom.
3. **Structural, not conventional.** The refusal lives in code with a test, because the
   defect is invisible at runtime and because it cannot occur at all on the 2.B side, so no
   amount of running the real cell will surface it.

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
