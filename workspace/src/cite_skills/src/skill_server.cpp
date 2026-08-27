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

// L3 skill server: one node per arm, hosting that arm's capabilities.
//
// Everything this node knows about its arm arrives as a generated parameter —
// the planning group, the tip link, the action names, the home configuration.
// Nothing here concatenates a topic, an action or a frame name. That is not a
// style preference: P2 says simulation and hardware are interchangeable, and
// that guarantee is made of names. A name built here would be a second place a
// name is made, and `ids.py`'s tests would not cover it.
//
// Goals are in task space. A joint-space goal in the *interface* would leak the
// robot's kinematics upward and break the promise that swapping this arm for a
// different one changes nothing above this line. Inside the skill it is the
// opposite: a Cartesian pose goal is never handed to the planner. The pose is
// resolved, IK is solved on that exact pose, and the planner is given the
// resulting joint configuration (ADR-0026) — because a pose goal is satisfied by
// random draws from inside its tolerance, and on an arm with fewer than six
// degrees of freedom almost every draw is unreachable.
//
// One arm executes one skill at a time. Five action servers share one
// MoveGroupInterface, which is not thread-safe and whose target, start state and
// scaling factors are per-object; a second goal accepted while one is in flight
// can plan to the target the first just installed, and the arm executes it. A
// second goal is therefore rejected rather than queued.
//
// `Detect` is the sixth skill and is deliberately NOT here. It commands no
// motion, needs neither the planner nor the gripper, and belongs to a zone's
// sensors rather than to one arm — three arms each serving it would be three
// views of one belt. It lives in `detection_server.cpp`.
//
// Every skill implements the full action contract, cancellation included. L3 is
// explicit that covering only the happy path is a review finding — a skill that
// cannot be cancelled leaves L4 with no way to recover from anything.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include <control_msgs/action/gripper_command.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <moveit/move_group_interface/move_group_interface.hpp>
#include <moveit/robot_model/joint_model_group.hpp>
#include <moveit/robot_state/robot_state.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include "tf2_ros/buffer.h"
#include "tf2_ros/transform_listener.h"
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>

#include <cite_interfaces/action/grasp.hpp>
#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/action/transfer.hpp>
#include <cite_interfaces/msg/result_code.hpp>

#include "cite_skills/approach.hpp"
#include "cite_skills/exclusive_goal.hpp"
#include "cite_skills/gripper.hpp"
#include "cite_skills/pose_goal.hpp"

