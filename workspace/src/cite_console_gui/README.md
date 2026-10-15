# cite_console_gui

**Status: `PARTIAL`.** The panel builds; its enablement table, its connection display's
rules, its reading of the contract and of its configuration, its ROS client
(`ConsoleClient`, against a fake console and a fake twin boundary on a graph of its own), its
view buttons' camera client (`CameraClient`, against a fake `CameraTracking` on a
gz-transport partition of its own), its world-statistics client and the frame's display rules
(event log, twin fidelity, progress) are unit-tested. Its QML is instantiated offscreen and
laid out at 1920×1080, 1600×900, 1366×768 and 1280×720, and held to the frame's layout rules
(see "Tests"). What no test verifies: the panel in gz-gui's real card and window — the mouse
reaching the scene through the middle, the title toolbar hidden, the window maximized — its
look on a real display, and whether `CameraTracking` honours the presets and Follow robot as
described below.

The operator console's panel in the Gazebo window
([ADR-0071](../../../docs/adr/0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md)
decision 5), and the first L7 package. A gz-gui 8 plugin, `CellConsole`, in C++ and QML. Since
[ADR-0074](../../../docs/adr/0074-the-operator-console-frames-the-3d-view.md) it **frames the
plant's window**: the operator window is the panel around the live 3D view.

**It holds no logic.** It shows the latched `ConsoleState` that `cell_console`
(`cite_bringup.program.console`) publishes, and it sends that console's requests. Every
refusal is the console's: a button the panel enables and the console refuses costs a
refusal message and nothing else. **Nothing on it is a safety function**, including its
connection display and its Stop.

## The frame (ADR-0074)

```
HEADER       mark, "<facility> Digital Twin", "<zone> Control Center" | twin mode | console state |
             connections (boundary, each side) | sim time, RTF, local time        information only
ALARM BAND   only while the console is in FAULT or says a last error             information only
MIDDLE       the live 3D view, with a label naming the last view chosen  | STATUS RAIL (right):
             (and a view failure, when there is one)                    | robot, cycle progress,
                                                                         | sides, twin fidelity,
                                                                         | event log  (info only)
QUESTION     the console's prompt, Confirm, Cancel (Stop) - only while it asks
COMMAND DECK view buttons | target ("Select a target" / "Start robot for this target"), speed, cycles |
             Start robot, Home, Start program, Validate then run | Stop (far right, full height)
```

- **Every clickable control is in the deck** (or in the question directly above it). The
  header, the alarm band and the rail hold none, and no control takes keyboard focus: the
  surface is mouse only, so a stray key cannot send a request again. The deck never scrolls.
  The question is never taller than the room between the header (and alarm band) and the
  deck; a longer prompt scrolls inside it, with its title, Confirm and Cancel on screen.
- **The rail** fits all five cards at 1920×1080 without scrolling; it scrolls only when the
  window is shorter. The Robot card shows a step in two lines at most; the event log, which
  scrolls inside itself and takes the room left in the rail, shows each step whole.
- **Sizes.** 1920×1080 is the primary display. At 1600 wide and above the rail is 380 px and
  the view buttons carry their labels; below that the rail is 300 px and the view buttons are
  icons with a tooltip. 1280 wide is a supported size and gets that medium layout; below 1200
  wide - under every supported size - the rail's cards collapse to one-line summaries and the
  event log is hidden. Stop is anchored to the deck's right edge on its own, so at any width
  the rest of the deck runs short, never Stop.
- **The middle takes no input**, so the mouse orbits, pans and zooms the scene there. Each
  opaque part takes the presses and the wheel that land on it (`InputShield`).
- **The view label** names the view the operator last chose with a view button. A drag in the
  scene is not seen by the panel, so it names the last choice, not where the camera is.
