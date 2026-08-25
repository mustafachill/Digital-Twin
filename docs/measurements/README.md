# Measurements

Published measurement campaigns. One directory per campaign, named
`YYYY-MM-DD-<question>`.

P8 says any fidelity claim is backed by a published metric. This directory is where that
metric goes, so that a claim can be checked instead of trusted. ADR-0029 is the first
decision in this repository whose evidence is a campaign here rather than a dated
inspection of code.

## The campaigns

| Campaign | Question | Answer, in one line |
|---|---|---|
| [`2026-08-25-friction-grasp/`](2026-08-25-friction-grasp/results.md) | Is a friction grasp in `cell_a` repeatable enough to build a scenario on? | Repeatable in **position**, not in **orientation**. 84 trials. Decided [ADR-0029](../adr/0029-simulated-grasping-by-friction.md). |
| [`2026-08-25-grasp-plane-offset/`](2026-08-25-grasp-plane-offset/ANALYSIS.md) | Does the grasp-plane offset cause the twist? | It causes the **high mode** and not the rest. Rotations above 20°: 12/20 uncorrected, 0/20 corrected. Up to 18.7° survives correction. |

Read the second alongside the first: it corrects two of the first campaign's published
readings, and the corrections are listed in its own *Corrections to the friction campaign*
section.

## What a campaign directory contains

| Path | What it is |
|---|---|
| `criteria.md` | The question, the thresholds, and the decision rule — **written and committed before the first trial ran** |
| `results.md` or `ANALYSIS.md` | The verdict against those thresholds, its deviations, and its threats to validity |
| `raw/` | What the harness recorded. Every figure in the write-up is derived from this |
| `harness/` | The code that produced `raw/`, and the reproduction command |

## Rules

- **`criteria.md` is frozen once the first trial has run.** A threshold moved after seeing
  the data is a threshold chosen by the data. Where an interpretation genuinely had to
  change, it is recorded as a numbered deviation in the write-up, applied to data already
  collected — never by re-running until the definition suited.
- **A campaign measures the simulator unless it says otherwise.** Nothing here evidences
  behaviour on the physical arm; the layout is `PROVISIONAL` and the physical scan is
  Phase 3 (charter §8).
- **Rates are rates over samples, not determinism claims.** Scenarios in this cell are not
  reproducible — see
  [`../architecture/cross-cutting-testing.md`](../architecture/cross-cutting-testing.md).
- **Do not restate a campaign's numbers elsewhere (P1).** Link to the directory. A number
  copied into a layer document is a number that will disagree with its source.
- **Interleave, do not block.** The offset campaign established that the twist in this cell
  is a two-state process, so a comparison split into consecutive blocks samples the two
  states unevenly and misleads. Alternate conditions against one running cell.
