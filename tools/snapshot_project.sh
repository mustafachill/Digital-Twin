#!/usr/bin/env bash
# Extract one commit of this repository into a frozen, self-contained snapshot.
#
#   tools/snapshot_project.sh <commit> <dest-dir>
#   tools/snapshot_project.sh b5a0bc9 projects/01-three-arm-event-driven-line
#
# WHAT IT IS FOR (ADR-0068). A proven milestone is kept under `projects/<name>/`
# as a whole tree that builds and runs from that folder alone. This script is the
# one mechanism that makes such a tree, so that every snapshot's PROVENANCE.md can
# name the exact command that produced it and a reviewer can re-run it and diff.
#
# WHAT IT DOES. `git archive <commit>` of the whole tree, minus the paths below,
# unpacked into <dest-dir>. The output is a function of the commit alone: git
# archive reads the object database, never the working tree, so an uncommitted
# edit, an untracked file or a build directory cannot leak into a snapshot.
#
# WHAT IT LEAVES OUT, and why each one:
#   docs/measurements/    thousands of raw records; they stay in the main tree
#   legacy/               the archived v1 tree, whose patterns are not precedent
#   real-robot-code/      the real cell's own archives, never committed anyway
#   CLAUDE.md, AGENTS.md, what-we-are-doing.md
#                         the rulebook and the charter belong to the main tree;
#                         a snapshot is a record of a past state, not a source
#   __pycache__/, log/    runtime output, excluded should any ever be tracked
#
# WHAT IT DOES NOT DO. It applies no patch. Every edit a snapshot carries beyond
# this extract is listed, with its rationale and its diff, in that snapshot's
# PROVENANCE.md (ADR-0068 decision 2).
#
# It refuses a destination that exists and is not empty, rather than merging a
# second extract into the first: a snapshot that is the union of two commits is
# a record of neither.

set -euo pipefail

usage() {
    sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac

if [ "$#" -ne 2 ]; then
    usage >&2
    exit 2
fi

COMMIT="$1"
DEST="$2"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

#: The excluded paths, as git pathspecs. One list, read by the extract below and
#: printed for PROVENANCE.md, so the record and the command cannot disagree.
EXCLUDES=(
    ':(exclude)docs/measurements'
    ':(exclude)legacy'
    ':(exclude)real-robot-code'
    ':(exclude)CLAUDE.md'
    ':(exclude)AGENTS.md'
    ':(exclude)what-we-are-doing.md'
    ':(exclude,glob)**/__pycache__/**'
    ':(exclude,glob)**/log/**'
)

if ! git -C "$REPO_ROOT" rev-parse --verify --quiet "${COMMIT}^{commit}" >/dev/null; then
    echo "error: '${COMMIT}' does not name a commit in ${REPO_ROOT}" >&2
    exit 1
fi

if [ -e "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
    echo "error: ${DEST} exists and is not empty; refusing to extract over it" >&2
    exit 1
fi

mkdir -p "$DEST"
git -C "$REPO_ROOT" archive --format=tar "$COMMIT" -- . "${EXCLUDES[@]}" \
    | tar -x -C "$DEST"

SHA="$(git -C "$REPO_ROOT" rev-parse "${COMMIT}^{commit}")"
echo "snapshot of ${SHA} extracted into ${DEST}"
echo "excluded:"
printf '  %s\n' "${EXCLUDES[@]}"
