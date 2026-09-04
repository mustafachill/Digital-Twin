#!/usr/bin/env bash
# The whole campaign, in `criteria.md` section 6's registered order. Run from the repository
# root ON THE HOST -- the container entry is host-side, the trials are not.
#
#   docs/measurements/2026-09-04-following-error/harness/run_campaign.sh [blocks...]
#
# DERIVED FROM `docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh`, copied
# at commit `8a35a03`, the commit that file last landed at -- `already_taken`, `build_once`,
# `quiesce`, `record_environment`, `enter`, `run_one` and the abort banner. That directory is FROZEN
# (`docs/measurements/README.md` rule 2) and nothing in it is edited from here.
#
# THREE BLOCKS, THREE BRING-UPS, 126 TRIALS. `criteria.md` section 6: a block is ONE cell
# bring-up; within it a cycle visits CRUISE, FAST, CARRY, CONC in that order; three cycles a
# block. Two blocks is the minimum that can show a block difference at all and three lets V6
# see one without the campaign resting on a single bring-up.
#
# A BLOCK THAT HAS ALREADY BEEN TAKEN IS SKIPPED rather than re-run, so a resumed campaign
# never silently tops a condition up (V8) -- and a block that ABORTED PART-WAY is skipped with
# a LOUD banner rather than with the same one-line "collected" a finished block gets.
# `measure.py` writes `<label>_complete.json` only after the last trial of the schedule, so
# the two states are distinguishable.
#
# A BLOCK THAT ABORTS STOPS THE CAMPAIGN, loudly, with the exit code captured rather than
# discarded.
#
# THE SHAKEDOWN IS NOT RUN FROM HERE. `criteria.md` section 10 permits exactly ONE shakedown
# per harness, it is NOT DATA, and it writes into `raw/shakedown/`. It is a separate,
# deliberate invocation -- see `README.md` -- so that it cannot be swept into a campaign run
# by habit.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
IN_CONTAINER="/workspace/docs/measurements/2026-09-04-following-error/harness"
mkdir -p "$RAW/logs"

BLOCKS=("$@")
if [ "${#BLOCKS[@]}" -eq 0 ]; then
    BLOCKS=(B1 B2 B3)
fi

# Returns 0 when the block must not be run.
already_taken() {
    local label="$1"
    if [ -f "$RAW/${label}_complete.json" ]; then
        echo "== skip ${label} (collected, ran to the end of its schedule)"
        return 0
    fi
    if [ -f "$RAW/${label}_trials.json" ]; then
        echo "" >&2
        echo "########################################################################" >&2
        echo "## ${label} is PARTIAL. ${label}_trials.json exists with no" >&2
        echo "## ${label}_complete.json beside it, so that block ABORTED part-way." >&2
        echo "## criteria.md V8: n is what it was. It is NOT re-run and NOT topped" >&2
        echo "## up. analyse.py reports it with the n it reached -- and V1's closing" >&2
        echo "## reading is taken AT the abort, so its rows carry their flag and" >&2
        echo "## survive. Read ${RAW}/logs/${label}_harness.log." >&2
        echo "########################################################################" >&2
        return 0
    fi
    return 1
}

# `criteria.md` section 6 and section 7.0: 30 s between a teardown and the next bring-up. IT
# SEQUENCES NOTHING. V13 requires the cell's own readiness EVENT, so the standing prohibition
# on sleeping to sequence startup (CLAUDE.md section 4, P4) is not in play. It exists so that
# a torn-down block's processes and their discovery state are gone before the next bring-up.
quiesce() {
    echo "== quiescing 30 s (criteria.md section 6) =="
    sleep 30
    uptime | tee -a "$RAW/logs/campaign.log"
}

# V11, ENFORCED rather than described. `./scripts/build` runs ONCE, before the first trial. It
# refuses to build a second time once any trial record exists or once `provenance.txt` already
# carries a build block -- so a RESUMED campaign, which this script advertises, does not
# rebuild the workspace under itself -- and it ABORTS the campaign when the build fails
# instead of recording an exit code and carrying on against a stale install.
build_once() {
    local out="$RAW/provenance.txt"
    if [ -n "$(find "$RAW" -maxdepth 1 -name '*_trials.json' -print -quit 2>/dev/null)" ]; then
        echo "== V11: trial records exist, so the build is NOT re-run =="
        return 0
    fi
    if [ -f "$out" ] && grep -q '^# ---- ./scripts/build ----$' "$out"; then
        echo "== V11: provenance.txt already carries a build block, so the build is NOT re-run =="
        return 0
    fi
    echo "== V11: ./scripts/build, once, before the first trial =="
    {
        echo "# ---- ./scripts/build ----"
        "$ROOT/scripts/build" 2>&1 | tee "$RAW/logs/build.log" \
            | grep -Ei "summary|failed|error" | tail -20
        echo "build_exit=${PIPESTATUS[0]}"
    } >> "$out"
    local code
    code="$(grep '^build_exit=' "$out" | tail -1 | cut -d= -f2)"
    if [ "${code:-1}" -ne 0 ]; then
        echo "ABORT: ./scripts/build exited ${code}. V11 puts the build before the first" >&2
        echo "       trial; running against a stale install would measure a cell nobody" >&2
        echo "       committed." >&2
        exit "$code"
    fi
}

