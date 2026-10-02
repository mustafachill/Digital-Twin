# Charter history

**This is an archive, not a working document.** On 2026-10-02 the charter,
[`what-we-are-doing.md`](../../what-we-are-doing.md), stopped holding measurements and
decision records (its §0, v1.17): a figure belongs to a measurement campaign or to a past
milestone's `MEASUREMENTS.md`, and the reasoning behind a decision belongs to its ADR. What
the charter said before that is kept here **verbatim**, so that nothing it recorded is lost
and every citation of an old version can still be followed.

- **Nothing here is current.** Every sentence was true, or believed true, at the version and
  date it names. Read the charter for what holds now, and the ADRs for why.
- **Line numbers are those of charter v1.16**, at main-repository commit `911ba08`
  (`git show 911ba08:what-we-are-doing.md`).
- **Each passage is quoted inside a fenced block**, so its headings, tables and code blocks
  are shown as written rather than rendered into this page.
- **One block of text is not here**: Phase 1's delivery notes and the evidence that closed its
  exit criterion (v1.16 lines 417-570, less the sub-phase texts and the exit criterion, which
  the charter still carries). That is a measurement record of the three-arm line, so it moved
  to that milestone's own `MEASUREMENTS.md` — see [`projects/README.md`](../../projects/README.md).
- **§9, the Definition of Done and the standing prohibitions, is not here either**: it is
  doctrine rather than a record, and the charter still carries it verbatim.
- This page is not edited further. A later change to the charter is recorded in its own §14,
  as one line.

## Document history up to v1.16, in full

_Charter v1.16, lines 750-770._ Each row is reproduced as it stood; the charter's §14 now
carries one line per version.

