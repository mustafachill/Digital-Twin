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

// The panel's ROS half, headless and without Qt (P-R02): `ConsoleClient`
// against a fake console in a SECOND context on the same domain, as the panel
// in the Gazebo window meets the real one in `cell_console`.
//
// Every wait here is bounded by `SETTLE` and ends the moment its condition
// holds; it is a hang detector, not a schedule. The one loop that sends again
// does so only while the client's graph has not yet discovered the fake's
// server, which the client reports at once rather than waiting.

#include <gtest/gtest.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "cite_console_gui/console_client.hpp"
#include "cite_interfaces/qos.hpp"

using cite_console_gui::ConsoleCallbacks;
using cite_console_gui::ConsoleClient;
using cite_console_gui::ConsoleNames;
using cite_interfaces::action::HomeRobot;
using cite_interfaces::action::RunProgram;
using cite_interfaces::msg::ConsoleState;
using cite_interfaces::srv::ConfirmOperator;
using cite_interfaces::srv::StartRobot;
using cite_interfaces::srv::StopCell;

namespace
{

/// The longest any one wait here may take. A hang detector.
constexpr std::chrono::seconds SETTLE{20};

/// A domain of this process's own, set before any context exists (each
/// context reads ROS_DOMAIN_ID when it initializes), so parallel suites do
/// not hear each other. Drawn from the private band 215 to 232 that
/// `cite_runtime`'s signal test established: valid on Linux, and disjoint
/// from every cell's domain (1 to 100, `scripts/_lib.sh`) and every launch
/// test's.
const bool DOMAIN_SET = []() {
    const std::string domain = std::to_string(215 + getpid() % 18);
    return setenv("ROS_DOMAIN_ID", domain.c_str(), 1) == 0;
  }();

ConsoleNames names_for(const std::string & test)
{
  const std::string base = "/cite/test_console_client_" + test + "/console/";
  ConsoleNames names;
  names.state = base + "state";
  names.start_robot = base + "start_robot";
  names.confirm_operator = base + "confirm_operator";
  names.stop = base + "stop";
  names.home = base + "home";
  names.run_program = base + "run_program";
  return names;
}

/// Everything the client told its owner, from its spin thread.
class Recorder
{
public:
  ConsoleCallbacks callbacks()
  {
    ConsoleCallbacks callbacks;
    callbacks.on_state = [this](const ConsoleState & state) {
        record([&]() {states.push_back(state);});
      };
    callbacks.on_state_lost = [this]() {record([&]() {++lost;});};
    callbacks.on_progress = [this](const std::string & text) {
        record([&]() {progress.push_back(text);});
      };
    callbacks.on_outcome = [this](const std::string & text) {
        record([&]() {outcomes.push_back(text);});
      };
    return callbacks;
  }

  /// Wait until `predicate` holds, read under the lock; false on the bound.
  bool wait_for(const std::function<bool()> & predicate)
  {
    std::unique_lock<std::mutex> lock(mutex);
    return changed.wait_for(lock, SETTLE, predicate);
  }

