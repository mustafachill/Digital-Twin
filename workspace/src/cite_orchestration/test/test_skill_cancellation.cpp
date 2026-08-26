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

// A leaf that gives up must cancel the goal it gives up on.
//
// The defect this locks down: `SkillNode::send` returned FAILURE on its deadline
// without cancelling. The tree's Fallback then ran the recovery branch, whose
// first leaf sends a new goal to the same server while the abandoned one is
// still executing — and `BT::SyncActionNode` has no halt, so nothing stopped it.
// With a server that admits one goal at a time, the recovery branch is then
// rejected and can never run at all.
//
// Driven against a real action server rather than a mock. The failure was in
// what this node does to a SERVER, so a test that stubbed the server away would
// be testing the wrong side of the boundary.
//
// The leaf is now a `BT::StatefulActionNode` — it had to become one for three
// stations to tick under a Parallel — so this test ticks it until it settles and
// spins the client node on its own thread. The property under test is unchanged
// and is the whole reason the conversion was done carefully: a leaf that gives
// up must still cancel the goal it gives up on, and must not return before that
// goal has reached a terminal state.

#include <atomic>
#include <chrono>
#include <memory>
#include <string>
#include <thread>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/move_to.hpp>

#include "gtest/gtest.h"
#include "cite_orchestration/skill_nodes.hpp"

namespace
{

using cite_interfaces::action::MoveTo;
using cite_orchestration::Context;
using cite_orchestration::MoveToHome;
using namespace std::chrono_literals;

//: The fake server below is a FIXTURE, so it is named as one — outside `/cite/`,
//: where no generated name can ever land.
//:
//: It used to be `/cite/cell_a/arm_1/move_to`, which is the real action arm_1
//: serves in the real cell. `colcon test` runs packages concurrently on one ROS
//: domain, and `cite_skills`'s `test_skill_contract.py` launches an actual skill
//: server advertising exactly that name — so two servers answered one action.
//: The leaf's client sent its goal to both (`accepted()` counted 3 instead of 1)
//: while the contract test's client logged "Ignoring unexpected goal response.
//: There may be more than one action server" and failed its own assertions. Each
//: suite passed alone and both failed together, which is why this looked like two
//: unrelated long-standing failures rather than one name.
//:
//: Nothing here asserts anything about the name — see the third test, whose whole
//: point is that a leaf builds no name of its own — so a realistic one bought
//: nothing and cost this.
constexpr char kAction[] = "/skill_cancellation_test/move_to";

/// A skill server that accepts a goal and never finishes it on its own.
///
/// Exactly the situation the deadline exists for: an arm that has taken a goal
/// and is still working on it when the coordinator stops waiting.
class NeverFinishingServer
{
public:
  NeverFinishingServer()
  : node_(std::make_shared<rclcpp::Node>("never_finishing_skill_server"))
  {
    server_ = rclcpp_action::create_server<MoveTo>(
      node_, kAction,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const MoveTo::Goal>) {
        ++accepted_;
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>>) {
        ++cancels_;
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle) {
        // Held, not run. The goal stays EXECUTING until it is cancelled, which
        // is the only way to reach the path under test.
        std::thread(
          [this, handle]() {
            while (rclcpp::ok() && !handle->is_canceling()) {
              std::this_thread::sleep_for(10ms);
            }
            if (handle->is_canceling()) {
              handle->canceled(std::make_shared<MoveTo::Result>());
              cancelled_to_completion_ = true;
            }
          }).detach();
      });

    executor_.add_node(node_);
    spinner_ = std::thread([this]() {executor_.spin();});
  }

  ~NeverFinishingServer()
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  int accepted() const {return accepted_;}
  int cancels() const {return cancels_;}
  bool cancelled_to_completion() const {return cancelled_to_completion_;}

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Server<MoveTo>::SharedPtr server_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
  std::atomic<int> accepted_{0};
  std::atomic<int> cancels_{0};
  std::atomic<bool> cancelled_to_completion_{false};
};

