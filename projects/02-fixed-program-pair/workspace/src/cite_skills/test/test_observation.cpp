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

// "There is no pose here" has to survive being read by someone who was not
// looking for it. These tests are that reading.

#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#include "cite_skills/observation.hpp"

namespace
{

/// A pose that a consumer would be right to act on.
geometry_msgs::msg::PoseStamped observed_pose()
{
  geometry_msgs::msg::PoseStamped pose;
  pose.header.stamp.sec = 12;
  pose.header.frame_id = "cite_world";
  pose.pose.position.x = 1.6;
  pose.pose.position.y = 0.0;
  pose.pose.position.z = 0.6;
  pose.pose.orientation.w = 1.0;
  return pose;
}

TEST(UnobservedPose, NamesNoFrame)
{
  // The semantic marker, and the one consumers test against — `PickAt` already
  // reads an empty frame as "no observation, use the station's own frame". If
  // this stops being empty the fallback stops firing and a station picks at
  // whatever the numbers happen to be.
  auto pose = observed_pose();
  cite_skills::mark_pose_unobserved(pose);
  EXPECT_TRUE(pose.header.frame_id.empty());
}

TEST(UnobservedPose, IsNotDated)
{
  // A header whose frame is unset is not a header. A stamp on it would date an
  // observation that was never made.
  auto pose = observed_pose();
  cite_skills::mark_pose_unobserved(pose);
  EXPECT_EQ(pose.header.stamp.sec, 0);
  EXPECT_EQ(pose.header.stamp.nanosec, 0u);
}

TEST(UnobservedPose, CannotBeMistakenForTheOrigin)
{
  // THE FAILURE THIS EXISTS TO PREVENT. Zeroing the numbers would leave a pose
  // that is a real place the moment anything stamps a frame onto it, and this
  // repository has already had to remove one field that read as a measurement
  // because it was permanently 0.0. NaN cannot be planned to.
  auto pose = observed_pose();
  cite_skills::mark_pose_unobserved(pose);

  EXPECT_TRUE(std::isnan(pose.pose.position.x));
  EXPECT_TRUE(std::isnan(pose.pose.position.y));
  EXPECT_TRUE(std::isnan(pose.pose.position.z));
}

TEST(UnobservedPose, AssertsNoRotationEither)
{
  // An identity quaternion is a rotation — "square to the frame" — and asserting
  // it is exactly the assumption ADR-0029 records as unsafe after a grasp. A
  // beam knows nothing about how the part is turned, so nothing is claimed.
  auto pose = observed_pose();
  cite_skills::mark_pose_unobserved(pose);

  EXPECT_TRUE(std::isnan(pose.pose.orientation.x));
  EXPECT_TRUE(std::isnan(pose.pose.orientation.y));
  EXPECT_TRUE(std::isnan(pose.pose.orientation.z));
  EXPECT_TRUE(std::isnan(pose.pose.orientation.w));
  EXPECT_FALSE(pose.pose.orientation.w == 1.0);
}

TEST(PoseIsObserved, IsFalseForAMarkedPose)
{
  auto pose = observed_pose();
  ASSERT_TRUE(cite_skills::pose_is_observed(pose));
  cite_skills::mark_pose_unobserved(pose);
  EXPECT_FALSE(cite_skills::pose_is_observed(pose));
}

TEST(PoseIsObserved, IsFalseForADefaultConstructedPose)
{
  // A `PoseStamped` nobody filled in is not an observation of the origin either.
  // The frame is what says so; the predicate must agree with the convention the
  // rest of the message already uses for `workpiece_id`.
  const geometry_msgs::msg::PoseStamped pose;
  EXPECT_FALSE(cite_skills::pose_is_observed(pose));
}

TEST(PoseIsObserved, IsFalseWhenAComponentIsNotFinite)
{
  // The guard has to work from the reading side too: a pose that acquired a
  // frame somewhere downstream but still carries NaN is not made observed by the
  // frame.
  auto pose = observed_pose();
  pose.pose.position.y = std::numeric_limits<double>::quiet_NaN();
  EXPECT_FALSE(cite_skills::pose_is_observed(pose));

  pose = observed_pose();
  pose.pose.orientation.w = std::numeric_limits<double>::infinity();
  EXPECT_FALSE(cite_skills::pose_is_observed(pose));
}

TEST(PoseIsObserved, IsTrueAtTheOriginOfANamedFrame)
{
  // The predicate must not confuse "unset" with "zero". A part sitting exactly
  // on a station's frame origin is a real, reportable observation, and a
  // detector that could measure it must not have it discarded here.
  geometry_msgs::msg::PoseStamped pose;
  pose.header.frame_id = "cell_a__conveyor_1__outfeed";
  pose.pose.orientation.w = 1.0;
  EXPECT_TRUE(cite_skills::pose_is_observed(pose));
}

}  // namespace
