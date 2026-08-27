# ADR-0035: Check the English-only rule by character signal, across the repository

- **Status:** Accepted (corrected 2026-08-27) — **the decision stands unchanged**: the
  instrument, the scope, the escape hatch and every rejected option are as decided. Three
  supporting claims were measured wrong and are corrected in place, each marked where it
  stands rather than withdrawn. (1) "Run unmodified against the archived v1 tree" reported
  only the first-party subset; both figures are now given, with the reproduction command.
  (2) The stated limit understated the gap — no Latin-script language other than Turkish is
  caught, not merely those inside Latin-1. (3) The claim that a file which cannot be decoded
  is reported was false for UTF-16, which was silently skipped; that is now a defect fixed
  rather than a limit accepted. See **Consequences**.
- **Date:** 2026-08-27
- **Deciders:** project owner, implementing agent
- **Related:** [ADR-0015](0015-english-only.md) (the rule this enforces),
  [ADR-0008](0008-external-dependencies-via-vcstool.md) (why vendor source is out of remit),
  charter §4 (P10), `CLAUDE.md` §3 (P10), §4 (standing prohibitions), §7 (`./scripts/lint`)

## Context

**P10 — "Everything in English" — is one of ten hard rules, and nothing checks it.** §4 lists
"any identifier, comment, or document not in English" among the standing prohibitions
"rejected in review, without discussion", and Phase 1.E describes the quality gates as
enforced. A search for any existing check across `scripts/`, `tools/`, `.github/` and
`.pre-commit-config.yaml` returns one unrelated hit, a `json.dumps(ensure_ascii=False)` in
`tools/cite_tools/model/export.py`.

[ADR-0015](0015-english-only.md) already predicted this ADR and never got it. Its
consequences section lists, as a benefit of the decision, that it is "machine-checkable: a
lint rule can catch violations, **which is what makes this a rule rather than an
aspiration**". No such rule was written.

**Review alone did not hold this line last time.**
[`docs/reference/v1-lessons.md`](../reference/v1-lessons.md) records that the English
requirement was written in this repository's second commit on 2025-11-25 and violated seven
days later, in `legacy/docs/HIZLITEST.md` on 2025-12-02. ADR-0015's own context section is
blunter: v1 mixed Turkish and English across 23 files "despite the project's own `GOALS.md`
explicitly requiring English-only, which is itself informative: **a rule nobody enforces is
not a rule**."

Two constraints are fixed and shape everything below.

**This repository's own prose is full of non-ASCII typography**, and it is legitimate. Em
dashes, box-drawing characters in architecture diagrams, `°`, `±`, `×`, `≤`, `→`, and Greek
letters used as mathematical notation. A check that fires on those is a check that is
disabled within a week, and a disabled check is worse than no check, because the gate then
reports a coverage it does not have — the failure mode `scripts/lint` already documents at
length for the ROS linter block.

**Turkish is the only language this project has ever leaked**, and the leak is well
documented, so unusually for a new gate there is a real corpus to measure a candidate
against rather than reason about: the archived v1 tree at `13b94a7`.

## Options considered

Every option below was measured, on the tree at this ADR's base commit (643 tracked files)
and against the v1 corpus at `13b94a7` (952 files, 833 decodable as text, of which 147 are
first-party and the rest vendored `xarm_ros2`). Both measurements were taken on one machine
on 2026-08-27, by one agent, with no thresholds registered beforehand — the size of the
evidence, not a campaign.

### Option A — Fail on any non-ASCII character

The obvious instrument, and it is dead on arrival. Measured on the current tree: **non-ASCII
appears in 89 of 89 Markdown files and 83 of 97 Python files**, plus every one of the fifteen
`scripts/*` entry points, 21 `.cpp`, 19 `.hpp` and 29 `.yaml` files. The dominant characters
are `—` (3442 occurrences), the box-drawing set (2229 for `─` alone), `§` (244) and `°` (208).

