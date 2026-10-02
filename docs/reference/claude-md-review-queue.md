# CLAUDE.md review queue

On 2026-10-01 `CLAUDE.md` was cut back to what the project is, what it is aiming for and the
working discipline. Section 2, "Current state", had grown to about 2,800 lines, most of it count
histories and measurement records. **Nothing was deleted.** Every line of the old section 2,
and every dated clause cut from section 7's table, went to exactly one of three places:

- **a snapshot's `MEASUREMENTS.md`**, when the measurement's subject has left the main tree —
  the three-arm line, `cell_a`, `pick_and_place`, `continuous_line`, the fixed program. Those
  files are reached through [`projects/README.md`](../../projects/README.md);
- **this queue**, for everything else: repository count histories, lessons, and main-tree
  status detail too long for the new section 2;
- **the new section 2**, which keeps one sentence of the old text verbatim and otherwise
  states the current state in its own words.

The old text is also `git show 960e6b4:CLAUDE.md`. Line numbers below refer to that file.

**This queue is the project owner's to work through, item by item. Nothing in it has been
resolved.** Each item carries a recommendation; a recommendation is a proposal, not a decision.
Do not act on an item without the owner's decision, and do not add new items here: this is a
one-off record of one cleanup, not a place for new content. (Q86-Q91 belong to the same
cleanup: they are main-tree counts and findings first placed in a snapshot's
`MEASUREMENTS.md` and moved here after review the same day.)

## Classes

| Class | Meaning |
|---|---|
| C | A repository count and its history (packages, tests, files, ADRs, assets). The current value is one command away. |
| D | A lesson or rule that is not specific to a milestone. Candidate for a rule in `CLAUDE.md`, a line in another document, or deletion. |
| B+ | A main-tree fact in more detail than the new section 2 carries. Usually already held by an ADR or an architecture document. |
| X | Wording in sections 3-12 that describes something the main tree no longer has. **Not changed in this round**; listed for a decision. |
| H | Dated history cut from a row of section 7 in this round. The row now states current behaviour only; the whole original row is quoted for the record. |
| stale | A statement found false or unresolvable while doing the move. |

## How the original text was carried

The original text in each `<details>` block is verbatim, with three mechanical changes and no
others:

1. **Common leading indentation was removed** from each excerpt, so that a fragment of a
   nested bullet does not render as a code block.

2. **Relative links were rebased** from the repository root to this file's directory, by
   prefixing `../../`, so that they still resolve.
3. **A full snapshot path is written with its folder name in parentheses**, as
   `projects/(name)/run`. The main tree may name a snapshot's path only in the files that
   document the snapshots (`tools/tests/test_nothing_reaches_into_a_snapshot.py`), and this
   file is not one of them.

Phrases such as "the bullet above" or "this file" refer to the old `CLAUDE.md`, not to this
queue.

## Index

