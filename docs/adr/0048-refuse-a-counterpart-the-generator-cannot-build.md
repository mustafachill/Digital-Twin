# ADR-0048: Refuse a counterpart whose backend differs from the plant's, until the generator emits per-side artifacts

- **Status:** Proposed — **nothing in this record is implemented, and nothing has ever brought
  a pair up.** Every claim below was established against the tree at `9233766` rather than
  taken from another record; the commands are in *Context*. In summary, at that commit:
  - `model/facility/zones.yaml` declares `twin.sides: single`, so nothing in this repository
    is paired.
  - **`counterpart_backend: real` validates cleanly and produces a counterpart handed the
    plant's artifacts.** Zero referential findings; 34 artifacts either way, identical file
    set; the counterpart is given `ros2_control_plugin="gz_ros2_control/GazeboSimSystem"`,
    `use_sim_time: true` and `hosted_by: simulator`.
  - **Exactly three generator sites branch on a backend, and all three read the plant's.**
    No other generator mentions a backend at all.
  - The tripwire added in 2.A — `test_pairing_a_zone_changes_nothing_but_the_bring_up_plan`
    — **cannot fire on this**, and its own docstring says so.
  - `hardware.params` has no side index either, and the counterpart's `real` backend
    parameters (`robot_ip`, `report_type`) are **not expressible on a paired zone at all**.

  Every "will" and "must" below is a commitment, not a description.

  **Promotion is split, and saying so here is deliberate.** ADR-0042 was promoted on a
  condition that read as though it covered everything and covered one class of process;
  ADR-0041 and ADR-0043 each went on saying "nothing implemented" after half of them shipped.
  A status line that names one condition for a two-clause decision earns both errors at once.
  - **Clause 1 promotes this record to `Accepted`**: the change that lands the refusal, with
    a test that a model whose two sides name different backends is refused, a test that a
    model whose sides agree is not, and a mutation check that the new rule is what refuses.
    That is testable today, on this checkout, with no pair and no hardware.
  - **Clause 2 is not promoted by that change and must not be read as promoted by it.** It is
    a commitment about a generator that does not exist. The change that lifts the refusal is
    the one that tests it, and **that change owes this record an amendment** — including to
    this status block.
  - **Clause 3 is promoted with clause 1 only if it lands with it**; if it does not, this
    block says so.
- **Date:** 2026-08-30
- **Deciders:** Docs-writer agent, on the gap
  `tools/tests/test_generate.py::TestTwinSidesAndTheGazeboPartition::test_pairing_a_zone_changes_nothing_but_the_bring_up_plan`
  records in its own docstring and explicitly declines to decide — *"Phase 2.B's owner owes
  either a refusal or a per-side artifact set ... that is an architectural decision and
  belongs in `docs/adr/`, not in a test's docstring"*. This record is that decision.
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md)
  (Decision 3, which this record narrows — see *Consequences*),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md) (its zero-Gazebo revisit item),
  [ADR-0043](0043-hold-both-sides-to-the-wall-clock.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) (clause 1, the P2 constraint
  every option here is measured against),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md) (its readiness witness),
  [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0021](0021-generated-artifacts-are-committed.md),
  [ADR-0040](0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md) (the
  `hardware.params` unreachability argument),
  [L0](../architecture/L0-facility-model.md), [L1](../architecture/L1-description-and-assets.md),
  [L2](../architecture/L2-control-and-hal.md),
  [`naming-and-namespaces.md`](../architecture/naming-and-namespaces.md),
  [`docs/measurements/2026-08-28-second-world-cost/`](../measurements/2026-08-28-second-world-cost/ANALYSIS.md),
  [`../../CLAUDE.md`](../../CLAUDE.md) §3 and §8, charter §4 (P1, P2, P5, P6, P7) and §8

## Context

### The gap, reproduced rather than quoted

The gap was found while building 2.A and written into a test's docstring. It was
**re-established against `9233766`** before anything below was decided, because a record that
takes its own premise from another document is a record nobody can check. The method: copy
`model/` to a scratch directory, set `twin.sides: pair`, write `counterpart_backend: real` on
`arm_1`, run `cite_tools.validate.referential.check` and `cite_tools.generate.generate` on
both models, and diff.

