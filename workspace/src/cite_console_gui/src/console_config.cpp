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
  if (std::strcmp(name, GZ_GUI_ELEMENT) == 0 || std::strcmp(name, HOME_CAMERA_POSE_KEY) == 0) {
    return true;
  }
  for (const char * key : CONSOLE_KEYS) {
    if (std::strcmp(name, key) == 0) {
      return true;
    }
  }
  return false;
}

}  // namespace

std::string read_console_names(const tinyxml2::XMLElement * plugin_element, ConsoleNames & names)
{
  std::string * const targets[] = {
    &names.state, &names.start_robot, &names.confirm_operator,
    &names.stop, &names.home, &names.run_program,
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
  const tinyxml2::XMLElement * element =
    plugin_element == nullptr ? nullptr : plugin_element->FirstChildElement(HOME_CAMERA_POSE_KEY);
  const char * text = element == nullptr ? nullptr : element->GetText();
  if (text == nullptr) {
    return std::string("The GUI configuration names no ") + HOME_CAMERA_POSE_KEY +
           " for this panel. Regenerate it: ./scripts/validate-model --write";
  }

  // The C locale, whatever the window's: "0.5" is a number here everywhere.
  std::istringstream stream{std::string(text)};
  stream.imbue(std::locale::classic());
  std::array<double, 6> values{};
  for (double & value : values) {
    if (!(stream >> value) || !std::isfinite(value)) {
      return std::string("The GUI configuration's ") + HOME_CAMERA_POSE_KEY + " '" + text +
             "' is not six finite numbers (x y z roll pitch yaw).";
    }
  }
  stream >> std::ws;
  if (!stream.eof()) {
    return std::string("The GUI configuration's ") + HOME_CAMERA_POSE_KEY + " '" + text +
           "' has more than six numbers (x y z roll pitch yaw).";
  }
  pose = CameraPose{values[0], values[1], values[2], values[3], values[4], values[5]};
  return "";
}

}  // namespace cite_console_gui
