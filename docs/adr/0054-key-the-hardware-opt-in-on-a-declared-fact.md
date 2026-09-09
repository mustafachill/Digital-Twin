# ADR-0054: Key the hardware opt-in on a fact the model declares, not on a backend's name

- **Status:** Proposed — **nothing in this record is implemented.** Every "will", "must" and
  "may not" below is a commitment, not a description — **and so is every sentence written in
  the present indicative.** The *Decision* sections describe the tree this record asks for,
  not the tree that exists: "the plan carries the fact per (asset, side)" and "the gate reads
  the declaration" are commitments in the present tense, because that is how a specification
  reads, and a reader landing mid-document must not take them for readings. Only *Context*
  describes the tree, and every line of it names the command that produced it. Established in
  this checkout on 2026-09-09, at `404bbac` on `main` and at `5afc065` on
  `feat/hardware-params`, by the commands in *Context*:
  - A type may declare the vendor's **physical** `ros2_control` plugin under the backend id
    `sim`. The shipped validator returns **zero referential findings** on that model, the
    generator emits a description naming that plugin, and
    `cite_bringup.plan.require_hardware_opt_in` returns without refusing, never having
    consulted `CITE_ALLOW_HARDWARE`.
  - The same model on `feat/hardware-params` — the unmerged branch implementing
    [ADR-0053](0053-index-hardware-params-by-backend.md) — additionally carries a **working
    `robot_ip`** into that description. Before that branch, the address was dropped and the
    vendor component took its own `ros2_control_node` down at `on_init`. **The branch converts
    an accidentally fail-closed misconfiguration into a working, unguarded hardware path**,
    which is why this record is written now and not later.
  - Five sites decide something by comparing a backend id against the literal `sim`. One of
    them is L5's mode gate, which reports **no physical side commanded**, for every mode, on a
    zone whose every side loads the vendor's physical component.
  - `./scripts/doctor` reported `53 records, all indexed` before this record was written, so
    0054 was the next free number; it reports **54** with this record and its index row in.

  **Promoted to `Accepted`** by the change that implements decisions 1 to 4, with **all nine**
  of the clauses in *The promotion condition*, below. Every one of them runs with no
  simulator and no physical arm, which is deliberate: **there is no physical arm** (charter §8
  puts hardware in Phase 2.B) and a condition that needed one would never be met.
  **Promotion is not a claim that anything is safe** — see *What promotion does not claim*,
  which is a permanent clause and not a status caveat.
- **Date:** 2026-09-09
- **Deciders:** The project owner, who decided that L0 declares per backend whether that
  backend can reach a physical machine, that the field is required with no default, and that
  the bring-up refusal keys on the declaration rather than on the id. The five sub-decisions
  below — the field's name and type, what becomes of `ids.SIMULATION_BACKEND`, how the plan
  carries the fact, the migration, and what the fixture backends imply — were taken by the
  docs-writer agent that recorded this, which reproduced every fact in *Context* by running
  the command beside it.
  **It diverges from the commission on one point, and says so rather than writing a record
  that justifies it.** The commission's reading was that both rules turning on
  `ids.SIMULATION_BACKEND` inside `cite_tools` should read the new declaration, after which
  the constant may be deletable. **Decision 2 takes only one of them**, because `use_sim_time`
  asks a different question — *does this backend's controller manager take its clock from the
  simulator* — which coincides with *can this backend reach a physical machine* on exactly the
  two backends this repository declares, and diverges on the third kind the commission itself
  raises. Deriving the clock from the safety fact would transcribe a coincidence, which is the
  move this whole record exists to refuse. So the constant survives with one meaning, and
  decision 2 says what is still wrong with it.
