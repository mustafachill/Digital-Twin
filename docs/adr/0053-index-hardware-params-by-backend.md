# ADR-0053: Index a backend's instance parameters by backend, and bind them into the generated description

- **Status:** Proposed — **nothing in this record is implemented.** Every "will", "must" and
  "may not" below is a commitment, not a description. Established in this checkout on
  2026-09-08 at `aed36c4`, by the commands in *Context*:
  - `grep -rn params tools/cite_tools/generate/` returns nothing, and
    `grep -rn params tools/cite_tools/model/resolve.py` returns nothing. **No generated
    artifact carries a `hardware.params` name or value**, on any backend.
  - `tools/tests/test_hardware_params_unbound.py` pins that property deliberately, with the
    backend's plugin string as a positive control.
  - `model/assets/types/robots/xarm5.yaml:218-225` declares
    `instance_params: [robot_ip, report_type]` for the `real` backend, and the vendor macro
    chain takes both names.
  - `HardwareSelection.params` (`tools/cite_tools/model/schema.py:1169`) is one flat
    `dict[str, str | bool | int | float]` with no index, and
    `tools/cite_tools/validate/referential.py:232` checks it against the **plant's** backend.
  - `model/facility/zones.yaml` declares `twin: {sides: single}`, so nothing in this
    repository is paired and nothing here needs pairing to be built or tested.

  **Promoted to `Accepted`** by the change that binds the parameters, with all seven of the
  clauses in *The promotion condition*, below. Every one of them is testable on a host with
  no ROS, no simulator and no physical arm, which is deliberate: there is no physical arm and
  a condition that needed one would never be met.
  **Promotion is not a claim that any physical arm has ever loaded the plugin** — see
  *What promotion does not claim*, which is a permanent clause and not a status caveat.
- **Date:** 2026-09-08
- **Deciders:** The project owner, who took decisions 1 to 4. Recorded by the docs-writer
  agent, which verified every fact in *Context* by running the command beside it and
  corrected the framing of decision 4's consequence against what the tree actually does —
  see *Decision 4* and its note on what was proposed and what is written here.
