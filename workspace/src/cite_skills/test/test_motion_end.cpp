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

// Where the arm ended up, relative to the trajectory it was given (ADR-0037).
//
// The classification decides whether L4 retries a station unattended or stops it
// for an operator, so the rule is tested as a rule rather than only through the
// running server. What a `launch_testing` fixture can show is that a real abort
// reaches the real classifier; what it cannot show is the boundary behaviour
// below, because a simulator cannot be asked to stop an arm at a chosen fraction
// of its path on demand.

#include <limits>
#include <vector>

#include "gtest/gtest.h"

#include "cite_skills/motion_end.hpp"

namespace
{

using cite_skills::MotionEnd;
using cite_skills::classify_motion_end;
using cite_skills::within_tolerance;

//: The arm's own goal tolerance, in radians, as the cell declares it in L0 and
//: as the generated controller configuration is written with. Named rather than
//: inlined so that a reader can see this is the model's number and not one
//: chosen to make a test pass.
constexpr double kGoalToleranceRad = 0.01;

const std::vector<double> kStart{0.0, 0.0, 0.0, 0.0, 0.0};
const std::vector<double> kGoal{1.0, -0.5, 0.25, 0.75, -1.0};

}  // namespace

TEST(MotionEndTest, AnArmThatNeverLeftTheStartIsReportedAsSuch)
{
  // The command did not take effect. Every joint sits inside the tolerance of
  // the trajectory's first point, including one right on the edge of it.
  const std::vector<double> current{0.009, 0.0, -0.005, 0.0, 0.002};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kGoalToleranceRad), MotionEnd::AT_START);
}

TEST(MotionEndTest, AnArmAtTheGoalIsReportedAsArrived)
{
  const std::vector<double> current{1.0, -0.5, 0.25, 0.75, -1.0};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kGoalToleranceRad), MotionEnd::AT_GOAL);
}

TEST(MotionEndTest, AnArmStoppedPartWayIsNeitherEndpoint)
{
  // Half way along. This is the case ADR-0037 exists for: the arm is holding a
  // position no part of the commanded motion asked it to hold.
  const std::vector<double> current{0.5, -0.25, 0.125, 0.375, -0.5};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kGoalToleranceRad), MotionEnd::PART_WAY);
}

TEST(MotionEndTest, OneMistrackingJointIsEnoughToBePartWay)
{
  // PER JOINT, not a norm. Five joints arrived and one did not, which is exactly
  // the shape a path-tolerance abort leaves behind — and a norm over six joints
  // would let that single large error hide under five zeroes and report the arm
  // as having arrived.
  std::vector<double> current = kGoal;
  current[2] += 0.4;
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kGoalToleranceRad), MotionEnd::PART_WAY);
}

TEST(MotionEndTest, JustOutsideToleranceIsPartWayAndJustInsideIsNot)
{
  // The boundary is the arm's own tolerance, so it is worth pinning that the
  // comparison is strict about which side it falls on rather than approximately
  // right. A boundary that drifted would silently move the line between "retry
  // this station" and "stop it for a person".
  std::vector<double> inside = kStart;
  inside[0] = kGoalToleranceRad * 0.5;
  EXPECT_EQ(classify_motion_end(inside, kStart, kGoal, kGoalToleranceRad), MotionEnd::AT_START);

  std::vector<double> outside = kStart;
  outside[0] = kGoalToleranceRad * 2.0;
  EXPECT_EQ(classify_motion_end(outside, kStart, kGoal, kGoalToleranceRad), MotionEnd::PART_WAY);
}

TEST(MotionEndTest, AShortTrajectoryWhoseEndsOverlapReportsArrival)
{
  // A trajectory whose start and goal are within one tolerance of each other puts
  // the arm inside BOTH, and the order the two tests are made in is what decides
  // the answer. ADR-0037 names this as a case the classification will meet.
  //
  // Arrival wins, deliberately: it is the more specific of the two true
  // statements, and reporting a completed short motion as one that never began
  // would send an operator looking for a command that did not take effect.
  const std::vector<double> start{0.0, 0.0};
  const std::vector<double> goal{0.001, 0.0};
  const std::vector<double> current{0.0005, 0.0};
  EXPECT_EQ(classify_motion_end(current, start, goal, kGoalToleranceRad), MotionEnd::AT_GOAL);
}

TEST(MotionEndTest, AnUnreadableArmIsUnknownRatherThanAtTheStart)
{
  // "I could not tell where the arm is" and "the arm did not move" are opposite
  // claims. The caller answers UNKNOWN with MOTION_INTERRUPTED, so folding it
  // into AT_START here would quietly turn every unreadable abort into a retry.
  EXPECT_EQ(classify_motion_end({}, kStart, kGoal, kGoalToleranceRad), MotionEnd::UNKNOWN);
  EXPECT_EQ(
    classify_motion_end({0.0, 0.0}, kStart, kGoal, kGoalToleranceRad), MotionEnd::UNKNOWN);
  EXPECT_EQ(classify_motion_end(kStart, kStart, kGoal, 0.0), MotionEnd::UNKNOWN);
}

TEST(MotionEndTest, ANonFiniteJointIsNotWithinAnyTolerance)
{
  // A NaN compares false against everything, so an unguarded comparison would
  // report "not within tolerance" for the goal and for the start, and land on
  // PART_WAY — an inference drawn from a reading that does not exist.
  const std::vector<double> broken{std::numeric_limits<double>::quiet_NaN(), 0.0};
  const std::vector<double> zeros{0.0, 0.0};
  EXPECT_FALSE(within_tolerance(broken, zeros, kGoalToleranceRad));
  EXPECT_FALSE(within_tolerance(zeros, broken, kGoalToleranceRad));
}

TEST(MotionEndTest, ANonPositiveToleranceMatchesNothing)
{
  // Mirrors `check_state_tolerance_per_joint`, which skips any variable whose
  // tolerance is not `> 0.0`. A zero tolerance here must not silently mean
  // "everything is within tolerance".
  const std::vector<double> zeros{0.0, 0.0};
  EXPECT_FALSE(within_tolerance(zeros, zeros, 0.0));
  EXPECT_FALSE(within_tolerance(zeros, zeros, -1.0));
  EXPECT_TRUE(within_tolerance(zeros, zeros, 0.01));
}
