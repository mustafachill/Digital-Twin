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
# assert_shellcheck_pinned — the shell gate's verdict must not depend on the
# machine that ran it.
#
# The first CI run in this repository's history failed here, and the findings
# were not the defect. `./scripts/lint` ran `have shellcheck` and then whatever
# was on PATH, so one command gave three answers on the same commit: clean on the
# host at 0.11.0, SC2119/SC2120/SC2015 on the runner at whatever ubuntu-24.04
# ships, and "not installed — skipped", reported as success, in the container
# where no shellcheck existed at all.
#
# So the interesting assertion is NOT that the scripts are clean — ./scripts/lint
# answers that, and answers it about one version. It is that the gate either runs
# the pinned version or refuses. Both halves are below, driven with stand-in
# binaries, because reproducing the real states means installing three different
# builds of the linter.
# -----------------------------------------------------------------------------
SC_FIXTURE="$(mktemp -d)"
trap 'rm -rf "${SC_FIXTURE}"' EXIT

# A stand-in shellcheck that reports whatever version it is told to, in the exact
# shape the real one prints — the parsing is part of what is under test.
fake_shellcheck() {  # fake_shellcheck <path> <version>
    cat >"$1" <<EOF
#!/bin/sh
printf 'ShellCheck - shell script analysis tool\nversion: %s\n' "$2"
EOF
    chmod +x "$1"
}

# The fixture pins a version this project does NOT use, deliberately. Restating
# the real pin here would put the value in a second place, which is the rule this
# block's last case enforces.
SC_REQ="${SC_FIXTURE}/dev.txt"
printf 'ruff==0.7.4\nshellcheck-py==0.10.0.1     # shellcheck 0.10.0\n' >"$SC_REQ"

expect_eq "the pinned shellcheck version is read from the requirements pin" \
          "0.10.0" "$(shellcheck_pinned_version "$SC_REQ")"

fake_shellcheck "${SC_FIXTURE}/matching" 0.10.0
expect_ok   "the gate accepts a shellcheck at exactly the pinned version" \
            assert_shellcheck_pinned "${SC_FIXTURE}/matching" "$SC_REQ"

# THE CASE THIS WHOLE BLOCK EXISTS FOR. 0.9.0 is the family the CI runner had, and
# it is a perfectly good shellcheck — it just answers a different question than the
# pin does. Silently using it is how the same commit was clean locally and red in
# CI, so the gate must refuse rather than run it.
fake_shellcheck "${SC_FIXTURE}/older" 0.9.0
expect_fail "the gate refuses a DIFFERENT shellcheck version rather than trusting it" \
            assert_shellcheck_pinned "${SC_FIXTURE}/older" "$SC_REQ"
SC_WHY="$(assert_shellcheck_pinned "${SC_FIXTURE}/older" "$SC_REQ" || true)"
case "$SC_WHY" in
    *0.10.0*0.9.0*) SELFTEST_PASS=$((SELFTEST_PASS + 1)) ;;
    *) SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
       printf '  %sFAIL%s the refusal names both the pinned and the actual version\n' \
              "$C_RED" "$C_RST" >&2
       printf '        actual: %s\n' "$SC_WHY" >&2 ;;
esac

# Absence is a refusal too, not a skip. This is the container's old steady state,
# where the shell gate reported success having read no shell script at all.
expect_fail "an absent shellcheck is a refusal, not a skipped check" \
            assert_shellcheck_pinned "${SC_FIXTURE}/not-installed" "$SC_REQ"

# And a requirements file that pins nothing must not read as "any version will do".
printf 'ruff==0.7.4\n' >"${SC_FIXTURE}/unpinned.txt"
expect_fail "a requirements file with no shellcheck-py pin is a refusal" \
            assert_shellcheck_pinned "${SC_FIXTURE}/matching" "${SC_FIXTURE}/unpinned.txt"

# The pin this project actually ships has to be readable by the same code.
expect_ok "requirements/dev.txt pins shellcheck-py" \
          shellcheck_pinned_version "$CITE_DEV_REQUIREMENTS"

# P1: the version is a value, and it lives in exactly one file. Scoped to the
# directories that could USE it — a document naming the version in prose is
# describing the pin, not being a second copy of it.
sc_pin_stated_outside_requirements() {
    local pin
    pin="$(pinned_version shellcheck-py "$CITE_DEV_REQUIREMENTS")"
    # No pin at all is not "exactly one place" either, and searching for the
    # bare `shellcheck-py==` would answer about whatever fixture matched first.
    [ -n "$pin" ] || return 0
    grep -rlF --exclude='dev.txt' "shellcheck-py==${pin}" \
        "${REPO_ROOT}/scripts" "${REPO_ROOT}/infra" \
        "${REPO_ROOT}/.github" "${REPO_ROOT}/requirements" >/dev/null 2>&1
}
expect_fail "the shellcheck pin is written down in requirements/dev.txt alone (P1)" \
            sc_pin_stated_outside_requirements

# The gate must run the pinned binary out of the virtualenv by path. A `have`
# probe followed by a bare invocation is PATH again, which IS the defect: it is
# what gave three machines three verdicts on one commit. Comments stripped first —
# the block above the step quotes the old form while explaining why it is gone.
lint_script_body() {
    grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/lint" || true
}
lint_script_probes_path_for_shellcheck() {
    grep -qF 'have shellcheck' <<<"$(lint_script_body)"
}
lint_script_runs_shellcheck_from_venv() {
    # shellcheck disable=SC2016  # the literal text is the point; it must not expand
    grep -qF '${VENV}/shellcheck' <<<"$(lint_script_body)"
}
expect_fail "scripts/lint no longer takes shellcheck off PATH" \
            lint_script_probes_path_for_shellcheck
expect_ok   "scripts/lint runs the shellcheck installed from the pin" \
            lint_script_runs_shellcheck_from_venv

# -----------------------------------------------------------------------------
# unpinned_manifest_entries — D-01. A SHA validator, not a spelling test.
# -----------------------------------------------------------------------------
FIXTURE="$(mktemp -d)"
trap 'rm -rf "${SC_FIXTURE}" "${FIXTURE}"' EXIT

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
          "" "$(unpinned_manifest_entries "$CITE_VCS_MANIFEST")"

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

# A checkout claims a PAIR of domains, so the assertion is about the pair and not
# only about the base. Domain 0 is the ecosystem default this exists to avoid;
# above 101 collides with the Linux ephemeral port range. The counterpart sits at
# base + 1, so the base must leave room for it.
#
# The parity is asserted rather than the bound alone, because parity is what the
# allocation buys: plants are odd and counterparts are even, so no counterpart of
# any checkout can equal any plant of any other. A derivation that drifted back
# to `sum % 101 + 1` would still satisfy a range check and would silently give
# that property away (ADR-0044, clause 4).
for candidate in /a /b /c /d/e/f /workspace "${REPO_ROOT}" /very/long/path/to/a/checkout; do
    DOMAIN="$(cite_domain_id "$candidate")"
    COUNTERPART=$((DOMAIN + 1))
    if [ "$DOMAIN" -ge 1 ] && [ "$COUNTERPART" -le 101 ] && [ $((DOMAIN % 2)) -eq 1 ]; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s domains for %s are an odd base with its counterpart in 1..101 (got %s, %s)\n' \
               "$C_RED" "$C_RST" "$candidate" "$DOMAIN" "$COUNTERPART" >&2
    fi
