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

#include "cite_console_gui/console_client.hpp"

#include <memory>
#include <string>
#include <utility>

#include "cite_interfaces/qos.hpp"

namespace cite_console_gui
{

using cite_interfaces::msg::ConsoleState;
using cite_interfaces::msg::TwinMode;
using cite_interfaces::srv::ConfirmOperator;
using cite_interfaces::srv::StartRobot;
using cite_interfaces::srv::StopCell;

namespace
{

std::string answered(const std::string & request, bool success, const std::string & detail)
{
  return request + (success ? ": done. " : ": refused or failed. ") + detail;
}

}  // namespace

ConsoleClient::ConsoleClient(const ConsoleNames & names, ConsoleCallbacks callbacks)
: callbacks_(std::move(callbacks)), context_(std::make_shared<rclcpp::Context>())
{
  rclcpp::InitOptions init_options;
  // The window owns SIGINT. A context of our own installs no handler, and one
  // that is shut down by a signal would leave a panel that silently hears
  // nothing.
  init_options.shutdown_on_signal = false;
  context_->init(0, nullptr, init_options);

  node_ = std::make_shared<rclcpp::Node>(
    "cell_console_panel",
    rclcpp::NodeOptions()
    .context(context_)
    .start_parameter_services(false)
    .start_parameter_event_publisher(false));

  // Both latched, matching their publishers: `cell_console` publishes its
  // state LATCHED, and the twin boundary its mode (cite_interfaces/qos.hpp).
  // A panel started late hears the current value at once.
  //
  // The console's going away is an EVENT, not a poll (P-R04): the
  // subscription's matched status says when its last publisher unmatched,
  // and that is when the panel says "No console".
  rclcpp::SubscriptionOptions state_options;
  state_options.event_callbacks.matched_callback = [this](rclcpp::MatchedInfo & info) {
      on_state_matched(info.current_count);
    };
  state_sub_ = node_->create_subscription<ConsoleState>(
    names.state, cite::qos::latched(),
    [this](const ConsoleState & state) {
      heard_ = true;
      if (callbacks_.on_state) {
        callbacks_.on_state(state);
      }
    },
    state_options);
  twin_mode_sub_ = node_->create_subscription<TwinMode>(
    TwinMode::TOPIC, cite::qos::latched(),
    [this](const TwinMode & mode) {
      if (callbacks_.on_twin_mode) {
        callbacks_.on_twin_mode(mode);
      }
    });

  start_robot_ = node_->create_client<StartRobot>(names.start_robot);
  confirm_operator_ = node_->create_client<ConfirmOperator>(names.confirm_operator);
  stop_ = node_->create_client<StopCell>(names.stop);
  home_ = rclcpp_action::create_client<Home>(node_, names.home);
  run_program_ = rclcpp_action::create_client<Run>(node_, names.run_program);

  rclcpp::ExecutorOptions executor_options;
  executor_options.context = context_;
  executor_ = std::make_unique<rclcpp::executors::SingleThreadedExecutor>(executor_options);
  executor_->add_node(node_);
  spinner_ = std::thread([this]() {executor_->spin();});
}

ConsoleClient::~ConsoleClient()
{
  // Shutting the context down ends `spin` whether or not it had started yet,
  // which `cancel` alone does not guarantee.
  context_->shutdown("the console panel was closed");
  executor_->cancel();
  if (spinner_.joinable()) {
    spinner_.join();
  }
  // Without a notification: the executor is no longer spinning, and its
  // guard condition belongs to a context that has just been shut down.
  executor_->remove_node(node_, false);
}

void ConsoleClient::on_state_matched(std::size_t publishers)
{
  if (heard_ && publishers == 0) {
    heard_ = false;
    if (callbacks_.on_state_lost) {
      callbacks_.on_state_lost();
    }
  }
}

void ConsoleClient::outcome(const std::string & text) const
{
  if (callbacks_.on_outcome) {
    callbacks_.on_outcome(text);
  }
}

void ConsoleClient::progress(const std::string & text) const
{
  if (callbacks_.on_progress) {
    callbacks_.on_progress(text);
  }
}

void ConsoleClient::start_robot()
{
  if (!start_robot_->service_is_ready()) {
    outcome("Start robot: the console does not serve it right now.");
    return;
  }
  progress("Start robot: sent.");
  start_robot_->async_send_request(
    std::make_shared<StartRobot::Request>(),
    [this](rclcpp::Client<StartRobot>::SharedFuture future) {
      const auto response = future.get();
      outcome(answered("Start robot", response->success, response->detail));
    });
}

void ConsoleClient::confirm_operator()
{
  if (!confirm_operator_->service_is_ready()) {
    outcome("Confirm: the console does not serve it right now.");
    return;
  }
  confirm_operator_->async_send_request(
    std::make_shared<ConfirmOperator::Request>(),
    [this](rclcpp::Client<ConfirmOperator>::SharedFuture future) {
      const auto response = future.get();
      outcome(answered("Confirm", response->success, response->detail));
    });
}

void ConsoleClient::stop()
{
  if (!stop_->service_is_ready()) {
    outcome("Stop: the console does not serve it right now. Use the E-stop if anything moves.");
    return;
  }
  stop_->async_send_request(
    std::make_shared<StopCell::Request>(),
    [this](rclcpp::Client<StopCell>::SharedFuture future) {
      const auto response = future.get();
      outcome(answered("Stop", response->success, response->detail));
    });
}

void ConsoleClient::home(double speed_scale, std::uint8_t target)
{
  if (!home_->action_server_is_ready()) {
    outcome("Home: the console does not serve it right now.");
    return;
  }
  Home::Goal goal;
  goal.speed_scale = speed_scale;
  goal.target = target;

  rclcpp_action::Client<Home>::SendGoalOptions options;
  options.goal_response_callback =
    [this](const rclcpp_action::ClientGoalHandle<Home>::SharedPtr & handle) {
      progress(handle ? "Home: accepted." : "Home: rejected by the console (see last error).");
    };
  options.feedback_callback =
    [this](rclcpp_action::ClientGoalHandle<Home>::SharedPtr,
    const std::shared_ptr<const Home::Feedback> feedback) {
      progress("Home: " + feedback->step);
    };
  options.result_callback =
    [this](const rclcpp_action::ClientGoalHandle<Home>::WrappedResult & result) {
      if (!result.result) {
        outcome("Home: ended with no result.");
        return;
      }
      outcome(answered("Home", result.result->success, result.result->detail));
    };
  home_->async_send_goal(goal, options);
}

void ConsoleClient::run_program(
  double speed_scale, std::uint8_t target, std::uint32_t cycles)
{
  if (!run_program_->action_server_is_ready()) {
    outcome("Start program: the console does not serve it right now.");
    return;
  }
  Run::Goal goal;
  goal.speed_scale = speed_scale;
  goal.target = target;
  goal.cycles = cycles;

  rclcpp_action::Client<Run>::SendGoalOptions options;
  options.goal_response_callback =
    [this](const rclcpp_action::ClientGoalHandle<Run>::SharedPtr & handle) {
      progress(
        handle ? "Start program: accepted." :
        "Start program: rejected by the console (see last error).");
    };
  options.feedback_callback =
    [this](rclcpp_action::ClientGoalHandle<Run>::SharedPtr,
    const std::shared_ptr<const Run::Feedback> feedback) {
      progress(
        "Cycle " + std::to_string(feedback->cycle) + ", step " +
        std::to_string(feedback->step_index) + " of " + std::to_string(feedback->step_count) +
        ": " + feedback->step);
    };
  options.result_callback =
    [this](const rclcpp_action::ClientGoalHandle<Run>::WrappedResult & result) {
      if (!result.result) {
        outcome("Start program: ended with no result.");
        return;
      }
      outcome(
        answered("Start program", result.result->success, result.result->detail) +
        " Cycles completed: " + std::to_string(result.result->cycles_completed) + ".");
    };
  run_program_->async_send_goal(goal, options);
}

}  // namespace cite_console_gui
