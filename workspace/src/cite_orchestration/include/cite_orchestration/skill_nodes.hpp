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

// L4 behaviour-tree leaves: one L3 skill each.
//
// In a header rather than beside `main` so that the leaves can be driven by a
// test against a real action server. What needed testing was not the happy path
// but the giving-up path — see `SkillNode::send` — and that path was
// unreachable from outside while these lived in an anonymous namespace inside an
// executable.
//
// Nothing here plans a trajectory or commands a controller. Every leaf calls an
// L3 skill as a ROS 2 action, and nothing else — that separation is what lets an
// arm be swapped without touching orchestration (P9).

#ifndef CITE_ORCHESTRATION__SKILL_NODES_HPP_
#define CITE_ORCHESTRATION__SKILL_NODES_HPP_

#include <chrono>
#include <memory>
#include <string>
#include <utility>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/msg/result_code.hpp>

#include "behaviortree_cpp/bt_factory.h"

namespace cite_orchestration
{

using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::msg::ResultCode;

/// Shared context every leaf needs. Passed in rather than looked up, so a leaf
/// cannot quietly acquire a dependency nobody declared.
struct Context
{
  rclcpp::Node::SharedPtr node;
  std::chrono::seconds skill_deadline{180};

  //: How long to wait for a server to acknowledge a cancellation and for the
  //: abandoned goal to reach a terminal state. A deadline, never a schedule: it
  //: sequences nothing, and expiry is reported rather than proceeded past.
  std::chrono::seconds cancel_deadline{30};
};

/// Base for a leaf that calls one L3 action.
///
/// Synchronous on purpose for Phase 1.C: the tree ticks one station at a time,
/// so a blocking leaf is honest about what is happening. When 1.D runs three
/// stations in parallel these become StatefulActionNodes, which is a change to
/// this file and to nothing else.
template<typename ActionT>
class SkillNode : public BT::SyncActionNode
{
public:
  SkillNode(const std::string & name, const BT::NodeConfig & config, Context context)
  : BT::SyncActionNode(name, config), context_(std::move(context))
  {
  }

protected:
  using GoalHandle = typename rclcpp_action::ClientGoalHandle<ActionT>::SharedPtr;
  using Client = typename rclcpp_action::Client<ActionT>::SharedPtr;

