# ADR-0059: Pair `cell_b` and leave `cell_a` single

- **Status:** Proposed
- **Date:** 2026-09-18
- **Deciders:** Project owner
- **Related:** [ADR-0041](0041-virtual-counterpart-is-a-second-full-simulation.md),
  [ADR-0042](0042-partition-gazebo-transport-per-side.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0047](0047-two-independent-launches-joined-not-sequenced.md),
  [ADR-0048](0048-refuse-a-counterpart-the-generator-cannot-build.md),
  [ADR-0050](0050-what-crosses-the-twin-boundary.md),
  [ADR-0056](0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md),
  [ADR-0057](0057-start-the-twin-boundary-from-the-pair-supervisor.md),
  charter §8 (Phase 2.A)

## Context

**ADR-0056 declared `cell_b` `single` and deferred this decision by name**: *"Flipping it to
`pair` is a separate change with its own record."* This is that record.

**What forces it now is an owner decision about what is being built, taken on 2026-09-18.**
The target system is **two twin sides, both digital, each with exactly one of everything** —
one arm, one conveyor, one of each fixture and sensor. The three-arm cell is finished,
archived and kept as a showcase; nobody works on it further. That is a statement about scope
and it is not derivable from the tree: `cell_b` is the target cell rather than a reduced
demonstration, and pairing it is the intended end state rather than an experiment.

**The reason ADR-0056 gave for deferring has since been removed.** It recorded that the
pairing *"inherits an open question this record does not answer: nothing starts L5"* — a pair
would come up with no boundary and a dispatched goal would have no server. ADR-0057 closed
that: the pair supervisor starts `twin_boundary` on the join, and its promotion clauses 1, 2,
3 and 5 are met on real runs.

**What has actually been observed, on one machine, with the model flipped for the run and
reverted afterwards. None of it is a rate and none of it is a CI gate.**

- A pair came up with a boundary and `SetMode` was called on it: the readiness token about
  1.5 s after the boundary was started, `accepted=True, 'SIM -> VIRTUAL_LEAD',
  current_mode=5`.
- A pair was torn down by **one** SIGINT: the supervisor stopped the boundary first, no
  participant printed `did not stop within … s of SIGINT`, and the verdict read
  `boundary: ready=True status=0`.
- `./scripts/validate-model` exits 0 with the zone paired, and the generated tree moves in
  `MODEL_HASH` and that zone's plan **only** — the plan gaining one `sides:` entry carrying
  the counterpart's partition and `domain_offset`, and `counterpart_backend`/
  `counterpart_commands_physical_hardware` per controller manager.

**Three fixed constraints this decision does not get to argue with.**

1. **Both sides are simulated, and the tree enforces it rather than asking.** ADR-0048
   clause 1 refuses any asset whose two sides declare different backends until clause 2 is
   built. Measured on 2026-09-18 by building a scratch model: a paired `cell_b` naming
   `counterpart_backend: real` produces `divergent-counterpart-backend` at **ERROR** and the
   model does not generate. Naming `real` on *both* sides produces
   `physical-plant-on-paired-zone` at ERROR as well. **So the L5 command path cannot reach a
   physical actuator by any L0 edit today**, and what protects it is a validate-time refusal
   rather than a safety layer. That is the same shape charter §8 already records for Phase
   2.A and it is not weakened here.
2. **2.A produces no fidelity number**, because both sides run the same L0 model and the same
   solver (charter §8). Nothing this record enables may be presented as one.
3. **Only one zone runs at a time** (ADR-0056 decision 3), because `/cite/facility`,
   `/cite/line` and `/cite/twin` are deliberately not zone-scoped.

## Options considered

### Option A — leave `cell_b` `single`, pair only by a temporary edit per experiment
The status quo, and how every pair to date has been brought up. It keeps the shipped model
minimal and keeps `./scripts/sim --pair` refusing on a clean checkout, which is one fewer way
to start two Gazebo worlds by accident.

**Not chosen**, because it makes the target system unreachable without an uncommitted edit
that moves `MODEL_HASH`. Every paired run so far has been taken on a model nobody could
reproduce from a checkout, which is precisely the condition under which a measurement cannot
be re-taken by a second reader. It also leaves the charter's three-arm sentence standing
against an owner decision that contradicts it.

