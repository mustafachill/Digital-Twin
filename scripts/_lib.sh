#!/usr/bin/env bash
# =============================================================================
# Shared helpers for ./scripts/*
#
# The central job of this file is `require_ros_env`, which lets the same script
# work from a macOS laptop and from a Linux workstation. Authoring happens on
# any machine; building and running happen on Linux. A developer should never
# have to think about which.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/infra/docker/docker-compose.yml"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
    C_BLU=$'\033[34m'; C_DIM=$'\033[2m';  C_RST=$'\033[0m'
else
    C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_RST=""
fi

info()  { printf '%s==>%s %s\n' "$C_BLU" "$C_RST" "$*"; }
ok()    { printf '%s  ok%s %s\n' "$C_GRN" "$C_RST" "$*"; }
warn()  { printf '%swarn%s %s\n' "$C_YEL" "$C_RST" "$*" >&2; }
die()   { printf '%serror%s %s\n' "$C_RED" "$C_RST" "$*" >&2; exit 1; }
step()  { printf '\n%s%s%s\n' "$C_DIM" "$*" "$C_RST"; }

in_container() { [ -f /etc/cite-container ]; }

have() { command -v "$1" >/dev/null 2>&1; }

# -----------------------------------------------------------------------------
# ROS_DOMAIN_ID — one DDS domain per checkout, not one for the whole machine.
#
# Everything used to default to domain 0. DDS discovery is multicast within a
# domain, so two cells running at once on the same host discovered each other's
# nodes: a scenario run took 421 s instead of 105 s because another workspace's
# move_group was visible in its graph, and `ros2 node list` showed nodes nobody
# had launched. That breaks parallel CI and makes any local result irreproducible
# whenever two people — or two agents — work at the same time.
#
# The identifier is derived from the absolute path of the checkout, which gives
# the two properties that matter at once:
#
#   isolation     two clones or worktrees never collide, without configuration
#   attachability `./scripts/sim` and `./scripts/enter` from the *same* checkout
#                 land on the same domain, so a shell can still see the cell it
#                 just launched. A random per-run value would break that.
#
# The value is computed on the outermost invocation and inherited from there:
# the container sees a different path (/workspace) and would otherwise derive a
# different number, so `compose` hands the host's value across and the branch
# below preserves anything already set. An explicit ROS_DOMAIN_ID in the
# environment always wins.
#
# Range 1-101: 0 is the ecosystem-wide default this exists to get away from, and
# on Linux domains above 101 collide with the ephemeral port range.
# -----------------------------------------------------------------------------
cite_domain_id() {
    local key="${1:-$REPO_ROOT}" sum
    # `cksum` is POSIX and identical on macOS and Linux; `md5sum` is neither.
    sum="$(printf '%s' "$key" | cksum | awk '{print $1}')"
    printf '%s' "$(( sum % 101 + 1 ))"
}

if [ -n "${ROS_DOMAIN_ID:-}" ]; then
    # Preserved rather than overwritten, so a container that inherited a derived
    # value does not report it as an explicit choice by the developer.
    CITE_DOMAIN_SOURCE="${CITE_DOMAIN_SOURCE:-explicit}"
else
    ROS_DOMAIN_ID="$(cite_domain_id)"
    CITE_DOMAIN_SOURCE="derived from this checkout"
fi
export ROS_DOMAIN_ID CITE_DOMAIN_SOURCE

