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

// Where the arm ended up, and which code L4 is given for it (ADR-0037).
//
// The classification decides whether L4 retries a station unattended or stops it
// for an operator, so the rule is tested as a rule rather than only through the
// running server: a simulator cannot be asked to stop an arm at a chosen
// fraction of its path on demand, and a fixture that could would be asserting
// the simulator rather than the policy.
//
// WHAT NO TEST IN THIS REPOSITORY SHOWS, and ADR-0037 decision 8 said otherwise
// until its correction: that a real abort reaches this classifier. The fixture
// that decision names,
// `cite_bringup/test/test_trajectory_constraints_launch.py`, drives
// `FollowJointTrajectory` directly against mock hardware — no `move_group`, no
// skill server — so its abort never enters L3, and the mistracking it injects
// with `disable_commands` leaves the joint state at the trajectory's FIRST
// point, which classifies AT_START. It cannot carry this assertion, and closing
// that gap needs a fixture nobody has built.

#include <cstdint>
#include <limits>
#include <map>
#include <string>
#include <vector>

#include "gtest/gtest.h"

#include "cite_skills/motion_end.hpp"

namespace
{

using cite_interfaces::msg::ResultCode;
using cite_skills::MotionEnd;
using cite_skills::classify_execution_failure;
using cite_skills::classify_motion_end;
using cite_skills::positions_in_trajectory_order;
using cite_skills::within_tolerance;
using moveit_msgs::msg::MoveItErrorCodes;

//: An arbitrary positive tolerance, in radians, and NOT the model's number.
//:
//: This said it was the model's number until 2026-08-27, and it was a copy of
//: it. Nothing here reads L0, so a test asserting that would have been asserting
//: that two constants agree — and it would have gone on passing after the model
//: changed, which is the opposite of what a P1 guard does.
//:
//: The functions below take the tolerance as an ARGUMENT; what they encode is a
//: rule, and the rule holds at any positive threshold.
//: `TheToleranceHandedInIsTheOneTheAnswerTurnsOn` is what stops the argument
//: being ignored in favour of a constant. That the number the running server
//: uses comes from L0 and from nowhere else is guarded where it can be —
//: `cite_bringup/test/test_plan.py`'s three `ARM_KEYS` tests — because that is
//: the layer the delivery actually happens at.
constexpr double kToleranceRad = 0.01;

const std::vector<double> kStart{0.0, 0.0, 0.0, 0.0, 0.0};
const std::vector<double> kGoal{1.0, -0.5, 0.25, 0.75, -1.0};
//: Neither end: every joint half way along its own travel.
const std::vector<double> kPartWay{0.5, -0.25, 0.125, 0.375, -0.5};

}  // namespace

TEST(MotionEndTest, AnArmThatNeverLeftTheStartIsReportedAsSuch)
{
  // The command did not take effect. Every joint sits inside the tolerance of
  // the trajectory's first point, including one right on the edge of it.
  const std::vector<double> current{0.009, 0.0, -0.005, 0.0, 0.002};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kToleranceRad), MotionEnd::AT_START);
}

TEST(MotionEndTest, AnArmAtTheGoalIsReportedAsArrived)
{
  const std::vector<double> current{1.0, -0.5, 0.25, 0.75, -1.0};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kToleranceRad), MotionEnd::AT_GOAL);
}

TEST(MotionEndTest, AnArmStoppedPartWayIsNeitherEndpoint)
{
  // Half way along. This is the case ADR-0037 exists for: the arm is holding a
  // position no part of the commanded motion asked it to hold.
  const std::vector<double> current{0.5, -0.25, 0.125, 0.375, -0.5};
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kToleranceRad), MotionEnd::PART_WAY);
}

TEST(MotionEndTest, OneMistrackingJointIsEnoughToBePartWay)
{
  // PER JOINT, not a norm. Five joints arrived and one did not, which is exactly
  // the shape a path-tolerance abort leaves behind — and a norm over six joints
  // would let that single large error hide under five zeroes and report the arm
  // as having arrived.
  std::vector<double> current = kGoal;
  current[2] += 0.4;
  EXPECT_EQ(classify_motion_end(current, kStart, kGoal, kToleranceRad), MotionEnd::PART_WAY);
}

