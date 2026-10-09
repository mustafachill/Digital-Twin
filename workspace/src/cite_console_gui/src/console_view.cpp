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

#include "cite_console_gui/console_view.hpp"

#include <string>

#include "cite_interfaces/msg/twin_mode.hpp"

namespace cite_console_gui
{

using cite_interfaces::msg::ConsoleState;
using cite_interfaces::msg::TwinMode;

Phase phase_from(std::uint8_t state)
{
  switch (state) {
    case ConsoleState::NOT_STARTED:
      return Phase::NOT_STARTED;
    case ConsoleState::STARTING:
      return Phase::STARTING;
    case ConsoleState::READY:
      return Phase::READY;
    case ConsoleState::HOMING:
      return Phase::HOMING;
    case ConsoleState::AWAITING_OPERATOR:
      return Phase::AWAITING_OPERATOR;
    case ConsoleState::RUNNING:
      return Phase::RUNNING;
    case ConsoleState::STOPPING:
      return Phase::STOPPING;
    case ConsoleState::FAULT:
      return Phase::FAULT;
    default:
      return Phase::UNKNOWN;
  }
}

Target target_from(std::uint8_t value)
{
  switch (value) {
    case ConsoleState::TARGET_SIM:
      return Target::SIM;
    case ConsoleState::TARGET_REAL:
      return Target::REAL;
    case ConsoleState::TARGET_TWIN:
      return Target::TWIN;
    default:
      return Target::NONE;
  }
}

std::uint8_t target_value(Target target)
{
  switch (target) {
    case Target::SIM:
      return ConsoleState::TARGET_SIM;
    case Target::REAL:
      return ConsoleState::TARGET_REAL;
    case Target::TWIN:
      return ConsoleState::TARGET_TWIN;
    case Target::NONE:
      break;
  }
  return 0;
}

ConsoleView view_from(const ConsoleState & state)
{
  ConsoleView view;
  view.heard = true;
  view.phase = phase_from(state.state);
  view.robot_started = state.robot_started;
  view.busy = state.busy;
  view.plant_at_start = state.plant_at_start;
  view.counterpart_at_start = state.counterpart_at_start;
  for (const std::uint8_t value : state.available_targets) {
    const Target target = target_from(value);
    if (target != Target::NONE) {
      view.available_targets.insert(target);
    }
  }
  view.minimum_speed_scale = state.minimum_speed_scale;
  view.twin_in_sim = state.twin_mode == TwinMode::MODE_SIM;
  view.has_physical_side = !state.physical_sides.empty();
  return view;
}

std::string twin_mode_name(std::uint8_t mode)
{
  switch (mode) {
    case TwinMode::MODE_SIM:
      return "SIM";
    case TwinMode::MODE_REAL:
      return "REAL";
    case TwinMode::MODE_SHADOW:
      return "SHADOW";
    case TwinMode::MODE_VALIDATED:
      return "VALIDATED";
    case TwinMode::MODE_CLOSED_LOOP:
      return "CLOSED_LOOP";
    case TwinMode::MODE_VIRTUAL_LEAD:
      return "VIRTUAL_LEAD";
    case ConsoleState::TWIN_MODE_UNKNOWN:
      return "unknown";
    default:
      return "unrecognised (" + std::to_string(mode) + ")";
  }
}

}  // namespace cite_console_gui