| Question | Answer at `9233766` |
|---|---|
| Does `counterpart_backend: real` on a paired zone validate? | **Yes — zero referential findings**, errors or warnings |
| How many artifacts does each side get? | **34, and the same 34** — `sorted(after) == sorted(before)` is `True` |
| Which files differ between an untwinned model and this one? | `MODEL_HASH` and `bringup/cell_a_plan.yaml`, and nothing else |
| Which `ros2_control` plugin does the counterpart load? | `gz_ros2_control/GazeboSimSystem` — the simulation plugin |
| What does its controller config say about time? | `use_sim_time: true`, for a side that has no simulator |
| What does the plan say hosts its controller manager? | `hosted_by: simulator` |
| What does the plan say the counterpart's backend is? | `counterpart_backend: real` — the one place the truth is stated |

So the model can say "this side is a physical cell" and the generator answers by handing that
side a description of a simulated one. Nothing anywhere refuses it.

The 34 is a cross-check rather than a new figure: ADR-0047's status block reached the same
count by the same method at `5c2990f`, with a `sim` counterpart. **The count does not move when
the counterpart is declared physical**, which is the finding rather than the number.

### The three sites, and all three read the plant

`grep -rn "backend\|SIMULATION_BACKEND" tools/cite_tools/generate/*.py` returns hits in
**`bringup.py` and `control.py` only**; `description.py`, `world.py`, `moveit.py`,
`planning_scene.py`, `frames.py`, `topology.py` and `package.py` do not mention a backend at
all. The third site reaches it through the resolver rather than by name.

| Site | Where | What it decides | What it reads |
|---|---|---|---|
| The hardware plugin | `ResolvedAsset.ros2_control_plugin`, `tools/cite_tools/model/resolve.py:73`, consumed at `tools/cite_tools/generate/description.py:161` | which `ros2_control` hardware component the description loads | `self.instance.hardware.backend` |
| The clock | `tools/cite_tools/generate/control.py:235-237` | `use_sim_time` in the controller configuration | `asset.instance.hardware.backend` |
| The host | `tools/cite_tools/generate/bringup.py:363-365` | `hosted_by: simulator` or `ros2_control_node` | `asset.instance.hardware.backend` |

`tools/cite_tools/model/ids.py:28-39` already names three rules turning on `SIMULATION_BACKEND`
and says a fourth statement of the string would be the P1 defect. The count is right and the
**side index is the thing missing from all three**: each reads `hardware.backend`, which
ADR-0041 Decision 3 established has no side index, and none of them has ever been asked which
side it is generating for.

### The plugin is a literal, and nothing can override it at load

This matters because it decides whether the first site can be made side-agnostic instead of
per-side. `workspace/src/cite_generated/description/cell_a_arm_1.urdf.xacro` contains
**zero `xacro:arg` declarations** (`grep -c "xacro:arg"` returns `0`); the plugin arrives as a
literal argument to the vendor macro on line 39,
`ros2_control_plugin="gz_ros2_control/GazeboSimSystem"`. There is no expansion-time knob, and
adding one would put the choice in a launch argument, which is where charter §4's P5 and
ADR-0021 both say it may not go. **A side that loads a different hardware component needs a
different file.**

### The tripwire is blind to this, and it says so

`test_pairing_a_zone_changes_nothing_but_the_bring_up_plan` asserts that pairing adds no file
and changes only the plan. It cannot fail on a divergent counterpart, and the reason is
structural rather than an oversight: with no per-side artifact set there is **no second
artifact to differ**. Its docstring states this in as many words and names what it does
protect against — reflex duplication, a generator emitting a byte-identical second world or
second controller config. That is a real property and it is worth keeping; it is simply not
this.

### The model cannot express a real counterpart either, and this is what settles the decision

Three further facts, each established the same way and none of them in the docstring:

