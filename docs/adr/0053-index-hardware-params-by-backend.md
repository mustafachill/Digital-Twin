# ADR-0053: Index a backend's instance parameters by backend, and bind them into the generated description

- **Status:** Proposed — **nothing in this record is implemented.** Every "will", "must" and
  "may not" below is a commitment, not a description — **and so is every sentence written in
  the present indicative.** *Decision* sections describe the tree this record asks for, not
  the tree that exists: "`_arm_view` filters the family" and "the argument is not emitted at
  all" are commitments in the present tense, because that is how a specification reads, and a
  reader landing mid-document must not take them for readings. Only *Context* describes the
  tree, and every line of it names the command that produced it. Established in this checkout
  on 2026-09-08 at `aed36c4`, by the commands in *Context*:
  - `grep -rn params tools/cite_tools/generate/` returns nothing, and
    `grep -rn params tools/cite_tools/model/resolve.py` returns nothing. **No generated
    artifact carries a `hardware.params` name or value**, on any backend.
  - `tools/tests/test_hardware_params_unbound.py` pins that property deliberately, with the
    backend's plugin string as a positive control.
  - `model/assets/types/robots/xarm5.yaml:228-249` declares
    `instance_params: [robot_ip, report_type]` for the `real` backend, and the vendor macro
    chain takes both names.
  - `HardwareSelection.params` (`tools/cite_tools/model/schema.py:1206`) is one flat
    `dict[str, str | bool | int | float]` with no index, and
    `tools/cite_tools/validate/referential.py:232` checks it against the **plant's** backend.
  - `model/facility/zones.yaml` declares `twin: {sides: single}`, so nothing in this
    repository is paired and nothing here needs pairing to be built or tested.

  **Promoted to `Accepted`** by the change that binds the parameters, with all nine of the
  clauses in *The promotion condition*, below. Every one of them is testable on a host with
  no ROS, no simulator and no physical arm, which is deliberate: there is no physical arm and
  a condition that needed one would never be met.
  **Promotion is not a claim that any physical arm has ever loaded the plugin** — see
  *What promotion does not claim*, which is a permanent clause and not a status caveat.
- **Date:** 2026-09-08
- **Deciders:** The project owner, who took decisions 1 to 4 and, on 2026-09-08, decision 2c.
  Recorded by the docs-writer agent, which verified every fact in *Context* by running the
  command beside it and corrected the framing of decision 4's consequence against what the
  tree actually does — see *Decision 4* and its note on what was proposed and what is written
  here.
  **Revised on 2026-09-08, before implementation, on an architecture review of the first
  draft.** The review reproduced the whole of *Context* independently and rejected no
  decision. What it changed: 2b's filter predicate, which as first written specified the
  silent swallow clause 4 exists to catch (see 2b); the addition of 2a's validator half; and
  three additions to the promotion condition. **These are edits to a `Proposed` draft, not
  corrections under `docs/adr/README.md`'s marker rules** — nothing was implemented against
  this record, no other record cites it, and it has never been on `main`. A marker records
  how a wrong claim survived *into use*; the review caught these before use, and the record
  says where each was wrong rather than pretending it always read this way.
- **Related:**
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md) (this record is the
  first item of its *What this record does not decide* list; its clause 1 refusal and its
  unbuilt clause 2 are what let this decision ignore pairing entirely),
  [ADR-0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md) (decision 2's
  first structural argument, its 2026-08-28 correction, and the revisit item this record
  discharges and re-frames — **the implementing change owes that record two separate changes,
  in two different marker families; clause 9 of the promotion condition names each**),
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

The implementing change hits this test three times, in this order — and the second of the
three is what forced decision 2c, so it is the one hit that decision removes again. The first
two are read from that file; the third follows from decision 1's shape.

1. **The mutation stops being a valid model.** `params: {"robot_ip": "192.168.1.100"}` is a
   flat map, and under decision 1 a `params` value is a per-backend block, so the mutation has
   to be rewritten as `params: {"real": {...}}` before anything else runs.
2. **The mutation must supply every key the selected backend declares.** Under decision 2a
   below, a declared key with no supplied value is refused. At `aed36c4` `xarm5.yaml:225`
   declares two, `[robot_ip, report_type]`, and the mutation supplies one — so at this commit
   the mutation would be refused. **Decision 2c drops `report_type` from that list**, which
   leaves `robot_ip` as the only key a `real` arm must state, and the mutation as written
   already supplies it. So this hit disappears; it is recorded because it is what forced 2c,
   and because a reader who reverts 2c gets it back.
3. **The line counts stop matching.** `arm.urdf.xacro.j2` emits one macro argument per line,
   so **one** emitted argument — `robot_ip`, after 2c — is one new line in the `real`
   description and none in the `sim` one, and `zip(..., strict=True)` raises `ValueError`
   before any assertion runs. The failure is not the readable one the test was written to
   give, and `assert len(rest) == 1` is not reached at all. **This hit does not disappear**,
   and the shape of the fix is clause 8 of the promotion condition: the added line is
   accounted for **by macro argument name**, and `strict=True` stays. Widening to
   `len(rest) <= 2`, or dropping `strict=True`, would retire the property this test exists
   for — and it is the highest-severity test in the repository by CLAUDE.md §3's ranking.

