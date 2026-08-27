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

// Where the arm ended up, relative to the trajectory it was given.
//
// ADR-0037. When `MoveGroupInterface::execute()` returns something other than
// SUCCESS, this answers the only question L4 can act on: did the arm not move,
// did it arrive, or is it standing somewhere in between? "In between" is the
// case that must not be retried unattended, because the world that the next plan
// would be built from is precisely the world the abort contradicted.
//
// ## Why the answer is read off the arm and not off an error code
//
// Because there is no error code to read. The controller's own
// `FollowJointTrajectory::Result::error_code` — the field that would say
// PATH_TOLERANCE_VIOLATED — is destroyed by three separate funnels before it
// reaches this layer, and ADR-0037 records all three with line numbers:
// `finishControllerExecution` takes an `rclcpp_action::ResultCode` and nothing
// else; `moveit_controller_manager::ExecutionStatus` is a closed seven-value
// enum with no payload field; and `execute_trajectory_action_capability`
// collapses everything but SUCCEEDED, PREEMPTED and TIMED_OUT into
// CONTROL_FAILED. Each of the three is sufficient on its own. Nothing is fixed
// upstream and nobody has asked.
//
// So the question is asked of the arm instead, and that turns out to be the
// better place to ask it rather than a consolation:
//
//   * P2 by construction. Joint states are identical on both backends. Nothing
//     here branches on whether the cell is simulated.
//   * P9 by construction. A robot type whose controller reports differently, or
//     does not report at all, classifies identically — this is a statement about
//     an arm, not about a controller.
//
// ## It is an inference, and it is written down as one
//
// This does not say WHY the arm stopped and cannot. A trajectory whose start and
// goal are close together, or an abort a few milliseconds after motion begins,
// lands near a boundary and will sometimes be classified wrongly. What keeps the
// answer defensible is that the threshold is the ARM'S OWN goal tolerance,
// declared once in L0 (ADR-0036) and handed to this layer as a parameter — the
// same number the controller itself checks against, not a second copy invented
// here (P1).

#ifndef CITE_SKILLS__MOTION_END_HPP_
#define CITE_SKILLS__MOTION_END_HPP_

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace cite_skills
{

/// Where an arm is standing, relative to the trajectory it was commanded along.
enum class MotionEnd : uint8_t
{
  //: Within tolerance of the trajectory's LAST point. The arm arrived. Whatever
  //: the controller objected to, it was not the position — this is the
  //: settling-side case, and it is reported as a completed-but-failed motion
  //: rather than as an interruption, because the arm is where it was sent.
  AT_GOAL,

  //: Within tolerance of the trajectory's FIRST point. The arm never left. The
  //: command did not take effect.
  AT_START,

  //: Neither. The arm stopped part-way and is holding a position that no part of
  //: the commanded motion asked it to hold.
  PART_WAY,

  //: The comparison could not be made — no trajectory, or a joint the plan names
  //: that the current state does not carry.
  ///
  /// Deliberately NOT folded into AT_START. "I could not tell where the arm is"
  /// and "the arm did not move" are opposite claims, and the caller must not
  /// answer an unreadable arm with the more reassuring of the two.
  UNKNOWN,
};

/// Whether every joint in `a` is within `tolerance_rad` of its partner in `b`.
///
/// Per joint and not a norm: a norm lets a large error on one joint hide under
/// small errors on five others, and the controller's own tolerance check —
/// `check_state_tolerance_per_joint` — is per joint too. Matching what the
/// controller checks is the whole reason the threshold is the arm's own.
inline bool within_tolerance(
  const std::vector<double> & a, const std::vector<double> & b, double tolerance_rad)
{
  if (a.size() != b.size() || a.empty() || !(tolerance_rad > 0.0)) {
    return false;
  }
  for (std::size_t i = 0; i < a.size(); ++i) {
    if (!std::isfinite(a[i]) || !std::isfinite(b[i])) {
      return false;
    }
    if (std::fabs(a[i] - b[i]) > tolerance_rad) {
      return false;
    }
  }
  return true;
}

/// Classify where the arm ended up.
///
/// `current`, `start` and `goal` are joint positions in radians, in ONE agreed
/// order — the caller is responsible for reading the current state by the joint
/// NAMES the plan carries, so that a group whose ordering differs from the
/// trajectory's cannot silently compare joint 1 against joint 3.
///
/// THE GOAL IS TESTED FIRST, and the order is a decision rather than an
/// accident. A short trajectory can put the arm within tolerance of both ends at
/// once; when that happens the arm is at the goal, and "it arrived" is the more
/// specific and more useful of the two true statements. Testing the start first
/// would report a completed short motion as one that never began.
inline MotionEnd classify_motion_end(
  const std::vector<double> & current, const std::vector<double> & start,
  const std::vector<double> & goal, double tolerance_rad)
{
  const bool comparable = !current.empty() && current.size() == start.size() &&
    current.size() == goal.size() && tolerance_rad > 0.0;
  if (!comparable) {
    return MotionEnd::UNKNOWN;
  }
  if (within_tolerance(current, goal, tolerance_rad)) {
    return MotionEnd::AT_GOAL;
  }
  if (within_tolerance(current, start, tolerance_rad)) {
    return MotionEnd::AT_START;
  }
  return MotionEnd::PART_WAY;
}

}  // namespace cite_skills

#endif  // CITE_SKILLS__MOTION_END_HPP_