BT::NodeConfig config_with(const std::string & action)
{
  BT::NodeConfig config;
  config.blackboard = BT::Blackboard::create();
  config.input_ports["asset"] = "arm_1";
  config.input_ports["action"] = action;
  return config;
}


/// Tick a leaf until it stops being RUNNING.
///
/// The leaves became `StatefulActionNode`s when the line gained parallel
/// stations: they send a goal, return RUNNING, and poll without spinning
/// anything. So a test drives them the way a tree does — by ticking — and
/// something else spins the node. The wait below is a POLL PERIOD on an
/// asynchronous result, not a guess at how long anything takes.
BT::NodeStatus tick_until_settled(BT::TreeNode & leaf)
{
  BT::NodeStatus status = leaf.executeTick();
  while (status == BT::NodeStatus::RUNNING) {
    std::this_thread::sleep_for(5ms);
    status = leaf.executeTick();
  }
  return status;
}

Context short_deadline_context(const rclcpp::Node::SharedPtr & node)
{
  Context context;
  context.node = node;
  // Short so the test is quick. Nothing about the behaviour under test depends
  // on the value — only that the deadline is reached rather than the result.
  context.skill_deadline = 2s;
  context.cancel_deadline = 10s;
  return context;
}

}  // namespace

class SkillCancellation : public ::testing::Test
{
protected:
  void SetUp() override
  {
    client_node_ = std::make_shared<rclcpp::Node>("skill_cancellation_test");
    // Somebody has to spin, and it is deliberately not the leaf. A leaf that
    // spun the node could not run beside a sibling station doing the same.
    executor_.add_node(client_node_);
    spinner_ = std::thread([this]() {executor_.spin();});
  }

  void TearDown() override
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  rclcpp::Node::SharedPtr client_node_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
};

TEST_F(SkillCancellation, a_leaf_that_hits_its_deadline_cancels_the_goal_it_abandons)
{
  NeverFinishingServer server;

  MoveToHome leaf("MoveToHome", config_with(kAction), short_deadline_context(client_node_));
  const auto status = tick_until_settled(leaf);

  EXPECT_EQ(status, BT::NodeStatus::FAILURE);
  EXPECT_EQ(server.accepted(), 1) << "the server never saw the goal, so nothing was tested";
  EXPECT_EQ(server.cancels(), 1)
    << "the leaf gave up without cancelling: the goal is still EXECUTING and the "
       "recovery branch's next goal will be rejected";
  EXPECT_TRUE(server.cancelled_to_completion())
    << "the leaf returned before the abandoned goal reached a terminal state";
}

TEST_F(SkillCancellation, the_recovery_branchs_next_goal_is_accepted_after_a_deadline)
{
  // The property the cancellation exists for, asserted end to end: a second goal
  // sent immediately after a leaf gave up is taken by the server, because the
  // first one is genuinely over.
  NeverFinishingServer server;

  MoveToHome first("MoveToHome", config_with(kAction), short_deadline_context(client_node_));
  ASSERT_EQ(tick_until_settled(first), BT::NodeStatus::FAILURE);

  auto client = rclcpp_action::create_client<MoveTo>(client_node_, kAction);
  ASSERT_TRUE(client->wait_for_action_server(10s));
  auto goal_future = client->async_send_goal(MoveTo::Goal{});
  // Waited on rather than spun for: this node already has an executor spinning
  // it, and spinning a node twice is not allowed.
  ASSERT_EQ(goal_future.wait_for(10s), std::future_status::ready);
  EXPECT_TRUE(goal_future.get()) << "the recovery goal was rejected; the arm is still "
    "held by the goal the previous leaf abandoned";

  client->async_cancel_all_goals();
}

TEST_F(SkillCancellation, a_leaf_with_no_action_name_fails_without_calling_anything)
{
  // Names arrive as data. A leaf that was given none must refuse rather than
  // invent one — the defect being kept out is this node composing
  // "/cite/<zone>/<asset>/<skill>" from a format string of its own.
  MoveToHome leaf("MoveToHome", config_with(""), short_deadline_context(client_node_));
  EXPECT_EQ(tick_until_settled(leaf), BT::NodeStatus::FAILURE);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
