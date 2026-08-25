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
# python_trees — T-08. The linter and the host suite must walk the scenarios.
#
# The defect being pinned: both ./scripts/lint and ./scripts/test named `tools`
# and only `tools`. tests/ was neither linted nor collected, so three ruff
# violations and a whole guard suite sat in the branch reporting nothing. These
# assertions fail if either tree is dropped again.
# -----------------------------------------------------------------------------
TREES="$(python_trees)"
case "$TREES" in
    *"${REPO_ROOT}/tools"*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s python_trees includes tools/\n' "$C_RED" "$C_RST" >&2 ;;
esac
case "$TREES" in
    *"${REPO_ROOT}/tests"*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s python_trees includes tests/\n' "$C_RED" "$C_RST" >&2 ;;
esac

# Tied to the file it exists to collect, not merely to a directory name: moving
# the guard out from under a walked tree has to fail here rather than silently
# stop being run. This is the assertion that would have caught the original gap.
GUARD_FOUND=0
while IFS= read -r tree; do
    [ -n "$tree" ] || continue
    if find "$tree" -name 'test_scenario_modules_load.py' -print -quit 2>/dev/null | grep -q .; then
        GUARD_FOUND=1
    fi
done <<< "$TREES"
expect_eq "the scenario-load guard lies inside a tree the host suite collects" \
          "1" "$GUARD_FOUND"

# ruff must resolve real configuration for every walked tree. Without a config
# between a tree and the repository root ruff falls back to its own defaults —
# a narrower rule set at a different line length — and reports "All checks
# passed" having checked almost nothing, which is how tests/ stayed dirty.
while IFS= read -r tree; do
    [ -n "$tree" ] || continue
    FOUND=""
    dir="$tree"
    while [ "$dir" != "/" ] && [ -n "$dir" ]; do
        if [ -f "${dir}/ruff.toml" ] || [ -f "${dir}/.ruff.toml" ] \
           || grep -qs '\[tool\.ruff' "${dir}/pyproject.toml"; then
            FOUND="$dir"
            break
        fi
        dir="$(dirname "$dir")"
    done
    expect_eq "ruff configuration is discoverable from $(basename "$tree")/" \
              "found" "$( [ -n "$FOUND" ] && printf 'found' || printf 'missing' )"
done <<< "$TREES"

# -----------------------------------------------------------------------------
# scripts/enter — T-09. A trailing command must not weaken the hardware opt-in.
#
# The hardware service grants host networking, /dev passthrough and privileged
# execution. `require_explicit_hardware_opt_in` is what stands between that and
# an accidental command to a physical arm, and it is gated on the SERVICE, never
# on whether arguments were supplied — an opt-in a caller can skip by appending
# a command is not an opt-in. Both forms are asserted, and neither reaches Docker.
# -----------------------------------------------------------------------------
expect_fail "enter rejects an unknown service" \
            "${REPO_ROOT}/scripts/enter" definitely_not_a_service
expect_fail "enter hardware refuses without the opt-in" \
            env CITE_ALLOW_HARDWARE=0 "${REPO_ROOT}/scripts/enter" hardware
expect_fail "enter hardware refuses without the opt-in when given a command" \
            env CITE_ALLOW_HARDWARE=0 "${REPO_ROOT}/scripts/enter" hardware ros2 topic list

# -----------------------------------------------------------------------------
# patch_state — T-10. The four states must be four states.
#
# The defect being pinned, exactly as it happened: bootstrap asked only
# `git apply --check`, so "already applied" (success, and the reason the check
# exists) and "does not apply" (a declared modification missing from every build)
# both took the else branch and printed the same info line at info level.
# 01-xarm_ros2-gripper-mimic-joints.patch was committed and then absent from
# every build and every measurement for hours with nothing anywhere reporting it.
#
# Built against a real git repository rather than mocked, because the whole
# question is what `git apply` does — a fake that returned what we expected would
# be asserting our own assumption. Each state below is reached by putting a
# checkout into it for real.
# -----------------------------------------------------------------------------
PATCHDIR="${FIXTURE}/patches"
REPO="${FIXTURE}/checkout"
mkdir -p "$PATCHDIR" "$REPO"