1. **`hardware.params` has no side index.** `xarm5.yaml` declares
   `instance_params: [robot_ip, report_type]` for the `real` backend.
   `cite_tools/validate/referential.py:257-258` checks `asset.hardware.params` against
   `backends[chosen]`, where `chosen` is `hardware.backend` — the **plant's**. Writing
   `robot_ip` and `report_type` on a paired zone whose plant is `sim` produces two
   `unexpected-hardware-param` errors reading *"backend 'sim' of type 'xarm5' declares no
   parameter 'robot_ip'. Declared parameters: (none)."* So the connection parameters a real
   counterpart needs are **not expressible at all**, and the field that would hold them is a
   single map shared by both sides.
2. **`hardware.params` reaches no generated artifact.** `tools/tests/test_hardware_params_unbound.py`
   pins exactly that property, and ADR-0040's 2026-08-28 correction is why it exists. So even
   a per-side `params` would still have no route into a description.
3. **A `counterpart_backend` on a type that declares no `hardware_backends` is unchecked and
   inert.** `referential.py:228-229` skips such types, and the plan's `controller_managers`
   cover the arms only. Setting `counterpart_backend: real` on `conveyor_1` produces zero
   findings and reaches **no artifact whatsoever** — verified by generating that model and
   listing the managers, which are `arm_1`, `arm_2`, `arm_3`.

**Per-side artifacts would therefore not make 2.B a data change either.** They would replace a
tree that is obviously wrong with a tree that is plausibly wrong, which is the worse of the
two.

### What already works, and it is why clause 2 is small

Switching an *asset's* backend in an untwinned zone already does exactly the right thing, and
a test already pins it: `tools/tests/test_generate.py::TestSimRealParity::test_only_the_plugin_differs_between_backends`
asserts that with `backend: real` on `arm_1`, the controller configuration is the simulated
one with `use_sim_time: true` replaced by `false` and **nothing else**, the description differs
on lines containing `ros2_control_plugin` and **nothing else**, and `arm_2` and `arm_3` are
untouched.

So the per-asset mechanism is correct and proven. What is missing is not a mechanism; it is a
second answer per side. That is what makes clause 2 a bounded change rather than a redesign —
and it is also why building it now would be building it for a consumer nobody has.

### What P2 requires of any answer, mechanically

Charter §4's P2 and [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) clause 1 fix
both sides' names byte-identically, and `naming-and-namespaces.md` rule 2 forbids a side
namespace, a suffix or a second form of any frame id. The mechanical form of that constraint
is already in the tree. `grep -c '^def ' tools/cite_tools/model/ids.py` returns **12**, and
**exactly two of them take a side**: `partition`, which forms a Gazebo transport namespace, and
`domain_offset`, which returns an integer. **None of the nine that form a ROS name does** —
`namespace`, `interface`, `scope`, `frame`, `prefix`, `joint`, `controller`, `link` and
`controller_action` — and under any answer here, none may start. (The twelfth is
`validate_identifier`, which forms nothing.) **A file path is not a ROS name**, and that
distinction is the whole of the P2 answer below.

## Options considered

### Option A — emit per-side artifacts now, only where a side actually differs

The three sites become per-side; everything else stays shared. It honours ADR-0041 Decision
3's promise that 2.B is a data change, it is bounded, and the invariant it needs is already
written down in `test_only_the_plugin_differs_between_backends`.

**Rejected as the thing to do now, and only on timing.** Three reasons, in order of weight:

- **Nothing can test it.** No pair has ever been brought up — ADR-0041, ADR-0043, ADR-0044 and
  ADR-0047 are all `Proposed` and their pair-side clauses all unimplemented — and no hardware
  exists. Per-side artifacts for a `real` side would ship as generator output whose only
  consumer is a machine nobody has, and it would be *believed*, because it validates and looks
  finished. That is charter §4's P6 and CLAUDE.md §4's "a capability marked complete in
  documentation without a test proving it", arriving as generated bytes rather than as prose.
- **It is not sufficient anyway.** The three facts above: `hardware.params` has no side index,
  reaches no artifact, and a non-arm asset's counterpart backend is unchecked and inert. A
  per-side artifact set would produce a counterpart carrying the vendor plugin and no
  `robot_ip` — a plausible tree that fails at a physical arm instead of at validation.