  std::mutex mutex;
  std::condition_variable changed;
  std::vector<ConsoleState> states;
  std::vector<std::string> progress;
  std::vector<std::string> outcomes;
  int lost{0};
  /// Set once the client is destroyed: nothing may be told after that.
  std::atomic<bool> closed{false};
  std::atomic<int> after_close{0};

private:
  void record(const std::function<void()> & change)
  {
    if (closed) {
      ++after_close;
    }
    {
      std::lock_guard<std::mutex> lock(mutex);
      change();
    }
    changed.notify_all();
  }
};

/// A console as far as the panel can tell: its state, its services, its
/// actions, on a context of its own. Every request is recorded; services
/// answer success, goals are rejected.
class FakeConsole
{
public:
  explicit FakeConsole(const ConsoleNames & names, bool answer_start_robot = true)
  : context_(std::make_shared<rclcpp::Context>())
  {
    rclcpp::InitOptions options;
    options.shutdown_on_signal = false;
    context_->init(0, nullptr, options);
    node_ = std::make_shared<rclcpp::Node>(
      "fake_cell_console", rclcpp::NodeOptions().context(context_));
    // On a node no executor holds: an executor's wait set keeps a strong
    // reference to the publisher's event handlers, and with them the
    // publisher itself, so `withdraw_state` would withdraw nothing.
    state_node_ = std::make_shared<rclcpp::Node>(
      "fake_cell_console_state", rclcpp::NodeOptions().context(context_));
    state_ = state_node_->create_publisher<ConsoleState>(names.state, cite::qos::latched());
    if (answer_start_robot) {
      start_robot_ = node_->create_service<StartRobot>(
        names.start_robot,
        [this](const std::shared_ptr<StartRobot::Request>,
        std::shared_ptr<StartRobot::Response> response) {
          note("start_robot");
          response->success = true;
          response->detail = "fake start_robot";
        });
    } else {
      // Never answered: a request that stays in flight.
      start_robot_ = node_->create_service<StartRobot>(
        names.start_robot,
        [this](const std::shared_ptr<rmw_request_id_t>,
        const std::shared_ptr<StartRobot::Request>) {note("start_robot");});
    }
    confirm_ = node_->create_service<ConfirmOperator>(
      names.confirm_operator,
      [this](const std::shared_ptr<ConfirmOperator::Request>,
      std::shared_ptr<ConfirmOperator::Response> response) {
        note("confirm_operator");
        response->success = false;
        response->detail = "fake confirm refused";
      });
    stop_ = node_->create_service<StopCell>(
      names.stop,
      [this](const std::shared_ptr<StopCell::Request>,
      std::shared_ptr<StopCell::Response> response) {
        note("stop");
        response->success = true;
        response->detail = "fake stop";
      });
    home_ = rclcpp_action::create_server<HomeRobot>(
      node_, names.home,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const HomeRobot::Goal> goal) {
        note(
          "home " + std::to_string(goal->speed_scale) + " target " +
          std::to_string(goal->target));
        return rclcpp_action::GoalResponse::REJECT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<HomeRobot>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<HomeRobot>>) {});
    run_ = rclcpp_action::create_server<RunProgram>(
      node_, names.run_program,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const RunProgram::Goal> goal) {
        note(
          "run_program " + std::to_string(goal->speed_scale) + " target " +
          std::to_string(goal->target) + " cycles " + std::to_string(goal->cycles));
        return rclcpp_action::GoalResponse::REJECT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<RunProgram>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<RunProgram>>) {});
    rclcpp::ExecutorOptions executor_options;
    executor_options.context = context_;
    executor_ = std::make_unique<rclcpp::executors::SingleThreadedExecutor>(executor_options);
    executor_->add_node(node_);
    spinner_ = std::thread([this]() {executor_->spin();});
  }

  ~FakeConsole()
  {
    context_->shutdown("the test ended");
    executor_->cancel();
    spinner_.join();
    executor_->remove_node(node_, false);
  }

  void publish(std::uint8_t state)
  {
    ConsoleState message;
    message.state = state;
    state_->publish(message);
  }

  /// Withdraw the state publisher, as a console that went away.
  void withdraw_state() {state_.reset();}

  std::vector<std::string> requests()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    return requests_;
  }

private:
  void note(const std::string & request)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    requests_.push_back(request);
  }

  rclcpp::Context::SharedPtr context_;
  rclcpp::Node::SharedPtr node_;
  rclcpp::Node::SharedPtr state_node_;
  rclcpp::Publisher<ConsoleState>::SharedPtr state_;
  rclcpp::Service<StartRobot>::SharedPtr start_robot_;
  rclcpp::Service<ConfirmOperator>::SharedPtr confirm_;
  rclcpp::Service<StopCell>::SharedPtr stop_;
  rclcpp_action::Server<HomeRobot>::SharedPtr home_;
  rclcpp_action::Server<RunProgram>::SharedPtr run_;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread spinner_;
  std::mutex mutex_;
  std::vector<std::string> requests_;
};

bool unserved(const std::string & line)
{
  return line.find("does not serve it right now") != std::string::npos;
}

/// Send with `send` until the client's graph has discovered the server, then
/// return the first line said after the send that reached it.
std::string sent_once_served(
  Recorder & recorder, const std::function<void()> & send,
  std::vector<std::string> Recorder::* channel)
{
  const auto deadline = std::chrono::steady_clock::now() + SETTLE;
  while (std::chrono::steady_clock::now() < deadline) {
    std::size_t outcomes_before = 0;
    std::size_t before = 0;
    {
      std::lock_guard<std::mutex> lock(recorder.mutex);
      outcomes_before = recorder.outcomes.size();
      before = (recorder.*channel).size();
    }
    send();
    {
      std::lock_guard<std::mutex> lock(recorder.mutex);
      // An unserved request is said synchronously, on this thread.
      if (recorder.outcomes.size() > outcomes_before &&
        unserved(recorder.outcomes.back()))
      {
        recorder.outcomes.pop_back();
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        continue;
      }
    }
    if (!recorder.wait_for([&]() {return (recorder.*channel).size() > before;})) {
      return "";
    }
    std::lock_guard<std::mutex> lock(recorder.mutex);
    return (recorder.*channel)[before];
  }
  return "";
}

}  // namespace