git -C "$REPO" init --quiet
git -C "$REPO" config user.email selftest@example.invalid
git -C "$REPO" config user.name  selftest
printf 'alpha\nbravo\ncharlie\n' > "${REPO}/file.txt"
git -C "$REPO" add file.txt
git -C "$REPO" commit --quiet -m "base"

# A patch that applies to the checkout above.
cat >"${PATCHDIR}/01-good.patch" <<'EOF'
# Repo:     checkout
diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 alpha
-bravo
+BRAVO
 charlie
EOF

# A patch whose context does not exist — the "declared but unreachable" case that
# used to read as "already applied or does not apply".
cat >"${PATCHDIR}/02-stale.patch" <<'EOF'
# Repo:     checkout
diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,3 @@
 alpha
-delta
+DELTA
 charlie
EOF

# A patch with no Repo: header binds to no checkout at all.
printf 'diff --git a/x b/x\n' >"${PATCHDIR}/03-headerless.patch"

expect_eq "declared_patches lists every patch in filename order" \
          "01-good.patch 02-stale.patch 03-headerless.patch" \
          "$(declared_patches "$PATCHDIR" | xargs -n1 basename | tr '\n' ' ' | sed 's/ $//')"
expect_eq "declared_patches on a directory that does not exist is empty, not an error" \
          "" "$(declared_patches "${FIXTURE}/nope")"
expect_eq "patch_target_repo reads the Repo: header" \
          "checkout" "$(patch_target_repo "${PATCHDIR}/01-good.patch")"
expect_eq "patch_target_repo reports a missing header as empty" \
          "" "$(patch_target_repo "${PATCHDIR}/03-headerless.patch")"

# The state machine, one state at a time.
expect_eq "a patch that applies cleanly is pending, not applied" \
          "pending" "$(patch_state "${PATCHDIR}/01-good.patch" "$REPO")"
expect_eq "a patch that cannot apply is conflict, NOT the same answer as applied" \
          "conflict" "$(patch_state "${PATCHDIR}/02-stale.patch" "$REPO")"

git -C "$REPO" apply "${PATCHDIR}/01-good.patch"
expect_eq "once applied, the same patch reads applied — this is what keeps bootstrap idempotent" \
          "applied" "$(patch_state "${PATCHDIR}/01-good.patch" "$REPO")"
expect_eq "an applied patch and a stale one are still distinguishable" \
          "conflict" "$(patch_state "${PATCHDIR}/02-stale.patch" "$REPO")"

# The two absence states. `empty` is the signature of an import that failed
# part-way, which is what a git worktree produced inside the container, and it is
# the state that used to be reported as "skipped" while the build lost the patch.
expect_eq "a target that was never imported is no-target" \
          "no-target" "$(patch_state "${PATCHDIR}/01-good.patch" "${FIXTURE}/absent")"
mkdir -p "${FIXTURE}/hollow"
expect_eq "a target directory that exists and is EMPTY is its own state" \
          "empty" "$(patch_state "${PATCHDIR}/01-good.patch" "${FIXTURE}/hollow")"

# The property that ties the four together, and the one the old code failed:
# success and total failure must never produce the same word.
if [ "$(patch_state "${PATCHDIR}/01-good.patch" "$REPO")" \
     != "$(patch_state "${PATCHDIR}/02-stale.patch" "$REPO")" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s an applied patch and an unappliable one report differently\n' \
           "$C_RED" "$C_RST" >&2
fi

# Every patch this repository actually ships must carry the header that binds it
# to a checkout. A patch without one is silently unappliable forever.
while IFS= read -r p; do
    [ -n "$p" ] || continue
    expect_eq "$(basename "$p") declares its target repository" \
              "found" "$( [ -n "$(patch_target_repo "$p")" ] && printf 'found' || printf 'missing' )"
done < <(declared_patches)

# -----------------------------------------------------------------------------
printf '  %s%d passed, %d failed%s (shell gate self-tests)\n' \
       "$( [ "$SELFTEST_FAIL" -eq 0 ] && printf '%s' "$C_GRN" || printf '%s' "$C_RED" )" \
       "$SELFTEST_PASS" "$SELFTEST_FAIL" "$C_RST"
[ "$SELFTEST_FAIL" -eq 0 ]
