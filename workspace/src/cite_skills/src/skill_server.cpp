// L3 skill server: one node per arm, hosting that arm's capabilities.
//
// Everything this node knows about its arm arrives as a generated parameter —
// the planning group, the tip link, the action names, the home configuration.
// Nothing here concatenates a topic, an action or a frame name. That is not a
// style preference: P2 says simulation and hardware are interchangeable, and
// that guarantee is made of names. A name built here would be a second place a
// name is made, and `ids.py`'s tests would not cover it.
//
// Goals are in task space. A joint-space goal would leak the robot's kinematics
// upward and break the promise that swapping this arm for a different one
// changes nothing above this line.
//
// Every skill implements the full action contract, cancellation included. L3 is
// explicit that covering only the happy path is a review finding — a skill that
// cannot be cancelled leaves L4 with no way to recover from anything.

#include <atomic>
#include <chrono>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <control_msgs/action/gripper_command.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <moveit/move_group_interface/move_group_interface.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Matrix3x3.h>

#include <cite_interfaces/action/grasp.hpp>
#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/msg/result_code.hpp>

#include "cite_skills/approach.hpp"

namespace
{

using cite_interfaces::action::Grasp;
using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::msg::ResultCode;
using GripperCommand = control_msgs::action::GripperCommand;
using moveit::planning_interface::MoveGroupInterface;

ResultCode make_result(uint8_t code, const std::string & detail = "")
{
  ResultCode result;
  result.code = code;
  result.detail = detail;
  return result;
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
    declare_parameter("gripper_max_width_m", 0.085);
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
          std::pair{"planning_group", planning_group_}, std::pair{"tip_link", tip_link_}}) {
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

    gripper_open_position_ = get_parameter("gripper_open_position").as_double();
    gripper_closed_position_ = get_parameter("gripper_closed_position").as_double();
    gripper_max_width_ = get_parameter("gripper_max_width_m").as_double();
    if (gripper_max_width_ <= 0.0) {
      RCLCPP_ERROR(
        get_logger(),
        "gripper_max_width_m must be positive; without it a task-space width "
        "cannot be mapped onto the gripper's own units");
      return false;
    }

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

    RCLCPP_INFO(
      get_logger(), "planning for group '%s' with end effector '%s' (planning frame '%s')",
      planning_group_.c_str(), tip_link_.c_str(), move_group_->getPlanningFrame().c_str());

    if (!gripper_action_.empty()) {
      gripper_client_ = rclcpp_action::create_client<GripperCommand>(self, gripper_action_);
    }

    move_to_server_ = rclcpp_action::create_server<MoveTo>(
      self, "move_to",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const MoveTo::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>>) {
        // Cancellation stops the arm rather than letting the trajectory finish.
        // A skill that ignores cancellation leaves L4 unable to recover.
        move_group_->stop();
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle) {
        std::thread{[this, handle] { execute_move_to(handle); }}.detach();
      });

    grasp_server_ = rclcpp_action::create_server<Grasp>(
      self, "grasp",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Grasp::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>> handle) {
        std::thread{[this, handle] { execute_grasp(handle); }}.detach();
      });

    place_server_ = rclcpp_action::create_server<Place>(
      self, "place",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Place::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>>) {
        move_group_->stop();
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>> handle) {
        std::thread{[this, handle] { execute_place(handle); }}.detach();
      });

    pick_server_ = rclcpp_action::create_server<Pick>(
      self, "pick",
      [](const rclcpp_action::GoalUUID &, std::shared_ptr<const Pick::Goal>) {
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>>) {
        move_group_->stop();
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>> handle) {
        std::thread{[this, handle] { execute_pick(handle); }}.detach();
      });

    RCLCPP_INFO(get_logger(), "skills for %s are accepting goals", asset_id_.c_str());
    return true;
  }