TEST(ConsoleClient, EachRequestReachesTheEndpointItsNameNames)
{
  ASSERT_TRUE(DOMAIN_SET);
  const ConsoleNames names = names_for("names");
  FakeConsole console(names);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());

  EXPECT_EQ(
    sent_once_served(recorder, [&]() {client.start_robot();}, &Recorder::outcomes),
    "Start robot: done. fake start_robot");
  EXPECT_EQ(
    sent_once_served(recorder, [&]() {client.confirm_operator();}, &Recorder::outcomes),
    "Confirm: refused or failed. fake confirm refused");
  EXPECT_EQ(
    sent_once_served(recorder, [&]() {client.stop();}, &Recorder::outcomes),
    "Stop: done. fake stop");
  EXPECT_EQ(
    sent_once_served(
      recorder, [&]() {client.home(0.5, ConsoleState::TARGET_REAL);}, &Recorder::progress),
    "Home: rejected by the console (see last error).");
  EXPECT_EQ(
    sent_once_served(
      recorder, [&]() {client.run_program(0.25, ConsoleState::TARGET_TWIN, 3);},
      &Recorder::progress),
    "Start program: rejected by the console (see last error).");

  // ADR-0072: each goal carries the target it was given, field for field.
  const std::vector<std::string> expected = {
    "start_robot", "confirm_operator", "stop",
    "home " + std::to_string(0.5) + " target " + std::to_string(ConsoleState::TARGET_REAL),
    "run_program " + std::to_string(0.25) + " target " +
    std::to_string(ConsoleState::TARGET_TWIN) + " cycles 3",
  };
  EXPECT_EQ(console.requests(), expected);
}

TEST(ConsoleClient, TheLatchedStateIsHeardAndItsPublisherLeavingIsNoConsole)
{
  const ConsoleNames names = names_for("latched");
  FakeConsole console(names);
  // Published before the client exists: only a latched match delivers it.
  console.publish(ConsoleState::READY);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());

  ASSERT_TRUE(recorder.wait_for([&]() {return !recorder.states.empty();}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.states.front().state, ConsoleState::READY);
    EXPECT_EQ(recorder.lost, 0);
  }
  console.withdraw_state();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.lost == 1;}))
    << "the publisher left and the panel was not told (P-R04)";
}

TEST(ConsoleClient, AnUnservedRequestIsReportedAtOnceAndNotWaitedFor)
{
  const ConsoleNames names = names_for("unserved");
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());

  const auto started = std::chrono::steady_clock::now();
  client.start_robot();
  client.confirm_operator();
  client.stop();
  client.home(1.0, ConsoleState::TARGET_SIM);
  client.run_program(1.0, ConsoleState::TARGET_SIM, 1);
  const auto took = std::chrono::steady_clock::now() - started;

  // Said on the caller's thread before each call returned: nothing waited.
  std::lock_guard<std::mutex> lock(recorder.mutex);
  ASSERT_EQ(recorder.outcomes.size(), 5u);
  for (const auto & line : recorder.outcomes) {
    EXPECT_TRUE(unserved(line)) << line;
  }
  EXPECT_NE(recorder.outcomes[2].find("E-stop"), std::string::npos);
  EXPECT_LT(took, std::chrono::seconds(1));
}

TEST(ConsoleClient, ItTearsDownWithARequestInFlightAndStateArriving)
{
  const ConsoleNames names = names_for("teardown");
  FakeConsole console(names, false);
  std::atomic<bool> publishing{true};
  std::thread publisher([&]() {
      while (publishing) {
        console.publish(ConsoleState::RUNNING);
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
    });

  Recorder recorder;
  auto client = std::make_unique<ConsoleClient>(names, recorder.callbacks());
  EXPECT_TRUE(recorder.wait_for([&]() {return !recorder.states.empty();}));
  // A request the fake never answers: in flight when the client goes.
  EXPECT_EQ(
    sent_once_served(recorder, [&]() {client->start_robot();}, &Recorder::progress),
    "Start robot: sent.");

  const auto started = std::chrono::steady_clock::now();
  client.reset();
  recorder.closed = true;
  EXPECT_LT(std::chrono::steady_clock::now() - started, SETTLE);

  publishing = false;
  publisher.join();
  EXPECT_EQ(recorder.after_close, 0) << "a callback ran after the client was destroyed";
  std::lock_guard<std::mutex> lock(recorder.mutex);
  EXPECT_TRUE(recorder.outcomes.empty()) << "the unanswered request was reported as ended";
}
