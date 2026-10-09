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
#include <utility>
#include <vector>

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

ValidationPhase validation_phase_from(std::uint8_t value)
{
  switch (value) {
    case ConsoleState::PHASE_NONE:
      return ValidationPhase::NONE;
    case ConsoleState::PHASE_VALIDATING:
      return ValidationPhase::VALIDATING;
    case ConsoleState::PHASE_RUNNING:
      return ValidationPhase::RUNNING;
    default:
      return ValidationPhase::UNKNOWN;
  }
}

ConsoleView view_from(const ConsoleState & state, std::vector<std::uint8_t> publisher)
{
  ConsoleView view;
  view.heard = true;
  view.publisher = std::move(publisher);
  view.phase = phase_from(state.state);
  view.robot_started = state.robot_started;
  view.busy = state.busy;
  view.plant_at_start = state.plant_at_start;
  view.counterpart_at_start = state.counterpart_at_start;
  view.counterpart_running = state.counterpart_running;
  for (const std::uint8_t value : state.available_targets) {
    view.served_values.insert(value);
    const Target target = target_from(value);
    if (target != Target::NONE) {
      view.available_targets.insert(target);
    }
  }
  for (const std::uint8_t value : state.startable_targets) {
    const Target target = target_from(value);
    if (target != Target::NONE) {
      view.startable_targets.insert(target);
    }
  }
  for (const std::uint8_t value : state.floored_targets) {
    const Target target = target_from(value);
    if (target != Target::NONE) {
      view.floored_targets.insert(target);
    }
  }
  view.minimum_speed_scale = state.minimum_speed_scale;
  view.twin_in_sim = state.twin_mode == TwinMode::MODE_SIM;
  view.has_physical_side = !state.physical_sides.empty();
  view.validate_then_run_offered = state.validate_then_run_offered;
  view.validation_phase = validation_phase_from(state.phase);
  return view;
}

std::string validate_then_run_outcome(
  const cite_interfaces::action::ValidateThenRun::Result & result)
{
  const ValidationPhase ended = validation_phase_from(result.ended_in);
  std::string where;
  if (ended != ValidationPhase::NONE) {
    where = std::string("Ended in: ") + validation_phase_name(ended) + ".";
  } else if (result.success) {
    where = "The console named no phase.";
  } else {
    where = "Refused before either phase began.";
  }
  return std::string("Validate then run") +
         (result.success ? ": done. " : ": refused or failed. ") + result.detail + " " + where +
         " Cycles completed on the twin: " + std::to_string(result.cycles_completed) + ".";
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
