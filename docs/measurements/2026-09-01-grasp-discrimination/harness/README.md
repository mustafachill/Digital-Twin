# Harness — what separates a grasp from a stall on nothing

Three arms, three rigs, one predicate. Reproduction from the repository root **on the
host**:

```sh
# AR -- the two shipped arithmetics. Deterministic, no cell, seconds.
docs/measurements/2026-09-01-grasp-discrimination/harness/build_host.sh
.venv/bin/python docs/measurements/2026-09-01-grasp-discrimination/harness/measure_ar.py \
    --eval docs/measurements/2026-09-01-grasp-discrimination/harness/predicate_eval_host

# FP -- a stall on nothing. A real controller manager, no Gazebo. Minutes.
./scripts/enter dev bash -lc \
  "bash /workspace/docs/measurements/2026-09-01-grasp-discrimination/harness/run_fp.sh 3"

# FN -- a real grasp. The shipped cell, headless, two blocks of sixteen. Hours.
docs/measurements/2026-09-01-grasp-discrimination/harness/run_fn_campaign.sh
```

| File | What it does |
|---|---|
| `arithmetic.py` | the **reference** implementation. `criteria.md` §2's cross-check and the source of the sweep points, and **nothing else**. No reported figure comes from it. |
| `predicate_eval.cpp` | a batch front end for the **shipped** predicate. Contains no arithmetic of its own. |
| `build.sh` / `build_host.sh` | compile it, in the container and on the host, from `workspace/src/cite_skills` unmodified. Both record the two source hashes into `raw/`. |
| `measure_ar.py` | AR — both shipped derivations on the same inputs, plus the evaluation-point grid |
| `measure_fp.py` | FP — the twelve stop widths and the control, through `cite_test_hardware/JointStopSystem` |
| `run_fp.sh` | the FP block: domain guard, fixture presence check, one launch per stop width |
| `measure_fn.py` | FN — sixteen trials against one running cell, four commanded widths interleaved |
| `run_fn_block.sh` | one FN block: domain guard, bring-up, trials, teardown sweep. **FN_B1 used this.** |
| `run_fn_block_after_ready.sh` | the same block, gated on the cell's own `CITE_SIDE_READY` token before the harness starts. **FN_B2 used this**, after three attempts through `run_fn_block.sh` were discarded by V1 for reading the description before `robot_state_publisher` was serving. `measure_fn.py` — the code that produces every FN figure — is byte-identical for both. `ANALYSIS.md` deviation D-1. |
| `run_fn_campaign.sh` | two FN blocks with a quiesce and a load reading between them |
| `analyse.py` | `criteria.md` §7's decision rules, applied to `raw/` |

## Why the predicate is compiled rather than copied

This campaign's subject is **two derivations of one policy disagreeing** (ADR-0052 §5,
P1). A campaign that answered that with a third derivation would be measuring itself. So:

- the C++ side is `workspace/src/cite_skills/src/gripper.cpp`, compiled unmodified;
- the validator side is `cite_tools.validate.physical._grasp_discrimination_margin_m`,
  imported and called on the `AssetType` loaded from the shipped `model/`;
- `arithmetic.py` is used for neither.

`cite_skills` exports no library — `gripper.cpp` is compiled straight into `skill_server`
— so `predicate_eval` compiles the same translation unit rather than linking a built
artefact. Same source at the same commit; not the same object file. The two builds
(container `g++` 13.3, host Apple `clang` 17) are recorded separately in
`raw/predicate_eval_provenance.txt` and `raw/predicate_eval_host_provenance.txt`.

## Nothing here edits the tree

No `model/`, no `workspace/src/`, no `tools/`, no threshold anywhere. The FN arm runs the
cell exactly as it ships; its lever is a field on a `Pick` goal. The FP arm substitutes a
hardware plugin **inside its own expanded copy** of the description and asserts, before
substituting, that what it is replacing is the production backend (`criteria.md` V7).
