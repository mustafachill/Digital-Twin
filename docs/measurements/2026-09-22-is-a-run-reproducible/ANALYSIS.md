# Analysis — is a run of this cell reproducible at all, and where does the irreproducibility enter?

**Verdict in one line: the whole cell put the work-piece in two places 0.763 mm apart under one
seed, and this campaign is not permitted to say where that comes from — because its own control
could not move the metric by more than the perturbation it injected, by a margin of
1.17e-16 m.**

- **Taken:** 2026-09-22, one machine (§9 of [`criteria.md`](criteria.md)), x86_64
- **Criteria frozen at:** `6c66cb9`, before the harness existed
- **Harness frozen at:** `deb2911`, before the first trial
- **Trials:** 14 registered, 14 ran, **14 valid, 0 instrument losses in every arm**
- **Thresholds moved:** none. **Arms topped up:** none. **Deviations:** three, below.

| # | Question | Verdict |
|---|---|---|
| **T1** | Q1 — is the physics engine reproducible? | **NOT ADMISSIBLE** (rule N) |
| **T2** | Q2 — does `gz sim --seed` change a physical outcome? | **NOT ADMISSIBLE** (rule N) |
| **T3** | the control — can the metric move? | **INSENSITIVE** — **rule N fires** |
| **T4** | Q3 — does a run of the whole cell reproduce? | **THE CELL DOES NOT REPRODUCE** |
| **T5** | Q4 — where does the irreproducibility enter? | **UNRESOLVED** |
| **T6** | the instrument ADR-0027 never recorded | **REPORTED**, no pass/fail |

---

## 1. The one thing this campaign establishes

**T4 is the only verdict here that is admissible, and it is a hard one.** Two runs of
`./scripts/scenario pick_and_place --zone cell_b`, same seed `20260824`, same world, same
commit, same machine, minutes apart:

| | C_01 | C_02 | difference |
|---|---|---|---|
| work-piece final position | `[0.49917458877176435, 2.9991366210913433, 0.624999819534483]` | `[0.499937533896322, 2.9991519749669706, 0.6249999795624329]` | |
| largest coordinate \|Δ\| | | | **7.629451245576568e-4 m** |
| cycle duration, as the scenario measured it | 70.128 s | 65.441 s | **4.687 s** |

The threshold was **1e-6 m**. The measured divergence is **763 times** it.

**Both runs passed.** Both printed the bare `Scenario 'pick_and_place' passed`, so cycle and
post-shutdown teardown both. **Both were Pilz-only** — V-planner flagged neither, on restricted
**and** region-unprefixed counts of 0, so no unseedable OMPL motion is inside this verdict.
That is §4.3's registered point demonstrated: **a scenario passing is not a statement that the
run reproduces**, and two green runs put the part in two different places.

**Two runs, one machine, one commit, nothing registered about frequency. That is not a rate.**

## 2. Why the other verdicts are refused, and what the figures were

**Rule N fired.** [`criteria.md`](criteria.md) §3 registered it first and said it was the rule
most likely to fire here. It was right.

The control, arm A′, perturbs the box's initial x by **1e-6 m**. T3 declares the metric
SENSITIVE when that moves the final position by **more than 1e-6 m**. All ten A′-vs-A pairs
returned the identical figure:

```
delta = 9.999999998830389e-07 m      delta / perturbation = 0.9999999998830389
```

**The perturbation passed through at unit gain and was not amplified at all**, and it landed on
the failing side of the threshold by **1.1696e-16 m**. So T3 reads INSENSITIVE, rule N fires,
and **T1 and T2 are NOT ADMISSIBLE**.

**The figures those two verdicts would have rested on are published, labelled as figures and
not as verdicts**, because §11 forbids reading an agreement as a result when the control did not
clear:

- arm A, five trials, one seed: maximum pairwise \|Δ\| **0.0 m** — the final positions are
  identical in every printed digit.
- arm A against arm B, 25 pairs across five different seeds: maximum \|Δ\| **0.0 m**; within-A
  spread 0.0, within-B spread 0.0.