### Option B — declare `cell_b` `twin: {sides: pair}` in L0
Chosen. One line in `model/facility/zones.yaml`, regenerated.

### Option C — pair `cell_a` instead, or as well
**Refused on two independent grounds.** `docs/open-work.md` #62: `cite_twin`'s two launch
fixtures append a counterpart to the live plan **unconditionally**, and both read `cell_a`
literally — `default_plan_path("cell_a")` and `ZONE = "cell_a"`, measured 2026-09-18. On a
checkout whose `cell_a` is paired, each writes a document with two sides named `counterpart`
and `cite_bringup.plan.load` refuses it, so `./scripts/test` fails. Pairing `cell_b` steps
around that defect rather than fixing it, and **#62 stays open and stays dormant only while
`cell_a` is single** — which is the condition this record makes load-bearing. Independently,
the owner has archived the three-arm cell, so pairing it would be work on the thing that was
set aside.

### Option D — a third zone, declared paired, beside the two
**Refused.** It would state the one-arm cell twice in L0, which is the duplication P1
forbids, and the one-zone-at-a-time rule would make it dead weight — a zone nothing can run
while `cell_b` is up.

## Decision

**`cell_b` declares `twin: {sides: pair}`. `cell_a` stays `single`.**

`cell_b` is the system under construction: two sides, both simulated, one of everything on
each. `cell_a` remains the generated, built, hand-launchable three-arm showcase that
ADR-0056 made it.

## Consequences

### What this gets us
- **The target system is reachable from a clean checkout.** `./scripts/sim --zone cell_b
  --pair` brings up two sides and a boundary with no edit to the model, so a paired run is
  reproducible by a second reader — which is what makes any future paired measurement worth
  taking.
- **The counterpart side is now covered by `./scripts/validate-model` and `./scripts/build`
  on every run**, rather than existing only inside somebody's temporary edit.
- **`MODE_VIRTUAL_LEAD` has a cell to dispatch to.** One goal to two arms — the thing the
  pair is for — no longer requires staging the model first.

### What this costs us
- **Nothing automated brings the pair up, and this record does not change that.** ADR-0057's
  promotion clause 4 — an automated paired scenario in CI — is still unmet. `grep -rn --
  --pair tests .github` and `grep -rn cite_twin tests .github scripts` both still return
  nothing. **A regression in the witness, the token, the boundary or either side's bring-up
  still fails no gate outside `cite_twin`'s own tests.** Declaring a zone paired is not
  testing it.
- **`./scripts/sim --zone cell_b --pair` no longer refuses on a clean checkout**, so two
  Gazebo worlds on one host is now one flag away. ADR-0043's floor is unmet on the machine
  that measured it and the capacity cost of a second world is real
  (`docs/measurements/2026-08-28-second-world-cost/`). Nothing here widens a ceiling to
  absorb it and nothing may.
- **`MODEL_HASH` moves**, and with it every artifact that carries it.
- **#62 becomes load-bearing rather than merely open.** It stays dormant only because both
  of its fixtures name `cell_a` and `cell_a` is `single`. Anyone who pairs `cell_a`, or who
  makes either fixture read the default zone, trips it immediately and `./scripts/test`
  fails. That is recorded in `docs/open-work.md` and is not fixed here.
- **The single-side path is the one that must not regress**, because it is what CI drives:
  the three scenarios bring `cell_b` up as the **plant alone**, on a plan that now declares a
  counterpart. That path is verified below rather than assumed.

### What we will have to revisit
- **When ADR-0057 clause 4 lands.** A paired scenario in CI is what turns this from a
  declaration into something a gate defends, and it is the next piece of work.
- **When a second zone is paired.** ADR-0056 already records that `ids.domain_offset` is a
  function of the side alone, so two paired zones in one checkout resolve to the same two
  domains. One paired zone does not reach that, and a second one does.
- **When Phase 2.B puts hardware on a side.** ADR-0048 clause 1 refuses a divergent backend
  until the per-side artifact set exists; that refusal is what makes both sides simulated
  today, and lifting it is that phase's work and not this record's.
- **If the paired bring-up proves unreliable on this host.** The evidence is one bring-up and
  one teardown on one machine. A second reader should re-take both rather than cite these.