| Version | Date | Change |
|---|---|---|
| 1.16 | 2026-10-02 | **The `docs-writer` agent is removed from the roster in §10.2, which is now ten roles.** Decided by the project owner on 2026-10-02: documentation is written by the orchestrating session when it needs writing, reviewed like any other change, and no agent is dedicated to it. §10.2's roster, its specialist-review sentence and its documentation-sync rule are updated to match; drift between code and documentation is still a defect (P7). No change to scope, architecture, technology baseline or roadmap. |
| 1.15 | 2026-10-01 | **§7's `cite_orchestration/` line is marked as not in the main tree and runnable as `projects/01` (ADR-0069).** Decided by the project owner on 2026-10-01. The behaviour-tree line, its detection and topology services, its line-only interfaces and zone `cell_a` leave the main tree; `projects/01` (ADR-0068) is where they still build and run. **L4 stays in the target architecture**: re-introducing it into the main tree is a new decision re-derived from that snapshot, never copied out of it. **Two consequential corrections, decided by the project owner on the same date.** §7's `cite_facility/` line said it serves *"the process topology as a typed LineTopology"*; the topology server and `LineTopology` left with the line, and the line now says what the package serves: the model version and the facility's static frames, plus the planning-scene load into MoveIt. §8's Phase 2.A paragraph said the three-arm cell *"lives on as the `cell_a` zone"*; it now lives on as projects/01. The v1.13 row below says the same thing and is **marked in place and not rewritten**, per the convention v1.10 states. No exit criterion is opened, closed or restated, and no change to scope, technology baseline or roadmap. |
| 1.14 | 2026-09-29 | **§7 gains `projects/`: frozen, runnable snapshots of the milestones this repository has proven and since moved past, each a record and not a source (ADR-0068).** Decided by the project owner on 2026-09-29, who ratified ADR-0068's exception to P1 and ordered this entry. Three folders are kept — the three-arm event-driven line, the fixed-program pair and the real program on a track — each a whole tree extracted from its source commit by `tools/snapshot_project.sh`, carrying only the patches its own `PROVENANCE.md` lists, and each building and running from its own folder alone. **This deliberately departs from the disposition v1 received**, and the departure is the decision rather than drift: v1 was removed from the working tree at the end of Phase 1, with *"knowledge rather than code"* carried forward (§7's `legacy/` paragraph, §12). v1 was superseded debt, and what it taught is `docs/reference/v1-lessons.md`; these three are proven, runnable results that the owner wants kept ready to run and extractable as one folder each. **The P1 exception is bounded and one-way**: nothing is copied from `projects/` into the main tree, the main tree neither imports nor builds from it, a snapshot's patterns are not precedent, and the main tree's own checks deliberately skip it. **What a snapshot promises is that it builds, its scenario passes and its `./run` runs** — its own lint, unit tests and `doctor` are outside that contract, because the extract omits `docs/measurements/`, `CLAUDE.md` and this charter. **No exit criterion is opened, closed or restated**, and no change to scope, layer architecture, technology baseline or roadmap. |
| 1.13 | 2026-09-18 | **The cell the twin is built on is no longer the three-arm cell, and the pair is declared in the model rather than staged for each run.** Decided by the project owner on 2026-09-18: the target system is **two twin sides, both digital, each with exactly one of everything** — one arm, one conveyor, one of each fixture and sensor. §8's Phase 2.A paragraph said *"a complete second simulation of the same three-arm cell"* and *"the cell stays three-armed"*; both are replaced. **The three-arm cell is finished and set aside rather than deleted** — it is the `cell_a` zone, generated from the same model, built on every run and launchable by hand, and no further work goes into it (**ADR-0056**, which also fixes one-zone-at-a-time). **`cell_b` now declares `twin: {sides: pair}` in L0** (**ADR-0059**), which is the flip ADR-0056 deferred to a record of its own; `cell_a` stays `single`, and that asymmetry is deliberate — `docs/open-work.md` #62 records that `cite_twin`'s two launch fixtures append a counterpart unconditionally and both name `cell_a` literally, so pairing that zone would fail `./scripts/test` today. **What this buys and what it does not, stated together because either half alone misleads.** It buys a paired run that is reproducible from a clean checkout — `./scripts/sim --zone cell_b --pair` brings up two sides and a twin boundary with no edit to the model, where every paired run before this was taken on an uncommitted edit that moved `MODEL_HASH`. It does **not** buy a gate: **ADR-0057's promotion clause 4 is still unmet**, no automated paired scenario exists, `grep -rn -- --pair tests .github` still returns nothing, and what CI drives on this zone is the **plant alone** — so a regression in the readiness witness, the boundary token or either side's bring-up still fails nothing outside `cite_twin`'s own tests. **Declaring a zone paired is not testing it.** **The evidence behind the flip is one bring-up and one teardown on one machine**, with nothing registered in advance and no directory in `docs/measurements/`: a pair came up with a boundary serving `SetMode` (`accepted=True, 'SIM -> VIRTUAL_LEAD'`), and a pair was torn down by one SIGINT with the boundary stopped first and `boundary: ready=True status=0`. **That is not a rate.** **2.A's standing note is untouched and is restated rather than weakened**: 2.A closes no clause of the Phase 2 exit criterion and produces **no fidelity number**, both sides running the same L0 model and the same solver, and under §2 the level stays at **L0**. **Both sides remain simulated by refusal**: ADR-0048 clause 1 makes a divergent counterpart backend an ERROR and a physical plant on a paired zone a second ERROR, so the L5 command path cannot reach a physical machine by any L0 edit — measured for this entry rather than assumed. **The five exit criteria are byte-identical and no clause of any of them is opened, closed or restated.** The v1.9 row below is **marked in place and not rewritten**, per the convention v1.10 states. **[Marked 2026-10-01 — this row says the three-arm cell *"is the `cell_a` zone, generated from the same model, built on every run and launchable by hand"*; v1.15 above replaces that: `cell_a` left L0 and the main tree, and the three-arm cell runs as projects/01 (**ADR-0069**, **ADR-0068**). Nothing else in this row is disturbed, and it is marked rather than rewritten per the convention v1.10 states.]** No change to scope, layer architecture, technology baseline, or the phases beyond 2. |
| 1.12 | 2026-09-01 | **Two corrections, taken together because both are claims this document made about things that have since been measured or built, and neither touches an exit criterion.** Decided by the project owner on 2026-09-01, on the evidence named in each. **First, the real-time figure in §8's Phase 2.A paragraph and in the v1.11 entry below — *"about 0.95 against a required 1.0"* — is withdrawn.** It was a **throttled** reading, and with the generated world's `real_time_factor` in force a measured real-time factor is capped at the declared factor by construction, so it could not have exceeded 1.0 whatever the machine did; **ADR-0049** establishes that from upstream `gz-sim` source, and **ADR-0028**'s and **ADR-0043**'s 2026-09-01 corrections withdraw the conclusion drawn from it. What replaces it is a **capacity** measurement taken with the throttle lifted, in `docs/measurements/2026-09-01-capacity-on-shipped-main/`: the configuration this repository now ships, unmodified, clears ADR-0043's floor of 1.0 on both sides of a pair concurrently, under a decision rule registered before that campaign's first trial. That campaign also answers the question it was commissioned for — all eight of its conditions reproduce `docs/measurements/2026-08-31-capacity-and-clock-deficit/`, the 2x2 that established capacity as the readable quantity, inside its registered threshold — so the branch-versus-shipped distinction changed nothing detectable. **The figures stay in the campaigns and are cited rather than copied** (P1), and §8 carries the three qualifications that must travel with them: every capacity figure there is a **lower bound** on a host that could not be quieted, which cuts one way only — the shipped configuration would clear the floor on a quiet machine, the vendor-mesh control's shortfall might not, and nobody may read that control as *"vendor meshes cannot reach 1.0"*; **clearing a bare floor is not a margin**, ADR-0049 setting neither of its two thresholds and remaining `Proposed`, its decision ratified by the owner on 2026-08-31 and ratification not being promotion; and it is one machine with every cell idle at home pose, an idle baseline being no work allowance. **The stale parenthetical in the same sentence goes with the figure**: convex hulls are the shipped selection since ADR-0028's promotion, and a corrected figure left attached to the wrong condition would be the more durable error. **None of this is a fidelity number, and 2.A's standing note is untouched.** **Second, the v1.9 entry below says *"nothing refuses a mode transition today, because no server implements `SetMode`"* and that *"`cite_twin` does not exist"*, and both clauses are false — read in the code for this entry rather than inferred.** `workspace/src/cite_twin/` is in the tree; `cite_twin/twin_boundary.py` creates the `SetMode` service on `/cite/twin/set_mode`; and `cite_twin/mode.py` decides each call and applies `cite_bringup.plan.require_hardware_opt_in` — the same check bring-up applies — **at the transition** rather than only at bring-up, with `force` unable to skip it, computing which transitions are gated from `cite_twin/routing.py`'s per-mode table instead of transcribing a list. **That closes the residual v1.9 recorded as open, and it does not make the gate live in any deployment of this repository**: nothing starts that server — `cite_bringup`, `scripts/` and `tests/` name it nowhere — and it refuses a zone that declares no counterpart, which the shipped model is. Its record is **ADR-0050**, which is `Proposed`, and what exercises the gate is that package's own unit and launch tests and no run of a cell. **Both entries below are marked in place and neither is rewritten.** §14 records what was believed at a version, which v1.10 states in as many words when it declined to rewrite v1.8; a bracketed marker keeps the original wording intact while stopping a reader who lands on the row from carrying the false claim away, and rewriting a row would destroy what this table is for. **The five exit criteria are byte-identical and no clause of any of them is opened, closed or restated.** No change to scope, architecture, technology baseline, or roadmap. |
| 1.11 | 2026-08-31 | **Two corrections to §8, and neither reopens a clause.** **First, Phase 2.A carried no progress marker at all**, so a reader could not tell that its bring-up half exists. It does: `./scripts/sim --pair` starts two independent launches and **joins** them — never sequences them — on a token each side prints from its own readiness witness, under a supervisor that owns the join and the pair's lifetime and holds no ROS context (**ADR-0047**); and **both isolations were verified at runtime rather than by reading the launch file** — one `/clock` publisher on each domain where a merged graph would show two, one Gazebo server per partition at different endpoints, and every name this project forms present exactly once on each side (**ADR-0044**, **ADR-0042**). That is P2 demonstrated rather than argued, and §8 records it with what it is not, in the same breath: **there is no paired scenario and none is possible in the present shape** — `launch_test` with `IncludeLaunchDescription` is one process holding one context on one domain — so nothing automated brings a pair up; the shipped model declares `single`; 2.A still produces **no fidelity number**, exactly as its standing note says it cannot; and **ADR-0043's real-time requirement is not met**, both sides reaching about 0.95 against a required 1.0 on one machine under the convex-hull geometry that is not the shipped default, which **ADR-0049** has since restated as a capacity measurement plus a clock-deficit budget with neither threshold yet set. **[Corrected 2026-09-01 — the figure and the condition beside it are both withdrawn, and the requirement is still not shown to be met: 0.95 was a throttled reading, which is capped at the declared factor by construction, and convex hulls are now the shipped selection. Measured as capacity, the shipped configuration clears the 1.0 floor, and clearing a bare floor is not a margin. The row is marked and not rewritten, per the convention v1.10 states. See the v1.12 entry above and §8.]** **The strength is three joined runs on one machine by the implementing agent, not re-taken by review, with no test and no CI run covering any of it** — which is why the marker reads in progress rather than complete, and why the sub-phase's note says so before it says anything else. **The Phase 2 exit criterion is byte-unchanged and 2.A closes no clause of it**, by construction. **Second, clause 2 of Phase 1's exit-criterion table said of the `continuous_line` cycle that the failed run inside `33158091922` was *"the only time this cycle has ever run on a machine nobody prepared"*.** That was true when the clause closed and is not true now: CI has run the scenario repeatedly since, with both passes and failures, and the log-derived tally lives in `CLAUDE.md` §2 and is cited rather than copied (P1) — together with the instrument problem it records, that `gh run view --json jobs` calls a `continue-on-error` step `success` even when it failed, so only the log answers. **The clause is neither reopened nor upgraded**: it closed on the evidence available then, a later run neither adds to nor subtracts from that closure, and the row still reads *not characterised* because nothing since has been a campaign. No change to scope, architecture, technology baseline, or any phase beyond the two records corrected here. |
| 1.10 | 2026-08-30 | **§8 carried a false causal attribution for the one failure inside the run that closed Phase 1, and it is struck.** The CI clause closed on run `33158091922`, whose advisory `continuous_line` step failed carrying 1 of 3 work-pieces; §8 said that failure was consistent with the failed-grasp dead end **ADR-0038** records as deliberately unfixed. **The run's own data falsifies that:** the piece passed the `lifted` milestone at `station_transfer_1`, and that milestone is *measured* — a sampled pose compared against the pick frame — rather than reported by the arm, so the grasp held and the stall was never a failed grasp. **The cause has since been established and is recorded in ADR-0045 and ADR-0046**, with **ADR-0038** amended on 2026-08-29 to record that the same dead end is reached through a second door. **§8 names those records and does not reproduce their mechanism, deliberately:** causal detail belongs in the ADRs, which carry their own status, and **both new records are `Proposed` — their mechanism is evidenced and their outcome is not**, no CI run having yet shown the gripper failing to answer and the line reporting it. A charter paragraph restating an unpromoted mechanism would be a claim with an expiry date; §8's job is the phase record, and it stays true longer by saying less. **The exit criterion is untouched and no clause is reopened** — the CI clause closed on evidence that never contained a cause, a cause adds no run, and §8 still records the criterion MET at exactly the strength it was met. **The v1.8 entry below is deliberately left as written**, carrying the attribution that was believed at that version: a version history records what was believed, and rewriting a past row destroys what §14 is for — the correction is recorded here instead. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.9 | 2026-08-29 | **Phase 2 splits into 2.A and 2.B, and gains a sixth operating mode.** §8 now states that the plant is first paired with a **virtual counterpart** — a complete second simulation of the same three-arm cell, modelled as if it were physical (**ADR-0041**, with **ADR-0042** and **ADR-0043** for the two defect classes that exist only because there are two sides, and `docs/measurements/2026-08-28-second-world-cost/` for what a second cell costs) — and that 2.B replaces that stand-in with the real cell. **2.A closes no clause of the Phase 2 exit criterion and produces no fidelity number**: both sides run the same L0 model and the same solver, so divergence across the pair is instrument, solver and scheduling noise, and under §2 the level stays at **L0**, since L1 and L2 are each defined by a flow from the physical that 2.A does not have. 2.A validates the instrument; 2.B first uses it. **The sixth mode is `VIRTUAL_LEAD`** — an operator commands the simulated side, the far side follows and actuates, nothing mirrors back — and it is added to §3.1's scope table, §5's L5 mode table and §8's Phase 2 scope sentence. **None of the five existing modes expressed that flow**: `SIM` and `REAL` each idle one side, `SHADOW` and `VALIDATED` are *defined* by a flow from the physical, and `CLOSED_LOOP` has the direction but is defined by the validation gate in front of it. §3.1 was a third charter location that two reviews missed and a grep found — and **that grep is the instrument, which undercounts**: `grep -rn CLOSED_LOOP` reaches the twelve locations in nine files ADR-0041 lists, while a thirteenth, `DivergenceMetrics.msg`, constrains the mode set in prose that names no constant and is invisible to it; it was found by reading, is left alone as an open L5 question, and whether others remain is unknown. A fourteenth location, in a file already among the nine, was found **wrong** rather than merely incomplete: `docs/onboarding/glossary.md` introduced the modes as *"Runtime modes at L5, corresponding to the levels above"*, which the sixth mode falsifies and which was already false, `REAL` having no level — the same diagnosis as ADR-0011's amendment, surfacing in a fifth document. One enumeration needing this many places to agree is P1's shape at the level of prose. **The direction is pulled forward into Phase 2; the level is not.** §2 places virtual → real at L3 and §8 places L3 in Phase 5, and what Phase 5 owns is the gate rather than the direction. **§2's new paragraph is load-bearing rather than explanatory.** ADR-0011's own level table gives L3 as a data flow and nothing else, so on that record alone this mode reads as an L3 flow arriving three phases early; the argument that it is not closes on §2's L3 row — *"Behaviour is validated in simulation and then commands the physical system"* — and on `docs/architecture/L5-twin-synchronization.md`'s mode table, and nowhere else. If either is ever read as putting the direction alone at L3, the mode must be re-argued rather than repeated. **ADR-0011 takes a matching amendment** rather than a supersession: its five levels, their literature mapping and its commitment are untouched, and only the mode set widens. **The Phase 2 exit criterion is untouched — no clause of it is closed by any of this**, and 2.A closes none of it by construction. What gates the mode against a physical far side is the refusal **already in the tree**, bring-up refusing a plan that names a non-`sim` backend unless `CITE_ALLOW_HARDWARE` is set to exactly `1`, and not a new gate; that it binds at bring-up rather than at the transition is the stated residual. **The three dangerous-transition lists now name this mode, and the residual has moved rather than closed.** `cross-cutting-safety.md`, `L5-twin-synchronization.md` and `SetMode.srv`'s header each carried two transitions — `SIM` → `REAL` and entry to `CLOSED_LOOP` — and each now carries three, entry to `VIRTUAL_LEAD` **against a real far side** joining them on the same criterion rather than by analogy: it is `CLOSED_LOOP` minus the validation gate, aimed at the same arm. Each also states that where the far side is a simulated counterpart — Phase 2.A — entering it can move nothing physical. **What stands behind those lists is not a refusal at the point of transition.** `require_hardware_opt_in` and `CITE_ALLOW_HARDWARE` bind at **bring-up**, so what they buy is that the stack could not have started with a physical backend, and **nothing refuses a mode transition today, because no server implements `SetMode`** — `cite_twin` does not exist. **[Corrected 2026-09-01 — both clauses are false: `cite_twin` is in the tree, `twin_boundary.py` serves `SetMode`, and `mode.py` applies the same hardware opt-in at the transition, with `force` unable to skip it. Nothing starts that server in this repository and it refuses a zone declaring no counterpart, so no deployment here has the gate live. The row is marked and not rewritten, per the convention v1.10 states. See the v1.12 entry above.]** **[Marked 2026-09-18 — this row scopes 2.A as *"a complete second simulation of the same three-arm cell"*, and v1.13 above replaces that: the paired cell is the one-arm `cell_b` and the three-arm cell is archived as `cell_a` (**ADR-0059**, **ADR-0056**). Nothing else in this row is disturbed, and it is marked rather than rewritten per the convention v1.10 states.]** That service's own standing commitment, that the L5 server which eventually serves it applies the same check at the transition, is cited and not extended; no new gate was invented for this mode. The gap is recorded here because it is what a future safety change has to close, and because a document asserting a guarantee no code provides is the false attestation P7 exists to prevent. No change to scope, layer architecture, technology baseline, or the phases beyond 2. |
| 1.8 | 2026-08-28 | **Phase 1 is closed: §8 records the exit criterion as MET.** The clause that had been open was "CI is green", and it was open for a reason outside the code — until that morning, every workflow run in this repository's history had been refused at the account level before a step executed, and the `ROS workspace (build, test)` job had never executed a step at all. Run `33158091922`, pushed to `main` on 2026-08-28, concluded `success` with all three jobs green, and the `ROS workspace (build, test)` job executed for the first time in this repository: image build, bootstrap, a 20-package build, the ROS linters, the tests, and all three simulation-in-the-loop scenarios. **The clause is recorded as met together with what its meeting contains.** Inside that green run the advisory `continuous_line` step **failed**, carrying 1 of 3 work-pieces and leaving a station stopped while `LineState` reported the line healthy — the blind spot **ADR-0039** records at that station and the dead end **ADR-0038** records as deliberately unfixed. The step is `continue-on-error`, so the workflow passed and the failure is real; §8 states both in one breath, because either half alone is a false reading. Two other clauses were corrected in the same pass rather than upgraded: clause 1 no longer rests on the manual clean-clone walk, which stopped at `lint` and never launched the cell, but on the CI run, which brought the three-arm cell up twice from a checkout on a machine that had never seen the project; and clause 2 records that the same run's `continuous_line` failed, being the only time that cycle has run outside a machine someone prepared. The fifth clause is untouched and still recorded as unclosable as stated. §8 also states what the run does not carry: one run, no thresholds registered in advance, at commit `60eb4a5`, three commits behind `main` and predating the ninth package. **§7 gains a third convention: its `workspace/src/` tree is the *production* structure, and packages that exist only to test it are deliberately not listed in it.** The first is `cite_test_hardware`, a `ros2_control` `SystemInterface` that cannot be selected as an arm's backend because its `on_init` refuses without a parameter the L0 model has nowhere to declare (**ADR-0040**). This is the opposite disposition to v1.7's, and deliberately: `cite_runtime` entered the tree because it ships inside the running system, which a test fixture does not. Written down so that a reader who counts more packages on disk than in the tree finds the rule rather than a drift. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.7 | 2026-08-27 | §7 gains `cite_runtime`, a package holding process-lifecycle mechanism only — signal handling and shutdown for `rclpy` nodes, with no domain knowledge and no in-project dependencies. It exists because a shutdown helper had to live somewhere and neither existing candidate was right: `cite_interfaces` holds interfaces and their delivery contract, and ADR-0025's closing clause named a helper landing there as the signal to reopen by amendment rather than let the package widen gradually — which is what this entry is; `cite_facility` describes itself as runtime access to artifacts generated from L0, which a signal handler is not. Recorded with the two upstream `rclpy` races it compensates for, and the condition for deleting each, in **ADR-0034**. One package added to the §7 tree. No change to scope, architecture, technology baseline, or roadmap. |
| 1.6 | 2026-08-27 | **Phase 1's record closed.** §8 marks sub-phases 1.A through 1.E complete, each with a note naming what was delivered and, where a figure is given, who measured it and over how many runs. **1.D is marked complete with one phrase explicitly not delivered as written:** "real handoff negotiation between robots" reaches for a direct arm-to-arm crossing, and what exists is conveyor-mediated, with L4 refusing a direct edge at plan time rather than leaving it unimplemented (ADR-0031 and its 2026-08-26 correction). The phrase is left standing and the divergence recorded beside it, rather than the phase being redefined to match what was built. **§8's exit criterion stays OPEN.** Three clauses are demonstrated — the clean-clone walk, the continuous sensor-driven cycle, and the layout being changeable from L0 alone — each with the size and limits of its evidence stated. The **CI clause is unverified and not currently verifiable**: every workflow run in this repository's history was refused at the account level before any step executed, for failed payments or a spending limit, which is a billing block and not a test result; the workflow running to completion is what would settle it. The fifth clause, "every architectural decision is written down", is recorded as unclosable as stated, since it is a universal and ADR-0031 is a known counter-instance. §7 removes `legacy/` from the repository tree, the v1 workspace having been deleted at the end of Phase 1 as that tree said it would be and after its lessons were captured in `docs/reference/v1-lessons.md`; the tree remains in version control. No change to scope, architecture, technology baseline, or the phases beyond 1. |
| 1.5 | 2026-08-25 | §7 brought back in line with the workspace. Added `cite_generated/`, which now exists and holds every artifact derived from L0 — descriptions, world, controller configuration, MoveIt configuration, static frames, process topology, bring-up plan and the planning scene. Corrected the description of `cite_facility/`, which had described something narrower than the package became: it is an L0–L1 **runtime** package that serves the generated model version, the frame and namespace plan and the process topology as a typed `LineTopology` message, and loads the generated planning scene into MoveIt — the generators themselves live in `tools/`, as the same tree already stated. Added pointers to ADR-0021 (generated artifacts are committed and verified against a fresh generator run) and ADR-0025 (the QoS profiles ship as a library inside `cite_interfaces`), because §7 is where a reader looks for the reasoning behind those two entries. No change to scope, architecture, technology baseline, or roadmap. |
| 1.4 | 2026-08-24 | Marked `.claude/` as local tooling that is not committed, in the §7 tree, §10.2 and the §11 documentation map. The agent configuration is excluded from the repository by decision; without the marker a reader would look for a directory a clone does not contain. Notes that the rules the agents enforce live in `CLAUDE.md`, which is committed, so the standards do not depend on the tooling. No change to scope, architecture, technology baseline, or roadmap. |
| 1.3 | 2026-08-24 | §7 repository structure brought back in line with the tree and given an explicit meaning: it describes the **target** structure, with markers for what does not yet exist (`model/`, `workspace/src/`, `hmi/`) and what is temporary (`legacy/`). Added `tools/`, `requirements/`, `docs/reference/`, `.devcontainer/`, `.github/` and `legacy/`; corrected the claim that `infra/` holds the devcontainer and CI, which live at the repository root because their tooling requires it. Removed `subagents/`, the portable upstream template library the active roles were adapted from — it was never tracked in git and is no longer present; the adapted roles in `.claude/agents/` are the only roster. §10.2 updated accordingly: the two roles deferred to Phase 4 will be written then rather than carried as dormant templates. No change to scope, architecture, technology baseline, or roadmap. |
| 1.2 | 2026-08-24 | Documentation tree written. Twin maturity levels renamed to align with the established literature: L1 `Mirror`→`Shadow`, L2 `Shadow`→`Validated`, with the corresponding L5 operating modes renamed to match (§2, §5). Architecture aligned with the ISO 23247 reference architecture (§2). The xArm Jazzy/Harmonic risk is closed following verification (§13). §11 documentation map expanded to the full tree and the status-marker convention introduced. No change to scope, layer architecture, technology baseline, or roadmap. |
| 1.1 | 2026-08-24 | Agent configuration integrated. Added `.claude/` and `subagents/` to the repository structure (§7); replaced the agent paragraph in §10.2 with the concrete eleven-role roster, the rationale for the two domain auditors, and the two roles deferred to Phase 4. No change to scope, architecture, technology baseline, or roadmap. |
| 1.0 | 2026-08-24 | Initial charter. Establishes project identity, twin maturity model, scope, engineering principles, layered architecture, technology baseline, repository structure, five-phase roadmap, quality gates, and working model. Supersedes all prior planning documents. |