# -----------------------------------------------------------------------------
# COMPOSE_PROJECT_NAME — one set of Docker volumes per checkout, not one per host.
#
# The compose file pins `name: cite-digital-twin` and declares its volumes as
# bare `cite-build`, `cite-install` and `cite-log`. Compose scopes a volume to
# the project, so those become `cite-digital-twin_cite-build` and friends — ONE
# set, shared by every checkout on the machine that does not override the project
# name. On a host running several worktrees at once that is shared mutable state
# between processes that do not know about each other, and it has produced all
# of the following here:
#
#   * concurrent builds corrupting each other, surfacing as
#     `failed to create symbolic link ... File exists`,
#     `rosidl_cmake ... No such file or directory`, and packages that fail to
#     configure with `CMAKE_C_COMPILER not set` — none of which name the cause;
#   * one checkout running another checkout's binaries out of the shared install
#     volume, so a test result described code nobody was looking at;
#   * `./scripts/clean --all` destroying another agent's build mid-session,
#     because `compose down --volumes` against the shared project takes the
#     shared volumes with it.
#
# The last one is why this is derived rather than left to convention. Several
# checkouts here had set COMPOSE_PROJECT_NAME by hand and were isolated; the ones
# that had not were silently sharing. A convention that only protects the people
# who remember it is not isolation, and the failure mode is invisible until it
# has already cost somebody a session.
#
# Derived from the absolute path of the checkout, exactly as cite_domain_id is
# and for the same two reasons:
#
#   isolation     two clones or worktrees never collide, without configuration
#   attachability `./scripts/enter` attaches to the cell `./scripts/sim` started
#                 from the SAME checkout, because the value is a pure function of
#                 the path rather than of the run
#
# Path, not git metadata, deliberately: a `git worktree`'s `.git` is a file
# pointing outside the directory compose bind-mounts as /workspace, which has
# already broken `vcs import` once and had to be worked around with
# GIT_CEILING_DIRECTORIES. Every worktree has a distinct absolute path, so the
# path alone gives the property we need and needs nothing mounted to read it.
#
# The name carries the checkout's directory name as well as the hash so that
# `docker volume ls` is legible when something does go wrong; the hash is what
# makes it unique, and two directories with the same basename still differ.
# -----------------------------------------------------------------------------
cite_project_name() {
    local key="${1:-$REPO_ROOT}" slug sum
    # `cksum` is POSIX and identical on macOS and Linux; `md5sum` is neither.
    sum="$(printf '%s' "$key" | cksum | awk '{print $1}')"
    # Compose accepts [a-z0-9_-] only, and must not start with a dash. Lowercase,
    # replace every other character, collapse runs, and trim the ends.
    slug="$(printf '%s' "${key##*/}" \
        | tr '[:upper:]' '[:lower:]' \
        | tr -c 'a-z0-9' '-' \
        | tr -s '-')"
    slug="${slug#-}"
    slug="${slug%-}"
    slug="$(printf '%s' "$slug" | cut -c1-24)"
    slug="${slug%-}"
    [ -n "$slug" ] || slug="checkout"
    printf 'cite-%s-%s' "$slug" "$sum"
}

if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
    # An explicit choice always wins, and is reported as one rather than being
    # mistaken for the derived value.
    CITE_PROJECT_SOURCE="${CITE_PROJECT_SOURCE:-explicit}"
else
    COMPOSE_PROJECT_NAME="$(cite_project_name)"
    CITE_PROJECT_SOURCE="derived from this checkout"
fi
export COMPOSE_PROJECT_NAME CITE_PROJECT_SOURCE

# -----------------------------------------------------------------------------
# Build freshness — a gate must not answer from artefacts older than the source.
#
# Namespacing the compose project stops one checkout reading ANOTHER checkout's
# build. It does nothing about a checkout reading its OWN stale build, and that
# is a distinct defect with the same shape: a confident wrong answer.
#
# It has now cost this branch twice.
#
#   * `./scripts/lint` reported that two packages "register no lint test at all"
#     while both package.xml files on disk declared <test_depend>ament_lint_common
#     </test_depend>. ament_lint_auto resolves its linter set at CONFIGURE time,
#     so a build tree configured before that dependency was added has already
#     baked in "zero linters" and no amount of re-running ctest changes it. After
#     a rebuild the same command reported `Lint clean` across all seven packages.
#   * The same staleness manufactured a "known-red at base" belief about two test
#     suites, which four agents repeated and the orchestrator propagated for
#     hours before a rebuild showed 129 tests passing.
#
# In both cases the source tree was correct, the command was correct, and the
# answer was wrong. Nothing in the output pointed at the build directory.
#
# The fix is a content fingerprint of the inputs that decide CMake configuration
# — every first-party package.xml and CMakeLists.txt — recorded in the build tree
# when a build succeeds and checked by the gates that consume it. Content, not
# timestamps: a mtime comparison is a timing heuristic and would be wrong across
# a bind mount, a `git checkout` that rewinds mtimes, and a volume restored from
# elsewhere (P4 applies to gates as much as to bring-up).
#
# Only package.xml and CMakeLists.txt are fingerprinted, deliberately. Changing a
# .cpp does not alter the build CONFIGURATION, and colcon's own dependency
# tracking rebuilds it correctly; a fingerprint over every source file would fire
# on every edit and be disabled within a day. This fires on exactly the class of
# change that colcon silently gets wrong.
#
# The stamp lives inside workspace/build, so it is scoped to the same volume as
# the artefacts it describes and is destroyed with them. Note that on a Docker
# host workspace/build is an empty directory until a container mounts the volume
# over it, so these are only meaningful where the build actually lives.
# -----------------------------------------------------------------------------
cite_build_stamp_path() {
    printf '%s' "${REPO_ROOT}/workspace/build/.cite-build-inputs"
}

