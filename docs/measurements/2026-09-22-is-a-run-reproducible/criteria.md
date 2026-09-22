# Criteria — is a run of this cell reproducible at all, and where does the irreproducibility enter?

**Written before the harness exists and before any trial has run.** At the moment this file is
committed this directory holds this file and nothing else — no `harness/`, no `raw/`.

- **Opened:** 2026-09-22
- **Branch under measurement:** `measure/is-a-run-reproducible`
- **`BASE_COMMIT`:** `79b1acd` — verified at every block with
  `git merge-base --is-ancestor 79b1acd HEAD`, which must succeed
- **Vendor pin:** `xarm_ros2` at `3dc2b5e8294758d96b54b15fa5920d581b7cbb3d`, from
  `external/cite.repos`
- **What asks for this:** the project owner's question — two digital sides, one environment, one
  signal, and movements that are not synchronous. An earlier plan answered *"the IK search is
  wall-clock bounded"*; that plan's own before-reading refuted it (identical joint solutions
  across sides, identical latency), so the question moved down a layer to the contact physics.
  There is **no `docs/open-work.md` item** for any of this: `grep -ci determin docs/open-work.md`
  returns **0** at `BASE_COMMIT`.
- **Records that own the claims this campaign reads, and may not be moved by it:**
  [ADR-0027](../../adr/0027-pilz-planning-pipeline.md) § *What `CITE_PHYSICS_SEED` does and does
  not buy*, [ADR-0029](../../adr/0029-simulated-grasping-by-friction.md),
  [ADR-0021](../../adr/0021-generated-artifacts-are-committed.md),
  [ADR-0042](../../adr/0042-partition-gazebo-transport-per-side.md),
  [`cross-cutting-testing.md`](../../architecture/cross-cutting-testing.md).
