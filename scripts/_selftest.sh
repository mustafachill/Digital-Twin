#!/usr/bin/env bash
# =============================================================================
# Regression tests for the gate logic in scripts/_lib.sh.
#
# These exist because the gates themselves were the defect: ./scripts/lint
# reported "Lint clean" while linting zero packages, and the manifest pinning
# check was a starts-with-lowercase test rather than a SHA validator. Both were
# green for months. A gate with no test of its own is indistinguishable from a
# gate that does nothing, which is exactly how those two survived.
#
# Deliberately ROS-free and dependency-free so they run on a laptop, in the
# container, and in the fast CI job alike. Invoked by ./scripts/test; runnable on
# its own with `bash scripts/_selftest.sh`.
#
# The leading underscore marks this as a helper, not an entry point: the command
# contract in CLAUDE.md §7 is unchanged.
# =============================================================================

# shellcheck source=scripts/_lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

SELFTEST_PASS=0
SELFTEST_FAIL=0

expect_ok() {   # expect_ok <description> <command...>
    local description="$1"; shift
    if "$@" >/dev/null 2>&1; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s %s\n' "$C_RED" "$C_RST" "$description" >&2
        printf '        expected success, got exit %s from: %s\n' "$?" "$*" >&2
    fi
}

expect_fail() { # expect_fail <description> <command...>
    local description="$1"; shift
    if "$@" >/dev/null 2>&1; then
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s %s\n' "$C_RED" "$C_RST" "$description" >&2
        printf '        expected failure, got success from: %s\n' "$*" >&2
    else
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    fi
}

expect_eq() {   # expect_eq <description> <expected> <actual>
    local description="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s %s\n' "$C_RED" "$C_RST" "$description" >&2
        printf '        expected: %s\n        actual:   %s\n' "$expected" "$actual" >&2
    fi
}

# -----------------------------------------------------------------------------
# assert_lint_coverage — T-04. The gate must fail when it checked nothing.
# -----------------------------------------------------------------------------
expect_ok   "every selected package processed and linted" \
            assert_lint_coverage 7 7

# The exact shape of the reported defect: --packages-skip-build-finished meant
# colcon reported "Summary: 0 packages finished" and lint still printed clean.
expect_fail "zero packages processed out of seven selected" \
            assert_lint_coverage 7 0
expect_fail "some packages skipped" \
            assert_lint_coverage 7 6
expect_fail "no first-party packages selected at all" \
            assert_lint_coverage 0 0

# The second, independent cause: packages processed, but zero linters registered,
# so ctest reports "No tests were found!!!" and exits 0.
expect_fail "all packages processed but none registers a linter" \
            assert_lint_coverage 7 7 a b c d e f g
expect_fail "a single package registers no linter" \
            assert_lint_coverage 7 7 cite_generated

# The diagnosis has to name what is missing, or the failure is as unactionable
# as the silent pass it replaces.
DIAGNOSIS="$(assert_lint_coverage 7 7 cite_generated || true)"
case "$DIAGNOSIS" in
    *cite_generated*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s coverage diagnosis names the offending package\n' \
              "$C_RED" "$C_RST" >&2
       printf '        actual: %s\n' "$DIAGNOSIS" >&2 ;;
esac

# The flag that caused the silent pass must not come back. Comments are stripped
# first, because the block that removed it names it while explaining why.
#
# Captured and matched against a here-string rather than piped: `grep -q` exits on
# its first match and SIGPIPEs the producer, which `set -o pipefail` then reports
# as a failed pipeline. This project has been bitten by that twice already.
lint_script_uses_skip_flag() {
    local body
    body="$(grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/lint" || true)"
    grep -q -- '--packages-skip-build-finished' <<<"$body"
}
expect_fail "scripts/lint no longer passes --packages-skip-build-finished" \
            lint_script_uses_skip_flag