cite_build_inputs_fingerprint() {
    local src="${REPO_ROOT}/workspace/src" file relative
    if [ ! -d "$src" ]; then
        printf 'no-source'
        return 0
    fi
    # `cksum < file` rather than `cksum file`: reading from stdin keeps the
    # filename out of the checksum, so the fingerprint is identical on the host
    # and in the container, where the same tree is /workspace rather than a home
    # directory. Paths are recorded separately, relative, for the same reason —
    # and they are recorded, so that ADDING or REMOVING a package is a change.
    {
        while IFS= read -r file; do
            relative="${file#"$src"/}"
            printf '%s %s\n' "$relative" "$(cksum < "$file" | awk '{print $1}')"
        done < <(find "$src" -mindepth 2 \
                     \( -name package.xml -o -name CMakeLists.txt \) \
                     -not -path '*/external/*' 2>/dev/null | LC_ALL=C sort)
    } | cksum | awk '{print $1}'
}

record_build_inputs() {
    local stamp
    stamp="$(cite_build_stamp_path)"
    [ -d "$(dirname "$stamp")" ] || return 0
    cite_build_inputs_fingerprint > "$stamp" 2>/dev/null || true
}

# assert_build_inputs_current <gate name>
#
# Fails closed. An unstamped build tree is not evidence of a fresh one — it is an
# absent answer, and presenting one of those as clean is the defect this whole
# block exists to stop. The one-time cost is a rebuild for anyone holding a
# volume created before this check existed.
assert_build_inputs_current() {
    local gate="$1" stamp recorded current
    stamp="$(cite_build_stamp_path)"

    if [ ! -f "$stamp" ]; then
        die "${gate} cannot trust this build tree: it carries no input fingerprint.
  It was built before this check existed, or by something other than ./scripts/build.
  A gate that reports on artefacts it cannot date is how this branch acquired a
  'known-red at base' belief that survived four agents and was false.
  Run ./scripts/build."
    fi

    recorded="$(cat "$stamp" 2>/dev/null || true)"
    current="$(cite_build_inputs_fingerprint)"
    if [ "$recorded" != "$current" ]; then
        die "${gate} is looking at a STALE build tree, and would report a wrong answer.
  A first-party package.xml or CMakeLists.txt has changed since this tree was built
  (fingerprint ${recorded:-none} on disk, ${current} in the source).

  This matters more than it sounds: ament_lint_auto resolves its linter set at
  CMake CONFIGURE time, so a stale tree reports 'registers no lint test at all'
  for a package whose package.xml declares ament_lint_common right now. The same
  staleness reported two suites as failing that pass on a fresh build.

  Run ./scripts/build."
    fi
}

