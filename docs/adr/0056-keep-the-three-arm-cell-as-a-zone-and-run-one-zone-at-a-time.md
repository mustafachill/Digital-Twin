# ADR-0056: Keep the three-arm cell as a second zone, and run one zone at a time

- **Status:** **Proposed — implemented, and all eight promotion clauses now have evidence
  behind them. Promotion is the project owner's, and this record does not take it**, for the
  reason clause 4's evidence gives below: the cycle is met as worded and it took two attempts
  per scenario to get there.
  **Clause 5 is met and it is the one this record said was most likely to be skipped.**
  `./scripts/sim --headless --zone cell_a` brought the three-arm showcase up — nine controllers
  active, one `move_group` and one skill server per arm, `zones=['cell_a']` — on 2026-09-17.
  Adding a second zone did not break the first.
  **Clause 4 is met as worded and the wording is narrower than it reads.** All three scenarios
  passed their cycle against `cell_b`: `bringup` 2 of 2 (both zones, under the *strict* policy,
  so cycle and post-shutdown teardown both), `pick_and_place` 1 of 2, `continuous_line` 2 of 2
  carrying 3 of 3 work-pieces with zero escalations in both. **Two of those four runs failed on
  the first attempt**, on two defects this branch did not create: the `frame_server` stall
  (`docs/open-work.md`, and it reached `pick_and_place` for the first time here) and a teardown
  in which `skill_server` and `move_group` failed to terminate 105 s after `SIGTERM` and were
  `SIGKILL`ed. Neither was absorbed by an exemption; the `-9` was reported, as the exemption's
  `-11`-only allowance requires.
  **What that evidence is not.** One or two runs per scenario on one host, with nothing
  registered in advance. It is a demonstration that the cell works, not a reliability figure,
  and **no CI run has driven `cell_b`** — the branch is unpushed.
  It said *"nothing in this record is implemented"* until 2026-09-17, which was true when it was
  written and had stopped being true by the time three reviewers found it independently.
- **Date:** 2026-09-16
- **Deciders:** Project owner; drafted by the orchestrator against a three-pass source audit
  of this checkout at `2b135b3`.
- **Related:** [ADR-0001](0001-rebuild-rather-than-migrate.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0020](0020-facility-model-conventions.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md),
  [ADR-0039](0039-report-a-station-that-cannot-be-triggered.md),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md);
  `docs/architecture/naming-and-namespaces.md` rule 6; charter §8.

## Context

### The scope change that forces the decision

Phase 1 closed on 2026-08-28 with a three-arm serial transfer cell, `cell_a`. The question
that cell existed to answer — whether this architecture drives a multi-robot line end to end
from one declarative model — **is answered.** The project owner has decided on 2026-09-16 that
the next work is narrower: **one arm, one conveyor**, driven first as a single cell and later
as a twin pair, with a physical arm eventually replacing one side.

The owner has also decided that `cell_a` **is kept**, as a showcase that still comes up on
demand. It is not deleted, and it is not the thing anyone works on. That is the requirement
this record answers: *where does a cell live when it is finished?*

### What the tree already does with zones, verified rather than assumed

Every claim here was read in this checkout.

- `tools/cite_tools/model/loader.py:88` globs every `*.yaml` under `model/` except
  `model/schema/`, and routes each document by its own `schema:` key. Content may live in new
  files; layout carries no meaning.
- `zones:` is a list (`model/facility/zones.yaml:7`), `zones.extend(...)` at `loader.py:147`
  accepts more than one document, and `resolve(model, zone_id)` (`resolve.py:376`) resolves
  **one** zone, filtering assets by `model.assets_in(zone_id)` (`:383`) and stations by
  `s.zone == zone_id` (`:471`).
- `generate/__init__.py:82` loops `for zone in model.zones:` and emits the **complete**
  artifact set per zone — description, world, control, moveit, planning scene, frames,
  topology, bring-up. Every path is zone-prefixed inside one of the seven directories
  `generate/package.py:20` installs, and the CMake template installs **directories**, so a
  second zone's artifacts install with **no change to the package** and `package.xml` is
  byte-identical.
- `cli.py:209` runs the geometric level once per zone. `referential.py` and `physical.py` are
  model-global and multi-zone-correct by construction.
- Asset types are global: `resolve.py:496` hands every type to every zone, so a second zone
  adds no type.
- **`model_hash` digests every zone** (`generate/__init__.py:50-61`), so a second zone moves
  `MODEL_HASH` and nothing else that `cell_a` owns.