done

# The property the parity exists for, asserted directly over the same fixtures:
# no checkout's counterpart is any checkout's plant. Stated separately from the
# loop above because it is a claim about the SET rather than about one path.
for candidate in /a /b /c /d/e/f /workspace "${REPO_ROOT}" /very/long/path/to/a/checkout; do
    COUNTERPART=$(( $(cite_domain_id "$candidate") + 1 ))
    COLLIDED=""
    for other in /a /b /c /d/e/f /workspace "${REPO_ROOT}" /very/long/path/to/a/checkout; do
        if [ "$COUNTERPART" -eq "$(cite_domain_id "$other")" ]; then
            COLLIDED="$other"
        fi
    done
    if [ -z "$COLLIDED" ]; then
        SELFTEST_PASS=$((SELFTEST_PASS + 1))
    else
        SELFTEST_FAIL=$((SELFTEST_FAIL + 1))
        printf '  %sFAIL%s the counterpart of %s (%s) is the plant of %s\n' \
               "$C_RED" "$C_RST" "$candidate" "$COUNTERPART" "$COLLIDED" >&2
    fi
done

# The base travels on its own channel, so that the plant's domain and the value
# anything checks it against are two independently sourced numbers rather than
# one number compared with itself.
#
# THE CONTRACT IS "the base is whatever ROS_DOMAIN_ID RESOLVED TO", and the two
# values are read out of the SAME subshell for that reason. Comparing against
# `cite_domain_id "$REPO_ROOT"` asserts something else - that the base is what
# THIS path derives - which is the opposite of the design and was red in two
# ordinary situations. A developer who exports ROS_DOMAIN_ID to join a
# colleague's cell got `expected: 9, actual: 42` on unrelated code, from the
# workflow the assertion three lines below exists to protect. And inside the
# container it failed on every run: the checkout is mounted at /workspace, which
# derives a different number, and compose carries CITE_DOMAIN_BASE across
# precisely so that it does not have to agree with the container's path. It was
# masked only because ./scripts/test runs this file on the host, before
# require_ros_env, and _lib.sh forwards CITE_SELFTESTS_DONE=1 into the container.
#
# `unset` in the command substitution's own subshell rather than `env -u`, which
# says the same thing: shellcheck stops recognising `bash -c` as code once `env`
# is in front of it, so it both warns about the quoting and stops linting the
# snippet.
BASE_PAIR="$(unset CITE_DOMAIN_BASE
             bash -c 'source "$1"; printf "%s %s" "$ROS_DOMAIN_ID" "$CITE_DOMAIN_BASE"' \
                  _ "${REPO_ROOT}/scripts/_lib.sh")"
expect_eq "CITE_DOMAIN_BASE defaults to the domain the same shell resolved" \
          "${BASE_PAIR% *}" "${BASE_PAIR#* }"

# The `:-$ROS_DOMAIN_ID` default itself, exercised deliberately with BOTH
# variables cleared. With nothing in the environment _lib.sh derives the domain
# from the checkout path and the base must follow it there - so this is the one
# assertion that may name `cite_domain_id "$REPO_ROOT"`, because it has removed
# the only thing that could make the two differ. The assertion above never
# reaches this branch: it inherits an ROS_DOMAIN_ID from its parent in every
# environment ./scripts/test runs it in.
expect_eq "with nothing inherited the base is the derived plant domain" \
          "$(cite_domain_id "${REPO_ROOT}")" \
          "$(unset CITE_DOMAIN_BASE ROS_DOMAIN_ID
             bash -c 'source "$1"; printf "%s" "$CITE_DOMAIN_BASE"' \
                  _ "${REPO_ROOT}/scripts/_lib.sh")"

# A counterpart's process carries ROS_DOMAIN_ID at base + 1 while the base stays
# the base. Sourcing _lib.sh inside it must not overwrite one with the other.
expect_eq "an inherited CITE_DOMAIN_BASE survives sourcing _lib.sh" \
          "7" "$(CITE_DOMAIN_BASE=7 ROS_DOMAIN_ID=8 \
                  bash -c 'source "$1"; printf "%s" "$CITE_DOMAIN_BASE"' \
                  _ "${REPO_ROOT}/scripts/_lib.sh")"

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

# R-03 (ADR-0070 item 6): compose() hands the repository-root `.env` over, because
# compose reads only the `.env` in the compose file's directory and so never saw
# it. The opt-in is never interpolated from that file: compose() always sets it
# from `hardware_opt_in`. `docker` is stubbed to print what it was given; nothing
# is started. A scratch root stands in for the repository's, so the developer's
# own `.env` is neither read nor touched.
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
compose_given() { # compose_given <repo root> [resolve] [VAR=value...]
    local root="$1" resolve=""; shift
    if [ "${1:-}" = resolve ]; then resolve=resolve_hardware_opt_in; shift; fi
    env -u CITE_ALLOW_HARDWARE "$@" bash -c '
        source "$1"
        docker() { printf "%s\n" "$@"; printf "ALLOW=%s\n" "${CITE_ALLOW_HARDWARE-unset}"; }
        REPO_ROOT="$2"
        $3
        compose config
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$root" "$resolve" 2>/dev/null
}
ENV_ROOT="$(mktemp -d)"
printf 'CITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_ok "compose() passes the repository-root .env with --env-file" \
    grep -qxF -- "${ENV_ROOT}/.env" <(compose_given "$ENV_ROOT")
expect_ok "compose() passes --env-file when the root .env exists" \
    grep -qxF -- "--env-file" <(compose_given "$ENV_ROOT")
expect_ok "compose() pins an unset opt-in to 0 when .env says 1 and nothing resolved it" \
    grep -qxF -- "ALLOW=0" <(compose_given "$ENV_ROOT")
expect_ok "compose() carries a 1 from .env once the opt-in is resolved" \
    grep -qxF -- "ALLOW=1" <(compose_given "$ENV_ROOT" resolve)
expect_ok "compose() carries the shell's 0 over a 1 in .env when resolved" \
    grep -qxF -- "ALLOW=0" <(compose_given "$ENV_ROOT" resolve CITE_ALLOW_HARDWARE=0)
rm -f "${ENV_ROOT}/.env"
expect_fail "compose() passes no --env-file when there is no root .env" \
    grep -qxF -- "--env-file" <(compose_given "$ENV_ROOT")