## Passages removed or rewritten in v1.17

### §0 — the change rule, before it said "as one line"

_Charter v1.16, lines 20-20._ Rewritten, and joined by the rule that the charter holds no measurements or decision records.

~~~~markdown
- **It changes only by decision, never by drift.** Every edit must correspond to a real decision about the project's direction, must bump the version number, and must be recorded in §14. Small factual corrections are exempt from the version bump but not from being correct.
~~~~
### §2 — the pointer to the ISO 23247 mapping

_Charter v1.16, lines 67-67._ The mapping document, `docs/architecture/standards-alignment.md`, left `docs/` on 2026-10-02 with the other documents describing unbuilt layers; the pointer now names `docs/reference/standards.md`.

~~~~markdown
These levels are deliberately aligned with the established literature rather than invented: L0 and L1 correspond to Kritzinger's *digital model* and *digital shadow*, and L3 onward to a full *digital twin* with automated bidirectional flow. L2 is our own refinement — a digital shadow that additionally proves its own accuracy — because a shadow whose error nobody measures is an assertion rather than a twin. The architecture is aligned with the ISO 23247 reference architecture for manufacturing digital twins; see `docs/architecture/standards-alignment.md` for the full mapping and `docs/reference/` for sources.
~~~~
### §6.1 — the migration work, as planned

