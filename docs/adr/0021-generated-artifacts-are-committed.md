# ADR-0021: Commit generated artifacts, in one generated package

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0004, ADR-0013, ADR-0020, [L0](../architecture/L0-facility-model.md)

## Context

[ADR-0004](0004-facility-model-single-source-of-truth.md) requires that worlds,
descriptions, controller configurations and launch graphs are generated from the L0 model,
that generation is byte-identical across runs, and that hand-editing a generated artifact
is a Critical review finding "enforced by the `model-validator` agent comparing against a
fresh generator run".

That enforcement sentence assumes something ADR-0004 never states: that there is a
committed artifact to compare a fresh run *against*. Whether generated files live in git or
are produced during the build is still open, and it has to be settled before the first
generator is written, because it determines where output lands, what CI can check, and
whether `./scripts/build` depends on the host Python environment.

Fixed constraints: the artifacts must be reachable by `package://` from four ROS packages;
`tools/cite_tools` has no ROS dependency and must stay that way ([ADR-0013](0013-host-agnostic-tooling.md));
and a fresh clone plus bootstrap must build.

## Options considered

### Option A — Produce at build time, gitignore the output
`./scripts/build` runs the generator before colcon, or a CMake custom command does.

Genuinely attractive: a hand-edit cannot be committed, so it cannot survive review. Pull
requests contain only model and generator changes — literally what ADR-0004 asks reviewers
to read. No merge conflicts in generated files.

Rejected on four counts. **CI can no longer detect a hand-edit, because there is nothing to
compare against** — the enforcement mechanism ADR-0004 and `L0-facility-model.md` both
specify stops existing, and both documents would need rewriting to say something weaker.
Determinism loses most of its purpose: byte-identical to *what*? The review signal that a
10 cm model edit produced exactly these four lines of SDF disappears, and that signal is
most valuable precisely while the generator is the component most likely to be wrong. And
it puts the host Python virtualenv on the ROS build's critical path, which is the coupling
ADR-0013 exists to prevent.

### Option B — Commit, scattered into the consuming packages
`cite_description/urdf/generated/`, `cite_control/config/generated/`, and so on. Rejected:
the hand-edit check then has four roots, and each package becomes a mixture of authored and
generated files. That mixture is how "just this one file, just this once" happens.

### Option C — Commit, in one wholly generated package
A single `workspace/src/cite_generated/` containing every generated artifact, including its
own `package.xml` and `CMakeLists.txt`. Chosen.

## Decision

Generated artifacts are **committed to git**, in a single package
`workspace/src/cite_generated/` that is generated in its entirety — nothing in it is
authored, including its build files. It carries a `GENERATED` marker file, and every
emitted file carries a header naming the generator and the command that regenerates it.

`cite-model generate` writes it. `cite-model validate` regenerates into a temporary
directory and fails if the result differs from the committed tree — that single whole-tree
diff is the hand-edit check, and it catches an added file, a missing file, or one changed
byte anywhere. `./scripts/validate-model` runs it, so CI runs it, on a job that needs no
ROS at all.

`./scripts/build` stays a pure `colcon` call with no dependency on the Python tooling.

The consuming packages — `cite_description`, `cite_control`, `cite_simulation`,
`cite_bringup` — declare `<exec_depend>cite_generated</exec_depend>` and contain **only
mechanism**: launch logic, plugins, RViz configurations. No facts about the facility.

The model's content hash is written to exactly one file, `cite_generated/MODEL_HASH`, and
not into every artifact's header — otherwise every model change churns every file and the
review signal this decision exists to preserve is destroyed by its own banner. That file is
also what satisfies L6's requirement that a recording carries the facility model version.

## Consequences

### What this gets us
- The hand-edit check works, by the exact mechanism ADR-0004 already assumes.
- Determinism has a stable target, so the byte-identical requirement earns its keep.
- Every model change shows its full effect in review, in the same diff.
- `./scripts/build` remains a pure colcon invocation, and a fresh clone builds without the
  host virtualenv.
- A contributor on macOS can read exactly what the Linux machine will load.

### What this costs us
- **Large diffs.** A layout change touches every generated file. Mitigated with
  `.gitattributes` marking the tree `linguist-generated`, which collapses it in review
  while keeping it diffable — but it is still noise, and it is the real price here.
- **Merge conflicts** when two people change the model at once. Resolved by regenerating,
  and the conflict is itself a useful signal.
- Someone will eventually hand-edit and push. That is what CI catches; it is the point,
  not a flaw. But it means the failure is discovered in CI rather than being impossible.
- One more package in the workspace whose build files nobody may edit.

### What we will have to revisit
If, by the end of Phase 1, generated diffs are measurably harming review, flip to
Option A and replace the hand-edit check with "the directory is absent from git" — a
strictly simpler check that costs the review signal. The flip is cheap in that direction
and expensive in the other, which is part of why this option is first.