TEST(MotionEndTest, JustOutsideToleranceIsPartWayAndJustInsideIsNot)
{
  // The boundary is the arm's own tolerance, so it is worth pinning that the
  // comparison is strict about which side it falls on rather than approximately
  // right. A boundary that drifted would silently move the line between "retry
  // this station" and "stop it for a person".
  std::vector<double> inside = kStart;
  inside[0] = kToleranceRad * 0.5;
  EXPECT_EQ(classify_motion_end(inside, kStart, kGoal, kToleranceRad), MotionEnd::AT_START);

  std::vector<double> outside = kStart;
  outside[0] = kToleranceRad * 2.0;
  EXPECT_EQ(classify_motion_end(outside, kStart, kGoal, kToleranceRad), MotionEnd::PART_WAY);
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
  EXPECT_EQ(classify_motion_end(current, start, goal, kToleranceRad), MotionEnd::AT_GOAL);
}

TEST(MotionEndTest, AnUnreadableArmIsUnknownRatherThanAtTheStart)
{
  // "I could not tell where the arm is" and "the arm did not move" are opposite
  // claims. The caller answers UNKNOWN with MOTION_INTERRUPTED, so folding it
  // into AT_START here would quietly turn every unreadable abort into a retry.
  EXPECT_EQ(classify_motion_end({}, kStart, kGoal, kToleranceRad), MotionEnd::UNKNOWN);
  EXPECT_EQ(
    classify_motion_end({0.0, 0.0}, kStart, kGoal, kToleranceRad), MotionEnd::UNKNOWN);
  EXPECT_EQ(classify_motion_end(kStart, kStart, kGoal, 0.0), MotionEnd::UNKNOWN);
}

