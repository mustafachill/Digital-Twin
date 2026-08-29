#!/usr/bin/env bash
# Two cells at once, both with hull collision meshes.
#
# Added after the main sequence, because the derived requirement in ANALYSIS.md
# section 5 would otherwise rest on multiplying the measured single-cell hull gain
# by the measured pairing penalty -- an extrapolation, where a measurement costs
# six minutes.
#
# A separate file rather than a new phase in run_campaign.sh: that script has
# already produced raw/, and the campaign convention freezes a harness once it has.
# This composes the phases that file already exposes and edits nothing.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../../.." && pwd)"
CAMPAIGN="docs/measurements/2026-08-28-second-world-cost"
HARNESS="/workspace/${CAMPAIGN}/harness"
RAW="/workspace/${CAMPAIGN}/raw"
INSTALL_MESHES=/workspace/workspace/install/xarm_description/share/xarm_description/meshes
LABEL="${1:-PAIRHULL_1}"

cd "$REPO_ROOT" || exit 1
./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" hull \
    --install-meshes "${INSTALL_MESHES}" --hull-root "${RAW}/hulls" \
    --state "${RAW}/mesh_swap_state.json" --subdir xarm5/visual --subdir gripper/xarm
"${HERE}/run_campaign.sh" pair "${LABEL}"
./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" vendor \
    --install-meshes "${INSTALL_MESHES}" --state "${RAW}/mesh_swap_state.json" \
    --subdir xarm5/visual --subdir gripper/xarm
./scripts/enter dev python3 "${HARNESS}/swap_meshes.py" verify \
    --install-meshes "${INSTALL_MESHES}" --state "${RAW}/mesh_swap_state.json" \
    --reference "${RAW}/mesh_reference.json" --subdir xarm5/visual --subdir gripper/xarm
