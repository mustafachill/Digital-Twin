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

// How a task-space pose becomes a motion (ADR-0026).
//
// The sequencing lives here, separated from MoveIt, so that the rule this
// project decided on — solve IK on the *exact* pose, plan to the resulting
// joint configuration, and try more than one IK branch before calling a pose
// unreachable — is testable without a planner, a robot model or a simulator.
//
// Nothing in this header knows what an arm is. The caller supplies two
// callables: one that installs an IK solution for a given seed, and one that
// plans to whatever the first one installed.

#ifndef CITE_SKILLS__POSE_GOAL_HPP_
#define CITE_SKILLS__POSE_GOAL_HPP_

#include <functional>

namespace cite_skills
{

/// Why a pose could not be turned into a planned motion.
///
/// `NoIkSolution` and `NoPlan` are deliberately distinct. They are different
/// diagnoses with different recoveries — one says the arm cannot reach the pose
/// at all, the other says it can but no path was found from where it stands —
/// and reporting them as one sentence is what sent three separate
/// investigations of `pick_and_place` to the wrong place.
enum class PoseGoalFailure
{
  None,          ///< A plan was produced.
  NoIkSolution,  ///< Every seed failed: the arm cannot reach this pose.
  NoPlan,        ///< IK solved, but no branch could be planned to.
  Cancelled,     ///< The goal was cancelled, or the node is shutting down.
};

/// What the search actually did, so a failure can report it rather than assert it.
struct PoseGoalAttempts
{
  int seeds_tried{0};       ///< How many seeds IK was run from.
  int branches_planned{0};  ///< How many IK solutions were handed to the planner.
};

/// Try IK seeds in order until one of them yields a plannable configuration.
///
/// `solve_ik(seed_index)` installs an IK solution for that seed and returns
/// whether it found one; seed 0 is by convention the arm's current state, which
/// keeps the chosen branch near where the arm already stands. `plan_to_solution()`
/// plans to whatever `solve_ik` last installed.
///
/// A joint-space goal commits to ONE IK branch, so a branch whose path is
/// blocked must not be mistaken for a pose the arm cannot reach — hence the
/// loop continues past a planning failure, and the two outcomes are told apart
/// by whether any branch was ever planned to.
PoseGoalFailure plan_to_pose(
  int max_seeds,
  const std::function<bool(int)> & solve_ik,
  const std::function<bool()> & plan_to_solution,
  const std::function<bool()> & cancelled,
  PoseGoalAttempts * attempts);

}  // namespace cite_skills

#endif  // CITE_SKILLS__POSE_GOAL_HPP_
