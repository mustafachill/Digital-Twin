#!/usr/bin/env bash
# The whole campaign, in `criteria.md` section 6's registered order. Run from the
# repository root ON THE HOST: `docker update` is host-side, and so are I5 and I6.
#
#   docs/measurements/2026-09-02-scenario-ceilings/harness/run_campaign.sh [labels...]
#
# With no argument it runs the whole schedule below in order. Named labels run only those,
# which is what a resumed campaign needs; a run whose record already exists is SKIPPED
# rather than re-run, so a resumed campaign never silently tops a condition up
# (`criteria.md` V8).
#
# DERIVED IN SHAPE FROM
# `docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh`, copied at
# commit `62051df` -- the `collected()` skip, the quiesce, the abort banner and the
# `record_environment` block that derives the isolation values through `scripts/_lib.sh`
# under bash are that file's. That directory is FROZEN and nothing in it is edited here.
#
# THE ORDER IS REGISTERED AND IS NOT A CONVENIENCE. Section 6 fixes it in three parts,
# because an earlier draft's order could not be executed against its own totals:
#
#   * Opening block -- one FULL run of each scenario, 3 runs. Enough to show the harness
#     parses a record from each scenario at the condition Q-A and Q-C rest on.
#   * Interleaved body -- the remaining 7 FULL runs and all 16 loaded runs, cycling
#     FULL / C4 / C2 / C1 and taking the scenarios in rotation, so that no condition is
#     taken in one consecutive block.
#   * Closing block -- the last 2 FULL runs, taken last.
#
# 3 + 7 + 2 = 12 FULL, and 12 + 16 = 28, which is section 6's minimum. FULL runs therefore
# appear at both ends and throughout, which is what makes a host drift over the campaign's
# duration visible as scatter WITHIN a condition rather than as a difference BETWEEN
# conditions.
#
# THESE ARE MINIMUMS AND NOT QUOTAS. A run that aborts is reported with the n it reached
# and is NEVER topped up (V8). If a run aborts, the schedule is not re-planned to restore
# the shape.
#
# A 60 s QUIESCE between a teardown and the next bring-up, with the survivor check that
# V5 spends. It is a quiesce for an instrument and not a step of any bring-up sequence --
# nothing here waits for a cell to be ready by sleeping (P4); `scripts/scenario` gates on
# the launch graph's own readiness.
#
# NOTHING HERE EDITS THE TREE. `criteria.md` section 0 forbids editing `model/`,
# `workspace/src/`, `tools/`, `tests/` and `scripts/`; V1 discards any run taken while one
# of those five differs from the base commit, and this script writes only under `raw/`.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
mkdir -p "$RAW/logs"

# The registered schedule: "<LABEL> <CONDITION> <SCENARIO>", in order.
SCHEDULE=(
    # -- opening block, one FULL run of each scenario ---------------------------
    "FULL_bringup_1 FULL bringup"
    "FULL_pick_and_place_1 FULL pick_and_place"
    "FULL_continuous_line_1 FULL continuous_line"
    # -- interleaved body, 7 FULL + all 16 loaded ------------------------------
    "FULL_bringup_2 FULL bringup"
    "C4_pick_and_place_1 C4 pick_and_place"
    "C2_continuous_line_1 C2 continuous_line"
    "C1_bringup_1 C1 bringup"
    "FULL_pick_and_place_2 FULL pick_and_place"
    "C4_continuous_line_1 C4 continuous_line"
    "C2_bringup_1 C2 bringup"
    "C1_pick_and_place_1 C1 pick_and_place"
    "FULL_continuous_line_2 FULL continuous_line"
    "C4_bringup_1 C4 bringup"
    "C2_pick_and_place_1 C2 pick_and_place"
    "C1_continuous_line_1 C1 continuous_line"
    "FULL_bringup_3 FULL bringup"
    "C4_pick_and_place_2 C4 pick_and_place"
    "C2_continuous_line_2 C2 continuous_line"
    "C1_bringup_2 C1 bringup"
    "FULL_pick_and_place_3 FULL pick_and_place"
    "C4_continuous_line_2 C4 continuous_line"
    "C2_bringup_2 C2 bringup"
    "FULL_continuous_line_3 FULL continuous_line"
    "C4_bringup_2 C4 bringup"
    "C2_pick_and_place_2 C2 pick_and_place"
    "FULL_bringup_4 FULL bringup"
    # -- closing block, the last 2 FULL runs -----------------------------------
    "FULL_bringup_5 FULL bringup"
    "FULL_pick_and_place_4 FULL pick_and_place"
)

WANTED=("$@")

collected() {
    [ -f "$RAW/${1}.json" ]
}

quiesce() {
    echo "== quiescing 60 s, then checking for survivors (V5) =="
    sleep 60
    uptime | tee -a "$RAW/logs/campaign.log"
    pgrep -af "gz sim" | tee -a "$RAW/logs/campaign.log" || true
}

