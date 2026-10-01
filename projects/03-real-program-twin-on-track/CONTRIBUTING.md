# Contributing

## Read first

1. [`what-we-are-doing.md`](what-we-are-doing.md) — what this project is and why.
2. [`CLAUDE.md`](CLAUDE.md) — the rules you will be held to.
3. [`docs/onboarding/getting-started.md`](docs/onboarding/getting-started.md) — get it
   running.
4. [`docs/onboarding/development-workflow.md`](docs/onboarding/development-workflow.md) —
   how work moves from idea to merge.

About two hours. It is less time than one rejected pull request.

## The short version

```bash
./scripts/bootstrap                                  # once
git checkout -b feat/<slug>                          # never work on main
# ... implement ...
./scripts/lint && ./scripts/build && ./scripts/test  # green before handing off
```

## Non-negotiables

Rejected in review without discussion ([`CLAUDE.md`](CLAUDE.md) §4):

- Hand-editing a generated artifact — change the facility model or the generator.
- Structured data in a `std_msgs/String`.
- `TimerAction` or `sleep` used to sequence startup.
- Copying third-party source into the tree instead of pinning it in the manifest.
- Marking something complete in documentation without a test proving it.
- Anything not in English.
- A value that now exists in two places.

Each of these has a reason, and each reason is a specific way the previous iteration of
this project failed. See [`docs/adr/`](docs/adr/README.md).

## Before a technical decision

If you are choosing a technology, moving an architectural boundary, or establishing a
convention others must follow, write an
[ADR](docs/adr/README.md) **first**. An ADR written afterwards is a justification.

## Two documents are protected

- **[`what-we-are-doing.md`](what-we-are-doing.md)** changes only by explicit decision of
  the project owner, with a version bump and a history entry. Never as a side effect of
  other work.
- **[`CLAUDE.md`](CLAUDE.md)** changes when a working rule genuinely changes — not to
  accommodate a change that violates it.

## Anything that can move a robot

Read [`docs/operations/safety-procedures.md`](docs/operations/safety-procedures.md) before
you write the code, not before you run it. Under
[ADR-0005](docs/adr/0005-ros2-control-sim-real-boundary.md) simulation code becomes
hardware code through a one-line configuration change, so write it as if it already is.

## When something is wrong

```bash
./scripts/doctor
```

Then [`docs/operations/troubleshooting.md`](docs/operations/troubleshooting.md).
