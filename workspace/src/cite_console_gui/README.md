# cite_console_gui

**Status: `PARTIAL`.** The panel builds; its enablement table, its connection display's
rules, its reading of the contract and of its configuration, its ROS client
(`ConsoleClient`, against a fake console and a fake twin boundary on a graph of its own) and
its view buttons' camera client (`CameraClient`, against a fake `CameraTracking` on a
gz-transport partition of its own) are unit-tested. Nothing in CI renders it; the panel in a
window — its layout, its colours, and whether `CameraTracking` honours the presets and Follow
robot as described below — has not been verified by a test.

The operator console's panel in the Gazebo window
([ADR-0071](../../../docs/adr/0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md)
decision 5), and the first L7 package. A gz-gui 8 plugin, `CellConsole`, in C++ and QML.

**It holds no logic.** It shows the latched `ConsoleState` that `cell_console`
(`cite_bringup.program.console`) publishes, and it sends that console's requests. Every
refusal is the console's: a button the panel enables and the console refuses costs a
refusal message and nothing else. **Nothing on it is a safety function**, including its
connection display and its Stop.

## What it shows and sends

| Element | What it is |
|---|---|
| Status | `ConsoleState`: state, step, last error, physical sides (badged `PHYSICAL`) |
| At start, per side | "Simulation at start" (`plant_at_start`) and "Real arm at start" (`counterpart_at_start`), the second only when the console says that side runs (`counterpart_running`) |
| Twin mode | `TwinMode` on `TwinMode::TOPIC`, read directly from the twin boundary (ADR-0044); marked "the real arm may be commanded" whenever a physical side runs and the mode is not known to be `SIM` |
| Phase | While a validate-then-run request runs: "Validating in simulation" or "Running twin" (`ConsoleState.phase`) |
| Connections | Live, stale or absent, for the twin boundary and for each side (see below). Monitoring only |
| Start robot | `StartRobot` |
| Target | Simulation, Real arm or Twin (`ConsoleState.TARGET_*`, [ADR-0072](../../../docs/adr/0072-the-operator-chooses-where-the-signal-goes.md)); a choice not in `available_targets` is disabled and labelled "not running". **Never preselected**, not even when only one is offered (see below) |
| Speed | 1.0 ("Original speed") preselected, then 0.5, 0.25, 0.1. The selected scale is stated under the choices. Where the console states a floor (`minimum_speed_scale`), the panel shows it and says whether it applies to the selected target; for a target the console lists in `floored_targets` — and while no target is selected — choices below it are disabled and labelled "below the floor". A choice per request, not a live override |
| Home | `HomeRobot`, with the selected speed and target |
| Start program | `RunProgram`, with the selected speed, target and a cycle count (at least 1); enabled only when the console lists the target in `startable_targets` |
| Validate in simulation, then run twin | `ValidateThenRun` ([ADR-0073](../../../docs/adr/0073-validate-in-simulation-then-run-the-twin.md)), with the selected speed and cycle count and **no target** (see below) |
| Confirm | `ConfirmOperator`, shown only in `AWAITING_OPERATOR`, with `prompt` verbatim; its cancel is Stop |
| Stop | `StopCell` — a software stop, **not an E-stop**, and labelled so. Always on screen, below the scrolled body |
| Progress, outcome | The goal's feedback and the last answer's detail |
| Reset view, Top, Side, Front, Follow robot | Move the 3D view's camera (see below). Move no robot |

