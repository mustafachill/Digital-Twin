# CLAUDE.md

Canonical working agreement for this repository. Auto-loaded into every session and every
subagent. **This file is the rulebook; `what-we-are-doing.md` is the reason.** When you
need to know *why* a rule exists, read the charter. When you need to know *what to do*,
this file is enough.

`AGENTS.md` points here. Do not duplicate this content anywhere else.

---

## 1. What this is

The **CITE Digital Twin** — a facility-scale digital twin of the Center for Innovation,
Technology and Entrepreneurship at Sam Houston State University, built on ROS 2 and
Gazebo, whose first instrument is a multi-robot xArm work cell.

It is a *twin*, not a simulation: real hardware and the virtual model share one control
interface, and the system continuously measures how far the model is from reality.

It is also a **rebuild**. A first iteration (v1) was archived under `legacy/` and deleted at
the end of Phase 1; it survives only in version control, and **its patterns are not
precedent** — do not reintroduce them. What it taught is
[`docs/reference/v1-lessons.md`](docs/reference/v1-lessons.md); why it was replaced rather
than migrated is [ADR-0001](docs/adr/0001-rebuild-rather-than-migrate.md); the debt that
forced the decision is charter §12.

Full charter — identity, scope, architecture rationale, roadmap: **`what-we-are-doing.md`**.

## 2. Current state — read this before assuming anything exists

**Phase 1 of the rebuild is closed**, as of 2026-08-28: charter §8 records its exit
criterion MET, and records in the same place what that closure rests on and what it does
not cover. Nothing below is retired by the closure — the gap list is still the gap list.
**Phase 2 has since split into 2.A and 2.B (charter v1.9, 2026-08-29) and 2.A's mechanism is
in the tree: a pair has come up, three times on one machine, covered by no test, and an L5
package has since landed beside it — `cite_twin` exists, and what it is and is not is the
Phase 2.A bullet below.** The charter describes the target; the repository is partway there.
Check before assuming.

**Every count below names the command that reproduces it, and every figure names who
measured it and over how many runs.** That is what P7 costs, and this section is where it is
kept or lost. This file has carried a wrong asset count, a wrong pass count, a wrong
account of a flake and a wrong package count; each was caught by someone re-running, never by
someone reading. The fourth is the most recent: `cite_twin` landed, nothing re-ran the
commands below, and **every reproducible count in this section but one was stale at once** —
packages, build, all three `test` figures, the collection, lint, the ADR index and the CI
table. The exception was `./scripts/validate-model`, which had not moved.
**The fifth is a sentence rather than a count, and it was written in capitals**: this section
declared that **no CI run had ever brought the cell up on the collision geometry it ships**,
and one had — the run at `e51238e` completed hours after the re-audit that wrote the sentence.
The collision-geometry item in the gap list below is where that is kept. **A claim about what
has never happened expires the moment the thing runs again, and only re-running catches it.**
**Two re-audits ran on 2026-09-01**, at `dd93488` and again at `abdae38`, each re-running every
command this section names. **Every figure below carries the commit it was taken at**; where a
figure names `abdae38` it is the second re-audit's, and where it names an earlier value with a
date it is that value's history and not a current reading.
**Where a figure names `df91154` it was taken on 2026-09-08 on the branch
`feat/hosted-by-derived`**, which added a third tree-parametrized test file and so moved four
counts: the `tools/tests` collection, `test`'s host half, `test`'s per-package total and the
`lint` walk. Six others were re-run and did not move — `test`'s shell gate, the `tests/`
collection, the ADR index, the `workspace/src` package count, `build`'s summary and
`validate-model`'s cardinality. **All ten were re-run rather than reasoned about**, and the
four that moved are reconciled where they are stated.
**Where a figure names `6d51966` it was taken on 2026-09-08 on `main`, and the CI figures were
re-read from CI logs on that date for the first time since `13bc8e9`** — **eleven commits
back** (`git log --oneline 13bc8e9..6d51966 | wc -l` reads 11 here). **No commit in between
opened a CI log**, because `gh` on this host was unauthenticated; the one that moved a CI
figure over that span, `987e6b6`, moved it on a reading another agent supplied, and the pass
that wrote `13bc8e9` said so where it mattered. `gh auth status` now
reports this host logged in, **two completed `main` runs had happened in the interval and one of
them failed**, and every CI count in this section was stale again — the table, `bringup`'s two
figures, `pick_and_place`'s, the advisory-branch count and the hull-run list, which was stale
in **two** of the three places it appeared. **Not touching a
figure you cannot measure is right; leaving it untouched once you can is how every wrong claim
listed above got written.** The two runs are `34258470163` at `e18251e` and `34280056331` at
`aed36c4`; both were read here with the instrument the `bringup` bullet mandates, and where a
statement below rests on one of them it says so.
**Three counts that no CI run touches moved over the same span and are re-run here**:
ADR-0053 landed, so the ADR index, the `lint` walk and the `tools/tests` collection each
stepped by one, and `test`'s host half stepped with the collection. **`./scripts/test`'s
host half and shell gate were re-run here and its per-package total was not** — see that
bullet.

- **Phase 1.A is closed.** Container image, the `./scripts/*` contract, dependency
  manifests, CI, and the asset policy all exist and work. `external/cite.repos` pins
  `xarm_ros2` to a commit SHA, after the branch was built and driven against our stack
  rather than merely inspected — see the verification table in
  [`docs/reference/toolchain.md`](docs/reference/toolchain.md). `./scripts/doctor` exits 0;
  run it to see the state of any machine.
- **The L0 model and its generators are built and proven** (Phase 1.B). `model/` describes
  the three-arm cell and `workspace/src/cite_generated/` holds everything derived from it:
  descriptions, the world, controller configuration, MoveIt configuration, the planning
  scene, static frames, process topology and the bring-up plan. That directory is
  **generated in its entirety and must never be hand-edited** (ADR-0021).
  `./scripts/validate-model` diffs it against a fresh generator run *and* regenerates in a
  second interpreter under a different hash seed to prove the output is byte-identical; it
  exits 0, reporting `1 zone(s), 7 type(s), 15 asset(s), 5 station(s), across 15 file(s)` in
  this checkout on 2026-09-01 at `abdae38` — re-run by both of that date's re-audits and
  **unchanged since 2026-08-29**, which
  is the one figure in this section neither re-audit had to move. **Re-run again on 2026-09-08
  at `df91154` on `feat/hosted-by-derived` and still identical**, which is worth one line
  because that branch changed a generated artifact: it removed the `hosted_by` key from every
  controller manager in `cell_a_plan.yaml` (ADR-0048 clause 3). The cardinality this line
  reports counts zones, types, assets, stations and files, none of which a removed field
  moves. **Re-run once more on 2026-09-08 at `6d51966` and identical again**, so it remains the
  one figure in this section no re-audit has had to move. The seventh type is the reference
  work-piece, which has no
  instances on purpose (ADR-0030).
  **Ask `./scripts/validate-model` for the cardinality; do not read it out of prose.** This
  file said "fourteen instances" until 2026-08-27 and it was fifteen — one addition, at
  `aef87e6`, falsified the number here, in L0's status line and in ADR-0027 at once, which is
  why ADR-0027's first correction ends *"do not state the cardinality of a generated
  collection in prose."*
  `tools/tests/` holds **1399** tests, counted by collection rather than by a run
  (`.venv/bin/python -m pytest tools/tests --collect-only -q`, this checkout, 2026-09-10 at
  `523ffd9`).
  It said **302** until 2026-08-29, **331** until 2026-08-31, **411** earlier on 2026-09-01,
  **902** later that day, **927** until 2026-09-02, **973** until 2026-09-08, **1023** for
  part of that day, **1376** for part of it too and **1377** until 2026-09-10.
  **The 902 → 927 move was entirely tree growth and not one new case**, and it is the clearest
  demonstration in this file of what the figure actually measures: `git diff --stat
  e51238e..abdae38 -- tools/tests tools/cite_tools` is **empty**, so not a line of the host
  suite
  changed, and the count still rose by 25. **Three files parametrize over the tree**, and this
  clause named one until 2026-09-01 and two until 2026-09-08. Each has its own base, all three
  walk `git ls-files`, and the per-file figures below are from
  `.venv/bin/python -m pytest <file> --collect-only -q | sed 's/\[.*//' | sort | uniq -c` in
  this checkout on 2026-09-08, at `df91154` for the split of each file into its parametrized
  bases and at `6d51966` for each file's total.
  `tools/tests/test_superseded_real_time_requirement.py` contributes **377**, **367** of them
  one case per tracked source file with a `.py`, `.cpp`, `.hpp`, `.sh`, `.yaml`, `.yml` or
  `.xacro` suffix and **9** one case per source file citing ADR-0043's half two;
  `tools/tests/test_interface_counts.py` contributes **159**, of which
  `test_no_document_states_a_wrong_interface_count` runs over every tracked `*.md`; and
  `tools/tests/test_a_removed_plan_key_stays_removed.py` contributes **350**, **348** of them
  one case per tracked file under the **seven** trees it names — `workspace`, `tools`,
  `tests`, `scripts`, `model`, `.github` and `infra` — at **every** suffix rather than a
  chosen set. **That third base is the widest of the three and grows fastest**: any tracked
  file added under those seven trees moves it, whatever its suffix, where the first moves only
  on seven suffixes and the second only on `.md`.
  **The third file's two numbers agree at 350 by coincidence and are not one quantity**:
  `git ls-files workspace tools tests scripts model .github infra | wc -l` also returns **350**
  in this checkout, and the collection is 350 because that walk less the guard's **2**
  exemptions is 348 parametrized cases, plus the file's **2** unparametrized ones.
  The first two read **375** and **158** in a worktree at `e18251e`,
  measured here on 2026-09-08 — the same pair this file records at `30baea8`, three commits
  earlier — and this file records **341** and **142** at `51195e0`, **321** and **138** at
  `abdae38`, and **304** and **131** in a worktree at `e51238e`, so they account for +24 of the
  +25 between the `e51238e` and `abdae38` figures, which is the move this paragraph is about.
  **The 927 → 973 move is both kinds at once and reconciles exactly**, measured in this checkout
  on 2026-09-02 by the breakdown command below. `tools/tests/test_stall_band.py` is new and
  collects **22** — it is the L0 half of ADR-0052's option F, landed at `53f1d58` — while the two
  parametrized files above grew by **20** and **4** as the source and documentation trees grew.
  22 + 20 + 4 = 46, which is the whole of the move; `tools/tests/test_validate_geometric.py` was
  edited over the same span and collects the same **64** it did before.
  **The 973 → 1023 move is tree growth alone and closes exactly**, measured in this checkout on
  2026-09-08 at `30baea8` by the breakdown command below, against the two per-file figures this
  bullet already records at `51195e0`. **No test file under `tools/tests` was added over that
  span and the one that was edited collects the same number as before** —
  `git diff --stat 51195e0..30baea8 -- tools/tests tools/cite_tools` names
  `test_stall_band.py` and nothing else, and that file collects **22** at both commits — and the
  count still rose by **50**:
  `test_superseded_real_time_requirement.py` 341 → **375** and `test_interface_counts.py`
  142 → **158**, which is the whole of the move. Both halves reconcile against the tree rather
  than against the suite. That first file carries **two** parametrized tests, both walking
  `git ls-files`: one over every tracked source file, which gained the **33** files added over
  the span with a `.py`, `.cpp`, `.hpp`, `.sh`, `.yaml`, `.yml` or `.xacro` suffix, and one over
  the source files citing ADR-0043's half two, which gained **1**. `test_interface_counts.py`
  walks `git ls-files '*.md'`, which gained exactly **16**. 33 + 1 + 16 = 50.
  **The 1023 → 1376 move is both kinds at once and closes exactly**, measured in this checkout
  on 2026-09-08 at `df91154` on
  `feat/hosted-by-derived` by the breakdown command below, against a worktree at this branch's
  base `e18251e` — which collects **1023**, so the three commits between `30baea8` and that
  base moved this figure not at all. The step is **+353**, in three files — the second-largest
  step in the history this bullet records, after the 411 → 902 of 2026-09-01, which is a
  statement about that history and not about every step ever taken.
  `tools/tests/test_a_removed_plan_key_stays_removed.py` is new and collects **350** —
  ADR-0048 clause 3's guard, landed at `7d7ac19` over four trees and widened to seven at
  `37921dd` — and it is itself tree-parametrized, so **348 of those 350 are the size of the
  tree and not the suite growing**.
  `test_superseded_real_time_requirement.py` moved 375 → **377**, which is exactly the
  branch's two added tracked `.py` files: `git diff --diff-filter=A --name-only
  e18251e..df91154` lists those two and nothing else, and `--diff-filter=D` and
  `--diff-filter=R` both count **0**.
  `test_generate.py` moved 67 → **68**, and that one *is* the suite — one hand-written case,
  `test_does_not_change_when_a_template_changes`. 350 + 2 + 1 = 353.
  `test_interface_counts.py` did **not** move, reading **158** on both sides, because the
  branch added no tracked `.md`.
  **The 1376 → 1377 move is one file and one `.md`, and it closes exactly.** ADR-0053 landed at
  `dd6772f` and was revised at `6d51966`; `git diff --diff-filter=A --name-only
  df91154..6d51966` lists `docs/adr/0053-index-hardware-params-by-backend.md` and nothing else,
  with `--diff-filter=D` and `--diff-filter=R` both **0**. So
  `test_interface_counts.py` moved 158 → **159** and the other two tree-parametrized files did
  not move at all — `test_superseded_real_time_requirement.py` reads **377** and
  `test_a_removed_plan_key_stays_removed.py` reads **350** at both commits, the first because
  an `.md` carries none of its seven suffixes and the second because `docs/` is not one of its
  seven trees. `test_generate.py` reads **68**, also unmoved. All four were re-collected at
  `6d51966` rather than reasoned about.
  **The 1377 → 1399 move is both kinds at once and closes exactly**, measured in this checkout
  on 2026-09-10 at `523ffd9` on `feat/declared-simulation-backend` — ADR-0054's implementation
  — against a worktree at that branch's base `404bbac`, by the breakdown command below. The
  step is **+22**, and **13 of it is the suite and 9 is the tree**.
  New cases: `tools/tests/test_declared_hardware_fact.py` collects **8** and
  `tools/tests/test_use_sim_time_still_keys_on_the_id.py` **2**, both new files, and
  `test_validate_referential.py` moved 26 → **29**.
  Tree growth, over the **5** tracked files that branch adds
  (`git diff --diff-filter=A --name-only 404bbac..523ffd9` counts 5, with `--diff-filter=D`
  and `--diff-filter=R` both **0**): `test_superseded_real_time_requirement.py` 377 → **381**,
  the **4** of those five carrying one of its seven suffixes;
  `test_a_removed_plan_key_stays_removed.py` 350 → **354**, the **4** under its seven trees,
  which are the same four files since the fifth is an ADR; and `test_interface_counts.py`
  159 → **160**, that one `.md`. 8 + 2 + 3 + 4 + 4 + 1 = 22. `test_generate.py` reads **68**
  on both sides, unmoved.
  **The two 4s are the same four files and are not one quantity counted twice** — one walk
  selects by suffix and the other by tree, and here they agree because ADR-0054's
  implementation added two `tools/tests` files and two `workspace/src` test files and nothing
  else. A `.md` under `docs/` moves neither.
  **The remaining +1 is an unresolved disagreement and is left stated rather than smoothed
  over.** That same worktree at `e51238e` collects **903**, not the **902** recorded above,
  and no test file changed between the two commits. Whether a worktree's tracked-file set
  differs from a checkout's by one, or the 902 was mis-transcribed, is **unestablished**; it
  was not chased. What is measured in this checkout at `abdae38` is 927.
  So this figure tracks the size of
  the source and documentation trees as well as the size of the suite — the same caveat the
  `lint` bullet below
  carries, for the same reason. Break it down with
  `--collect-only -q | sed 's/::.*//' | sort | uniq -c` rather than reading a coverage claim
  into it. **Collection and a run are
  different numbers, and so are
  these trees**: what `./scripts/test` reports is in the packages bullet below, and its host
  half walks `tests/` as well as `tools/`, so it is a larger number for a reason and not a
  correction to this one.
- **Eleven first-party packages exist**, and `workspace/src/external/` adds the twelve from
  `xarm_ros2`. `./scripts/build` is a blocking CI step. Eight of the eleven are
  `cite_interfaces`, `cite_runtime`, `cite_facility`, `cite_generated`, `cite_bringup`,
  `cite_skills`, `cite_orchestration` and `cite_simulation`. The ninth is
  **`cite_description`, added 2026-08-31** — charter §7's L1 package, created for the first
  thing that needed it. It holds **no code and no node**: it installs `assets/meshes` into its
  share directory so that a `package://` or `file://$(find cite_description)` URI resolves,
  and it is the only package permitted to install from `assets/`. Its admission test is in
  its own `package.xml`. The tenth is
  **`cite_twin`, charter §7's L5 package, which now exists** — the Phase 2.A bullet below is
  where what it does and does not do is kept, and it is not restated here. The eleventh is
  **`cite_test_hardware`, which is test-only and deliberately not in charter §7's tree**:
  §7 is the production structure, and the package is barred from production use by its own
  `on_init` rather than by convention
  ([ADR-0040](docs/adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md),
  charter v1.8). So `cite_test_hardware` appearing on disk and not in §7's tree is the rule,
  not drift.
  `cite_runtime` holds process-lifecycle
  mechanism only — signals, shutdown, spin-and-exit for `rclpy` nodes — and exists rather
  than a helper landing in `cite_interfaces`
  ([ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md), charter v1.7).
  **`cite_telemetry`, `cite_safety`, `cite_control` and
  `cite_hardware` do not exist**; those four plus the ten named above are the fourteen
  charter §7 lists (`cite_test_hardware` is not one of the fourteen). `cite_description` was
  in the does-not-exist list until 2026-08-31 and **`cite_twin` was in it until 2026-09-01**
  — this bullet said "ten first-party packages" and named five that do not exist while
  `workspace/src/cite_twin/package.xml` was committed and building. The instrument that
  settles it is `find workspace/src -name package.xml -not -path '*/external/*' | wc -l`,
  which reads **11** in this checkout on 2026-09-01.
  `./scripts/doctor`'s `workspace/src` line counts every `package.xml`
  beneath it and read **23** in this checkout on 2026-09-01, with the manifest imported; it
  read **22** on 2026-08-31. **The pre-import figure is measured at this commit and is 11**,
  from the same `doctor` line run on this worktree before `./scripts/bootstrap` imported
  `external/cite.repos` on 2026-09-01. It was 9 on 2026-08-29 and was unmeasured between.
  `./scripts/build` reported `Summary: 23 packages finished` in this
  checkout on 2026-09-01, and `find workspace/src -name package.xml | wc -l` agrees at
  **23** — the eleven plus the twelve. **Both `doctor`'s `workspace/src` line and `build`'s
  summary were re-run on 2026-09-08 at `df91154` and read 23 again**; that branch added no
  package. **`doctor`'s line was re-run once more later that day at `6d51966` and read 23**;
  `build` was **not** re-run there, and the only tracked change over that span is one added
  `.md` under `docs/adr/`, which is a reason to expect its summary not to have moved and **is
  not a measurement of it**. **Both were re-run again on 2026-09-10 at `523ffd9` and read
  23** — `doctor`'s line and `Summary: 23 packages finished` — so that gap is closed by a
  reading rather than left as an expectation; `feat/declared-simulation-backend` adds four
  test files and an ADR and no package. This line carried **20** until 2026-08-29, which was
  CI's figure at `60eb4a5`, before `cite_test_hardware` existed, **21** until 2026-08-31 and
  **22** until 2026-09-01.
  **`./scripts/test` counts by a run and reports three numbers, not one, and all three were
  re-taken on 2026-09-10 at `523ffd9` from ONE full run**, which is what it takes: a
  `--host-only` run cannot refresh the third at all. `124 passed, 0 failed
  (shell gate self-tests)`, unchanged since
  2026-08-31; `1468 passed, 1 skipped` for the host half, which walks `tools/` **and**
  `tests/`, so it is larger than the `tools/tests` collection above; and, over the eleven
  first-party packages, eleven per-package summaries totalling **1363 tests, 0 failures, 56
  skipped**. Its exit status was 0.
  `./scripts/test` builds and tests the eleven only — the
  twelve imported packages are built and not tested here. The three read 113 / 367 / 854 on
  2026-08-29, 124 / 447 / 962 on 2026-08-31, 124 / 938 / 1217 earlier on 2026-09-01,
  124 / 963 / 1221 later the same day, 124 / 1009 / 1250 until 2026-09-08,
  124 / 1075 / 1250 for a few hours of that day, 124 / 1092 / 1250 for a few hours more,
  124 / 1445 / 1296 for a few hours after that and 124 / 1446 / 1296 until 2026-09-10.
  **All three were re-run at that branch's tip `b072bfa` and read the same 124 / 1468 / 1363**,
  which is the first time this bullet's figures have been reproduced by a second full run at a
  second commit rather than stated from one. The four commits between the two are
  documentation and one comment, so the agreement is what had to happen and is recorded as a
  reading rather than as evidence about anything else.
  **A third full run sits between those two and exited 1**, and it is recorded because a
  failure this file does not mention is a failure the next reader re-discovers.
  `cite_orchestration`'s `test_skill_cancellation` hit its **60 s** ctest timeout;
  re-run alone it passes in **4.23 s**, and the run either side of it passed it. `git diff
  --stat 404bbac..b072bfa -- workspace/src/cite_orchestration` is **empty**, so the package is
  untouched by that branch. **A second container was being started on the same host while it
  ran**, which is a confound the reader should know about and **is not an attribution** — one
  event, on one machine, with nothing registered in advance, and it is not classified here.
  **One arithmetic check ties the host half to the collection above, and it is what separates a
  re-measurement from a guess.** The host half moved 963 → 1009, **+46**, the same step the
  `tools/tests` collection took over the same span, which is what has to happen if the host half
  walks `tools/`. The check held at the move before it too: 938 → 963, **+25**, against the
  collection's own +25.
  **It held again at 1009 → 1075, and this time both halves were derived.** The step is **+66**:
  `tools/tests` moved +50, as reconciled above, and `tests/` moved **37 → 53**, +16, measured by
  `.venv/bin/python -m pytest tests --collect-only -q` in a worktree at `51195e0` and in this
  checkout on 2026-09-08. 50 + 16 = 66. The `tests/` half is nine cases in the new guard
  `test_a_stopped_line_ends_the_run.py`, five in `test_timing_records.py`, and
  `test_gz_calls_carry_the_partition.py` moving 11 → 13 because it parametrizes over the files
  under `tests/` — the same tree-growth effect this bullet already records for `tools/tests`.
  **And again at 1075 → 1092, hours later the same day, when `b6ab34a` answered a review of that
  same guard.** The step is **+17** and it is entirely one file:
  `test_a_stopped_line_ends_the_run.py` moved **9 → 26**, chiefly because its halt fabrications
  were parametrized over all three stopped states after a mutation sweep found that every one of
  them had been `STALLED` — so the arm both CI incidents actually published was never executed.
  `tools/tests` did **not** move this time, because no file was *added* under `tests/`; for the
  same reason `test_gz_calls_carry_the_partition.py` stayed at 13. The tie closes exactly:
  1023 + 70 = 1093 = 1092 passed plus the 1 skipped.
  **And again at 1092 → 1445, on `feat/hosted-by-derived`, where the whole of the move is the
  `tools/` half.** The step is **+353**: `tools/tests` moved +353, as reconciled above, and `tests/` did
  not move at all, collecting **70** both in a worktree at `e18251e` and in this checkout
  (`.venv/bin/python -m pytest tests --collect-only -q`, both read on 2026-09-08). The tie
  closes exactly: 1376 + 70 = 1446 = 1445 passed plus the 1 skipped.
  **And again at 1446 → 1468, on `feat/declared-simulation-backend`, where the whole of the
  move is again the `tools/` half.** The step is **+22**: `tools/tests` moved +22, as
  reconciled above, and `tests/` did not move, collecting **70** both in a worktree at
  `404bbac` and in this checkout on 2026-09-10. The tie closes exactly: 1399 + 70 = 1469 =
  1468 passed plus the 1 skipped. **Predicted before it was measured, and it held** — this is
  the second time that has been done here, and both times the prediction was written down
  first and then a full run was taken rather than the arithmetic being published as a reading.
  **And again at 1445 → 1446, and that one was the smallest step the tie has ever had to
  close.** `tools/tests` moved +1, as reconciled above, and `tests/` did not move, collecting
  **70** at `6d51966` as it did at `df91154`. The tie closes exactly: 1377 + 70 = 1447 =
  1446 passed plus the 1 skipped. **The prediction was written before the measurement and then
  the measurement was taken** — this bullet briefly said the host half "would have to read
  1446", and `./scripts/test --host-only` then read 1446. A prediction that is cheap to settle
  should be settled rather than published.
  **The pair recorded at `51195e0` is internally consistent and was checked rather than
  assumed**: 973 + 37 = 1010 = 1009 passed + 1 skipped.
  **The per-package total carries no such tie and is not given one here.**
  **Its 1296 → 1363 step, +67, is stated and NOT reconciled**, for the reason the rest of this
  paragraph gives: the eleven `Summary:` lines are printed in one block with no package name
  against any of them, so the log cannot attribute a single test to a package, and attributing
  it would need a full run at `404bbac` as well, which was not taken. What is checkable is
  that the branch changes tests in **`cite_bringup` and `cite_twin` only** — `git diff --stat
  404bbac..523ffd9 -- workspace/src` names those two and `cite_generated`, whose change is one
  generated plan — which is a reason to expect the move to sit there and **is not a
  measurement of it**. **One test of the 67 is attributed**, because it was measured directly:
  `cite_twin/test/test_l5_gate_reads_the_declared_fact.py` went 20 → **21** when the
  live-plan guard was added on 2026-09-10, read from that file's own pytest line.
  Its 1217 → 1221 step was the four tests the three commits after `f859cb3` added under
  `workspace/src`; the 1221 → 1250 step, **+29**, was **not** reconciled against the
  `workspace/src` diff, and that is left stated rather than asserted. **Nor is the 1250 → 1296
  step, +46.** The eleven `Summary:` lines the script prints carry no package name, so the
  total cannot be attributed from the log, and attributing it would mean a full run at the base
  as well, which was not taken. What is checkable is that the only package whose tests changed
  on this branch is `cite_bringup` — `git diff --stat e18251e..df91154 -- workspace` names that
  package and no other — which is a reason to expect the move to sit there and **is not a
  measurement of it**. The shell gate did not move in any of the three steps.
  **The per-package total is a sum this file performs and `test` does not print**: the script
  emits one `Summary:` line per package and no grand total, so the 1296 and the 56 were
  added up by hand from the eleven lines. The two host figures are printed verbatim. **A
  `--host-only` reading cannot refresh the third figure at all**, which runs the same two host
  suites and stops there: that is why the per-package total carried 2026-09-02's date through
  2026-09-08's `--host-only` reading at `b6ab34a`, and why the three above were taken from one
  full run instead.
