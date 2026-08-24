# Lifecycle and bring-up

- **Status:** `DESIGNED` — no nodes exist. The pattern is binding on all of them.
- **Related:** charter §4 (P4), [ADR-0009](../adr/0009-docker-primary-environment.md), [`../operations/bring-up.md`](../operations/bring-up.md)

## The problem this solves

The v1 workspace sequenced startup with sleeps
(`legacy/fleet_manager/launch/multi_robot_test.launch.py`):

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
