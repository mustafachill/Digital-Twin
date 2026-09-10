# ADR-0054: Key the hardware opt-in on a fact the model declares, not on a backend's name

- **Status:** Proposed (corrected 2026-09-10) — **decisions 1 to 4 are implemented**, and this
  record is **NOT promoted**, for one reason stated in full below.
  **The correction does not withdraw any decision and does not touch the promotion condition.**
  It corrects the **size of the residual** this record states in three places: the gate is
  defeated not only by a false declaration in L0 but by an **omitted binding**, with the
  declaration honest — nothing verifies that the plugin L0 declares is the plugin the
  description loads. It is pre-existing, this record did not create it, and it is filed rather
  than fixed. See the section "Correction — 2026-09-10: the residual is not confined to a false
  declaration, and an omitted binding reaches an arm with L0 telling the truth", immediately
  after this block. Nothing in the *Decision* sections is
  a commitment any more; what remains a commitment is clause 10's own wording. Every other
  sentence in this record still describes the tree it asked for, and *Context* still describes
  the tree as it was on 2026-09-09 at `404bbac`, which is what makes it readable as the
  reproduction rather than as a current reading.
  - A type may no longer declare the vendor's **physical** `ros2_control` plugin under the
    backend id `sim` and pass every gate. `HardwareBackend.commands_physical_hardware` is
    required with no default, the generated plan carries it per (asset, side), and
    `cite_bringup.plan.require_hardware_opt_in`, `validate.referential`'s
    `physical-plant-on-paired-zone`, `cite_twin.mode.Deployment.physical_sides_commanded` and
    `cite_twin.twin_boundary`'s `far_side_physical` all decide on it. The reproduction is
    refused end to end.
  - `ids.SIMULATION_BACKEND` survives, deciding `use_sim_time` and nothing else, with its
    comment corrected and the residual pinned by two characterisation tests.
  - **Ten of the eleven clauses in *The promotion condition* are met in full.** The eleventh,
    clause 10, is met in substance and **its literal wording cannot be met by any
    implementation**, which is a defect in the clause rather than in the change — see below.

  **Clauses met, each by the test named.** 1 —
  `tools/tests/test_declared_hardware_fact.py`, two tests on a scratch type, the error naming
  the field and the backend. 2 — both models state the field, `./scripts/validate-model`
  exits 0, `model/schema/asset_type.schema.json` regenerated through `cite-model
  schema --write`. 3 — the generated tree moves in exactly `MODEL_HASH` and
  `bringup/cell_a_plan.yaml`; no description, world or controller configuration moves.
  4, 5 — `cite_bringup/test/test_plan.py`, both directions of the gate and both plan keys
  refused when omitted. 6 —
  `cite_bringup/test/test_the_reproduction_is_refused.py`, which edits L0, generates through
  the shipped generator, loads the plan and calls the gate with an empty environment. **It
  lives in `cite_bringup` rather than in `tools/tests` because the clause's own preamble
  splits in a way this path does not**: it needs `cite_tools` (pydantic) *and* `cite_bringup`
  (`ament_index_python`) in one interpreter, and `./scripts/test`'s host half clears
  `PYTHONPATH` deliberately, so a `tools/tests` home would have made the one end-to-end
  hardware-gate assertion skip in every run. The generator half is driven through the
  repository virtualenv in a subprocess; the L0-to-artifact leg is asserted separately and
  without ROS in `tools/tests/test_declared_hardware_fact.py`, and a guard compares the two
  halves' model builders so they cannot drift.
  7 — `tools/tests/test_validate_referential.py`, by rule id and `where`; the `where` moved to
  `types.<type>.hardware_backends.<id>.commands_physical_hardware`, which is decision 2 item
  2's expected move, decided rather than inherited. 8 —
  `cite_twin/test/test_l5_gate_reads_the_declared_fact.py`, all three assertions, none
  constructing a node. 9 — a guard in `test_declared_hardware_fact.py` that carries its own
  falsification test. 11 — `tools/tests/test_use_sim_time_still_keys_on_the_id.py`.

  **WHY CLAUSE 10 IS NOT MET AS WRITTEN, AND WHY IT COULD NEVER HAVE BEEN.** The clause asks
  that `grep -rn SIMULATION_BACKEND tools workspace/src --include=*.py` reach the definition
  in `cite_tools.model.ids`, the `use_sim_time` derivation at `generate/control.py:236`, *"and
  nothing else"*. After the change it reaches **four lines in three files**: those two, and
  `validate/referential.py`'s hint inside `_counterpart_backend_matches_the_plant`, which
  restates the `use_sim_time` derivation in a message — `f"use_sim_time: {'true' if plant ==
  ids.SIMULATION_BACKEND else 'false'}"`. **That line is one of the four hint strings this
  record's own *Context* counted among the seventeen non-deciding lines**, and no decision here
  asks for it to go; `tools/tests/test_validate_referential.py` asserts on the substring it
  produces. So "and nothing else" contradicts the inventory in the same record, and the only
  arrangements that satisfy it either delete a tested message or route both derivations
  through one helper — at which point `generate/control.py` stops naming the constant and the
  clause's other half goes stale instead. **The implementing change did neither**, on the
  ground that a record's clause is corrected by its owner and not worked around by the
  implementer.

  **What clause 10 asked for in substance is met**, and is separately checkable: the
  `cite_bringup.plan` and `cite_twin.mode` restatements are gone with their consumers, and the
  surviving comment no longer says *"the one backend id that cannot reach a physical machine"*
  — it says what the id decides, that the same defect class survives in that one rule, and
  what would close it.

  **The decision this leaves open is one line**, and it is the project owner's: either restate
  clause 10 so that it names the two DECIDING sites and the two removed restatements rather
  than the raw grep — the route [ADR-0049](0049-measure-the-real-time-floor-as-capacity.md)
  and [ADR-0051](0051-restate-the-hull-grasp-gate.md) both took with a clause that could not
  be met as worded — or decide that the hint string is a second statement of a generator rule
  and should be routed through one helper, which is its own change and reopens nothing here.
  **Promotion is not a claim that anything is safe** — see *What promotion does not claim*,
  which is a permanent clause and not a status caveat, and which is already true of the
  implemented tree.

  **One factual correction to decision 2, found in the code.** That section warns that
  migrating `twin_boundary` with the refusing accessor *"makes `TwinBoundary.__init__` raise
  on the shipped model"*. **It would not**: `__init__` resolves both sides through `address()`
  before it builds any map, and `Plan.side_named` already refuses a counterpart the shipped
  single-sided plan does not declare, so the node never reaches the map on that model. The
  conclusion is unchanged and the total sibling accessor is still required — clause 8's own
  second bullet calls `deployment_from_plan` on that same shipped plan with no node, and a
  refusing accessor makes *that* raise. The masking is pinned by
  `test_the_boundary_refuses_the_shipped_plan_at_side_resolution`.

  **And one to decision 4's migration list.** It names
  `tools/tests/fixtures/minimal/schema/asset_type.schema.json` and offers two branches — the
  change *"either regenerates it or establishes what reads it"*. **The second branch was
  taken, and what it established is that no test and no script reads it.**
  `cite_tools.model.loader` prunes any path with a `schema` component from its walk, and
  `export.differences` is called only on `model/schema` by the CLI, which no test invokes with
  the fixture. **This passage said *"nothing can read it"* until 2026-09-09, and that is
  false**: `cite-model schema --model tools/tests/fixtures/minimal` is a shipped, read-only
  command, and it opens every one of those exports and reports on them. A claim about what
  nothing *can* do is a claim with an expiry date; what is measured is what nothing *does*.
  **Five of the fixture's six committed exports are stale, and were already stale on `main`**
  — `git ls-tree -r --name-only <ref> tools/tests/fixtures/minimal/schema/ | wc -l` reads
  **6** at `main` and at this branch's tip, and that read-only `cite-model schema` command
  reports **5** `error` lines at each; only `flow.schema.json` matches a fresh export. The
  record said *"four of five"* and both halves were wrong. Regenerating
  `asset_type.schema.json` alone produces a **591**-line diff at this branch's tip and
  **584** at `main` (`git diff --no-index --numstat <committed> <fresh>`, +578 −13 and
  +572 −12), **of which seven are this change's** — the same command over a fresh export at
  `main` against one at this tip reads +6 −1, and 584 + 7 = 591. The record said *ten*.
  Bringing that drift into a safety change would have obscured it; the fixture's exports are
  left untouched and the staleness is recorded in [`../open-work.md`](../open-work.md).

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
  move this whole record exists to refuse. **The third kind is not hypothetical: it is in this
  checkout twice**, as `mock_components/GenericSystem` — which four launch rigs load and which
  three of them want on `use_sim_time: false` while the fourth wants it `true` — and as the
  vendor's `UFRobotFakeSystemHardware`, which nothing forbids naming in `model/`. Decision 2
  measures both. So the constant survives with one meaning, and decision 2 says what is still
  wrong with it.
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