# -----------------------------------------------------------------------------
# assert_lint_coverage <selected> <finished> [package-with-no-lint-test...]
#
# The judgement at the heart of ./scripts/lint: did the linter run actually look
# at anything? Separated from the colcon plumbing so it can be driven with
# synthetic numbers by scripts/_selftest.sh — the states that matter here are
# precisely the ones that are awkward to reproduce on demand.
#
# Returns 0 when every selected package was processed and registered at least one
# linter. Otherwise prints a diagnosis on stdout and returns 1. "Nothing was
# checked" is a failure, not a pass: the whole defect this replaces was a gate
# that could not tell a clean result from an absent one.
# -----------------------------------------------------------------------------
assert_lint_coverage() {
    local selected="$1" finished="$2"; shift 2
    local -a without_linters=("$@")

    if [ "$selected" -eq 0 ]; then
        printf 'no first-party packages were selected, so nothing was linted'
        return 1
    fi
    if [ "$finished" -lt "$selected" ]; then
        printf 'colcon processed %s of %s selected package(s); the rest were skipped' \
            "$finished" "$selected"
        return 1
    fi
    if [ "${#without_linters[@]}" -gt 0 ]; then
        printf '%s of %s package(s) register no lint test at all: %s' \
            "${#without_linters[@]}" "$selected" "${without_linters[*]}"
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# Scenario outcomes, split by phase.
#
# A `launch_test` run answers two independent questions in one exit code:
#
#   cycle     did the cell do the thing? — the active-phase tests, which are the
#             assertions a phase item's acceptance claim actually rests on
#   teardown  did every process exit cleanly? — the `@post_shutdown_test` class
#
# Collapsing both into one status is what makes the scenario steps in CI
# un-gateable. The teardown question currently fails for a reason outside this
# project: a SIGSEGV/abort inside rclpy/rmw destruction, measured at roughly 7.5%
# per process over 40 trials, which across the processes a scenario launches is
# about a one-in-five chance of a spurious teardown failure per run. A gate that
# fails one run in five for an upstream reason is not a gate — it is a coin toss
# that teaches people to re-run until green, which is worse than having no gate.
#
# THE OBVIOUS FIX IS THE WRONG ONE, and it has already been rejected on measured
# grounds. Exempting the offending process would be a guess dressed as a
# discriminator: teardown failures here have landed on at least four distinct
# processes with three distinct exits — `parameter_bridge` (-6), `gz` (-9) and
# `topology_server.py` (1) among them — and CLAUDE.md §2 records the conclusion
# drawn from that set, which is that PROCESS IDENTITY DOES NOT PREDICT IT.
# `topology_server.py` is ours, so even "exempt the upstream processes" has no
# boundary to draw. There is no signature to key on. Widening the allowlist in
# `TestCleanShutdown` would therefore not target the upstream defect at all; it
# would leave an assertion that cannot fail, and the existing one-process one-
# signal `move_group`/-11 allowance is already on the record as the mistake of
# exempting the process that most needed the assertion.
#
# So the split is by PHASE, which is a real property of the run, and never by
# process name or exit code, which are not. The teardown assertion keeps running,
# keeps checking every process, and keeps reporting every bad exit in full — it
# is neither deleted nor exempted. `./scripts/scenario --teardown-advisory`
# merely stops it deciding the exit status, and the caller that asks for that is
# responsible for surfacing what it found. CI does so as an annotation, so a
# first-party teardown regression is visible on the pull request rather than
# buried in a collapsed log.
#
# FAIL-CLOSED IS THE INVARIANT. Anything this cannot confidently classify as a
# teardown failure counts as a cycle failure and gates: an unreadable or absent
# report, a `launch_test` that died before writing one, a failing class this does
# not recognise. A renamed or additional post-shutdown class therefore starts
# gating rather than starts being ignored.
# -----------------------------------------------------------------------------

#: The post-shutdown class every scenario declares. Recognised by name because
#: `launch_test`'s JUnit report records no phase marker of its own — a testcase
#: carries only `classname` and `name`, so the convention is the only handle
#: there is. Keep it in step with tests/scenarios/*.py; a mismatch makes teardown
#: failures gate, which is the safe direction and is asserted in _selftest.sh.
SCENARIO_TEARDOWN_CLASS="TestCleanShutdown"

# scenario_failed_cases <junit-xml>
#
# Prints one tab-separated record per failing or erroring testcase:
#
#     <phase>\t<classname>.<name>\t<summary>
#
# <phase> is `teardown` for the post-shutdown class and `cycle` for everything
# else. <summary> is the last line of the failure text, which for a unittest
# assertion is the `AssertionError: ...` line carrying the process and exit code.
#
# Returns 0 when the report was readable, 1 when it was not. Emptiness is a valid
# readable answer and means the report recorded no failure.
scenario_failed_cases() {
    local xml="$1"
    [ -f "$xml" ] || return 1

    # `launch_test` writes the whole report on one line, so split it into one
    # record per testcase first. The literal newline in the replacement is the
    # portable spelling: BSD sed on the macOS host rejects `\n` there, and this
    # function is driven on the host by scripts/_selftest.sh.
    #
    # `|| [ -n "$record" ]` is load-bearing, not defensive. `launch_test` writes
    # its report with NO trailing newline, so the final chunk — which is where
    # every `<testcase>` lives, the whole document being one line — makes `read`
    # return non-zero and a plain `while read` drops it. The symptom was a report
    # containing a failure being classified as containing none, which fell to the
    # fail-closed branch and gated a run whose cycle had passed. The synthetic
    # fixtures hid it by ending in a newline; junit_report in _selftest.sh no
    # longer does, so this line is covered.
    sed 's/<testcase /\
<testcase /g' "$xml" | while IFS= read -r record || [ -n "$record" ]; do
        case "$record" in
            '<testcase '*) record="${record#<testcase }" ;;
            *) continue ;;
        esac
        # A passing testcase is self-closing and carries neither child element.
        case "$record" in
            *'<failure'* | *'<error'*) ;;
            *) continue ;;
        esac

        # Attribute values in this report are `launch_test`'s own output and
        # contain no escaped quotes, so the delimiters are unambiguous. Read with
        # parameter expansion rather than a regex: the pattern needed to tell
        # `name=` from `classname=` is exactly the kind of quoting that breaks
        # differently between bash 3.2 on the macOS host and bash 5 in the
        # container, and this function has to give the same answer in both.
        local classname name phase summary rest
        rest="${record#classname=\"}"
        classname="${rest%%\"*}"
        rest="${rest#*\"}"
        rest="${rest#* name=\"}"
        name="${rest%%\"*}"

        # Match the class's own name, never the module that qualifies it, so that
        # a scenario module named after the class cannot be mistaken for it.
        case "${classname##*.}" in
            "$SCENARIO_TEARDOWN_CLASS") phase="teardown" ;;
            *) phase="cycle" ;;
        esac

        # Isolate the message attribute BEFORE decoding, or the entity-decoded
        # newlines make the closing tags the last line and every summary reads
        # `" /></testcase>`. Real quotes inside the message are written `&quot;`,
        # so the attribute delimiters are unambiguous at this point and stop
        # being so immediately after.
        case "$record" in
            *'message="'*)
                summary="${record#*message=\"}"
                summary="${summary%%\"*}"
                ;;
            *) summary="" ;;
        esac

        # Decode the entities and keep the last non-empty line, which is the
        # assertion itself rather than the traceback leading to it.
        if [ -n "$summary" ]; then
            summary="$(
                printf '%s\n' "$summary" \
                    | sed -e 's/&#10;/\
/g' -e 's/&quot;/"/g' -e 's/&lt;/</g' -e 's/&gt;/>/g' -e 's/&amp;/\&/g' \
                    | grep -v '^[[:space:]]*$' \
                    | tail -n 1
            )"
        fi
        [ -n "$summary" ] || summary="(no failure message recorded)"

        printf '%s\t%s.%s\t%s\n' "$phase" "$classname" "$name" "$summary"
    done
}

