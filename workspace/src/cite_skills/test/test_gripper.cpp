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

// -----------------------------------------------------------------------------
// Is it holding anything?
//
// ADR-0022 leaves this as `Grasp`'s own work: "a stall is reported, not
// interpreted. Deciding whether a stall means 'holding the object' or 'closed on
// nothing' is Grasp's job and needs a real width check." These are that check.
//
// The defect they pin: `holding` used to be the controller's `stalled` flag
// copied straight through. A run on 2026-08-24 lifted a work-piece 0.633 m and
// reported "closed without stalling" in the same breath, because the flag alone
// answers a different question from the one the skill is asking.
// -----------------------------------------------------------------------------

TEST(GripperHolding, AStallOnTheOpenSideOfTheCommandIsAGrasp)
{
  // Commanded to squeeze to 45 mm, stopped by a 50 mm box. The gripper could not
  // reach where it was sent, and what stopped it is between the pads.
  EXPECT_TRUE(cite_skills::gripper_is_holding({0.045, 0.050, true, false}));
}

TEST(GripperHolding, ReachingTheCommandedWidthIsNotAGrasp)
{
  // Nothing in the way: the gripper arrived exactly where it was told. Whatever
  // else is true, this run learned nothing about an object.
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, 0.045, false, true}));
}

TEST(GripperHolding, ClosingFullyOnNothingIsNotAGrasp)
{
  // The observed failure, with the numbers it was observed with: commanded shut,
  // closed shut, controller reports the goal reached. `stalled` is false and so
  // is this.
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.0, 0.0, false, true}));
}

TEST(GripperHolding, AStallShutOnNothingIsNotAGrasp)
{
  // The case `stalled` alone gets wrong, and the reason a width check is needed
  // at all: the gripper jammed, or fouled its own fingers, and stopped at or
  // past the width it was commanded to. Nothing is between the pads holding it
  // open, so nothing is being held.
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, 0.0, true, false}));
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, 0.045, true, false}));
}

TEST(GripperHolding, NeedsNoToleranceOfItsOwn)
{
  // The controller only reports a stall once the position error has passed its
  // own `goal_tolerance`, so a stall already carries a margin and a second
  // tolerance here would be a second number to get wrong. What is tested is that
  // the decision turns on the SIGN of the difference and nothing else.
  EXPECT_TRUE(cite_skills::gripper_is_holding({0.045, 0.0451, true, false}));
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, 0.0449, true, false}));
}

TEST(GripperHolding, IsDecidedFromFieldsBothPathsCarry)
{
  // P2: the judgement reads only what `control_msgs/GripperCommand.Result`
  // carries, which is identical in simulation and on hardware. Nothing here
  // consults the simulator, and there is no branch that could.
  const cite_skills::GripperReport report{0.045, 0.050, true, false};
  EXPECT_EQ(cite_skills::gripper_is_holding(report), report.stalled &&
            report.reached_width_m > report.commanded_width_m);
}