## Correction — 2026-09-10: the residual is not confined to a false declaration, and an omitted binding reaches an arm with L0 telling the truth

**This is the first correction on this record.** The decision stands in full and nothing in
the *Decision* sections is withdrawn: the field is still required with no default, the plan
still carries it per (asset, side), and the four gates still decide on it. What is corrected
is the size of the residual this record states in three places, which is larger than every
one of them says.

### What was written

Three sentences, all bounding the residual to a **false statement in L0**.

Decision 1 says *"It is a claim the model makes about itself, and nothing checks it. A model
may declare `false` beside the vendor's physical plugin and this record does not catch it"*,
and closes: *"a reviewer reading a backend declaration sees the plugin and the claim one line
apart."* *What this costs us* says *"The model can lie, and nothing catches it. **This is the
real price.**"* *What promotion does not claim* says *"L0 states it and nothing verifies it
against the plugin string beside it."*

Read together they say the gate is defeated only by someone writing a value that is untrue,
in the one place a reviewer is looking. Every one of those sentences is true on its own. The
framing they share is false.

### What is true

**Nothing verifies that the plugin L0 declares is the plugin the description loads.** The
declaration can be entirely honest and the arm still physical, because the binding that
carries the declared plugin string into the generated description is itself unguarded.

`model/assets/types/robots/xarm5.yaml` binds the vendor macro's `ros2_control_plugin`
parameter in `bound_args`, on one line. Delete that line — a plausible edit while re-working
bindings, and one no rule anywhere refuses — and:

