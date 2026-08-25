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

compose() {
    if have docker && docker compose version >/dev/null 2>&1; then
        CITE_UID="$(id -u)" CITE_GID="$(id -g)" \
            docker compose -f "$COMPOSE_FILE" "$@"
    elif have docker-compose; then
        CITE_UID="$(id -u)" CITE_GID="$(id -g)" \
            docker-compose -f "$COMPOSE_FILE" "$@"
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
    local running
    running="$(compose ps --status running 2>/dev/null || true)"
    if grep -q "cite-${service}" <<<"$running"; then
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
