# Results: teardown signal deaths, `./scripts/scenario bringup`

Read [`criteria.md`](criteria.md) first. Its decision rules were fixed
before the first trial and are applied literally below, including where they
force an "inconclusive".

One machine (aarch64, Docker Desktop on macOS), one checkout with its own build
volumes, `de67d8b`, 2026-08-27. **Not a campaign.**

Relocated here from a top-level `measure/` directory on 2026-08-28. **No number,
no verdict and no sentence of the analysis was changed**; what changed is where
the files sit and the paths this write-up uses to name them. See
[*Provenance and relocation*](#provenance-and-relocation-2026-08-28) at the end,
and read it before quoting anything here as current.

## What was measured, and what was thrown away

| Set | Runs | Status |
|---|---:|---|
| pre-fix ([`raw/pre/`](raw/pre/)) | **30** | Valid. Ran 13:10-13:35, no foreign container present. |
| post-fix, clean ([`raw/post-clean/`](raw/post-clean/)) | **11** | Valid. Completed before 13:45:05. |
| post-fix, contended ([`raw/post-contended/`](raw/post-contended/)) | 7 | **Suspect.** Overlapped a `cite-*` container this agent did not start (`cite-agent-a498db94...`, created 13:45:05). Reported separately, never pooled. |
| post-fix, failed ([`raw/post-failed/`](raw/post-failed/)) | 12 | **Discarded.** Docker's image store threw `input/output error` on a blob and the image vanished; no container started, duration 0 s. |
| first attempt ([`raw/discarded-stalled-attempt/`](raw/discarded-stalled-attempt/)) | 7 | **Discarded entirely.** A harness stall gave run 6 a 1421 s duration and truncated run 7. Kept in `raw/discarded-stalled-attempt/` as a record, used for nothing. |

Discarding is stated rather than smoothed over: the contended and failed sets
are the exact conditions the brief warned corrupt a rate.

## Primary outcome, per pre-registered rule 1

**`skill_server` at -11: 0 events in 90 pre-fix teardowns.**

Rule 1 fires. The experiment is **INCONCLUSIVE for `skill_server`'s -11**: this
rig does not reproduce the defect, so the post-fix count of 0 in 33 teardowns
carries no information about it and **is not reported as a pass**. The single
`skill_server` -11 on record, from `continuous_line`, remains un-reproduced and
un-explained.

## Secondary outcomes

| Observable | pre-fix (30 runs) | post-fix clean (11 runs) | post-fix contended (7 runs) |
|---|---:|---:|---:|
| `class_loader` "objects ... exist in the heap" | **89** / 90 teardowns | **0** / 33 | 0 / 21 |
| `move_group` -11 | **90** / 90 | **33** / 33 | 21 / 21 |
| `skill_server` -11 | 0 / 90 | 0 / 33 | 0 / 21 |
| `skill_server` -9 (hang, then SIGKILL) | 1 / 90 | 0 / 33 | 0 / 21 |
| `parameter_bridge` -6 | 1 / 30 | 0 / 11 | 0 / 7 |
| `parameter_bridge` -11 | **1** / 30 | 0 / 11 | 0 / 7 |

### The leak is the one thing that moved deterministically

89 of 90 pre-fix `skill_server` teardowns emit the `class_loader` warning; the
missing 90th is the process that hung and was SIGKILLed before it reached exit,
which is consistent rather than an exception. Post-fix it is 0 of 54 across both
subsets. That is a **state**, not a rate, and it is what a P6 regression test
should assert.

### `move_group` -11 is invariant and upstream

90 of 90 pre-fix, 33 of 33 post-fix. Nothing our side did touched it, which is
what the backtrace already implied: frame #11 is `move_group`'s own `main`.

### Two events that cannot be turned into rates

`skill_server` -9 (1/90) and `parameter_bridge` -6 (1/30) are single events.
Nothing here distinguishes their post-fix counts of zero from chance.

### The one qualitatively new observation

**`parameter_bridge` exited -11 once** (run 25), immediately after logging
`signal_handler(SIGINT/SIGTERM)`. `parameter_bridge` links no MoveIt code at
all, so a SIGSEGV at teardown is not exclusive to MoveIt-linked processes.

---

## Provenance and relocation, 2026-08-28

### Where this came from, and why it nearly did not land

The measurement was taken on 2026-08-27 and committed to the branch
`evidence/teardown-signal-family` at `8b86223`, under a top-level `measure/`
directory that no convention in this repository provides for. That branch was
cut from an older `main` and **must not be merged**: work that has since landed —
`cite_skills/motion_end.hpp`, the whole of `cite_test_hardware/` and more — shows
up in its diff as deletions, because it did not exist when the branch was cut.

What was relocated on 2026-08-28 is the campaign's own files and nothing else,
copied out of that branch rather than merged from it. Every file was checked
byte-for-byte against the branch after the move.

| Was | Is now |
|---|---|
| `measure/PREREGISTERED.md` | [`criteria.md`](criteria.md) — renamed, contents untouched |
| `measure/RESULTS.md` | `results.md` — this file, with the notes below appended |
| `measure/analyse.py`, `measure/run.sh` | [`harness/`](harness/) |
| `measure/pre/`, `post-clean/`, `post-contended/`, `post-failed/`, `discarded-stalled-attempt/`, `stacks/` | [`raw/`](raw/), one subdirectory each |

### `PREREGISTERED.md` is this repository's `criteria.md`, and was renamed rather than rewritten

[`../README.md`](../README.md) defines `criteria.md` as "the question, the
thresholds, and the decision rule — **written and committed before the first
trial ran**". `PREREGISTERED.md` is exactly that and nothing else: it states the
question, the vehicle and why it was chosen, the sample size with the arithmetic
behind it, three numbered decision rules fixed in advance, and a co-primary
observable. It needed the filename the convention uses and nothing more.

It was therefore **renamed, with its bytes unchanged**. Rewriting a
pre-registration into a house style after the data exists would destroy the one
property that makes it a pre-registration, and the freeze rule in
[`../README.md`](../README.md) forbids it. The convention's boilerplate header
about being frozen is absent from this file; the sentence "Written **before** the
first trial of either arm" does that work, and it was there before the first run.

### "Not a campaign" is the author's sentence and it stays

The opening of this file calls the exercise "Not a campaign". That sentence is
kept verbatim, and it is not in conflict with this directory. What it disclaims
is **generalisation**: one machine, one architecture, one checkout, no claim
about anywhere else. What makes a directory belong here is a narrower thing —
thresholds written down and committed before the first trial — and this exercise
has that, which is why it is published rather than lost with its branch.

### The discarded sets are kept, and why each was discarded

Three sets are kept in `raw/` and used for nothing, which is the point of keeping
them. Their reasons are in the table at the top of this file; all three are
environmental rather than reasons to distrust the readings that were kept:

- [`raw/discarded-stalled-attempt/`](raw/discarded-stalled-attempt/) — the
  harness stalled. Its [`summary.txt`](raw/discarded-stalled-attempt/summary.txt)
  records six runs and stops; the seventh log exists and has no summary line,
  because the run it belongs to never finished. The set is a record of a broken
  measurement, not a measurement.
- [`raw/post-failed/`](raw/post-failed/) — Docker's image store failed. No
  container started in any of the twelve, so these logs contain **no teardown of
  any process**; there is nothing in them to count either way.
- [`raw/post-contended/`](raw/post-contended/) — a foreign `cite-*` container
  overlapped the runs. Reported in its own column above and never pooled with the
  clean set.

## Note, 2026-08-28 — the co-primary observable is evidenced in `raw/stacks/`, not in the tables above

[`criteria.md`](criteria.md) registers a co-primary that is a state rather than a
rate: `node.use_count()` at the end of `main`, and whether `~SkillServer` runs.
The tables above report only its proxy, the `class_loader` warning. The direct
observation is in [`raw/stacks/`](raw/stacks/), which the body of this file never
points at, and [`raw/stacks/README.md`](raw/stacks/README.md) describes what each
file there is.

The two tripwire logs read, in the two conditions
[`criteria.md`](criteria.md) named:

- [`raw/stacks/skill_server-gdb-cycle-intact.log`](raw/stacks/skill_server-gdb-cycle-intact.log)
  — `CITE_TRIPWIRE: use_count before return = 9`, then `main returning`, and no
  `~SkillServer` line at all.
- [`raw/stacks/skill_server-gdb-cycle-broken.log`](raw/stacks/skill_server-gdb-cycle-broken.log)
  — `use_count before return = 1`, then `~SkillServer entered` and
  `~SkillServer done`.

That is **one run in each direction**, on the `test_skill_contract` rig, exactly
the n `criteria.md` declared it had. It settles that the destructor does not run
while the reference cycle is intact, and **it settles nothing about the signal
deaths**: the primary outcome above is still inconclusive, and no mechanism
linking a skipped destructor to a SIGSEGV has been shown here.

[`raw/stacks/move_group-gdb-backtrace.log`](raw/stacks/move_group-gdb-backtrace.log)
carries the `move_group` SIGSEGV under `gdb`. Thread 1's frame #9 is
`moveit_cpp::MoveItCpp::~MoveItCpp()` and frame #11 is `main ()`, which is what
the "invariant and upstream" reading above rests on.

## Note, 2026-08-28 — the counts above were recomputed from `raw/`, and reproduce

`harness/analyse.py` was run again over the relocated logs on 2026-08-28, on a
copy placed where the script expects its inputs (see the next note). **Every
count in both tables above reproduced exactly**, and the `post-failed` set
confirmed to contain zero teardown samples of any process, consistent with no
container having started. Nothing in this file is restated here; the point of the
note is that the file and the data still agree after the move.

## Note, 2026-08-28 — the harness names paths that no longer exist, and is not edited

Both files in [`harness/`](harness/) resolve their paths relative to their own
location, and that location was `measure/` at the repository root when they ran:

- `analyse.py` reads `<the directory holding analyse.py>/<arm>/run*.log`. The log
  sets now live under `raw/`, so invoking it in place finds nothing.
- `run.sh` takes the repository root to be its own parent directory, and writes to
  `${ROOT}/measure/${ARM}`. Its own parent is now `docs/measurements/`, and
  `measure/` no longer exists anywhere in the tree.

**Neither file is corrected, and this note is the correction instead.**
`harness/` is the code that produced `raw/`; editing it makes it no longer that,
and [`../README.md`](../README.md) states the rule. A stale path inside a harness
is a fact about where the measurement was taken from; a fixed one is a claim about
code that never ran.

To recompute the counts without editing anything, copy the analyser next to the
sets it expects and run it from there:

```
cp docs/measurements/2026-08-27-teardown-signal-family/harness/analyse.py /tmp/analyse.py
cp -R docs/measurements/2026-08-27-teardown-signal-family/raw/pre /tmp/pre
python3 /tmp/analyse.py pre
```

`run.sh` cannot be re-run from its published location at all, and re-running it
would in any case produce a different measurement rather than this one.

## Note, 2026-08-28 — the tree has moved since `de67d8b`

Everything above was measured at `de67d8b`, which is an ancestor of `main`. Two
things about the distance between them matter when this campaign is cited:

- **The "pre-fix" arm is still the shipped configuration.** `move_group_.reset()`
  was never landed; a search of `workspace/src/cite_skills/` on 2026-08-28 found
  no such call, and the commit that published this campaign states that no fix was
  left in the tree. The `SkillServer` ownership of `MoveGroupInterface` that the
  pre-fix arm measured is the one the tree has.
- **`skill_server.cpp` is not the file that was measured.** It gained roughly a
  hundred lines between `de67d8b` and `main` at `c405051` — motion-end monitoring,
  `cite_skills/motion_end.hpp` and its tests. The diff between those two commits
  touches no line containing `shutdown`, `~SkillServer`, or a reset of
  `move_group_`; the only added line naming `move_group_` is a `getCurrentState`
  call. So the shutdown path is unchanged, and the process around it is not.

A teardown count taken here is therefore a reading on `de67d8b`, not a reading on
`main`. It is not re-measured, and no number above is adjusted for the difference.

## Note, 2026-08-28 — the raw logs also carry a `bringup` *cycle* failure rate, which this campaign did not set out to measure

Everything above counts teardowns. The scenario's own verdict is a different
question, and the logs carry it too — as `rc=` in
[`raw/pre/summary.txt`](raw/pre/summary.txt), and as the assertion text in the
runs themselves.

Five of the thirty pre-fix runs exited non-zero, and **they are not all teardown
failures**. Three failed the functional half, on `bringup`'s `MoveTo` assertion —
twice as "the goal was never accepted", once as "never returned a result". Two
failed on teardown alone, `parameter_bridge` at -11 and at -6. One run is in both
groups. The eleven clean post-fix runs all passed. The contended set has one
failure, a 30 s timeout waiting for the model version, in a set that was already
set aside.

**This was observed when the campaign was relocated. It is not a pre-registered
outcome and it is not a rate this rig was built to estimate**, and it changes
nothing above: a run that fails its cycle still tears its processes down, and
those teardowns are already in the counts. It is written down because
`./scripts/scenario bringup` is described elsewhere as a blocking CI gate and no
document reported that it had failed on this rig at all. Whether it still fails is
**unmeasured** — see the note above on how far the tree has moved since `de67d8b`.