_Charter v1.16, lines 263-270._ Rewritten as done.

~~~~markdown
### 6.1 Known migration work created by this baseline

These are consequences of the baseline, identified now so they are planned rather than discovered:

1. **The conveyor plugin must be rewritten.** The IFRA conveyor plugin used previously is a Gazebo Classic plugin and will not load in Harmonic. It becomes a first-party Gazebo Sim system plugin with a typed ROS 2 interface.
2. **xArm Jazzy/Harmonic support must be verified early.** The vendor's ROS 2 support for the target release combination is a Phase 1.A verification gate, not an assumption. If gaps exist, they are found in week one, not month three.
3. **All sensor plugins must be re-specified** against Gazebo Sim's sensor system and `ros_gz_bridge`.
4. **World and model formats must be regenerated**, not ported — which is consistent with P1, since they become generated artifacts.
~~~~
### §7 — the repository tree and its three conventions

_Charter v1.16, lines 274-393._ The tree of what exists moved to `docs/architecture/repository-layout.md`; the charter keeps the target shape.

~~~~markdown
## 7. Repository structure

The repository is a monorepo. It contains the ROS 2 workspace, the facility model, the asset pipeline, infrastructure, and documentation, because these must version together.

**This tree describes the target structure, not today's snapshot.** Entries are marked
where they do not yet exist, or will not exist for long. Directories that carry no marker
exist now.

