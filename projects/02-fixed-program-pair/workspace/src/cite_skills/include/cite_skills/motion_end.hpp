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
#include <string>
#include <vector>

#include <cite_interfaces/msg/result_code.hpp>
#include <moveit_msgs/msg/move_it_error_codes.hpp>

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

/// The joint positions a trajectory names, in the trajectory's own order.
///
/// READ BY NAME, and that is the whole reason this exists rather than a copy of
/// a positions array. A planning group's variable order and a trajectory's
/// `joint_names` order are not required to agree, and comparing joint 1 against
/// joint 3 produces a confidently wrong answer rather than no answer at all —
/// which is the worse of the two outcomes for a classification that decides
/// whether an arm is replanned around unattended.
///
/// `lookup(name, out)` answers for one joint name and returns false when it
/// cannot. A single unanswerable name empties the whole result: a partial vector
/// would be compared element-wise against a full one, and `classify_motion_end`
/// would then be judging a different arm from the one the trajectory describes.
/// Templated on the callable so this header stays free of the robot model the
/// caller reads from.
template<typename Lookup>
std::vector<double> positions_in_trajectory_order(
  const std::vector<std::string> & names, const Lookup & lookup)
{
  std::vector<double> positions;
  positions.reserve(names.size());
  for (const auto & name : names) {
    double value = 0.0;
    if (!lookup(name, value)) {
      return {};
    }
    positions.push_back(value);
  }
  return positions;
}

/// A `ResultCode` and the prose that goes with it.
///
/// Returned as a pair rather than assembled by the caller so that the decision
/// and the sentence describing it cannot drift: a caller that switched a second
/// time to pick the wording would be a second copy of this rule.
struct ExecutionFailure
{
  uint8_t code{cite_interfaces::msg::ResultCode::MOTION_INTERRUPTED};
  std::string detail;
};

/// Whether MoveIt itself named why the motion ended.
///
/// Exactly the two values ADR-0037 decision 4 establishes survive MoveIt's
/// funnels intact. `classify_execution_failure` answers from the code alone when
/// this is true, so a caller can skip reading the arm — and skipping it is not an
/// optimisation: `getCurrentState` blocks for up to its timeout, and charging a
/// timeout that has already been reported against a second wait would make a
/// reported failure slower than an unreported one.
///
/// The two values are named HERE and nowhere else, so the predicate and the
/// classification cannot disagree about which codes they are (P1).
inline bool end_is_named_by_moveit(int moveit_error_code)
{
  return moveit_error_code == moveit_msgs::msg::MoveItErrorCodes::TIMED_OUT ||
         moveit_error_code == moveit_msgs::msg::MoveItErrorCodes::PREEMPTED;
}