# S-06 (ADR-0054): exec_in_container always hands the opt-in across, as the
# command resolved it, so `compose exec` into a container started with
# CITE_ALLOW_HARDWARE=1 cannot carry that stale opt-in into a later command.
# `compose` is stubbed: it reports the service as running (so the exec path is
# taken) and prints what it was given; nothing is started.
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
exec_given() { # exec_given <repo root> [resolve] [VAR=value...]
    local root="$1" resolve=""; shift
    if [ "${1:-}" = resolve ]; then resolve=resolve_hardware_opt_in; shift; fi
    env -u CITE_ALLOW_HARDWARE "$@" bash -c '
        source "$1"
        compose() {
            if [ "$1" = ps ]; then echo dev; return 0; fi
            printf "%s\n" "$@"
        }
        REPO_ROOT="$2"
        $3
        exec_in_container dev true
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$root" "$resolve" 2>/dev/null
}
expect_ok "exec_in_container pins an unset opt-in to 0 on compose exec" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=0" <(exec_given "$ENV_ROOT")
# R-01: the same with a 1 in `.env` that nothing resolved — on `compose exec`,
# on `compose run`, and through `require_ros_env`, the path every container
# command takes. A resolve call slipped into any of them turns these red.
printf 'CITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_ok "exec_in_container hands over 0 on compose exec when .env says 1 and nothing resolved it" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=0" <(exec_given "$ENV_ROOT")
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
run_given() { # run_given <repo root> — exec_in_container with no running service
    env -u CITE_ALLOW_HARDWARE bash -c '
        source "$1"
        compose() { if [ "$1" = ps ]; then return 0; fi; printf "%s\n" "$@"; }
        REPO_ROOT="$2"
        exec_in_container dev true
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$1" 2>/dev/null
}
expect_ok "exec_in_container hands over 0 on compose run when .env says 1 and nothing resolved it" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=0" <(run_given "$ENV_ROOT")
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
ros_env_given() { # ros_env_given <repo root> — require_ros_env re-entering the container
    env -u CITE_ALLOW_HARDWARE CITE_ENV=docker bash -c '
        source "$1"
        in_container() { return 1; }
        docker() { return 0; }
        compose() { if [ "$1" = ps ]; then return 0; fi; printf "%s\n" "$@"; }
        REPO_ROOT="$2"
        require_ros_env test
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$1" 2>/dev/null
}
expect_ok "require_ros_env hands over 0 when .env says 1 and nothing resolved it" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=0" <(ros_env_given "$ENV_ROOT")
rm -f "${ENV_ROOT}/.env"
expect_fail "exec_in_container passes the opt-in exactly once" \
    test "$(exec_given "$ENV_ROOT" CITE_ALLOW_HARDWARE=0 | grep -c '^CITE_ALLOW_HARDWARE=')" -ne 1

# The opt-in's resolution (owner decision 2026-10-06, ADR-0070 amendment item 2):
# shell > repository-root `.env` > 0, in `resolve_hardware_opt_in` and only
# there, and only for the commands that may start the physical side.
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
resolved_given() { # resolved_given <repo root> [VAR=value...]
    local root="$1"; shift
    env -u CITE_ALLOW_HARDWARE "$@" bash -c '
        source "$1"
        REPO_ROOT="$2"
        resolve_hardware_opt_in
        printf "%s|%s" "$(hardware_opt_in)" "$(bash -c "printf %s \"\${CITE_ALLOW_HARDWARE-unset}\"")"
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$root" 2>/dev/null
}
expect_eq "with no .env and no shell value the opt-in resolves to 0" \
    "0|0" "$(resolved_given "$ENV_ROOT")"
printf 'ROS_DOMAIN_ID=0\nCITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_eq "a 1 in .env resolves to 1, exported to child processes" \
    "1|1" "$(resolved_given "$ENV_ROOT")"
expect_eq "the shell's 0 outranks a 1 in .env" \
    "0|0" "$(resolved_given "$ENV_ROOT" CITE_ALLOW_HARDWARE=0)"
expect_eq "a shell value set empty outranks .env too, and means 0" \
    "0|" "$(resolved_given "$ENV_ROOT" CITE_ALLOW_HARDWARE=)"
printf 'CITE_ALLOW_HARDWARE=0\n' > "${ENV_ROOT}/.env"
expect_eq "the shell's 1 outranks a 0 in .env" \
    "1|1" "$(resolved_given "$ENV_ROOT" CITE_ALLOW_HARDWARE=1)"
expect_eq "a 0 in .env resolves to 0" "0|0" "$(resolved_given "$ENV_ROOT")"
printf '# CITE_ALLOW_HARDWARE=1\nCITE_ALLOW_HARDWARE=0\n' > "${ENV_ROOT}/.env"
expect_eq "a commented-out 1 in .env is not read" "0|0" "$(resolved_given "$ENV_ROOT")"

# S-01/S-02/S-03 (ADR-0070): `.env` is read FAIL CLOSED. Only one well-formed
# `CITE_ALLOW_HARDWARE=<value>` line whose value is 1 arms; every other way of
# naming the key resolves to 0 and warns with the offending line's NUMBER, never
# its text, so no other key's value is echoed.
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
opt_in_warning() { # opt_in_warning <repo root> — what resolving the opt-in says on stderr
    env -u CITE_ALLOW_HARDWARE bash -c '
        source "$1"; REPO_ROOT="$2"; C_YEL=""; C_RST=""
        { resolve_hardware_opt_in >/dev/null; } 2>&1
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$1"
}
env_arms() { # env_arms <description> <expected 0|1> <.env content, printf format>
    # shellcheck disable=SC2059  # the content IS the format, so \r and \n are written
    printf "$3" > "${ENV_ROOT}/.env"
    expect_eq "$1" "${2}|${2}" "$(resolved_given "$ENV_ROOT")"
}
env_arms ".env: a plain 1 arms" 1 'CITE_ALLOW_HARDWARE=1\n'
env_arms ".env: a double-quoted 1 with a trailing comment arms" 1 'CITE_ALLOW_HARDWARE="1"  # armed\n'
env_arms ".env: a single-quoted 1 arms" 1 "CITE_ALLOW_HARDWARE='1'\\n"
env_arms ".env: CRLF and surrounding whitespace are tolerated" 1 '  CITE_ALLOW_HARDWARE=1 \r\n'
env_arms ".env: a 1 among other keys arms" 1 'ROS_DOMAIN_ID=3\nCITE_ALLOW_HARDWARE=1\nCITE_XARM_IP=\n'
env_arms ".env: an empty value is off" 0 'CITE_ALLOW_HARDWARE=\n'
env_arms ".env: a quoted 0 is off" 0 'CITE_ALLOW_HARDWARE="0" # off\n'
env_arms ".env: export CITE_ALLOW_HARDWARE=1 does not arm" 0 'export CITE_ALLOW_HARDWARE=1\n'
env_arms ".env: spaces around = do not arm" 0 'CITE_ALLOW_HARDWARE = 1\n'
env_arms ".env: a space after = does not arm" 0 'CITE_ALLOW_HARDWARE= 1\n'
env_arms ".env: a colon for = does not arm" 0 'CITE_ALLOW_HARDWARE: 1\n'
env_arms ".env: the key twice does not arm, even both 1" 0 'CITE_ALLOW_HARDWARE=1\nCITE_ALLOW_HARDWARE=1\n'
env_arms ".env: a 0 then a 1 does not arm" 0 'CITE_ALLOW_HARDWARE=0\nCITE_ALLOW_HARDWARE="1"  # armed\n'
env_arms ".env: a 1 then a malformed line does not arm" 0 'CITE_ALLOW_HARDWARE=1\nexport CITE_ALLOW_HARDWARE=0\n'
env_arms ".env: an unterminated quote does not arm" 0 'CITE_ALLOW_HARDWARE="1\n'
env_arms ".env: a quoted 1 followed by text does not arm" 0 'CITE_ALLOW_HARDWARE="1" x\n'
env_arms ".env: a comment with no space before it does not arm" 0 'CITE_ALLOW_HARDWARE=1#x\n'
env_arms ".env: yes does not arm" 0 'CITE_ALLOW_HARDWARE=yes\n'
env_arms ".env: true does not arm" 0 'CITE_ALLOW_HARDWARE=true\n'
printf 'CITE_XARM_IP=192.0.2.7\nexport CITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_ok "a malformed opt-in line is named by its line number" \
    grep -qF '.env: line 2 names CITE_ALLOW_HARDWARE in a form other than' <(opt_in_warning "$ENV_ROOT")
