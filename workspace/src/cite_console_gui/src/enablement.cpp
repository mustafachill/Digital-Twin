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

ButtonStates enabled_for(const ConsoleView & view)
{
  ButtonStates states;
  if (!view.heard) {
    return states;
  }
  const bool idle = !view.busy;
  const bool ready = view.phase == Phase::READY;

  states.start_robot = idle &&
    (view.phase == Phase::NOT_STARTED || ready || view.phase == Phase::FAULT);
  states.home = idle && view.robot_started && ready;
  states.start_program = idle && view.robot_started && ready && view.at_start;
  states.stop = view.busy ||
    (view.phase == Phase::FAULT && !view.twin_in_sim && view.has_physical_side);
  states.confirm = view.phase == Phase::AWAITING_OPERATOR;
  return states;
}

bool speed_choice_enabled(double scale, double minimum_speed_scale)
{
  return scale > 0.0 && scale <= 1.0 && scale >= minimum_speed_scale;
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
