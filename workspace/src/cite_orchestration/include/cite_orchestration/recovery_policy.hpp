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

// What the line does about a failure, chosen from the structured code.
//
// L4 lists "fault recovery policy — what to retry, what to escalate, what to
// stop" under Owns, and says recovery is expressed rather than implied: "a
// generic retry loop is not a recovery policy — it is a way of failing
// repeatedly at speed". This file is where that sentence becomes code.
//
// It reads `ResultCode.code` and nothing else. `ResultCode.detail` is prose for a
// person and NOTHING may parse it — that is stated on the message itself, and it
// is why v1's orchestration could only ever retry generically.
//
// The distinction the codes were widened for is the one this file must not blur.
// `UNREACHABLE` means no inverse-kinematics solution exists for the pose AT ALL;
// `PLANNING_FAILED` means one exists and no collision-free path to it was found.
// Retrying an `UNREACHABLE` goal unchanged cannot succeed however many times it
// is sent — the station or the pose has to move, and that is a person's
// decision. Reporting the first as the second sent three investigations to the
// wrong place; retrying it would send the line round the same loop instead.

#ifndef CITE_ORCHESTRATION__RECOVERY_POLICY_HPP_
#define CITE_ORCHESTRATION__RECOVERY_POLICY_HPP_

#include <cstdint>

#include <cite_interfaces/msg/result_code.hpp>

namespace cite_orchestration
{

/// The four responses L4 names, plus the absence of one.
///
/// Deliberately not an open-ended "retry n times": each value says something
/// different about WHY the same goal would or would not work again.
enum class Recovery : uint8_t
{
  //: Nothing failed. Present so that a caller handing this function a success
  //: code gets an answer rather than a policy.
  NONE,

  //: The same goal, unchanged, has a real chance of working: whatever went wrong
  //: was transient. Bounded by a budget — see `within_budget`.
  RETRY_SAME,

  //: The same goal cannot work until the world is looked at again. The station
  //: re-observes and builds a new goal from what it finds, rather than resending
  //: one built from an assumption that has already been contradicted.
  RETRY_DIFFERENTLY,

  //: A person has to decide. The line stops this station, keeps the work-piece
  //: where it is, and says so.
  ESCALATE,

