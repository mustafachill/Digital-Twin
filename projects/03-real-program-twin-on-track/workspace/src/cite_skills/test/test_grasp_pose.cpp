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

// Turning an object's pose into the tool pose that grasps it.
//
// `Pick.Goal.object_pose` is documented "where the object is" and
// `Place.Goal.target_pose` is where it should end up. Neither is a tool pose, and
// the skill server used to plan both straight to `link_tcp` — which is the
// FINGERTIP plane, not the gripping plane. The pad faces therefore sat proximal
// of the commanded point by `gripper_pad_plane_offset_m`, and the 40-trial
// campaign in `docs/measurements/2026-08-25-grasp-plane-offset/` measured the
// result: 19.3 mm of a 37.5 mm pad face on a 50 mm work-piece, the contact patch
// 15.35 mm above its centre of mass, and a couple that rotated the part past 20
// degrees in 12 of 20 trials. Corrected, 0 of 20, p < 0.0001.
//
// The correction is two pieces of arithmetic that already had unit tests each —
// the offset, and the offset-along-the-tool-axis. What had no test, and what this
// file is for, is their COMPOSITION: the sign, and the axis. Both were free to be
// wrong in a way that looks plausible in a diff and moves the arm 37 mm the wrong
// way in the cell.
//
// Nothing here needs a planner, a simulator, or a controller: the correction is
// planning-side geometry on the end effector's declared dimensions, which is
// exactly why it applies unchanged on hardware (P2).

#include <gtest/gtest.h>

#include <cmath>

#include <geometry_msgs/msg/pose.hpp>

#include "cite_skills/approach.hpp"
#include "cite_skills/gripper.hpp"

namespace
{

//: The xArm parallel gripper as the L0 end-effector type declares it and the
//: generated bring-up plan delivers it.
cite_skills::GripperTravel travel()
{
  cite_skills::GripperTravel t;
  t.open_position = 0.0;
  t.closed_position = 0.85;
  t.drive_pivot_y_m = 0.035;
  t.finger_offset_y_m = 0.035465;
  t.finger_offset_z_m = 0.042039;
  t.pad_inset_m = 0.026;
  t.drive_pivot_z_m = 0.059098;
  t.tip_link_z_m = 0.172;
  t.pad_face_centre_z_m = 0.041003;
  t.goal_tolerance = 0.01;
  return t;
}

//: The default grasp width the end-effector type declares, and where a 50 mm
//: part actually stops the jaws.
constexpr double kDefaultGraspWidth = 0.045;
constexpr double kWorkpieceStall = 0.405605;

//: A 50 mm cube resting on a surface: its centre is half its height up.
constexpr double kWorkpieceCentreHeight = 0.025;

/// The correction the skill server applies, written once here so that a test
/// asserting the sign cannot be satisfied by restating the implementation.
geometry_msgs::msg::Pose tool_pose_for(
  const geometry_msgs::msg::Pose & object, double drive_position)
{
  return cite_skills::offset_along_tool_z(
    object, -cite_skills::gripper_pad_plane_offset_m(drive_position, travel()));
}

/// A pose with the tool pointing straight down — a half turn about X, which is
/// what both `PickAt` and `PlaceAt` send.
geometry_msgs::msg::Pose pointing_down(double z)
{
  geometry_msgs::msg::Pose pose;
  pose.position.z = z;
  pose.orientation.x = 1.0;
  pose.orientation.w = 0.0;
  return pose;
}

}  // namespace

TEST(GraspPose, PutsTheTipLinkBelowTheObjectNotAboveIt)
{
  // The sign, which is the whole point. `offset_along_tool_z` stands OFF along
  // the tool axis, and the pad plane is proximal of the tip, so the correction is
  // negative — the tip link goes further in. Getting this backwards doubles the
  // error instead of removing it, and reads as a plausible diff.
  const auto object = pointing_down(kWorkpieceCentreHeight);
  const auto tool = tool_pose_for(
    object, cite_skills::gripper_position_for(kDefaultGraspWidth, travel()));

  EXPECT_LT(tool.position.z, object.position.z);
  EXPECT_NEAR(object.position.z - tool.position.z, 0.018581, 5e-6);
}

