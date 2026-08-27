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

// L4: the line coordinator.
//
// Behaviour trees rather than a hand-written state machine (ADR-0007), from
// three failed v1 attempts: state machines make asynchronous operations,
// cancellation and recovery awkward enough that developers route around them,
// and offer no runtime introspection that would reveal it.
//
// This node decides *what happens next*. It never plans a trajectory and never
// commands a controller — every leaf of every tree is an L3 skill called as a
// ROS 2 action, and the leaves themselves live in `skill_nodes.hpp` so that they
// can be tested.
//
// It builds no name. Every action it calls arrives as a parameter, exactly as
// the frames and the asset do — CLAUDE.md §8 puts name construction in the
// model and says no asset name is ever written by hand twice, and this file used
// to compose `/cite/<zone>/<asset>/<skill>` from a format string of its own. The
// names come from the model end to end now: the generated bring-up plan carries a
// `skills:` block per arm and the launch mechanism reads it, so nothing composes
// a skill name anywhere between L0 and here.
//
// ONE STATION, ON PURPOSE. The line lives in `line_orchestrator.cpp`, which
// instantiates a subtree per station from the L0 topology. This executable runs
// ONE station's tree from parameters and exits when it finishes, which is what
// makes a station — and a handoff, `Transfer` having had a server since ADR-0024's
// motion half was built — drivable in isolation with no second arm and no
// topology server present. ADR-0024 requires exactly that isolation, and
// `tests/scenarios/pick_and_place.py` is what currently uses it. The two share
// every mechanism through the headers. The continuous-line scenario this comment
// once waited on exists — `tests/scenarios/continuous_line.py` — and the two
// entry points are still two; folding them into one is undone, not decided.
//
// THE NODE IS SPUN HERE, NOT IN A LEAF. The leaves became `StatefulActionNode`s
// when the line gained parallel stations: they send a goal, return RUNNING, and
// poll without spinning anything. So something has to spin, and it is the
// executor thread below. Without it every leaf sits at RUNNING for ever, which
// looks exactly like a skill server taking a long time.

#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include "behaviortree_cpp/bt_factory.h"
#include "cite_orchestration/skill_nodes.hpp"

namespace
{

using cite_orchestration::Context;

/// Read a parameter that must be supplied, collecting the missing ones.
std::string required(
  const rclcpp::Node::SharedPtr & node, const std::string & name,
  std::vector<std::string> & missing)
{
  node->declare_parameter(name, "");
  const auto value = node->get_parameter(name).as_string();
  if (value.empty()) {
    missing.push_back(name);
  }
  return value;
}

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("line_coordinator");

  std::vector<std::string> missing;
  const auto tree_path = required(node, "tree", missing);
  const auto asset = required(node, "asset", missing);
  const auto pick_frame = required(node, "pick_frame", missing);
  const auto place_frame = required(node, "place_frame", missing);
  const auto workpiece = required(node, "workpiece", missing);
  const auto move_to_action = required(node, "move_to_action", missing);
  const auto pick_action = required(node, "pick_action", missing);
  const auto place_action = required(node, "place_action", missing);

  if (!missing.empty()) {
    std::string names;
    for (const auto & name : missing) {
      names += (names.empty() ? "" : ", ") + name;
    }
    RCLCPP_FATAL(
      node->get_logger(),
      "these parameters are required and were not supplied: %s. They describe which "
      "station this is and what it calls, and they come from the model rather than from "
      "this node's own initiative — refusing to start rather than guessing.",
      names.c_str());
    rclcpp::shutdown();
    return 1;
  }

  // Spun on its own thread. The tree is ticked on this one; no leaf spins, and
  // no leaf blocks except on the cancellation path.
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spinner([&executor]() {executor.spin();});

  Context context;
  context.node = node;

  BT::BehaviorTreeFactory factory;
  factory.registerNodeType<cite_orchestration::MoveToHome>("MoveToHome", context);
  factory.registerNodeType<cite_orchestration::PickAt>("PickAt", context);
  factory.registerNodeType<cite_orchestration::PlaceAt>("PlaceAt", context);
  factory.registerNodeType<cite_orchestration::ReportBlocked>("ReportBlocked", node);

  auto blackboard = BT::Blackboard::create();
  blackboard->set("asset", asset);
  blackboard->set("pick_frame", pick_frame);
  blackboard->set("place_frame", place_frame);
  blackboard->set("workpiece", workpiece);
  blackboard->set("move_to_action", move_to_action);
  blackboard->set("pick_action", pick_action);
  blackboard->set("place_action", place_action);

  auto tree = factory.createTreeFromFile(tree_path, blackboard);
  RCLCPP_INFO(node->get_logger(), "running station cycle for %s", asset.c_str());

  const auto status = tree.tickWhileRunning();
  RCLCPP_INFO(
    node->get_logger(), "station cycle finished: %s",
    status == BT::NodeStatus::SUCCESS ? "SUCCESS" : "FAILURE");

  // Halt before shutting down. A tree that finished has nothing running, but a
  // tree that was interrupted does, and an arm left moving under a goal nobody is
  // holding is the defect the cancellation discipline exists to prevent.
  tree.haltTree();

  executor.cancel();
  if (spinner.joinable()) {
    spinner.join();
  }
  rclcpp::shutdown();
  return status == BT::NodeStatus::SUCCESS ? 0 : 1;
}
