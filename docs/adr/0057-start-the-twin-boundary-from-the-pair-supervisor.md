# ADR-0057: Start the twin boundary from the pair supervisor, after the join

- **Status:** Proposed — nothing in this record is implemented.
- **Date:** 2026-09-17
- **Deciders:** Project owner, who chose this shape over two alternatives on 2026-09-17;
  drafted by the orchestrator against a measurement taken the same day.
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md),
  [ADR-0056](0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md);
  charter §8's Phase 2.A.

## Context

### What works, and the one thing that does not

A pair comes up. `./scripts/sim --pair` starts two independent launches and **joins** them on a
token each side prints once its own readiness witness has seen every action server the plan
declares answering on that side's domain ([ADR-0047](0047-two-independent-launches-joined-not-sequenced.md)).
Both isolations were verified at runtime rather than read off a launch file: one `/clock`
publisher per domain, one Gazebo server per partition, every name present once on each side.

**Nothing starts L5.** `cite_twin/twin_boundary.py` is installed as a program and appears in **no
launch file, no script and no generated plan slot** — `grep -rn twin_boundary workspace/src`
outside `cite_twin` returns comments only. So a pair comes up with no boundary, `SetMode` has no
server, and the operator-facing flow this project is aiming at — one goal dispatched to both
sides under `MODE_VIRTUAL_LEAD` — **cannot be demonstrated at all.** That is the gap this record
closes, and it is the whole of Phase 2.A's remaining bring-up work.

### What pairing a zone actually costs, measured rather than predicted

Measured on 2026-09-17 against a scratch copy of `model/` with `cell_b`'s `twin.sides` flipped to
`pair` and nothing else changed:

- **48 artifacts before, 48 after.** No file added, none removed.
- **Exactly two artifacts change**: `MODEL_HASH`, and `bringup/cell_b_plan.yaml`, which gains
  **15 lines** — a second `sides:` entry carrying `gz_partition: cite/cell_b/counterpart` and
  `domain_offset: 1`, and **two** keys per controller manager, `counterpart_backend` *and*
  `counterpart_commands_physical_hardware`.
- **Zero validator findings** at all three levels, both zones.

So the L0 and generator half of pairing is a **one-line change**, and no part of this record is
about it. The work is entirely in who starts the boundary.

### The constraint that makes this a decision rather than a patch

`cite_bringup/pair.py:28` states, in the supervisor's own words, that it may not decide
*"anything about what crosses between the sides, which is L5's definition and this is not L5."*
That sentence is right and this record does not weaken it. It is also the reason the obvious
implementation — "have the supervisor bring the boundary up" — needs an argument rather than a
commit.

The supervisor is nevertheless the only component that knows **both sides are ready**. It owns
the join, the readiness tokens and the pair's lifetime. A boundary started before both sides
answer has nothing to connect to; one started by hand afterwards puts a human in the position
the join exists to remove.

### What the boundary needs, read from its source

`twin_boundary.py` takes `--zone` and an optional `--plan`, declares one parameter
(`divergence_period_s`), requires `CITE_DOMAIN_BASE` in its environment, and builds a
`SideContext` per side from the plan. It refuses a `single` zone by construction, and refuses a
side whose node carries `use_sim_time`, because the two sides' simulated clocks are independent.

## Options considered

### Option A — the pair supervisor starts it, after the join
Chosen. The supervisor already waits for both readiness tokens; the boundary is started on that
event and on nothing else.

### Option B — a separate launch file, started by hand
`twin.launch.py`, invoked after `./scripts/sim --pair`. It leaves `pair.py`'s contract untouched,
which is its whole appeal. Rejected because it **discards the join**: nothing would know both
sides are ready, so either an operator judges it by eye or a second mechanism re-derives what the
supervisor already knows. A bring-up that proceeds because a human thought it looked ready is the
timing guess P4 forbids, wearing a different hat.

### Option C — a slot in the generated bring-up plan
The most P5-shaped answer: the plan declares the boundary, and launch reads it. Rejected **for
now**, on cost against need: it is a new generated key and therefore
[ADR-0021](0021-generated-artifacts-are-committed.md) territory, moving the schema, the
generator, the template and `plan.py`'s reader together — and the plan is a **per-zone** document
while the boundary is a per-*pair* process, so the slot would be declared on every `single` zone
that will never start one. It becomes the right answer the day a facility runs more than one
pair; this record does not foreclose it.

## Decision

