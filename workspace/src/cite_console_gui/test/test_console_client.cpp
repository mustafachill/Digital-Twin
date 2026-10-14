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
#include "cite_console_gui/enablement.hpp"
#include "cite_interfaces/qos.hpp"

using cite_console_gui::ConsoleCallbacks;
using cite_console_gui::ConsoleClient;
using cite_console_gui::ConsoleNames;
using cite_console_gui::RunProgress;
using cite_interfaces::action::HomeRobot;
using cite_interfaces::action::RunProgram;
using cite_interfaces::action::ValidateThenRun;
using cite_interfaces::msg::ConsoleState;
using cite_interfaces::msg::DivergenceMetrics;
using cite_interfaces::msg::TwinHeartbeat;
using cite_interfaces::msg::TwinMode;
using cite_interfaces::msg::TwinSides;
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
  names.validate_then_run = base + "validate_then_run";
  return names;
}

/// Everything the client told its owner, from its spin thread.
class Recorder
{
public:
  ConsoleCallbacks callbacks()
  {
    ConsoleCallbacks callbacks;
    callbacks.on_state = [this](
      const ConsoleState & state, const std::vector<std::uint8_t> & publisher) {
        record([&]() {states.push_back(state); publishers.push_back(publisher);});
      };
    callbacks.on_state_lost = [this]() {record([&]() {++lost;});};
    callbacks.on_twin_mode = [this](const TwinMode & message) {
        record([&]() {modes.push_back(message);});
      };
    callbacks.on_twin_mode_lost = [this]() {record([&]() {++modes_lost;});};
    callbacks.on_twin_sides = [this](const TwinSides & message) {
        record([&]() {sides.push_back(message);});
      };
    callbacks.on_twin_sides_lost = [this]() {record([&]() {++sides_lost;});};
    callbacks.on_heartbeat = [this]() {record([&]() {++heartbeats;});};
    callbacks.on_heartbeat_lost = [this]() {record([&]() {++heartbeat_lost;});};
    callbacks.on_progress = [this](const std::string & text) {
        record([&]() {progress.push_back(text);});
      };
    callbacks.on_outcome = [this](const std::string & text) {
        record([&]() {outcomes.push_back(text);});
      };
    callbacks.on_divergence = [this](const DivergenceMetrics & message) {
        record([&]() {divergence.push_back(message);});
      };
    callbacks.on_divergence_lost = [this]() {record([&]() {++divergence_lost;});};
    callbacks.on_run_progress = [this](const RunProgress & position) {
        record([&]() {positions.push_back(position);});
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
  /// The publisher identity each state came with, in the same order.
  std::vector<std::vector<std::uint8_t>> publishers;
  std::vector<std::string> progress;
  std::vector<std::string> outcomes;
  int lost{0};
  std::vector<TwinMode> modes;
  int modes_lost{0};
  std::vector<TwinSides> sides;
  int sides_lost{0};
  int heartbeats{0};
  int heartbeat_lost{0};
  std::vector<DivergenceMetrics> divergence;
  int divergence_lost{0};
  std::vector<RunProgress> positions;
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

/// What the fake does with a RunProgram goal.
enum class RunGoal
{
  /// Rejected.
  REJECT,
  /// Accepted; one feedback (cycle 2, step 3 of 7), then it succeeds.
  SUCCEED,
  /// Accepted; one feedback, then it holds until a Stop is served and ends
  /// unsuccessfully, as `cell_console` ends a run its Stop stopped (aborted,
  /// not cancelled: the stop came by StopCell, not by the goal's cancel).
  END_WHEN_STOPPED,
};

/// A console as far as the panel can tell: its state, its services, its
/// actions, on a context of its own. Every request is recorded; services
/// answer success, goals are rejected unless asked otherwise.
class FakeConsole
{
public:
  /// `run` says what a RunProgram goal meets. With `accept_validate_then_run`
  /// a ValidateThenRun goal is accepted, reports one feedback in phase 1
  /// (cycle 1, step 2 of 5) and one in phase 2 (cycle 2, step 4 of 5), and
  /// succeeds having completed three cycles on the twin.
  explicit FakeConsole(
    const ConsoleNames & names, bool answer_start_robot = true, RunGoal run = RunGoal::REJECT,
    bool accept_validate_then_run = false)
  : context_(std::make_shared<rclcpp::Context>())
  {
    const bool accept_run = run != RunGoal::REJECT;
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
        {
          std::lock_guard<std::mutex> lock(mutex_);
          stopped_ = true;
        }
        stop_served_.notify_all();
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
      [this, accept_run](
        const rclcpp_action::GoalUUID &, std::shared_ptr<const RunProgram::Goal> goal) {
        note(
          "run_program " + std::to_string(goal->speed_scale) + " target " +
          std::to_string(goal->target) + " cycles " + std::to_string(goal->cycles));
        return accept_run ? rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE :
               rclcpp_action::GoalResponse::REJECT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<RunProgram>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this, run](std::shared_ptr<rclcpp_action::ServerGoalHandle<RunProgram>> handle) {
        // Off the executor's thread, as a real server runs its goal.
        runner_ = std::thread([this, handle, run]() {
          auto feedback = std::make_shared<RunProgram::Feedback>();
          feedback->cycle = 2;
          feedback->step_index = 3;
          feedback->step_count = 7;
          feedback->step = "Pick";
          handle->publish_feedback(feedback);
            // The feedback is a topic and the result a service: a result that
            // overtook it would drop it at the client, which forgets a goal
            // once it has its result. A test fake's margin, not a sequence.
          std::this_thread::sleep_for(std::chrono::milliseconds(500));
          auto result = std::make_shared<RunProgram::Result>();
          if (run == RunGoal::END_WHEN_STOPPED) {
            // Held until a Stop is served; a hang detector bounds it.
            std::unique_lock<std::mutex> lock(mutex_);
            stop_served_.wait_for(lock, SETTLE, [this]() {return stopped_;});
            lock.unlock();
            result->success = false;
            result->detail = "Start program was stopped; nothing homes on its own";
            result->cycles_completed = 0;
            handle->abort(result);
            return;
          }
          result->success = true;
          result->cycles_completed = 3;
          handle->succeed(result);
          });
      });
    validate_then_run_ = rclcpp_action::create_server<ValidateThenRun>(
      node_, names.validate_then_run,
      [this, accept_validate_then_run](
        const rclcpp_action::GoalUUID &, std::shared_ptr<const ValidateThenRun::Goal> goal) {
        note(
          "validate_then_run " + std::to_string(goal->speed_scale) + " cycles " +
          std::to_string(goal->cycles));
        return accept_validate_then_run ? rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE :
               rclcpp_action::GoalResponse::REJECT;
      },
      [](std::shared_ptr<rclcpp_action::ServerGoalHandle<ValidateThenRun>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](std::shared_ptr<rclcpp_action::ServerGoalHandle<ValidateThenRun>> handle) {
        runner_ = std::thread([handle]() {
          auto validating = std::make_shared<ValidateThenRun::Feedback>();
          validating->phase = ConsoleState::PHASE_VALIDATING;
          validating->cycle = 1;
          validating->step_index = 2;
          validating->step_count = 5;
          validating->step = "Pick";
          handle->publish_feedback(validating);
          // As for RunProgram: a test fake's margin between a topic and a
          // service, so that neither feedback is overtaken.
          std::this_thread::sleep_for(std::chrono::milliseconds(300));
          auto running = std::make_shared<ValidateThenRun::Feedback>();
          running->phase = ConsoleState::PHASE_RUNNING;
          running->cycle = 2;
          running->step_index = 4;
          running->step_count = 5;
          running->step = "Place";
          handle->publish_feedback(running);
          std::this_thread::sleep_for(std::chrono::milliseconds(500));
          auto result = std::make_shared<ValidateThenRun::Result>();
          result->success = true;
          result->detail = "passed in simulation (1 cycle), then 3 cycle(s) on the twin";
          result->ended_in = ConsoleState::PHASE_RUNNING;
          result->cycles_completed = 3;
          handle->succeed(result);
          });
      });
    rclcpp::ExecutorOptions executor_options;
    executor_options.context = context_;
    executor_ = std::make_unique<rclcpp::executors::SingleThreadedExecutor>(executor_options);
    executor_->add_node(node_);
    spinner_ = std::thread([this]() {executor_->spin();});
  }

  ~FakeConsole()
  {
    if (runner_.joinable()) {
      runner_.join();
    }
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

  /// A second state publisher on the same topic, as a console restarted
  /// before its predecessor's publisher unmatched; publishes `state` on it.
  void publish_from_another(std::uint8_t state)
  {
    other_state_ = state_node_->create_publisher<ConsoleState>(
      state_->get_topic_name(), cite::qos::latched());
    ConsoleState message;
    message.state = state;
    other_state_->publish(message);
  }

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
  rclcpp::Publisher<ConsoleState>::SharedPtr other_state_;
  rclcpp::Service<StartRobot>::SharedPtr start_robot_;
  rclcpp::Service<ConfirmOperator>::SharedPtr confirm_;
  rclcpp::Service<StopCell>::SharedPtr stop_;
  rclcpp_action::Server<HomeRobot>::SharedPtr home_;
  rclcpp_action::Server<RunProgram>::SharedPtr run_;
  rclcpp_action::Server<ValidateThenRun>::SharedPtr validate_then_run_;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread spinner_;
  std::thread runner_;
  std::mutex mutex_;
  std::condition_variable stop_served_;
  bool stopped_{false};
  std::vector<std::string> requests_;
};

/// The twin boundary as far as the panel can tell on its own domain: its
/// latched TwinMode and TwinSides and its heartbeat, on a context of its own. Each
/// publisher is on a node no executor holds, so withdrawing it unmatches it.
class FakeBoundary
{
public:
  FakeBoundary()
  : context_(std::make_shared<rclcpp::Context>())
  {
    rclcpp::InitOptions options;
    options.shutdown_on_signal = false;
    context_->init(0, nullptr, options);
    node_ = std::make_shared<rclcpp::Node>(
      "fake_twin_boundary", rclcpp::NodeOptions().context(context_));
    mode_ = node_->create_publisher<TwinMode>(TwinMode::TOPIC, cite::qos::latched());
    sides_ = node_->create_publisher<TwinSides>(TwinSides::TOPIC, cite::qos::latched());
    heartbeat_ = node_->create_publisher<TwinHeartbeat>(TwinHeartbeat::TOPIC, cite::qos::state());
    divergence_ = node_->create_publisher<DivergenceMetrics>(
      DivergenceMetrics::TOPIC, cite::qos::state());
  }

  ~FakeBoundary() {context_->shutdown("the test ended");}

  void publish_mode(std::uint8_t mode)
  {
    TwinMode message;
    message.mode = mode;
    mode_->publish(message);
  }

  void publish_sides(const std::vector<std::string> & running, const std::string & detail)
  {
    TwinSides message;
    message.running = running;
    message.commandable = {running.front()};
    message.detail = detail;
    sides_->publish(message);
  }

  void beat()
  {
    TwinHeartbeat message;
    message.sequence = ++sequence_;
    heartbeat_->publish(message);
  }

  /// The heartbeat publisher's subscriber count: a heartbeat sent before the
  /// panel matched reaches nobody (STATE is volatile).
  std::size_t heartbeat_subscribers() const {return heartbeat_->get_subscription_count();}

  /// One sample for `asset`, as the boundary publishes one per asset.
  void publish_divergence(const std::string & asset, bool valid)
  {
    DivergenceMetrics message;
    message.asset_id = asset;
    message.valid = valid;
    divergence_->publish(message);
  }

  std::size_t divergence_subscribers() const {return divergence_->get_subscription_count();}

  void withdraw_divergence() {divergence_.reset();}
  void withdraw_mode() {mode_.reset();}
  void withdraw_sides() {sides_.reset();}
  void withdraw_heartbeat() {heartbeat_.reset();}

private:
  rclcpp::Context::SharedPtr context_;
  rclcpp::Node::SharedPtr node_;
  rclcpp::Publisher<TwinMode>::SharedPtr mode_;
  rclcpp::Publisher<TwinSides>::SharedPtr sides_;
  rclcpp::Publisher<TwinHeartbeat>::SharedPtr heartbeat_;
  rclcpp::Publisher<DivergenceMetrics>::SharedPtr divergence_;
  std::uint64_t sequence_{0};
};

bool unserved(const std::string & line)
{
  return line.find("does not serve it right now") != std::string::npos;
}

/// Send with `send` until the client's graph has discovered the server, then
/// return the first line said after the send that reached it. An empty line -
/// the last outcome cleared as a new request is sent (T-05) - is not one.
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
    const auto said = [&]() -> std::string {
        for (std::size_t at = before; at < (recorder.*channel).size(); ++at) {
          if (!(recorder.*channel)[at].empty()) {
            return (recorder.*channel)[at];
          }
        }
        return "";
      };
    if (!recorder.wait_for([&]() {return !said().empty();})) {
      return "";
    }
    std::lock_guard<std::mutex> lock(recorder.mutex);
    return said();
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

  // ADR-0073: the scale and cycles as given, and no target.
  EXPECT_EQ(
    sent_once_served(
      recorder, [&]() {client.validate_then_run(0.5, 2);}, &Recorder::progress),
    "Validate then run: rejected by the console (see last error).");
  const auto requests = console.requests();
  ASSERT_FALSE(requests.empty());
  EXPECT_EQ(requests.back(), "validate_then_run " + std::to_string(0.5) + " cycles 2");
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

TEST(ConsoleClient, EachStateCarriesItsPublishersIdentity)
{
  // R-02: a console restarted with no unmatch in between is told apart by
  // its publisher's GID, which the panel's selection is settled against.
  const ConsoleNames names = names_for("identity");
  FakeConsole console(names);
  console.publish(ConsoleState::READY);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.states.size() == 1;}));

