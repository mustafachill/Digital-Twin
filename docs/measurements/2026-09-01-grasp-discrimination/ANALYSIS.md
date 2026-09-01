# What separates a grasp from a stall on nothing — both directions, measured

**Verdict, in this campaign's own terms.**

| Direction | Verdict | In one line |
|---|---|---|
| **False negative** (Q1, D1) | **OBSERVED** | A real grasp — witnessed by the work-piece's own contact sensor — is reported empty, and `Pick` returns `EXECUTION_FAILED`. **7 of 7** valid trials at a commanded 48.0 mm. **The first time ADR-0052's defect has been observed firing in this repository.** At 42.0, 45.0 and 47.0 mm it did not fire, in **0 of 8** each, and rule M governs how that may be written. |
| **False positive** (Q2, D5) | **REPRODUCED** | A stall on nothing is reported as a grasp. **18 of 33** valid trials, at every stop width above the band edge; the flip is bracketed to **0.05 mm** and lands where the arithmetic says. Rule N does not fire. |
| **The two arithmetics** (Q3, D4) | **IMMATERIAL** | They disagree by at most **0.049 mm** across the whole 20–85 mm commandable range, below the 0.100 mm registered materiality, and no row of the grid produces a different verdict. **The shape is new**: the term ADR-0052 reports is the smaller of two. |
| **The unvalidated door** (Q4, D6) | **DEMONSTRATED** | A caller-supplied `grasp_width_m` above the validator's ceiling puts the band where the shipped default does not. It is the 48.0 mm condition above. |
| **Does the distribution move with the command?** (D2) | **INCONCLUSIVE** | Not detected (`p = 0.600`), and the non-detection is downgraded by **V5** and unresolved by **rule R**. This campaign cannot answer it at n = 8 per command, and states what n would. |

**And the quantity that was not a registered verdict but is the campaign's most
decision-relevant number:** the measured band edge in commanded-width terms is
**47.698 mm**, and `default-grasp-width-never-closes`'s ceiling is **47.862 mm**. **The
validator's ceiling sits 0.164 mm above the band this cell actually produces.** That is
ADR-0052 §2.3's third door — *"a stall that lands inside the band at a part the validator
was happy with"* — measured for the first time.

- **Campaign:** `docs/measurements/2026-09-01-grasp-discrimination/`
- **Branch / commit under measurement:** `measure/grasp-discrimination`, off `main` at `e51238e`
- **The record that asked for it:**
  [ADR-0052](../../adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), promotion
  gate clause 2. **Its status does not move and no option among A–F is chosen,
  recommended or ranked here.** See §9.
- **`criteria.md` sha256:**
  `33bf39f5fabbf4c8754853b78858e89bcc4852553a79561f7b9f597dcad87351`
  Committed at **`c99d6c3`**, *before* the harness existed and before any trial ran. The
  first data commit is `eeaf903`, and every trial commit is after it.

## 1. What was run

| Arm | Question | Rig | n |
|---|---|---|---|
| **FN** | Q1, Q4 | the shipped cell, headless, `Pick` on a real 50 mm work-piece, four commanded widths interleaved | **32 trials**, 2 blocks of 16; **31 valid** |
| **FP** | Q2 | a real `ros2_control_node` over `cite_test_hardware/JointStopSystem`, **nothing between the pads** | **36 stop trials + 3 controls**, one launch each; **33 valid** |
| **AR** | Q3 | both shipped derivations called directly | **262** swept widths + a **99**-row evaluation-point grid |

**Every figure below comes from the shipped implementations**, never from a copy.
`predicate_eval` compiles `workspace/src/cite_skills/src/gripper.cpp` unmodified
(`sha256 b7688390…`, recorded per build in `raw/predicate_eval_provenance.txt` and
`raw/predicate_eval_host_provenance.txt`); the validator side is
`cite_tools.validate.physical._grasp_discrimination_margin_m`, imported and called on the
`AssetType` loaded from the shipped `model/`. `harness/arithmetic.py` reproduces
ADR-0052's published arithmetic to four decimal places and **is used for no reported
figure**.