  /// Send a goal and wait for its result, with a deadline that fails.
  ///
  /// Every path that gives up cancels first. Returning FAILURE while the goal is
  /// still EXECUTING is not "giving up" — it is losing track of a moving arm.
  /// The tree's Fallback then runs the recovery branch, whose first leaf sends a
  /// new goal to the same server, and `BT::SyncActionNode` has no halt so
  /// nothing stops the first one. Depending on what the server does with the
  /// second goal, that is either two motion goals racing on one arm or a
  /// recovery branch that can never run — and the skill server now rejects a
  /// second goal, so it is reliably the latter. Cancelling is what makes the
  /// recovery branch work at all.
  BT::NodeStatus send(const std::string & action_name, const typename ActionT::Goal & goal)
  {
    auto client = rclcpp_action::create_client<ActionT>(context_.node, action_name);
    if (!client->wait_for_action_server(context_.cancel_deadline)) {
      RCLCPP_ERROR(
        context_.node->get_logger(), "no skill server at %s", action_name.c_str());
      // Nothing was sent, so there is nothing to cancel.
      return BT::NodeStatus::FAILURE;
    }

    auto goal_future = client->async_send_goal(goal);
    if (rclcpp::spin_until_future_complete(
        context_.node, goal_future, context_.cancel_deadline) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(
        context_.node->get_logger(), "%s never accepted the goal", action_name.c_str());
      // The acceptance never arrived, so this node has no handle to cancel with —
      // but the server may still have accepted it and be executing. Cancelling
      // everything on that action is the only way to be sure the arm is not left
      // moving under a goal nobody is holding.
      CancelAll(client, action_name);
      return BT::NodeStatus::FAILURE;
    }
    auto handle = goal_future.get();
    if (!handle) {
      RCLCPP_ERROR(context_.node->get_logger(), "%s rejected the goal", action_name.c_str());
      return BT::NodeStatus::FAILURE;
    }

    auto result_future = client->async_get_result(handle);
    if (rclcpp::spin_until_future_complete(
        context_.node, result_future, context_.skill_deadline) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(
        context_.node->get_logger(), "%s did not finish in time", action_name.c_str());
      Abandon(client, handle, result_future, action_name);
      return BT::NodeStatus::FAILURE;
    }

    const auto outcome = result_future.get().result->result;
    if (outcome.code != ResultCode::SUCCESS) {
      // The code, not the text, is what a recovery branch reacts to. v1 could
      // only retry generically because its failures were prose. The goal has
      // already reached a terminal state here, so there is nothing to cancel.
      RCLCPP_WARN(
        context_.node->get_logger(), "%s returned code %u: %s", action_name.c_str(),
        outcome.code, outcome.detail.c_str());
      return BT::NodeStatus::FAILURE;
    }
    return BT::NodeStatus::SUCCESS;
  }

private:
  /// Cancel a goal this node has given up on, and wait for it to end.
  ///
  /// Both waits are deadlines, and expiry is reported rather than ignored: a
  /// server that will not acknowledge a cancellation is a fault worth naming,
  /// and the arm may genuinely still be moving.
  template<typename ResultFuture>
  void Abandon(
    const Client & client, const GoalHandle & handle, ResultFuture & result_future,
    const std::string & action_name)
  {
    auto cancel_future = client->async_cancel_goal(handle);
    if (rclcpp::spin_until_future_complete(
        context_.node, cancel_future, context_.cancel_deadline) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "%s did not answer the cancellation; the abandoned goal may still be executing",
        action_name.c_str());
      return;
    }

    // Then wait for the goal to actually END. Acknowledgement means the server
    // accepted the request, not that the arm has stopped; sending the recovery
    // branch's next goal before then races exactly the motion this cancellation
    // exists to stop.
    if (rclcpp::spin_until_future_complete(
        context_.node, result_future, context_.cancel_deadline) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "%s acknowledged the cancellation but the goal has not ended; the arm may "
        "still be moving",
        action_name.c_str());
      return;
    }
    RCLCPP_INFO(
      context_.node->get_logger(), "%s: abandoned goal cancelled", action_name.c_str());
  }

  /// Cancel every goal on one action, for the case where no handle was received.
  void CancelAll(const Client & client, const std::string & action_name)
  {
    auto cancel_future = client->async_cancel_all_goals();
    if (rclcpp::spin_until_future_complete(
        context_.node, cancel_future, context_.cancel_deadline) !=
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "%s did not answer a blanket cancellation; a goal it accepted without telling "
        "us may still be executing",
        action_name.c_str());
    }
  }

protected:
  Context context_;
};

class MoveToHome : public SkillNode<MoveTo>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("action", "the MoveTo action this station's arm serves"),
    };
  }

  BT::NodeStatus tick() override
  {
    const auto action = getInput<std::string>("action");
    if (!action || action->empty()) {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "MoveToHome was given no action name. Names come from the generated model; "
        "this node does not build one.");
      return BT::NodeStatus::FAILURE;
    }
    MoveTo::Goal goal;
    // "home" resolves against the L0 model inside the skill server, not here:
    // where an arm rests between cycles is a fact about the facility.
    goal.named_configuration = "home";
    return send(action.value(), goal);
  }
};