- **Components.** `src/CellConsole.qml` is the frame; its parts are in `src/components/`
  (`Theme`, `HeaderBar`, `AlarmBand`, `StatusRail`, `StatusCard`, `ProgressRing`,
  `ConnectionPill`, `HeaderFigure`, `EventLog`, `CommandDeck`, `ViewGroup`, `SegmentedSelector`,
  `ConfirmBanner`, `StopButton` and small helpers), imported as `qrc:/CellConsole/components`
  so that none of them shadows the `CellConsole` context property.

### What it relies on in gz-gui, and the risk

The frame works around three gz-gui 8 internals, read on gz-gui 8.4.0 with Qt 5.15 and shown
in a spike on 2026-10-14 (ADR-0074). **A gz-gui upgrade can break any of them.**
`test_panel_in_gz_gui` loads the panel through `gz::gui::Application` into gz-gui's real
card and main window, headlessly, and holds all three; re-check them on a real display on any
gz-gui version change, or fall back to ADR-0074's Option B.

1. **The card swallows the mouse.** gz-gui puts the panel in a card whose `Pane` and own
   `MouseArea`s take every press over the whole card. When the panel is given its parent, the
   QML sets the card's `containmentMask` to an empty item and disables the `MouseArea`s that
   are direct children of the card's `contentItem` (`passMouseThrough` in `CellConsole.qml`).
   A parent that has no `card()` - the offscreen test's - is left alone. **Stop comes first:**
   once gz-gui's window is shown, and on every relayout, change of the card's z or the frame's
   visibility, and coming or going of the question after that, the plugin judges whether a
   press at the centre of each control that stops or answers the console reaches it - the
   deck's Stop and, while the question is shown, its Cancel (Stop) and Confirm - picking the
   item as Qt Quick 5.15 does (`pressReaches`). A control that cannot be pressed at all (its
   centre outside the window, no size) fails. While a modal popup holds every press nothing is
   judged, and the frame is judged again once it closes (`modalOverlay`). If one fails - a card
   that clipped its children would, masked, take every press - the mask and the `MouseArea`s
   are put back, a warning is printed, and the panel keeps working while the scene loses the
   mouse over the middle.
2. **The title toolbar** is the main window's `ApplicationWindow.header`. The plugin hides it
   (`frame_window` in `cell_console.cpp`), and only in gz-gui's own main window.
3. **Maximized, not fullscreen**: the plugin calls `showMaximized` on the same window, so the
   desktop's title bar and close button stay. Both 2 and 3 happen once the window that shows
   the panel is visible - on `QQuickItem::windowChanged` and `QWindow::visibleChanged`, never on
   a timer (P4). The maximize is queued: gz-gui resizes the window to the configured size
   after it adds the plugins, and a queued call runs once that is done.

### What the plant's window loses

The plant's GUI configuration leaves out every gz-gui plugin that edits the world or its run:
Spawn, Shapes, Lights, TransformControl, CopyPaste, Screenshot, the entity context menu and
its VisualizationCapabilities, WorldControl (play, pause, step) and WorldStats; and
SelectEntities, whose left-click selection left a box on the scene that nothing in this
window uses. Sim time and RTF are in the header. A developer who needs the editing tools runs `./scripts/sim` on its
own. The counterpart's window is Harmonic's default, unchanged.

## What it shows and sends