| Fact | Instrument, run in this checkout on 2026-09-10 | Result |
|---|---|---|
| no validator reads `bound_args` at all | `grep -rn bound_args tools/cite_tools/validate/ \| wc -l` | **0** |
| the model still validates | `cite-model validate --write` | exit 0, `ok model valid — 1 zone(s), 7 type(s), 15 asset(s), 5 station(s), across 15 file(s)` |
| `--strict` does not change that answer | `cite-model validate --strict` | exit 0, the same line, no finding |
| the generated description passes no such argument | `grep -n ros2_control_plugin workspace/src/cite_generated/description/cell_a_arm_1.urdf.xacro` | **no match** — the `<xacro:xarm_device …/>` call carries **17** arguments where the committed one carries 18, and this is the one it loses |
| so the vendor's own default applies | `xarm_description/urdf/xarm_device_macro.xacro:14` and `urdf/xarm5/xarm5.ros2_control.xacro:5`, both `ros2_control_plugin:='uf_robot_hardware/UFRobotSystemHardware'`, emitted at `xarm5.ros2_control.xacro:15` as `<plugin>${ros2_control_plugin}</plugin>` | the **physical** component |
| and L0 and the plan are still honest | `model/…/xarm5.yaml` still reads `ros2_control_plugin: gz_ros2_control/GazeboSimSystem` beside `commands_physical_hardware: false`; `cell_a_plan.yaml` carries `commands_physical_hardware: false` on all three arms | the gate returns without ever consulting `CITE_ALLOW_HARDWARE` |

So the route this record closed — a physical plugin declared under the id `sim` — is closed,
and a second route of the same shape is open beside it, reached by **omission** rather than
by assertion. `cross-cutting-safety.md`'s requirement that a hardware path is never reachable
by omission is met at the L0 field (clause 1) and at the plan key (clause 5), and is **not**
met at the binding, which no clause of this record ever looked at.

**It is pre-existing and this record did not create it.** The binding line is present at
`404bbac`, and `bound_args` had zero validator readers there too; the change this record
specifies strictly narrows the neighbouring hazard and widens nothing. It does not block the
promotion of anything, and it was not fixed here.

### What survives

Everything the decision commits to. Decision 1's field, decision 2's split, decision 3's plan
key and decision 4's migration are unaffected, and the reproduction in *Context* is still
refused end to end. What changes is that this record may no longer be cited for the
proposition that the declaration is the only way in. *What promotion does not claim* gains a
bullet naming the second route; the three sentences above are left where they stand, marked.

**The structural fix is not taken here**, because it is an owner-facing choice between two
shapes and neither is free. It is filed as item **#65** in [`../open-work.md`](../open-work.md),
scoped to *What we will have to revisit*'s **hardware launch shape** bullet and to be settled
before any hardware launch exists — which is the last moment at which no deployment depends
on the answer. The two candidate shapes are recorded there and neither is chosen.

### How the error survived

**The record audited the value and never the path the value travels.** Every clause of *The
promotion condition* asserts on what L0 states, on what the plan carries, or on how a gate
branches; clause 3 even asserts that **no description moves**, which is exactly the artifact
in which this defect appears. A condition that is satisfied by a description not changing
cannot notice a description that is wrong.

**And the reassurance was structural-sounding rather than measured.** *"One line from the
plugin string it is about"* is an argument about where a reviewer's eye lands, and it was
written as though it bounded the failure. It does not: the plugin string a reviewer reads in
`hardware_backends` and the plugin string the description loads are two different quantities
that this repository connects by a single unguarded binding, 160 lines away in the same file.
The generator was trusted to carry a declared value because it does carry it, and nothing
asked what happens when it is not asked to.

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
**seven** lines, of which **one is emitted and six are prose**. The emitted one is the Gazebo
plugin element in `templates/description/arm.urdf.xacro.j2:50`. **One of the six comments is in
`validate/`** — `validate/physical.py:967`, inside `_followers_can_still_correct`, saying that
dartsim implements no mimic constraint so `gz_ros2_control` substitutes a proportional servo.
It bounds a gripper follower joint's headroom and says nothing about which plugin a backend id
may name. So the claim this grep supports is not that `validate/` never mentions a plugin
string; it is that **no rule anywhere reads the plugin string a backend declares**, which the
grep shows by what is absent from it rather than by where its hits are.

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

`cross-cutting-safety.md:124-146` records what transcribing a list cost this project: the
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

**And the two layers fail together rather than independently, which is why decision 2 has to
move both.** L5 does not carry its own refusal:
`twin_boundary.py:299` injects `partial(require_hardware_opt_in, plan, environ)` into
`ModeAuthority`, and `mode.ModeAuthority._require_hardware_opt_in` (`:392-394`) calls exactly
that.
So the reproduction defeats the **bring-up** gate and the **transition** gate in one move — both
key on the same name, one of them by calling the other. A reader could otherwise take the two
as independent barriers and conclude that one surviving would catch the other's miss; neither
survives, and moving only one would leave a gate whose refusal is decided by the id it was
supposed to stop trusting.

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

`grep -c "backend: " workspace/src/cite_generated/bringup/cell_a_plan.yaml` returns **3**,
one per controller manager, at `:108`, `:251` and `:394`.
`require_hardware_opt_in` iterates `plan.controller_managers`, so **the twelve non-arm assets
are outside it, and they are outside it in two different ways.** `cite_tools.model.loader.load`
on `model/` returns **15** assets, three of them arms. **Seven** of the other twelve reach the
plan with no backend key — three under `conveyors:` (`:536`, assets at `:537`, `:541`, `:545`)
and four under `sensors:` (`:564`, assets at `:565`, `:573`, `:581`, `:589`). The remaining
**five** — `pedestal_1`, `pedestal_2`, `pedestal_3`, `table_accumulation` and `table_pick` —
**are absent from the plan document entirely**, so there is nothing for a gate iterating the
plan to skip. Derived on 2026-09-09 by differencing the loader's asset ids against the ids the
plan states. **That is pre-existing and this record does not change it**; it is stated because
a reader would otherwise take "the gate" for "the cell", and because the second way is the
stronger one — a future belt gate cannot be written as "also iterate the conveyors" without
first deciding what to do about five assets the plan never mentions.

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
`cross-cutting-safety.md:124-146` is this project's own record of what one cost: the list was
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
`mock_components/GenericSystem`, which **four** `cite_bringup` launch tests substitute into a
description — `test_abort_classification_launch.py:120`, `test_gripper_deadline_launch.py:130`
and `test_grasp_predicate_launch.py:108` name it as their own constant, and
`test_trajectory_constraints_launch.py:190` writes the `<hardware><plugin>` block itself
(`grep -rn "mock_components/GenericSystem" workspace/src/cite_bringup/test/`, 2026-09-09).

