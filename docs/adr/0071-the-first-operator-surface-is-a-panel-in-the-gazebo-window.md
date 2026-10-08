# ADR-0071: The first operator surface is a panel in the Gazebo window

- **Status:** Proposed
- **Date:** 2026-10-08
- **Deciders:** Project owner
- **Related:** [ADR-0018](0018-visualization-rviz-and-foxglove.md) (no Phase 4 HMI commitment),
  [ADR-0010](0010-typed-ros-interfaces.md), [ADR-0037](0037-classify-an-abort-before-any-recovery-motion.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md) (L7 reads L5's published state),
  [ADR-0067](0067-the-real-program-drives-the-twin-on-a-track.md),
  [ADR-0070](0070-the-physical-arm-is-cell-b-s-counterpart.md);
  [`../architecture/cross-cutting-safety.md`](../architecture/cross-cutting-safety.md) §E-stop;
  charter §5 (L7), §8 (Phase 4)

## Context

The real program now drives the physical xArm 5 and its Gazebo twin from one signal
(ADR-0070). Operating the cell is still a set of terminal commands: `./scripts/home`,
`./scripts/program`, and an Enter keypress at a terminal as the operator's go-ahead after placing
the part by hand (`cite_bringup/program/operator.py`).

The project owner decided on 2026-10-08 that the Gazebo window, which opens on the plant side,
also serves as a simple operator panel. It has these buttons: **Start robot**, **Home**,
**Start program** and **Stop**. Until Start robot succeeds, no other button can be pressed.

Fixed facts:

- There is no single "start", "home" or "run" interface. Each one is a sequence of Python calls
  in `cite_bringup.program`: `home.initialize`, `home.bring_to_start`, `steps.run`, `RosCell`
  and `operator.confirm_operator`.
- Under `sim --pair`, only the plant side opens a Gazebo window when the counterpart is
  physical. That window is on the plant's ROS domain, which is where `/cite/twin/*` is served.
- The charter puts the operator HMI in L7, in Phase 4, as a web interface. ADR-0018 makes no
  commitment to an HMI stack.
- No software path in this repository is an E-stop (`cross-cutting-safety.md`). The physical
  E-stop is the only closure.

## Options considered

### Option A — Buttons that run the scripts
The panel runs `./scripts/home` and `./scripts/program` as subprocesses. This needs the least new
code. It was not chosen for three reasons:
- The gating could only be enforced in the GUI, so the rule "nothing before Start robot" would
  live in a widget.
- Progress is available only as parsed log text, which fails P3.
- The planned Phase 4 web HMI could not reuse any of it.

### Option B — The panel calls the twin boundary directly
A gz-gui plugin calls `SetMode`, `MoveTo` and the other boundary interfaces itself. This was not
chosen because it puts the program's sequencing in C++ inside a GUI process. That would copy
`cite_bringup.program` and put the copy in a process nobody can test headlessly (P1, P6).

### Option C — A headless console server plus a thin gz-gui panel
A managed node, `cell_console`, wraps the existing program functions. It exposes typed services
and actions and publishes a latched `ConsoleState`. The state machine and its refusals are
enforced there. The Gazebo plugin only sends requests and shows `ConsoleState`.

## Decision

Option C.

1. **Server.** `cell_console` in `cite_bringup.program` serves the following, under
   `/cite/<zone>/console/` on the plant domain:
   - `StartRobot`, `ConfirmPart` and `StopCell` (services)
   - `HomeRobot` and `RunProgram` (actions)
   - `ConsoleState` (latched)

   It refuses Home and Run until Start robot has succeeded, and it refuses `ConfirmPart` in every
   state except waiting for the part.

2. **Speed.** The panel preselects 1.0, the program as written, and offers lower scales. The
   panel sends the scale explicitly in every goal, and the server rejects a goal that carries
   none. The rule that a physical side is never moved at a *defaulted* scale stands: the value is
   one the operator sees on screen and sends.

3. **Part go-ahead.** The terminal Enter is replaced by a confirmation in the panel. The server
   asks for it only after reading the twin mode as SIM. That is the same condition
   `confirm_operator` enforces today.

4. **Stop is a software stop, not an E-stop.** It cancels the goal in flight and sends the
   existing hold (`RosCell.cancel`). It shares the command path, so the panel labels it that way.
   After a Stop or a failure the console does not home on its own (ADR-0037); the operator
   decides the next step.

5. **Panel.** `cite_console_gui` is a gz-gui 8 plugin (C++ and QML) and the first L7 package. It
   holds no logic. If it hears no `ConsoleState`, it disables every button. The generated GUI
   config adds it only on the plant side of a paired zone (P1).

6. **Interim.** This panel is the first operator surface, not the Phase 4 HMI. A web HMI reuses
   the same contracts unchanged. The charter is not amended.

## Consequences

### What this gets us
- The cell can be operated from one window, and gating that a GUI bug cannot bypass.
- The console's contracts are typed, versioned and testable without a display, so CI exercises
  them.
- The Phase 4 HMI starts with a working backend.

### What this costs us
- A Qt/gz-gui C++ package. The CI container needs its build dependencies, and nothing in CI
  renders the panel itself; only the server is tested headlessly.
- A second way to run the program beside `./scripts/program`, over the same library functions.
  Any change to the program's sequence must keep both callers working.
- Preselecting 1.0 makes full speed one click away on the physical arm. That is the owner's
  decision. The operator can see it on screen and change it.
- A software stop that looks like a stop button. Mislabelled, it would be mistaken for an E-stop.
  The label is part of this decision.

### What we will have to revisit
- In Phase 4, when the web HMI is designed: decide whether this panel stays as a local debug
  surface or is removed.
- When an independent E-stop path is built (`cross-cutting-safety.md`): the panel may then show
  its state.