namespace
{

using cite_interfaces::action::Grasp;
using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::action::Transfer;
using cite_interfaces::msg::ResultCode;
using GripperCommand = control_msgs::action::GripperCommand;
using moveit::planning_interface::MoveGroupInterface;

//: How long to wait for the gripper controller, its acceptance, and its result.
constexpr std::chrono::seconds kGripperServerWait{10};
constexpr std::chrono::seconds kGripperAcceptWait{10};
constexpr std::chrono::seconds kGripperResultWait{20};
//: How often a wait on the gripper's result looks up to see whether the goal it
//: is serving has been cancelled. A poll period on a future, not a guess at how
//: long anything takes (P4).
constexpr std::chrono::milliseconds kCancelPollPeriod{20};
//: How long the goal thread waits for an accepted cancel to reach the goal
//: handle before reporting the result. Bounded, so a cancel that is never
//: completed cannot hold a goal open.
constexpr std::chrono::milliseconds kCancelHandshake{2000};

ResultCode make_result(uint8_t code, const std::string & detail = "")
{
  ResultCode result;
  result.code = code;
  result.detail = detail;
  return result;
}

double distance_between(
  const geometry_msgs::msg::Point & a, const geometry_msgs::msg::Point & b)
{
  const double dx = a.x - b.x;
  const double dy = a.y - b.y;
  const double dz = a.z - b.z;
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

/// The skill server for one arm.
class SkillServer : public rclcpp::Node
{
public:
  SkillServer()
  : Node("skill_server")
  {
    // Every one of these is supplied by the generated bring-up plan. A default
    // that silently works would hide a plan that failed to deliver it, so the
    // defaults are empty and `configure()` refuses to continue without them.
    declare_parameter("asset_id", "");
    declare_parameter("zone", "");
    declare_parameter("planning_group", "");
    declare_parameter("tip_link", "");
    declare_parameter("gripper_action", "");
    declare_parameter("home_rad", std::vector<double>{});
    declare_parameter("planning_time_s", 5.0);
    declare_parameter("planning_attempts", 10);
    declare_parameter("gripper_max_effort_n", 60.0);
    // The gripper's own units at each end of its travel, and the opening they
    // correspond to. GripperCommand.position is passed straight to the joint, so
    // for a revolute drive joint it is an ANGLE — a skill that sent a width in
    // metres would command a nearly-closed gripper when it meant fully open, and
    // nothing would report it because 0.085 is a perfectly valid angle.
    declare_parameter("gripper_open_position", 0.0);
    declare_parameter("gripper_closed_position", 0.85);
    // The linkage that converts between the two. The widest opening is derived
    // from these rather than declared beside them: it was declared once, as
    // 0.085, and disagreed with the mechanism's true 0.08893 for as long as it
    // existed.
    declare_parameter("gripper_drive_pivot_y_m", 0.035);
    declare_parameter("gripper_finger_offset_y_m", 0.035465);
    declare_parameter("gripper_finger_offset_z_m", 0.042039);
    declare_parameter("gripper_pad_inset_m", 0.026);
    // The rest of the same linkage, resolved along the tool axis instead of
    // across it: where the planning tip link is, where the drive pivot is, and
    // where on the finger the pad face is centred. Together with the two finger
    // offsets above they give `gripper_pad_plane_offset_m`, which is what lets
    // `Pick` and `Place` take an OBJECT pose rather than a tool pose.
    //
    // Three dimensions rather than the one constant the campaign quotes, for the
    // reason the widest opening is derived rather than declared: 0.0718988 is
    // their difference, and storing the difference alongside them is a second
    // place for one fact to live.
    declare_parameter("gripper_drive_pivot_z_m", 0.059098);
    declare_parameter("gripper_tip_link_z_m", 0.172);
    declare_parameter("gripper_pad_face_centre_z_m", 0.041003);
    // The gripper controller's own goal tolerance, carried here from the same L0
    // controller parameters that configure the controller. gripper_is_holding
    // needs it to size the margin that separates a real grasp from the position
    // bias the controller's own end-of-goal test produces.
    declare_parameter("gripper_goal_tolerance_rad", 0.01);
    // The drive joint's installed maximum rate, carried here under the name the
    // generated bring-up plan uses for it.
    //
    // THIS NODE DOES NOT ACT ON IT, and that is stated rather than left to be
    // inferred from the absence of a reader. The rate bounds the joint, and the
    // place a joint is bounded is its description: the generated
    // `*.urdf.xacro` takes the same L0 value as an argument, which is the path by
    // which the gripper actually moves at it. Nothing in L3 sequences on it, and
    // deriving a timeout from it here would be a second opinion about the same
    // number.
    //
    // It is declared because the plan delivers it. An override for a parameter a
    // node never declared is accepted by launch, dropped by rclcpp and reported
    // by neither — the exact failure mode that let `gripper_default_grasp_width_m`
    // and seven linkage dimensions never arrive while the node ran on compiled
    // defaults that happened to equal the L0 values. Declaring it makes the
    // delivered value land, and makes it readable with `ros2 param get`, so the
    // plan's gripper block and this node's parameter set are the same set rather
    // than two sets that agree by eleven twelfths.
    declare_parameter("gripper_max_drive_rate_rad_s", 1.0);
    // What `Pick.Goal.grasp_width_m == 0` resolves to — the end effector's
    // default grasp opening. Zero means "not supplied", which is a state the
    // skill reports rather than papers over.
    //
    // Named to match the key the generated bring-up plan carries, exactly as the
    // three values above are. Every other gripper value crosses that boundary
    // under one spelling; this one used to change name in transit, which is a
    // place for a delivery to fail silently and read as "no default configured".
    declare_parameter("gripper_default_grasp_width_m", 0.0);
    // How many seeds IK is tried from before a pose is called unreachable
    // (ADR-0026). Seed 0 is the arm's current state; the rest are random within
    // the joint limits, which is what recovers the choice of IK branch that a
    // pose goal would have had.
    declare_parameter("ik_seeds", 8);
    declare_parameter("current_state_timeout_s", 5.0);
    declare_parameter("tf_timeout_s", 5.0);
    declare_parameter("feedback_period_s", 0.1);
    // How far the tool backs out along its own axis once a `Transfer` has let go.
    //
    // A parameter rather than a goal field because `Transfer.action` has no
    // retreat distance in it and this change does not widen the contract (P3).
    // `Pick` and `Place` take theirs from the goal, so this is the one motion
    // distance in this node that is configuration rather than a caller's choice;
    // it is stated here so that it is at least stated once, and the bring-up plan
    // can override it the day L0 has an opinion about it.
    declare_parameter("transfer_retreat_distance_m", 0.10);
  }

  ~SkillServer() override
  {
    shutdown();
  }

  /// Read parameters and build the MoveIt client. Returns false with a reason.
  bool configure()
  {
    asset_id_ = get_parameter("asset_id").as_string();
    zone_ = get_parameter("zone").as_string();
    planning_group_ = get_parameter("planning_group").as_string();
    tip_link_ = get_parameter("tip_link").as_string();
    gripper_action_ = get_parameter("gripper_action").as_string();
    home_ = get_parameter("home_rad").as_double_array();

    for (const auto & [name, value] :
      {std::pair{"asset_id", asset_id_}, std::pair{"zone", zone_},
        std::pair{"planning_group", planning_group_}, std::pair{"tip_link", tip_link_}})
    {
      if (value.empty()) {
        RCLCPP_ERROR(
          get_logger(),
          "parameter '%s' is empty. Every name this node uses comes from the generated "
          "bring-up plan; an empty one means the plan did not deliver it, and guessing "
          "would put this arm's actions somewhere nothing looks.",
          name);
        return false;
      }
    }

    travel_.open_position = get_parameter("gripper_open_position").as_double();
    travel_.closed_position = get_parameter("gripper_closed_position").as_double();
    travel_.drive_pivot_y_m = get_parameter("gripper_drive_pivot_y_m").as_double();
    travel_.finger_offset_y_m = get_parameter("gripper_finger_offset_y_m").as_double();
    travel_.finger_offset_z_m = get_parameter("gripper_finger_offset_z_m").as_double();
    travel_.pad_inset_m = get_parameter("gripper_pad_inset_m").as_double();
    travel_.drive_pivot_z_m = get_parameter("gripper_drive_pivot_z_m").as_double();
    travel_.tip_link_z_m = get_parameter("gripper_tip_link_z_m").as_double();
    travel_.pad_face_centre_z_m = get_parameter("gripper_pad_face_centre_z_m").as_double();
    travel_.goal_tolerance = get_parameter("gripper_goal_tolerance_rad").as_double();
    if (cite_skills::gripper_max_width_m(travel_) <= 0.0) {
      RCLCPP_ERROR(
        get_logger(),
        "the gripper linkage yields a non-positive opening at open_position; without a "
        "usable linkage a task-space width cannot be mapped onto the gripper's own units");
      return false;
    }
    if (travel_.goal_tolerance <= 0.0) {
      RCLCPP_ERROR(
        get_logger(),
        "gripper_goal_tolerance_rad must be positive; it is what sizes the margin "
        "separating a real grasp from the controller's own end-of-goal position bias, "
        "and at zero every close in free air reports as holding");
      return false;
    }
    default_grasp_width_m_ = get_parameter("gripper_default_grasp_width_m").as_double();
    held_drive_position_.store(
      default_grasp_width_m_ > 0.0 ?
          cite_skills::gripper_position_for(default_grasp_width_m_, travel_) :
          travel_.closed_position);

    ik_seeds_ = static_cast<int>(get_parameter("ik_seeds").as_int());
    if (ik_seeds_ < 1) {
      RCLCPP_ERROR(
        get_logger(),
        "ik_seeds must be at least 1: every motion this node commands is planned to a "
        "joint configuration obtained from IK (ADR-0026), so zero seeds is a node that "
        "can never move");
      return false;
    }
    current_state_timeout_s_ = get_parameter("current_state_timeout_s").as_double();
    tf_timeout_s_ = get_parameter("tf_timeout_s").as_double();
    feedback_period_ = std::chrono::duration<double>(
      get_parameter("feedback_period_s").as_double());

    tf_buffer_ = std::make_shared<tf2_ros::Buffer>(get_clock());
    tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);
    return true;
  }

  /// Build the MoveIt interface and advertise. Separate from `configure()`
  /// because MoveGroupInterface needs this node already spinning.
  ///
  /// Returns false if MoveIt never became available, so bring-up stops with a
  /// diagnosis instead of a node that is up and silently useless.
  bool activate(const rclcpp::Node::SharedPtr & self)
  {
    // An explicit deadline. MoveGroupInterface's default is to wait forever for
    // move_group's servers, and a forever-wait is indistinguishable from a hang:
    // the node stays alive, advertises nothing, and the visible symptom is a
    // client timing out on an action that was never created.
    const auto deadline = rclcpp::Duration::from_seconds(120.0);

    // The namespace has to be passed explicitly. MoveGroupInterface::Options
    // carries its OWN move_group_namespace, and it defaults to the root — it
    // does not inherit the node's. Left at the default this node waits for
    // /move_action while move_group is serving
    // /cite/<zone>/<asset_id>/move_action, and the two never meet. The visible
    // symptom is a skill server that starts, loads its model and kinematics, and
    // then simply never advertises anything.
    const std::string move_group_namespace = get_effective_namespace();
    MoveGroupInterface::Options options(
      planning_group_, MoveGroupInterface::ROBOT_DESCRIPTION, move_group_namespace);

    try {
      move_group_ = std::make_shared<MoveGroupInterface>(
        self, options, tf_buffer_, deadline);
    } catch (const std::exception & error) {
      RCLCPP_ERROR(
        get_logger(),
        "MoveIt did not become available within %.0f s for group '%s' in namespace "
        "'%s': %s. move_group must be running in that namespace before this arm's "
        "skills can start.",
        deadline.seconds(), planning_group_.c_str(), move_group_namespace.c_str(),
        error.what());
      return false;
    }
    move_group_->setEndEffectorLink(tip_link_);
    move_group_->setPlanningTime(get_parameter("planning_time_s").as_double());
    move_group_->setNumPlanningAttempts(
      static_cast<unsigned int>(get_parameter("planning_attempts").as_int()));

    // The scaling factors MoveGroupInterface started with. They come from
    // `robot_description_planning.default_*_scaling_factor`, which the bring-up
    // plan hands this node out of the generated joint_limits.yaml — so the
    // default speed of this arm is stated in exactly one place (P1). Recorded
    // here because every goal resets to it: a factor set by one goal on a
    // long-lived MoveGroupInterface otherwise stays set for the next one, and
    // motion speed becomes a function of goal history.
    default_velocity_scaling_ = move_group_->getMaxVelocityScalingFactor();
    default_acceleration_scaling_ = move_group_->getMaxAccelerationScalingFactor();

    const auto model = move_group_->getRobotModel();
    const moveit::core::JointModelGroup * group =
      model != nullptr ? model->getJointModelGroup(planning_group_) : nullptr;
    if (group == nullptr) {
      RCLCPP_ERROR(
        get_logger(),
        "the robot model has no planning group '%s'. The group name comes from the "
        "generated bring-up plan and the SRDF comes from the same model, so a mismatch "
        "here means they were generated from different sources.",
        planning_group_.c_str());
      return false;
    }
    // Without a kinematics solver every skill fails at IK, one goal at a time,
    // with an error that names inverse kinematics rather than the missing
    // `robot_description_kinematics` parameter that caused it.
    if (!group->getSolverInstance()) {
      RCLCPP_ERROR(
        get_logger(),
        "planning group '%s' has no kinematics solver. Every motion this node commands "
        "is planned to a joint configuration obtained from IK (ADR-0026), so without a "
        "solver it can advertise skills but never move one.",
        planning_group_.c_str());
      return false;
    }
    // Checked here rather than on first use: a home configuration of the wrong
    // length leaves the previous target installed and the arm plans somewhere
    // unrelated, with no diagnostic anywhere.
    if (!home_.empty() && home_.size() != group->getVariableCount()) {
      RCLCPP_ERROR(
        get_logger(),
        "home_rad has %zu values but planning group '%s' has %u; the home configuration "
        "comes from the L0 model and the group from the generated SRDF, and the two "
        "disagree.",
        home_.size(), planning_group_.c_str(), group->getVariableCount());
      return false;
    }

    RCLCPP_INFO(
      get_logger(), "planning for group '%s' with end effector '%s' (planning frame '%s')",
      planning_group_.c_str(), tip_link_.c_str(), move_group_->getPlanningFrame().c_str());

    if (!gripper_action_.empty()) {
      gripper_client_ = rclcpp_action::create_client<GripperCommand>(self, gripper_action_);
    }

    move_to_server_ = rclcpp_action::create_server<MoveTo>(
      self, "move_to",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const MoveTo::Goal>) {
        return claim(uuid, "move_to");
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle) {
        start([this, handle] {execute_move_to(handle);});
      });

    grasp_server_ = rclcpp_action::create_server<Grasp>(
      self, "grasp",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Grasp::Goal>) {
        return claim(uuid, "grasp");
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>> handle) {
        start([this, handle] {execute_grasp(handle);});
      });

