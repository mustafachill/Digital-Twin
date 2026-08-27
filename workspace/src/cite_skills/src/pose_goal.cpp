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

#include "cite_skills/pose_goal.hpp"

namespace cite_skills
{

PoseGoalAttempts operator+(const PoseGoalAttempts & a, const PoseGoalAttempts & b)
{
  PoseGoalAttempts sum;
  sum.seeds_tried = a.seeds_tried + b.seeds_tried;
  sum.branches_planned = a.branches_planned + b.branches_planned;
  return sum;
}

bool fallback_is_allowed(PoseGoalFailure first, bool have_fallback, bool cartesian_request)
{
  return first == PoseGoalFailure::NoPlan && have_fallback && !cartesian_request;
}

PoseGoalFailure combined_failure(PoseGoalFailure first, PoseGoalFailure second)
{
  if (second == PoseGoalFailure::None || second == PoseGoalFailure::Cancelled) {
    return second;
  }
  return first;
}

PoseGoalFailure plan_to_pose(
  int max_seeds,
  const std::function<bool(int)> & solve_ik,
  const std::function<bool()> & plan_to_solution,
  const std::function<bool()> & cancelled,
  PoseGoalAttempts * attempts)
{
  PoseGoalAttempts local;
  PoseGoalAttempts & counted = attempts != nullptr ? *attempts : local;
  counted = PoseGoalAttempts{};

  for (int seed = 0; seed < max_seeds; ++seed) {
    if (cancelled()) {
      return PoseGoalFailure::Cancelled;
    }

    ++counted.seeds_tried;
    if (!solve_ik(seed)) {
      continue;
    }

    if (cancelled()) {
      return PoseGoalFailure::Cancelled;
    }

    ++counted.branches_planned;
    if (plan_to_solution()) {
      return PoseGoalFailure::None;
    }
  }

  // Never having reached the planner is a different failure from having reached
  // it and been refused, and the caller reports them under different codes.
  return counted.branches_planned == 0 ? PoseGoalFailure::NoIkSolution :
         PoseGoalFailure::NoPlan;
}

}  // namespace cite_skills