  // Published while the first publisher is still matched: never an unmatch.
  console.publish_from_another(ConsoleState::NOT_STARTED);
  ASSERT_TRUE(
    recorder.wait_for(
      [&]() {
        for (const auto & state : recorder.states) {
          if (state.state == ConsoleState::NOT_STARTED) {
            return true;
          }
        }
        return false;
      }));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  EXPECT_EQ(recorder.lost, 0);
  ASSERT_EQ(recorder.publishers.size(), recorder.states.size());
  const std::vector<std::uint8_t> first = recorder.publishers.front();
  EXPECT_FALSE(first.empty());
  EXPECT_NE(first, std::vector<std::uint8_t>(first.size(), 0)) << "no GID was read";
  for (std::size_t i = 0; i < recorder.states.size(); ++i) {
    if (recorder.states[i].state == ConsoleState::NOT_STARTED) {
      EXPECT_NE(recorder.publishers[i], first) << "two publishers, one identity";
    } else {
      EXPECT_EQ(recorder.publishers[i], first);
    }
  }
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
  client.validate_then_run(1.0, 1);
  const auto took = std::chrono::steady_clock::now() - started;

  // Said on the caller's thread before each call returned: nothing waited.
  std::lock_guard<std::mutex> lock(recorder.mutex);
  ASSERT_EQ(recorder.outcomes.size(), 6u);
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
  for (const auto & line : recorder.outcomes) {
    EXPECT_TRUE(line.empty()) << "the unanswered request was reported as ended: " << line;
  }
}