- **The simulated cell comes up.** `./scripts/sim --headless` brings the scene and three
  arms into Gazebo Harmonic with nine controllers active, one `move_group` and one skill
  server per arm, one detection server for the zone, the generated planning scene applied
  and read back, the facility's model version, frames and topology served, and one
  `ros_gz_bridge` carrying `/clock` plus every belt and beam topic the generated plan
  declares. The L4 coordinator is **off unless `line:=true`**, because it takes exclusive
  hold of each arm's skills. `./scripts/scenario bringup` asserts the bring-up and is a
  blocking CI gate, run twice per CI run.
  **It is not a scenario that always passes, and until 2026-08-28 nothing said so.** Thirty
  consecutive local runs at `de67d8b` — taken for another purpose and published as
  [`docs/measurements/2026-08-27-teardown-signal-family/`](docs/measurements/2026-08-27-teardown-signal-family/results.md)
  — include runs that failed `bringup`'s own `MoveTo` assertion, not merely its teardown
  check. That campaign's note on the finding is explicit that it is **not a pre-registered
  rate** and that whether it still happens is **unmeasured**. **It still happens**: the same
  `the MoveTo goal was never accepted` assertion failed **one local run of four** on 2026-08-29,
  on the merged Phase 2.A branch, reported by the implementing agent — one more event, on one
  machine, with nothing registered in advance, and not a rate either. Against that,
  `bringup`'s **cycle** has passed **50 of 50** in CI: it runs twice per run and the
  twenty-five runs listed in the `continuous_line` bullet below all passed its cycle twice.
  **Its teardown is clean in 47 of the 50**, and the three exceptions are `f6a3779` and
  `13bc8e9`, both 2026-09-07, and **`e18251e` on 2026-09-08** — in each of the three, one of
  that run's two invocations printed `Scenario 'bringup' passed its cycle assertions` and the
  other printed the bare verdict. **They are no longer the only advisory verdicts in CI**:
  `pick_and_place` printed one in that same `e18251e` run, which is the bullet below. That is a
  statement about the twenty-five tabled `main` runs, twenty-two of them read on 2026-09-07,
  the twenty-third on 2026-09-08 and **the last two read here on 2026-09-08 from their own
  logs**, and about nothing
  else. The cycle figure said
  **12 of 12 across the six** until 2026-09-01, **36 of 36 across the eighteen** later that
  day, **38 of 38 across the nineteen** until 2026-09-07, **44 of 44 across the twenty-two**
  until 2026-09-08 and **46 of 46 across the twenty-three** for part of that day,
  each right over the runs that
  existed then; **until 2026-09-07 no teardown figure was stated separately at all**, because
  until then no `bringup` teardown had failed in CI and the two questions had never come
  apart, and the teardown figure read **44 of 46** until 2026-09-08.
  **The 46 → 50 and 44 → 47 steps are different sizes and that is the whole point of stating
  them apart.** Two runs added four invocations, all four of which passed their cycle, and
  three of the four had a clean teardown: `aed36c4`'s two were both bare `passed`, and
  `e18251e`'s were one bare and one advisory. 46 + 4 = 50 and 44 + 3 = 47.
  **That the `13bc8e9` run's other `bringup` invocation passed its cycle is inferred, not
  read.** The scenario step is blocking and `pick_and_place` and `continuous_line` ran after it
  in that run, which they cannot do if it exited non-zero (`.github/workflows/ci.yml`: only the
  `continuous_line` step carries `continue-on-error`). Say it that way rather than as a
  reading; the advisory verdict itself is what was read.
  **The instrument this bullet used to name cannot tell those two apart, and that is the
  finding of the 2026-09-07 re-read.** It was `grep -c "Scenario 'bringup' passed"`, which is
  a prefix and also matches `Scenario 'bringup' passed its cycle assertions`; over
  `34085965578`'s log it returns **2**, exactly as it does for a run whose teardown was clean.
  Extract the whole verdict line and match it anchored at both ends instead — the logs carry
  `\r`, so strip it first: `gh run view <id> --log | grep -o "Scenario '[a-z_]*'[^\"]*" |
  sed 's/\r//'`, then count `Scenario 'bringup' passed` and
  `Scenario 'bringup' passed its cycle assertions` as separate whole lines. That is how the
  44 / 43 split then current was derived, over all twenty-two runs' logs on 2026-09-07.
  **The instrument has a second defect, from the opposite direction, and this file's own
  documentation is what triggered it.** A CI log carries the **commit message** — it is echoed
  in the `Build image` step — so a whole-log grep also counts every verdict string the commit
  body quotes. `13bc8e9`'s message quotes `Scenario 'bringup' passed` while explaining the
  prefix defect above (`git log -1 --format=%B 13bc8e9`, re-read here on 2026-09-08), and a
  whole-log grep over its run reported **four** `bringup` verdicts where the scenario step
  printed two. **Restrict the grep to the scenario steps' own columns.** The step-conclusion
  warning in the
  `continuous_line` bullet below is the same hazard from the other side: there the instrument
  under-reads a failure, here it over-reads a pass. The over-count was observed on 2026-09-08
  by the agent that read that run; the half that is re-derived here is that the string is in
  the commit body.
  **There are three such step names, not one, and this file named only the first until
  2026-09-08.** `grep -n "Simulation-in-the-loop" .github/workflows/ci.yml`, run here on that
  date, returns `Simulation-in-the-loop scenarios` (both `bringup` invocations),
  `Simulation-in-the-loop scenario — pick_and_place` and `Simulation-in-the-loop scenario —
  continuous_line (advisory)`. A restriction to the first alone drops the other two scenarios'
  verdicts entirely. The whole instrument, as run here over both 2026-09-08 runs:
  `awk -F'\t' '$2 ~ /Simulation-in-the-loop/' <log> | grep -o "Scenario '[a-z_]*'[^\"]*" |
  sed 's/\r//' | sort | uniq -c` — the log is tab-separated with the step name in column 2.
  **A fourth string matches that pattern and is not a verdict**, which is why the counting rule
  is exact whole-line equality and not the pattern's raw output: `scripts/scenario:142` prints
  `Scenario 'X': the cycle passed and the post-shutdown check did not.` as a `warn` beside the
  advisory `ok` verdict, so an advisory branch emits **two** matching strings. Read that file's
  four print sites (lines 123, 142, 154 and 158, read 2026-09-08) rather than inferring the set.
  **The over-count did not fire on either 2026-09-08 run, and why not is the point.**
  `34258470163`'s log does carry a commit body quoting the verdict — `987e6b6`'s, echoed in the
  `Build image` step as the push payload's `"message"` field — but the quotation is **line-wrapped
  there**, so what the log contains is `Scenario 'bringup'\npassed` and the anchored pattern
  does not match it; the whole-log and step-restricted counts agree exactly for that run.
  `aed36c4`'s body quotes no verdict at all (`git log -1 --format=%B aed36c4 | grep -c`, run
  here, returns 0). **So the step-column restriction is what makes a reading reliable, and a
  whole-log grep that happens to agree is agreeing by where the commit message wrapped.**
  **Thirty-six of the fifty are on vendor collision geometry and fourteen are on convex
  hulls** — the last seven rows of that table are the runs taken on the geometry this
  repository ships; it said "two are on convex hulls" and "the last row" until 2026-09-07,
  "eight" and "the last four rows" until 2026-09-08, and "ten" and "the last five rows" for
  part of that day. **The vendor half has stopped moving and only the hull half grows**, which
  is what has to happen once the selection changed.
  **One local pair of runs was taken on `feat/hosted-by-derived` and enters none of the CI
  figures above.** At `37921dd` — that branch's second commit, not its tip `df91154` — with
  `CITE_PHYSICS_SEED=42`, `bringup` printed the bare verdict `Scenario 'bringup' passed`, so
  its cycle and its post-shutdown teardown were both clean, and `pick_and_place`'s cycle passed
  **2 of 2** with one of those two runs failing its teardown on `gz-1 exited with -9`. **One
  machine, one commit, two scenarios, no thresholds registered in advance, reported by the
  `tester` agent that ran them and not re-run by the pass that wrote this down.** It is local,
  so it moves no count in the CI tables in this section, and it is not at the tip. The `-9` is
  the signal the teardown-family bullet below records as outside the set that split was
  measured over and still unclassified.
  Treat a `bringup` failure as a finding to
  investigate, not as a known flake to re-run past.
- **Motion is planned by Pilz.** ADR-0027 is implemented and merged: L0 declares the
  pipeline choice and the limits, the generator emits `cell_a_arm_*_planning_pipelines.yaml`
  per arm declaring both pipelines, and the L3 skill server asks for Pilz PTP and falls back
  to OMPL **only** on a planning failure — never on an unreachable pose, and never when the
  requested planner is a Cartesian one, where the shape of the path is the contract.
  **What is proven:** an identical request returns a byte-identical trajectory from one
  `move_group`, and a PTP path through a named object in the real generated planning scene
  is refused — mutation-checked, and observed refusing a real path during `continuous_line`.
  **What is not:** same seed, same trajectory *across runs*. **LIN is configured and usable
  on one motion shape only**, and nothing in L3 asks for it. That, the measurement, and the
  fact that no error code tells a collision refusal from a geometric one are in
  [ADR-0027](docs/adr/0027-pilz-planning-pipeline.md)'s 2026-08-27 correction; the gate's own
  residual is in the gap list below.
- **A mistracked trajectory is now detected at execution, and the detector's own values are
  copied rather than measured.** Every generated `JointTrajectoryController` carries a
  `constraints:` block — `goal_time`, and per-joint `trajectory` and `goal` tolerances —
  declared on the arm type in L0 and identical on both backends
  ([ADR-0036](docs/adr/0036-execution-side-trajectory-tolerances.md)). Until it existed every
  tolerance was `0.0`, `0.0` disables the comparison, and **a physically obstructed arm ran
  the trajectory to its end and reported `SUCCESSFUL`** — silence that reached `Pick` as a
  successful pick. A launch test drives two real controller managers over mock hardware and
  requires a tracked trajectory to succeed, a held joint to abort as
  `PATH_TOLERANCE_VIOLATED`, and an error between the two thresholds to abort as
  `GOAL_TOLERANCE_VIOLATED`.
  **It is a detector, not a protective measure**, and must never be cited as one: it reports
  after the fact, and what stops an arm driving into a fixture is the vendor controller's
  torque limiting and physical guarding (charter §3.2).
  **The values are UFACTORY's, recorded as copied**, and ADR-0036's 2026-08-27 correction is
  where the residuals live — including that `stopped_velocity_tolerance` is structurally dead
  on a position-only command interface. What is unmeasured is in the gap list below.
