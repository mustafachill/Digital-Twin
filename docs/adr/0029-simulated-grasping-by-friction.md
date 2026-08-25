# ADR-0029: Rest simulated grasping on friction, and remove the attachment plugin

- **Status:** Accepted — **decided, and the removal is not yet in the tree.** Written before
  the implementation, as CLAUDE.md §12 requires. At the time of writing
  `workspace/src/cite_simulation/src/grasp_attachment.cpp` still exists and every generated
  arm description still carries its `<plugin>` block. Read the tree, not this line, for what
  is in it today (P7).
- **Date:** 2026-08-25
- **Deciders:** Project owner, on the 84-trial friction-grasp campaign
- **Supersedes:** [ADR-0023](0023-simulated-grasping-via-attachment.md)
- **Related:** [ADR-0005](0005-ros2-control-sim-real-boundary.md),
  [ADR-0006](0006-moveit2-motion-planning.md),
  [ADR-0022](0022-gripper-as-ros2-control-controller.md),
  [ADR-0024](0024-handoff-split-between-l3-and-l4.md),
  [ADR-0027](0027-pilz-planning-pipeline.md),
  [ADR-0028](0028-convex-hull-collision-meshes.md),
  [L1](../architecture/L1-description-and-assets.md),
  [L2](../architecture/L2-control-and-hal.md),
  [cross-cutting-testing.md](../architecture/cross-cutting-testing.md)