**The pair supervisor starts `twin_boundary` after both sides have announced readiness, and
passes it nothing but the zone and the plan path.**

**The distinction that keeps `pair.py:28` intact, and it is the load-bearing sentence of this
record: starting a process is not deciding what crosses.** The supervisor learns nothing about
modes, routing, skills or divergence, and gains no branch on any of them. It hands over two
facts it already holds — which zone this is, and where the plan is — and every decision about
what crosses the boundary stays where ADR-0050 put it, inside `cite_twin`. If a future change
makes the supervisor pass a mode, a side preference or a skill list, that change has crossed the
line this record draws and needs its own ADR.

**The boundary's failure ends the pair, and is reported as the boundary's.** A pair whose sides
are up and whose boundary is not is a pair that cannot answer `SetMode`, which is the thing the
pair exists for. It fails with a diagnosis naming the boundary, not a side.

## Consequences

### What this gets us
- **The demonstration becomes possible**: one goal into `SetMode`, dispatched to both sides,
  which is charter §8's virtual-led flow and the owner's stated target.
- **The join is reused rather than re-derived.** The boundary starts on an event that already
  exists and already has a ceiling.
- **Pairing stays a one-line L0 change**, as measured above. Nothing in the generated tree moves
  for this record.

### What this costs us
- **`pair.py` grows a responsibility**, and the line it must not cross is now a sentence in a
  record rather than a property of the code. That is weaker than a mechanism, and it is the
  honest cost of choosing A over C.
- **`--pair` gains a process whose failure mode is new**, and the supervisor's stop path is
  already sequential: two stuck sides cost `2 × (90 + 30) s` today, and a third participant
  extends that.
- **Still no fidelity number.** 2.A produces none by construction, both sides running the same
  L0 model and the same solver (charter §8), and `MODE_VIRTUAL_LEAD` computes no divergence
  **by definition** — `routing.py`'s `observed_sides` is empty for it, because the mode *is* the
  absence of a reverse flow. Nothing here changes that, and no number this produces may be
  presented as fidelity.
- **`DivergenceMetrics.valid` remains false for every sample**, because ADR-0049 sets no
  `DEFICIT_BOUND_S` and nothing in this tree measures a clock deficit. Starting the boundary
  does not make its metric true, and **the term must not be weakened to make it so.**

### What we will have to revisit
- **When a facility runs more than one pair.** Option C becomes correct, and this record should
  be superseded rather than amended.
- **If the supervisor is ever asked to pass anything beyond the zone and the plan path.** That is
  the line above, and crossing it is a new decision.
- **When Phase 2.B puts hardware on a side.** ADR-0048 clause 1 refuses a divergent counterpart
  backend until the per-side artifact set exists, so this record's pair is simulated on both
  sides and says nothing about a physical one.

## The promotion condition

1. `./scripts/sim --pair --zone <paired zone>` brings both sides up **and** a boundary, and the
   boundary is observed serving `SetMode` on the plant's domain.
2. A pair whose boundary fails to start fails the run **naming the boundary**, and a test drives
   that path rather than describing it.
3. `pair.py` passes the zone and the plan path and nothing else; a test fails if it passes more.
4. **An automated paired scenario exists and runs in CI.** The shape is already proven in
   `cite_twin/test/test_twin_boundary_paired_launch.py`: each side an `ExecuteProcess` with its
   own `ROS_DOMAIN_ID` in `additional_env`, the test process holding one context on the plant's
   domain, the far side read through `proc_output`. Until this clause is met, **nothing automated
   brings a pair up** and a regression in the witness, the token, either side's bring-up or the
   boundary fails no gate.
5. `./scripts/validate-model` exits 0 with the zone paired, and the generated tree moves in
   `MODEL_HASH` and that zone's plan only — as measured above, and re-measured at implementation
   rather than quoted from here.

## What this record does not decide

- **Which mode drives the demonstration.** `MODE_VIRTUAL_LEAD` dispatches to both sides and
  produces no divergence number; `MODE_VALIDATED` observes both. That is a separate choice and
  neither is implied here.
- **Whether `cell_b` is paired at all.** ADR-0056 ships it `single`; flipping it is a one-line L0
  change and the owner's to make.
- **Anything about the charter.** `what-we-are-doing.md` §8 scopes Phase 2.A to *"a complete
  second simulation of the same three-arm cell"* and says *"the cell stays three-armed"*. Pairing
  a one-arm cell instead is the sentence that becomes false, and the charter is protected: that
  amendment is the project owner's, with a version bump and a §14 entry.