**V1 — the geometry that actually ran.** Both FN blocks read the description the running
cell publishes: **13** hull collision references, `geometry_verified: true`
(`raw/FN_B*_geometry.json`). **Every grasp figure here is on convex-hull collision
geometry**, which shipped on 2026-09-01. Every previous grasp figure in this repository is
on vendor meshes, except the hull arm of
[`2026-09-01-hull-grasp/`](../2026-09-01-hull-grasp/ANALYSIS.md).

## 2. The false-negative direction — D1, and it fired

### 2.1 The distribution, per commanded width

`ratio = (reached − commanded) / (2 · tolerance(q_reached))`. **`ratio < 1` is the
predicate reporting no grasp.** All widths in mm.

| `w_cmd` | n | reached min | reached median | reached max | reached IQR | threshold median | ratio min | ratio median | ratio max | **in band** | D1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **42.0** | 8 | 48.109 | 49.776 | 49.977 | 0.153 | 2.1062 | 2.887 | 3.692 | 3.790 | **0** | NOT OBSERVED |
| **45.0** | 8 | 48.691 | 49.828 | 49.930 | 0.340 | 2.1059 | **1.747** | 2.293 | 2.342 | **0** | NOT OBSERVED |
| **47.0** | 8 | 49.224 | 49.906 | 49.967 | 0.671 | 2.1054 | **1.054** | 1.380 | 1.410 | **0** | NOT OBSERVED |
| **48.0** | 7 | 49.071 | 49.202 | 49.954 | 0.429 | 2.1097 | 0.507 | 0.570 | **0.928** | **7** | **OBSERVED** |

Wilson 95 % intervals on the in-band proportion: `[0.000, 0.324]` at 42.0, 45.0 and 47.0;
**`[0.646, 1.000]` at 48.0.**

### 2.2 What "OBSERVED" means here, stated so that it cannot be over-read

At a commanded 48.0 mm, in **all 7** valid trials:

- the work-piece's own passive contact sensor reported **40 finger contact points** —
  V2's witness, and an instrument independent of the quantity under measurement;
- the gripper controller reported `stalled = true, reached_goal = false`;
- the drive joint stopped between **49.07 and 49.95 mm** of opening, against a part
  declared 50.0 mm wide;
- and `cite_skills::gripper_is_holding` returned **false**, so `Pick` returned
  `EXECUTION_FAILED` with `holding = false` and the skill server logged `-> empty`.

All four instruments agree in all seven. The skill server's own detail string on one of
them reads:

> `nothing was picked up: commanded 48.0 mm, reached 49.1 mm, stalled=true. The gripper
> stopped short of its command, but not by enough width to be a part…`

**The part was in the jaws.** That is the defect ADR-0052 states as arithmetic, produced
on demand and reported by three independent instruments plus the production one.

**What it is not.** It is not a rate, and it is not a statement about the shipped
operating point: it took a commanded width **above** the ceiling the validator enforces
(§5), and the shipped 45.0 mm command produced it in none of 8. Rule M therefore governs
the other three columns, and their reading is *"not observed at n = 8 per command, at these
four commands, on this machine"* — **never that the defect does not occur there**.

### 2.3 How close the other columns came, which is rule M's required figure

| `w_cmd` | minimum ratio | margin at that trial | headroom above the band edge |
|---|---|---|---|
| 42.0 mm | 2.887 | 6.109 mm | **3.98 mm** |
| 45.0 mm | **1.747** | 3.691 mm | **1.58 mm** |
| 47.0 mm | **1.054** | 2.224 mm | **0.114 mm** |

**The worst trial at the shipped 45.0 mm command cleared the band by 1.58 mm**; the worst
at 47.0 mm — still inside the validator's ceiling — cleared it by **0.114 mm**, which is
**one part in eighteen** of the threshold and is close to the 0.100 mm resolution of the
instrument the production system prints widths with.

### 2.4 D2 — does the distribution move with the commanded width? INCONCLUSIVE

