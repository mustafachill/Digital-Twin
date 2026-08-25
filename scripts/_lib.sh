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

    if compose ps --status running 2>/dev/null | grep -q "cite-${service}"; then
        compose exec -T ${env_args[@]+"${env_args[@]}"} "$service" "$@"
    else
        compose run --rm ${env_args[@]+"${env_args[@]}"} "$service" "$@"
    fi
    exit $?
}

# Guard for anything that must not run against physical hardware by accident.
require_explicit_hardware_opt_in() {
    if [ "${CITE_ALLOW_HARDWARE:-0}" != "1" ]; then
        die "This command can command physical hardware.
  Set CITE_ALLOW_HARDWARE=1 to proceed, and confirm the cell is clear first."
    fi
}