**Rejected on the record's own argument.** The question every gate asks is binary — *can this
reach a physical machine* — so a third value makes each consumer map three values onto two,
and that map is a list, in as many places as there are consumers.

**And the direction of that map is a per-consumer choice, which is the sharper half of the
cost.** A consumer with three values writes either `value is PHYSICAL` or
`value is not SIMULATION`, and the two agree on every value anyone has anticipated and
**disagree exactly on the one nobody has**: a fourth value added later is dangerous under the
first spelling and safe under the second. The first is a denylist reachable by omission, which
`plan.py:35-41` already rejects by name — *"a backend nobody anticipated is refused rather than
permitted"*. So an enumeration does not merely multiply the mapping; it makes each site's
failure direction an independent decision that nothing in the type system records, at exactly
the sites where the safe direction matters most. A boolean has one spelling and one direction.

The distinction the third value would carry also belongs to a different mechanism: neither
fixture is declarable in L0 at all (decision 5), so there is no `hardware_backends` entry for
either whose value could be written. **The asymmetry there is the reason the enum is worse than
neutral**: the vendor's own fake system, `uf_robot_hardware/UFRobotFakeSystemHardware`, **is**
nameable in L0 and nothing forbids it, while `cite_test_hardware` is refused by a token guard —
so the third kind arrives without an enum anyway, and an enum only adds a spelling for the one
kind ADR-0040 keeps unnameable. What would reopen this is in *What we will have to revisit*.

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
**[Corrected 2026-09-10 — see the Correction section above. The plugin string a reviewer reads
here and the plugin string the description loads are two quantities, joined by one unguarded
binding; the claim being true is not sufficient.]**

### 2. The safety gates read the declaration; `use_sim_time` does not, and the constant survives

Four of the five sites in *Context* ask *can this reach a physical machine* and are moved onto
the declared fact:

1. `cite_bringup.plan.require_hardware_opt_in` — refuses on the declared fact, per (asset,
   side), whatever the id is called.
2. `validate.referential`'s `physical-plant-on-paired-zone` — a paired zone's plant must
   declare `commands_physical_hardware: false`. **The rule id
   `physical-plant-on-paired-zone` is unchanged**, so no other record's citation of it goes
   stale; only its message and its hints are reworded. **Its `where` is expected to move**, and
   that is deliberate rather than incidental: it is
   `assets.<id>.hardware.backend` today (`referential.py:305`), and after this change the cause
   is no longer the id the asset selected but the declaration on the type's backend, so the
   `where` should point at the type's `hardware_backends` entry. Clause 7 asserts on `where`, so
   the implementing change decides it explicitly rather than inheriting the old string.
3. `cite_twin.mode.Deployment.physical_sides_commanded` — the intersection stays exactly as it
   is; the second datum becomes the declared fact rather than the id.
4. `cite_twin.twin_boundary`'s `far_side_physical` — the same question, on the map that decides
   whether the injected hardware refusal runs at all. **It is not a substitution of one
   expression for another**, and the two paragraphs below are the reason: 3 and 4 both read a
   map whose absent entries carry meaning, and a migration that drops that meaning passes every
   behavioural assertion in *The promotion condition* while retiring a refusal.

**`Deployment`'s map stays three-valued, and collapsing it is a silent safety regression.**
`Deployment.backend` returns `str | None` and `None` means *this asset has no such side*;
`assets_without_a_far_side` tests exactly that (`mode.py:214-217`), and that is what drives the
`PRECONDITION_FAILED` refusal of a two-sided mode on a one-sided deployment
(`mode.py:344-362`). A map carrying a bare `bool` per (asset, side) makes every unpaired asset
look like it *has* a far side that is merely simulated, and **that refusal stops firing** —
on the shipped single-sided model, which is every deployment this repository can generate today
(`model/facility/zones.yaml` declares `sides: single`). So the migrated map carries
`bool | None`, with `None` still meaning "no such side", and every existing `is None` test keeps
its meaning.

**And `twin_boundary`'s map may not simply call the refusing accessor.** It builds two maps
straight off the raw fields — `_far_side_backends` at `twin_boundary.py:282-285` and the
`Deployment` at `:288-297` — and `manager.counterpart_backend` is `None` on an unpaired zone,
which the shipped plan is.
`commands_physical_hardware_on(side)` refuses an undeclared side with `SideNotDeclaredError`
(decision 3), so a literal substitution makes **`TwinBoundary.__init__` raise on the shipped
model**, and **no existing test would catch it**: both launch tests fabricate a paired plan
before constructing the node (`test_twin_boundary_launch.py`,
`test_twin_boundary_paired_launch.py`). `backend_on`'s own docstring already priced this —
*"Whoever migrates it adds a total sibling accessor or accepts that cost knowingly"* — and it
is quoted here because it is the instruction, not a remark. The implementing change therefore
either adds a **total** sibling accessor returning `bool | None`, or wraps each (asset, side) in
`try/except SideNotDeclaredError` the way `require_hardware_opt_in` already does at
`plan.py:1141-1144`, and says in the code which it chose and why. **And it builds that map
somewhere callable without a node**, because the failure this paragraph is about is an exception
raised *inside* `__init__`, which no test needing a working `__init__` can reach; clause 8
asserts it there.

