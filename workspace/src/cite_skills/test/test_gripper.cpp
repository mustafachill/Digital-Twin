// Gripper arithmetic: task-space metres against the drive joint's own units,
// and what a `Pick` closes to when the goal leaves the width unset.

#include <gtest/gtest.h>

#include <cmath>

#include "cite_skills/gripper.hpp"

namespace
{

//: The values the L0 end-effector type carries for the xArm parallel gripper,
//: as the generated bring-up plan delivers them. Kept in step with
//: `model/assets/types/end_effectors/xarm_parallel_gripper.yaml`; the tooling
//: test `tools/tests/test_gripper_linkage.py` pins the same map on the model
//: side, so a change to one that is not made to the other fails there.
cite_skills::GripperTravel travel()
{
  cite_skills::GripperTravel t;
  t.open_position = 0.0;
  t.closed_position = 0.85;
  t.drive_pivot_y_m = 0.035;
  t.finger_offset_y_m = 0.035465;
  t.finger_offset_z_m = 0.042039;
  t.pad_inset_m = 0.026;
  t.goal_tolerance = 0.01;
  return t;
}

constexpr double kTolerance = 1e-9;

//: Openings measured from the simulator, by drive-joint position.
constexpr double kOpenWidth = 0.088930;    // q = 0.000
constexpr double kClosedWidth = 0.001646;  // q = 0.850

//: Where the pads meet the cell's 50 mm reference work-piece. The map predicts
//: 0.4056 rad and the simulator settles at 0.4056 across six runs.
constexpr double kWorkpieceWidth = 0.050;
constexpr double kWorkpieceStall = 0.405605;

//: What the drive joint reaches in FREE AIR when commanded to 45 mm.
//: `GripperActionController` ends the goal as soon as |error| < goal_tolerance,
//: so it stops about 0.008 rad short — which reads back as ~0.85 mm of width
//: that was never there. This constant is the whole reason the predicate needs a
//: threshold; see `GripperHolding` below.
constexpr double kFreeAirSettle = 0.444793;

}  // namespace

// -----------------------------------------------------------------------------
// The width map.
//
// This was a linear interpolation of the stroke and was wrong across the whole
// working range — 85.00 mm claimed fully open against a true 88.93 mm, and
// 45.00 mm claimed at q=0.400 against a true 50.59 mm. On a 50 mm work-piece
// that last error is larger than the entire clearance, so the default grasp
// commanded the pads WIDER than the part and closed on air.
// -----------------------------------------------------------------------------

TEST(GripperWidth, MatchesTheMeasuredStroke)
{
  EXPECT_NEAR(cite_skills::gripper_width_for(0.000, travel()), 0.088930, 5e-6);
  EXPECT_NEAR(cite_skills::gripper_width_for(0.300, travel()), 0.060915, 5e-6);
  EXPECT_NEAR(cite_skills::gripper_width_for(0.400, travel()), 0.050589, 5e-6);
  EXPECT_NEAR(cite_skills::gripper_width_for(0.850, travel()), 0.001646, 5e-6);
}

TEST(GripperWidth, IsNotTheLinearApproximationItReplaced)
{
  // The linear map read 45.00 mm at q=0.400. The mechanism opens to 50.59 mm
  // there. Restated concretely so a "simplification" back to a straight line
  // fails loudly rather than silently reintroducing the original defect.
  const double linear_at_0_4 = 0.085 * (1.0 - 0.400 / 0.85);
  EXPECT_NEAR(linear_at_0_4, 0.045, 1e-4);
  EXPECT_GT(cite_skills::gripper_width_for(0.400, travel()) - linear_at_0_4, 0.004);
}

TEST(GripperPosition, FullyOpenIsTheOpenPosition)
{
  EXPECT_NEAR(cite_skills::gripper_position_for(kOpenWidth, travel()), 0.0, 1e-5);
}

TEST(GripperPosition, FullyClosedIsTheClosedPosition)
{
  EXPECT_NEAR(cite_skills::gripper_position_for(kClosedWidth, travel()), 0.85, 1e-5);
}

