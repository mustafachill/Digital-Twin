#!/usr/bin/env bash
# The whole campaign, in `../criteria.md` section 6's registered order. Run from
# anywhere, ON THE HOST -- the container entries are host-side, the probe trials
# are not.
#
#   docs/measurements/2026-09-22-is-a-run-reproducible/harness/run_campaign.sh
#
# DERIVED FROM `docs/measurements/2026-09-04-following-error/harness/run_campaign.sh`,
# copied at commit `30d916c` -- the commit that file last landed at -- for
# `already_taken`, `build_once`, `record_environment` and the abort banner; and
# from `docs/measurements/2026-08-31-capacity-and-clock-deficit/harness/run_campaign.sh`
# at `28de922` for `sweep`'s container check. Both directories are FROZEN
# (`docs/measurements/README.md` rule 2) and nothing in either is edited here.
#
# THE ORDER IS REGISTERED AND IS NOT A CONVENIENCE. `../criteria.md` section 6,
# V-order: arms A and B alternate -- A B A B A B A B A B -- so that drift in
# machine state over the block does not align with the condition. The
# directory README's "interleave, do not block" cannot apply within a run when
# the condition IS the run: two seeds cannot share a bring-up. The departure is
# registered there rather than taken silently, and this loop is what implements
# the compensation. THEN A' twice, THEN C twice, THEN S.
#
# V-CONTAINER IS A REFUSAL, NOT A WARNING. `docker ps` must be empty before
# every block. CLAUDE.md section 2 records that a run taken while a `dev`
# container is up is not a reading of this repository -- `exec_in_container`
# reuses it with `compose exec`, which does not run the entrypoint, and
# nothing of ours executes at all.
#
# IT IS RESUMABLE. A trial whose record exists is SKIPPED rather than re-run,
# so an interrupted campaign continues rather than topping an arm up (V8).
# `build_once` refuses to rebuild once any record exists (V6).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="$HERE/../raw"
IN_CONTAINER="/workspace/docs/measurements/2026-09-22-is-a-run-reproducible"
PROVENANCE="$RAW/provenance.txt"
mkdir -p "$RAW" "$RAW/shakedown"

# The registered values are read from `common.py` rather than restated here: a
# seed written in two places is a value in two places (P1), and the one that
# reaches `gz sim` would be this copy.
ask() { python3 -c "import sys; sys.path.insert(0, '$HERE'); import common; print($1)"; }
SEED_A="$(ask 'common.SEED_A')"
read -r -a SEEDS_B <<<"$(ask "' '.join(str(s) for s in common.SEEDS_B)")"
PERTURBATION="$(ask 'repr(common.PERTURBATION_M)')"

fail() {
    echo "" >&2
    echo "########################################################################" >&2
    echo "## $1" >&2
    echo "## THE CAMPAIGN STOPS HERE. criteria.md V8: n is what it was, and an" >&2
    echo "## arm is never topped up. Read $RAW before doing anything else." >&2
    echo "########################################################################" >&2
    exit "${2:-1}"
}

# V-container, checked before every block and REFUSING rather than reporting.
require_no_container() {
    local left
    left="$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$left" != "0" ]; then
        docker ps --format '{{.Names}} {{.Image}} {{.Status}}' >&2
        fail "V-container: ${left} container(s) are running before block '$1'." 2
    fi
}

# V6, ENFORCED rather than described: the workspace is built ONCE, before the
# first block, and never again inside a campaign. A resumed campaign does not
# rebuild the workspace under itself.
build_once() {
    if [ -n "$(find "$RAW" -maxdepth 1 -name '*.json' -print -quit 2>/dev/null)" ]; then
        echo "== V6: trial records exist, so the build is NOT re-run =="
        return 0
    fi
    if [ -f "$PROVENANCE" ] && grep -q '^# ---- ./scripts/build ----$' "$PROVENANCE"; then
        echo "== V6: provenance.txt already carries a build block; NOT re-run =="
        return 0
    fi
    echo "== V6: ./scripts/build, once, before the first block =="
    mkdir -p "$RAW/logs"
    {
        echo "# ---- ./scripts/build ----"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        "$ROOT/scripts/build" 2>&1 | tee "$RAW/logs/build.log" \
            | grep -Ei 'summary|failed|error' | tail -20
        echo "build_exit=${PIPESTATUS[0]}"
    } >> "$PROVENANCE"
    local code
    code="$(grep '^build_exit=' "$PROVENANCE" | tail -1 | cut -d= -f2)"
    if [ "${code:-1}" -ne 0 ]; then
        fail "./scripts/build exited ${code}. V6 puts the build before the first block;
## running against a stale install would measure a cell nobody committed." "$code"
    fi
}

# `../criteria.md` section 9 and I4, recorded once per campaign run. It appends
# and never truncates.
record_environment() {
    {
        echo "# ---- campaign environment, recorded by run_campaign.sh ----"
        echo "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "host_uname=$(uname -a)"
        echo "host_uptime=$(uptime)"
        echo "host_loadavg=$(cat /proc/loadavg 2>/dev/null)"
        echo "git_head=$(git -C "$ROOT" rev-parse HEAD)"
        echo "git_status_porcelain<<EOF"
        git -C "$ROOT" status --porcelain
        echo "EOF"
        # V1's ancestry clause, stated rather than assumed.
        if git -C "$ROOT" merge-base --is-ancestor "$(ask 'common.BASE_COMMIT')" HEAD; then
            echo "base_commit_is_ancestor=true"
        else
            echo "base_commit_is_ancestor=false"
        fi
        echo "criteria_sha256=$(sha256sum "$HERE/../criteria.md" | cut -d' ' -f1)"
        echo "probe_template_sha256=$(sha256sum "$HERE/probe.sdf.in" | cut -d' ' -f1)"
        echo "vendor_pin_manifest=$(grep -Eo '[0-9a-f]{40}' "$ROOT/external/cite.repos" | head -1)"
        echo "seed_a=${SEED_A}"
        echo "seeds_b=${SEEDS_B[*]}"
        echo "perturbation_m=${PERTURBATION}"
        echo "probe_iterations=$(ask 'common.PROBE_ITERATIONS')"
        echo "docker_ps_at_start<<EOF"
        docker ps --format '{{.Names}} {{.Image}} {{.Status}}'
        echo "EOF"
    } >> "$PROVENANCE"
}

