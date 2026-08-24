# syntax=docker/dockerfile:1
# =============================================================================
# CITE Digital Twin — development and CI image
#
# One image, two consumers: a developer's workstation and the CI runner. They
# must be the same image, or "works on my machine" becomes possible again.
#
# Base: ROS 2 Jazzy on Ubuntu 24.04 (Noble) — the Tier-1 platform for the
# Jazzy + Gazebo Harmonic combination locked in CLAUDE.md §6.
# =============================================================================

FROM ros:jazzy-ros-base-noble

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    ROS_DISTRO=jazzy

# Marker used by scripts/_lib.sh to detect that it is already inside the
# container and must not try to re-enter one.
RUN touch /etc/cite-container

# --- Base tooling ------------------------------------------------------------
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git git-lfs curl wget gnupg lsb-release ca-certificates \
      python3-pip python3-venv python3-colcon-common-extensions python3-vcstool \
      python3-rosdep python3-argcomplete \
      clang-format clangd gdb valgrind \
      `# NOTE: linux-tools-common is deliberately absent. It provides only a perf` \
      `# shim that fails against the container's kernel — see docs/reference/toolchain.md.` \
      bash-completion less nano tini \
    && rm -rf /var/lib/apt/lists/*

# --- Gazebo Harmonic ---------------------------------------------------------
# Harmonic ships from the OSRF repository. Added explicitly rather than relying
# on transitive resolution, so the source of the simulator is auditable.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
      -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
      http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
      > /etc/apt/sources.list.d/gazebo-stable.list \
 && apt-get update && apt-get install -y --no-install-recommends gz-harmonic \
 && rm -rf /var/lib/apt/lists/*

# --- ROS 2 stack -------------------------------------------------------------
# Grouped by architectural layer so that a reader can tell why each is here.
# Anything a workspace package needs belongs in that package's package.xml and
# is resolved by rosdep; these are the stack-level dependencies.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      `# L1 description` \
      ros-jazzy-xacro \
      ros-jazzy-urdf \
      ros-jazzy-robot-state-publisher \
      ros-jazzy-joint-state-publisher \
      `# L2 control and hardware abstraction` \
      ros-jazzy-ros2-control \
      ros-jazzy-ros2-controllers \
      ros-jazzy-controller-manager \
      ros-jazzy-gz-ros2-control \
      `# L2 motion planning` \
      ros-jazzy-moveit \
      ros-jazzy-moveit-ros-planning-interface \
      `# L1/L5 simulator bridge` \
      ros-jazzy-ros-gz \
      `# L4 orchestration` \
      ros-jazzy-behaviortree-cpp \
      `# L6 recording` \
      ros-jazzy-rosbag2 \
      ros-jazzy-rosbag2-storage-mcap \
      `# visualization and debugging` \
      ros-jazzy-rviz2 \
      ros-jazzy-tf2-tools \
      ros-jazzy-rqt-common-plugins \
      `# test tooling` \
      ros-jazzy-launch-testing \
      ros-jazzy-launch-testing-ros \
      ros-jazzy-ament-lint-auto \
      ros-jazzy-ament-cmake-clang-format \
    && rm -rf /var/lib/apt/lists/*

# --- osv-scanner (supply-chain CVE scanning) ---------------------------------
# Pinned by version AND checksum. Bumping the version forces updating the hash,
# which makes the upgrade a deliberate act rather than a silent one — the same
# discipline ADR-0008 applies to source dependencies.
ARG OSV_SCANNER_VERSION=v2.5.1
RUN arch="$(dpkg --print-architecture)" \
 && case "$arch" in \
      amd64) osv_sha=f9f25499a2c8cc367b3af45df2ea7eeca7fbccceab9c35079968f4b3652194be ;; \
      arm64) osv_sha=3d0f5aa5a6baa8eb32bcef247388e149ef6030a6634ccae6fa0d62681fb27a6d ;; \
      *) echo "osv-scanner: unsupported architecture '$arch'" >&2; exit 1 ;; \
    esac \
 && curl -fsSL -o /usr/local/bin/osv-scanner \
      "https://github.com/google/osv-scanner/releases/download/${OSV_SCANNER_VERSION}/osv-scanner_linux_${arch}" \
 && echo "${osv_sha}  /usr/local/bin/osv-scanner" | sha256sum -c - \
 && chmod +x /usr/local/bin/osv-scanner \
 && osv-scanner --version

# --- Host-agnostic Python tooling -------------------------------------------
# The L0 layer has no runtime behaviour (charter §5) — it is data, a validator,
# and generators. Keeping it as plain Python in its own virtualenv means it runs
# identically here, on a developer's macOS machine, and in CI.
ENV CITE_VENV=/opt/cite-venv
COPY requirements/tools.txt requirements/dev.txt /tmp/requirements/
RUN python3 -m venv "$CITE_VENV" \
 && "$CITE_VENV/bin/pip" install --no-cache-dir --upgrade pip \
 && "$CITE_VENV/bin/pip" install --no-cache-dir \
      -r /tmp/requirements/tools.txt -r /tmp/requirements/dev.txt \
 && rm -rf /tmp/requirements

# --- Non-root user -----------------------------------------------------------
# UID/GID are build args so that files created in the mounted workspace are
# owned by the host user. Getting this wrong produces root-owned build
# artifacts that the host cannot delete.
ARG USERNAME=cite
ARG USER_UID=1001
ARG USER_GID=1001
RUN groupadd --gid "$USER_GID" "$USERNAME" 2>/dev/null || true \
 && useradd --uid "$USER_UID" --gid "$USER_GID" -m -s /bin/bash "$USERNAME" 2>/dev/null || true \
 && apt-get update && apt-get install -y --no-install-recommends sudo \
 && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME" \
 && chmod 0440 "/etc/sudoers.d/$USERNAME" \
 && rm -rf /var/lib/apt/lists/*

RUN rosdep update --rosdistro "$ROS_DISTRO" || true

COPY infra/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER $USERNAME
WORKDIR /workspace

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