Kruskal–Wallis across the four commands on the reached width: `H = 1.871, p = 0.600`.
Largest Hodges–Lehmann shift against the 45.0 mm anchor: **0.529 mm** (at 48.0 mm).
`p ≥ 0.01`, so **D2 — NOT DETECTED** by §7.3's rule.

**Two registered rules then downgrade that non-detection, and both fire:**

- **V5, the block effect.** At 48.0 mm the two blocks differ by **0.719 mm** — *larger*
  than the largest between-command shift of 0.529 mm. Block FN_B1's valid 48.0 mm ratios
  are `0.507, 0.926, 0.928` and FN_B2's are `0.554, 0.561, 0.570, 0.599`. **D2 is
  downgraded to INCONCLUSIVE whatever `p` says**, exactly as registered.
- **Rule R, resolution.** Within-condition IQR exceeds the metric's MIS for
  `reached_width_mm`, `margin_mm` and `ratio` at **every one of the four commands** —
  0.153 to 0.671 mm against a 0.100 mm MIS, and 0.074 to 0.321 against a 0.05 ratio MIS.
  Only `threshold_mm` is resolved (IQR 0.0009–0.0040 mm), and that is because the threshold
  barely varies over this narrow band of reached positions.

**What n would resolve it**, which rule R requires this campaign to state: the pooled
within-condition spread implies a standard deviation of about **0.295 mm**, so detecting a
0.100 mm shift at `α = 0.01` with 80 % power needs roughly **204 trials per commanded
width** — about **816 trials**, against this campaign's 32. **This campaign is twenty-five
times too small to answer D2, and says so rather than reporting its own sample size.**

**The registered expected direction is therefore neither confirmed nor refuted.**
`criteria.md` §7.3 registered "weakly increasing in `w_cmd`" and said a decrease, or a move
above 0.5 mm across the span, would be a finding about the mimic servo. The observed
largest shift is 0.529 mm and it is *negative*, which is both of those — **and V5 says the
same data cannot separate it from a block effect.** It is recorded as unresolved, not as a
finding.

### 2.5 The instruments against each other

| pair | agreement |
|---|---|
| I1 (server log, 0.1 mm) vs I2 (`/joint_states`, full precision) | max gap **0.094 mm** across the 31 valid trials, below the log's own resolution |
| I1 verdict vs I2 predicate vs I3 `Pick.Result.holding` vs I4 `Grasp.Result.holding` | **identical in all 31** — 24 holding, 7 empty |

**I4 is a different event and behaves like one.** Re-commanding the same width against the
jaws as they stand moves the reported width by **−0.76 to +0.60 mm** relative to the Pick's
own close. It agreed with I2 on every verdict, which is why it is reported as
corroboration; it is not evidence that the two closes are the same measurement, and that
spread is why `criteria.md` registered it as secondary.

## 3. The false-positive direction — D5, and it reproduced

Command held at the shipped 45.0 mm throughout; the lever is where
`cite_test_hardware/JointStopSystem` stops `arm_1_drive_joint`, with **no work-piece, no
Gazebo and no physics** in the rig at all. All widths in mm.

| stop width | reached | margin | threshold | ratio | `stalled` | `reached_goal` | **predicate** |
|---|---|---|---|---|---|---|---|
| 46.00 | 46.000 | 1.000 | 2.1276 | 0.470 | false | **true** | false |
| 46.50 | 46.500 | 1.500 | 2.1249 | 0.706 | true | false | false |
| 47.00 | 47.000 | 2.000 | 2.1222 | 0.942 | true | false | false |
| 47.05 | 47.050 | 2.050 | 2.1219 | 0.966 | true | false | false |
| **47.10** | 47.100 | 2.100 | 2.1216 | **0.990** | true | false | **false** |
| **47.15** | 47.150 | 2.150 | 2.1214 | **1.013** | true | false | **TRUE** |
| 47.20 | 47.200 | 2.200 | 2.1211 | 1.037 | true | false | **TRUE** |
| 47.50 | 47.500 | 2.500 | 2.1194 | 1.180 | true | false | **TRUE** |
| 48.00 | 48.000 | 3.000 | 2.1166 | 1.417 | true | false | **TRUE** |
| 49.00 | 49.000 | 4.000 | 2.1108 | 1.895 | true | false | **TRUE** |
| 50.00 | 50.000 | 5.000 | 2.1049 | 2.375 | true | false | **TRUE** |