- **Evidence:** [`docs/measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md)

## Context

[ADR-0023](0023-simulated-grasping-via-attachment.md) rejected friction grasping and chose a
contact-triggered `DetachableJoint`. It rejected friction **by inference** — no trial was run
— and its correction of 2026-08-25 then established that the attach condition it specifies
had never been implementable. That left the project holding a mechanism whose record does not
describe it, chosen over an alternative nobody had measured.

The alternative has now been measured. The campaign is published in full at
[`docs/measurements/2026-08-25-friction-grasp/`](../measurements/2026-08-25-friction-grasp/results.md):
84 trials in 8 blocks on the full `cell_a` rig, with the thresholds written and saved in
[`criteria.md`](../measurements/2026-08-25-friction-grasp/criteria.md) *before* the first
trial ran. `results.md` is the authority for every figure quoted here and the numbers are not
restated a third time (P1); what follows is only what the decision turns on.

**This is the first decision in this repository whose evidence is a published measurement
directory rather than a dated inspection.** `docs/measurements/` holds this campaign and
nothing else at the time of writing. P8 asks for a metric behind a fidelity claim; this is
what that looks like.

Four findings decide it.

1. **Friction holds the part, in position, every time it was asked to.** `trial_success`
   28/28 at the shipped `max_step_size = 0.001` (Wilson 95% lower bound 0.879), and 68/68
   across every friction configuration tested — three timesteps and three friction
   coefficients. Nothing was flung and nothing was dropped in 84 trials. These are rates over
   independent samples, not determinism claims: `CITE_PHYSICS_SEED` reaches nothing
   ([ADR-0027](0027-pilz-planning-pipeline.md)) and OMPL is unseeded
   ([ADR-0006](0006-moveit2-motion-planning.md)).
2. **Friction does not hold the part in orientation, and this is timestep-sensitive by a
   factor of 24.5.** The work-piece rotates between the jaws by up to 34.3° about the
   pad-to-pad axis while the pads themselves turn 0.14°. Median twist runs 0.71° → 9.60° →
   17.43° as `max_step_size` goes 0.002 → 0.001 → 0.0005. **The finer the timestep, the worse
   the grasp** — so refining physics for fidelity makes this worse, and coarsening it for
   real-time factor ([ADR-0028](0028-convex-hull-collision-meshes.md), Phase 3) makes the
   simulator flatter you.
3. **Two of ADR-0023's stated premises did not survive.** The friction coefficient is not the
   controlling variable and is not even monotonic across a 4× range; and "the solver's
   iteration count" is not a parameter this stack exposes — the dartsim engine plugin in
   gz-physics 7 offers a solver *type* and a collision detector, and no iteration count. The
   record names a knob that does not exist here.
4. **The plugin, as shipped, does not deliver a grasp.** The campaign's decisive control
   changed one thing — the spawned model's name, so that the plugin's `<graspable>` list
   matched in one arm of the pair and not in the other. Plugin blind: `Pick` SUCCESS 8/8.
   Plugin firing: `EXECUTION_FAILED` 8/8, while the `DetachableJoint` carried the part 0.576 m
   anyway.

Finding 4 is the one that ends the debate, and the mechanism behind it is worth stating
exactly. `closed_threshold_rad` is 0.30 rad — the L0 schema default in
`tools/cite_tools/model/schema.py`, which the end-effector type does not override, generated
into all three arms as `<closed_threshold_rad>0.3</closed_threshold_rad>` — while the pads
first meet a 50 mm part at q = 0.4056 rad. The closure gate is therefore
already open when contact occurs, so the plugin welds the part to a finger at *first pad
contact*, before any contact force develops. The jaws then close through it to 46 mm feeling
nothing, and report `stalled=false, reached_goal=true` — which
`cite_skills::gripper_is_holding` correctly reads as an empty gripper, because a gripper that
reaches its commanded width reached it through empty space. **The plugin destroys the very
evidence [ADR-0022](0022-gripper-as-ros2-control-controller.md) relies on to know that a
grasp happened.** It delivers a lift with a failed `Pick`.

The cheap repair is closed off. The threshold cannot simply be raised past contact, because
contact is at q = 0.406 and the settled stall is at q ≈ 0.409 — three milliradians apart. The
settled condition ADR-0023 specifies needs per-pad contact sensors, which the generated
description does not contain.

## Options considered

### Option A — Keep the plugin and reshape its trigger
Attach on a *settled* stall rather than on first contact. This is the option ADR-0023's own
correction sketches, and it is not a straw man: it preserves an attach/detach event that L4
could one day consume, and it keeps grasping independent of the timestep.

Rejected on cost and on evidence. It requires a per-pad `<sensor type="contact">` in the
generated description, a list of pad suffixes in the L0 end-effector type where there is one
`attach_link_suffix` today, and a `FindGraspable` that does not discard the reporting sensor's
identity — all of it to reach a condition that is bracketed by 3 mrad. That is a substantial
build against a mechanism whose measured contribution today is to turn eight successful picks
into eight failures.

### Option B — Rest simulated grasping on friction, and delete the plugin
What the cell already does whenever the plugin does not fire: the gripper closes on the part,
stalls on it, and friction holds it. Chosen. It needs no new code, it restores `Pick` to
SUCCESS, and it is what the 68 friction trials measured. Its cost is real and is recorded
under *Consequences* rather than discounted.

### Option C — Keep both mechanisms, selected per scenario
Friction for fidelity study, attachment for line-cycle tests. ADR-0023's own *revisit* clause
proposes exactly this shape in the other direction.

Rejected. ADR-0023 already lists "two mechanisms now exist for object contact … and someone
will eventually be confused about which is acting" as a cost, and the campaign is the record
of that confusion being paid for: every lift in Phase 1.C came from the plugin, and the
project believed it was watching a gripper. A second, selectable grasp mechanism reintroduces
the ambiguity while doubling what a scenario failure could mean.

## Decision

**Simulated grasping rests on friction. The contact-triggered attachment plugin is removed.**

Concretely, the removal covers the `cite_simulation` Gazebo system plugin, its generated
`<plugin>` block in all three arm descriptions, and the L0 fields that exist only to configure
it — `attach_link_suffix`, `closed_threshold_rad`, `open_threshold_rad`. The travel, linkage
and width fields in the same L0 block **stay**: the L3 skill server reads them on the
simulated *and* the physical path, and they are the same stroke described once.

Two things are the implementer's to resolve rather than this record's to dictate, named here
so they are not discovered late. `closed_threshold_rad` is not only plugin configuration —
`tools/cite_tools/validate/physical.py` derives the default-grasp-width ceiling from it, and
that rule's stated rationale is the plugin's attach condition. The rule still has a job under
friction (a commanded width the gripper reaches in free air produces no stall and therefore no
grasp), so it needs **re-deriving from the stall condition, not deleting**. And the
`<graspable>` list is generated from the facility's own work-piece models, not invented for
the plugin; what else consumes them is a question for the change, not an assumption for this
record.

Nothing above `ros2_control` changes, because nothing above it ever knew the plugin existed.
That was ADR-0023's critical property and it is preserved exactly:
[ADR-0005](0005-ros2-control-sim-real-boundary.md)'s boundary is untouched, `Grasp` still
commands `GripperCommand` on the gripper controller and nothing else, and there is no sim-only
branch in any skill.

**A scenario may assert where a part ends up. No scenario may assert how a part is oriented in
the jaws** until the debt below is closed. That restriction is the decision as much as the
deletion is.

## What ADR-0023 got right

Superseding is not being wrong throughout, and the parts that held are the parts worth
carrying.

- **Its instinct was sound.** Simulated grasping did need deliberate attention rather than a
  friction coefficient and a hope. This campaign exists because ADR-0023 made the question
  explicit enough to be measured.
- **Its central objection is upheld.** Grasping here *is* timestep-sensitive, decisively — a
  factor of 24.5 in median twist over a 4× change. ADR-0023 was right about the mechanism and
  wrong about the symptom.
- **Its costs section proved truer than it knew.** It warned that "the simulation now flatters
  us about grasping". It did, and by a wider margin than the warning imagined: its own
  correction records that every lift in Phase 1.C came from the `DetachableJoint` and that the
  fingers never closed on the work-piece at all.
- **Its rejection of Option B (a vacuum end-effector) stands** and is not reopened here.

## Open debt: orientation is not assertable today

Recorded here with its number attached so that it is discoverable by whoever meets it, rather
than rediscovered.

**The work-piece rotates between the jaws by up to 34.3°, and within a single configuration
the twist ranges 1.4°–30.1°, set by which plan the unseeded planner happens to return.** A
cube going onto a belt does not care, which is why a position-only scenario passes while this
happens.

Two pieces of work will care.

- **[ADR-0024](0024-handoff-split-between-l3-and-l4.md)'s `Transfer`.** A two-party handoff
  requires knowing *how* a part is held, not only that it is held. `Transfer` has a typed
  `.action` and no server; whoever writes that server inherits this.
- **Phase 1.D's continuous sensor-driven line.** A cycle that runs without intervention
  accumulates orientation error across stations.

Neither mechanism was ready for this: friction twists the part, and the plugin failed `Pick`
0/8. Closing the gap is work that has not started.

The campaign's other pre-registered failure belongs to the same debt. **Slip failed both
halves of its threshold** — `slip_max` exceeded 5 mm in 16 of 28 shipped-timestep trials, and
`slip_rate` was positive in every one of the 76 friction trials, so the displacement grows
through the carry and stops only when the arm stops. A 12-second carry is the only reason the
number is not larger. This is bounded well inside the 100 mm place tolerance today; it is not
bounded by anything for a longer carry.

## The candidate cause, under test and unproven

A parallel investigation reports a measured **+23.6 mm grasp-plane offset**: the pads engage
only the top 19.3 mm of a 37.5 mm pad face, entirely above the part's centre of mass. Two
forces applied above the centre of mass are a couple, and a couple rotates things. That is the
leading hypothesis for the twist, and a `debugger` is measuring whether correcting the offset
removes it.

**Stated as a hypothesis, because that is what it is.** These figures come from work in
progress and are not in the measurement record at this commit; they are unverified here, and
this record must not be cited as evidence for them. What it can be cited for is the
consequence either way:

- **If correcting the offset removes the twist**, the twist was ours, the debt above closes
  cheaply, and this ADR is not affected — friction remains the mechanism.
- **If it does not**, the twist is a limit of this simulator's contact solver, and it transfers
  to Phase 2 as a **known sim/real divergence** to be measured against hardware under
  `VALIDATED` mode rather than designed away.

Nothing in this campaign evidences that a friction grasp is mechanically sound on the physical
xArm — or that it is not. It measures the simulator. The layout is `PROVISIONAL` and the
physical scan is Phase 3.

## Consequences

### What this gets us
- **`Pick` reports the truth again.** With the plugin blind, the gripper stalls on the part
  every time, `gripper_is_holding` reads holding, and `Pick` returned SUCCESS 8/8 in the
  campaign's control pair. The L2 stall evidence stops being destroyed by an L1 weld. Whether
  `./scripts/scenario pick_and_place` then passes is for the change and its test to establish;
  that scenario fails today for reasons this record does not enumerate, and nothing here
  asserts that removing the plugin is sufficient to turn it green.
- **One mechanism for object contact instead of two**, which removes the ambiguity ADR-0023
  listed as a cost and the project then paid.
- **Code and schema get smaller**: a C++ system plugin, its tests, its generated SDF block and
  three L0 fields, all deleted rather than maintained.
- **The failure mode moves to somewhere a test can see it.** A friction grasp that fails shows
  up as a part on the floor. An attachment that fails shows up as a green scenario.

### What this costs us
- **Grasp quality is now coupled to the physics timestep**, in the unhelpful direction: better
  physics, worse grasp. Any change to `max_step_size` — and both
  [ADR-0028](0028-convex-hull-collision-meshes.md) and Phase 3 point at retuning physics for
  real-time factor — moves grasp quality with it, and must be re-measured, not assumed. This
  is exactly the coupling ADR-0023 refused, accepted here with open eyes because the
  alternative does not grasp at all.
- **Orientation and slip debt**, as above.
- **No attach/detach events.** The day L4 needs to react to a grasp it did not command, there
  is no simulator-side event to react to. ADR-0023 had already withdrawn the typed-event claim,
  so nothing that exists is lost.
- **Scenario gates rest on a rate over samples, not on a determinism guarantee.** 68/68 with a
  Wilson lower bound of 0.879 is what is known. A flaky grasp gate would be worse than no gate
  ([cross-cutting-testing.md](../architecture/cross-cutting-testing.md)), so this rate is a
  thing to keep measuring, not a result to file away.

### What we will have to revisit
- **When `max_step_size` changes for any reason.** Re-run the campaign's harness; the numbers
  above belong to 0.001.
- **When `Transfer` or the Phase 1.D line needs a known part orientation.** That is the debt
  above coming due, and the twist figure is the size of it.
- **When the grasp-plane offset result lands**, either closing the debt or promoting the twist
  to a tracked sim/real divergence.
- **In Phase 2, under `VALIDATED` mode.** Grasping remains the most likely source of sim/real
  divergence; only the reason has changed, from a weld that flatters us to a contact solver
  that twists.

## How the error survived

The same way it survived in [ADR-0022](0022-gripper-as-ros2-control-controller.md), which is
why two records here have now needed correcting: **an untested inference was written down as
settled fact, and the failure it caused was silent.**

ADR-0023 rejected friction on reasoning that sounded like domain knowledge and was never
tried. Three of its specific claims about friction are now measured false — the coefficient
does not control the outcome, the part is never flung, the solver iteration count does not
exist. None of the three was tested before it was relied upon, because a plausible sentence
about physics reads like a fact about physics.

Then the sharp part, which is the transferable lesson. **The symptom ADR-0023 predicted is one
a scenario would have caught. The symptom it produced is one a scenario would not.** It
predicted the part sliding out or being flung — a part on the floor, a red gate, a
five-minute diagnosis. What friction actually does is rotate the part between the jaws, which
a scenario asserting only position cannot see; and what the plugin it chose actually did was
weld the part to a finger, which made the cycle look correct while `Pick` failed. Both real
failures were invisible to the assertions in the tree, and the predicted, visible one never
happened.

The remedy is not to write better predictions. It is that **a claim about physical behaviour
is not a decision input until something has run.** The campaign that overturned ADR-0023's
rejection of friction took a day, on the rig that already existed, with a harness of about
1,300 lines. The same day was available before the record was written.