**Nobody may write that arm A was shown to reproduce, or that the seed was shown not to reach
the physics.** Those are exactly the sentences rule N exists to stop, and the campaign stops
them against its own prediction.

**T5 is therefore UNRESOLVED.** The registered sentence — *"the irreproducibility is in the
asynchronous coupling and not in the solver"* — requires T1 REPRODUCIBLE **and** T3 SENSITIVE
**and** T4 DOES NOT REPRODUCE. What came back is `NOT ADMISSIBLE / INSENSITIVE / THE CELL DOES
NOT REPRODUCE`. **The sentence may not be written, in that form or any weaker one.**

## 3. Deviations, numbered, applied to data already collected

### D1 — T3's threshold is unsatisfiable by construction on this probe world

**The threshold was wrong, it was applied literally (V9), and it is recorded as wrong rather
than corrected.**

The probe world's ground plane is infinite and centred, so the dynamics are **exactly
translation-equivariant in x**. A perturbation along x can therefore only ever return ≈1e-6 m,
and T3 demands strictly *more*. **The rig could only ever have read SENSITIVE by floating-point
luck**: had `0.0168715895203964 + 1e-6` rounded one unit in the last place the other way, T3
would have read SENSITIVE, T1 and T2 would have been admissible and T5's sentence would have
been permitted — **on identical physics**.

So the admissibility of three verdicts turned on a rounding bit. That is a defect in the
criteria I froze, discovered by the measurement, and it cost fourteen trials to find a property
of the rig's own geometry.

**It is not grounds for a re-run and it is not used to rescue any verdict.** What it changes is
what a *future* campaign must do: perturb along an axis the dynamics are not equivariant in, or
perturb a rotation, and state the expected gain before the first trial.

**What the data do show about the instrument, stated as a figure and not as a rescued verdict:**
the recorded difference between A′ and A is 1e-6 m, which is **a thousand times** T1's 1e-9 m
resolution. The instrument transmits a difference of that size to the record. It has **not**
been shown to transmit a smaller one, nor a difference in *timing* rather than position, and the
rule keys on the threshold rather than on this observation.

### D2 — V-container's per-row field cannot carry a reading

All twelve probe rows record
`"<error FileNotFoundError: … 'docker'>"` for the container check, because the probe trials run
**inside** the container, where the docker CLI does not exist. The refusal that actually
enforces V-container is host-side, in `run_campaign.sh`, and it is real. The analyser labels the
section honestly rather than printing a pass.

### D3 — `provenance.txt`'s `docker_ps_at_start` is empty, and empty renders as "not recorded"

The heredoc block is present and empty — which is the desired state, no container running — but
the analyser prints an empty block identically to a missing field. **The one host-side record of
V-container's precondition therefore reads as `<not recorded>` rather than as "empty".** The
`tester` verified independently that `docker ps -a` returned nothing before and after the
campaign.

## 4. The prediction in §2, scored

[`criteria.md`](criteria.md) §2 registered a prediction before the first trial and required it to
be scored including where it is wrong.

| predicted | verdict | scored |
|---|---|---|
| arm A reproduces | NOT ADMISSIBLE | **not as predicted** |
| arm B shows no effect | NOT ADMISSIBLE | **not as predicted** |
| arm C does not reproduce | THE CELL DOES NOT REPRODUCE | **as predicted** |

**One of three.** The nuance stated precisely rather than softened: the underlying *figures* for
A and B were exactly what §2 predicted — 0.0 m in both — but the campaign's own control forbids
crediting them. **The prediction was not vindicated; it was rendered unscoreable by its own
control**, which is what a control is for.

## 5. Arm S — the instrument ADR-0027 never recorded, and what it adds

[`criteria.md`](criteria.md) §2 records that the claim *"the seed does not reach the physics
solver"* lives in two prose sentences with **no command, tool, library list or output** written
down anywhere, and that the `nm` recipe this project remembers it by belongs to the **adjacent**
OMPL check, run on an **arm64** image. This host is x86_64.

The scan is now in `raw/symbol_scan.txt` with its command, its seventeen libraries, both vendor
roots confirmed present, and `uname -m`. Two findings:

