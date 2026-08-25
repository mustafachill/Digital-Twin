# QoS profiles

- **Status:** `BUILT` — the five profiles ship as a library in both languages,
  `cite_interfaces/cite_interfaces/qos.py` and `include/cite_interfaces/qos.hpp`
  ([ADR-0025](../adr/0025-qos-profiles-in-cite-interfaces.md)), with a test asserting the two
  agree. The table below was checked against `qos.py` and matches it exactly. Every publisher
  in the tree declares a named profile from it, and `./scripts/scenario bringup` asserts that
  a subscriber actually **receives** — the only test a QoS mismatch cannot pass.
- **Related:** [`README.md`](README.md), [`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md)

## Why this has its own document

Incompatible QoS between a publisher and a subscriber **connects silently and delivers
nothing.** `ros2 topic list` shows the topic. `ros2 topic info` shows both endpoints. No
data flows, and no error is produced anywhere.

It is the most-misdiagnosed failure in ROS 2, and it is entirely preventable by declaring
profiles explicitly and using the named set below rather than improvising per publisher.

**Never rely on the default profile.** Declare a profile, from this table, every time.

## The profiles

| Profile | Reliability | Durability | History | Depth | Use for |
|---|---|---|---|---|---|
| `SENSOR` | Best effort | Volatile | Keep last | 5 | High-rate sensor streams where the newest value is what matters |
| `STATE` | Reliable | Volatile | Keep last | 10 | Periodic state — joint state, line state, divergence metrics |
| `COMMAND` | Reliable | Volatile | Keep last | 10 | Commands that must arrive |
| `LATCHED` | Reliable | Transient local | Keep last | 1 | Configuration a late joiner must receive — model version, mode, robot description |
| `EVENT` | Reliable | Volatile | Keep all | 100 | Discrete events that must not be dropped — faults, transitions, handoffs |

## Choosing

```
Is it configuration a late-joining node must receive?     → LATCHED
Is it a discrete event that must never be lost?           → EVENT
Is it a command that must arrive?                         → COMMAND
Is it high-rate data where only the newest matters?       → SENSOR
Otherwise                                                 → STATE
```

## Compatibility

A subscriber's requested QoS must be **no stricter** than the publisher's offered QoS.

| Publisher offers | Subscriber requests | Connects |
|---|---|---|
| Reliable | Reliable | Yes |
| Reliable | Best effort | Yes |
| Best effort | Best effort | Yes |
| Best effort | **Reliable** | **No — silently** |
| Transient local | Volatile | Yes |
| Volatile | **Transient local** | **No — silently** |

The two "No" rows are the failure. Nothing reports them at runtime; the endpoints simply
never match.

## Diagnosing a suspected mismatch

```bash
ros2 topic info /cite/cell_a/arm_1/joint_states --verbose
```

Compare reliability, durability, and history on both sides. If the topic exists, both
endpoints are listed, and no data arrives, this is almost certainly the cause — check it
**before** looking anywhere else. It is the first entry under "A topic exists but no data
arrives" in [`../operations/troubleshooting.md`](../operations/troubleshooting.md) for
exactly this reason.

## Testing

Integration tests assert that a message **actually arrives**, not merely that a publisher
and subscriber were created. A test that constructs both and never checks delivery passes
happily against a QoS mismatch — which is the shape of the v1 handoff defect, where a
coordinator published commands to a topic with no subscriber and every transaction timed
out forever.

## Latching and late joiners

`LATCHED` (transient local, depth 1) is what makes a late-joining node receive the current
value rather than waiting for the next publication. Use it for anything a node needs
**immediately on startup**:

- Robot descriptions
- The facility model version
- The current operating mode
- Static configuration

Do not use it for streams. Transient local on a high-rate topic makes every late joiner
receive stale data and costs memory for no benefit.
