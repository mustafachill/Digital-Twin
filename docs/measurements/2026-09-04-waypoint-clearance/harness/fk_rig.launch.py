"""The I12 rig as a launch file, started by `fk_check.py` through `ros2 launch`.

**It is a file rather than a `LaunchService` in a thread, and the shakedown is why.**
`fk_check.py` first ran the launch with `LaunchService.run()` on a daemon thread; every
service came back unadvertised and the report read `rows: 0`. `LaunchService.run` installs
asyncio signal handlers, which only the main thread may do, and the main thread there is
holding the `rclpy` executor. A launch file started as a subprocess is how everything else in
this repository starts a launch, and it puts the signal handling in a process that owns it.

The arm is passed in the environment rather than as a launch argument so that this file has no
declarable surface of its own: it is not a launch anyone is meant to configure, it is
`fk_check.py`'s own rig expressed where `ros2 launch` can reach it.

The launch description itself is `fk_check._launch_description`, which is where the parameter
assembly copied from `workspace/src/cite_skills/test/test_planning_pipeline.py` lives. A second
copy here would be the value-in-two-places defect P1 names.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fk_check  # noqa: E402


def generate_launch_description():
    return fk_check._launch_description(os.environ["CITE_WC_FK_ARM"])
