# Lifecycle and bring-up

- **Status:** `PARTIAL`.
  **Built:** bring-up is event-driven. `cite_bringup/launch/simulation.launch.py` contains
  **no `TimerAction` and no sleep**, and sequences on 7 registered event handlers — process
  exit and service availability — with every deadline documented as a ceiling on a failure
  rather than a schedule. The three `cite_facility` nodes (`frame_server`, `model_info`,
  `topology_server`) are `LifecycleNode`s with real `on_configure`/`on_activate` work.
  **Not built:** "every node that participates in bring-up is a managed node" is not true
  today. `cite_skills`' skill server and `cite_orchestration`'s line coordinator are plain
  `rclcpp::Node`s with no lifecycle interface. The pattern below remains binding on them.
  **Nor is shutdown symmetric with startup**: on SIGINT the Python lifecycle nodes are
  destroyed without transitioning, so `on_deactivate` and `on_cleanup` never run — see
  *Lifecycle callbacks do not run on SIGINT* below, which records it as a gap.
- **Related:** charter §4 (P4), [ADR-0009](../adr/0009-docker-primary-environment.md),
  [ADR-0034](../adr/0034-process-lifecycle-mechanism-in-cite-runtime.md),
  [`../operations/bring-up.md`](../operations/bring-up.md), [`../reference/v1-lessons.md`](../reference/v1-lessons.md)

## The problem this solves

The v1 workspace sequenced startup with sleeps, in
`legacy/fleet_manager/launch/multi_robot_test.launch.py`. That tree was deleted at the end
of Phase 1 and survives only in version control, so the path is cited as text rather than
as a link; recover the file with
`git show f16ea98^:legacy/fleet_manager/launch/multi_robot_test.launch.py`. The lines below
were read from it that way on 2026-08-27 — lines 190-191, 236 and 263:

```python
spawn_delay = 2.0
delay_increment = 12.0     # Increased from 8.0 to allow more time for controller loading
...
current_delay = spawn_delay + (i * delay_increment)
controller_delay = current_delay + 5.0
```

Every step was a `TimerAction`. For three robots that put the third robot's spawn at
t = 26 s, its controllers at t = 31 s, its interface node at t = 34 s, and the handoff
coordinator at t = 43 s. The comment is the tell: the number was raised because startup
failed, not because twelve seconds means anything. On a slower machine it fails again; on a
faster one it wastes most of a minute. Nothing detected either case, because there was
nothing to detect against.

**A system that works only because a machine is fast enough is broken.** P4 exists for
this, and it is the reason `TimerAction` and `sleep` for sequencing are standing
prohibitions.

## The pattern

Every node that participates in bring-up is a **managed (lifecycle) node**.

```
   unconfigured ──configure──► inactive ──activate──► active
        ▲                          │                     │
        └────────cleanup───────────┘◄────deactivate──────┘
                                   │
                              (on error)
                                   ▼
                              finalized
```

| Transition | Does | Must not |
|---|---|---|
| `configure` | Read parameters, allocate, create interfaces, validate | Publish, command, or move anything |
| `activate` | Begin publishing and accepting goals | Fail on something `configure` could have caught |
| `deactivate` | Stop publishing and accepting goals; hold a safe state | Leave the robot in an indeterminate position |
| `cleanup` | Release everything `configure` allocated | Leave a resource held |

Bring-up sequences on **transition results**, not elapsed time. A node is activated when
its dependencies report active — which means bring-up is as fast as the machine allows and
as slow as it needs to be, on every machine.

## Ordering

Dependency order, each step gated by the previous one reporting success:

```
1. Simulator or hardware connection
2. Description publishers                (need 1 for the simulator)
3. Controller manager + hardware iface   (needs 2 for the description)
4. Controllers                           (need 3 active)
5. MoveIt                                (needs 4 for state)
6. Skill servers                         (need 5)
7. Twin synchronization                  (needs 4; sets the mode)
8. Orchestration                         (needs 6 and 7)
```

Failure at any step **stops bring-up with a diagnosis**. It does not continue with a
degraded system and discover the problem three layers later — which is what timing-based
sequencing does by construction.

## Shutdown is a designed path

Shutdown gets the same discipline as startup, in reverse. It is not an afterthought:

- Orchestration stops accepting work.
- In-flight skills complete or cancel cleanly.
- Controllers deactivate with the robot in a safe state.
- The simulator or hardware connection closes.
- **No orphaned processes remain.**

That last point is not hygiene. An orphaned `gz sim` holds ports and names, and the next
bring-up fails in a way that points nowhere near the cause. It is in the `debugger` agent's
trap list because it costs people hours.

