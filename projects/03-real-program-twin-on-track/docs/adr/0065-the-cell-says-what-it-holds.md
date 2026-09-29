# ADR-0065: The cell says what it holds, and the simulation is told

- **Status:** Proposed (amended 2026-09-28) — the Decision below is unchanged and its promotion clauses 1, 2 and 4 are met, reported in the Measurement section. **What changed is the bar the project is measured against**: it is 0.5 mm, bound to no gate, and the ±0.1 mm it replaces compared two different quantities. See the section *Amendment — 2026-09-28: the bar is 0.5 mm, and what it is a bar on*.
- **Date:** 2026-09-28
- **Deciders:** Project owner — *"let the cell say it, go that way"*
- **Related:** [ADR-0061](0061-hold-the-box-while-the-jaws-are-shut.md) (its trigger is replaced
  by this record), [ADR-0064](0064-let-go-once-the-pads-are-clear.md),
  [ADR-0063](0063-the-drive-joint-may-not-be-clamped.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md), CLAUDE.md §3 (P1, P2, P3)

## Amendment — 2026-09-28: the bar is 0.5 mm, and what it is a bar on

**The project owner set the bar at 0.5 mm on 2026-09-28, deliberately bound to no gate.** It
replaces the ±0.1 mm below, and the sentence below stays where it is because it was right when
written.

**Why the old bar was the wrong comparison, and the error was mine to make.** ±0.1 mm is what a
real xArm 5 repeats a *taught position* to — **one machine, run to run**. What this record
measures is **two replicas at one instant**. Those are different quantities, and the options
that led the owner to pick the first as a bar on the second were written by the implementer, not
by the owner.

**What a survey of public practice found, 2026-09-28.** No published work claims, or even
measures, sub-millimetre agreement between two contact-rich simulation replicas. The one
comparable published figure is GPUSimBench's run-to-run divergence at fixed seed with
randomisation disabled: **13.9 mm** (MuJoCo Playground), **21.5 mm** (MuJoCo Warp), **114.7 mm**
(Madrona); the engines it scores at "0.00 cm" report to a precision of **0.1 mm**, so they could
not resolve this cell's worst run. And MuJoCo's own documentation states the governing physics:
*"Contact events have high Lyapunov exponents; this is a property of any rigid-body simulator
(and indeed of real-world physics)."* **Non-zero divergence between two contact-rich replicas is
the expected outcome; zero is the claim that would need evidence.**

**The band the bar sits on, nine paired runs on this configuration, one machine:**

| | |
|---|---|
| runs | 0.023, 0.048, 0.054, 0.096, 0.117, 0.199, 0.381, 0.412, 0.483 mm |
| mean | **0.201 mm** |
| standard deviation | **0.177 mm** |
| median | 0.117 mm |
| highest | **0.483 mm** |
| sideways travel during the fall | **0.000 mm**, all eighteen sides |

**0.5 mm passes nine of nine, and that is the honest limit of the claim: the highest of nine
samples is not a bound.** A tenth run may exceed it without anything having broken. The
distribution is also **bimodal** — five runs below 0.12 mm and four above 0.38 mm, with nothing
between — and **what separates the two groups is not established.** A clock-offset correlation
held on six runs and died on nine.

**This bar is bound to nothing, by decision.** No scenario, no threshold and no gate reads it;
`pick_and_place` asserts placement against `PLACE_TOLERANCE_M = 0.10`, four hundred times wider,
and L5's `DivergenceMetrics` still cannot produce a valid sample (ADR-0049). It is a stated
expectation, not a gate, and nothing in this repository may cite it as one.

## Context

**Two decisions have now been refuted by measurement in five days, and they were the same
mistake twice.** [ADR-0062](0062-the-clamp-is-modelled-end-to-end.md) stopped the drive joint at
a declared width; refuted — the paired spread went 2.418 mm to 74.68 mm.
[ADR-0064](0064-let-go-once-the-pads-are-clear.md) moved the release threshold from
`detach_margin_rad` to the window's open end; refuted by its own promotion condition, which said
it fails if a side still travels a millimetre, and two of three runs travelled 1.309 mm and
1.073 mm.