# scenario_verdict <junit-xml> <teardown-policy>
#
# The judgement CI and ./scripts/scenario both need, separated from the
# `launch_test` plumbing so scripts/_selftest.sh can drive it with synthetic
# reports — the states that matter here are precisely the ones that are expensive
# to reproduce on demand, each costing a full simulated bring-up.
#
# <teardown-policy> is `blocking` or `advisory`. Returns 0 when the run counts as
# a pass under that policy, 1 otherwise. Called only when `launch_test` itself
# failed, so "no failures recorded" means the report does not explain the failure
# and is treated as a cycle failure.
scenario_verdict() {
    local xml="$1" policy="$2"
    local cases cycle_failures teardown_failures tab
    tab="$(printf '\t')"

    if ! cases="$(scenario_failed_cases "$xml")"; then
        printf 'no readable JUnit report at %s — treating as a cycle failure' "$xml"
        return 1
    fi

    # Anchored on the field separator so that a summary mentioning either word
    # cannot be counted as a phase. `grep -c` exits 1 on zero matches, which
    # `set -o pipefail` would otherwise turn into a failed assignment.
    cycle_failures="$(printf '%s\n' "$cases" | grep -c "^cycle${tab}" || true)"
    teardown_failures="$(printf '%s\n' "$cases" | grep -c "^teardown${tab}" || true)"

    if [ "$cycle_failures" -gt 0 ]; then
        printf '%s cycle assertion(s) failed' "$cycle_failures"
        return 1
    fi
    if [ "$teardown_failures" -eq 0 ]; then
        printf 'the run failed but its report records no failing testcase'
        return 1
    fi
    if [ "$policy" != "advisory" ]; then
        printf '%s teardown assertion(s) failed' "$teardown_failures"
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# unpinned_manifest_entries — vcs manifest entries not pinned to a commit SHA.
#
# Prints one "<repo>: <version>" line per offending entry; empty output means
# every entry is pinned. This is the only mechanical guard on ADR-0008, so it
# lives here once and is called by both ./scripts/doctor and the CI supply-chain
# job. It used to be restated in both places as `grep -E '^\s+version:\s*[a-z]'`,
# which is a starts-with-lowercase test rather than a SHA validator and was wrong
# in both directions: a real 40-character SHA beginning with a-f was reported
# unpinned, and a branch named `2.x` passed as pinned. The current entry passed
# only because its SHA happens to begin with a digit.
# -----------------------------------------------------------------------------
unpinned_manifest_entries() {
    local manifest="${1:-${REPO_ROOT}/external/cite.repos}"
    [ -f "$manifest" ] || return 0
    awk '
        # A repository key: indented, ends the line with a colon and nothing else.
        /^[[:space:]]+[^[:space:]#][^:]*:[[:space:]]*$/ {
            entry = $1; sub(/:$/, "", entry); next
        }
        $1 == "version:" {
            value = $2
            gsub(/["\x27]/, "", value)           # strip quoting, if any
            if (value !~ /^[0-9a-fA-F]{40}$/) {
                print (entry == "" ? "?" : entry) ": " (value == "" ? "(empty)" : value)
            }
        }
    ' "$manifest"
}

# -----------------------------------------------------------------------------
# Local patches (ADR-0008) — one implementation, two callers.
#
# ./scripts/bootstrap APPLIES these; ./scripts/doctor AUDITS them. The two must
# agree on what "present" means, and while bootstrap alone decided, it could not
# tell the states apart at all: a failing `git apply --check` meant either
# "already applied", which is success and the reason the check is there, or
# "does not apply", which is a declared modification missing from every build.
# Both printed the same info line and execution continued.
#
# That is not hypothetical. 01-xarm_ros2-gripper-mimic-joints.patch was committed
# and then absent from every build and every measurement taken for hours, while
# bootstrap reported "already applied or does not apply — skipped" each time and
# nothing else in the repository looked at all. The four states below exist so
# that success and total failure can never again print the same sentence.
# -----------------------------------------------------------------------------

# declared_patches [dir] — every patch file, in the order bootstrap applies them.
declared_patches() {
    local dir="${1:-${REPO_ROOT}/external/patches}"
    [ -d "$dir" ] || return 0
    find "$dir" -maxdepth 1 -type f -name '*.patch' 2>/dev/null | sort
}

# patch_target_repo <patch-file> — the `# Repo:` header, or empty if absent.
#
# The header is what binds a patch to a checkout. A patch without one can never
# be applied to anything, so both callers treat empty as a defect in the patch
# rather than as a reason to move on.
patch_target_repo() {
    sed -n 's/^# Repo:[[:space:]]*//p' "$1" | head -1
}

# patch_state <patch-file> <target-dir>
#
# Prints exactly one word. The point of the function is that these are five
# different words rather than one:
#
#   applied     the change is in the checkout. Re-applying it would fail, so
#               bootstrap skips it — this is what makes bootstrap idempotent,
#               and it is a PASS, not a "could not tell".
#   pending     it applies cleanly and is not yet in the checkout.
#   conflict    it neither applies nor is present. A declared modification that
#               cannot reach the build: fatal, never an info line. The usual
#               cause is a version bump that moved the code the patch edits.
#   no-target   the target directory does not exist — external source has not
#               been imported here yet.
#   empty       the target directory exists and is empty. Distinct from
#               no-target on purpose: this is the signature of an import that
#               failed part-way, which is precisely what a broken worktree
#               produced, and it is the state that used to read as "skipped".
patch_state() {
    local patch="$1" target="$2"
    [ -d "$target" ] || { printf 'no-target'; return 0; }
    [ -n "$(ls -A "$target" 2>/dev/null)" ] || { printf 'empty'; return 0; }
    # Reverse-check first. An applied patch fails the forward check, so asking
    # the forward question alone is what conflated success with failure.
    if git -C "$target" apply --reverse --check "$patch" >/dev/null 2>&1; then
        printf 'applied'
    elif git -C "$target" apply --check "$patch" >/dev/null 2>&1; then
        printf 'pending'
    else
        printf 'conflict'
    fi
}

# -----------------------------------------------------------------------------
# git_without_enclosing_repo <command...>
#
# Runs <command> with git's repository discovery stopped at REPO_ROOT.
#
# THE DEFECT THIS EXISTS FOR. A git worktree's `.git` is a FILE holding an
# absolute path to the real gitdir, which lives inside the main checkout —
# outside the directory docker-compose bind-mounts as /workspace. Inside the
# container that path does not exist, so git's upward search finds the pointer,
# fails to open what it names, and aborts *every* git command run anywhere under
# /workspace with
#
#     fatal: not a git repository: /Users/.../.git/worktrees/<name>
#
# `vcs import` hits this in its ref-type probe. It reports the failure, but it
# has already created workspace/src/external/xarm_ros2, so what the build sees is
# an empty directory rather than a missing one. Bootstrap then found no source to
# patch and said "skipped". Three agents independently worked around this by
# cloning the pinned SHA on the host; a workaround everybody reinvents is a
# defect, not a technique.
#
# WHY THIS IS THE FIX AND NOT A DODGE. The import does not need the enclosing
# repository. It clones fresh repositories into workspace/src, and its only
# interest in an outer repository is an accident of git's upward search.
# GIT_CEILING_DIRECTORIES is git's own mechanism for bounding that search, and it
# is applied unconditionally rather than only in worktrees: a branch that fires
# on one machine's directory layout and nowhere else is a branch nobody tests.
#
# Scoped to the one command and to the search *above* REPO_ROOT, so nothing below
# it changes — `git -C <clone> apply` still finds the clone's own .git at once.
# -----------------------------------------------------------------------------
git_without_enclosing_repo() {
    GIT_CEILING_DIRECTORIES="${REPO_ROOT}" "$@"
}

# repo_git_readable — can git open the repository that contains REPO_ROOT?
#
# False in a worktree seen from inside the container, per the block above. Any
# check that needs repository metadata has to ask this first, or it reports the
# absence of an answer as a clean result.
repo_git_readable() {
    git -C "${REPO_ROOT}" rev-parse --git-dir >/dev/null 2>&1
}

host_os() {
    case "$(uname -s)" in
        Linux)  echo linux ;;
        Darwin) echo macos ;;
        *)      echo other ;;
    esac
}