# -----------------------------------------------------------------------------
# unpinned_manifest_entries — D-01. A SHA validator, not a spelling test.
# -----------------------------------------------------------------------------
FIXTURE="$(mktemp -d)"
trap 'rm -rf "${FIXTURE}"' EXIT

cat >"${FIXTURE}/pinned.repos" <<'EOF'
---
repositories:
  external/starts_with_digit:
    type: git
    url: https://example.invalid/a.git
    version: 3dc2b5e8294758d96b54b15fa5920d581b7cbb3d
  external/starts_with_letter:
    type: git
    url: https://example.invalid/b.git
    version: abcdef0123456789abcdef0123456789abcdef01   # the false positive
EOF

cat >"${FIXTURE}/unpinned.repos" <<'EOF'
---
repositories:
  external/numeric_branch:
    type: git
    url: https://example.invalid/c.git
    version: 2.x                                        # the false negative
  external/branch:
    type: git
    url: https://example.invalid/d.git
    version: jazzy
  external/tag:
    type: git
    url: https://example.invalid/e.git
    version: v1.2.3
  external/short_sha:
    type: git
    url: https://example.invalid/f.git
    version: 3dc2b5e
EOF

expect_eq "a 40-character SHA beginning with a letter counts as pinned" \
          "" "$(unpinned_manifest_entries "${FIXTURE}/pinned.repos")"

UNPINNED="$(unpinned_manifest_entries "${FIXTURE}/unpinned.repos")"
expect_eq "every non-SHA version is reported, including the branch '2.x'" \
          "4" "$(printf '%s\n' "$UNPINNED" | grep -c .)"
case "$UNPINNED" in
    *numeric_branch*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s branch "2.x" is reported unpinned\n' "$C_RED" "$C_RST" >&2 ;;
esac
case "$UNPINNED" in
    *short_sha*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s an abbreviated SHA is reported unpinned\n' "$C_RED" "$C_RST" >&2 ;;
esac

# The manifest actually shipped must pass its own gate.
expect_eq "external/cite.repos is fully pinned" \
          "" "$(unpinned_manifest_entries)"

# -----------------------------------------------------------------------------
# cite_domain_id — T-07. Deterministic per checkout, distinct between checkouts.
# -----------------------------------------------------------------------------
expect_eq "the same checkout always yields the same domain" \
          "$(cite_domain_id /a/b/c)" "$(cite_domain_id /a/b/c)"

DOMAIN_A="$(cite_domain_id /home/dev/twin)"
DOMAIN_B="$(cite_domain_id /home/dev/twin-review)"
if [ "$DOMAIN_A" != "$DOMAIN_B" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s two checkouts get different domains\n' "$C_RED" "$C_RST" >&2
fi

# Domain 0 is the ecosystem default this exists to avoid; above 101 collides with
# the Linux ephemeral port range.
for candidate in /a /b /c /d/e/f /workspace "${REPO_ROOT}" /very/long/path/to/a/checkout; do
    DOMAIN="$(cite_domain_id "$candidate")"
    if [ "$DOMAIN" -ge 1 ] && [ "$DOMAIN" -le 101 ]; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s domain for %s is in 1..101 (got %s)\n' \
               "$C_RED" "$C_RST" "$candidate" "$DOMAIN" >&2
    fi
done

# An explicit setting always wins, or a developer cannot join a colleague's cell.
expect_eq "an explicit ROS_DOMAIN_ID survives sourcing _lib.sh" \
          "42" "$(ROS_DOMAIN_ID=42 bash -c 'source "$1"; printf "%s" "$ROS_DOMAIN_ID"' \
                  _ "${REPO_ROOT}/scripts/_lib.sh")"

# -----------------------------------------------------------------------------
printf '  %s%d passed, %d failed%s (shell gate self-tests)\n' \
       "$( [ "$SELFTEST_FAIL" -eq 0 ] && printf '%s' "$C_GRN" || printf '%s' "$C_RED" )" \
       "$SELFTEST_PASS" "$SELFTEST_FAIL" "$C_RST"
[ "$SELFTEST_FAIL" -eq 0 ]
