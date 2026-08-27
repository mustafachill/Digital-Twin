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

// The rule from ADR-0026, tested as what it is: a sequence.
//
// `pick_and_place` failed because a 6-DOF pose goal on a 5-DOF arm is satisfied
// by random draws that are almost never reachable. The fix is to solve IK on the
// exact pose and plan to the joint configuration — and, because a joint goal
// commits to one IK branch, to try more than one seed before reporting failure.
// These tests pin that sequence, and they pin the distinction between "the arm
// cannot reach this" and "the arm cannot get there", which one shared message
// used to hide.

#include <gtest/gtest.h>

#include <vector>

#include "cite_skills/pose_goal.hpp"

namespace
{

using cite_skills::PoseGoalAttempts;
using cite_skills::PoseGoalFailure;
using cite_skills::combined_failure;
using cite_skills::fallback_is_allowed;
using cite_skills::plan_to_pose;

const auto kNeverCancelled = [] {return false;};

}  // namespace

TEST(PoseGoal, PlansFromTheFirstSeedWhenItSolves)
{
  std::vector<int> seeds;
  int plans = 0;
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    8, [&](int seed) {seeds.push_back(seed); return true;},
    [&] {++plans; return true;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::None);
  // The current state is seed 0 and it is tried first: the branch nearest where
  // the arm already stands is the one an operator expects it to take.
  ASSERT_EQ(seeds.size(), 1u);
  EXPECT_EQ(seeds.front(), 0);
  EXPECT_EQ(plans, 1);
  EXPECT_EQ(attempts.seeds_tried, 1);
  EXPECT_EQ(attempts.branches_planned, 1);
}

TEST(PoseGoal, TriesFurtherSeedsWhenIkFails)
{
  std::vector<int> seeds;
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    8,
    [&](int seed) {
      seeds.push_back(seed);
      return seed == 3;  // only the fourth seed finds a solution
    },
    [] {return true;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::None);
  EXPECT_EQ(seeds, (std::vector<int>{0, 1, 2, 3}));
  EXPECT_EQ(attempts.branches_planned, 1);
}

TEST(PoseGoal, TriesAnotherBranchWhenTheFirstOneCannotBePlannedTo)
{
  // The cost of a joint-space goal: it names ONE IK branch, and that branch may
  // have no collision-free path even though another does. Giving up after the
  // first branch would report a reachable pose as unreachable.
  int plans = 0;
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    8, [](int) {return true;}, [&] {return ++plans == 3;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::None);
  EXPECT_EQ(plans, 3);
  EXPECT_EQ(attempts.seeds_tried, 3);
  EXPECT_EQ(attempts.branches_planned, 3);
}

TEST(PoseGoal, ReportsUnreachableOnlyWhenNoSeedEverSolved)
{
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    5, [](int) {return false;}, [] {return true;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::NoIkSolution);
  EXPECT_EQ(attempts.seeds_tried, 5);
  EXPECT_EQ(attempts.branches_planned, 0);
}

TEST(PoseGoal, ReportsAPlanningFailureWhenIkSolvedButNothingCouldBePlanned)
{
  // Distinct from the case above on purpose. One is a reachability failure and
  // the other is a path failure; they need different recoveries, and reporting
  // both as "no collision-free path was found" is what sent three separate
  // investigations of this bug to the wrong place.
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    4, [](int) {return true;}, [] {return false;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::NoPlan);
  EXPECT_EQ(attempts.seeds_tried, 4);
  EXPECT_EQ(attempts.branches_planned, 4);
}

TEST(PoseGoal, StopsAtOnceWhenCancelled)
{
  int ik_calls = 0;
  int plans = 0;

  const auto failure = plan_to_pose(
    8, [&](int) {++ik_calls; return true;}, [&] {++plans; return false;},
    [] {return true;}, nullptr);

  EXPECT_EQ(failure, PoseGoalFailure::Cancelled);
  // Cancelled before anything was attempted: a cancelled skill must not keep
  // searching for a motion nobody is waiting for.
  EXPECT_EQ(ik_calls, 0);
  EXPECT_EQ(plans, 0);
}

TEST(PoseGoal, StopsBetweenIkAndPlanningWhenCancelledInBetween)
{
  int ik_calls = 0;
  int plans = 0;
  bool cancelled = false;

  const auto failure = plan_to_pose(
    8,
    [&](int) {
      ++ik_calls;
      cancelled = true;  // the cancel arrives while IK is running
      return true;
    },
    [&] {++plans; return true;}, [&] {return cancelled;}, nullptr);

  EXPECT_EQ(failure, PoseGoalFailure::Cancelled);
  EXPECT_EQ(ik_calls, 1);
  EXPECT_EQ(plans, 0);
}