native_ros_available() {
    [ -f "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash" ]
}

# -----------------------------------------------------------------------------
# cite_venv_bin — absolute path to the bin/ of the Python tooling environment.
#
# There are two of them and picking the wrong one fails confusingly. The host
# virtualenv lives at .venv/ inside the repository, which is bind-mounted into
# the container — so inside the container `.venv/bin/python` *exists and is
# executable* while being a macOS binary. Testing `-x` and taking the first hit,
# which is what several scripts used to do, therefore selects a binary that
# cannot run, and the error ("cannot execute binary file") names neither venv.
#
# Inside the container the container's own venv always wins. Outside it, the
# repository venv does.
# -----------------------------------------------------------------------------
cite_venv_bin() {
    local container_venv="${CITE_VENV:-/opt/cite-venv}"
    if in_container && [ -x "${container_venv}/bin/python" ]; then
        printf '%s' "${container_venv}/bin"
        return 0
    fi
    if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
        printf '%s' "${REPO_ROOT}/.venv/bin"
        return 0
    fi
    if [ -x "${container_venv}/bin/python" ]; then
        printf '%s' "${container_venv}/bin"
        return 0
    fi
    return 1
}

cite_python() {
    local bin
    bin="$(cite_venv_bin)" || { command -v python3 || return 1; return 0; }
    printf '%s/python' "$bin"
}