# `criteria.md` section 9's isolation values and the environment the campaign ran in.
# Appended ONCE at the start of a campaign run, from the host, because the isolation values
# are the host script's. It appends and never truncates.
record_environment() {
    local out="$RAW/provenance.txt"
    {
        echo "# ---- campaign environment, recorded by run_campaign.sh ----"
        echo "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "blocks_requested=${BLOCKS[*]}"
        echo "host_uname=$(uname -a)"
        echo "host_uptime=$(uptime)"
        echo "host_loadavg=$(cat /proc/loadavg 2>/dev/null)"
        # Both are derived per checkout by `scripts/_lib.sh`, so they are read through it
        # rather than restated here (P1) -- and read UNDER BASH, by absolute path. `_lib.sh`
        # computes `REPO_ROOT` from `${BASH_SOURCE[0]}`, which no other shell sets; sourcing
        # it from the campaign shell derives a project name and a domain that are BOTH WRONG
        # and look exactly as plausible as the right ones.
        eval "$(bash -c '. "$1/scripts/_lib.sh" >/dev/null 2>&1
            # %q, not %s: `CITE_PROJECT_SOURCE` is a SENTENCE, and an unquoted assignment of
            # it through `eval` sets the first word and then tries to RUN the second.
            printf "CITE_CPN=%q\nCITE_RDI=%q\nCITE_SRC=%q\n" \
                "${COMPOSE_PROJECT_NAME:-<unset>}" "${ROS_DOMAIN_ID:-<unset>}" \
                "${CITE_PROJECT_SOURCE:-<unset>}"' _ "$ROOT")"
        echo "compose_project_name=${CITE_CPN}"
        echo "ros_domain_id=${CITE_RDI}"
        echo "compose_project_source=${CITE_SRC}"
        echo "git_head=$(git -C "$ROOT" rev-parse HEAD)"
        echo "criteria_sha256=$(sha256sum "$RAW/../criteria.md" | cut -d' ' -f1)"
        echo "vendor_pin_manifest=$(grep -Eo '[0-9a-f]{40}' "$ROOT/external/cite.repos" | head -1)"
        VENDOR_TREE="$ROOT/workspace/src/external/xarm_ros2"
        echo "vendor_pin_checkout=$(git -C "$VENDOR_TREE" rev-parse HEAD 2>/dev/null \
            || echo '<absent>')"
        echo "gz_note=this rig BRINGS GAZEBO UP, so V12 binds: every Gazebo-transport call in"
        echo "gz_note=the harness goes through cite_bringup.gz and the launch carries the"
        echo "gz_note=partition itself (ADR-0042)"
    } >> "$out"
}

# Runs one block inside the container and RETURNS ITS CODE. Nothing here swallows it.
enter() {
    "$ROOT/scripts/enter" dev bash -lc "$1"
}

run_one() {
    local label="$1" command="$2" code=0
    enter "$command" || code=$?
    if [ "$code" -ne 0 ]; then
        echo "" >&2
        echo "########################################################################" >&2
        echo "## BLOCK ${label} ABORTED, exit ${code}. THE CAMPAIGN STOPS HERE." >&2
        echo "## criteria.md V8: n is what it was. A block that aborted is reported" >&2
        echo "## with the n it actually reached and is NEVER topped up -- and the" >&2
        echo "## next block is not run over the top of it. Read" >&2
        echo "## ${RAW}/logs/${label}_harness.log before doing anything else." >&2
        echo "########################################################################" >&2
        exit "$code"
    fi
}

record_environment
build_once

for label in "${BLOCKS[@]}"; do
    case "$label" in
        B1|B2|B3) ;;
        *)
            echo "ABORT: '${label}' is not a registered block. criteria.md section 6" >&2
            echo "       registers B1, B2 and B3 and nothing else. A shakedown is run" >&2
            echo "       through run_cell_block.sh with --shakedown; see README.md." >&2
            exit 2
            ;;
    esac
    if already_taken "$label"; then continue; fi
    echo ""
    echo "===== ${label}: one bring-up, 3 cycles, 14 trials a cycle ====="
    quiesce
    run_one "$label" "bash ${IN_CONTAINER}/run_cell_block.sh ${label}"
done

echo ""
echo "== every requested block is collected. Read the result with:"
echo "     python3 ${HERE}/analyse.py > /tmp/following_error_analysis.txt"
echo "   THE PRINT IS THE PRODUCT AND IT IS LONG. Redirect it; do not pipe it through"
echo "   \`head\` -- a previous operator did, saw 143 lines of 1034, and \`tee\` still"
echo "   exited 0."