class PickAt : public SkillNode<Pick>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("frame"),
      BT::InputPort<std::string>("action", "the Pick action this station's arm serves"),
      BT::InputPort<std::string>("workpiece", "which work-piece this station handles"),
      // How far above the station's frame the work-piece's centre sits. A
      // stand-in for Detect, which is what tells the line where a work-piece
      // actually is; until that skill exists, saying so with a port is more
      // honest than burying the number in this file.
      //
      // A WORK-PIECE FACT, and nothing else. This port used to be
      // `grasp_height_m` at 0.030 — the height to put the TOOL at, which is a
      // different question and one L4 has no business answering. The cell's
      // reference work-piece is a 50 mm cube resting on the frame, so its centre
      // is at 0.025; the extra 5.00 mm was this file guessing at the gripper's
      // geometry, and guessing low. `Pick.Goal.object_pose` is "where the object
      // is", the L3 skill server offsets it onto the pad plane using the end
      // effector's own declared linkage, and the two questions are now asked in
      // the two places that can answer them (P5, P9).
      BT::InputPort<double>(
        "workpiece_height_m", 0.025, "the work-piece's centre above the frame"),
      BT::InputPort<double>("approach_m", 0.10, "standoff before grasping"),
      BT::InputPort<double>("retreat_m", 0.12, "lift after grasping"),
      // The jaw width commanded on the part, and a stand-in in the same sense:
      // L0 records no work-piece geometry, so nothing can derive it yet.
      //
      // WHERE THIS NUMBER COMES FROM. Against the WORK-PIECE, which is the only
      // datum it has ever really been about: a parallel gripper evidences a grasp
      // by failing to reach where it was sent (ADR-0022), so the command has to be
      // narrower than the part. The scenario's part is a 50 mm cube, and 0.045
      // leaves 5.00 mm of margin — against the ~2.11 mm that `gripper_is_holding`
      // needs to tell a real grasp from the controller's own end-of-goal position
      // bias. Wider than the part and the jaws arrive on target and learn nothing;
      // much narrower and the jaws close through nothing at all.
      //
      // WHAT USED TO BE WRITTEN HERE, because the correction is the point. The
      // bound was derived from `closed_threshold / closed_position` — parameters
      // of ADR-0023's contact-triggered attachment plugin. That put an L4
      // orchestration file reasoning from the configuration of an L1 SIMULATION
      // plugin, which is the boundary ADR-0023 was supposed to protect and the
      // one thing that must never leak (P2): a number justified by how the
      // simulator is built cannot be right on hardware except by accident. The
      // plugin was removed and ADR-0023 superseded by ADR-0029; the value 0.045
      // survives because the bound above is the real one and always was.
      //
      // THE VALUE IS ALSO IN L0, as `default_grasp_width_m` on the end-effector
      // type, and `Pick.Goal.grasp_width_m == 0` means "use that". Sending 0 from
      // here is where this belongs and is deliberately NOT done yet: the
      // generated bring-up plan carries the default, but the launch mechanism
      // does not pass it to the skill server, so a 0 sent today resolves to no
      // width at all and closes the gripper against its effort limit. Sending the
      // number keeps the cell working; it is a duplicate until that delivery is
      // fixed, and it is named as one here rather than left to be discovered.
      BT::InputPort<double>("grasp_width_m", 0.045, "commanded jaw width on the part"),
    };
  }

  BT::NodeStatus tick() override
  {
    const auto action = getInput<std::string>("action");
    const auto frame = getInput<std::string>("frame");
    if (!action || action->empty() || !frame) {
      RCLCPP_ERROR(
        context_.node->get_logger(), "PickAt needs both an action name and a frame");
      return BT::NodeStatus::FAILURE;
    }

    Pick::Goal goal;
    // The pose is a frame the station named in L0, resolved through TF. No world
    // coordinate is written here, which is what stopped v1's pick tables from
    // diverging from the cell they described.
    goal.object_pose.header.frame_id = frame.value();
    goal.object_pose.pose.position.z =
      getInput<double>("workpiece_height_m").value_or(0.025);

    // Pointing DOWN — a half turn about X. This is not cosmetic: the skill stands
    // off along the tool's own -Z, so with an identity orientation the approach
    // pose would be *below* the table rather than above it, and the plan would
    // fail with an inverse-kinematics error that says nothing about orientation.
    goal.object_pose.pose.orientation.x = 1.0;
    goal.object_pose.pose.orientation.y = 0.0;
    goal.object_pose.pose.orientation.z = 0.0;
    goal.object_pose.pose.orientation.w = 0.0;

    // What the skill records as held on success. Left empty, the server warns
    // about a work-piece named `''` and the line has no idea what it is carrying.
    goal.workpiece_id = getInput<std::string>("workpiece").value_or("");
    goal.approach_distance_m = getInput<double>("approach_m").value_or(0.10);
    goal.retreat_distance_m = getInput<double>("retreat_m").value_or(0.12);
    goal.grasp_width_m = getInput<double>("grasp_width_m").value_or(0.045);
    return send(action.value(), goal);
  }
};

