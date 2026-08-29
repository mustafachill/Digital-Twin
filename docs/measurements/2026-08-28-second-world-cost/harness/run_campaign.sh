#!/usr/bin/env bash
# Drive the campaign. Run from the repository root:
#
#   docs/measurements/2026-08-28-second-world-cost/harness/run_campaign.sh <phase>
#
# Phases are separate so that a failure re-runs one arm rather than the whole set,
# and so that the interleaving in criteria.md is visible in the invocation order
# rather than buried in a loop.
#
#   host        record the machine state into raw/host.txt
#   hulls       compute the convex hulls the H condition needs
#   solo LABEL  one cell, sampled
#   pair LABEL  two cells on two ROS domains, both sampled over one shared window
#   pairgz LABEL  the same, with a distinct GZ_PARTITION per cell
#   hull LABEL  one cell with hull collision meshes, sampled, meshes restored after
#   mirror      the domain-crossing latency rig
#   shadow LABEL  a physics-free virtual side beside one real cell
#   world       the arms-free ablation
#
# Every cell run goes through ./scripts/sim, so the thing measured is the thing the
# project ships rather than a launch graph invented for the measurement.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CAMPAIGN="docs/measurements/2026-08-28-second-world-cost"
HARNESS="/workspace/${CAMPAIGN}/harness"
RAW="/workspace/${CAMPAIGN}/raw"
HOST_RAW="${REPO_ROOT}/${CAMPAIGN}/raw"

# Two domains, fixed, so that a run's raw record says which side it was.
DOMAIN_A=41
DOMAIN_B=87

SAMPLE_S="${CITE_SAMPLE_SECONDS:-120}"

MESH_SUBDIRS=(--subdir xarm5/visual --subdir gripper/xarm)
INSTALL_MESHES=/workspace/workspace/install/xarm_description/share/xarm_description/meshes
HULL_ROOT=/workspace/${CAMPAIGN}/raw/hulls
SWAP_STATE=/workspace/${CAMPAIGN}/raw/mesh_swap_state.json
MESH_REF=/workspace/${CAMPAIGN}/raw/mesh_reference.json

cd "$REPO_ROOT" || exit 1

phase_host() {
    {
        echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "commit: $(git rev-parse HEAD)"
        echo "branch: $(git rev-parse --abbrev-ref HEAD)"
        echo "main: $(git rev-parse main)"
        echo "uname: $(uname -a)"
        echo "docker: $(docker info --format '{{.ServerVersion}} ncpu={{.NCPU}} mem={{.MemTotal}}')"
        echo "--- containers running at this moment ---"
        docker ps --format '{{.Names}} {{.Image}}'
        echo "--- docker stats ---"
        docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'
    } >> "${HOST_RAW}/host.txt" 2>&1
}

phase_hulls() {
    ./scripts/enter dev python3 "${HARNESS}/make_hulls.py" \
        --source "${INSTALL_MESHES}" --dest "${HULL_ROOT}" \
        "${MESH_SUBDIRS[@]}" | tee -a "${HOST_RAW}/hulls.txt"
    ./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" record \
        --install-meshes "${INSTALL_MESHES}" --state "${SWAP_STATE}" \
        --reference "${MESH_REF}" "${MESH_SUBDIRS[@]}" | tee -a "${HOST_RAW}/hulls.txt"
}

run_cell() {
    local label="$1" domain="$2"
    shift 2
    ROS_DOMAIN_ID="$domain" ./scripts/enter dev \
        python3 "${HARNESS}/cell_run.py" --label "$label" --out "${RAW}" \
        --sample-seconds "${SAMPLE_S}" "$@"
}

phase_solo() {
    local label="$1"
    run_cell "$label" "$DOMAIN_A" 2>&1 | tail -3 | tee -a "${HOST_RAW}/run_log.txt"
}

