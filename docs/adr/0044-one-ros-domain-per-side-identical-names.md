# ADR-0044: Give each side of a twin pair its own ROS domain, and keep both sides' names byte-identical

- **Status:** Proposed — **nothing in this record is implemented.** At `29068d4`:
  `ROS_DOMAIN_ID` is one value for the whole checkout, derived from the checkout path by
  `cite_domain_id` in [`scripts/_lib.sh`](../../scripts/_lib.sh) and handed to the container
  by [`infra/docker/docker-compose.yml`](../../infra/docker/docker-compose.yml).
  `grep -rn ROS_DOMAIN_ID scripts/ infra/ workspace/src/ tools/` returns **34 hits in 13
  files** in this checkout on 2026-08-29, and **not one of them gives a second side a second
  domain**: they are that derivation, its `doctor` check, its self-test, the value the
  scenario runner prints, and comments recording that the variable does **not** isolate Gazebo
  transport. The one place that sets a distinct domain is
  `cite_runtime/test/test_shutdown_under_signal.py`, which puts a test's own child process on
  a domain of its own — test isolation, not a side.
  The generated plan's `sides:` list carries a `gz_partition` per side and
  **no domain** (`workspace/src/cite_generated/bringup/cell_a_plan.yaml`); `model/facility/zones.yaml`
  declares `twin.sides: single`, so the list has one entry; `cite_bringup.gz.gz_environment`
  takes `plan.sides[0]` and says in its own docstring that "bringing a counterpart up is a
  separate launch and is not built yet"; and `cite_twin` does not exist.
  Every "will" and "must" below is a commitment, not a description.
  **Promoted to `Accepted` by the change that first brings two sides up on two domains under
  bring-up's own control, with a test that a side's processes carry the domain the plan
  resolves for them** (P7). Nothing weaker promotes it: this record's whole content is a claim
  about two graphs, and one graph cannot evidence it.
