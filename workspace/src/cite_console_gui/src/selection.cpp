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

#include "cite_console_gui/selection.hpp"

namespace cite_console_gui
{

void PanelSelection::apply(const ConsoleView & view)
{
  const ConsoleView before = view_;
  view_ = view;
  settle(before);
}

void PanelSelection::forget()
{
  const ConsoleView before = view_;
  view_ = ConsoleView{};
  settle(before);
}

bool PanelSelection::select(Target target)
{
  if (!target_choice_enabled(view_, target)) {
    return false;
  }
  selected_ = target;
  settle(view_);
  return true;
}

bool PanelSelection::may_home(double speed_scale) const
{
  return buttons_.home && speed_choice_enabled(speed_scale, view_, selected_);
}

bool PanelSelection::may_run(double speed_scale, int cycles) const
{
  return buttons_.start_program && cycles >= 1 &&
         speed_choice_enabled(speed_scale, view_, selected_);
}

bool PanelSelection::may_validate_then_run(double speed_scale, int cycles) const
{
  return buttons_.validate_then_run && cycles >= 1 &&
         speed_choice_enabled(speed_scale, view_, Target::TWIN);
}

void PanelSelection::settle(const ConsoleView & before)
{
  selected_ = settled_selection(before, view_, selected_);
  buttons_ = enabled_for(view_, selected_);
}

}  // namespace cite_console_gui