# Every compose invocation is scoped to this checkout's project with an explicit
# `-p`, not left to the COMPOSE_PROJECT_NAME environment variable. Both would work
# for `up` and `run`, but `-p` is the highest-precedence form and does not depend
# on remembering how compose ranks the env var against the `name:` key in the
# file. It is passed here, once, so that no caller can forget it — and `clean
# --all`, which is the command that can destroy another checkout's work, gets the
# scoping by construction rather than by its own care.
compose() {
    if have docker && docker compose version >/dev/null 2>&1; then
        CITE_UID="$(id -u)" CITE_GID="$(id -g)" \
            docker compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
    elif have docker-compose; then
        CITE_UID="$(id -u)" CITE_GID="$(id -g)" \
            docker-compose -p "$COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
    else
        die "Docker Compose not found. Install Docker Desktop (macOS) or docker-compose-plugin (Linux)."
    fi
}

# -----------------------------------------------------------------------------
# require_ros_env <script-name> [args...]
#
# Guarantees that the calling script is running somewhere the ROS stack exists.
# If it is not, the script re-executes itself inside the container and the
# outer invocation ends there.
#
#   CITE_ENV=native  never enter a container; fail if ROS is missing
#   CITE_ENV=docker  always enter the container
#   CITE_ENV=auto    (default) native when possible, container otherwise
# -----------------------------------------------------------------------------
require_ros_env() {
    local script_name="$1"; shift
    local mode="${CITE_ENV:-auto}"

    if in_container; then
        return 0
    fi

    case "$mode" in
        native)
            native_ros_available || die \
                "CITE_ENV=native but /opt/ros/${ROS_DISTRO:-jazzy}/setup.bash was not found.
  Install ROS 2 Jazzy natively, or unset CITE_ENV to use the container."
            return 0
            ;;
        docker) ;;
        auto)
            if native_ros_available; then
                return 0
            fi
            ;;
        *) die "CITE_ENV must be one of: auto, native, docker (got '$mode')" ;;
    esac

    if ! have docker; then
        die "No native ROS 2 installation and no Docker.
  This machine can edit the repository but cannot build or run it.
  Install Docker, or work on a Linux machine with ROS 2 Jazzy.
  See docs/onboarding/getting-started.md."
    fi

    # Warn before a first-run image build. Without this, `./scripts/test` on a
    # machine with no image looks like it has hung for ten minutes.
    if ! docker image inspect cite-digital-twin:dev >/dev/null 2>&1; then
        warn "The container image does not exist yet and must be built first."
        warn "This takes several minutes. Run ./scripts/bootstrap to do it explicitly,"
        warn "or wait while it happens now."
    fi

    info "Not a ROS environment — running '${script_name}' inside the container"
    local service="${CITE_SERVICE:-dev}"
    exec_in_container "$service" "./scripts/${script_name}" "$@"
}

