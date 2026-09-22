#!/usr/bin/env bash
# Arm S -- instrument I5. The symbol scan, WITH ITS COMMAND WRITTEN DOWN.
#
#   docs/measurements/2026-09-22-is-a-run-reproducible/harness/scan_symbols.sh
#
# WHY THIS ARM EXISTS. `../criteria.md` section 2: the claim that
# `gz sim --seed` does not reach the physics solver appears in exactly two prose
# sentences -- `ADR-0027:474-478` and `docs/reference/toolchain.md:118` -- and
# NEITHER records a command, a tool, a library list or an output. The
# `nm -D -u ... | c++filt` recipe this project remembers it by belongs to the
# ADJACENT OMPL check at `toolchain.md:88-97`, whose `aarch64-linux-gnu` path
# shows that block ran on an arm64 image. This host is x86-64
# (`../criteria.md` section 9), so the architecture attribution is by proximity
# and not by record. This closes that, and closes it as an INSTRUMENT being
# written down rather than as a hypothesis being tested.
#
# T6: REPORTED, NO PASS/FAIL. Whatever it prints goes into `raw/` -- including
# nothing, including a surprise. It cannot by itself confirm or refute T2, for
# the reason `../criteria.md` section 2 gives: a fixed-step rigid-body
# integrator can be perfectly deterministic while drawing from no RNG at all,
# and an undefined `rand` symbol is a link against libc and not a proof that
# anything calls it.
#
# IT SCANS EVERY SHARED OBJECT UNDER BOTH VENDOR TREES and does not choose
# among them. A scan that looked only at the library somebody expected would be
# a scan of an expectation.
#
# It runs INSIDE `cite-digital-twin:dev` and re-enters the container itself when
# started from the host, so that the image it reports is the image the trials
# ran in.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
RAW="${CITE_SCAN_OUT:-$HERE/../raw}"
OUT="${RAW}/symbol_scan.txt"

VENDOR_ROOTS=(
    /opt/ros/jazzy/opt/gz_physics_vendor
    /opt/ros/jazzy/opt/gz_dartsim_vendor
)

if [ ! -f /etc/cite-container ]; then
    # V-container applies to the caller, not here: `run_campaign.sh` checks
    # `docker ps` before this block. `./scripts/enter` is used rather than a
    # bare `docker run` so that the image, the mounts and the entrypoint are
    # the ones every other trial got.
    mkdir -p "$RAW"
    exec "$ROOT/scripts/enter" dev bash -lc \
        "CITE_SCAN_OUT=/workspace/docs/measurements/2026-09-22-is-a-run-reproducible/raw \
         bash /workspace/docs/measurements/2026-09-22-is-a-run-reproducible/harness/scan_symbols.sh"
fi

mkdir -p "$RAW"

{
    echo "# arm S -- docs/measurements/2026-09-22-is-a-run-reproducible, instrument I5"
    echo "# T6: reported, no pass/fail. This is an instrument being written down."
    echo "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "uname_m=$(uname -m)"
    echo "uname_a=$(uname -a)"
    echo "image=cite-digital-twin:dev"
    echo "gz_sim_version=$(gz sim --version 2>&1 | head -1)"
    echo "nm=$(command -v nm || echo '<absent>')"
    echo "cxxfilt=$(command -v c++filt || echo '<absent>')"
    echo "git_head=$(git -C /workspace rev-parse HEAD 2>/dev/null || echo '<unknown>')"
    echo "command_per_library=nm -D -u <lib> | c++filt | grep -i rand"
    echo "vendor_roots=${VENDOR_ROOTS[*]}"
    echo ""

    # EACH ROOT AND WHETHER IT EXISTS, BEFORE THE `find` THAT WALKS THEM.
    # `find` writes "No such file or directory" to stderr and that was sent to
    # /dev/null, so a vendor tree that had moved produced `library_count=0` --
    # indistinguishable from a scan that walked both trees and found nothing.
    # This arm exists because the claim it re-takes has NO RECORDED INSTRUMENT
    # (`../criteria.md` section 2); an instrument that cannot tell "I looked and
    # saw nothing" from "I looked in the wrong place" is the same gap again.
    echo "## the roots, and whether each one exists"
    ROOTS_PRESENT=0
    for root in "${VENDOR_ROOTS[@]}"; do
        if [ -d "$root" ]; then
            echo "  present  $root"
            ROOTS_PRESENT=$((ROOTS_PRESENT + 1))
        else
            echo "  ABSENT   $root"
        fi
    done
    echo "vendor_roots_present=${ROOTS_PRESENT} of ${#VENDOR_ROOTS[@]}"
    echo ""

    echo "## the library list, in full"
    LIBS=()
    FIND_ERRORS="$(mktemp)"
    while IFS= read -r lib; do
        [ -n "$lib" ] && LIBS+=("$lib")
    done < <(find "${VENDOR_ROOTS[@]}" -name '*.so*' -type f 2>"$FIND_ERRORS" | sort)
    echo "library_count=${#LIBS[@]}"
    # `find`'s own complaint, reported rather than discarded -- and kept OUT of
    # the list above, which is why it goes to a file and not to the pipeline.
    if [ -s "$FIND_ERRORS" ]; then
        echo "find_stderr<<EOF"
        cat "$FIND_ERRORS"
        echo "EOF"
    else
        echo "find_stderr=<empty>"
    fi
    rm -f "$FIND_ERRORS"
    if [ "$ROOTS_PRESENT" -ne "${#VENDOR_ROOTS[@]}" ]; then
        echo "# WARNING: a vendor root is missing, so the count above is NOT a"
        echo "#          measurement of what this image contains. T6 reports; it"
        echo "#          does not pass or fail, and this line is part of the report."
    fi
    for lib in "${LIBS[@]}"; do
        echo "  $lib"
    done
    echo ""

    echo "## the scan, per library, COMPLETE -- including the empty answers"
    for lib in "${LIBS[@]}"; do
        echo "---- $lib"
        # `-u` is undefined symbols: what this object needs from somewhere else.
        # Both halves of the pipeline are reported, and a failure of either is
        # printed rather than swallowed -- `grep` exits 1 on no match, which is
        # an ANSWER here and not an error, so the status is stated.
        output="$(nm -D -u "$lib" 2>&1 | c++filt 2>&1 | grep -i rand)"
        status=$?
        if [ -n "$output" ]; then
            printf '%s\n' "$output"
        fi
        if [ "$status" -eq 0 ]; then
            echo "     (grep status 0; matched)"
        else
            echo "     (grep status ${status}; no match)"
        fi
    done
    echo ""

    echo '## the same scan over DEFINED symbols, for context only'
    echo '## (nm -D --defined-only; NOT part of I5, which registers -u. It is'
    echo '##  here because an undefined-only answer cannot distinguish a library'
    echo '##  that defines its own generator from one that uses none.)'
    for lib in "${LIBS[@]}"; do
        echo "---- $lib"
        nm -D --defined-only "$lib" 2>&1 | c++filt 2>&1 | grep -i rand || \
            echo "     (no match)"
    done
} > "$OUT" 2>&1

echo "arm S: wrote $OUT"
