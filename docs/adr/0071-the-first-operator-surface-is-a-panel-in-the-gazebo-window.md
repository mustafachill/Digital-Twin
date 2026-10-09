# ADR-0071: The first operator surface is a panel in the Gazebo window

- **Status:** Proposed
- **Amended 2026-10-09 by [ADR-0072](0072-the-operator-chooses-where-the-signal-goes.md):** Home and Start program carry an explicit target (simulation, real arm or twin); "at the start" is per side; the console takes a mode hold for each run and reads custody through L5 (`/cite/twin/holding`), so it no longer reads another domain for custody.
- **Amended 2026-10-09:** the panel gains **Reset view**, which returns the 3D view's camera, zoom included, to the generated starting pose through gz-gui's `/gui/move_to/pose`. It moves no robot, so it is the one control that does not depend on the console. It adds gz-transport, gz-msgs and gz-math (vendor packages) to the panel's dependencies.
- **Date:** 2026-10-08 (Decision 1–4 amended 2026-10-08 after the safety, architecture and code reviews of the first implementation)
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

1. **Server.** `cell_console` in `cite_bringup.program` serves the following on the plant domain.
   Their names are formed once by `ids.zone_scope` and emitted into the plan's `console:` block, and
   `console` is a reserved zone scope that no asset may take:
   - `StartRobot`, `ConfirmOperator` and `StopCell` (services)
   - `HomeRobot` and `RunProgram` (actions)
   - `ConsoleState` (latched; the server numbers its snapshots and never publishes an older one after a newer, so the last message is never stale). A refused request's reason is published in
     `last_error`

   The gating is enforced on the server:
   - Home is refused until Start robot has succeeded.
   - Start program is refused until the arm is known to be at the program's start (`at_start`).
     A successful Home or a completed cycle sets it; a Stop, a failure or a new Start robot clears
     it. Before cycle 1, Start program also measures the start and refuses if the arms are away.
   - `ConfirmOperator` is refused in every state except `AWAITING_OPERATOR`.
   - When a side is physical, every request is refused while the twin is in any mode other than
     SIM that the console did not enter itself.

   The console starts only when it is asked for, through `./scripts/sim --pair --console` or
   `./scripts/console`. `./scripts/program` never starts it. While a console serves the pair, the
   terminal clients (`./scripts/home` and `python3 -m cite_bringup.program`) refuse to run, and
   the console refuses while a terminal program node is on the graph. Both checks rest on DDS
   discovery, so they are advisory. An owner that the twin enforces is open-work #100. One
   sequencer, `program/cycle.py`, serves both the terminal path and the console.

   The console is a **cross-domain client**, under the carve-out ADR-0070 gave the program for
   ADR-0044 clause 3. Outside the plant domain it touches exactly two things:
   - `InitializeAsset`, and the vendor track stop, on the physical side's domain;
   - the belt command, on each simulated side's domain.

2. **Speed.** The panel preselects 1.0, the program as written, and offers lower scales. The
   lowest scale it offers is the physical floor (`minimum_speed_scale`, which the server reads from
   `required_speed_scale`). The panel sends the scale explicitly in every goal, and the server
   rejects a goal that carries none. The rule that a physical side is never moved at a *defaulted*
   scale stands: the value is one the operator sees on screen and sends.

3. **Operator go-ahead.** The terminal Enter is replaced by a confirmation in the panel. The panel
   shows the exact text in `ConsoleState.prompt`. On a physical side three requests ask for the
   go-ahead:
   - **Start robot**, because initializing may home the track and move it to its start;
   - **Home**;
   - **each program cycle**, to place the part.

   The server asks only after reading the twin mode as SIM, refuses a confirmation that arrives
   while the mode is not SIM, and reads the mode again afterwards.

4. **Stop is a software stop, not an E-stop.** It cancels the goal in flight and sends the
   existing hold (`RosCell.cancel`), and it shares the command path, so the panel labels it that
   way.
   - **What "stopped" means.** It is reported only after the cancelled goal's terminal status has
     been read and the twin has been asked back to SIM. That request is retried while the twin
     refuses it because goals are still running.
   - **During initialization.** The vendor track is stopped and the initializer's answer is
     awaited, then the track is stopped again.
   - **When the twin cannot return to SIM.** The console reports FAULT, and in that state Stop asks
     for SIM again.
   - **Gripper.** A gripper motion already in progress on the physical arm is not stopped
     (ADR-0070 item 4).
   - **No automatic homing.** After a Stop or a failure the console does not home on its own
     (ADR-0037); the operator decides the next step.

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
- A second caller of the program beside `./scripts/program`. Both callers go through one sequencer,
  `program/cycle.py`, so a check added to the cycle reaches both.
- The console holds contexts on more than one domain, as described in Decision 1. Moving
  `InitializeAsset` and the belt behind L5 endpoints would put it on one domain.
- Preselecting 1.0 makes full speed one click away on the physical arm. That is the owner's
  decision. The operator can see it on screen and change it.
- A software stop that looks like a stop button. Mislabelled, it would be mistaken for an E-stop.
  The label is part of this decision.

### What we will have to revisit
- In Phase 4, when the web HMI is designed: decide whether this panel stays as a local debug
  surface or is removed.
- When L4 gets its own package (charter §5): `program/` and the console move out of
  `cite_bringup` together.
- When an independent E-stop path is built (`cross-cutting-safety.md`): the panel may then show
  its state.