expect_fail "and the warning echoes no line's text, so no other key's value" \
    grep -qF '192.0.2.7' <(opt_in_warning "$ENV_ROOT")
printf 'CITE_ALLOW_HARDWARE=0\n\nCITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_ok "a repeated key is named with both line numbers" \
    grep -qF 'line 3 names CITE_ALLOW_HARDWARE again (first on line 1)' <(opt_in_warning "$ENV_ROOT")
printf 'CITE_ALLOW_HARDWARE="1" x\n' > "${ENV_ROOT}/.env"
expect_ok "an unrecognised value is named by its line number" \
    grep -qF 'line 1 gives CITE_ALLOW_HARDWARE a value that is neither 1 nor 0' <(opt_in_warning "$ENV_ROOT")
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
expect_ok "the refusal names the line it did not read" \
    grep -qF 'Not read from .env:' <(env -u CITE_ALLOW_HARDWARE bash -c '
        source "$1"; REPO_ROOT="$2"; resolve_hardware_opt_in; require_explicit_hardware_opt_in
    ' _ "${REPO_ROOT}/scripts/_lib.sh" "$ENV_ROOT" 2>&1)
printf 'CITE_ALLOW_HARDWARE=1\n' > "${ENV_ROOT}/.env"
expect_ok "a resolved 1 from .env is what exec_in_container hands the container" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=1" <(exec_given "$ENV_ROOT" resolve)
expect_fail "and it is handed across exactly once" \
    test "$(exec_given "$ENV_ROOT" resolve | grep -c '^CITE_ALLOW_HARDWARE=')" -ne 1
expect_ok "the shell's 0 is what it hands the container over a 1 in .env" \
    grep -qxF -- "CITE_ALLOW_HARDWARE=0" <(exec_given "$ENV_ROOT" resolve CITE_ALLOW_HARDWARE=0)
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
expect_ok "require_explicit_hardware_opt_in passes on a 1 resolved from .env" \
    env -u CITE_ALLOW_HARDWARE bash -c 'source "$1"; REPO_ROOT="$2"; resolve_hardware_opt_in; require_explicit_hardware_opt_in' \
        _ "${REPO_ROOT}/scripts/_lib.sh" "$ENV_ROOT"
# shellcheck disable=SC2016  # expanded by the inner shell, on purpose
expect_fail "and refuses on the same .env when nothing resolved it" \
    env -u CITE_ALLOW_HARDWARE bash -c 'source "$1"; REPO_ROOT="$2"; require_explicit_hardware_opt_in' \
        _ "${REPO_ROOT}/scripts/_lib.sh" "$ENV_ROOT"
rm -f "${ENV_ROOT}/.env"
rmdir "$ENV_ROOT"

# Who resolves it. Exactly the entry points that may start or command the
# physical side call `resolve_hardware_opt_in`; test, scenario, lint, build and everything
# CI runs do not, so a developer's `1` in .env never reaches them and their
# "refused without the opt-in" behaviour holds. A new caller has to be added here
# deliberately.
expect_eq "only enter, home, program and sim resolve the opt-in from .env" \
    "enter home program sim" \
    "$(cd "${REPO_ROOT}/scripts" && grep -l 'resolve_hardware_opt_in' -- * \
        | grep -vx -e _lib.sh -e _selftest.sh | sort | tr '\n' ' ' | sed 's/ $//')"
expect_fail "and no CI workflow resolves it" \
    grep -rqs 'resolve_hardware_opt_in' "${REPO_ROOT}/.github"
expect_eq "_lib.sh spells the opt-in's default in exactly one place" \
    "1" "$(grep -c 'CITE_ALLOW_HARDWARE:-' "${REPO_ROOT}/scripts/_lib.sh")"
opt_in_body() { # opt_in_body <function> — that function's body in _lib.sh
    awk -v head="$1() {" '$0 == head { on = 1; next } on && $0 == "}" { exit } on' \
        "${REPO_ROOT}/scripts/_lib.sh"
}
# R-06: the resolver and the .env reader spell no default of their own; the
# resolved value goes through `hardware_opt_in`.
expect_fail "resolve_hardware_opt_in spells no default of its own" \
    grep -qE ':-[^}]*}' <(opt_in_body resolve_hardware_opt_in)
expect_fail "nor does the .env reader" \
    grep -qE ':-[^}]*}' <(opt_in_body env_file_opt_in)
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok "resolve_hardware_opt_in takes the resolved value through hardware_opt_in" \
    grep -qxF '    CITE_ALLOW_HARDWARE="$(hardware_opt_in)"' <(opt_in_body resolve_hardware_opt_in)
# R-01: _lib.sh itself never resolves — not in compose, exec_in_container,
# require_ros_env or anywhere else — outside the resolver's own definition.
expect_eq "_lib.sh calls resolve_hardware_opt_in nowhere outside its definition" \
    "0" "$(grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/_lib.sh" \
        | grep -v '^resolve_hardware_opt_in() {$' | grep -c 'resolve_hardware_opt_in' || true)"
# R-02: awk, not `grep -zP`, which neither BSD grep nor macOS has.
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok "./scripts/sim resolves it only for a pair" \
    awk 'p2 == "if [ \"$PAIR\" -eq 1 ]; then" && p1 == "    resolve_hardware_opt_in" && $0 == "fi" { f = 1 }
         { p2 = p1; p1 = $0 } END { exit !f }' "${REPO_ROOT}/scripts/sim"
expect_eq "and resolves it nowhere else" \
    "1" "$(grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/sim" | grep -c 'resolve_hardware_opt_in' || true)"
enter_line_of() { awk -v text="$1" 'index($0, text) { print NR; exit }' "${REPO_ROOT}/scripts/enter"; }
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok "./scripts/enter resolves it inside the hardware branch, before the check" \
    test "$(enter_line_of 'if [ "$SERVICE" = "hardware" ]')" -lt "$(enter_line_of '    resolve_hardware_opt_in')" \
      -a "$(enter_line_of '    resolve_hardware_opt_in')" -lt "$(enter_line_of '    require_explicit_hardware_opt_in')"

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
done < <(declared_patches "$CITE_PATCH_DIR")

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
trap 'rm -rf "${SC_FIXTURE}" "${FIXTURE}" "${JUNIT_TMP}"' EXIT

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
# A first-party node aborting on UnknownGoalHandleError is a real cancellation
# defect that this check has already caught once (in the line coordinator that
# now runs as projects/01), and it must stay reported.
TEARDOWN_OURS='<testcase classname="program_cycle.TestCleanShutdown" name="test_nothing_of_ours_exited_badly" time="0.001"><failure message="Traceback (most recent call last):&#10;AssertionError: -6 not found in [0, -2] : skill_server-9 exited with -6&#10;" /></testcase>'

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
# parameter_bridge" would have meant and what is unsupportable — process
# identity does not predict these failures in advance (ADR-0034 and
# docs/measurements/2026-08-27-teardown-signal-family/).
expect_fail "a first-party teardown failure gates under the blocking policy" \
            scenario_verdict "${JUNIT_TMP}/teardown-ours.xml" blocking