TEST(ConsoleClient, TheBoundarysSidesAreHeardAndTheirPublisherLeavingIsSaid)
{
  // Latched: published before the client exists, still heard.
  FakeBoundary boundary;
  boundary.publish_sides({"plant", "counterpart"}, "counterpart: deadman TRIPPED");
  Recorder recorder;
  ConsoleClient client(names_for("sides"), recorder.callbacks());
  ASSERT_TRUE(recorder.wait_for([&]() {return !recorder.sides.empty();}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.sides.back().running, (std::vector<std::string>{"plant", "counterpart"}));
    EXPECT_EQ(recorder.sides.back().detail, "counterpart: deadman TRIPPED");
    EXPECT_EQ(recorder.sides_lost, 0);
  }
  boundary.withdraw_sides();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.sides_lost == 1;}))
    << "TwinSides' publisher left and the panel was not told";
}

TEST(ConsoleClient, EachHeartbeatArrivalIsSaidAndItsPublisherLeavingIsAbsence)
{
  FakeBoundary boundary;
  Recorder recorder;
  ConsoleClient client(names_for("heartbeat"), recorder.callbacks());
  // STATE is volatile: a heartbeat sent before the panel's subscription
  // matched reaches nobody (CLAUDE.md §10), so the first is sent once it has.
  // A hang detector, ended by the match.
  const auto deadline = std::chrono::steady_clock::now() + SETTLE;
  while (boundary.heartbeat_subscribers() == 0 && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  ASSERT_GT(boundary.heartbeat_subscribers(), 0u);
  boundary.beat();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.heartbeats > 0;}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.heartbeat_lost, 0);
  }
  boundary.withdraw_heartbeat();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.heartbeat_lost == 1;}))
    << "the heartbeat's publisher left and the panel was not told";
}