/// Turn a failed `execute()` into a code L4 can act on (ADR-0037).
///
/// TWO AXES, AND THE NAMED ONE WINS. They are genuinely orthogonal, and ADR-0037
/// requires the implementation to state which takes precedence rather than
/// leaving it to whichever branch happened to be written first:
///
///   * MoveIt's error code says WHY the motion ended, for the two values that
///     survive its funnels intact — TIMED_OUT and PREEMPTED.
///   * The world-state test says WHETHER THE ARM MOVED, and is the only axis
///     available for everything else.
///
/// The named code wins, and the reason is definitional rather than a tie-break:
/// `MOTION_INTERRUPTED` is defined as "why it stopped is NOT ESTABLISHED". Where
/// MoveIt names the reason it HAS been established, so that code's own
/// definition excludes the case. Classifying a timeout as an interruption would
/// be a report that we cannot tell why the arm stopped, issued at the one moment
/// we can.
///
/// A TIMED_OUT or PREEMPTED arm may well be standing mid-path, and that is
/// accepted rather than overlooked: `TIMEOUT` and `CANCELLED` carry their own
/// policy rows in `recovery_policy.hpp`, decided in the knowledge that the stop
/// was MoveIt's own doing rather than the world's.
///
/// ADR-0037 CORRECTS THE SKILL SERVER'S PREVIOUS NOTE, which said that "reading
/// a distinction out of `executed.val` would be inventing one". That holds for
/// ABORTED, which arrives as CONTROL_FAILED alongside everything else. It is
/// false for these two: they are distinct values in that same field, set at
/// distinct sites, and passed through the capability rather than collapsed by
/// it.
///
/// WHY THIS IS A FREE FUNCTION AND NOT A METHOD ON THE SERVER. It was a private
/// method, and nothing tested it: the decision that chooses between retrying a
/// station unattended and stopping it for an operator was reachable only by
/// standing up `move_group` and provoking a real abort. As a free function over
/// the numbers it actually uses, every row of it is a unit test.
///
/// THAT A REAL ABORT REACHES IT is a separate claim and is evidenced separately,
/// by `cite_bringup/test/test_abort_classification_launch.py` (ADR-0040), which
/// stops one joint part way along its trajectory under a real `move_group` and
/// the real skill server. Read its module docstring for what that rig's perfect-
/// follower plant does and does not establish before citing it for anything about
/// an arm that decelerates.
inline ExecutionFailure classify_execution_failure(
  int moveit_error_code, const std::vector<double> & current,
  const std::vector<double> & start, const std::vector<double> & goal, double tolerance_rad)
{
  using cite_interfaces::msg::ResultCode;
  using moveit_msgs::msg::MoveItErrorCodes;

  if (moveit_error_code == MoveItErrorCodes::TIMED_OUT) {
    // `TrajectoryExecutionManager` stopped the controller because it overran the
    // trajectory's own expected duration. MoveIt knows this because MoveIt wrote
    // the duration.
    return {
      ResultCode::TIMEOUT,
      "MoveIt stopped the trajectory because the controller overran its expected duration"};
  }
  if (moveit_error_code == MoveItErrorCodes::PREEMPTED) {
    // `TrajectoryExecutionManager::stopExecution()` was called. The decision to
    // stop was taken somewhere that knew why, and re-deciding it here would
    // override it — the same reasoning `recovery_policy.hpp` gives CANCELLED.
    return {
      ResultCode::CANCELLED, "trajectory execution was preempted before it finished"};
  }

  // Everything else arrives as CONTROL_FAILED carrying no usable reason. Ask the
  // arm where it is instead — see this header's opening note for why that is the
  // better question rather than merely the available one.
  const std::string moveit_code =
    " (MoveIt error code " + std::to_string(moveit_error_code) + ")";
  switch (classify_motion_end(current, start, goal, tolerance_rad)) {
    case MotionEnd::AT_START:
      return {
        ResultCode::EXECUTION_FAILED,
        "the commanded trajectory did not take effect: the arm is still within its goal "
        "tolerance of the trajectory's first point" + moveit_code};

    case MotionEnd::AT_GOAL:
      return {
        ResultCode::EXECUTION_FAILED,
        "the arm reached the trajectory's last point, but the controller did not report the "
        "goal met" + moveit_code};

    case MotionEnd::PART_WAY:
      return {
        ResultCode::MOTION_INTERRUPTED,
        "the arm stopped part-way along the commanded trajectory and is holding position; it "
        "is neither at the start nor at the goal, and nothing on this stack reports why" +
        moveit_code};

    case MotionEnd::UNKNOWN:
    default:
      // Where the arm ended up could not be established. That is not evidence
      // that it is somewhere harmless, so it does not get the reassuring answer:
      // an arm whose position cannot be read is exactly the arm that nothing
      // should replan around unattended.
      return {
        ResultCode::MOTION_INTERRUPTED,
        "the controller did not complete the planned trajectory, and where the arm ended up "
        "could not be established from its joint state" + moveit_code};
  }
}

}  // namespace cite_skills

#endif  // CITE_SKILLS__MOTION_END_HPP_
