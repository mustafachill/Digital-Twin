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

// The panel's configuration against the one the generator installs (A-02).
//
// The generator writes the console's names into the plant's GUI configuration
// under the keys of the plan's `console:` block; the panel reads them under
// `CONSOLE_KEYS`. Two spellings of one list, in two languages, so this test
// reads the INSTALLED configuration and holds every `CellConsole` element in it
// to the panel's list - a key renamed on either side fails here, not in a
// window with a panel that commands nothing.

#include <gtest/gtest.h>
#include <tinyxml2.h>

#include <cstring>
#include <filesystem>
#include <set>
#include <string>
#include <vector>

#include "ament_index_cpp/get_package_share_directory.hpp"
#include "cite_console_gui/console_config.hpp"

using cite_console_gui::CONSOLE_KEYS;
using cite_console_gui::ConsoleNames;
using cite_console_gui::GZ_GUI_ELEMENT;
using cite_console_gui::read_console_names;

namespace
{

/// Every GUI configuration the generator installs for a window, by path.
std::vector<std::filesystem::path> installed_gui_configs()
{
  const std::filesystem::path worlds =
    std::filesystem::path(ament_index_cpp::get_package_share_directory("cite_generated")) /
    "worlds";
  std::vector<std::filesystem::path> found;
  for (const auto & entry : std::filesystem::recursive_directory_iterator(worlds)) {
    const std::string name = entry.path().filename().string();
    if (entry.is_regular_file() && name.size() > 11 &&
      name.compare(name.size() - 11, 11, "_gui.config") == 0)
    {
      found.push_back(entry.path());
    }
  }
  return found;
}

std::set<std::string> keys()
{
  return std::set<std::string>(CONSOLE_KEYS.begin(), CONSOLE_KEYS.end());
}

}  // namespace

TEST(ConsoleConfig, TheInstalledPlantConfigurationGivesThePanelExactlyItsKeys)
{
  const auto configs = installed_gui_configs();
  ASSERT_FALSE(configs.empty()) << "cite_generated installs no *_gui.config";
  int panels = 0;
  for (const auto & path : configs) {
    tinyxml2::XMLDocument document;
    ASSERT_EQ(document.LoadFile(path.c_str()), tinyxml2::XML_SUCCESS) << path;
    for (const tinyxml2::XMLElement * plugin = document.FirstChildElement("plugin");
      plugin != nullptr; plugin = plugin->NextSiblingElement("plugin"))
    {
      const char * filename = plugin->Attribute("filename");
      if (filename == nullptr || std::strcmp(filename, "CellConsole") != 0) {
        continue;
      }
      ++panels;
      std::set<std::string> children;
      for (const tinyxml2::XMLElement * child = plugin->FirstChildElement(); child != nullptr;
        child = child->NextSiblingElement())
      {
        if (std::strcmp(child->Name(), GZ_GUI_ELEMENT) != 0) {
          children.insert(child->Name());
        }
      }
      EXPECT_EQ(children, keys()) << path;
      ConsoleNames names;
      EXPECT_EQ(read_console_names(plugin, names), "") << path;
      for (const std::string * name : {&names.state, &names.start_robot,
          &names.confirm_operator, &names.stop, &names.home, &names.run_program})
      {
        EXPECT_EQ(name->rfind("/cite/", 0), 0u) << *name << " in " << path;
      }
    }
  }
  // Only the plant's window of a paired zone carries the panel, and L0
  // declares one such zone: at least one panel is installed.
  EXPECT_GE(panels, 1);
}

TEST(ConsoleConfig, AMissingKeyIsNamed)
{
  tinyxml2::XMLDocument document;
  document.Parse(
    "<plugin filename=\"CellConsole\"><gz-gui/>"
    "<state>/s</state><start_robot>/a</start_robot><confirm_operator>/c</confirm_operator>"
    "<stop>/t</stop><home></home></plugin>");
  ConsoleNames names;
  const std::string problem = read_console_names(document.FirstChildElement(), names);
  EXPECT_NE(problem.find("names no home, run_program"), std::string::npos) << problem;
}

TEST(ConsoleConfig, AChildThePanelDoesNotReadIsRefused)
{
  tinyxml2::XMLDocument document;
  document.Parse(
    "<plugin filename=\"CellConsole\"><gz-gui/>"
    "<state>/s</state><start_robot>/a</start_robot><confirm_operator>/c</confirm_operator>"
    "<stop>/t</stop><home>/h</home><run_program>/r</run_program>"
    "<estop>/e</estop></plugin>");
  ConsoleNames names;
  const std::string problem = read_console_names(document.FirstChildElement(), names);
  EXPECT_NE(problem.find("estop"), std::string::npos) << problem;
  EXPECT_EQ(problem.find("names no"), std::string::npos) << problem;
}

TEST(ConsoleConfig, EveryKeyReachesItsOwnName)
{
  tinyxml2::XMLDocument document;
  document.Parse(
    "<plugin filename=\"CellConsole\">"
    "<state>/s</state><start_robot>/a</start_robot><confirm_operator>/c</confirm_operator>"
    "<stop>/t</stop><home>/h</home><run_program>/r</run_program></plugin>");
  ConsoleNames names;
  EXPECT_EQ(read_console_names(document.FirstChildElement(), names), "");
  EXPECT_EQ(names.state, "/s");
  EXPECT_EQ(names.start_robot, "/a");
  EXPECT_EQ(names.confirm_operator, "/c");
  EXPECT_EQ(names.stop, "/t");
  EXPECT_EQ(names.home, "/h");
  EXPECT_EQ(names.run_program, "/r");
}

TEST(ConsoleConfig, NoElementNamesNothing)
{
  ConsoleNames names;
  EXPECT_NE(read_console_names(nullptr, names).find("names no state"), std::string::npos);
}
