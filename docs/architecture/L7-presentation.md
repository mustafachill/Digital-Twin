# L7 — Presentation

- **Status:** `PARTIAL`. The first L7 package, `cite_console_gui`, exists
  ([ADR-0071](../adr/0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md)). It is
  an operator panel docked in the plant side's Gazebo window.
  - **Built:** a gz-gui 8 plugin `CellConsole` (C++ and QML). It sends requests to the console
    server `cell_console` and shows the server's latched `ConsoleState`, and it reads the twin's
    mode directly from `TwinMode`.
  - **Not built:** the browser-based HMI the charter places in Phase 4, remote access, and any
    telemetry view. ADR-0018 still makes no commitment to that stack.
  - **Tests:** the button-enablement table, the ROS client and the generated plugin parameters
    are tested headlessly. Nothing in CI
    renders the panel.

## What L7 may depend on

An L7 package depends on:

- `cite_interfaces`, the typed contracts it calls and reads;
- client libraries (`rclcpp`, `rclcpp_action`);
- its own toolkit. For the panel that is `gz_gui_vendor`, `gz_plugin_vendor` and Qt 5 through
  rosdep.

It never depends on `cite_bringup`, `cite_twin`, `cite_tools` or `cite_generated` at build or
run time. One test, `test_console_config`, reads `cite_generated`'s installed GUI configuration,
so `cite_generated` is a test-only dependency. Nothing below L7
names an L7 package. That includes `simulation.launch.py`, which would otherwise be an upward
L2→L7 dependency.

## How the panel is found and named

- **Finding the plugin.** The package exports its own `GZ_GUI_PLUGIN_PATH` through an ament
  environment hook (`hooks/gz_gui_plugin_path.dsv.in`), the same pattern `cite_simulation` uses for
  `GZ_SIM_SYSTEM_PLUGIN_PATH`. `./scripts/sim --pair --console` refuses to start if `CellConsole`
  does not resolve on that path.
- **Where it appears.** The generator emits one GUI config per side, and only the plant's config
  carries the `CellConsole` plugin block (`tools/cite_tools/generate/gui.py`).
- **Names.** The plugin block passes the console's six names as plugin parameters, taken from the
  same function that writes the plan's `console:` block (`bringup.console_names`). The panel forms
  no name, and it takes the twin-mode topic from `TwinMode::TOPIC`.
- **ROS domain.** The panel runs inside `gz sim`, so it inherits the plant side's `ROS_DOMAIN_ID`.
  It holds one ROS context, on that domain only (ADR-0044's L7 clause).

## A pure view

- **Every refusal is the server's.** The panel decides only which buttons are enabled. That rule
  is one function with no Qt and no ROS (`enablement.hpp`, `enabled_for`). It mirrors the server's
  gating so that a button the server would refuse is greyed out. It does not replace that gating.
- **When the console is silent.** If the panel hears no `ConsoleState`, or the console's publisher
  leaves the graph, it shows "No console" and disables every button.
- **Stop.** Stop is labelled a software stop, not an E-stop
  ([`cross-cutting-safety.md`](cross-cutting-safety.md)).

## How it fails

| Failure | What the operator sees |
|---|---|
| The console is not running, or has exited | "No console"; every button is disabled |
| `CellConsole` is not built or not on the plugin path | `./scripts/sim --pair --console` refuses before bring-up |
| A request is refused | The refusal reason in the panel's last-error line |
| A plugin parameter is missing or unknown | The panel says which one and stays disabled |
