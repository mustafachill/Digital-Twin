# Teardown signal-death investigation: raw evidence

All captured 2026-08-27 on one machine (aarch64, Docker Desktop on macOS),
one checkout with its own build volumes, at `de67d8b`.

The container **does** permit debugging, which is the finding that unblocked
everything else: `/usr/bin/gdb` is present, `ptrace` works, `ulimit -Hc` is
`unlimited`, and `/proc/sys/kernel/core_pattern` is the plain word `core`
(no pipe to a crash daemon). `gdb` was used rather than core files because
`core_pattern` carries no `%p`, so several crashing processes in one working
directory would overwrite each other's dump.

| File | What it is |
|---|---|
| `move_group-gdb-backtrace.log` | `move_group` under `gdb`, SIGSEGV caught with a full `thread apply all bt`. **The stack.** |
| `skill_server-gdb-cycle-intact.log` | `skill_server` under `gdb`, unmodified. Tripwire shows `use_count = 9` and `~SkillServer` never entered. |
| `skill_server-gdb-cycle-broken.log` | Same, with `move_group_.reset()`. Tripwire shows `use_count = 1` and `~SkillServer` entered and completed. |
| `skill_contract-baseline.log` | First `test_skill_contract` run, no debugger, showing the `class_loader` leak warning and `move_group` at -15. |
| `bringup-first-run.log` | First `./scripts/scenario bringup`, showing `move_group` at -11, `parameter_bridge` at -6, and one `class_loader` warning per `skill_server`. |

## The vehicle

`test_skill_contract.py` (`cite_skills`) launches `move_group` + `skill_server`
with **no simulator and no controllers** and reproduces the `move_group`
segfault on every run in about 90 s. `./scripts/scenario bringup` reproduces it
in about 40 s with the full cell. Neither needs `continuous_line`'s ~480 s.

## What is NOT here

**No `skill_server` backtrace, because `skill_server` never segfaulted.** Across
every run recorded here and the 5 clean baseline runs of the discarded first
measurement attempt, the tally of signal deaths was 18 x `move_group` -11,
3 x `move_group` -15 and 1 x `parameter_bridge` -6, and **zero** for
`skill_server`. The one `skill_server` -11 on record remains un-reproduced.