TEST(GripperPosition, IsClampedToTheStroke)
{
  // A width wider than the gripper is the gripper's own maximum, not an
  // out-of-range joint command — and never a NaN out of `acos`, which is what an
  // unclamped inverse would hand to the controller.
  EXPECT_NEAR(cite_skills::gripper_position_for(1.0, travel()), 0.0, kTolerance);
  EXPECT_NEAR(cite_skills::gripper_position_for(-1.0, travel()), 0.85, kTolerance);
  EXPECT_FALSE(std::isnan(cite_skills::gripper_position_for(1.0, travel())));
  EXPECT_FALSE(std::isnan(cite_skills::gripper_position_for(-1.0, travel())));
}

TEST(GripperWidth, IsTheInverseOfThePositionMapping)
{
  // What makes `reached_width_m` a measurement: the controller reports where the
  // drive joint stopped, and that comes back as an opening in metres.
  for (const double width : {0.005, 0.02, 0.05, 0.08}) {
    const double position = cite_skills::gripper_position_for(width, travel());
    EXPECT_NEAR(cite_skills::gripper_width_for(position, travel()), width, 1e-9);
  }
}

TEST(GripperWidth, MeetsA50MmPartWhereTheSimulatorMeetsIt)
{
  // Geometry against measurement, agreeing to four decimals. This is the single
  // strongest evidence that the map describes the real mechanism.
  EXPECT_NEAR(
    cite_skills::gripper_position_for(kWorkpieceWidth, travel()), kWorkpieceStall, 1e-4);
  EXPECT_NEAR(
    cite_skills::gripper_width_for(kWorkpieceStall, travel()), kWorkpieceWidth, 1e-5);
}

TEST(GripperWidth, DerivesItsOwnExtremesRatherThanBeingToldThem)
{
  // `max_width_m` used to be configured next to the linkage, as 0.085, and
  // disagreed with it. Derived, the two cannot drift apart (P1).
  EXPECT_NEAR(cite_skills::gripper_max_width_m(travel()), kOpenWidth, 5e-6);
  EXPECT_NEAR(cite_skills::gripper_min_width_m(travel()), kClosedWidth, 5e-6);
}

TEST(GripperWidthTolerance, ScalesWithTheDeclaredGoalTolerance)
{
  // Derived from the controller's own tolerance, never a hardcoded millimetre
  // count: a gripper configured with a looser tolerance widens the margin that
  // `gripper_is_holding` demands, instead of quietly reporting phantom grasps.
  auto loose = travel();
  loose.goal_tolerance = 0.02;
  EXPECT_NEAR(
    cite_skills::gripper_width_tolerance_m(kWorkpieceStall, loose),
    2.0 * cite_skills::gripper_width_tolerance_m(kWorkpieceStall, travel()), 1e-12);
}

TEST(GripperWidthTolerance, VariesAcrossTheStrokeBecauseTheMapIsNotLinear)
{
  const double near_open = cite_skills::gripper_width_tolerance_m(0.05, travel());
  const double mid = cite_skills::gripper_width_tolerance_m(0.45, travel());
  EXPECT_GT(mid, near_open);
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
// Two defects are pinned here, not one.
//
//   1. `holding` was once the controller's `stalled` flag copied straight
//      through. A run on 2026-08-24 lifted a work-piece 0.633 m and reported
//      "closed without stalling" in the same breath.
//   2. The width check that replaced it — `reached_width_m > commanded_width_m`
//      — had NO DISCRIMINATING POWER. Measured under a working mimic coupling,
//      free air commanded to 45.0 mm reported 45.80 mm: the bare `>` is true
//      with nothing between the pads at all. The controller ends its goal the
//      instant |error| < goal_tolerance, so the reported position is
//      systematically short of the command and reads back as phantom width.
//
// The tests below therefore assert the MARGIN, not the sign.
// -----------------------------------------------------------------------------

TEST(GripperHolding, AStallOnTheOpenSideOfTheCommandIsAGrasp)
{
  // Commanded to squeeze to 45 mm, stopped by a 50 mm box at q = 0.4056. The
  // gripper could not reach where it was sent, and what stopped it is between
  // the pads: 5.00 mm of margin against a 2.11 mm threshold.
  EXPECT_TRUE(
    cite_skills::gripper_is_holding({0.045, kWorkpieceStall, true, false}, travel()));
}

TEST(GripperHolding, FreeAirIsNotAGraspEvenThoughItReportsExtraWidth)
{
  // THE REGRESSION. This is the measured free-air case: commanded 45.0 mm, no
  // part, the controller stops 0.008 rad short and reports 45.85 mm. A predicate
  // testing only `reached > commanded` calls this a grasp. This one must not.
  EXPECT_GT(cite_skills::gripper_width_for(kFreeAirSettle, travel()), 0.045);
  EXPECT_FALSE(
    cite_skills::gripper_is_holding({0.045, kFreeAirSettle, true, false}, travel()));
}

TEST(GripperHolding, ReachingTheCommandedWidthIsNotAGrasp)
{
  // Nothing in the way: the gripper arrived exactly where it was told. Whatever
  // else is true, this run learned nothing about an object.
  const double at_command = cite_skills::gripper_position_for(0.045, travel());
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, at_command, false, true}, travel()));
}

