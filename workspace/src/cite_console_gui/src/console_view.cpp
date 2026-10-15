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

#include <initializer_list>
#include <set>
#include <sstream>
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

std::string outcome_opening(const std::string & request, bool success, bool after_stop)
{
  return request + (success ? ": done. " :
         after_stop ? ": ended after a Stop request. " : ": refused or failed. ");
}

std::string as_sentence(const std::string & text)
{
  const auto first = text.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) {
    return "";
  }
  const auto last = text.find_last_not_of(" \t\r\n");
  std::string sentence = text.substr(first, last - first + 1);
  const char end = sentence.back();
  if (end != '.' && end != '!' && end != '?') {
    sentence += '.';
  }
  return sentence;
}

namespace
{

/// A number as a step writes one: digits, a sign, at most one decimal point.
bool is_number(const std::string & word)
{
  std::size_t at = word.empty() || (word[0] != '-' && word[0] != '+') ? 0 : 1;
  bool digits = false;
  bool point = false;
  for (; at < word.size(); ++at) {
    if (word[at] >= '0' && word[at] <= '9') {
      digits = true;
    } else if (word[at] == '.' && !point) {
      point = true;
    } else {
      return false;
    }
  }
  return digits;
}

/// A unit a step or an outcome writes after a number, or the "/" of a rate.
bool is_unit(const std::string & word)
{
  static const std::set<std::string> units = {
    "/", "m/s", "mm/s", "rad/s", "/s", "m", "mm", "s", "ms", "rad", "deg", "°", "%", "Hz", "×"};
  return units.count(word) == 1;
}

}  // namespace

std::string display_text(const std::string & text)
{
  std::vector<std::string> words;
  std::istringstream stream(text);
  for (std::string word; stream >> word; ) {
    words.push_back(word);
  }
  std::string line;
  for (std::size_t index = 0; index < words.size(); ++index) {
    if (index > 0) {
      const std::string & before = words[index - 1];
      const bool bound = is_unit(words[index]) && (is_number(before) || before == "/");
      line += bound ? "\u00a0" : " ";
    }
    line += words[index];
  }
  return line;
}

namespace
{

/// `parts` joined by one space, the empty ones left out.
std::string joined(std::initializer_list<std::string> parts)
{
  std::string line;
  for (const std::string & part : parts) {
    const auto first = part.find_first_not_of(' ');
    if (first == std::string::npos) {
      continue;
    }
    const auto last = part.find_last_not_of(' ');
    if (!line.empty()) {
      line += ' ';
    }
    line += part.substr(first, last - first + 1);
  }
  return line;
}

}  // namespace

std::string run_program_outcome(
  const cite_interfaces::action::RunProgram::Result & result, bool after_stop)
{
  return joined(
    {outcome_opening("Start program", result.success, after_stop), as_sentence(result.detail),
      result.success ? std::string() :
      "Cycles completed: " + std::to_string(result.cycles_completed) + "."});
}

std::string validate_then_run_outcome(
  const cite_interfaces::action::ValidateThenRun::Result & result, bool after_stop)
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
  const std::string opening = outcome_opening("Validate then run", result.success, after_stop);
  return joined(
    {opening, as_sentence(result.detail), where,
      "Cycles completed on the twin: " + std::to_string(result.cycles_completed) + "."});
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

DivergenceSample divergence_sample_from(const cite_interfaces::msg::DivergenceMetrics & sample)
{
  DivergenceSample read;
  read.asset_id = sample.asset_id;
  read.valid = sample.valid;
  read.joint_error_rms_rad = sample.joint_error_rms_rad;
  read.joint_error_max_rad = sample.joint_error_max_rad;
  read.tcp_position_error_m = sample.tcp_position_error_m;
  read.tcp_orientation_error_rad = sample.tcp_orientation_error_rad;
  read.far_side_physical = sample.far_side_physical;
  return read;
}

}  // namespace cite_console_gui