Which buttons are enabled is `enabled_for` in
[`include/cite_console_gui/enablement.hpp`](include/cite_console_gui/enablement.hpp), a pure
function with no Qt and no ROS in it, and nothing else. Before any `ConsoleState` is heard,
or once its publisher has unmatched (the subscription's matched event, not a poll), every
console button is disabled, the twin mode, progress and outcome said for the console that
left are cleared, and the panel says "No console".

### The target selection

The selected target is held by the plugin and settled by `settled_selection` in the same
header, so the rule is unit-tested. The panel **never selects a target itself**, not even
the only one a plant-only deployment offers: the operator always picks (ADR-0072 decision 3,
safety audit R-18). The selection is cleared to none when the panel loads, when the console
leaves (its state publisher unmatched) and comes back, and whenever `available_targets`
changes in any way; Home and Start program stay disabled until the operator picks again. A
console that restarts without its publisher ever unmatching, serving the same targets,
keeps the selection — the panel cannot see that restart.

### Validate in simulation, then run twin

One request (ADR-0073): one cycle on the simulation alone and, only if it completed there in
the same request, the selected number of cycles on the twin with every twin gate unchanged.
The button is enabled when the console offers it (`validate_then_run_offered`), Start robot
has succeeded, the console is `READY` and idle, and the console lists the twin in
`startable_targets` (both arms at the program's start). It carries no target, so the
operator's target selection does not touch it; the twin's floor applies to both phases, so
it is sent only at a scale the twin accepts (`PanelSelection::may_validate_then_run`).

The panel shows the phase as "Validating in simulation" and "Running twin", and the outcome
in the console's own words. It never says "safe", "verified" or "validated for the real
cell": beside the button it states that passing in simulation is not evidence that the real
arm's cycle is safe (ADR-0073 decision 5).

### Connections

What the panel can hear on its own domain, and nothing more: it opens no other domain
(ADR-0044). `side_health` in
[`include/cite_console_gui/health.hpp`](include/cite_console_gui/health.hpp) is the rule, a
pure function.

- **Twin boundary:** its `TwinHeartbeat` on the plant's domain (`TwinHeartbeat::TOPIC`),
  timed on the panel's own steady clock between arrivals. Absent with no publisher or none
  heard yet; stale once the last is older than the configuration's
  `heartbeat_stale_after_s` (the physical side's deadman timeout, where one is declared);
  live otherwise.
- **Each side** (the configuration's `twin_sides`): absent while the boundary is absent,
  `TwinSides` is unheard, or the side is not running; stale while the boundary's heartbeat
  is late or the boundary does not list the side as `commandable`, with `TwinSides.detail`
  as the reason; live otherwise. A live physical side also shows whether the boundary lists
  it as stationary.

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
  `follow_model`, and the view follows that model until another view button is pressed.
  Every pose is preceded by an empty follow, which stops following; a followed camera would
  otherwise be put back on the model every frame.

Both names were read off the vendor's `libCameraTracking.so` (gz-gui 8). gz-gui 8 has no
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
- The home view is the plugin's `home_camera_pose` parameter: the same text the generator
  writes as the 3D view's `camera_pose`, rendered once (`gui_camera_pose`). The presets are
  `camera_presets`, the follow model `follow_model`, the sides `twin_sides` and the stale
  threshold `heartbeat_stale_after_s`, all derived from L0 in the same file. Tests hold the
  installed plant configuration's values to those functions.

The panel builds no name.

## Colour

Normal is grey; colour is only for the abnormal (ISA-101): red for a `FAULT`, a refusal's
"Last error" and a view failure; orange for a stale or absent connection and for a physical
side that may be commanded (twin mode not known to be `SIM`); blue for the console asking
the operator to act. Every colour is in the QML's one `theme` object. Stop is dark grey, not
red: red is the physical E-stop's, and Stop is not an E-stop.

## How it is found and run

The package's environment hook puts its `lib` directory on `GZ_GUI_PLUGIN_PATH` when the
workspace is sourced, so nothing below L7 names it. Run it with `./scripts/console`
(the same as `./scripts/sim --pair --console`, windowed).

It joins ROS with a context of its own, on the domain the window was started on — the
plant's — and spins it on its own thread; it installs no signal handler. Every request is
asynchronous; a server that is not there is reported in the panel, never waited for.

## How it fails

- **No console running:** "No console", every console button disabled; the view buttons and
  the connection display still work.
- **A configuration missing a name, or giving the panel one it does not read:** the panel
  says which and stays disabled. The keys it reads are `CONSOLE_KEYS` and the view keys in
  [`include/cite_console_gui/console_config.hpp`](include/cite_console_gui/console_config.hpp),
  and a test holds the installed plant configuration to them.
- **No home pose in the configuration, or one that is not six finite numbers:** every view
  button is disabled and the panel says why; the console's buttons are unaffected.
- **A preset, the follow model, the sides or the stale threshold missing or malformed:**
  the panel says which on the view line; the presets, Follow robot and the connection
  display are not shown, and Reset view still works.
- **No `CameraTracking` in the window, or a refused move or follow:** the view line says so
  ("View: nothing answered on /gui/move_to/pose ..."), never the console's outcome line; the
  next view request that succeeds clears it.
- **No twin boundary:** the connection display shows it and every side as absent.
- **A target the console does not serve:** not offered, and a goal naming one is refused by
  the console (`HomeRobot.action`, `RunProgram.action`); the panel never sends an unset one.
- **Validate then run on a deployment without the twin target:** disabled, and the panel says
  it is offered only when both sides run; the console refuses it anyway.
- **A request the console refuses:** the outcome line shows the console's detail. A
  rejected goal carries no reason to its client, so the console publishes it in its state
  as `last_error` ("refused: <reason>", the state itself unchanged), and the panel shows it
  under "Last error".
- **Every string the console sends is shown as plain text**, never as markup.
- **The panel is not a safety function.** The physical E-stop is the only closure
  (`docs/architecture/cross-cutting-safety.md`).