```
Digital-Twin/
├── what-we-are-doing.md          the charter — what we are building and why
├── CLAUDE.md                     the rulebook — how to work here
├── AGENTS.md                     vendor-neutral pointer to CLAUDE.md
├── CONTRIBUTING.md               human contribution workflow
├── README.md                     orientation and quick start; points here
├── LICENSE                       Apache-2.0
│
├── model/                        ← L0: the facility model            (Phase 1.B)
│   ├── facility/                 ←   zones, layout, coordinate frames
│   ├── assets/                   ←   asset instances and their poses
│   ├── topology/                 ←   process flow and station relationships
│   └── schema/                   ←   JSON Schema definitions + validator
│
├── workspace/src/                ← The ROS 2 workspace               (Phase 1.B)
│   ├── cite_interfaces/          ←   L3-L5: typed messages, services, actions
│   ├── cite_runtime/             ←   process lifecycle mechanism only (ADR-0034)
│   ├── cite_facility/            ←   L0-L1 at runtime: serves the generated model
│   │                                 version and the facility's static frames, and
│   │                                 loads the generated planning scene into MoveIt
│   ├── cite_generated/           ←   every artifact generated from L0: descriptions,
│   │                                 world, controller config, MoveIt config, static
│   │                                 frames, process topology, bring-up plan, planning
│   │                                 scene. Committed, never hand-edited (ADR-0021)
│   ├── cite_description/         ←   L1: robot and component descriptions
│   ├── cite_hardware/            ←   L2: hardware interfaces, sim and real
│   ├── cite_control/             ←   L2: controller configuration and bringup
│   ├── cite_skills/              ←   L3: robot-agnostic capability servers
│   ├── cite_orchestration/       ←   L4: behaviour trees and line coordination
│   │                                 — not in the main tree; runnable as
│   │                                 projects/01 (ADR-0069)
│   ├── cite_twin/                ←   L5: mode control, sync bridge, twin monitor
│   ├── cite_telemetry/           ←   L6: telemetry, recording, historian bridge
│   ├── cite_safety/              ←   cross-cutting: interlocks and limits
│   ├── cite_bringup/             ←   composed launch entry points
│   ├── cite_simulation/          ←   Gazebo systems, plugins, generated worlds
│   └── external/                 ←   imported by vcstool; never committed
│
├── tools/                        ← Host-agnostic Python tooling: the L0 validator,
│                                   the generators, the asset pipeline. No ROS
│                                   dependency, so it runs on any operating system.
│
├── assets/                       ← L1: 3D assets and the scan pipeline
│   ├── scans/                    ←   raw and processed capture data (not in git)
│   ├── meshes/                   ←   visual and collision meshes
│   ├── materials/
│   └── manifest.yaml             ←   provenance and checksums for external assets
│
├── hmi/                          ← L7: web operator interface        (Phase 4)
│
├── infra/docker/                 ← Container image and compose services
├── .devcontainer/                ← Editor devcontainer definition
├── .github/workflows/            ← CI
│
├── external/                     ← Pinned third-party sources: the vcstool manifest
│                                   and reviewable patch files. Never vendored.
│
├── requirements/                 ← Host Python dependencies, and the document
│                                   explaining which of the four dependency layers
│                                   each kind belongs in.
│
├── .claude/                      ← Agent configuration      (local; not committed)
│   ├── agents/                   ←   active subagent roles (11)
│   └── orchestration.md          ←   pipeline and dispatch routing
│
├── scripts/                      ← one command per task; the contract every tool
│                                   and agent invokes instead of colcon or docker
│
├── tests/                        ← System- and scenario-level tests
│
├── projects/                     ← frozen, runnable milestone snapshots (records,
│                                   not sources; ADR-0068)
│
└── docs/
    ├── adr/                      ← Architecture Decision Records
    ├── architecture/             ← Detailed per-layer design
    ├── interfaces/               ← Interface contract reference
    ├── operations/               ← Runbooks, bring-up, calibration, safety
    ├── onboarding/               ← Getting started, workflow, glossary
    └── reference/                ← Standards, literature, toolchain
```