There is no version of this that survives contact with the repository. Rejected.

### Option B — Fail on any non-ASCII *alphabetic* character

A real narrowing: it drops all typography and punctuation and keeps only letters. Measured on
the current tree it reduces the field from thousands of lines to **28**. But the composition
of those 28 is what rejects it:

- **24 lines are mathematics.** `θ` for yaw in ADR-0033 and the conveyor-yaw campaign, `ρ`
  for a correlation coefficient in ADR-0029, `α` for a significance level, `Δ` for a
  difference, `ẋ` for a task-space velocity in ADR-0027.
- **2 lines are proper nouns** in [`docs/reference/literature.md`](../reference/literature.md)
  — *Söderlund* and *Wąsowski*, two cited authors.
- **2 lines are the actual Turkish**, in `docs/reference/v1-lessons.md`.

So the instrument is 26 false positives to 2 true positives, and the false positives are in
the two categories most likely to recur: this is a robotics project that will keep writing
`θ`, and a research project that will keep citing European authors. Silencing them would mean
exempting the Greek block and the Latin-1 diacritics — which is Option D arrived at
backwards, with the exemption list doing the work the instrument should have done. Rejected.

### Option C — A word-level signal (a list of Turkish function words)

Genuinely attractive, because it is the only candidate that can catch **Turkish written
without any Turkish-specific character**, which is the one gap in the chosen option. It was
measured rather than assumed, with a 52-word list of Turkish function words, against the v1
corpus.

It failed on false positives, badly, and the reason generalises. The two highest-scoring files
in the entire corpus were `uf_ros_lib/substitutions/controllers.py` (38 hits) and
`joint_limits.py` (34 hits) — **English Python whose every hit was a local variable named
`var`**. The next tier was `once`, which is English. `legacy/docs/GOALS.md`, which is written
in English, was flagged; the vendored `xarm_api.h` was flagged four times.

Pruning the list to unambiguous words removes most of its value, because **nearly every
Turkish function word unambiguous enough to keep already contains a Turkish-specific
letter** and is therefore already caught by Option D; what pruning leaves behind is the
short, ASCII, collision-prone tail. Measured directly: restricted to `legacy/docs/`, the
number of Turkish documents the word signal caught that the character signal missed was
**zero**, and the number of English documents it falsely flagged was one.

That is the wrong trade for a gate. Rejected as the primary instrument; the gap it would have
covered is recorded under *What this costs us* rather than papered over.

### Option D — A narrow character signal: letters that are specific to one language

Fail on the six letters specific to the Turkish alphabet — dotless i and dotted capital I
(`U+0131`, `U+0130`), s-cedilla in both cases (`U+015F`, `U+015E`) and g-breve in both cases
(`U+011F`, `U+011E`) — and on the code-point ranges of scripts that are not used to write
English at all (Cyrillic, Arabic, Hebrew, Devanagari, Thai, Hiragana, Katakana, CJK,
Hangul). Deliberately **not** included:

- **c-cedilla, o-diaeresis, u-diaeresis and the rest of Latin-1.** Shared with German,
  French, Hungarian, Swedish and Turkish alike, and with proper nouns. Including them costs
  a false positive on *Soderlund* — spelt with the diaeresis in
  [`docs/reference/literature.md`](../reference/literature.md) — today. Measured against the
  v1 corpus, including them buys **nothing**: 16 first-party files contain a shared
  diacritic, 17 contain a Turkish-specific letter, and the number of files containing a
  shared diacritic **but no** Turkish-specific letter is **zero**.
- **Greek.** Measured: 34 occurrences in this tree, every one of them mathematical notation.

Measured on the v1 corpus, this signal catches **17 first-party files** spanning `.md`,
`.py`, `.yaml`, `.txt`, `.world`, `.sdf` and `.config` — documentation, launch code, world
files and configuration, which is the full spread of the historical violation — and **6 of
the 6 Turkish documents** in `legacy/docs/`, `HIZLITEST.md` among them.