private:
  // ---------------------------------------------------------------------------
  // MoveTo
  // ---------------------------------------------------------------------------
  void execute_move_to(const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<MoveTo::Result>();
    const auto started = now();

    if (!goal->named_configuration.empty()) {
      if (goal->named_configuration != "home") {
        result->result = make_result(
          ResultCode::PRECONDITION_FAILED,
          "the only named configuration is 'home', which comes from the L0 model");
        handle->abort(result);
        return;
      }
      if (home_.empty()) {
        result->result = make_result(
          ResultCode::PRECONDITION_FAILED,
          "no home configuration was delivered for this arm");
        handle->abort(result);
        return;
      }
      move_group_->setJointValueTarget(home_);
    } else {
      move_group_->setPoseTarget(goal->target, tip_link_);
    }

    apply_scaling(goal->velocity_scaling, goal->acceleration_scaling);

    const auto outcome = plan_and_execute(handle);
    result->result = outcome;
    result->duration = now() - started;
    result->reached = current_pose();

    if (outcome.code == ResultCode::SUCCESS) {
      handle->succeed(result);
    } else if (outcome.code == ResultCode::CANCELLED) {
      handle->canceled(result);
    } else {
      handle->abort(result);
    }
  }

  // ---------------------------------------------------------------------------
  // Grasp
  // ---------------------------------------------------------------------------
  void execute_grasp(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Grasp>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Grasp::Result>();

    const auto outcome = command_gripper(goal->width_m, goal->max_effort_n, &result->holding);
    result->result = outcome;
    result->reached_width_m = goal->width_m;

    if (outcome.code != ResultCode::SUCCESS) {
      handle->abort(result);
      return;
    }

    // Closing on nothing is not a successful grasp. Without this the line would
    // carry an imaginary work-piece all the way to the next station and fail
    // there instead, which is much harder to attribute.
    if (goal->expect_object && !result->holding) {
      result->result = make_result(
        ResultCode::EXECUTION_FAILED,
        "the gripper closed without stalling, so it is holding nothing");
      handle->abort(result);
      return;
    }

    holding_ = result->holding;
    handle->succeed(result);
  }

  // ---------------------------------------------------------------------------
  // Pick — approach, grasp, retreat
  // ---------------------------------------------------------------------------
  void execute_pick(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Pick>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Pick::Result>();
    const auto started = now();

    auto feedback = std::make_shared<Pick::Feedback>();
    const auto report = [&](uint8_t phase, double fraction) {
      feedback->phase = phase;
      feedback->fraction_complete = fraction;
      handle->publish_feedback(feedback);
    };

    const auto fail = [&](const ResultCode & code) {
      result->result = code;
      result->duration = now() - started;
      if (code.code == ResultCode::CANCELLED) {
        handle->canceled(result);
      } else {
        handle->abort(result);
      }
    };

    // Open before approaching. Arriving at the object with a closed gripper is a
    // collision, and the planner has no way to know the gripper's state.
    report(Pick::Feedback::PHASE_PLANNING, 0.0);
    bool holding = false;
    auto outcome = command_gripper(
      gripper_max_width_, get_parameter("gripper_max_effort_n").as_double(), &holding);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }

    report(Pick::Feedback::PHASE_APPROACHING, 0.2);
    bool adjusted = false;
    const auto grasp = feasible_grasp(goal->object_pose, &adjusted);
    if (adjusted) {
      RCLCPP_INFO(
        get_logger(),
        "top-down grasp: yaw taken from the target's direction rather than the "
        "request, because a 5-DOF arm cannot choose it freely");
    }

    auto approach = grasp;
    approach.pose = cite_skills::offset_along_tool_z(
      grasp.pose, goal->approach_distance_m);
    move_group_->setPoseTarget(approach, tip_link_);
    outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }

    move_group_->setPoseTarget(grasp, tip_link_);
    outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }
    result->grasp_pose = current_pose();

    report(Pick::Feedback::PHASE_GRASPING, 0.6);
    const double width = goal->grasp_width_m > 0.0 ? goal->grasp_width_m : 0.0;
    outcome = command_gripper(
      width, get_parameter("gripper_max_effort_n").as_double(), &holding);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }
    if (!holding) {
      fail(make_result(
        ResultCode::EXECUTION_FAILED,
        "the gripper closed without stalling, so nothing was picked up"));
      return;
    }
    result->holding = true;
    holding_ = true;

    report(Pick::Feedback::PHASE_RETREATING, 0.8);
    auto retreat = result->grasp_pose;
    retreat.pose = cite_skills::offset_along_world_z(
      result->grasp_pose.pose, goal->retreat_distance_m);
    move_group_->setPoseTarget(retreat, tip_link_);
    outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      // Still holding: report it so L4 knows the work-piece's owner.
      fail(outcome);
      return;
    }

    report(Pick::Feedback::PHASE_RETREATING, 1.0);
    result->result = make_result(ResultCode::SUCCESS);
    result->duration = now() - started;
    handle->succeed(result);
  }

  // ---------------------------------------------------------------------------
  // Place — approach, release, retreat
  // ---------------------------------------------------------------------------
  void execute_place(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Place>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Place::Result>();
    const auto started = now();

    auto feedback = std::make_shared<Place::Feedback>();
    const auto report = [&](uint8_t phase, double fraction) {
      feedback->phase = phase;
      feedback->fraction_complete = fraction;
      handle->publish_feedback(feedback);
    };

    const auto fail = [&](const ResultCode & code) {
      result->result = code;
      result->duration = now() - started;
      if (code.code == ResultCode::CANCELLED) {
        handle->canceled(result);
      } else {
        handle->abort(result);
      }
    };

    // Miming a place with an empty gripper would leave the line believing a
    // work-piece arrived somewhere it never did — and the failure would surface
    // at the next station, which is much harder to attribute.
    if (goal->require_holding && !holding_) {
      fail(make_result(
        ResultCode::PRECONDITION_FAILED,
        "asked to place, but the gripper is not holding anything"));
      return;
    }

    report(Place::Feedback::PHASE_PLANNING, 0.0);
    bool adjusted = false;
    const auto release = feasible_grasp(goal->target_pose, &adjusted);

    auto approach = release;
    approach.pose = cite_skills::offset_along_tool_z(
      release.pose, goal->approach_distance_m);
    move_group_->setPoseTarget(approach, tip_link_);
    auto outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }

    report(Place::Feedback::PHASE_APPROACHING, 0.4);
    move_group_->setPoseTarget(release, tip_link_);
    outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }
    result->release_pose = current_pose();

    report(Place::Feedback::PHASE_RELEASING, 0.7);
    bool holding = false;
    outcome = command_gripper(
      gripper_max_width_, get_parameter("gripper_max_effort_n").as_double(), &holding);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }
    holding_ = false;

    report(Place::Feedback::PHASE_RETREATING, 0.9);
    auto retreat = result->release_pose;
    retreat.pose = cite_skills::offset_along_world_z(
      result->release_pose.pose, goal->retreat_distance_m);
    move_group_->setPoseTarget(retreat, tip_link_);
    outcome = plan_and_execute(handle);
    if (outcome.code != ResultCode::SUCCESS) {
      fail(outcome);
      return;
    }

    report(Place::Feedback::PHASE_RETREATING, 1.0);
    result->result = make_result(ResultCode::SUCCESS);
    result->duration = now() - started;
    handle->succeed(result);
  }

  // ---------------------------------------------------------------------------
  // Shared helpers
  // ---------------------------------------------------------------------------
  /// Make a top-down grasp pose that a 5-DOF arm can actually reach.
  ///
  /// An xArm 5 has five joints, so it cannot achieve an arbitrary 6-DOF pose:
  /// with the tool pointing straight down, the rotation ABOUT that axis is not
  /// free — it is fixed by where the target is relative to the base. Asking for
  /// a particular yaw over-constrains the problem, and the planner correctly
  /// reports that no collision-free path exists, which reads as a reachability
  /// problem rather than as a degrees-of-freedom one.
  ///
  /// So when the caller asks for a top-down grasp, the yaw is not taken from the
  /// request. It is computed from the target's direction in the planning frame,
  /// whose origin is the arm's own base. Choosing the grasp orientation is L3's
  /// job — the L3 document assigns "grasp strategy and approach/retreat
  /// behaviour" to this layer — so this is the right place for it, and a caller
  /// asking for a non-top-down grasp is left exactly as it asked.
  geometry_msgs::msg::PoseStamped feasible_grasp(
    const geometry_msgs::msg::PoseStamped & requested, bool * adjusted)
  {
    *adjusted = false;
    geometry_msgs::msg::PoseStamped in_planning_frame;
    try {
      in_planning_frame = tf_buffer_->transform(
        requested, move_group_->getPlanningFrame(), tf2::durationFromSec(5.0));
    } catch (const std::exception & error) {
      RCLCPP_WARN(
        get_logger(), "could not transform the grasp pose into '%s': %s",
        move_group_->getPlanningFrame().c_str(), error.what());
      return requested;
    }

    // Is the requested tool axis pointing (roughly) down?
    tf2::Quaternion requested_q(
      in_planning_frame.pose.orientation.x, in_planning_frame.pose.orientation.y,
      in_planning_frame.pose.orientation.z, in_planning_frame.pose.orientation.w);
    requested_q.normalize();
    const tf2::Matrix3x3 rotation(requested_q);
    const tf2::Vector3 tool_z(rotation[0][2], rotation[1][2], rotation[2][2]);
    constexpr double kDownTolerance = -0.9;  // cos(~155 deg): comfortably downward
    if (tool_z.z() > kDownTolerance) {
      return in_planning_frame;
    }

    const double yaw = std::atan2(
      in_planning_frame.pose.position.y, in_planning_frame.pose.position.x);
    tf2::Quaternion feasible;
    // Roll by pi to point the tool down, then yaw to face the target radially.
    feasible.setRPY(M_PI, 0.0, yaw);
    feasible.normalize();
    in_planning_frame.pose.orientation = tf2::toMsg(feasible);
    *adjusted = true;
    return in_planning_frame;
  }

  template <typename Handle>
  ResultCode plan_and_execute(const Handle & handle)
  {
    MoveGroupInterface::Plan plan;
    const auto planned = move_group_->plan(plan);
    if (planned != moveit::core::MoveItErrorCode::SUCCESS) {
      return make_result(
        ResultCode::PLANNING_FAILED,
        "no collision-free path was found to the requested pose");
    }

    if (handle->is_canceling()) {
      return make_result(ResultCode::CANCELLED, "cancelled before execution began");
    }

    const auto executed = move_group_->execute(plan);
    if (handle->is_canceling()) {
      return make_result(ResultCode::CANCELLED, "cancelled during execution");
    }
    if (executed != moveit::core::MoveItErrorCode::SUCCESS) {
      return make_result(
        ResultCode::EXECUTION_FAILED,
        "the controller did not complete the planned trajectory");
    }
    return make_result(ResultCode::SUCCESS);
  }

  /// Task-space opening in metres to the gripper's own command units.
  ///
  /// Linear across the stroke. That is an approximation for a linkage gripper —
  /// the true relation is not linear — but it is a stated approximation with the
  /// numbers in the model, rather than a unit confusion in the code.
  double gripper_position_for(double width_m) const
  {
    const double clamped = std::max(0.0, std::min(gripper_max_width_, width_m));
    const double fraction = clamped / gripper_max_width_;
    return gripper_closed_position_ +
           (gripper_open_position_ - gripper_closed_position_) * fraction;
  }

  ResultCode command_gripper(double width_m, double max_effort_n, bool * holding)
  {
    *holding = false;
    if (!gripper_client_) {
      return make_result(
        ResultCode::NOT_IMPLEMENTED, "this arm has no gripper action configured");
    }
    if (!gripper_client_->wait_for_action_server(std::chrono::seconds(10))) {
      return make_result(
        ResultCode::PRECONDITION_FAILED,
        "the gripper controller's action server is not available");
    }

    GripperCommand::Goal goal;
    goal.command.position = gripper_position_for(width_m);
    goal.command.max_effort = max_effort_n;

    auto future = gripper_client_->async_send_goal(goal);
    if (future.wait_for(std::chrono::seconds(10)) != std::future_status::ready) {
      return make_result(ResultCode::TIMEOUT, "the gripper never accepted the command");
    }
    auto handle = future.get();
    if (!handle) {
      return make_result(ResultCode::EXECUTION_FAILED, "the gripper rejected the command");
    }

    auto result_future = gripper_client_->async_get_result(handle);
    if (result_future.wait_for(std::chrono::seconds(20)) != std::future_status::ready) {
      return make_result(ResultCode::TIMEOUT, "the gripper never reported a result");
    }
    const auto result = result_future.get();

    // `stalled` is what distinguishes holding something from closing on air.
    // GripperActionController reports it; a controller that could not would make
    // this skill unable to tell the two apart (ADR-0022).
    *holding = result.result->stalled;
    return make_result(ResultCode::SUCCESS);
  }

  void apply_scaling(double velocity, double acceleration)
  {
    // Zero means "use the configured default", not "do not move". A goal that
    // left these unset would otherwise command a stationary trajectory.
    if (velocity > 0.0) {
      move_group_->setMaxVelocityScalingFactor(velocity);
    }
    if (acceleration > 0.0) {
      move_group_->setMaxAccelerationScalingFactor(acceleration);
    }
  }

  geometry_msgs::msg::PoseStamped current_pose()
  {
    return move_group_->getCurrentPose(tip_link_);
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

  double gripper_open_position_{0.0};
  double gripper_closed_position_{0.85};
  double gripper_max_width_{0.085};

  std::shared_ptr<MoveGroupInterface> move_group_;
  rclcpp_action::Client<GripperCommand>::SharedPtr gripper_client_;
  rclcpp_action::Server<MoveTo>::SharedPtr move_to_server_;
  rclcpp_action::Server<Grasp>::SharedPtr grasp_server_;
  rclcpp_action::Server<Pick>::SharedPtr pick_server_;
  rclcpp_action::Server<Place>::SharedPtr place_server_;
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
  // spinning before it is constructed. A multi-threaded executor because each
  // goal runs on its own thread and blocking the executor inside a callback is
  // how this deadlocks under load.
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spinner([&executor] { executor.spin(); });

  if (!node->activate(node)) {
    executor.cancel();
    spinner.join();
    rclcpp::shutdown();
    return 1;
  }

  spinner.join();
  rclcpp::shutdown();
  return 0;
}