expect_eq "a first-party teardown failure is reported with its process named" \
          "AssertionError: -6 not found in [0, -2] : skill_server-9 exited with -6" \
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
# assert_cite_tools_local / cite_tools_found_dir — the gate that stops a checkout
# running another checkout's tooling.
#
# The reported failure, in the paths it actually had: a worktree with no
# virtualenv of its own falls back to the main checkout's `python3`, whose
# editable install of cite_tools points at the main checkout's tools/. The model
# validator then applied MAIN's schema to the WORKTREE's model and reported nine
# "unknown key" errors against a model that was valid. The same mechanism reports
# a broken model as valid whenever the foreign tree is the older one, so this
# must fail closed in both directions.
# -----------------------------------------------------------------------------
CHECKOUT_TOOLS="/repo/tools/cite_tools"
WORKTREE_TOOLS="/repo/.claude/worktrees/agent-x/tools/cite_tools"

expect_ok   "the checkout's own cite_tools is accepted" \
            assert_cite_tools_local "$CHECKOUT_TOOLS" "$CHECKOUT_TOOLS"

# The reported case, in both directions. Neither tree is privileged: whichever
# one is running, importing the other's code is the defect.
expect_fail "a worktree resolving the main checkout's cite_tools is refused" \
            assert_cite_tools_local "$WORKTREE_TOOLS" "$CHECKOUT_TOOLS"
expect_fail "the main checkout resolving a worktree's cite_tools is refused" \
            assert_cite_tools_local "$CHECKOUT_TOOLS" "$WORKTREE_TOOLS"

# Two checkouts whose paths differ by one character are still two checkouts. A
# comparison on basenames, or on anything shorter than the whole path, calls
# these equal — and they are the two trees a person is most likely to have open.
expect_fail "checkouts differing only in the last path element are not a match" \
            assert_cite_tools_local "/repo/twin-2/tools/cite_tools" \
                                    "/repo/twin/tools/cite_tools"

# Both absence states are refusals rather than passes, because "cannot tell" and
# "correct" must never produce the same answer.
expect_fail "cite_tools that is not importable at all is refused, not assumed local" \
            assert_cite_tools_local "$CHECKOUT_TOOLS" ""
expect_fail "a checkout with no tools/ directory is refused" \
            assert_cite_tools_local "" "$CHECKOUT_TOOLS"

# The other half: the reported path must be what the interpreter would ACTUALLY
# import, not a guess assembled from REPO_ROOT. Driven with a decoy package on
# PYTHONPATH, which is how a wrong tree gets resolved in the first place.
if have python3; then
    DECOY="$(mktemp -d)"
    trap 'rm -rf "${SC_FIXTURE}" "${FIXTURE}" "${JUNIT_TMP}" "${DECOY}" "${DECOY}.link"' EXIT
    mkdir -p "${DECOY}/cite_tools"
    : > "${DECOY}/cite_tools/__init__.py"

    expect_eq "cite_tools_found_dir reports where the interpreter would import from" \
              "$(cd "$DECOY" && pwd -P)/cite_tools" \
              "$(PYTHONPATH="$DECOY" cite_tools_found_dir python3)"

    # THE PROPERTY THE COMPARISON RESTS ON. Both sides are resolved through
    # symlinks before they are compared, so one checkout reached by two paths is
    # one checkout. macOS makes this immediate — /tmp is a symlink to /private/tmp
    # and `mktemp -d` hands back the former — and without it this gate refuses a
    # correctly bootstrapped checkout and names two paths that are the same
    # directory, which is the most confusing failure it could produce.
    ln -s "$DECOY" "${DECOY}.link"
    expect_eq "the same tree reached through a symlink resolves to one path" \
              "$(PYTHONPATH="$DECOY" cite_tools_found_dir python3)" \
              "$(PYTHONPATH="${DECOY}.link" cite_tools_found_dir python3)"

    # `die` exits, so the guard is called in a subshell — otherwise a passing
    # test would terminate this file and the run would look complete.
    guard_under_pythonpath() {  # guard_under_pythonpath <pythonpath>
        ( PYTHONPATH="$1" require_local_cite_tools python3 "The self-test" )
    }

    expect_fail "require_local_cite_tools refuses a foreign cite_tools" \
                guard_under_pythonpath "$DECOY"
    expect_ok   "require_local_cite_tools accepts this checkout's own cite_tools" \
                guard_under_pythonpath "${REPO_ROOT}/tools"

    # Absence is the caller's message to give, not this one's: every script that
    # imports cite_tools already reports "not installed" in its own words, and
    # replacing those with this gate's wording would lose the remedy they name.
    # Driven with an interpreter that resolves nothing, rather than by unsetting
    # PYTHONPATH — the ambient editable install would still answer and this would
    # be testing the mismatch case again under a different name.
    printf '#!/bin/sh\nexit 1\n' > "${DECOY}/resolves-nothing"
    chmod +x "${DECOY}/resolves-nothing"
    expect_ok   "an absent cite_tools is left to the caller's own report" \
                require_local_cite_tools "${DECOY}/resolves-nothing" "The self-test"
else
    printf '  %s!%s python3 absent — the interpreter half of the cite_tools gate did not run\n' \
           "$C_YEL" "$C_RST" >&2
fi

# -----------------------------------------------------------------------------
# ./scripts/sim — a zone is defaulted only when the model leaves one answer.
#
# When the generated plans declare exactly one zone, `--zone` may be left out and
# that zone comes up; when they declare several, it is required and the script
# refuses, naming them (ADR-0069 decision 5) — ADR-0056's rule, returning by
# itself the day a second zone is declared. The rule is `default_zone`, which
# runs `cite_bringup/zones.py`; it is driven here against synthetic plan sets,
# because driving `./scripts/sim` with no zone on a one-zone model would START a
# cell, and a self-test may not.
#
# Only the REFUSING paths of `./scripts/sim` itself are driven. Every case below
# exits before `require_ros_env`, which is the line that decides where the rest
# of the script runs.
# -----------------------------------------------------------------------------
ZONES_TMP="$(mktemp -d)"
mkdir -p "${ZONES_TMP}/one" "${ZONES_TMP}/two" "${ZONES_TMP}/none"
printf 'zone: zone_x\n' > "${ZONES_TMP}/one/zone_x_plan.yaml"
printf 'zone: zone_x\n' > "${ZONES_TMP}/two/zone_x_plan.yaml"
printf 'zone: zone_y\n' > "${ZONES_TMP}/two/zone_y_plan.yaml"
zone_refusal() { # zone_refusal <expected substring> <plans-dir>
    local output
    output="$(default_zone "$2" 2>&1 || true)"
    grep -qF -- "$1" <<<"$output"
}