**Both were attempts to guess, from the drive joint's position, something the cell already
knows.** `cite_simulation`'s grasp-hold plugin decides on its own that a grasp has happened —
stall, plus a declared part-width window, plus proximity — and decides on its own that it is
over. Every one of those is a re-derivation of `cite_skills::gripper_is_holding`, which is the
one place this project decided that question (ADR-0052). Two thresholds in two packages
answering one question is the shape P1 exists to forbid, and it has now cost two records.

**The upstream design is not this.** Gazebo Harmonic ships its own `DetachableJoint` system,
which the community describes as the standard answer to unreliable simulated grasping, and it is
**driven by a topic**: something outside publishes, and the joint attaches or detaches.
Harmonic extended it to support re-attachment for the same reason. Our plugin uses the same
`components::DetachableJoint` and then supplies its own guesswork in place of that topic.

**And the interface this needs already exists and has never been wired.**
`cite_interfaces/msg/RobotState.msg` declares `STATE_HOLDING`, `bool gripper_holding` — its own
comment reads *"true when the end effector reports a stalled close"* — and
`string held_workpiece_id`. **Nothing publishes it and nothing consumes it**; the only
`RobotState` in `cite_skills` is MoveIt's unrelated class. That is the same shape CLAUDE.md
already records for `ConveyorState`: a typed contract designed for exactly this and left
unconnected, so the information exists in the system and is not on the wire.

## Decision

**The skill server publishes what it holds, and the simulation is told rather than left to
infer it.**

1. **L3 publishes `RobotState`** on `/cite/<zone>/<asset_id>/state`, carrying `gripper_holding`,
   `held_workpiece_id` and `active_skill`. It is filled from the values the node already
   computes — `holding_`, `custody_unknown_`, `gripper_is_holding`'s verdict — and invents no new
   judgement.
2. **A simulation-only bridge** subscribes to it and publishes attach and detach on the
   plugin's own gz-transport topics, in the shape Harmonic's `DetachableJoint` already uses. It
   is started by `simulation.launch.py` and by nothing else.
3. **The plugin stops guessing.** The stall clock, the part-width window and
   `detach_margin_rad` are no longer what triggers it. What it keeps is the question the cell
   cannot answer: **which** declared graspable is in the jaws, which is still
   `attach_radius_m` and `<graspable>`.

**This is not a simulation hack riding in L3, and the distinction is the whole of P2.** A
physical arm publishing its own custody is a thing this project wants for its own sake — the
message was declared for it — and the publisher is identical on both backends. **Only the bridge
is simulation-only, and it is absent from the hardware launch**, exactly as the grasp hold itself
already is (ADR-0061).

## Options considered

### Option A — tune the plugin's thresholds again
Rejected on evidence. Twice, measured, in ADR-0062 and ADR-0064. A third value is a third guess.

### Option B — have the bridge re-derive the grasp from `/joint_states`
Rejected. It would put `gripper_is_holding`'s judgement in a third place, which is the defect
this record is written to remove.

### Option C — have L3 publish straight to the plugin's gz-transport topic
Rejected, and it is the tempting one. It is fewer moving parts and it breaks P2 outright: the
skill server would speak a bus that exists only in simulation, so the code driving the simulated
cell would no longer be the code driving the physical one.

### Option D — the cell says what it holds, a sim-only bridge tells the simulation
Chosen.

## Consequences

### What this gets us
- **One place answers "is it holding".** `gripper_is_holding` keeps the judgement; the plugin
  stops mirroring it. That is P1 restored on a question that has cost two ADRs.
- **Attach and detach become observable events on a typed topic** (P3). Neither can be inferred
  wrongly from a log that `gz sim` block-buffers, which is what made this week's contradiction
  unresolvable with the instruments available.
- **`RobotState` gets its publisher**, which the system has wanted since it was declared.

### What this costs us
- **The plugin gains gz-transport**, which it deliberately did not have. Its header states that
  it reads only the ECM; that property goes, and the reason has to go in beside it.
