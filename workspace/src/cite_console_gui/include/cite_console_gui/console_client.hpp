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
// NAMES ARE HANDED IN. The console's six names come from the generated GUI
// configuration (generate/gui.py) and the twin mode's from the contract's own
// `TwinMode::TOPIC`. This file builds no name.
//
// No clock is read and nothing runs on a timer: the console's going away is the
// state subscription's matched event (its last publisher unmatched), so
// `use_sim_time` has nothing to change.

#ifndef CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_
#define CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <thread>

#include "cite_interfaces/action/home_robot.hpp"
#include "cite_interfaces/action/run_program.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"
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
};

/// What the client tells its owner. Each is called on the spin thread.
struct ConsoleCallbacks
{
  std::function<void(const cite_interfaces::msg::ConsoleState &)> on_state;
  /// The console's state publisher left the graph after it had been heard.
  std::function<void()> on_state_lost;
  std::function<void(const cite_interfaces::msg::TwinMode &)> on_twin_mode;
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
  void home(double speed_scale);
  void run_program(double speed_scale, std::uint32_t cycles);

private:
  using Home = cite_interfaces::action::HomeRobot;
  using Run = cite_interfaces::action::RunProgram;

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
  rclcpp::Client<cite_interfaces::srv::StartRobot>::SharedPtr start_robot_;
  rclcpp::Client<cite_interfaces::srv::ConfirmOperator>::SharedPtr confirm_operator_;
  rclcpp::Client<cite_interfaces::srv::StopCell>::SharedPtr stop_;
  rclcpp_action::Client<Home>::SharedPtr home_;
  rclcpp_action::Client<Run>::SharedPtr run_program_;
  /// Touched only on the spin thread.
  bool heard_{false};
  std::thread spinner_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_CLIENT_HPP_