Measured on the current tree, it fires on **2 lines in 1 file**.

Chosen.

## Decision

**`./scripts/lint` fails when a tracked text file contains a letter specific to a language
other than English**, where "specific" means one of the six Turkish letters above or a
character in one of the named non-Latin script ranges. The code points, the script ranges
and the exemptions are **configuration** — `.english-only.yaml` at the repository root — and
the checker in `tools/cite_tools/english.py` is mechanism only (P5).

Four subordinate decisions carry as much weight as the instrument.

**The scope is every tracked file, prose documentation included.** This is the opposite of
what was expected going in, and the measurement is why: the typography argument that makes
prose the hard case for Options A and B does not apply to Option D at all, which fires on 2
lines of prose across the whole tree. Restricting the check to source would have discarded
**6 of the 17** v1 files it catches, including every Turkish document in `legacy/docs/` —
that is, the entire violation the rule was written for. A scope is a filter applied because
the instrument is imprecise; a precise enough instrument does not need one.

**The file set is a filesystem walk sharing `doclinks.py`'s remit**, extracted to
`tools/cite_tools/tree.py` so that the answer to "which files here are ours to check" exists
once (P1) rather than twice.

`git ls-files` was implemented first and rejected on evidence, which is worth recording
because the argument for it was good. It makes the file set a property of the *commit*
rather than of the machine — the lesson `doclinks.py` records after its own file count moved
between 88 and 100 depending on whether `vcs import` had run — and it excludes the vendor
tree, `.venv/`, build output and the `.claude/` agent worktrees for free. **It also does not
work here.** An agent worktree's `.git` is a *file* holding an absolute path into the parent
clone, and that path does not exist inside the container, so `git ls-files` fails outright
with `fatal: not a git repository` — measured by running `./scripts/enter dev ./scripts/lint`
in a worktree on 2026-08-27. The container is where the full gate runs, and worktrees are how
this project runs its agents. A discovery mechanism that works in a fresh clone and fails in
the setup actually in use is not a discovery mechanism.

The walk keeps the stability the git argument was really about, because the skip rules are
what made `doclinks.py`'s count stable in the first place. It also gains something: a lapse
is reported when the file is *written*, not when it is staged, which for a lint gate is the
more useful moment.

**The escape hatch is one exact path and one mandatory reason, and a stale entry fails the
gate.** No globs, no directory prefixes, no inline suppression comment. The precedent is the
teardown exemption in `tests/scenarios/continuous_line.py`, kept to "one signal, one process
name" and recorded in `CLAUDE.md` §2 as never having been widened. An inline marker is the
easiest possible hatch to reach and would make the rule optional; an exact path in a
configuration file makes every addition a visible diff on a small file that a reviewer will
read. Every run prints the exemptions it applied, so the list's growth is visible on every
invocation and not only at review time.

**The check's own machinery is written so that it does not trip its own rule.** A file that
declares "these characters are forbidden" naturally contains them, and so do an ADR arguing
about which letters to pick and a test proving the check catches them. The lazy resolution
is three more exemptions, which would triple the escape-hatch list on the day it was created
and with the author's own files. Instead the signal is declared as **code points**, this ADR
names the letters by description and code point, and `tools/tests/test_english.py` writes its
Turkish fixtures as `\u` escapes — so all three files are pure ASCII in the places that
matter and none of them needs exempting. The side benefit is real: a dotless i and an i are
hard to tell apart by eye, and a specification of characters should not depend on the reader
distinguishing them.

**There is exactly one exemption**, and it is the case the hatch was designed for:
`docs/reference/v1-lessons.md` quotes the original Turkish as primary-source evidence, with
an English rendering beside each quotation, and the analysis turns on the Turkish grammar —
the document explicitly reasons about the unstated subject of *gidecek*. Removing the Turkish
would destroy the argument that document exists to make.

## Consequences

### What this gets us

- The first automated enforcement of a `CLAUDE.md` §3 rule. Nine remain unchecked; this
  establishes the shape.