**`legacy/` is gone.** The superseded v1 workspace was archived here for the length of the
rebuild and deleted at the end of Phase 1, as this tree said it would be. What it taught is
in `docs/reference/v1-lessons.md`, written before the deletion and anchored to the code that
proved each point; why it was replaced rather than migrated is **ADR-0001**. The tree itself
remains in version control, as §12 says — it is removed from the working tree, not from the
repository's history.

Three conventions in the tree above have their reasoning recorded rather than restated here:

- **`cite_generated/` is committed, not built.** Generated artifacts live in git and are
  verified against a fresh generator run, which is what makes hand-editing one detectable
  rather than merely forbidden. See **ADR-0021**.
- **QoS profiles are a library inside `cite_interfaces`, not a table each node copies.** An
  incompatible publisher/subscriber pair connects silently and delivers nothing, so the
  profiles are code with one definition rather than prose with many. See **ADR-0025**.
- **The `workspace/src/` tree above is the *production* structure. Packages that exist only
  to test it are deliberately not listed in it.** The first of them is `cite_test_hardware`,
  a `ros2_control` `SystemInterface` whose purpose is to make a fault happen on demand, and
  it is barred from production use by construction rather than by convention: its `on_init`
  refuses to initialise without a parameter that has nowhere to be declared in the L0 model,
  so it cannot be selected as the backend for an arm. What it is for, and why the fixture had
  to be a package rather than a flag on an existing one, is **ADR-0040**.
  **So `workspace/src/` contains a package this tree does not list, and that difference is
  this rule rather than drift.** `./scripts/doctor` counts every `package.xml` on disk, so its
  count answers what *exists*; this tree answers what is *production*, and the two are not
  meant to match. The next test-only fixture belongs outside this tree for the same
  reason. The precedent runs the other way only for production code: `cite_runtime` was added
  to this tree by explicit decision (**ADR-0034**, §14 v1.7) because it ships inside the
  running system, which a test fixture does not.
