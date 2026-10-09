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

#include "cite_console_gui/enablement.hpp"

namespace cite_console_gui
{

namespace
{

bool served(const ConsoleView & view, Target target)
{
  return target != Target::NONE && view.available_targets.count(target) == 1;
}

/// The console says every side of `target` is at the program's start.
bool startable(const ConsoleView & view, Target target)
{
  return target != Target::NONE && view.startable_targets.count(target) == 1;
}

}  // namespace

ButtonStates enabled_for(const ConsoleView & view, Target selected)
{
  ButtonStates states;
  if (!view.heard) {
    return states;
  }
  const bool idle = !view.busy;
  const bool ready = view.phase == Phase::READY;

  states.start_robot = idle &&
    (view.phase == Phase::NOT_STARTED || ready || view.phase == Phase::FAULT);
  states.home = idle && view.robot_started && ready && served(view, selected);
  states.start_program = states.home && startable(view, selected);
  states.stop = view.busy ||
    (view.phase == Phase::FAULT && !view.twin_in_sim && view.has_physical_side);
  states.confirm = view.phase == Phase::AWAITING_OPERATOR;
  return states;
}

bool target_choice_enabled(const ConsoleView & view, Target target)
{
  return view.heard && served(view, target);
}

Target settled_selection(const ConsoleView & before, const ConsoleView & now, Target selected)
{
  const bool unchanged = before.heard && now.heard &&
    before.publisher == now.publisher &&
    before.served_values == now.served_values &&
    before.available_targets == now.available_targets;
  return unchanged && served(now, selected) ? selected : Target::NONE;
}

bool counterpart_running(const ConsoleView & view)
{
  return view.heard && view.counterpart_running;
}

bool speed_choice_enabled(double scale, const ConsoleView & view, Target target)
{
  if (!view.heard || scale <= 0.0 || scale > 1.0) {
    return false;
  }
  const bool floor_applies =
    target == Target::NONE || view.floored_targets.count(target) == 1;
  return !floor_applies || scale >= view.minimum_speed_scale;
}

const char * target_name(Target target)
{
  switch (target) {
    case Target::SIM:
      return "Simulation";
    case Target::REAL:
      return "Real arm";
    case Target::TWIN:
      return "Twin";
    case Target::NONE:
      break;
  }
  return "None";
}

const char * phase_name(Phase phase)
{
  switch (phase) {
    case Phase::NOT_STARTED:
      return "NOT_STARTED";
    case Phase::STARTING:
      return "STARTING";
    case Phase::READY:
      return "READY";
    case Phase::HOMING:
      return "HOMING";
    case Phase::AWAITING_OPERATOR:
      return "AWAITING_OPERATOR";
    case Phase::RUNNING:
      return "RUNNING";
    case Phase::STOPPING:
      return "STOPPING";
    case Phase::FAULT:
      return "FAULT";
    case Phase::UNKNOWN:
      break;
  }
  return "UNKNOWN";
}

}  // namespace cite_console_gui