- In production, the zone is already a **parameter**, and `cell_a` is only its default:
  `plan.py:1586`, `simulation.launch.py:157`, `pair.py:621`, `twin_boundary.py:1122`,
  `frame_server.py:45`, `topology_server.py:69`, `planning_scene_loader.py:77`, and
  `model_info.py:43`, which takes a `zones` **list** and is already multi-zone in shape. Five
  modules already require it with no default at all — `cite_bringup/gz.py`,
  `readiness_witness.py`, `skill_server.cpp`, `detection_server.cpp`, and `plan.py` past line
  1586 — and they are the pattern the rest should follow.

**No two-zone model has ever been generated.** `./scripts/validate-model` reports `1 zone(s)`
in this checkout. So the above is *the code is shaped for it*, not *it works*, and this record
must not be read as reporting a working state.

### What collides if two zones run at the same time

Also verified, and this is the constraint that shapes the decision rather than a defect list.

`/cite/facility/`, `/cite/line/` and `/cite/twin/` are **facility-scope reserved names by
design** — `docs/architecture/naming-and-namespaces.md:117-124`, and `ids.RESERVED_SCOPES`
(`ids.py:64`) refuses any zone or asset called `facility`, `twin` or `line`. They are
deliberately not zone-scoped. Meanwhile `ROS_DOMAIN_ID` is derived per **checkout × side** and
never per zone: `scripts/_lib.sh:118-123` hashes the checkout path into one odd base, and
`ids.domain_offset(side)` (`ids.py:174-210`) takes **only** a side, returning 0 or 1. Its own
docstring argues at length that the offset is a function of nothing but the side.

So two zones launched from one checkout share one ROS graph, and collide at:

- duplicate `/cite/facility/{frame_server,model_info,topology_server}` node names, and two
  servers on the fixed service `/cite/facility/get_model_version` (`model_info.py:36`);
- two latched publishers on `/cite/line/topology`, after which
  `line_orchestrator.cpp:408-414` **`RCLCPP_FATAL`s** on a zone mismatch — a hard,
  race-dependent bring-up failure;
- `/cite/line/state` and the node `/cite/line/line_orchestrator`;
- two `parameter_bridge`es on one `/clock` (`simulation.launch.py:391`, whose own comment says
  *"every zone has exactly one clock"*);
- two scene publishers on `/robot_description` (`simulation.launch.py:503-518`);
- `/cite/twin/mode` and `/cite/twin/divergence`, if two L5 boundaries ever ran.

**Gazebo transport does not collide.** `ids.partition(zone, side)` → `cite/<zone>/<side>`
(`ids.py:145-171`) carries the zone, so two zones' simulators are already isolated and nothing
here reopens ADR-0042.

### What a one-arm line can be

The minimum runnable line is **three stations**, and this is enforced, not stylistic:
`line_plan.hpp:332-342` requires every transfer station to have **exactly one** upstream and
**exactly one** downstream; `line_plan.hpp:457-459` refuses a topology with no transfer
station; `schema.py:1631` requires at least one flow edge; `referential.py:804` refuses a
self-edge. With one arm there is only one possible actor, so the two remaining slots must be a
source and a sink.

Two further facts about that shape, both verified:

- **ADR-0031's direct-handoff refusal is structurally unreachable in a one-arm zone.**
  `line_plan.hpp:441-443` computes `receiver_is_a_robot` as *not a sink and has an actor*, and
  a source or sink may not have an actor at all (`:276-279`). There is no second robot to
  receive.
- **An inbound edge with `via: null` makes ADR-0039's detector structurally silent.**
  `line_nodes.hpp:265-291` returns `nullopt` immediately when the inbound belt is empty, so a
  table-fed station has no belt setpoint to read. This is the blind spot ADR-0039 records at
  `station_transfer_1` today, and in a one-arm table-fed cell it is the **whole** of the cell's
  belt-side stall coverage; what remains is ADR-0046's custody rule
  (`line_nodes.hpp:340-350`).

## Options considered

### Option A — delete `cell_a`

The cheapest. Rejected by the owner: the three-arm cell is the demonstration that the
architecture works, and it is wanted on demand.

### Option B — copy `cell_a` into a subdirectory of the repository

The literal request as first stated. Rejected on three independent grounds. It is what
`legacy/` was, which ADR-0001 and CLAUDE.md §1 record as a mistake whose patterns *"are not
precedent"*. It creates a second L0 model and a second generated tree, which is the value in
two places CLAUDE.md §4 prohibits outright. And it is unnecessary: the cell is not a
directory, it is a few dozen lines of YAML, and `./scripts/validate-model` proves the
committed tree is reproducible from them byte for byte.