| # | Class | Source lines | Summary | Recommendation |
|---|---|---|---|---|
| [Q01](#q01) | B+ | 32-39 | Phase status preamble: Phase 1 closed, Phase 2 split into 2.A/2.B, `cite_twin` exists. | Delete. Rewritten in the new section 2's first bullet; charter section 8 owns the record. |
| [Q02](#q02) | D | 41-53 | Every count names its command and who measured it; the history of wrong counts; a claim about what has never happened expires when the thing runs again. | Promote the two rules (a count names its command; a claim that something has never happened expires) to CLAUDE.md as rules, the first is already in the new section 2. Delete the history. |
| [Q03](#q03) | C | 54-83 | Re-audit metadata: which commit each figure was taken at (dd93488, abdae38, df91154, 6d51966), and `gh` being unauthenticated for eleven commits. | Delete; git history has it. Lines 74-76 ("not touching a figure you cannot measure is right; leaving it untouched once you can...") are a candidate rule. |
| [Q04](#q04) | C | 84-94 | ADR-0069 re-measurement note and the CLOSED RECORD notice for the `cell_a` tables. | Delete. The closed-record figures now live in the snapshot that keeps `cell_a` (see projects/README.md). |
| [Q05](#q05) | B+ | 96-110 | Milestones are frozen snapshots under `projects/`; what the main tree's checks do and do not walk there. | Delete. Summarised in the new section 2; projects/README.md and ADR-0068 are the record. |
| [Q06](#q06) | B+ | 111-116 | Phase 1.A closed: container, scripts contract, manifests, CI, asset policy; `xarm_ros2` pinned by SHA. | Delete. docs/reference/toolchain.md carries the pin's verification table. |
| [Q07](#q07) | B+ | 117-122 | L0 describes one cell; `cite_generated` is generated in its entirety and never hand-edited (ADR-0021). | Delete. Rewritten in the new section 2; section 4 and ADR-0021 hold the rule. |
| [Q08](#q08) | C | 123-134 | `./scripts/validate-model` cardinality readings and their history; pairing a zone moves none of the five numbers. | Delete. Run the command. |
| [Q09](#q09) | B+ | 135-151 | What pairing `cell_b` changed in the generated tree (2 of 48 artifacts, 15 added plan lines), and the trace showing every consumer addresses a side by name. | Move the consumer trace (lines 145-151) to docs/architecture/L5-twin-synchronization.md or docs/operations/bring-up.md if it is still wanted; delete the diff figures. |
| [Q10](#q10) | C | 152-168 | Earlier cardinality (`cell_a` era), the +7 assets / +3 stations of `cell_b`, why the type count did not move. | Delete. The reference work-piece having no instances is ADR-0030's. |
| [Q11](#q11) | B+ | 169-175 | Only one zone up at a time (ADR-0056 decision 3), overtaken 2026-10-01. | Delete. ADR-0069 decision 5 carries the residue: `--zone` becomes required again when a second zone is declared. |
| [Q12](#q12) | D | 176-180 | Ask `./scripts/validate-model` for the cardinality; never state the cardinality of a generated collection in prose. | Promote to a CLAUDE.md rule (it is ADR-0027's first correction); the new section 2's "ask a command" bullet covers most of it. |
| [Q13](#q13) | C | 181-191 | `tools/tests` collection count readings on 2026-10-01 (1599, 1597). | Delete. Run the collection. |
| [Q14](#q14) | C | 195-311 | `tools/tests` collection step reconciliations 1564 -> 1516 and earlier, each closed term by term. | Delete. The embedded rule "do not difference two figures taken at non-adjacent commits" (lines 221-225, 263-265) is a candidate for a rule in docs/architecture/cross-cutting-testing.md. |
| [Q15](#q15) | C | 312-414 | `tools/tests` collection history 902 -> 1399 and the tree-parametrized suites that make it grow. | Delete. |
| [Q16](#q16) | D | 415-424 | The collection measures the size of the source and documentation trees, not coverage; collection and a run are different numbers. | Move to docs/architecture/cross-cutting-testing.md as one sentence, or delete. |
| [Q17](#q17) | B+ | 425-464 | First-party package roles: `cite_description`, `cite_twin`, `cite_test_hardware` outside charter section 7 (ADR-0040), `cite_runtime` (ADR-0034), the packages that do not exist; package counts. | Move the role sentences to docs/architecture/README.md (or each package README); delete the counts. |
| [Q18](#q18) | C | 465-482 | `doctor`'s `workspace/src` line and `build`'s summary readings and history. | Delete. |
| [Q19](#q19) | C | 483-511 | `./scripts/test` figures on 2026-10-01 (4ba6783, 35b254a, 416ffc8). Note: the newest reading (483) sits above an older one (491). | Delete. Run the command. |
| [Q20](#q20) | C | 512-589 | `./scripts/test` figures 2026-09-17 to 2026-09-28, two disagreeing full runs, a `cite_orchestration` `test_skill_cancellation` timeout, the failing host test fixed rather than re-run. | Delete. The `test_skill_cancellation` timeout belongs to a package that now lives only in the three-arm snapshot. |
| [Q21](#q21) | D | 590-596 | The per-package total was nearly published as arithmetic; `flake8` runs only in the container, so the host half cannot see it. | Promote as a rule ("measure a figure, never derive it"), or move to docs/architecture/cross-cutting-testing.md. |
| [Q22](#q22) | B+ | 597-608 | `./scripts/enter dev ./scripts/test` attaches with `compose exec`, skips the entrypoint, and runs no test at all; a live defect in `scripts/_lib.sh`. | Move to docs/operations/troubleshooting.md and open a docs/open-work.md item; it is a live tooling hazard, not history. |
| [Q23](#q23) | C | 609-780 | Shell gate, `tests/` half and per-package total histories and their reconciliations. | Delete. |
| [Q24](#q24) | D | 781-787 | The per-package total is a hand sum `test` does not print; a `--host-only` run cannot refresh it. | Move to docs/architecture/cross-cutting-testing.md. |
| [Q25](#q25) | B+ | 788-825 | Bring-up drives lifecycle transitions by request and confirmation (ADR-0058); its clause 1 is deliberately open; the harness defect #72. | Delete. Summarised in the new section 2; ADR-0058, docs/architecture/cross-cutting-lifecycle.md and docs/open-work.md #72 hold it. |
| [Q26](#q26) | B+ | 826-837 | The simulated cell comes up: what `./scripts/sim` starts on `cell_b`; scenarios `bringup` and `program_cycle`. | Delete. Summarised in the new section 2; docs/operations/bring-up.md is the runbook. |
| [Q27](#q27) | D | 956-960 | Commit-message trap: a whole-log grep counts figures and verdict strings quoted in echoed commit bodies. | Move, with items on lines 1020-1071, into one "reading a CI log" note in docs/architecture/cross-cutting-testing.md. |
| [Q28](#q28) | D | 1020-1040 | The verdict instrument: a prefix grep cannot tell `passed` from `passed its cycle assertions`; match whole lines anchored; restrict to the scenario step column. | Move to the "reading a CI log" note (see the item on lines 956-960). |
| [Q29](#q29) | B+ | 1041-1047 | The two current scenario step names in `ci.yml`; `program_cycle` blocking since 2026-09-29. | Move to the "reading a CI log" note; the step names are read from `.github/workflows/ci.yml`. |
| [Q30](#q30) | D | 1051-1071 | The whole instrument (awk over the step column), the fourth matching string that is not a verdict, why the over-count did not fire. | Move to the "reading a CI log" note. |
| [Q31](#q31) | D | 1088-1089 | Treat a `bringup` failure as a finding to investigate, not a flake to re-run past. | Promote, generalised to every scenario, as a CLAUDE.md rule (`.github/workflows/ci.yml` already says it of `program_cycle`). Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules", generalised to every scenario. The verbatim text stays here. |
| [Q32](#q32) | B+ | 1090-1103 | Motion is planned by Pilz with OMPL fallback on planning failure only; what is and is not proven (ADR-0027). | Delete. Summarised in the new section 2; ADR-0027 and docs/architecture/L3-capabilities.md hold it. |
| [Q33](#q33) | B+ | 1104-1130 | The arm takes the short way round (ADR-0060); a measurement on a pick-and-place cycle; two collision-coverage gaps #80/#81. STALE: "what unwinds this cell's arm is `MoveToHome` at both ends of every cycle" was written for the pick-and-place cycle; whether the real program unwinds the arm is unverified. | Delete; ADR-0060 holds it. Re-check the `MoveToHome` sentence against the real program (it is also in ADR-0060's index row). |
| [Q34](#q34) | B+ | 1131-1142 | `Place.Result.still_holding`: a `Place` that aborts says the arm is still holding the part; nothing decides what to do with a held part (ADR-0038 decision 5). | Delete. docs/architecture/L3-capabilities.md and the interface reference hold it. |
| [Q35](#q35) | B+ | 1143-1159 | Execution-side trajectory tolerances (ADR-0036): a detector, not a protective measure; values copied from UFACTORY. | Delete; ADR-0036 holds it. "A detector is not a protective measure" could join docs/architecture/cross-cutting-safety.md if it is not there. |
| [Q36](#q36) | B+ | 1160-1185 | An execution abort is classified in L3 before any recovery motion (ADR-0037); the abort fixture (ADR-0040). | Delete. ADR-0037, ADR-0040 and docs/architecture/L3-capabilities.md hold it. Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules": ADR-0037 is binding and violating it is an `ESCALATE` (ADR-0048 clause 1 is listed beside it, its own status block saying the same). |
| [Q37](#q37) | B+ | 1205-1210 | P10 has an automated check (ADR-0035), chosen against the v1 tree. | Delete. ADR-0035 holds it. |
| [Q38](#q38) | C | 1211-1346 | English-check walk counts (`files checked`) and their history. | Delete. Run `./scripts/lint`. |
| [Q39](#q39) | D | 1347-1380 | The walk counts what is on disk, not what is committed; `.git/info/exclude` keeps a file out of git and not out of `lint`. | Move the on-disk point to docs/onboarding/getting-started.md (or leave it to `tools/cite_tools/tree.py`'s docstring); delete the counts. |
| [Q40](#q40) | B+ | 1381-1384 | The one English-check exemption, `docs/reference/v1-lessons.md`; the check's limits are ADR-0035's. | Delete. `.english-only.yaml` and ADR-0035 hold it. |
| [Q41](#q41) | stale | 1385-1390 | "One arm picks and places a work-piece, and friction alone holds it" (ADR-0029). STALE: ADR-0061 holds the box with a grasp-hold plugin, and ADR-0065 feeds it from a simulation-only bridge (`cite_bringup/grasp_hold_bridge.py`). | Delete. The headline is false today. |
| [Q42](#q42) | B+ | 1782-1791 | Teardown flake is two families; the exit-1 family (`rclpy` shutdown races) is fixed (ADR-0034). | Delete. ADR-0034 holds it. |
| [Q43](#q43) | B+ | 1792-1824 | The signal-death family: campaign INCONCLUSIVE, the `skill_server` destructor demonstration, no exemption widened. | Delete; docs/measurements/2026-08-27-teardown-signal-family/ holds it. "No exemption may be widened to absorb a failure" is a candidate rule. The rule "no exemption may be widened to absorb a failure" was restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules"; the verbatim text stays here. |
| [Q44](#q44) | B+ | 1878-1906 | The 0.14 real-time factor is conditional on about one CPU core; never quote Gazebo's own `real_time_factor` field; the ceilings campaign. | Delete; docs/architecture/cross-cutting-testing.md is the one statement (campaign `2026-08-29-real-time-factor-conditions`). Promote "never widen a ceiling to absorb a slow host" and "measure the real-time factor from the stats topic, never quote the field". "Never widen a ceiling to absorb a slow host" was restored to CLAUDE.md §2 on 2026-10-01 as part of the general no-widening rule. |
| [Q45](#q45) | B+ | 1907-1941 | Phase 2.A: what landed (ADR-0041 to ADR-0044, `MODE_VIRTUAL_LEAD`); what a paired model adds to the plan; ask the plan for its shape. | Move to docs/architecture/L5-twin-synchronization.md if not already there; delete. |
| [Q46](#q46) | B+ | 1942-1981 | How a pair comes up (ADR-0047), its evidence (three runs at `b3b7b66`), what a pair is not, no paired scenario, `pair.py` hazards. STALE: the readiness witness is said to wait on "every skill and detection action server"; there is no `Detect.action` in `cite_interfaces` today. | Move to docs/architecture/L5-twin-synchronization.md or docs/operations/bring-up.md with the stale clause corrected; delete the evidence counts. |
| [Q47](#q47) | B+ | 1982-2003 | A checkout claims two domains (odd base, even counterpart); the plan carries an offset; `require_domain`; ADR-0044 still Proposed. | Delete. docs/onboarding/getting-started.md, docs/operations/troubleshooting.md and ADR-0044 hold it. |
| [Q48](#q48) | B+ | 2004-2049 | `MODE_VIRTUAL_LEAD` routes; what `twin_boundary.py` wires; the supervisor starts L5 (ADR-0057); nothing in CI reaches it; test-module count history. | Move to docs/architecture/L5-twin-synchronization.md; delete the count history. |
| [Q49](#q49) | B+ | 2065-2077 | `DivergenceMetrics.valid` is false by construction (clock-deficit term has no instrument); do not make it true by weakening a term. | Delete; summarised in the new section 2. docs/architecture/L5-twin-synchronization.md should carry it. |
| [Q50](#q50) | B+ | 2078-2130 | The throttle is a ceiling; ADR-0043 half 2 unmet in two ways; ADR-0049 ratified, not promoted; nothing measures capacity during a run. | Delete. ADR-0043, ADR-0049 and the capacity campaign hold it. |
| [Q51](#q51) | D | 2131-2139 | The Gazebo-partition defect class and the one door, `cite_bringup/gz.py`, with its guard. | Delete; section 10 already carries it as a review checkpoint. |
| [Q52](#q52) | B+ | 2140-2141 | Header of "What does not work, stated plainly". | Delete; the new section 2 has its own. |
| [Q53](#q53) | B+ | 2211-2309 | Option F (ADR-0052): the superseded predicate, the implemented one, the gate not fully cleared, the open-stroke region it opens, the caller door closed. OPEN OWNER DECISION: whether the monotonicity term returns. | Delete; docs/open-work.md #36 and ADR-0052 hold it. The owner decision on the monotonicity term stays open there. |
| [Q54](#q54) | B+ | 2310-2320 | No vendor-described link's mass or inertia is validated by anything; "owed its own record". | Needs an ADR (or a docs/open-work.md item); it is a live structural gap. |
| [Q55](#q55) | B+ | 2321-2335 | The collision gate's sampling edge (0.1 s, 40 mm, 0.40 m/s) is unmeasured; the waypoint-clearance campaign did not exercise it. | Delete. ADR-0027's amendment of 2026-09-04 holds it. |
| [Q56](#q56) | B+ | 2336-2356 | Execution tolerances under Gazebo: the quiet is measured, detecting an obstruction is not; never widen a tolerance. | Delete. ADR-0036's 2026-09-04 amendment and its campaign hold it. "Never widen a tolerance" was restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules"; the verbatim text stays here. |
| [Q57](#q57) | B+ | 2357-2376 | A grasp holds a position, not an orientation; the 18.7 degree residual is a roll, the yaw figure is 10.62 degrees; a yawed square part parks short. | Move to docs/architecture/L3-capabilities.md (or L1) if still wanted; the campaigns hold the figures. |
| [Q58](#q58) | B+ | 2382-2387 | `Transfer`, `Pick` and `Place` have servers and no program caller. | Delete; summarised in the new section 2. |
| [Q59](#q59) | B+ | 2404-2438 | Scenarios are not deterministic: what the seed reaches, the 2026-09-22 campaign and what it is forbidden to say, `./scripts/sim` passes no seed, `libdart`'s own generator. | Delete; summarised in the new section 2. docs/architecture/cross-cutting-testing.md and the campaign hold it. |
| [Q60](#q60) | B+ | 2439-2531 | Convex-hull collision meshes (ADR-0028): selection, promotion on a restated clause (ADR-0051), the 50 mm bound, residuals, count history of hull CI runs, a hull adds no clearance, the `self_collide` hazard. | Move "a hull adds no clearance and may never be cited as margin" and the `self_collide` hazard to docs/architecture/cross-cutting-safety.md; delete the rest (ADR-0028 holds it). |
| [Q61](#q61) | D | 2598-2600 | Do not widen any ceiling to absorb whatever CI shows next. | Promote to a CLAUDE.md rule (with tolerances and exemptions: never widen one to absorb a failure). Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules" (ceilings, tolerances and teardown exemptions). The verbatim text stays here. |
| [Q62](#q62) | B+ | 2601-2614 | The capacity case: hulls clear the 1.0 floor with the throttle lifted, vendor meshes miss it; no requirement shown passing. | Delete. The capacity campaign and ADR-0049 hold it. |
| [Q63](#q63) | D | 2615-2624 | Two hull mechanisms stated as fact and falsified; an audit taken at a commanded value must state whether the machine reaches it; a gate must not be written against an unobserved mechanism. | Promote to a CLAUDE.md rule; `tools/tests/test_the_retracted_gripper_claim.py` already enforces the retraction. |
| [Q64](#q64) | B+ | 2625-2640 | The cell runs the real robot's program (ADR-0067); the event-driven line removed (ADR-0069); the belt route kept with no in-tree client. | Delete; rewritten in the new section 2. |
| [Q65](#q65) | B+ | 2641-2643 | The layout is PROVISIONAL until the Phase 3 scan. | Delete; rewritten in the new section 2. |
| [Q66](#q66) | B+ | 2644-2648 | Documentation status markers DESIGNED / PARTIAL / BUILT. | Delete; rewritten in the new section 2. |
| [Q67](#q67) | B+ | 2649-2653 | Measured evidence lives in docs/measurements/; an inconclusive campaign is published too. | Delete; rewritten in the new section 2. |
| [Q68](#q68) | B+ | 2654-2657 | Lead-in: charter section 8 owns Phase 1's clause-by-clause record. | Delete; the new section 2 points to charter section 8. |
| [Q69](#q69) | D | 2675-2679 | Never cite "CI is green" as evidence; cite the step that gates it; a `continue-on-error` step's conclusion is not its result. (The last line runs into the CI-failure tally that moved with the three-arm snapshot.) | Promote to a CLAUDE.md rule; the new section 2 states the step-log half. |
| [Q70](#q70) | C | 2713-2719 | ADR index count on 2026-10-01 (68 records; glob 69) and the newest record. | Delete. Run `./scripts/doctor`. |
| [Q71](#q71) | C | 2767-2830 | ADR index history 59 -> 40 and the glob-versus-doctor relation; ADR-0059's pairing decision; `cell_a` load-bearingly single (overtaken). | Delete. The ADR index table in docs/adr/README.md is the record. |
| [Q72](#q72) | D | 2831-2838 | Name the command with the number; run `doctor` rather than quoting the ADR count; `doctor` checks indexing, not completeness, and no check can. | Move the completeness sentence to docs/adr/README.md; the rest is the new section 2's "ask a command" rule. |
| [Q73](#q73) | stale | 12-28 | Section 1 as it stood: "whose first instrument is a multi-robot xArm work cell", read as stale since ADR-0069 (the main tree is one xArm 5 per side of the paired `cell_b`); the sentence mirrors charter section 1 and was restored. | The identity sentence ("whose first instrument is a multi-robot xArm work cell", which mirrors charter section 1) was restored verbatim to CLAUDE.md section 1 on 2026-10-01 after review; the new paragraph is kept beside it as the main tree's current scope statement. Owner decision: whether the charter's identity wording should change, which is a charter change. |
| [Q74](#q74) | H | 2953 | Section 7, `./scripts/sim` row: dated history clauses (required with no default until 2026-10-01; `--pair` used to imply `--headless`; every GUI run rendered in software until 2026-09-28). | Delete the history. The row in CLAUDE.md now states only current behaviour; the GPU-library rationale is in `scripts/sim`'s own comment. |
| [Q75](#q75) | H | 2957 | Section 7, `./scripts/scenario` row: "`pick_and_place` and `continuous_line` left the main tree with ADR-0069 and run from projects/01". | Delete; projects/README.md says where they run. |
| [Q76](#q76) | H | 2958 | Section 7, `./scripts/program` row: "(ADR-0067, which replaced ADR-0066's taught poses)" and "ADR-0066's taught-pose version runs as ... /run". | Delete; projects/README.md lists the fixed-program snapshot. |
| [Q77](#q77) | H | 2962 | Section 7, `projects/<name>/run` row: "what `./scripts/demo` showed until ADR-0069 removed it on 2026-10-01". The row keeps the snapshot path, which `tools/tests/test_nothing_reaches_into_a_snapshot.py` requires CLAUDE.md to carry. | Delete the history clause (done in CLAUDE.md); keep the path. |
| [Q78](#q78) | X | 2867-2868 | Section 3, P9: "A new robot type must not touch orchestration" names a layer (L4 behaviour trees) the main tree no longer has. | Owner decision: keep as a principle for whatever drives the cell (the real program, the twin boundary), or reword. Not changed this round. |
| [Q79](#q79) | X | 2886-2895 | Section 5, layer stack: L4 reads "behaviour trees, line coordination, handoff" and L3 lists `Detect`; the main tree has no L4 package and no `Detect.action`. | Owner decision: reword L4 to what drives the cell today (the real program through the twin boundary) and drop `Detect`, or keep both as the target architecture (charter section 5). Not changed this round. |
| [Q80](#q80) | X | 2932 | Section 6, technology baseline: "Orchestration \| BehaviorTree.CPP v4 + Groot2"; nothing in the main tree uses BehaviorTree.CPP since ADR-0069. | Needs an ADR to change (section 6 says so). Not changed this round. |
| [Q81](#q81) | X | 3005-3011 | Section 10, QoS note: "That cost this project a belt setpoint that was never once delivered" is an anecdote about the removed L4 line. | Delete the anecdote sentence, keep the rule. Not changed this round. |
| [Q82](#q82) | X | 3044-3047 | Section 11: "This happened on 2026-08-24 and cost a whole phase's worth of work its review." | Delete the dated incident, keep the rule. Not changed this round. |
| [Q83](#q83) | stale | 1660, 2203 (moved) | "Both records are implemented and merged on `main` at `c555440`" (ADR-0045, ADR-0046): `git cat-file -t c555440` fails in this repository on 2026-10-01, so the citation does not resolve. The text moved with the three-arm snapshot's MEASUREMENTS.md and is quoted here only for this finding. | Owner decision whether to resolve the right SHA; snapshot text is a record and is not corrected. |
| [Q84](#q84) | stale | none | The seventeen campaigns under docs/measurements/ stayed where they are. Which milestone each one's subject belongs to has not been decided; a first sort, by date and title only and NOT verified against each campaign's criteria.md, is in the original-text block. | Owner decision per campaign: keep in docs/measurements/ (subject still in the main tree) or record in the relevant snapshot's MEASUREMENTS.md that it belongs there. Campaign folders are frozen and are not moved by this cleanup. |
| [Q85](#q85) | stale | none | Citations of "CLAUDE.md section 2" (or of a paragraph of it) left untouched because the file is protected, an ADR, a frozen campaign, or a dated record. | Leave as they are: each names the pre-2026-10-01 text, which is `git show 960e6b4:CLAUDE.md` and is preserved in this queue and in the snapshots' MEASUREMENTS.md files. The charter's three are the owner's to change. |
| [Q86](#q86) | C | 192-194 | `tools/tests` collection reading 1782 on `feat/projects-snapshots` (2026-09-30), the branch that made the snapshots, whose base `e90d230` is the real-program snapshot's source commit. Moved here from that snapshot's `MEASUREMENTS.md` on 2026-10-01: it is a main-tree count, not a measurement of the milestone. | Delete. Run the collection. |
| [Q87](#q87) | C | 2720-2729 | ADR index readings 67 (2026-09-29) and 65 (2026-09-28), around the source commits of the fixed-program and real-program snapshots; no reading of 66 was taken. Continues Q70 mid-sentence and runs into Q91. Moved here from those snapshots' `MEASUREMENTS.md` files on 2026-10-01: a main-tree count, not a measurement of either milestone. | Delete. Run `./scripts/doctor`; docs/adr/README.md is the record. |
| [Q88](#q88) | B+ | 896-921 | The first pair brought up from the committed model (2026-09-18, `cell_b`, one run) and one `MoveTo` dispatched to two arms through the boundary, with the bypass control. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: its subject, the paired `cell_b`, is the main tree. | Delete. ADR-0059 holds the figures and the control (its table of goals); ADR-0057 clause 4 holds the missing gate. |
| [Q89](#q89) | B+ | 922-940 | `bringup` run four times locally against the paired `cell_b` (2026-09-18): 3 of 4, the one failure a lost goal response (`Failed to send goal response … (timeout)`) behind the `the MoveTo goal was never accepted` assertion; the base-rate run was not taken. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: `bringup` on `cell_b` is a main-tree gate. The first sentence also carries the `pick_and_place` run and stays in that snapshot too; it is quoted here as context. | Move the finding to docs/open-work.md #26 (the `MoveTo` never-accepted item) as an occurrence on the paired plan, with its strength; delete the rest. |
| [Q90](#q90) | B+ | 2050-2064 | A boundary brought up and `SetMode` called on it, and a pair torn down by one SIGINT, boundary first (2026-09-18, one machine, model flipped and reverted); `move_group` -11 on both sides, unclassified. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: the pair and its boundary are the main tree. | Delete. ADR-0057's promotion section and ADR-0059 hold the `SetMode` reading and the teardown; the -11 is the teardown-signal family (docs/measurements/2026-08-27-teardown-signal-family/). |
| [Q91](#q91) | B+ | 2730-2766 | ADR index readings 64 and 62, carrying the box-spread figures of ADR-0065 (0.000 mm sideways push over nine paired runs, the 0.5 mm bar bound to no gate, a bimodal spread with no established separator) and what ADR-0063 does not buy. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: the grasp-hold bridge and the paired box spread are main-tree subjects. | Delete. ADR-0065 holds the box-spread figures and the bar; ADR-0063 and its amendment hold the clamp decision. Run `./scripts/doctor` for the ADR count. |

## Items

### Q01

- **Class:** B+
- **Source:** `CLAUDE.md` lines 32-39 at `960e6b4`
- **Summary:** Phase status preamble: Phase 1 closed, Phase 2 split into 2.A/2.B, `cite_twin` exists.
- **Recommendation:** Delete. Rewritten in the new section 2's first bullet; charter section 8 owns the record.

<details><summary>Original text</summary>

**Phase 1 of the rebuild is closed**, as of 2026-08-28: charter §8 records its exit
criterion MET, and records in the same place what that closure rests on and what it does
not cover. Nothing below is retired by the closure — the gap list is still the gap list.
**Phase 2 has since split into 2.A and 2.B (charter v1.9, 2026-08-29) and 2.A's mechanism is
in the tree: a pair has come up, three times on one machine, covered by no test, and an L5
package has since landed beside it — `cite_twin` exists, and what it is and is not is the
Phase 2.A bullet below.** The charter describes the target; the repository is partway there.
Check before assuming.

</details>

### Q02

- **Class:** D
- **Source:** `CLAUDE.md` lines 41-53 at `960e6b4`
- **Summary:** Every count names its command and who measured it; the history of wrong counts; a claim about what has never happened expires when the thing runs again.
- **Recommendation:** Promote the two rules (a count names its command; a claim that something has never happened expires) to CLAUDE.md as rules, the first is already in the new section 2. Delete the history.

<details><summary>Original text</summary>

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

</details>

### Q03

- **Class:** C
- **Source:** `CLAUDE.md` lines 54-83 at `960e6b4`
- **Summary:** Re-audit metadata: which commit each figure was taken at (dd93488, abdae38, df91154, 6d51966), and `gh` being unauthenticated for eleven commits.
- **Recommendation:** Delete; git history has it. Lines 74-76 ("not touching a figure you cannot measure is right; leaving it untouched once you can...") are a candidate rule.

<details><summary>Original text</summary>

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

</details>

### Q04

- **Class:** C
- **Source:** `CLAUDE.md` lines 84-94 at `960e6b4`
- **Summary:** ADR-0069 re-measurement note and the CLOSED RECORD notice for the `cell_a` tables.
- **Recommendation:** Delete. The closed-record figures now live in the snapshot that keeps `cell_a` (see projects/README.md).

<details><summary>Original text</summary>

**Where a figure names 2026-10-01 and `feat/remove-parked-line` it was taken after [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md)
removed the event-driven line, `cite_orchestration`, the detection and topology servers, ten
line-only interfaces, `./scripts/demo`, the `pick_and_place` and `continuous_line` scenarios and
zone `cell_a` from the main tree.** Every count that branch moved — the `validate-model`
cardinality, the package count, `build`'s summary, all three `test` figures, the collection, the
`lint` walk and the ADR index — **was re-measured or quoted from a named run, and every step
spans a removal and is not reconciled term by term.** The `build` and `test` figures are the
`coder` agent's verbatim readings from its own run at `416ffc8` and were not re-run by the pass
that wrote them here. **The CI tables and every `cell_a`, `pick_and_place` and
`continuous_line` figure below are a CLOSED RECORD of a cell and scenarios no longer in the main
tree**; they run only in the `projects/01` snapshot.

</details>

### Q05

- **Class:** B+
- **Source:** `CLAUDE.md` lines 96-110 at `960e6b4`
- **Summary:** Milestones are frozen snapshots under `projects/`; what the main tree's checks do and do not walk there.
- **Recommendation:** Delete. Summarised in the new section 2; projects/README.md and ADR-0068 are the record.

<details><summary>Original text</summary>

- **Milestones are kept under [`projects/`](../../projects/README.md)** as frozen, runnable
  snapshots ([ADR-0068](../../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md),
  `Proposed`): `01-three-arm-event-driven-line` from `b5a0bc9` (tag `event-driven-line-v1`),
  `02-fixed-program-pair` from `c83119b` and `03-real-program-twin-on-track` from `e90d230`.
  **Whether each builds and runs is recorded in its own `PROVENANCE.md` and is not copied
  here.** Nothing in this section describes a snapshot. The main tree's checks skip
  `projects/` except for exactly this: `projects/README.md` and `projects/snapshots.yaml` are
  walked (English, links) and the manifest yamllinted; each snapshot's `run` is shellchecked;
  and each snapshot's committed tree is checked against the hash the manifest pins. Four
  repository walkers are narrowed to leave the snapshots out — three `git ls-files` host tests
  and `cite_test_hardware`'s ctest walk (ADR-0068 decision 4).
  **Since 2026-10-01 the main tree no longer carries what `01` records**: [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) removed the
  event-driven line and `cell_a` from it, so `projects/01` is the only place they build and
  run, checked by the weekly, non-blocking `.github/workflows/projects.yml`, which does not gate
  `main`.

</details>

### Q06

- **Class:** B+
- **Source:** `CLAUDE.md` lines 111-116 at `960e6b4`
- **Summary:** Phase 1.A closed: container, scripts contract, manifests, CI, asset policy; `xarm_ros2` pinned by SHA.
- **Recommendation:** Delete. docs/reference/toolchain.md carries the pin's verification table.

<details><summary>Original text</summary>

- **Phase 1.A is closed.** Container image, the `./scripts/*` contract, dependency
  manifests, CI, and the asset policy all exist and work. `external/cite.repos` pins
  `xarm_ros2` to a commit SHA, after the branch was built and driven against our stack
  rather than merely inspected — see the verification table in
  [`docs/reference/toolchain.md`](../../docs/reference/toolchain.md). `./scripts/doctor` exits 0;
  run it to see the state of any machine.

</details>

### Q07

- **Class:** B+
- **Source:** `CLAUDE.md` lines 117-122 at `960e6b4`
- **Summary:** L0 describes one cell; `cite_generated` is generated in its entirety and never hand-edited (ADR-0021).
- **Recommendation:** Delete. Rewritten in the new section 2; section 4 and ADR-0021 hold the rule.

<details><summary>Original text</summary>

- **The L0 model and its generators are built and proven** (Phase 1.B). `model/` describes
  **one cell, `cell_b`**, and `workspace/src/cite_generated/` holds everything derived from it:
  descriptions, the world, controller configuration, MoveIt configuration, the planning
  scene, static frames, process topology and the bring-up plan, **one complete set per
  zone**. That directory is
  **generated in its entirety and must never be hand-edited** (ADR-0021).

</details>

### Q08

- **Class:** C
- **Source:** `CLAUDE.md` lines 123-134 at `960e6b4`
- **Summary:** `./scripts/validate-model` cardinality readings and their history; pairing a zone moves none of the five numbers.
- **Recommendation:** Delete. Run the command.

<details><summary>Original text</summary>

`./scripts/validate-model` diffs it against a fresh generator run *and* regenerates in a
second interpreter under a different hash seed to prove the output is byte-identical; it
exits 0, reporting **`1 zone(s), 7 type(s), 7 asset(s), 3 station(s), across 17 file(s)`** in
this checkout on **2026-10-01 on `feat/remove-parked-line`**, after [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) removed zone `cell_a`
from L0. **That step spans a removal — `cell_a`'s zone, flow, stations and instances, the
`pedestal_600` type — and the branches between it and the reading below, which among other
things added the linear-axis type (ADR-0067), and it is not reconciled term by term here.** It read
`2 zone(s), 7 type(s), 22 asset(s), 8 station(s), across 16 file(s)` in
this checkout on 2026-09-16 at `0dae8a0` on `feat/cell-b-zone`, **and identical again on
`main` on 2026-09-18 with `cell_b` declared `pair`** (ADR-0059) — which is the property to
carry: **pairing a zone moves none of those five numbers**, because it adds no asset, no
station and no file.

</details>

### Q09

- **Class:** B+
- **Source:** `CLAUDE.md` lines 135-151 at `960e6b4`
- **Summary:** What pairing `cell_b` changed in the generated tree (2 of 48 artifacts, 15 added plan lines), and the trace showing every consumer addresses a side by name.
- **Recommendation:** Move the consumer trace (lines 145-151) to docs/architecture/L5-twin-synchronization.md or docs/operations/bring-up.md if it is still wanted; delete the diff figures.

<details><summary>Original text</summary>

**What it does move was measured rather than described, by generating both models and
differencing every artifact**: exactly **two** of the 48 differ, `MODEL_HASH` and
`bringup/cell_b_plan.yaml`, and the plan's **15** changed lines are **all additions, with
nothing modified and nothing removed** — the counterpart's `sides:` entry with its partition
and `domain_offset`, and `counterpart_backend` / `counterpart_commands_physical_hardware`
with their comments. **So nothing the plant reads ABOUT ITSELF changed**, and the loose form
of that sentence — "nothing the plant side reads changed" — is false in two ways a reader
would quote: the plant reads the **whole** plan document, which is not byte-identical, and
`cite_facility/artifacts.py` reads `MODEL_HASH`, which `model_info` serves, so the cell
publishes a different model version after the flip.
**What actually carries "the single-side path is untouched" is the consumers, not the diff**,
and they were traced rather than assumed: every consumer of a side addresses it **by name** —
`simulation.launch.py` defaults `side:=plant` and passes the name on, `cite_bringup/gz.py`
addresses a side by name and records in its own docstring that `plan.sides[0]` was removed for
exactly this reason, `resolve_domain_id` is called per requested side,
`require_hardware_opt_in` iterates both sides and both are `false`, and `cite_facility` and
`tests/scenarios/` read no side at all.

</details>

### Q10

- **Class:** C
- **Source:** `CLAUDE.md` lines 152-168 at `960e6b4`
- **Summary:** Earlier cardinality (`cell_a` era), the +7 assets / +3 stations of `cell_b`, why the type count did not move.
- **Recommendation:** Delete. The reference work-piece having no instances is ADR-0030's.

<details><summary>Original text</summary>

**It read `1 zone(s), 7 type(s), 15 asset(s), 5 station(s), across 15 file(s)` until that
date, and that reading had survived four re-audits** — 2026-09-01 at `abdae38` twice,
2026-09-08 at `df91154` and again at `6d51966` — which is what made it, until now, the one
figure in this section no re-audit had ever had to move. **What moved it was a model change
and not a re-audit**: ADR-0056 declares a second zone `cell_b`, a one-arm cell, and keeps
the three-arm `cell_a` as a zone beside it rather than deleting or copying it. Both cells
are generated by the same generator from the same model, so every platform fix reaches
both, and `validate-model` and `build` cover both. **[Overtaken 2026-10-01 — ADR-0069 removed
`cell_a` from L0, so one cell is generated; the three-arm cell is kept only in the
`projects/01` snapshot, which receives no platform fix.]**
**The +7 assets and +3 stations are `cell_b`'s entire content**, and the +1 file is its
flow document — `model/topology/flow_cell_b.yaml`, separate because `FlowDocument` holds
exactly one flow. **The type count did not move, and that is the property worth stating**:
`resolve.py` hands every type to every zone, so a second cell built from the same component
library adds no type. The seventh type is the reference
work-piece, which has no
instances on purpose (ADR-0030).

</details>

### Q11

- **Class:** B+
- **Source:** `CLAUDE.md` lines 169-175 at `960e6b4`
- **Summary:** Only one zone up at a time (ADR-0056 decision 3), overtaken 2026-10-01.
- **Recommendation:** Delete. ADR-0069 decision 5 carries the residue: `--zone` becomes required again when a second zone is declared.

<details><summary>Original text</summary>

**Only one zone is up at a time** (ADR-0056 decision 3), because the three reserved
facility scopes `/cite/facility`, `/cite/line` and `/cite/twin` are deliberately not
zone-scoped and `ROS_DOMAIN_ID` is derived per checkout × side and never per zone. That
record declines four ADR-sized changes on the record rather than leaving them to be
discovered. **[Overtaken 2026-10-01 — ADR-0056 is superseded by ADR-0069 and L0 declares one
zone; the reasoning is what a second zone would have to answer, and `--zone` becomes required
again the day one is declared.]**

</details>

### Q12

- **Class:** D
- **Source:** `CLAUDE.md` lines 176-180 at `960e6b4`
- **Summary:** Ask `./scripts/validate-model` for the cardinality; never state the cardinality of a generated collection in prose.
- **Recommendation:** Promote to a CLAUDE.md rule (it is ADR-0027's first correction); the new section 2's "ask a command" bullet covers most of it.

<details><summary>Original text</summary>

**Ask `./scripts/validate-model` for the cardinality; do not read it out of prose.** This
file said "fourteen instances" until 2026-08-27 and it was fifteen — one addition, at
`aef87e6`, falsified the number here, in L0's status line and in ADR-0027 at once, which is
why ADR-0027's first correction ends *"do not state the cardinality of a generated
collection in prose."*

</details>

### Q13

- **Class:** C
- **Source:** `CLAUDE.md` lines 181-191 at `960e6b4`
- **Summary:** `tools/tests` collection count readings on 2026-10-01 (1599, 1597).
- **Recommendation:** Delete. Run the collection.

<details><summary>Original text</summary>

`tools/tests/` holds **1599** tests, counted by collection rather than by a run
(`.venv/bin/python -m pytest tools/tests --collect-only -q`, this checkout, on
`feat/remove-parked-line` at `35b254a`, 2026-10-01, after that branch's review
remediation). **The 1597 -> 1599 step is +2 and it is tree growth alone**: the remediation
adds one tracked file, `tests/scenarios/guards/test_program_cycle_stops_its_belt.py`, which
`test_superseded_real_time_requirement.py` counts by suffix and
`test_a_removed_plan_key_stays_removed.py` counts by tree. 1 + 1 = 2.
It read **1597** earlier the same day on the same branch. **The 1782 -> 1597 step spans ADR-0069's removal —
deleted guards such as `test_event_driven_line_is_kept.py`, tests retargeted from three arms
to one, and fewer tracked files for the tree-parametrized suites to count — and is not
reconciled term by term.**

</details>

### Q14

- **Class:** C
- **Source:** `CLAUDE.md` lines 195-311 at `960e6b4`
- **Summary:** `tools/tests` collection step reconciliations 1564 -> 1516 and earlier, each closed term by term.
- **Recommendation:** Delete. The embedded rule "do not difference two figures taken at non-adjacent commits" (lines 221-225, 263-265) is a candidate for a rule in docs/architecture/cross-cutting-testing.md.

<details><summary>Original text</summary>

It read **1569** on `feat/let-go-when-clear`, 2026-09-28.
**The 1564 -> 1569 step is +5 and it is the first in this bullet's recent history that is NOT
tree growth alone** — it is tree growth **minus** a deletion, and both halves were measured on
both sides in a worktree at `main` rather than differenced. The branch adds **5** tracked files
(`git diff --diff-filter=A --name-only main..HEAD`, with `--diff-filter=D` and `R` both **0**):
two `.md`, ADR-0064 and ADR-0065, and three `.py` — the simulation-only grasp-hold bridge and
its two guards. Per file: `test_superseded_real_time_requirement.py` 419 -> **422**, the three
`.py`; `test_a_removed_plan_key_stays_removed.py` 387 -> **390**, the same three under
`workspace/`; `test_interface_counts.py` 173 -> **175**, the two `.md`. That is +8. Against it,
`test_generate_world.py` 29 -> **26**: ADR-0065 removes eight world parameters the plugin no
longer reads, and the tests asserting them went with them. 8 - 3 = 5.
**A deletion in this figure is worth one line, because the bullet's whole argument is that it
measures the size of the trees and not coverage.** Eight assertions left the suite and the
number still rose.
It read **1564** on `feat/clamp-the-box` at `50a51a9`, 2026-09-24.
**The 1560 -> 1564 step is +4, it is tree growth alone, and every term of it was MEASURED on
both sides rather than attributed** — `main`'s figures were taken in a worktree at `main` the
same day, not differenced from an earlier reading. The branch adds exactly **3** tracked files
(`git diff --diff-filter=A --name-only main..HEAD`, with `--diff-filter=D` and `--diff-filter=R`
both **0**): two `.md`, ADR-0062 and ADR-0063, and one `.py`,
`workspace/src/cite_bringup/test/test_release_confirmation_launch.py`. Per file:
`test_interface_counts.py` 171 -> **173**, the two `.md`;
`test_superseded_real_time_requirement.py` 418 -> **419**, the one `.py` carrying one of its
seven suffixes; `test_a_removed_plan_key_stays_removed.py` 386 -> **387**, that same `.py`
under `workspace/`. 2 + 1 + 1 = 4. **Not one test case was added to `tools/tests`**, and the
two 1s are one file counted by two walks rather than one quantity counted twice.
**The previous reading here was 1542 and it is NOT differenced against.** It was taken on
`measure/is-a-run-reproducible` and this is `main` plus four commits; the two are not adjacent,
and attributing a step across them is the habit this bullet spends most of its length warning
about. It read **1542** on that branch on 2026-09-22 and **1531** on `main` on 2026-09-18 with
`cell_b` paired.
**The 1531 -> 1542 step is +11, it is tree growth alone, and it was predicted before it was
measured.** The branch publishes a campaign and adds **61** tracked files
(`git diff --diff-filter=A --name-only 79b1acd..HEAD`, with `--diff-filter=D` and `R` both
**0**), of which **4** are `.md` — `test_interface_counts.py` +4 — and **7** carry one of
`test_superseded_real_time_requirement.py`'s seven suffixes, being 5 `.py` and 2 `.sh`, so +7.
4 + 7 = 11. **`test_a_removed_plan_key_stays_removed.py` did not move at all**, and that is
the property worth stating: its walk is over **seven trees** — `workspace`, `tools`, `tests`,
`scripts`, `model`, `.github`, `infra` — and **`docs/` is not one of them**, so the other 50
files, every `.json`, `.console`, `.sdf` and `.txt` of a published campaign's raw records,
move this figure not at all. **A campaign is the one kind of change that moves the `lint` walk
far more than it moves this count**, and the bullet below is where that shows.
**The 1521 -> 1523 step is two `.md` files and nothing else, and it closes in two parts
because the two figures sit at non-adjacent commits** — which is the habit this bullet warns
against, so the intermediate reading was taken rather than the difference attributed.
Measured in a worktree at `6ae160d`, the commit before this change: **1522**. The step from
`7c6e902` to there is `git diff --diff-filter=A --name-only 7c6e902..6ae160d`, which lists
**one** file, `docs/adr/0057-…md`, with `--diff-filter=D` and `R` both **0** — and only
`test_interface_counts.py` counts an `.md`. This change then adds `docs/adr/0059-…md`, the
same +1 by the same walk. **Not one test case was added to `tools/tests` by either**, and
pairing a zone adds no tracked file at all.
**The 1516 → 1521 step is tree growth alone and closes exactly**, which is worth one line
because it is the first step in this bullet's history whose three contributors are all
different files. `main` gained **3** tracked files over that span
(`git diff --diff-filter=A --name-only 1af668b..7c6e902`, with `--diff-filter=D` and `R`
both **0**): two `.py` under `workspace/src/cite_bringup`, which
`test_superseded_real_time_requirement.py` counts by suffix (404 → **406**) and
`test_a_removed_plan_key_stays_removed.py` counts by tree (378 → **380**); and one `.md`,
`docs/adr/0058-…`, which only `test_interface_counts.py` counts (161 → **162**).
2 + 2 + 1 = 5. Not one test case was added to `tools/tests`.
It said **302** until 2026-08-29, **331** until 2026-08-31, **411** earlier on 2026-09-01,
**902** later that day, **927** until 2026-09-02, **973** until 2026-09-08, **1023** for
part of that day, **1376** for part of it too, **1377** until 2026-09-10, **1399** while
that reading stood, **1468** unrecorded and **1514** for part of 2026-09-17.
**That last entry is the point of this sentence: 1468 was never written here.** The figure
read 1399, taken at `523ffd9`, and two commits landed after it — `ee3d609` and `2b135b3`,
both validator refusals — that moved it to **1468** without anyone re-collecting. It was
measured on 2026-09-16 in a worktree at `1adf0cf`, which is this branch's base, and the +69
those two commits account for is **not reconciled here**: this work did not take them apart,
and attributing a step to a commit nobody measured is what this bullet spends most of its
length warning against.
**The 1468 -> 1502 step is this branch's alone and closes exactly**, measured in this
checkout against that same worktree at `1adf0cf`, and it is **both kinds at once**: **+3 is
the suite and +31 is the tree**.
New cases: `tools/tests/test_every_zone_has_a_flow_document.py` collects **3**, a new file.
It is also itself one of the tracked files counted below, so **2 of the 31 are that guard
being counted by two other suites** — a file cannot add three cases of its own without
adding two of somebody else's.
Tree growth, over the **16** tracked files this branch adds (`git diff --diff-filter=A
--name-only 1adf0cf..HEAD` counts 16, with `--diff-filter=D` and `--diff-filter=R` both
**0**): `test_superseded_real_time_requirement.py` 382 -> **397**, the **15** of those
sixteen carrying one of its seven suffixes — `cell_b.sdf` carries none — and
`test_a_removed_plan_key_stays_removed.py` 355 -> **371**, all **16** being under its seven
trees. `test_interface_counts.py` did **not** move, reading **161** on both sides, because
the branch adds no tracked `.md`. 3 + 15 + 16 = 34, and 1468 + 34 = 1502.
**Fourteen of those sixteen files are generated**, which is the clearest illustration in
this bullet of what the figure measures: declaring one zone in `model/` — one hand-written
flow document — emitted **fourteen** artifacts, and every one of them is a tracked file that
two tree-parametrized suites then count a case for. **Twenty-seven of the 31 tree cases are
those fourteen files**, and not one of them is a new assertion about anything.
**The 1502 -> 1514 step is the remediation of that branch's four reviews, and it is tree
growth ALONE** — measured in this checkout on 2026-09-17, against the figures the paragraph
above records at `f7aed46`. **No file was added under `tools/tests` at all**, so the +12 is
entirely the six tracked files the remediation adds elsewhere being counted twice:
`test_superseded_real_time_requirement.py` 397 -> **403**, all **6** carrying one of its
seven suffixes since all six are `.py`, and `test_a_removed_plan_key_stays_removed.py`
371 -> **377**, the same six, all under `tests/` or `workspace/`.
`test_interface_counts.py` did **not** move, reading **161** on both sides: the remediation
adds no tracked `.md`, and the one `.md` it touched by name — ADR-0055 renumbered to
ADR-0056 — is a rename and not an addition. 6 + 6 = 12.
**The two 6s are the same six files and are not one quantity counted twice.** One walk
selects by suffix and the other by tree, and they agree here because every file the
remediation adds is a `.py` under `tests/` or `workspace/`.
**The 1514 -> 1516 step is the SECOND remediation round of that branch, and it is tree
growth alone** — measured in this checkout on 2026-09-17, against the figures the paragraph
above records. That round adds **exactly one** tracked file,
`tests/scenarios/guards/test_expected_joint_names.py` (`git diff --diff-filter=A
--name-only 4f29761..HEAD` counts 1, with `--diff-filter=D` and `--diff-filter=R` both
**0**), and **no file at all under `tools/tests`**, so every case of the +2 is that one file
being counted by two other suites: `test_superseded_real_time_requirement.py` 403 -> **404**,
it being a `.py`, and `test_a_removed_plan_key_stays_removed.py` 377 -> **378**, it being
under `tests/`. `test_interface_counts.py` did **not** move, reading **161** on both sides
and for the third consecutive step, because the round adds no tracked `.md` — it edits
`docs/open-work.md`, `docs/adr/0056-*.md` and this file, and an edit is not an addition.
1 + 1 = 2. **This is the smallest step this bullet has ever had to close**, and it is a
guard whose own ten cases live under `tests/` and are therefore counted in the OTHER half,
below.

</details>

### Q15

- **Class:** C
- **Source:** `CLAUDE.md` lines 312-414 at `960e6b4`
- **Summary:** `tools/tests` collection history 902 -> 1399 and the tree-parametrized suites that make it grow.
- **Recommendation:** Delete.

<details><summary>Original text</summary>

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

</details>

### Q16

- **Class:** D
- **Source:** `CLAUDE.md` lines 415-424 at `960e6b4`
- **Summary:** The collection measures the size of the source and documentation trees, not coverage; collection and a run are different numbers.
- **Recommendation:** Move to docs/architecture/cross-cutting-testing.md as one sentence, or delete.

<details><summary>Original text</summary>

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

</details>

### Q17

- **Class:** B+
- **Source:** `CLAUDE.md` lines 425-464 at `960e6b4`
- **Summary:** First-party package roles: `cite_description`, `cite_twin`, `cite_test_hardware` outside charter section 7 (ADR-0040), `cite_runtime` (ADR-0034), the packages that do not exist; package counts.
- **Recommendation:** Move the role sentences to docs/architecture/README.md (or each package README); delete the counts.

<details><summary>Original text</summary>

- **Ten first-party packages exist**, and `workspace/src/external/` adds the twelve from
  `xarm_ros2`. **It said eleven until 2026-10-01**, when [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) removed `cite_orchestration` —
  charter §7's L4 package, the behaviour-tree line — from the main tree; it builds and runs
  only in the `projects/01` snapshot, and charter v1.15 marks its §7 line so. The instrument,
  `find workspace/src -name package.xml -not -path '*/external/*' | wc -l`, reads **10** in this
  checkout on 2026-10-01 on `feat/remove-parked-line`; `./scripts/doctor`'s `workspace/src` line
  reads **22** there, and `./scripts/build` reported `Summary: 22 packages finished` on that
  branch at `416ffc8` — **that summary is the `coder` agent's verbatim reading from its own run,
  not re-run by this pass**. Everything below in this bullet that says eleven, 23 or names
  `cite_orchestration` as present is that figure's history.
  `./scripts/build` is a blocking CI step. Seven of the ten are
  `cite_interfaces`, `cite_runtime`, `cite_facility`, `cite_generated`, `cite_bringup`,
  `cite_skills` and `cite_simulation`; until 2026-10-01 the list here was eight of eleven and
  included `cite_orchestration`. The next is
  **`cite_description`, added 2026-08-31** — charter §7's L1 package, created for the first
  thing that needed it. It holds **no code and no node**: it installs `assets/meshes` into its
  share directory so that a `package://` or `file://$(find cite_description)` URI resolves,
  and it is the only package permitted to install from `assets/`. Its admission test is in
  its own `package.xml`. The next is
  **`cite_twin`, charter §7's L5 package, which now exists** — the Phase 2.A bullet below is
  where what it does and does not do is kept, and it is not restated here. The last is
  **`cite_test_hardware`, which is test-only and deliberately not in charter §7's tree**:
  §7 is the production structure, and the package is barred from production use by its own
  `on_init` rather than by convention
  ([ADR-0040](../../docs/adr/0040-stop-a-joint-part-way-with-a-test-only-hardware-plugin.md),
  charter v1.8). So `cite_test_hardware` appearing on disk and not in §7's tree is the rule,
  not drift.
  `cite_runtime` holds process-lifecycle
  mechanism only — signals, shutdown, spin-and-exit for `rclpy` nodes — and exists rather
  than a helper landing in `cite_interfaces`
  ([ADR-0034](../../docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md), charter v1.7).
  **`cite_telemetry`, `cite_safety`, `cite_control` and
  `cite_hardware` do not exist**, and `cite_orchestration` is not in the main tree; those five
  plus the nine named above other than `cite_test_hardware` are the fourteen
  charter §7 lists (`cite_test_hardware` is not one of the fourteen). `cite_description` was
  in the does-not-exist list until 2026-08-31 and **`cite_twin` was in it until 2026-09-01**
  — this bullet said "ten first-party packages" and named five that do not exist while
  `workspace/src/cite_twin/package.xml` was committed and building. The instrument that
  settles it is `find workspace/src -name package.xml -not -path '*/external/*' | wc -l`,
  which reads **11** in this checkout on 2026-09-01.

</details>

### Q18

- **Class:** C
- **Source:** `CLAUDE.md` lines 465-482 at `960e6b4`
- **Summary:** `doctor`'s `workspace/src` line and `build`'s summary readings and history.
- **Recommendation:** Delete.

<details><summary>Original text</summary>

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

</details>

### Q19

- **Class:** C
- **Source:** `CLAUDE.md` lines 483-511 at `960e6b4`
- **Summary:** `./scripts/test` figures on 2026-10-01 (4ba6783, 35b254a, 416ffc8). Note: the newest reading (483) sits above an older one (491).
- **Recommendation:** Delete. Run the command.

<details><summary>Original text</summary>

**Re-taken again the same day at `4ba6783`, after the second remediation round, from one full
run with `docker ps` empty, exit 0, by the `fixer` agent**: `182 passed, 0 failed (shell gate
self-tests)`; `1635 passed, 1 skipped`; ten `Summary:` lines totalling **1220 tests, 0
failures, 33 skipped**. Both moves are attributed: the shell gate's +10 is the process-group
self-tests for `./scripts/program`'s pair, and the per-package +1 is
`test_an_interrupted_bring_up_is_not_a_refusal` in `cite_bringup`. The host half did not
move — that round adds no file under `tools/` or `tests/` — and the tie still closes at
1599 + 37 = 1636.
**Re-taken on 2026-10-01 on `feat/remove-parked-line` at `35b254a`, after that branch's
review remediation, from one full `./scripts/test` run with `docker ps` empty, exit 0, by the
`fixer` agent**: `172 passed, 0 failed (shell gate self-tests)`; `1635 passed, 1 skipped` for
the host half; and ten per-package `Summary:` lines totalling **1219 tests, 0 failures, 33
skipped**. **All three steps are attributed, because each was measured directly**: the shell
gate's +20 is the remediation's new self-test cases (undeclared, empty and named zones on
`sim`, `program` and `scenario`, `zones.py --check`, the install-prefix refusal, and the
belt stop in `./scripts/program`); the per-package +2 is two new cases in
`cite_bringup/test/test_simulation_launch.py`; and the host half's +5 is `tools/tests`' +2
above plus `tests/`' **34 -> 37** — the new guard's 2 cases and one more
`test_gz_calls_carry_the_partition.py` case, which parametrises over the `.py` files under
`tests/`. The tie closes: 1599 + 37 = 1636 = 1635 passed plus the 1 skipped.
**On 2026-10-01 on `feat/remove-parked-line`, at `416ffc8`, the `coder` agent took one full
`./scripts/test` run, exit 0, and reported these verbatim; this pass did not re-run it**:
`152 passed, 0 failed (shell gate self-tests)`; `1630 passed, 1 skipped` for the host half;
and **ten** per-package `Summary:` lines totalling **1217 tests, 0 failures, 33 skipped**.
**All three steps span ADR-0069's removal** — a package, its tests, three scenarios' guards
and the tests retargeted from three arms to one — **and none is reconciled term by term.**
**The host-half tie closes**, from two collections this pass took on that branch on that date:
`tools/tests` collects **1597** and `tests/` **34**, and 1597 + 34 = 1631 = 1630 passed plus
the 1 skipped. Everything below in this bullet is the history of these three figures.

</details>

### Q20

- **Class:** C
- **Source:** `CLAUDE.md` lines 512-589 at `960e6b4`
- **Summary:** `./scripts/test` figures 2026-09-17 to 2026-09-28, two disagreeing full runs, a `cite_orchestration` `test_skill_cancellation` timeout, the failing host test fixed rather than re-run.
- **Recommendation:** Delete. The `test_skill_cancellation` timeout belongs to a package that now lives only in the three-arm snapshot.

<details><summary>Original text</summary>

**`./scripts/test` counts by a run and reports three numbers, not one, and all three were
re-taken on 2026-09-17 from ONE full run**, over a working tree whose content is this
branch's second remediation round — which is what
it takes: a
`--host-only` run cannot refresh the third at all. `144 passed, 0 failed
(shell gate self-tests)`; `1676 passed, 1 skipped` for the host half, which walks `tools/`
**and**
`tests/`, so it is larger than the `tools/tests` collection above; and, over the eleven
first-party packages, eleven per-package summaries totalling **1523 tests, 0 failures, 61
skipped**. Its exit status was 0 and all eleven packages reported `100% tests passed`.
**Re-taken on `feat/let-go-when-clear` on 2026-09-28**, from one full run with `docker ps`
confirmed empty first and empty again after; `test_skill_cancellation` did not fire.
It read 144 / 1671 / 1499 on `feat/clamp-the-box` at `50a51a9` on 2026-09-24.
**TWO full runs were taken back to back and THEY DID NOT AGREE ON THEIR EXIT STATUS.** The
first exited 0. The second exited **1**, on `test_skill_cancellation (Timeout)` — 1 of 17 in
`cite_orchestration`, the **ctest** timeout, not an assertion. Re-run alone it passes in
**4.23 s**, which is the identical figure this bullet already records for that test at
`b072bfa`, so this is a **third** occurrence of a signature that is **attributed to nothing**.
This branch does not touch that package at all — `git diff --stat main..HEAD --
workspace/src/cite_orchestration` is empty. **The confound is named rather than left out**:
two full suites were run back to back on this host with several container starts between
them, and this bullet's own earlier entry for this signature carries the same kind of
confound.
**The failure also cost the third figure its instrument, which is worth one line.**
`scripts/test` prints the eleven per-package summaries in a loop AFTER
`colcon test --return-code-on-test-failure`, so a run that fails exits before reaching them
and prints none; the 1499 was reproduced by running that same loop by hand. The 61 skipped and
the 1 failure are that loop's, and the eleven summaries add to 1499 exactly.
It read 144 / 1649 / 1481 on `measure/is-a-run-reproducible` on 2026-09-22,
144 / 1638 / 1481 on `main` on 2026-09-18 with `cell_b` paired, and
144 / 1628 / 1435 at `7c6e902`.
**Only the host half moved, and the other two not moving is the property worth stating.** The
shell gate is untouched because the change adds no script; the per-package total is untouched
because it adds **no package test at all** — its whole content is one published campaign under
`docs/measurements`, which `./scripts/test` does not execute. **So a campaign is visible to
`lint` and to the `tools/tests` collection and invisible to the eleven packages**, and that is
a statement about what each instrument walks rather than about coverage.
**The per-package 1435 -> 1448 step is NOT attributed and is stated as what it is**: the
eleven `Summary:` lines carry no package name, and the two figures sit at non-adjacent
commits. What is checkable is that this change adds **no** package test — its only test edit
is one assertion in `tools/tests/test_generate.py` — so the +13 sits in the pair-boundary
work merged before it, which is a reason to expect it there and **is not a measurement of
it**.
**One host test failed on the first full run of this change and was fixed rather than
re-run**: `test_an_untwinned_zone_says_nothing_about_a_counterpart` joined every artifact
into one blob and asserted `"counterpart" not in` it, which asserted the property **and**
that no shipped zone is paired at all — and pairing `cell_b` removed the second premise while
the property held perfectly. Measured before touching it: of **48** generated artifacts
**exactly one** mentions a counterpart, `bringup/cell_b_plan.yaml`, the paired zone's own
plan, and **none** of `cell_a`'s 30 do. The assertion now takes the paired set from the model
and degenerates to the original `not in` on an all-`single` facility; it was mutation-checked
by treating that set as empty, where it fires. **This is the same breakage `per_zone` in that
file was written for, in a fourth assertion.**
**The host-half tie closes exactly, and it was predicted before it was measured** —
**the fourth time that has been done here, and the prediction was written into the session
before the run was started**: `tools/tests` collects **1569** and `tests/` **108**, and
1569 + 108 = 1677 = **1676** passed plus the 1 skipped, on `feat/let-go-when-clear`,
2026-09-28. It closed the same way at 1564 + 108 = 1672 on `feat/clamp-the-box` at `50a51a9`
on 2026-09-24, on **both** of that day's full runs, including the one that exited 1 on a
package test.
**One reading of this figure was taken against a tree that did not yet contain its own new
file, and the +2 it was missing is exactly this tie's arithmetic working.** A host half of
1669 + 1 was reported before
`workspace/src/cite_bringup/test/test_release_confirmation_launch.py` was tracked; once it
was, `test_superseded_real_time_requirement.py` and `test_a_removed_plan_key_stays_removed.py`
each gained one, 1670 + 2 = 1672. The figure was never wrong — it belonged to a different
tree, which is the distinction this whole section is about.
It read 1542 + 108 = 1650 = 1649 plus the 1 skipped on 2026-09-22, and 1531 + 108 = 1639 =
1638 plus the 1 skipped on `main` on 2026-09-18.
**`tests/` did not move**, collecting 108 at both, because the change adds no file under it.
**The 1523 -> 1531 step is +8, it is tree growth alone, and it closes exactly.** This branch
adds **5** tracked files and no case to `tools/tests`: two `.md` — a campaign `criteria.md` and
ADR-0060 — which only `test_interface_counts.py` counts, at +1 each; and three `.hpp`/`.cpp`
under `workspace/`, which `test_superseded_real_time_requirement.py` counts by suffix and
`test_a_removed_plan_key_stays_removed.py` counts by tree, at +3 each. 2 + 3 + 3 = 8.
**The two 3s are the same three files and are not one quantity counted twice** — one walk
selects by suffix and the other by tree. It read 1521 + 108 = 1629 = 1628 + 1 at `7c6e902`. **`tests/` did not move**,
collecting 108 at both.

</details>

### Q21

- **Class:** D
- **Source:** `CLAUDE.md` lines 590-596 at `960e6b4`
- **Summary:** The per-package total was nearly published as arithmetic; `flake8` runs only in the container, so the host half cannot see it.
- **Recommendation:** Promote as a rule ("measure a figure, never derive it"), or move to docs/architecture/cross-cutting-testing.md.

<details><summary>Original text</summary>

**The per-package total is the one figure here that was nearly published as arithmetic**, and
the episode is worth keeping. It was reasoned about as 1432 + 3 from an earlier run, and a
re-review caught that the newest full log on that host predated the commits it was being
attributed to. Measuring it instead **failed on `flake8`** — a 104-character line in a
documentation correction, invisible to the host half because the ROS package linters run only
in the container. The line was fixed and the run retaken; 1435 is a reading. **This is the
mechanism by which this section has acquired a wrong count four times, caught on the fifth.**

</details>

### Q22

- **Class:** B+
- **Source:** `CLAUDE.md` lines 597-608 at `960e6b4`
- **Summary:** `./scripts/enter dev ./scripts/test` attaches with `compose exec`, skips the entrypoint, and runs no test at all; a live defect in `scripts/_lib.sh`.
- **Recommendation:** Move to docs/operations/troubleshooting.md and open a docs/open-work.md item; it is a live tooling hazard, not history.

<details><summary>Original text</summary>

**THAT RUN WAS TAKEN AS `./scripts/enter dev ./scripts/test` AND NOT AS `./scripts/test`,
and the difference is not cosmetic.** `exec_in_container` reuses a running container with
`compose exec` when one of the service is up, and `docker exec` does **not** run the image's
entrypoint — which is what sources `/opt/ros/jazzy/setup.bash` and the overlay. Attached to
a `dev` container another session had left running, `PYTHONPATH` was **unset** and every
ctest invocation died on `ModuleNotFoundError: No module named 'ament_cmake_test'`: **0 of
11 packages passed, three runs running**, with the `flake8`, `pep257` and `copyright` meta
tests among the casualties, and nothing of ours was executed at all. The same eleven
packages pass 11 of 11 through `compose run`, which does run the entrypoint. So **a `test`
reading taken while any `dev` container is up is not a reading of this repository**; check
`compose ps --services --status running` before believing one. The defect is
`scripts/_lib.sh`'s `compose exec` branch and it is not fixed here.

</details>

### Q23

- **Class:** C
- **Source:** `CLAUDE.md` lines 609-780 at `960e6b4`
- **Summary:** Shell gate, `tests/` half and per-package total histories and their reconciliations.
- **Recommendation:** Delete.

<details><summary>Original text</summary>

`./scripts/test` builds and tests the eleven only — the
twelve imported packages are built and not tested here. The three read 113 / 367 / 854 on
2026-08-29, 124 / 447 / 962 on 2026-08-31, 124 / 938 / 1217 earlier on 2026-09-01,
124 / 963 / 1221 later the same day, 124 / 1009 / 1250 until 2026-09-08,
124 / 1075 / 1250 for a few hours of that day, 124 / 1092 / 1250 for a few hours more,
124 / 1445 / 1296 for a few hours after that, 124 / 1446 / 1296 until 2026-09-10,
124 / 1468 / 1363 until 2026-09-16, 124 / 1571 / 1364 until 2026-09-17 and
135 / 1610 / 1414 for part of that day.
**The shell gate's 124 -> 135 is the first move that figure has made since 2026-08-31**, and
it is entirely `./scripts/sim`'s argument parsing: **eleven** cases for `--zone` — absent,
dangling, swallowing the next flag, given a launch argument instead of a name, and two
spellings naming different zones in either order — **five of the eleven asserting on the
DIAGNOSIS rather than on the exit status**, because a refusal that does not say which flag
or which zone sends the reader nowhere. Every one of them exits before `require_ros_env`, so
the self-test starts no cell and no container. 124 + 11 = 135.
**The 135 -> 144 step is the same parsing question asked of `./scripts/scenario`**, whose
`--zone` had none of those guards: **nine** cases, **four** of them asserting on the
diagnosis. They cover the two silences the second remediation round closed — `--zone`
swallowing `--teardown-advisory`, which set the zone to that flag AND left the teardown
policy gating, and an empty `--zone=`, which fell back to the default the caller had just
overridden. 135 + 9 = 144.
**What discriminates is the diagnosis and that was measured, not assumed**: with the
refusals stripped out, every `expect_fail` in the new block still passes — the run fails
downstream instead — and only the message assertions fail. The `expect_fail` half is kept
for what it does pin, which is that a refusal EXITS rather than warning.
**The host half ties to the collection above, and the tie is checked at THIS commit rather
than differenced against the last recorded one.** `tools/tests` collects **1516** here and
`tests/` **108**, and 1516 + 108 = 1624 = 1623 passed plus the 1 skipped.
**It was predicted before it was measured and it held** — the arithmetic was written down
off the two collections and a full run then read 1623. It said 1514 / 97 / 1611 / 1610 until
the second remediation round of 2026-09-17.
**The 1610 -> 1623 step is +13, and BOTH halves moved.** `tools/tests` moved **+2**, as
reconciled above. `tests/` moved **97 -> 108**, **+11**, measured in this checkout on
2026-09-17 by `--collect-only -q | sed 's/::.*//' | sort | uniq -c`: **+10** is
`test_expected_joint_names.py`, a new guard holding `bringup`'s expected joint names to the
plan's asset ids, and **+1 is tree growth of the same kind the `tools/` half shows** —
`test_gz_calls_carry_the_partition.py` 15 -> **16**, because it parametrises over the `.py`
files under `tests/` and that guard is one. 10 + 1 = 11, and 2 + 11 = 13.
**The `tests/` half moved 70 -> 97 and closes exactly**, measured in this checkout on
2026-09-17 by `--collect-only -q | sed 's/::.*//' | sort | uniq -c`. **+16** is
`test_continuous_line_ladder.py` 16 -> **32** and **+5** is
`test_place_assertion_sees_height.py` 5 -> **10**: both stopped naming `cell_a`'s artifacts
and now parametrise over every zone the generated tree declares, so each zone-dependent case
became two and each gained one tripwire for the parametrisation collecting nothing. **+4** is
four new cases in `test_scenario_modules_load.py` holding the driven zone to one statement.
**+2 is tree growth of the same kind the `tools/` half shows**:
`test_gz_calls_carry_the_partition.py` 13 -> **15**, because it parametrises over the files
under `tests/` and two were added there. 16 + 5 + 4 + 2 = 27.
**The per-package 1364 -> 1414 step, +50, is stated and NOT reconciled**, for the reason
this bullet already gives: the eleven `Summary:` lines carry no package name, so the log
cannot attribute a test to a package, and attributing it would need a full run at the base
as well, which was not taken. What is checkable is that the remediation changes tests in
**`cite_facility`, `cite_bringup` and `cite_twin` only** (`git diff --stat f7aed46..HEAD --
'workspace/src/*/test/*'`), which is a reason to expect the move to sit there and **is not a
measurement of it**. **Thirty-nine of the 50 are attributed, because they were measured
directly**: three new files collect **11**, **12** and **6** cases
(`test_a_node_without_a_zone_refuses.py`, `test_one_zone_at_a_time.py`,
`test_the_boundary_needs_a_zone.py`, each collected in the container), and **5**, **3** and
**2** cases were added to `test_artifacts.py`, `test_simulation_launch.py` and
`test_pair.py`. **The remaining 11 is not attributed and was not chased**: a ctest
per-package total and a pytest collection are different instruments, and guessing which
accounts for the difference is exactly what the rule above forbids. **The 1468 -> 1571
step is deliberately NOT reconciled**, because the two figures sit at commits four apart —
1468 was taken at `523ffd9` and this at `f7aed46` — and two commits landed in between that
this work did not measure. What IS reconciled, in the collection bullet above, is
1468 -> 1502 over this branch alone, against a worktree at its base `1adf0cf`.
**Differencing two figures taken at non-adjacent commits is how a number gets attributed to
the wrong change**, and the collection bullet above already records one unresolved +1 from
exactly that habit.
**The per-package total's 1414 -> 1415 step IS attributed, because it was measured
directly**, which is the exception this bullet's standing rule allows rather than a
weakening of it: the second remediation round adds exactly one package test, the
planning-scene loader's declared-default check, to
`cite_facility/test/test_a_node_without_a_zone_refuses.py`, and that file collects **11 ->
12** in the container. Nothing else under `workspace/src/*/test/*` changed but the same
file's refusal assertion, which is a rewrite of an existing case and not a new one
(`git diff --name-only 4f29761..HEAD -- 'workspace/src/*/test/*'` names that one file).
**The per-package total's 1363 -> 1364 step is stated and NOT reconciled**, for the standing
reason: the eleven `Summary:` lines carry no package name, so the log cannot attribute a
test, and attributing it would need a full run at `1adf0cf` as well, which was not taken.
What is checkable is that this branch adds **no** package test at all — its `workspace/src`
changes are `cite_generated`, four `cite_facility` nodes, `cite_bringup`, `cite_twin` and
no test file (`git diff --name-only 1adf0cf..HEAD -- 'workspace/src/*/test/*'` is empty) —
so the +1 sits somewhere in the two commits between `523ffd9` and `1adf0cf`
and not in this work. That is a reason to expect it there and **is not a measurement of
it**.
**A full run on this branch before those fixes exited 1**, and it is recorded because a
failure this file does not mention is one the next reader re-discovers. Two `cite_twin`
launch tests failed — `test_twin_boundary_launch.py` and, on its ctest timeout,
`test_twin_boundary_paired_launch.py` — because making `--zone` unconditionally required
broke the two rigs that start the boundary with `--plan` and no zone; that is fixed at
`1314022` and both pass in the run above. `cite_orchestration` also failed in that run and
**passed in the run above with no change whatever to it**. **Which of its tests failed was
not read** — the run was cut short at its summary line — so it is recorded as an unattributed
failure and NOT as another instance of the `test_skill_cancellation` timeout this bullet
records at `b072bfa`, however alike the two look. **A build and a container lint were
running on the same host while it failed**, which is a confound the reader should know
about and **is not an attribution** either.
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

</details>

### Q24

- **Class:** D
- **Source:** `CLAUDE.md` lines 781-787 at `960e6b4`
- **Summary:** The per-package total is a hand sum `test` does not print; a `--host-only` run cannot refresh it.
- **Recommendation:** Move to docs/architecture/cross-cutting-testing.md.

<details><summary>Original text</summary>

**The per-package total is a sum this file performs and `test` does not print**: the script
emits one `Summary:` line per package and no grand total, so the 1296 and the 56 were
added up by hand from the eleven lines. The two host figures are printed verbatim. **A
`--host-only` reading cannot refresh the third figure at all**, which runs the same two host
suites and stops there: that is why the per-package total carried 2026-09-02's date through
2026-09-08's `--host-only` reading at `b6ab34a`, and why the three above were taken from one
full run instead.

</details>

### Q25

- **Class:** B+
- **Source:** `CLAUDE.md` lines 788-825 at `960e6b4`
- **Summary:** Bring-up drives lifecycle transitions by request and confirmation (ADR-0058); its clause 1 is deliberately open; the harness defect #72.
- **Recommendation:** Delete. Summarised in the new section 2; ADR-0058, docs/architecture/cross-cutting-lifecycle.md and docs/open-work.md #72 hold it.

<details><summary>Original text</summary>

- **Bring-up now drives its lifecycle transitions by asking and confirming, and a stalled
  facility node stops the cell instead of misleading it**
  ([ADR-0058](../../docs/adr/0058-drive-lifecycle-transitions-by-request-and-confirmation.md),
  merged 2026-09-18). `cite_bringup/lifecycle_driver.py` takes each `cite_facility` managed
  node through `configure` and `activate` by calling `change_state` and **confirming with
  `get_state`**, and **everything downstream of the facility nodes is gated on its exit** —
  the controllers and the planners (and the detection server, until it left the main tree with
  ADR-0069 on 2026-10-01).
  **The rule that carries it: the confirmation is the gate, not the response.** A service
  reply can be dropped exactly as a broadcast can, and `get_state` is idempotent and
  re-askable, so asking again is free and correct. The shape was already in the tree —
  `cite_facility/planning_scene_loader.py` calls a service, reads the response and then
  confirms with a second read-only query, for the same reason one layer up.
  **What it replaced was a silent loss.** Activation used to be triggered by a launch event
  `launch_ros` derives from a **subscription** to `transition_event`; both endpoints are
  RELIABLE + VOLATILE, and reliable is a promise to **matched** subscribers only, so a
  transition published before that subscription matched was dropped and never re-sent. The
  node then sat in `inactive` publishing no TF, bring-up carried on for ten seconds, and the
  launch died **naming frames and the planning scene** — pointing the reader at the model,
  which was not the cause. That is CLAUDE.md §10's own first bullet, inside upstream
  plumbing, and it was **pre-existing**: `_managed` was byte-identical on `main`, and the
  stall reproduced on `cell_a` and in a Gazebo-free three-node harness.
  **ADR-0058 is `Proposed` and its promotion clause 1 is deliberately open. NOBODY MAY WRITE
  THAT THE STALL STOPPED REPRODUCING.** The experiment that would show it is underpowered on
  the host it was run on: the **control** arm — the arm whose job is to prove the stall can
  still be produced — fired **1 of 45** loaded and **0 of 35** unloaded, against recorded
  before-figures of 4 of 45 and 2 of 35. A treatment arm of 0 of 80 against a control that
  barely fires is consistent with a working fix **and** with a quiet afternoon, and the
  `tester` declined to close the clause on it. **What IS evidenced** is the mechanism — there
  is no transition event left to lose — and the failure path, observed end to end: a node that
  never answers produces a diagnosis naming **that node and that step**, the gate fires, and
  nothing downstream starts.
  **The harness that measures this has a defect of its own**, recorded in
  [`docs/open-work.md`](../../docs/open-work.md) #72: its probe re-drives the transition part-way
  through a trial, which makes the node publish and the trial's own success check match, so a
  stalled trial is counted as a pass. The before-figures are therefore **lower bounds taken
  with an instrument that rescues what it counts**, and anyone re-running clause 1 needs that
  before they compare.

</details>

### Q26

- **Class:** B+
- **Source:** `CLAUDE.md` lines 826-837 at `960e6b4`
- **Summary:** The simulated cell comes up: what `./scripts/sim` starts on `cell_b`; scenarios `bringup` and `program_cycle`.
- **Recommendation:** Delete. Summarised in the new section 2; docs/operations/bring-up.md is the runbook.

<details><summary>Original text</summary>

- **The simulated cell comes up.** `./scripts/sim --headless` — `--zone` defaults to the one
  zone L0 declares, `cell_b` — brings its scene and its one arm, `picker`, on its linear track,
  into Gazebo Harmonic with the controllers the generated plan declares for it active (four:
  joint-state broadcaster, gripper, arm and track trajectory controllers), one `move_group`
  and one skill server, the generated planning scene applied and read back, the facility's
  model version and frames served, and one `ros_gz_bridge` carrying `/clock` plus every belt
  and beam topic the generated plan declares. **There is no detection server, no topology
  server and no L4 coordinator, and `line:=true` is gone**: all of them left the main tree with
  [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) on 2026-10-01 and run in the `projects/01` snapshot. `./scripts/sim --pair` brings both
  sides of `cell_b` up, and the twin boundary with them. `./scripts/scenario bringup` asserts
  the single-side bring-up on `cell_b` and is a blocking CI gate, run twice per CI run;
  `program_cycle` is the other blocking scenario and there is no third.

</details>

### Q27

- **Class:** D
- **Source:** `CLAUDE.md` lines 956-960 at `960e6b4`
- **Summary:** Commit-message trap: a whole-log grep counts figures and verdict strings quoted in echoed commit bodies.
- **Recommendation:** Move, with items on lines 1020-1071, into one "reading a CI log" note in docs/architecture/cross-cutting-testing.md.

<details><summary>Original text</summary>

**The commit-message trap fired on the way to this reading and is worth one line.** A
whole-log grep for the host test figure returns `1610` as well as `1623`, because the `Build
image` step echoes the pushed commit bodies and those bodies quote earlier figures. Only the
`Test` step's `1623 passed, 1 skipped` is a reading. Same hazard the `bringup` bullet
records for verdict strings, in a different string.

</details>

### Q28

- **Class:** D
- **Source:** `CLAUDE.md` lines 1020-1040 at `960e6b4`
- **Summary:** The verdict instrument: a prefix grep cannot tell `passed` from `passed its cycle assertions`; match whole lines anchored; restrict to the scenario step column.
- **Recommendation:** Move to the "reading a CI log" note (see the item on lines 956-960).

<details><summary>Original text</summary>

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

</details>

### Q29

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1041-1047 at `960e6b4`
- **Summary:** The two current scenario step names in `ci.yml`; `program_cycle` blocking since 2026-09-29.
- **Recommendation:** Move to the "reading a CI log" note; the step names are read from `.github/workflows/ci.yml`.

<details><summary>Original text</summary>

**There are TWO such step names as of 2026-10-01**, on `feat/remove-parked-line`:
`grep -n "Simulation-in-the-loop" .github/workflows/ci.yml` returns `Simulation-in-the-loop
scenarios` (both `bringup` invocations) and `Simulation-in-the-loop scenario — program_cycle`
— **with no `(advisory)` suffix**, because that step has been blocking since 2026-09-29, and
this file carried the stale `(advisory)` name until 2026-10-01. The `pick_and_place` and
`continuous_line` steps left with ADR-0069, so the instrument below reads the CI runs that
had them and not the ones after.

</details>

### Q30

- **Class:** D
- **Source:** `CLAUDE.md` lines 1051-1071 at `960e6b4`
- **Summary:** The whole instrument (awk over the step column), the fourth matching string that is not a verdict, why the over-count did not fire.
- **Recommendation:** Move to the "reading a CI log" note.

<details><summary>Original text</summary>

**There were three such step names, not one, and this file named only the first until
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

</details>

### Q31

- **Class:** D
- **Source:** `CLAUDE.md` lines 1088-1089 at `960e6b4`
- **Summary:** Treat a `bringup` failure as a finding to investigate, not a flake to re-run past.
- **Recommendation:** Promote, generalised to every scenario, as a CLAUDE.md rule (`.github/workflows/ci.yml` already says it of `program_cycle`). Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules", generalised to every scenario. The verbatim text stays here.

<details><summary>Original text</summary>

Treat a `bringup` failure as a finding to
investigate, not as a known flake to re-run past.

</details>

### Q32

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1090-1103 at `960e6b4`
- **Summary:** Motion is planned by Pilz with OMPL fallback on planning failure only; what is and is not proven (ADR-0027).
- **Recommendation:** Delete. Summarised in the new section 2; ADR-0027 and docs/architecture/L3-capabilities.md hold it.

<details><summary>Original text</summary>

- **Motion is planned by Pilz.** ADR-0027 is implemented and merged: L0 declares the
  pipeline choice and the limits, the generator emits `<zone>_<arm>_planning_pipelines.yaml`
  per arm declaring both pipelines (today one file, `cell_b_picker_planning_pipelines.yaml`; it
  named `cell_a_arm_*` here until 2026-10-01), and the L3 skill server asks for Pilz PTP and falls back
  to OMPL **only** on a planning failure — never on an unreachable pose, and never when the
  requested planner is a Cartesian one, where the shape of the path is the contract.
  **What is proven:** an identical request returns a byte-identical trajectory from one
  `move_group`, and a PTP path through a named object in the real generated planning scene
  is refused — mutation-checked, and observed refusing a real path during `continuous_line`.
  **What is not:** same seed, same trajectory *across runs*. **LIN is configured and usable
  on one motion shape only**, and nothing in L3 asks for it. That, the measurement, and the
  fact that no error code tells a collision refusal from a geometric one are in
  [ADR-0027](../../docs/adr/0027-pilz-planning-pipeline.md)'s 2026-08-27 correction; the gate's own
  residual is in the gap list below.

</details>

### Q33

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1104-1130 at `960e6b4`
- **Summary:** The arm takes the short way round (ADR-0060); a measurement on a pick-and-place cycle; two collision-coverage gaps #80/#81. STALE: "what unwinds this cell's arm is `MoveToHome` at both ends of every cycle" was written for the pick-and-place cycle; whether the real program unwinds the arm is unverified.
- **Recommendation:** Delete; ADR-0060 holds it. Re-check the `MoveToHome` sentence against the real program (it is also in ADR-0060's index row).

<details><summary>Original text</summary>

- **The arm takes the short way round to a pose, and it did not before**
  ([ADR-0060](../../docs/adr/0060-take-the-ik-solution-nearest-the-arm.md), 2026-09-21). `joint1` and
  `joint5` are declared over ±2π, so every reachable pose has a **wound twin 360° away and both
  are legal** — legal in the model, to `setFromIK`, to `setJointValueTarget` and to the runtime
  limiter. `plan_to_pose` returned on the **first seed that planned** and compared nothing, and
  `KDLKinematicsPlugin` restarts randomly inside its own timeout, so even the current-state seed
  could come back wound. **Nothing anywhere preferred the nearer of two identical postures.**
  The project owner watched the consequence: the arm picked a box off the table and handed it to
  the belt by swinging almost all the way round the back, standing at `joint1 = 5.253 rad`
  (**301°**) at a pose reachable at **-59°**.
  An IK solution is now shifted by whole turns toward the configuration the arm stands in, inside
  that joint's own declared limits, and verified to be a whole multiple of 2π.
  **Measured after, on a running cell**: over a full pick-and-place cycle sampled at the
  joint-state topic, 20 626 samples, `picker_joint1` spans **[-59.0°, +57.7°]**, a range of
  **116.8°** — and those two extremes are the azimuths L0 puts the pick table and the belt at, so
  the arm crosses directly between them. The widest excursion of any joint from zero was 147.7°,
  inside half a turn. **One run, one machine, nothing registered in advance. That is not a rate.**
  **It guarantees per-move minimal travel and NOT an unwound arm**, and the difference matters:
  a cell whose stations all sat at negative arm-frame angles could keep an arm wound indefinitely
  with every individual move still minimal. What unwinds this cell's arm is `MoveToHome` —
  `joint1 = 0`, absolute, never routed through IK — at both ends of every cycle.
  **Two collision-coverage gaps the shorter arc newly exercises are recorded and not fixed**, by
  owner decision: the held work-piece is attached to nothing so the gate cannot see it, and the
  new arc crosses the azimuth of the 40 mm housing ADR-0027's sampling residual is about.
  `docs/open-work.md` #80 and #81. **Neither is a predicted collision** — both are regions newly
  entered and unmeasured, and what checks them today is that the scenarios assert where the
  work-piece ends up.

</details>

### Q34

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1131-1142 at `960e6b4`
- **Summary:** `Place.Result.still_holding`: a `Place` that aborts says the arm is still holding the part; nothing decides what to do with a held part (ADR-0038 decision 5).
- **Recommendation:** Delete. docs/architecture/L3-capabilities.md and the interface reference hold it.

<details><summary>Original text</summary>

- **A `Place` that aborts now says the arm is still holding the part.** `Place` opens the jaws
  at a step *after* the descent, so a descent that aborts leaves them shut — and until
  2026-09-21 nothing could say so: `Place.Result` had no custody field where `Transfer` and
  `Pick` both do, and L4's "still holds work-piece" sentence sat behind a `would_retry` test
  that is **false** for `MOTION_INTERRUPTED`, because that code already escalates. So for the
  one failure it was written for, the sentence was never written. `Place.Result.still_holding`
  is now filled at every exit and is **true when custody is unknown**, which is the direction
  the field's own contract demands; the blocked reason names the held piece whatever the
  recovery; and `Transfer` carried the identical defect and was fixed with it.
  **Nothing opens the jaws, and nothing decides what to do with a held part** — that is
  ADR-0038 decision 5 and it stays open. **The failure this was built for is `docs/open-work.md`
  #60**, which now records a third occurrence, on `cell_b`, kept apart from the `cell_a` counts.

</details>

### Q35

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1143-1159 at `960e6b4`
- **Summary:** Execution-side trajectory tolerances (ADR-0036): a detector, not a protective measure; values copied from UFACTORY.
- **Recommendation:** Delete; ADR-0036 holds it. "A detector is not a protective measure" could join docs/architecture/cross-cutting-safety.md if it is not there.

<details><summary>Original text</summary>

- **A mistracked trajectory is now detected at execution, and the detector's own values are
  copied rather than measured.** Every generated `JointTrajectoryController` carries a
  `constraints:` block — `goal_time`, and per-joint `trajectory` and `goal` tolerances —
  declared on the arm type in L0 and identical on both backends
  ([ADR-0036](../../docs/adr/0036-execution-side-trajectory-tolerances.md)). Until it existed every
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

</details>

### Q36

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1160-1185 at `960e6b4`
- **Summary:** An execution abort is classified in L3 before any recovery motion (ADR-0037); the abort fixture (ADR-0040).
- **Recommendation:** Delete. ADR-0037, ADR-0040 and docs/architecture/L3-capabilities.md hold it. Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules": ADR-0037 is binding and violating it is an `ESCALATE` (ADR-0048 clause 1 is listed beside it, its own status block saying the same).

<details><summary>Original text</summary>

- **An execution abort is classified before any recovery motion is dispatched**
  ([ADR-0037](../../docs/adr/0037-classify-an-abort-before-any-recovery-motion.md), binding —
  violating it is an `ESCALATE`). `ResultCode` gained `MOTION_INTERRUPTED = 10`, defined in
  world terms — the arm stopped part-way and is holding position — with policy row
  `ESCALATE`; `EXECUTION_FAILED` narrowed to the two endpoint cases. The classification is a
  free function in **L3**, `cite_skills::classify_execution_failure`, computed from the plan
  and the joint state rather than from any L2 error code, so it holds for any robot type
  (P9) and is identical on both backends (P2). **The reset half left the main tree with
  ADR-0069 on 2026-10-01**: `ResetStation.srv` and the `cite_orchestration` server that answered
  it — commanding no motion — run only in the `projects/01` snapshot, and so does
  `recovery_policy.hpp`, the line's table that maps `MOTION_INTERRUPTED` to `ESCALATE`. The L3
  classification is unaffected, and the twin boundary still ranks `MOTION_INTERRUPTED` when it
  merges two sides' results (`cite_twin/twin_boundary.py`). Every row of the classifier is unit-tested in
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

</details>

### Q37

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1205-1210 at `960e6b4`
- **Summary:** P10 has an automated check (ADR-0035), chosen against the v1 tree.
- **Recommendation:** Delete. ADR-0035 holds it.

<details><summary>Original text</summary>

- **P10 has its first automated check** ([ADR-0035](../../docs/adr/0035-check-the-english-only-rule-by-character-signal.md)).
  `./scripts/lint` fails when a text file in this checkout contains a letter specific to a
  language
  other than English — six Turkish-specific letters plus nine non-Latin script ranges, chosen
  by measuring four candidate instruments against the archived v1 tree, where this one catches
  **17 of 17** first-party files. It runs in the host half of `lint`, the half that always

</details>

### Q38

- **Class:** C
- **Source:** `CLAUDE.md` lines 1211-1346 at `960e6b4`
- **Summary:** English-check walk counts (`files checked`) and their history.
- **Recommendation:** Delete. Run `./scripts/lint`.

<details><summary>Original text</summary>

runs, and reported **`2002 files checked, no non-English content outside 1 exemption(s)`** on
`feat/remove-parked-line` at `35b254a`, 2026-10-01, after that branch's review remediation —
**+1, the one tracked file it adds**, the guard the collection above counts, with the same
untracked files still on disk. It reported **`2001 files checked`** earlier that day,
**5** of them untracked — the same five as below,
re-derived by differencing `cite_tools.english.files_to_check` against `git ls-files` — so
**1996** were tracked. **The 2091 -> 2001 step spans ADR-0069's removal of the line,
`cite_orchestration`, `cell_a`'s generated artifacts and the documents' and tests' edits, and
is not reconciled term by term.** It reported `2091 files checked` on
`feat/projects-snapshots`, 2026-09-30, **5** of them untracked (the 3 below plus two
`real-robot-code/` archives), so a clean clone reports **2086**. **The step from 2045 spans
several branches and is not reconciled here.**
It reported `2045 files checked` on
`feat/let-go-when-clear`, 2026-09-28 — **+5, the same five tracked files the collection above
reconciles**, with the same 3 untracked still on disk, so a clean clone reports **2042**.
It read `2040 files checked` on `feat/clamp-the-box` at `50a51a9`, 2026-09-24.
**The 2034 -> 2040 figure is NOT a +6 step and must not be read as one**, which is the whole
reason this bullet distinguishes what is on disk from what is committed. `main`'s clean-clone
walk is **2034**, measured the same day in a worktree; this branch adds **3** tracked files, so
a clean clone of it reports **2037**; and this checkout reports 2040 because the same **3**
untracked files this bullet already records are still on disk — the two gitignored campaign
binaries and `assets/scans/raw/scan 1 room scan.e57`. 2037 + 3 = 2040. Both ends were derived
by differencing `cite_tools.english.files_to_check` against `git ls-files` rather than carried
forward.
**A 32-file scratch directory was in this walk earlier the same day and had to be moved out
before the figure could be taken.** `tools/cite_tools/tree.py`'s `SKIP_NAMES` holds exactly
`.git`, so `.git/info/exclude` keeps a directory out of git and **not** out of `lint`; the
first reading of this branch was 2072 and it was wrong by exactly those 32. That is the second
time this has happened here, and the first is recorded three paragraphs down.
It read **2033** on `measure/is-a-run-reproducible` on 2026-09-22 and **1972** on `main` on
2026-09-18 with `cell_b` paired.
**The 1972 -> 2033 step is +61 and closes exactly, and it is the first move in six to have a
campaign in it.** `git diff --diff-filter=A --name-only 79b1acd..HEAD` counts **61** tracked
files added, with `--diff-filter=D` and `--diff-filter=R` both **0**, and **all 61 are under
`docs/measurements`** — one published campaign's criteria, harness, write-up and raw records,
and nothing else. **That figure was written here as "57 of the 61" and corrected on the same
pass by running the grep**, which is this section's own rule working at the scale of one
clause. The same **3** untracked files are still on disk and are the same three as before,
re-derived here by differencing `cite_tools.english.files_to_check` against `git ls-files`
rather than carried forward. **A clean clone therefore reports 2030.**
**This is the arithmetic demonstration this bullet exists for**, from the sharpest direction
it has had: the same change moves this walk by **61** and the `tools/tests` collection above
by **11**, because 50 of the files are raw records under `docs/`, which the collection's tree
walk does not reach and this one does. **It measures how much evidence is committed and is
not a measure of coverage.**
It said `1972 files checked` until 2026-09-22. **The 1965 -> 1967 step is +2 and both are `.md`** —
`docs/adr/0057-…md` and `docs/adr/0059-…md`, the same two files that moved the collection
above — with nothing under `docs/measurements`, which makes **six** consecutive moves with no
campaign in them. **Pairing a zone moves this figure not at all**: it modifies two generated
artifacts and adds no file. **Exactly 3 of those 1967 are untracked** — the two
gitignored campaign binaries this bullet already records, plus
`assets/scans/raw/scan 1 room scan.e57`, a raw capture moved out of the repository root and
deliberately left out of git (`assets/README.md`'s storage policy) — re-derived by
differencing `cite_tools.english.files_to_check` against `git ls-files` rather than carried
forward — re-derived again here on 2026-09-18 by differencing `files_to_check` against
`git ls-files`, which named the same three and no others. **A clean clone therefore reports
1964**, and it reported 1962 at `7c6e902`.
**The previous reading was 1979 and it was NOT reproducible, which is why it is retired
rather than differenced against.** It was taken while a concurrent debugging session was
writing a `.dbg/` directory into the walk: 21 untracked, 18 of them that session's, and the
same tree then read 1980, 1999 and 1999 again with **no commit between any of them**. Nothing
is reconciled across that reading, and nothing should be.
It said **661** until 2026-08-29, **1048**
until
2026-08-31, **1085** earlier on 2026-09-01, **1267** later that day, **1430** until
2026-09-02, **1540** until 2026-09-08, **1928** and then **1930** for parts of that day,
**1931** until 2026-09-10, **1936** until 2026-09-17 and **1961** for part of that day.
**The 1936 was stale for the whole of this branch and nothing here caught it**, which is
worth one line because the branch re-derived every neighbouring count in this section and
not this one. A reviewer found it by running `lint`, which is the only way any of these has
ever been found.
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
**The 1936 → 1961 move is +25 and closes exactly, in the two parts this bullet's caveat
requires.** `git diff --diff-filter=A --name-only 523ffd9..HEAD` counts **24** tracked files
added — fourteen of them the artifacts one declared zone emits, the rest source and one ADR,
**none** under `docs/measurements` — with `--diff-filter=D` and `--diff-filter=R` both **0**.
That is 1934 + 24 = **1958** tracked. The other **+1 is a third untracked file**: the project
owner's raw LiDAR capture under `assets/scans/raw/`, Phase 3 material which
`assets/README.md` keeps out of git. 1958 + 3 = 1961. **So four consecutive moves have now
added nothing under `docs/measurements`**, and this is the first whose additions are mostly
GENERATED — which is the same lesson from a new direction: declaring one zone in `model/`
moves this figure by fourteen without anybody writing fourteen files.
**The 1961 -> 1979 move is +18 and only ONE of the eighteen is this repository's**, which is
why the in-checkout reading is retired above in favour of the clean-worktree one. The second
remediation round adds **1** tracked file,
`tests/scenarios/guards/test_expected_joint_names.py` (`git diff --diff-filter=A
--name-only 4f29761..HEAD`, with `--diff-filter=D` and `--diff-filter=R` both **0**). The
other **+17** is a concurrent debugging session's `.dbg/` directory arriving in the walk
while this was being measured, and it was **18 files by the time the container run read it**
— a number that was still moving. Nothing under `docs/measurements` was added, which makes
this the **fifth** consecutive move with no campaign in it.
**A superlative was drafted here and withdrawn on checking, which is the reason to say so.**
It read *"the first in this bullet's history that is entirely source"*, and the move
immediately above it — 1928 → 1930, `df91154` — was **two added tracked `.py` files and
nothing else**, so it is more entirely source than this one, which carries an ADR among its
five. The paragraph above records those two files, in this same file, four paragraphs up.

</details>

### Q39

- **Class:** D
- **Source:** `CLAUDE.md` lines 1347-1380 at `960e6b4`
- **Summary:** The walk counts what is on disk, not what is committed; `.git/info/exclude` keeps a file out of git and not out of `lint`.
- **Recommendation:** Move the on-disk point to docs/onboarding/getting-started.md (or leave it to `tools/cite_tools/tree.py`'s docstring); delete the counts.

<details><summary>Original text</summary>

**This figure counts what is on disk, not what is committed, and this bullet said "a tracked
text file" until 2026-09-08.** The remit is an `os.walk` from the repository root with
directories pruned (`cite_tools.tree.our_files`, reached from
`cite_tools.english.files_to_check`), and `tools/tests/test_english.py` carries a test named
`test_a_file_that_is_written_but_not_staged_is_still_reported` asserting exactly that. So a
file that is present but untracked is checked and counted. **21 of this checkout's 1979 are
untracked, and that is the largest this bullet has ever recorded** — `predicate_eval` and
`predicate_eval_superseded`, gitignored binaries built by the 2026-09-03 stall-band
campaign's harness; `assets/scans/raw/scan 1 room scan.e57`, the raw capture above; and
**18 files under `.dbg/`, which belong to a concurrent debugging session and to no commit**.
**Re-derived rather than carried
forward**, on 2026-09-17 on `feat/cell-b-zone`, by differencing `files_to_check` against
`git ls-files`; the same difference named three files earlier that day and two
at `523ffd9`, at `6d51966` and at `df91154`. It said **3 of 1961** earlier on 2026-09-17 and
**2 of 1936** before that.
**A clean clone of this branch's tip
reports 1959**, which is **measured here and not predicted**: `files_to_check` over a fresh
worktree at `cca27b8` returns exactly **1959**, and over one at `4f29761` exactly **1958**,
both on 2026-09-17. The commits after `cca27b8` add no tracked file — one edits a docstring
and one edits this file — so the figure is the tip's, and that is said rather than assumed
because naming a commit and meaning a different one is how the counts in this section go
wrong. That pair is what closes the +1 this round owns and separates it from
the +17 it does not. **The 1958 half also confirms the prediction this bullet made earlier
the same day**, which said a clean clone of this branch's tip would report 1958 and had not
been checked. This figure depends on local
build state — and, as of this reading, on what another agent happens to be writing — in a way
none of the
other counts in this section does. **That prediction has now been checked once and it held**:
this file said a clean clone of `30baea8` would report **1926**, and `files_to_check` over a
fresh worktree at `e18251e` — three commits after `30baea8`, with no tracked file
added in between — returns exactly **1926** on 2026-09-08. That the 1540 was itself
effectively a tracked-only reading was checked the same way: `files_to_check` over a fresh
worktree at `51195e0` returns **1540** on 2026-09-08. The three tree-parametrized test files
above do **not** share this property — all three walk `git ls-files`. Run `lint` rather than

</details>

### Q40

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1381-1384 at `960e6b4`
- **Summary:** The one English-check exemption, `docs/reference/v1-lessons.md`; the check's limits are ADR-0035's.
- **Recommendation:** Delete. `.english-only.yaml` and ADR-0035 hold it.

<details><summary>Original text</summary>

quoting it. The one exemption is
`docs/reference/v1-lessons.md`, which quotes the
original Turkish as primary-source evidence. The limits — chiefly that ASCII-only Turkish and
every other Latin-script language pass untouched — are the ADR's; do not restate them.

</details>

### Q41

- **Class:** stale
- **Source:** `CLAUDE.md` lines 1385-1390 at `960e6b4`
- **Summary:** "One arm picks and places a work-piece, and friction alone holds it" (ADR-0029). STALE: ADR-0061 holds the box with a grasp-hold plugin, and ADR-0065 feeds it from a simulation-only bridge (`cite_bringup/grasp_hold_bridge.py`).
- **Recommendation:** Delete. The headline is false today.

<details><summary>Original text</summary>

- **One arm picks and places a work-piece, and friction alone holds it.** ADR-0029 removed
  the contact-triggered attachment plugin, so nothing on the simulation side assists a grasp:
  the pads close on the part, stall on it, and the controller reports
  `stalled=true, reached_goal=false -> holding` — the evidence ADR-0022 shaped the gripper
  path around. The 84-trial measurement the decision rests on is
  [`docs/measurements/2026-08-25-friction-grasp/`](../../docs/measurements/2026-08-25-friction-grasp/results.md).

</details>

### Q42

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1782-1791 at `960e6b4`
- **Summary:** Teardown flake is two families; the exit-1 family (`rclpy` shutdown races) is fixed (ADR-0034).
- **Recommendation:** Delete. ADR-0034 holds it.

<details><summary>Original text</summary>

- **The teardown flake is two failure families, and process identity predicts the family
  exactly.** What this file said until 2026-08-27 — four undifferentiated processes, identity
  not predictive, run duration the only candidate predictor, cause unestablished — was wrong
  on all four counts. Split by exit status:
  - **Exit code 1 — `topology_server.py` and `model_info.py`.** Both `cite_facility` `rclpy`
    nodes, both instances of **one cause, which is established and fixed**.
    [ADR-0034](../../docs/adr/0034-process-lifecycle-mechanism-in-cite-runtime.md) records it: two
    upstream `rclpy` shutdown races, each link read in upstream source rather than inferred,
    each compensation carrying the condition for deleting it. **Read the ADR.** Restating the
    mechanism here would be the duplication P1 forbids.

</details>

### Q43

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1792-1824 at `960e6b4`
- **Summary:** The signal-death family: campaign INCONCLUSIVE, the `skill_server` destructor demonstration, no exemption widened.
- **Recommendation:** Delete; docs/measurements/2026-08-27-teardown-signal-family/ holds it. "No exemption may be widened to absorb a failure" is a candidate rule. The rule "no exemption may be widened to absorb a failure" was restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules"; the verbatim text stays here.

<details><summary>Original text</summary>

- **Signal deaths — `move_group` (×3) and `skill_server` (×1), and still unexplained.** The
  two observed in `continuous_line` are both MoveIt-linked C++, and **"MoveIt-linked" is no
  longer a description of the family**: the campaign below caught `parameter_bridge`, which
  links no MoveIt code, exiting -11 at teardown. One event, and enough to retire the
  characterisation.
  **This family now has a campaign, and it is the citation for every figure that used to sit
  in this bullet** —
  [`docs/measurements/2026-08-27-teardown-signal-family/`](../../docs/measurements/2026-08-27-teardown-signal-family/results.md).
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

</details>

### Q44

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1878-1906 at `960e6b4`
- **Summary:** The 0.14 real-time factor is conditional on about one CPU core; never quote Gazebo's own `real_time_factor` field; the ceilings campaign.
- **Recommendation:** Delete; docs/architecture/cross-cutting-testing.md is the one statement (campaign `2026-08-29-real-time-factor-conditions`). Promote "never widen a ceiling to absorb a slow host" and "measure the real-time factor from the stats topic, never quote the field". "Never widen a ceiling to absorb a slow host" was restored to CLAUDE.md §2 on 2026-10-01 as part of the general no-widening rule.

<details><summary>Original text</summary>

- **The recorded real-time factor of 0.14 is conditional, and the condition is roughly one CPU
  core.** It is not wrong: it reproduces on the development host — both halves of the recorded
  pair, RTF and the `joint_states` rate, together and by two independent instruments — when the
  cell is confined to about one core. Unconfined, the same host idles slightly **above** real
  time and holds the configured `joint_states` rate. Bring-up is rejected as the condition and
  so is load. Every figure is
  [`docs/measurements/2026-08-29-real-time-factor-conditions/`](../../docs/measurements/2026-08-29-real-time-factor-conditions/ANALYSIS.md);
  **the one place in the tree that states the figure with its condition is
  [`docs/architecture/cross-cutting-testing.md`](../../docs/architecture/cross-cutting-testing.md)
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
  [`docs/measurements/2026-09-02-scenario-ceilings/`](../../docs/measurements/2026-09-02-scenario-ceilings/ANALYSIS.md)
  — thresholds registered before the first trial, machine named, taken on the shipped
  configuration — bands every scenario ceiling per allocation. **Read it before touching a
  ceiling**, and read what it refuses to say: it attributes nothing to either the throttle or
  the hulls, a family of its cells has **no upper bound at all** because the intervals are
  smaller than its poll quantum, eight are **NOT ASSESSED** where silence is not a clearance,
  and its own rule forbids differencing any margin against the 2026-08-29 campaign's. **It
  changes no ceiling and proposes no value; changing one is the project owner's.** The figures
  stay in that directory (P1) — cite it, and the standing instruction above is untouched: **no
  ceiling may be widened to absorb a slow host.**

</details>

### Q45

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1907-1941 at `960e6b4`
- **Summary:** Phase 2.A: what landed (ADR-0041 to ADR-0044, `MODE_VIRTUAL_LEAD`); what a paired model adds to the plan; ask the plan for its shape.
- **Recommendation:** Move to docs/architecture/L5-twin-synchronization.md if not already there; delete.

<details><summary>Original text</summary>

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
  **What a paired model is not, and this is the part to carry. It said `model/facility/zones.yaml`
  declares `sides: single` today, so nothing in this repository is paired — and that is false
  since 2026-09-18**: `cell_b` declares `twin: {sides: pair}` (ADR-0059, the project owner's
  decision that the target system is two digital sides with one of everything on each), and
  `cell_a` stays `single` deliberately. **[Overtaken 2026-10-01 — ADR-0069 removed `cell_a` from L0; `cell_b` is the only zone.]** What pairing a zone does to the generated tree is
  unchanged and was re-measured at the flip: the plan gains **one more `sides:` entry — carrying the counterpart's
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

</details>

### Q46

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1942-1981 at `960e6b4`
- **Summary:** How a pair comes up (ADR-0047), its evidence (three runs at `b3b7b66`), what a pair is not, no paired scenario, `pair.py` hazards. STALE: the readiness witness is said to wait on "every skill and detection action server"; there is no `Detect.action` in `cite_interfaces` today.
- **Recommendation:** Move to docs/architecture/L5-twin-synchronization.md or docs/operations/bring-up.md with the stale clause corrected; delete the evidence counts.

<details><summary>Original text</summary>

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
CI. **The sentence that used to close this paragraph is now false and its replacement is
narrower**: it said the shipped model is `single`, so `./scripts/sim --pair` refuses on a
clean checkout and reproducing a paired run means editing L0. Since 2026-09-18 `cell_b` is
paired in the model, so `./scripts/sim --zone cell_b --pair` brings a pair up from a clean
checkout and a paired run is reproducible by a second reader. **`cell_a` still refuses**
**[Overtaken 2026-10-01 — ADR-0069 removed `cell_a` from L0; `cell_b` is the only zone.]**, and
**nothing automated brings either up** — which is the half of the old sentence that survives
and the one that matters. Two hazards are recorded in `cite_bringup/pair.py` rather than fixed — a
signal handler's `Queue.put` can deadlock the supervisor against its own join, with the ceiling
unable to fire because the stuck call is what enforces it; and `READY_CEILING_S` is stated
rather than derived from the ceilings a side's own gate chain carries.
**ADR-0041 and ADR-0047 were promoted on this and ADR-0043 and ADR-0044 were not**, each on
the condition it wrote for itself. Read those four status blocks rather than this paragraph
before assuming which way any of them went.

</details>

### Q47

- **Class:** B+
- **Source:** `CLAUDE.md` lines 1982-2003 at `960e6b4`
- **Summary:** A checkout claims two domains (odd base, even counterpart); the plan carries an offset; `require_domain`; ADR-0044 still Proposed.
- **Recommendation:** Delete. docs/onboarding/getting-started.md, docs/operations/troubleshooting.md and ADR-0044 hold it.

<details><summary>Original text</summary>

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

</details>

### Q48

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2004-2049 at `960e6b4`
- **Summary:** `MODE_VIRTUAL_LEAD` routes; what `twin_boundary.py` wires; the supervisor starts L5 (ADR-0057); nothing in CI reaches it; test-module count history.
- **Recommendation:** Move to docs/architecture/L5-twin-synchronization.md; delete the count history.

<details><summary>Original text</summary>

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
**What L5 is not, and this is the part to carry. It said "**Nothing starts it**" until
2026-09-18, and the pair supervisor now does** (ADR-0057). `./scripts/sim --pair` starts both
sides, joins them on their readiness tokens, and starts `twin_boundary.py` **on that event**,
passing it the zone and the plan path and nothing else; the boundary announces itself on
**stdout** from inside the plant's executor and the supervisor joins on that line too. The
instrument that falsified the old sentence is the one it named: `grep -rn twin_boundary
workspace/src` outside `cite_twin` now reaches `cite_bringup/pair.py`, where it returned
nothing on 2026-09-01. **What survives of the old sentence is most of it.** It is still in
**no launch file** and the generated bring-up plan still has **no entry** for it (ADR-0057
rejects that slot for now), so `./scripts/sim` **without `--pair`** brings up no L5 at all.
**No scenario and no CI step reaches it**: `grep -rn -- --pair tests .github` and `grep -rn
cite_twin tests .github scripts` both still return nothing on 2026-09-18 — so a regression in
the boundary, the mode gate or the monitor still fails no gate outside the package's own
tests, which is ADR-0057's unmet promotion clause 4 and not a detail. **This clause also read
"the shipped model is `single`, so `--pair` refuses on a clean checkout", and that is false
since `cell_b` was paired** (ADR-0059). The refusal is gone and **the missing gate is not**:
a pair now comes up from a checkout and still nothing in CI brings one up, which makes the
clause-4 gap wider rather than narrower. What holds it is those tests,
which `./scripts/test` runs — **seven** pytest modules and two launch tests, driving the node
against **fake sides**, which bring no cell up and move no arm. It said **five** until
2026-09-18, and it was left stale on purpose by the branch that noticed it: that pass was told
not to edit this section, so it restored the figure verbatim and named the count it had
measured in its own commit message. Re-measured here on `main` by two instruments that agree —
`ls workspace/src/cite_twin/test/*.py` less the `fake_side.py` helper, and that package's
`CMakeLists.txt`, which registers seven `ament_add_pytest_test` and two `add_launch_test`
entries. **Nothing here is evidence about motion, and 2.A produces no fidelity number
in any case** (charter §8).

</details>

### Q49

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2065-2077 at `960e6b4`
- **Summary:** `DivergenceMetrics.valid` is false by construction (clock-deficit term has no instrument); do not make it true by weakening a term.
- **Recommendation:** Delete; summarised in the new section 2. docs/architecture/L5-twin-synchronization.md should carry it.

<details><summary>Original text</summary>

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

</details>

### Q50

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2078-2130 at `960e6b4`
- **Summary:** The throttle is a ceiling; ADR-0043 half 2 unmet in two ways; ADR-0049 ratified, not promoted; nothing measures capacity during a run.
- **Recommendation:** Delete. ADR-0043, ADR-0049 and the capacity campaign hold it.

<details><summary>Original text</summary>

**The throttle is a ceiling, and ADR-0043's other half is now measured and NOT MET.**
SDFormat's `real_time_factor` bounds how fast a server may run and cannot make a slow one
faster, so it binds only where the cell has spare capacity: on the machine that measured it,
it is at or near a no-op under load and binds only on an idle cell.
**Both sets of figures live in
[ADR-0043](../../docs/adr/0043-hold-both-sides-to-the-wall-clock.md) — half 1's in its 2026-08-29
correction, the pair's in its 2026-08-30 one — and are deliberately not copied here (P1).**
What belongs in this file is their strength and their verdict. Each was taken by the
implementing agent of the change that produced it, on **one machine**, with **no thresholds
registered in advance** and **no directory in
[`docs/measurements/`](../../docs/measurements/README.md)**; neither was re-taken for this file, and
neither is a campaign — a campaign's thresholds are written before its first trial, and these
have none, which is why they are recorded in a decision record instead of being dressed as
one. **The verdict: both sides of the pair fell short of the 1.0 ADR-0043 requires, by about
the margin
[`2026-08-28-second-world-cost`](../../docs/measurements/2026-08-28-second-world-cost/ANALYSIS.md)
predicted for vendor collision meshes, on a different host and with the throttle now in the
world.**
**Half 2 is unmet in two different ways and only one of them is the machine. This file called
it "a measured gap in the machine" until 2026-08-31, and that was half the story.** The other
half is the shape of the requirement: with half 1's throttle in the world a measured real-time
factor is **capped at the declared factor by construction**, so half 2 as worded is a test no
machine passes, and an over-provisioned machine answers it much as an adequate one does. That
is read in upstream `gz-sim` source and recorded in
[ADR-0049](../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md) and in ADR-0043's
2026-08-31 correction — which also records that ADR-0043's own throttled/unthrottled idle rows
were the evidence against its own requirement and were never read against each other.
**The machine is nevertheless genuinely short, and as of 2026-09-01 that is measured rather
than inferred**: the paired shortfall is about an eighth, far outside anything a throttle loss
accounts for, and
[`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../../docs/measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
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
[ADR-0028](../../docs/adr/0028-convex-hull-collision-meshes.md)'s hulls; it has been pulled and it
was not enough — read the collision-geometry item in the gap list below, which is where that
record's state is kept.

</details>

### Q51

- **Class:** D
- **Source:** `CLAUDE.md` lines 2131-2139 at `960e6b4`
- **Summary:** The Gazebo-partition defect class and the one door, `cite_bringup/gz.py`, with its guard.
- **Recommendation:** Delete; section 10 already carries it as a review checkpoint.

<details><summary>Original text</summary>

**The sharpest lesson of that work is a defect class, not a decision.** Every process the
launch graph starts carried the partition; the scenario harness started its own and carried
none, so both cycle scenarios hung at their work-piece spawn — and an unpartitioned
`gz model --list` **exits 0 having reached no world**, so fixing only the spawn would have
produced scenarios that verify a part moved by asking an empty transport. One door now
exists (`cite_bringup/gz.py`) and a guard,
`tests/scenarios/guards/test_gz_calls_carry_the_partition.py`, fails the suite if a raw
Gazebo-transport subprocess call reappears under `tests/`. §10 carries it as a review
checkpoint.

</details>

### Q52

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2140-2141 at `960e6b4`
- **Summary:** Header of "What does not work, stated plainly".
- **Recommendation:** Delete; the new section 2 has its own.

<details><summary>Original text</summary>

- **What does not work, stated plainly** (Phase 1.C/1.D, in progress). **None of these is an
  exit-criterion clause** — that list is the last bullet in this section, and it is separate.

</details>

### Q53

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2211-2309 at `960e6b4`
- **Summary:** Option F (ADR-0052): the superseded predicate, the implemented one, the gate not fully cleared, the open-stroke region it opens, the caller door closed. OPEN OWNER DECISION: whether the monotonicity term returns.
- **Recommendation:** Delete; docs/open-work.md #36 and ADR-0052 hold it. The owner decision on the monotonicity term stays open there.

<details><summary>Original text</summary>

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
  [ADR-0052](../../docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md), which states
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
  [`docs/measurements/2026-09-02-option-f-regions/`](../../docs/measurements/2026-09-02-option-f-regions/ANALYSIS.md)
  — thresholds registered before the first trial, machine named, measured on the **implemented**
  predicate at `d3eeac4` — reports in its own §2.2 and §9 that item 2's second bullet is **not
  met here**: the gate asks for the false-positive flip bracketed to at least **0.05 mm**, that
  arm's stop grid is **2.00 mm**, and the flip is located only to (46.00, 48.00] mm at the
  narrow side. **Do not read "implemented" as "the gate cleared."**
  **A later campaign moved half of that gate and not the rest.**
  [`docs/measurements/2026-09-03-stall-band-flip/`](../../docs/measurements/2026-09-03-stall-band-flip/ANALYSIS.md)
  brackets the **narrow** edge of the implemented predicate's flip to the width §A.10 asks for.
  The **wide** edge is **not** bracketed, and what stopped it is an instrument failure rather
  than a measurement: one trial read the robot description back as zero characters and the
  validity rule's discard granularity took the whole block with it. **A null is not a
  clearance** — that campaign's own rule refuses to read its silence at that edge as agreement
  with the arithmetic or as validation of either band value. The gate is **still not cleared**;
  [`docs/open-work.md`](../../docs/open-work.md) #36 is where its clause-by-clause state is kept.
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
  [`docs/measurements/2026-09-01-grasp-discrimination/`](../../docs/measurements/2026-09-01-grasp-discrimination/ANALYSIS.md),
  thresholds registered before the first trial, machine named — and it **observed** a real
  grasp reported empty, witnessed by the work-piece's own contact sensor, and separately
  **reproduced** a stall on nothing reported as a grasp. **Both directions fire.** It is
  still not a rate: one machine, one arm, one part, one timestep, and it took a commanded
  width above the ceiling the validator enforces. **Cite the campaign; its own write-up asks
  that its figures stay in its directory, and the four the decision rests on are quoted in
  ADR-0052 and nowhere else.** Its verdict on whether the stall distribution moves with the
  commanded width is **INCONCLUSIVE** by two of its own pre-registered rules, and ADR-0052
  §A.9 records that F's threshold may depend on the question that verdict leaves open.

</details>

### Q54

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2310-2320 at `960e6b4`
- **Summary:** No vendor-described link's mass or inertia is validated by anything; "owed its own record".
- **Recommendation:** Needs an ADR (or a docs/open-work.md item); it is a live structural gap.

<details><summary>Original text</summary>

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

</details>

### Q55

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2321-2335 at `960e6b4`
- **Summary:** The collision gate's sampling edge (0.1 s, 40 mm, 0.40 m/s) is unmeasured; the waypoint-clearance campaign did not exercise it.
- **Recommendation:** Delete. ADR-0027's amendment of 2026-09-04 holds it.

<details><summary>Original text</summary>

- **The only environment-collision gate has an unmeasured edge.** Pilz does not search the
  scene, so `ValidateSolution` is the sole gate, and it checks trajectory waypoints while
  interpolating nothing between them. The sampling time is **0.1 s**, a C++ default argument
  with no ROS parameter exposing it. The smallest object in the generated planning scene is
  a **40 mm** break-beam housing, so a waypoint step exceeds it whenever the tool point moves
  faster than **0.40 m/s**. The arithmetic and the two ways the step can grow are ADR-0027's.
  **The residual has since been tested for, and the region was not exercised**:
  [`docs/measurements/2026-09-04-waypoint-clearance/`](../../docs/measurements/2026-09-04-waypoint-clearance/ANALYSIS.md)
  measured the per-waypoint tool-point step directly on the trajectories the shipped scenarios
  published, and **no interval anywhere carried both a large enough step and a close enough
  bracketing distance at the same time** — the cell moves fast where it is far from everything
  and creeps where it is close. **Its "no body passed between two checked waypoints" is refused
  as evidence by its own pre-registered rule and may not be read as a clearance.** The edge is
  still unmeasured; ADR-0027 carries a dated amendment of 2026-09-04 saying exactly that, and
  its status did not move.

</details>

### Q56

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2336-2356 at `960e6b4`
- **Summary:** Execution tolerances under Gazebo: the quiet is measured, detecting an obstruction is not; never widen a tolerance.
- **Recommendation:** Delete. ADR-0036's 2026-09-04 amendment and its campaign hold it. "Never widen a tolerance" was restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules"; the verbatim text stays here.

<details><summary>Original text</summary>

- **What the execution-side tolerances do under Gazebo is half measured, and the open half is
  the one a fault needs. This bullet said "nothing has measured" and "no following error has
  been sampled there" until 2026-09-04, and both clauses are now false.**
  [`docs/measurements/2026-09-04-following-error/`](../../docs/measurements/2026-09-04-following-error/ANALYSIS.md)
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

</details>

### Q57

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2357-2376 at `960e6b4`
- **Summary:** A grasp holds a position, not an orientation; the 18.7 degree residual is a roll, the yaw figure is 10.62 degrees; a yawed square part parks short.
- **Recommendation:** Move to docs/architecture/L3-capabilities.md (or L1) if still wanted; the campaigns hold the figures.

<details><summary>Original text</summary>

- **A grasp holds a position, not an orientation, and the two published residuals are
  different quantities.** Correcting the grasp-plane offset took rotations above 20° from
  60% to 0% of trials and left a residual —
  [`docs/measurements/2026-08-25-grasp-plane-offset/`](../../docs/measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md).
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
  [`docs/measurements/2026-08-26-conveyor-yaw-transfer/`](../../docs/measurements/2026-08-26-conveyor-yaw-transfer/ANALYSIS.md).

</details>

### Q58

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2382-2387 at `960e6b4`
- **Summary:** `Transfer`, `Pick` and `Place` have servers and no program caller.
- **Recommendation:** Delete; summarised in the new section 2.

<details><summary>Original text</summary>

- **`Transfer` has a server and no caller**, and since 2026-10-01 neither do `Pick` and
  `Place`: the real program drives `MoveTo` and `Grasp` only, and the scenario that drove the
  other two, `pick_and_place`, left the main tree with ADR-0069. Their callers are tests and
  the twin boundary's forwarding. It read "Today's L0 topology is conveyor-mediated and L4
  refuses a direct arm-to-arm edge at plan time (ADR-0031)" until that date; ADR-0031 is
  deprecated.

</details>

### Q59

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2404-2438 at `960e6b4`
- **Summary:** Scenarios are not deterministic: what the seed reaches, the 2026-09-22 campaign and what it is forbidden to say, `./scripts/sim` passes no seed, `libdart`'s own generator.
- **Recommendation:** Delete; summarised in the new section 2. docs/architecture/cross-cutting-testing.md and the campaign hold it.

<details><summary>Original text</summary>

- **Scenarios are not deterministic, and since 2026-09-22 that is measured rather than
  reasoned.** `CITE_PHYSICS_SEED` still reaches only `gz sim --seed`, which seeds sensor noise
  and **not the physics solver**. What changed is which part is stochastic: planning is no
  longer it wherever Pilz answers, and physics still is. The OMPL fallback remains unseeded
  and unseedable. See `docs/architecture/cross-cutting-testing.md` and ADR-0027 before writing
  anything about determinism, and do not upgrade the claim on the strength of the planner
  alone.
  **The cell has now been run twice under one seed and did not reproduce** —
  [`docs/measurements/2026-09-22-is-a-run-reproducible/`](../../docs/measurements/2026-09-22-is-a-run-reproducible/ANALYSIS.md),
  criteria frozen before its harness existed and harness frozen before its first trial.
  `pick_and_place` on `cell_b`, one seed, one commit, minutes apart: the work-piece ended up
  **0.763 mm** apart against a **1e-6 m** threshold, and the two cycles differed by
  **4.687 s**. **Both runs passed, and both were answered by Pilz alone**, so no unseedable
  OMPL motion is inside it. **Two runs on one machine. That is not a rate.** Until this, the
  only behavioural evidence was a four-run observation taken **before** the seed was plumbed
  and flagged as not repeated since the planner changed.
  **What that campaign is FORBIDDEN to say, and nobody may write on its strength.** Its
  control did not clear — a 1e-6 m perturbation passed through at unit gain and missed the
  sensitivity threshold by 1.17e-16 m — so its rule N fired and **two of its three questions
  are NOT ADMISSIBLE**. **Nobody may write that the physics engine was shown to reproduce,
  that `gz sim --seed` was shown not to reach it, or that the divergence sits in the solver,
  the coupling or the planner.** Where it enters is **UNRESOLVED**; `docs/open-work.md` #85
  owns it. The underlying figures are published there, labelled as figures and not as
  verdicts, and may be cited only that way.
  **Two facts that campaign wrote down which stand on their own.** First, **`./scripts/sim`
  passes no seed at all** — `grep -rn CITE_PHYSICS_SEED scripts` reaches `scripts/scenario`
  and nothing else, and the launch file omits `--seed` entirely when the variable is unset —
  so every `./scripts/sim` and `./scripts/sim --pair` run is unseeded, **including the paired
  runs that prompted the campaign**. Second, the symbol scan ADR-0027 rests on **had no
  recorded command anywhere until that campaign ran it**, and the `nm` recipe this project
  remembers it by belongs to the adjacent OMPL check on an **arm64** image; run on **x86_64**
  with its output committed, it **confirms** that record — no gz-physics plugin references
  `gz::math::Rand` — and shows that **`libdart` defines its own generator with its own seed
  setter**, which `gz sim --seed` does not reach. So *"the physics is unseeded because there
  is nothing there to seed"* is no longer an available reading.

</details>

### Q60

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2439-2531 at `960e6b4`
- **Summary:** Convex-hull collision meshes (ADR-0028): selection, promotion on a restated clause (ADR-0051), the 50 mm bound, residuals, count history of hull CI runs, a hull adds no clearance, the `self_collide` hazard.
- **Recommendation:** Move "a hull adds no clearance and may never be cited as margin" and the `self_collide` hazard to docs/architecture/cross-cutting-safety.md; delete the rest (ADR-0028 holds it).

<details><summary>Original text</summary>

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
  [`docs/measurements/2026-09-01-hull-grasp/`](../../docs/measurements/2026-09-01-hull-grasp/ANALYSIS.md)
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
  campaign; [ADR-0051](../../docs/adr/0051-restate-the-hull-grasp-gate.md) **restates it rather
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

</details>

### Q61

- **Class:** D
- **Source:** `CLAUDE.md` lines 2598-2600 at `960e6b4`
- **Summary:** Do not widen any ceiling to absorb whatever CI shows next.
- **Recommendation:** Promote to a CLAUDE.md rule (with tolerances and exemptions: never widen one to absorb a failure). Restored to CLAUDE.md §2 on 2026-10-01, after review, under "Binding standing rules" (ceilings, tolerances and teardown exemptions). The verbatim text stays here.

<details><summary>Original text</summary>

**The standing instruction is unchanged and is not retired by this run:
do not widen any ceiling to absorb whatever CI shows next**; a ceiling widened to fit a
geometry change is a measurement thrown away.

</details>

### Q62

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2601-2614 at `960e6b4`
- **Summary:** The capacity case: hulls clear the 1.0 floor with the throttle lifted, vendor meshes miss it; no requirement shown passing.
- **Recommendation:** Delete. The capacity campaign and ADR-0049 hold it.

<details><summary>Original text</summary>

**The capacity case is separate and was never grasp evidence.** Measured as capacity with
the world's throttle lifted by
[`docs/measurements/2026-08-31-capacity-and-clock-deficit/`](../../docs/measurements/2026-08-31-capacity-and-clock-deficit/ANALYSIS.md)
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
([ADR-0049](../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md)).

</details>

### Q63

- **Class:** D
- **Source:** `CLAUDE.md` lines 2615-2624 at `960e6b4`
- **Summary:** Two hull mechanisms stated as fact and falsified; an audit taken at a commanded value must state whether the machine reaches it; a gate must not be written against an unobserved mechanism.
- **Recommendation:** Promote to a CLAUDE.md rule; `tools/tests/test_the_retracted_gripper_claim.py` already enforces the retraction.

<details><summary>Original text</summary>

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

</details>

### Q64

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2625-2640 at `960e6b4`
- **Summary:** The cell runs the real robot's program (ADR-0067); the event-driven line removed (ADR-0069); the belt route kept with no in-tree client.
- **Recommendation:** Delete; rewritten in the new section 2.

<details><summary>Original text</summary>

- **The cell runs the real robot's program, and the event-driven line is no longer in the
  main tree**
  ([ADR-0067](../../docs/adr/0067-the-real-program-drives-the-twin-on-a-track.md), `Proposed`;
  [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md),
  `Proposed`, which supersedes ADR-0066 and ADR-0056).
  ADR-0067 replaced ADR-0066's taught L0 joint poses: `python3 -m cite_bringup.program` now
  runs the real xArm 5's own Blockly program, read from
  `model/programs/xarm5_real_demo.blockly.xml`, through the twin boundary on both sides of
  `cell_b`, with the arm on a linear track. ADR-0066's taught-pose runner is kept, runnable, in
  `projects/(02-fixed-program-pair)` (ADR-0068); ADR-0069 removed its leftovers —
  `program/cell_b_pick_place.py` and L0's `configuration.poses_rad` field — from the main tree.
  **The beam-triggered line was parked here until 2026-10-01** — unchanged, tested and in CI,
  tagged `event-driven-line-v1` — and **ADR-0069 then removed it, with `cell_a`, from the main
  tree**: it runs as `projects/(01-three-arm-event-driven-line)/run`. **The twin boundary's belt
  route stays, on the project owner's decision, with no in-tree client**: only `cite_twin`'s own
  tests hold it.

</details>

### Q65

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2641-2643 at `960e6b4`
- **Summary:** The layout is PROVISIONAL until the Phase 3 scan.
- **Recommendation:** Delete; rewritten in the new section 2.

<details><summary>Original text</summary>

- **The layout is `PROVISIONAL`.** The coordinates in `model/` are engineered, not surveyed.
  Charter §8 puts the physical scan in Phase 3; until then a measurement taken from this model
  does not transfer to the building, and no report should imply that it does.

</details>

### Q66

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2644-2648 at `960e6b4`
- **Summary:** Documentation status markers DESIGNED / PARTIAL / BUILT.
- **Recommendation:** Delete; rewritten in the new section 2.

<details><summary>Original text</summary>

- **The documentation is written, and its status markers are the thing to read.** Each document
  in `docs/architecture/` and `docs/interfaces/` carries `DESIGNED`, `PARTIAL` or `BUILT`, with
  the evidence named. `DESIGNED` means the contract the code must satisfy; `PARTIAL` says which
  part is real and which is not. Read the layer document before touching a layer, and read its
  status line before believing its body.

</details>

### Q67

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2649-2653 at `960e6b4`
- **Summary:** Measured evidence lives in docs/measurements/; an inconclusive campaign is published too.
- **Recommendation:** Delete; rewritten in the new section 2.

<details><summary>Original text</summary>

- **Measured evidence lives in [`docs/measurements/`](../../docs/measurements/README.md)**, one
  directory per campaign, each with its thresholds written down before the first trial. This is
  what P8 looks like in practice. Cite a campaign; do not copy its numbers around. **A campaign
  whose answer is "inconclusive" is published too** — the teardown one is, and its rule refused
  a clean arm as evidence rather than banking it.

</details>

### Q68

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2654-2657 at `960e6b4`
- **Summary:** Lead-in: charter section 8 owns Phase 1's clause-by-clause record.
- **Recommendation:** Delete; the new section 2 points to charter section 8.

<details><summary>Original text</summary>

- **Where Phase 1's exit criterion stands, and nothing above changes it.** **The clause-by-clause
  record is charter §8 and is not copied here** (P1) — it states which evidence closed which
  clause, at what strength, and what the closure does not cover. What belongs in a rulebook is
  the part that changes how you read everything else in this section:

</details>

### Q69

- **Class:** D
- **Source:** `CLAUDE.md` lines 2675-2679 at `960e6b4`
- **Summary:** Never cite "CI is green" as evidence; cite the step that gates it; a `continue-on-error` step's conclusion is not its result. (The last line runs into the CI-failure tally that moved with the three-arm snapshot.)
- **Recommendation:** Promote to a CLAUDE.md rule; the new section 2 states the step-log half.

<details><summary>Original text</summary>

A workflow whose conclusion is `success` is therefore not a statement that every scenario
passed. **Never cite "CI is green" as evidence that a capability works; cite the step that
gates it** — and note that **the step's own conclusion is not the step's result either**:
GitHub reports a `continue-on-error` step as `success` when it failed, so the log is the
only instrument. See the table in the `continuous_line` bullet, where **seven of

</details>

### Q70

- **Class:** C
- **Source:** `CLAUDE.md` lines 2713-2719 at `960e6b4`
- **Summary:** ADR index count on 2026-10-01 (68 records; glob 69) and the newest record.
- **Recommendation:** Delete. Run `./scripts/doctor`.

<details><summary>Original text</summary>

- **"Every architectural decision is written down" is the one clause the charter records as
  unclosable as stated**, and the counting is the reproducible part. `./scripts/doctor`'s
  `ADR index` line reported **68 records, all indexed** on 2026-10-01 on
  `feat/remove-parked-line`, and `ls docs/adr/[0-9]*.md | wc -l` read **69** there, the glob
  also matching the template; the newest record is
  [ADR-0069](../../docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md) — remove the
  parked line and `cell_a` from the main tree, `Proposed`, which supersedes ADR-0056 and

</details>

### Q71

- **Class:** C
- **Source:** `CLAUDE.md` lines 2767-2830 at `960e6b4`
- **Summary:** ADR index history 59 -> 40 and the glob-versus-doctor relation; ADR-0059's pairing decision; `cell_a` load-bearingly single (overtaken).
- **Recommendation:** Delete. The ADR index table in docs/adr/README.md is the record.

<details><summary>Original text</summary>

**The step from 59 is +3 and NOT from 2026-09-21's tree**: `main` already held **60** before
this branch, because ADR-0061's merge moved no count here, and the branch adds ADR-0062 and
ADR-0063. That staleness was this file's, not the branch's, and it is the fifth time a
figure in this section has been found stale by somebody re-running rather than reading.
It read **59 records, all indexed** on 2026-09-21, the newest being
[ADR-0060](../../docs/adr/0060-take-the-ik-solution-nearest-the-arm.md) — take the IK solution
nearest the arm rather than the first one that plans, `Proposed`, and the record that amends
ADR-0026's branch policy. It read **58 records, all indexed** on `main`, 2026-09-18 — then the
newest
being [ADR-0059](../../docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md), which pairs
`cell_b` and keeps `cell_a` `single`, on the project owner's decision that the target
system is **two twin sides, both digital, each with exactly one of everything**. **It is
`Proposed` and it defends nothing**: what would defend it is ADR-0057's clause 4, an
automated paired scenario in CI, which is still unmet — so `./scripts/sim --zone cell_b
--pair` now works from a clean checkout and **nothing in CI brings a pair up**, which makes
that gap wider rather than narrower. `cell_a` stays `single` **load-bearingly**:
`docs/open-work.md` #62's two fixtures append a counterpart unconditionally and both name
`cell_a` literally, so pairing that zone fails `./scripts/test` today. **[Overtaken
2026-10-01 — ADR-0069 removed `cell_a`, and #62 is closed: both fixtures read `cell_b`'s
paired plan without appending a side.]**
It read **56** at `7c6e902` with ADR-0058 newest — `Proposed` with **promotion clause 1
deliberately open**: nobody may write that the stall it repairs stopped reproducing, because the
control arm of the experiment that would show it barely reproduced. It read **55** on
2026-09-17 on `feat/cell-b-zone`, whose one added record is ADR-0056. It read **54** on 2026-09-10 at
`523ffd9`, 53 on 2026-09-08 at `6d51966`, 52 on 2026-09-01 at
`abdae38` and **still 52 when re-run on 2026-09-08 at `df91154`** — that branch amended
existing records and added none, which `git diff --diff-filter=A --name-only
e18251e..df91154` confirms by listing no file under `docs/adr/`. It said 51 earlier on
2026-09-01, 48 on 2026-08-30, 46 the day before that, 43
earlier that day, and 40 before that —
the newest being
[ADR-0056](../../docs/adr/0056-keep-the-three-arm-cell-as-a-zone-and-run-one-zone-at-a-time.md) —
keep the three-arm cell as a second zone and run one zone at a time, **`Proposed` and not
promoted**, because its clauses 4 and 5 want a `cell_b` bring-up and a `cell_a` showcase
bring-up and neither run exists. **ADR-0055 is not on this branch**: a concurrent session
holds it unmerged, which is why this record was renumbered from 0055 at `f762a35`, and
why `doctor`'s count here is 55 rather than 56. Before it,
[ADR-0054](../../docs/adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md) — the hardware
opt-in keyed on a declared fact rather than on a backend's name, **`Proposed (corrected
2026-09-10)` and not promoted**, for the clause-10 reason its own status block gives —
with
[ADR-0053](../../docs/adr/0053-index-hardware-params-by-backend.md),
[ADR-0049](../../docs/adr/0049-measure-the-real-time-floor-as-capacity.md),
[ADR-0050](../../docs/adr/0050-what-crosses-the-twin-boundary.md),
[ADR-0051](../../docs/adr/0051-restate-the-hull-grasp-gate.md) and
[ADR-0052](../../docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md) before it.
**This file named
ADR-0051 as the newest while ADR-0052 was already on disk**, which is the drift the
paragraph's own closing instruction exists to catch.
**`ls docs/adr/[0-9]*.md` returns exactly one more than `doctor` does**, because the glob
also matches `0000-template.md`; it read **69** on 2026-10-01 on `feat/remove-parked-line`
against `doctor`'s 68, **68** on 2026-09-29 on
`feat/projects-snapshots` against `doctor`'s 67, **65** on 2026-09-28 against `doctor`'s 64,
**63** on 2026-09-24 against `doctor`'s 62,
**60** on 2026-09-21 against `doctor`'s 59, **59**
on `main` on 2026-09-18 against `doctor`'s
58, **57** at `7c6e902` that same day against `doctor`'s 56, **56** on 2026-09-17 on `feat/cell-b-zone`
against `doctor`'s 55, **55** on 2026-09-10 at `523ffd9` against
`doctor`'s 54, **54** on 2026-09-08 at `6d51966` against
`doctor`'s 53, and **53** on 2026-09-01 at `abdae38` against
`doctor`'s 52, so the
relation has held at every re-audit — as it did at 52 against 51 earlier on 2026-09-01.
Both numbers are
right and

</details>

### Q72

- **Class:** D
- **Source:** `CLAUDE.md` lines 2831-2838 at `960e6b4`
- **Summary:** Name the command with the number; run `doctor` rather than quoting the ADR count; `doctor` checks indexing, not completeness, and no check can.
- **Recommendation:** Move the completeness sentence to docs/adr/README.md; the rest is the new section 2's "ask a command" rule.

<details><summary>Original text</summary>

they count different things, so name the command with the number. **This figure moves
every time a decision is recorded, which is often — run `doctor` rather than quoting the
number here.** The breakdown of corrected,
amended and superseded records is the table in
[`docs/adr/README.md`](../../docs/adr/README.md) and is deliberately not copied here — `doctor`
does not count those. `doctor` enforces that every ADR on disk is indexed and that every ADR
referenced from `docs/` exists; it does **not** check that the set is *complete*, and no check
can. That clause is a judgement, not a measurement.

</details>

### Q73

- **Class:** stale
- **Source:** `CLAUDE.md` lines 12-28 at `960e6b4`
- **Summary:** Section 1 as it stood: "whose first instrument is a multi-robot xArm work cell", read as stale since ADR-0069 (the main tree is one xArm 5 per side of the paired `cell_b`); the sentence mirrors charter section 1 and was restored.
- **Recommendation:** The identity sentence ("whose first instrument is a multi-robot xArm work cell", which mirrors charter section 1) was restored verbatim to CLAUDE.md section 1 on 2026-10-01 after review; the new paragraph is kept beside it as the main tree's current scope statement. Owner decision: whether the charter's identity wording should change, which is a charter change.

<details><summary>Original text</summary>

```markdown
## 1. What this is

The **CITE Digital Twin** — a facility-scale digital twin of the Center for Innovation,
Technology and Entrepreneurship at Sam Houston State University, built on ROS 2 and
Gazebo, whose first instrument is a multi-robot xArm work cell.

It is a *twin*, not a simulation: real hardware and the virtual model share one control
interface, and the system continuously measures how far the model is from reality.

It is also a **rebuild**. A first iteration (v1) was archived under `legacy/` and deleted at
the end of Phase 1; it survives only in version control, and **its patterns are not
precedent** — do not reintroduce them. What it taught is
[`docs/reference/v1-lessons.md`](../../docs/reference/v1-lessons.md); why it was replaced rather
than migrated is [ADR-0001](../../docs/adr/0001-rebuild-rather-than-migrate.md); the debt that
forced the decision is charter §12.

Full charter — identity, scope, architecture rationale, roadmap: **`what-we-are-doing.md`**.
```

</details>

### Q74

- **Class:** H
- **Source:** `CLAUDE.md` lines 2953 at `960e6b4`
- **Summary:** Section 7, `./scripts/sim` row: dated history clauses (required with no default until 2026-10-01; `--pair` used to imply `--headless`; every GUI run rendered in software until 2026-09-28).
- **Recommendation:** Delete the history. The row in CLAUDE.md now states only current behaviour; the GPU-library rationale is in `scripts/sim`'s own comment.

<details><summary>Original text</summary>

| `./scripts/sim [--zone <name>] [--headless] [--pair]` | Launch the simulated cell. **`--zone` defaults to the model's only zone and is required only when L0 declares more than one** (ADR-0069 decision 5, derived once in `cite_bringup/zones.py`); L0 declares one zone today, `cell_b`, the one-arm cell. It was required with no default from ADR-0056 until 2026-10-01, while `cell_a` was a second zone. Exactly one zone runs at a time. `--pair` brings both sides of a twin pair up under the pair supervisor and requires an L0 model that declares `twin: {sides: pair}`. It **used to imply `--headless` and no longer does**: both sides run in the one container the supervisor is started in, so one display passthrough serves both, and the cost is that the two windows carry the same world name and cannot be told apart by their titles. **A windowed run now selects a GPU vendor library when the container has one**, guarded on that library existing so a host without it falls through untouched — until 2026-09-28 every GUI run in this project rendered in SOFTWARE without saying so, and the script's own comment carries what that cost |

</details>

### Q75

- **Class:** H
- **Source:** `CLAUDE.md` lines 2957 at `960e6b4`
- **Summary:** Section 7, `./scripts/scenario` row: "`pick_and_place` and `continuous_line` left the main tree with ADR-0069 and run from projects/01".
- **Recommendation:** Delete; projects/README.md says where they run.

<details><summary>Original text</summary>

| `./scripts/scenario [name] [--zone <name>]` | Headless simulation-in-the-loop scenario; no argument lists them. `--zone` follows the same rule as `./scripts/sim`'s — the model's only zone by default, required when there are several (ADR-0069 decision 5) — through `tests/scenarios/_cell.py`, which asks `cite_bringup/zones.py`. The scenarios are `bringup` and `program_cycle`; `pick_and_place` and `continuous_line` left the main tree with ADR-0069 and run from `projects/01` |

</details>

### Q76

- **Class:** H
- **Source:** `CLAUDE.md` lines 2958 at `960e6b4`
- **Summary:** Section 7, `./scripts/program` row: "(ADR-0067, which replaced ADR-0066's taught poses)" and "ADR-0066's taught-pose version runs as ... /run".
- **Recommendation:** Delete; projects/README.md lists the fixed-program snapshot.

<details><summary>Original text</summary>

| `./scripts/program [--zone <name>] [--headless] [--cycles N]` | Bring the twin pair up, start each side's belt on that side, put a box on each side's table and run the real xArm 5's program once through the twin boundary (ADR-0067, which replaced ADR-0066's taught poses): both arms and both tracks from one client. `--zone` as for `./scripts/sim`. **A demonstration, not an instrument**: it gates nothing and is in no CI step; `./scripts/scenario program_cycle` is what checks it, on the plant. ADR-0066's taught-pose version runs as `projects/(02-fixed-program-pair)/run` |

</details>

### Q77

- **Class:** H
- **Source:** `CLAUDE.md` lines 2962 at `960e6b4`
- **Summary:** Section 7, `projects/<name>/run` row: "what `./scripts/demo` showed until ADR-0069 removed it on 2026-10-01". The row keeps the snapshot path, which `tools/tests/test_nothing_reaches_into_a_snapshot.py` requires CLAUDE.md to carry.
- **Recommendation:** Delete the history clause (done in CLAUDE.md); keep the path.

<details><summary>Original text</summary>

| `projects/<name>/run [--headless]` | Run a frozen milestone snapshot from its own folder, which is its own repository root with its own `./scripts/*` (ADR-0068). Not a main-tree command: nothing in the main tree calls it or builds from there. **The three-arm, beam-triggered line — what `./scripts/demo` showed until ADR-0069 removed it on 2026-10-01 — runs as `projects/(01-three-arm-event-driven-line)/run`** |

</details>

### Q78

- **Class:** X
- **Source:** `CLAUDE.md` lines 2867-2868 at `960e6b4`
- **Summary:** Section 3, P9: "A new robot type must not touch orchestration" names a layer (L4 behaviour trees) the main tree no longer has.
- **Recommendation:** Owner decision: keep as a principle for whatever drives the cell (the real program, the twin boundary), or reword. Not changed this round.

<details><summary>Original text</summary>

- **P9 — Plug in, plug out.** Robot types, end-effectors, sensors, and process modules are
  replaceable at their interface boundary. A new robot type must not touch orchestration.

</details>

### Q79

- **Class:** X
- **Source:** `CLAUDE.md` lines 2886-2895 at `960e6b4`
- **Summary:** Section 5, layer stack: L4 reads "behaviour trees, line coordination, handoff" and L3 lists `Detect`; the main tree has no L4 package and no `Detect.action`.
- **Recommendation:** Owner decision: reword L4 to what drives the cell today (the real program through the twin boundary) and drop `Detect`, or keep both as the target architecture (charter section 5). Not changed this round.

<details><summary>Original text</summary>

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

</details>

### Q80

- **Class:** X
- **Source:** `CLAUDE.md` lines 2932 at `960e6b4`
- **Summary:** Section 6, technology baseline: "Orchestration | BehaviorTree.CPP v4 + Groot2"; nothing in the main tree uses BehaviorTree.CPP since ADR-0069.
- **Recommendation:** Needs an ADR to change (section 6 says so). Not changed this round.

<details><summary>Original text</summary>

| Orchestration | BehaviorTree.CPP v4 + Groot2 |

</details>

### Q81

- **Class:** X
- **Source:** `CLAUDE.md` lines 3005-3011 at `960e6b4`
- **Summary:** Section 10, QoS note: "That cost this project a belt setpoint that was never once delivered" is an anecdote about the removed L4 line.
- **Recommendation:** Delete the anecdote sentence, keep the rule. Not changed this round.

<details><summary>Original text</summary>

- **QoS**: declare profiles explicitly. Incompatible publisher/subscriber QoS connects
  silently and delivers nothing — the most common silent failure in ROS 2. **Compatible QoS
  is not delivery either:** reliable is a promise to *matched* subscribers, so anything
  published in the same callback that created the publisher reaches nobody. That cost this
  project a belt setpoint that was never once delivered. Treat a match as an event, never a
  sleep or a publish loop — see
  [`docs/interfaces/qos-profiles.md`](../../docs/interfaces/qos-profiles.md).

</details>

### Q82

- **Class:** X
- **Source:** `CLAUDE.md` lines 3044-3047 at `960e6b4`
- **Summary:** Section 11: "This happened on 2026-08-24 and cost a whole phase's worth of work its review."
- **Recommendation:** Delete the dated incident, keep the rule. Not changed this round.

<details><summary>Original text</summary>

- **A session instruction that conflicts with this is an `ESCALATE`.** If the tooling a
  contributor is running tells them not to delegate, that contradicts this file, and this
  file is the rulebook. Say so and ask; do not quietly pick a side. This happened on
  2026-08-24 and cost a whole phase's worth of work its review.

</details>

### Q83

- **Class:** stale
- **Source:** `CLAUDE.md` lines 1660, 2203 (moved) at `960e6b4`
- **Summary:** "Both records are implemented and merged on `main` at `c555440`" (ADR-0045, ADR-0046): `git cat-file -t c555440` fails in this repository on 2026-10-01, so the citation does not resolve. The text moved with the three-arm snapshot's MEASUREMENTS.md and is quoted here only for this finding.
- **Recommendation:** Owner decision whether to resolve the right SHA; snapshot text is a record and is not corrected.

<details><summary>Original text</summary>

for the L4 retry. **Both stay `Proposed`, and both are now implemented and merged on `main` at `c555440`.** The
...
**Both records are implemented and merged on `main` at `c555440`**, and both stay `Proposed`. **The mechanism is evidenced

</details>

### Q84

- **Class:** stale
- **Source:** none; found while doing the move, not carried from a line of `CLAUDE.md`
- **Summary:** The seventeen campaigns under docs/measurements/ stayed where they are. Which milestone each one's subject belongs to has not been decided; a first sort, by date and title only and NOT verified against each campaign's criteria.md, is in the original-text block.
- **Recommendation:** Owner decision per campaign: keep in docs/measurements/ (subject still in the main tree) or record in the relevant snapshot's MEASUREMENTS.md that it belongs there. Campaign folders are frozen and are not moved by this cleanup.

<details><summary>Original text</summary>

| Campaign | First sort (unverified) |
|---|---|
| `2026-08-25-friction-grasp` | three-arm line era; friction grasping superseded by ADR-0061 |
| `2026-08-25-grasp-plane-offset` | three-arm line era; the offset correction it led to is still in L3 |
| `2026-08-26-conveyor-yaw-transfer` | three-arm line (three stations) |
| `2026-08-27-teardown-signal-family` | three-arm line era; `move_group` and `skill_server` still exist |
| `2026-08-28-second-world-cost` | main tree (a pair) |
| `2026-08-29-real-time-factor-conditions` | main tree; cited by `tools/tests/test_rtf_figure_conditions.py` |
| `2026-08-31-capacity-and-clock-deficit` | main tree (ADR-0049) |
| `2026-09-01-capacity-on-shipped-main` | main tree |
| `2026-09-01-grasp-discrimination` | main tree (ADR-0052) |
| `2026-09-01-hull-grasp` | main tree (ADR-0028) |
| `2026-09-02-option-f-regions` | main tree (ADR-0052) |
| `2026-09-02-scenario-ceilings` | three-arm line era (its scenarios); ceilings still apply |
| `2026-09-03-stall-band-flip` | main tree (ADR-0052) |
| `2026-09-04-following-error` | main tree (ADR-0036) |
| `2026-09-04-waypoint-clearance` | three-arm line era scenarios; the gate (ADR-0027) is still in the main tree |
| `2026-09-21-place-abort-and-the-held-part` | `cell_b`, before the real program |
| `2026-09-22-is-a-run-reproducible` | `cell_b` `pick_and_place`, a scenario now only in the three-arm snapshot |


</details>

### Q85

- **Class:** stale
- **Source:** none; found while doing the move, not carried from a line of `CLAUDE.md`
- **Summary:** Citations of "CLAUDE.md section 2" (or of a paragraph of it) left untouched because the file is protected, an ADR, a frozen campaign, or a dated record.
- **Recommendation:** Leave as they are: each names the pre-2026-10-01 text, which is `git show 960e6b4:CLAUDE.md` and is preserved in this queue and in the snapshots' MEASUREMENTS.md files. The charter's three are the owner's to change.

<details><summary>Original text</summary>

Found on 2026-10-01 by grepping tracked files outside `projects/` for citations of `CLAUDE.md` section 2. Line numbers are at the cleanup's working tree.

**Protected, ADRs, frozen campaigns and the dated open-work snapshot (not edited by rule):**

- `docs/adr/0001-rebuild-rather-than-migrate.md`: line(s) 95
- `docs/adr/0028-convex-hull-collision-meshes.md`: line(s) 1238
- `docs/adr/0033-derive-the-index-standoff-from-the-workpiece.md`: line(s) 148
- `docs/adr/0035-check-the-english-only-rule-by-character-signal.md`: line(s) 180
- `docs/adr/0038-stop-the-line-without-ending-the-process.md`: line(s) 104
- `docs/adr/0039-report-a-station-that-cannot-be-triggered.md`: line(s) 72
- `docs/adr/0045-measure-a-gripper-deadline-in-the-simulated-clock.md`: line(s) 38
- `docs/adr/0046-a-retry-may-not-destroy-the-trigger-it-waits-on.md`: line(s) 29, 169, 486
- `docs/adr/0048-refuse-a-counterpart-the-generator-cannot-build.md`: line(s) 311, 683
- `docs/adr/0052-what-separates-a-grasp-from-a-stall-on-nothing.md`: line(s) 65, 893
- `docs/adr/0053-index-hardware-params-by-backend.md`: line(s) 41
- `docs/adr/0054-key-the-hardware-opt-in-on-a-declared-fact.md`: line(s) 290, 308, 989
- `docs/adr/0057-start-the-twin-boundary-from-the-pair-supervisor.md`: line(s) 293
- `docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md`: line(s) 235
- `docs/adr/0061-hold-the-box-while-the-jaws-are-shut.md`: line(s) 454
- `docs/adr/0069-remove-the-parked-line-and-cell-a-from-the-main-tree.md`: line(s) 238
- `docs/measurements/2026-08-28-second-world-cost/ANALYSIS.md`: line(s) 240, 421
- `docs/measurements/2026-08-29-real-time-factor-conditions/criteria.md`: line(s) 10, 126
- `docs/measurements/2026-09-01-capacity-on-shipped-main/ANALYSIS.md`: line(s) 423
- `docs/measurements/2026-09-02-option-f-regions/ANALYSIS.md`: line(s) 470
- `docs/measurements/2026-09-02-option-f-regions/raw/shakedown/NOTES.md`: line(s) 86
- `docs/measurements/2026-09-02-scenario-ceilings/ANALYSIS.md`: line(s) 749
- `docs/measurements/2026-09-02-scenario-ceilings/criteria.md`: line(s) 125, 784
- `docs/measurements/2026-09-04-waypoint-clearance/criteria.md`: line(s) 474
- `docs/measurements/2026-09-04-waypoint-clearance/harness/capture.py`: line(s) 527
- `docs/measurements/2026-09-22-is-a-run-reproducible/criteria.md`: line(s) 282
- `docs/measurements/2026-09-22-is-a-run-reproducible/harness/analyse.py`: line(s) 640, 674
- `docs/measurements/2026-09-22-is-a-run-reproducible/harness/common.py`: line(s) 204, 215, 238
- `docs/measurements/2026-09-22-is-a-run-reproducible/harness/README.md`: line(s) 32, 282
- `docs/measurements/2026-09-22-is-a-run-reproducible/harness/run_campaign.sh`: line(s) 24
- `docs/measurements/2026-09-22-is-a-run-reproducible/harness/trial_cell.py`: line(s) 18, 46
- `docs/open-work.md`: line(s) 84, 219, 1153, 1158, 1354, 1412, 1725, 2061, 2138, 2439, 2550
- `what-we-are-doing.md`: line(s) 486, 516, 758

**Code, configuration and test comments, not edited by this cleanup** (the documentation
pass that did it writes no source, configuration or test file). Whether each target survives
in the new section 2 was judged by reading both:

- Target survives in the new section 2 (left as is): `scripts/build:16`, `scripts/doctor:354`,
  `scripts/scenario:75`, `scripts/sim:208`, `scripts/test:119`, `scripts/validate-model:21`
  (all "see section 2 for what exists"); `.english-only.yaml:22`, `tools/cite_tools/english.py:15`
  ("cite a campaign; do not copy its numbers"); `tools/tests/test_english.py:12`,
  `tools/tests/test_interface_counts.py:32,164` ("a count names its command");
  `workspace/src/cite_bringup/launch/simulation.launch.py:1198` (the real-time-factor bullet);
  `workspace/src/cite_bringup/test/test_release_confirmation_launch.py:98` (`Transfer` has no
  caller); `tests/scenarios/program_cycle.py:19` (nothing automated holds two sides);
  `docs/onboarding/getting-started.md:48` (what `doctor` skips does not exist yet: see
  section 2); `docs/architecture/cross-cutting-testing.md:307` (the status block, for the
  cycle-completion row).
- **Target moved, citation now stale** — the paragraph is in this queue or in the three-arm
  snapshot's `MEASUREMENTS.md`, not in section 2:
  `.english-only.yaml:88` (an exemption never widened: Q-items on lines 1792-1824 and the
  snapshot), `.github/workflows/ci.yml:147`, `scripts/_lib.sh:477` and `scripts/_selftest.sh:910`
  (the teardown families: lines 1782-1877), `scripts/_lib.sh:936` (shared-volume contamination:
  lines 1396-1399, in the snapshot), `scripts/program:64` (a run attached to another container:
  lines 597-608), `workspace/src/cite_bringup/cite_bringup/program/cell.py:72` (Gazebo's
  real-time-factor field over-reporting: lines 1878-1906),
  `workspace/src/cite_twin/test/test_twin_boundary_launch.py:35` (`./scripts/scenario`
  addresses the plant: lines 1962-1981),
  `workspace/src/cite_test_hardware/test/test_unreachable.py:130` (the v1 tree is section 1,
  and was before this cleanup too),
  `tools/cite_tools/generate/planning_scene.py:21` and its template
  `tools/cite_tools/templates/moveit/planning_scene.yaml.j2:23` (and therefore the generated
  `workspace/src/cite_generated/moveit/cell_b_planning_scene.yaml:27`, which must be
  regenerated, never hand-edited, if the template changes). **These three are also false on
  their own terms**: they say nothing reads the planning scene because no loader exists in
  `cite_facility` or `cite_bringup`, and `cite_facility/planning_scene_loader.py` exists and
  applies it (old lines 788-825 and the L2 architecture document).

(Permanent comments point at permanent homes — an ADR, a campaign, a section of `CLAUDE.md`
or a document under `docs/` — or state the fact inline, never at an item of this queue.)

**Fixed on 2026-10-01 by a follow-up comment-only pass** (no behaviour changed; the generated
planning scene was regenerated with `./scripts/validate-model --write`, never hand-edited):

- `.english-only.yaml:22` and `tools/cite_tools/english.py:15`: the quoted sentence no longer
  exists; now quote section 2's "cite it, do not copy its numbers".
- `.english-only.yaml:88`: "never widened" re-pointed to section 2's binding no-widening rule
  and the 2026-08-27 teardown-signal-family campaign.
- `.github/workflows/ci.yml:147`, `scripts/_lib.sh:477`, `scripts/_selftest.sh:910`: re-pointed
  to ADR-0034 and the 2026-08-27 teardown-signal-family campaign. Also FALSE as
  written: section 2 had recorded since 2026-08-27 that process identity predicts the
  *family*; the comments now say it sorts failures into two families and predicts none.
- `scripts/_lib.sh:936`: the citation replaced by the fact stated inline (shared Docker volumes
  once made a pass count report another worktree's binaries).
- `scripts/program:64`: the citation replaced by the fact stated inline (`compose exec` skips
  the entrypoint that sources ROS and the overlay).
- `workspace/src/cite_bringup/cite_bringup/program/cell.py:72`: re-pointed to the campaign
  `docs/measurements/2026-08-29-real-time-factor-conditions/`.
- `workspace/src/cite_twin/test/test_twin_boundary_launch.py:35`: re-pointed to ADR-0057's
  unmet clause 4 (the automated paired scenario).
- `workspace/src/cite_test_hardware/test/test_unreachable.py:130`: section 2 corrected to
  section 1.
- `tools/cite_tools/generate/planning_scene.py:21`, `tools/cite_tools/templates/moveit/planning_scene.yaml.j2:23`
  and the regenerated `workspace/src/cite_generated/moveit/cell_b_planning_scene.yaml`: the
  false "nothing reads this file" replaced by the loader that does.
- `workspace/src/cite_bringup/test/test_release_confirmation_launch.py:98`: FALSE as written
  (L4 and its arm-to-arm refusal left the main tree with ADR-0069, and ADR-0031 is deprecated);
  now "a server and no program calls it", which is section 2's.

Re-checked and left as is, the target surviving in the new section 2: the six `scripts/*`
"see section 2" lines, `tools/tests/test_english.py:12`,
`tools/tests/test_interface_counts.py:32,164`, `tools/tests/test_rtf_figure_conditions.py:5,55`
(past-tense history), `workspace/src/cite_bringup/launch/simulation.launch.py:1198` and
`tests/scenarios/program_cycle.py:19`.


</details>

### Q86

- **Class:** C
- **Source:** `CLAUDE.md` lines 192-194 at `960e6b4`
- **Summary:** `tools/tests` collection reading 1782 on `feat/projects-snapshots` (2026-09-30), the branch that made the snapshots, whose base `e90d230` is the real-program snapshot's source commit. Moved here from that snapshot's `MEASUREMENTS.md` on 2026-10-01: it is a main-tree count, not a measurement of the milestone.
- **Recommendation:** Delete. Run the collection.

<details><summary>Original text</summary>

It read **1782** on `feat/projects-snapshots`, 2026-09-30. **The step from 1569 spans several
branches and is not reconciled here**; the reviewer of that branch measured 1716 at
`e90d230`, its base.

</details>

### Q87

- **Class:** C
- **Source:** `CLAUDE.md` lines 2720-2729 at `960e6b4`
- **Summary:** ADR index readings 67 (2026-09-29) and 65 (2026-09-28), around the source commits of the fixed-program and real-program snapshots; no reading of 66 was taken. Continues Q70 mid-sentence and runs into Q91. Moved here from those snapshots' `MEASUREMENTS.md` files on 2026-10-01: a main-tree count, not a measurement of either milestone.
- **Recommendation:** Delete. Run `./scripts/doctor`; docs/adr/README.md is the record.

<details><summary>Original text</summary>

ADR-0066 and deprecates ADR-0031, ADR-0032 and ADR-0039. It reported **67 records, all
indexed** on 2026-09-29 on
`feat/projects-snapshots`, the newest being
[ADR-0068](../../docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md) — keep each proven
milestone as a frozen, runnable snapshot under `projects/`, `Proposed`. **No reading of 66
was taken**: ADR-0067 landed on `main` without this figure being re-run. It read
**65 records, all indexed** on 2026-09-28 on
`feat/fixed-program`, the newest being
[ADR-0066](../../docs/adr/0066-run-the-cell-from-a-fixed-program.md) — run the cell from a fixed
program through the twin boundary and park the event-driven line, `Proposed`. It read

</details>

### Q88

- **Class:** B+
- **Source:** `CLAUDE.md` lines 896-921 at `960e6b4`
- **Summary:** The first pair brought up from the committed model (2026-09-18, `cell_b`, one run) and one `MoveTo` dispatched to two arms through the boundary, with the bypass control. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: its subject, the paired `cell_b`, is the main tree.
- **Recommendation:** Delete. ADR-0059 holds the figures and the control (its table of goals); ADR-0057 clause 4 holds the missing gate.

<details><summary>Original text</summary>

**The pair itself has now been brought up from the committed model, which is the first time
any paired run recorded in this file was reproducible from a checkout.** `./scripts/sim
--zone cell_b --pair` on 2026-09-18, no edit to `model/`: both sides announced readiness in
about 15 s, the supervisor started the boundary on the join, and it printed
`CITE_BOUNDARY_READY zone=cell_b` after reporting `twin boundary up: plant on domain 43,
counterpart on domain 44, 5 routable skill(s), mode SIM`. One SIGINT tore it down in about
3 s, boundary first, `boundary: ready=True status=0`. **It is also the first paired run of
`cell_b`** — one arm, one conveyor — every earlier one having been taken on a hand-flipped
model whose zone this file never named. **One run, one machine, nothing registered in
advance. That is not a rate**, and **nothing automated brings a pair up**, which is
ADR-0057's unmet clause 4.
**One operator goal has now been dispatched to two digital arms and both acted**, which is
what the pair is for. `SetMode(VALIDATED)` accepted, then **one** `MoveTo` to
`/cite/twin/cell_b/picker/move_to`: both arms moved **1.3996 rad** and finished **0.000000
rad** apart. **A control run is what makes that mean anything** — commanded directly through
the plant's own trajectory controller with the boundary bypassed, the plant moved 0.2971 rad
and the counterpart **0.0000**, so the two sides are independent simulations rather than one
observed twice. A third goal, sent from the divergent state the control left, brought them
back to 0.000671 rad apart. **Both sides were shown to ACT rather than to move**: the
counterpart's `move_group` executed on every goal, taking 6.04 s for the first and 0.104 s
for one it was already at.
**It is not a fidelity number and cannot become one**: both sides run the same model and the
same solver, so agreement is what must happen (charter §8). **The driver is not committed,
nothing automated does any of it, and ADR-0057's clause 4 is still unmet** — so none of this
is defended by a gate. The figures and the control are in
[ADR-0059](../../docs/adr/0059-pair-cell-b-and-leave-cell-a-single.md) and are not copied here (P1).

</details>

### Q89

- **Class:** B+
- **Source:** `CLAUDE.md` lines 922-940 at `960e6b4`
- **Summary:** `bringup` run four times locally against the paired `cell_b` (2026-09-18): 3 of 4, the one failure a lost goal response (`Failed to send goal response … (timeout)`) behind the `the MoveTo goal was never accepted` assertion; the base-rate run was not taken. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: `bringup` on `cell_b` is a main-tree gate. The first sentence also carries the `pick_and_place` run and stays in that snapshot too; it is quoted here as context.
- **Recommendation:** Move the finding to docs/open-work.md #26 (the `MoveTo` never-accepted item) as an occurrence on the paired plan, with its strength; delete the rest.

<details><summary>Original text</summary>

**`bringup` was run four times locally against a PAIRED `cell_b` on 2026-09-18, and it
passed 3 of the 4**, and `pick_and_place` — a **blocking** CI step on this zone — passed once
with the bare verdict and one genuine friction stall. That is `./scripts/sim`'s single-side
path — the plant alone, on a plan that now declares a counterpart — which is exactly what
ADR-0059 had to leave working. The passes printed the **bare** verdict, so cycle and
post-shutdown teardown both. **The one failure shares its assertion string with the `MoveTo`
failure this bullet already records as recurring, and that is all it shares**: that earlier
event was on `cell_a`, unpaired, weeks before this change, and **no mechanism was ever
attached to it**. It is reported here as a finding rather than re-run past.
**Its mechanism was captured and it is not what the assertion says.** The message is `the
MoveTo goal was never accepted`, and the goal **was** accepted: the log carries
`[skill_server] [rclcpp_action]: Failed to send goal response … (timeout): client will not
receive response` — the acceptance was sent and lost, so the client's handle stayed `None`.
**Read that as a lost response, not a rejection**, and note that the string appeared in **0**
of the three passing runs. One machine, four runs, nothing registered in advance. **That is
not a rate**, and **nothing here attributes the loss to pairing and nothing exonerates it**:
the cheapest discriminator — four `bringup` runs at the commit before the flip, for a base
rate to compare 1-of-4 against — **was not taken**, so 3 of 4 supports neither direction.
What does bear on it is structural and is in the `validate-model` bullet above: every

</details>

### Q90

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2050-2064 at `960e6b4`
- **Summary:** A boundary brought up and `SetMode` called on it, and a pair torn down by one SIGINT, boundary first (2026-09-18, one machine, model flipped and reverted); `move_group` -11 on both sides, unclassified. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: the pair and its boundary are the main tree.
- **Recommendation:** Delete. ADR-0057's promotion section and ADR-0059 hold the `SetMode` reading and the teardown; the -11 is the teardown-signal family (docs/measurements/2026-08-27-teardown-signal-family/).

<details><summary>Original text</summary>

**A pair with a boundary has been brought up and `SetMode` called on it**, by a `tester` on
one machine on 2026-09-18, with the model flipped to `pair` for the run and reverted — the
token in about 1.5 s, `accepted=True, 'SIM -> VIRTUAL_LEAD', current_mode=5`, and the failure
path naming the boundary 2 of 2. **One machine, no thresholds registered in advance, no
directory in [`docs/measurements/`](../../docs/measurements/README.md), not re-taken here. That is
not a rate and it is not a CI gate.**
**And a pair has now been torn down by one signal**, on this machine on 2026-09-18, the same
way and reverted the same way: the supervisor stopped the **boundary first**, no participant
printed `did not stop within … s of SIGINT`, and the verdict read `boundary: ready=True
status=0` — so the boundary ran its own shutdown rather than being waited out and killed.
**It measures no cost**: the whole teardown fitted inside the 5 s granularity of the
instrument, so the `3 × (90 + 30) s` worst case ADR-0057 states was never approached and stays
stated rather than measured. `move_group` exited **-11** on **both** sides in that teardown —
the characterised upstream family member, seen for the first time in a paired teardown, and
**not classified there or here**. One machine, one run, nothing registered in advance.

</details>

### Q91

- **Class:** B+
- **Source:** `CLAUDE.md` lines 2730-2766 at `960e6b4`
- **Summary:** ADR index readings 64 and 62, carrying the box-spread figures of ADR-0065 (0.000 mm sideways push over nine paired runs, the 0.5 mm bar bound to no gate, a bimodal spread with no established separator) and what ADR-0063 does not buy. Moved here from the three-arm snapshot's `MEASUREMENTS.md` on 2026-10-01: the grasp-hold bridge and the paired box spread are main-tree subjects.
- **Recommendation:** Delete. ADR-0065 holds the box-spread figures and the bar; ADR-0063 and its amendment hold the clamp decision. Run `./scripts/doctor` for the ADR count.

<details><summary>Original text</summary>

**64 records, all indexed** earlier on 2026-09-28 on
`feat/let-go-when-clear`, the newest being
[ADR-0065](../../docs/adr/0065-the-cell-says-what-it-holds.md) — **the cell says what it holds and
the simulation is told**, `Proposed`, written after two records were refuted in five days
and **both were the same mistake**: ADR-0062 and
[ADR-0064](../../docs/adr/0064-let-go-once-the-pads-are-clear.md) each guessed, from the drive
joint's position, something `cite_skills::gripper_is_holding` already decides. The plugin is
now told over a topic — Harmonic's own `DetachableJoint` shape — by a **simulation-only**
bridge fed by L3's first-ever `RobotState` publisher, a contract this repository declared and
never wired. **Measured: the sideways push both superseded records chased is gone** — 0.000 mm
on **eighteen** sides across **nine** paired runs — and the box spread reads
0.023 / 0.048 / 0.054 / 0.096 / 0.117 / 0.199 / 0.381 / 0.412 / 0.483 mm against
1.150 / 1.116 / 1.269 before: mean **0.201**, sd **0.177**, highest **0.483**.
**The bar is 0.5 mm as of 2026-09-28 and it is bound to no gate**, on the project owner's
decision; the ±0.1 mm it replaces was a real arm's *run-to-run* repeatability compared
against a *two-replica* figure, which are different quantities, and the options that led to
it were the implementer's. **0.5 mm passes nine of nine and the highest of nine samples is
not a bound.** The distribution is **bimodal** — five below 0.12 mm, four above 0.38 mm,
nothing between — and **what separates them is unestablished**: a clock-offset correlation
held on six runs and died on nine. For scale, the one comparable published figure is
GPUSimBench's run-to-run divergence at fixed seed — **13.9 / 21.5 / 114.7 mm** on three
engines, with the ones it scores "0.00 cm" reporting to 0.1 mm and therefore unable to
resolve this cell's worst run. Nine runs, one machine, nothing registered in advance —
**not a rate**. It read **62 records** on 2026-09-24 on
`feat/clamp-the-box` at `50a51a9`, the newest then being
[ADR-0063](../../docs/adr/0063-the-drive-joint-may-not-be-clamped.md) — **the gripper's drive
joint may not be clamped**, `Accepted`, and the record that supersedes
[ADR-0062](../../docs/adr/0062-the-clamp-is-modelled-end-to-end.md) one day after it was written.
It publishes four measured arms so the door stays shut, and **what it does not buy is stated
in it**: the paired box spread is back at 2.418 mm against a bar that was then a real xArm's ±0.1 mm and is
**0.5 mm since 2026-09-28** (ADR-0065's amendment), the
divergence is still born at first jaw contact, and `DetachableJointInfo` carries no pose
field — so what decides where the box sits in the gripper is still the contact solve.
**Its own amendment of the same date is the part a reader must not miss**: ADR-0062's
rejected Option A was *"keep the clamp AND teach L3 to wait for the release"*, and only the
clamp half is shut — an L3 confirmation of the release ships in the same branch, without the
clamp and without the re-asking the 116-commands-zero-releases measurement condemned.

</details>
