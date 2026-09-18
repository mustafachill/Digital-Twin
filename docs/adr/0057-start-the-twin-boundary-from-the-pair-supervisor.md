# ADR-0057: Start the twin boundary from the pair supervisor, after the join

- **Status:** Proposed. **The Decision is implemented** on `feat/pair-boundary`; the promotion
  condition is **not met**, and implementation is not promotion. This line read *"nothing in
  this record is implemented"* until 2026-09-18 and was made false by the change that
  implements it — the same drift ADR-0058's status line records one record along, and the
  reason charter §2's discipline is to re-run rather than to re-read. See
  *Implemented — 2026-09-18* below for what each clause rests on.
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
  exists — `pair.py`'s `if all(s.ready for s in sides)`, the one place the join completes as an
  event rather than as a re-derived predicate.
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
  **by definition** — `routing.py`'s `reverse_state_flow` returns `()` for it, because the mode
  *is* the absence of a reverse flow. Nothing here changes that, and no number this produces may be
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
   boundary is observed serving `SetMode` on the plant's domain **by a token it prints on
   stdout**, not by a log line. There is no such token today: `twin_boundary` logs prose through
   the ROS logger, whose sink is stderr, and `readiness.py` matches only `CITE_SIDE_READY`. The
   clause therefore names a mechanism the implementing change has to build, and said so from
   here on rather than reading as though one existed.
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

## Correction — 2026-09-18: three defects this record carried, found by exploring what implementing it would touch

Written before implementation, and three of its sentences did not survive contact with the
source. None withdraws a decision.

**1. The ceiling claim was half wrong.** *"The boundary starts on an event that already exists
and already has a ceiling"* — the event exists, and the ceiling does not apply to it.
`pair.py`'s join loop sets its timeout to `None` on the same iteration that marks the last side
ready, so anything started at the join point is covered by **no ceiling at all**. A boundary
that hangs would leave the supervisor waiting indefinitely. **The implementing change owes the
boundary a ceiling of its own**, written in the house idiom — a failure naming what never
answered — and **not** an extension of `READY_CEILING_S`, which that module already records as
stated rather than derived, and which a third contributor makes harder to sum rather than easier.

**2. `observed_sides` does not exist.** The function is `reverse_state_flow`, and it returns
`()` for `MODE_VIRTUAL_LEAD`. The claim was right and the name was invented; a reader greps and
finds nothing. ADR-0056 carries the same wrong name and is corrected in the same pass.

**3. Promotion clause 1 named a mechanism that does not exist.** It asks for the boundary
*"observed serving `SetMode`"*, and nothing witnesses the boundary the way `readiness_witness`
witnesses a side. The clause is not relaxed — it is the implementing change's job to build the
token, and the clause now says so.

**One thing measured rather than argued, and it shortens the work:** flipping a zone's
`twin.sides` to `pair` moves **two** artifacts, `MODEL_HASH` and that zone's plan, with **zero**
validator findings. The L0 half of pairing is one line; the work is entirely in who starts the
boundary, which is what this record decides.

## Implemented — 2026-09-18: four clauses met on real runs, and the fifth untouched

The Decision above is in the tree. **Clauses 1, 2, 3 and 5 are met; clause 4 is not, and it is
the one that decides promotion** — so this record stays `Proposed`, in the shape ADR-0045 and
ADR-0046 are kept in: a mechanism that is evidenced and an outcome that is not.

**The strength of what follows.** Clauses 1, 2 and 3 were exercised by a `tester` agent driving
real paired bring-ups on one machine, with the shipped model temporarily flipped to `pair` for
the run and reverted afterwards **[Overtaken 2026-09-18 —
[ADR-0059](0059-pair-cell-b-and-leave-cell-a-single.md) pairs `cell_b`, so no flip is needed to
repeat this on that zone. The evidence below was taken before that and is not re-taken.]** —
**no thresholds registered in advance, no directory in
`docs/measurements/`, and not re-taken by the pass that wrote this**. That is the size of the
evidence, and it is not a campaign.

- **Clause 1 — the token, and `SetMode` exercised rather than read off a log.** `./scripts/sim
  --pair` brought both sides and a boundary up, and the boundary printed
  `CITE_BOUNDARY_READY zone=<zone>` on **stdout** about **1.5 s** after it was started, against
  the 120 s ceiling the correction below asked for. The token is built where the mechanism the
  clause named had to be built: `cite_bringup.readiness` states both words, and
  `twin_boundary.py` prints this one from **inside** the plant's executor, so it says the
  endpoints are being served rather than that they exist. `SetMode` was then **called** on the
  running boundary and answered `accepted=True`, `'SIM -> VIRTUAL_LEAD'`, `current_mode=5`.