    place_server_ = rclcpp_action::create_server<Place>(
      self, "place",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Place::Goal>) {
        return claim(uuid, "place");
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>> handle) {
        start([this, handle] {execute_place(handle);});
      });

    pick_server_ = rclcpp_action::create_server<Pick>(
      self, "pick",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Pick::Goal>) {
        return claim(uuid, "pick");
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>> handle) {
        start([this, handle] {execute_pick(handle);});
      });

    transfer_server_ = rclcpp_action::create_server<Transfer>(
      self, "transfer",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Transfer::Goal>) {
        return claim(uuid, "transfer");
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Transfer>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Transfer>> handle) {
        start([this, handle] {execute_transfer(handle);});
      });

    RCLCPP_INFO(get_logger(), "skills for %s are accepting goals", asset_id_.c_str());
    return true;
  }

  /// Stop moving and let the goal thread finish, before anything is destroyed.
  ///
  /// `spin()` returns on SIGINT while a goal may still be inside `plan()`,
  /// `execute()` or `publish_feedback()`. Releasing the node under it is a
  /// use-after-free at every teardown — and one that would look exactly like the
  /// teardown noise the scenarios already tolerate for move_group, which is why
  /// it has to be joined rather than lived with.
  void shutdown()
  {
    if (shutting_down_.exchange(true)) {
      return;
    }
    abort_motion();

    std::thread worker;
    {
      const std::lock_guard<std::mutex> lock(worker_mutex_);
      worker = std::move(worker_);
    }
    if (worker.joinable()) {
      worker.join();
    }
  }