| Element | What it is |
|---|---|
| Status | `ConsoleState`: state, step, last error, physical sides (badged `PHYSICAL`) |
| At start, per side | "Simulation at start" (`plant_at_start`) and "Real arm at start" (`counterpart_at_start`), the second only when the console says that side runs (`counterpart_running`) |
| Twin mode | `TwinMode` on `TwinMode::TOPIC`, read directly from the twin boundary (ADR-0044); marked "the real arm may be commanded" whenever a physical side runs and the mode is not known to be `SIM` |
| Phase | While a validate-then-run request runs: "Validating in simulation" or "Running twin" (`ConsoleState.phase`) |
| Connections | Live, stale or absent for the twin boundary; for each side also not ready or not started (see below). Monitoring only |
| Start robot | `StartRobot`, with the selected target ([ADR-0075](../../../docs/adr/0075-start-robot-and-home-act-on-the-selected-target.md)): it starts **only that target's sides**. Simulation asks nothing and initializes nothing; Real arm and Twin ask the operator to confirm before the track may move, then initialize the real arm. Enabled while a served target is selected, started or not (see below) |
| Target | Simulation, Real arm or Twin (`ConsoleState.TARGET_*`, [ADR-0072](../../../docs/adr/0072-the-operator-chooses-where-the-signal-goes.md)); a choice not in `available_targets` is disabled and labelled "not running". **Simulation is preselected** whenever it is offered; Real arm and Twin **never** are, not even when only one is offered (see below). While none is selected the deck says "Select a target" |
| Speed | 1.0 ("Original speed") preselected, then 0.5, 0.25, 0.1. The selected scale is stated in the rail's Robot card. Where the console states a floor (`minimum_speed_scale`), the panel shows it there and says whether it applies to the selected target; for a target the console lists in `floored_targets` — and while no target is selected — choices below it are disabled and labelled "below the floor". A choice per request, not a live override |
| Home | `HomeRobot`, with the selected speed and target; enabled only when the console lists the target in `started_targets` |
| Start program | `RunProgram`, with the selected speed, target and a cycle count (at least 1); enabled only when the console lists the target in `started_targets` and in `startable_targets` |
| Validate in simulation, then run twin | `ValidateThenRun` ([ADR-0073](../../../docs/adr/0073-validate-in-simulation-then-run-the-twin.md)), with the selected speed and cycle count and **no target** (see below) |
| Confirm | `ConfirmOperator`, shown only in `AWAITING_OPERATOR`, with `prompt` verbatim; its cancel is Stop |
| Stop | `StopCell` — a software stop, **not an E-stop**, and labelled so. Always on screen, at the deck's far right |
| Progress, outcome | The goal's feedback and the last answer's detail |
| Cycle progress | A ring with the running request's cycle of cycles and step of steps, from its feedback (`RunProgress`, `progress_fraction`); for validate-then-run, per phase (phase 1 is one cycle) |
| Twin fidelity | `DivergenceMetrics` on `DivergenceMetrics::TOPIC` (STATE), per asset (`fidelity_view`): **"Not measured" and no number while a sample is not valid**; "not computed" for a field the twin marks NaN; a valid comparison of two simulations is said as an instrument test, never as a fidelity result |
| Event log | The last `EVENT_LOG_CAPACITY` changes ([`event_log.hpp`](include/cite_console_gui/event_log.hpp)) of the console's state, step or last error, newest first, timed by the panel's wall clock (`EventLog`). A display, not a record of the cell |
| Sim time, RTF | The window's own world statistics over gz transport (`WorldStatsClient`, on `world_stats_topic`); dashes until heard; "paused" when the world says so |
| Reset view, Top, Side, Front, Follow robot | Move the 3D view's camera (see below). Move no robot |

Which buttons are enabled is `enabled_for` in
[`include/cite_console_gui/enablement.hpp`](include/cite_console_gui/enablement.hpp), a pure
function with no Qt and no ROS in it, and nothing else. Before any `ConsoleState` is heard,
or once its publisher has unmatched (the subscription's matched event, not a poll), every
console button is disabled, the progress and outcome said for the console that left are
cleared, and the panel says "No console". The twin mode is not the console's and is not
cleared: `TwinMode` is the boundary's latched, published-on-change topic, so a mode cleared
then would not be heard again while the boundary stays up. It becomes "unknown" only when
`TwinMode`'s own publisher unmatches, as `TwinSides` and the heartbeat do
(`BoundaryState` in [`include/cite_console_gui/health.hpp`](include/cite_console_gui/health.hpp)).

### The target selection

The selected target is held by the plugin and settled by `settled_selection` in the same
header, so the rule is unit-tested. The panel selects **Simulation** whenever the console
offers it and nothing else is selected — on the first `ConsoleState` heard, and again
whenever a selection is dropped (ADR-0072 decision 3, amended 2026-10-15). The simulation
never routes to the physical side, so this default cannot send a signal to the real arm.
The panel **never selects Real arm or Twin itself**, not even when one of them is all that
is offered: the operator picks those (safety audit R-18), and the default never replaces a
pick that stands. An operator's pick is dropped when the console leaves (its state publisher
unmatched) and comes back, and whenever `available_targets` changes in any way; the panel
then falls back to Simulation if it is offered, and otherwise selects nothing. A console
that restarts without its publisher ever unmatching, serving the same targets, keeps the
selection — the panel cannot see that restart.

