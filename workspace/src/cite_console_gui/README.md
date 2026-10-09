# cite_console_gui

**Status: `PARTIAL`.** The panel builds; its enablement table, its reading of the contract
and of its configuration, and its ROS client (`ConsoleClient`, against a fake console on a
graph of its own) are unit-tested. Nothing in CI renders it; the panel in a window has not been
verified by a test.

The operator console's panel in the Gazebo window
([ADR-0071](../../../docs/adr/0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md)
decision 5), and the first L7 package. A gz-gui 8 plugin, `CellConsole`, in C++ and QML.

**It holds no logic.** It shows the latched `ConsoleState` that `cell_console`
(`cite_bringup.program.console`) publishes, and it sends that console's requests. Every
refusal is the console's: a button the panel enables and the console refuses costs a
refusal message and nothing else.

## What it shows and sends

| Element | What it is |
|---|---|
| Status | `ConsoleState`: state, step, at start, last error, physical sides (badged `PHYSICAL`) |
| Twin mode | `TwinMode` on `TwinMode::TOPIC`, read directly from the twin boundary (ADR-0044) |
| Start robot | `StartRobot` |
| Home | `HomeRobot`, with the selected speed |
| Start program | `RunProgram`, with the selected speed and a cycle count (at least 1) |
| Speed | 1.0 ("Original speed") preselected, then 0.5, 0.25, 0.1; choices below `minimum_speed_scale` disabled |
| Confirm | `ConfirmOperator`, shown only in `AWAITING_OPERATOR`, with `prompt` verbatim; its cancel is Stop |
| Stop | `StopCell` — a software stop, **not an E-stop**, and labelled so |
| Progress, outcome | The goal's feedback and the last answer's detail |

Which buttons are enabled is `enabled_for` in
[`include/cite_console_gui/enablement.hpp`](include/cite_console_gui/enablement.hpp), a pure
function with no Qt and no ROS in it, and nothing else. Before any `ConsoleState` is heard,
or once its publisher has unmatched (the subscription's matched event, not a poll), every
button is disabled, the twin mode, progress and outcome said for the console that left are
cleared, and the panel says "No console".

## Where its names come from

- The console's six names are the plugin's XML parameters, written into the plant's GUI
  configuration by the generator (`tools/cite_tools/generate/gui.py`) from the same function
  the plan's `console:` block is emitted from. Only the plant's window of a paired zone
  carries the plugin.
- The twin mode's topic is `cite_interfaces::msg::TwinMode::TOPIC`, a constant in the
  contract.

The panel builds no name.

## How it is found and run

The package's environment hook puts its `lib` directory on `GZ_GUI_PLUGIN_PATH` when the
workspace is sourced, so nothing below L7 names it. Run it with `./scripts/console`
(the same as `./scripts/sim --pair --console`, windowed).

It joins ROS with a context of its own, on the domain the window was started on — the
plant's — and spins it on its own thread; it installs no signal handler. Every request is
asynchronous; a server that is not there is reported in the panel, never waited for.

## How it fails

- **No console running:** "No console", everything disabled.
- **A configuration missing a name, or giving the panel one it does not read:** the panel
  says which and stays disabled. The keys it reads are `CONSOLE_KEYS` in
  [`include/cite_console_gui/console_config.hpp`](include/cite_console_gui/console_config.hpp),
  and a test holds the installed plant configuration to them.
- **A request the console refuses:** the outcome line shows the console's detail. A
  rejected goal carries no reason to its client, so the console publishes it in its state
  as `last_error` ("refused: <reason>", the state itself unchanged), and the panel shows it
  under "Last error".
- **Every string the console sends is shown as plain text**, never as markup.
- **The panel is not a safety function.** The physical E-stop is the only closure
  (`docs/architecture/cross-cutting-safety.md`).