The parity test's own subject is untouched: P2's subjects are topic, action, controller,
joint and frame names, and none of them moves. What has to change is how the assertion
accounts for the descriptions' differing line counts. **It must be tightened and not
widened**, and a reviewer must check exactly that — which is why clause 8 pins the shape
rather than leaving it to the implementing change.

### `hardware.params` is already inside `MODEL_HASH`, before any change here

`cite_tools.generate.model_hash` (`tools/cite_tools/generate/__init__.py:42-61`) digests
`model_dump_json()` over **six** collections — the facility, and every zone, **type**, asset,
station and flow (`:50-58`) — and `params` is a field of `HardwareSelection`, so it enters
through the asset half. **The type half matters too**, and decision 2c is where: an edit to a
type's `instance_params` moves the hash for the same reason. Measured: two scratch models identical except that one says
`robot_ip: 203.0.113.7` and the other `203.0.113.8` hash to
`214d3050…` and `f83cf715…`. **A one-digit change to an address already moves `MODEL_HASH`
today.** Decision 3's cost is therefore a cost this repository already pays for any facility
that writes the field, not a new one this record introduces.

### The declaration is already written, with a comment saying why

`model/assets/types/robots/xarm5.yaml:228-249`:

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

`HardwareBackend.instance_params` (`tools/cite_tools/model/schema.py:458`) is therefore
already **per backend**, and has been since before pairing existed. That is the shape the
decision below follows rather than invents.

### What the schema already says about side indexing

`HardwareSelection.counterpart_backend`'s comment
(`tools/cite_tools/model/schema.py:1189-1204`) states the rule this record extends:

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
backend at `schema.py:458`, months before pairing existed. A side gets the parameters of
whatever backend it loads; nothing about which side is physical is restated, and nothing here
can disagree with `counterpart_backend` (P1).

**"Per backend" is a statement about the index, not about ownership, and the difference is
worth one sentence because the reader most likely to act on the wrong reading arrives in six
months.** `params` remains a field of `HardwareSelection` (`schema.py:1178-1206`) and is
therefore **per instance**; the backend id is a second index *inside* it. Two instances of one
backend hold different values under it, which is exactly what `robot_ip` requires. The
argument above — that `robot_ip` is a property of the UFACTORY hardware component — is true of
the component **class** and must not be read as licence to hoist `params` onto
`HardwareBackend` (`schema.py:403-458`), where the type declares it once and three arms would
share one address. That hoist would look like the same shape and would be the one thing this
decision is not.