# Two cells, two ROS domains, one shared sampling window.
#
# The window is shared on purpose. Sampling them one after the other would compare
# a cell that had the host to itself for part of the time with one that did not,
# and the whole question is what they cost each other. Each cell writes a ready
# file when its controllers are active and then blocks on a gate file that this
# function creates once BOTH are ready -- so both sample the same 120 s.
phase_pair() {
    local label="$1" partition="${2:-}"
    local gate_dir="${HOST_RAW}/gate"
    mkdir -p "$gate_dir"
    rm -f "${gate_dir}/${label}"*
    local ready_a="${RAW}/gate/${label}_A.ready"
    local ready_b="${RAW}/gate/${label}_B.ready"
    local gate="${RAW}/gate/${label}.go"

    local pre_a="" pre_b=""
    if [ -n "$partition" ]; then
        pre_a="export GZ_PARTITION=${label}_A; "
        pre_b="export GZ_PARTITION=${label}_B; "
    fi

    ROS_DOMAIN_ID="$DOMAIN_A" ./scripts/enter dev bash -lc \
        "${pre_a}exec python3 ${HARNESS}/cell_run.py --label ${label}_A --out ${RAW} \
         --sample-seconds ${SAMPLE_S} --ready-file ${ready_a} --start-gate ${gate}" \
        > "${HOST_RAW}/${label}_A.console" 2>&1 &
    local pid_a=$!
    ROS_DOMAIN_ID="$DOMAIN_B" ./scripts/enter dev bash -lc \
        "${pre_b}exec python3 ${HARNESS}/cell_run.py --label ${label}_B --out ${RAW} \
         --sample-seconds ${SAMPLE_S} --ready-file ${ready_b} --start-gate ${gate}" \
        > "${HOST_RAW}/${label}_B.console" 2>&1 &
    local pid_b=$!

    local waited=0
    while [ "$waited" -lt 1200 ]; do
        if [ -f "${gate_dir}/${label}_A.ready" ] && [ -f "${gate_dir}/${label}_B.ready" ]; then
            break
        fi
        sleep 5
        waited=$((waited + 5))
    done
    echo "both-ready-after=${waited}s" >> "${HOST_RAW}/run_log.txt"
    docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' \
        >> "${HOST_RAW}/${label}.dockerstats" 2>&1
    date +%s > "${gate_dir}/${label}.go"
    (
        for _ in $(seq 1 24); do
            sleep 5
            docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' \
                >> "${HOST_RAW}/${label}.dockerstats" 2>&1
        done
    ) &
    wait "$pid_a" "$pid_b"
}

# The H arm of Q3.1. The vendor meshes are restored and verified byte-identical
# whether the run succeeded or not -- a rig that leaves a mutated build tree
# behind poisons every measurement taken after it.
phase_hull() {
    local label="$1"
    ./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" hull \
        --install-meshes "${INSTALL_MESHES}" --hull-root "${HULL_ROOT}" \
        --state "${SWAP_STATE}" "${MESH_SUBDIRS[@]}" | tee -a "${HOST_RAW}/run_log.txt"
    run_cell "$label" "$DOMAIN_A" 2>&1 | tail -3 | tee -a "${HOST_RAW}/run_log.txt"
    ./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" vendor \
        --install-meshes "${INSTALL_MESHES}" --state "${SWAP_STATE}" \
        "${MESH_SUBDIRS[@]}" | tee -a "${HOST_RAW}/run_log.txt"
    ./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" verify \
        --install-meshes "${INSTALL_MESHES}" --state "${SWAP_STATE}" \
        --reference "${MESH_REF}" "${MESH_SUBDIRS[@]}" | tee -a "${HOST_RAW}/run_log.txt"
}

phase_mirror() {
    ./scripts/enter dev python3 "${HARNESS}/mirror_latency.py" \
        --domain-a "$DOMAIN_A" --domain-b "$DOMAIN_B" \
        --out "${RAW}/mirror_latency.json" 2>&1 | tail -3 | tee -a "${HOST_RAW}/run_log.txt"
}

phase_world() {
    ./scripts/enter dev python3 "${HARNESS}/world_only.py" --out "${RAW}" \
        --sample-seconds "${SAMPLE_S}" 2>&1 | tail -5 | tee -a "${HOST_RAW}/run_log.txt"
}

phase_shadow() {
    local label="$1"
    local gate_dir="${HOST_RAW}/gate"
    mkdir -p "$gate_dir"
    rm -f "${gate_dir}/${label}"*
    ROS_DOMAIN_ID="$DOMAIN_A" ./scripts/enter dev \
        python3 "${HARNESS}/cell_run.py" --label "${label}_plant" --out "${RAW}" \
        --sample-seconds "${SAMPLE_S}" --ready-file "${RAW}/gate/${label}_A.ready" \
        --start-gate "${RAW}/gate/${label}.go" \
        > "${HOST_RAW}/${label}_plant.console" 2>&1 &
    local pid_a=$!
    local waited=0
    while [ "$waited" -lt 1200 ]; do
        [ -f "${gate_dir}/${label}_A.ready" ] && break
        sleep 5
        waited=$((waited + 5))
    done
    ROS_DOMAIN_ID="$DOMAIN_B" ./scripts/enter dev \
        python3 "${HARNESS}/shadow_side.py" --label "${label}_shadow" --out "${RAW}" \
        --plant-domain "$DOMAIN_A" --sample-seconds "${SAMPLE_S}" \
        --gate "${RAW}/gate/${label}.go" \
        > "${HOST_RAW}/${label}_shadow.console" 2>&1 &
    local pid_b=$!
    wait "$pid_a" "$pid_b"
}

PHASE="${1:-}"
shift || true
case "$PHASE" in
    host)   phase_host ;;
    hulls)  phase_hulls ;;
    solo)   phase_solo "$@" ;;
    pair)   phase_pair "$@" ;;
    pairgz) phase_pair "$1" partition ;;
    hull)   phase_hull "$@" ;;
    mirror) phase_mirror ;;
    world)  phase_world ;;
    shadow) phase_shadow "$@" ;;
    *) echo "unknown phase: ${PHASE}" >&2; exit 2 ;;
esac