- **2.A does not need it.** In a 2.A pair both sides are `sim`, because Decision 3 refuses a
  physical plant and a 2.A counterpart writes no `counterpart_backend` at all. So this option
  builds 2.B's generator before 2.A has run once, and pays for it with the shared-artifact-set
  property 2.A just established.

It is the right answer **later**, which is why it is clause 2 rather than a rejected option.

### Option B — refuse the combination until the sites are per-side

Turns a silent wrong answer into a loud refusal, at validation, on this checkout, with a test
that needs neither a pair nor a machine. It is the pattern this project already used for
`backend: real` under `sides: pair` — ADR-0041 Decision 3's own words, *"a configuration
nobody wants is cheapest to remove before anything can produce it"* — applied to a
configuration that **is** wanted and that nothing can yet produce.

**Chosen, as clause 1.** The honest cost is stated in *Consequences* and it is real: 2.B
becomes two changes rather than one.

### Option C — make the three sites side-agnostic instead of per-side

The best possible answer if it worked, and it was checked site by site rather than dismissed.

- **The plugin: no.** It is a literal in a committed xacro file with no `xacro:arg`, and the
  hardware component it selects is what `ros2_control` loads. Making it a launch argument
  moves a generated value into Python (ADR-0021, P5).
- **`use_sim_time`: no, and rejecting it is the closer call.** It could be supplied per side at
  bring-up, since the plan already states each side's backend. But the value would then live in
  the generated controller configuration *and* in a launch override, and the committed file
  would state something false about one side — a value in two places with a wrong copy, which
  is P1's failure mode with the volume turned up. It stays in the file, and the file becomes
  per-side.
- **`hosted_by`: yes.** It is a total function of a value the plan already carries — `simulator`
  when the backend is `sim`, `ros2_control_node` otherwise — so emitting it *at all* is already
  a value in two places, and emitting it per side would be that twice. **And nothing reads
  it:** `git grep -n hosted_by -- workspace/src/cite_bringup` finds the dataclass field
  (`plan.py:305`), the parser (`plan.py:840`) and two test fixtures, and
  `simulation.launch.py` never mentions it. No production path starts a `ros2_control_node`
  either — `git grep -n ros2_control_node -- workspace scripts tools tests` reaches three
  launch tests (`test_abort_classification_launch.py`, `test_gripper_deadline_launch.py`,
  `test_trajectory_constraints_launch.py`), the generator's own comment and the value it
  emits, and one package README. Nothing in the launch graph, and nothing in `scripts/`.

So the option is **partly available and is partly taken**, as clause 3. One of the three sites
never needed a side index; the other two do.

### Option D — document the hazard and leave it expressible

A warning finding, or a paragraph in the L0 document. It preserves expressibility, costs
nothing, and keeps ADR-0041 Decision 3's promise intact on paper.

**Rejected on ADR-0042's precedent, which is this repository's own scar.** That record refused
a warning in as many words — *"a warning would be read once and then never again, and what it
guards against produces no symptom"* — and this is the same shape: `./scripts/validate-model`
would still exit 0, the wrong tree would still be generated, and under ADR-0021 it would be
**committed and hashed**. A hazard note does not stop a generator.

### Option E — refuse now, and decide the shape that lifts the refusal

Chosen.

## Decision

**A model may not describe a counterpart whose backend differs from its plant's, because the
generator cannot build one. The refusal is temporary by construction: this record fixes the
shape that lifts it, and the refusal's own message names it.**

Three clauses. Clause 1 is built now; clause 2 is a commitment; clause 3 removes one of the
three sites rather than duplicating it.

### 1. Refuse a divergent counterpart at validation, now

A referential rule — **`divergent-counterpart-backend`** — refuses any asset whose
`effective_counterpart_backend` differs from its `hardware.backend`.

- **Keyed on difference, not on `real`.** The generator's defect is that the counterpart is
  handed artifacts derived from the plant's backend; it bites whenever the two differ and not
  otherwise. Keying on the literal `real` would leave a third backend to rediscover it.
- **It lives in `cite_tools.validate.referential`, not in the schema.** A cross-field equality
  is not declarative on a field, and `cite_tools/validate/__init__.py`'s own rule is that a
  constraint pydantic cannot express declaratively belongs in this package so that **the
  exported JSON Schema never claims it**. It sits beside `physical-plant-on-paired-zone`,
  which closed the other half of the same cross product.
