# ADR-0024: Split handoff — L4 owns the negotiation, L3 owns the motion

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0007, ADR-0010, [L3](../architecture/L3-capabilities.md), [L4](../architecture/L4-orchestration.md)

## Context

Two documents both describe handoff, and neither is wrong, but together they leave the
division of labour undefined.

[`L4-orchestration.md`](../architecture/L4-orchestration.md) lists "the handoff protocol
between robots" under **Owns**, and fixes four rules: a work-piece has exactly one owner at
any instant and ownership transfers atomically; both parties must confirm before physical
transfer begins; a timeout has a defined outcome — the upstream robot retains ownership and
the line reports a blocked station; and a handoff is testable in isolation.

[`L3-capabilities.md`](../architecture/L3-capabilities.md) lists a `Transfer` skill taking
a "peer identity, handoff pose" and returning "transferred / failed".

So both layers have a claim on the word. That ambiguity has to be resolved before Phase
1.D, because it decides what `Transfer.action` contains — and an interface package is
reviewed before its consumers ([ADR-0010](0010-typed-ros-interfaces.md)), so getting it
wrong means a breaking rename later.

The reason this matters more than a normal boundary question is that this is precisely
where v1 failed: its coordinator published handoff commands to a topic nothing subscribed
to, every transaction timed out forever, and no test noticed.

## Options considered

### Option A — L3 owns the whole handoff
`Transfer` takes a peer's identity and internally negotiates with that peer's skill server.

Rejected. It makes a skill aware of another robot, which contradicts L3's own rule that
"a skill that branches on robot type has failed at its job" and, more seriously, it puts
resource arbitration inside a layer that has no view of the line. Two `Transfer` calls
racing for the same shared volume would have nothing to arbitrate between them. It also
creates lateral L3-to-L3 communication, which is not a layer violation in the strict
downward-dependency sense but is a topology nothing else in the system has.

### Option B — L4 owns everything, no `Transfer` skill
L4 sequences `Place` on the upstream arm and `Pick` on the downstream arm and calls that a
handoff. Simple, and for a conveyor-mediated line it is almost sufficient.

Rejected because it cannot express a *direct* arm-to-arm handoff, where both grippers hold
the work-piece at once and release order matters. Phase 1.D's line is conveyor-mediated, so
this would work today — but the charter's L3 vocabulary names `Transfer` deliberately, and
removing it would mean re-adding it the first time two arms hand over directly.

### Option C — Split at the ownership boundary
L4 negotiates; L3 executes one half of the physical motion. Chosen.

## Decision

**L4 owns ownership.** The line coordinator holds the single owner of each work-piece,
performs the two-party confirmation, enforces the timeout with its defined outcome, and
arbitrates the shared volume. Ownership state lives in exactly one place and is published
as typed line state.

**L3 owns motion, for one robot at a time.** `Transfer` is a single-robot skill: bring the
held work-piece to a handoff pose, signal ready, hold position until released, then retreat.
It takes a **pose and a rendezvous token**, not a peer identity — so it never knows which
robot, if any, is on the other side. The receiving robot runs `Pick` at the same pose.

The rendezvous token is issued by L4 and is opaque to L3. That is what lets a handoff be
tested in isolation, as L4 requires: a test issues a token and drives one arm, with no
second arm present.

**A skill never talks to another skill.** All coordination is L4 calling L3 actions
downward. There is no lateral channel.

**A timeout is an outcome, not an expiry.** `Transfer` returns
`RESULT_HANDOFF_TIMEOUT` with the work-piece still held, and L4's defined response is that
the upstream robot retains ownership and the station is reported blocked. The failure is
structured, so recovery is chosen from `result_code` rather than parsed from text.

## Consequences

### What this gets us
- Ownership exists in one place, so "two robots think they hold it" is unrepresentable
  rather than merely unlikely.
- `Transfer` stays robot-agnostic and peer-agnostic, so L3 keeps the property that makes
  P9 achievable.
- A handoff is testable with one arm, which is what makes it testable at all — v1's defect
  survived precisely because nothing could exercise the protocol in isolation.
- Conveyor-mediated and direct arm-to-arm handoff are the same L4 protocol with different
  L3 calls, so Phase 1.D's line does not have to be rewritten to gain direct handoff.

### What this costs us
- **A rendezvous token is state that must be created, matched and expired**, and expiry is
  a source of subtle bugs. It buys the isolation-testability that L4 demands, but it is not
  free and it needs its own tests.
- L4 becomes the busiest node in the system and its failure stops the line. It is not a
  safety mechanism — L2's limits and collision checking are — but it is a single point of
  *availability*, and that should be stated rather than discovered.
- `Transfer` holding position while waiting for release means an arm can be commanded to
  hold indefinitely if L4 dies. The skill therefore needs its own bounded hold with a safe
  exit, which is duplicate-looking timeout logic that is genuinely necessary.

### What we will have to revisit
If a work-piece ever needs to be owned by two stations at once — a two-arm cooperative
carry, where neither is the owner — the single-owner rule breaks and the protocol needs
extending rather than reinterpreting. That is out of scope for Phase 1 and should not be
designed for speculatively.