expect_eq   "one declared zone is the default" \
            "zone_x" "$(default_zone "${ZONES_TMP}/one" 2>/dev/null)"
expect_fail "two declared zones have no default" \
            default_zone "${ZONES_TMP}/two"
expect_ok   "and the refusal says --zone is required" \
            zone_refusal "--zone is required" "${ZONES_TMP}/two"
expect_ok   "and names every zone, so the reader can act on it" \
            zone_refusal "zone_x, zone_y" "${ZONES_TMP}/two"
expect_eq   "and prints no zone on stdout for a caller to pick up by mistake" \
            "" "$(default_zone "${ZONES_TMP}/two" 2>/dev/null || true)"
expect_fail "no declared zone has no default either" \
            default_zone "${ZONES_TMP}/none"
expect_ok   "the shipped model's plans have exactly one answer" \
            default_zone

# A NAMED zone is checked against the same plans. An undeclared one used to
# start a container, fail inside the launch's plan lookup and exit 0.
check_refusal() { # check_refusal <expected substring> <zone> <plans-dir>
    local output
    output="$(require_declared_zone "$2" "$3" 2>&1 || true)"
    grep -qF -- "$1" <<<"$output"
}
expect_ok   "a declared zone passes the check" \
            require_declared_zone zone_y "${ZONES_TMP}/two"
expect_fail "an undeclared zone is refused" \
            require_declared_zone zone_z "${ZONES_TMP}/two"
expect_ok   "and the refusal names it and every declared zone" \
            check_refusal "no zone 'zone_z'. Declared: zone_x, zone_y." zone_z "${ZONES_TMP}/two"
expect_ok   "and says so when there are none at all" \
            check_refusal "Declared: none" zone_z "${ZONES_TMP}/none"
expect_ok   "the shipped model declares the zone its default names" \
            require_declared_zone "$(default_zone)"
rm -rf "$ZONES_TMP"

# zones.py answers from the source tree only, and refuses from anywhere its
# source-tree plans are not — which is where an install prefix puts its copy.
ZONES_COPY="$(mktemp -d)"
cp "${REPO_ROOT}/workspace/src/cite_bringup/cite_bringup/zones.py" "${ZONES_COPY}/zones.py"
zones_copy_says() { # zones_copy_says <expected substring>
    local output
    output="$(python3 "${ZONES_COPY}/zones.py" 2>&1 || true)"
    grep -qF -- "$1" <<<"$output"
}
expect_fail "zones.py refuses to run where it has no source-tree plans beside it" \
            python3 "${ZONES_COPY}/zones.py"
expect_ok   "and says it is the copy an install prefix carries" \
            zones_copy_says "the copy an install prefix carries"
rm -rf "$ZONES_COPY"

# The two shell entry points that default a zone themselves ask that one
# function rather than stating a zone; `./scripts/scenario` gets the same
# answer through `tests/scenarios/_cell.py`, whose guards hold it there. A grep,
# because the alternative is starting a cell.
# The pattern is matched literally, so the `$(...)` in it is text and is never
# expanded; that is what the single quotes are for.
for entry in sim program; do
    # shellcheck disable=SC2016
    expect_ok "./scripts/${entry} defaults its zone through default_zone" \
              grep -qF 'ZONE="$(default_zone)"' "${REPO_ROOT}/scripts/${entry}"
done

sim_args() { "${REPO_ROOT}/scripts/sim" "$@"; }
# Captured and then matched, never piped: `set -o pipefail` is in force here, and
# a refusal exits non-zero by design, so a pipeline would report the refusal
# rather than whether the diagnosis said the right thing.
sim_says() { # sim_says <expected substring> <args...>
    local expected="$1"; shift
    local output
    output="$("${REPO_ROOT}/scripts/sim" "$@" 2>&1 || true)"
    grep -qF -- "$expected" <<<"$output"
}

# `--zone` as the last token. Without the check this leaves ZONE empty and the
# next refusal fires with a message about a missing flag the caller did type.
expect_fail "./scripts/sim --zone with no name after it refuses" \
            sim_args --zone
expect_ok   "and says what is missing is the zone NAME" \
            sim_says "needs a zone name" --zone

# `--zone` swallowing the next flag. This used to set ZONE="--headless" and hand
# it to the launch, which failed looking for a plan of that name.
expect_fail "./scripts/sim --zone --headless refuses rather than swallowing the flag" \
            sim_args --zone --headless
expect_ok   "and quotes the token it was given" \
            sim_says "was given '--headless'" --zone --headless
expect_fail "./scripts/sim --zone zone:=cell_b refuses too" \
            sim_args --zone zone:=cell_b

# Three spellings set one value. A comment claimed a bare `zone:=X` was "caught
# below rather than silently competing with the flag"; both halves were false —
# the case arm consumed it and the last writer won.
expect_fail "two spellings naming different zones are refused" \
            sim_args --zone cell_x zone:=cell_b
expect_ok   "and the refusal names both spellings and both zones" \
            sim_says "--zone says 'cell_x' and zone:= says 'cell_b'" --zone cell_x zone:=cell_b
expect_fail "and it is refused whichever order they come in" \
            sim_args zone:=cell_b --zone=cell_x

# A zone the model does not declare is refused on the host, naming the ones it
# does, before any container. It used to start one and exit 0.
expect_fail "./scripts/sim --zone with an undeclared zone refuses" \
            sim_args --zone zone_nobody_declared --headless
expect_ok   "and names the zone and the declared ones" \
            sim_says "the model declares no zone 'zone_nobody_declared'. Declared: $(default_zone)." \
            --zone zone_nobody_declared --headless
expect_ok   "whichever spelling named it" \
            sim_says "zone:= named a zone the model does not declare" zone:=zone_nobody_declared

# An empty zone is refused in every spelling rather than falling back to the
# default, as ./scripts/scenario and ./scripts/program already refused it.
expect_fail "./scripts/sim --zone= refuses instead of falling back to the default" \
            sim_args --zone= --headless
expect_ok   "and says that an empty zone would have run the default" \
            sim_says "empty zone name" --zone= --headless
expect_fail "./scripts/sim zone:= refuses too" \
            sim_args zone:= --headless
expect_ok   "with the same diagnosis" \
            sim_says "zone:= was given an empty zone name" zone:= --headless
expect_fail "and so does the two-token spelling of an empty zone" \
            sim_args --zone "" --headless

# ./scripts/console is `./scripts/sim --pair --console`, windowed, and nothing
# else (ADR-0071): every rule is sim's. Driven only on paths that refuse before a
# container, as above.
console_says() { # console_says <expected substring> <args...>
    local expected="$1"; shift
    local output
    output="$("${REPO_ROOT}/scripts/console" "$@" 2>&1 || true)"
    grep -qF -- "$expected" <<<"$output"
}
expect_fail "./scripts/console --headless refuses: the panel needs a window" \
            "${REPO_ROOT}/scripts/console" --headless