While a console is heard and no target is selected (`target_hint_shown`), Start robot, Home
and Start program are disabled and the deck says "Select a target" beside its Setup title,
in the attention colour (ISA-101), not the alarm's. Every Start robot request and every Home
and Start program goal names its target explicitly, and the console refuses one without it.

The deck follows the target (ADR-0075). Start robot starts only the selected target's sides,
and the console publishes which targets are started (`started_targets`: Start robot started
every side, and the twin calls each commandable now; a physical side that ceases to be
commandable must be started again); the panel restates no side map. Home and Start program are
enabled only for a started target. While the selected
target is served but not started (`start_hint_shown`), the deck says "Start robot for this
target" in the same place and colour as "Select a target". After starting Simulation,
selecting Twin enables Start robot again and disables Home until Twin is started; back on
Simulation, Home is offered again. Start robot stays enabled on a started target, to start it
again. Real arm and Twin may be selected before the physical track has found its zero: Start
robot is then the only request the console accepts for them, and they are not listed as started
until the twin calls the track commandable.

When the panel drops an operator's Real arm or Twin pick, its event log says so: "Target
selection dropped", with "Console changed: now Simulation" (or "now none")
(`dropped_pick_note` in [`include/cite_console_gui/selection.hpp`](include/cite_console_gui/selection.hpp)).
A display, like the rest of the log.

### Validate in simulation, then run twin

One request (ADR-0073): one cycle on the simulation alone and, only if it completed there in
the same request, the selected number of cycles on the twin with every twin gate unchanged.
The button is enabled when the console offers it (`validate_then_run_offered`), the console is
`READY` and idle, and it lists the twin in `started_targets` (Start robot succeeded for the
twin, ADR-0075) and in `startable_targets` (both arms at the program's start). It carries no target, so the
operator's target selection does not touch it; the twin's floor applies to both phases, so
it is sent only at a scale the twin accepts (`PanelSelection::may_validate_then_run`).

The panel shows the phase as "Validating in simulation" and "Running twin", and the outcome
in the console's own words. It never says "safe", "verified" or "validated for the real
cell"; a pass is "passed in simulation". No caveat text sits beside the button (ADR-0073
decision 5, amended 2026-10-15): the twin's own prompt, which the operator confirms in phase
2, says that the simulation pass is not evidence of physical safety.

### Connections

What the panel can hear on its own domain, and nothing more: it opens no other domain
(ADR-0044). `side_health` in
[`include/cite_console_gui/health.hpp`](include/cite_console_gui/health.hpp) is the rule, a
pure function, and `BoundaryState` in the same header holds what it is applied to.