- **Campaigns whose rules this one inherits, each FROZEN and none of them edited here:**
  [`2026-09-21-place-abort-and-the-held-part`](../2026-09-21-place-abort-and-the-held-part/criteria.md)
  (§10's validity set, and instrument I4),
  [`2026-08-31-capacity-and-clock-deficit`](../2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  (the one-invocation-one-record harness shape),
  [`2026-09-03-stall-band-flip`](../2026-09-03-stall-band-flip/ANALYSIS.md) (rule N — a null is
  never a clearance),
  [`2026-08-27-teardown-signal-family`](../2026-08-27-teardown-signal-family/results.md)
  (rule 1 — a control that does not fire refuses the treatment arm as evidence).

## §0 This campaign decides nothing

- **No record is corrected on this evidence inside this directory.** Where the result disagrees
  with a statement in the tree, the disagreement is stated here and the correction is a separate
  change with its own review.
- **No tolerance, ceiling or threshold anywhere in the repository moves on this evidence.**
- **Nothing here is a fidelity claim.** Both sides of everything measured are simulated, and the
  layout is `PROVISIONAL`.
- **Nothing here proposes a fix.** If the result localises the irreproducibility, what to do
  about it is the project owner's decision, taken after reading the result and not before.
- **No frozen campaign is edited.** Four measurement files carry a stale sentence this campaign
  is about — `2026-08-25-friction-grasp/{results,criteria}.md`,
  `2026-08-25-grasp-plane-offset/criteria.md`,
  `2026-08-26-conveyor-yaw-transfer/{criteria,ANALYSIS}.md`. The directory's own freeze rule
  keeps them exactly as they are.

## §1 The question, and the ones it is not

- **Q1 — Is the physics engine reproducible?** Given one world, one seed and no external
  process, does the same run produce the same physical outcome?
- **Q2 — Does `gz sim --seed` change a physical outcome?** ADR-0027:474-481 says it does not
  reach the physics solver. That has never been tested behaviourally, and the evidence for it is
  §2 below.
- **Q3 — Is a run of the whole cell reproducible?** Given one seed, do two runs of the same
  scenario put the part in the same place?
- **Q4 — If Q1 and Q3 disagree, where does the irreproducibility enter?** This is the question
  the campaign exists for, and it is answerable only as the *difference* between two arms.

### §1.2 Not in scope, deliberately

- **Whether two *concurrent* sides agree.** A pair is not run. A run that does not reproduce
  against itself can never agree with a concurrent twin, so the sequential question is the
  necessary condition and is the cheaper one. What a pair does is unmeasured here.
- **The planner.** Step 3a of the plan that preceded this campaign measured the IK solutions
  across sides as identical to 0.000000° at identical latency. That reading is not re-taken and
  not appended to.
- **Orientation.** The instrument returns position only (§4, I1). A campaign that measured
  orientation would be a different campaign with a different door.
- **Any rate.** Every number here is a count or a value over the trials that ran.

## §2 The mechanism as recorded, read at `BASE_COMMIT` before any trial

**The seed's path is one hop and is fully read.** `scripts/scenario:90` assigns the default
`20260824` host-side; `_lib.sh:1007-1013` carries every `CITE_*` variable into the container;
`simulation.launch.py:441-469` (`_seed`) returns `None` for an unset or empty value and raises
`PlanError` for a malformed one; `simulation.launch.py:475-476` appends `--seed <value>` to the
`gz sim` command line only when it is not `None`. That is the whole plumbing.

**Two facts read here that bear directly on what the owner watched.**

- **`./scripts/sim` sets no seed at all.** `grep -rn CITE_PHYSICS_SEED scripts` reaches
  `scripts/scenario:90` and nothing else, so a `./scripts/sim` or `./scripts/sim --pair` run
  omits `--seed` entirely. Whatever the flag does or does not do, **it was not in play in the
  paired runs that prompted this campaign.**
- **The generated world declares no engine, no solver and no seed.** `cell_b.sdf:9-12` is
  `<physics name="default" type="ignored">` with `max_step_size` `0.001` and `real_time_factor`
  `1`; `grep -rn "<engine\|<solver" --include=*.sdf --include=*.j2` returns nothing; SDFormat has
  no seed element (`test_simulation_launch.py:520`). Gazebo Harmonic therefore loads its default
  physics plugin, DART.

**The evidence that the seed does not reach the physics solver has no recorded instrument.** It
appears in exactly two prose sentences — `ADR-0027:474-478` and
`docs/reference/toolchain.md:118` — and **neither records a command, a tool, a library list or an
output.** The `nm -D -u … | c++filt` recipe this project remembers it by belongs to the
**adjacent** OMPL check at `toolchain.md:88-97`, whose `aarch64-linux-gnu` path shows that block
ran on an arm64 image. **This host is x86-64** (§9). So the architecture attribution is by
proximity and not by record, and arm S exists to close that.

**And the scan, taken at face value, answers a narrower question than Q1.** It rules out one
path from the flag to the solver. It says nothing about whether a run reproduces: a fixed-step
rigid-body integrator can be perfectly deterministic while drawing from no RNG at all.

**The prediction this campaign is scored against, written before any trial.** Arm A reproduces
(DART is a deterministic integrator and nothing seeds it), arm B shows no effect (the scan is
right), and arm C **does not** reproduce — because `gz_ros2_control` runs the controller manager
as a Gazebo **system plugin**, in lockstep with physics, while `move_group` and the skill server
are separate asynchronous processes, so *when* a trajectory lands relative to a physics step
varies between runs and that is a different physics input. **If that is not what we see, the
reading above is wrong and the campaign says so.**

**A prior result exists, is unpublished, and is not appended to.** `scripts/scenario:56-61`
records that `pick_and_place` run four times under one seed produced two distinct failure modes,
each twice — *"that measurement predates ADR-0027 and has not been repeated under it."* It is in
no campaign directory. Arm C is its successor in question and **not** in sample: no count here is
added to it.

## §3 Arms, and rule T

| Arm | What runs | What it answers |
|---|---|---|
| **A** | the probe world, **no ROS**, one body off equilibrium, **the same seed** every trial | Q1 |
| **B** | the same probe, **a different seed** per trial | Q2 |
| **A′** | the same probe, the same seed as A, initial pose perturbed by **1e-6 m** in x | the sensitivity control |
| **C** | the whole cell — `./scripts/scenario pick_and_place --zone cell_b`, **one seed**, twice | Q3 |
| **S** | the symbol scan, **re-run with its command written down**, in this image on this host | the instrument gap in §2 |

**Rule T — the arms are not each other's evidence.** Every verdict is stated per arm. §7's rules
are applied to each separately, and Q4's answer is the only statement permitted to combine two.

**Rule N, inherited from the stall-band campaign, and load-bearing here.** A null is never a
clearance. If arm A′ does not move the metric, then arms A and B have not been shown capable of
detecting a difference, **their agreement evidences nothing**, and T1 and T2 are **NOT
ADMISSIBLE** rather than passing. This is the rule most likely to fire in this campaign and it
is registered first for that reason.

## §4 Instruments, registered before the first trial

- **I1 — body position.** `cite_bringup.gz.ModelPoses.position()`
  (`workspace/src/cite_bringup/cite_bringup/gz.py:174-234`), which takes the partition from the
  plan through the one door ADR-0042 mandates. It subscribes once to
  `/world/<world>/dynamic_pose/info` and parses `gz.msgs.Pose_V`; the coordinates are protobuf
  **doubles**, so full precision reaches the record.
  - **Registered limit: it returns position only, no orientation.** A tumbling box's orientation
    is the more sensitive channel and this door does not offer one. This is recorded as a limit
    of the campaign, not worked around with a second subscriber.
  - **Registered hazard: `position()` returns `None` both before the first snapshot and for a
    model that is absent** (`gz.py:189-195`). The harness treats first-snapshot arrival as an
    **event** and never as a sleep (V4); a `None` after that event means absent.
- **I2 — the at-rest rule.** Two samples taken at least **1.0 s** apart whose every coordinate
  agrees to **< 1e-9 m**. `ModelPoses` keeps only the newest snapshot and is read at a
  **wall-clock** instant, so two runs sampled while the body still moves would be compared at
  two different *simulated* times. A trial that does not reach rest inside a **120 s** wall
  ceiling is an **instrument loss** under V11 — never a quiet trial.
- **I3 — arm C's outcome.** The work-piece's position by I1 after the scenario's cycle
  assertions have passed; the scenario's own verdict line; the run's wall duration; and **which
  planner answered each motion**, read from the run log (`scripts/scenario:170-180`).
- **I4 — preconditions, recorded per block as fields.** `gz sim --help` lists `--seed`;
  `docker ps` empty; `git rev-parse HEAD`; `git status --porcelain` at **both** ends of the
  block; host load average; `uname -m`.
- **I5 — arm S.** `nm -D -u <lib> | c++filt | grep -i rand` over every shared object under
  `gz_physics_vendor` and `gz_dartsim_vendor` in `cite-digital-twin:dev` on this host. The
  command, the library list and the **full** output go into `raw/`, whatever they say.

### §4.3 What is deliberately not an instrument

- **The GUI.** No trial runs with a Gazebo GUI; a rendered window is a load confound.
- **A screenshot or a visual reading.** Nothing here is decided by looking.
- **Gazebo's own `real_time_factor` field.** It over-reports under starvation by up to 4.15x
  (`2026-08-29-real-time-factor-conditions`), and nothing in this campaign reads it.
- **The scenario's pass/fail as a proxy for reproducibility.** Two runs can both pass and put the
  part in different places; that is the whole of Q3.

## §5 What varies, what is held fixed

**Varies:** the arm (A, B, A′, C), the seed value within arm B, and the 1e-6 m offset within
arm A′.

**Held fixed:** one machine (§9), one image, one commit, one checkout, one writer; headless
throughout; no pair; zone `cell_b`; the probe body's mass, inertia and friction, copied from
`tests/scenarios/pick_and_place.py:_workpiece_sdf`; the probe world's `<physics>` block, held
equal to the installed generated world's by V-physics; `max_step_size` `0.001`, which
`tools/cite_tools/generate/world.py:31-34` records as *"the value a scenario's determinism
depends on"*.

### §5.3 What a healthy trial means, defined before the data

- **Arms A / B / A′:** the server started, a first snapshot arrived, the body reached rest under
  I2 inside the ceiling, and two independent samples were recorded.
- **Arm C:** the scenario printed a verdict line and the work-piece position was read before
  teardown.
- **A trial that never reached readiness is not a quiet trial; it is an instrument loss under
  V11.**

## §6 Design, sample size and order

**One invocation = one trial = one JSON record.** The shape is copied from
`2026-08-31-capacity-and-clock-deficit/harness/trial.py`; a trial whose record already exists is
skipped rather than re-run, and no arm is topped up.

| Arm | n | Why this n |
|---|---|---|
| A | 5 | A determinism question is **binary per trial**. Five is enough to catch a difference and is not enough to estimate a rate — and §7 is written so that it produces an honest verdict at that resolution rather than a confident number. |
| B | 5 | Paired against A trial for trial under V-order. |
| A′ | 2 | It is a control on the instrument, not a measurement of the cell. |
| C | 2 | Two runs is what Q3 asks — *the same thing twice*. It costs about twenty minutes and it is what the plan's own step called for. |
| S | 1 | It is a scan, not a trial. |

**n is a judgement, not a derivation**, and it is what fits the wall clock on this host.

**V-order — alternate, do not block.** The directory README's *"Interleave, do not block"*
cannot apply within a run when the condition **is** the run: two seeds cannot share a bring-up.
The departure is registered here rather than taken silently, and it is compensated the only way
available — arms A and B are run **A B A B A B A B A B**, so that drift in machine state over
the block does not align with the condition.

**Exactly one shakedown**, published under `raw/shakedown/`, excluded from every figure, and it
may not set or adjust any threshold in this file.

## §7 Thresholds — the decision rules, applied literally

| # | Question | Rule |
|---|---|---|
| **T1** | Q1 | Over arm A's 5 trials, every pairwise coordinate difference **< 1e-9 m** ⟹ **REPRODUCIBLE AT 1e-9 m**. Any larger ⟹ **NOT REPRODUCIBLE**, reported with the maximum \|Δ\| and never rounded away. The resolution is named in the verdict: agreement here is **INDISTINGUISHABLE**, never **IDENTICAL** — the instrument bounds the claim. 1e-9 m is a judgement, chosen an order below the perturbation T3 uses and far below anything physically meaningful for a 50 mm box; it is not a derivation. |
| **T2** | Q2 | Arm B's set compared against arm A's. Any difference **> 1e-9 m** ⟹ **THE SEED REACHES A PHYSICAL OUTCOME**, and ADR-0027:480 is wrong on this host. No difference ⟹ **NO EFFECT DETECTED**, which is **not** the sentence *"the seed does nothing"* and may not be written as one unless T3 reads SENSITIVE. |
| **T3** | the control | Arm A′ against arm A. A 1e-6 m initial offset must move the final position by **> 1e-6 m** ⟹ **SENSITIVE**. Otherwise ⟹ **INSENSITIVE**, rule N fires, and **T1 and T2 are NOT ADMISSIBLE.** |
| **T4** | Q3 | Arm C's two work-piece positions agreeing to **< 1e-6 m** ⟹ **THE CELL REPRODUCES**; otherwise **THE CELL DOES NOT REPRODUCE**, with the \|Δ\| and the wall-duration difference reported **as two values over two runs, never as a rate**. The 1e-6 m is three orders below the 50 mm part and is a judgement. |
| **T5** | Q4 | The sentence *"the irreproducibility is in the asynchronous coupling and not in the solver"* may be written **only** when T1 reads REPRODUCIBLE **and** T3 reads SENSITIVE **and** T4 reads DOES NOT REPRODUCE. In every other combination the campaign states which combination it got and answers Q4 **UNRESOLVED**. |
| **T6** | §2's gap | Arm S's output, with its command, its library list and `uname -m`. **Reported; no pass/fail.** It is an instrument being written down, not a hypothesis being tested, and it cannot by itself confirm or refute T2. |

## §8 Explicitly not measured, recorded here rather than discovered later

- **Whether two concurrent sides agree.** §1.2. No pair is run.
- **Orientation, contact forces, joint trajectories.** One position per trial is the whole
  instrument.
- **Where inside arm C the divergence accumulates.** Q4 localises it to a layer, not to a line.
- **Whether `cell_a` behaves the same.** `cell_b` only.
- **Anything about hardware.** Both sides of everything here are simulated.
- **Whether a different `max_step_size` changes any verdict.** It is held fixed.

## §9 The machine, named

11th Gen Intel Core i7-11800H @ 2.30 GHz, 16 logical CPUs, 31 GiB RAM, **x86_64**, Linux, Docker.
**One machine.** Every figure this campaign produces is a figure about this host — and the
architecture is itself load-bearing here, because §2's gap is that the claim under test was
recorded on an arm64 image.

## §10 Validity rules, registered before the first trial

*A rule that only ever confirms is not a rule.*

- **V1 — clean tree.** `git rev-parse HEAD` and `git status --porcelain` taken at **both ends**
  of every block and written **into the record as fields**. The analyser drops any row without
  them. `git merge-base --is-ancestor 79b1acd HEAD` must succeed.
- **V2 — the thing that actually ran.** Each trial records the seed it was given, read back from
  the command line it launched, and not from the value it intended to pass.
- **V3 — the world that actually ran.** Each trial records the SHA-256 of the world file it
  launched. Two trials with different world hashes are not comparable and are not compared.
- **V4 — subscription as an event.** The first snapshot must have arrived before any sample is
  taken. Reliable QoS is a promise to matched subscribers only; treat the match as an event,
  never as a sleep.
- **V5 — one writer.** One checkout, one writer, for the length of a block.
- **V6 — no rebuild mid-campaign.** The workspace is built once, before the first block, and the
  build is recorded in `raw/provenance.txt`.
- **V7 — load is flagged, never excluded.** A load threshold chosen after seeing the data is a
  threshold chosen by the data.
- **V8 — n is what it was.** No arm is topped up after seeing its numbers.
- **V9 — no threshold moves.** A threshold discovered to be wrong is applied literally and
  recorded as wrong, and the disagreement becomes a numbered deviation in `ANALYSIS.md`, applied
  to data already collected.
- **V10 — the partition door.** Every Gazebo-transport process goes through `cite_bringup.gz`.
  An unpartitioned `gz model --list` reaches no world and exits 0.
- **V11 — instrument loss is counted, never quiet.** A trial whose instrument returned nothing is
  excluded, **counted and reported separately from every other exclusion**, and never recorded as
  a trial in which nothing happened. Above 20 % per arm the verdict is **NOT ADMISSIBLE**.
- **V-physics — the probe is the cell's physics.** Before the first trial the harness compares
  its probe world's `<physics>` block against the **installed** generated world's, read through
  `ros2 pkg prefix cite_generated`, and refuses to run if they differ. Otherwise arm A measures a
  different simulator from the one the cell runs.
- **V-container — no live container.** `docker ps` is empty before every block. CLAUDE.md §2
  records that a run taken while a `dev` container is up is not a reading of this repository.
- **V-planner — arm C flags the fallback.** A trial in which OMPL answered any motion is flagged
  and reported separately, because an unseedable planner would confound Q3 with a question this
  campaign is not asking. It is not silently pooled with a Pilz-only trial.

## §11 Honesty bounds, fixed in advance

- **A null is not a clearance.** If arm A and arm B agree, that is evidence about the seed only
  when T3 has shown the metric can move. Rule N, and it is the rule most likely to fire here.
- **A null is not a pass.** "No difference detected at 1e-9 m" is not "identical", and
  `ANALYSIS.md` writes the resolution beside every agreement.
- **`ANALYSIS.md` states rule T and rule N beside every verdict.**
- **Every count is a count over the trials that ran.** Not a rate. Five trials on one machine at
  one commit is five trials on one machine at one commit.
- **The prediction in §2 is scored, including where it is wrong.** A campaign that only ever
  confirms its own reading is not a measurement.
- **Nothing here may be cited as evidence about the physical cell**, about `cell_a`, about a
  pair, or about any host but §9's.
