#!/usr/bin/env bash
# Q1.4, the other half: does a CONTAINER boundary keep two Gazebo transports apart?
#
# gz_crossing.py answers the one-container case. This answers the case the PAIR
# runs actually used -- two containers on one host, on the same compose network,
# with no GZ_PARTITION set anywhere. The PAIR records show one clean statistics
# stream per side, which is suggestive; a publisher count is evidence.
#
# Each side starts a bare `gz sim` on the generated world, waits for its own
# statistics topic, and then asks `gz topic --info` how many publishers that topic
# has. One means the boundary holds. Two means it does not.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/../../../.." && pwd)"
RAW="${REPO_ROOT}/docs/measurements/2026-08-28-second-world-cost/raw"
WORLD=/workspace/workspace/src/cite_generated/worlds/cell_a.sdf

probe_cmd='export GZ_SIM_SYSTEM_PLUGIN_PATH=/opt/ros/jazzy/lib:${GZ_SIM_SYSTEM_PLUGIN_PATH:-};
gz sim -s -r -v 1 '"${WORLD}"' >/tmp/gz.log 2>&1 &
for i in $(seq 1 60); do gz topic --list 2>/dev/null | grep -q /world/cell_a/stats && break; sleep 1; done
sleep 25
echo "HOSTNAME=$(hostname)"
echo "GZ_PARTITION=${GZ_PARTITION:-<unset>}"
gz topic --info -t /world/cell_a/stats
gz topic --info -t /cite/cell_a/conveyor_1/command
kill %1 2>/dev/null; wait 2>/dev/null'

cd "$REPO_ROOT" || exit 1
ROS_DOMAIN_ID=41 ./scripts/enter dev bash -lc "$probe_cmd" > "${RAW}/gz_containers_A.txt" 2>&1 &
pid_a=$!
ROS_DOMAIN_ID=87 ./scripts/enter dev bash -lc "$probe_cmd" > "${RAW}/gz_containers_B.txt" 2>&1 &
pid_b=$!
wait "$pid_a" "$pid_b"
cat "${RAW}/gz_containers_A.txt" "${RAW}/gz_containers_B.txt"
