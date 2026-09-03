#!/usr/bin/env bash
# The whole campaign, in `criteria.md` section 6's registered order. Run from the repository
# root ON THE HOST -- the container entry is host-side, the trials are not.
#
#   docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh [blocks...]
#
# DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh`,
# copied at commit `62051df`, for the `collected()` skip, the quiesce, the abort banner and
# `record_environment`; and from
# `docs/measurements/2026-09-02-scenario-ceilings/harness/run_campaign.sh` at `ee1c997` for
# `build_once`, which enforces BOTH halves of V11 rather than describing them. Both
# directories are FROZEN (`docs/measurements/README.md`) and nothing in either is edited
# from here.
#
# THE ORDER IS REGISTERED AND IS NOT A CONVENIENCE (`criteria.md` section 6). LO-C and HI-C
# must complete before any refinement, because a refinement's interval is LOCATED by them;
# INV depends on knowing which stops straddle; CTL is independent and runs last so that a
# failure in it cannot consume the campaign's time budget.
#
# WITH NO ARGUMENT THIS RUNS THE TWO COARSE BLOCKS AND STOPS. That is deliberate. A script
# that went on to refine would have to choose the refinement interval, and section 5.1 is
# explicit that the STEP is registered and the INTERVAL is located by the data -- by a
# person reading the coarse table, not by this file. The banner at the end says what to read
# and what to pass.
#
# A BLOCK THAT HAS ALREADY BEEN TAKEN IS SKIPPED rather than re-run, so a resumed campaign
# never silently tops a condition up (V8) -- and a block that ABORTED PART-WAY is skipped
# with a LOUD banner rather than with the same one-line "collected" a finished block gets.
# `measure.py` writes `<label>_complete.json` only after the last trial of the schedule, so
# the two states are distinguishable; before that marker existed they were not, and an
# aborted block was reported as done.
#
# A BLOCK THAT ABORTS STOPS THE CAMPAIGN, loudly, with the exit code captured rather than
# discarded.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
IN_CONTAINER="/workspace/docs/measurements/2026-09-03-stall-band-flip/harness"
mkdir -p "$RAW/logs"

BLOCKS=("$@")
if [ "${#BLOCKS[@]}" -eq 0 ]; then
    BLOCKS=(LO-C HI-C)
fi

# A block must not be re-run once it has been taken, whether it FINISHED or ABORTED --
# re-running either tops a condition up, which V8 forbids. But the two states are different
# findings and they are reported differently. `measure.py` writes `<label>_complete.json`
# only after the last trial of the schedule, so a trials file WITHOUT it is a block that
# died part-way. Skipping that silently, as a bare `-f <label>_trials.json` test does, is
# how an aborted block stops being visible as one.
#
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
        echo "## up. analyse.py reports it with the n it reached -- every cycle that" >&2
        echo "## CLOSED carries its V1 flag and survives; the cycle that was open" >&2
        echo "## when it died carries none and its rows are dropped." >&2
        echo "## Read ${RAW}/logs/${label}_harness.log." >&2
        echo "########################################################################" >&2
        return 0
    fi
    return 1
}

quiesce() {
    echo "== quiescing 30 s (criteria.md section 6) =="
    sleep 30
    uptime | tee -a "$RAW/logs/campaign.log"
}

# V11, ENFORCED rather than described. `./scripts/build` runs ONCE, before the first trial.
# It refuses to build a second time once any trial record exists or once `provenance.txt`
# already carries a build block -- so a RESUMED campaign, which this script advertises, does
# not rebuild the workspace under itself -- and it ABORTS the campaign when the build fails
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