**18 of 33 valid trials report a grasp with nothing between the pads**, Wilson 95 %
`[0.380, 0.702]` — a proportion of the sweep this campaign chose, not a rate of anything.
**D5 — REPRODUCED. Rule N does not fire.**

**The flip is bracketed to 0.05 mm and lands where the arithmetic says.** Not holding at
47.10 mm, holding at 47.15 mm; `criteria.md` §2 predicted the band edge at **47.1215 mm**
from the shipped constants alone, before any trial. The prediction is inside the bracket.

**Where the controller's own flag takes over from the margin**, which §7.6 also asks for:
`reached_goal` is true at stop widths 45.50 and 46.00 mm and false from 46.50 mm up, so the
takeover sits between **1.0 and 1.5 mm** of margin. That brackets the **1.065 mm** that one
`goal_tolerance` is worth in width at the commanded position — ADR-0052 §3's first
checkable claim, confirmed by a different route.

**The rig is exactly deterministic.** Replicate spread in the reported drive position is
**0.0 rad** — bit-identical — at every one of the eleven valid stop widths, across three
launches each. `criteria.md` §6.2 registered that expectation and it held.

**V6 excluded the three 45.50 mm trials**, uniformly and for the registered reason: the
joint came to rest at 0.4466666 rad against a declared stop of 0.4481009 rad, 1.43 mrad
away, outside V6's 1.0 mrad clause. It never reached the stop — the goal-tolerance branch
terminated the close first — so the stop did not engage and the trial is not about a
stopped joint. Two of the three also failed V6's announcement clause. **The exclusion is
conservative against this arm's headline** (a 45.50 mm stop would have been a non-holding
trial) and it is reported rather than absorbed.

### 3.1 The control refutes its own registered prediction, and the refutation is the mechanism

`criteria.md` §7.9 **P4** predicted that FP-C — the same rig on plain
`mock_components/GenericSystem`, no stop — would report `reached_goal = true, stalled =
false`, so the margin would never run. That is ADR-0052 §3's prediction about the
production backend. **P4 is refuted.** All three controls reported `stalled = true,
reached_goal = false` at a drive position of **0.29999997 rad** — 60.92 mm of opening
against a 45.0 mm command — and the predicate returned **true**.

**The cause is in the log, measured rather than inferred:**

> `actual: [Joint: 'arm_1_drive_joint', position: 0.000000, velocity: 0.000000], command:
> [position: 0.452793], limited: [position: 0.006667] with desired period: 0.006667 sec`

Two facts, both readable there. The controller manager rate-limits the position command to
**0.006667 rad per 6.667 ms cycle** — exactly the L0 `max_drive_rate_rad_s` of 1.0 rad/s —
so the joint ramps rather than jumping. And `GenericSystem` writes **velocity 0.000000**,
because it mirrors commands into states and nothing claims the velocity command interface.
The gripper controller's stall detector therefore sees a sub-threshold velocity from the
first cycle and declares a stall after `stall_timeout = 0.3 s` — which at 1.0 rad/s is
**0.300 rad**, the position observed, to seven decimal places.

**So the reading is: FP-C did not test what it was designed to test.** It is a property of
mock hardware's dead velocity channel, not of the shipped backend, and **it may not be
counted as evidence about the production system in either direction**. Its value is as a
controlled comparison: the same command, the same controller, the same timeline, and only
the hardware plugin differing — the `JointStopSystem` trials do **not** stall at 0.3 rad,
they rest exactly at their declared stops, because that plugin differentiates the clamped
position and says so in its own banner (*"6 joint(s) report a differentiated velocity"*).
**The fixture is valid because the control failed.**

**One incidental observation, recorded and not pursued.** `mock_components/GenericSystem`
fabricates a stall on a ramping joint after exactly `stall_timeout`. Nothing in this
campaign's scope depends on it and no finding is claimed from it; it is written down
because it is a property of a fixture this repository uses elsewhere.

