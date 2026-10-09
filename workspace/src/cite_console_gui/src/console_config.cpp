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

#include "cite_console_gui/console_config.hpp"

#include <array>
#include <cmath>
#include <cstring>
#include <initializer_list>
#include <locale>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace cite_console_gui
{

namespace
{

std::string joined(const std::vector<std::string> & items)
{
  std::string text;
  for (const auto & item : items) {
    text += (text.empty() ? "" : ", ") + item;
  }
  return text;
}

bool is_known(const char * name)
{
  for (const char * key : {GZ_GUI_ELEMENT, HOME_CAMERA_POSE_KEY, FOLLOW_TARGET_KEY, TWIN_SIDES_KEY,
      HEARTBEAT_STALE_AFTER_KEY})
  {
    if (std::strcmp(name, key) == 0) {
      return true;
    }
  }
  for (const CameraPresetKey & preset : CAMERA_PRESET_KEYS) {
    if (std::strcmp(name, preset.key) == 0) {
      return true;
    }
  }
  for (const char * key : CONSOLE_KEYS) {
    if (std::strcmp(name, key) == 0) {
      return true;
    }
  }
  return false;
}

/// The text of `plugin_element`'s `key` child, or nullptr if there is none.
const char * child_text(const tinyxml2::XMLElement * plugin_element, const char * key)
{
  const tinyxml2::XMLElement * element =
    plugin_element == nullptr ? nullptr : plugin_element->FirstChildElement(key);
  return element == nullptr ? nullptr : element->GetText();
}

std::string unnamed(const char * key)
{
  return std::string("The GUI configuration names no ") + key +
         " for this panel. Regenerate it: ./scripts/validate-model --write";
}

}  // namespace

std::string read_console_names(const tinyxml2::XMLElement * plugin_element, ConsoleNames & names)
{
  std::string * const targets[] = {
    &names.state, &names.start_robot, &names.confirm_operator,
    &names.stop, &names.home, &names.run_program, &names.validate_then_run,
  };
  static_assert(
    sizeof(targets) / sizeof(targets[0]) == CONSOLE_KEYS.size(),
    "every key has exactly one name to fill");

  std::vector<std::string> missing;
  for (std::size_t index = 0; index < CONSOLE_KEYS.size(); ++index) {
    const char * key = CONSOLE_KEYS[index];
    const tinyxml2::XMLElement * element =
      plugin_element == nullptr ? nullptr : plugin_element->FirstChildElement(key);
    const char * text = element == nullptr ? nullptr : element->GetText();
    *targets[index] = text == nullptr ? "" : text;
    if (targets[index]->empty()) {
      missing.emplace_back(key);
    }
  }

  std::vector<std::string> unknown;
  if (plugin_element != nullptr) {
    for (const tinyxml2::XMLElement * child = plugin_element->FirstChildElement();
      child != nullptr; child = child->NextSiblingElement())
    {
      if (!is_known(child->Name())) {
        unknown.emplace_back(child->Name());
      }
    }
  }

  std::string problem;
  if (!missing.empty()) {
    problem = "The GUI configuration names no " + joined(missing) + " for this panel.";
  }
  if (!unknown.empty()) {
    problem += std::string(problem.empty() ? "" : " ") +
      "The GUI configuration gives this panel " + joined(unknown) +
      ", which it does not read.";
  }
  if (!problem.empty()) {
    problem += " Regenerate it: ./scripts/validate-model --write";
  }
  return problem;
}

std::string read_home_camera_pose(const tinyxml2::XMLElement * plugin_element, CameraPose & pose)
{
  return read_camera_pose(plugin_element, HOME_CAMERA_POSE_KEY, pose);
}

std::string read_camera_pose(
  const tinyxml2::XMLElement * plugin_element, const char * key, CameraPose & pose)
{
  const char * text = child_text(plugin_element, key);
  if (text == nullptr) {
    return unnamed(key);
  }

  // The C locale, whatever the window's: "0.5" is a number here everywhere.
  std::istringstream stream{std::string(text)};
  stream.imbue(std::locale::classic());
  std::array<double, 6> values{};
  for (double & value : values) {
    if (!(stream >> value) || !std::isfinite(value)) {
      return std::string("The GUI configuration's ") + key + " '" + text +
             "' is not six finite numbers (x y z roll pitch yaw).";
    }
  }
  stream >> std::ws;
  if (!stream.eof()) {
    return std::string("The GUI configuration's ") + key + " '" + text +
           "' has more than six numbers (x y z roll pitch yaw).";
  }
  pose = CameraPose{values[0], values[1], values[2], values[3], values[4], values[5]};
  return "";
}

std::string read_view_config(const tinyxml2::XMLElement * plugin_element, ViewConfig & config)
{
  ViewConfig read;
  for (const CameraPresetKey & preset : CAMERA_PRESET_KEYS) {
    CameraPose pose;
    const std::string problem = read_camera_pose(plugin_element, preset.key, pose);
    if (!problem.empty()) {
      return problem;
    }
    read.presets.emplace_back(preset.label, pose);
  }

  const char * target = child_text(plugin_element, FOLLOW_TARGET_KEY);
  if (target == nullptr || std::string(target).find_first_not_of(" \t\n") == std::string::npos) {
    return unnamed(FOLLOW_TARGET_KEY);
  }
  read.follow_target = target;

  const char * sides = child_text(plugin_element, TWIN_SIDES_KEY);
  if (sides != nullptr) {
    std::istringstream stream{std::string(sides)};
    for (std::string side; stream >> side; ) {
      read.twin_sides.push_back(side);
    }
  }
  if (read.twin_sides.empty()) {
    return unnamed(TWIN_SIDES_KEY);
  }

  const char * stale = child_text(plugin_element, HEARTBEAT_STALE_AFTER_KEY);
  if (stale == nullptr) {
    return unnamed(HEARTBEAT_STALE_AFTER_KEY);
  }
  std::istringstream stream{std::string(stale)};
  stream.imbue(std::locale::classic());
  double seconds = 0.0;
  if (!(stream >> seconds) || !std::isfinite(seconds) || seconds <= 0.0 ||
    !(stream >> std::ws).eof())
  {
    return std::string("The GUI configuration's ") + HEARTBEAT_STALE_AFTER_KEY + " '" + stale +
           "' is not one positive, finite number of seconds.";
  }
  read.heartbeat_stale_after_s = seconds;

  config = std::move(read);
  return "";
}

}  // namespace cite_console_gui