exec_in_container() {
    local service="$1"; shift

    # `compose run` starts a fresh container and inherits nothing from this shell,
    # so any CITE_* setting made on the host has to be handed across explicitly.
    # Without this, a variable set before re-entry silently arrives unset and the
    # branch that depends on it becomes unreachable — which is easy to mistake for
    # the feature simply not working.
    local env_args=() v
    for v in $(compgen -e 2>/dev/null | grep '^CITE_' || true); do
        env_args+=(-e "${v}=${!v}")
    done

    # The DDS domain is decided once, by the outermost invocation, and carried in.
    # `compose run` would pick it up through the compose file's ${ROS_DOMAIN_ID}
    # substitution, but `compose exec` attaches to a container whose environment
    # was fixed when it started — so passing it explicitly is what keeps a shell
    # and the cell it attaches to on the same domain. See cite_domain_id above.
    env_args+=(-e "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}")

    # Captured rather than piped: `grep -q` exits on its first match and SIGPIPEs
    # the producer, which `set -o pipefail` then reports as a failed pipeline. Here
    # the effect was silent — a running container was never reused, and every
    # command started a fresh one instead.
    #
    # Matched on the SERVICE name rather than on a container name. The container
    # names used to be pinned in the compose file (`container_name: cite-dev`),
    # which is a host-global identifier and so collided between checkouts exactly
    # as the volumes did; they are derived from the project now. `--services`
    # asks compose which services are up and is independent of how it chooses to
    # name their containers, so this check cannot drift out of step with that
    # naming again.
    local running
    running="$(compose ps --services --status running 2>/dev/null || true)"
    if grep -qx "$service" <<<"$running"; then
        compose exec -T ${env_args[@]+"${env_args[@]}"} "$service" "$@"
    else
        compose run --rm ${env_args[@]+"${env_args[@]}"} "$service" "$@"
    fi
    exit $?
}

# -----------------------------------------------------------------------------
# first_party_packages — the package names we are responsible for.
#
# workspace/src/external/ holds vcstool-imported third-party source (ADR-0008).
# It has to be *built*, because we depend on it, but its tests are not ours: the
# vendor's copyright, cpplint, flake8 and uncrustify checks fail against their own
# code and tell us nothing about ours. Running them would leave CI permanently red
# for reasons no change of ours could fix, which is how a red build stops meaning
# anything.
#
# Prints one package name per line, sorted. Empty output means there is nothing of
# ours to test yet.
# -----------------------------------------------------------------------------
first_party_packages() {
    local src="${REPO_ROOT}/workspace/src"
    [ -d "$src" ] || return 0
    find "$src" -mindepth 2 -name package.xml -not -path '*/external/*' -print0 2>/dev/null \
        | xargs -0 -r -n1 sed -n 's:.*<name>\([^<]*\)</name>.*:\1:p' \
        | sort -u
}

# -----------------------------------------------------------------------------
# python_trees — the Python trees this repository owns, one absolute path a line.
#
# Both the linter and the host test suite walk exactly these, and they walk the
# same ones deliberately. When the two lists were written out separately at their
# call sites they drifted: `tools/` was linted and tested, `tests/` was neither,
# and three ruff violations plus an entire guard suite sat in the branch with
# nothing collecting or reporting them. A list named once cannot drift from
# itself (P1).
#
# `tests/` holds the simulation scenarios and their guards. The scenarios are not
# collected by pytest — they are named `bringup.py` and `pick_and_place.py`, not
# `test_*.py`, and they need a running simulator — but the guards under
# `tests/scenarios/guards/` are, and they are the reason this path is here.
#
# Only paths that exist are printed, so a checkout part-way through a phase does
# not fail on a directory that has not been created yet.
# -----------------------------------------------------------------------------
python_trees() {
    local tree
    for tree in tools tests; do
        [ -d "${REPO_ROOT}/${tree}" ] && printf '%s\n' "${REPO_ROOT}/${tree}"
    done
    return 0
}

# -----------------------------------------------------------------------------
# source_overlay — source the colcon overlay without tripping `set -u`.
#
# _lib.sh sets `set -euo pipefail`, and colcon's generated setup.bash references
# COLCON_TRACE without a default. Sourcing it directly therefore aborts with
# "COLCON_TRACE: unbound variable" before anything has run — a failure that names
# a colcon internal and says nothing about the command the developer typed.
# -----------------------------------------------------------------------------
source_overlay() {
    local overlay="${REPO_ROOT}/workspace/install/setup.bash"
    [ -f "$overlay" ] || return 1
    set +u
    # shellcheck disable=SC1090  # generated by colcon at build time
    source "$overlay"
    set -u
}

# Guard for anything that must not run against physical hardware by accident.
require_explicit_hardware_opt_in() {
    if [ "${CITE_ALLOW_HARDWARE:-0}" != "1" ]; then
        die "This command can command physical hardware.
  Set CITE_ALLOW_HARDWARE=1 to proceed, and confirm the cell is clear first."
    fi
}