- **Twin boundary:** its `TwinHeartbeat` on the plant's domain (`TwinHeartbeat::TOPIC`),
  timed on the panel's own steady clock between arrivals. Absent with no publisher or none
  heard yet; stale once the last is older than the configuration's
  `heartbeat_stale_after_s` (the physical side's deadman timeout, where one is declared);
  live otherwise.
- **Each side** (the configuration's `twin_sides`): absent while the boundary is absent or
  `TwinSides` is unheard. A side `TwinSides` does not list as running is **not started**
  (grey, normal: a plant-only deployment's counterpart) if it has never been listed since
  the panel started, and **absent** if it was and has gone. A running side is stale while
  the boundary's heartbeat is late, and **not ready** while the boundary does not list it
  as `commandable` (connected and on time, but not commandable), with `TwinSides.detail` as
  the reason; live otherwise. A running side the boundary lists as `held` is **connected,
  held - press Start robot** (normal: ADR-0076's arm until the operator starts it).
  A side `TwinSides` lists as `expected` and not running is the operator console's kept real
  arm ([ADR-0077](../../../docs/adr/0077-the-operator-console-keeps-the-physical-counterpart.md)):
  **waiting for robot** (normal) until it has run, **connecting** while its side comes up,
  **disconnected, reconnecting** (abnormal) once it ran, and **failed** (abnormal) when it is
  not retried. Freshness and readiness are kept apart: not ready is never
  shown as stale. A live physical side also shows whether the boundary lists it as
  stationary.

What it cannot show: the counterpart's own heartbeat is on the counterpart's domain, so how
fresh that side is, is the boundary's `commandable` verdict, which `TwinSides` publishes on
change and without an age. A Qt timer repaints the boundary's line; it sequences and gates
nothing.

### The view buttons

They ask the window rather than the console, and move no robot. `CameraClient`
([`include/cite_console_gui/camera_client.hpp`](include/cite_console_gui/camera_client.hpp))
calls gz-gui 8's `CameraTracking` plugin, which serves, in the same window:

- `/gui/move_to/pose` (`gz.msgs.GUICamera`): **Reset view** sends the configuration's
  `home_camera_pose`, and **Top**, **Side** and **Front** send `top_camera_pose`,
  `side_camera_pose` and `front_camera_pose`. In a perspective view zoom is the camera's
  distance, so a pose restores it.
- `/gui/follow` (`gz.msgs.StringMsg`): **Follow robot** sends the configuration's
  `follow_target`, and the view follows that rendering node until another view button is
  pressed. The target is the link that rides the arm's track, as gz-sim names its node,
  `<model>::<link>` (`picker::picker_track_carriage` in `cell_b`), not the arm's model: the
  model's root is welded to the world and the carriage moves on a prismatic joint inside
  it, so a camera following the model would never move. Every pose is preceded by an empty
  follow, which stops following; a followed camera would otherwise be put back on its target
  every frame.
- **`/gui/follow` is deprecated in gz-gui 8.4** in favour of the `/gui/track` topic
  (`gz.msgs.CameraTrack`). The panel keeps it because, in gz-gui 8.4.0's `CameraTracking`,
  `/gui/track` cannot stop following (an empty `follow_target` is ignored and
  `track_mode: NONE` leaves the current target in place), and as a topic it answers nothing.
  See [`include/cite_console_gui/camera_client.hpp`](include/cite_console_gui/camera_client.hpp).

Both names were read off the vendor's `libCameraTracking.so` (gz-gui 8). The node name
`<model>::<link>` is gz-sim 8's (`SceneManager::CreateLink`), looked up by `NodeByName` in
`CameraTracking`; it was read from their sources, and the link was checked to survive the
URDF-to-SDF conversion (the arm's base, fixed to the carriage, does not). It has not been
seen followed in a rendered window. gz-gui 8 has no
in-process event that moves the camera, so the services are the documented route. Their
names are scoped by the gz-transport partition, not the world, and the panel's node is in
the window's process, so it carries the window's `GZ_PARTITION`.

The view buttons are enabled whenever the configuration gave them what they need,
independent of the console's state and of "No console", and they never block the window:
the calls are made on a thread of their own with a bounded wait, and a press made while one
is in flight replaces the one still waiting (the latest wins; N presses during one request
send at most one more). Destroying the panel waits for the one call in flight and sends
nothing that was waiting.

## Where its names come from

- The console's seven names are the plugin's XML parameters, written into the plant's GUI
  configuration by the generator (`tools/cite_tools/generate/gui.py`) from the same function
  the plan's `console:` block is emitted from. Only the plant's window of a paired zone
  carries the plugin.
- The twin boundary's topics are `TOPIC` constants in the contract: `TwinMode::TOPIC`,
  `TwinSides::TOPIC`, `TwinHeartbeat::TOPIC`.
- The header's labels and the world's statistics topic are `facility_label` ("CITE", the
  facility's L0 id in capitals), `zone_label` ("Cell B", the zone's L0 id in words) and
  `world_stats_topic` (`/world/<zone>/stats`: the world is named for the zone), derived in
  `generate/gui.py`. `DivergenceMetrics::TOPIC` is the contract's.
- The home view is the plugin's `home_camera_pose` parameter: the same text the generator
  writes as the 3D view's `camera_pose`, rendered once (`gui_camera_pose`). The presets are
  `camera_presets`, the follow target `follow_target` and its words `follow_label`, the sides
  `twin_sides` and the stale threshold `heartbeat_stale_after_s`, all derived from L0 in the
  same file, and `world_stats_stale_after_s`, how long the header shows sim time and RTF as
  current with none heard (`WORLD_STATS_STALE_AFTER_S` there). Tests hold the installed plant
  configuration's values to those functions.

The panel builds no name.

## Colour

A dark control-room theme. Normal is grey; colour is only for the abnormal (ISA-101), and
nothing flashes: red for a `FAULT`, a refusal's "Last error" and a view failure; amber for a
stale, absent or not ready connection (a side never started is grey), for "No console" and
for a physical side that may be commanded (twin mode not known to be `SIM`); blue for the
console asking the operator to act. The brand colour (SHSU orange) is identity only - the
mark, the title's accent and the focus ring - and never says anything about the cell. Every
colour, size and duration is in one singleton, `src/components/Theme.qml`; text is WCAG AA on
its surface. Stop is dark grey, not red: red is the physical E-stop's, and Stop is not an
E-stop. Motion is limited to 150-200 ms colour transitions and the progress ring's movement;
normal is static, and nothing pulses or flashes.

Type is Open Sans, which the container ships (`fonts-open-sans`); where it is absent Qt
substitutes the default sans family. No font and no icon file is copied into the tree: the
icons are drawn in QML (`GlyphIcon`, `BrandMark`).

## How it is found and run

The package's environment hook puts its `lib` directory on `GZ_GUI_PLUGIN_PATH` when the
workspace is sourced, so nothing below L7 names it. Run it with `./scripts/console`
(the same as `./scripts/sim --pair --console`, windowed).

It joins ROS with a context of its own, on the domain the window was started on — the
plant's — and spins it on its own thread; it installs no signal handler. Every request is
asynchronous; a server that is not there is reported in the panel, never waited for.

## Tests

Besides the unit tests named above, `test_panel_qml` loads the QML from the plugin's own
resource, as gz-gui does, and fails on any QML warning. At each of 1920×1080, 1600×900,
1366×768 and 1280×720 it holds that every console and view button lies in the deck, inside the
window, unclipped and overlapping no other; that the question, shown by hand, is above the deck
and inside the window; that nothing clickable lies outside the deck and the question; that
nothing at the middle of the 3D view takes the mouse, while the header, the rail and the deck
do; that no target is selected with no console heard and 1.0 is; that Stop's label is exact;
that every console button is disabled with no console; and that no caveat text sits beside
Validate then run. With the simulation offered, it holds that Simulation is selected and Real
arm and Twin are not; without it, that nothing is selected, Start robot is disabled and "Select
a target" is shown whole in the deck just above the target selector, at every size, until the
operator picks, when it says "Start robot for this target" instead. With Simulation started,
selecting Twin enables Start robot, disables Home and Start program, and says "Start robot for
this target"; selecting Simulation again enables Home and takes the hint away (ADR-0075). Below those sizes it holds that Stop stays inside the window and
clear of every other control. With a console heard - an alarm band, the boundary and both
sides live, a divergence sample, a long step - at 1920×1080 and 1280×720 it holds that every
header pill keeps its status word and overlaps nothing, that the deck's controls stay whole and
apart, and that the Robot card's step takes two lines at most; at 1920×1080, that every rail
card fits without scrolling. It also holds that a segment always shows the plugin's
selection, never the click; that the cycles shown are the cycles sent; that no control takes
keyboard focus; that a long question never covers the header; where the layout steps down;
that Stop's subtitle never breaks inside "E-stop"; that stale world statistics are said
stale, and, through the plugin's own gz transport subscription and display timer on an
injected clock, that they turn stale past the threshold and current again on arrival; and, with a stand-in card, that a real click through the window on Stop, on the
question's Cancel (Stop) and on Confirm reaches the plugin while one in the middle of the view
reaches the scene under the card, and that the mouse pass-through is undone when any of them
would lose its press, when Stop is outside the window, and after a modal popup closes - never
while it is open. `test_panel_in_gz_gui` holds the pass-through, a real click on Stop, the
middle taken by no item of the card, the hidden toolbar and the maximize in gz-gui's own card
and window.

It also writes a picture of the frame at each size - no console, the question shown, and a
console heard - to
`CITE_PANEL_PNG_DIR` (default: `panel_png/` in the package's build directory). They are for a
person to look at, not a gate.

## How it fails

- **No console running:** "No console", every console button disabled; the view buttons and
  the connection display still work.
- **A configuration missing a name, or giving the panel one it does not read:** the panel
  says which and stays disabled. The keys it reads are `CONSOLE_KEYS` and the view keys in
  [`include/cite_console_gui/console_config.hpp`](include/cite_console_gui/console_config.hpp),
  and a test holds the installed plant configuration to them.
- **No home pose in the configuration, or one that is not six finite numbers:** every view
  button is disabled and the panel says why; the console's buttons are unaffected.
- **A preset, the follow target, the sides or the stale threshold missing or malformed:**
  the panel says which on the view line; the presets, Follow robot and the connection
  display are not shown, and Reset view still works.
- **No `CameraTracking` in the window, or a refused move or follow:** the view line says so
  ("View: nothing answered on /gui/move_to/pose ..."), never the console's outcome line; the
  next view request that succeeds clears it.
- **No twin boundary:** the connection display shows it and every side as absent.
- **No world statistics** (no world, or a `world_stats_topic` nobody publishes): sim time and
  RTF show dashes; once heard and then not for longer than `world_stats_stale_after_s`, the
  last figures are dimmed and said "stale". A configuration without the header's keys is
  said on the view's line.
- **No `DivergenceMetrics`, or none valid:** the Twin fidelity card says "Not measured".
- **A gz-gui that differs from 8.4 in the three internals above:** the scene may not get the
  mouse through the middle, or the title toolbar may stay. Where the pass-through would keep a
  press from Stop, the panel undoes it and warns; anything else it cannot tell, and says
  nothing.
- **A request that ended after a Stop:** its outcome opens "ended after a Stop request" when its
  goal was cancelled, or the console's acceptance of a Stop arrived before its result, and it
  did not complete; otherwise "refused or failed". Neither says why it ended: the console ends a
  stopped request and a faulted one alike (aborted), so the panel never calls a fault that
  raced a Stop "stopped". The console's own detail, which does say, always follows. A new
  request clears the last one's outcome, and a request's progress line is cleared when it ends.
- **A target the console does not serve:** not offered, and a goal naming one is refused by
  the console (`HomeRobot.action`, `RunProgram.action`); the panel never sends an unset one.
- **Validate then run on a deployment without the twin target:** disabled; the console
  refuses it anyway.
- **A request the console refuses:** the outcome line shows the console's detail. A
  rejected goal carries no reason to its client, so the console publishes it in its state
  as `last_error` ("refused: <reason>", the state itself unchanged), and the panel shows it
  under "Last error".
- **Every string the console sends is shown as plain text**, never as markup.
- **The panel is not a safety function.** The physical E-stop is the only closure
  (`docs/architecture/cross-cutting-safety.md`).
