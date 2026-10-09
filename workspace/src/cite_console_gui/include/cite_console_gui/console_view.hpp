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

// The contract's constants, turned into the panel's view - in one place.
//
// Every value compared here is a constant from the generated message headers
// (ConsoleState, TwinMode); none is written as a number. A state this panel
// does not recognise becomes `Phase::UNKNOWN` rather than a guess.

#ifndef CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_
#define CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_

#include <cstdint>
#include <string>

#include "cite_console_gui/enablement.hpp"
#include "cite_interfaces/msg/console_state.hpp"

namespace cite_console_gui
{

/// ConsoleState.state as a phase; `UNKNOWN` for a value the contract this
/// panel was built against does not define.
Phase phase_from(std::uint8_t state);

/// What the buttons depend on, from a ConsoleState that was just heard.
ConsoleView view_from(const cite_interfaces::msg::ConsoleState & state);

/// A TwinMode.MODE_* value (or ConsoleState.TWIN_MODE_UNKNOWN) by its name.
std::string twin_mode_name(std::uint8_t mode);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_