- **Related:**
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) (this record is the
  first item of its *What this record does not decide* list; its clause 1 refusal and its
  unbuilt clause 2 are what let this decision ignore pairing entirely),
  [ADR-0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md) (decision 2's
  first structural argument, its 2026-08-28 correction, and the revisit item this record
  discharges and re-frames — **the implementing change owes that record an amendment**),
  [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md) (Decision 3, which
  established that a backend has no side index),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) (clause 4, and the
  `domain_offset` argument decision 3 distinguishes itself from),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0020](0020-facility-model-conventions.md),
  [L0](../architecture/L0-facility-model.md),
  [L1](../architecture/L1-description-and-assets.md),
  [L2](../architecture/L2-control-and-hal.md),
  [`cross-cutting-safety.md`](../architecture/cross-cutting-safety.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §3, charter §4 (P1, P2, P5, P6, P7, P9) and §8
  (Phase 2.B)

## Context

Every fact below was produced by the command beside it, run in this checkout on the branch
`docs/adr-0053-hardware-params` at `aed36c4`. Nothing here is quoted from another record
without being re-established.

### The gap, reproduced rather than quoted

Method, the same one ADR-0048's Context uses: copy `model/` to a scratch directory, set
`arm_1` to `hardware: {backend: real, params: {robot_ip: 203.0.113.7, report_type: normal}}`,
then run `cite_tools.validate.referential.check` and `cite_tools.generate.generate` on it.

| Question | Answer at `aed36c4` |
|---|---|
| Does the model validate? | **Yes — zero referential findings**, errors or warnings |
| How many artifacts? | 34 |
| Does the plugin string reach `description/cell_a_arm_1.urdf.xacro`? | **Yes** — `uf_robot_hardware/UFRobotSystemHardware` |
| Does `203.0.113.7` reach that description? | **No** |
| Does `robot_ip` or `report_type` reach it, as a name? | **No** |
| Does either name or value reach **any** of the 34 artifacts? | **No** — the search over every artifact returns an empty list |

The generated macro invocation is the whole of it. On that `backend: real` arm it reads, in
full, **eighteen** arguments of which **none is `robot_ip` and none is `report_type`**:

```xml
  <xacro:xarm_device
      add_gripper="true"
      ...
      ros2_control_plugin="uf_robot_hardware/UFRobotSystemHardware"
      velocity_control="false"
  />
```

So the model can say "this arm is the physical one at this address" and the generator answers
by naming the physical plugin and dropping the address.

### The generator binds one field of `hardware:` and enumerates the rest

`tools/cite_tools/generate/description.py:161` binds `instance.hardware.ros2_control_plugin`,
inside the `values` map of `_binding_value` (`description.py:138-194`).
`grep -rn params tools/cite_tools/generate/` returns **nothing**, and
`grep -rn params tools/cite_tools/model/resolve.py` returns **nothing**. The map is exhaustive
by design: its own docstring says *"Every binding is enumerated. An unknown one raises rather
than defaulting, so a typo in the component library fails loudly here instead of silently
handing the vendor macro its own default — which would produce a description that loads and
is wrong."*

`tools/tests/test_hardware_params_unbound.py` pins the absence, and its docstring is the
clearest statement of this gap in the tree. It also scripts its own succession: *"Phase 2
fails that test at the moment a reviewer needs to see it."* That sentence is
ADR-0040's, at `docs/adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md:213`;
the test file itself says the same thing in different words.

### The vendor macro takes both names, and its `<param>` block is guarded on the plugin

Read from the imported vendor source at `workspace/src/external/xarm_ros2/`:

| Where | What it does |
|---|---|
| `xarm_description/urdf/xarm_device_macro.xacro:36-37` | declares `robot_ip:=''` and `report_type:='normal'` as macro parameters |
| the same file, lines 128-129, inside its `${dof == 5}` branch | passes both into `xarm5_robot` (the other five branches do the same for the other models) |
| `xarm_description/urdf/xarm5/xarm5_robot_macro.xacro:11-12`, and lines 35 and 59 | declares the same two defaults and passes both to `xarm5_ros2_control` |
| `xarm_description/urdf/xarm5/xarm5.ros2_control.xacro:16-28` | emits `<param name="robot_ip">R${robot_ip}</param>` and `<param name="report_type">…</param>`, inside `<xacro:if value="${ros2_control_plugin == 'uf_robot_hardware/UFRobotSystemHardware'}">` |

Three consequences of that last row, all of which the decision below depends on.

1. **The guard is total and has no `else`.** `grep -n "xacro:if\|xacro:unless" xarm5.ros2_control.xacro`
   returns two lines, 16 and 28 — one conditional and its close, no `else`, no `unless`. A
   description that loads
   `gz_ros2_control/GazeboSimSystem` gets `<hardware><plugin>…</plugin></hardware>` with **no
   `<param>` at all**, whatever `robot_ip` was passed. Passing the parameter on a `sim` arm
   would therefore be inert — and emitting nothing is the same output for a stronger reason.
2. **This project authors no `<ros2_control>` block of its own.**
   `grep -rn ros2_control tools/cite_tools/templates/description/*.j2` reaches two comment
   lines and the `gz_ros2_control-system` Gazebo plugin, and no `<ros2_control>` element. The
   only route from L0 to a `<param>` is a vendor macro argument.
3. **The value the plugin receives is not the value L0 states.** The vendor prefixes an `R`,
   and `workspace/src/external/xarm_ros2/xarm_controller/src/hardware/uf_robot_system_hardware.cpp:67`
   strips it again with `robot_ip_ = it->second.substr(1);`. A test that asserts an exact
   `<param>` value has to know that; a substring search does not.

### What an empty address does today, read in the vendor's own source

`uf_robot_system_hardware.cpp:64-73`: the component reads `robot_ip`, takes `substr(1)`, and
if the result is empty it logs `No param named 'robot_ip'`, calls `rclcpp::shutdown()` and
`exit(1)`. So today's defect does **not** produce an arm quietly connected to the wrong
address — it produces a `ros2_control_node` that terminates abruptly from inside a loaded
plugin, at `on_init`, with a message naming a parameter the model did state. That is a loud
failure, and it is still the wrong place for it: the value exists in L0 and is discarded by
the generator, so the failure lands at bring-up on the machine standing next to the arm
instead of at `./scripts/validate-model` on a laptop.

### The allowlist reads the plant's backend, and skips almost every asset

`tools/cite_tools/validate/referential.py`:

- line 230-231 — `if not backends: continue`. A type that declares no `hardware_backends` is
  skipped entirely.
- line 232 — `chosen = asset.hardware.backend`. The **plant's**.
- lines 258-259 — `allowed = set(backends[chosen].instance_params)`, and every key of
  `asset.hardware.params` outside it is an `unexpected-hardware-param` ERROR.

`grep -rl hardware_backends model/assets/types/` returns **one file**,
`model/assets/types/robots/xarm5.yaml`. Loading the shipped model and asking it directly:
**7 types, 1 of which declares `hardware_backends`; 15 assets, of which 3** (`arm_1`,
`arm_2`, `arm_3`) reach the allowlist and **12** (`beam_c1_out`, `beam_c2_out`,
`beam_c3_out`, `beam_pick`, `conveyor_1`, `conveyor_2`, `conveyor_3`, `pedestal_1`,
`pedestal_2`, `pedestal_3`, `table_accumulation`, `table_pick`) are skipped at line 230.
Every one of those twelve writes `hardware: {backend: sim}`, which nothing checks against
anything. **Any rule written here binds three assets and is silent on twelve.**

Three consequences, each reproduced:

- **A `sim` arm may not carry `robot_ip` today.** `params: {robot_ip: 203.0.113.7}` on
  `arm_1` with `backend: sim` produces
  `ERROR unexpected-hardware-param assets.arm_1.hardware.params.robot_ip — backend 'sim' of
  type 'xarm5' declares no parameter 'robot_ip'. Declared parameters: (none).`
- **A paired zone whose counterpart is `real` cannot carry them either.** Setting
  `twin.sides: pair`, `counterpart_backend: real` and the two parameters produces **three**
  errors: the same two `unexpected-hardware-param`, plus ADR-0048 clause 1's
  `divergent-counterpart-backend`.
- **So the divergent-counterpart case is refused twice over, by two different rules**, and
  ADR-0048 clause 1 refuses it before this record's subject matter arises. **Nothing here
  needs pairing.** The problem this record fixes is live on an untwinned zone with a single
  side, which is the zone this repository ships.

### One existing test already writes `params` on a `real` arm, and this change breaks it

`tools/tests/test_generate.py::TestSimRealParity::test_only_the_plugin_differs_between_backends`
(lines 237-300) switches `arm_1` to
`{"backend": "real", "params": {"robot_ip": "192.168.1.100"}}` and then asserts that the two
descriptions differ in **exactly two lines** — the plugin and, since 2026-09-01, the
collision root's URI scheme. Its comparison is
`zip(sim.splitlines(), real.splitlines(), strict=True)`.

The implementing change hits this test three times, in this order. The first two are read
from that file; the third follows from decision 1's shape.

1. **The mutation stops being a valid model.** `params: {"robot_ip": "192.168.1.100"}` is a
   flat map, and under decision 1 a `params` value is a per-backend block, so the mutation has
   to be rewritten as `params: {"real": {...}}` before anything else runs.
2. **The model then supplies `robot_ip` and not `report_type`**, while `xarm5.yaml:225`
   declares both. Under decision 2a below, binding `report_type` and leaving it unsupplied is
   a `BindingError` — so **every `real` arm in any model must state both**. That is a real
   consequence of 2a and not an oversight in it: `HardwareSelection.backend` is already
   required with no default for the same reason, and a `report_type` chosen by nobody is a
   value chosen by nobody.
3. **With both supplied, the line counts stop matching.** `arm.urdf.xacro.j2` emits one macro
   argument per line, so two emitted arguments are two new lines in the `real` description and
   none in the `sim` one — and `zip(..., strict=True)` raises `ValueError` before any
   assertion runs. The failure is not the readable one the test was written to give, and
   `assert len(rest) == 1` is wrong by two once it is.

The parity test's own subject is untouched: P2's subjects are topic, action, controller,
joint and frame names, and none of them moves. What has to change is the assertion's
arithmetic and its model, and a reviewer must check that the widening is exactly that.

### `hardware.params` is already inside `MODEL_HASH`, before any change here

`cite_tools.generate.model_hash` digests `a.model_dump_json()` for every asset
(`tools/cite_tools/generate/__init__.py:42-62`), and `params` is a field of
`HardwareSelection`. Measured: two scratch models identical except that one says
`robot_ip: 203.0.113.7` and the other `203.0.113.8` hash to
`214d3050…` and `f83cf715…`. **A one-digit change to an address already moves `MODEL_HASH`
today.** Decision 3's cost is therefore a cost this repository already pays for any facility
that writes the field, not a new one this record introduces.

### The declaration is already written, with a comment saying why

`model/assets/types/robots/xarm5.yaml:218-225`:

```yaml
  hardware_backends:
    sim:
      ros2_control_plugin: gz_ros2_control/GazeboSimSystem
      instance_params: []
    real:
      ros2_control_plugin: uf_robot_hardware/UFRobotSystemHardware
      # Phase 2. Declared now so that a mixed fleet is a data change.
      instance_params: [robot_ip, report_type]
```

`HardwareBackend.instance_params` (`tools/cite_tools/model/schema.py:421`) is therefore
already **per backend**, and has been since before pairing existed. That is the shape the
decision below follows rather than invents.

### What the schema already says about side indexing

`HardwareSelection.counterpart_backend`'s comment
(`tools/cite_tools/model/schema.py:1152-1167`) states the rule this record extends:

> `backend` is a scalar with no side index: it says which plugin *this instance* loads, and
> in a twin pair this instance exists on both sides. So a backend is selected per
> (asset, side), and the only thing ever written per asset is a side that DIFFERS from the
> plant — which is a genuine per-asset fact.

### What the generator is allowed to know about the vendor

`DescriptionSpec`'s docstring (`tools/cite_tools/model/schema.py:375-383`):

> The generator's entire knowledge of the vendor package is the argument names below, which
> are model data. It never opens a vendor file and never patches one, so a vendor upgrade
> that renames a parameter is a two-line model diff.

### The precedent for emitting no argument at all

`_collision_args` (`tools/cite_tools/generate/description.py:252-297`) returns `[]` at line
289 when nothing is selected, and its docstring calls that emptiness load-bearing: *"A
binding that changed the output when nothing was selected would have made the byte-identity
check unable to tell 'the default is unchanged' from 'the default moved'."* The same function
reads `asset.instance.hardware.backend` at line **290** to pick the URI scheme — so
`description.py` already resolves a per-backend model fact, and already resolves it against
the plant, because there is one artifact set per asset today (ADR-0048 clause 2 is unbuilt).

## Options considered

### Option A — index `params` by side

```yaml
      params:
        plant: {}
        counterpart: {robot_ip: 192.168.1.203, report_type: normal}
```

Plausible because the thing 2.B is about is a side, and because ADR-0042 and ADR-0044 both
index by side. Rejected for three reasons, in increasing order of severity.

1. **It restates a fact `counterpart_backend` already carries.** Which side is physical is
   stated once, in `counterpart_backend`. A side-indexed `params` says it a second time by
   implication, and P1 forbids a value existing in two places. Worse than the duplication is
   that the two can *disagree*: `counterpart_backend: sim` with a `counterpart:` block full
   of connection parameters is a model no rule catches, and the reader cannot tell which
   half is stale.
2. **It becomes invalid the moment a zone unpairs.** `twin.sides` is a zone fact and this is
   an asset fact; setting `sides: single` leaves every `counterpart:` block orphaned, and the
   orphan is silent, because `referential.py:230` never reaches most assets at all.
3. **It still needs the backend.** The allowlist is `HardwareBackend.instance_params`, which
   is keyed by backend. A side index would have to be resolved *to* a backend before any
   check could run, so the side index buys an extra hop and no information.

### Option B — leave `params` flat and widen the allowlist to the union of every declared backend

The tempting minimum: change `allowed = set(backends[chosen].instance_params)` to the union
over `backends`, and the paired and untwinned cases both start validating with no schema
change at all. It is one line, and for today's model — one type, two backends, disjoint
parameter names — it is indistinguishable from the decision below.

Rejected because it is indistinguishable **only for today's model**. With a third backend —
a second vendor, a different hardware interface for the same arm — two backends can declare
the same parameter name needing different values, and a flat map has no way to say which is
which. There is no error at that point; there is a wrong value, silently.

The alternative to closing that now is a warning or a paragraph in the L0 document, which is
exactly ADR-0048's Option D, and it was rejected there on ADR-0042's precedent: *"a warning
would be read once and then never again, and what it guards against produces no symptom"*
(quoted in `0048-refuse-a-counterpart-the-generator-cannot-build.md:526-527`). The shape here
is the same. A flat map holding one of two backends' values for a shared name is a
**well-formed model** — there is nothing to warn about, nothing to fail, and no symptom until
an arm connects to the wrong thing. Choosing the flat map now would also mean choosing it
again later under pressure, with a facility already written against it and a migration to
perform.

### Option C — derive the macro arguments from `instance_params` directly, with no `bound_args` entry

Plausible on a real observation: `instance_params: [robot_ip, report_type]` are already
*exactly* the vendor macro's parameter names, so the generator could emit
`name="value"` for each entry without the type having to bind anything.

Rejected because it makes `instance_params` do two unrelated jobs at once — the L0 allowlist
of what an instance may state, and the vendor's spelling of its own macro parameters. A
vendor rename would then silently change which L0 keys are legal, and an L0 rename to
something more readable would silently stop reaching the vendor. It also contradicts
`DescriptionSpec`'s docstring, quoted above: the generator's entire knowledge of the vendor
package is `fixed_args` and `bound_args`, and this option would give it a second channel that
no `bound_args` diff would show.

### Option D — emit the parameters on every backend, and let the vendor's guard drop them

Since `xarm5.ros2_control.xacro:16` discards every `<param>` on a non-UFACTORY plugin
anyway, the generator could pass `robot_ip=""` unconditionally and let the vendor ignore it.
Simplest possible generator: no filter, no conditional.

Rejected for the reason `_collision_args`' docstring already gives about a different
argument. Emitting an argument that is only inert *because a third party's `<xacro:if>` drops
it* moves the guarantee out of this repository and into a vendor file that a pin bump can
change. It would also change the committed generated tree for the shipped, all-`sim` model —
so `./scripts/validate-model`'s byte-identity check would stop being able to tell "the
default is unchanged" from "the default moved", which is precisely the property that
docstring says the emptiness protects.

### Option E — put the address outside L0, in an environment variable or a deployment file

The obvious objection to decision 3 taken to its conclusion: an IP is deployment
configuration, so put it where deployment configuration goes, and keep it out of the hashed
artifact.

Rejected because it is the inversion P5 names — code and launch arguments would then encode
*which* arm exists at *which* address — and ADR-0021 forbids the generated tree taking a
value from anywhere but L0. It also loses the property that makes the twin a twin: a
recording stamped with `MODEL_HASH` would no longer identify the facility it was taken on,
because the facility's addresses would live outside the hash.
See decision 3 for why this argument does **not** carry over from `domain_offset`, which is
the strongest-looking precedent for this option.

## Decision

### 1. `hardware.params` is indexed by **backend**, not by side

```yaml
    hardware:
      backend: sim
      counterpart_backend: real
      params:
        real: {robot_ip: 192.168.1.203, report_type: normal}
```

The map's keys are backend ids declared in the type's `hardware_backends`. The values are the
flat `dict[str, str | bool | int | float]` `params` is today.

**The argument, and it follows from a rule already in the tree rather than from taste.**
`HardwareSelection.counterpart_backend`'s own comment fixes it: *"a backend is selected per
(asset, side), and the only thing ever written per asset is a side that DIFFERS from the
plant."* Take that seriously and the parameters follow. `robot_ip` is a property of the
UFACTORY hardware component — of the thing that opens a socket — and not of the side that
happens to load it. That is why `HardwareBackend.instance_params` is already declared per
backend at `schema.py:421`, months before pairing existed. A side gets the parameters of
whatever backend it loads; nothing about which side is physical is restated, and nothing here
can disagree with `counterpart_backend` (P1).

**The address in the example above is an illustration.** `tools/tests/test_hardware_params_unbound.py`
uses `203.0.113.7` and says why in its own comment — TEST-NET-3, reserved for documentation
by RFC 5737 (verified 2026-09-08 against `https://www.rfc-editor.org/rfc/rfc5737.txt`, which
reads *"The blocks 192.0.2.0/24 (TEST-NET-1), 198.51.100.0/24 (TEST-NET-2), and
203.0.113.0/24 (TEST-NET-3) are provided for use in documentation."*). Any address written in
a document is a placeholder; the facility's real ones are written in `model/` and nowhere
else.

**The validation rule that follows, stated so the implementer cannot read it three ways.**

- A key of `params` that is **not a declared backend id of that type** is an ERROR. This is
  the typo case, and it is the one thing this shape catches that a flat map cannot.
- A parameter name inside a backend's block that the **named** backend does not declare in
  `instance_params` is an ERROR — the existing `unexpected-hardware-param`, now resolved
  against the backend the block names rather than against the plant's.
- A backend block for a backend **nobody on this asset selects** is legal and inert.

**The widening the third rule buys, and its cost, stated rather than hidden.** Today
`params: {robot_ip: …}` on a `sim` arm is refused (reproduced in *Context*). Under this
decision `params: {real: {robot_ip: …}}` on a `sim` arm is accepted and reaches no artifact.
That is deliberate: it is what makes flipping an arm to hardware a **one-field edit** — change
`backend: sim` to `backend: real` — which is the property `xarm5.yaml:224`'s own comment
*"Declared now so that a mixed fleet is a data change"* was written for.
**The cost: a parameter written for a backend nobody selects sits in L0 unexercised, and no
test can tell it from a deliberate pre-declaration.** A wrong address for an arm that has not
been switched over yet is not detectable by anything in this repository, and will be found by
the arm failing to connect. A typo in a *backend id* is still caught, by the first rule
above; a typo in a *value* is not, and never could be.

### 2. The binding family `instance.hardware.params.*`, emitted conditionally

`xarm5.yaml` gains two `bound_args` entries beside the **eight** it has (counted by loading
the model and asking the type, 2026-09-08):

```yaml
    bound_args:
      robot_ip: instance.hardware.params.robot_ip
      report_type: instance.hardware.params.report_type
```

and `_binding_value` (`description.py:138-194`) gains the `instance.hardware.params.*`
family, resolved from the **selected backend's** block of `params`. "Selected" means
`asset.instance.hardware.backend` — the same quantity `_collision_args` resolves the
collision URI scheme against at `description.py:290` — and it is the plant's, because there
is one artifact set per asset. **ADR-0048 clause 2 is what makes it per-side**, and until
clause 2 is built ADR-0048 clause 1 refuses any asset whose two sides differ, so the two
sides always load the same backend and the question cannot arise. Nothing in this decision
needs pairing, and nothing in it may be read as building any part of clause 2.

Two sub-rules, each with its reason.

**2a. A declared key with no supplied value raises `BindingError`.** If the selected
backend's `instance_params` contains `robot_ip`, the type binds a macro argument to
`instance.hardware.params.robot_ip`, and the asset's `params` block for that backend does not
supply it, the generator raises — in the shape `_end_effector_drive_rate` already uses at
`description.py:178-186`, naming the type, the asset and the binding.

The reason is the one that shape was chosen for. A connection parameter has no default that
could be right, and the failure mode of defaulting is measured rather than imagined: the
vendor's `robot_ip:=''` becomes `<param name="robot_ip">R</param>`, and
`uf_robot_system_hardware.cpp:64-73` responds with `exit(1)` inside a loaded plugin at
`on_init`. Raising at generate time moves that from the cell to a laptop.

**2b. On a backend that declares no such parameter, the argument is not emitted at all.**
`sim`'s `instance_params` is `[]`, so `_arm_view` (`description.py:213-240`) filters the
family — dropping any `instance.hardware.params.<key>` binding whose `<key>` is not in the
selected backend's `instance_params` — **before** resolving it. The vendor's own
`robot_ip:=''` default then stands, which is correct rather than merely tolerable, because
`xarm5.ros2_control.xacro:16-28` emits no `<param>` block whatsoever unless the plugin is the
UFACTORY one.

The precedent is `_collision_args` in the same file: `return []` at line 289, emitting no
macro argument at all, with a docstring calling that emptiness load-bearing. The consequence
here is the same one: the shipped, all-`sim` model must generate byte-identically after this
change, so `./scripts/validate-model` can still tell "unchanged" from "moved".

**Why 2b does not weaken "an unknown binding raises rather than defaulting".** The filter
tests membership in the selected backend's `instance_params`, which is a list L0 authors. A
typo *inside* the family — `instance.hardware.params.robot_ipp` — is not in that list on any
backend, so it is not filtered and falls through to the existing unknown-binding
`BindingError` at `description.py:189-193`. The filter drops a binding **because a backend
deliberately declares no such parameter**, never because the generator failed to resolve one.
An implementation that filters on "could not resolve" instead of on "the backend does not
declare it" satisfies the letter of this clause and defeats its purpose; clause 4 of the
promotion condition exists to catch exactly that.

### 3. An IP address belongs in the hashed L0 artifact

The obvious objection is `domain_offset`'s. `tools/cite_tools/model/ids.py:169-181` refuses
to put a ROS domain id into the generated tree, because *"A domain id is not a name: it is a
host-scoped resource allocation, closer to a TCP port"*, and because deriving it either way
fails: from the deployment it differs in every clone and breaks
`./scripts/validate-model`'s byte-identity check, and from the model it is identical in every
clone so two checkouts of one commit collide.

**An arm's address is not that, and the difference is the arbitration.** A ROS domain is
*arbitrated per checkout* — `scripts/_lib.sh:93` reads *"Plants are odd and counterparts are
even, so no counterpart of any checkout can"* land on another checkout's plant — so the
correct value is a function of *who is running*, which is exactly what may not enter a
committed artifact. An arm's address is a
function of nobody running anything. It is a property of the **installed machine**: this arm,
bolted to this table, on this cell's network. It is identical in every clone of the model
that describes that facility, and it is therefore an L0 fact in the same sense as the arm's
world pose, its joint limits, or which pedestal it stands on.

**This rests on an assumption about a network that does not exist yet, and it is an
assumption rather than a fact.** The decision assumes each arm takes a **static** address on
an isolated, non-globally-routable cell network, and that the address is not a secret. No
such network has been built — charter §8 puts the physical cell in Phase 2.B — so nothing
here is verified about it, and the last bullet of *What we will have to revisit* is what
happens if any of the three assumptions turns out false.

Two things recorded honestly rather than left to be discovered.

- **The cost.** Renumbering the lab's subnet moves `MODEL_HASH`, which stamps every L6
  recording. That is correct behaviour — the described facility changed — but it means a
  network change invalidates the identity of past recordings for a reason that has nothing to
  do with the robots, and somebody will be surprised by it. Measured in *Context*: the hash
  already moves on a one-digit address change today.
- **The residual, and this decision deliberately does not close it.** A facility whose arms
  take **DHCP** addresses has no L0 answer here. There is no correct value to write, and an
  environment-variable indirection is the P5 inversion Option E was rejected for. If such a
  facility appears, this record is reopened rather than worked around.

### 4. What this does to ADR-0040, stated more narrowly than it was proposed

ADR-0040's revisit list predicts this record
(`0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md:567-570`):

> **If the L0 model ever gains a hardware-plugin selector richer than the backend it has
> today**, the first structural argument has to be re-checked: what makes the fixture
> unreachable is that the model cannot express its parameters, and a more expressive model is
> exactly what would change that.

**The prediction's premise does not happen here, and its conclusion is already known to be
wrong.** The selector is unchanged — still `hardware_backends`, keyed by backend id, one
plugin class string each. And "the model cannot express its parameters" was already false
before this record: ADR-0040's own 2026-08-28 correction says so, and
`tools/tests/test_hardware_params_unbound.py` exists to hold the true version. What changes
here is the **generator**. So this record discharges the revisit item and corrects its
framing at the same time: the item should have said *"if the generator ever carries
`hardware.params` into a description"*, and the change that implements this record must amend
ADR-0040 to say so.

**Now the consequence, and it is not the one this decision was proposed with.** The proposal
put to this record was that after the change *"the only thing keeping `cite_test_hardware`
out of production is its own `on_init` refusal"*, narrowing the safety argument from three
legs to one. Read against the tree, that is wrong in both directions, and a record that
repeated it would understate one hazard and overstate another.

**The `on_init` refusal is the leg this change weakens, not the leg that survives it.**
`joint_stop_system.cpp:76-90` refuses when `stop_joint` is absent or empty — its comment
says *"it cannot start without a stop, and a stop has nowhere to be declared in the L0 model
(ADR-0040 decision 2)"* — and `cite_test_hardware/test/test_unreachable.py`'s docstring rests
on the same conditional: *"the fixture refuses to initialise without a `stop_joint`
parameter, and the L0 model has no way to express one."* A refusal conditioned on a parameter
being unsupplied is worth exactly as much as the impossibility of supplying it. Supply it and
`on_init` returns `SUCCESS` with an `RCLCPP_WARN`.

**Three other legs survive, and none of them is `on_init`.**

1. **`cite_test_hardware/test/test_unreachable.py` forbids the token in `model/` by name.**
   Four contexts may name `cite_test_hardware` — its own package, any `.md`, anything under a
   `test/` or `tests/` directory, and `docs/measurements/` — and the docstring lists what
   stays forbidden: *"a description, a world, a controller configuration, a launch file, a
   bring-up plan, the L0 model, and any non-test source file in any package."* Selecting the
   fixture requires writing its plugin class string into a type's `hardware_backends`, in
   `model/`. That guard refuses it, and it refuses it today.
2. **`cite_bringup.plan.require_hardware_opt_in` refuses any non-`sim` backend.**
   `plan.py:1145` tests `backend != SIMULATION_BACKEND`, on **every side**, so a fixture
   backend under any name fails bring-up unless the hardware opt-in environment variable is
   set deliberately.
3. **The vendor's own guard leaves the fixture no route on this type.** The fixture's three
   parameters are `stop_joint`, `stop_lower_rad` and `stop_upper_rad`
   (`cite_test_hardware/include/cite_test_hardware/joint_stop_system.hpp:93-97`), and
   `grep -n "stop_joint\|stop_lower\|stop_upper" xarm_device_macro.xacro` returns
   **nothing** — none of the three is a parameter of the vendor macro, so no `bound_args`
   entry can carry them. And `xarm5.ros2_control.xacro:16` emits `<param>` elements only for
   the UFACTORY plugin, while this project authors no `<ros2_control>` block of its own. So
   for every type in this model, the family decision 2 adds carries **nothing** to a fixture.
   **This is the weakest of the three legs**: it is a property of a vendor file and of a
   component library that any new type could change, and nothing tests it.

**The honest statement of the consequence is therefore narrower and more useful than the one
proposed.** ADR-0040 decision 2's first structural argument survives this change, but for a
different reason than the one it gives, and for a *weaker* reason than it used to have: not
"the fixture's parameters are unreachable", but "no type binds a macro argument that would
carry them, and the L0 model may not name the plugin at all". The first of those two is a
property of the component library that any future type could change without noticing; the
second is tested. **The implementing change must amend ADR-0040 with this paragraph**, and
must not delete `test_unreachable.py`'s claim without replacing it with the accurate one.

## Consequences

### What this gets us

- **A `backend: real` arm generates a description carrying the address the facility states.**
  The value reaches the vendor's own macro parameter with no hand edit anywhere. **That is a
  claim about generated text and not about a connection** — see *What promotion does not
  claim*. It is a Phase 2.B prerequisite, and it is met on an untwinned zone with no pairing
  and no per-side artifacts.
- **Flipping one arm to hardware becomes a one-field edit**, which is the "mixed fleet is a
  data change" property `xarm5.yaml:224` was written for and ADR-0041 Decision 3 promised.
- **A missing connection parameter fails on a laptop instead of beside the arm** — a
  `BindingError` from `./scripts/validate-model` rather than an `exit(1)` from inside a
  loaded plugin at bring-up.
- **The shipped model's generated tree does not change**, because every arm is `sim` and
  `sim` declares no instance parameters. The change is provably inert until someone selects
  a backend that declares one.
- **The first item of ADR-0048's `What this record does not decide` list is closed.** That
  item has two halves — *"the side index for `hardware.params`"* and *"how a backend's
  instance parameters reach a generated description at all"*. The second is answered by
  decision 2. The first is answered by **declining to add one**, with the reason written
  down, which is the answer a later reader is most likely to want and least likely to find if
  it is not recorded.

### What this costs us

- **A model may now carry an unexercised parameter block indefinitely**, and no test can
  distinguish a stale value from a deliberate pre-declaration. Decision 1 states this; it is
  the price of the one-field flip and it is not recoverable by any check inside this
  repository.
- **`MODEL_HASH` becomes sensitive to a network renumbering.** It already is, but nothing
  previously wrote an address into `model/`, so nobody has met it. An L6 recording taken
  before the renumbering will not match a facility described after it, correctly and
  confusingly.
- **A DHCP facility has no answer**, and this record deliberately invents none.
- **`instance_params` acquires a second consumer.** It was an allowlist; it is now also the
  filter that decides whether a macro argument is emitted. That is one field doing two jobs —
  which is what Option C was rejected for — and the defence is thin: both jobs are the same
  question ("does this backend take this parameter?"), asked by the validator and by the
  generator. If they ever diverge, this is where the divergence will be.
- **`ADR-0040`'s first structural argument is now held by the component library.** Nothing
  fails if a future type binds a macro argument that a fixture backend could fill. The three
  surviving legs in decision 4 are the ones a reviewer must check, and they are named there
  so that a reviewer can.
- **Every `real` arm must now state every parameter its backend declares.** Decision 2a
  makes an unsupplied declared key a hard error, so `xarm5`'s `real` backend requires both
  `robot_ip` and `report_type` on every instance that selects it. That is more typing and it
  is the point; the alternative is a `report_type` nobody chose.
- **Work the implementing change owes**, in the order it will hit: the schema change (no
  migration of shipped data is needed — no asset writes `params` at all today, verified by
  `grep -rn "params:" model/assets/instances/`, which returns nothing); the validator rule;
  the binding family; the filter; **fixing
  `test_generate.py::TestSimRealParity::test_only_the_plugin_differs_between_backends`**,
  which breaks on a `ValueError` rather than an assertion for the reason in *Context*; the
  seven promotion-condition tests; the rewrite of `test_hardware_params_unbound.py`; and an
  amendment to ADR-0040.

### What we will have to revisit

- **If a facility's arms take DHCP addresses**, or an address is otherwise not a property of
  the installed machine, decision 3 is reopened. Nothing here may be stretched to cover it.
- **If ADR-0048 clause 2 is built**, "the selected backend" in decision 2 becomes per-side and
  this record's binding family must be resolved per side with it. It is one accessor, and the
  place it will go is `cite_bringup.plan.ControllerManager.backend_on`'s generator-side
  equivalent.
- **If a third backend ever declares a parameter name a second backend also declares**,
  decision 1 is the thing that made that expressible; check that the validator's message
  names the backend block and not just the key, or the ambiguity comes back as a confusing
  error rather than as a wrong value.
- **If a type is ever added whose vendor macro takes a parameter a test fixture could fill**,
  decision 4's third leg is gone and only the two tested ones remain. That is the review
  checkpoint.
- **If a connection parameter ever needs to be a secret** — a token, a password — decision 3
  does not cover it, because the argument for L0 rests on the value not being one.
- **When the physical cell's network is actually built**, decision 3's three assumptions —
  static addressing, an isolated non-globally-routable network, and no secret — must be
  checked against it rather than assumed to have held. Any one of them failing reopens this
  decision, and the DHCP case above is only the first of the three.

## The promotion condition

Promoted to `Accepted` by the change that implements decisions 1 and 2, with **all seven** of
the following. Every clause runs on a host with no ROS, no simulator and no physical arm.

1. **The values reach the description on a selecting arm.** With one arm on a backend whose
   `instance_params` declares them and a `params` block supplying them, the generated
   description's **macro invocation** carries `robot_ip="…"` and `report_type="…"` as
   arguments — asserted against the argument list, not by substring search of the file, so
   that a value written into a comment cannot pass.
2. **They do not reach a `sim` arm's description.** Same model, an arm on `sim`: neither
   argument name appears in its macro invocation at all. Absence, not an empty value —
   clause 6 is what makes "absent" checkable.
3. **A declared-but-unsupplied key raises rather than defaulting.** The generator raises
   `BindingError` naming the asset and the binding, and the same model with the value
   supplied does not raise. Both halves, or the test proves only that something raised.
4. **The filter is keyed on the declaration, not on resolution failure.** A `bound_args`
   entry naming `instance.hardware.params.<key>` for a `<key>` no backend declares raises the
   existing unknown-binding `BindingError`, on both a `sim` and a `real` arm. This is the
   clause that separates decision 2b from a silent swallow, and it is the one most likely to
   be implemented wrongly.
5. **The validator's three answers, one test each.** A `params` key that is not a declared
   backend id is an ERROR; a parameter inside a backend block that the **named** backend does
   not declare is an ERROR naming that backend; and a block for an unselected but declared
   backend produces no finding of any severity.
6. **The shipped model is byte-identical and `./scripts/validate-model` exits 0.** Nothing in
   `workspace/src/cite_generated/` changes, because every shipped arm is `sim`. This is the
   cheapest check that the change is inert where it should be, and it is the only clause that
   would catch an implementation that emits `robot_ip=""` unconditionally.
7. **`tools/tests/test_hardware_params_unbound.py` is rewritten, keeping its positive
   control, and ADR-0040 is amended.** The rewritten file must still find the backend's
   plugin string by the same search in the same artifact, so that any silence it reports is a
   **measured** silence rather than a blind one; it must state what it now pins instead; and
   it must not be deleted. The ADR-0040 amendment is decision 4's paragraph, and it is part
   of this condition rather than a follow-up, because ADR-0048's clause 3 status sat wrong for
   eight days when a deliverable was left outside the condition that governed it.

**This is a longer condition than the one this record was proposed with**, which had four
clauses: reach on a selecting arm, absence on `sim`, raise on an unsupplied key, and the
rewrite keeping its positive control. Three were added and one strengthened, for reasons
worth stating rather than burying. Clause 4 was added because decision 2b's filter has an
implementation that satisfies every other clause and defeats the record — filter on "could
not resolve" and a typo silently vanishes. Clause 5 was added because decision 1 is a
*schema and validator* decision and the proposed condition tested none of it, which would
have promoted a record on half its own content. Clause 6 was added because it is nearly free
and it is the only clause that fails loudly if the generator emits an empty argument
everywhere. Clause 1 was strengthened from "the values reach the description" to an assertion
on the macro argument list, because a substring search over a generated file passes on a
comment.

**The condition is deliberately not split by clause**, unlike ADR-0048's. All four decisions
here are satisfied or falsified by one change to one generator and one schema; there is no
part of this that can land separately and no part that is a commitment about a component
nobody has. If the implementing change lands only some of it, this record stays `Proposed`
and its status block says which clauses were met.

## What promotion does not claim

Permanent. Not a status caveat, and not discharged by anything below the promotion condition.

- **That any physical arm has ever loaded `uf_robot_hardware/UFRobotSystemHardware`.** None
  has. No hardware exists in this project (charter §8 puts it in Phase 2.B), and every clause
  above runs against generated text.
- **That `robot_ip` has ever been resolved by a network stack**, or that any address written
  in `model/` reaches a machine. The generator's job ends at the macro argument; everything
  after it — xacro expansion, `<param>`, `substr(1)`, a socket — is untested here and mostly
  untestable without an arm.
- **That the vendor hardware interface works.** Nothing in this record is evidence about
  `uf_robot_hardware`. It is evidence that a value the facility states arrives at that
  component's declared parameter, and about nothing on the far side of it.
- **That P2 has been demonstrated for the `real` backend.** `test_only_the_plugin_differs_between_backends`
  compares two generated artifact sets; it does not compare two running cells, and no run of
  a physical cell exists to compare against.
- **That a facility's addresses are correct.** Decision 1 states plainly that an unexercised
  parameter block is undetectable. A model that validates, generates and promotes this record
  may still hold a wrong address.
