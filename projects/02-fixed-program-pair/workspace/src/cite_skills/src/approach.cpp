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

#include "cite_skills/approach.hpp"

#include <tf2/LinearMath/Matrix3x3.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Vector3.h>

namespace cite_skills
{

geometry_msgs::msg::Pose offset_along_tool_z(
  const geometry_msgs::msg::Pose & pose, double distance_m)
{
  tf2::Quaternion orientation(
    pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w);
  orientation.normalize();

  // The tool's own Z in the pose's frame. Standing off means moving back along
  // it, so the offset is negative.
  const tf2::Matrix3x3 rotation(orientation);
  const tf2::Vector3 tool_z(rotation[0][2], rotation[1][2], rotation[2][2]);

  geometry_msgs::msg::Pose result = pose;
  result.position.x -= tool_z.x() * distance_m;
  result.position.y -= tool_z.y() * distance_m;
  result.position.z -= tool_z.z() * distance_m;
  return result;
}

geometry_msgs::msg::Pose offset_along_world_z(
  const geometry_msgs::msg::Pose & pose, double distance_m)
{
  geometry_msgs::msg::Pose result = pose;
  result.position.z += distance_m;
  return result;
}

}  // namespace cite_skills