TEST(GripperHolding, ReachedGoalAloneDisqualifiesIt)
{
  // The second signal, standing on its own. A gripper that arrived where it was
  // sent is not holding anything, however wide it claims to have stopped — and
  // this needs no threshold, so it cannot be miscalibrated.
  EXPECT_FALSE(
    cite_skills::gripper_is_holding({0.045, kWorkpieceStall, true, true}, travel()));
}

TEST(GripperHolding, ClosingFullyOnNothingIsNotAGrasp)
{
  // Commanded shut, closed shut, controller reports the goal reached. `stalled`
  // is false and so is this.
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.0, 0.85, false, true}, travel()));
}

TEST(GripperHolding, AStallShutOnNothingIsNotAGrasp)
{
  // The case `stalled` alone gets wrong, and the reason a width check is needed
  // at all: the gripper jammed, or fouled its own fingers, and stopped at or
  // past the width it was commanded to. Nothing is between the pads holding it
  // open, so nothing is being held.
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, 0.85, true, false}, travel()));
  const double at_command = cite_skills::gripper_position_for(0.045, travel());
  EXPECT_FALSE(cite_skills::gripper_is_holding({0.045, at_command, true, false}, travel()));
}

TEST(GripperHolding, RequiresAMarginWiderThanTheControllerBias)
{
  // The threshold itself, from both sides. `goal_tolerance` is worth ~1.05 mm of
  // width at this part of the stroke, so the predicate demands ~2.11 mm.
  const double reached = cite_skills::gripper_width_for(kWorkpieceStall, travel());
  const double threshold =
    2.0 * cite_skills::gripper_width_tolerance_m(kWorkpieceStall, travel());
  EXPECT_NEAR(threshold, 0.002105, 5e-6);

  // Just inside the threshold: not a grasp.
  EXPECT_FALSE(cite_skills::gripper_is_holding(
    {reached - 0.9 * threshold, kWorkpieceStall, true, false}, travel()));
  // Just outside it: a grasp.
  EXPECT_TRUE(cite_skills::gripper_is_holding(
    {reached - 1.1 * threshold, kWorkpieceStall, true, false}, travel()));
}

TEST(GripperHolding, WidensItsMarginWhenTheControllerToleranceIsLooser)
{
  // The threshold is derived from the declared tolerance, so a looser controller
  // demands more evidence rather than silently accepting more phantom width.
  auto loose = travel();
  loose.goal_tolerance = 0.05;

  const cite_skills::GripperReport marginal{0.0455, kWorkpieceStall, true, false};
  EXPECT_TRUE(cite_skills::gripper_is_holding(marginal, travel()));
  EXPECT_FALSE(cite_skills::gripper_is_holding(marginal, loose));
}

TEST(GripperHolding, IsDecidedFromFieldsBothPathsCarry)
{
  // P2: the judgement reads only what `control_msgs/GripperCommand.Result`
  // carries — position, stalled, reached_goal — which is identical in simulation
  // and on hardware. Nothing here consults the simulator, and there is no branch
  // that could. Asserted by behaviour rather than by restating the expression,
  // which is what the previous version of this test did: it recomputed the
  // implementation and so would have passed against any implementation at all.
  const cite_skills::GripperReport holding{0.045, kWorkpieceStall, true, false};
  const cite_skills::GripperReport empty{0.045, kFreeAirSettle, true, false};
  EXPECT_TRUE(cite_skills::gripper_is_holding(holding, travel()));
  EXPECT_FALSE(cite_skills::gripper_is_holding(empty, travel()));
}
