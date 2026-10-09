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

// The panel's configuration: the console's names, read off the plugin element
// the generated GUI configuration gives it (generate/gui.py), with no Qt in it.
//
// The keys are stated ONCE, here, as `CONSOLE_KEYS` (A-02). The generator emits
// them from the plan's `console:` block; a test reads the installed
// configuration and holds its `CellConsole` children to this list, so a key
// renamed on one side fails a test instead of leaving a panel that commands
// nothing.

#ifndef CITE_CONSOLE_GUI__CONSOLE_CONFIG_HPP_
#define CITE_CONSOLE_GUI__CONSOLE_CONFIG_HPP_

#include <tinyxml2.h>

#include <array>
#include <string>

#include "cite_console_gui/camera_pose.hpp"
#include "cite_console_gui/console_client.hpp"

namespace cite_console_gui
{

/// The plugin element's children that name the console's endpoints, by the
/// keys of the plan's `console:` block.
constexpr std::array<const char *, 6> CONSOLE_KEYS = {
  "state", "start_robot", "confirm_operator", "stop", "home", "run_program",
};

/// gz-gui's own settings, which every plugin element carries.
constexpr const char * GZ_GUI_ELEMENT = "gz-gui";

/// Where "Reset view" returns the 3D view: the generator writes the same text
/// as MinimalScene's `<camera_pose>` here (generate/gui.py). Not a console
/// name - it commands no robot - so it is not one of `CONSOLE_KEYS`.
constexpr const char * HOME_CAMERA_POSE_KEY = "home_camera_pose";

/// Fill `names` from `plugin_element`. Returns what is wrong - a key missing
/// or empty, or a child that is none of `CONSOLE_KEYS`, `HOME_CAMERA_POSE_KEY`
/// nor `GZ_GUI_ELEMENT` - or an empty string when nothing is. A child this
/// panel does not read is refused rather than ignored: it is a name the
/// generator meant for a panel that is not this one. The home pose is read by
/// `read_home_camera_pose`, and its absence is that function's to report.
std::string read_console_names(const tinyxml2::XMLElement * plugin_element, ConsoleNames & names);

/// Fill `pose` from the `HOME_CAMERA_POSE_KEY` child of `plugin_element`:
/// exactly six finite numbers, `x y z roll pitch yaw`. Returns what is wrong,
/// or an empty string when nothing is; on a problem `pose` is left untouched.
std::string read_home_camera_pose(const tinyxml2::XMLElement * plugin_element, CameraPose & pose);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_CONFIG_HPP_