class PlaceAt : public SkillNode<Place>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("frame"),
      BT::InputPort<std::string>("action", "the Place action this station's arm serves"),
      // Where the WORK-PIECE's centre is left, above the station's frame — not
      // where the tool goes. `Place.Goal.target_pose` is the object's target and
      // the L3 skill server offsets it onto the pad plane, exactly as `Pick`
      // does; this port names a height in the same terms the pick side does.
      //
      // 0.040 against a 50 mm part resting at 0.025 is a deliberate 15 mm drop:
      // the arm lets go slightly above the surface rather than pressing the part
      // into it, which is what it did while this number was read as a tool height
      // and the pad plane was a stroke-dependent distance below it.
      BT::InputPort<double>(
        "release_height_m", 0.04, "the work-piece's centre at release, above the frame"),
      BT::InputPort<double>("approach_m", 0.10, "standoff before releasing"),
      BT::InputPort<double>("retreat_m", 0.12, "lift after releasing"),
    };
  }

  BT::NodeStatus tick() override
  {
    const auto action = getInput<std::string>("action");
    const auto frame = getInput<std::string>("frame");
    if (!action || action->empty() || !frame) {
      RCLCPP_ERROR(
        context_.node->get_logger(), "PlaceAt needs both an action name and a frame");
      return BT::NodeStatus::FAILURE;
    }

    Place::Goal goal;
    goal.target_pose.header.frame_id = frame.value();
    goal.target_pose.pose.position.z = getInput<double>("release_height_m").value_or(0.04);
    // Pointing down, for the same reason Pick does: the skill stands off along
    // the tool's own -Z, so an identity orientation would put the approach below
    // the belt rather than above it.
    goal.target_pose.pose.orientation.x = 1.0;
    goal.target_pose.pose.orientation.w = 0.0;
    goal.approach_distance_m = getInput<double>("approach_m").value_or(0.10);
    goal.retreat_distance_m = getInput<double>("retreat_m").value_or(0.12);
    // Refuse to mime a place with an empty gripper: the line would believe a
    // work-piece arrived somewhere it never did, and the failure would surface
    // at the next station instead.
    goal.require_holding = true;
    return send(action.value(), goal);
  }
};

/// Report a station as blocked. The recovery branch's terminal step.
class ReportBlocked : public BT::SyncActionNode
{
public:
  ReportBlocked(
    const std::string & name, const BT::NodeConfig & config, rclcpp::Node::SharedPtr node)
  : BT::SyncActionNode(name, config), node_(std::move(node))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {BT::InputPort<std::string>("asset"), BT::InputPort<std::string>("reason")};
  }

  BT::NodeStatus tick() override
  {
    RCLCPP_ERROR(
      node_->get_logger(), "station blocked at %s: %s",
      getInput<std::string>("asset").value_or("?").c_str(),
      getInput<std::string>("reason").value_or("no reason given").c_str());
    // SUCCESS: reporting the blockage is what this node was asked to do. The
    // line's state, not this tick, is what says the station is not working.
    return BT::NodeStatus::SUCCESS;
  }

private:
  rclcpp::Node::SharedPtr node_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__SKILL_NODES_HPP_