expect_ok   "and names the headless spelling in full" \
            console_says "./scripts/sim --pair --console --headless" --headless
expect_fail "./scripts/console hands --zone to sim, which refuses an undeclared zone" \
            "${REPO_ROOT}/scripts/console" --zone zone_nobody_declared
expect_ok   "with sim's own diagnosis" \
            console_says "no zone 'zone_nobody_declared'" --zone zone_nobody_declared
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "./scripts/console execs sim with --pair --console and the caller's arguments" \
            grep -qxF 'exec "${REPO_ROOT}/scripts/sim" --pair --console "$@"' \
            "${REPO_ROOT}/scripts/console"
expect_eq   "and resolves no hardware opt-in of its own: sim's is the one" \
    "0" "$(grep -v '^[[:space:]]*#' "${REPO_ROOT}/scripts/console" | grep -c 'hardware_opt_in' || true)"

# A-03: a windowed console refuses when its panel's plugin is not on the gz-gui
# search path, rather than opening a window without its Stop button.
PLUGIN_FIXTURE="$(mktemp -d)"
mkdir -p "${PLUGIN_FIXTURE}/a" "${PLUGIN_FIXTURE}/b" "${PLUGIN_FIXTURE}/c"
touch "${PLUGIN_FIXTURE}/b/libCellConsole.so" "${PLUGIN_FIXTURE}/c/libCellConsole.so"
touch "${PLUGIN_FIXTURE}/a/CellConsole.so"
expect_eq   "gui_plugin_dir finds lib<plugin>.so, first match on the path wins" \
    "${PLUGIN_FIXTURE}/b" \
    "$(gui_plugin_dir CellConsole "${PLUGIN_FIXTURE}/a::${PLUGIN_FIXTURE}/b:${PLUGIN_FIXTURE}/c")"
expect_fail "gui_plugin_dir fails when no directory holds it (a bare name is not lib<name>.so)" \
    gui_plugin_dir CellConsole "${PLUGIN_FIXTURE}/a"
expect_fail "gui_plugin_dir fails on an empty search path" \
    gui_plugin_dir CellConsole ""
rm -rf "$PLUGIN_FIXTURE"
sim_console_check() { # the sim lines that guard a windowed console on the plugin
    awk '/^if \[ "\$CONSOLE" -eq 1 \] && \[ "\$HEADLESS" -eq 0 \]; then$/ { f = 1 }
         f { print } f && /^fi$/ { exit }' "${REPO_ROOT}/scripts/sim"
}
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "./scripts/sim asks gui_plugin_dir for CellConsole when the console is windowed" \
    grep -qF 'gui_plugin_dir CellConsole "${GZ_GUI_PLUGIN_PATH:-}"' <(sim_console_check)
expect_ok   "and dies, naming the headless spelling, when it does not resolve" \
    grep -qF './scripts/sim --pair --console --headless' <(sim_console_check)
sim_line_of() { awk -v text="$1" 'index($0, text) { print NR; exit }' "${REPO_ROOT}/scripts/sim"; }
expect_ok   "after the overlay is sourced, and before anything is launched" \
    test "$(sim_line_of 'source_overlay')" -lt "$(sim_line_of 'gui_plugin_dir CellConsole')" \
      -a "$(sim_line_of 'gui_plugin_dir CellConsole')" -lt "$(sim_line_of 'exec python3 -m cite_bringup.pair')"
# ADR-0072: the hardware opt-in decides which sides a pair starts, in sim and
# nowhere else, by the one rule (`program.sides.pair_sides`), and the choice is
# handed to the supervisor explicitly - never inferred inside pair.py.
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "./scripts/sim hands the supervisor --sides, read from sides --pair-sides" \
    grep -qF 'PAIR_ARGS=(--sides "$PAIR_SIDES" "${PAIR_ARGS[@]}")' "${REPO_ROOT}/scripts/sim"
expect_ok   "after the opt-in is resolved, and before the supervisor is started" \
    test "$(sim_line_of '    resolve_hardware_opt_in')" -lt "$(sim_line_of 'cite_bringup.program.sides --zone "$ZONE" --pair-sides')" \
      -a "$(sim_line_of 'cite_bringup.program.sides --zone "$ZONE" --pair-sides')" -lt "$(sim_line_of 'exec python3 -m cite_bringup.pair')"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "and says why when it starts the plant alone" \
    grep -qF 'warn "$(head -n -1 <<<"$PAIR_SIDES_SAID")"' "${REPO_ROOT}/scripts/sim"

# ./scripts/program checks a named zone the same way, before it stops this
# checkout's containers or starts any.
program_says() { # program_says <expected substring> <args...>
    local expected="$1"; shift
    local output
    output="$("${REPO_ROOT}/scripts/program" "$@" 2>&1 || true)"
    grep -qF -- "$expected" <<<"$output"
}
expect_fail "./scripts/program --zone with an undeclared zone refuses" \
            "${REPO_ROOT}/scripts/program" --zone zone_nobody_declared --headless
expect_ok   "and names the zone" \
            program_says "no zone 'zone_nobody_declared'" --zone zone_nobody_declared --headless

# ./scripts/program stops every side's belt before it stops the pair, on every
# route out — a normal end, a failure and Ctrl-C all reach `teardown`. A
# simulated belt stops when its simulator does; a physical one is a drive whose
# setpoint persists, and StopAll, which used to stop every belt, left with the
# line (ADR-0069). A grep, because driving it means starting a pair.
# The pair runs in a process group of its own, so the terminal's Ctrl-C reaches
# only this script's trap and the order program -> belts -> pair holds. Driven
# here with ordinary processes standing in for the supervisor; no container.
GROUP_TMP="$(mktemp -d)"
group_of() { ps -o pgid= -p "$1" 2>/dev/null | tr -d ' '; }
start_in_own_group "${GROUP_TMP}/a.log" sleep 30
own_pid="$STARTED_PID"
expect_ok   "start_in_own_group puts the job in a process group of its own" \
            test "$(group_of "$own_pid")" = "$own_pid"
expect_ok   "which is not the script's group, so the terminal's SIGINT misses it" \
            test "$(group_of "$own_pid")" != "$(group_of $$)"
expect_ok   "and stop_own_group ends a job that obeys SIGINT without killing it" \
            stop_own_group "$own_pid" 5
expect_fail "and leaves nothing running" kill -0 "$own_pid"
# A job that ignores SIGINT, with a child of its own: the ceiling has to fire
# and SIGKILL has to reach the whole group, child included.
# shellcheck disable=SC2016  # expanded by the inner shell, not this one
start_in_own_group "${GROUP_TMP}/b.log" \
    bash -c 'trap "" INT; sleep 30 & echo "$!" > "$0"; wait' "${GROUP_TMP}/child.pid"
stubborn_pid="$STARTED_PID"
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "${GROUP_TMP}/child.pid" ] && break; sleep 0.2; done
expect_fail "a job that ignores SIGINT is killed at the ceiling, and says so" \
            stop_own_group "$stubborn_pid" 1
expect_fail "and the job is gone" kill -0 "$stubborn_pid"
expect_fail "and so is its child, because SIGKILL went to the group" \
            kill -0 "$(cat "${GROUP_TMP}/child.pid" 2>/dev/null || echo 0)"