~~~~
### §8 Phase 2.A — the sub-phase as written up to v1.16

_Charter v1.16, lines 580-591._ Rewritten without its figures, dates and correction markers; each figure is in the ADR or campaign the passage cites.

~~~~markdown
**2.A — The twin mechanism against a virtual counterpart — IN PROGRESS: the pair comes up; nothing automated brings it up**
The plant is paired with a **virtual counterpart**: a complete second simulation of the same cell, generated from the same L0 model and modelled *as if it were physical*. **The paired cell is `cell_b` — one arm, one conveyor, one of everything — and both sides are digital.** That is the project owner's decision of 2026-09-18, recorded as **ADR-0059**, and it replaces what this paragraph said until that date: *"a complete second simulation of the same three-arm cell"* and *"the cell stays three-armed"*. **The three-arm cell is finished and set aside, not deleted**: it lives on as projects/01, a frozen, runnable snapshot outside the main tree, and nobody works on it further (**ADR-0069**, which removed the `cell_a` zone from the main tree and supersedes **ADR-0056**; **ADR-0068** for the snapshot). **What 2.A delivers is unchanged by which cell carries it** — the mechanism the twin is made of: mode switching and command routing, the mirroring path, and the monitor that will later compute fidelity, all exercised end to end before any hardware exists. That the counterpart is a full second simulation rather than a kinematic echo or a replayed trajectory is **ADR-0041**; the two defect classes that exist only because there are two sides are **ADR-0042** (transport partitioning per side) and **ADR-0043** (both sides held to the wall clock); and the twin boundary that serves a running pair is started by the pair supervisor on the join rather than by a launch file, which is **ADR-0057**. What a second cell costs was measured before the design fixed its shape — `docs/measurements/2026-08-28-second-world-cost/` — **on the three-arm cell, and it has not been re-taken for a one-arm pair.**

> **Both sides are simulated by refusal, not by convention, and this is what stands between 2.A and a physical machine today.** ADR-0048 clause 1 makes an asset whose two sides name different backends an **ERROR** at validate time, and a physical plant on a paired zone a second ERROR; measured on 2026-09-18 by building a scratch model, both fire and the model does not generate. **So the L5 command path cannot reach a physical actuator by any edit to the L0 model** — what protects it is a validate-time refusal rather than a safety layer, and that distinction must be carried rather than smoothed over. Lifting it is Phase 2.B's work.

> **What 2.A cannot claim, stated here rather than discovered later.** 2.A closes **no clause** of the exit criterion below, and **no number it produces is a fidelity measurement**. Both sides run the same L0 model, the same generated description and the same physics solver, so divergence measured across the pair is instrument, solver and scheduling noise; it is not a reality gap and does not become one by being plotted. Under §2's maturity model 2.A stays at level **L0**, however much of L5 it exercises: L1 and L2 are each defined by an information flow from the physical, and 2.A has no physical side. **2.A validates the instrument; 2.B is what first uses it.**

> **What exists, as of 2026-08-31: a pair comes up.** `./scripts/sim --pair` starts two independent launches and **joins** them — it does not sequence them — on a token each side prints from its own readiness witness, under a supervisor that owns the join and the pair's lifetime and holds no ROS context (**ADR-0047**). **Both isolations were verified at runtime rather than by reading the launch file:** one `/clock` publisher on each domain where a merged graph would show two, one Gazebo server per partition at different endpoints, and every name this project forms present exactly once on each side (**ADR-0044**, **ADR-0042**). That is the P2 property demonstrated rather than argued.
>
> **What is not built, in the same breath, because the bring-up half is the smaller one.** There is **no paired scenario, and none is possible in the present shape** — `launch_test` with `IncludeLaunchDescription` is one process holding one context on one domain — so **nothing automated brings a pair up**, and a regression in the witness, the token or either side's bring-up would not fail CI. The shipped model declares `single`, so a pair does not come up on a clean checkout. **[Marked 2026-09-18 — that last sentence is now false and the rest of this paragraph is not: **ADR-0059** declares `cell_b` `twin: {sides: pair}`, so `./scripts/sim --zone cell_b --pair` does bring a pair up from a clean checkout, and it has been run. `cell_a` still refuses. **What is unchanged is the half that matters here**: there is still no paired scenario, nothing automated brings a pair up, and a regression in the witness, the token or either side's bring-up still fails no gate. See the v1.13 entry in §14.]** **2.A still produces no fidelity number**, exactly as the note above says it cannot. And **ADR-0043's real-time requirement is still not shown to be met, though no longer for the reason this paragraph gave until 2026-09-01.** The figure it carried — both sides of a pair reaching about 0.95 against a required 1.0 — was a **throttled** reading, and with the generated world's `real_time_factor` in force a measured real-time factor is **capped at the declared factor by construction**, so it could not have exceeded 1.0 whatever the machine did; **ADR-0049** establishes that from upstream `gz-sim` source, and **ADR-0028**'s and **ADR-0043**'s 2026-09-01 corrections withdraw it. The condition stated beside that figure — convex hulls as *"not the shipped default"* — was stale in the same breath: they are the shipped selection since ADR-0028 was promoted. **Measured as capacity instead, with the throttle lifted, the configuration this repository ships clears ADR-0043's floor of 1.0 on both sides of a pair concurrently**, under a decision rule registered before the first trial — `docs/measurements/2026-09-01-capacity-on-shipped-main/`, whose figures stay there and are cited rather than copied. **Three qualifications travel with that, and a sentence dropping one is worse than the sentence it replaced.** Every capacity figure in that campaign is a **lower bound**, its host being contended and impossible to quiet, and that cuts one way only: the shipped configuration would clear the floor on a quiet machine, its vendor-mesh control's shortfall might not, and nobody may read that control as *"vendor meshes cannot reach 1.0"*. **Clearing a bare floor is not a margin** — **ADR-0049**, which restates this requirement as a capacity measurement plus a clock-deficit budget, sets **neither of its two thresholds** and is itself `Proposed`; the project owner ratified its decision on 2026-08-31, and ratification is not promotion. And it is **one machine, with every cell idle at home pose**: an idle baseline is not a work allowance.
>
> **Strength: three joined runs on one machine by the implementing agent, not re-taken by review, with no test and no CI run covering any of it.** That is why this sub-phase is marked in progress and not complete, and none of it closes any clause of the exit criterion below.
~~~~
### §8 Phase 2.B — the heterogeneous-fleet sentence