- **An execution abort is classified before any recovery motion is dispatched**
  ([ADR-0037](docs/adr/0037-classify-an-abort-before-any-recovery-motion.md), binding —
  violating it is an `ESCALATE`). `ResultCode` gained `MOTION_INTERRUPTED = 10`, defined in
  world terms — the arm stopped part-way and is holding position — with policy row
  `ESCALATE`; `EXECUTION_FAILED` narrowed to the two endpoint cases. The classification is a
  free function in **L3**, `cite_skills::classify_execution_failure`, computed from the plan
  and the joint state rather than from any L2 error code, so it holds for any robot type
  (P9) and is identical on both backends (P2). A typed `ResetStation.srv` exists and is
  served by `cite_orchestration`, which had no `create_service` call at all before it; the
  reset commands no motion. Every row of the classifier is unit-tested in
  `cite_skills/test/test_motion_end.cpp`.
  **A genuine abort now reaches the classifier on demand, and this file said otherwise until
  2026-08-29.** ADR-0040's `cite_test_hardware/JointStopSystem` puts hard stops on one named
  joint, and `cite_bringup/test/test_abort_classification_launch.py` drives a real
  `ros2_control_node`, a real `move_group` and the real skill server: one goal clear of the
  stops must succeed, one through them must come back `MOTION_INTERRUPTED` with a `part-way`
  reason — the same rig, the same hardware, differing only in the goal. It passed 4 of 4 in
  `./scripts/test` in this checkout on 2026-08-29. The gap list below said no such fixture
  existed; the fixture landed at `a90b05f` on 2026-08-28 and this file was edited twice after
  that without noticing. **What it still cannot answer** is in its own docstring: mock
  hardware is a perfect follower, so the early abort ADR-0037 names — a decelerating arm still
  within tolerance of the start, misclassified as never having moved — cannot be produced
  there, and only a scenario measures the `gz_ros2_control` command interface.
- **A station's escalation now stops the line and leaves the coordinator alive to serve that
  reset** ([ADR-0038](docs/adr/0038-stop-the-line-without-ending-the-process.md)). The
  generated root was a bare `Parallel`, so an escalating station failed the root, ended the
  tick loop and exited the process — which tore the whole cell down and took the evidence of
  the fault with it. The root is now a `Fallback` over that unchanged `Parallel` and a fault
  `Sequence` of `OnFault → StopAll → AwaitReset → AwaitReArm` in `line_fault.hpp`. A latched
  fault still exits 1 on **either** route into the branch, so a run in which the line stopped
  still fails CI.
  **`StopAll` is a P2 fix, not a convenience**, and it gives `ConveyorIndex::stop()` its first
  production caller. The simulated belts stopped by accident — Gazebo died with the launch and
  there was no belt left to run; a physical belt is a VFD and **a setpoint persists**. Identical
  command path, divergent consequence, and only the simulated half has ever been observed.
  **It is a state machine, not a protective measure.** What it buys is that the coordinator
  is still there to be asked a question, and that it stops commanding belts it has stopped
  supervising.
- **P10 has its first automated check** ([ADR-0035](docs/adr/0035-check-the-english-only-rule-by-character-signal.md)).
  `./scripts/lint` fails when a text file in this checkout contains a letter specific to a
  language
  other than English — six Turkish-specific letters plus nine non-Latin script ranges, chosen
  by measuring four candidate instruments against the archived v1 tree, where this one catches
  **17 of 17** first-party files. It runs in the host half of `lint`, the half that always
  runs, and reported `1936 files checked, no non-English content outside 1 exemption(s)` in
  this checkout on 2026-09-10 at `523ffd9`; it said **661** until 2026-08-29, **1048** until
  2026-08-31, **1085** earlier on 2026-09-01, **1267** later that day, **1430** until
  2026-09-02, **1540** until 2026-09-08, **1928** and then **1930** for parts of that day and
  **1931** until 2026-09-10.
  Most of the
  difference is the
  measurement campaigns publishing their raw logs into the walk — `git diff --diff-filter=A
  --name-only 60eb4a5..HEAD -- docs/measurements` counts **1175** files added there since the
  first of those figures was taken, and read 368 on 2026-08-31, 523 earlier on 2026-09-01,
  684 later that day and 791 until 2026-09-08 —
  so **this number tracks how
  much evidence is committed and is not a
  measure of coverage.** The last two moves demonstrate it arithmetically. The 1267 → 1430 move:
  the walk grew by
  **163** and `git diff --diff-filter=A --name-only dd93488..HEAD -- docs/measurements` counted
  **161** files added under that one directory over the same span. The 1430 → 1540 move closes
  exactly: the walk grew by **110**, `git diff --diff-filter=A --name-only abdae38..HEAD` counts
  **110** tracked files added over that span with **107** of them under `docs/measurements`, and
  `--diff-filter=D` and `--diff-filter=R` both count **0**, so nothing left the walk to offset
  it. The 1540 → 1928 move closes exactly in **two** parts, and the second part is the caveat
  below: `git diff --diff-filter=A --name-only 51195e0..30baea8` counts **386** tracked files
  added, **384** of them under `docs/measurements`, with `--diff-filter=D` and
  `--diff-filter=R` both **0**, so 1540 + 386 = **1926** — and the two *untracked* files below
  make 1928. **The 1928 → 1930 move was the smallest this figure had taken and closes the same
  way**: `git diff --diff-filter=A --name-only 30baea8..df91154` counts **2** tracked files
  added, **neither** of them under `docs/measurements`, with `--diff-filter=D` and
  `--diff-filter=R` both **0**, and the same two untracked files are still on disk. It was the
  first of the moves this bullet breaks down whose
  additions include nothing under `docs/measurements` at all: that branch published no
  campaign.
  **The 1930 → 1931 move is smaller still and closes the same way.** `git diff
  --diff-filter=A --name-only df91154..6d51966` counts **1** tracked file added,
  `docs/adr/0053-index-hardware-params-by-backend.md`, **none** of it under
  `docs/measurements`, with `--diff-filter=D` and `--diff-filter=R` both **0**, and the same
  two untracked files are still on disk. **So the two smallest moves this figure has taken are
  consecutive and are both documentation**, which is what this bullet means when it says the
  number is not a measure of coverage. That superlative was re-checked against the move below
  before being kept, and it survives: +1 and +2 are still the two smallest and still adjacent.
  **The 1931 → 1936 move is +5 and closes the same way.** `git diff --diff-filter=A
  --name-only 404bbac..523ffd9`
  counts **5** tracked files added — four test files and one ADR — **none** under
  `docs/measurements`, with `--diff-filter=D` and `--diff-filter=R` both **0**, and the same
  two untracked files are still on disk. 1931 + 5 = 1936. **So three consecutive moves have
  now added nothing under `docs/measurements`**, which is a statement about these three
  branches and not a trend.
  **A superlative was drafted here and withdrawn on checking, which is the reason to say so.**
  It read *"the first in this bullet's history that is entirely source"*, and the move
  immediately above it — 1928 → 1930, `df91154` — was **two added tracked `.py` files and
  nothing else**, so it is more entirely source than this one, which carries an ADR among its
  five. The paragraph above records those two files, in this same file, four paragraphs up.
  **This figure counts what is on disk, not what is committed, and this bullet said "a tracked
  text file" until 2026-09-08.** The remit is an `os.walk` from the repository root with
  directories pruned (`cite_tools.tree.our_files`, reached from
  `cite_tools.english.files_to_check`), and `tools/tests/test_english.py` carries a test named
  `test_a_file_that_is_written_but_not_staged_is_still_reported` asserting exactly that. So a
  file that is present but untracked is checked and counted. **Exactly 2 of this checkout's
  1936 are untracked** — `predicate_eval` and `predicate_eval_superseded`, gitignored binaries
  built by the 2026-09-03 stall-band campaign's harness — **re-derived rather than carried
  forward**, on 2026-09-10 at `523ffd9`, by differencing `files_to_check` against
  `git ls-files`, which named those two files and no others; the same difference at `6d51966`
  and at `df91154` named the same two. **A clean clone of `523ffd9`
  therefore reports 1934**, and this figure depends on local build state in a way none of the
  other counts in this section does. **That prediction has now been checked once and it held**:
  this file said a clean clone of `30baea8` would report **1926**, and `files_to_check` over a
  fresh worktree at `e18251e` — three commits after `30baea8`, with no tracked file
  added in between — returns exactly **1926** on 2026-09-08. That the 1540 was itself
  effectively a tracked-only reading was checked the same way: `files_to_check` over a fresh
  worktree at `51195e0` returns **1540** on 2026-09-08. The three tree-parametrized test files
  above do **not** share this property — all three walk `git ls-files`. Run `lint` rather than
  quoting it. The one exemption is
  `docs/reference/v1-lessons.md`, which quotes the
  original Turkish as primary-source evidence. The limits — chiefly that ASCII-only Turkish and
  every other Latin-script language pass untouched — are the ADR's; do not restate them.
- **One arm picks and places a work-piece, and friction alone holds it.** ADR-0029 removed
  the contact-triggered attachment plugin, so nothing on the simulation side assists a grasp:
  the pads close on the part, stall on it, and the controller reports
  `stalled=true, reached_goal=false -> holding` — the evidence ADR-0022 shaped the gripper
  path around. The 84-trial measurement the decision rests on is
  [`docs/measurements/2026-08-25-friction-grasp/`](docs/measurements/2026-08-25-friction-grasp/results.md).
  **The cycle passed 6 of 6** in the measurement the implementing agent took on 2026-08-26,
  in one isolated freshly built tree on one machine, every run reporting a genuine friction
  stall. **The scenario verdict in those same runs was 5 of 6**: one run passed the cycle and
  then failed the post-shutdown teardown check. No thresholds were registered in advance and
  this is not a claim about any other machine.
  **The wrong pass count named above was this bullet's.** It said 8/8; those runs executed
  another worktree's binaries through shared Docker volumes, and the number arrived here
  supplied rather than measured. Each checkout is now isolated and `lint`/`test` refuse to
  answer from a stale build tree — **measure it yourself anyway.**
  **`./scripts/scenario pick_and_place` is a blocking CI step**, promoted at `c1e9e03`. CI
  passes `--teardown-advisory` to all three scenarios, splitting the two questions a scenario
  answers in one exit code: **the cycle is gated, the post-shutdown teardown is reported and
  not gated.** The flag is off by default, so an interactive run still answers the strict
  question. Read `scripts/scenario`'s header and the phase-split block in `scripts/_lib.sh`
  before treating a teardown failure as a gate — and never answer one by widening a tolerance.
  **Its two questions have now come apart in CI, and until 2026-09-08 they never had.** Over
  the twenty-five tabled `main` runs in the bullet below — one `pick_and_place` invocation
  each — **the cycle has passed 25 of 25 and the teardown is clean in 24 of the 25**. The one
  exception is `34258470163` at `e18251e`, which printed
  `Scenario 'pick_and_place' passed its cycle assertions` and failed
  `test_nothing_of_ours_exited_badly` on `AssertionError: -9 not found in [0, 130] : gz-1
  exited with -9`; read here on 2026-09-08 with the instrument the `bringup` bullet mandates.
  **This file stated one figure where there are two until that date** — the hull paragraph
  below said `pick_and_place` "passed in all twenty-three tabled runs: 22 of 22 by exact-string
  match … so 23 of 23", and that string was the bare verdict, so it was a claim about the cycle
  **and** the teardown at once. The cycle half of it survives the twenty-fourth and
  twenty-fifth runs untouched; the teardown half does not, and is stated separately from here
  on. **Nothing here attributes the `-9`** — see the teardown-family bullet below, which is
  where that process and that signal are kept and where they stay unclassified.
