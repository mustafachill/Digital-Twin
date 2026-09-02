#!/usr/bin/env bash
# The whole campaign, in `criteria.md` section 6's registered order: B, then A, then D,
# then C. Run from the repository root ON THE HOST -- the container entry is host-side,
# the trials are not.
#
#   docs/measurements/2026-09-02-option-f-regions/harness/run_campaign.sh [arms...]
#
# With no argument it runs all four in order. Named arms run only those, which is what a
# resumed campaign needs; a block whose trials file already exists is SKIPPED rather than
# re-run, so a resumed campaign never silently tops a condition up (`criteria.md` V8).
#
# THE ORDER IS REGISTERED AND IS NOT A CONVENIENCE. B is the cheapest and the only one
# with no cell; A answers the question with the largest predicted effect; C is last
# because it is the one whose mechanism is least certain (section 2.2).
#
# TWO BLOCKS WHEREVER THE CELL IS BROUGHT UP, so that a block effect is visible and V6 can
# spend them. Three cycles over 13 widths and over 8 yaws do not divide evenly in two, so
# the split is two cycles in the first block and one in the second; the trials add up to
# section 6's 39 and 24, and the block a trial belongs to is on every record.
#
# QUIESCE 60 s between a teardown and the next bring-up, and record the host's load
# average at the start of every block. That is section 6, and it is a quiesce for an
# instrument rather than a step of any bring-up sequence -- nothing here waits for a cell
# to be ready by sleeping (P4); `run_cell_block.sh` gates on the cell's own token.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
IN_CONTAINER="/workspace/docs/measurements/2026-09-02-option-f-regions/harness"
mkdir -p "$RAW/logs"

ARMS=("$@")
if [ "${#ARMS[@]}" -eq 0 ]; then
    ARMS=(B A D C)
fi

collected() {
    [ -f "$RAW/${1}_trials.json" ]
}

quiesce() {
    echo "== quiescing 60 s =="
    sleep 60
    uptime | tee -a "$RAW/logs/campaign.log"
}

enter() {
    "$ROOT/scripts/enter" dev bash -lc "$1"
}

for arm in "${ARMS[@]}"; do
    case "$arm" in
        B)
            if collected B; then echo "== skip B (collected)"; continue; fi
            echo "===== Arm B: 5 jam positions x 3, relaunch-interleaved ====="
            quiesce
            enter "bash ${IN_CONTAINER}/run_arm_b.sh 3 B"
            ;;
        A)
            for block in 1 2; do
                LABEL="A_B${block}"
                CYCLES=$([ "$block" = 1 ] && echo 2 || echo 1)
                if collected "$LABEL"; then echo "== skip $LABEL (collected)"; continue; fi
                echo "===== Arm A block ${block}: ${CYCLES} cycle(s) over 13 widths ====="
                quiesce
                enter "bash ${IN_CONTAINER}/run_cell_block.sh a ${LABEL} --cycles ${CYCLES}"
            done
            ;;
        A_REFINE)
            # The refinement grid, whose STEP is registered in criteria.md section 5.1 and
            # whose INTERVAL is bracketed by the coarse data. Both bounds are given in mm
            # on the command line, so the bracket is visible in the shell history and in
            # this script rather than buried in a runner.
            LABEL="A_REFINE"
            LOW="${CITE_OFR_REFINE_LOW_MM:?set CITE_OFR_REFINE_LOW_MM from the coarse data}"
            HIGH="${CITE_OFR_REFINE_HIGH_MM:?set CITE_OFR_REFINE_HIGH_MM from the coarse data}"
            if collected "$LABEL"; then echo "== skip $LABEL (collected)"; continue; fi
            echo "===== Arm A refinement: [${LOW}, ${HIGH}] mm at 0.05 mm x 3 ====="
            quiesce
            enter "bash ${IN_CONTAINER}/run_cell_block.sh a ${LABEL} \
                     --refine-low-mm ${LOW} --refine-high-mm ${HIGH}"
            ;;
        D)
            for block in 1 2; do
                LABEL="D_B${block}"
                # The three Pick-at-48.0 refusal trials go in the FIRST block and command
                # no motion at all, so they cannot disturb the grasps they sit beside.
                REFUSALS=$([ "$block" = 1 ] && echo 3 || echo 0)
                if collected "$LABEL"; then echo "== skip $LABEL (collected)"; continue; fi
                echo "===== Arm D block ${block}: 4 pairs, ${REFUSALS} refusal trial(s) ====="
                quiesce
                enter "bash ${IN_CONTAINER}/run_cell_block.sh d ${LABEL} \
                         --pairs 4 --refusals ${REFUSALS}"
            done
            ;;
        C)
            for block in 1 2; do
                LABEL="C_B${block}"
                CYCLES=$([ "$block" = 1 ] && echo 2 || echo 1)
                if collected "$LABEL"; then echo "== skip $LABEL (collected)"; continue; fi
                echo "===== Arm C block ${block}: ${CYCLES} cycle(s) over 8 yaws ====="
                quiesce
                enter "bash ${IN_CONTAINER}/run_cell_block.sh c ${LABEL} --cycles ${CYCLES}"
            done
            ;;
        *)
            echo "unknown arm '${arm}'; expected B, A, A_REFINE, D or C" >&2
            exit 2
            ;;
    esac
done
echo "campaign runner done for: ${ARMS[*]}"
