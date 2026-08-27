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

//: The server for the halt-after-the-goal-ended case, on its own name so the two
//: fixtures cannot answer each other's goals.
constexpr char kHeldAction[] = "/skill_cancellation_test/move_to_held";

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

/// A skill server that holds a goal until the test says to finish it.
///
/// The difference from `NeverFinishingServer` is the whole point: this one lets
/// the test decide the exact moment the goal reaches a TERMINAL state, which is
/// the precondition for the crash below. Nothing here sleeps to sequence
/// anything — the execute thread polls a flag the test sets.
class HeldGoalServer
{
public:
  HeldGoalServer()
  : node_(std::make_shared<rclcpp::Node>("held_goal_skill_server"))
  {
    server_ = rclcpp_action::create_server<MoveTo>(
      node_, kHeldAction,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const MoveTo::Goal>) {
        ++accepted_;
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>>) {
        ++cancels_;
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<MoveTo>> handle) {
        std::thread(
          [this, handle]() {
            while (rclcpp::ok() && !finish_.load() && !handle->is_canceling()) {
              std::this_thread::sleep_for(5ms);
            }
            if (handle->is_canceling()) {
              handle->canceled(std::make_shared<MoveTo::Result>());
              return;
            }
            auto result = std::make_shared<MoveTo::Result>();
            result->result.code = cite_interfaces::msg::ResultCode::SUCCESS;
            handle->succeed(result);
          }).detach();
      });

    executor_.add_node(node_);
    spinner_ = std::thread([this]() {executor_.spin();});
  }

  ~HeldGoalServer()
  {
    finish_ = true;
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  /// Let the held goal succeed. The leaf is NOT ticked after this, so it never
  /// consumes the result — which is exactly the state a halt used to crash in.
  void finish() {finish_ = true;}

  int accepted() const {return accepted_;}
  int cancels() const {return cancels_;}

private:
  rclcpp::Node::SharedPtr node_;
  rclcpp_action::Server<MoveTo>::SharedPtr server_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
  std::atomic<int> accepted_{0};
  std::atomic<int> cancels_{0};
  std::atomic<bool> finish_{false};
};

/// A `MoveToHome` whose two goal predicates a test can read.
///
/// They are `SkillNode`'s own — `halt_goal` branches on the first and `abandon`
/// on the second — re-exposed rather than reimplemented, so this drives the leaf
/// through the same state the coordinator does instead of a paraphrase of it.
class ProbeMoveToHome : public MoveToHome
{
public:
  using MoveToHome::MoveToHome;
  using MoveToHome::goal_already_ended;
  using MoveToHome::goal_is_outstanding;
};

/// Poll a condition until it holds, or give up and say so.
///
/// A FAILURE deadline on an asynchronous fact, not a schedule: nothing under test
/// is sequenced by it, and reaching it means the test reports instead of hanging.
template<typename Predicate>
bool wait_until(Predicate predicate, std::chrono::seconds deadline = 20s)
{
  const auto give_up = std::chrono::steady_clock::now() + deadline;
  while (std::chrono::steady_clock::now() < give_up) {
    if (predicate()) {
      return true;
    }
    std::this_thread::sleep_for(5ms);
  }
  return predicate();
}

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

/// Long enough that the leaf never reaches its own deadline during the test.
///
/// The deadline path is a DIFFERENT route into `abandon` and is covered by the
/// first test; this one is about a halt arriving from outside, which is what a
/// sibling station's failure or a preemption does.
Context patient_context(const rclcpp::Node::SharedPtr & node)
{
  Context context;
  context.node = node;
  context.skill_deadline = 120s;
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

TEST_F(SkillCancellation, halting_a_leaf_whose_goal_has_already_ended_does_not_abort)
{
  // THE CRASH. `abandon()` called `client_->async_cancel_goal(handle_)` on a
  // handle the client had already forgotten, which throws
  // `UnknownGoalHandleError` — on the TICK thread, where nothing caught it:
  //
  //     terminate called after throwing an instance of
  //       'rclcpp_action::exceptions::UnknownGoalHandleError'
  //       Goal handle is not known to this client
  //
  // The window is narrow and entirely ordinary. `rclcpp_action::Client`'s result
  // callback does `goal_handle->set_result(...)` and then
  // `goal_handles_.erase(...)`, on the executor's thread. So a leaf whose last
  // `poll` found the result not ready, and which is then HALTED before it is
  // ticked again, cancels a goal the client will not admit to knowing.
  //
  // It matters because halting is not only what shutdown does. The station
  // subtree's Fallback halts a leaf to run its recovery branch, and the line
  // tree's Parallel halts every sibling when one station fails — so this was a
  // crash on precisely the path that has to work when something else has already
  // gone wrong. It was measured on 1 continuous-line run in 4 and had been
  // written off as teardown noise.
  //
  // THE ASSERTION IS THAT THIS FUNCTION RETURNS. On the unfixed leaf the process
  // aborts inside `halt()` and the test binary never reaches the checks below.
  HeldGoalServer server;
  ProbeMoveToHome leaf(
    "MoveToHome", config_with(kHeldAction), patient_context(client_node_));

  // 1. Get the leaf to where it is holding an accepted goal.
  ASSERT_TRUE(
    wait_until(
      [&leaf]() {
        leaf.executeTick();
        return leaf.goal_is_outstanding();
      }))
    << "the leaf never took a goal handle, so the state under test was never reached";
  ASSERT_EQ(leaf.status(), BT::NodeStatus::RUNNING);
  ASSERT_EQ(server.accepted(), 1);
  ASSERT_FALSE(leaf.goal_already_ended());

  // 2. The goal ends while the leaf is RUNNING and is NOT ticked again, so the
  //    result is never consumed and the handle is never released. This is the
  //    state, and it is reached by waiting on the fact rather than on a duration.
  server.finish();
  ASSERT_TRUE(wait_until([&leaf]() {return leaf.goal_already_ended();}))
    << "the goal never reached the client, so the crash state was never set up";

  // 3. ...and now a sibling's failure halts this leaf. `haltNode` rather than
  //    `halt`, because that is the public entry point a parent control node
  //    calls — the Fallback above a recovery branch and the Parallel above the
  //    stations both reach a leaf this way.
  leaf.haltNode();

  EXPECT_EQ(leaf.status(), BT::NodeStatus::IDLE);
  EXPECT_EQ(server.cancels(), 0)
    << "the leaf asked a server to cancel a goal that had already succeeded; there was "
       "nothing to cancel and the request should never have been sent";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