- **Two hints, one rule.** On a paired zone: the generator would hand this side the plant's
  description, its `gz_ros2_control` plugin and `use_sim_time: true` — name the three sites and
  this record. On a `single` zone: this states a fact about a side the zone does not have.
  Both are refusals rather than warnings, for Option D's reason.
- **It does not touch anything else.** `counterpart_backend` written where it *agrees* stays
  legal and stays byte-identical to omitting it — the property
  `test_writing_the_counterpart_backend_it_already_has_changes_nothing` pins.
  `require_hardware_opt_in` is unchanged: it already reads both sides, so if the refusal is
  ever lifted for a run, the hardware gate is still in front of it.

**What this narrows, stated plainly rather than buried.** ADR-0041 Decision 3 named
`counterpart_backend: real` as the 2.B encoding and this refuses it, and
`tools/tests/test_validate_referential.py::test_a_physical_counterpart_on_a_paired_zone_is_allowed`
asserts today that it produces no findings, with the comment *"it is the encoding that must
stay expressible"*. **That comment is right about the vocabulary and wrong about the tree.**
The encoding stays the 2.B encoding and this record does not propose another; what is refused
is *generating from it* while the generator cannot honour it. The implementing change rewrites
that test to assert the refusal and corrects its comment, rather than deleting either.

### 2. The shape that lifts the refusal, decided now and built later

When the generator emits per-side artifacts, it emits them like this. This is a commitment,
and no part of it is implemented.

- **Per-side only where the content differs: the description and the controller
  configuration.** Nothing else. The world, the MoveIt configuration, the planning scene, the
  static frames, the topology and the package files contain no backend term — established by
  the grep in *Context* — so a second copy of any of them would be a byte-identical file under
  a second name, which is the reflex duplication the existing tripwire exists to catch. It
  keeps catching it.
- **The side goes in the file path and never in a name.** `description/plant/cell_a_arm_1.urdf.xacro`
  or `description/cell_a_arm_1.plant.urdf.xacro` — the spelling is not decided here; the
  constraint is. No `ids.py` name-forming function gains a side argument, no namespace, topic,
  action, service, controller, joint, frame or node name differs by one byte between the sides,
  and `naming-and-namespaces.md` is not edited. **That is the P2 answer, and it is the test the
  shape has to pass**: ADR-0044 clause 1 exists because in 2.B the physical cell must present
  what Phase 1 already addresses, and a file a launch loads is not something a consumer names.
- **The invariant is asserted, not argued.** The replacement for today's tripwire is the
  side-axis form of `test_only_the_plugin_differs_between_backends`: the counterpart's
  description equals the plant's except on lines containing `ros2_control_plugin`, and the
  counterpart's controller configuration equals the plant's except for `use_sim_time`. Any
  other difference fails. That converts "the sides carry identical names" from a rule someone
  has to remember into a diff a test takes.
- **A side that names the same backend as the plant emits one artifact, not two.** Otherwise
  every 2.A pair — where both sides are `sim` by construction — pays for 2.B with two copies of
  every description, and the shared-artifact-set property is lost to a case that does not need
  it.

### 3. `hosted_by` is derived at bring-up, not emitted, and never becomes per-side

It is a total function of the backend the plan already states per side, it is read by nothing,
and no production path starts a `ros2_control_node`. So the plan stops stating it and
`cite_bringup` derives it, in one function, from the side's own backend.

This is the one part of the gap that closes by **removing** a value rather than by adding a
side to it — and it is worth doing with clause 1 rather than with clause 2, because a field
nobody reads is at its cheapest to delete before something starts reading it.

**What it means for ADR-0047 and the bring-up plan**, which is the question that motivated
looking at it:

- **A real side's process set is different**, and that is not `hosted_by`'s doing. It starts a
  `ros2_control_node` per asset and no `gz sim`, no `parameter_bridge` and no
  `ros_gz_sim create`. Today's `simulation.launch.py` is built the other way round —
  `_simulator`, `_scene` and `_arms` all spawn into Gazebo before `_controllers` runs — so a
  hardware side needs its own launch shape. **That is owed to 2.B and is not decided here.**
