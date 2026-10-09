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

// The panel's ROS half: what it hears and what it asks, with no Qt in it.
//
// ONE CONTEXT OF ITS OWN. The plugin lives in the `gz sim` GUI process, which
// owns no ROS context and installs its own signal handling. This client
// initializes a private `rclcpp::Context` - without rclcpp's signal handlers, so
// Ctrl-C stays the window's - on whatever domain the process was started on,
// which is the plant's: the plant's launch starts the window, and the console
// serves on the plant's domain (ADR-0071 decision 1). It spins that context on a
// thread of its own and never on the GUI thread.
//
// NOTHING HERE BLOCKS. Every request is sent asynchronously and answered in a
// callback; a server that is not there is reported, never waited for. Every
// callback runs on the spin thread and is handed to the owner, which must move
// it to its own thread before touching anything it shares (the plugin queues
// each one onto the Qt thread).
//
// NAMES ARE HANDED IN. The console's seven names come from the generated GUI
// configuration (generate/gui.py), and the twin boundary's three - its mode,
// its sides and its heartbeat - from the contract's own `TOPIC` constants
// (TwinMode, TwinSides, TwinHeartbeat). This file builds no name.
//
// No clock is read and nothing runs on a timer: the console's, the sides' and
// the heartbeat's going away are their subscriptions' matched events (the last
// publisher unmatched), so `use_sim_time` has nothing to change. How long ago a
// heartbeat arrived is the owner's to time, on its own steady clock
// (TwinHeartbeat.msg: a receiver concludes arrival, never age).

#ifndef CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_
#define CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "cite_interfaces/action/home_robot.hpp"
#include "cite_interfaces/action/run_program.hpp"
#include "cite_interfaces/action/validate_then_run.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/twin_heartbeat.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"
#include "cite_interfaces/msg/twin_sides.hpp"
#include "cite_interfaces/srv/confirm_operator.hpp"
#include "cite_interfaces/srv/start_robot.hpp"
#include "cite_interfaces/srv/stop_cell.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"

namespace cite_console_gui
{

/// The console's names, by the keys the plan's `console:` block uses.
struct ConsoleNames
{
  std::string state;
  std::string start_robot;
  std::string confirm_operator;
  std::string stop;
  std::string home;
  std::string run_program;
  std::string validate_then_run;
};

/// What the client tells its owner. Each is called on the spin thread.
struct ConsoleCallbacks
{
  /// A ConsoleState, with the rmw GID of the publisher that sent it: a GID
  /// that differs from the last one heard is a console that came back, even
  /// when its predecessor's unmatch was never seen.
  std::function<void(const cite_interfaces::msg::ConsoleState &,
    const std::vector<std::uint8_t> &)> on_state;
  /// The console's state publisher left the graph after it had been heard.
  std::function<void()> on_state_lost;
  std::function<void(const cite_interfaces::msg::TwinMode &)> on_twin_mode;
  /// The boundary's TwinSides (latched, on change).
  std::function<void(const cite_interfaces::msg::TwinSides &)> on_twin_sides;
  /// TwinSides' publisher left the graph after it had been heard.
  std::function<void()> on_twin_sides_lost;
  /// A boundary heartbeat arrived on this domain. Its content is not passed:
  /// what may be concluded from one is its arrival (TwinHeartbeat.msg).
  std::function<void()> on_heartbeat;
  /// The heartbeat's last publisher left the graph after one had been heard.
  std::function<void()> on_heartbeat_lost;
  /// A request's progress, as the operator reads it.
  std::function<void(const std::string &)> on_progress;
  /// How a request ended, or why it could not be sent.
  std::function<void(const std::string &)> on_outcome;
};

class ConsoleClient
{
public:
  ConsoleClient(const ConsoleNames & names, ConsoleCallbacks callbacks);
  ~ConsoleClient();

  ConsoleClient(const ConsoleClient &) = delete;
  ConsoleClient & operator=(const ConsoleClient &) = delete;

  void start_robot();
  void confirm_operator();
  void stop();
  /// `target` is the ConsoleState.TARGET_* the goal carries (ADR-0072), sent
  /// as given: the console, not this client, refuses one it does not serve.
  void home(double speed_scale, std::uint8_t target);
  void run_program(double speed_scale, std::uint8_t target, std::uint32_t cycles);
  /// ValidateThenRun (ADR-0073): no target - phase 1 is the simulation, phase
  /// 2 the twin, both the console's to choose.
  void validate_then_run(double speed_scale, std::uint32_t cycles);

private:
  using Home = cite_interfaces::action::HomeRobot;
  using Run = cite_interfaces::action::RunProgram;
  using ValidateThenRun = cite_interfaces::action::ValidateThenRun;

  /// The state subscription's matched status changed; ``publishers`` is how
  /// many publishers it is matched with now.
  void on_state_matched(std::size_t publishers);
  void outcome(const std::string & text) const;
  void progress(const std::string & text) const;

  ConsoleCallbacks callbacks_;
  rclcpp::Context::SharedPtr context_;
  rclcpp::Node::SharedPtr node_;
  std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  rclcpp::Subscription<cite_interfaces::msg::ConsoleState>::SharedPtr state_sub_;
  rclcpp::Subscription<cite_interfaces::msg::TwinMode>::SharedPtr twin_mode_sub_;
  rclcpp::Subscription<cite_interfaces::msg::TwinSides>::SharedPtr twin_sides_sub_;
  rclcpp::Subscription<cite_interfaces::msg::TwinHeartbeat>::SharedPtr heartbeat_sub_;
  rclcpp::Client<cite_interfaces::srv::StartRobot>::SharedPtr start_robot_;
  rclcpp::Client<cite_interfaces::srv::ConfirmOperator>::SharedPtr confirm_operator_;
  rclcpp::Client<cite_interfaces::srv::StopCell>::SharedPtr stop_;
  rclcpp_action::Client<Home>::SharedPtr home_;
  rclcpp_action::Client<Run>::SharedPtr run_program_;
  rclcpp_action::Client<ValidateThenRun>::SharedPtr validate_then_run_;
  /// Touched only on the spin thread.
  bool heard_{false};
  bool sides_heard_{false};
  bool heartbeat_heard_{false};
  std::thread spinner_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_