**The address in the example above is an illustration.** `tools/tests/test_hardware_params_unbound.py`
uses `203.0.113.7` and says why in its own comment — TEST-NET-3, reserved for documentation
by RFC 5737 (verified 2026-09-08 against `https://www.rfc-editor.org/rfc/rfc5737.txt`, which
reads *"The blocks 192.0.2.0/24 (TEST-NET-1), 198.51.100.0/24 (TEST-NET-2), and
203.0.113.0/24 (TEST-NET-3) are provided for use in documentation."*). Any address written in
a document is a placeholder; the facility's real ones are written in `model/` and nowhere
else.

**The four validation rules that follow, stated so the implementer cannot read them three
ways.**

- A key of `params` that is **not a declared backend id of that type** is an ERROR, rule
  `unknown-hardware-param-backend`. This is the typo case, and it is the one thing this shape
  catches that a flat map cannot.
- A parameter name inside a backend's block that the **named** backend does not declare in
  `instance_params` is an ERROR — the existing `unexpected-hardware-param`, now resolved
  against the backend the block names rather than against the plant's.
- A parameter the **selected** backend declares and the asset does not supply is an ERROR,
  rule `missing-hardware-param`. It is the mirror of the rule above and it is decision 2a's
  reporting half; see 2a for why it lives here and not only in the generator.
- A backend block for a backend **nobody on this asset selects** is legal and inert.

**Each rule is named, because clause 5 of the promotion condition asserts against the rule
name and a finding nobody can address by name is a traceback with better formatting.**

**And the first rule has to be evaluated in front of `referential.py:230`'s skip, or it binds
three assets and is silent on twelve.** That line is `if not backends: continue`: a type
declaring no `hardware_backends` never reaches the params check at all — reproduced in
*Context*, where **12 of this model's 15 assets** are skipped there. On such a type
`params: {typo: {…}}` is unread today, and moving the check behind the same skip would leave
it unread. **The closure is taken, and it needs no new rule**: on a type with no declared
backends the set of declared backend ids is empty, so *every* key of a non-empty `params` is
already "not a declared backend id" and `unknown-hardware-param-backend` fires on it. There is
no backend id such a key could legitimately name. All the implementation owes is to run that
answer before line 230's `continue` rather than after it. It costs nothing on the shipped
model — `grep -rn "params:" model/assets/instances/` returns nothing, so no asset writes the
field at all (2026-09-08) — and it is checked by clause 5.

**The widening the fourth rule buys, and its cost, stated rather than hidden.** Today
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

`xarm5.yaml` gains **one** `bound_args` entry beside the **eight** it has (counted by loading
the model and asking the type, 2026-09-08):

```yaml
    bound_args:
      robot_ip: instance.hardware.params.robot_ip
```

**One and not two**, because decision 2c below removes `report_type` from `real`'s
`instance_params` and adds no binding for it. The family takes as many entries as a type has
parameters to bind; today's model has exactly one.

And `_binding_value` (`description.py:138-194`) gains the `instance.hardware.params.*`
family, resolved from the **selected backend's** block of `params`. "Selected" means
`asset.instance.hardware.backend` — the same quantity `_collision_args` resolves the
collision URI scheme against at `description.py:290` — and it is the plant's, because there
is one artifact set per asset. **ADR-0048 clause 2 is what makes it per-side**, and until
clause 2 is built ADR-0048 clause 1 refuses any asset whose two sides differ, so the two
sides always load the same backend and the question cannot arise. Nothing in this decision
needs pairing, and nothing in it may be read as building any part of clause 2.

Three sub-rules, each with its reason.

**2a. A declared key with no supplied value is refused — as a finding first and a raise
second.** If the selected backend's `instance_params` contains `robot_ip`, the type binds a
macro argument to `instance.hardware.params.robot_ip`, and the asset's `params` block for that
backend does not supply it, then the model is refused. Start with the generator half: it
raises, in the shape `_end_effector_drive_rate` already uses at `description.py:178-186`,
naming the type, the asset and the binding. The validator half is three paragraphs below, and
it is the half a model author meets.

The reason is the one that shape was chosen for. A connection parameter has no default that
could be right, and the failure mode of defaulting is measured rather than imagined: the
vendor's `robot_ip:=''` becomes `<param name="robot_ip">R</param>`, and
`uf_robot_system_hardware.cpp:64-73` responds with `exit(1)` inside a loaded plugin at
`on_init`. Raising at generate time moves that from the cell to a laptop.

**But a raise alone is the wrong reporting shape, and it is in the wrong layer.**
`BindingError` (`description.py:29`) is a bare `Exception` carrying no `rule` and no `where`,
and `cli._generate` catches only `PlanningConfigurationError` (`cli.py:56-61`), whose
docstring states the house rule this record is bound by: *"Carries `rule` and `where` so the
CLI can report it in the same shape as every other model problem — `error <rule> <where>` —
rather than as a raw traceback. A traceback is the right answer for a generator bug and the
wrong one for a model that says something the generator will not build."* A missing `robot_ip`
is squarely the second. Left as a `BindingError`, the promised outcome — *"a `BindingError`
from `./scripts/validate-model`"* — reaches a model author as a raw traceback that aborts the
run, so the author fixes one missing key per invocation instead of reading a report.

The layer is wrong for a second reason. The exact **inverse** of this question already lives
in `validate.referential`: `unexpected-hardware-param` (`referential.py:258-268`) fires on a
key the backend does **not** declare. "A key the backend declares and the instance does not
supply" is the same question asked the other way. Putting one half in the validator and the
other in the generator would split one question across two layers with two output shapes, and
only one of them appears in the findings report an author actually reads.

**So 2a has two halves.** The **validator** answers first: `missing-hardware-param`, listed
among decision 1's rules above, reported as
`error missing-hardware-param assets.<id>.hardware.params.<backend>.<key>` like every other
finding, non-aborting, so an author sees every missing key at once. The **generator** keeps
the raise as a **backstop**: `validate` is not the only door into `cite_tools.generate`, and a
`BindingError` is the right answer for a caller that came in another way. Clause 3 of the
promotion condition asserts both halves, and asserts the finding's shape rather than only that
something raised.

**2b. On a backend that declares no such parameter, the argument is not emitted at all.**
`sim`'s `instance_params` is `[]`, so `_arm_view` (`description.py:213-240`) filters the
family **before** resolving it. **The predicate is a union, and it must be written as one:**

> Drop an `instance.hardware.params.<key>` binding **iff** `<key>` is declared in
> `instance_params` by **some** backend of the type **and not** by the **selected** one.

A `<key>` that **no** backend declares is therefore never filtered: it falls through to
`_binding_value` and raises the existing unknown-binding `BindingError` at
`description.py:189-193`. The union costs the implementation nothing —
`asset.asset_type.hardware_backends` is already in scope in `_arm_view`, and
`ResolvedAsset.ros2_control_plugin` (`resolve.py:83-85`) reads that same map to resolve the
plugin string.

**This union is not Option B's, and the two must not be confused.** Option B takes the union
of every backend's `instance_params` and uses it as the **validator's allowlist** over a
**flat** `params` map, which is what loses the ability to say which backend a shared name
belongs to. Here the map is indexed by backend, the validator still checks each block against
the backend that block **names**, and the union appears only in the **generator's filter**,
where its job is to separate "a backend deliberately declares no such parameter" from "nobody
declares it, so this is a typo". Nothing about decision 1's validation rules is widened.

The vendor's own `robot_ip:=''` default then stands where the argument is dropped, which is
correct rather than merely tolerable, because `xarm5.ros2_control.xacro:16-28` emits no
`<param>` block whatsoever unless the plugin is the UFACTORY one.

The precedent is `_collision_args` in the same file: `return []` at line 289, emitting no
macro argument at all, with a docstring calling that emptiness load-bearing. The consequence
here is the same one: **no description, world, controller configuration or bring-up plan may
change** for the shipped, all-`sim` model, so `./scripts/validate-model` can still tell
"unchanged" from "moved". The one artifact that does move is `MODEL_HASH`, and it moves
because of decision 2c's L0 edit rather than because of anything the filter does — clause 7
draws that line and asserts it.

**Why the union form is the whole of the clause, and why a single term is the silent swallow
this decision exists to avoid.** The predicate's two terms do different jobs and both are
load-bearing. The first — *declared by some backend* — is what makes a drop **deliberate**: it
fires only on a key L0 has stated somewhere, so the generator is honouring a declaration
rather than concealing a failure. The second — *not declared by the selected backend* — is
what makes the drop **conditional** on which backend is loaded, which is the whole point of
2b.

A typo inside the family, `instance.hardware.params.robot_ipp`, fails the **first** term on
every backend: no backend declares it, so it is not dropped anywhere and it raises. **That is
why the union cannot swallow a typo — a key no backend declares fails the "declared
somewhere" term, so it is never a candidate for the filter at all.**

**A single-term predicate — "not in the selected backend's `instance_params`" — is exactly the
silent swallow.** `robot_ipp` is in neither `sim`'s `[]` nor `real`'s `[robot_ip]`, so it
would be dropped on **both** backends and would never reach `description.py:189-193`. That
one-term rule was what this clause said in its first draft, and it contradicted this
paragraph; an architecture review found the contradiction before anything was implemented
against it. An implementation that filters on "could not resolve" instead of on "some backend
declares it and the selected one does not" fails in the same direction. **Clause 4 of the
promotion condition exists to catch both**, and it is the clause most likely to be
implemented wrongly.

**2c. `report_type` leaves `real`'s `instance_params`, and no binding is added for it.**
`model/assets/types/robots/xarm5.yaml:249` becomes `instance_params: [robot_ip]`.

**This is a decision and not a consequence, and the record's first draft presented it as
one.** That draft said every `real` arm must state both `robot_ip` and `report_type`, as
though 2a forced it. Nothing in 2a forces it. What forces it is one authored line —
`report_type` appearing in `real.instance_params` — and 2a's justification does not reach that
far. *"A connection parameter has no default that could be right"* is an argument about
`robot_ip`, where it is correct: no vendor can guess an address. `report_type` has a default
the vendor states twice, `report_type:='normal'` (`xarm_device_macro.xacro:37` and
`xarm5.ros2_control.xacro:7`), and it is a fact about the vendor's reporting protocol rather
than a per-instance choice — the same category as `control.update_rate_hz`, which this project
deliberately keeps at type level (`xarm5.yaml:234`; `ControlSpec`'s docstring gives P5 as the
reason).

**What 2c buys, through 2b's own mechanism rather than through an exception to it.** With
`real.instance_params` reading `[robot_ip]`, `report_type` is declared by no backend of the
type, no `bound_args` entry names it, the union predicate never sees it, no argument is
emitted on either backend, and the vendor's `normal` stands. **Only `robot_ip` — which
genuinely has no possible default — is mandatory on a `real` arm.** Nothing special-cases
`report_type` anywhere in the generator or the validator.

**The route for a facility that ever wants a non-default report mode, weighed rather than
left to be inferred.** Two homes are available and they are not equivalent. **`fixed_args` is
the answer.** It is already documented as *"facts about the type — identical for every
instance of it"* (`xarm5.yaml:42`), a report mode is exactly that, and writing
`report_type: dev` there is a one-line type edit that reaches every instance of the type and
needs no schema field, no validator rule and no binding. Putting the name back into
`instance_params` is the other route, and it is a data change with a per-instance obligation
attached: under 2a it makes the key **mandatory on every instance that selects the backend**,
which is a cost paid by every arm for a fact that is usually not per arm. So: `fixed_args`
first, and `instance_params` only when a facility can name two instances of one type that
genuinely need different report modes. Until it can, the per-instance channel would be
carrying a per-type fact, which is the P1 shape this record is otherwise built to avoid.

**The cost, measured rather than predicted.** Removing that one line **moves `MODEL_HASH`**,
because `model_hash` digests every **type** as well as every asset
(`tools/cite_tools/generate/__init__.py:50-58`) and `instance_params` is part of the type's
dump. Measured on 2026-09-08 by loading the shipped model and a scratch copy with the line
removed: `95dbbdd9…` becomes `08986aa6…`, and of the **34** generated artifacts **exactly one
differs — `MODEL_HASH` itself**. No description, world, controller configuration or bring-up
plan moves. That is why the promotion condition asserts the generated tree's movement rather
than its stillness; see clause 7.

### 3. An IP address belongs in the hashed L0 artifact

The obvious objection is `domain_offset`'s. `tools/cite_tools/model/ids.py:184-196` refuses
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

**The second prong is answered too, and it is the one `domain_offset` calls the defect.**
That docstring refuses an absolute domain in **both** derivations, not one: from the
deployment it differs in every clone and breaks byte-identity, **and** from the model it is
identical in every clone, *"so two checkouts of one commit resolve the same domain and
discover each other, which is the defect the per-checkout derivation exists to prevent"*. For
an address, that second property is the **intended** behaviour rather than a defect, and the
reason is that there is **one arm**. Two clones of one facility model describe the same
machine at the same address; a value that differed between them would be wrong in at least
one of them. The residual hazard is real and it is a different hazard: two checkouts can
command that one arm at once. It is arbitrated by
`cite_bringup.plan.require_hardware_opt_in` (`plan.py:1207-1311`), which refuses any non-`sim`
backend on any side unless `CITE_ALLOW_HARDWARE=1` is set deliberately (`plan.py:50-51`),
and beyond that by physical procedure — **not by the value in `model/`**. A domain collision can be arbitrated by
choosing a different number; an arm collision cannot be, because there is only one arm, and
pretending otherwise is the wrong lesson to draw from `domain_offset`.

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
being unsupplied is worth exactly as much as the impossibility of supplying it.

**Supply what it asks for and `on_init` returns `SUCCESS` with an `RCLCPP_WARN`
(`joint_stop_system.cpp:141-147`) — and what it asks for is all three parameters, not
`stop_joint` alone.** `stop_joint` by itself still returns `ERROR`: `:92-99` requires finite
`stop_lower_rad` and `stop_upper_rad`, `:100-105` requires `lower < upper`, and `:110-125`
requires the named joint to declare **both** a position command interface and a position state
interface. So **three further refusals** stand between `stop_joint` and the warning, and
`mock_components::GenericSystem::on_init` runs before all four (`:71-74`). The point is
unchanged — supplying three values is no harder than supplying one, and decision 2 is about a
channel rather than about a count — but this record must not understate what the fixture
demands, because it is the sentence ADR-0040 is about to receive.

**Three other legs survive, and none of them is `on_init`.**

1. **`cite_test_hardware/test/test_unreachable.py` forbids the token in `model/` by name.**
   Four contexts may name `cite_test_hardware` — its own package, any `.md`, anything under a
   `test/` or `tests/` directory, and `docs/measurements/` — and the docstring lists what
   stays forbidden: *"a description, a world, a controller configuration, a launch file, a
   bring-up plan, the L0 model, and any non-test source file in any package."* Selecting the
   fixture requires writing its plugin class string into a type's `hardware_backends`, in
   `model/`. That guard refuses it, and it refuses it today.
2. **`cite_bringup.plan.require_hardware_opt_in` refuses any non-`sim` backend.**
   `plan.py:1145`, **read at `404bbac` and not renumbered**, tests
   `backend != SIMULATION_BACKEND`, on **every side**, so a fixture
   backend under any name fails bring-up unless the hardware opt-in environment variable is
   set deliberately. **ADR-0054 deleted that test**: the gate now refuses on
   `commands_physical_hardware`, which the type declares per backend, so a fixture backend is
   refused for what it declares rather than for not being called `sim`. The conclusion is
   unchanged and the instrument is not — read `require_hardware_opt_in`, not this number.
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
second is tested.

**Two different things are owed to ADR-0040, and they are not the same kind of change.** The
record's first draft called both an amendment. `docs/adr/README.md`'s marker table separates
them, and getting it wrong tells a reader the wrong thing about why the sentence is still
there — which is the failure clause 9 was written to prevent, one record over.

1. **The revisit item is re-framed and recorded discharged — amendment-shaped.**
   `0040:567-570` predicts *"if the L0 model ever gains a hardware-plugin selector richer than
   the backend it has today"*. The premise never happens: the selector is unchanged. The item
   should have said *"if the generator ever carries `hardware.params` into a description"*.
   Changing the trigger a revisit item states **changes a decision the record states**, so the
   route is a `## Amendment — YYYY-MM-DD` section with `**[Amended YYYY-MM-DD — …]**` beside
   the item. `Amended` is the row whose meaning is *the decision it states has been changed*,
   and that is what this is.
2. **A sentence inside ADR-0040's 2026-08-28 Correction stops being true — and it is
   explicitly not `Amended`.** `0040:463-465` reads *"this argument is inert and the `on_init`
   refusal is the one that is load-bearing"*, and `0040:231` says the same in the correction's
   body. Once the generator carries `hardware.params`, `on_init`'s refusal is conditioned on
   something a model could in principle supply, so it is no longer the leg that carries the
   weight — the paragraphs above are that argument. **No decision changes**, so `Amended` is
   the wrong row.
   **Which of the two remaining rows applies is a judgement, and this record takes
   `Overtaken` while naming the discriminator.** `Overtaken` is right if the sentence was true
   on 2026-08-28 and this change made it false — which is the reading this record takes, since
   on that date nothing could supply `stop_joint` and `on_init` was the only one of decision
   2's three mechanisms that fired unconditionally in the build everyone performs. A **second
   `## Correction`** is right instead if the implementing reviewer judges the sentence was
   already overstated when written, on the argument two paragraphs above that a conditioned
   refusal is worth only the impossibility of its condition. `README.md` records that an
   earlier correction is not exempt from being corrected, so that route exists; a second
   correction goes **above** the first. Take one, state which, and say why — do not take both.

**The implementing change must also not delete `test_unreachable.py`'s claim without replacing
it with the accurate one**, which is a third deliverable and is in clause 9 with the other
two.

## Consequences

### What this gets us

- **A `backend: real` arm generates a description carrying the address the facility states.**
  The value reaches the vendor's own macro parameter with no hand edit anywhere. **That is a
  claim about generated text and not about a connection** — see *What promotion does not
  claim*. It is a Phase 2.B prerequisite, and it is met on an untwinned zone with no pairing
  and no per-side artifacts.
- **Flipping one arm to hardware becomes a one-field edit**, which is the "mixed fleet is a
  data change" property `xarm5.yaml:224` was written for and ADR-0041 Decision 3 promised.
- **A missing connection parameter fails on a laptop instead of beside the arm** — an
  `error missing-hardware-param …` line from `./scripts/validate-model`, in the same shape as
  every other model finding, rather than an `exit(1)` from inside a loaded plugin at bring-up.
  Not a raw `BindingError`: that is the generator's backstop for a caller that bypassed the
  validator, and 2a says why the difference matters.
- **No generated description, world, controller configuration or bring-up plan changes**,
  because every shipped arm is `sim` and `sim` declares no instance parameters. The binding is
  provably inert until someone selects a backend that declares one. The single exception is
  `MODEL_HASH`, which moves on decision 2c's edit to the type — measured, and asserted as
  exactly one artifact by clause 7.
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
- **Every `real` arm must state every parameter its backend declares — and 2c makes that
  exactly one.** Decision 2a makes an unsupplied declared key a hard error, so what
  `instance_params` lists is what every instance selecting the backend is obliged to write.
  That is the reason 2c is a decision rather than a formality: after it, `xarm5`'s `real`
  backend obliges an instance to state `robot_ip` and nothing else, because `robot_ip` is the
  only one of the two with no default that could be right. The obligation is real and it is
  narrow.
- **A per-type fact now has a stated home, and it is not `instance_params`.** 2c records
  `fixed_args` as the route for a non-default `report_type`, so the next contributor who needs
  one does not reach for the per-instance channel by default. The cost of getting that wrong
  is not an error — it is an obligation silently imposed on every future instance of the type.
- **`MODEL_HASH` moves once, on 2c's L0 edit.** Measured: one artifact of 34 differs, and it
  is `MODEL_HASH`. Every L6 recording stamped before the implementing change carries the old
  value, for a change that alters no description and commands no machine differently. That is
  correct behaviour under ADR-0021 and it will still surprise somebody.
- **Work the implementing change owes**, in the order it will hit. Nothing on this list is
  optional and every item is named because leaving one outside the condition that governs it
  is how ADR-0048's clause 3 status sat wrong for eight days.
  1. **The schema change** — `HardwareSelection.params` becomes a map of backend id to the
     flat parameter block. No migration of shipped data is needed: no asset writes `params`
     at all today, verified by `grep -rn "params:" model/assets/instances/`, which returns
     nothing.
  2. **`model/schema/asset_instances.schema.json`**, whose
     `$defs.HardwareSelection.properties.params` states the old type. It is a **generated
     artifact under ADR-0021** — `tools/cite_tools/model/export.py` renders it and
     `cli.validate` counts every difference toward the exit code — so it is **regenerated by
     `cite-model schema --write`** (equivalently `./scripts/validate-model --write`) and
     **never hand-edited** (CLAUDE.md §4). Leaving it stale does more than fail clause 6: it
     **suppresses clause 7**, because `cli.py:224` runs the committed-vs-fresh check only
     `if model_resolves and not schema_problems`, so the schema difference would go red while
     the generated tree went unevaluated.
  3. **The validator rules** — `unknown-hardware-param-backend`, `unexpected-hardware-param`
     re-resolved against the named backend, and the new **`missing-hardware-param`** mirror,
     with the backend-id rule evaluated in front of `referential.py:230`'s skip.
  4. **The binding family and its union filter** in `_binding_value` and `_arm_view`.
  5. **`model/assets/types/robots/xarm5.yaml:249`** — drop `report_type` from `real`'s
     `instance_params` (decision 2c) and add the single `robot_ip` `bound_args` entry. This
     moves `MODEL_HASH`, so `workspace/src/cite_generated/MODEL_HASH` is regenerated with it.
  6. **`test_generate.py::TestSimRealParity::test_only_the_plugin_differs_between_backends`**,
     which breaks on a `ValueError` rather than an assertion for the reason in *Context*.
     **Tightened, not widened** — clause 8 pins the shape.
  7. **`tools/tests/test_hardware_params_unbound.py`** — rewritten keeping its positive
     control, **including the sentence at `:106-109`** telling its future reader that if it
     fires *"the fixture in cite_test_hardware is now expressible in L0"*, which decision 4
     establishes is not what firing means.
  8. **`workspace/src/cite_test_hardware/test/test_unreachable.py:21`** — the docstring still
     asserts *"the L0 model has no way to express one"*, which ADR-0040's own 2026-08-28
     correction already made false, and which this change makes conspicuous.
  9. **ADR-0040's two changes**, in the two marker families decision 4 names.
  10. **The nine promotion-condition tests.**

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
  does not cover it, because the argument for L0 rests on the value not being one. **Stated as
  a boundary rather than as a note, because a revisit note is worth little: this record's own
  rejection of Option B says a warning "would be read once and then never again", and that
  applies to this bullet as much as to anything.** What decisions 1 and 2 license is a
  **channel**, not a value — `instance_params` will carry whatever the next backend declares
  into a committed, hashed, version-controlled artifact, and **nothing in this repository
  guards that boundary today**. That is accepted knowingly rather than overlooked. The guard's
  shape, named here so that whoever adds the parameter that needs it does not have to invent
  it: a per-name marker on `HardwareBackend` — the same field that already declares which
  names are legal — with `validate.referential` refusing any marked name in `params`, so the
  refusal lands at `./scripts/validate-model` and the value is resolved outside L0. That
  resolution is the P5 inversion Option E was rejected for, which is exactly why it is scoped
  to marked names only and is not built pre-emptively for a parameter nobody has.
- **When the physical cell's network is actually built**, decision 3's three assumptions —
  static addressing, an isolated non-globally-routable network, and no secret — must be
  checked against it rather than assumed to have held. Any one of them failing reopens this
  decision, and the DHCP case above is only the first of the three.

## The promotion condition

Promoted to `Accepted` by the change that implements decisions 1 and 2, with **all nine** of
the following. Every clause runs on a host with no ROS, no simulator and no physical arm.

1. **The value reaches the description on a selecting arm.** With one arm on a backend whose
   `instance_params` declares a parameter and a `params` block supplying it, the generated
   description's **macro invocation** carries `robot_ip="…"` as an argument — asserted against
   the argument list, not by substring search of the file, so that a value written into a
   comment cannot pass. **One name only on the shipped type, because decision 2c leaves
   `real` declaring one**, so the clause is met a second time on a scratch model whose type
   declares two — otherwise it tests one binding and not a family, and an implementation that
   hard-codes `robot_ip` passes it.
2. **It does not reach a `sim` arm's description.** Same model, an arm on `sim`: the argument
   name does not appear in its macro invocation at all. Absence, not an empty value — and
   asserted against the argument list for the same reason as clause 1.
3. **A declared-but-unsupplied key is reported as a finding, and the generator raises as a
   backstop.** Both halves of 2a, and both halves asserted. The validator reports
   `missing-hardware-param` in the `error <rule> <where>` shape, asserted **against the rule
   name and the `where`** rather than against a message substring, and reports it without
   aborting, so a model missing two keys yields two findings. The generator, called directly,
   raises `BindingError` naming the asset and the binding. The same model with the value
   supplied does neither — without that half the test proves only that something raised.
4. **The filter is keyed on the declaration, not on resolution failure.** A `bound_args`
   entry naming `instance.hardware.params.<key>` for a `<key>` no backend declares raises the
   existing unknown-binding `BindingError`, on both a `sim` and a `real` arm. This is the
   clause that separates decision 2b from a silent swallow, and it is the one most likely to
   be implemented wrongly.
5. **The validator's four answers, one test each, asserted by rule name.**
   `unknown-hardware-param-backend` on a `params` key that is not a declared backend id;
   `unexpected-hardware-param` on a parameter inside a backend block that the **named**
   backend does not declare, with the message naming that backend; `missing-hardware-param` as
   clause 3 requires; and **no finding of any severity** for a block naming an unselected but
   declared backend. **Plus the skip**: a non-empty `params` on a type declaring no
   `hardware_backends` is an ERROR, which is the case `referential.py:230` silently passes
   today and the reason the rule is evaluated in front of that line.
6. **The schema export is regenerated and `./scripts/validate-model` exits 0.**
   `model/schema/asset_instances.schema.json` states the new type of
   `$defs.HardwareSelection.properties.params`, produced by `cite-model schema --write` and
   not by hand, so `export.differences` finds none. This clause is separate from clause 7 on
   purpose: `cli.py:224` runs the committed-vs-fresh generated check only
   `if model_resolves and not schema_problems`, so a stale export would make clause 7 pass
   vacuously by never being evaluated.
7. **The generated tree moves in exactly one artifact, and it is `MODEL_HASH`.** A diff of
   `workspace/src/cite_generated/` across the implementing change names `MODEL_HASH` and
   nothing else: no description, no world, no controller configuration, no bring-up plan.
   Every shipped arm is `sim`, so the binding must reach nothing; the hash moves because
   decision 2c edits a type, which `model_hash` digests. **This is the clause that catches an
   implementation emitting `robot_ip=""` unconditionally**, which would change all three arm
   descriptions. Asserted as "exactly this one file", not as "no file", because "no file" is
   now false and a clause nobody can satisfy is a clause nobody checks.
8. **The P2 parity test is tightened, not widened.**
   `test_generate.py::TestSimRealParity::test_only_the_plugin_differs_between_backends` must
   still fail if anything but the plugin, the collision root's URI scheme and the declared
   macro arguments differs between the two backends' descriptions. Every line the `real`
   description carries that the `sim` one does not is accounted for **by macro argument
   name** — today exactly one, `robot_ip` — and any remaining line-for-line comparison keeps
   `strict=True`. **Widening `assert len(rest) == 1` to a bound, or dropping `strict=True` to
   make the length mismatch go away, retires the "only the plugin differs" property and fails
   this clause**, whatever else passes. It is the highest-severity test in the repository by
   CLAUDE.md §3's ranking, and the reason for this clause is that every other clause in this
   condition passes without it.
9. **The two rewritten tests, and ADR-0040's two changes.**
   `tools/tests/test_hardware_params_unbound.py` is rewritten keeping its positive control:
   it must still find the backend's plugin string by the same search in the same artifact, so
   that any silence it reports is a **measured** silence rather than a blind one; it must
   state what it now pins instead; **its `:106-109` message must stop telling its reader that
   firing means "the fixture in cite_test_hardware is now expressible in L0"**, which decision
   4 establishes is not what firing means; and it must not be deleted.
   `workspace/src/cite_test_hardware/test/test_unreachable.py:21`'s docstring must stop
   asserting *"the L0 model has no way to express one"*, false since ADR-0040's 2026-08-28
   correction. And **ADR-0040 receives both** of the changes decision 4 names, each in the
   marker family named there — the revisit item `Amended`, the correction's sentence
   `Overtaken` or given a second `Correction`, and explicitly not both. All of this is part
   of the condition rather than a follow-up, because ADR-0048's clause 3 status sat wrong for
   eight days when a deliverable was left outside the condition that governed it.

**This condition grew twice, and both growths are recorded rather than smoothed into a
list.** It was **proposed with four** clauses: reach on a selecting arm, absence on `sim`,
raise on an unsupplied key, and the rewrite keeping its positive control. The first draft of
this record took it to **seven**. An architecture review of that draft took it to **nine**.

**Four to seven.** Clause 4 was added because decision 2b's filter has an implementation that
satisfies every other clause and defeats the record — filter on "could not resolve" and a typo
silently vanishes. Clause 5 was added because decision 1 is a *schema and validator* decision
and the proposed condition tested none of it, which would have promoted a record on half its
own content. What is now clause 7 was added because it is nearly free and it is the only
clause that fails loudly if the generator emits an empty argument everywhere. Clause 1 was
strengthened from "the values reach the description" to an assertion on the macro argument
list, because a substring search over a generated file passes on a comment.

**Seven to nine, and each addition closes something the seven-clause version let through.**
The old clause 6 bundled two questions — the schema export and the generated tree — and the
bundle was unsatisfiable as written *and* self-suppressing: it asserted byte-identity while
2c moves `MODEL_HASH`, and a stale export would have stopped `cli.py:224` from evaluating the
generated half at all. It is now clauses 6 and 7, one question each. **Clause 8 is the
important one.** The parity test's fix was in the owed-work list and in no clause, so a
rewrite that dropped `strict=True` or loosened the count would have satisfied all seven
clauses while retiring the "only the plugin differs" property — the highest-severity test in
the repository. Clause 9 absorbed two stale docstrings and split the ADR-0040 obligation in
two, for the reason clause 9 itself gives.

**The condition is deliberately not split by clause**, unlike ADR-0048's. All of this record's
decisions are satisfied or falsified by one change to one generator, one schema and one line
of L0; there is no part of it that can land separately and no part that is a commitment about
a component nobody has. If the implementing change lands only some of it, this record stays
`Proposed` and its status block says which clauses were met.

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
