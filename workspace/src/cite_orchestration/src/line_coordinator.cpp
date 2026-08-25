// L4: the line coordinator.
//
// Behaviour trees rather than a hand-written state machine (ADR-0007), from
// three failed v1 attempts: state machines make asynchronous operations,
// cancellation and recovery awkward enough that developers route around them,
// and offer no runtime introspection that would reveal it.
//
// This node decides *what happens next*. It never plans a trajectory and never
// commands a controller — every leaf of every tree is an L3 skill called as a
// ROS 2 action. The topology it sequences comes from the generated artifact, so
// which stations exist is data (P5).

#include <chrono>
#include <memory>
#include <string>
#include <vector>

#include <behaviortree_cpp/bt_factory.h>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/msg/result_code.hpp>

namespace
{

using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::msg::ResultCode;

/// Shared context every leaf needs. Passed in rather than looked up, so a leaf
/// cannot quietly acquire a dependency nobody declared.
struct Context
{
  rclcpp::Node::SharedPtr node;
  std::string zone;
  std::chrono::seconds skill_deadline{180};
};

/// Base for a leaf that calls one L3 action.
///
/// Synchronous on purpose for Phase 1.C: the tree ticks one station at a time,
/// so a blocking leaf is honest about what is happening. When 1.D runs three
/// stations in parallel these become StatefulActionNodes, which is a change to
/// this file and to nothing else.
template <typename ActionT>
class SkillNode : public BT::SyncActionNode
{
public:
  SkillNode(const std::string & name, const BT::NodeConfig & config, Context context)
  : BT::SyncActionNode(name, config), context_(std::move(context))
  {
  }

protected:
  /// Send a goal and wait for its result, with a deadline that fails.
  BT::NodeStatus send(const std::string & action_name, const typename ActionT::Goal & goal)
  {
    auto client = rclcpp_action::create_client<ActionT>(context_.node, action_name);
    if (!client->wait_for_action_server(std::chrono::seconds(30))) {
      RCLCPP_ERROR(
        context_.node->get_logger(), "no skill server at %s", action_name.c_str());
      return BT::NodeStatus::FAILURE;
    }

    auto goal_future = client->async_send_goal(goal);
    if (rclcpp::spin_until_future_complete(
          context_.node, goal_future, std::chrono::seconds(30)) !=
        rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_ERROR(context_.node->get_logger(), "%s never accepted the goal",
                   action_name.c_str());
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
      RCLCPP_ERROR(context_.node->get_logger(), "%s did not finish in time",
                   action_name.c_str());
      return BT::NodeStatus::FAILURE;
    }

    const auto outcome = result_future.get().result->result;
    if (outcome.code != ResultCode::SUCCESS) {
      // The code, not the text, is what a recovery branch reacts to. v1 could
      // only retry generically because its failures were prose.
      RCLCPP_WARN(
        context_.node->get_logger(), "%s returned code %u: %s", action_name.c_str(),
        outcome.code, outcome.detail.c_str());
      return BT::NodeStatus::FAILURE;
    }
    return BT::NodeStatus::SUCCESS;
  }

  std::string skill_action(const std::string & asset, const std::string & skill) const
  {
    // The one place this node composes a name, and it composes it from the zone
    // and asset it was given rather than from anything it decided.
    return "/cite/" + context_.zone + "/" + asset + "/" + skill;
  }

  Context context_;
};

class MoveToHome : public SkillNode<MoveTo>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts() { return {BT::InputPort<std::string>("asset")}; }

  BT::NodeStatus tick() override
  {
    const auto asset = getInput<std::string>("asset");
    if (!asset) {
      return BT::NodeStatus::FAILURE;
    }
    MoveTo::Goal goal;
    // "home" resolves against the L0 model inside the skill server, not here:
    // where an arm rests between cycles is a fact about the facility.
    goal.named_configuration = "home";
    return send(skill_action(asset.value(), "move_to"), goal);
  }
};

class PickAt : public SkillNode<Pick>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {BT::InputPort<std::string>("asset"), BT::InputPort<std::string>("frame")};
  }

  BT::NodeStatus tick() override
  {
    const auto asset = getInput<std::string>("asset");
    const auto frame = getInput<std::string>("frame");
    if (!asset || !frame) {
      return BT::NodeStatus::FAILURE;
    }

    Pick::Goal goal;
    // The pose is a frame the station named in L0, resolved through TF. No
    // coordinate is written here, which is what stopped v1's pick tables from
    // diverging from the world they described.
    goal.object_pose.header.frame_id = frame.value();
    goal.object_pose.pose.orientation.w = 1.0;
    goal.approach_distance_m = 0.10;
    goal.retreat_distance_m = 0.12;
    return send(skill_action(asset.value(), "pick"), goal);
  }
};

/// Report a station as blocked. The recovery branch's terminal step.
class ReportBlocked : public BT::SyncActionNode
{
public:
  ReportBlocked(const std::string & name, const BT::NodeConfig & config,
                rclcpp::Node::SharedPtr node)
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

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("line_coordinator");

  node->declare_parameter("zone", "cell_a");
  node->declare_parameter("tree", "");
  node->declare_parameter("asset", "");
  node->declare_parameter("pick_frame", "");

  Context context;
  context.node = node;
  context.zone = node->get_parameter("zone").as_string();

  const auto tree_path = node->get_parameter("tree").as_string();
  const auto asset = node->get_parameter("asset").as_string();
  const auto pick_frame = node->get_parameter("pick_frame").as_string();

  if (tree_path.empty() || asset.empty() || pick_frame.empty()) {
    RCLCPP_FATAL(
      node->get_logger(),
      "the 'tree', 'asset' and 'pick_frame' parameters are all required. They come "
      "from the generated topology; refusing to start rather than choosing a station "
      "on this node's own initiative.");
    rclcpp::shutdown();
    return 1;
  }

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<MoveToHome>("MoveToHome", context);
  factory.registerNodeType<PickAt>("PickAt", context);
  factory.registerNodeType<ReportBlocked>("ReportBlocked", node);

  auto blackboard = BT::Blackboard::create();
  blackboard->set("asset", asset);
  blackboard->set("pick_frame", pick_frame);

  auto tree = factory.createTreeFromFile(tree_path, blackboard);
  RCLCPP_INFO(node->get_logger(), "running station cycle for %s", asset.c_str());

  const auto status = tree.tickWhileRunning();
  RCLCPP_INFO(
    node->get_logger(), "station cycle finished: %s",
    status == BT::NodeStatus::SUCCESS ? "SUCCESS" : "FAILURE");

  rclcpp::shutdown();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