- **The shipped check, run unmodified against the archived v1 tree, reports 804 findings
  across 68 files. 214 of those, across 17 files, are first-party** — `legacy/docs/HIZLITEST.md`
  among them, the document the record names as the first violation. That is the check
  catching the lapse it was written for, rather than a prototype doing so. `./scripts/lint`
  runs in both CI jobs, so it gates every change from the day it lands.

  **Both numbers matter, and an earlier draft of this bullet gave only the second while
  calling the run "unmodified".** It was not: the 214/17 figure is the first-party *subset*.
  `SKIP_PATHS` anchors the vendor skip at `workspace/src/external`, and v1's vendored
  `xarm_ros2` lived at `legacy/xarm_ros2` instead, so a genuinely unmodified run walks it and
  reports it. The instrument is fine and the subset is the meaningful figure — no commit of
  ours may act on a finding inside pinned vendor source (ADR-0008) — but the sentence was
  doing unpaid work. Reproduce with:

  ```
  git archive 13b94a7 | tar -x -C <dir> && cp .english-only.yaml <dir>
  .venv/bin/python -m cite_tools.english <dir>
  ```

  Taken on one machine on 2026-08-27. Two of the 804 are the vendor tree's UTF-16 files,
  `xarm.rc` and `RCa02900`, which were silently skipped until the decode gap below was
  closed — the whole-tree figure was 802 across 66 files before that fix.
- It runs in the **host half** of `./scripts/lint`, which is the half that always runs. A
  macOS laptop silently skips the ROS linters; it does not skip this.
- Fast enough that nobody has a reason to route around it: **0.25 s** over ~640 files. The
  naive per-character implementation of the same rule took **15.7 s** on the same tree, which
  is why the signal is compiled to a single regular expression and each file is
  whole-text-rejected before any line is examined.
- Files that are not valid UTF-8 are **reported, not silently skipped**. A checker that
  cannot decode a file and says nothing is claiming a coverage it does not have. That now
  includes **UTF-16, with or without a byte-order mark**, which the first implementation
  dropped without a word: every ASCII character in UTF-16 is a byte and a NUL, so the
  binary-content test matched on the first letter and the file never reached the decode.
  It was a suppression route needing no configuration change and reachable by accident —
  Windows PowerShell and several editors write UTF-16 by default — and it was live on real
  content, hiding the two vendor files named above. A file whose NUL bytes all fall at one
  parity is decoded and reported instead; the parity test comes first because
  `decode("utf-16-le")` succeeds on almost any even-length input and would otherwise report
  every mesh in `assets/` as text.
- **A file whose own name spells a skipped directory is checked.** The first implementation
  tested every element of `Path.parts` against the skip list, and `parts` includes the
  basename — so on a whole-file walk it dropped `scripts/build`, one of the fifteen
  documented `./scripts/*` entry points, from the gate entirely. Demonstrated rather than
  argued: with a Turkish comment appended to that file the shipped checker reported "no
  non-English content" and exited 0. The predicate is now split — one form for directories,
  where the basename is a directory name and must match, one for files, where it must not.
  `doclinks.py` was never affected in practice, since it only ever passes `*.md` paths.
- **The file set no longer moves with local build state.** The walk and `git ls-files`
  return the same 648 files in a bootstrapped checkout on 2026-08-27. Packaging metadata
  under `tools/cite_tools.egg-info/` and the per-machine `.env` are skipped: the first is
  install output, and the second is the one file where a finding could be repaired by no
  commit and silenced by no shared exemption, since the escape hatch takes an exact path in
  a tracked file. `.env.example`, which is tracked, is checked.

### What this costs us

- **Turkish written entirely in ASCII is not caught.** This is the real limit, it is Option
  C's territory, and Option C was measured to cost more than it returns. A quoted `"Kolay"`
  on its own would pass. What makes the residual tolerable rather than fatal is that Turkish
  prose of any length reliably contains one of the six — measured at 6 of 6 on the only
  corpus available — but that is evidence from one corpus, not a proof, and review remains
  the backstop for the rest.
