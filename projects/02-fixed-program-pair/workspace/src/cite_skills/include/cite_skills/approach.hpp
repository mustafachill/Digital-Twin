// Copyright 2026 Sam Houston State University
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Approach and retreat geometry.
//
// Separated from the skill server so it can be tested without a planner, a
// simulator, or any waiting. `cross-cutting-testing.md` is explicit about this:
// push tests down, and do not spend the scenario suite on things a unit test
// could have caught.

#ifndef CITE_SKILLS__APPROACH_HPP_
#define CITE_SKILLS__APPROACH_HPP_

#include <geometry_msgs/msg/pose.hpp>

namespace cite_skills
{

/// A pose offset along the target's own -Z axis by `distance_m`.
///
/// The tool approaches along its own approach axis rather than along the world's
/// Z, because a grasp on a tilted surface is still a grasp — offsetting in world
/// coordinates would put the standoff in the wrong direction the moment anything
/// is not level, and that error is invisible in a cell where everything happens
/// to be flat.
geometry_msgs::msg::Pose offset_along_tool_z(
  const geometry_msgs::msg::Pose & pose, double distance_m);

/// A pose lifted straight up in the frame the pose is expressed in.
///
/// Retreat is deliberately a world-frame lift, not a tool-frame one: after a
/// grasp the safe direction is away from the surface the object was resting on,
/// which is up, whatever the tool's orientation happens to be.
geometry_msgs::msg::Pose offset_along_world_z(
  const geometry_msgs::msg::Pose & pose, double distance_m);

}  // namespace cite_skills

#endif  // CITE_SKILLS__APPROACH_HPP_