TEST(GraspPose, LeavesTheOrientationAndTheHorizontalPlaceAlone)
{
  auto object = pointing_down(kWorkpieceCentreHeight);
  object.position.x = 0.4;
  object.position.y = -0.2;
  const auto tool = tool_pose_for(object, kWorkpieceStall);

  EXPECT_DOUBLE_EQ(tool.position.x, object.position.x);
  EXPECT_DOUBLE_EQ(tool.position.y, object.position.y);
  EXPECT_DOUBLE_EQ(tool.orientation.x, object.orientation.x);
  EXPECT_DOUBLE_EQ(tool.orientation.w, object.orientation.w);
}

TEST(GraspPose, PutsThePadFaceOnTheWorkpiecesCentreOfMass)
{
  // End to end, in the campaign's own terms. Command the correction for the
  // 45 mm default, then ask where the pad face actually ends up once a 50 mm part
  // has stopped the jaws at 0.4056 rad.
  const auto object = pointing_down(kWorkpieceCentreHeight);
  const auto tool = tool_pose_for(
    object, cite_skills::gripper_position_for(kDefaultGraspWidth, travel()));

  const double pad_centre =
    tool.position.z + cite_skills::gripper_pad_plane_offset_m(kWorkpieceStall, travel());
  // Within a millimetre of the part's centre of mass. The residual is the
  // clearance between the commanded width and the part's own — this layer cannot
  // remove it, because L0 records no work-piece geometry and the goal carries
  // none. Against the 24.2 mm being corrected it is not the term that matters.
  EXPECT_NEAR(pad_centre, kWorkpieceCentreHeight, 0.001);
  EXPECT_GT(pad_centre, kWorkpieceCentreHeight);
}

TEST(GraspPose, IsTheDefectTheCampaignMeasuredWhenTheCorrectionIsOmitted)
{
  // The uncorrected case, kept as a test so the number this fix removes is
  // written down rather than remembered. Planning the tip link straight to the
  // object's pose leaves the pad face 19.3 mm above it, and `PickAt`'s
  // hand-written 30 mm tool height added a further 5.0 mm — the 24.2 mm the
  // campaign measured against 24.4 mm observed.
  const double uncorrected =
    cite_skills::gripper_pad_plane_offset_m(kWorkpieceStall, travel());
  EXPECT_NEAR(uncorrected, 0.019277, 5e-6);
  EXPECT_NEAR(uncorrected + (0.030 - kWorkpieceCentreHeight), 0.024277, 5e-6);
}

TEST(GraspPose, TracksTheGripperRatherThanAConstant)
{
  // A wider grasp is a shallower one: the pads slide back up the tool axis as
  // they open, so the tip link has to go further in for a narrow grasp than for a
  // wide one. A correction baked in as one number cannot express that, which is
  // why the deleted `grasp` frame's single 0.172 m was wrong at every width.
  const auto object = pointing_down(kWorkpieceCentreHeight);
  const auto wide = tool_pose_for(object, travel().open_position);
  const auto narrow = tool_pose_for(
    object, cite_skills::gripper_position_for(kDefaultGraspWidth, travel()));

  EXPECT_LT(wide.position.z, narrow.position.z);
  EXPECT_NEAR(narrow.position.z - wide.position.z, 0.011279, 5e-6);
}

TEST(GraspPose, FollowsTheToolAxisRatherThanTheWorldsZ)
{
  // The axis, which is the composition's other free variable. A grasp approached
  // from the side has to be corrected sideways; correcting in world Z would be
  // invisible in this cell, where every grasp happens to point down, and wrong
  // the first time one does not.
  geometry_msgs::msg::Pose sideways;
  // A quarter turn about Y: the tool's +Z now points along the world's +X.
  sideways.orientation.y = std::sin(M_PI / 4.0);
  sideways.orientation.w = std::cos(M_PI / 4.0);

  const auto tool = tool_pose_for(sideways, kWorkpieceStall);
  EXPECT_NEAR(tool.position.x, 0.019277, 5e-6);
  EXPECT_NEAR(tool.position.z, 0.0, 1e-9);
}