- **A simulation-only node exists that must not reach the hardware path.** Nothing enforces that
  today beyond the launch file, and a guard is owed.
- **A dropped or late message changes behaviour**, where a plugin reading the ECM could not miss
  one. QoS is a decision here, not a detail (CLAUDE.md §10), and reliable-plus-transient-local is
  what a state topic of this kind needs.

### What we will have to revisit
- **Whether the ejection this week measured survives the change at all.** This record fixes
  *who decides*; it does not by itself decide *what happens at the release*. If a box still
  leaves the jaws with a sideways kick once the cell owns the timing, that is a separate
  question and it is still open.

## Measurement — 2026-09-28: the sideways push is gone, and two of three runs meet the bar

Three paired runs on this branch, one machine, `docker ps` confirmed empty before each.
Each box read at its own events, so the two worlds' clock phase cancels.

| | final spread | plant sideways | counterpart sideways |
|---|---|---|---|
| ADR-0061, the stall trigger | 1.150 / 1.116 / 1.269 mm | 0.003 / 0.003 / 1.341 mm | 0.882 / 1.257 / 0.003 mm |
| ADR-0064, a second threshold | 0.728 / 0.513 / 1.225 mm | 0.656 / 1.309 / 1.073 mm | 0.808 / 0.740 / 0.001 mm |
| **this record, told by the cell** | **0.412 / 0.048 / 0.054 mm** | **0.000 mm** | **0.000 mm** |

**Clause 1 is met and it is the load-bearing one.** It said this change is refuted if a side
still travels a millimetre during the fall. **No side travels anything at all** — six sides,
three runs, 0.000 mm. The push that both superseded records were written to chase does not
occur.

**Clause 2 is met.** Empty air `commanded 88.9 mm, reached 88.9 mm, stalled=false,
reached_goal=true -> empty`; the box `commanded 45.0 mm, reached 49.7 mm, stalled=true,
reached_goal=false -> holding`, identical on both sides and contact-determined, not modelled.
**Clause 4 is met**: both scenarios printed the bare verdict on `cell_b`, `continuous_line`
carrying 3 of 3 with three attaches and three releases against three genuine friction stalls.

**What is NOT met is the project owner's bar, which is a different bar.** It is the ±0.1 mm a
real xArm 5 repeats a taught position to, and it requires **all three** runs. Two are — 0.048 mm
and 0.054 mm. One is 0.412 mm.
**[Amended 2026-09-28 — see the Amendment section above: the bar is now 0.5 mm, and the ±0.1 mm
it replaces was a comparison between two different quantities.]**

**Where that one differs is measured, not guessed, and it is not the grasp.** Its two sides
began **2.010 s** apart in simulated time, against 0.001 s and 0.040 s for the two runs that
met the bar, and its spread is born in the grasp-and-carry phase rather than at the release —
0.180 mm at first movement, 0.392 mm by the peak, and 0.412 mm at rest, with the release adding
0.024 mm. **Three points are three points**; the correlation is stated as what it is and
attributed to nothing.

**It may be the harness rather than the cell.** The rig spawns the two boxes sequentially and
waits a fixed interval before driving the cycle, and it does not check that both have come to
rest — which is the same defect a scenario had before a settle gate was added to it. Whether
the outlier survives a two-sided settle gate is the next measurement and it touches no
production code.

## Promotion condition

1. **Three paired runs**, reported whatever they say: the final spread and the sideways travel
   of each box during its fall, against this week's 1.150 / 1.116 / 1.269 mm and against a
   sideways travel that reached 1.341 mm.
2. **The grasp is untouched.** A grasp on the box still reports `stalled=true,
   reached_goal=false`; a grasp on empty air still reports `reached_goal=true`. **If either
   fails the change is abandoned rather than patched** — ADR-0061's kill switch, unweakened.
3. **The hardware path is shown to be free of it**: a source check that the bridge is reachable
   from no launch but the simulated one.
4. `pick_and_place` and `continuous_line` pass on `cell_b`.
