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

// What the panel holds between two things the console says: the last view,
// the operator's selected target and the buttons they enable (ADR-0072
// decision 3, safety audit R-18).
//
// The plugin delegates to this and holds none of it itself, so the sequences
// that keep or clear a selection - a state, a pick, a lost console, a console
// that came back - are tested without a window, a QML engine or a ROS graph.
// No Qt and no message type here: the view is `view_from`'s.

#ifndef CITE_CONSOLE_GUI__SELECTION_HPP_
#define CITE_CONSOLE_GUI__SELECTION_HPP_

#include "cite_console_gui/enablement.hpp"

namespace cite_console_gui
{

class PanelSelection
{
public:
  /// A ConsoleState was heard, as `view` (with its publisher's identity).
  /// The selection is re-settled against the view it replaces.
  void apply(const ConsoleView & view);

  /// The console's state publisher left: no view, no selection, no buttons.
  void forget();

  /// The operator picks `target`. Ignored, returning false, unless the
  /// console serves it.
  bool select(Target target);

  const ConsoleView & view() const {return view_;}
  Target selected() const {return selected_;}
  const ButtonStates & buttons() const {return buttons_;}

  /// Home at `speed_scale` toward the selected target may be sent: Home is
  /// enabled and the scale is one the panel offers for that target.
  bool may_home(double speed_scale) const;

  /// Start program at `speed_scale` for `cycles` may be sent: as `may_home`,
  /// with Start program enabled and at least one cycle.
  bool may_run(double speed_scale, int cycles) const;

  /// Validate then run at `speed_scale` for `cycles` may be sent (ADR-0073):
  /// its button is enabled, at least one cycle, and the scale is one the panel
  /// offers for the twin target, whose floor applies to both phases. The
  /// selected target plays no part: the request carries none.
  bool may_validate_then_run(double speed_scale, int cycles) const;

private:
  void settle(const ConsoleView & before);

  ConsoleView view_;
  Target selected_{Target::NONE};
  ButtonStates buttons_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__SELECTION_HPP_
