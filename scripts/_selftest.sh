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
# cite_project_name — one set of Docker volumes per checkout, not one per host.
#
# Compose scopes named volumes to the project name. While that name was a single
# fixed string, every checkout on this machine shared ONE cite-build, cite-install
# and cite-log: concurrent builds corrupted each other, one checkout ran another's
# binaries, and `clean --all` destroyed a worktree's build that was in progress.
# The properties below are what stop that, so each is asserted rather than
# assumed.
# -----------------------------------------------------------------------------

# Stability. `./scripts/enter` must attach to the cell `./scripts/sim` started
# from the same checkout, which it cannot do if the name varies between calls.
expect_eq "the same checkout always yields the same project name" \
          "$(cite_project_name /a/b/c)" "$(cite_project_name /a/b/c)"

# Isolation. This is the assertion that would have caught the original defect:
# under a fixed name these two are equal.
PROJECT_A="$(cite_project_name /home/dev/twin)"
PROJECT_B="$(cite_project_name /home/dev/twin-review)"
if [ "$PROJECT_A" != "$PROJECT_B" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s two checkouts get different project names\n' "$C_RED" "$C_RST" >&2
fi

# Worktrees are the common case on this host, and they differ only in their last
# path segment — which is also the part the readable slug is built from, so a
# derivation that used the basename alone would still collide.
WT_A="$(cite_project_name /repo/.claude/worktrees/agent-aaaa)"
WT_B="$(cite_project_name /repo/.claude/worktrees/agent-bbbb)"
if [ "$WT_A" != "$WT_B" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s two sibling worktrees get different project names\n' \
           "$C_RED" "$C_RST" >&2
fi

# Two checkouts may share a basename while living in different places. The hash
# is what separates them; the slug alone does not.
SAME_A="$(cite_project_name /home/alice/twin)"
SAME_B="$(cite_project_name /home/bob/twin)"
if [ "$SAME_A" != "$SAME_B" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s equal basenames in different parents still differ\n' \
           "$C_RED" "$C_RST" >&2
fi

# Compose only accepts [a-z0-9_-], and rejects a name that does not start with a
# letter or digit. A name it rejects fails every command, not just the volume
# scoping, so the character set is checked over paths chosen to break it.
for candidate in /a "/UPPER/Case Path" "/has.dots/and+plus" /trailing/dash- \
                 /workspace "${REPO_ROOT}" "/a/very/long/checkout/name/that/keeps/going/on"; do
    NAME="$(cite_project_name "$candidate")"
    if printf '%s' "$NAME" | grep -Eq '^[a-z0-9][a-z0-9_-]*$'; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s project name for %s is compose-legal (got %s)\n' \
               "$C_RED" "$C_RST" "$candidate" "$NAME" >&2
    fi
done

# The fixed name that caused the incident must never be derivable again. Any
# checkout returning it would be back to sharing the host-wide volume set.
for candidate in /a /b "${REPO_ROOT}" /home/dev/cite-digital-twin; do
    if [ "$(cite_project_name "$candidate")" != "cite-digital-twin" ]; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s %s must not derive the shared fallback project name\n' \
               "$C_RED" "$C_RST" "$candidate" >&2
    fi
done

# An explicit setting always wins, so a developer can deliberately join another
# checkout's project — and is reported as explicit rather than as derived.
expect_eq "an explicit COMPOSE_PROJECT_NAME survives sourcing _lib.sh" \
          "chosen-by-hand" \
          "$(COMPOSE_PROJECT_NAME=chosen-by-hand bash -c \
              'source "$1"; printf "%s" "$COMPOSE_PROJECT_NAME"' \
              _ "${REPO_ROOT}/scripts/_lib.sh")"

# Every compose invocation must carry the project explicitly. `-p` is the
# highest-precedence form; without it the scoping depends on an environment
# variable reaching a subprocess, which is the kind of assumption that decays.
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
if grep -Eq -- '-p "\$COMPOSE_PROJECT_NAME"' "${REPO_ROOT}/scripts/_lib.sh"; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s compose() passes -p with the derived project name\n' \
           "$C_RED" "$C_RST" >&2
fi

# container_name pins a host-global identifier and collides between checkouts
# exactly as the volumes did. It must stay out of the compose file.
if ! grep -q "container_name" "${REPO_ROOT}/infra/docker/docker-compose.yml"; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s docker-compose.yml pins no container_name\n' "$C_RED" "$C_RST" >&2
fi

# -----------------------------------------------------------------------------
# scripts/lint — it must select linters by LABEL, not by name.
#
# ament registers every linter with the `linter` label. Their NAMES only sometimes
# contain "lint": `ctest -R lint` matches cpplint, lint_cmake and xmllint, and
# silently drops flake8, pep257, copyright, cppcheck and uncrustify. The gate ran
# 3 of 8 linters per package while reporting "Lint clean", and five of them had
# never run under it — a change passed this gate with flake8 and pep257 failing.
#
# Measured, not argued: on cite_skills, `ctest -N -L linter` lists 8 tests and
# `ctest -N -R lint` lists 3. Across the seven packages the label selects 41.
#
# The same expression appears twice — the run and the coverage count — and they
# must agree, or the check that asks "which packages registered no linter" counts
# a different population than the one that ran. Both are asserted.
# -----------------------------------------------------------------------------
LINT_CODE="$(grep -vE '^[[:space:]]*#' "${REPO_ROOT}/scripts/lint" || true)"

LINT_LABEL_USES="$(printf '%s' "$LINT_CODE" | grep -c -- '-L linter' || true)"
if [ "${LINT_LABEL_USES:-0}" -ge 2 ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s scripts/lint selects linters by label in both places (found %s)\n' \
           "$C_RED" "$C_RST" "${LINT_LABEL_USES:-0}" >&2
fi

# The name filter must not come back. It is the specific expression that made a
# blocking gate enforce three eighths of itself.
if ! printf '%s' "$LINT_CODE" | grep -Eq -- '-R "?lint"?'; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s scripts/lint no longer selects linters by name (-R lint)\n' \
           "$C_RED" "$C_RST" >&2
fi

# -----------------------------------------------------------------------------
# cite_build_inputs_fingerprint — a gate must not answer from a stale build tree.
#
# The namespace stops one checkout reading another's artefacts. This is the other
# half: a checkout reading its OWN. It reported "registers no lint test at all"
# for packages whose package.xml declared ament_lint_common, and reported two
# suites red that pass on a fresh build.
# -----------------------------------------------------------------------------

# Deterministic, or the gates fire at random and get switched off.
expect_eq "the fingerprint is stable across calls" \
          "$(cite_build_inputs_fingerprint)" "$(cite_build_inputs_fingerprint)"

# Path-independent: the build happens in the container, where this tree is
# /workspace, and the check may run from either side of that boundary. A
# fingerprint that embedded absolute paths would report every build as stale.
SELFTEST_TMP="$(mktemp -d)"
mkdir -p "${SELFTEST_TMP}/a/workspace/src/pkg" "${SELFTEST_TMP}/b/workspace/src/pkg"
printf '<package><name>pkg</name></package>\n' \
    > "${SELFTEST_TMP}/a/workspace/src/pkg/package.xml"
printf '<package><name>pkg</name></package>\n' \
    > "${SELFTEST_TMP}/b/workspace/src/pkg/package.xml"
FP_A="$(REPO_ROOT="${SELFTEST_TMP}/a" cite_build_inputs_fingerprint)"
FP_B="$(REPO_ROOT="${SELFTEST_TMP}/b" cite_build_inputs_fingerprint)"
expect_eq "the same content under a different path fingerprints the same" \
          "$FP_A" "$FP_B"

# A changed package.xml must change the fingerprint. This is the exact edit that
# caused the incident: adding a test dependency that ament_lint_auto resolves at
# configure time, which a stale tree cannot see.
printf '<package><name>pkg</name><test_depend>ament_lint_common</test_depend></package>\n' \
    > "${SELFTEST_TMP}/b/workspace/src/pkg/package.xml"
FP_B2="$(REPO_ROOT="${SELFTEST_TMP}/b" cite_build_inputs_fingerprint)"
if [ "$FP_A" != "$FP_B2" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s adding a test_depend changes the build fingerprint\n' \
           "$C_RED" "$C_RST" >&2
fi

# A changed CMakeLists.txt must change it too — find_package/ament_lint_auto calls
# live there and are equally configure-time.
printf 'project(pkg)\n' > "${SELFTEST_TMP}/a/workspace/src/pkg/CMakeLists.txt"
FP_A2="$(REPO_ROOT="${SELFTEST_TMP}/a" cite_build_inputs_fingerprint)"
if [ "$FP_A" != "$FP_A2" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s adding a CMakeLists.txt changes the build fingerprint\n' \
           "$C_RED" "$C_RST" >&2
fi

# Adding a whole package must change it: "no linters registered" is a per-package
# answer, so a package appearing or disappearing is a configuration change.
mkdir -p "${SELFTEST_TMP}/a/workspace/src/pkg2"
printf '<package><name>pkg2</name></package>\n' \
    > "${SELFTEST_TMP}/a/workspace/src/pkg2/package.xml"
FP_A3="$(REPO_ROOT="${SELFTEST_TMP}/a" cite_build_inputs_fingerprint)"
if [ "$FP_A2" != "$FP_A3" ]; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s adding a package changes the build fingerprint\n' \
           "$C_RED" "$C_RST" >&2
fi

# Vendor source is imported by vcstool at arbitrary revisions and is not ours to
# lint; including it would make the fingerprint churn for reasons unrelated to
# the gates it guards.
mkdir -p "${SELFTEST_TMP}/a/workspace/src/external/vendor"
printf '<package><name>vendor</name></package>\n' \
    > "${SELFTEST_TMP}/a/workspace/src/external/vendor/package.xml"
expect_eq "vendor source under external/ is excluded from the fingerprint" \
          "$FP_A3" "$(REPO_ROOT="${SELFTEST_TMP}/a" cite_build_inputs_fingerprint)"

rm -rf "$SELFTEST_TMP"

# The gates must actually consult it. A fingerprint nothing checks is decoration.
for gate in lint test; do
    if grep -q "assert_build_inputs_current" "${REPO_ROOT}/scripts/${gate}"; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s scripts/%s checks the build fingerprint\n' \
               "$C_RED" "$C_RST" "$gate" >&2
    fi
done

if grep -q "record_build_inputs" "${REPO_ROOT}/scripts/build"; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s scripts/build records the build fingerprint\n' "$C_RED" "$C_RST" >&2
fi

# -----------------------------------------------------------------------------
# scripts/format — it may only run the reformatter the lint gate checks.
#
# `clang-format -i` with no .clang-format in the repository applies LLVM style
# while the gate checks ament_uncrustify, so running ./scripts/format rewrote
# ~1300 lines of packages that passed the linter before it ran.
# -----------------------------------------------------------------------------
# Two refinements, both learned by getting this wrong. Comment lines are stripped
# first, because the script explains at length why it does NOT use clang-format
# and a naive grep matches that explanation and reports the very defect it is
# describing. And the match is on clang-format in COMMAND position rather than
# anywhere on the line, because the script also names it inside a warning that
# tells the reader not to reach for it. What is forbidden is running it.
#
# Captured rather than piped into `grep -q`, which exits on its first match and
# SIGPIPEs the producer under `set -o pipefail`.
FORMAT_CODE="$(grep -vE '^[[:space:]]*#' "${REPO_ROOT}/scripts/format" || true)"
if ! printf '%s' "$FORMAT_CODE" | grep -Eq '(^|[|;]|&&)[[:space:]]*clang-format'; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s scripts/format does not reformat C++ with clang-format\n' \
           "$C_RED" "$C_RST" >&2
fi

if printf '%s' "$FORMAT_CODE" | grep -q "ament_uncrustify --reformat"; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s scripts/format reformats C++ with the linter own tool\n' \
           "$C_RED" "$C_RST" >&2
fi

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
# scenario_failed_cases / scenario_verdict — the phase split behind CI's scenario
# gates. These decide whether a red `launch_test` reds the build, so a mistake
# here is a gate that stops gating, and the states that matter each cost a full
# simulated bring-up to reproduce. Driven with synthetic reports instead.
#
# The fixtures below are the real shape, copied from a `launch_test --junit-xml`
# run rather than imagined: one line, self-closing `<testcase>` for a pass, a
# `<failure>` child whose `message` attribute carries the whole traceback with
# newlines as `&#10;` and quotes as `&quot;`.
# -----------------------------------------------------------------------------
JUNIT_TMP="$(mktemp -d)"
trap 'rm -rf "${FIXTURE}" "${JUNIT_TMP}"' EXIT

# NOTE THE ABSENT TRAILING NEWLINE, which is not a detail. `launch_test` ends
# its report without one, and an earlier version of this helper added it — which
# made every fixture here pass while the real thing failed, because `while read`
# drops a final line that has no newline and the whole document is that line. A
# fixture that is tidier than reality tests the fixture. Do not add the newline.
junit_report() {  # junit_report <file> <testcase-xml...>
    local out="$1"; shift
    {
        printf '<?xml version=%s1.0%s encoding=%sutf-8%s?>\n' "'" "'" "'" "'"
        printf '<testsuites name="s.s"><testsuite name="s.s.launch_tests">'
        printf '%s' "$@"
        printf '</testsuite></testsuites>'
    } > "$out"
}

PASSING_CASE='<testcase classname="bringup.TestBringup" name="test_a_trajectory_executes" time="1.0" />'
CYCLE_FAILURE='<testcase classname="bringup.TestBringup" name="test_a_trajectory_executes" time="1.0"><failure message="Traceback (most recent call last):&#10;AssertionError: no trajectory executed&#10;" /></testcase>'
# The upstream teardown abort this whole split exists for.
TEARDOWN_UPSTREAM='<testcase classname="bringup.TestCleanShutdown" name="test_nothing_of_ours_exited_badly" time="0.001"><failure message="Traceback (most recent call last):&#10;AssertionError: -6 not found in [0, -2] : parameter_bridge-5 exited with -6&#10;" /></testcase>'
# A first-party teardown bug wearing the SAME exit code as the upstream one.
# `line_orchestrator` aborting on UnknownGoalHandleError is a real cancellation
# defect that this check has already caught once, and it must stay reported.
TEARDOWN_OURS='<testcase classname="continuous_line.TestCleanShutdown" name="test_nothing_of_ours_exited_badly" time="0.001"><failure message="Traceback (most recent call last):&#10;AssertionError: -6 not found in [0, -2] : line_orchestrator-9 exited with -6&#10;" /></testcase>'

junit_report "${JUNIT_TMP}/cycle-failed.xml" "$CYCLE_FAILURE" "$PASSING_CASE"
junit_report "${JUNIT_TMP}/teardown-upstream.xml" "$PASSING_CASE" "$TEARDOWN_UPSTREAM"
junit_report "${JUNIT_TMP}/teardown-ours.xml" "$PASSING_CASE" "$TEARDOWN_OURS"
junit_report "${JUNIT_TMP}/both-failed.xml" "$CYCLE_FAILURE" "$TEARDOWN_UPSTREAM"
junit_report "${JUNIT_TMP}/nothing-failed.xml" "$PASSING_CASE"

expect_eq "a failing cycle assertion is classified as the cycle phase" \
          "cycle" \
          "$(scenario_failed_cases "${JUNIT_TMP}/cycle-failed.xml" | cut -f1)"
expect_eq "a failing post-shutdown assertion is classified as the teardown phase" \
          "teardown" \
          "$(scenario_failed_cases "${JUNIT_TMP}/teardown-upstream.xml" | cut -f1)"
expect_eq "a passing testcase is not reported as a failure" \
          "" \
          "$(scenario_failed_cases "${JUNIT_TMP}/nothing-failed.xml")"
expect_eq "the failing process and exit code survive into the summary" \
          "AssertionError: -6 not found in [0, -2] : parameter_bridge-5 exited with -6" \
          "$(scenario_failed_cases "${JUNIT_TMP}/teardown-upstream.xml" | cut -f3)"

# The gate proper. A cycle failure must red the build under EITHER policy —
# --teardown-advisory buys nothing for the assertion the acceptance claim rests
# on, which is the entire point of splitting by phase rather than by process.
expect_fail "a cycle failure gates under the blocking policy" \
            scenario_verdict "${JUNIT_TMP}/cycle-failed.xml" blocking
expect_fail "a cycle failure gates under the advisory policy too" \
            scenario_verdict "${JUNIT_TMP}/cycle-failed.xml" advisory
expect_fail "a cycle failure gates even when a teardown failure accompanies it" \
            scenario_verdict "${JUNIT_TMP}/both-failed.xml" advisory

expect_fail "a teardown failure gates under the blocking policy" \
            scenario_verdict "${JUNIT_TMP}/teardown-upstream.xml" blocking
expect_ok   "a teardown failure is advisory under the advisory policy" \
            scenario_verdict "${JUNIT_TMP}/teardown-upstream.xml" advisory

# THE PROPERTY THAT KEEPS THIS FROM BECOMING AN EXEMPTION. The split is by phase
# and never by process or exit code, so a first-party teardown bug is treated
# exactly like the upstream one: still asserted, still reported, and gating
# whenever the caller has not explicitly asked for advisory teardown. What must
# never happen is the two being told apart by name, which is what "exempt
# parameter_bridge" would have meant and what CLAUDE.md §2 records as
# unsupportable — process identity does not predict these failures.
expect_fail "a first-party teardown failure gates under the blocking policy" \
            scenario_verdict "${JUNIT_TMP}/teardown-ours.xml" blocking
expect_eq "a first-party teardown failure is reported with its process named" \
          "AssertionError: -6 not found in [0, -2] : line_orchestrator-9 exited with -6" \
          "$(scenario_failed_cases "${JUNIT_TMP}/teardown-ours.xml" | cut -f3)"

# Fail-closed, three ways. Anything unclassifiable must gate rather than pass.
expect_fail "an absent report gates" \
            scenario_verdict "${JUNIT_TMP}/does-not-exist.xml" advisory
expect_fail "a report recording no failure at all gates, because it explains nothing" \
            scenario_verdict "${JUNIT_TMP}/nothing-failed.xml" advisory

# A post-shutdown class this does not recognise must gate, not be ignored. This
# is what makes renaming TestCleanShutdown in tests/scenarios/ safe: the gate
# tightens rather than silently stops covering teardown.
junit_report "${JUNIT_TMP}/unknown-class.xml" \
    '<testcase classname="bringup.TestSomeOtherShutdownClass" name="test_x" time="0.0"><failure message="AssertionError: gz-4 exited with -9&#10;" /></testcase>'
expect_fail "an unrecognised post-shutdown class gates instead of being ignored" \
            scenario_verdict "${JUNIT_TMP}/unknown-class.xml" advisory
expect_eq "an unrecognised class is classified as the cycle phase" \
          "cycle" \
          "$(scenario_failed_cases "${JUNIT_TMP}/unknown-class.xml" | cut -f1)"

# The class is matched on its own name, not on the module qualifying it, so a
# scenario module could not be mistaken for the class.
junit_report "${JUNIT_TMP}/module-named-like-class.xml" \
    '<testcase classname="TestCleanShutdown.TestBringup" name="test_x" time="0.0"><failure message="AssertionError: boom&#10;" /></testcase>'
expect_eq "a module named like the teardown class does not make a cycle failure teardown" \
          "cycle" \
          "$(scenario_failed_cases "${JUNIT_TMP}/module-named-like-class.xml" | cut -f1)"

# ./scripts/scenario must keep asking the strict question unless asked otherwise:
# the advisory policy is opt-in, so an interactive run and a review agent both
# still see a teardown failure as a failure.
# shellcheck disable=SC2016  # matching the literal default, which must not expand
if grep -q 'TEARDOWN_POLICY="blocking"' "${REPO_ROOT}/scripts/scenario"; then
    SELFTEST_PASS=$((SELFTEST_PASS + 1))
else
    SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
    printf '  %sFAIL%s ./scripts/scenario gates on teardown unless --teardown-advisory\n' \
           "$C_RED" "$C_RST" >&2
fi

# -----------------------------------------------------------------------------
printf '  %s%d passed, %d failed%s (shell gate self-tests)\n' \
       "$( [ "$SELFTEST_FAIL" -eq 0 ] && printf '%s' "$C_GRN" || printf '%s' "$C_RED" )" \
       "$SELFTEST_PASS" "$SELFTEST_FAIL" "$C_RST"
[ "$SELFTEST_FAIL" -eq 0 ]