TEST(ConsoleClient, TheModeIsForgottenOnlyWhenItsOwnPublisherLeaves)
{
  // R-02: TwinMode is latched and published on change. The console leaving
  // says nothing about it; its own publisher leaving is what makes it unknown.
  const ConsoleNames names = names_for("mode");
  FakeBoundary boundary;
  boundary.publish_mode(TwinMode::MODE_SIM);
  auto console = std::make_unique<FakeConsole>(names);
  console->publish(ConsoleState::READY);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  ASSERT_TRUE(
    recorder.wait_for([&]() {return !recorder.modes.empty() && !recorder.states.empty();}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.modes.back().mode, TwinMode::MODE_SIM);
  }

  console->withdraw_state();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.lost == 1;}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.modes_lost, 0) << "the console leaving was taken for the mode's";
  }

  boundary.withdraw_mode();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.modes_lost == 1;}))
    << "TwinMode's publisher left and the panel was not told";
}

TEST(ConsoleClient, EachDivergenceSampleIsHeardAndItsPublisherLeavingIsSaid)
{
  // The frame's "Twin fidelity" card (ADR-0074): STATE, as the boundary
  // publishes it, so a sample sent before the panel matched reaches nobody.
  FakeBoundary boundary;
  Recorder recorder;
  ConsoleClient client(names_for("divergence"), recorder.callbacks());
  const auto deadline = std::chrono::steady_clock::now() + SETTLE;
  while (boundary.divergence_subscribers() == 0 && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  }
  ASSERT_GT(boundary.divergence_subscribers(), 0u);
  boundary.publish_divergence("picker", false);
  ASSERT_TRUE(recorder.wait_for([&]() {return !recorder.divergence.empty();}));
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    EXPECT_EQ(recorder.divergence.back().asset_id, "picker");
    EXPECT_FALSE(recorder.divergence.back().valid);
    EXPECT_EQ(recorder.divergence_lost, 0);
  }
  boundary.withdraw_divergence();
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.divergence_lost == 1;}))
    << "DivergenceMetrics' publisher left and the panel was not told";
}