### Option C — a git tag or branch as the showcase

Better than B, and genuinely tempting: zero cost today. Rejected because **it rots**. A tagged
commit receives no fix that lands on `main` — not a hull re-derivation, not a tolerance
change, not a container-image bump — so the showcase drifts away from the platform until one
day it does not come up, and nobody finds out until they try to show it. It also cannot be
covered by `validate-model` or `build` on `main`, so its decay is invisible.

### Option D — a second zone, with both zones able to run concurrently

The most capable answer, and it is what the name tree would have to become eventually for a
multi-cell facility (charter §8 puts multi-zone work in Phase 3). Rejected **for now**, on
cost against need: it requires renaming or per-zone namespacing the three reserved
facility scopes — which `naming-and-namespaces.md:107-108` says *"changes every name in the
system"* and needs its own ADR — plus a redesign of domain allocation, a decision about
`/clock`, and per-zone facility services. Four ADR-sized changes, for a capability nobody has
asked for: the showcase and the working cell are never wanted at the same moment.

### Option E — a second zone, one zone up at a time

Chosen.

## Decision

**1. `cell_a` stays in the L0 model as a zone.** It is not deleted, not copied and not moved.
It is generated by the same generator from the same model, so every fix that lands on `main`
reaches it, and `./scripts/validate-model` and `./scripts/build` keep covering it.

**2. A second zone `cell_b` is declared: one arm, one conveyor, three stations** — a source
station at a table, one transfer station whose actor is the arm, and a sink station the belt
feeds. The arm picks from the table and places on the conveyor infeed. No asset type is added.

**3. A zone is addressed by name, and exactly one zone is up at a time.** The three reserved
facility scopes stay singular and unchanged. This record **declines**, explicitly and with the
reason recorded, the four changes Option D would require: reserved-scope namespacing, a
per-zone domain allocation, `/clock` namespacing, and per-zone facility services. Declining
them is the decision; discovering them later would not have been.

**What enforces clause 3, and what it does not catch.** `model_info.on_configure`
asks the ROS graph's own name list which *other declared* zone has names on it,
and returns `FAILURE` with a diagnosis naming that zone;
`simulation.launch.py` already turns a configure failure into a `Shutdown`
carrying the node's own message, so this is the existing refusal route rather
than a new one. The set of zone names comes from the generated bring-up plans,
so a third zone is covered without an edit. It is a **graph-cache query and
nothing waits**, which makes it sound and **incomplete** in two stated ways:

- **The discovery race.** DDS discovery is asynchronous, so a zone started at the
  same instant may not be in the cache yet and will not be seen. Concluding "I am
  alone" from an absence needs a timeout, and a bring-up that waits a guessed
  interval to decide is the timing guess CLAUDE.md P4 forbids. Refusing on a
  positive is an event; refusing on an absence is not.
- **The same zone twice.** Two `cell_b` bring-ups collide identically and this
  says nothing about them. Deliberately: CI brings one zone up twice per run, and
  a rule that could not tell an unfinished teardown from a second cell would turn
  a lingering process into a hard bring-up failure.

It **refuses a bring-up**. It is not a protective measure, it cannot stop a cell
that is already running, and it moves no robot. Both residuals are filed in
`docs/open-work.md`. Until this existed the invariant was enforced by nothing:
exactly one of the collisions listed above was loud, and only with `line:=true`.

**4. `default_plan_path`'s zone parameter becomes required** (`plan.py:1586`). It is the root
of every silent `cell_a`, and making it required turns each remaining default into a visible
call site rather than a behaviour nobody chose.

**5. CI drives `cell_b`.** `cell_a` keeps `validate-model` and `build` coverage and stops being
driven by the three simulation-in-the-loop scenarios. This is the project owner's decision of
2026-09-16 and it is a deliberate reduction in regression coverage, recorded as such below.

## Consequences

### What this gets us

- **A showcase that does not rot.** The three-arm cell stays byte-reproducible from L0 and
  keeps receiving platform fixes, which is the property Option C cannot have.
- **Scope reduction without losing evidence.** The fifteen campaigns in `docs/measurements/`
  and the CI history stand whatever the model declares; they are records of runs, not of the
  current model.
- **The scope-down is a data change.** No package is added, `package.xml` does not move, and
  the only generated artifact `cell_a` owns that changes is `MODEL_HASH`.