- **Date:** 2026-08-29
- **Deciders:** Project owner — that the two sides carry identical names and are separated by
  domain, argued from P2. The argument was checked rather than accepted (see *Context*), the
  rejected alternatives and everything under *What this record does not decide* are the
  docs-writer agent's, and the evidence is
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md).
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) (Decision 3,
  and the second-side emission bullet this record unblocks),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0011](0011-twin-maturity-model-and-modes.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md),
  [`qos-profiles.md`](../interfaces/qos-profiles.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §8 and §10, charter §4 (P1, P2, P5, P7) and §8

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

- **Q1.2, PASS.** 44 nodes and 93 topics in a solo cell; **44 and 93 on each side of every
  pair**, the only set differences being ROS's own address-suffixed names.
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

| Quantity | Value | What it rules out |
|---|---|---|
| `matched_at_start.pub_a_subscribers` | **2** | domain A's publisher matched its two domain-A subscribers and **not** the identically-named domain-B one |
| `matched_at_start.pub_b_subscribers` | **1** | likewise in the other direction |
| `published` / `crossed.n` / `same_domain.n` | **20000 / 20000 / 20000** | no message arrived twice, so nothing leaked around the relay |

Two publishers on one fully-qualified topic name, in one process and one network namespace,
did not see each other; 20,000 messages crossed only through the relay that was written to
carry them. **That is the decision, demonstrated: identical names, separated by domain,
spanned deliberately by one component.** It was built to price mirroring, not to test
isolation, which is why the isolation result is a by-product rather than a pre-registered
finding — and it is the reason this record cites the rig rather than the paired cells.

The rig also priced the span, and the figures belong to the campaign rather than here: read
§4.2 for the one-way latency across the boundary and the relay's own CPU cost. The one number
worth carrying into a design discussion is not a latency at all — it is
[ADR-0043](0043-hold-both-sides-to-the-wall-clock.md)'s finding that at the measured paired
real-time factor the clock deficit passes the p99 crossing latency within the first
twenty-three milliseconds of a run. **The domain boundary is not what will make mirroring
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

**If this refutation is ever itself refuted, stop.** The whole record rests on it: if someone
shows that a prefixed counterpart can become physical in 2.B without any consumer changing,
then Option A is cheaper than this decision and this decision should be withdrawn rather than
patched.

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

### Option D — one ROS domain per side, byte-identical names on both

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

**Two carve-outs, stated so they are not read as loopholes.**

- **A test harness is not part of the running system.** A scenario that asserts something about
  a pair has to observe both sides; that is legitimate, and it must go through **one stated
  door** the way every Gazebo call now does, so that the set of cross-domain observers is a
  list somebody can read rather than a grep nobody runs.
- **A recorder is not exempt, it is unresolved.** L6 records both sides' telemetry, which is a
  cross-domain observation by any reading of the rule above. Whether L6 records per side and
  merges later, or receives everything through L5, is **not decided here** — see *What this
  record does not decide*. Until it is, an L6 process holding two domains is a finding to raise
  rather than a pattern to copy.

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
facility. Committing an absolute domain number into `cite_generated/` would put one machine's
allocation into a tree that is committed and hashed (ADR-0021) and would undo the per-checkout
isolation `cite_domain_id` exists to provide — two checkouts of the same commit would generate
the same absolute domain and discover each other, which is the exact defect that comment
records as having cost a scenario run four times its runtime.

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
- **Bring-up refuses**, in the same manner and the same place as the partition: a side whose
  process environment does not carry the domain the plan resolves for it does not start.
  Symmetry with clause 2 is the requirement — one refusal covering both variables, so that
  carrying one and not the other is impossible rather than merely discouraged.

**The cost this creates, named because it is a new failure mode and nothing detects it.** A
checkout now claims **two consecutive domains instead of one**, which roughly doubles the
surface on which two checkouts on one host collide — and this checkout's counterpart can collide
with another checkout's plant, which is the more confusing direction because the intruder is on
the side that "should not be twinned". Two specific obligations follow for the implementing
change:

- **Both resolved values must stay inside the range upstream calls safe.** `cite_domain_id`
  currently returns 1 to 101; base 101 plus offset 1 is 102, which is outside the `0-101` band
  the ROS 2 documentation names for Linux (quoted in *Context*). The allocation has to be
  narrowed or wrapped, and that is a change to `scripts/_lib.sh`'s stated range.
- **`./scripts/doctor` reports one domain and would report only the plant's.** It should report
  every side the plan declares, or say plainly that it does not.

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
- **One `ros2 launch` process cannot drive both sides, so a paired bring-up is two launches.**
  This is not a preference and it is verified rather than assumed:
  > **Verified 2026-08-29 in upstream source, `jazzy` branch of <https://github.com/ros2/launch_ros>.**
  > `launch_ros/ros_adapters.py`'s `ROSAdapter.start()` creates **one** `rclpy.Context` and one
  > node — `rclpy.create_node('launch_ros_{}'.format(os.getpid()), context=self.__ros_context)`
  > — and `get_ros_adapter()` keeps one adapter per launch context.
  > `launch_ros/utilities/lifecycle_event_manager.py` calls `get_ros_node(context)` and creates
  > both the `transition_event` subscription and the `ChangeState` client **on that node**.

  This repository's bring-up is built on exactly that mechanism: `simulation.launch.py`'s
  `_managed()` drives every managed node through `EmitEvent(ChangeState)` and gates the next
  stage on `OnStateTransition`, which is what makes bring-up event-driven rather than timed
  (P4). A launch process therefore drives lifecycle nodes on **its own domain only**, and a
  second side needs its own launch process with its own `ROS_DOMAIN_ID`, sequenced by something
  above both. `gz.py`'s docstring already anticipates this — "bringing a counterpart up is a
  separate launch and is not built yet" — and this record is what makes that the decided shape
  rather than an implementation note. **What sequences the two launches, and how a failure on
  one side stops the other, is not decided here and must not be answered with a sleep.**
- **A cross-domain component sees two frame trees whose frame ids are identical.** That follows
  directly from clause 1: both sides broadcast `cell_a__conveyor_1__infeed` and
  `arm_1_link_base`. The two trees must therefore never be fed into one TF buffer — one buffer
  per side, keyed by side — and any cross-domain component that resolves a frame must say which
  side it meant. CLAUDE.md §10's "one publisher per transform" is not violated by the pair,
  because the two publishers are in two graphs; it *would* be violated the moment something
  merges them.
- **Two consecutive domains per checkout, with a new collision mode and no detector.** Stated in
  full under Decision clause 4, including the `101 + 1 = 102` edge and the two obligations it
  places on the implementing change.
- **Every place that assumes one domain has to learn about two** — `doctor`, `_lib.sh`, the
  compose environment, `./scripts/enter`, and any scenario that asserts across a pair. That is
  the ROS-side twin of the cost ADR-0042 paid on the Gazebo side, and ADR-0042's correction is
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
  ADR-0041's two, and `ids.SIDES` has two members; a third side needs the allocation rethought
  rather than extended, for the range reason in clause 4.

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
- **How L6 records a pair**, per clause 3's second carve-out.