TEST(ConsoleClient, ARunsFeedbackIsItsPositionAndItsEndClearsIt)
{
  const ConsoleNames names = names_for("run_progress");
  FakeConsole console(names, true, RunGoal::SUCCEED);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  // Sent once the action server is discovered; three cycles asked for.
  const std::string accepted = sent_once_served(
    recorder, [&]() {client.run_program(1.0, ConsoleState::TARGET_SIM, 3);}, &Recorder::progress);
  EXPECT_EQ(accepted, "Start program: accepted.");
  ASSERT_TRUE(recorder.wait_for([&]() {return !recorder.outcomes.empty();}));
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.positions.size() >= 2;}));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  const RunProgress & running = recorder.positions.front();
  EXPECT_TRUE(running.active);
  EXPECT_EQ(running.cycle, 2u);
  EXPECT_EQ(running.cycles, 3u);
  EXPECT_EQ(running.step_index, 3u);
  EXPECT_EQ(running.step_count, 7u);
  EXPECT_FALSE(recorder.positions.back().active) << "the run ended and its position stayed";
}

TEST(ConsoleClient, ARejectedRunHasNoPosition)
{
  const ConsoleNames names = names_for("run_rejected");
  FakeConsole console(names);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  sent_once_served(
    recorder, [&]() {client.run_program(1.0, ConsoleState::TARGET_SIM, 1);}, &Recorder::progress);
  ASSERT_TRUE(recorder.wait_for([&]() {return !recorder.positions.empty();}));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  EXPECT_FALSE(recorder.positions.back().active);
}