_Charter v1.16, lines 596-596._ Rewritten: it named a three-arm mix.

~~~~markdown
The architecture is designed for heterogeneous, incrementally-arriving hardware: the system runs correctly with one physical arm and two simulated ones, and gains arms without structural change.
~~~~
### §10.2 and §10.3 — the agent roster and change control

_Charter v1.16, lines 667-694._ The roster and the reasoning for it moved to `docs/onboarding/development-workflow.md`; change control points at `CLAUDE.md` §12.

~~~~markdown
### 10.2 AI agents in the workflow

AI agents are first-class participants in this project, with defined roles and defined limits. `CLAUDE.md` is the canonical rulebook loaded by every session and every agent; `AGENTS.md` points to it; the pipeline and dispatch routing are defined in `.claude/orchestration.md`.

**`.claude/` is local tooling and is not committed to this repository.** A fresh clone will not contain it, and every reference to it below describes a directory the reader may have to obtain separately. The rules the agents enforce are in `CLAUDE.md`, which *is* committed — so the standards survive without the tooling, and a contributor working without agents is held to exactly the same bar.

The active roster is ten roles in `.claude/agents/`:

- **Core pipeline** — `coder`, `reviewer`, `tester`, `fixer`.
- **Domain auditors** — `model-validator` (the L0 model and everything generated from it: schema, kinematic trees, inertia tensors, collision geometry, interface matching) and `safety-auditor` (every path that can produce motion: safety-layer bypass, E-stop propagation, limit enforcement, watchdogs, mode transitions).
- **Conditional specialists** — `architect-reviewer`, `debugger`, `performance-engineer`, `dependency-auditor`.

The two domain auditors exist because this project's most expensive failures are not ordinary bugs. A wrong inertia tensor produces a simulation that runs confidently and is wrong; an unguarded command path produces a physical arm that moves when nobody expected it. Neither is caught by ordinary code review.

Two roles are deliberately **absent** until Phase 4, when a historian and remote access give them a real domain: database and telemetry-schema review, and security auditing. They will be written then, against the domain they actually have to audit, rather than carried as dormant files — an agent with no live domain still competes for description-based routing and degrades dispatch accuracy for every other role.

The operating rules:

- **Agents propose; humans and tests decide.** No agent output merges without review and passing CI.
- **Agents are bound by this document.** An agent that produces work contradicting §4 or §9 is producing a defect.
- **Specialist review is routine, not exceptional.** Architecture, testing, security, dependency, and performance review agents run against changes as part of the normal flow rather than on request.
- **Documentation is written by the orchestrating session, when it needs writing, and verified by humans; there is no documentation agent.** Drift between code and documentation is treated as a defect (P7).

### 10.3 Change control

- **Architecture Decision Records** (`docs/adr/`) capture every significant technical decision: context, options considered, decision, consequences. An ADR is written *before* the decision is implemented, not after.
- **This document** is updated when direction changes, and only then (§0).
- **Commits and pull requests** describe intent and reference the ADR or phase item they serve.
~~~~
### §11 — the table of where things are written down

_Charter v1.16, lines 698-714._ Rewritten for the documents that exist after 2026-10-02.

~~~~markdown
## 11. Where things are written down

| Question | Where |
|---|---|
| What are we building and why? | **This document** |
| What are the rules for working here? | `CLAUDE.md` |
| Why was this technical choice made? | `docs/adr/` — one record per decision |
| How does layer *X* work in detail? | `docs/architecture/L*.md` |
| How does this relate to industry standards? | `docs/architecture/standards-alignment.md` |
| What is the shape of this interface? | `docs/interfaces/` and the interface packages |
| How do I get started? | `docs/onboarding/getting-started.md` |
| How do we work day to day? | `docs/onboarding/development-workflow.md` |
| What does this term mean here? | `docs/onboarding/glossary.md` |
| How do I bring up / calibrate / recover the cell? | `docs/operations/` |
| Where do I read more? | `docs/reference/` — standards, literature, toolchain |
| How should an AI agent behave here? | `CLAUDE.md` and `AGENTS.md` (committed); `.claude/orchestration.md` (local, not committed) |
| What is being worked on right now? | The issue tracker — **not** this document |
~~~~
### §13 — the closed xArm risk

_Charter v1.16, lines 740-740._ Shortened to a pointer at ADR-0003.

~~~~markdown
| ~~xArm ROS 2 support on Jazzy/Harmonic is incomplete~~ **Closed 2026-08-24** | — | Verified: the `jazzy` branch of `xarm_ros2` declares `gz_ros2_control`, `ros_gz_sim`, and `ros_gz_bridge` — full Gazebo Harmonic support. The upstream README still links to Gazebo Classic and is simply stale. Residual work is pinning to a commit SHA and confirming a real build. See ADR-0003. |
~~~~
