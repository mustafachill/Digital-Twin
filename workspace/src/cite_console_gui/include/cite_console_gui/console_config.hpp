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
#include <utility>
#include <vector>

#include "cite_console_gui/camera_pose.hpp"
#include "cite_console_gui/console_client.hpp"

namespace cite_console_gui
{

/// The plugin element's children that name the console's endpoints, by the
/// keys of the plan's `console:` block.
constexpr std::array<const char *, 7> CONSOLE_KEYS = {
  "state", "start_robot", "confirm_operator", "stop", "home", "run_program", "validate_then_run",
};

/// gz-gui's own settings, which every plugin element carries.
constexpr const char * GZ_GUI_ELEMENT = "gz-gui";

/// Where "Reset view" returns the 3D view: the generator writes the same text
/// as MinimalScene's `<camera_pose>` here (generate/gui.py). Not a console
/// name - it commands no robot - so it is not one of `CONSOLE_KEYS`.
constexpr const char * HOME_CAMERA_POSE_KEY = "home_camera_pose";

/// One of the panel's preset views: the key the generator writes its pose
/// under (generate/gui.py `camera_presets`), and the button's label.
struct CameraPresetKey
{
  const char * key;
  const char * label;
};

/// The preset views, in the order the panel offers them.
constexpr std::array<CameraPresetKey, 3> CAMERA_PRESET_KEYS = {{
  {"top_camera_pose", "Top"},
  {"side_camera_pose", "Side"},
  {"front_camera_pose", "Front"},
}};

/// The model "Follow robot" asks the window to follow: the arm's name in the
/// plant's world (generate/gui.py `follow_model`).
constexpr const char * FOLLOW_MODEL_KEY = "follow_model";

/// The pair's side names, space-separated, by the names TwinSides uses.
constexpr const char * TWIN_SIDES_KEY = "twin_sides";

/// Seconds the boundary's heartbeat may go unheard before the panel shows it as
/// stale (generate/gui.py `heartbeat_stale_after_s`).
constexpr const char * HEARTBEAT_STALE_AFTER_KEY = "heartbeat_stale_after_s";

/// The panel's views and connection display, as the configuration gives them.
struct ViewConfig
{
  /// Each preset's label and pose, in `CAMERA_PRESET_KEYS` order.
  std::vector<std::pair<std::string, CameraPose>> presets;
  std::string follow_model;
  std::vector<std::string> twin_sides;
  double heartbeat_stale_after_s{0.0};
};

/// Fill `names` from `plugin_element`. Returns what is wrong - a key missing
/// or empty, or a child that is none of `CONSOLE_KEYS`, the view keys above
/// nor `GZ_GUI_ELEMENT` - or an empty string when nothing is. A child this
/// panel does not read is refused rather than ignored: it is a name the
/// generator meant for a panel that is not this one. The view keys are read by
/// `read_home_camera_pose` and `read_view_config`, and their absence is those
/// functions' to report.
std::string read_console_names(const tinyxml2::XMLElement * plugin_element, ConsoleNames & names);

/// Fill `pose` from the `HOME_CAMERA_POSE_KEY` child of `plugin_element`:
/// exactly six finite numbers, `x y z roll pitch yaw`. Returns what is wrong,
/// or an empty string when nothing is; on a problem `pose` is left untouched.
std::string read_home_camera_pose(const tinyxml2::XMLElement * plugin_element, CameraPose & pose);

/// Fill `pose` from the `key` child of `plugin_element`, as
/// `read_home_camera_pose` reads its own.
std::string read_camera_pose(
  const tinyxml2::XMLElement * plugin_element, const char * key, CameraPose & pose);

/// Fill `config` from `plugin_element`: every preset pose, the follow model,
/// the side names (at least one) and a positive, finite stale threshold.
/// Returns what is wrong, or an empty string when nothing is; on a problem
/// `config` is left untouched.
std::string read_view_config(const tinyxml2::XMLElement * plugin_element, ViewConfig & config);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_CONFIG_HPP_