# `criteria.md` section 9's isolation values and the gates that run clean before the first
# trial. Appended ONCE at the start of a campaign run, from the host, because the isolation
# values are the host script's. It appends and never truncates: `build_superseded.sh` writes
# V12's provenance into the same file and this must not remove it.
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
        # rather than restated here (P1) -- and read UNDER BASH, by absolute path.
        # `_lib.sh` computes `REPO_ROOT` from `${BASH_SOURCE[0]}`, which no other shell
        # sets; sourcing it from the campaign shell derives a project name and a domain
        # that are BOTH WRONG and look exactly as plausible as the right ones.
        eval "$(bash -c '. "$1/scripts/_lib.sh" >/dev/null 2>&1
            # %q, not %s: `CITE_PROJECT_SOURCE` is a SENTENCE, and an unquoted assignment
            # of it through `eval` sets the first word and then tries to RUN the second.
            printf "CITE_CPN=%q\nCITE_RDI=%q\nCITE_SRC=%q\n" \
                "${COMPOSE_PROJECT_NAME:-<unset>}" "${ROS_DOMAIN_ID:-<unset>}" \
                "${CITE_PROJECT_SOURCE:-<unset>}"' _ "$ROOT")"
        echo "compose_project_name=${CITE_CPN}"
        echo "ros_domain_id=${CITE_RDI}"
        echo "compose_project_source=${CITE_SRC}"
        echo "git_head=$(git -C "$ROOT" rev-parse HEAD)"
        echo "criteria_sha256=$(sha256sum "$RAW/../criteria.md" | cut -d' ' -f1)"
        echo "gz_note=this rig starts no Gazebo-transport process at all, so no GZ_PARTITION binds here"
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

# One refinement. Its two endpoints arrive on the environment so that the LOCATED interval
# is visible in the shell history and in this script rather than buried in a runner, and
# `measure.py` REFUSES a pair that is not an adjacent pair of the arm's own coarse grid.
refine() {
    local label="$1" low_var="$2" high_var="$3"
    local low="${!low_var:-}" high="${!high_var:-}"
    if [ -z "$low" ] || [ -z "$high" ]; then
        echo "ABORT: ${label} is a refinement and needs ${low_var} and ${high_var}, the" >&2
        echo "       two endpoints of the coarse interval the coarse stage LOCATED." >&2
        echo "       criteria.md section 5.1: the step is registered and the interval is" >&2
        echo "       located by the data. Read the coarse table first." >&2
        exit 2
    fi
    if already_taken "$label"; then return 0; fi
    echo "===== ${label}: 6 stops at 0.05 mm across [${low}, ${high}] mm x 3 ====="
    quiesce
    run_one "$label" \
        "bash ${IN_CONTAINER}/run_block.sh ${label} --low-mm ${low} --high-mm ${high}"
}

# `criteria.md` section 6's REGISTERED ORDER, enforced rather than emergent. The order is
# not a convenience: LO-C and HI-C must complete before any refinement, because a
# refinement's interval is LOCATED by them; INV depends on knowing which stops straddle;
# CTL runs last so that a failure in it cannot consume the campaign's time budget.
#
# It used to be enforced only INDIRECTLY -- `refine` refuses a coarse pair that is not
# adjacent on the arm's own grid, and INV refuses a wrong stop count, so an operator who
# had not read the coarse table could not supply the arguments. That is a real constraint
# and it is why nothing was ever mis-ordered, but it is emergent: it holds because of what
# the refinements happen to require, not because this script checks. A requested list is
# now required to be a SUBSEQUENCE of the registered order.
#
# THE ORDER IS READ FROM `common.BLOCK_ORDER` AND NOT RESTATED HERE (P1). `common.py`
# imports nothing but the standard library at module level, so this works on the host,
# where this script runs.
ORDER="$(PYTHONPATH="$HERE" python3 -c \
    'import common; print(" ".join(common.BLOCK_ORDER))' 2>/dev/null)"
if [ -z "$ORDER" ]; then
    echo "ABORT: could not read criteria.md section 6's block order from common.py." >&2
    echo "       The order is registered there and is not restated in this script." >&2
    exit 2
fi