- **Related:**
  [ADR-0053](0053-index-hardware-params-by-backend.md) (this record must land **before** that
  record's implementation merges; it does not reopen any of its decisions),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md) (the boundary that makes a one-line
  configuration change enough to point this code at a physical arm),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) (Decision 3 — a backend
  is selected per (asset, side), which is the grain decision 3 keeps),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) (clause 3's precedent —
  a value that is a total function of what the plan already carries is derived and not
  emitted; decision 3 says why this value is not one),
  [ADR-0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md) (decision 5 takes
  a position on what this field must **not** be allowed to express),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md) (`twin_boundary`'s `far_side_physical`,
  one of the five sites),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md) (the enforcement point,
  and lines 113-135 — *"apply the criterion; never transcribe the list"*),
  [L0](../architecture/L0-facility-model.md), [L2](../architecture/L2-control-and-hal.md),
  [L5](../architecture/L5-twin-synchronization.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §3 (P1, P2, P5, P7) and §10, charter §3.2 and §8

## Context

Every fact below was produced by the command beside it, run in this checkout on 2026-09-09.
Readings marked `main` are at `404bbac`; readings marked `branch` are at `5afc065` on
`feat/hardware-params`, which is unmerged. Nothing here is quoted from another record without
being re-established.

### The reproduction

**Method.** Copy `model/` to a scratch directory. In `assets/types/robots/xarm5.yaml`,
replace the `sim` backend's declaration with the vendor's physical one, leaving the id alone:

```yaml
  hardware_backends:
    sim:
      ros2_control_plugin: uf_robot_hardware/UFRobotSystemHardware
      instance_params: [robot_ip]
```

Give each of the three arms an address — `params: {robot_ip: 203.0.113.7}` and two more on
`main`, `params: {sim: {robot_ip: …}}` on the branch, which indexes `params` by backend
(ADR-0053 decision 1). Then run `cite_tools.model.loader.load`,
`cite_tools.validate.referential.check` and `cite_tools.generate.generate` on it, write the
artifacts to a directory, and call `cite_bringup.plan.load` and
`cite_bringup.plan.require_hardware_opt_in` on the generated plan with an **empty** environment
mapping. On `main` the whole of it runs in one interpreter inside `./scripts/enter dev`, with
`PYTHONPATH=/workspace/tools:/workspace/workspace/src/cite_bringup:/opt/ros/jazzy/lib/python3.12/site-packages`
and the repository venv's Python, because `cite_tools` needs `pydantic` and `cite_bringup`
needs `ament_index_python` and no single interpreter has both by default. The `branch` column
was taken on the host, in a `git worktree` at `5afc065`, with `.venv/bin/python` and
`PYTHONPATH` pointed at that worktree's `tools/`: it reaches no `cite_bringup` code, and the
row that does is measured once for both trees, immediately below.

| Question | `main` at `404bbac` | `branch` at `5afc065` |
|---|---|---|
| Referential findings | **0** | **0** |
| Artifacts generated | 34 | 34 |
| `ros2_control_plugin` in `description/cell_a_arm_1.urdf.xacro` | `uf_robot_hardware/UFRobotSystemHardware` | the same |
| Macro arguments emitted | 18 | **19** |
| `robot_ip` among them | **absent** | **`203.0.113.7`** |
| `bringup/cell_a_plan.yaml`, `arm_1` | `backend: sim` | `backend: sim` |
| `control/cell_a_arm_1_controllers.yaml` | `use_sim_time: true` | `use_sim_time: true` |
| `require_hardware_opt_in(plan, {})` | **returns `None`** | same function, byte-identical |

The last row is measured once and applies to both trees:
`git diff main..feat/hardware-params -- workspace/src/cite_bringup/cite_bringup/plan.py
tools/cite_tools/model/ids.py | wc -l` returns **0**, so neither the gate nor the constant it
compares against differs between them.

**So the branch is what closes the accident.** `main` drops the address, and
`uf_robot_system_hardware.cpp:64-73` (path from `find workspace/src/external -name
uf_robot_system_hardware.cpp`) reads `robot_ip`, takes `substr(1)`, finds it empty, logs
`No param named 'robot_ip'`, calls `rclcpp::shutdown()` and `exit(1)` at line 72. **That is
fail-closed by accident, not by design** — nothing in this repository asked for it, and it
fires on the machine standing next to the arm. The branch supplies the address, the vendor
component initialises, and the last barrier is gone.

**The `<param>` block is emitted exactly because the plugin string is the vendor's.**
`xarm5.ros2_control.xacro:16` guards it with
`<xacro:if value="${ros2_control_plugin == 'uf_robot_hardware/UFRobotSystemHardware'}">` and
line 20 emits `<param name="robot_ip">R${robot_ip}</param>` — the `R` the `substr(1)` above
strips. The guard turns on the **plugin**, so a physical plugin declared under any id gets the
physical parameter block.

**And the generated description carries the Gazebo system plugin regardless of backend.**
`tools/cite_tools/templates/description/arm.urdf.xacro.j2:50` emits
`<plugin filename="gz_ros2_control-system" …>` unconditionally; on the reproduction's own
generated description both are present —
`'filename="gz_ros2_control-system"' in text` is `True` and the `ros2_control_plugin`
argument is the vendor's. So `./scripts/sim` starts Gazebo, Gazebo loads
`gz_ros2_control`, and `gz_ros2_control` builds a controller manager from a
`<ros2_control>` block naming the physical hardware component.

### What the id decides, and what the id says

`tools/cite_tools/model/ids.py:28-29`, its own comment:

> The one backend id that cannot reach a physical machine. Every other value names a
> `ros2_control` plugin that drives real hardware.

`workspace/src/cite_bringup/cite_bringup/plan.py:35-41`, the intent the reproduction defeats:

> The one backend that cannot reach a physical machine. Every other value names a
> `ros2_control` plugin that drives real hardware, so the check below is an allowlist rather
> than a denylist: a backend nobody anticipated is refused rather than permitted.
> `cross-cutting-safety.md` requires that a hardware path is never reachable by omission, and
> a denylist is reachable by omission by construction.

**It is an allowlist over names, and a name says nothing about the plugin behind it.**
Nothing anywhere constrains what plugin an id may carry:
`grep -rn "gz_ros2_control\|GazeboSimSystem\|uf_robot_hardware" tools/cite_tools/` returns
seven lines, and **not one of them is in `validate/`** — one is the Gazebo plugin element in
`templates/description/arm.urdf.xacro.j2:50` and the other six are comments.

`grep -rn SIMULATION_BACKEND tools workspace/src --include=*.py` returns **22** lines and
`grep -rn SIMULATION_BACKEND tools/tests workspace/src/*/test --include=*.py` returns **0**,
so no test names the constant. **Five of the 22 decide something:**

| Site | What it decides |
|---|---|
| `tools/cite_tools/generate/control.py:236` | `use_sim_time` in the controller configuration |
| `tools/cite_tools/validate/referential.py:300` | `physical-plant-on-paired-zone` — a paired zone's plant must be `sim` |
| `workspace/src/cite_bringup/cite_bringup/plan.py:1145` | the bring-up refusal, `backend != SIMULATION_BACKEND` |
| `workspace/src/cite_twin/cite_twin/mode.py:242` | `physical_sides_commanded` — L5's mode gate |
| `workspace/src/cite_twin/cite_twin/twin_boundary.py:756` | `far_side_physical`, which feeds ADR-0050's divergence validity |

The remaining seventeen are three definitions, eight comment lines, four hint strings
(`referential.py:307`, `:313`, `:396` and `:402`), one import at `twin_boundary.py:106`, and
`Deployment.paired`'s construction of a plant side at `mode.py:176`. **The comment at
`ids.py:31` says "two rules turn on it"; that is true of `cite_tools` and is not the
repository-wide count**, and the same comment says so — *"`grep -rn SIMULATION_BACKEND` is
what says how many statements exist, not this comment"*.

### The gate the safety document holds up as the right shape returns the wrong answer

`cross-cutting-safety.md:113-135` records what transcribing a list cost this project: the
three-dangerous-transition list was copied into L5's mode server, `VALIDATED` was not on it, a
goal reached the physical arm, and *"a test asserted that acceptance and passed"*. Its
conclusion is **"Apply the criterion; never transcribe the list."**
`cite_twin.mode.physical_sides_commanded` is the in-tree answer, and its own docstring is
explicit that it *"does the intersection and knows nothing about which modes are dangerous"*.

**It computes rather than transcribes, and one of the two data it computes from is the id.**
Run inside `./scripts/enter dev`, on the deployment shape the reproduction generates — every
side stating the backend id `sim`, while that id names
`uf_robot_hardware/UFRobotSystemHardware`:

```
Deployment.paired({"arm_1": "sim", "arm_2": "sim", "arm_3": "sim"})
MODE_VIRTUAL_LEAD -> physical_sides_commanded = ()
MODE_VALIDATED    -> physical_sides_commanded = ()
MODE_SHADOW       -> physical_sides_commanded = ()
MODE_REAL         -> physical_sides_commanded = ()
```

**No mode is gated on a cell where both sides load the physical hardware component.** That is
the same outcome the safety document is a record of, reached by a different route: the shape
is right and the datum is wrong. A criterion applied to a name is still a name.

### The other direction, and it is not symmetrical

Declare the **simulation** plugin under the id `real` and select it — same method, `main`:

- referential findings: **0**;
- the description names `gz_ros2_control/GazeboSimSystem`;
- `control/cell_a_arm_1_controllers.yaml` says **`use_sim_time: false`**;
- the plan says `backend: real`, and `require_hardware_opt_in(plan, {})` **refuses** a cell
  that contains no physical machine, run end to end through the same door as the
  reproduction: `zone 'cell_a' declares a hardware backend for arm_1 (backend 'real'), arm_2
  (backend 'real'), arm_3 (backend 'real'), and CITE_ALLOW_HARDWARE is not set to 1.`

So the id decides three things and answers none of them. A false refusal is the cheap half;
`use_sim_time: false` on an arm driven by Gazebo is CLAUDE.md §10's *"a mixed-time system
produces plausible, wrong results"*, and the reproduction's own `use_sim_time: true` on a
**physical** arm is the same defect pointing at the machine.

### A paired zone is not refused either

Same method, `main`, with the physical plugin under `sim` and `model/facility/zones.yaml`
edited to `twin: {sides: pair}`: **0 referential findings**. `physical-plant-on-paired-zone`
compares the id and is satisfied; `divergent-counterpart-backend` does not fire because the
counterpart falls back to the plant's id. Both sides of the pair would load the vendor's
physical component with nothing refusing at any layer.

### What the gate covers, and what carries no backend at all

`grep -cn "backend: " workspace/src/cite_generated/bringup/cell_a_plan.yaml` returns **3**,
one per controller manager, at `:108`, `:251` and `:394`.
`require_hardware_opt_in` iterates `plan.controller_managers`, so the twelve non-arm assets,
which the plan carries under `conveyors:` (`:536`) and `sensors:` (`:564`) with no backend key,
are outside it. **That is pre-existing and this record does not change it**; it is stated
because a reader would otherwise take "the gate" for "the cell".

### What declares a backend at all

`grep -rl hardware_backends model/assets/types/` returns **one** file,
`model/assets/types/robots/xarm5.yaml`, with two entries, `sim` and `real`
(`:218-225` on `main`). **Repository-wide the answer is two models, not one**:
`grep -rln hardware_backends tools workspace/src --include=*.py --include=*.yaml
--include=*.json | grep -v /external/` also reaches
`tools/tests/fixtures/minimal/assets/types/xarm5.yaml:22-27`, which declares the same two ids,
and two committed schema exports, `model/schema/asset_type.schema.json:709` and
`tools/tests/fixtures/minimal/schema/asset_type.schema.json`. The fixture is copied by
`tools/tests/conftest.py:26` and `grep -rc minimal_model tools/tests/test_validate_referential.py`
returns **73**.

### Two facts about the surrounding machinery, both load-bearing for decisions 3 and 4

- `HardwareSelection.backend` (`tools/cite_tools/model/schema.py:1141-1150`) and
  `TwinSpec.sides` (`:1394-1398`) are both **required with no default**, each saying in its own
  comment that this is because `cross-cutting-safety.md` forbids a hardware path reachable by
  omission. `HardwareBackend` (`:403-421`) has two fields and neither is that fact.
- `cli.py:224` reads `if model_resolves and not schema_problems:` before running the
  committed-versus-fresh generated check, so **a stale schema export suppresses the check that
  would catch a regression** — the trap ADR-0053's review found in exactly such an owed-work
  list.

### Where the plan states a backend today

`bringup/cell_a_plan.yaml` states `backend:` per controller manager and, on a paired zone,
`counterpart_backend:`. `ControllerManager.backend_on(side)`
(`plan.py:384`) is *"the one place in `cite_bringup` that turns an (asset, side) into a
backend"*, and its own docstring records that it is **not yet the only reader**:
`cite_twin.twin_boundary` builds its own `{asset: {side: backend}}` map off the two fields,
*"and that map is what decides whether the injected hardware refusal runs at all"*.

## Options considered

### Option A — a `validate.referential` rule refusing a non-simulation plugin under the id `sim`

The minimal fix, and it lands with the ADR-0053 branch. The rule holds a set of plugin class
strings known to be simulations and errors when a backend named `sim` declares something
outside it.

**Rejected, and it is the same lesson twice.** The set is a transcribed list, and
`cross-cutting-safety.md:113-135` is this project's own record of what one cost: the list was
copied into L5's mode server, a transition nobody had put on it was accepted with no gate, and
a test asserted the acceptance and passed. That document's conclusion is *"APPLY THE
CRITERION; NEVER TRANSCRIBE THE LIST."*

Two further defects, either of which is disqualifying on its own. **It refuses the wrong
shape**: it inspects the id `sim`, so the physical plugin declared under any *other* friendly
id — `plant`, `cell_a_arm`, `virtual` — passes it untouched, and nothing says an id must be
`sim` to be treated as simulated. And **the list has no safe failure direction**: a simulation
plugin nobody anticipated is either refused, which breaks the day a second simulator is
adopted, or permitted, which is the denylist `plan.py:35-41` says is reachable by omission by
construction.

### Option B — key the gate on the plugin class string the plan carries

Emit `ros2_control_plugin` into the bring-up plan and let `require_hardware_opt_in` decide from
it. It removes the id from the safety path, which is the right half of the diagnosis.

**Rejected: it relocates the list one layer up.** Something must still decide which plugin
strings are simulations, and that decision is now inside `cite_bringup` instead of inside the
validator — a list in a different build unit, with the same two failure directions. It also
puts a vendor class string into an artifact that has no other use for one, and makes the
safety gate a parser of vendor identifiers; ADR-0005's boundary is that the plugin is the
*only* thing that differs, not that its name is a datum other layers reason about.

### Option C — declare the fact per backend in L0, required, with no default

The type declares, beside the plugin string it already authors, whether that plugin can reach a
physical machine. The generated plan carries the fact per (asset, side); every gate reads the
fact. **Chosen** — see *Decision*.

### Option D — declare the fact per instance, on `HardwareSelection`

The same field, written on each arm instead of on the type. It has one attraction: the arm is
where a person thinks about whether a machine is real.

**Rejected on P1.** The fact is a property of the plugin the type names, not of the instance:
three arms selecting the same backend would state it three times, and the model would then be
able to say that `arm_1`'s `sim` reaches hardware and `arm_2`'s does not while both load the
same plugin. Written on the backend it is stated once, one line from the plugin string it is
about, which is also where a reviewer reads the two together.

### Option E — a three-valued enumeration: simulation, physical machine, test fixture

Weighed seriously, because two things in this tree are neither the shipped simulator nor a
physical arm: `cite_test_hardware/JointStopSystem` (ADR-0040) and
`mock_components/GenericSystem`, which three `cite_bringup` launch tests substitute into a
description.

**Rejected on the record's own argument.** The question every gate asks is binary — *can this
reach a physical machine* — so a third value makes each consumer map three values onto two,
and that map is a list, in as many places as there are consumers. The distinction the third
value would carry belongs to a different mechanism: neither fixture is declarable in L0 at
all (decision 5), so there is no `hardware_backends` entry for either whose value could be
written. What would reopen this is in *What we will have to revisit*.

### Option F — do nothing, and rely on the vendor's `exit(1)`

`uf_robot_system_hardware.cpp:64-73` does take the node down when the address is empty, which
on `main` is what happens.

**Rejected: it is an accident and the ADR-0053 branch removes it.** It is not a property this
repository decided, tests, or may keep; it fires inside a loaded plugin, at bring-up, on the
machine beside the arm rather than at `./scripts/validate-model` on a laptop; and it exists
only for the UFACTORY component, so it says nothing about any other vendor.

## Decision

### 1. `HardwareBackend` declares whether the backend commands physical hardware

A new field on `HardwareBackend` (`tools/cite_tools/model/schema.py:403`), **required, with no
default**:

```yaml
  hardware_backends:
    sim:
      ros2_control_plugin: gz_ros2_control/GazeboSimSystem
      commands_physical_hardware: false
      instance_params: []
    real:
      ros2_control_plugin: uf_robot_hardware/UFRobotSystemHardware
      commands_physical_hardware: true
      instance_params: [robot_ip]
```

**Required with no default, for the reason `HardwareSelection.backend` and `TwinSpec.sides`
are** — both say it in their own comments, and `cross-cutting-safety.md` is explicit that a
hardware path must never be reachable by omission. A default of `false` would restore this
record's own defect with a shorter spelling; a default of `true` would refuse every model that
has not been migrated, which is a different way of not being answered.

**A boolean, not an enumeration**, for the reason option E gives.

**Named for the question the gate asks, not for the software.** `simulated:` describes the
implementation and forces every safety site to read a negation — `if not backend.simulated` —
which a reviewer has to invert before believing. `commands_physical_hardware:` is the sentence
the refusal already prints (*"Starting would command a physical machine"*), and the **dangerous
branch is the positive one**: every gate reads `if … commands_physical_hardware:` and the
value that must be written to reach an arm is `true`.

**It is a claim the model makes about itself, and nothing checks it.** A model may declare
`false` beside the vendor's physical plugin and this record does not catch it — see *What
promotion does not claim*. What changes is that the fact has a home: today there is nowhere in
L0 to state it truthfully at all, and a reviewer reading a backend declaration sees the plugin
and the claim one line apart.

### 2. The safety gates read the declaration; `use_sim_time` does not, and the constant survives

Four of the five sites in *Context* ask *can this reach a physical machine* and are moved onto
the declared fact:

1. `cite_bringup.plan.require_hardware_opt_in` — refuses on the declared fact, per (asset,
   side), whatever the id is called.
2. `validate.referential`'s `physical-plant-on-paired-zone` — a paired zone's plant must
   declare `commands_physical_hardware: false`. The rule's identity, its `where` and its hints
   change wording, not subject.
3. `cite_twin.mode.Deployment.physical_sides_commanded` — the intersection stays exactly as it
   is; the second datum becomes the declared fact rather than the id.
4. `cite_twin.twin_boundary`'s `far_side_physical` — the same substitution, on the map that
   decides whether the injected hardware refusal runs at all.

**The fifth is `use_sim_time`, and it stays on the id.** It asks *does this backend's
controller manager take its clock from the simulator*, which is a different question that
happens to have the same answer on the two backends this repository declares. A clock derived
from *can this reach a physical machine* is right for `gz_ros2_control` and for
`uf_robot_hardware`, and **wrong for any hardware component that is neither** — the third kind
option E weighs, which would be handed `use_sim_time: true` for no better reason than that it
is not a physical arm. **Transcribing a coincidence is the move this record refuses.**

**So `ids.SIMULATION_BACKEND` is not deleted, and this record says what it still means and
what is still wrong with it.** After this change it decides one thing: which controller
configuration says `use_sim_time: true`. **That one thing is decided by a name in exactly the
way this record's subject was** — *Context* measures `use_sim_time: false` on a Gazebo-driven
arm named `real` and `use_sim_time: true` on a physical arm named `sim`. It is left open
deliberately rather than closed by extension, because whether the clock is a per-backend fact
at all is unsettled:
`grep -c use_sim_time workspace/src/cite_bringup/launch/simulation.launch.py` returns **10**,
every one of them hardcoded `True` (the same grep filtered for lines without `True` returns
**0**), so the per-asset derivation is the only place the value varies, and it varies inside a
launch that asserts the opposite answer everywhere else. **Answering that needs its own
record**; this one requires only that the constant's comment stop asserting what *Context*
falsifies, and that a test pin the residual so no later reader believes it was closed.

`cite_bringup.plan.SIMULATION_BACKEND` and `cite_twin.mode.SIMULATION_BACKEND` — the second and
third statements, each deliberate and each explained in its own comment — have no consumer left
once 1, 3 and 4 above move, and go with them.

### 3. The plan carries the fact per (asset, side), emitted and not derived

Each controller manager gains, beside the backend keys it already states:

```yaml
    - asset: arm_1
      backend: sim
      commands_physical_hardware: false
      # on a paired zone, additionally:
      counterpart_backend: real
      counterpart_commands_physical_hardware: true
```

Consumers ask `ControllerManager.commands_physical_hardware_on(side)`, which is to this fact
what `backend_on(side)` is to the backend: **the one place an (asset, side) becomes the
answer**, refusing an undeclared side with the same `SideNotDeclaredError` for the same reason,
so the two accessors answer the same shape of question about the same grain. Reading the raw
keys is the value-in-two-places P1 forbids, and the field that stops being read is the one that
goes stale.

**Emitted rather than derived, and ADR-0048 clause 3's precedent is why the question had to be
asked.** That clause removed a plan key because it was a total function of a backend the plan
already states per side. **This one is not.** The mapping from a backend id to the fact lives
in the *type's* `hardware_backends`, which the plan does not carry, and it is per type rather
than per zone — two types may declare the same id with different answers, and nothing forbids
it. Deriving it at bring-up would mean emitting the whole backend table and each asset's type
into the plan: more emitted data, for the same fact, one indirection further from the consumer.

**Per (asset, side) and never per asset**, because that is the grain at which a backend is
selected (ADR-0041 Decision 3) and the grain `physical_sides_commanded` refuses to coarsen —
*"two assets answering 'simulated' is not an answer for the third"*.

### 4. Migration, and everything the change owes

- `model/assets/types/robots/xarm5.yaml` — both backends state the field. `MODEL_HASH` moves,
  because `model_hash` digests every type.
- `model/schema/asset_type.schema.json` — regenerated by `cite-model schema --write`, never by
  hand. **Named separately from the generated tree because `cli.py:224` skips the
  committed-versus-fresh check while the export is stale**, so a forgotten export does not
  fail; it *suppresses* the check that would have failed.
- `tools/tests/fixtures/minimal/assets/types/xarm5.yaml` — the second model that declares
  `hardware_backends`. Both of its backends state the field, or the 73 uses of `minimal_model`
  in `tools/tests/test_validate_referential.py` stop loading.
- `tools/tests/fixtures/minimal/schema/asset_type.schema.json` — the fixture's own committed
  export. **A survey of `tools/tests` on 2026-09-09 found no test that compares it**; the
  implementing change either regenerates it or establishes what reads it, and does not assume
  the survey is a proof that nothing does.
- `workspace/src/cite_generated/bringup/cell_a_plan.yaml` — gains one key per controller
  manager. **No description, world or controller configuration may move**: decision 2 leaves
  `use_sim_time` alone, and a diff that touches those artifacts is an implementation that
  rewired something this record did not decide.
- Test fixtures that build a plan or a type inline — `test_plan.py`, `test_pair.py`,
  `test_gz.py`, `test_simulation_launch.py`, `test_a_removed_plan_key_is_ignored.py` under
  `cite_bringup/test/`, and the `cite_twin` tests that construct a `Deployment`.

### 5. The fixture backends stay inexpressible, and this field may not be the door

`cite_test_hardware/JointStopSystem` is barred from production by ADR-0040, and the leg that
does it is `cite_test_hardware/test/test_unreachable.py`, which forbids the token
`cite_test_hardware` anywhere in `model/`. **So the fixture has no `hardware_backends` entry
whose field could carry a value, and this record must not give it one.** A third enumeration
value meaning "test fixture" would create a place in L0 where the fixture is nameable, which
is the leg ADR-0053 decision 4 records as the *surviving* one after that record weakens
`on_init`'s. Weakening it here, in a record whose subject is a hardware gate, would be the
worst possible place to do it.

`mock_components/GenericSystem` is not declared in L0 either: three `cite_bringup` launch tests
name it as their own constant and
`test_trajectory_constraints_launch.py:190` writes the `<hardware><plugin>` block itself. If it
ever were declared it would state `commands_physical_hardware: false`, and that answer would be
correct for every gate in decision 2 — **which is the point of a field named for the question
rather than for the software.**

## Consequences

### What this gets us

- **The refusal answers the question it claims to answer.** A physical backend is refused
  whatever it is called, and a simulated one is permitted whatever it is called. The
  reproduction in *Context* becomes a bring-up refusal instead of a Gazebo world driving a
  physical hardware component.
- **The ADR-0053 branch can merge.** It is held today because it completes a hardware path that
  nothing guards; with this in, the address it delivers arrives behind the opt-in.
- **L5's mode gate gets the datum its shape deserves.** `physical_sides_commanded` already
  applies a criterion instead of a list; it will apply it to a fact.
- **P5, concretely.** The model states what a backend *is*; the code decides what to do about
  it. Which backend is dangerous stops being knowledge encoded in a string literal in three
  build units.
- **The fact is reviewable where it is written.** `commands_physical_hardware: true` sits one
  line from the plugin string it describes, in the one file that authors plugin strings.

### What this costs us

- **A required field in L0, and a migration that cannot be partial.** Two model files, two
  schema exports, one generated plan, `MODEL_HASH`, and every test fixture that builds a type
  or a plan inline.
- **The model can lie, and nothing catches it.** This is the real price.
  `commands_physical_hardware: false` beside `uf_robot_hardware/UFRobotSystemHardware`
  validates, generates and starts.
  Catching it needs a list of plugin strings, which is option A, which is the thing this record
  refuses. What the change buys is not detection: it is that the fact is stated by the person
  who chose the plugin, in the place they chose it, rather than implied by an id nobody was
  asked about.
- **A plan key that is redundant on every model anyone has written.** Today one type declares
  backends and both answers are what the id already implied, so the emitted key adds nothing to
  the shipped cell. It earns itself only on the day the id and the fact disagree — which is the
  day this record is about.
- **The `use_sim_time` residual is left open, named, and pinned by a test.** Decision 2 chooses
  that deliberately, and it means the same defect class survives in one rule until a second
  record answers it.
- **Four consumers change at once, across three build units.** Two of the four are in
  `cite_twin`, which no launch file starts today (CLAUDE.md §2), so that half of the change is
  held by the package's own tests and by nothing else.

### What we will have to revisit

- **A backend that is neither the shipped simulator nor a physical arm being declared in L0.**
  That is the day option E's enumeration is worth re-weighing, and the day `use_sim_time`'s
  derivation from the id becomes wrong rather than coincidentally right. Whichever arrives
  first reopens decision 2.
- **The hardware launch shape.** `simulation.launch.py` hardcodes `use_sim_time: True` at
  ten sites; a launch that brings up a physical arm has to answer the clock question
  properly, and it will settle whether the clock is a per-backend fact at all.
- **The twelve assets that carry no backend into the plan.** Conveyors and sensors are outside
  the gate entirely. When an L1/L2 hardware driver exists for a belt, the gate's remit is a
  decision that has to be taken and is not taken here.
- **A false declaration being observed.** If one ever is, the cost of option A's list has to
  be re-weighed against the cost of an undetected false declaration — with the evidence in
  hand rather than in advance.
- **ADR-0053's `params` family under a lying declaration.** A backend declaring `false` while
  naming a physical plugin still receives its `instance_params`. Nothing here changes that, and
  it is the sharpest edge of the "the model can lie" cost.

## The promotion condition

Promoted to `Accepted` by the change that implements decisions 1 to 4, with **all nine** of the
following. **None of them needs a simulator or a physical arm**; the `cite_bringup` and
`cite_twin` clauses need a ROS environment for an import and bring nothing up, and the
`cite_tools` clauses run on the host.

1. **The field is required and unreachable by omission.** A `hardware_backends` entry omitting
   it fails to load, with the error naming the field and the backend. Asserted on a scratch
   type, not on the shipped one. **This is the clause every other clause rests on**: with a
   default, all eight below can pass while a backend becomes physical because a key was left
   out.
2. **The shipped model migrates and the exports are regenerated.** Both backends of
   `model/assets/types/robots/xarm5.yaml`, and both of the minimal fixture's, state the field;
   `./scripts/validate-model` exits 0; `model/schema/asset_type.schema.json` is produced by
   `cite-model schema --write` so that `export.differences` finds none. **Stated apart from
   clause 3 on purpose**, because `cli.py:224` makes a stale export suppress clause 3 rather
   than fail it.
3. **The generated tree moves in exactly two artifacts, and they are `MODEL_HASH` and
   `bringup/cell_a_plan.yaml`.** No description, no world, no controller configuration.
   Asserted as "exactly these two", not as "no unexpected file": this is the clause that
   catches an implementation that also rewired `use_sim_time`, which decision 2 forbids.
4. **`require_hardware_opt_in` keys on the fact and not on the name, in both directions.** On a
   plan built in the test: a manager whose backend is named `sim` and whose declared fact is
   physical is **refused** with `HardwareNotPermittedError` and permitted under
   `CITE_ALLOW_HARDWARE=1`; a manager whose backend is named `real`, or `plant`, or anything at
   all, and whose declared fact is not physical is **permitted with an empty environment**.
   Both sides asserted, and the refusal still names the asset and the plan field, so the
   message the existing tests assert against does not silently change shape.
5. **The reproduction in *Context* is refused end to end.** Build that scratch model with the
   field declared truthfully, generate it, load the plan, call `require_hardware_opt_in` with an
   empty mapping, and require `HardwareNotPermittedError`. **This is the clause that fails if
   any of decisions 1 to 3 lands partially**, because it is the only one that runs the whole
   path the defect ran.
6. **`physical-plant-on-paired-zone` reads the declaration.** A paired zone whose plant backend
   is named `sim` and declares physical is an ERROR, asserted **by rule name and `where`** and
   not by message substring; a paired zone whose plant is named anything at all and declares
   non-physical is not a finding of any severity. The rule keeps its name, so no other record's
   citation of it goes stale.
7. **L5's gate answers on the fact.** On the deployment *Context* measures — every side stating
   the id `sim` while that backend declares physical — `physical_sides_commanded` names at
   least one (asset, side) for every mode that commands the far side, where today it names
   none for any mode; and `twin_boundary`'s `far_side_physical` is true for that far side.
   Asserted directly on `Deployment`, with no ROS graph. **Without this clause the record's own
   headline finding stays unfixed**, and `cite_twin` is unreachable from any launch, so nothing
   else would notice.
8. **`ids.SIMULATION_BACKEND` survives with one meaning, and its comment stops asserting the
   falsified one.** `grep -rn SIMULATION_BACKEND tools workspace/src --include=*.py` reaches
   the definition in `cite_tools.model.ids`, the `use_sim_time` derivation at
   `generate/control.py:236`, and nothing else — the `cite_bringup.plan` and `cite_twin.mode`
   restatements are gone with their consumers. The surviving comment no longer says *"the one
   backend id that cannot reach a physical machine"*, and says instead what the id decides and
   what it does not.
9. **The `use_sim_time` residual is pinned rather than left implicit.** A test asserts that a
   backend declaring `commands_physical_hardware: true` under the id `sim` still generates
   `use_sim_time: true`, naming decision 2 as the reason. It is a **characterisation test of a
   known gap**, and it says so in its own docstring, so that a later reader meets the residual
   instead of inferring from the record's title that it was closed.

**The condition is deliberately not split by clause**, unlike ADR-0048's. One field, one plan
key and four consumers are satisfied or falsified by one change; there is no part of it that is
a commitment about a component nobody has. If only some of it lands, this record stays
`Proposed` and its status block names the clauses that were met — the failure ADR-0053's
clause 9 names, where a deliverable left outside the condition that governed it left
ADR-0048's clause-3 status wrong for eight days.

**What this condition deliberately does not require.** No clause asks that a false declaration
be detected, because option A is the only mechanism that would and it is rejected. No clause
asks for a scenario or a CI run: nothing in this record changes what a simulated cell does, and
a green `bringup` would be evidence about the cell that was.

## What promotion does not claim

Permanent. Not a status caveat, and not discharged by anything above.

- **That the declared fact is true.** L0 states it and nothing verifies it against the plugin
  string beside it. A model declaring `commands_physical_hardware: false` on the vendor's
  physical component passes every clause above and reaches an arm.
- **That this is a protective measure.** It is a **bring-up refusal**: it decides whether a
  process starts, once, and it is not a per-command check. It cannot stop an arm that is
  already moving, and it interposes nothing on any command path.
- **That charter §3.2 moves.** The risk assessment, the safety-rated controller, the physical
  guarding and certification against ISO 10218-1/-2 are outside this repository and are neither
  touched nor substituted by anything here. `cross-cutting-safety.md` says it in its own second
  paragraph: no amount of careful software substitutes for them.
- **That the gate covers the cell.** It covers assets with a controller manager. The twelve
  conveyor, sensor and fixture assets carry no backend into the plan at all, so a physical belt
  driver would be outside it — measured in *Context*, and not fixed here.
- **That any physical arm exists or has ever loaded anything.** None does (charter §8). Every
  clause above runs against generated text and in-memory objects.
- **That `use_sim_time` is right.** It still keys on the id, and *Context* measures it wrong in
  both directions. Clause 9 pins that; it does not fix it.
- **That a paired cell has been brought up this way.** `model/facility/zones.yaml` declares
  `twin: {sides: single}`, so the paired readings in *Context* are of a scratch model, and
  nothing paired ships.