TEST(ConsoleClient, AValidateThenRunsFeedbackIsItsPhaseAndItsPosition)
{
  // R-04: phase 1 is one cycle on the simulation, whatever the goal's cycles
  // (ValidateThenRun.action); phase 2 runs the goal's cycles on the twin. Each
  // is labelled as the operator reads its phase, and the end clears it.
  const ConsoleNames names = names_for("validate_progress");
  FakeConsole console(names, true, RunGoal::REJECT, true);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  EXPECT_EQ(
    sent_once_served(
      recorder, [&]() {client.validate_then_run(0.5, 3);}, &Recorder::progress),
    "Validate then run: accepted.");
  ASSERT_TRUE(
    recorder.wait_for(
      [&]() {return !recorder.outcomes.empty() && !recorder.outcomes.back().empty();}));
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.positions.size() >= 3;}));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  const RunProgress & validating = recorder.positions[0];
  EXPECT_TRUE(validating.active);
  EXPECT_EQ(
    validating.phase,
    cite_console_gui::validation_phase_name(cite_console_gui::ValidationPhase::VALIDATING));
  EXPECT_EQ(validating.cycle, 1u);
  EXPECT_EQ(validating.cycles, 1u) << "phase 1 is one cycle, not the goal's";
  EXPECT_EQ(validating.step_index, 2u);
  EXPECT_EQ(validating.step_count, 5u);
  const RunProgress & running = recorder.positions[1];
  EXPECT_TRUE(running.active);
  EXPECT_EQ(
    running.phase,
    cite_console_gui::validation_phase_name(cite_console_gui::ValidationPhase::RUNNING));
  EXPECT_EQ(running.cycle, 2u);
  EXPECT_EQ(running.cycles, 3u) << "phase 2 runs the goal's cycles";
  EXPECT_FALSE(recorder.positions.back().active) << "the request ended and its position stayed";
  // Its progress line is gone with it, and the outcome is the console's.
  EXPECT_EQ(recorder.progress.back(), "") << "the progress line outlived its request";
  EXPECT_EQ(
    recorder.outcomes.back(),
    "Validate then run: done. passed in simulation (1 cycle), then 3 cycle(s) on the twin "
    "Ended in: Running twin. Cycles completed on the twin: 3.");
}

TEST(ConsoleClient, ANewRequestClearsTheLastOutcomeAndItsEndClearsItsProgress)
{
  // T-05 (c, d): while a request runs, no earlier request's outcome is shown
  // as the latest; once it has ended, its progress is not shown as ongoing.
  const ConsoleNames names = names_for("outcome_cleared");
  FakeConsole console(names, true, RunGoal::SUCCEED);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  EXPECT_EQ(
    sent_once_served(recorder, [&]() {client.start_robot();}, &Recorder::outcomes),
    "Start robot: done. fake start_robot");
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    ASSERT_GE(recorder.progress.size(), 2u);
    EXPECT_EQ(recorder.progress[recorder.progress.size() - 2], "Start robot: sent.");
    EXPECT_EQ(recorder.progress.back(), "") << "Start robot stayed 'sent' once it was done";
  }

  std::size_t before = 0;
  {
    std::lock_guard<std::mutex> lock(recorder.mutex);
    before = recorder.outcomes.size();
  }
  client.run_program(1.0, ConsoleState::TARGET_SIM, 3);
  ASSERT_TRUE(recorder.wait_for([&]() {return recorder.outcomes.size() >= before + 2;}));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  EXPECT_EQ(recorder.outcomes[before], "") << "the last outcome was not cleared on sending";
  EXPECT_EQ(recorder.outcomes[before + 1].rfind("Start program: done.", 0), 0u)
    << recorder.outcomes[before + 1];
  EXPECT_EQ(recorder.progress.back(), "");
}

TEST(ConsoleClient, ARunEndedByAStopIsSaidStoppedNotFailed)
{
  // T-05 (b): the console accepted the operator's Stop while the run was in
  // flight, and the run then ended unsuccessfully: it was stopped.
  const ConsoleNames names = names_for("stopped");
  FakeConsole console(names, true, RunGoal::END_WHEN_STOPPED);
  Recorder recorder;
  ConsoleClient client(names, recorder.callbacks());
  EXPECT_EQ(
    sent_once_served(
      recorder, [&]() {client.run_program(1.0, ConsoleState::TARGET_SIM, 2);},
      &Recorder::progress),
    "Start program: accepted.");
  client.stop();
  ASSERT_TRUE(
    recorder.wait_for(
      [&]() {
        for (const auto & line : recorder.outcomes) {
          if (line.rfind("Start program:", 0) == 0) {
            return true;
          }
        }
        return false;
      }));
  std::lock_guard<std::mutex> lock(recorder.mutex);
  std::string run_outcome;
  for (const auto & line : recorder.outcomes) {
    if (line.rfind("Start program:", 0) == 0) {
      run_outcome = line;
    }
  }
  EXPECT_EQ(
    run_outcome,
    "Start program: stopped. Start program was stopped; nothing homes on its own "
    "Cycles completed: 0.");
}
