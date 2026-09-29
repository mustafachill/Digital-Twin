# Operations

Runbooks: what to do, in order, and what you should see.

- **Status:** `PARTIAL` — [bring-up.md](bring-up.md) and [troubleshooting.md](troubleshooting.md)
  describe a simulated cell that exists and commands that run. The other three describe
  procedures for parts of the system that are not built.
  **No procedure here is valid for physical hardware until Phase 2.**

| Runbook | For |
|---|---|
| [bring-up.md](bring-up.md) | Starting the system, simulated or physical |
| [calibration-and-registration.md](calibration-and-registration.md) | Establishing the correspondence between the real cell and the model |
| [safety-procedures.md](safety-procedures.md) | Anything involving physical motion |
| [recording-and-replay.md](recording-and-replay.md) | Capturing a run and replaying it |
| [troubleshooting.md](troubleshooting.md) | When something is wrong |

## How these are written

Each step states **what to do**, **what you should observe**, and **what to do when the
observation differs.** A runbook that only lists commands is useless at 2am, because the
commands are the easy part.

If a procedure here does not match reality, that is a defect in the runbook. Fix it in the
same session — a runbook nobody trusts is worse than none, because someone will follow it
anyway.

## Before anything involving physical hardware

Read [safety-procedures.md](safety-procedures.md). Not "skim" — read it. Nothing in this
repository commands a physical arm unless `CITE_ALLOW_HARDWARE=1` is set deliberately, and
that variable exists so that no one reaches hardware by accident.