TEST(MotionEndTest, ANonFiniteJointIsNotWithinAnyTolerance)
{
  // A NaN compares false against everything, so an unguarded comparison would
  // report "not within tolerance" for the goal and for the start, and land on
  // PART_WAY — an inference drawn from a reading that does not exist.
  const std::vector<double> broken{std::numeric_limits<double>::quiet_NaN(), 0.0};
  const std::vector<double> zeros{0.0, 0.0};
  EXPECT_FALSE(within_tolerance(broken, zeros, kToleranceRad));
  EXPECT_FALSE(within_tolerance(zeros, broken, kToleranceRad));
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

// --- The code L4 acts on, and the two axes that decide it (ADR-0037) ---------
//
// WHAT THESE DO NOT SHOW, said first because ADR-0037 decision 8 got it wrong.
// They do not show that a real abort reaches this function. Nothing in this
// repository does: the fixture decision 8 names,
// `cite_bringup/test/test_trajectory_constraints_launch.py`, drives
// `FollowJointTrajectory` directly against `mock_components/GenericSystem` — no
// `move_group`, no skill server — so the abort it produces never enters L3 at
// all, and its `disable_commands` injection freezes the joint state at the
// trajectory's FIRST point, which is AT_START and therefore the one answer that
// is not MOTION_INTERRUPTED. See that ADR's correction.
//
// What they do show is every row of the decision itself, which was reachable by
// no test at all while it was a private method of the server.

TEST(ExecutionFailureTest, MoveItsOwnTimeoutIsReportedAsATimeoutAndNotAsAnInterruption)
{
  // ADR-0037 decision 4. `TIMED_OUT` survives MoveIt's funnels intact, and
  // `ResultCode::TIMEOUT` already has its own policy row. Collapsing it into
  // `EXECUTION_FAILED` is what `execute_plan` used to do.
  const auto answer = classify_execution_failure(
    MoveItErrorCodes::TIMED_OUT, kPartWay, kStart, kGoal, kToleranceRad);
  EXPECT_EQ(answer.code, ResultCode::TIMEOUT);
  EXPECT_FALSE(answer.detail.empty());
}

TEST(ExecutionFailureTest, APreemptedExecutionIsReportedAsCancelled)
{
  const auto answer = classify_execution_failure(
    MoveItErrorCodes::PREEMPTED, kPartWay, kStart, kGoal, kToleranceRad);
  EXPECT_EQ(answer.code, ResultCode::CANCELLED);
  EXPECT_FALSE(answer.detail.empty());
}

TEST(ExecutionFailureTest, OnlyTheTwoSurvivingCodesCountAsNamedByMoveIt)
{
  // The predicate the server uses to decide whether it is worth reading the arm
  // at all. It has to agree with the classification exactly: a code it called
  // named but the classifier answered from the world state would be classified
  // from three empty vectors, which is UNKNOWN and therefore MOTION_INTERRUPTED
  // — a station blocked for an operator because a predicate drifted.
  using cite_skills::end_is_named_by_moveit;
  EXPECT_TRUE(end_is_named_by_moveit(MoveItErrorCodes::TIMED_OUT));
  EXPECT_TRUE(end_is_named_by_moveit(MoveItErrorCodes::PREEMPTED));
  EXPECT_FALSE(end_is_named_by_moveit(MoveItErrorCodes::CONTROL_FAILED));
  EXPECT_FALSE(end_is_named_by_moveit(MoveItErrorCodes::FAILURE));

  // The agreement itself: the predicate is true exactly when the answer does not
  // depend on where the arm is. An arm AT THE START is what makes this a real
  // check — it is the one endpoint whose code differs from the code an unread arm
  // gets, so a predicate that named too much would show up here.
  for (const int32_t code :
    {MoveItErrorCodes::TIMED_OUT, MoveItErrorCodes::PREEMPTED,
      MoveItErrorCodes::CONTROL_FAILED, MoveItErrorCodes::FAILURE})
  {
    const bool same_without_the_arm =
      classify_execution_failure(code, kStart, kStart, kGoal, kToleranceRad).code ==
      classify_execution_failure(code, {}, {}, {}, kToleranceRad).code;
    EXPECT_EQ(end_is_named_by_moveit(code), same_without_the_arm)
      << "code " << code << ": the predicate and the classification disagree about whether "
      "the arm has to be read";
  }
}

TEST(ExecutionFailureTest, TheNamedCodeWinsOverTheWorldStateTest)
{
  // THE PRECEDENCE ADR-0037 REQUIRES THE IMPLEMENTATION TO STATE AND TEST. Both
  // calls above pass an arm standing MID-PATH, which on the world-state axis
  // alone is MOTION_INTERRUPTED. It is not reported as one, because
  // MOTION_INTERRUPTED is defined as "why it stopped is not established" and
  // these two establish it.
  ASSERT_EQ(classify_motion_end(kPartWay, kStart, kGoal, kToleranceRad), MotionEnd::PART_WAY);
  for (const int32_t named : {MoveItErrorCodes::TIMED_OUT, MoveItErrorCodes::PREEMPTED}) {
    EXPECT_NE(
      classify_execution_failure(named, kPartWay, kStart, kGoal, kToleranceRad).code,
      ResultCode::MOTION_INTERRUPTED)
      << "MoveIt named the reason and it was answered with the code that means nothing "
      "named it";
  }
}

TEST(ExecutionFailureTest, AnArmStoppedPartWayIsTheOneCodeThatIsNeverRetried)
{
  // `CONTROL_FAILED` is what every abort that is not one of the two above
  // arrives as, so it is the value the world-state axis actually answers for.
  const auto answer = classify_execution_failure(
    MoveItErrorCodes::CONTROL_FAILED, kPartWay, kStart, kGoal, kToleranceRad);
  EXPECT_EQ(answer.code, ResultCode::MOTION_INTERRUPTED);
  // The MoveIt code is carried in the prose, which nothing parses — it is there
  // for the person reading the log, and `ResultCode.msg` says as much of the
  // field.
  EXPECT_NE(answer.detail.find("-4"), std::string::npos);
}

TEST(ExecutionFailureTest, BothEndpointsAreExecutionFailedAndSayWhichEndTheyAre)
{
  // ADR-0037's decision 2 narrowed `EXECUTION_FAILED` to the start-side case and
  // left the goal-side one unassigned; the ADR's correction assigns both. The
  // shared answer is deliberate — at either endpoint the arm is somewhere the
  // next attempt can be planned from — and the two are told apart in the prose
  // rather than in the code.
  const auto never_moved = classify_execution_failure(
    MoveItErrorCodes::CONTROL_FAILED, kStart, kStart, kGoal, kToleranceRad);
  const auto arrived = classify_execution_failure(
    MoveItErrorCodes::CONTROL_FAILED, kGoal, kStart, kGoal, kToleranceRad);

  EXPECT_EQ(never_moved.code, ResultCode::EXECUTION_FAILED);
  EXPECT_EQ(arrived.code, ResultCode::EXECUTION_FAILED);
  EXPECT_NE(never_moved.detail, arrived.detail)
    << "the two endpoint cases are indistinguishable in the log as well as in the code";
}

TEST(ExecutionFailureTest, AnArmThatCouldNotBeReadGetsTheUnreassuringAnswer)
{
  // An empty `current` is what the server produces when the joint state could
  // not be read, or when a joint the trajectory names is not in the model. "I
  // could not tell where the arm is" must not be answered with "it is fine".
  const auto answer = classify_execution_failure(
    MoveItErrorCodes::CONTROL_FAILED, {}, kStart, kGoal, kToleranceRad);
  EXPECT_EQ(answer.code, ResultCode::MOTION_INTERRUPTED);
}

TEST(ExecutionFailureTest, TheToleranceHandedInIsTheOneTheAnswerTurnsOn)
{
  // P1's half of this: the threshold is a PARAMETER, carried from the same L0
  // `constraints:` block the controller is configured from (ADR-0036), and not a
  // constant compiled in beside the rule. A test that only ever passed one
  // tolerance would pass just as happily against a hard-coded one.
  std::vector<double> just_off = kStart;
  just_off[0] = 0.05;

  EXPECT_EQ(
    classify_execution_failure(
      MoveItErrorCodes::CONTROL_FAILED, just_off, kStart, kGoal, 0.01).code,
    ResultCode::MOTION_INTERRUPTED);
  EXPECT_EQ(
    classify_execution_failure(
      MoveItErrorCodes::CONTROL_FAILED, just_off, kStart, kGoal, 0.1).code,
    ResultCode::EXECUTION_FAILED)
    << "the same arm at the same place classified the same way under a tolerance ten times "
    "wider, so the number handed in is not the one being used";
}

TEST(ExecutionFailureTest, ADegenerateOnePointTrajectoryIsNotTheHarshestAnswer)
{
  // A trajectory whose only point is where the arm already is. The server hands
  // `front()` and `back()` in as start and goal, which are the same point here,
  // and the goal-first rule answers AT_GOAL. Before this, the server required
  // two points and a one-point trajectory produced UNKNOWN -> MOTION_INTERRUPTED
  // -> ESCALATE: the harshest answer in the policy, for the motion least able to
  // have gone wrong.
  EXPECT_EQ(
    classify_execution_failure(
      MoveItErrorCodes::CONTROL_FAILED, kStart, kStart, kStart, kToleranceRad).code,
    ResultCode::EXECUTION_FAILED);
}

// --- Reading the arm by the names the trajectory carries ---------------------

TEST(PositionsInTrajectoryOrderTest, PositionsComeBackInTheTrajectorysOrderNotTheModels)
{
  // The defect this exists to prevent is not a missing answer, it is a
  // confidently wrong one: a planning group whose variable order differs from
  // the trajectory's `joint_names` would have joint 1 compared against joint 3
  // and the arm declared to be somewhere it is not.
  const std::map<std::string, double> model{{"j1", 1.0}, {"j2", 2.0}, {"j3", 3.0}};
  const auto lookup = [&model](const std::string & name, double & out) {
      const auto entry = model.find(name);
      if (entry == model.end()) {
        return false;
      }
      out = entry->second;
      return true;
    };

  const std::vector<std::string> names{"j3", "j1", "j2"};
  EXPECT_EQ(
    positions_in_trajectory_order(names, lookup), (std::vector<double>{3.0, 1.0, 2.0}));
}

TEST(PositionsInTrajectoryOrderTest, OneUnreadableJointEmptiesTheWholeAnswer)
{
  // A partial vector would be compared element-wise against a full one and the
  // classifier would be judging a different arm. Empty is what `MotionEnd`
  // reads as UNKNOWN, which is the honest answer.
  const auto lookup = [](const std::string & name, double & out) {
      out = 0.0;
      return name != "j2";
    };
  EXPECT_TRUE(positions_in_trajectory_order({"j1", "j2", "j3"}, lookup).empty());
  EXPECT_EQ(positions_in_trajectory_order({"j1", "j3"}, lookup).size(), 2u);
}