expect_eq   "and job control is put back as it was" "" "$(case "$-" in *m*) echo on ;; esac)"
rm -rf "$GROUP_TMP"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "./scripts/program starts the pair in its own process group" \
            grep -qF 'start_in_own_group "$PAIR_LOG" "${REPO_ROOT}/scripts/sim"' \
            "${REPO_ROOT}/scripts/program"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "and stops it with the SIGKILL fallback" \
            grep -qF 'stop_own_group "$PAIR_PID" "$PAIR_STOP_CEILING_S"' \
            "${REPO_ROOT}/scripts/program"
# T-01: a physical side without CITE_ALLOW_HARDWARE=1 is refused before bring-up,
# by the plan's own rule (`cite_bringup.program.sides --hardware-opt-in`), not
# found later in a side's launch log. A grep, because driving it needs ROS.
program_line_of() { awk -v text="$1" 'index($0, text) { print NR; exit }' "${REPO_ROOT}/scripts/program"; }
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
OPT_IN_LINE="$(program_line_of 'cite_bringup.program.sides --zone "$ZONE" --hardware-opt-in')"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
BRING_UP_LINE="$(program_line_of 'start_in_own_group "$PAIR_LOG"')"
expect_ok   "./scripts/program asks the hardware opt-in before it brings anything up" \
            test "${OPT_IN_LINE:-999999}" -lt "${BRING_UP_LINE:-0}"
# The T-01 check sees the RESOLVED opt-in (shell > .env > 0): it is resolved
# on the host before the container is entered, and so before the check.
RESOLVE_LINE="$(awk '$0 == "resolve_hardware_opt_in" { print NR; exit }' "${REPO_ROOT}/scripts/program")"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
ENTER_LINE="$(program_line_of 'require_ros_env program "$@"')"
expect_ok   "./scripts/program resolves the opt-in before it enters the container" \
            test "${RESOLVE_LINE:-999999}" -lt "${ENTER_LINE:-0}"
expect_ok   "and so before the check before bring-up" \
            test "${RESOLVE_LINE:-999999}" -lt "${OPT_IN_LINE:-0}"
# shellcheck disable=SC2016  # the literal text is the point; it must not expand
expect_ok   "./scripts/program's teardown commands every side's belt to zero" \
            grep -qF 'python3 -m cite_bringup.program.belt --zone "$ZONE" --stop' \
            "${REPO_ROOT}/scripts/program"

# -----------------------------------------------------------------------------
# ./scripts/scenario — the same two token guards, for the script whose default is
# read by the scenario itself.
#
# `./scripts/scenario --zone` exports a selection that `tests/scenarios/_cell.py`
# reads, falling back to `cite_bringup/zones.py`'s answer when it is empty
# (ADR-0069 decision 5). So naming a zone is an override, and that is exactly why
# its failure modes are quieter, and why they are driven here.
#
# WHAT CARRIES THE WEIGHT IS THE MESSAGE, not the exit status, and that is
# measured rather than assumed. Strip the refusals out and every `expect_fail`
# below still passes — the run goes on to fail downstream instead, which is the
# same shape of evidence as the ctest timeout that used to stand in for the
# planning-scene-loader assertion. Only the `scenario_says` cases fail: 2 of them
# did when this was mutation-checked. So each refusal gets one of each, and the
# `expect_fail` half is there to pin that a refusal EXITS rather than warning.
#
# With the refusals in place every case exits inside the FIRST parse loop, which
# runs before `require_ros_env`, so none of them starts a container. That is a
# property of the refusals and not of the argument lists: a regression that
# removes one lets that case re-enter the container, which is the price of
# driving the entry point rather than a function — the same price the
# `./scripts/sim` block above pays.
scenario_args() { "${REPO_ROOT}/scripts/scenario" "$@"; }
# Captured and then matched, never piped, for the reason `sim_says` gives.
scenario_says() { # scenario_says <expected substring> <args...>
    local expected="$1"; shift
    local output
    output="$("${REPO_ROOT}/scripts/scenario" "$@" 2>&1 || true)"
    grep -qF -- "$expected" <<<"$output"
}

# `--zone` swallowing the next flag. This set CITE_SCENARIO_ZONE to
# '--teardown-advisory' AND let the second parse loop consume that flag as the
# zone's name, so TEARDOWN_POLICY stayed `blocking`: the caller asked for an
# advisory teardown, silently got a gating one, and the run then died at plan
# load naming a zone nobody typed.
expect_fail "./scripts/scenario --zone --teardown-advisory refuses rather than swallowing it" \
            scenario_args bringup --zone --teardown-advisory
expect_ok   "and quotes the token it was given" \
            scenario_says "was given '--teardown-advisory'" bringup --zone --teardown-advisory
expect_fail "./scripts/scenario --zone zone:=cell_x refuses too" \
            scenario_args bringup --zone zone:=cell_x
expect_ok   "and quotes that token as well" \
            scenario_says "was given 'zone:=cell_x'" bringup --zone zone:=cell_x
# Already refused before the guards landed, and pinned here so the two spellings
# of a missing name cannot come apart.
expect_fail "./scripts/scenario --zone with no name after it refuses" \
            scenario_args bringup --zone
expect_fail "./scripts/scenario --zone with an undeclared zone refuses on the host" \
            scenario_args bringup --zone zone_nobody_declared
expect_ok   "and names the zone" \
            scenario_says "no zone 'zone_nobody_declared'" bringup --zone zone_nobody_declared

# An empty zone is refused rather than falling back. `_cell.zone()` treats an
# exported empty string as no selection and returns the default: the caller
# named something and would silently get the model's only zone.
expect_fail "./scripts/scenario --zone= refuses instead of falling back to the default" \
            scenario_args bringup --zone=
expect_ok   "and says that an empty zone would have run the default" \
            scenario_says "empty zone name" bringup --zone=
expect_fail "and the two-token spelling of an empty zone is refused as well" \
            scenario_args bringup --zone ""
expect_ok   "with the same diagnosis, so the two spellings cannot come apart" \
            scenario_says "empty zone name" bringup --zone ""

# The GPU selection that made the windows affordable. It is guarded on the
# NVIDIA vendor library EXISTING in the container, so a host without one falls
# through untouched; naming a vendor library that is absent is how this would
# break somebody else's machine.
expect_ok   "./scripts/sim selects a GPU vendor library for a windowed run" \
            grep -q '__GLX_VENDOR_LIBRARY_NAME' "${REPO_ROOT}/scripts/sim"
expect_ok   "and only when the container actually has that library" \
            grep -q 'libGLX_nvidia.so.0' "${REPO_ROOT}/scripts/sim"

# -----------------------------------------------------------------------------
printf '  %s%d passed, %d failed%s (shell gate self-tests)\n' \
       "$( [ "$SELFTEST_FAIL" -eq 0 ] && printf '%s' "$C_GRN" || printf '%s' "$C_RED" )" \
       "$SELFTEST_PASS" "$SELFTEST_FAIL" "$C_RST"
[ "$SELFTEST_FAIL" -eq 0 ]