- **The line has completed in eighteen of the twenty-five CI runs that have driven it, and
  this
  is still the least-settled claim in this file.** It read "three of the six" until
  2026-09-01, "fourteen of the eighteen" later that day, "fifteen of the nineteen" until
  2026-09-07, "sixteen of the twenty-two" until 2026-09-08 and "seventeen of the twenty-three"
  for part of that day, and **the extra runs make the
  count look better without making the
  finding go away**: the three-of-six failures are all still there, they are still
  unreproduced locally, and there are now **three distinct failure signatures among seven
  failures**, not one among four — a spawn timeout joined on 2026-08-31 and a pair of
  escalated aborts joined on 2026-09-02.
  **The set of signatures did not grow on 2026-09-08; the spawn timeout did.** The seventh
  failure, `34258470163` at `e18251e`, is the **second** occurrence of the spawn-timeout
  signature, eight days and thirteen table rows after the first — row 24 against row 11. **That is a count inside one
  signature and not a fourth signature**, and it is also not a rate: two events, at two
  commits, on two runners nobody prepared, with nothing registered in advance. Neither
  occurrence is attributed, and the reasons the first was not attributed are unchanged.
  `./scripts/scenario continuous_line` drives the three-arm sensor-driven line: the aid
  topics are bridged, `Detect` turns a beam level into a typed `DetectionEvent`, L4 stops the
  belt on that edge and restarts it on `CompleteHandoff` (ADR-0032), and the beam indexes on
  the part's body rather than its origin (ADR-0033). It runs in CI as `continue-on-error`.
  **A harness had been doing L4's job, and this is the sharpest example in this file of why a
  green run is not evidence.** ADR-0032 gave the belt setpoint an owner in L4 on 2026-08-26
  and that owner delivered nothing: `ConveyorIndex` creates its publishers inside the topology
  callback and published from the same callback, and **reliable QoS is a promise to *matched*
  subscribers**, of which there were none at that instant. The belts were being started by the
  scenario's own repeated sends. Every `continuous_line` figure recorded before 2026-08-27 was
  produced with the test harness compensating for a defect in the thing under test. Fixed
  event-driven — a subscriber matching is treated as an event — and the pre-fix counts are not
  re-measured.
  **What has been measured since, in the order it was taken.** All of it is on one machine
  with **no thresholds registered in advance** and **no directory in
  [`docs/measurements/`](docs/measurements/README.md)**; these are the size of the evidence,
  not a campaign.
  - Fixing agent, 2026-08-27, three runs: cycle **3 of 3**, teardown **3 of 3**.
  - Project owner, 2026-08-27, three runs, independent: cycle **3 of 3**, scenario verdict
    **1 of 3**. Both failures were teardown-only. **The cycle figure replicated and the
    teardown figure did not** — "the line works" and "the scenario is green" are not the same
    claim.
  - Most recent local run, one run: **3 of 3** work-pieces carried end to end, all four beams
    firing at every station, all nine grasps reporting a genuine friction stall, and cycle and
    teardown passing separately. It is better than anything above it. **The tester's own
    reading is that it is one good sample and not a new baseline**, and that is how it is
    recorded here. Do not promote a gate on it.
  **CI has now run it twenty-five times, and this is the only body of `continuous_line`
  evidence nobody's local environment could have flattered.** Every one of the twenty-five was
  on `main`, on a runner nobody prepared. It said "nineteen times" until 2026-09-07,
  "twenty-two" until 2026-09-08 and "twenty-three" for part of that day. Read by
  grepping each run's log for the scenario's own verdict
  line, because **the step conclusion lies**: the step is `continue-on-error`, and
  `gh run view <id> --json jobs` reports it `success` whether the scenario passed or failed —
  verified on 2026-08-29 against `33158091922`, whose `continuous_line` is *known* to have
  failed and which the API still calls `success`. The instrument is
  `gh run view <id> --log | grep "Scenario 'continuous_line'"`, **restricted to that
  scenario's own step column, `Simulation-in-the-loop scenario — continuous_line (advisory)`**
  — the `bringup` bullet above records what a
  whole-log grep counted instead, and records that there are three scenario step names rather
  than the one this line named until 2026-09-08.

  | CI run | date | commit | cycle |
  |---|---|---|---|
  | `33158091922` | 2026-08-28 | `60eb4a5` | **failed** — 1 of 3 |
  | `33208064683` | 2026-08-28 | `a8f1e3d` | **failed** — 2 of 3 |
  | `33235590086` | 2026-08-29 | `f1f914f` | passed |
  | `33241186260` | 2026-08-29 | `7afb2c6` | passed |
  | `33244350584` | 2026-08-29 | `3d23999` | passed |
  | `33261637940` | 2026-08-29 | `29068d4` | **failed** — 2 of 3 |
  | `33288010305` | 2026-08-30 | `b8a6c10` | passed |
  | `33290887432` | 2026-08-30 | `3f68a47` | passed |
  | `33298445106` | 2026-08-30 | `5c2990f` | passed |
  | `33331623351` | 2026-08-30 | `aafae47` | passed |
  | `33343317444` | 2026-08-31 | `3b8cd19` | **failed** — see below, a different signature |
  | `33377192704` | 2026-08-31 | `b6efc95` | passed |
  | `33398446772` | 2026-08-31 | `35ff5be` | passed |
  | `33424510102` | 2026-08-31 | `d35eca9` | passed |
  | `33438471901` | 2026-08-31 | `d7b1097` | passed |
  | `33472144723` | 2026-09-01 | `d79a856` | passed |
  | `33479867459` | 2026-09-01 | `2cf66df` | passed |
  | `33485617966` | 2026-09-01 | `c0badfb` | passed |
  | `33501707588` | 2026-09-01 | `e51238e` | passed — **the first row measured on convex hulls** |
  | `33575992281` | 2026-09-02 | `4ef2d7c` | **failed** — a third signature, below |
  | `33603610958` | 2026-09-02 | `51195e0` | **failed** — the same third signature |
  | `34085965578` | 2026-09-07 | `f6a3779` | passed |
  | `34247027502` | 2026-09-07 | `13bc8e9` | passed |
  | `34258470163` | 2026-09-08 | `e18251e` | **failed** — 2 of 3, the spawn signature a second time |
  | `34280056331` | 2026-09-08 | `aed36c4` | passed |

  **Eighteen of twenty-five is a count over the runs that exist, not a rate** — no thresholds
  were registered in advance and the twenty-five sit at twenty-five different commits. The
  table
  said **three of six** until 2026-09-01, **fourteen of eighteen** later that day,
  **fifteen of nineteen** until 2026-09-07, **sixteen of twenty-two** until 2026-09-08 and
  **seventeen of twenty-three** for part of that day, each
  right
  over the runs that existed when it was written; the
  twelve rows below `29068d4` were read on 2026-09-01 by the instrument named above, over every
  completed `main` run since, **every one of the nineteen rows was re-read by that
  instrument at `abdae38`**, reproducing the table exactly, and **all twenty-two rows then
  existing were
  re-read again on 2026-09-07**, this time with the whole verdict string anchored at both ends
  rather than matched as a prefix, reproducing the table exactly again.
  **The twenty-third row is weaker than the twenty-two above it and is marked so.** It was read
  on 2026-09-08 by the agent that supplied it, with the whole verdict string anchored and
  restricted to the scenario step column, and **it was not re-read by the pass that wrote it
  here**: `gh` was present on this host but unauthenticated, so no CI log could be opened at
  all. Everything in this file about run `34247027502` — its `continuous_line` verdict, its
  `pick_and_place` verdict and its `bringup` teardown — carries that one reading and no
  second one. **That weakness is not inherited by the two rows below it**: `gh auth status`
  reports this host authenticated as of 2026-09-08, and both new rows were read here from
  their own downloaded logs.
  **The twenty-fourth and twenty-fifth rows were read on 2026-09-08 at `6d51966`**, each by
  `gh run view <id> --log` into a file and then the step-restricted anchored match the
  `bringup` bullet gives. `34280056331` prints one line, `Scenario 'continuous_line' passed`.
  `34258470163` prints one line, `Scenario 'continuous_line' failed — 1 cycle assertion(s)
  failed`.
  **The last seven rows are the ones taken on the geometry this repository ships**, and the
  collision-geometry item in the gap list below is where that is kept; this file said "the
  last row is the only one" until 2026-09-07, "the last four rows" until 2026-09-08 and "the
  last five rows" for part of that day.
  **The prediction the previous re-audit made here was wrong, and how it was wrong is the
  point.** It said *"The next reader should not expect a twentieth soon"*, on the strength of
  five completed `main` runs after `e51238e` — `33534312429`, `33537296558`, `33551642119`,
  `33553778365` and `33567737946` — that all failed at the `Test` step and therefore
  **skipped** all three scenario steps (`gh run view <id> --json jobs`, read over all five on
  2026-09-01; that reading is not disturbed). **The next scenario-driving run started about
  eighteen minutes after the re-audit's own run did** — `33574775657` at `abdae38` was created
  2026-09-02T00:18Z and `33575992281` at `4ef2d7c` at 2026-09-02T00:36Z
  (`gh run list --branch main --json createdAt`) — and two more followed. The full account of
  the window, from
  `gh run list --branch main` on 2026-09-07, is those five plus **two cancelled runs that
  reached no scenario at all** — `33550148315` at `1b4c07b` and `33574775657` at `abdae38`,
  each with **no verdict line of any kind** in its log — plus the three new table rows. The
  five-run list was never wrong about those five; it was **incomplete as an account of the
  window**, because it omitted `33550148315`, which was already cancelled when it was written.
  A forecast about CI is not a measurement and should not be written in a rulebook.
  **The account of the window since `13bc8e9` is complete and short**, from
  `gh run list --branch main` on 2026-09-08: the two new table rows and **one run still in
  progress** — `34284120566` at `6d51966`, created 2026-09-08T22:05:52Z, which has reached no
  scenario verdict and is in no figure here. **No run exists for `dd6772f` at all**
  (`gh api repos/:owner/:repo/commits/dd6772f/check-runs` reports `total_count` 0, read on that
  date): it and `6d51966` were pushed together, so only the tip was built. **A commit on `main`
  is not a CI run**, and counting commits would have produced a twenty-sixth row that never
  ran. No forecast is made here about what `34284120566` will say.
  **Teardown is read for eighteen of the twenty-five and is clean in all eighteen, and this
  file
  said it was unread until 2026-09-01, read for fifteen of nineteen until 2026-09-07, for
  sixteen of twenty-two until 2026-09-08 and for seventeen of twenty-three for part of that
  day.**
  The verdict line distinguishes **three** states, not
  two: `scripts/scenario` prints `Scenario 'X' passed` only when `launch_test` itself exited 0,
  which it cannot do while a post-shutdown `TestCleanShutdown` assertion is failing; it prints
  `Scenario 'X' passed its cycle assertions` on the advisory branch where the cycle passed and
  teardown did not; and `Scenario 'X' failed — …` otherwise. **The middle string appears for
  `continuous_line` in none of the twenty-five runs**, so each of the eighteen bare `passed`
  verdicts carries its teardown with it, and in the seven whose cycle failed teardown is masked
  by the cycle failure and stays genuinely unread.
  **This file said until 2026-09-07 that "the advisory branch has never fired in CI", and
  that is now false.** It appears **four** times in the twenty-five runs' logs and still
  **never for this
  scenario**: at `f6a3779`, and again at `13bc8e9`, one of the two `bringup` invocations printed
  `Scenario 'bringup' passed its cycle assertions`; and at `e18251e` **both** a `bringup`
  invocation and `pick_and_place` did. It said "exactly once" until 2026-09-08 and "twice … on
  consecutive runs" for part of that day —
  counts over the runs that existed then.
  **The clause "and never for this scenario" was the only durable half and it is worth keeping
  separate**: three of the four appearances are `bringup`'s and one is `pick_and_place`'s, and
  the sentence about `continuous_line` has not been falsified once. The rest of it was a claim
  about what has never happened, and §2 has now been caught by that **three** times.
  **`--teardown-advisory` never reaches the scenario Python**: `scripts/scenario` puts it in
  `TEARDOWN_POLICY` and not in `LAUNCH_TEST_ARGS`, so the post-shutdown assertions always run
  and the flag only decides how their failure is reported. **`scripts/scenario` is correct here
  and is not to be changed on the strength of this paragraph** — what was wrong was the reading
  of it, not the instrument.
  **The fourth failure is not the other three, and that was the finding of the 2026-09-01
  re-audit.**
  `33343317444` never reached a milestone at all: its cycle assertion is
  `subprocess.TimeoutExpired` on `ros2 run ros_gz_sim create -file /tmp/cite_workpiece.sdf`
  after **120 s**, so the work-piece was never spawned and the line was never given anything to
  carry. That is the spawn path, not the transfer stall — and it must not be folded into the
  three below on the strength of sharing a scenario name.
  **This file called it "one event" until 2026-09-08. It is two, and the second one carried
  two work-pieces end to end first.** `34258470163` at `e18251e` fails on the same exception
  from the same command — `subprocess.TimeoutExpired: Command '['ros2', 'run', 'ros_gz_sim',
  'create', '-file', '/tmp/cite_workpiece.sdf', '-name', 'workpiece', '-x', '-0.475', '-y',
  '0.0', '-z', '0.63']' timed out after 120 seconds` — raised through
  `cite_bringup/gz.py`'s `run` from `_spawn_workpiece`, read here from that run's own log on
  2026-09-08. **Where the two differ is how far the run got before it**, and that is why the
  table row says 2 of 3 rather than 0 of 3: pieces 1 and 2 each walked the whole ten-milestone
  ladder, `line_orchestrator` printed `wp_000001 reached station_accumulation; 1 completed` and
  then `wp_000002 … 2 completed`, and the six grasps in those two carries all reported a
  genuine friction stall (`commanded 45.0 mm, reached 49.5–49.9 mm, stalled=true,
  reached_goal=false, effort=60.0 -> holding`, six occurrences in that run's
  `continuous_line` step). The timeout is on the spawn of
  **piece 3**, about 122 s after piece 2's last milestone, and `Ran 1 test in 890.871s`.
  **So "never reached a milestone at all" describes the 2026-08-31 event and not this one**, and
  the shared thing is the exception and the command, not the state of the line.
  **Nothing about either is attributed and the second adds no attribution.** It is still not
  established whether this is the partition defect class §10 names, a starved runner, or
  something else. **The line was not stopped**: no `escalated to an operator` line appears in
  that run's `continuous_line` step, no station reported `BLOCKED` — the eight `BLOCKED` strings
  in that step are `detection_server` reporting beam levels — and the raise came from
  `_spawn_workpiece` before any milestone loop. **So `30baea8`'s halt check and `_context`
  report were not on this run's path**, and the sentence below saying no run of the cell has
  exercised them survives its first CI failure since it was written. Two events, at
  two commits, on two runners nobody prepared, eight days apart, with nothing registered in
  advance. **That is not a rate**, and a second occurrence of an unattributed signature is a
  second occurrence and not a diagnosis.
  **The other three failures have the identical signature**, which is the finding: a work-piece
  reaches milestone 2 of 10, `lifted(station_transfer_1: cell_a__table_pick__surface)`, never
  reaches milestone 3, `on_link(station_transfer_1: cell_a__conveyor_1__infeed)`, and times
  out on the 420 s leg ceiling with `station_transfer_1` reporting `WAITING`, occupancy 1/1
  and the piece still assigned to it. **In all three of those `LineState` read `RUNNING` with
  `blocked_reason=none stall_reasons=none`.** `station_transfer_1`'s inbound edge in the
  generated topology is `via: null`, so ADR-0039's detector has no belt setpoint to read and
  is structurally silent there — the blind spot that record names.
  **The three runs end with the part at the same pose to the millimetre**, held in the air for
  the rest of the leg: `(-0.001, 0.273, 1.201)`, `(-0.001, 0.273, 1.201)` and
  `(-0.001, 0.274, 1.201)`, each about 390 s after the peak of the lift. **So the grasp is not
  what failed** — `lifted` is *measured*, computed by the scenario as
  `sample.z - self._resolve(milestone.frame)[2] > LIFTED_M` — in that file's `milestone.kind == "lifted"` branch,
  cited by symbol because the line number given here (`674-675`) was stale by 2026-09-08 and a
  line number in a file under active edit goes stale again — rather than
  reported by the arm, so the piece demonstrably rose off the pick frame and never came back
  down.
  **What stops the piece between those two milestones is now established, by one
  investigation and not by a campaign.** The gripper's *result* timed out on a wall-clock
  deadline supervising a simulation-time process, `Pick` returned `TIMEOUT` without ever
  saying what the gripper did, and the retry's own `MoveToHome` carried the part **off** the
  beam the station was about to wait on again — so the station re-entered `AwaitTrigger` on a
  beam that had gone clear and stayed clear, holding the piece. Two layers, two records, both
  written 2026-08-29:
  [ADR-0045](docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md) for the L3
  deadline and [ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)
  for the L4 retry. **Both stay `Proposed`, and both are now implemented and merged on `main` at `c555440`.** The
  status does not move because what would move it is a `continuous_line` run on a CI runner in
  which the gripper fails to answer and the line reports it, and **no such run exists** — a
  run in which the gripper answers quickly shows nothing at all. **What is evidenced is the
  mechanism, not the outcome:** a launch test holds simulated time still while the wall clock
  passes the constant the old code compared against, then advances simulated time past the
  declared value and requires the wait to end, the cancel to be sent and the report to say
  custody is unestablished; unit tests on the shipped station tree require a station that
  still holds its work-piece to be refused its retry and to go `STATE_BLOCKED`. Both ADRs were
  corrected on 2026-08-30 in that review — see each record's Correction section.
  **Every timing figure in those records is reported by the project owner's investigation and
  was not re-measured**, including the on-demand reproduction under CPU starvation — no
  thresholds registered in advance, no directory in
  [`docs/measurements/`](docs/measurements/README.md), and both records say so in their own
  verification tables. What *is* checkable in the mechanism — the constant, the clock it is
  compared against, the controller's terminating rule read upstream, the recovery branch, the
  topology edge — was read from source and is tabulated there. Cite the records; do not copy
  their numbers around (P1).
  **This supersedes the account that called `33158091922` "the only one ever taken off a
  developer machine".** It also means the local sets above and the CI set disagree, and that
  the disagreement is now a repeated failure rather than a single one.
  **The fifth and sixth failures are a third signature, and unlike the other four the line
  said so.** `33575992281` at `4ef2d7c` and `33603610958` at `51195e0`, both 2026-09-02, fail
  with the same assertion character for character apart from its timestamp — `the line stopped
  while waiting for the work-piece 'workpiece' to leave the simulator. BLOCKED at <t>:
  station_transfer_1: result code 10: escalated to an operator` — followed in both by
  `1 not found in [0, 130] : line_orchestrator-30 exited with 1`. The two tracebacks name the
  same four frames at the same four line numbers, and each log carries **3**
  `escalated to an operator` lines emitted by `line_orchestrator`, against **0** in the run
  that passed. **Count the emitter, not the string**: `grep -c "escalated to an operator"`
  returns 20, 20 and 16 over the three runs, because seventeen or sixteen of those come from
  `skill_goals_test` and `line_nodes_test` in the `Test` step and have nothing to do with the
  scenario. That raw count was nearly written into this file as the signature.
  **This is not the silent dead end and must not be folded into it.** In the three failures
  above, `LineState` read `RUNNING` with `blocked_reason=none stall_reasons=none` and nothing
  escalated; here the station reports `BLOCKED`, the coordinator escalates, the belts are
  commanded to a standstill and the process exits 1 — which is what ADR-0038 specifies. It is
  also not the spawn timeout at `33343317444` or the one at `e18251e`. Three signatures, seven
  failures; sharing a scenario
  name is not evidence of sharing a cause, which is the move this bullet already warns against
  for the fourth failure. It said "six failures" until 2026-09-08, and **the signature set did
  not change when the seventh arrived** — three, two and two.
  **That sentence ended "so the scenario's fail-fast fired as designed rather than waiting out
  the leg ceiling" until 2026-09-08, and that clause was false.** Two independent readings say
  so. **Timestamps:** from the coordinator's first `escalated to an operator` line to the
  `AssertionError` is **417.8 s** at `4ef2d7c` and **420.6 s** at `51195e0`, against
  `LEG_CEILING_S = 420.0` — the ceiling was spent in full, and those figures are the
  investigation's, read from the two CI logs and **not re-read here**. **Source:** through
  `13bc8e9`, and identically at both failing commits, `_run_one_piece`'s per-milestone loop
  contained no halt check at all — neither `self._halt` nor `_fail_if_the_line_has_stopped`
  appears between its definition and `_context` at `4ef2d7c`, `51195e0` or `13bc8e9` — and
  `_fail_if_the_line_has_stopped` was reached only from `_spin_until`; what finally raised was
  the *removal* wait's pre-loop check, which is why the message named the work-piece leaving
  the simulator — a wait with nothing to do with the fault — and carried none of the diagnostic
  report, because `_context` was built at the verdict step and every earlier raise skipped it.
  That half was re-derived on 2026-09-08 with `git show <sha>:tests/scenarios/continuous_line.py`
  over all three commits.
  **It is fixed at `30baea8` on `main`, and what the fix evidences is narrow.** The leg loop
  gained a halt check and `_fail_if_the_line_has_stopped` now appends the full `_context`
  report on every path that raises. The guard is
  `tests/scenarios/guards/test_a_stopped_line_ends_the_run.py`, and it **fails 6 of its 9**
  against the pre-fix scenario and **passes 9 of 9** after — re-derived on 2026-09-08 by
  running that file from `30baea8` against a worktree at `13bc8e9`, then in this checkout.
  **It is a guard over a fabricated clock and a fabricated `LineState`, not a run of the
  cell**: it drives the shipped functions unbound against a fabricated `self` and brings
  nothing up. **No run of the cell has exercised the new path.** So what is evidenced is that
  the code can now end a run promptly and print the report; nothing here says the next failure
  of this kind was, or will be, reported that way.
  **What the logs record above the escalation, stated as what the log says and not as a
  cause.** In both runs `/cite/cell_a/arm_1/place` returned code 10, after the arm's
  `JointTrajectoryController` aborted — `State tolerances failed for joint 2` and `Aborted due
  to goal_time_tolerance exceeding by 0.506172 s` at `4ef2d7c`, `0.506390 s` at `51195e0`.
  **Why the arm stopped part-way is not established** and nothing here attributes it. The
  chain from an execution-side tolerance (ADR-0036) through the classifier (ADR-0037) to the
  stopped line (ADR-0038) is visible in both logs and **absent from the scenario half of
  `f6a3779`'s**, whose only code-10 lines come from `skill_goals_test` and `line_nodes_test`.
  Whether any of the nineteen runs before these contains the same chain was **not checked** —
  for those nineteen only the verdict lines were re-read.
  **What an investigation added on 2026-09-08, at investigation strength: read from those two
  logs, on two runs, with nothing registered in advance and no cause attributed.** The skill is
  `Place` and the motion is its **final descent onto the release pose** — the fifth trajectory
  of the piece, after `Place`'s own approach had reported `Goal reached, success!` — so the arm
  was over `cell_a__conveyor_1__infeed` **holding the part** when it failed. The joint is
  **`arm_1_joint3`**, and the log's `State tolerances failed for joint 2` names that same joint
  rather than a second one: the controller prints a **zero-based index** into its own `joints:`
  list, which for `arm_1_joint_trajectory_controller` is `joint1 … joint5`
  (`workspace/src/cite_generated/control/cell_a_arm_1_controllers.yaml:47-52`), and upstream
  prints `joint_idx` as an index into the error arrays (`ros2_controllers`, `jazzy`,
  `joint_trajectory_controller/include/joint_trajectory_controller/tolerances.hpp`, read
  2026-09-08). **Those two source facts are re-derived here; every log-derived figure in this
  paragraph and the next is the investigation's and was not re-read.**
  **The arm was stationary or drifting further from its goal, not converging, and this is the
  strongest thing the investigation produced.** Recovered two independent ways that agree — the
  limiter's clamped command plus one control cycle of that joint's 3.14 rad/s limit, against
  `actual + reported error` — the implied movement over the last cycle is **1.0e-4 rad** at
  `4ef2d7c` and **4.3e-6 rad** at `51195e0`. **That is what rules out a scheduling lag**: a lag
  closing on its target would show the opposite velocity sign.
  **It violates a deliberate design margin.** `PlaceAt`'s `release_height_m` default is
  **0.04** against a 50 mm part whose centre rests at 0.025 — a deliberate **15 mm** air gap,
  stated in that port's own comment
  (`workspace/src/cite_orchestration/include/cite_orchestration/skill_nodes.hpp:675-686`, read
  2026-09-08) — so nothing should touch the belt during that descent.
  **Nothing in the cell changed to explain the onset, and option F is not the discriminator.**
  Between the last passing hull run `e51238e` and the first failure `4ef2d7c`, the diff over
  `workspace model tools tests scripts .github assets` is **one test file**
  (`cite_test_hardware/test/test_unreachable.py`). And `git merge-base --is-ancestor d3eeac4
  <sha>` fails for `4ef2d7c`, which failed **without** option F, and succeeds for `51195e0`,
  which failed **with** it, and for `f6a3779`, which **passed** with it. Both re-derived on
  2026-09-08.
  **The physical cause is unestablished and nothing above attributes one.**
  [`docs/open-work.md`](docs/open-work.md) #60 is where the item and the cheapest measurement
  that would settle it are kept.
  **Neither run is evidence for ADR-0045's or ADR-0046's promotion condition, and it would be
  easy to read it as such.** That condition is a `continuous_line` run in which *the gripper
  fails to answer and the line reports it*. Result code 10 is `MOTION_INTERRUPTED`, ADR-0037's
  classification of a trajectory that stopped part-way; **no gripper deadline expiry appears
  in either scenario** — the only `returned code 9` lines in either log come from the
  `line_nodes_test` unit test, not from the cell. That these failures land at the same station
  as the three silent ones is a **hypothesis and nothing more**; it is unestablished, an
  investigation is running separately, and its result may not be anticipated here.
  **Two events, on two CI runners nobody prepared, at two commits, with nothing registered in
  advance. That is not a rate.**