- **Clause 2 — a boundary that fails names the boundary.** Observed **2 of 2** on real runs, and
  driven by tests rather than described: a boundary that exits, one that never announces, and
  one that announces another zone each end the pair with a diagnosis naming `boundary` while
  both sides report `ready=True`.
- **Clause 3 — the zone and the plan path and nothing else.** A test asserts the argument vector
  exactly and fails if anything is added, `divergence_period_s` by name; a second scans the
  supervisor's own identifiers for the vocabulary of what crosses.
- **Clause 5 — `validate-model` with the zone paired.** Re-measured at implementation rather
  than quoted from the Context above: exit 0, and the generated tree moved in `MODEL_HASH` and
  that zone's plan only.
- **Clause 4 — untouched.** No automated paired scenario exists and none runs in CI. The shipped
  model is `single`, so `./scripts/sim --pair` refuses on a clean checkout, and `grep -rn
  cite_twin tests .github` still reaches nothing. **A regression in the witness, the token,
  either side's bring-up or the boundary fails no gate**, exactly as the clause says.
  **[Overtaken 2026-09-18 — [ADR-0059](0059-pair-cell-b-and-leave-cell-a-single.md) pairs
  `cell_b`, so the refusal is gone and the missing gate is not: a pair now comes up from a
  clean checkout and still fails no gate, which makes this clause a WIDER gap rather than a
  narrower one. The clause itself is still untouched.]**

**The ceiling the correction below asked for is built and is its own number**
(`BOUNDARY_CEILING_S`), not an extension of `READY_CEILING_S`, and a test asserts that the
number the diagnosis prints is the boundary's rather than whatever the sides' ceiling had left.

**Two defects on the teardown path were found in review and fixed before this was written**, and
they are recorded here because both are consequences of the third participant this record adds.
`ros2 run` forks and forwards nothing, so a SIGINT to the leader alone never reached the
boundary at all: it was waited out for the full grace and then killed, and its own `stop()` and
`rclpy` shutdown never ran. And the stop loop is sequential, so appending the boundary stopped
**the only participant that commands anything** last — leaving it serving `SetMode` and holding
an action client on each side for the whole of both sides' teardown. **Neither was fixed by
moving a ceiling.** The cost this record's Consequences section states — a third participant
extending the worst case to `3 × (90 + 30) s` — is unchanged and remains stated rather than
measured.

**A real paired teardown has now been observed, which is the one thing the tests above cannot
show, and it is one run.** Taken on this machine on 2026-09-18, on `cell_b` flipped to `pair`
for the run and reverted afterwards, with **one** SIGINT delivered to the container's PID 1 —
where a `Ctrl-C` in the terminal running `./scripts/sim` arrives. What was read from the
supervisor's own output: it printed `asked to stop (signal 2); ending both sides`, then
`stopping boundary`, `stopping plant`, `stopping counterpart` **in that order**, so the
participant that commands anything is stopped first; no participant printed
`did not stop within … s of SIGINT`; and the verdict line read **`boundary: ready=True
status=0`**, so the boundary ran its own `stop()` and `rclpy` shutdown rather than being waited
out and killed. **Both sides reported `status=1` and that is not a failure**: `_verdict` keys on
no participant's exit status, and 1 is what `ros2 launch` exits after an interrupt — all three
participants were `ready`, so the run graded 0.

**What this run does NOT measure is the cost the paragraph above states.** The whole teardown
completed inside the 5 s polling granularity of the instrument that timed it, so the
`3 × (90 + 30) s` worst case was never approached and is **still stated rather than measured**.
One machine, one run, nothing registered in advance, no directory in `docs/measurements/`.
**That is not a rate.**

**The instrument has a trap worth writing down, because the first attempt fell into it.** A
SIGINT sent to the *host* process group of `./scripts/sim` kills `docker compose run` and the
container dies before the supervisor's stop path runs: the log then contains **no** `[pair]
stopping …` line at all and no verdict, and a reader could take that silence for a clean
teardown. Signal the container, not the host side.

**One process died badly on this teardown, on both sides, and it is not classified here.**
`move_group` exited **-11** on the plant and on the counterpart. That is the member of the
teardown signal family CLAUDE.md §2 records as characterised and upstream, and the only one the
scenarios exempt. What is new is that it was seen in a **paired** teardown, symmetrically on
both sides; **sharing a signal is not evidence of sharing a cause**, no exemption is widened
here, and nothing else exited badly in the run.
