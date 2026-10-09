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

// The sequences the panel lives through, on the holder the plugin delegates to
// (R-01): which views reach `settled_selection`, and what is left selected and
// enabled after each step. Views are built by `view_from` from ConsoleState
// messages, as the plugin builds them; no graph, no window.

#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "cite_console_gui/console_view.hpp"
#include "cite_console_gui/selection.hpp"
#include "cite_interfaces/msg/console_state.hpp"

using cite_console_gui::PanelSelection;
using cite_console_gui::Target;
using cite_console_gui::target_from;
using cite_console_gui::view_from;
using cite_interfaces::msg::ConsoleState;

namespace
{

using Publisher = std::vector<std::uint8_t>;

const Publisher FIRST = {1, 2, 3, 4};
const Publisher SECOND = {5, 6, 7, 8};

const std::vector<std::uint8_t> BOTH_SIDES = {
  ConsoleState::TARGET_SIM, ConsoleState::TARGET_REAL, ConsoleState::TARGET_TWIN};
const std::vector<std::uint8_t> PLANT_ONLY = {ConsoleState::TARGET_SIM};

/// A READY, started, idle console with both arms at the start, serving `served`.
ConsoleState ready(const std::vector<std::uint8_t> & served = BOTH_SIDES)
{
  ConsoleState state;
  state.state = ConsoleState::READY;
  state.robot_started = true;
  state.busy = false;
  state.plant_at_start = true;
  state.counterpart_at_start = true;
  state.minimum_speed_scale = 0.25;
  state.available_targets = served;
  return state;
}

/// A value of ConsoleState.available_targets this panel does not recognise.
std::uint8_t unknown_target()
{
  std::uint8_t value = 0xFE;
  while (target_from(value) != Target::NONE) {
    --value;
  }
  return value;
}

}  // namespace

TEST(PanelSelection, LoadedPanelSelectsNothingAndEnablesNothing)
{
  PanelSelection selection;
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
  EXPECT_FALSE(selection.select(Target::SIM)) << "chosen before any console was heard";
  EXPECT_EQ(selection.selected(), Target::NONE);
}

TEST(PanelSelection, LoadStateSelectThenAChangedSetClearsIt)
{
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE) << "the panel picked for the operator";
  EXPECT_FALSE(selection.buttons().home);

  ASSERT_TRUE(selection.select(Target::TWIN));
  EXPECT_EQ(selection.selected(), Target::TWIN);
  EXPECT_TRUE(selection.buttons().home);
  EXPECT_TRUE(selection.buttons().start_program);

  // Same publisher, same set, another phase: the pick stays.
  ConsoleState running = ready();
  running.state = ConsoleState::RUNNING;
  running.busy = true;
  selection.apply(view_from(running, FIRST));
  EXPECT_EQ(selection.selected(), Target::TWIN);
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::TWIN);

  // The real arm's side went away: cleared, and SIM is not chosen for them.
  selection.apply(view_from(ready(PLANT_ONLY), FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
  EXPECT_FALSE(selection.buttons().start_program);
}

TEST(PanelSelection, SelectLostThenBackWithTheSameSetClearsIt)
{
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::REAL));
  selection.forget();
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
  // Back, same publisher identity, same set: still cleared.
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
}

TEST(PanelSelection, AnUnservedTargetIsIgnored)
{
  PanelSelection selection;
  selection.apply(view_from(ready(PLANT_ONLY), FIRST));
  ASSERT_TRUE(selection.select(Target::SIM));
  EXPECT_FALSE(selection.select(Target::TWIN));
  EXPECT_FALSE(selection.select(Target::REAL));
  EXPECT_FALSE(selection.select(Target::NONE));
  EXPECT_EQ(selection.selected(), Target::SIM) << "an ignored pick changed the selection";
}

TEST(PanelSelection, AnotherConsoleWithTheSameSetClearsIt)
{
  // R-02: a console restarted without its predecessor's unmatch being seen
  // speaks from another publisher; that is a console that came back.
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::TWIN));
  selection.apply(view_from(ready(), SECOND));
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
  EXPECT_FALSE(selection.buttons().start_program);
}

TEST(PanelSelection, AnUnknownServedValueAppearingClearsIt)
{
  // R-03: a value this panel cannot read is not offered, but it is a change.
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::SIM));
  std::vector<std::uint8_t> with_unknown = BOTH_SIDES;
  with_unknown.push_back(unknown_target());
  selection.apply(view_from(ready(with_unknown), FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE);
  // Offered: only what the panel recognises.
  EXPECT_EQ(selection.view().available_targets.size(), 3U);
  // And it goes away again: also a change.
  ASSERT_TRUE(selection.select(Target::SIM));
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE);
}

TEST(PanelSelection, HomeAndStartProgramAreNotSentAtAScaleTheTargetRefuses)
{
  // R-04: below the real arm's floor for a target with the real arm.
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::TWIN));
  EXPECT_TRUE(selection.may_home(0.5));
  EXPECT_TRUE(selection.may_run(0.5, 1));
  EXPECT_FALSE(selection.may_home(0.1));
  EXPECT_FALSE(selection.may_run(0.1, 1));
  EXPECT_FALSE(selection.may_home(0.0));
  EXPECT_FALSE(selection.may_run(1.5, 1));
  EXPECT_FALSE(selection.may_run(0.5, 0));
  // The simulation alone has no floor.
  ASSERT_TRUE(selection.select(Target::SIM));
  EXPECT_TRUE(selection.may_home(0.1));
  EXPECT_TRUE(selection.may_run(0.1, 2));
  // Nothing selected: nothing sent at any scale.
  selection.forget();
  EXPECT_FALSE(selection.may_home(1.0));
  EXPECT_FALSE(selection.may_run(1.0, 1));
}