- **The teardown flake is two failure families, and process identity predicts the family
  exactly.** What this file said until 2026-08-27 — four undifferentiated processes, identity
  not predictive, run duration the only candidate predictor, cause unestablished — was wrong
  on all four counts. Split by exit status:
  - **Exit code 1 — `topology_server.py` and `model_info.py`.** Both `cite_facility` `rclpy`
    nodes, both instances of **one cause, which is established and fixed**.
    [ADR-0034](docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md) records it: two
    upstream `rclpy` shutdown races, each link read in upstream source rather than inferred,
    each compensation carrying the condition for deleting it. **Read the ADR.** Restating the
    mechanism here would be the duplication P1 forbids.
  - **Signal deaths — `move_group` (×3) and `skill_server` (×1), and still unexplained.** The
    two observed in `continuous_line` are both MoveIt-linked C++, and **"MoveIt-linked" is no
    longer a description of the family**: the campaign below caught `parameter_bridge`, which
    links no MoveIt code, exiting -11 at teardown. One event, and enough to retire the
    characterisation.
    **This family now has a campaign, and it is the citation for every figure that used to sit
    in this bullet** —
    [`docs/measurements/2026-08-27-teardown-signal-family/`](docs/measurements/2026-08-27-teardown-signal-family/results.md).
    Thresholds were registered before the first trial and applied literally. Read it rather
    than trusting the summary here; the numbers are deliberately not copied (P1).
    **Its primary result is INCONCLUSIVE and must not be read as reassurance.**
    `skill_server` did not exit -11 at all in the campaign's **pre-fix** arm, so the rig does
    not reproduce the defect, and the campaign's own rule 1 refuses the clean post-fix arm as
    evidence that anything was fixed. The `continuous_line` death remains un-reproduced and
    un-explained; it is *rarer*, not *understood*. **This bullet said until 2026-08-28 that the
    non-recurrence figure was "supplied rather than reproducible from this checkout". It is now
    published with its logs and its analyser** — and note that it was measured at `de67d8b`,
    not at this commit.
    **The hypothesis gained a demonstration and did not gain a cause.** `skill_server` holds a
    `shared_ptr<MoveGroupInterface>` constructed from its own node and
    `MoveGroupInterface::getNode()` returns a `shared_ptr` reference, so a reference cycle may
    mean `~SkillServer` never runs. This bullet said until 2026-08-28 that **nothing had been
    instrumented to show the destructor is skipped. That is wrong** — the campaign instrumented
    it under `gdb`, one run in each direction, and the destructor demonstrably does not run
    while the cycle is intact. What is still **not** demonstrated is the part that matters: no
    mechanism links a skipped destructor to a signal death, and the arm that would have tested
    it never reproduced one.
    **`skill_server`'s -11 is outside the exemption and stays there.** The exemption in
    `tests/scenarios/continuous_line.py` covers `move_group` and -11 and nothing else.
    `move_group`'s is characterised and upstream, with the stack — the campaign's `gdb`
    backtrace puts frame #11 in `move_group`'s own `main`. **No exemption has been added or
    widened**, and widening one to cover `skill_server` would tolerate an undemonstrated cause,
    which is the opposite of what the split bought.
  **Run duration is retired as a predictor.** Three `continuous_line` runs on one machine on
  2026-08-27 took **478.055 s (passed), 480.607 s (failed) and 497.710 s (failed)**. The
  longest did fail, so duration is not *uncorrelated* — but 2.5 s separating a pass from a fail
  rules it out as the mechanism. The comment in `tests/scenarios/continuous_line.py` still
  asserts the duration correlation and has not been updated. The superseded account also named
  `parameter_bridge` (-6) and `gz` (-9); those two are outside the set the split was measured
  over and are not classified here. `parameter_bridge` has since been observed on **both** -6
  and -11 in the campaign cited above, each once — which is what removes "MoveIt-linked" from
  the signal family's description, and is still two events rather than a rate.
  **The family now has two occurrences on CI runners nobody prepared, on consecutive runs and
  on both signals.**
  The two campaign events are at `de67d8b` on a developer machine; these two are not.
  In CI run `34085965578` at `f6a3779`, one of the two `bringup` invocations passed its cycle and
  failed its post-shutdown check on `FAIL: test_nothing_of_ours_exited_badly` with
  `parameter_bridge-2 exited with -11`, and nothing else in that run exited badly. **In the next scenario-driving run in the
  table above, `34247027502` at `13bc8e9`, the same thing happened on the other
  signal**: `parameter_bridge-2 exited with -6`. **Neither is exempted**:
  `tests/scenarios/bringup.py`'s
  `UPSTREAM_TEARDOWN_SEGFAULT` covers
  `move_group` and -11 and nothing else, so the process that died is outside it on both
  signals, exactly as
  `skill_server`'s -11 is outside `continuous_line`'s. **Four `parameter_bridge` events in
  total across two
  machines, and still not a rate.** This bullet said "a third … three in total" until
  2026-09-08. Nothing about the
  cause moves: no mechanism is demonstrated for any member of this family, and **no exemption
  may be widened to absorb this one.** The `13bc8e9` reading is the single 2026-09-08 reading
  described in the `continuous_line` bullet and was not re-read here.
  **`gz` at -9 has reached CI, and it is recorded here rather than classified.** In CI run
  `34258470163` at `e18251e`, two post-shutdown checks failed in the same run, in two different
  scenarios, on the identical assertion: `FAIL: test_nothing_of_ours_exited_badly` with
  `AssertionError: -9 not found in [0, 130] : gz-1 exited with -9`, once in
  `bringup.TestCleanShutdown` at 17:59:45Z and once in `pick_and_place.TestCleanShutdown` at
  18:04:00Z. Nothing else exited badly anywhere in that run's three scenario steps, and the
  `continuous_line` step recorded no bad exit at all. Read here on 2026-09-08 from that run's
  own log. **It is not exempted anywhere**: `UPSTREAM_TEARDOWN_SEGFAULT` is `"move_group"` and
  the allowance is `-11` in all three of `tests/scenarios/bringup.py`,
  `tests/scenarios/pick_and_place.py` and `tests/scenarios/continuous_line.py`, read in this
  checkout on that date. **No exemption may be widened to absorb it.**
  **This is deliberately not folded into the signal family above, and the reason is this
  bullet's own rule.** The superseded account named `gz` (-9) among the processes it listed, and
  this file has said since 2026-08-27 that `parameter_bridge` (-6) and `gz` (-9) are **outside
  the set the family split was measured over and are not classified here**. That is still the
  case: -9 is `SIGKILL` and the other members of the family died on -6 and -11, the split was
  never measured over this process, and **sharing a teardown and a minus sign is not evidence
  of sharing a cause**. Two events, in one CI run, at one commit, on one runner nobody
  prepared, with nothing registered in advance. **That is not a rate and it is not a
  classification.**
  **One earlier observation of the same process and signal exists and is local**, at `37921dd`
  on `feat/hosted-by-derived`, recorded in the `bringup` bullet above where `pick_and_place`
  failed a teardown on `gz-1 exited with -9`. **That it is the same string is a fact; that it
  is the same cause is not established**, and the local pair was reported by the agent that ran
  it and not re-run.
- **The recorded real-time factor of 0.14 is conditional, and the condition is roughly one CPU
  core.** It is not wrong: it reproduces on the development host — both halves of the recorded
  pair, RTF and the `joint_states` rate, together and by two independent instruments — when the
  cell is confined to about one core. Unconfined, the same host idles slightly **above** real
  time and holds the configured `joint_states` rate. Bring-up is rejected as the condition and
  so is load. Every figure is
  [`docs/measurements/2026-08-29-real-time-factor-conditions/`](docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md);
  **the one place in the tree that states the figure with its condition is
  [`docs/architecture/cross-cutting-testing.md`](docs/architecture/cross-cutting-testing.md)
  under "Wall-clock ceilings"**, and everything else cites it rather than restating it (P1) —
  six copies of an unconditioned number is how the omission survived for five days.
  Two consequences to carry: **every scenario ceiling is wall clock**, so a starved host times a
  scenario out with nothing broken and **no ceiling may be widened to absorb that**; and
  **Gazebo's own `real_time_factor` field over-reports under CPU starvation by up to a factor of
  four**, printing a number close to 0.14 while the cell runs at a twenty-fifth of real time.
  Measure `Δ sim_time / Δ real_time` from the world's stats topic over a stated window; never
  quote that field.
  **The ceilings themselves have since been measured, at four allocations on one host, and two
  of them read too loose.**
  [`docs/measurements/2026-09-02-scenario-ceilings/`](docs/measurements/2026-09-02-scenario-ceilings/ANALYSIS.md)
  — thresholds registered before the first trial, machine named, taken on the shipped
  configuration — bands every scenario ceiling per allocation. **Read it before touching a
  ceiling**, and read what it refuses to say: it attributes nothing to either the throttle or
  the hulls, a family of its cells has **no upper bound at all** because the intervals are
  smaller than its poll quantum, eight are **NOT ASSESSED** where silence is not a clearance,
  and its own rule forbids differencing any margin against the 2026-08-29 campaign's. **It
  changes no ceiling and proposes no value; changing one is the project owner's.** The figures
  stay in that directory (P1) — cite it, and the standing instruction above is untouched: **no
  ceiling may be widened to absorb a slow host.**