enforce_order() {
    local remaining=" ${ORDER} " block
    for block in "${BLOCKS[@]}"; do
        case " ${ORDER} " in
            *" ${block} "*) ;;
            *)
                echo "ABORT: unknown block '${block}'. criteria.md section 6 registers" >&2
                echo "       ${ORDER}" >&2
                exit 2 ;;
        esac
    done
    for block in "${BLOCKS[@]}"; do
        case "$remaining" in
            *" ${block} "*) remaining=" ${remaining#*" ${block} "}" ;;
            *)
                echo "" >&2
                echo "ABORT: '${BLOCKS[*]}' is not in criteria.md section 6's" >&2
                echo "       registered order, which is:" >&2
                echo "           ${ORDER}" >&2
                echo "       '${block}' appears after a block that follows it there," >&2
                echo "       or twice. The order is REGISTERED and is not a" >&2
                echo "       convenience: a refinement's interval is LOCATED by the" >&2
                echo "       coarse stage, INV depends on knowing which stops straddle," >&2
                echo "       and CTL runs last so a failure in it cannot consume the" >&2
                echo "       campaign's time budget. Re-run with the blocks in order." >&2
                exit 2 ;;
        esac
    done
}

enforce_order
build_once
record_environment

for block in "${BLOCKS[@]}"; do
    case "$block" in
        LO-C|HI-C)
            if already_taken "$block"; then continue; fi
            echo "===== ${block}: 9 coarse stops at 0.25 mm x 2, relaunch-interleaved ====="
            quiesce
            run_one "$block" "bash ${IN_CONTAINER}/run_block.sh ${block}"
            ;;
        LO-F) refine LO-F CITE_SBF_LO_F_LOW_MM CITE_SBF_LO_F_HIGH_MM ;;
        HI-F) refine HI-F CITE_SBF_HI_F_LOW_MM CITE_SBF_HI_F_HIGH_MM ;;
        LO-S) refine LO-S CITE_SBF_LO_S_LOW_MM CITE_SBF_LO_S_HIGH_MM ;;
        INV)
            STOPS="${CITE_SBF_INV_STOPS_MM:-}"
            if [ -z "$STOPS" ]; then
                echo "ABORT: INV needs CITE_SBF_INV_STOPS_MM, the FOUR fine-grid stops" >&2
                echo "       straddling F's two verdict changes (criteria.md 5.2)." >&2
                exit 2
            fi
            if already_taken INV; then continue; fi
            echo "===== INV: 4 straddling stops at the second command x 3 ====="
            quiesce
            run_one INV "bash ${IN_CONTAINER}/run_block.sh INV --stops-mm ${STOPS}"
            ;;
        CTL)
            if already_taken CTL; then continue; fi
            echo "===== CTL: no stop, plain mock, x 3 ====="
            quiesce
            run_one CTL "bash ${IN_CONTAINER}/run_block.sh CTL"
            ;;
        *)
            echo "unknown block '${block}'; criteria.md section 6 registers" >&2
            echo "LO-C, HI-C, LO-F, HI-F, LO-S, INV, CTL" >&2
            exit 2
            ;;
    esac
done

echo "campaign runner done for: ${BLOCKS[*]}"
if [ "$#" -eq 0 ]; then
    cat <<'BANNER'

========================================================================
The two COARSE blocks are done and this script has stopped on purpose.

criteria.md section 5.1: the STEP is registered and the INTERVAL is
LOCATED BY THE DATA -- by a person reading the coarse table, not by this
script. Read it:

    python3 docs/measurements/2026-09-03-stall-band-flip/harness/analyse.py

then pass the located intervals and re-run, for example:

    CITE_SBF_LO_F_LOW_MM=<a> CITE_SBF_LO_F_HIGH_MM=<b> \
    CITE_SBF_HI_F_LOW_MM=<c> CITE_SBF_HI_F_HIGH_MM=<d> \
    CITE_SBF_LO_S_LOW_MM=<e> CITE_SBF_LO_S_HIGH_MM=<f> \
        docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh \
            LO-F HI-F LO-S

    CITE_SBF_INV_STOPS_MM=<w,x,y,z> \
        docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh INV

    docs/measurements/2026-09-03-stall-band-flip/harness/run_campaign.sh CTL

Each pair must be an ADJACENT pair of that arm's own coarse grid, and the
runner refuses anything else. No stop outside the two coarse spans is run,
whatever the coarse grid shows.
========================================================================
BANNER
fi