**One thing is deliberately lost, and it is named rather than allowed to happen quietly.**
`physical_sides_commanded` returns `f"{asset} ({side} {backend!r})"`, and that string is the
`SAFETY_BLOCKED` diagnostic at `mode.py:392-405`. Once the decision is made on a boolean, the
backend id is no longer the datum the criterion used, and **printing it would be printing the
value the record just removed from the safety path**. The load-bearing half is the (asset,
side), which clause 8 requires the message to keep naming; the id may be carried alongside as
context or dropped, and the implementing change states which. What it may not do is leave the
message reading as though the id had decided anything.

**The fifth is `use_sim_time`, and it stays on the id.** It asks *does this backend's
controller manager take its clock from the simulator*, which is a different question that
happens to have the same answer on the two backends this repository declares. A clock derived
from *can this reach a physical machine* is right for `gz_ros2_control` and for
`uf_robot_hardware`, and **wrong for any hardware component that is neither**.
**Transcribing a coincidence is the move this record refuses.**

**The third kind is not hypothetical, and this is what makes the refusal an argument rather
than a preference. It is in this checkout twice** — both readings taken on 2026-09-09:

- **`mock_components/GenericSystem`, in four `cite_bringup` launch rigs, and the four do not
  agree with each other about the clock.** Three override the generated `use_sim_time: true`
  back to `False` and say in a comment why —
  `test_trajectory_constraints_launch.py:219-225`, `test_abort_classification_launch.py:320-327`
  and `test_grasp_predicate_launch.py:328-334`. The fourth,
  `test_gripper_deadline_launch.py:275-280`, loads **the same** hardware component and keeps
  `use_sim_time: true` deliberately, because it measures a deadline that must follow a `/clock`
  its own test process publishes; its comment says *"Here that is not an override at all — it is
  the setting the rig wants"*. **One hardware component, four rigs, two different right
  answers.** So the clock is demonstrably not a function of the hardware component even inside
  this repository, and a field about physical reachability could not carry it.
- **`uf_robot_hardware/UFRobotFakeSystemHardware`**, exported beside the physical component by
  the pinned vendor library
  (`workspace/src/external/xarm_ros2/xarm_controller/uf_hardware_interface_plugins.xml`).
  **Nothing forbids naming it in `model/`** — unlike `cite_test_hardware`, which a token guard
  refuses there (decision 5). So the third kind arrives as a **data change**, not as a future
  event: one `hardware_backends` entry, no code, and `commands_physical_hardware: false` is the
  honest answer for it while `use_sim_time` has no honest answer derivable from that field at
  all.

**And there is an architectural reason quite apart from the third kind.** A field that gates a
hardware path should have the **fewest possible consumers, all asking the same question**, so
that what it means can be sharpened later by reading one list of call sites. Wiring a clock
derivation onto it makes any later refinement of the safety field's meaning silently move a
controller manager's clock — a change to a safety declaration with a control-timing side
effect, which is precisely the kind of coupling a reviewer of the safety change would not think
to look for.

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

**The plan key is parsed with `_require`, and the `hosted_by` precedent beside it is
explicitly not followed.** `_manager` reads `backend` with `_require` at `plan.py:1172` and
`counterpart_backend` with `_optional` at `:1173`; the new keys are emitted and parsed
**exactly where those two are**, so the backend accessor and the fact accessor can never
disagree about which sides a manager declares — `commands_physical_hardware` with
`_require`, and `counterpart_commands_physical_hardware` with `_optional`, beside its
backend, present exactly when the counterpart is.

**This has to be said because the comment immediately below them argues the other way**, and an
implementer reading in file order meets it first. `plan.py:1174-1185` records that the removed
`hosted_by` key is *"IGNORED rather than rejected, and that is a decision"*, because *"the
document most likely to still carry it is a plan left in a stale build tree"*. **That reasoning
does not transfer, and the distinction is the whole of it: a removed key's presence is an
absence of information, and this key's absence is a safety fact nobody stated.** Tolerating it
would make the plan layer **strictly weaker than it is today** — a plan missing `backend`
raises `PlanError` now
(`test_a_removed_plan_key_is_ignored.py:102-105` asserts exactly that), while a plan missing
the new key would parse cleanly, default to `False` at every manager, and never consult
`CITE_ALLOW_HARDWARE`. **And the stale build tree the `hosted_by` comment is about is precisely
the state that would produce it**: `simulation.launch.py:193` loads the plan from the package
share via `default_plan_path`, not from the source tree, so a stale installed `cite_generated`
is a plan document that looks valid, reads `False` everywhere and reopens this record's own
defect in a build state nobody notices. A `PlanError` naming the key sends its reader to
rebuild; a default sends nobody anywhere. Clause 5 pins it.

