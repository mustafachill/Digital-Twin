#include "cite_skills/pose_goal.hpp"

namespace cite_skills
{

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
  return counted.branches_planned == 0 ? PoseGoalFailure::NoIkSolution
                                       : PoseGoalFailure::NoPlan;
}

}  // namespace cite_skills