- **ADR-0047's readiness witness contract survives, and the chain it terminates does not.**
  The contract is that readiness is *computed inside the side, on the side's own domain, and
  announced on that side's own standard output*. It holds for a hardware side: by ADR-0044's
  refutation of its Option D a physical cell necessarily presents a ROS graph, carrying by P2
  the identical names, with a controller manager to observe. What does not carry over is
  ADR-0047 clause 3's assumption that the witness's exit is consumed by `_gate` at
  `simulation.launch.py:1077` at the end of *that* file's chain. **The witness is portable; the
  gate chain in front of it is not**, and the change that gives a hardware side a launch owes
  the second half. ADR-0047 already lists the other half of this — that "stop the other side"
  means something different when the other side is a powered machine — under its own revisit
  section, and this record does not duplicate it.

### What each isolation means on a side that starts no simulator

Both ADR-0042's refusal and ADR-0043's requirement are per-side conditions, and both were
asked here because a real side runs no Gazebo server.

- **`GZ_PARTITION`.** `require_gz_partition(side, environ)` is already per-side and already
  binds on the environment a caller is about to hand over, so it fires only where something
  builds a Gazebo environment for that side — it does not fire on a side merely existing. What
  ADR-0042 left owed is the condition itself, and **the condition is now named: a side starts a
  Gazebo server exactly when at least one asset on that side resolves to the `sim` backend.**
  Two consequences. First, charter §8 scopes Phase 2 as one physical arm and two simulated
  ones, so the counterpart in 2.B is a **mixed** side that still starts a server; the
  zero-Gazebo case needs *every* asset on the side non-`sim`. Second, the condition is an L0
  fact that the plan does **not** currently carry: `controller_managers` covers the arms only,
  and the belts and beams that also live in the world are not in it. So making it available at
  bring-up means either emitting it per side or widening what the plan states — a choice the
  change that lifts the refusal makes, under the constraint that it is derived from L0 and
  never from a count of running processes. **The partition itself keeps being emitted for every
  side, including a `single` zone's plant**, which is ADR-0042 clause 1 unchanged: an isolation
  that appeared only when someone paired a cell would be untested on every run that does not.
  **ADR-0042's revisit item is therefore closed as to the rule and open as to the code**, and
  it cannot be tested until clause 2 exists, which is why it is not a clause of this decision.
- **`real_time_factor`.** ADR-0043 half 1 is a value in the generated world. A side that loads
  no world is not held by it and does not need to be: half 1 exists so that a side with
  headroom does not run ahead of the wall clock, and a physical cell has no such headroom —
  ADR-0043's own words, *"a real arm runs at 1.0 by definition"*. **So on a fully-hardware side
  half 1 is vacuous and half 2 is inapplicable rather than met** — a side with no simulated
  clock has no real-time factor to measure, and what ADR-0043 was buying there, a side that
  keeps wall-clock time, it has by construction. On a **mixed** side both halves apply in full
  and both are unmeasured: ADR-0043 stays `Proposed` for exactly that reason and nothing here
  changes it. What must not be inferred is that hardware makes the requirement easier — it
  removes the requirement from one side and leaves it whole on the other, which is the case
  charter §8 actually scopes.

## Consequences

### What this gets us

- **The model's expressible set equals the generator's producible set, today.** That is the
  property this repository keeps losing and re-buying: a fact that validates cleanly and
  generates a wrong artifact is the failure mode ADR-0042's correction, ADR-0041's correction
  and the wrong figures CLAUDE.md §2 records all share: each was caught by someone re-running,
  never by someone reading.
- **A refusal that can be tested on this checkout, with no pair and no hardware.** Compare
  clause 2, which cannot be tested by anything that exists.
- **One of the three sites disappears instead of doubling** (clause 3), and it disappears while
  nothing reads it.
- **The tripwire keeps meaning what it says.** With clause 1 in place no paired zone's sides
  can differ, so "pairing changes nothing but the bring-up plan" stays a true and *enforced*
  property rather than a coincidence of the committed model.
