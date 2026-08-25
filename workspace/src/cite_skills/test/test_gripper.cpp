// Gripper arithmetic: task-space metres against the drive joint's own units,
// and what a `Pick` closes to when the goal leaves the width unset.

#include <gtest/gtest.h>

#include "cite_skills/gripper.hpp"

namespace
{

//: The values the L0 end-effector type carries for the xArm parallel gripper.
cite_skills::GripperTravel travel()
{
  return cite_skills::GripperTravel{0.0, 0.85, 0.085};
}

constexpr double kTolerance = 1e-9;

}  // namespace

TEST(GripperPosition, FullyOpenIsTheOpenPosition)
{
  EXPECT_NEAR(cite_skills::gripper_position_for(0.085, travel()), 0.0, kTolerance);
}

TEST(GripperPosition, FullyClosedIsTheClosedPosition)
{
  EXPECT_NEAR(cite_skills::gripper_position_for(0.0, travel()), 0.85, kTolerance);
}

TEST(GripperPosition, IsClampedToTheStroke)
{
  // A width wider than the gripper is the gripper's own maximum, not an
  // out-of-range joint command.
  EXPECT_NEAR(cite_skills::gripper_position_for(1.0, travel()), 0.0, kTolerance);
  EXPECT_NEAR(cite_skills::gripper_position_for(-1.0, travel()), 0.85, kTolerance);
}

TEST(GripperWidth, IsTheInverseOfThePositionMapping)
{
  // What makes `reached_width_m` a measurement: the controller reports where the
  // drive joint stopped, and that comes back as an opening in metres.
  for (const double width : {0.0, 0.02, 0.05, 0.085}) {
    const double position = cite_skills::gripper_position_for(width, travel());
    EXPECT_NEAR(cite_skills::gripper_width_for(position, travel()), width, 1e-9);
  }
}

TEST(GripperWidth, ReportsAStallPartWayThroughTheStroke)
{
  // The case that matters: commanded shut, stalled on a 50 mm box. The reached
  // width is the box, not the request.
  const double stalled_at = cite_skills::gripper_position_for(0.05, travel());
  EXPECT_NEAR(cite_skills::gripper_width_for(stalled_at, travel()), 0.05, 1e-9);
}

TEST(GraspWidth, PrefersTheWidthTheGoalAskedFor)
{
  const auto resolved = cite_skills::resolve_grasp_width(0.03, 0.04);
  EXPECT_EQ(resolved.source, cite_skills::GraspWidthSource::Goal);
  EXPECT_NEAR(resolved.width_m, 0.03, kTolerance);
}

TEST(GraspWidth, FallsBackToTheConfiguredDefaultWhenTheGoalLeavesItUnset)
{
  // `Pick.Goal.grasp_width_m` documents "0 means use the object type's default".
  // Zero is a request for a default — never a request to close completely, which
  // is what the code it replaced did to every pick in the system.
  const auto resolved = cite_skills::resolve_grasp_width(0.0, 0.04);
  EXPECT_EQ(resolved.source, cite_skills::GraspWidthSource::Default);
  EXPECT_NEAR(resolved.width_m, 0.04, kTolerance);
}

TEST(GraspWidth, SaysSoWhenNothingSuppliedOne)
{
  // Neither the goal nor configuration knows the object type. The skill still
  // has to do something, but it must be able to tell the caller that the width
  // it used was not resolved from anything.
  const auto resolved = cite_skills::resolve_grasp_width(0.0, 0.0);
  EXPECT_EQ(resolved.source, cite_skills::GraspWidthSource::Unknown);
}

TEST(GraspWidth, TreatsANegativeRequestAsUnset)
{
  const auto resolved = cite_skills::resolve_grasp_width(-0.01, 0.0);
  EXPECT_EQ(resolved.source, cite_skills::GraspWidthSource::Unknown);
}