## 4. The two arithmetics — D4 IMMATERIAL, and the shape is new

`cite_skills::gripper_width_tolerance_m` linearises at the **reached** position;
`_grasp_discrimination_margin_m` takes an exact finite difference at the **commanded** one.
**The disagreement therefore has two components, and ADR-0052 reports only the first.**

**The linearisation term**, both evaluated at the commanded position, over 262 widths from
20.0 to 85.0 mm:

| `w_cmd` | 20.0 | 45.0 | 47.86 | 85.0 |
|---|---|---|---|---|
| C++ (linearised) | 2.1997 | 2.1327 | 2.1174 | 1.7448 mm |
| validator (finite difference) | 2.1999 | 2.1380 | 2.1232 | 1.7581 mm |
| difference | +0.00025 | **+0.0053** | +0.0058 | **+0.0133 mm** |

Monotonically increasing in `w_cmd` across the whole range. The 45.0 mm figure reproduces
ADR-0052's to four decimals. **P5 confirmed.**

**The evaluation-point term is the larger one.** Over the 99-row grid of the four commands
crossed with plausible stalls, the **total** disagreement between what the two
implementations actually compute runs **+0.0064 to +0.0493 mm**, median **+0.0236 mm** — up
to **3.7 times** the largest linearisation term anywhere in the commandable range. At a
45.0 mm command with a 50.0 mm stall it is **+0.0331 mm**, six times the +0.0053 mm
ADR-0052 quotes.

**D4 — IMMATERIAL**, by the registered rule: the largest total, **0.0493 mm**, is below the
0.100 mm materiality, and **0 of 99** grid rows produce a different verdict from the two
implementations. **This is not a statement that the P1 hole is harmless.** What the
registered rule says is that no instrument in this system reports widths finely enough to
see the present disagreement — and the hole ADR-0052 §5 names is that two independent
derivations of one policy are free to diverge on the *next* edit. A small disagreement
today is not evidence about that.

**And one figure that was quoted rather than verified is now run.** ADR-0052 records the
validator's ceiling as 47.86 mm and states that *"the validator was not run — no Python
environment in this worktree"*. Run here on the shipped model, the rule computes a
discrimination of **2.137972 mm** at the shipped default and a ceiling of **47.862028 mm**;
a declared default of 47.86 mm is accepted and one of 48.00 mm is refused. The quoted
figure is confirmed.

## 5. D3 and D6 — where the band sits, and the door nothing validates

### 5.1 The band edge against the measured distribution

Pooled over all 31 valid FN trials: reached width median **49.804 mm** (IQR 0.682 mm),
threshold median **2.1061 mm** (IQR 0.0041 mm).

- **Band edge in commanded-width terms: 47.698 mm** — the largest command at which the
  observed median stall still clears the band.
- **Distance from the shipped 45.0 mm command: 2.698 mm**, which is **3.96 pooled IQRs** of
  the reached width.
- **`default-grasp-width-never-closes`'s ceiling is 47.862 mm.** The measured band edge is
  **0.164 mm below it.**

That last line is the campaign's most decision-relevant quantity and it is reported as a
quantity. The validator computes its ceiling against the work-piece's **nominal** 50.0 mm;
the cell stalls at a median of 49.804 mm. **A declared default that the validator accepts
can therefore already sit inside the band this cell produces** — ADR-0052 §2.3's third
door, which that record calls *"the one this cell is actually near"*, measured. It is
0.164 mm on this machine, at this timestep, with this part, on this arm, at n = 31.

### 5.2 D6 — a caller-supplied width can put the band somewhere worse

**DEMONSTRATED.** 48.0 mm is above the 47.862 mm ceiling
`default-grasp-width-never-closes` enforces, so it is a width the validator **refuses as a
declared default** — verified by running the rule (§4). Nothing validates it as a
`Pick.Goal.grasp_width_m`: `resolve_grasp_width` takes any positive request verbatim. In
this campaign that unvalidated width produced **7 of 7** in-band trials where the shipped
45.0 mm default on the same blocks produced **0 of 8**.

## 6. Deviations, numbered, applied to data already collected

