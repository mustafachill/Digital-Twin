# Measurements — `02-fixed-program-pair`

This file is **this snapshot's measurement point**: from 2026-10-01 on, the measurements of the fixed-program pair are kept
here: a measurement taken of this snapshot is appended, dated, with
the command, the commit, the machine and who took it — with the tree-hash bump in
`projects/snapshots.yaml` that every change to a snapshot needs (main-repository
`docs/adr/0068-keep-proven-milestones-as-frozen-snapshots.md`, amendment of 2026-10-01).
Earlier campaigns whose subject is this milestone remain under the main repository's
`docs/measurements/`, frozen where they are (its review queue's Q84 sorts them).
Whether the snapshot builds and runs is not a measurement of it in this sense: those runs are
in `PROVENANCE.md`'s verification log and stay there.

## Where the text below came from

On 2026-10-01 the main repository's `CLAUDE.md` was cut back to the project's identity, goal
and working discipline. The measurements it held whose subject had left the main tree came
here; everything else it held went to the main repository's
`docs/reference/claude-md-review-queue.md`. Each section below names the lines of
`CLAUDE.md` it came from, at main-repository commit `960e6b4`
(`git show 960e6b4:CLAUDE.md`).

- **This is a CLOSED RECORD.** Every figure was true at the commit and on the date it names,
  and none has been re-measured. Do not append to these sections; add a new, dated one.
- **The text is verbatim**, with three mechanical changes: common leading indentation was
  removed; Markdown links were turned into plain-text paths, because this folder may be copied
  out of the repository; and a section header and source line were added above each excerpt.
- **Paths are main-repository paths.** Several do not exist inside this folder —
  `docs/measurements/`, `CLAUDE.md` and the charter are not part of the extract.
- **"Above", "below" and "this file" inside an excerpt refer to the old `CLAUDE.md`**, not to
  this file. Some excerpts begin or end mid-sentence where the original paragraph was split
  between destinations; each such cut is marked.

Little was recorded about this milestone in `CLAUDE.md` itself. The runs that verify this
snapshot are in `PROVENANCE.md`'s verification log; the decision it implements is
main-repository `docs/adr/0066-run-the-cell-from-a-fixed-program.md`.

## Scenario step names while `program_cycle` was advisory

_Source: `CLAUDE.md` lines 1048-1050 at `960e6b4`._

**There were FOUR such step names as of 2026-09-28** — the same grep on
`feat/fixed-program` adds `Simulation-in-the-loop scenario — program_cycle (advisory)`
(ADR-0066), so a restriction to the three below drops that scenario's verdict.