- **Phase 2 has split into 2.A and 2.B, and 2.A's bring-up mechanism is built: a pair has come
  up.** Charter v1.9 (2026-08-29) records the split: 2.A
  pairs the plant with a **virtual counterpart** — a second full simulation of the same cell,
  modelled as if it were physical — and 2.B replaces that stand-in with the real cell. The
  charter also records that **2.A closes no clause of the Phase 2 exit criterion and produces
  no fidelity number**, since both sides run the same L0 model and the same solver. Read §8
  there rather than inferring it from what is on disk.
  **What landed:** ADR-0041's decision 3 as a zone-level `twin: {sides: single | pair}`,
  required with no default, plus an optional per-asset `hardware.counterpart_backend`;
  ADR-0042 as a Gazebo transport partition derived per side and emitted into the generated
  bring-up plan; ADR-0043's first half as `real_time_factor: 1.0` in the generated world;
  `TwinMode/MODE_VIRTUAL_LEAD = 5` in `cite_interfaces`; and, on 2026-08-30, ADR-0044 clause 4's
  domain refusal, ADR-0047's readiness witness and pair supervisor, and the `--pair` flag that
  reaches them.
  **What a paired model is not, and this is the part to carry.** `model/facility/zones.yaml`
  declares `sides: single` today, so nothing in this repository is paired. Set it to `pair`
  and the generated plan gains **one more `sides:` entry — carrying the counterpart's
  partition *and* its `domain_offset` — and a `counterpart_backend:` line per controller
  manager. That is all it gains** — no second world, no second controller manager, no second
  set of node names, and **no second launch file**: a counterpart is the same
  `simulation.launch.py` started again in another environment, so there is nothing here for
  pairing to add. **The offset is emitted for every side, including a
  `single` zone's plant**, which is why it is not a thing pairing adds: an isolation that
  appeared only when someone paired a cell would be untested on every run that does not
  (ADR-0042, ADR-0044 clause 4). **Ask the plan for the shape rather than reading it out of
  this paragraph** — an exhaustive list of what a change does not do is a claim with an expiry
  date, and this sentence has already expired once.
  `cite_bringup/gz.py` addresses **a side by name and never by position**. This file quoted
  that module's docstring until 2026-08-30 for the sentence "bringing a counterpart up is a
  separate launch and is not built yet"; **`grep -n "not built yet"` on that file now returns
  nothing**, and the separate launch exists. A quotation of another file is a claim about that
  file and goes stale exactly as a count does.
  **A pair comes up, and what is evidenced is the mechanism and the two isolations — nothing
  more.** `./scripts/sim --pair` starts two independent `ros2 launch` processes through
  `cite_bringup.pair`: the same `simulation.launch.py` twice, each given its own `side:=` and
  its own `ROS_DOMAIN_ID`, joined on a token each side prints once its own readiness witness has
  seen every skill and detection action server the plan declares answering **on that side's
  domain**. Nothing sequences them, because there is no order to impose (ADR-0047). The
  supervisor holds no ROS context, and an import-graph test — one that resolves first-party
  packages and relative imports, after three bypasses were found in a walk that did not — is
  what makes that a fact rather than a promise. A side that ends ends the pair, naming the side
  and its status; a pair that never joins fails on a ceiling saying that side never announced
  **and** never exited, which fired on its first real cause: an installed program without its
  executable bit, a failure `launch` reports on its own logger without emitting `ProcessExited`,
  so no gate saw it and nothing else would have.
  **The evidence is three runs on one machine, reported by the implementing agent of `b3b7b66`
  and not re-taken by review.** Both isolations were read back **at runtime** rather than off
  the launch file: `/clock` with **one** publisher on each domain where a merged graph would
  show two; **22** Gazebo topics per partition under byte-identical names, one stats publisher
  each at different endpoints; and **41** nodes per domain, every name this project forms
  present once on each. That is P2 demonstrated — on one machine, three times, by the agent that
  wrote it.
  **What a pair is not, and none of this is a fidelity claim.** 2.A produces no fidelity number
  at all, because both sides run the same L0 model and the same solver. **No paired scenario
  exists, and none can take today's shape**: `launch_test` with `IncludeLaunchDescription` puts
  the launch inside the test process, which holds one context on one domain, so two sides cannot
  be included there, and `./scripts/scenario` addresses the plant. **So nothing automated brings
  a pair up** — a regression in the witness, the token or either side's bring-up would not fail
  CI. And because the shipped model is `single`, as above, **`./scripts/sim --pair` refuses on a
  clean checkout** rather than inventing a second side: reproducing the run means editing L0 and
  regenerating, which moves `MODEL_HASH`. Two hazards are recorded in `cite_bringup/pair.py` rather than fixed — a
  signal handler's `Queue.put` can deadlock the supervisor against its own join, with the ceiling
  unable to fire because the stuck call is what enforces it; and `READY_CEILING_S` is stated
  rather than derived from the ceilings a side's own gate chain carries.
  **ADR-0041 and ADR-0047 were promoted on this and ADR-0043 and ADR-0044 were not**, each on
  the condition it wrote for itself. Read those four status blocks rather than this paragraph
  before assuming which way any of them went.
  **A checkout now claims two domains, not one, and every checkout's domain changed the day
  that landed.** `scripts/_lib.sh` allocates an odd base per checkout and the counterpart takes
  the even number above it, so no counterpart can land on another checkout's plant — parity,
  not luck. A cell launched before that change and a shell entered after it are on different
  domains, and the shell finds an empty graph; it is one-time and moves no committed artifact.
  `./scripts/enter`, `./scripts/scenario` and `./scripts/sim` **without `--pair`** all land on
  the **plant**, which is the side every script here addresses; `./scripts/sim --pair` starts
  both sides and leaves the invoking shell on the plant's domain. `./scripts/doctor` prints that
  domain and says which side it is. `docs/operations/troubleshooting.md` has the recipe for resolving any side's
  domain from the plan, and `docs/onboarding/getting-started.md` states the allocation.
  **The plan carries an offset and never an absolute domain** — one derived from the deployment
  differs in every clone and breaks `./scripts/validate-model`'s byte-identity check; one
  derived from the model is identical in every clone and lets two checkouts of one commit
  discover each other. `cite_bringup.plan.resolve_domain_id` is the one place base and offset
  are added, and **the refusal ADR-0044 clause 4 owes is built**: `require_domain` refuses a side
  whose process environment does not carry the domain the plan resolves for it, the way
  `require_gz_partition` refuses a missing partition, with the base arriving on its own channel
  `CITE_DOMAIN_BASE` so that the plant's half compares two independently sourced values instead
  of the tautology `env == env + 0`. **ADR-0044 is nevertheless still `Proposed`, for a reason
  it names itself**: its promotion condition also requires a source scan over `tests/` that
  fails when a harness enters a ROS graph outside one stated door, that guard does not exist,
  and `grep -n rclpy.init tests/scenarios/*.py` still returns three bare calls.
  **`MODE_VIRTUAL_LEAD` was vocabulary only until 2026-09-01 and is not any more.** This file
  said *"nothing routes on it, `SetMode` has no server, and `cite_twin` does not exist"*, and
  all three clauses are now false. `cite_twin` is on disk, in charter §7's tree and built by
  `./scripts/build`, and `grep -rn MODE_VIRTUAL_LEAD workspace/src` now also reaches
  `cite_twin/cite_twin/routing.py` **twice, once in each of that module's two tables** — which
  is what "routes on it" means. Run the grep for the full set rather than taking a list from
  here; it reaches `mode.py`, `cite_bringup/plan.py` and the package's tests as well.
  **What is wired, read from the source on 2026-09-01.** `cite_twin/twin_boundary.py` is one
  node holding **one ROS context per side** — the only component with endpoints in both
  domains (ADR-0044 clause 3) — and it `create_service`s `SetMode` on
  `SetMode.Request.SERVICE`, publishes `TwinMode` latched and `DivergenceMetrics` per asset,
  and serves the L3 skill actions with an `ActionClient` per (side, skill). Nothing is
  republished across the boundary; what crosses, crosses in that process's memory (ADR-0050).
  `mode.py` decides one `SetMode` call and **computes** which transitions are gated instead of
  listing them: the gate is `commanded_sides(mode)` from `routing.py` intersected with the
  backend the generated plan declares for each (asset, side), and it is evaluated **before**
  `force` is read anywhere, so `force` is structurally unable to skip it. `routing.py` holds
  ADR-0050 decision 2's table and refuses to import if `TwinMode` declares a mode either table
  has not been told about. `MODE_VIRTUAL_LEAD` dispatches to both sides in that table.
  **What L5 is not, and this is the part to carry.** **Nothing starts it.** `twin_boundary.py`
  is installed as a program and appears in **no launch file** — `grep -rn twin_boundary
  workspace/src` outside `cite_twin` returns nothing, and the generated bring-up plan has no
  entry for it, so `./scripts/sim` in any form brings up no L5 at all. **No scenario and no CI
  step reaches it**: `grep -rn -- --pair tests .github` and `grep -rn cite_twin tests .github
  scripts` both return nothing on 2026-09-01, so a regression in the boundary, the mode gate or
  the monitor fails no gate outside the package's own tests. What holds it is those tests, which
  `./scripts/test` runs — five pytest modules and two launch tests, driving the node against
  **fake sides**, which bring no cell up and move no arm. **Nothing here is evidence about
  motion, and 2.A produces no fidelity number in any case** (charter §8).
  **The divergence metric has a consumer and no producer, and that is by decision rather than
  by omission.** ADR-0050 decision 3's conjunction has five terms, and term 3 — each side's
  accumulated clock deficit, within ADR-0049's bound — is **false for every sample by
  construction**, for two independent reasons that are both in the code: `DEFICIT_BOUND_S` is
  `None` (ADR-0049 decision 2 declines to set it) and the one production caller that builds an
  `Operand`, at `twin_boundary.py:720`, passes `clock_deficit_s=None` because nothing in this
  tree measures it. So **`valid` cannot be true today**, the node publishes samples that name
  the term that failed, and the package's own paired launch test asserts exactly that —
  `self.assertFalse(sample.valid, "the clock-deficit term has no instrument")`, in
  `test_twin_boundary_paired_launch.py`, after requiring both operands to have arrived. Four of
  `DivergenceMetrics`' six fields carry NaN rather than zero, because they are uncomputed rather
  than invalidated. **Do not make `valid` true by weakening a term**; the module says so itself,
  and no number it produces is a fidelity number.
  **The throttle is a ceiling, and ADR-0043's other half is now measured and NOT MET.**
  SDFormat's `real_time_factor` bounds how fast a server may run and cannot make a slow one
  faster, so it binds only where the cell has spare capacity: on the machine that measured it,
  it is at or near a no-op under load and binds only on an idle cell.
  **Both sets of figures live in
  [ADR-0043](docs/adr/0043-hold-both-sides-to-the-wall-clock.md) — half 1's in its 2026-08-29
  correction, the pair's in its 2026-08-30 one — and are deliberately not copied here (P1).**
  What belongs in this file is their strength and their verdict. Each was taken by the
  implementing agent of the change that produced it, on **one machine**, with **no thresholds
  registered in advance** and **no directory in
  [`docs/measurements/`](docs/measurements/README.md)**; neither was re-taken for this file, and
  neither is a campaign — a campaign's thresholds are written before its first trial, and these
  have none, which is why they are recorded in a decision record instead of being dressed as
  one. **The verdict: both sides of the pair fell short of the 1.0 ADR-0043 requires, by about
  the margin
  [`2026-08-28-second-world-cost`](docs/measurements/2026-08-28-second-world-cost/ANALYSIS.md)
  predicted for vendor collision meshes, on a different host and with the throttle now in the
  world.**
  **Half 2 is unmet in two different ways and only one of them is the machine. This file called
  it "a measured gap in the machine" until 2026-08-31, and that was half the story.** The other
  half is the shape of the requirement: with half 1's throttle in the world a measured real-time
  factor is **capped at the declared factor by construction**, so half 2 as worded is a test no
  machine passes, and an over-provisioned machine answers it much as an adequate one does. That
  is read in upstream `gz-sim` source and recorded in
  [ADR-0049](docs/adr/0049-measure-the-real-time-floor-as-capacity.md) and in ADR-0043's
  2026-08-31 correction — which also records that ADR-0043's own throttled/unthrottled idle rows
  were the evidence against its own requirement and were never read against each other.
  **The machine is nevertheless genuinely short, and as of 2026-09-01 that is measured rather
  than inferred**: the paired shortfall is about an eighth, far outside anything a throttle loss
  accounts for, and
  [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](docs/measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
  measures the shipped vendor pair short of the 1.0 floor **with the throttle lifted** — so it
  is the machine and not the instrument. **The factor is the campaign's and is cited, not copied
  (P1)**, and every capacity figure in it is a **lower bound**, because its host could not be
  made quiet. The project owner **ratified ADR-0049's
  decision on 2026-08-31** — the 1.0 floor is kept, not relaxed, and moves onto **capacity**
  measured with the throttle lifted, plus a second requirement on the **accumulated clock
  deficit** in seconds, measured with the throttle in force. **Ratification is not promotion**:
  ADR-0049 stays `Proposed` and **neither of its two thresholds is set** — the campaign it asked
  for has run and **deliberately set neither**, and it records that the two shipped-relevant
  configurations sit far enough apart that any margin between zero and nineteen per cent
  separates them identically. **Nothing in `workspace/`, `tools/`, `tests/` or `scripts/`
  measures either quantity during a run** (`grep -rn real_time_factor workspace tools tests
  scripts` reaches the generator, its template, two world files and two test files, and no
  measurement, in this checkout on 2026-09-01); the only instrument that exists is that
  campaign's **frozen harness** under `docs/measurements/`, which no bring-up, scenario or CI
  step reaches. So half 2 is unmet under the new shape as well as the old, and nothing can be
  shown to *pass*, only to fail. ADR-0043 stays `Proposed` too, and no longer for
  the "unmeasurable today" reason it used to give. **No scenario ceiling was changed and
  none may be widened to absorb this.** The lever the campaign named is
  [ADR-0028](docs/adr/0028-convex-hull-collision-meshes.md)'s hulls; it has been pulled and it
  was not enough — read the collision-geometry item in the gap list below, which is where that
  record's state is kept.
  **The sharpest lesson of that work is a defect class, not a decision.** Every process the
  launch graph starts carried the partition; the scenario harness started its own and carried
  none, so both cycle scenarios hung at their work-piece spawn — and an unpartitioned
  `gz model --list` **exits 0 having reached no world**, so fixing only the spawn would have
  produced scenarios that verify a part moved by asking an empty transport. One door now
  exists (`cite_bringup/gz.py`) and a guard,
  `tests/scenarios/guards/test_gz_calls_carry_the_partition.py`, fails the suite if a raw
  Gazebo-transport subprocess call reappears under `tests/`. §10 carries it as a review
  checkpoint.
- **What does not work, stated plainly** (Phase 1.C/1.D, in progress). **None of these is an
  exit-criterion clause** — that list is the last bullet in this section, and it is separate.
  - **The line still stalls after a failed grasp, and the dead end is observed rather than
    predicted.** A piece fails the friction grasp, the station retries, returns to
    `AwaitTrigger` on a beam the part is **already breaking**, and waits out the leg ceiling —
    while `LineState` reports `RUNNING`, so nothing escalates and the scenario's fail-fast —
    which keys on `BLOCKED`, `FAULTED` **and `STALLED`** in the tree today
    (`STOPPED_STATES`, `tests/scenarios/continuous_line.py:467`; it was 458 until 2026-09-01
    and 465 until `eef5468` on 2026-09-02, this file carried 465 until 2026-09-03, and **the
    set itself is unchanged** through all three — re-read the line rather than trusting it,
    because it has moved twice in a week), and this file said only the first two —
    correctly stays quiet, because the line publishes none of the three. Seen twice,
    reported by the project owner on 2026-08-27. ADR-0038 records why this is deliberately **not** fixed: the
    cheap fix restarts the belt, the retry begins with `MoveToHome` carrying whatever the arm
    holds, and `Pick`'s first physical act is to open the gripper — so the retry's first move
    would open the jaws at the home pose and drop a part no planner knows is held.
    **This is one entrance to the dead end and not the whole of it** — ADR-0038's 2026-08-29
    amendment records the second, which is the item below.
    **The account above is falsified for a failed grasp by the change recorded in the item below,
    and this is the fourth time this section has carried a wrong claim.** `TakeCustody` stands
    **above** `PickAt` in the shipped tree, so a failed grasp fails *after* custody is taken —
    which means ADR-0046's custody refusal covers it: the retry is refused, the station goes
    `STATE_BLOCKED`, and `LineState` no longer reads `RUNNING`. Its own test
    (`RunningLine.AStationStillHoldingItsWorkpieceIsRefusedTheRetryAndEscalates`) drives
    exactly that case through the shipped XML. **What is evidenced is the mechanism, not the
    outcome:** no run of the cell has produced this failure and reported it, so "the line
    stalls silently after a failed grasp" is corrected as an account of the *code* and not
    retired as an account of any *run*. **What is not covered is a failure above
    `TakeCustody`** — `DetectAt` is the only skill there — which still retries onto a beam the
    part is already breaking and is reported by nothing at a table-fed station. ADR-0038
    decision 5 is untouched either way: nothing decides what to do with a held part, and an
    escalating station performs no motion, so the arm stops where it stood.
  - **The same dead end reached through a second door: the grasp holds and the retry carries
    the part off its own trigger.** Three CI runs have left a work-piece stuck between
    `lifted` and `on_link` at `station_transfer_1` — the arm has the part, the place onto
    `conveyor_1`'s infeed never happens, `LineState` reads `RUNNING` and nothing escalates.
    The evidence and the milestone ladder are in the `continuous_line` bullet above and are
    not repeated here. **The cause is established** and has two records, both written
    2026-08-29 and both `Proposed`: the gripper result deadline is a wall-clock `constexpr`
    supervising a simulation-time process
    ([ADR-0045](docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md)), and a
    station that still holds its work-piece re-enters a wait its own recovery made
    unsatisfiable
    ([ADR-0046](docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md)).
    **It is the item above's dead end with a different entrance, and the difference decides
    what a fix must do.** There the grasp fails, the beam stays blocked and the arm is empty;
    here the grasp holds, the beam goes clear and the part is in the gripper — so **a fix
    keyed on "the beam is blocked" catches only one of the two**, which is why ADR-0046 keys
    its refusal on custody instead.
    **Widening the constant is not available as a fix**: `GripperActionController` resets its
    stall search on every control cycle in which the joint exceeds
    `stall_velocity_threshold`, so the quantity the deadline is asked to bound has no upper
    bound — the rule read upstream in ADR-0045's verification table.
    **The detector is not broken; its coverage is.** In one local run reported by the
    investigation, the same fault class at belt-fed `station_transfer_3` was named by
    ADR-0039's detector **0.341 s** later and aborted the run; at table-fed
    `station_transfer_1`, `untriggerable_reason` returns `nullopt` at its first test because
    there is no inbound belt, so the line published `RUNNING` for the rest of the leg. That
    contrast is ADR-0039's 2026-08-29 amendment, one run, not re-measured.
    **Three things stay explicitly unmeasured**, chief among them why CI's gripper-close
    distribution has a long tail that the investigating host did not reproduce at a comparable
    real-time factor. ADR-0045 lists all three with the measurement that would settle each;
    none may be smoothed over here or anywhere else.
    **Both records are implemented and merged on `main` at `c555440`**, and both stay `Proposed`. **The mechanism is evidenced
    and the outcome is not**: the deadline is now measured in the node's clock and declared in
    L0, an expiry sends a cancel and latches custody as unknown so that `Pick`, `Place` and
    `Transfer` refuse rather than assume an empty gripper, and a station that still holds its
    work-piece is refused its retry and goes `STATE_BLOCKED`. Every one of those is held by a
    unit or launch test; **none of them is held by a run of the cell in which this failure
    occurred**, because no such run has been taken since. Until one is, this is still the
    failure this project has the most evidence for, and nobody may write that it is fixed.
  - **A real grasp could be reported empty; the predicate that did it was replaced on
    2026-09-01, and the replacement opens a region of its own.**
    **The arithmetic in this paragraph is about the superseded predicate** and is kept because
    it is what ADR-0052 is a record of and what both grasp campaigns measured. Until 2026-09-01
    `cite_skills::gripper_is_holding` required the reached width to
    exceed the **commanded** width by more than **twice** the linkage's own width tolerance at
    that drive angle. Recomputed from the L0 linkage dimensions for ADR-0045 and reproducing
    exactly: against a commanded 45.0 mm, a genuine 46.6 mm stall leaves 1.6 mm of margin
    against a 2.12 mm threshold, so `Pick` returned `EXECUTION_FAILED` with an empty-grasp
    description while the part was in the jaws. **That was arithmetic over the shipped
    constants, not an observed run** — no CI failure was ever attributed to it — and it was
    observed firing later, which is the paragraph below.
    `EXECUTION_FAILED` shares the `RETRY_SAME` branch with `TIMEOUT`, so it used to reach the
    same dead end as the item above by a different entrance — a second reason ADR-0046 refuses
    on custody rather than on a result code, and on the branch above that entrance is closed
    with the others: the misreported grasp still happened, and the station now escalates instead
    of dead-ending. **The record ADR-0045 says is owed exists**:
    [ADR-0052](docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), which states
    the defect as a **band** rather than as the 46.6 mm example and weighs six options. This
    bullet said "that record does not exist yet" until 2026-09-01.
    **It said the record chooses nothing until later that same day, and it now chooses.** The
    project owner took **option F on 2026-09-01** — judge the grasp against the part rather
    than against the commanded width — and the record is `Accepted`. The mechanism F is given,
    the answer
    for a facility handling more than one part, what the validator rule becomes, and the gate
    the implementing change has to pass are that record's amendment of that date. **Read it
    rather than taking a shape from here** — it decides a plan-level delivery and two new L0
    fields, and an exhaustive summary of a specification in a rulebook is a claim with an
    expiry date.
    **This bullet said until 2026-09-02 that "`Accepted` here means a decision and a
    specification and nothing else: no line of code, no threshold and no test moved, and the
    defect is exactly as live as it was." That is false, and it was already false about nine
    hours later, on the same day.** This file said "the day after it was written" until
    2026-09-03: the status sentence landed at `5a929c4`, 12:19, and the first implementing
    commit is `53f1d58` at 21:08, both on 2026-09-01 (`git log --date=iso`).
    Option F is implemented and on `main`, in five commits ending `d3eeac4` on
    2026-09-01: `53f1d58` declares the band and the work-piece interval in L0, `7a3e4d3` carries
    both into the generated bring-up plan, `3f6fe6f` replaces the predicate, and `f14d189` and
    `d3eeac4` are the tests — `git merge-base --is-ancestor <sha> main` succeeds for each.
    `cite_skills::gripper_is_holding` now takes a `WorkpieceWidths` argument and judges the
    **reached** width against the facility's declared work-piece interval, widened by a stall
    band at each edge; its own comment states that `report.commanded_width_m` is **deliberately
    not read**, so the quantity the defect was about has left the decision entirely
    (`workspace/src/cite_skills/src/gripper.cpp:142-161`).
    **The implementation landing promotes nothing.** ADR-0052 was already `Accepted` when the
    owner chose F and it is `Accepted` now; no status moved. Note that the record's own status
    block still says `cite_skills::gripper_is_holding` **is untouched**, which was true when it
    was written and is not now.
    **§A.10's gate is not fully met, and the campaign that ran it says so about itself.**
    [`docs/measurements/2026-09-02-option-f-regions/`](docs/measurements/2026-09-02-option-f-regions/ANALYSIS.md)
    — thresholds registered before the first trial, machine named, measured on the **implemented**
    predicate at `d3eeac4` — reports in its own §2.2 and §9 that item 2's second bullet is **not
    met here**: the gate asks for the false-positive flip bracketed to at least **0.05 mm**, that
    arm's stop grid is **2.00 mm**, and the flip is located only to (46.00, 48.00] mm at the
    narrow side. **Do not read "implemented" as "the gate cleared."**
    **A later campaign moved half of that gate and not the rest.**
    [`docs/measurements/2026-09-03-stall-band-flip/`](docs/measurements/2026-09-03-stall-band-flip/ANALYSIS.md)
    brackets the **narrow** edge of the implemented predicate's flip to the width §A.10 asks for.
    The **wide** edge is **not** bracketed, and what stopped it is an instrument failure rather
    than a measurement: one trial read the robot description back as zero characters and the
    validity rule's discard granularity took the whole block with it. **A null is not a
    clearance** — that campaign's own rule refuses to read its silence at that edge as agreement
    with the arithmetic or as validation of either band value. The gate is **still not cleared**;
    [`docs/open-work.md`](docs/open-work.md) #36 is where its clause-by-clause state is kept.
    **And that campaign REPRODUCED a region the new predicate opens.** A drive joint jammed
    part-way through an **opening** stroke, inside the window, on jaws opening onto nothing,
    reports `holding = true` on **9 of 9** valid in-window jams, where the superseded predicate
    reports `false` on all nine; the two controls outside the window are rejected, so the window
    is what decides. This is a direction ADR-0052 §A.3's specification **permits** — F drops the
    monotonicity term `reached > commanded` by design — and the measurement is what dropping it
    costs on that rig. **Whether that term returns is an open project-owner decision**, and the
    campaign registered before its first trial that it does not take it. Nothing here settles
    it; do not write as though it were settled.
    **Two things in that record change how the superseded account above should be read, and its
    figures are
    cited and not copied here (P1).** The 46.6 mm example describes a *declared work-piece*,
    and `default-grasp-width-never-closes` already refused that model at validate time; the
    doors that were open were a caller-supplied `grasp_width_m`, which nothing validated, and a
    stall landing short of the part's nominal width, which the cell does.
    **The caller door is closed by the same change.** `cite_skills::resolve_grasp_width` now
    refuses a requested *or* configured width — `GraspWidthSource::Refused`, rather than
    executing it and judging afterwards — whenever it lands within
    `gripper_discrimination_margin_m` of the narrowest declared part
    (`workspace/src/cite_skills/src/gripper.cpp:107-139`). **The second door is not a door into
    the same defect any more**, because F does not read the command at all; what it opens
    instead is the region the 2026-09-02 campaign reproduced, above.
    **This bullet said until 2026-09-01 that the defect has "never been observed firing". That
    is now false and the correction is the whole reason the decision could be taken.** The
    campaign the record's gate asked for has run —
    [`docs/measurements/2026-09-01-grasp-discrimination/`](docs/measurements/2026-09-01-grasp-discrimination/ANALYSIS.md),
    thresholds registered before the first trial, machine named — and it **observed** a real
    grasp reported empty, witnessed by the work-piece's own contact sensor, and separately
    **reproduced** a stall on nothing reported as a grasp. **Both directions fire.** It is
    still not a rate: one machine, one arm, one part, one timestep, and it took a commanded
    width above the ceiling the validator enforces. **Cite the campaign; its own write-up asks
    that its figures stay in its directory, and the four the decision rests on are quoted in
    ADR-0052 and nowhere else.** Its verdict on whether the stall distribution moves with the
    commanded width is **INCONCLUSIVE** by two of its own pre-registered rules, and ADR-0052
    §A.9 records that F's threshold may depend on the question that verdict leaves open.
  - **No vendor-described link's mass or inertia tensor is validated by anything, and this
    is the same structural blindness ADR-0028 just fixed for collision geometry.** The
    validator reads `description.body`; every vendor-described type leaves `body` unset; so
    the rule returns an empty list for exactly the links where the failure it names occurs.
    That is the shape ADR-0028 decision 4 closed for collision meshes by making L0 declare
    what the vendor does, and the identical hole is still open for inertia — which CLAUDE.md
    §10 names in the same breath as dense collision geometry, and which
    `model-validator` is documented as always checking. **Nothing is known to be wrong**: the
    2026-08-31 audit read all **27** vendor-described links itself and found **0** violations,
    one pass by one reader, not a check. What is missing is that nothing would notice if a
    vendor bump made one wrong. This is owed its own record and does not have one.
  - **The only environment-collision gate has an unmeasured edge.** Pilz does not search the
    scene, so `ValidateSolution` is the sole gate, and it checks trajectory waypoints while
    interpolating nothing between them. The sampling time is **0.1 s**, a C++ default argument
    with no ROS parameter exposing it. The smallest object in the generated planning scene is
    a **40 mm** break-beam housing, so a waypoint step exceeds it whenever the tool point moves
    faster than **0.40 m/s**. The arithmetic and the two ways the step can grow are ADR-0027's.
    **The residual has since been tested for, and the region was not exercised**:
    [`docs/measurements/2026-09-04-waypoint-clearance/`](docs/measurements/2026-09-04-waypoint-clearance/ANALYSIS.md)
    measured the per-waypoint tool-point step directly on the trajectories the shipped scenarios
    published, and **no interval anywhere carried both a large enough step and a close enough
    bracketing distance at the same time** — the cell moves fast where it is far from everything
    and creeps where it is close. **Its "no body passed between two checked waypoints" is refused
    as evidence by its own pre-registered rule and may not be read as a clearance.** The edge is
    still unmeasured; ADR-0027 carries a dated amendment of 2026-09-04 saying exactly that, and
    its status did not move.
  - **What the execution-side tolerances do under Gazebo is half measured, and the open half is
    the one a fault needs. This bullet said "nothing has measured" and "no following error has
    been sampled there" until 2026-09-04, and both clauses are now false.**
    [`docs/measurements/2026-09-04-following-error/`](docs/measurements/2026-09-04-following-error/ANALYSIS.md)
    sampled the controller's own following error on a real `gz_ros2_control` arm, under a
    registered rule that refuses a silence produced by an instrument that received nothing — so
    **the quiet is a measured quiet**, which the launch test against mock hardware could never
    have shown. **The path tolerance also fired**, on the concurrently loaded condition,
    attributed by the instrument's own naming to the arm under test's own controller.
    **What is still not established is the half that matters for a fault.** Those firings were
    **not induced**; nothing there shows the tolerance can *detect an obstruction* under this
    backend, and the campaign registered that half as out of scope before its first trial.
    Making it fire needs a Gazebo-side mechanism that obstructs an arm **link** while
    `gz_ros2_control` stays the loaded hardware component, which `cite_test_hardware`'s joint
    stop cannot supply — it is loaded *instead of* that plugin, not beside it. At full velocity
    scaling the healthy peak lands **above** ADR-0036's own order-of-magnitude line; that
    comparison, and the campaign's other figures, stay in that record's 2026-09-04 amendment and
    in the campaign directory (P1), and **ADR-0036's status did not move**. Its "revisit" section
    is **not** discharged either: the scenario sample it asks for is untaken, since that campaign
    drives L3 directly and runs neither `pick_and_place` nor `continuous_line`. **Never widen a
    tolerance to absorb any of this.**
  - **A grasp holds a position, not an orientation, and the two published residuals are
    different quantities.** Correcting the grasp-plane offset took rotations above 20° from
    60% to 0% of trials and left a residual —
    [`docs/measurements/2026-08-25-grasp-plane-offset/`](docs/measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md).
    **That residual, up to 18.7°, is a *roll* about the pad-to-pad axis, not a yaw.**
    Re-analysed on 2026-08-26 over 72 committed carries: every net carry rotation lies along
    the pad-to-pad axis, the component about the world vertical never exceeds 0.49°, and the
    trial that *is* the published 18.71° has a vertical component of 0.01°. **The yaw figure is
    10.62°**, from the conveyor-yaw campaign's twelve end-to-end trials. An angle without an
    axis is not a measurement of anything — do not put 18.7° into anything only a yaw can enter.
    The offset correction is in the tree, where the campaign said it belonged: L0's end-effector
    `linkage` block declares the vendor dimensions and the L3 skill server derives the offset
    from them. Per ADR-0029 a scenario may assert where a part ends up and **may not assert how
    it is held**.
    **A square part arriving yawed parks a few millimetres short**, because a leading-edge test
    makes the index position depend on yaw. That sensitivity is **real on hardware** — a
    physical photo-eye behaves the same way — and must not be described as a simulation artefact
    or compensated in the beam. Whether the residual accumulates over three stations is listed
    as **explicitly unmeasured** in
    [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md).
  - **L4 refuses a direct arm-to-arm handoff, and the residual is no longer the stated reason.**
    ADR-0031 was corrected on 2026-08-26: nothing re-observes the part, and what makes the
    *permitted* conveyor edge safe is the receiving gripper closing on a free part — which a
    direct handoff denies. Read that ADR's correction before writing about either case. The
    refusal string in `line_plan.hpp` still carries the pre-correction reasoning.
  - **`Transfer` has a server and no caller.** Today's L0 topology is conveyor-mediated and L4
    refuses a direct arm-to-arm edge at plan time (ADR-0031).
  - **L4's own tests move no arm.** `line_orchestrator` derives one subtree per station from
    `LineTopology` and owns handoff, recovery, the fault branch and `LineState`; its unit and
    launch tests use fake action servers that succeed because they are told to, so what they
    prove is **sequence, ownership and the stop**, not motion. Motion is evidenced only by the
    scenarios.
  - **The belts are commanded open-loop.** `ConveyorState` exists in `cite_interfaces` to make
    commanded and measured speed disagree visibly, and **nothing publishes it**; the bridge
    carries a bare `std_msgs/Float64` each way. So `StopAll` states an intent it cannot confirm,
    and a belt that fails to stop, or fails to restart, is a spilling or a stalled line that
    nothing notices. **This is the gap that hid the delivery defect above for ten commits**:
    with no confirmation path, "commanded" and "running" were indistinguishable from inside the
    system. A publisher of `ConveyorState` — in the simulation plugin and on the hardware drive,
    which is L1/L2 work — is what closes it.
  - **Scenarios are not deterministic.** `CITE_PHYSICS_SEED` still reaches only
    `gz sim --seed`, which seeds sensor noise and **not the physics solver**. What changed is
    which part is stochastic: planning is no longer it wherever Pilz answers, and physics still
    is. The OMPL fallback remains unseeded and unseedable. See
    `docs/architecture/cross-cutting-testing.md` and ADR-0027 before writing anything about
    determinism, and do not upgrade the claim on the strength of the planner alone.
  - **Twelve links per arm collided against their visual mesh until 2026-09-01. They now
    collide against derived convex hulls, and what is open is the residuals promotion did
    not close.** §10 below names the defect class. **Do not state how many residuals there are
    here** — this bullet said "three" for one day and the list it pointed at had four, dropping
    the narrow-part case that the new validator rule exists for; read ADR-0028's amendment of
    2026-09-01 and its "Residuals recorded 2026-08-31" section, which is where they are kept.
    **The shipped selection is
    `convex_hull`** — `grep -n "select:" model/assets/types/robots/xarm5.yaml` is the
    instrument, and `./scripts/validate-model` exits 0 on it, reporting the model valid.
    Selecting the vendor's meshes is now an **ERROR** in
    `cite_tools.validate.physical._vendor_collision_is_declared` rather than the WARNING it was
    from 2026-08-31; `--strict` no longer changes that answer.
    **This bullet said until 2026-09-01 that ADR-0028's gate "requires the friction-grasp
    campaign re-run against hull geometry first, and that campaign has not been run", and
    described the shipped default as the vendor's meshes. Both are now false.**
    **ADR-0028 is `Accepted` as of 2026-09-01, and it was promoted on a campaign whose verdict
    was INCONCLUSIVE. Do not read the promotion as a clean grasp result.** The campaign is
    [`docs/measurements/2026-09-01-hull-grasp/`](docs/measurements/2026-09-01-hull-grasp/ANALYSIS.md)
    — 47 trials, thresholds registered before the first trial, machine named — and its own
    pre-registered rule S fired: the mechanism the three instruments were chosen to detect
    **does not occur**, so the campaign has not tested the prediction and its silence about the
    grasp may not be read as "no change". **The campaign's figures are cited and not copied
    (P1); read it rather than taking a number from here, and never write that hulls grasp
    better — every outcome difference it measured is below the effect size it registered in
    advance, in either direction, and the honest statement is "no distinguishable difference at
    this n".**
    **Promotion rests on a restated clause, not on that null.** ADR-0028's clause 2 as written
    asked for the consequences of the non-occurring mechanism and could not be met by any
    campaign; [ADR-0051](docs/adr/0051-restate-the-hull-grasp-gate.md) **restates it rather
    than relaxing it** — the same route ADR-0049 took with ADR-0043's half 2 — and is
    `Accepted` on the project owner's ratification of that wording. What carries the clause's
    2c is a **geometric** clearance argument computed twice by instruments that share nothing,
    agreeing to 0.01 mm. Read ADR-0028's amendment of 2026-09-01 for all four sub-clauses with
    the strength of each; it is not restated here.
    **The evidence is bounded to a work-piece no narrower than 50.0 mm — the width the
    2026-09-01 campaign ran at — and the bound is enforced rather than written down.** Say it
    that way and not as "this cell's 50 mm cube": today's L0 cube is 50 mm too, and **those are
    two quantities that agree by coincidence**. The code keeps them apart on purpose, because a
    range derived from L0 would make the check `narrowest >= narrowest`, which cannot fail.
    A narrower part closes the jaws further and has never been tested against a
    derived set, so `_derived_collision_is_within_its_measured_range` in the same validator
    **fails** a model that binds a derived set while declaring one — declaring a narrow part is
    the act ADR-0051 says reopens clause 2, and this rule is the only thing that will say so.
    **The rule has a stated edge and one remaining silence, and this file asserted the
    enforcement without either until 2026-09-01.** A work-piece whose width L0 cannot compute —
    a **mesh** part — is its own ERROR since that date (`derived-collision-range-unstated`);
    before it, changing the cube to a mesh switched the range rule *and*
    `default-grasp-width-never-closes` off in one line with no finding at all. What stays
    silent is a facility that declares **no work-piece whatsoever**: the derived set then ships
    against a width nobody has stated, and the rule's own docstring records that as a gap
    rather than as coverage. **Selecting the vendor's meshes is legal wherever that rule
    fires** — it has to be, or a narrow part would have no valid collision selection at all,
    which is the state this branch shipped for one day.
    **Residuals are open and `Accepted` closes none of them**, all in ADR-0028's amendment and
    residuals section with their figures — do not count them here: the generated SRDF still
    invokes the **vendor's** self-collision matrix, computed against vendor geometry, and the
    mismatch is now **declared in L0 and held by a validator rule** in ADR-0028 decision 4's
    shape rather than checked — declaring is not fixing, and the rule verifies no figure in the
    declaration; `end_tool` is the one link where the hull trades
    fidelity for a negligible share of the saving; one campaign metric — the jaws stalling
    marginally earlier on hulls — was DETECTED, is a **control**, and is **unexplained**; the
    **narrow-part case is untested**, which is what the validator rule above refuses rather
    than fixes; and four pipeline gates prove less than they appear to. **Half of the
    CPU-architecture residual is retired and half is not**: CI run `33479867459` on `main`
    reports `ok 1 set(s), 13 mesh(es) match the vendor` on ubuntu-24.04, so the committed hulls
    re-derive byte-identically on x86_64 — that is the *derivation*, and it says nothing about
    the shipped *selection*, which **seven** CI runs have since brought a cell up on — the
    seven the paragraphs below name and enumerate. It said "no CI run" until
    2026-09-01, "**one** CI run" until 2026-09-07 and "**four**" until 2026-09-08.
    **That "four" was stale for most of a day against this file's own paragraphs**, and finding
    it is the reason the list now lives in one place. `987e6b6` moved the enumeration below to
    five runs on 2026-09-08 and left **two** other statements of the count at four: this
    sentence, and the capitalised one below. **This sentence carries the count and no list from
    here on** — the enumeration is below and nowhere else — because two lists of the same runs
    is the duplication P1 forbids and is exactly how they came apart.
    Every figure behind
    the grasp clause is **one machine, one arm, one part, one `max_step_size`**, and Phase 3's
    physics retune reopens it.
    **A HULL ADDS NO CLEARANCE, AND THE OPPOSITE IS THE NATURAL INFERENCE FROM EVERYTHING
    ABOVE.** Over 20,000 random directions on all thirteen hulls the hull's support function
    exceeds its source's by **+0.000000 mm** — every gram of added material is inside a
    concavity. So **ADR-0027's sampling residual is untouched** (a tool point above 0.40 m/s
    still steps past a 40 mm beam housing; tunnelling is an approach from outside), and **hulls
    may never be cited as margin in a safety case.**
    **One hull property is load-bearing on a setting nothing here sets, and the generator now
    refuses the combination.** Under hulls the gripper linkage interpenetrates in **every**
    sampled configuration where the vendor geometry keeps 1.57 mm, and SDFormat's
    `<self_collide>` default of `false` is the only thing making that inert. Enabling it — an
    ordinary fidelity improvement — would stall the drive joint at spawn and report every grasp
    empty **on the simulated side only**, which is a **P2 divergence with the simulation as the
    broken half**. The interpenetration is measured and exhaustive over the sampled stroke; the
    consequence is **reasoned from SDFormat's documented semantics and has not been observed on
    a running cell**, and may not be written up as though it had.
    **MOST SCENARIO AND CI FIGURES IN THIS SECTION WERE MEASURED WITH VENDOR GEOMETRY; SEVEN
    CI RUNS WERE MEASURED WITH HULLS.** This file said **"NO SCENARIO OR CI FIGURE ANYWHERE IN
    THIS SECTION WAS MEASURED WITH HULLS"** and **"no CI run has ever brought this cell up
    against the hulls"** until 2026-09-01, in capitals, and the second clause was false when
    the first re-audit published it; it then said **"EXACTLY ONE CI RUN WAS"** until
    2026-09-07, and that expired within seconds of being written and stood for five days
    before anyone re-read it; **"FOUR"** until 2026-09-08 and **"FIVE"** for part of that day.
    **That is four falsifications of one sentence** — none, one, four, five — and the count is
    the only part of it that has ever been wrong.
    **What stays true, and it is most of the sentence.** `bringup`'s first 36 of 50, every
    `pick_and_place` run before `e51238e`, the first eighteen rows of the `continuous_line`
    table and the whole teardown-family split were all taken with **vendor** collision
    geometry. Read them as evidence about the cell that was.
    **What is false, and by how much.** Seven CI runs on `main` have brought this cell up
    against the hulls: **`33501707588`** at **`e51238e`**, **`33575992281`** at **`4ef2d7c`**,
    **`33603610958`** at **`51195e0`**, **`34085965578`** at **`f6a3779`**,
    **`34247027502`** at **`13bc8e9`**, **`34258470163`** at **`e18251e`** and
    **`34280056331`** at **`aed36c4`**. That they are
    hull runs is established rather than assumed: `git merge-base --is-ancestor dd93488 <sha>`
    succeeds for each and `git show <sha>:model/assets/types/robots/xarm5.yaml | grep select:`
    reads `select: convex_hull` for each — re-derived over the last two on 2026-09-08, the five
    above them having been re-derived the same way earlier that day. Verdicts
    were read from the logs, never from the step
    conclusion, by the instrument this section mandates.
    **What those seven runs show, scenario by scenario, and `pick_and_place` now needs two
    figures where it needed one.** `pick_and_place`'s **cycle** passed in all seven, and in all
    twenty-five tabled
    runs; its **teardown** was clean in six of the seven, failing at `e18251e` on `gz-1 exited
    with -9`. That split is the `pick_and_place` bullet above and is not restated here.
    `bringup`'s cycle passed in all fourteen invocations, and three of the fourteen failed their
    teardown, at `f6a3779` on a `parameter_bridge` -11, at `13bc8e9` on a -6 and at `e18251e` on
    a `gz-1` -9 — the
    teardown-family bullet above is
    where all three are kept. `continuous_line` **passed in four of the seven and failed in
    three**; two of the three failures are the third signature recorded in that bullet and the
    third is the spawn signature's second occurrence.
    **What the seven runs are not.** **Seven runs**, at seven commits, on runners nobody
    prepared,
    with **no thresholds registered in advance. It is not a rate**, and three of the seven
    contain a `continuous_line` failure. This paragraph counted four runs until 2026-09-08 and
    five for part of that day.
    They say **nothing about the grasp** — the 2026-09-01
    hull-grasp campaign's verdict is INCONCLUSIVE by its own pre-registered rule S and these
    runs do not touch it — and **nothing about capacity**, which is the separate case below.
    **Why the "no CI run" clause survived to be falsified twice, because that is the lesson.**
    The runs at `dd93488` and `d6db73b` — the hull promotion and the commit after it — were
    both **cancelled**; `e51238e`'s run completed *after* the re-audit that wrote the first
    sentence, so the window in which anyone could have noticed was **one run wide**. The
    replacement sentence was falsified by **the CI run of the very commit that wrote it**:
    `git log --date=iso -S "EXACTLY ONE" -- CLAUDE.md` puts it at `4ef2d7c`, committed
    2026-09-02T00:35:51Z, and `gh run list` puts `33575992281` — the hull run of that same
    commit — at 2026-09-02T00:36:00Z, **nine seconds later**. It then stood in this file for
    five days. A sentence about what CI has never done expires the moment CI runs again, and
    twice now nothing re-read it; the second time, the push that wrote the sentence was itself
    the thing that expired it.
    **The count that replaced it has now expired twice more, and the second time repeats the
    lesson to the minute.** "FOUR" was written at `13bc8e9`, and that commit's own CI run
    `34247027502` was itself the fifth hull run. "FIVE" was written at `987e6b6`, committed
    2026-09-08T17:20:18Z, and `34258470163` at `e18251e` — the sixth — was created at
    2026-09-08T17:39:58Z, **under twenty minutes later** (`git log --date=iso` and
    `gh run list --branch main --json createdAt`, both read 2026-09-08). That is the same shape
    as the nine-second falsification above.
    **What was different in the days between is why nobody caught it:** the three commits after
    `13bc8e9` could not open a CI log at all, because `gh` on this host was unauthenticated.
    **An instrument you cannot run is a claim you cannot keep**, and this paragraph is where
    that shows first.
    **The standing instruction is unchanged and is not retired by this run:
    do not widen any ceiling to absorb whatever CI shows next**; a ceiling widened to fit a
    geometry change is a measurement thrown away.
    **The capacity case is separate and was never grasp evidence.** Measured as capacity with
    the world's throttle lifted by
    [`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](docs/measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
    — 24 trials, thresholds registered before the first trial, machine named — the same lever on
    the same machine **clears the 1.0 floor with hulls and misses it with vendor meshes**. Cite
    it; the figures are not copied here. **It does not show a requirement passing:** ADR-0049
    sets no capacity margin above 1.0, every capacity figure it reports is a **lower bound**
    because its host could not be made quiet, and one of its validity rules was found to read
    the container VM's load rather than the host's and was applied literally anyway, excluding
    4 of 24 trials with the unexcluded medians larger in every case. **This file carried a
    verdict read off the wrong quantity until 2026-09-01** — *"hulls move a pair materially and
    still do not reach the 1.0 ADR-0043 requires"* — taken with the world's throttle in force,
    under which a measured real-time factor is **capped at 1.0 by construction**
    ([ADR-0049](docs/adr/0049-measure-the-real-time-floor-as-capacity.md)).
    **Two earlier lessons this bullet keeps.** ADR-0028 said in four places that a hull
    *"fills the space between the fingers"*; it does not, because each link is hulled
    separately, and **that sentence was the hypothesis the gate's measurement would have been
    designed against**. Its replacement — inclined wedges contacting the part at each pad's
    relief step — was derived the same way from the same static audit at a **commanded**
    aperture the gripper never occupies, and **is wrong too**: the wedges sit behind the pad
    plane on the same rigid link. Two mechanisms, both stated as fact, both falsified by
    measurement. **An audit taken at a commanded value must state whether the machine ever
    reaches that value, and a promotion gate must not be written against a mechanism nothing
    has observed.**
- **The layout is `PROVISIONAL`.** The coordinates in `model/` are engineered, not surveyed.
  Charter §8 puts the physical scan in Phase 3; until then a measurement taken from this model
  does not transfer to the building, and no report should imply that it does.
- **The documentation is written, and its status markers are the thing to read.** Each document
  in `docs/architecture/` and `docs/interfaces/` carries `DESIGNED`, `PARTIAL` or `BUILT`, with
  the evidence named. `DESIGNED` means the contract the code must satisfy; `PARTIAL` says which
  part is real and which is not. Read the layer document before touching a layer, and read its
  status line before believing its body.
- **Measured evidence lives in [`docs/measurements/`](docs/measurements/README.md)**, one
  directory per campaign, each with its thresholds written down before the first trial. This is
  what P8 looks like in practice. Cite a campaign; do not copy its numbers around. **A campaign
  whose answer is "inconclusive" is published too** — the teardown one is, and its rule refused
  a clean arm as evidence rather than banking it.
- **Where Phase 1's exit criterion stands, and nothing above changes it.** **The clause-by-clause
  record is charter §8 and is not copied here** (P1) — it states which evidence closed which
  clause, at what strength, and what the closure does not cover. What belongs in a rulebook is
  the part that changes how you read everything else in this section:
  - **The criterion is MET as of 2026-08-28 and that is not a green light.** It closed on CI run
    `33158091922`, one run, no thresholds registered in advance, at commit `60eb4a5`. **Inside
    that green run the advisory `continuous_line` step failed** — 1 of 3 work-pieces, a station
    stopped while `LineState` still read healthy. That silence is the blind spot ADR-0039
    records at that station. **What stopped the piece was not established when the clause
    closed and has been established since** — the gripper-result timeout and the retry that
    carried the part off its own trigger, ADR-0045 and ADR-0046, at the strength the
    `continuous_line` bullet above states. Nothing about that changes the closure: it was
    closed on evidence that did not include a cause, and knowing the cause does not add a run.
    **One attribution names the right dead end by the wrong door and must not be repeated as
    it stands.** Charter §8 reads that run as consistent with the *failed-grasp* dead end
    ADR-0038 records. It is that dead end, and it is not the failed grasp: the run's own
    milestone ladder puts the piece past `lifted(station_transfer_1:
    cell_a__table_pick__surface)` and leaves it in the air at `(-0.001, 0.273, 1.201)` for the
    rest of the leg, so the grasp held, and ADR-0038's 2026-08-29 amendment records the second
    door it went through instead. The charter is protected and still carries that sentence;
    treat the ladder and the two records as the record.
    A workflow whose conclusion is `success` is therefore not a statement that every scenario
    passed. **Never cite "CI is green" as evidence that a capability works; cite the step that
    gates it** — and note that **the step's own conclusion is not the step's result either**:
    GitHub reports a `continue-on-error` step as `success` when it failed, so the log is the
    only instrument. See the table in the `continuous_line` bullet, where **seven of
    twenty-five**
    CI runs failed the cycle, in **three** distinct signatures — three of them in the same way,
    **two** on a spawn timeout, and two that escalated and stopped the line. It said "four of
    nineteen … three of them in the same way and the fourth on a different signature entirely"
    until 2026-09-07 and "six of twenty-three … one on a spawn timeout" until 2026-09-08.
    **`34258470163` at `e18251e` is a fresh demonstration of the trap this paragraph names**:
    its workflow conclusion is `success` and its `continuous_line` failed.
  - **The clean-clone walk of 2026-08-27 demonstrated clone-to-green, not a running line.** It
    ran `doctor` (23 passed, 0 failed), `build` (19 packages, before `cite_runtime` existed),
    `test` and `lint`, all clean, from a fresh clone of the remote with zero deviations — and
    **stopped at `lint` without launching the cell**. The clone-to-running-cell half is
    evidenced by the CI runs above, each of which brought the cell up twice from a checkout —
    `bringup`'s cycle has passed **50 of 50** across the twenty-five, with its teardown clean
    in
    **47** of those 50 — and by nothing else. It said "38 of 38 across the nineteen" until
    2026-09-07, when no teardown figure was stated separately because none had yet failed,
    "44 of 44 … 43" until 2026-09-08 and "46 of 46 … 44" for part of that day.
  - **The cycle clause is the least-settled of them.** **Seven** CI failures are now part of
    its
    record, not one: three stopped the same piece at the same milestone, **two** timed out
    spawning a work-piece, and two escalated and stopped the line. It said "four" until
    2026-09-07 and "six" until 2026-09-08.
    **Eighteen CI runs have passed the cycle since the clause closed, and that does not settle
    it** — it was closed on one run with no thresholds registered in advance, and a longer
    unregistered tally is a longer unregistered tally. **The figure here read "thirteen more
    CI runs have passed the cycle since 2026-08-29" until 2026-09-07, and it reconciled with
    no reading of the table that could be derived on that date**: counting the table's `passed`
    rows dated 2026-08-29 or later gave 15 and counting those strictly later gave 12, neither
    of them 13. The seventeen above is every `passed` row in the table, which is the whole of it
    since the closure run `33158091922` is the table's first row and it failed; it read
    "sixteen" until 2026-09-08 and "seventeen" for part of that day. See
    the `continuous_line` bullet above, including that a
    harness had been starting the belts and that the best local figure is a single run.
  - **"Every architectural decision is written down" is the one clause the charter records as
    unclosable as stated**, and the counting is the reproducible part. `./scripts/doctor`'s
    `ADR index` line reported **54 records, all indexed** in this checkout on 2026-09-10 at
    `523ffd9`. It read 53 on 2026-09-08 at `6d51966`, 52 on 2026-09-01 at
    `abdae38` and **still 52 when re-run on 2026-09-08 at `df91154`** — that branch amended
    existing records and added none, which `git diff --diff-filter=A --name-only
    e18251e..df91154` confirms by listing no file under `docs/adr/`. It said 51 earlier on
    2026-09-01, 48 on 2026-08-30, 46 the day before that, 43
    earlier that day, and 40 before that —
    the newest being
    [ADR-0054](docs/adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md) — the hardware
    opt-in keyed on a declared fact rather than on a backend's name, **`Proposed (corrected
    2026-09-10)` and not promoted**, for the clause-10 reason its own status block gives —
    with
    [ADR-0053](docs/adr/0053-index-hardware-params-by-backend.md),
    [ADR-0049](docs/adr/0049-measure-the-real-time-floor-as-capacity.md),
    [ADR-0050](docs/adr/0050-what-crosses-the-twin-boundary.md),
    [ADR-0051](docs/adr/0051-restate-the-hull-grasp-gate.md) and
    [ADR-0052](docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) before it.
    **This file named
    ADR-0051 as the newest while ADR-0052 was already on disk**, which is the drift the
    paragraph's own closing instruction exists to catch.
    **`ls docs/adr/[0-9]*.md` returns exactly one more than `doctor` does**, because the glob
    also matches `0000-template.md`; it read **55** on 2026-09-10 at `523ffd9` against
    `doctor`'s 54, **54** on 2026-09-08 at `6d51966` against
    `doctor`'s 53, and **53** on 2026-09-01 at `abdae38` against
    `doctor`'s 52, so the
    relation has held at every re-audit — as it did at 52 against 51 earlier on 2026-09-01.
    Both numbers are
    right and
    they count different things, so name the command with the number. **This figure moves
    every time a decision is recorded, which is often — run `doctor` rather than quoting the
    number here.** The breakdown of corrected,
    amended and superseded records is the table in
    [`docs/adr/README.md`](docs/adr/README.md) and is deliberately not copied here — `doctor`
    does not count those. `doctor` enforces that every ADR on disk is indexed and that every ADR
    referenced from `docs/` exists; it does **not** check that the set is *complete*, and no check
    can. That clause is a judgement, not a measurement.

State this honestly in reports. Never claim a capability exists because the charter
describes it.

## 3. Hard rules

Violating any of these is a defect, regardless of how well the code otherwise works.
Charter §4 carries the full reasoning.

- **P1 — One source of truth.** The facility is described once, declaratively, in the L0
  model. Worlds, descriptions, controller configs, and launch graphs are *generated* from
  it. A value must never exist in two places.
- **P2 — Sim and real are interchangeable.** Code that commands the simulated cell
  commands the physical cell unmodified. Topic, action, controller, joint, and frame names
  are identical; only the loaded `ros2_control` hardware plugin differs. Breaking this is
  the highest-severity defect in the project.
- **P3 — Typed contracts, always.** Every interface is a versioned `.msg`/`.srv`/`.action`
  in an interface package. If a consumer cannot discover the shape with
  `ros2 interface show`, the interface does not exist.
- **P4 — Determinism over timing.** Startup, shutdown, and mode transitions are driven by
  lifecycle states and events. Never by sleeping for a guessed duration.
- **P5 — Configuration is data, code is mechanism.** Code encodes *how* things work, never
  *which* things exist.
- **P6 — Nothing is done until tested and reproducible.** Every capability ships with
  automated tests that run headlessly in CI.
- **P7 — Honest status.** Documentation states what the system does, not what was
  intended. A checkbox is ticked only when a test proves it.
- **P8 — The twin measures itself.** Any fidelity claim is backed by a published metric.
- **P9 — Plug in, plug out.** Robot types, end-effectors, sensors, and process modules are
  replaceable at their interface boundary. A new robot type must not touch orchestration.
- **P10 — Everything in English.** Code, comments, identifiers, configuration, commit
  messages, documentation, and agent reports. No exceptions.

## 4. Standing prohibitions — rejected in review, without discussion

- Hand-edited generated artifacts (world files, controller configs, launch graphs).
- `std_msgs/String` carrying structured data.
- `TimerAction` or `sleep` used to sequence startup.
- Third-party source copied into the tree instead of pinned in the vcs manifest.
- A capability marked complete in documentation without a test proving it.
- Any identifier, comment, or document not in English.
- A value that exists in two places.

## 5. Layer stack

```
L7 PRESENTATION        operator HMI, remote access                    (Phase 4)
L6 DATA & TELEMETRY    telemetry schema, recording, historian, replay (Phase 4)
L5 TWIN SYNC           mode control, mirroring, divergence metrics    (Phase 2)
L4 ORCHESTRATION       behaviour trees, line coordination, handoff
L3 CAPABILITY          MoveTo / Pick / Place / Transfer / Grasp / Detect
L2 CONTROL & HAL       ros2_control, controllers, MoveIt 2, hw interfaces
L1 DESCRIPTION         URDF/Xacro, SDF, meshes, generated worlds
L0 FACILITY MODEL      the single declarative source of truth
```

**A layer may depend only on layers below it.** An upward dependency is an architectural
defect and an `ESCALATE`, not a finding.

Each layer has a design document in [`docs/architecture/`](docs/architecture/README.md) —
[L0](docs/architecture/L0-facility-model.md),
[L1](docs/architecture/L1-description-and-assets.md),
[L2](docs/architecture/L2-control-and-hal.md),
[L3](docs/architecture/L3-capabilities.md),
[L4](docs/architecture/L4-orchestration.md),
[L5](docs/architecture/L5-twin-synchronization.md),
[L6](docs/architecture/L6-data-and-telemetry.md),
[L7](docs/architecture/L7-presentation.md).

Cross-cutting: [safety and interlocks](docs/architecture/cross-cutting-safety.md),
[lifecycle management](docs/architecture/cross-cutting-lifecycle.md),
[testing](docs/architecture/cross-cutting-testing.md),
[naming](docs/architecture/naming-and-namespaces.md), diagnostics, configuration, CI/CD,
security.

The architecture is aligned with the ISO 23247 reference architecture for manufacturing
digital twins — see [standards-alignment.md](docs/architecture/standards-alignment.md).

## 6. Technology baseline

Every row below has an ADR recording why it was chosen and what it costs — see
[`docs/adr/`](docs/adr/README.md). Changing any of them requires a new ADR.

| Concern | Choice |
|---|---|
| OS | Ubuntu 24.04 LTS (Noble) |
| Middleware | ROS 2 Jazzy Jalisco |
| Simulator | Gazebo Harmonic (LTS) — **not** Gazebo Classic, which is EOL |
| ROS↔Sim | `ros_gz_sim`, `ros_gz_bridge` |
| Control | `ros2_control` + `gz_ros2_control` |
| Motion planning | MoveIt 2 |
| Orchestration | BehaviorTree.CPP v4 + Groot2 |
| Robot support | `xarm_ros2`, pinned via manifest, local changes as patch files |
| Recording | `rosbag2` with MCAP storage |
| Visualization | RViz 2 (native debug), Foxglove (shareable) |
| Dependencies | `vcstool` manifest + `rosdep` — never vendored into the tree |
| Environment | Docker + devcontainer |
| Languages | C++ for real-time and control paths; Python for orchestration, tooling, generators |

## 7. Commands

Fixed entry points. Always invoke these rather than the underlying tool, so that changes
to the toolchain do not ripple through agent configurations and documentation.

| Command | Purpose |
|---|---|
| `./scripts/bootstrap` | Prepare or repair the environment. Idempotent. `--host-only` skips everything needing ROS. |
| `./scripts/doctor` | Diagnose the environment. Run first when something is wrong. |
| `./scripts/build` | Build the workspace |
| `./scripts/test` | Host tooling tests, then unit + integration + launch tests |
| `./scripts/lint` | Linters and type checks |
| `./scripts/format` | Apply formatting in place |
| `./scripts/sim [--headless] [--pair]` | Launch the simulated cell. `--pair` brings both sides of a twin pair up under the pair supervisor, implies `--headless`, and requires an L0 model that declares `twin: {sides: pair}` |
| `./scripts/validate-model` | L0 schema validation + generator dry-run. Runs anywhere. |
| `./scripts/hulls [--write]` | Check, or re-derive, the convex-hull collision meshes L0 declares (ADR-0028). Needs the imported vendor source, so unlike `validate-model` it does not run anywhere. |
| `./scripts/audit-deps` | Scan dependencies for known vulnerabilities. Read its header — it does not cover every layer. |
| `./scripts/scenario [name]` | Headless simulation-in-the-loop scenario; no argument lists them |
| `./scripts/enter [dev\|gui\|hardware] [command...]` | Interactive shell in the container; with a trailing command, runs it there and exits |
| `./scripts/fetch-assets` | Download large assets declared in `assets/manifest.yaml` |
| `./scripts/clean [--all]` | Remove build artifacts |

Quality gate before any handoff: `./scripts/lint && ./scripts/build && ./scripts/test`.

**Always invoke these rather than `colcon`, `docker`, or `ros2 launch` directly.** They
route to the right environment automatically: on a machine without ROS they re-execute
themselves inside the container, so the same command works from a macOS laptop and from
the Linux workstation. A command written directly against `colcon` works for its author
and for nobody else.

Dependencies are declared in four layers, each with exactly one correct home — see
`requirements/README.md`. In short: ROS and system packages in `package.xml` resolved by
`rosdep`; external ROS source pinned in `external/cite.repos`; host Python tooling in
`requirements/tools.txt`. Never install a ROS Python dependency with `pip`.

## 8. Naming

```
/cite/<zone>/<asset_id>/<interface>
```

Deterministic, generated from the L0 model, identical in simulation and on hardware.
Frame identifiers follow the same rule. No asset name is ever written by hand twice.

## 9. Definition of Done

A capability is done only when **all** hold. There is no partial credit.

1. Generated from or declared in the L0 model where applicable.
2. Interfaces are typed and live in an interface package.
3. Tested at the right level — unit, integration (`launch_testing`), simulation-in-the-loop
   scenario, and interface-contract regression — and passing in CI.
4. Runs headlessly in CI on a clean container with no manual step.
5. Works identically in simulation and on hardware, or its hardware path is explicitly
   marked unimplemented.
6. Documented: what it does, its interfaces, how to run it, how it fails.
7. Reviewed by a human and by the relevant review agents.
8. Startup and shutdown are event-driven, containing no timing guesses.

## 10. ROS 2 practice notes

Recurring failure classes in this domain. Treat each as a review checkpoint.

- **QoS**: declare profiles explicitly. Incompatible publisher/subscriber QoS connects
  silently and delivers nothing — the most common silent failure in ROS 2. **Compatible QoS
  is not delivery either:** reliable is a promise to *matched* subscribers, so anything
  published in the same callback that created the publisher reaches nobody. That cost this
  project a belt setpoint that was never once delivered. Treat a match as an event, never a
  sleep or a publish loop — see
  [`docs/interfaces/qos-profiles.md`](docs/interfaces/qos-profiles.md).
- **Gazebo transport is a second namespace, and `ROS_DOMAIN_ID` does not touch it.** Every
  process that speaks it — `gz sim`, `parameter_bridge`, `ros_gz_sim create`, every `gz`
  probe — must carry the `GZ_PARTITION` the generated plan names, and one that does not
  discovers a world that is not there. It does not fail loudly: `gz model --list` against no
  world **exits 0**. Start such a process through `cite_bringup/gz.py` and nothing else; a
  guard under `tests/scenarios/guards/` enforces that for `tests/`. ADR-0042 has the decision
  and its correction.
- **Lifecycle**: use managed nodes. They are what makes P4 achievable.
- **Executors and callback groups**: never block inside a callback; choose the callback
  group deliberately, or you will deadlock under load.
- **Time**: honour `use_sim_time` consistently. A mixed-time system produces plausible,
  wrong results.
- **TF**: one publisher per transform; watch for extrapolation errors at startup.
- **Actions**: implement cancellation and preemption paths, not just the happy path.
- **Inertia and collision geometry**: wrong inertia tensors and dense visual meshes reused
  as collision geometry make a simulation run confidently and wrongly. Always validated by
  `model-validator`.

## 11. Agents

Subagent roles live in `.claude/agents/`. The pipeline and dispatch routing are defined in
**`.claude/orchestration.md`** — read it before delegating.

`.claude/` is local tooling and **is not committed**, so a fresh clone will not contain it.
This file is committed, which is the point: the rules below bind every contributor whether
or not they have the agents.

- **The pipeline is how work is done here, not an option.** An orchestrator writes the task
  spec, `coder` implements, the routed reviewers fan out in parallel, `tester` verifies, and
  `fixer` remediates. Doing the coder's work in the orchestrator conversation skips review
  and test as separate roles, which is exactly what rule 6 in `.claude/orchestration.md`
  forbids — "the coder never self-certifies".
- **A session instruction that conflicts with this is an `ESCALATE`.** If the tooling a
  contributor is running tells them not to delegate, that contradicts this file, and this
  file is the rulebook. Say so and ask; do not quietly pick a side. This happened on
  2026-08-24 and cost a whole phase's worth of work its review.
- Agents propose; humans and tests decide. Nothing merges without review and green CI.
- Agents are bound by this file. Output contradicting §3 or §4 is a defect.
- Reports are written in **English**, with a `Status:` verdict line first, summarized
  evidence, and never a full log dump.
- A conflict with a locked decision is `ESCALATE` — returned to the user, never
  self-resolved.

## 12. Change control

- **`what-we-are-doing.md` is protected.** It changes only by explicit user decision, with
  a version bump and a §14 entry. Never edit it as a side effect of other work.
- **ADRs** ([`docs/adr/`](docs/adr/README.md)) record every significant technical
  decision, written *before* implementation. Use
  [`0000-template.md`](docs/adr/0000-template.md).
- **Commits and PRs** describe intent and reference the ADR or phase item they serve.