- **Pairing `cell_b` later keeps two filed defects dormant.** `docs/open-work.md` #62 and #63
  both concern fixtures that append a counterpart to the live plan; every one of them reads
  `cell_a_plan.yaml` by literal name. Pairing `cell_a` would trip both immediately; pairing
  `cell_b` does not. This was not previously written down anywhere.
- **Four ADR-sized changes are declined on the record**, rather than being met one at a time by
  whoever next tries to run two cells.

### What this costs us

- **`cell_a` loses its scenario regression coverage.** Three scenarios stop running against
  it. A regression that breaks the three-arm cell but not the one-arm cell will not be caught
  by CI, and will be found by whoever next launches the showcase. This is the owner's explicit
  choice and it is a real cost, not a formality.
- **The two cells cannot be demonstrated side by side.** A visitor sees one or the other.
- **ADR-0039 is structurally silent at `cell_b`'s only acting station**, because its inbound
  edge is `via: null`. The cell's belt-side stall coverage is therefore zero and its custody
  coverage is ADR-0046's. Accepted deliberately; the alternative shape — feeding the arm *from*
  the belt — would keep ADR-0039 live at the cost of making three geometric indexing rules
  live too, and it is not the flow the owner chose.

  **What that costs in motion terms, which is the only form of it worth reading.**
  A `DetectAt` failure sits *above* `TakeCustody` in the shipped station tree, so
  ADR-0046's custody refusal does not cover it: the station retries, re-enters
  `AwaitTrigger` on a beam the part is **already breaking**, and waits. Because
  the inbound edge has no belt, `untriggerable_reason` returns `nullopt` at its
  first test and nothing is reported; `LineState` reads `RUNNING` with
  `blocked_reason=none`. In `cell_a` a stall at one station eventually shows as
  the *next* station starving, which is a second symptom a reader can notice.
  **With one arm there is no next station**, so there is no second symptom at
  all: the line sits, healthy by every published signal, until the 420 s leg
  ceiling ends the scenario. This is the dead end ADR-0038 records, at the only
  station the cell has.

- **Four belt- and handoff-side paths become code no running cell executes.** Not
  a test-count observation — a statement about which motions the cell can
  produce. `cell_b` has one belt, which runs continuously and is never indexed or
  stopped, and one arm, which hands off to a sink rather than to a receiver. So:
  `ConveyorIndex::index_on`/`on_edge` — stopping a moving belt at a pick point on
  a beam edge — never runs; `ConveyorIndex::run()` after the initial `run_all()`
  — the belt restart at `CompleteHandoff` (ADR-0032) — never runs;
  `CompleteHandoff` never transfers ownership to a **receiving robot**, because
  there is no second robot (the same structural fact that makes ADR-0031's
  refusal unreachable here); and `untriggerable_reason`'s belt branch never
  evaluates at an acting station, per the item above. All four keep their unit
  tests, and those tests drive **fake action servers that move no arm** — which
  is the whole of the difference between "covered" and "exercised". A regression
  in any of them reaches nothing CI runs until a cell with a belt-fed station or
  a second robot is driven again.
- **Two validator gaps are exposed and not closed.** Nothing compares two zones' AABBs, and
  `_no_overlapping_bodies` only ever sees one zone's assets, so a `cell_b` placed inside
  `cell_a`'s box produces zero findings. And `referential.py:686` and `:786` check station and
  flow references against **globally** known ids, so a `cell_b` station naming a `cell_a`
  actor passes referential validation and then *silently* skips its reach check
  (`geometric.py:241`). Both are filed in `docs/open-work.md` rather than fixed: a guard
  written against the one case we control is weaker than placing the cell correctly and
  recording why.
- **A zone with no flow document generates nothing, silently** (`generate/topology.py:35-37`),
  and its `unreachable-station` check never runs. `cell_b` must ship a flow document; this is
  the likeliest way it would validate clean while being non-functional.
- **Two scenarios must be parameterised, not edited.** `bringup.py:44` and
  `pick_and_place.py:43-51` name assets and frames directly. `continuous_line.py` does not —
  it derives its whole milestone ladder from the generated topology — and needs one line.

### What we will have to revisit

- **When two zones must run concurrently.** Option D's four changes come back in full, and
  `naming-and-namespaces.md:107` requires an ADR for the first of them.
- **When a second zone is paired.** `ids.domain_offset` is a function of the side alone, so
  two paired zones in one checkout resolve to the same two domains. Nothing in ADR-0044,
  `_lib.sh`, `ids.py` or `plan.py` contemplates that, and the band is 1..101 with 50 odd bases.
  Under this record's decision 3 the case does not arise, and if decision 3 is ever lifted it
  arises immediately.