`criteria.md` was frozen at `c99d6c3` and **no threshold, rule, MIS or exclusion in it was
changed** after the first trial. These are the four places where reality had to be recorded
rather than the definition adjusted.

**D-1 — three FN_B2 attempts were discarded by V1 before collecting a trial, and the
harness was not edited to prevent it.** `measure_fn.py` reads the running description
immediately on start, before `robot_state_publisher` is serving; block FN_B1 won that race
and three consecutive FN_B2 attempts lost it, each reporting `description_chars: 0` and
aborting. **V1 prescribes exactly this** — *"a block that disagrees with its own label is
discarded, not relabelled, and the discard is reported"* — so all three are published under
`raw/logs/FN_B2_attempt{1,3}_discarded_*` and `raw/FN_B2_attempt1_discarded_geometry.json`.
Attempt 1's own sim log reaches `CITE_SIDE_READY`, so **the cell was never the fault**. The
resolution was a new block runner, `run_fn_block_after_ready.sh`, which gates on the cell's
own readiness token rather than on a sleep (P4). **It changes the runner and not the
measurement:** `measure_fn.py` is byte-identical for both blocks, and the domain guard,
launch command and teardown sweep are copied verbatim. **FN_B1 used `run_fn_block.sh`;
FN_B2 used `run_fn_block_after_ready.sh`.** Both blocks passed V1 with 13 hull references.

**D-2 — `analyse.py` had to learn from the data which report line is I1.** `Pick`'s first
physical act is to *open* the jaws, so the skill server emits **two** report lines per
`Pick` — one at the gripper's full 88.9 mm opening and one at the grasp. The analyser
originally took the first, which would have compared I2 against the opening and excluded
every trial under V4. It now selects by commanded width and returns nothing when the
selection is ambiguous, so an ambiguous trial is excluded rather than guessed at. **This
changed no threshold**; it corrected which number a registered rule is applied to.

**D-3 — one trial was excluded by V4 and the exclusion is inconvenient.** FN_B1 trial 8,
commanded 48.0 mm: I1 printed 49.9 mm and I2 read 49.786 mm, a gap of **0.114 mm** against
V4's 0.100 mm clause. It is a marginal exclusion, it is **not** a rounding artefact (49.786
rounds to 49.8, not 49.9), and it **removed an in-band trial** — that is, it made the
false-negative arm's headline count smaller rather than larger. Applied literally, as
registered.

**D-4 — `raw/logs/` was gzipped after collection.** A storage decision taken after every
figure was derived; no log content changed. The hull-grasp campaign publishes its logs the
same way.

**One thing that is not a deviation and is stated so it is not mistaken for one.**
`analyse.py` was written after the data was collected. That is unavoidable for an analyser
and is what its own docstring says; every constant in it carries the `criteria.md` section
it is quoted from, and it introduces no metric, threshold or exclusion that file does not
already carry.

## 7. The machine, and what host load could and could not reach

| | |
|---|---|
| Host | Apple **M4 Pro** (`Mac16,8`), 12 cores, 24 GiB, macOS 26.5.2 (Darwin 25.5.0, build 25F84) |
| Container | Docker Desktop 28.5.1, Linux VM allocated **12 CPUs / 7.65 GiB**, `overlayfs` |
| Isolation | `COMPOSE_PROJECT_NAME=cite-agent-a424bd5e5ac7644b0-2554422286`, `ROS_DOMAIN_ID=73`, own build/install/log volumes |
| Build | `./scripts/build` — `Summary: 23 packages finished` |

**Host load, recorded before each block rather than claimed.** 1-minute load average
**3.21** when `criteria.md` was written, **3.83** before FN_B1, **6.45** before FN_B2, on 12
cores, with **11 unrelated containers** running throughout — a Supabase stack belonging to
another project — plus a browser and macOS file providers. **This host was not quiet and
could not be made quiet**, exactly as the capacity campaign found and said.