Consumers ask `ControllerManager.commands_physical_hardware_on(side)`, which is to this fact
what `backend_on(side)` is to the backend: **the one place an (asset, side) becomes the
answer**, refusing an undeclared side with the same `SideNotDeclaredError` for the same reason,
so the two accessors answer the same shape of question about the same grain. Reading the raw
keys is the value-in-two-places P1 forbids, and the field that stops being read is the one that
goes stale. **Clause 9 makes that checkable rather than asserted**, because "every consumer
asks the accessor" is a claim about routes and every clause that only asserts behaviour can be
satisfied by an implementation that open-codes the key in two build units — which is exactly
the debt ADR-0048's clause-3 promotion had to retrofit eight days late.

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
  committed-versus-fresh check while the export is stale.** A stale export **does** fail —
  `schema_problems` is printed as `error schema-export` and added to `error_count`
  (`cli.py:216-236`) — so the hazard is not that a forgotten export passes; it is **masking**.
  Measured on 2026-09-09 on two scratch copies of `model/`: with
  `asset_type.schema.json` perturbed, `cite-model validate` exits **1** printing
  `error schema-export … differs from a fresh export` and `1 error(s). The model is not
  valid.`, and **not one `error generated` line**; with the export left alone, the same command
  on the same shape of copy exits 1 printing **34** `error generated` lines. The generated check
  ran in one case and did not run at all in the other, which is why clause 2 is stated apart
  from clause 3: a genuine generated regression would hide behind a schema-export error until
  the export is fixed.
- `tools/tests/fixtures/minimal/assets/types/xarm5.yaml` — the second model that declares
  `hardware_backends`. Both of its backends state the field, or the 73 uses of `minimal_model`
  in `tools/tests/test_validate_referential.py` stop loading.
- `tools/tests/fixtures/minimal/schema/asset_type.schema.json` — the fixture's own committed
  export. **A survey of `tools/tests` on 2026-09-09 found no test that compares it**; the
  implementing change either regenerates it or establishes what reads it, and does not assume
  the survey is a proof that nothing does.
- `workspace/src/cite_generated/bringup/cell_a_plan.yaml` — gains **one** key per controller
  manager on the shipped single-sided zone, and **two** on a paired one, the counterpart key
  being emitted exactly where `counterpart_backend` is (decision 3). **No description, world or
  controller configuration may move**: decision 2 leaves
  `use_sim_time` alone, and a diff that touches those artifacts is an implementation that
  rewired something this record did not decide.
- Test fixtures that build a plan or a type inline — `test_plan.py`, `test_pair.py`,
  `test_gz.py`, `test_simulation_launch.py`, `test_a_removed_plan_key_is_ignored.py` under
  `cite_bringup/test/`, and the `cite_twin` tests that construct a `Deployment`.

### 5. The fixture backends stay inexpressible, and this field may not be the door

`cite_test_hardware/JointStopSystem` is barred from production by ADR-0040, and the leg that
does it is `cite_test_hardware/test/test_unreachable.py`, whose `TOKEN` is the package name
`cite_test_hardware` and whose `test_the_generated_tree_and_the_model_never_name_it` refuses
that token anywhere under `model/` or `workspace/src/cite_generated/`. **So the fixture has no
`hardware_backends` entry whose field could carry a value, and this record must not give it
one.**

**The mechanism is worth stating exactly, because the obvious reading of it is wrong.** The
token guard bars the fixture **whether this field is a boolean or an enumeration** — what it
catches is the plugin class string, which contains the package name, not the value of any field
beside it. An enum value spelled `test_fixture` would not itself trip it. The objection is
therefore not that the enum makes the fixture declarable; it is that the enum **would create L0
vocabulary for a kind ADR-0040 keeps unnameable**, and a vocabulary with a word for a thing
that may not be written is an invitation to a later reader who does not know why the word has
no referent. That is the leg ADR-0053 decision 4 records as the *surviving* one after that
record weakens `on_init`'s, and weakening it here, in a record whose subject is a hardware gate,
would be the worst possible place to do it. Note the asymmetry option E already names: the
**vendor's** fake system is nameable in L0 and this project's fixture is not, so the enum opens
a door on the side that is already shut and adds nothing on the side that is already open.

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
- **It makes a sentence the safety document already states become true.**
  `cross-cutting-safety.md:141-143` states the criterion as *"does any of those sides, for any
  asset in scope, load something other than a simulation, **which the generated bring-up plan
  states per (asset, side)**"*. The plan states a **name** per (asset, side), not that; the
  document describes the artifact this record produces. Nothing in the safety document has to
  change — the gap was between it and the plan, and it closes from the plan's side.

### What this costs us

- **A required field in L0, and a migration that cannot be partial.** Two model files, two
  schema exports, one generated plan, `MODEL_HASH`, and every test fixture that builds a type
  or a plan inline.
- **The model can lie, and nothing catches it.** This is the real price.
  **[Corrected 2026-09-10 — see the Correction section above. It is *a* price, not *the*
  price: the model can also tell the truth and be ignored, because nothing binds the declared
  plugin string to the description that loads one.]**
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
- **It removes a barrier that was standing in front of the mixed-time misconfiguration by
  accident, and that is a cost rather than a neutral fact.** *Context* measures the reverse
  case: Gazebo's own plugin declared under the id `real` generates `use_sim_time: false` and is
  **refused at bring-up today**, because `require_hardware_opt_in` keys on the id. That refusal
  is wrong about the cell — nothing physical is there — but it is loud, and it is
  currently the only thing that stops that model starting. After this change the same model
  declares `commands_physical_hardware: false`, is **correctly permitted**, and starts an arm
  Gazebo drives under `use_sim_time: false`: CLAUDE.md §10's *"a mixed-time system produces
  plausible, wrong results"*. **So this record converts a loud false refusal into a silently
  wrong cell**,
  and it leaves the clock on the id, which is what decides that outcome. Clause 11 pins both
  directions for that reason; nothing here fixes either.
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
  **It also has to answer the binding the Correction section above measures** — whether the
  plugin L0 declares is the plugin the description loads — because that is the last point at
  which no deployment depends on the answer. `../open-work.md` **#65** carries the two
  candidate shapes and chooses neither.