- **When Phase 3's multi-zone facility work begins.** This record is a narrow answer sized to
  two zones and one of them idle; it is not the multi-cell design.
- **If the showcase is found broken after a platform change.** That is the cost above coming
  due, and the answer is either a cheap periodic `bringup` against `cell_a` or accepting the
  cost knowingly — not widening anything.

## The promotion condition

This record moves to `Accepted` when all of the following hold, each by the named instrument.

1. `./scripts/validate-model` exits 0 and reports **2 zones**, in a clean checkout.
2. The same command's byte-identity and second-interpreter checks pass, and **every `cell_a`
   artifact that moves against `main` is accounted for by a deliberate change to the generator
   or its templates, with regeneration proving it produced the diff.** A `cell_a` diff nobody
   intended — an ordering dependency, a mapping that acquired an entry, a path that resolved
   differently — is a defect in this change and not an acceptable diff.

   **Reworded 2026-09-17, with the deviation that forced it recorded rather than explained
   away.** The clause said `git status` after regeneration must name **`MODEL_HASH` and
   `cell_b_*` artifacts only — no `cell_a_*` artifact moves**, and four do:
   `cell_a_arm_{1,2,3}.urdf.xacro` and `cell_a_scene.urdf.xacro`, **fourteen lines, all of them
   inside XML comments and none of them structural**. They are produced by `c22d087`, which
   stopped the description templates asserting a three-arm cell — "With all three arms in one
   model, all three managers claimed all eighteen joints", "joint reaction torques from three
   arms". Those sentences were false for any zone that is not `cell_a` the moment a second zone
   was generated from the same templates, so correcting them is the work this record asks for
   and the clause as written could only have been satisfied by leaving a generated comment
   lying. What makes them generator-produced rather than hand-edited (ADR-0021) is that
   `./scripts/validate-model` regenerates the tree and re-runs the generator in a second
   interpreter under a different hash seed, and the output is byte-identical both times.

   **The previous fix round on `feat/cell-b-zone` reported "no `cell_a_*` artifact moved", which
   is wrong as stated.** The reviewer that found it is the reason this clause is reworded
   instead of being quietly treated as met.
3. `./scripts/build` still reports 23 packages, with no edit to `generate/package.py`, the
   CMake template or `package.xml`.
4. `./scripts/sim --headless --zone cell_b` brings the cell up, and
   `./scripts/scenario bringup`, `pick_and_place` and `continuous_line` each pass their cycle
   against it.
5. **`./scripts/sim --headless --zone cell_a` still brings the showcase up.** This is the
   clause the whole record turns on and the one most likely to be skipped.
6. `default_plan_path` has no default zone, and no module reaches a plan without naming a zone.
7. A test fails if `cell_b`'s flow document is removed — the silent-no-topology trap above is
   pinned rather than described.
8. `docs/open-work.md` carries the zone-AABB gap and the cross-zone-reference gap, each with
   the command that reproduces it.

## What this record does not decide

- **The pair.** `cell_b` is declared `single`. Flipping it to `pair` is a separate change with
  its own record, and it inherits an open question this record does not answer: **nothing
  starts L5.** `twin_boundary.py` appears in no launch file, no script and no generated plan
  slot, so a pair comes up with no boundary and a dispatched goal has no server. A plan slot
  would be a new generated key and therefore ADR-0021 territory.
- **Whether `MODE_VIRTUAL_LEAD` is the right mode for the demonstration.** It dispatches to both
  sides (`routing.py:181`) and produces **no divergence number by its own definition**
  (`routing.py:270-283` makes `observed_sides` empty, because the mode *is* the absence of a
  reverse flow). `VALIDATED` is the mode that observes both sides. Whichever is chosen, 2.A
  produces no fidelity number at all (charter §8).
- **Phase 2.B.** ADR-0048 clause 1 refuses any asset whose two sides declare different
  backends until clause 2 is built, so `cell_b`'s arm must name one backend on both sides. That
  rule is what makes hardware a later change and not this one.
- **Anything about the charter.** `what-we-are-doing.md` §8 currently scopes Phase 2.A as *"a
  complete second simulation of the same three-arm cell"* and states *"the cell stays
  three-armed"*. A one-arm cell paired instead contradicts that sentence. The charter is
  protected (CLAUDE.md §12): the amendment is the project owner's, with a version bump and a
  §14 entry, and this record does not make it.
