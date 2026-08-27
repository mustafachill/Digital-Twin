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

## Reliable is a promise to *matched* subscribers, and this cost the project a working line

Compatibility is not the only way a reliable message reaches nobody. **Reliability is
retransmission to endpoints the publisher has already been matched with**, and matching is a
discovery event. Publish before it happens and the message is delivered to zero subscribers,
with no incompatibility to find and nothing wrong on either side of `ros2 topic info`.

The measured case is in this repository. `ConveyorIndex` creates its belt command publishers
inside `line_orchestrator`'s topology callback and publishes the start-up setpoint from the
same callback. With the scenario's own publisher removed, **a subscriber that had been up for
a hundred seconds received nothing for the following three hundred.** The bridge had been
running the whole time; the profile was `COMMAND`, reliable; nothing was misconfigured. L4's
belt command had never once arrived, and a test harness had been starting the belts.
See the 2026-08-27 correction on [ADR-0032](../adr/0032-index-the-belt.md).

**Tell the two apart before reaching for a profile change:**

| Symptom | Likely cause |
|---|---|
| Endpoints listed, profiles differ on a "No" row above | Incompatible QoS |
| Endpoints listed, profiles agree, nothing ever arrives from one specific publish | The publish happened before the match |
| Data arrives once the subscriber restarts, or once anything else appears on the topic | The publish happened before the match |

**The fix is an event, never a retry, a sleep or a wider profile (P4).**

- Treat a subscriber matching as an event —
  `rclcpp::PublisherOptions::event_callbacks.matched_callback` — and send the publisher's
  *current* value from it. Sending the current value, not the original, means a bridge that
  restarts mid-run learns the present state rather than the start-up state.
- **Keep the original immediate publish**, so an RMW that does not deliver the matched event
  degrades to the previous behaviour rather than to something worse.
- **`LATCHED` is not the general answer.** Transient local would deliver the last value to a
  late joiner, but it also replays it to every future one, which for a command topic means a
  belt learning a setpoint that was current minutes ago. Use it for configuration, per the
  section below; use the matched event for commands.
- Never fix it by publishing on a timer until something answers. That is a guessed duration
  in the shape of a workaround, and it fails silently again the day discovery is slower.

**The test has to be ordered the way production is.** Every pre-existing case against
`ConveyorIndex` subscribed first and then commanded, and not one of them could see this. The
two that catch it are ordered index, command, subscribe — the production order. A delivery
test that sets up its subscriber first is testing a scenario the running system never
executes.

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