# Section 9's environment block, appended ONCE at the start of a campaign run, from the
# host. It appends and never truncates.
record_environment() {
    local out="$RAW/provenance.txt"
    {
        echo "# ---- campaign environment, recorded by run_campaign.sh ----"
        echo "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "labels_requested=${WANTED[*]:-<all>}"
        echo "host_uname=$(uname -a)"
        echo "host_uptime=$(uptime)"
        echo "host_loadavg=$(cat /proc/loadavg)"
        # Both derived per checkout by `scripts/_lib.sh`, so they are read THROUGH it
        # rather than restated here (P1) -- and read UNDER BASH, by absolute path.
        # `_lib.sh` computes `REPO_ROOT` from `${BASH_SOURCE[0]}`, which no other shell
        # sets; sourcing it from anything else derives a project name and a domain that
        # are both wrong and look exactly as plausible as the right ones.
        eval "$(bash -c '. "$1/scripts/_lib.sh" >/dev/null 2>&1
            # %q, not %s: CITE_PROJECT_SOURCE is a SENTENCE, and an unquoted assignment
            # of it through `eval` sets the first word and then tries to RUN the second.
            printf "CITE_CPN=%q\nCITE_RDI=%q\nCITE_SRC=%q\n" \
                "${COMPOSE_PROJECT_NAME:-<unset>}" "${ROS_DOMAIN_ID:-<unset>}" \
                "${CITE_PROJECT_SOURCE:-<unset>}"' _ "$ROOT")"
        echo "compose_project_name=${CITE_CPN}"
        echo "ros_domain_id=${CITE_RDI}"
        echo "compose_project_source=${CITE_SRC}"
        echo "git_head=$(git -C "$ROOT" rev-parse HEAD)"
        echo "base_commit=c38a42c"
        echo "criteria_sha256=$(sha256sum "$RAW/../criteria.md" | cut -d' ' -f1)"
        echo "image_id=$(docker image inspect --format '{{.Id}}' cite-digital-twin:dev)"
    } >> "$out"
}

# V11 -- THE BUILD RUNS ONCE, BEFORE THE FIRST TRIAL, AND THE SCRIPT ENFORCES THAT.
#
# This block used to sit inside `record_environment`, which is called unconditionally on
# every invocation, while the header above advertises resumption. So resuming a campaign
# rebuilt the workspace mid-campaign -- which V11 makes a NUMBERED DEVIATION requiring
# every run before it to be reported separately from every run after it -- and nothing
# detected it. Two guards, either of which is sufficient: a run record already exists, or
# provenance already carries a build block.
#
# AND THE BUILD IS GATED. `build_exit` was recorded and never read, so a FAILED build let
# the campaign proceed against a stale install and produce twenty-eight runs of intervals
# measured on code that is not the code the record names. `set -e` is deliberately NOT
# turned on for the whole script -- `pgrep`, `grep`, `wanted` and `run_trial.py` all
# return non-zero on purpose here, and the abort logic below depends on reading those
# codes rather than dying on them -- so the one status that must stop the campaign is
# checked explicitly.
build_once() {
    local out="$RAW/provenance.txt" status
    if [ -n "$(ls -1 "$RAW"/*.json 2>/dev/null)" ]; then
        echo "== V11: run records already exist; ./scripts/build is NOT re-run." \
            | tee -a "$out"
        echo "build_skipped=run records already present at $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            >> "$out"
        return 0
    fi
    if grep -q '^# ---- \./scripts/build, recorded once for V11' "$out" 2>/dev/null; then
        echo "== V11: provenance.txt already carries a build block; not building again." \
            | tee -a "$out"
        echo "build_skipped=provenance already carries a build block at $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            >> "$out"
        return 0
    fi
    echo "# ---- ./scripts/build, recorded once for V11 ----" >> "$out"
    "$ROOT/scripts/build" > "$RAW/logs/build.log" 2>&1
    status=$?
    grep -Ei "summary|failed|error" "$RAW/logs/build.log" | tail -10 >> "$out"
    echo "build_exit=${status}" >> "$out"
    if [ "$status" -ne 0 ]; then
        echo "" >&2
        echo "######################################################################" >&2
        echo "## ./scripts/build FAILED, exit ${status}. THE CAMPAIGN STOPS HERE." >&2
        echo "## Every interval below would be measured against a STALE install," >&2
        echo "## and the record would name a build that did not produce it." >&2
        echo "## See $RAW/logs/build.log." >&2
        echo "######################################################################" >&2
        exit "$status"
    fi
}

wanted() {
    local label="$1" candidate
    [ "${#WANTED[@]}" -eq 0 ] && return 0
    for candidate in "${WANTED[@]}"; do
        [ "$candidate" = "$label" ] && return 0
    done
    return 1
}

record_environment
build_once

for entry in "${SCHEDULE[@]}"; do
    read -r LABEL CONDITION SCENARIO <<<"$entry"
    wanted "$LABEL" || continue
    if collected "$LABEL"; then
        echo "== skip ${LABEL} (collected). V8: it is not re-run over the top of itself."
        continue
    fi
    echo "===== ${LABEL}: ${SCENARIO} at ${CONDITION} ====="
    quiesce
    CODE=0
    "$HERE/run_trial.py" --label "$LABEL" --condition "$CONDITION" \
        --scenario "$SCENARIO" --out "$RAW" || CODE=$?
    # A NON-ZERO CODE IS NOT AN ABORT. `scripts/scenario` exits 1 when a scenario fails,
    # and a failed scenario is DATA here: rule X refuses its cycle record, rule X2 admits
    # every other one, and rule F reads the failure text. What stops the campaign is a
    # missing record file, which means the runner itself did not finish.
    if ! collected "$LABEL"; then
        echo "" >&2
        echo "######################################################################" >&2
        echo "## ${LABEL} WROTE NO RECORD, exit ${CODE}. THE CAMPAIGN STOPS HERE." >&2
        echo "## criteria.md V8: n is what it was. A run that aborted is reported" >&2
        echo "## with the n it reached and is NEVER topped up -- and the next run" >&2
        echo "## is not taken over the top of it." >&2
        echo "######################################################################" >&2
        exit "${CODE:-1}"
    fi
    echo "== ${LABEL} recorded (scenario exit ${CODE}; a failed scenario is data)"
done

echo "campaign runner done for: ${WANTED[*]:-<all>}"
