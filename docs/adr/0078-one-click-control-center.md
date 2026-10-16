# ADR-0078: One-click control center; a closed window is a clean end

- **Status:** Accepted 2026-10-16 (owner, after the physical run)
- **Date:** 2026-10-15
- **Deciders:** Project owner (decision of 2026-10-15: "an executable script and a desktop icon
  that start the app")
- **Related:** [ADR-0071](0071-the-first-operator-surface-is-a-panel-in-the-gazebo-window.md),
  [ADR-0074](0074-the-operator-console-frames-the-3d-view.md), open-work #107, CLAUDE.md §7

## Context

The operator console is started today with `./scripts/console` from a terminal, which leaves
several gaps:

- **X access:** nothing grants it, and nobody checks Docker access or whether the build is
  current. `./scripts/sim` even exits 0 when `cite_bringup` is not built.
- **Closing the window:** the run ends with exit code 3 (`PAIR_ENDED`), as if a part of the
  cell had failed (open-work #107).

The owner wants the control center started by double-clicking an icon.

## Decision

1. **`scripts/control-center` is the one-click entry point.** The repository root holds a thin
   `./cite-control-center` that only runs it. In order, it:
   - logs to `~/.local/state/cite-digital-twin/logs/` and keeps the last 20 logs;
   - allows one instance at a time;
   - checks Docker access and says what to do, without ever running `sudo`;
   - grants X access to the same user only (`xhost +SI:localuser:$USER`), and revokes it on exit
     if it added it;
   - bootstraps if the image or the imported vendor source is missing;
   - builds only if an input changed (`./scripts/build --if-stale`): first-party source, the
     vendor source's HEAD and local diff, `external/cite.repos`, `external/patches/` and
     `assets/meshes`;
   - refuses to start while another simulation window of the same checkout runs, because the
     console would attach to that container and a stop could then not tell the two apart;
   - runs `./scripts/console` in a container labelled with this run's id, and on HUP, INT or
     TERM sends SIGINT to that container alone;
   - reports any exit other than a clean one in a dialog that names the log.
2. **`scripts/install-launcher` installs the icon.** It installs a desktop entry and an icon
   drawn for this project into the user's menu, and with `--desktop` onto the desktop.
   `--uninstall` removes them.
3. **Closing the window is a clean end.**
   - A windowed side runs the server (`gz sim -s`) and its window (`gz sim -g`) as two
     processes, with the same partition and world. The combined `gz sim` cannot be used: it is
     a wrapper that exits 0 whichever of its server and GUI ended first, so a crashed server
     would read as a closed window.
   - When the plant's window exits 0 while its server is still running and no teardown is
     under way, its launch announces `CITE_WINDOW_CLOSED`. A server exit, a window exit other
     than 0, and a counterpart's window are not a close.
   - The supervisor treats that announcement, from the plant naming itself, as a stop and
     returns 0.
   - `PAIR_ENDED` stays the code for a participant that went away unexpectedly.
4. **`./scripts/sim` refuses a missing `cite_bringup` build** instead of exiting 0.
5. **CLAUDE.md §7 gains the new entry points** (`scripts/control-center`,
   `scripts/install-launcher`, `build --if-stale`). This is an owner-approved factual addition.

## Consequences

### What this gets us
- An operator starts the control center with one double-click.
- A normal close is not reported as a failure.

### What this costs us
- More shell to maintain, and the desktop entry depends on the desktop environment (GNOME is
  tested).
- Granting X access, even scoped to the same user, is a change to the host. It is revoked on
  exit.

### What we will have to revisit
- The Phase 4 web HMI, which would replace the desktop entry.
