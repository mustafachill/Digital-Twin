# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The one line a side prints when it has finished coming up, and its reader.

ADR-0047 clause 3: a side announces its own readiness **on its own standard
output**, and the pair supervisor's readiness fact is that line arriving on that
side's pipe. This module is the token, stated once and imported by both ends —
the launch graph that emits it and the supervisor that reads it. Two string
literals would be the same defect this whole design is built to avoid, in
miniature.

**Standard output rather than a ready file, and the reason is this repository's
own rig.** The second-world-cost campaign joined its two cells with ready files
and had to `rm -f` them before every run. A stale ready file is a false join: it
reports a side up that was never started this time. A pipe has no state to go
stale, cannot be written by anything except the child that owns it, and needs no
polling interval — a blocking read on it is not a timer.

Nothing here imports `rclpy`, and that is load-bearing rather than incidental:
the supervisor imports this module, and ADR-0047 clause 2 forbids the supervisor
an import graph that reaches a ROS client library. See
`cite_bringup/test/test_pair.py` for the check that makes that a fact rather than
a promise.
"""

from __future__ import annotations

#: The fixed word a ready line begins with.
#:
#: Deliberately not a sentence anything else would print. The supervisor scans
#: every line of a side's output for it, and that output also carries three
#: Gazebo servers' worth of logging, so the token has to be one a log line does
#: not produce by accident. It is uppercase and prefixed for the same reason.
READY_TOKEN = "CITE_SIDE_READY"


def ready_announcement(side: str, zone: str) -> str:
    """Format the one line a side emits when its own gate chain has completed.

    The side is named in the line even though the supervisor already knows which
    child's pipe it is reading. That redundancy is the check: a launch started
    with the wrong `side:=` argument would otherwise announce readiness for a
    side the supervisor believes is the other one, which is precisely the class
    of error the two isolations exist to prevent and the one thing the supervisor
    is positioned to catch for free.
    """
    return f"{READY_TOKEN} side={side} zone={zone}"


def announced_side(line: str) -> str | None:
    """Return the side named by a ready line, or ``None`` if this is not one.

    Substring rather than prefix matching, because `launch` prefixes what it logs
    — the emitter's line reaches the pipe as `[INFO] [launch.user]: CITE_SIDE_READY
    side=plant zone=cell_a`. Matching on the token rather than on the start of the
    line keeps this reader independent of that formatting, which is upstream's and
    not ours.
    """
    if READY_TOKEN not in line:
        return None
    for field in line.split():
        if field.startswith("side="):
            return field[len("side="):]
    return None