  //: Stop the whole line now. Reserved for the two codes that mean the cell
  //: itself is not in a state to be commanded.
  STOP_LINE,
};

/// Choose a response for one `ResultCode.code`.
///
/// Every constant the message declares is listed. A code this build does not
/// know — a `ResultCode` extended by a newer producer — is ESCALATE and never a
/// retry: the one thing worse than not knowing what went wrong is retrying
/// through it.
inline Recovery recovery_for(uint8_t code)
{
  using cite_interfaces::msg::ResultCode;
  switch (code) {
    case ResultCode::SUCCESS:
      return Recovery::NONE;

    //: The operator asked for this, or a leaf gave up and cancelled. Either way
    //: the decision to stop was taken somewhere that knew why, and re-deciding
    //: it here would override it.
    case ResultCode::CANCELLED:
      return Recovery::NONE;

    //: The next attempt has to be a genuinely DIFFERENT attempt, and what makes
    //: it one is the re-observation this value names — not the planner.
    //:
    //: That distinction used to be carried by "a planner is stochastic and a
    //: scene changes", and the first half of it stopped being true under
    //: ADR-0027: the default planner integrates a profile, so an identical goal
    //: against an unchanged scene returns an identical refusal, immediately.
    //: Nothing about the policy changes, because the policy never rested on
    //: redrawing samples: `RecoverNode` returns the station to WAITING and the
    //: station's tree detects before it picks, so the goal is rebuilt from what
    //: the cell looks like now. What is bounded is the loop — `recovery_for`
    //: with a budget turns a retry past `retry_budget` into an ESCALATE — so a
    //: pose that keeps failing reaches an operator rather than circling.
    case ResultCode::PLANNING_FAILED:
      return Recovery::RETRY_DIFFERENTLY;

    //: "The world was not in the state the goal assumed" is, in as many words, a
    //: statement that the assumption has to be replaced rather than repeated.
    case ResultCode::PRECONDITION_FAILED:
      return Recovery::RETRY_DIFFERENTLY;

    //: A trajectory that aborted or a goal that ran long says nothing about
    //: whether the goal was right, so the same goal is the right next attempt —
    //: bounded, because a controller that aborts every time is a fault and not a
    //: transient.
    //:
    //: NARROWED BY ADR-0037, AND THE NARROWING IS IN L3 RATHER THAN HERE. The
    //: sentence above stopped being universally true when ADR-0036 gave the
    //: controller a path tolerance: a `PATH_TOLERANCE_VIOLATED` abort means
    //: something physically held the arm, and replanning from a model of the
    //: world that the abort itself contradicts is not a retry of the same goal —
    //: it is the same goal against a world nobody has looked at.
    //:
    //: What that needed was a discriminator, and the branch that carried this
    //: note said one did not exist. That was half right. It reasoned from what
    //: the `FollowJointTrajectory` ACTION DEFINITION makes expressible rather
    //: than from what THIS CONTROLLER emits, and so listed `INVALID_JOINTS` and
    //: `OLD_HEADER_TIMESTAMP` as arriving indistinguishably — describing the
    //: second as a transport fault that MUST keep retrying. Neither is ever set
    //: by `joint_trajectory_controller`. Both conditions are caught in
    //: `validate_trajectory_msg` and turned into a goal REJECTION, and a ROS 2
    //: rejection carries no result message and therefore no code at all. The
    //: retryable transport fault that argued for keeping this branch broad does
    //: not exist on this stack.
    //:
    //: So the discriminator is not a vendor code. L3 asks the ARM where it is —
    //: at the start, at the goal, or part-way — and answers `MOTION_INTERRUPTED`
    //: for the third. This branch keeps its meaning for the two endpoint cases,
    //: where the arm is somewhere the next attempt can be planned from.
    case ResultCode::EXECUTION_FAILED:
    case ResultCode::TIMEOUT:
      return Recovery::RETRY_SAME;

    //: The arm stopped part-way through a commanded motion and is holding a
    //: position no part of that motion asked it to hold, and nothing on this
    //: stack reports why. There is no goal to resend against a world that has
    //: already contradicted the plan the last one was built from.
    //:
    //: ESCALATE AND NOT STOP_LINE, deliberately. One station is compromised; the
    //: cell is not. `STOP_LINE` stays reserved for `SAFETY_BLOCKED` and
    //: `HARDWARE_FAULT`, the two codes that say the cell itself cannot be
    //: commanded at all — and widening it to cover an arm that stopped would
    //: make every path-tolerance abort a line-wide fault, which is how a
    //: detector gets exempted rather than fixed.
    //:
    //: THIS IS NOT A PROTECTIVE MEASURE. It removes an automatic resumption.
    //: What stops an arm remains the vendor controller's torque limiting and
    //: physical guarding (charter §3.2). A station that stops instead of
    //: retrying is not safer in any certifiable sense; it is diagnosable.
    case ResultCode::MOTION_INTERRUPTED:
      return Recovery::ESCALATE;

    //: No IK solution exists for this pose. Not "not found this time" — none
    //: exists. Resending it is the definition of failing repeatedly at speed;
    //: what has to change is the station's geometry or the pose, and neither is
    //: L4's to change.
    case ResultCode::UNREACHABLE:
      return Recovery::ESCALATE;

    //: A path deliberately unbuilt (P7). Retrying an unimplemented path builds
    //: nothing and hides that it is unbuilt.
    case ResultCode::NOT_IMPLEMENTED:
      return Recovery::ESCALATE;

    //: L2 refused the motion. L4 is not the safety mechanism and must never
    //: behave as though a refusal were a transient — retrying through one is how
    //: a coordination bug becomes an injury.
    case ResultCode::SAFETY_BLOCKED:
      return Recovery::STOP_LINE;

    //: The cell is not in a state to be commanded at all, so no other station's
    //: work is trustworthy either.
    case ResultCode::HARDWARE_FAULT:
      return Recovery::STOP_LINE;

    default:
      return Recovery::ESCALATE;
  }
}

/// Whether a retry still has attempts left.
///
/// Separated from `recovery_for` because the budget is a property of the station
/// that is retrying, not of the code that came back. A retry past its budget
/// becomes an escalation rather than silently continuing: "recovery masking a
/// real fault — the line works while silently degrading" is a named L4 failure
/// mode, and an unbounded retry is how it happens.
inline bool within_budget(uint32_t attempts_already_made, uint32_t budget)
{
  return attempts_already_made < budget;
}

/// The response with the budget applied. This is what a caller should use.
inline Recovery recovery_for(uint8_t code, uint32_t attempts_already_made, uint32_t budget)
{
  const Recovery response = recovery_for(code);
  const bool is_retry =
    response == Recovery::RETRY_SAME || response == Recovery::RETRY_DIFFERENTLY;
  if (is_retry && !within_budget(attempts_already_made, budget)) {
    return Recovery::ESCALATE;
  }
  return response;
}

/// A name for a log line and for `LineState.blocked_reason`. Never parsed.
inline const char * describe(Recovery recovery)
{
  switch (recovery) {
    case Recovery::NONE:
      return "no recovery needed";
    case Recovery::RETRY_SAME:
      return "retrying the same goal";
    case Recovery::RETRY_DIFFERENTLY:
      return "re-observing and rebuilding the goal";
    case Recovery::ESCALATE:
      return "escalated to an operator";
    case Recovery::STOP_LINE:
      return "stopping the line";
  }
  return "unknown recovery";
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__RECOVERY_POLICY_HPP_