TEST(PoseGoal, AcceptsANullAttemptsPointer)
{
  const auto failure = plan_to_pose(
    2, [](int) {return false;}, [] {return true;}, kNeverCancelled, nullptr);
  EXPECT_EQ(failure, PoseGoalFailure::NoIkSolution);
}


// --- Two passes, one verdict (ADR-0027) --------------------------------------
//
// A goal is searched for once per planner. The second pass draws its own random
// seeds, so it can answer a different question from the first one's — and the
// answers are not interchangeable: L4 ESCALATEs UNREACHABLE and retries
// PLANNING_FAILED, so letting the second pass overwrite the first's diagnosis
// spends an operator's attention on a goal that was merely blocked.

TEST(PoseGoalTwoPass, TheSecondPassMayNotDowngradeTheFirstsDiagnosis)
{
  // Pass 1 proved IK has a solution and no path to it was found. Pass 2's
  // different seeds all miss. The answer is still that the pose is reachable.
  EXPECT_EQ(
    combined_failure(PoseGoalFailure::NoPlan, PoseGoalFailure::NoIkSolution),
    PoseGoalFailure::NoPlan);
}

TEST(PoseGoalTwoPass, TheSecondPassMayImproveTheVerdict)
{
  EXPECT_EQ(
    combined_failure(PoseGoalFailure::NoPlan, PoseGoalFailure::None),
    PoseGoalFailure::None);
  // A cancel during the second pass is news, not a downgrade: the goal was
  // called off and saying anything else about it would be wrong.
  EXPECT_EQ(
    combined_failure(PoseGoalFailure::NoPlan, PoseGoalFailure::Cancelled),
    PoseGoalFailure::Cancelled);
}

TEST(PoseGoalTwoPass, CountsAccumulateAcrossPasses)
{
  // `plan_to_pose` zeroes what it is given, so the totals an operator reads have
  // to be summed by the caller. Eight seeds tried twice is sixteen, not eight.
  PoseGoalAttempts first;
  first.seeds_tried = 8;
  first.branches_planned = 3;
  PoseGoalAttempts second;
  second.seeds_tried = 8;
  second.branches_planned = 5;

  const auto total = first + second;
  EXPECT_EQ(total.seeds_tried, 16);
  EXPECT_EQ(total.branches_planned, 8);
}

TEST(PoseGoalTwoPass, OnlyAPlanningFailureFallsBack)
{
  EXPECT_TRUE(fallback_is_allowed(PoseGoalFailure::NoPlan, true, false));
  // Reachability is a property of the arm, not of the planner (ADR-0026).
  EXPECT_FALSE(fallback_is_allowed(PoseGoalFailure::NoIkSolution, true, false));
  EXPECT_FALSE(fallback_is_allowed(PoseGoalFailure::Cancelled, true, false));
  EXPECT_FALSE(fallback_is_allowed(PoseGoalFailure::None, true, false));
  EXPECT_FALSE(fallback_is_allowed(PoseGoalFailure::NoPlan, false, false));
}

TEST(PoseGoalTwoPass, ACartesianRequestIsRefusedRatherThanRescued)
{
  // The one that has no caller yet and is the reason this function exists. A
  // planner asked for a straight line and a planner that samples are not
  // interchangeable: the substitute returns a curve through the same endpoints,
  // the skill reports SUCCESS, and every scenario assertion — all of which are
  // about where the work-piece ends up — still passes. The boundary would then
  // be rediscovered on the physical cell.
  EXPECT_FALSE(fallback_is_allowed(PoseGoalFailure::NoPlan, true, true));
}

// --- The classification an out-of-limits IK solution gets ---------------------

TEST(PoseGoal, ASolutionRejectedBeforeThePlannerIsNotAPlanningFailure)
{
  // The caller installs the target inside `solve_ik`, so a solution the move
  // group refuses for being outside the joint limits never counts as a branch
  // that was planned to. Reported the other way round, it produced the sentence
  // "the planner found no path" about a planner that was never called — and
  // triggered a whole fallback pass for a failure no planner had produced.
  int plans = 0;
  PoseGoalAttempts attempts;

  const auto failure = plan_to_pose(
    4, [](int) {return false;},  // every seed: IK solved, target refused
    [&] {++plans; return true;}, kNeverCancelled, &attempts);

  EXPECT_EQ(failure, PoseGoalFailure::NoIkSolution);
  EXPECT_EQ(plans, 0);
  EXPECT_EQ(attempts.seeds_tried, 4);
  EXPECT_EQ(attempts.branches_planned, 0);
}
