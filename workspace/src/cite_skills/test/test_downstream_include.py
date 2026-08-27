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

"""Another package has to be able to include this one's headers.

Installing a header and exporting it are different things, and the difference is
invisible from inside the package that owns it. `cite_skills` installed
`observation.hpp` and declared no `ament_export_*` at all, so
`find_package(cite_skills)` succeeded, contributed no include directory, and the
first `#include <cite_skills/observation.hpp>` in another package failed to
compile. Every test in this package kept passing throughout, because they all
reach the header through `target_include_directories(... PRIVATE include)` on the
source tree — the one path a consumer does not have.

It had a consumer waiting. `observation.hpp` holds `pose_is_observed`, the rule
for READING the unobserved-pose convention, beside `mark_pose_unobserved`, the
rule for writing it — one place, so the two cannot drift. L4's `PickAt` needs
exactly that predicate, could not reach it, and settled for testing
`header.frame_id.empty()` on its own, which admits a pose with a frame set and
NaN components and hands it to the planner.

So this test is a consumer. It configures and compiles a throwaway CMake project
that does what a downstream package does — `find_package(cite_skills REQUIRED)`,
`ament_target_dependencies(... cite_skills)`, `#include
<cite_skills/observation.hpp>` — against the INSTALL space. Asserting that the
export variable is set would pass on a path that names a directory the headers
are not in; only compiling proves the header is reachable.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

CONSUMER_CMAKE = """
cmake_minimum_required(VERSION 3.16)
project(cite_skills_consumer_probe CXX)

find_package(ament_cmake REQUIRED)
find_package(cite_skills REQUIRED)
find_package(geometry_msgs REQUIRED)

add_library(consumer_probe consumer.cpp)
ament_target_dependencies(consumer_probe cite_skills geometry_msgs)
"""

# Both halves of the convention, so the test fails if either stops being
# reachable rather than only the one that happens to be listed first.
CONSUMER_SOURCE = """
#include <cite_skills/observation.hpp>

#include <geometry_msgs/msg/pose_stamped.hpp>

bool probe_marks_and_reads_back()
{
  geometry_msgs::msg::PoseStamped pose;
  cite_skills::mark_pose_unobserved(pose);
  // An unobserved pose must read back as unobserved. If this header ever stops
  // agreeing with itself the compile still succeeds, which is fine: what is
  // under test here is reachability, and the semantics have their own gtest.
  return cite_skills::pose_is_observed(pose);
}
"""


@pytest.mark.skipif(shutil.which("cmake") is None, reason="cmake is not on PATH")
def test_a_downstream_package_can_include_the_header(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "CMakeLists.txt").write_text(CONSUMER_CMAKE)
    (source / "consumer.cpp").write_text(CONSUMER_SOURCE)
    build = tmp_path / "build"

    configure = subprocess.run(
        ["cmake", "-S", str(source), "-B", str(build)],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert configure.returncode == 0, (
        "a downstream package cannot even configure against cite_skills:\n"
        f"{configure.stdout}\n{configure.stderr}"
    )

    compile_result = subprocess.run(
        ["cmake", "--build", str(build)],
        capture_output=True,
        text=True,
        env=os.environ,
        check=False,
    )
    assert compile_result.returncode == 0, (
        "a downstream package cannot include <cite_skills/observation.hpp>. "
        "This is what a missing ament_export_include_directories looks like from "
        "the outside:\n"
        f"{compile_result.stdout}\n{compile_result.stderr}"
    )