- **P2 is answered explicitly rather than by silence.** Clause 2 states where a side may appear
  — a file path — and where it may not, and gives the assertion that checks it.

### What this costs us

- **2.B is blocked on a second change, and ADR-0041 Decision 3's "2.B remains a data change"
  is narrowed.** The *model edit* is still one line, exactly as promised; what was never true
  is that the generator was ready for it. This record does not withdraw the promise, it names
  its precondition. **The dishonest version of this cost would be to say the refusal creates
  the blockage.** It does not: `hardware.params` has no side index, reaches no artifact, and
  ADR-0044 clause 4 and ADR-0047 are both unimplemented. The refusal makes a blockage that
  already existed visible at validation instead of at a physical arm.
- **An existing test is contradicted and must be rewritten**, not deleted:
  `test_a_physical_counterpart_on_a_paired_zone_is_allowed` asserts zero findings for exactly
  the configuration clause 1 refuses. Its comment is corrected rather than removed, because
  what it says about the *vocabulary* is right.
- **A second test's docstring goes stale**, and the implementing change owes it:
  `test_a_physical_counterpart_reaches_the_plan` calls the generator directly, not the
  validator, so it keeps passing — while its comment, *"Phase 2.B as a data change"*, becomes
  a claim this record narrows. A test that passes for a reason its comment no longer states is
  how a wrong claim survives; this is the same shape as the status-line errors ADR-0041 and
  ADR-0043 both corrected.
- **`hosted_by` leaving the plan is a plan-schema change**, so `cite_bringup.plan` and its
  tests move with it, and the plan is committed and hashed (ADR-0021) — the change lands a
  `cite_generated/` diff and a new `MODEL_HASH`.
- **Someone will hit the refusal on a model that would have been fine**, in the sense that they
  wrote a true fact about the facility and were told no. That is the same trade ADR-0042 and
  ADR-0041 Decision 3 each took, and the message has to be good enough to move them: it names
  the three sites, the record and the condition that lifts it.
- **Clause 2 is a commitment with no test date**, and a commitment nobody is scheduled to keep
  decays into a description. The counter-pressure is that clause 1 makes it *visible* — the
  refusal fires the day someone tries — rather than leaving the wrong tree to be discovered by
  a machine.

### What we will have to revisit

- **When the refusal is lifted**, which is the change that implements clause 2. It owes the
  tripwire's replacement, the P2 equality assertion, the two test corrections above, and an
  amendment to this record's status block.
- **When `hardware.params` needs a side index.** It is not decided here — see below — and the
  ordering is forced rather than chosen: clause 1 means a divergent counterpart cannot exist
  until clause 2 lands, so the parameters cannot be needed before then.
- **When a hardware side needs a launch.** ADR-0047's witness contract holds and its gate chain
  does not; whoever writes that launch settles the second half.
- **If a zone ever needs a side that is neither wholly `sim` nor wholly hardware in a way the
  per-asset grain cannot express.** Today it can: the backend is per (asset, side), and
  charter §8's one-physical-arm-and-two-simulated is that grain exactly.
- **If clause 3 turns out to have been load-bearing.** `hosted_by` is removed on the evidence
  that nothing reads it at `9233766`. If a consumer appears that needs the distinction, it
  derives it from the backend rather than reinstating the field.

## What this record does not decide

- **The side index for `hardware.params`, and how a backend's instance parameters reach a
  generated description at all.** Both are needed for 2.B and neither is settled. The second
  is entangled with ADR-0040's unreachability argument, which
  `tools/tests/test_hardware_params_unbound.py` pins deliberately, so it is its own decision
  and not a detail of this one.
- **The spelling of a per-side artifact path.** Clause 2 fixes the constraint and not the
  convention.
- **The launch shape of a hardware side**, and what replaces `_simulator`, `_scene` and
  `_arms` there.
- **Whether the plan gains a per-side "starts a Gazebo server" statement or states every
  asset's backend per side.** The rule is decided above; the emission is owed to the change
  that lifts the refusal.
- **Anything about L5, mirroring or the divergence metric.** Those remain ADR-0041's and
  ADR-0044's open questions, untouched here.