- **The twelve non-arm assets, which are outside the gate in two different ways.** Seven reach
  the plan with no backend key; five are not in the plan at all. When an L1/L2 hardware driver
  exists for a belt, the gate's remit is a decision that has to be taken and is not taken here —
  and the five will need a plan entry before they can have a backend to gate.
- **A false declaration being observed.** If one ever is, the cost of option A's list has to
  be re-weighed against the cost of an undetected false declaration — with the evidence in
  hand rather than in advance.
- **ADR-0053's `params` family under a lying declaration.** A backend declaring `false` while
  naming a physical plugin still receives its `instance_params`. Nothing here changes that, and
  it is the sharpest edge of the "the model can lie" cost.

## The promotion condition

Promoted to `Accepted` by the change that implements decisions 1 to 4, with **all eleven** of
the following. **None of them needs a simulator, a running cell or a physical arm**; the
clauses that import `cite_bringup` or `cite_twin` need a ROS environment for that import and
bring nothing up, the `cite_tools` clauses and clause 9's `grep` run on the host, and every
assertion is against generated text or an in-memory object.

1. **The field is required and unreachable by omission.** A `hardware_backends` entry omitting
   it fails to load, with the error naming the field and the backend. Asserted on a scratch
   type, not on the shipped one. **This is the clause every other clause rests on at the L0
   layer**: with a default, all ten below can pass while a backend becomes physical because a
   key was left out. **Clause 5 is its counterpart at the plan layer**, and one without the
   other leaves a whole layer reachable by omission.
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
5. **The plan key is required too, and a plan that omits it is refused.** Deleting
   `commands_physical_hardware` from a controller manager in a plan document raises `PlanError`
   naming the key, exactly as deleting `backend` does today
   (`test_a_removed_plan_key_is_ignored.py:102-105`). Asserted on a document built in the test,
   with no ROS graph. **This clause exists because every other clause here can be satisfied by
   an implementation that parses the key with `_optional(..., False)`**, which would make the
   plan layer strictly weaker than it is today and would read `False` for every manager of a
   stale installed `cite_generated` — see decision 3. Asserted on the **counterpart** key as
   well, in the form decision 3 requires: present exactly when `counterpart_backend` is, absent
   exactly when it is absent, so the two accessors never disagree about which sides exist.
6. **The reproduction in *Context* is refused end to end.** Build that scratch model with the
   field declared truthfully, generate it, load the plan, call `require_hardware_opt_in` with an
   empty mapping, and require `HardwareNotPermittedError`. **This is the clause that fails if
   any of decisions 1 to 3 lands partially**, because it is the only one that runs the whole
   path the defect ran.
7. **`physical-plant-on-paired-zone` reads the declaration.** A paired zone whose plant backend
   is named `sim` and declares physical is an ERROR, asserted **by rule id and `where`** and
   not by message substring; a paired zone whose plant is named anything at all and declares
   non-physical is not a finding of any severity. **The rule id `physical-plant-on-paired-zone`
   is unchanged**, so no other record's citation of it goes stale. The `where` is asserted at
   whatever value decision 2 item 2 settles — it is `assets.<id>.hardware.backend` today and is
   expected to move to the type's backend declaration, which is where the cause now lives; the
   clause requires that it be **chosen and asserted**, not that it stay as it was.
8. **L5's gate answers on the fact, and the shipped single-sided deployment still behaves.**
   Three assertions. **None of them constructs a node, starts a graph or brings anything up**;
   each calls a function on an in-memory object, which is a requirement on the implementation as
   much as on the test — see the third bullet.
   - On the deployment *Context* measures — every side stating the id `sim` while that backend
     declares physical — `physical_sides_commanded` names at least one (asset, side) for every
     mode that commands the far side, where today it names none for any mode, and the
     `SAFETY_BLOCKED` message still names the (asset, side) it refused for.
   - **On a `Deployment` built from the shipped single-sided plan,
     `assets_without_a_far_side` still names the assets it names today.** This is the assertion
     that catches decision 2's two-valued collapse: a `bool` map makes every unpaired asset look
     like it has a simulated far side, silently retiring the `PRECONDITION_FAILED` refusal of a
     two-sided mode on a one-sided deployment. **The construction of that map from the plan must
     itself be callable without a node** — a free function or a static method taking the
     plan — both so this assertion is possible on the host and because the failure it guards is
     an exception raised *during* `TwinBoundary.__init__`, which no test that needs a working
     `__init__` can reach. Nothing existing would catch either failure: both twin-boundary
     launch tests fabricate a paired plan before constructing the node.
   - **`far_side_physical` is asserted separately, because it does not live on `Deployment`.**
     It is a local in `twin_boundary._sample` (`:756`) computed from `self._far_side_backends`
     (`:282-285`), so an implementation could migrate `Deployment` fully, satisfy both
     assertions above, and leave `_sample` still deciding on a name. The clause requires that
     the derivation be a **free function of the declared fact**, called by `_sample` and
     asserted directly — which is what makes it host-testable at all. It is **not a motion
     path**: it feeds only `frames_correspond` (`divergence.py:244`), a P8 concern, which is why
     it is a clause and not a High.

   **Without this clause the record's own headline finding stays unfixed**, and `cite_twin` is
   unreachable from any launch, so nothing else would notice.
9. **The raw plan keys have exactly one reader per build unit, checked by `grep` and not by
   assertion.** `grep -rn "commands_physical_hardware" workspace/src --include=*.py` outside
   tests reaches, in `cite_bringup`, only `plan.py`'s parser and its
   `commands_physical_hardware_on` accessor, and in `cite_twin` only call sites of that accessor
   — no consumer names `manager.commands_physical_hardware` or
   `manager.counterpart_commands_physical_hardware` directly. **Stated as a route and not as a
   behaviour on purpose**: clause 4 and clause 8 are both satisfied by an implementation that
   open-codes the two keys inside `require_hardware_opt_in` **and** inside `twin_boundary`,
   which is four keys across two build units and exactly the P1 debt ADR-0048's clause-3
   promotion had to retrofit eight days late. Checked the way clause 10 already checks the
   constant.