## How an `rclpy` process exits

**Scope: this section is about `rclpy` and nothing else.** The convention below exists to
compensate for two specific defects in rclpy's shutdown path, both recorded with their
mechanism and their **removal conditions** in
[ADR-0034](../adr/0034-process-lifecycle-mechanism-in-cite-runtime.md). It is implemented
once, in `cite_runtime`, and imported — it is not copied into a node.

- **SIGINT does not raise.** A handler is installed that returns without raising, so no
  `KeyboardInterrupt` can be delivered asynchronously into a message conversion. rclpy's
  own handler still runs, so shutdown remains an *event* (P4); only the exception riding
  alongside it is removed.
- **Shutdown is observed, not caught.** A node exits on `rclpy.ok()` going false or on
  `ExternalShutdownException`. `except KeyboardInterrupt` is no longer a shutdown path,
  because nothing raises it any more.
- **One exception is tolerated, narrowly.** An `RCLError` out of the executor is swallowed
  **only while `rclpy.ok()` is already false**. Under any other condition it propagates.

**Do not delete the no-op handler because it looks wrong.** It looks wrong; it is load-bearing
until upstream is fixed, and ADR-0034 states the two conditions under which each half is to
be deleted rather than kept.

**The C++ side has no equivalent, and this document does not invent one.** `rclcpp` does
not chain to a Python handler, has no `KeyboardInterrupt`, and does not run the message
conversion that fails — so neither race is known to port. Whether `rclcpp` has a teardown
race of its own is an **open question**: this project has seen an unexplained `skill_server`
SIGSEGV at teardown, a `MoveGroupInterface` reference cycle is *suspected*, and nothing has
been demonstrated. A convention would be written for a defect nobody has shown to exist.

### Lifecycle callbacks do not run on SIGINT — this is a gap

Three of the four `cite_facility` Python nodes are `LifecycleNode`s. All three implement
`on_cleanup`; `frame_server` also implements `on_deactivate`. **On SIGINT, none of them
runs.** `main()` calls `destroy_node()` directly, so the process goes from `active` to gone
without passing through `deactivate` or `cleanup`.

That was already true of the code the shutdown fix replaced, so the fix does not introduce
it — but it canonizes it, and it contradicts the transition table above, which says
`cleanup` "release[s] everything `configure` allocated".

**Recorded as a gap, not as a design.** It is harmless *today* for one checkable reason:
those callbacks release publishers and services and nothing else, and process exit releases
those anyway. It stops being harmless at the first Python lifecycle node whose `on_cleanup`
releases something that outlives the process or matters on the way out — a file being
written, a hardware handle, a latched output, a safety interlock. At that point an
event-driven `deactivate` → `cleanup` on the shutdown path is required, and it is a
decision to be recorded, not a patch.

## Testing bring-up

Bring-up is tested like anything else ([cross-cutting-testing.md](cross-cutting-testing.md)):

- It reaches fully active, repeatably, across runs.
- It reaches active on a deliberately loaded machine — this is what catches a lurking
  timing assumption.
- A failure at any step produces a clear diagnosis rather than a hang.
- Shutdown leaves nothing behind.

## Failure modes

| Failure | How it shows | Detection |
|---|---|---|
| Timing-based sequencing | Works locally, fails in CI or on a slow machine | Standing prohibition; `reviewer`; `architect-reviewer` |
| Node publishing while inactive | Consumers receive data from a node that is not ready | `reviewer` |
| `activate` failing on a config problem | Late, confusing failure | `reviewer` |
| Unsafe state on `deactivate` | Arm left in an indeterminate position | `safety-auditor` — Critical |
| Orphaned process after shutdown | The *next* bring-up fails, pointing nowhere useful | `tester` standing check |
| Circular dependency | Bring-up hangs with no error | Explicit ordering; scenario test |
| `rclpy` node exits 1 at teardown | `RuntimeError: Unable to convert call argument '0' to Python object`, intermittently and only under load | Scenario teardown check; the convention above ([ADR-0034](../adr/0034-process-lifecycle-mechanism-in-cite-runtime.md)) |
| The no-op SIGINT handler removed as "obviously wrong" | The teardown failure above returns at roughly 1 run in 10 under load — low enough to be dismissed as flake | ADR-0034's removal conditions; `reviewer` |
| A Python lifecycle node holding a resource that matters | Nothing on SIGINT: `on_cleanup` never runs, so the resource is released only by process exit | Nothing detects this today — see the gap recorded above |