1. **ADR-0027 is confirmed on this architecture.** No gz-physics plugin references
   `gz::math::Rand` — including `libgz-physics7-dartsim-plugin.so.7.8.0`, the one that is
   actually loaded.
2. **And the record's implication is narrower than its sentence suggests.** `libdart.so.6.13.2`
   **defines its own generator** — `dart::math::Random::setSeed`, `getSeed`, `generateSeed`,
   `getGenerator` — and `libdart-external-odelcpsolver.so` defines ODE's `dRand`, `dRandSetSeed`
   and `dRandGetSeed`; `libdart.so` carries undefined references to `dRandInt` and to three
   `std::random_device` symbols. **So the physics stack is not free of randomness. It has a
   generator with its own seed setter, and `gz sim --seed` does not reach it.**

**T6 is reported with no pass/fail and cannot by itself confirm or refute T2.** An undefined
`rand` symbol is a link, not a call site, and a fixed-step integrator can be perfectly
deterministic while drawing from no RNG at all. What the scan settles is that the *instrument*
now exists, on the right architecture, with its output committed.

## 6. What this campaign does NOT establish

- **Where the cell's 0.763 mm comes from.** T5 is UNRESOLVED. No localisation to the solver, to
  the coupling, to the planner or to anything else may be read out of this directory.
- **That the physics engine is deterministic.** T1 is NOT ADMISSIBLE.
- **That `gz sim --seed` has no physical effect.** T2 is NOT ADMISSIBLE.
- **Anything about two concurrent sides.** No pair was run. A run that does not reproduce
  against itself cannot agree with a concurrent twin, so T4 is a necessary condition and not a
  measurement of a pair.
- **Anything about orientation.** The instrument returns position only, which
  [`criteria.md`](criteria.md) §4 registered as a limit.
- **Anything about the cell's contacts, from arm A.** The probe's box strikes an infinite ground
  plane; the cell's is held by two gripper pads, set on a table and placed on a conveyor. This
  matters for a reason worth stating: **a solver deterministic on one plane contact but not on a
  four-body grasp would produce exactly the combination T5 permits.** Had T5 been permitted, this
  limit would still have bounded it. The harness README's limit 6 carries it.
- **Any rate.** Two cell runs and five probe runs on one machine at one commit.
- **Anything about hardware, about `cell_a`, or about any host but §9's.**

## 7. Threats to validity

- **D1 above is the largest**, and it is a threat to the campaign's *design*, not to its data.
- **The arm-C reader is a process this campaign added.** It is a second container holding a
  long-lived subscription to the cell's ~60 Hz `dynamic_pose/info`, and `pick_and_place` normally
  has no persistent subscriber there. **Its confound points the same way as the result** — it
  could make a run less reproducible, which is what T4 reports — and it attaches at a wall-clock
  instant that differs between the two runs. Stated rather than dismissed.
- **V2's arm-C read-back is not an independent check and the record says so.** `SEED_A` is
  `scripts/scenario:90`'s own default, so the printed seed line is identical whether or not the
  variable crossed the container boundary. The field carries
  `seed_readback_is_independent: false`. The probe's read-back *is* independent — it comes from
  `/proc/<pid>/cmdline`.
- **V7 load is flagged and never excluded.** Probe rows 0.31–0.61; C_02 closed at 2.88.
- **The V6 build was a no-op.** It ran before the first block and exited 0, satisfying V6
  literally, but compiled nothing — the install under test predates the campaign. What V6
  protects is that all fourteen trials are trials of one install, and they are.
- **Every probe row's "at rest" is a body at rest and not a frozen subscription**, checked
  because the instrument cannot distinguish them by itself: all twelve rows show **7 distinct
  sampled positions**, a last change 13.608–13.612 s before the last sample, and a server exit 0
  after the full 15 000 iterations.

## 8. What this campaign decides

**Nothing.** [`criteria.md`](criteria.md) §0 said so before any trial: no record is corrected
inside this directory, no threshold anywhere moves, no fix is proposed, and no frozen campaign is
edited. What T4 implies for the project is the project owner's, after reading this.