**What that threatens.** Every FN quantity is simulation state sampled in simulation time —
the drive joint's own position, contact-sensor stamps, and widths derived from a static
linkage — so load moves how long a trial takes and not where a joint stops. The one route
to the physics is a missed real-time deadline changing the interleaving of controller
updates with physics steps, which is what V5 exists to catch; **V5 fired**, and the block
carrying the higher load average (FN_B2, 6.45) is the one whose 48.0 mm ratios are
systematically lower and tighter. **This campaign cannot separate that from a block
effect**, and D2 is INCONCLUSIVE partly for that reason. The FP and AR arms have no physics
at all, and the FP arm is bit-identical across replicates.

**No real-time-factor claim is made from this campaign.**

## 8. What this campaign does not establish

Registered in `criteria.md` §8 before the first trial, and none of it moved.

- **Anything about the physical gripper.** ADR-0052 records that there is no
  `GripperActionController` on the hardware path at all — the vendor macro emits the
  gripper's `<ros2_control>` block only for the simulated plugin. **Nothing here is a P2
  result**, and the Phase 2.B bring-up is the only thing that would settle it.
- **A rate of anything.** Every count is over the trials that ran: n = 8 per FN command,
  n = 3 per FP stop width, one machine, one timestep, one part, one arm. The 7-of-7 at
  48.0 mm is a count, not a probability.
- **D2 — whether the stall distribution moves with the commanded width.** Not detected,
  downgraded by V5, unresolved by rule R at every width metric, and this campaign is about
  **25x too small** to answer it. §2.4.
- **Why the drive joint reads narrower than the part it holds.** ADR-0052 names the mimic
  servo as a candidate; nothing here isolates it, and this campaign reports the reached
  width without explaining it.
- **Where a real jam stops.** The FP arm produces a *synthetic stop at a declared position*,
  not a fouled finger. It answers what the predicate does with such a stall; it says nothing
  about where a physical jam would land, which is the quantity the margin's real job is
  sized against and which still has no campaign.
- **Whether ordinary free air on the production backend behaves as ADR-0052 §3 predicts.**
  The control that was meant to answer that measured mock hardware's dead velocity channel
  instead (§3.1). **The prediction is untested by this campaign, not confirmed by it.**
- **Any timestep but 0.001 s, any part but the 50 mm cube, any arm but `arm_1`, any effort
  but 60 N, and vendor collision geometry.**
- **Grasp quality.** Whether the part is held *well* is the friction and offset campaigns'
  question. Per ADR-0029 a scenario may assert where a part ends up and may not assert how
  it is held; this campaign reads the close and stops.

## 9. What this campaign does not decide

**Nothing in ADR-0052's options A–F is chosen, recommended, ranked or argued for**, and that
constraint was registered in `criteria.md` §0 before any trial. ADR-0052's status does not
move. Nothing in `model/`, `workspace/src/` or `tools/` was edited; no threshold, ceiling or
tolerance anywhere in the tree was changed, and none may be changed to absorb anything here.

Where a figure above bears on an option, it is a quantity with its consumer named and the
sentence stops there:

| Quantity | Which option consumes it |
|---|---|
| the band edge in commanded terms, 47.698 mm, against the validator's 47.862 mm ceiling (§5.1) | B, D and F all move or derive this edge; E decides whether the two derivations of it stay one statement |
| the false-positive flip at 47.1215 mm, bracketed to 0.05 mm (§3) | B and D both lower the threshold, and this is the width at which lowering it starts admitting stalls on nothing |
| the total disagreement between the two derivations, ≤ 0.0493 mm (§4) | E |
| 7 of 7 in-band at an unvalidated goal-supplied width (§5.2) | the door ADR-0052 records as open; F is the option that changes the reference point it depends on |
| the minimum ratio at the shipped 45.0 mm command, 1.747 (§2.3) | A, which spends this headroom |

**The choice is the project owner's.** This campaign exists to make it decidable.

## 10. Reproduction

`harness/README.md` carries the three commands. `raw/analysis.json` is `analyse.py`'s output
over `raw/`, and every figure above is derived from it or from the trial files it reads.
**Figures stay in this directory** — nothing here is copied into ADR-0052, CLAUDE.md, the L0
comments or any layer document (P1). Cite the directory.
