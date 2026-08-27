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

// Approach and retreat geometry. Pure arithmetic, tested without a planner.

#include <gtest/gtest.h>
#include <tf2/LinearMath/Quaternion.h>

#include <cmath>

#include "cite_skills/approach.hpp"

namespace
{

geometry_msgs::msg::Pose make_pose(
  double x, double y, double z, double roll,
  double pitch, double yaw)
{
  geometry_msgs::msg::Pose pose;
  pose.position.x = x;
  pose.position.y = y;
  pose.position.z = z;
  tf2::Quaternion q;
  q.setRPY(roll, pitch, yaw);
  pose.orientation.x = q.x();
  pose.orientation.y = q.y();
  pose.orientation.z = q.z();
  pose.orientation.w = q.w();
  return pose;
}

constexpr double kTolerance = 1e-9;

}  // namespace

TEST(Approach, StandsOffAlongMinusZWhenToolPointsUp)
{
  const auto pose = make_pose(1.0, 2.0, 0.6, 0.0, 0.0, 0.0);
  const auto approach = cite_skills::offset_along_tool_z(pose, 0.1);
  EXPECT_NEAR(approach.position.x, 1.0, kTolerance);
  EXPECT_NEAR(approach.position.y, 2.0, kTolerance);
  EXPECT_NEAR(approach.position.z, 0.5, kTolerance);
}

TEST(Approach, StandsOffAlongTheToolAxisWhenTheToolPointsDown)
{
  // A gripper reaching down onto a table: tool Z points at the table, so the
  // standoff is ABOVE the grasp. Offsetting in world coordinates instead would
  // put it below, inside the table.
  const auto pose = make_pose(1.0, 2.0, 0.6, M_PI, 0.0, 0.0);
  const auto approach = cite_skills::offset_along_tool_z(pose, 0.1);
  EXPECT_NEAR(approach.position.z, 0.7, kTolerance);
}

TEST(Approach, FollowsATiltedToolRatherThanTheWorld)
{
  // Tilted 90 degrees about Y: the tool's Z is the world's +X, so the standoff
  // moves in -X and not at all in Z. This is the case a world-frame offset gets
  // wrong, and it is invisible in a cell where everything happens to be level.
  const auto pose = make_pose(1.0, 0.0, 0.5, 0.0, M_PI / 2.0, 0.0);
  const auto approach = cite_skills::offset_along_tool_z(pose, 0.2);
  EXPECT_NEAR(approach.position.x, 0.8, 1e-9);
  EXPECT_NEAR(approach.position.z, 0.5, 1e-9);
}

TEST(Approach, ZeroDistanceIsTheIdentity)
{
  const auto pose = make_pose(0.3, -0.4, 0.9, 0.2, -0.3, 1.1);
  const auto approach = cite_skills::offset_along_tool_z(pose, 0.0);
  EXPECT_NEAR(approach.position.x, pose.position.x, kTolerance);
  EXPECT_NEAR(approach.position.y, pose.position.y, kTolerance);
  EXPECT_NEAR(approach.position.z, pose.position.z, kTolerance);
}

TEST(Approach, OrientationIsNeverChanged)
{
  const auto pose = make_pose(0.3, -0.4, 0.9, 0.2, -0.3, 1.1);
  const auto approach = cite_skills::offset_along_tool_z(pose, 0.15);
  EXPECT_DOUBLE_EQ(approach.orientation.x, pose.orientation.x);
  EXPECT_DOUBLE_EQ(approach.orientation.y, pose.orientation.y);
  EXPECT_DOUBLE_EQ(approach.orientation.z, pose.orientation.z);
  EXPECT_DOUBLE_EQ(approach.orientation.w, pose.orientation.w);
}

TEST(Retreat, LiftsInTheWorldFrameWhateverTheToolOrientation)
{
  // After a grasp the safe direction is away from the surface the object rested
  // on, which is up regardless of how the tool is turned.
  const auto pose = make_pose(1.0, 0.0, 0.5, 0.0, M_PI / 2.0, 0.7);
  const auto retreat = cite_skills::offset_along_world_z(pose, 0.12);
  EXPECT_NEAR(retreat.position.x, 1.0, kTolerance);
  EXPECT_NEAR(retreat.position.z, 0.62, kTolerance);
}