# One probe trial, inside a FRESH container. `./scripts/enter` is
# `docker compose run --rm`, so the container is destroyed when the trial
# returns and no orphaned `gz sim` can hold the next trial's partition -- which
# `require_no_container` then checks rather than assumes.
probe() {  # probe <arm> <index> <seed> <x-offset> <out-dir> <label> [extra...]
    local arm="$1" index="$2" seed="$3" offset="$4" out="$5" label="$6"; shift 6
    if [ -f "${out}/${label}.json" ]; then
        echo "== skip ${label} (collected)"
        return 0
    fi
    require_no_container "$label"
    echo ""
    echo "===== ${label}: arm ${arm}, seed ${seed}, x offset ${offset} ====="
    local out_in_container="/workspace${out#"$ROOT"}"
    "$ROOT/scripts/enter" dev bash -lc \
        "python3 ${IN_CONTAINER}/harness/trial_probe.py \
            --arm ${arm} --index ${index} --seed ${seed} --label ${label} \
            --x-offset ${offset} --out ${out_in_container} $*"
    local code=$?
    # An instrument loss is exit 5 and is DATA (V11): it is counted and
    # reported, not treated as a broken run. Anything else stops the campaign.
    case "$code" in
        0|5) ;;
        *) fail "trial ${label} exited ${code}, which is neither collected (0) nor an
## instrument loss (5)." "$code" ;;
    esac
}

cell() {  # cell <index>
    local index="$1" label
    label="$(printf 'C_%02d' "$index")"
    if [ -f "${RAW}/${label}.json" ]; then
        echo "== skip ${label} (collected)"
        return 0
    fi
    require_no_container "$label"
    echo ""
    echo "===== ${label}: arm C, ./scripts/scenario pick_and_place --zone cell_b ====="
    # ON THE HOST. `./scripts/scenario` re-executes itself into the container
    # and the reader needs a container of its own; see trial_cell.py's header
    # for why the order matters.
    python3 "$HERE/trial_cell.py" --index "$index" --seed "$SEED_A" --out "$RAW"
    local code=$?
    case "$code" in
        0|5) ;;
        *) fail "trial ${label} exited ${code}." "$code" ;;
    esac
}

echo "== docs/measurements/2026-09-22-is-a-run-reproducible =="
record_environment
build_once

# ---- the one permitted shakedown (`../criteria.md` section 6) -------------
# NOT DATA. It is published under `raw/shakedown/`, it is excluded from every
# figure by three independent refusals in `analyse.py`, and it may not set or
# adjust any threshold in `../criteria.md`. If it reveals a defect, the harness
# is fixed and the criteria is not touched.
if [ -f "$RAW/shakedown/SHAKEDOWN_01.json" ]; then
    echo "== skip the shakedown (already run; section 6 permits exactly one)"
else
    echo ""
    echo "===== SHAKEDOWN: one probe trial, NOT DATA ====="
    # Arm A's shape, so that the shakedown exercises the path a campaign trial
    # takes -- and carrying `is_shakedown`, which is what excludes it.
    probe A 1 "$SEED_A" 0.0 "$RAW/shakedown" SHAKEDOWN_01 --shakedown
fi

# ---- arms A and B, alternating (V-order) ----------------------------------
for i in 1 2 3 4 5; do
    probe A "$i" "$SEED_A" 0.0 "$RAW" "$(printf 'A_%02d' "$i")"
    probe B "$i" "${SEEDS_B[$((i - 1))]}" 0.0 "$RAW" "$(printf 'B_%02d' "$i")"
done

# ---- arm A', the sensitivity control --------------------------------------
# The same seed as arm A. The ONLY difference is the 1e-6 m offset in x.
for i in 1 2; do
    probe Aprime "$i" "$SEED_A" "$PERTURBATION" "$RAW" "$(printf 'Aprime_%02d' "$i")"
done

# ---- arm C, the whole cell ------------------------------------------------
for i in 1 2; do
    cell "$i"
done

# ---- arm S, the symbol scan -----------------------------------------------
if [ -f "$RAW/symbol_scan.txt" ]; then
    echo "== skip arm S (collected)"
else
    require_no_container "S"
    echo ""
    echo "===== S: the symbol scan, with its command written down ====="
    bash "$HERE/scan_symbols.sh" || fail "arm S exited non-zero." 1
fi

echo ""
echo "== every registered trial is collected. Read the result with:"
echo "     python3 $HERE/analyse.py > /tmp/is_a_run_reproducible.txt"
echo "   THE PRINT IS THE PRODUCT AND IT IS LONG. Redirect it; do not pipe it"
echo "   through \`head\` -- a previous campaign's operator did, saw 143 lines of"
echo "   1034, and \`tee\` still exited 0."
