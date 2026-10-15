# ADR-0075: Start robot and Home act on the selected target

- **Status:** Proposed
- **Date:** 2026-10-15
- **Deciders:** Project owner (decision of 2026-10-15: "when the target changes, Start robot
  follows it; Home, likewise, affects only the target")
- **Related:**
  - Amends [ADR-0071](0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md)
    decision 1 ("nothing before Start robot" becomes per target).
  - Amends [ADR-0072](0072-the-operator-chooses-where-the-signal-goes.md) decision 2, its review
    amendment item 4 and its 2026-10-15 amendment ("Start robot carries no target").
  - [ADR-0070](0070-the-physical-arm-is-cell-b-s-counterpart.md) (initializing the physical arm),
    [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
    [ADR-0074](0074-the-operator-console-frames-the-3d-view.md)

## Context

Today `StartRobot` carries no target. It initializes every running physical side, whatever the
operator has selected, and sets one console-wide `robot_started`. Since 2026-10-15 the panel
preselects Simulation, so an operator who sees "Simulation" and presses Start robot on a
hardware pair starts the physical arm too. The go-ahead prompt announces that the track may
move, but what the operator selected and what is commanded disagree.

Home already carries a target and initializes only the physical sides of that target, but its
go-ahead prompt says "both arms will move" whatever the target is.

There is one coupling to break. ADR-0072's review amendment item 4 offers the real arm and the
twin only once the physical track reads as on zero, and today only Start robot zeroes it. So if
Start robot followed a Simulation selection, a cold track could never become selectable.

The owner decided on 2026-10-15 that Start robot and Home act on the selected target only, and
that changing the target moves the panel's progression with it.

Fixed facts, unchanged by this ADR:
- The server never defaults a target, and refuses a goal without one.
- Simulation routes to the plant only. Start robot never leaves `SIM`.
- On a physical side, Start robot and Home still ask for the operator's go-ahead before anything
  can move (ADR-0071 decision 3).
- No homing after a Stop or failure (ADR-0037).

## Options considered

### Option A — Start robot carries the target; "started" is tracked per side
`StartRobot` gains a target. It starts only the sides of that target. The console tracks which
sides are started and publishes the targets every side of which is started. Home and Start
program need their target started. A target whose physical side runs but has not found its zero
is offered for selection and for Start robot only. Chosen.

### Option B — Keep Start robot global, gate it in the panel only
Leave the server alone and only re-enable Start robot when the target changes. The panel would
still start every running side on any target, which is the disagreement the owner asked to
remove. Rejected.

### Option C — Fold Start robot into Home
Home initializes whatever its target needs, and Start robot disappears. This changes ADR-0071's
button set and its operator flow more than asked. Rejected.

## Decision

1. **`StartRobot.srv` gains `uint8 target`** (`ConsoleState.TARGET_*`, never defaulted, refused
   when 0 or not available). Start robot starts **only the sides of its target**:
   - **Simulation:** the plant side only. Nothing is asked and no physical side is initialized.
   - **Real arm or Twin:** the console reads the twin's mode as `SIM`, asks the operator's
     go-ahead (the prompt names the arms of the target) and initializes the target's physical
     side. For Twin the plant side is started too.
   - Custody is read for the target's sides only.
2. **"Started" is per side.** `ConsoleState` gains `uint8[] started_targets`: the available
   targets every side of which is started, derived from the console's one target table, so the
   panel restates no side map. `robot_started` keeps its name and means "at least one side is
   started". A FAULT, or a new Start robot on a side, clears that side's started flag exactly as
   the console-wide flag was cleared before.
3. **Home and Start program need their target started.** A goal whose target is not in
   `started_targets` is refused, with a detail that names Start robot. Home initializes only the
   physical sides of its target (as today), and its go-ahead prompt names the target's arms
   instead of "both arms".
4. **Selection versus readiness (amends ADR-0072 review item 4).** A target is **available**
   (selectable, and accepted by Start robot) when every side it commands runs. A physical side
   that has not found its zero is not commandable: Home and Start program for a target that
   includes it are refused until Start robot has initialized it and the track reads as on zero.
   So the real arm and the twin can be selected on a cold track, and the only request they
   accept there is Start robot, which is the request that zeroes it.
5. **The panel follows the target.** Start robot is enabled while the selected target is not in
   `started_targets` (and the console is idle in `NOT_STARTED`, `READY` or `FAULT`), and also
   when it is, to allow a re-start. Home and Start program are enabled only for a started
   target. When the operator changes the target, the deck follows: for example, after starting
   Simulation, selecting Twin enables Start robot again and disables Home until Twin is started.
   The deck says "Start robot for this target" when the selection is not yet started.

The terminal path (`./scripts/home`, `./scripts/program`) does not call the console's
Start robot, and its Home behaviour is unchanged.

## Consequences

### What this gets us
- What the deck shows and what the cell does agree: a Simulation start never touches the real
  arm, and a Home moves only the arms of its target.
- A physical arm is initialized only when the operator has chosen a target that includes it.

### What this costs us
- A contract change to `StartRobot.srv` and `ConsoleState.msg`, with the interface baseline,
  the console state machine, the panel and their tests changing together.
- Per-side state replaces one flag, so there are more states to test.
- The real arm and the twin become selectable before the track has found its zero. Item 4 now
  rests on the server refusing Home and Start program for them, not on the panel hiding them.

### What we will have to revisit
- A second physical side, or a target with more than two sides.
- The Phase 4 web HMI, which must follow the same per-target rule.