- **No Latin-script language other than Turkish is caught at all.** This is the honest form
  of the limit, and an earlier draft understated it by saying "a language with no character
  outside Latin-1 is not caught" and naming German, French, Spanish and Italian — which
  invites the inference that a language *with* characters outside Latin-1 is caught. It is
  not. Verified against 13 language samples on 2026-08-27: Polish, Czech, Hungarian, modern
  Romanian and Vietnamese all use Latin Extended characters and all pass this gate
  untouched. Modern Romanian is the sharpest case, because its `ș` and `ț` (U+0219, U+021B)
  are *distinct code points* from the cedilla forms and nothing in the signal covers them.
  What the check covers is the one language P10 has actually had to defend against, plus the
  non-Latin scripts, which are free to cover. Stated plainly rather than left for a reader
  to discover.
- **Turkish written with only the shared diacritics passes.** This is the specific price the
  Latin-1 exclusion buys, and it belongs here rather than only in the Option D section
  above, because the costs section is where a reader looks for limits. A Turkish sentence
  using `ç`, `ö` and `ü` but none of the six is not reported — confirmed directly. What the
  measurement showed is narrower than "no cost": adding the shared diacritics buys no
  additional *file* on the v1 corpus, because every first-party file carrying one also
  carries one of the six. It does not show that no such sentence can exist.
- **File-level recall is 17 of 17; line-level recall is about 78%.** Across those 17 v1
  files, 214 lines carry the signal and a further **59** carry only a shared diacritic —
  `legacy/docs/HIZLITEST.md` reports 3 lines and has a 4th. This does not weaken the gate,
  which is why file-level recall is the right headline: every one of the 17 fails either
  way. It matters to a *reader of the finding list*, who will undercount by a fifth how much
  of a file needs rewriting. The finding list is where to start, not the extent.
- **An exempt file is exempt as a whole.** A new Turkish paragraph added to
  `docs/reference/v1-lessons.md` would not be reported. The mitigation is that the list is
  one entry long, the file is a reference document that changes rarely, and every run prints
  the exemption being exercised.
- **`.claude/` is skipped, and [ADR-0015](0015-english-only.md) named part of it as in
  scope.** ADR-0015 extends P10 to "the report templates in `.claude/agents/`". Skipping the
  directory wholesale is still right — it holds agent worktrees, which are whole copies of
  this repository, so walking it reports every finding many times over against trees no
  commit can repair — but the consequence is that content another ADR placed in scope is
  covered by no gate. Nor could it be: `CLAUDE.md` §11 makes `.claude/` local tooling that is
  deliberately not committed, so a fresh clone does not contain it and CI never sees it. The
  gap is real, it is a property of that decision rather than of this one, and review remains
  the only thing covering those templates.
- One more configuration file at the repository root, and one more thing a contributor adding
  a legitimate citation has to learn about. The failure message names the file and the
  required shape, so the cost is bounded to reading one error.
- The check reads every tracked text file, including the 174 measurement CSVs. That is where
  most of the 0.25 s goes, and it is paid on every `./scripts/lint`.

### What we will have to revisit

- **If a second language leaks**, or the project takes on contributors writing in one, the
  signal set is data and gains a row without touching the checker. That is the point of P5
  here.
- **If the exemption list ever reaches a second or third entry**, the per-file granularity
  should be reconsidered before the list grows further — the precedent this borrows from is
  valuable precisely because it was never widened.
- **If a legitimate use of a listed script appears** — a cited Japanese paper title, a
  Cyrillic author name — that is an exemption on `docs/reference/literature.md` with a
  reason, not a reason to drop the range.
- **If ASCII-only Turkish is ever actually found in review**, Option C's word list should be
  reopened with that instance as its first measured true positive. The measurement above says
  the word list has no value today; it does not say it never will.