10. **`ids.SIMULATION_BACKEND` survives with one meaning, and its comment stops asserting the
   falsified one.** `grep -rn SIMULATION_BACKEND tools workspace/src --include=*.py` reaches
   the definition in `cite_tools.model.ids`, the `use_sim_time` derivation at
   `generate/control.py:236`, and nothing else — the `cite_bringup.plan` and `cite_twin.mode`
   restatements are gone with their consumers. The surviving comment no longer says *"the one
   backend id that cannot reach a physical machine"*, and says instead what the id decides and
   what it does not.
11. **The `use_sim_time` residual is pinned in both directions, with its consequence.** Two
    characterisation tests, not one, because *Context* measures the rule wrong in both
    directions and **the direction this record leaves reachable is the one that produces a
    running, wrong cell**:
    - a backend declaring `commands_physical_hardware: true` under the id `sim` still generates
      `use_sim_time: true` — the physical direction, which after this change is reachable only
      behind a deliberate opt-in or a false declaration;
    - a backend declaring `commands_physical_hardware: false` under the id `real` still
      generates `use_sim_time: false` — **the direction this record unblocks**, since that model
      is refused at bring-up today only because the gate keys on the id, and after this change
      it is correctly permitted and starts a Gazebo-driven arm on the wrong clock.

    Both name decision 2 as the reason, and the second cites *What promotion does not claim*'s
    `use_sim_time` bullet, so a reader meets the traced consequence — a deadline owned by a
    process that is not the arm — and not merely the existence of a gap. They are
    **characterisation tests of a known gap** and say so in their own docstrings, so that a
    later reader does not infer from the record's title that it was closed.

**The condition is deliberately not split by clause**, unlike ADR-0048's. One field, two plan
keys and four consumers are satisfied or falsified by one change; there is no part of it that is
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
- **That the plugin L0 declares is the plugin the description loads.** Added 2026-09-10 by the
  Correction section above, which measures it; this list is permanent, and a list of routes to
  an arm that omits one is the dangerous kind of incomplete. The type's `bound_args` carries
  the declared plugin string into the vendor macro on one line, **no validator reads
  `bound_args` at all**, and the vendor macro's own default is
  `uf_robot_hardware/UFRobotSystemHardware`. So deleting that binding leaves L0 honest, the
  plan honest, the gate correctly silent, and the physical component loaded. Reachable by
  **omission**, which is the failure mode `cross-cutting-safety.md` forbids and which clauses
  1 and 5 close at the two layers they cover. Filed as `../open-work.md` **#65**; not fixed
  here.
- **That this is a protective measure.** It is a **bring-up refusal**: it decides whether a
  process starts, once, and it is not a per-command check. It cannot stop an arm that is
  already moving, and it interposes nothing on any command path.
- **That charter §3.2 moves.** The risk assessment, the safety-rated controller, the physical
  guarding and certification against ISO 10218-1/-2 are outside this repository and are neither
  touched nor substituted by anything here. `cross-cutting-safety.md` says it in its own second
  paragraph: no amount of careful software substitutes for them.
- **That the gate covers the cell.** It covers assets with a controller manager. Of the twelve
  non-arm assets, seven reach the plan with no backend key and five do not reach it at all, so
  a physical belt driver would be outside it — measured in *Context*, and not fixed here.
- **That any physical arm exists or has ever loaded anything.** None does (charter §8). Every
  clause above runs against generated text and in-memory objects.
- **That `use_sim_time` is right.** It still keys on the id, and *Context* measures it wrong in
  both directions. Clause 11 pins that; it does not fix it.
  **The consequence of the physical direction is stated here rather than left as "a gap",
  because it is attributable from the code path without any measurement — and it is reasoned
  from that path, not measured, and unmeasurable until a hardware launch exists.**
  `templates/description/arm.urdf.xacro.j2:50-51` emits the `gz_ros2_control` plugin
  unconditionally and hands it the generated controller configuration through `<parameters>`, so
  a controller manager hosting the vendor's *physical* component takes its clock from the
  simulator; every quantity in that control path measured in that clock — trajectory sampling,
  ADR-0036's `goal_time` and path tolerances, every deadline — is then owned by a process that
  is not the arm, and **if the simulator stalls mid-trajectory none of them ever expires while
  the arm holds its last command**. That is `cross-cutting-safety.md:109-112`'s *"motion
  **stops**. It does not continue on the last command"* failing in the one direction a watchdog
  cannot catch, because the watchdog's clock is what stopped. It is the mirror of ADR-0045, a
  deadline measured in the wrong clock, which this project has already paid for once.
  **It is nevertheless acceptable to carry, and the reasons are what make it a residual rather
  than a blocker**: after this change it is never the first thing that has to go wrong — it
  needs either a deliberate `CITE_ALLOW_HARDWARE` opt-in or a false `commands_physical_hardware`
  declaration standing in front of it — there is no hardware launch for it to bite in its own
  right (`simulation.launch.py` hardcodes `use_sim_time: True` at ten sites), and clause 11 pins
  it so that the next reader meets it.
- **That a paired cell has been brought up this way.** `model/facility/zones.yaml` declares
  `twin: {sides: single}`, so the paired readings in *Context* are of a scratch model, and
  nothing paired ships.
