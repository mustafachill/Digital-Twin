# ADR-0074: The operator console frames the 3D view

- **Status:** Accepted 2026-10-15 (owner, on merge)
- **Date:** 2026-10-14
- **Deciders:** Project owner
- **Related:** [ADR-0071](0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md) (amended here, layout only),
  [ADR-0072](0072-the-operator-chooses-where-the-signal-goes.md),
  [ADR-0073](0073-validate-in-simulation-then-run-the-twin.md),
  [ADR-0004](0004-facility-model-single-source-of-truth.md) and
  [ADR-0021](0021-generated-artifacts-are-committed.md) (the GUI config stays generated),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md); charter §5 (L7)

## Context

ADR-0071 put the operator console in the plant side's Gazebo window as one floating
380×640 card in the 3D view's top-right corner. The rest of that window is Gazebo's default
editor layout: its title toolbar, the Shapes, Lights, TransformControl, Spawn and CopyPaste
tools, and the WorldControl and WorldStats overlays.

On 2026-10-14 the project owner decided that the window as a whole should be the operator
surface. It should be a modern, corporate control center that frames the live 3D view, with
**every clickable control in a command deck at the bottom**, a dark control-room theme,
1920×1080 as the primary display, and a layout that degrades gracefully at smaller sizes.
The surface is shown to visitors as well as used by operators.

Fixed facts:

- Everything ADR-0071, ADR-0072 and ADR-0073 decide about **behaviour** is unchanged. The
  panel holds no logic. Stop is labelled "software stop, not an E-stop" and is not red. The
  target is never preselected. Confirm shows the verbatim prompt. The UI never says "safe"
  or "verified", and the validate-then-run caveat stays beside its button. There is one ROS
  context, on the plant domain. Every console button is disabled while no `ConsoleState` is
  heard.
- The GUI config is generated (`tools/cite_tools/generate/gui.py`) and never hand-edited.
- gz-gui 8.4.0 on Qt 5.15 is what the container ships. A feasibility spike on 2026-10-14
  established the following on screen, using a stand-in plugin on a light world:
  - A floating card anchored to all four edges of the "3D View" stretches with the window.
  - The card's own Pane and its full-card MouseAreas swallow mouse input over its whole
    area. Setting the card's `containmentMask` to an empty item, and disabling the card's
    own MouseAreas, lets left-drag, right-drag and wheel input in the empty middle reach the
    scene.
  - The config cannot remove gz-gui's title toolbar or maximize the window. Both can be done
    from the plugin through the main window's `QQuickWindow`.
  - `material_theme="Dark"` applies to gz-gui's remaining chrome.
  - The RTF difference was within noise on that light world. It has not been measured on
    `cell_b`.

## Options considered

### Option A — One full-window frame card, middle left empty
The existing `CellConsole` card is anchored to all four edges of the 3D view with a
transparent background. Its QML draws an opaque header, a status rail and a command deck,
and leaves the middle empty, with the mouse workaround above. There is one plugin, one ROS
context, and one QML tree that can be tested offscreen. Chosen.

### Option B — Three edge cards driven by one plugin
Header, rail and deck are separate floating cards, each anchored to one edge, sharing one
client. This avoids the mouse workaround but splits one view across three cards that
gz-gui positions independently, and the layout can no longer be tested as one tree. Kept
as the fallback if a gz-gui upgrade breaks the workaround.

### Option C — Leave gz-gui (a separate Qt application, or the Phase 4 web HMI now)
This gives full visual freedom. It was rejected by the owner on 2026-10-14. A separate
window that embeds Ogre's render window is fragile, and the web HMI is Phase 4 work
(ADR-0071 Decision 6).

## Decision

On the plant side of a paired zone, the generated GUI config makes the `CellConsole` card
fill the 3D view. The plugin hides gz-gui's title toolbar and maximizes the window, and the
panel becomes a frame with these parts:

- **Header (information only)** — the facility and zone identity; the twin mode; the
  console state; the connection health of the boundary and of each side; sim time, RTF and
  wall clock.
- **Alarm band (information only)** — shown only while there is a `last_error` or a FAULT.
- **Status rail on the right (information only)** — the robot state and step, cycle
  progress, the sides, twin fidelity and an event log, in that order of priority.
  - Twin fidelity shows "Not measured" while `DivergenceMetrics.valid` is false (P7, P8).
- **The live 3D view in the middle**, with a non-interactive label naming the current view.
- **A command deck at the bottom that holds every clickable control**, in this order:
  - the view buttons (Reset, Top, Side, Front, Follow), visually subdued;
  - target, speed and cycles;
  - Start robot, Home, Start program, and Validate then run with its caveat;
  - Stop at the far right.
  - The Confirm band appears directly above the deck.

The window's other default plugins are removed: Spawn, Shapes, Lights, TransformControl,
CopyPaste, Screenshot, EntityContextMenu, VisualizationCapabilities, SelectEntities,
WorldControl and WorldStats - every plugin outside the generator's operator-window set,
which `OPERATOR_WINDOW_PLUGINS` in `tools/tests/test_generate_world.py` holds. Sim time and
RTF move into the header.
The theme is dark. Brand colour is used for identity only, never for state. Status colours
keep ISA-101 meanings: grey when normal, colour only for the abnormal, and no flashing.

The window opens **maximized, not fullscreen**, so the desktop's title bar and close button
remain. The counterpart's window config is unchanged.

## Consequences

### What this gets us
- One coherent operator surface. Every control sits in one place, and the information is
  placed by priority.
- No editor tools for an operator to misuse, so the world cannot be edited from the operator
  window.
- The layout is one QML tree, testable offscreen at several window sizes.

### What this costs us
- The workaround relies on gz-gui internals: the card's `containmentMask`, its MouseArea
  children, and the main window's `header` property. A gz-gui upgrade can break it.
  `test_panel_in_gz_gui` loads the panel into gz-gui's real card offscreen and holds the
  pass-through and that real clicks reach Stop, and at runtime the panel undoes the
  pass-through and warns if Stop, or the question's Confirm and Cancel, would no longer take
  a press. What a real display and window manager do
  is still checked only by hand.
- The plant window under `./scripts/sim --pair` loses Gazebo's editing tools and its pause
  control. A developer who needs them runs `./scripts/sim` on its own.
- The panel takes on more to display: world stats over gz-transport, `DivergenceMetrics`,
  and an event log. That means more code in a package CI cannot render.
- Visual quality is judged on a real display, not by a test.

### What we will have to revisit
- Any gz-gui version change. Re-check the mouse pass-through and the toolbar hiding, or fall
  back to Option B.
- The Phase 4 web HMI (ADR-0071 Decision 6). This layout is its design reference, not its
  implementation.
- Measured RTF on `cell_b` with the frame, if it is ever below the existing measurements'
  conditions.