private:
  // ---------------------------------------------------------------------------
  // Goal admission: one arm, one skill at a time
  // ---------------------------------------------------------------------------
  rclcpp_action::GoalResponse claim(const rclcpp_action::GoalUUID & uuid, const char * skill)
  {
    if (shutting_down_.load()) {
      return rclcpp_action::GoalResponse::REJECT;
    }
    if (gate_.claim(uuid, skill)) {
      cancel_requested_.store(false);
      return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    }
    RCLCPP_WARN(
      get_logger(),
      "rejecting a '%s' goal: '%s' still holds this arm. One arm runs one skill at a "
      "time — a second goal would share this arm's planner and its trajectory with the "
      "first. The caller that abandoned the earlier goal has to cancel it.",
      skill, gate_.skill().c_str());
    return rclcpp_action::GoalResponse::REJECT;
  }

  /// Accept a cancellation only for the goal that actually holds the arm.
  ///
  /// `move_group->stop()` stops whatever is executing. A cancel that did not
  /// check whose goal it was would stop an unrelated skill's trajectory.
  template<typename Handle>
  rclcpp_action::CancelResponse cancel(const Handle & handle)
  {
    if (!gate_.owns(handle->get_goal_id())) {
      return rclcpp_action::CancelResponse::REJECT;
    }
    // Recorded as well as acted on. `is_canceling()` only becomes true once this
    // callback has returned, so a goal thread that looked only at the handle
    // could see its own motion stopped and report it as an execution failure.
    cancel_requested_.store(true);
    abort_motion();
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  /// Stop the arm and the gripper, whichever of them is moving.
  void abort_motion()
  {
    if (move_group_) {
      move_group_->stop();
    }
    rclcpp_action::ClientGoalHandle<GripperCommand>::SharedPtr gripper;
    {
      const std::lock_guard<std::mutex> lock(gripper_mutex_);
      gripper = gripper_goal_;
    }
    if (gripper && gripper_client_) {
      gripper_client_->async_cancel_goal(gripper);
    }
  }

  /// Run one goal on the node's single worker thread.
  ///
  /// Owned rather than detached: a detached thread cannot be waited for, and at
  /// teardown it outlives the node it holds a raw pointer to.
  template<typename Work>
  void start(Work work)
  {
    std::thread previous;
    {
      const std::lock_guard<std::mutex> lock(worker_mutex_);
      previous = std::move(worker_);
      worker_ = std::thread([this, work] {
            work();
            gate_.release();
      });
    }
    // The previous goal has already released the gate — otherwise this one would
    // have been rejected — so this join is the handshake that reaps its thread,
    // not a wait for it to finish its work.
    if (previous.joinable()) {
      previous.join();
    }
  }

  template<typename Handle>
  bool cancelled(const Handle & handle) const
  {
    return handle->is_canceling() || cancel_requested_.load() ||
           shutting_down_.load() || !rclcpp::ok();
  }

  /// Report a result on the goal handle, whatever state the process is in.
  ///
  /// At teardown the context may already be shut down, and a throw here would
  /// take the goal thread down with it and leave the client with nothing.
  template<typename Handle, typename Result>
  void terminate(
    const Handle & handle, const std::shared_ptr<Result> & result, const ResultCode & outcome)
  {
    try {
      if (outcome.code == ResultCode::SUCCESS) {
        handle->succeed(result);
      } else if (outcome.code == ResultCode::CANCELLED && wait_until_cancelling(handle)) {
        handle->canceled(result);
      } else {
        handle->abort(result);
      }
    } catch (const std::exception & error) {
      RCLCPP_WARN(get_logger(), "could not report a goal's result: %s", error.what());
    }
  }

  /// Wait for the cancel that is in progress to reach the goal handle.
  ///
  /// The state machine moves to CANCELING only after the cancel callback has
  /// returned, and the goal thread can get there first. Without this the result
  /// would be reported with `abort()` on a goal the caller cancelled.
  template<typename Handle>
  bool wait_until_cancelling(const Handle & handle)
  {
    if (!cancel_requested_.load()) {
      return false;
    }
    const auto deadline = std::chrono::steady_clock::now() + kCancelHandshake;
    while (!handle->is_canceling() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(kCancelPollPeriod);
    }
    return handle->is_canceling();
  }

  template<typename Handle, typename Feedback>
  void report_feedback(const Handle & handle, const std::shared_ptr<Feedback> & feedback)
  {
    try {
      handle->publish_feedback(feedback);
    } catch (const std::exception & error) {
      RCLCPP_WARN(get_logger(), "could not publish feedback: %s", error.what());
    }
  }

  // ---------------------------------------------------------------------------
  // MoveTo
  // ---------------------------------------------------------------------------
  void execute_move_to(const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<MoveTo::Result>();
    const auto started = now();

    // No requested Cartesian target means there is nothing to measure a position
    // error against. NaN says "not measured"; 0.0 would be a standing claim of
    // perfect accuracy, which is exactly what P8 forbids.
    result->position_error_m = std::numeric_limits<double>::quiet_NaN();

    const auto finish = [&](const ResultCode & outcome) {
        result->result = outcome;
        result->duration = now() - started;
        result->reached = current_pose();
        terminate(handle, result, outcome);
      };

    if (goal->cartesian_path) {
      // Refused rather than silently planned as a joint-space move. A straight
      // line is a continuum of poses, and on an arm whose reachable orientations
      // at a point form a measure-zero set almost none of the interpolated poses
      // has an IK solution (ADR-0026). A caller asking for a straight line along
      // a surface and receiving an arbitrary joint path would be receiving a
      // different, possibly colliding, motion.
      finish(make_result(
        ResultCode::NOT_IMPLEMENTED,
        "a straight-line Cartesian path is not implemented for this arm; see ADR-0026"));
      return;
    }

    apply_scaling(goal->velocity_scaling, goal->acceleration_scaling);

    if (!goal->named_configuration.empty()) {
      if (goal->named_configuration != "home") {
        finish(make_result(
          ResultCode::PRECONDITION_FAILED,
          "the only named configuration is 'home', which comes from the L0 model"));
        return;
      }
      if (home_.empty()) {
        finish(make_result(
          ResultCode::PRECONDITION_FAILED,
          "no home configuration was delivered for this arm"));
        return;
      }
      // Checked: on a size mismatch this returns false AND leaves the previous
      // target installed, so an unchecked call plans somewhere unrelated.
      if (!move_group_->setJointValueTarget(home_)) {
        finish(make_result(
          ResultCode::PRECONDITION_FAILED,
          "the home configuration was refused by the planning group; it is out of "
          "bounds or does not match the group's joints"));
        return;
      }

      MoveGroupInterface::Plan plan;
      if (move_group_->plan(plan) != moveit::core::MoveItErrorCode::SUCCESS) {
        finish(make_result(
          ResultCode::PLANNING_FAILED,
          "no path was found from the current state to the home configuration"));
        return;
      }
      finish(execute_plan(plan, handle, {}));
      return;
    }

    geometry_msgs::msg::PoseStamped target;
    const auto resolved = to_planning_frame(goal->target, &target);
    if (resolved.code != ResultCode::SUCCESS) {
      finish(resolved);
      return;
    }

    // Feedback comes from TF rather than from MoveGroupInterface: it is
    // published from a second thread while `execute()` blocks, and the planner
    // is not thread-safe. The tool's pose on /tf is the same fact from a source
    // that is.
    const auto publish_progress = [&](double fraction) {
        auto feedback = std::make_shared<MoveTo::Feedback>();
        feedback->fraction_complete = fraction;
        geometry_msgs::msg::PoseStamped current;
        if (tool_pose(&current)) {
          feedback->current = current;
          feedback->distance_remaining_m =
            distance_between(current.pose.position, target.pose.position);
        } else {
          feedback->distance_remaining_m = std::numeric_limits<double>::quiet_NaN();
        }
        report_feedback(handle, feedback);
      };

    const auto outcome = move_to_pose(target, handle, publish_progress);
    result->reached = current_pose();
    // Measured, not assumed: with a joint-space goal the residual is the IK
    // solver's, and P8 requires the number behind the claim.
    result->position_error_m =
      distance_between(result->reached.pose.position, target.pose.position);
    result->result = outcome;
    result->duration = now() - started;
    terminate(handle, result, outcome);
  }

  // ---------------------------------------------------------------------------
  // Grasp
  // ---------------------------------------------------------------------------
  void execute_grasp(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Grasp::Result>();

    const auto publish_progress = [&](double width_m, double effort_n) {
        auto feedback = std::make_shared<Grasp::Feedback>();
        feedback->current_width_m = width_m;
        feedback->current_effort_n = effort_n;
        report_feedback(handle, feedback);
      };

    const auto gripper = command_gripper(
      goal->width_m, goal->max_effort_n, handle, publish_progress);
    result->result = gripper.result;
    // What the gripper reached, not the request echoed back. The two differ by
    // exactly the object's width whenever it stalls on something, which is the
    // case a caller most needs to see.
    result->reached_width_m = gripper.reached_width_m;
    result->measured_effort_n = gripper.effort_n;
    result->holding = gripper.holding;

    if (gripper.result.code != ResultCode::SUCCESS) {
      terminate(handle, result, gripper.result);
      return;
    }

    // Closing on nothing is not a successful grasp. Without this the line would
    // carry an imaginary work-piece all the way to the next station and fail
    // there instead, which is much harder to attribute.
    if (goal->expect_object && !result->holding) {
      const auto outcome =
        make_result(ResultCode::EXECUTION_FAILED, describe_empty_grasp(gripper));
      result->result = outcome;
      terminate(handle, result, outcome);
      return;
    }

    holding_ = result->holding;
    terminate(handle, result, gripper.result);
  }

  // ---------------------------------------------------------------------------
  // Pick — approach, grasp, retreat
  // ---------------------------------------------------------------------------
  void execute_pick(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Pick::Result>();
    const auto started = now();

    const auto report = [&](uint8_t phase, double fraction) {
        auto feedback = std::make_shared<Pick::Feedback>();
        feedback->phase = phase;
        feedback->fraction_complete = fraction;
        report_feedback(handle, feedback);
      };

    const auto finish = [&](const ResultCode & outcome) {
        result->result = outcome;
        result->duration = now() - started;
        terminate(handle, result, outcome);
      };

    apply_scaling(0.0, 0.0);
    const double max_effort = get_parameter("gripper_max_effort_n").as_double();

    // The width is resolved before anything moves, because the pose planned to
    // depends on it: the pad face slides along the tool axis as the jaws close,
    // so where the tip link has to be put is a function of how wide the grasp is.
    const auto width = cite_skills::resolve_grasp_width(
      goal->grasp_width_m, default_grasp_width_m_);
    if (width.source == cite_skills::GraspWidthSource::Unknown) {
      // Not silent. `grasp_width_m == 0` means "use the object type's default",
      // and that default is L0 data this skill has not been given: no
      // `gripper_default_grasp_width_m` reached this node, and nothing here knows
      // what a work-piece is. Closing against the effort limit is what a parallel
      // gripper does with an unknown object, and it is said out loud rather than
      // presented as a resolved width.
      RCLCPP_WARN(
        get_logger(),
        "no grasp width for work-piece '%s': the goal left grasp_width_m at 0 and no "
        "gripper_default_grasp_width_m reached this node, so the gripper closes against "
        "its %.0f N effort limit. The end-effector type declares one; the bring-up plan "
        "carries it; check that the launch mechanism passes it through.",
        goal->workpiece_id.c_str(), max_effort);
    }

    // Open before approaching. Arriving at the object with a closed gripper is a
    // collision, and the planner has no way to know the gripper's state.
    report(Pick::Feedback::PHASE_PLANNING, 0.0);
    auto gripper = command_gripper(cite_skills::gripper_max_width_m(travel_), max_effort, handle);
    if (gripper.result.code != ResultCode::SUCCESS) {
      finish(gripper.result);
      return;
    }

    geometry_msgs::msg::PoseStamped grasp;
    const auto resolved = to_planning_frame(goal->object_pose, &grasp);
    if (resolved.code != ResultCode::SUCCESS) {
      finish(resolved);
      return;
    }
    // `object_pose` is where the OBJECT is, which the action has always said and
    // this skill did not do: it planned the tip link straight to it. The tip link
    // is the fingertip plane, so that parked the pad faces a stroke-dependent
    // distance above the object — 24.4 mm at the shipped grasp, which the 40-trial
    // campaign in `docs/measurements/2026-08-25-grasp-plane-offset/` measured
    // engaging half of a 37.5 mm pad face and rotating the work-piece past 20
    // degrees in 12 of 20 trials. Correcting it removed every one of them.
    //
    // Evaluated at the drive angle the RESOLVED WIDTH commands, not at the angle
    // the jaws are open to now: the arm holds still while the gripper closes, and
    // it is the closed configuration that has to be right. The part stops the
    // stroke a little wider than commanded, which leaves the pad centre 0.65 mm
    // high on the cell's 50 mm reference part. That residual cannot be removed
    // here, because the part's width is neither recorded in L0 nor carried by the
    // goal; against the 24.4 mm being corrected it is not the term that matters.
    //
    // Negative, because `offset_along_tool_z` stands OFF along the tool axis while
    // the pad plane sits proximal of the tip: the tip link has to go further in.
    const double pad_offset_m = cite_skills::gripper_pad_plane_offset_m(
      cite_skills::gripper_position_for(width.width_m, travel_), travel_);
    grasp.pose = cite_skills::offset_along_tool_z(grasp.pose, -pad_offset_m);

    report(Pick::Feedback::PHASE_APPROACHING, 0.2);
    auto approach = grasp;
    approach.pose = cite_skills::offset_along_tool_z(grasp.pose, goal->approach_distance_m);
    auto outcome = move_to_pose(approach, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      finish(outcome);
      return;
    }

    outcome = move_to_pose(grasp, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      finish(outcome);
      return;
    }
    result->grasp_pose = current_pose();

    report(Pick::Feedback::PHASE_GRASPING, 0.6);
    gripper = command_gripper(width.width_m, max_effort, handle);
    if (gripper.result.code != ResultCode::SUCCESS) {
      finish(gripper.result);
      return;
    }
    if (!gripper.holding) {
      finish(make_result(ResultCode::EXECUTION_FAILED, describe_empty_grasp(gripper)));
      return;
    }
    result->holding = true;
    holding_ = true;

    report(Pick::Feedback::PHASE_RETREATING, 0.8);
    auto retreat = result->grasp_pose;
    retreat.pose = cite_skills::offset_along_world_z(
      result->grasp_pose.pose, goal->retreat_distance_m);
    outcome = move_to_pose(retreat, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      // Still holding: report it so L4 knows the work-piece's owner.
      finish(outcome);
      return;
    }

    report(Pick::Feedback::PHASE_RETREATING, 1.0);
    finish(make_result(ResultCode::SUCCESS));
  }

  // ---------------------------------------------------------------------------
  // Place — approach, release, retreat
  // ---------------------------------------------------------------------------
  void execute_place(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Place::Result>();
    const auto started = now();

    const auto report = [&](uint8_t phase, double fraction) {
        auto feedback = std::make_shared<Place::Feedback>();
        feedback->phase = phase;
        feedback->fraction_complete = fraction;
        report_feedback(handle, feedback);
      };

    const auto finish = [&](const ResultCode & outcome) {
        result->result = outcome;
        result->duration = now() - started;
        terminate(handle, result, outcome);
      };

    // Miming a place with an empty gripper would leave the line believing a
    // work-piece arrived somewhere it never did — and the failure would surface
    // at the next station, which is much harder to attribute.
    if (goal->require_holding && !holding_) {
      finish(make_result(
        ResultCode::PRECONDITION_FAILED,
        "asked to place, but the gripper is not holding anything"));
      return;
    }

    apply_scaling(0.0, 0.0);
    const double max_effort = get_parameter("gripper_max_effort_n").as_double();

    report(Place::Feedback::PHASE_PLANNING, 0.0);
    geometry_msgs::msg::PoseStamped release;
    const auto resolved = to_planning_frame(goal->target_pose, &release);
    if (resolved.code != ResultCode::SUCCESS) {
      finish(resolved);
      return;
    }
    // `target_pose` is where the OBJECT should end up, and the object is between
    // the pads — not at the fingertip plane the planner drives. Same correction
    // as `Pick`, and it has to be here too: `Place` plans to the same tip link,
    // so leaving it out would release the work-piece a stroke-dependent distance
    // from where the caller asked for it, in the same direction and by the same
    // amount that miscentred every grasp.
    //
    // Evaluated at the angle the jaws are ACTUALLY at rather than at a commanded
    // one, because here that is known: the part stopped the stroke during the
    // pick and `held_drive_position_` recorded where. Unlike `Pick`, this leaves
    // no residual.
    const double pad_offset_m =
      cite_skills::gripper_pad_plane_offset_m(held_drive_position_.load(), travel_);
    release.pose = cite_skills::offset_along_tool_z(release.pose, -pad_offset_m);

    auto approach = release;
    approach.pose = cite_skills::offset_along_tool_z(release.pose, goal->approach_distance_m);
    auto outcome = move_to_pose(approach, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      finish(outcome);
      return;
    }

    report(Place::Feedback::PHASE_APPROACHING, 0.4);
    outcome = move_to_pose(release, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      finish(outcome);
      return;
    }
    result->release_pose = current_pose();

    report(Place::Feedback::PHASE_RELEASING, 0.7);
    const auto gripper =
      command_gripper(cite_skills::gripper_max_width_m(travel_), max_effort, handle);
    if (gripper.result.code != ResultCode::SUCCESS) {
      finish(gripper.result);
      return;
    }
    holding_ = false;

    report(Place::Feedback::PHASE_RETREATING, 0.9);
    auto retreat = result->release_pose;
    retreat.pose = cite_skills::offset_along_world_z(
      result->release_pose.pose, goal->retreat_distance_m);
    outcome = move_to_pose(retreat, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      finish(outcome);
      return;
    }

    report(Place::Feedback::PHASE_RETREATING, 1.0);
    finish(make_result(ResultCode::SUCCESS));
  }

  // ---------------------------------------------------------------------------
  // Transfer — carry a held work-piece to a handoff pose, let go, back out
  //
  // Half of a handoff, and deliberately only half (ADR-0024). L4 owns ownership:
  // it holds the single owner of each work-piece, performs the two-party
  // confirmation, and arbitrates the shared volume. This owns the motion for one
  // robot, takes an opaque token rather than a peer's identity, and never learns
  // whether anything is on the other side. A skill never talks to another skill.
  //
  // ## What this skill assumes about how the part is held, which is a real
  // ## assumption and not a formality
  //
  // A handoff needs to know how a part is held, not only that it is. In this cell
  // that is not knowable. Under friction grasping (ADR-0029) the work-piece
  // rotates between the jaws about the pad-to-pad axis while the pads themselves
  // turn 0.14 degrees. Correcting the grasp-plane offset removed every rotation
  // above 20 degrees — 12/20 trials became 0/20 — but a residual of up to
  // **18.71 degrees**, median 7.97, survives it and is a recorded open sim/real
  // divergence. See `docs/measurements/2026-08-25-grasp-plane-offset/ANALYSIS.md`
  // and ADR-0029's "what we will have to revisit", which names this skill.
  //
  // `Transfer` is built anyway, and this is the reasoning, so that whoever finds
  // this later can judge it rather than re-derive it:
  //
  // 1. **It claims nothing it cannot measure.** `Transfer.Result` carries a code,
  //    `still_holding` and a duration — no achieved pose, no error term. There is
  //    no field here that a residual would make into a false number, which is
  //    exactly the trap `MoveTo.position_error_m` fell into when it shipped a
  //    permanent 0.0.
  // 2. **The position half is known.** Where the part sits along the tool axis
  //    comes from the drive angle the jaws actually stopped at, the same
  //    mechanism `Place` already uses, and the campaign measured the pad centre
  //    0.2 mm from the part's centre of mass with the full face engaged.
  // 3. **The unknown is orientation about the pad-to-pad axis, and it matters
  //    only to whatever re-acquires the part** — a receiving `Pick`, or a
  //    fixture. It does not affect this skill's own motion.
  //
  // **So the standing assumption is: the work-piece is symmetric about the
  // pad-to-pad axis over the residual, or it is delivered onto a fixture that
  // re-datums it.** The cell's reference part is a 50 mm cube, which is symmetric
  // under 90-degree rotations about that axis and therefore tolerates 18.71
  // degrees only in the sense that no orientation is being relied upon. The day a
  // non-symmetric part arrives — anything keyed, polarised, or needing to be
  // presented a particular way up — **this assumption is false and this skill
  // will deliver it wrong by up to 18.71 degrees without reporting anything.**
  // That is stated in the result's `detail` on every success, because a caveat
  // nobody reads is a caveat that does not exist.
  //
  // The gap is not closed here. L3's own document requires whoever writes this to
  // "close this gap first or state plainly that they have not", and this states
  // plainly that it has not.
  // ---------------------------------------------------------------------------

  //: The residual rotation a friction grasp leaves in the work-piece's
  //: orientation about the pad-to-pad axis, in degrees. The maximum over the
  //: 20-trial corrected condition, not the median, because it is the bound that a
  //: consumer would have to tolerate.
  static constexpr double kHeldOrientationResidualDeg = 18.71;

  void execute_transfer(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Transfer>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Transfer::Result>();
    const auto started = now();

    const auto report = [&](uint8_t phase) {
        auto feedback = std::make_shared<Transfer::Feedback>();
        feedback->phase = phase;
        feedback->waited = now() - started;
        report_feedback(handle, feedback);
      };

    const auto finish = [&](const ResultCode & outcome) {
        result->result = outcome;
        // Read at every exit rather than set on the success path, so that a
        // cancel, a planning failure and a refusal all report the truth about who
        // has the work-piece. `still_holding` is the field L4 chooses a recovery
        // from: wrong here, the line either abandons a part it still holds or
        // goes looking for one it let go of.
        result->still_holding = holding_.load();
        result->duration = now() - started;
        terminate(handle, result, outcome);
      };

    // An unnegotiated handoff is refused. The token is opaque to this layer —
    // nothing here reads it, matches it, or expires it, which is ADR-0024's whole
    // point — but its ABSENCE is meaningful: L4 issues one for every handoff it
    // has negotiated, so an empty token is a caller that skipped the two-party
    // confirmation. Releasing a work-piece into a rendezvous nobody agreed to is
    // how a part ends up on the floor between two arms.
    if (goal->rendezvous_token.empty()) {
      finish(make_result(
        ResultCode::PRECONDITION_FAILED,
        "no rendezvous token: a handoff is negotiated by L4 (ADR-0024) and this skill "
        "will not release a work-piece into a rendezvous that was never confirmed"));
      return;
    }

    // Carrying nothing to a handoff pose and opening the jaws is a handoff the
    // line believes happened. `Place` refuses the same way and for the same
    // reason: the failure would otherwise surface at the receiving station, which
    // is much harder to attribute.
    if (!holding_.load()) {
      finish(make_result(
        ResultCode::PRECONDITION_FAILED,
        "asked to transfer work-piece '" + goal->workpiece_id +
          "', but this arm is not holding anything"));
      return;
    }

    // -------------------------------------------------------------------------
    // The peer-release wait, and why it is refused rather than faked
    //
    // ADR-0024 has this skill "signal ready, hold position until released, then
    // retreat", and `hold_timeout` is contracted to expire with the piece still
    // held. Both need L4 to tell this arm that the peer has taken the part.
    //
    // **There is no typed channel for that signal.** `cite_interfaces` has six
    // actions, fourteen messages and two services, and none of them carries a
    // rendezvous release; `LineState` and `StationState` publish ownership
    // nowhere. Inventing one is not this change's to make — the interface package
    // is reviewed before its consumers (ADR-0010) — and improvising an untyped
    // one would be P3 twice over.
    //
    // So a caller asking for the hold is told, in a code it can branch on, that
    // the path is unbuilt. It is told BEFORE the arm moves: parking a loaded arm
    // at a rendezvous it can never complete is a worse failure than refusing.
    //
    // What is NOT done here is a bounded wait that expires and reports TIMEOUT.
    // That is the contract's own defined outcome and it would look completely
    // correct — a handoff that waited and was not met — while nothing was ever
    // listening. That is v1's handoff exactly: it published to a topic nothing
    // subscribed to and every transaction timed out forever, with no test able to
    // notice. A TIMEOUT here would be the same lie with a passing test beside it.
    // -------------------------------------------------------------------------
    const rclcpp::Duration hold_timeout(goal->hold_timeout);
    if (hold_timeout > rclcpp::Duration(0, 0)) {
      report(Transfer::Feedback::PHASE_WAITING_FOR_PEER);
      finish(make_result(
        ResultCode::NOT_IMPLEMENTED,
        "a hold_timeout of " + std::to_string(hold_timeout.seconds()) +
          " s asks this arm to hold at the handoff pose until a peer takes the "
          "work-piece, and no typed channel exists for L4 to signal that release "
          "(ADR-0024). The arm has not moved and is still holding. Send "
          "hold_timeout = 0 for a conveyor-mediated transfer, where the two-party "
          "confirmation has already happened before this goal was sent"));
      return;
    }

    apply_scaling(0.0, 0.0);
    const double max_effort = get_parameter("gripper_max_effort_n").as_double();

    report(Transfer::Feedback::PHASE_PLANNING);
    geometry_msgs::msg::PoseStamped handoff;
    const auto resolved = to_planning_frame(goal->handoff_pose, &handoff);
    if (resolved.code != ResultCode::SUCCESS) {
      finish(resolved);
      return;
    }
    // `handoff_pose` is where the WORK-PIECE should be presented, not where the
    // tip link should go — the same reading `Pick` and `Place` give their poses,
    // and it has to be the same one, because the receiving robot runs `Pick` at
    // this very pose (ADR-0024). If one side of a handoff meant the object and
    // the other meant the fingertip plane, the two would miss each other by the
    // pad-plane offset — 18.6 mm at the cell's grasp width — and the part would
    // be handed to a gripper closing above it.
    //
    // Evaluated at the angle the jaws are actually at, which here is known: the
    // part stopped the stroke during the pick and `held_drive_position_` recorded
    // where. Same as `Place`, and it leaves no residual in position.
    const double pad_offset_m =
      cite_skills::gripper_pad_plane_offset_m(held_drive_position_.load(), travel_);
    handoff.pose = cite_skills::offset_along_tool_z(handoff.pose, -pad_offset_m);

    report(Transfer::Feedback::PHASE_APPROACHING);
    auto outcome = move_to_pose(handoff, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      // Still holding, and `finish` reports it. A failed approach leaves
      // ownership exactly where it was, which is what lets L4 retry.
      finish(outcome);
      return;
    }
    const auto release_pose = current_pose();

    report(Transfer::Feedback::PHASE_RELEASING);
    const auto gripper =
      command_gripper(cite_skills::gripper_max_width_m(travel_), max_effort, handle);
    if (gripper.result.code != ResultCode::SUCCESS) {
      // The jaws did not open, so the part is still between them. Reported as
      // held rather than as transferred: L4's recovery for a stuck gripper and
      // its recovery for a completed handoff are opposites.
      finish(gripper.result);
      return;
    }
    holding_.store(false);

    report(Transfer::Feedback::PHASE_RETREATING);
    // Backed out along the tool's own axis, not lifted in world Z as `Pick` and
    // `Place` retreat. The hazard is different and so is the safe direction:
    // after a pick the danger is the surface the part was resting on, which is
    // below, but after a handoff the danger is the peer and the work-piece it now
    // holds, which are along the tool axis. Lifting straight up out of a
    // rendezvous drags the jaws through the space the receiving gripper is in.
    auto retreat = release_pose;
    retreat.pose = cite_skills::offset_along_tool_z(
      release_pose.pose, get_parameter("transfer_retreat_distance_m").as_double());
    outcome = move_to_pose(retreat, handle, {});
    if (outcome.code != ResultCode::SUCCESS) {
      // The part is transferred either way — the jaws are open and it is not this
      // arm's any more. A failed retreat is an arm parked in the rendezvous, not
      // a failed handoff, and `still_holding` false is what tells L4 which.
      finish(outcome);
      return;
    }

    // The caveat rides on the success, where a reader will actually meet it.
    // `detail` is for people and nothing may parse it, which is exactly right
    // for a bound that is real, unmeasured per-goal, and not expressible in any
    // field this contract has.
    std::ostringstream note;
    note.setf(std::ios::fixed);
    note.precision(2);
    note << "transferred work-piece '" << goal->workpiece_id
         << "'. Position is corrected for the grasp plane; ORIENTATION IS NOT KNOWN — a "
      "friction grasp leaves up to " << kHeldOrientationResidualDeg
         << " degrees of unmeasured rotation about the pad-to-pad axis (ADR-0029). This "
      "is sound only for a part symmetric over that residual, or one delivered onto a "
      "fixture that re-datums it";
    finish(make_result(ResultCode::SUCCESS, note.str()));
  }

  // ---------------------------------------------------------------------------
  // Motion
  // ---------------------------------------------------------------------------
  using ProgressFn = std::function<void(double)>;

  /// Resolve a requested pose into the frame the planner works in.
  ResultCode to_planning_frame(
    const geometry_msgs::msg::PoseStamped & requested,
    geometry_msgs::msg::PoseStamped * resolved) const
  {
    try {
      *resolved = tf_buffer_->transform(
        requested, move_group_->getPlanningFrame(), tf2::durationFromSec(tf_timeout_s_));
    } catch (const std::exception & error) {
      return make_result(
        ResultCode::PRECONDITION_FAILED,
        "the target is in frame '" + requested.header.frame_id +
          "', which TF could not resolve into the planning frame '" +
          move_group_->getPlanningFrame() + "': " + error.what());
    }
    return make_result(ResultCode::SUCCESS);
  }

  /// Move the tool to a pose (ADR-0026).
  ///
  /// The pose is never handed to the planner as a goal. IK is solved on the
  /// exact pose and the planner is given the joint configuration that came out,
  /// because a pose goal is satisfied by drawing random poses from inside its
  /// tolerance, and on this arm almost every draw tilts the tool out of the
  /// plane its three parallel pitch joints live in and has no IK solution at all.
  template<typename Handle>
  ResultCode move_to_pose(
    const geometry_msgs::msg::PoseStamped & target, const Handle & handle,
    const ProgressFn & on_progress)
  {
    const auto state = move_group_->getCurrentState(current_state_timeout_s_);
    if (!state) {
      return make_result(
        ResultCode::PRECONDITION_FAILED,
        "the arm's joint state has not arrived, so there is no seed for IK and no start "
        "state to plan from");
    }
    const moveit::core::JointModelGroup * group = state->getJointModelGroup(planning_group_);
    if (group == nullptr) {
      return make_result(
        ResultCode::PRECONDITION_FAILED,
        "the robot model has no planning group '" + planning_group_ + "'");
    }

    moveit::core::RobotState solution(*state);
    MoveGroupInterface::Plan plan;
    cite_skills::PoseGoalAttempts attempts;

    const auto failure = cite_skills::plan_to_pose(
      ik_seeds_,
      [&](int seed) {
        // Seed 0 is where the arm stands, so the branch chosen is the one
        // nearest the current configuration. The rest are random within the
        // joint limits: a joint-space goal commits to one IK branch, and this is
        // what recovers the choice among branches that a pose goal had.
        if (seed == 0) {
          solution = *state;
        } else {
          solution.setToRandomPositions(group);
        }
        // A zero timeout means the solver's own configured timeout, which comes
        // from the generated kinematics.yaml.
        return solution.setFromIK(group, target.pose, tip_link_, 0.0);
      },
      [&] {
        if (!move_group_->setJointValueTarget(solution)) {
          RCLCPP_WARN(
            get_logger(),
            "discarding an IK solution that falls outside the joint limits");
          return false;
        }
        return move_group_->plan(plan) == moveit::core::MoveItErrorCode::SUCCESS;
      },
      [&] {return cancelled(handle);}, &attempts);

    switch (failure) {
      case cite_skills::PoseGoalFailure::None:
        break;
      case cite_skills::PoseGoalFailure::Cancelled:
        return make_result(ResultCode::CANCELLED, "cancelled before execution began");
      case cite_skills::PoseGoalFailure::NoIkSolution:
        // `UNREACHABLE`, NOT `PLANNING_FAILED`, and the difference is the whole
        // point of the code existing. `ResultCode.msg` says why: no IK solution
        // exists for this pose at all, so the remedy is to move the station or
        // re-reach the pose, not to clear an obstacle. L4's recovery policy
        // ESCALATEs this one and RETRY_DIFFERENTLYs a planning failure, so
        // sending the wrong one spends a station's whole retry budget resending
        // a pose no IK branch can reach.
        //
        // No local alias stands between this line and the constant. There was
        // one, pointing at `PLANNING_FAILED` while the constant it described did
        // not yet exist; the constant landed and the alias did not move, and
        // nothing failed. Naming the constant directly is what makes its absence
        // a compile error rather than a comment that quietly stopped being true.
        return make_result(
          ResultCode::UNREACHABLE,
          "this arm cannot reach the requested pose: inverse kinematics found no "
          "solution from any of " + std::to_string(attempts.seeds_tried) +
            " seeds. This is a reachability or degrees-of-freedom failure, not an "
            "obstacle");
      case cite_skills::PoseGoalFailure::NoPlan:
        return make_result(
          ResultCode::PLANNING_FAILED,
          "inverse kinematics reached the requested pose (" +
            std::to_string(attempts.branches_planned) +
            " configuration(s) tried) but the planner found no path to any of them from "
            "where the arm stands");
    }

    return execute_plan(plan, handle, on_progress);
  }

  template<typename Handle>
  ResultCode execute_plan(
    const MoveGroupInterface::Plan & plan, const Handle & handle,
    const ProgressFn & on_progress)
  {
    if (cancelled(handle)) {
      return make_result(ResultCode::CANCELLED, "cancelled before execution began");
    }

    // Progress is reported from a second thread because `execute()` blocks until
    // the trajectory finishes. The period is a publication RATE — nothing is
    // sequenced by it, and the motion's completion is still an event (P4).
    std::atomic<bool> running{true};
    std::thread reporter;
    if (on_progress) {
      const auto & points = plan.trajectory.joint_trajectory.points;
      const double total =
        points.empty() ? 0.0 : rclcpp::Duration(points.back().time_from_start).seconds();
      const auto started = now();
      reporter = std::thread([this, &running, total, started, &on_progress] {
            while (running.load()) {
              const double elapsed = (now() - started).seconds();
              on_progress(total > 0.0 ? std::min(1.0, elapsed / total) : 0.0);
              std::this_thread::sleep_for(
            std::chrono::duration_cast<std::chrono::milliseconds>(feedback_period_));
            }
      });
    }

    const auto executed = move_group_->execute(plan);
    running.store(false);
    if (reporter.joinable()) {
      reporter.join();
    }
    if (on_progress) {
      on_progress(1.0);
    }

    if (cancelled(handle)) {
      return make_result(ResultCode::CANCELLED, "cancelled during execution");
    }
    if (executed != moveit::core::MoveItErrorCode::SUCCESS) {
      // MoveIt's own code, carried through. "The controller did not complete the
      // trajectory" covers a controller that refused the goal, one that timed
      // out, and one that finished outside tolerance, and telling them apart
      // from the text alone cost a whole investigation.
      return make_result(
        ResultCode::EXECUTION_FAILED,
        "the controller did not complete the planned trajectory (MoveIt error code " +
          std::to_string(executed.val) + ")");
    }
    return make_result(ResultCode::SUCCESS);
  }

  void apply_scaling(double velocity, double acceleration)
  {
    // Both factors are set at the start of every goal, never left as the last
    // goal's. They live on the long-lived MoveGroupInterface, so a goal that
    // asked for 10% used to leave every later goal at 10% — motion speed as a
    // function of goal history. Zero still means "the configured default", which
    // is now what it actually gets.
    move_group_->setMaxVelocityScalingFactor(
      velocity > 0.0 ? velocity : default_velocity_scaling_);
    move_group_->setMaxAccelerationScalingFactor(
      acceleration > 0.0 ? acceleration : default_acceleration_scaling_);
  }

  // ---------------------------------------------------------------------------
  // Gripper
  // ---------------------------------------------------------------------------
  struct GripperOutcome
  {
    ResultCode result;
    bool holding{false};
    double reached_width_m{0.0};
    double effort_n{0.0};
    // Kept so that a failure can quote the numbers it was decided on. A grasp
    // that reports "nothing was picked up" without saying what it commanded and
    // what came back sends the next reader to the simulator to find out (P8).
    double commanded_width_m{0.0};
    bool stalled{false};
    bool reached_goal{false};
  };

  /// Why a close ended up holding nothing, in the numbers it was judged on.
  ///
  /// The two cases fail for opposite reasons and are fixed in opposite
  /// directions, so telling them apart here saves the reader a simulation run.
  static std::string describe_empty_grasp(const GripperOutcome & gripper)
  {
    std::ostringstream message;
    message.setf(std::ios::fixed);
    message.precision(1);
    message << "nothing was picked up: commanded " << gripper.commanded_width_m * 1000.0
            << " mm, reached " << gripper.reached_width_m * 1000.0 << " mm, stalled="
            << (gripper.stalled ? "true" : "false") << ". ";
    if (gripper.reached_goal) {
      message << "The gripper arrived where it was sent, so nothing was between the "
        "pads to stop it — either the work-piece was not there, or the "
        "commanded width is wider than the part. A grasp is evidenced by "
        "FAILING to reach the command, so the width must be narrower than the "
        "object it closes on";
    } else {
      message << "The gripper stopped short of its command, but not by enough width to "
        "be a part: a close that ends within the controller's own goal "
        "tolerance reports a little more width than it actually reached, and "
        "that phantom margin is what this rejects. Either nothing was between "
        "the pads, or the gripper jammed or fouled its own fingers";
    }
    return message.str();
  }

  using GripperProgressFn = std::function<void(double, double)>;

  template<typename Handle>
  GripperOutcome command_gripper(
    double width_m, double max_effort_n, const Handle & handle,
    const GripperProgressFn & on_progress = {})
  {
    GripperOutcome outcome;
    if (!gripper_client_) {
      outcome.result = make_result(
        ResultCode::NOT_IMPLEMENTED, "this arm has no gripper action configured");
      return outcome;
    }
    if (!gripper_client_->wait_for_action_server(kGripperServerWait)) {
      outcome.result = make_result(
        ResultCode::PRECONDITION_FAILED,
        "the gripper controller's action server is not available");
      return outcome;
    }

    GripperCommand::Goal goal;
    goal.command.position = cite_skills::gripper_position_for(width_m, travel_);
    goal.command.max_effort = max_effort_n;

    rclcpp_action::Client<GripperCommand>::SendGoalOptions options;
    if (on_progress) {
      const auto travel = travel_;
      options.feedback_callback =
        [on_progress, travel](
        rclcpp_action::ClientGoalHandle<GripperCommand>::SharedPtr,
        const std::shared_ptr<const GripperCommand::Feedback> feedback) {
          on_progress(cite_skills::gripper_width_for(feedback->position, travel),
                      feedback->effort);
        };
    }

    auto future = gripper_client_->async_send_goal(goal, options);
    if (future.wait_for(kGripperAcceptWait) != std::future_status::ready) {
      outcome.result = make_result(
        ResultCode::TIMEOUT, "the gripper never accepted the command");
      return outcome;
    }
    auto gripper_handle = future.get();
    if (!gripper_handle) {
      outcome.result = make_result(
        ResultCode::EXECUTION_FAILED, "the gripper rejected the command");
      return outcome;
    }

    {
      const std::lock_guard<std::mutex> lock(gripper_mutex_);
      gripper_goal_ = gripper_handle;
    }

    auto result_future = gripper_client_->async_get_result(gripper_handle);
    // Waited on in slices rather than in one block, so that a cancellation
    // reaches the gripper rather than being noticed after it has finished. A
    // Grasp that accepted a cancel and then ran to completion is a Grasp that
    // cannot be cancelled at all.
    const auto deadline = std::chrono::steady_clock::now() + kGripperResultWait;
    bool requested_cancel = false;
    std::future_status status = std::future_status::timeout;
    while (true) {
      status = result_future.wait_for(kCancelPollPeriod);
      if (status == std::future_status::ready) {
        break;
      }
      if (!requested_cancel && cancelled(handle)) {
        gripper_client_->async_cancel_goal(gripper_handle);
        requested_cancel = true;
      }
      if (std::chrono::steady_clock::now() >= deadline) {
        break;
      }
    }

    {
      const std::lock_guard<std::mutex> lock(gripper_mutex_);
      gripper_goal_.reset();
    }

    if (status != std::future_status::ready) {
      outcome.result = make_result(
        ResultCode::TIMEOUT, "the gripper never reported a result");
      return outcome;
    }

    const auto wrapped = result_future.get();
    if (wrapped.result) {
      // A stall is reported by the controller and judged here, which is the split
      // ADR-0022 fixes. `stalled` alone used to stand in for "holding", and it
      // cannot: it says the joint stopped short of its command, not what stopped
      // it. gripper_is_holding adds the question that distinguishes a part from a
      // jam — did it stop on the OPEN side of the width we asked for.
      outcome.reached_width_m =
        cite_skills::gripper_width_for(wrapped.result->position, travel_);
      outcome.effort_n = wrapped.result->effort;
      outcome.commanded_width_m = width_m;
      outcome.stalled = wrapped.result->stalled;
      outcome.reached_goal = wrapped.result->reached_goal;
      outcome.holding = cite_skills::gripper_is_holding(
        {width_m, wrapped.result->position, outcome.stalled, outcome.reached_goal}, travel_);
      if (outcome.holding) {
        // Where the jaws actually stopped, kept for `Place`. The pad face sits a
        // stroke-dependent distance back up the tool axis, so releasing an object
        // *where the caller asked for it* needs the angle the part is held at —
        // and that angle is not the commanded one, because the part is what
        // stopped the stroke. Stored as the drive position rather than as an
        // offset in metres, so the linkage stays the only thing that converts
        // between the two (P1).
        held_drive_position_.store(wrapped.result->position);
      }

      RCLCPP_INFO(
        get_logger(),
        "gripper: commanded %.1f mm, reached %.1f mm, stalled=%s, reached_goal=%s, "
        "effort=%.1f -> %s",
        width_m * 1000.0, outcome.reached_width_m * 1000.0,
        outcome.stalled ? "true" : "false", outcome.reached_goal ? "true" : "false",
        outcome.effort_n, outcome.holding ? "holding" : "empty");
    }

    if (wrapped.code == rclcpp_action::ResultCode::CANCELED ||
      wrapped.code == rclcpp_action::ResultCode::ABORTED)
    {
      outcome.result = wrapped.code == rclcpp_action::ResultCode::CANCELED ?
        make_result(ResultCode::CANCELLED, "the gripper command was cancelled") :
        make_result(
                             ResultCode::EXECUTION_FAILED,
                             "the gripper controller aborted the command");
      return outcome;
    }

    outcome.result = make_result(ResultCode::SUCCESS);
    return outcome;
  }

  // ---------------------------------------------------------------------------
  // Where the tool is
  // ---------------------------------------------------------------------------
  geometry_msgs::msg::PoseStamped current_pose()
  {
    return move_group_->getCurrentPose(tip_link_);
  }

  /// The tool's pose from TF, which — unlike MoveGroupInterface — may be read
  /// while a motion is executing.
  bool tool_pose(geometry_msgs::msg::PoseStamped * pose) const
  {
    try {
      const auto transform = tf_buffer_->lookupTransform(
        move_group_->getPlanningFrame(), tip_link_, tf2::TimePointZero);
      pose->header = transform.header;
      pose->pose.position.x = transform.transform.translation.x;
      pose->pose.position.y = transform.transform.translation.y;
      pose->pose.position.z = transform.transform.translation.z;
      pose->pose.orientation = transform.transform.rotation;
      return true;
    } catch (const std::exception &) {
      return false;
    }
  }

  std::string asset_id_;
  std::string zone_;
  std::string planning_group_;
  std::string tip_link_;
  std::string gripper_action_;
  std::vector<double> home_;

  //: Whether this arm believes it is holding a work-piece. Set by Pick and Grasp,
  //: cleared by Place. It is the arm's own belief, not the line's record — L4
  //: owns ownership (ADR-0024); this exists only so Place can refuse to mime one.
  std::atomic<bool> holding_{false};

  cite_skills::GripperTravel travel_;
  double default_grasp_width_m_{0.0};

  //: The drive-joint position the gripper last closed to while holding something.
  //: `Place` reads it to work out where the pad face — and therefore the object —
  //: is relative to the tip link it plans to.
  //:
  //: Initialised in `configure` to the position the default grasp width commands,
  //: which is only ever the value used when a caller places with
  //: `require_holding` false and an empty gripper. That is a mimed place; the
  //: number then describes where a part would have been rather than where one is,
  //: and nothing is holding it to be wrong about.
  std::atomic<double> held_drive_position_{0.0};

  int ik_seeds_{8};
  double current_state_timeout_s_{5.0};
  double tf_timeout_s_{5.0};
  std::chrono::duration<double> feedback_period_{0.1};
  double default_velocity_scaling_{1.0};
  double default_acceleration_scaling_{1.0};

  //: One goal at a time, and cancellation addressed to the goal that owns the arm.
  cite_skills::ExclusiveGoal<rclcpp_action::GoalUUID> gate_;
  std::mutex worker_mutex_;
  std::thread worker_;
  std::atomic<bool> shutting_down_{false};

  std::atomic<bool> cancel_requested_{false};

  std::mutex gripper_mutex_;
  rclcpp_action::ClientGoalHandle<GripperCommand>::SharedPtr gripper_goal_;

  std::shared_ptr<MoveGroupInterface> move_group_;
  rclcpp_action::Client<GripperCommand>::SharedPtr gripper_client_;
  rclcpp_action::Server<MoveTo>::SharedPtr move_to_server_;
  rclcpp_action::Server<Grasp>::SharedPtr grasp_server_;
  rclcpp_action::Server<Pick>::SharedPtr pick_server_;
  rclcpp_action::Server<Place>::SharedPtr place_server_;
  rclcpp_action::Server<Transfer>::SharedPtr transfer_server_;
  std::shared_ptr<tf2_ros::Buffer> tf_buffer_;
  std::shared_ptr<tf2_ros::TransformListener> tf_listener_;
};

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<SkillServer>();

  if (!node->configure()) {
    RCLCPP_FATAL(
      node->get_logger(),
      "refusing to start. Failing here stops bring-up with a diagnosis rather than "
      "advertising skills that cannot work.");
    rclcpp::shutdown();
    return 1;
  }

  // MoveGroupInterface talks to move_group over services, so this node must be
  // spinning before it is constructed. A multi-threaded executor because the
  // goal thread waits on results the executor has to deliver, and blocking the
  // executor inside a callback is how this deadlocks under load.
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spinner([&executor] {executor.spin();});

  if (!node->activate(node)) {
    node->shutdown();
    executor.cancel();
    spinner.join();
    rclcpp::shutdown();
    return 1;
  }

  spinner.join();
  // spin() returns on SIGINT, and a goal may still be inside plan(), execute()
  // or a feedback publication at that moment. Stop the arm and join the goal
  // thread before anything this node owns is destroyed.
  node->shutdown();
  rclcpp::shutdown();
  return 0;
}
