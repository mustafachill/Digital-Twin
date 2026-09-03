#!/usr/bin/env bash
# Build the SUPERSEDED predicate from its own commit's source, never from a rewrite.
#
#   build_superseded.sh [repository-root]
#
# DERIVED FROM `docs/measurements/2026-09-02-option-f-regions/harness/build_superseded.sh`,
# copied at commit `3235cbc`. That directory is FROZEN (`docs/measurements/README.md`) and
# nothing in it is edited from here. What changed: the validity rule it names is this
# campaign's V12 rather than that campaign's V10, and the refusal below now also refuses a
# commit that is not an ancestor of `HEAD`.
#
# `criteria.md` V12 in one script: `holding_S` and `flip_S_lo` contribute to nothing unless
# `raw/provenance.txt` records the `4ef2d7c` worktree commit and the sha256 of the binary
# that produced them. So this creates a DETACHED `git worktree` at that commit, compiles
# `gripper.cpp` out of it unmodified, records both, and removes the worktree again.
#
# WHY A WORKTREE AND NOT `git show`. `gripper.cpp` includes its own header and the two have
# to agree; checking out the pair is the operation that guarantees they came from one
# commit. It is removed afterwards so that nothing under this repository's working tree
# moves -- section 0 permits this campaign to write under `docs/measurements/` and nowhere
# else, and a worktree left behind inside the repository would be a second checkout of a
# different commit sitting in the tree the campaign claims not to have touched.
#
# THE BINARY IS NOT COMMITTED and is in `.gitignore`. What is committed is its sha256.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-$(cd "${HERE}/../../../.." && pwd)}"
RAW="${HERE}/../raw"

#: The commit `criteria.md` section 4.3 names -- the last commit before option F landed.
#: Stated here, once.
SUPERSEDED_COMMIT=4ef2d7c

WORKTREE="${TMPDIR:-/tmp}/cite_stall_band_flip_superseded_${SUPERSEDED_COMMIT}"

mkdir -p "${RAW}"

cleanup() {
    git -C "${ROOT}" worktree remove --force "${WORKTREE}" >/dev/null 2>&1 || true
    rm -rf "${WORKTREE}"
}
trap cleanup EXIT

cleanup

# Refused rather than assumed. `criteria.md` section 4.3 states that the commit is an
# ancestor of `HEAD`, verified on 2026-09-03; a campaign that built a commit off some other
# line of development would be comparing against a predicate this branch never had.
if ! git -C "${ROOT}" merge-base --is-ancestor "${SUPERSEDED_COMMIT}" HEAD; then
    echo "ABORT: ${SUPERSEDED_COMMIT} is not an ancestor of HEAD, so it is not the" >&2
    echo "       predicate this branch replaced." >&2
    exit 2
fi

git -C "${ROOT}" worktree add --detach "${WORKTREE}" "${SUPERSEDED_COMMIT}" >/dev/null

RESOLVED="$(git -C "${WORKTREE}" rev-parse HEAD)"
SKILLS="${WORKTREE}/workspace/src/cite_skills"
test -f "${SKILLS}/src/gripper.cpp"
test -f "${SKILLS}/include/cite_skills/gripper.hpp"

# Refused rather than warned about. If the commit's header already carries the bands, then
# it is not the superseded predicate and `holding_S` would be `holding_F` wearing another
# name -- which would put a quantity into `ANALYSIS.md` that says nothing while looking
# like a comparison.
if grep -q "stall_band_narrow_m" "${SKILLS}/include/cite_skills/gripper.hpp"; then
    echo "ABORT: ${SUPERSEDED_COMMIT} already declares stall_band_narrow_m, so it is not" >&2
    echo "       the command-referenced predicate criteria.md section 4.3 defines." >&2
    exit 2
fi

if command -v sha256sum >/dev/null 2>&1; then
    SHA() { sha256sum "$1" | cut -d' ' -f1; }
else
    SHA() { shasum -a 256 "$1" | cut -d' ' -f1; }
fi

c++ -std=c++17 -O2 -Wall -Wextra -Werror \
    -I "${SKILLS}/include" \
    -o "${HERE}/predicate_eval_superseded" \
    "${HERE}/predicate_eval_superseded.cpp" \
    "${SKILLS}/src/gripper.cpp"

{
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "worktree_commit=${RESOLVED}"
    echo "worktree_commit_short=${SUPERSEDED_COMMIT}"
    echo "gripper_cpp_sha256=$(SHA "${SKILLS}/src/gripper.cpp")"
    echo "gripper_hpp_sha256=$(SHA "${SKILLS}/include/cite_skills/gripper.hpp")"
    echo "front_end_sha256=$(SHA "${HERE}/predicate_eval_superseded.cpp")"
    echo "binary_sha256=$(SHA "${HERE}/predicate_eval_superseded")"
    echo "compiler=$(c++ --version | head -1)"
} | tee "${RAW}/predicate_eval_superseded_provenance.txt" >> "${RAW}/provenance.txt"

echo "built ${HERE}/predicate_eval_superseded"
