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

using cite_console_gui::dropped_pick_note;
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

/// A READY, started, idle console with both arms at the start, serving `served`:
/// every served target startable, and those with the real arm floored, as the
/// console derives them (R-02).
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
  state.startable_targets = served;
  for (const std::uint8_t target : served) {
    if (target == ConsoleState::TARGET_REAL || target == ConsoleState::TARGET_TWIN) {
      state.floored_targets.push_back(target);
    }
  }
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
  EXPECT_FALSE(selection.buttons().start_robot);
  EXPECT_FALSE(selection.select(Target::SIM)) << "chosen before any console was heard";
  EXPECT_EQ(selection.selected(), Target::NONE);
}

TEST(PanelSelection, LoadStateSelectThenAChangedSetDropsItToTheSimulation)
{
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  // ADR-0072 decision 3 (amended 2026-10-15): the simulation, and only it.
  EXPECT_EQ(selection.selected(), Target::SIM) << "the simulation is not preselected";
  EXPECT_TRUE(selection.buttons().start_robot);
  EXPECT_TRUE(selection.buttons().home);

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

  // The real arm's side went away: the Twin pick is dropped, and the
  // simulation, still served, is selected in its place.
  selection.apply(view_from(ready(PLANT_ONLY), FIRST));
  EXPECT_EQ(selection.selected(), Target::SIM);
  EXPECT_TRUE(selection.buttons().home);
}

TEST(PanelSelection, TheOperatorsTwinIsKeptWhileItIsServed)
{
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_EQ(selection.selected(), Target::SIM);
  ASSERT_TRUE(selection.select(Target::TWIN));
  for (int heard = 0; heard < 5; ++heard) {
    selection.apply(view_from(ready(), FIRST));
    EXPECT_EQ(selection.selected(), Target::TWIN) << "the default overwrote the operator's pick";
  }
}

TEST(PanelSelection, WithoutTheSimulationNothingIsSelectedAndStartRobotWaits)
{
  ConsoleState state = ready({ConsoleState::TARGET_REAL});
  state.state = ConsoleState::NOT_STARTED;
  state.robot_started = false;
  PanelSelection selection;
  selection.apply(view_from(state, FIRST));
  EXPECT_EQ(selection.selected(), Target::NONE) << "the real arm was preselected";
  EXPECT_FALSE(selection.buttons().start_robot);
  ASSERT_TRUE(selection.select(Target::REAL));
  EXPECT_TRUE(selection.buttons().start_robot);
  // The simulation came up: the served set changed, the pick is dropped, and
  // the simulation is selected.
  state.available_targets = {ConsoleState::TARGET_SIM, ConsoleState::TARGET_REAL};
  selection.apply(view_from(state, FIRST));
  EXPECT_EQ(selection.selected(), Target::SIM);
}

TEST(PanelSelection, SelectLostThenBackWithTheSameSetDropsIt)
{
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::REAL));
  selection.forget();
  EXPECT_EQ(selection.selected(), Target::NONE);
  EXPECT_FALSE(selection.buttons().home);
  EXPECT_FALSE(selection.buttons().start_robot);
  // Back, same publisher identity, same set: the real arm is not selected
  // again; the simulation is.
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::SIM);
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

TEST(PanelSelection, AnotherConsoleWithTheSameSetDropsIt)
{
  // R-02: a console restarted without its predecessor's unmatch being seen
  // speaks from another publisher; that is a console that came back.
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::TWIN));
  selection.apply(view_from(ready(), SECOND));
  EXPECT_EQ(selection.selected(), Target::SIM);
}

TEST(PanelSelection, AnUnknownServedValueAppearingDropsIt)
{
  // R-03: a value this panel cannot read is not offered, but it is a change.
  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::TWIN));
  std::vector<std::uint8_t> with_unknown = BOTH_SIDES;
  with_unknown.push_back(unknown_target());
  selection.apply(view_from(ready(with_unknown), FIRST));
  EXPECT_EQ(selection.selected(), Target::SIM);
  // Offered: only what the panel recognises.
  EXPECT_EQ(selection.view().available_targets.size(), 3U);
  // And it goes away again: also a change.
  ASSERT_TRUE(selection.select(Target::REAL));
  selection.apply(view_from(ready(), FIRST));
  EXPECT_EQ(selection.selected(), Target::SIM);
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

TEST(PanelSelection, ValidateThenRunIsSentOnlyAtAScaleTheTwinAccepts)
{
  // ADR-0073: no target is sent, and the twin's floor holds for both phases
  // whatever target the operator has selected for Home and Start program.
  ConsoleState state = ready();
  state.validate_then_run_offered = true;
  PanelSelection selection;
  selection.apply(view_from(state, FIRST));
  EXPECT_TRUE(selection.buttons().validate_then_run);
  EXPECT_TRUE(selection.may_validate_then_run(0.5, 1));
  EXPECT_TRUE(selection.may_validate_then_run(0.25, 3));
  EXPECT_FALSE(selection.may_validate_then_run(0.1, 1)) << "below the twin's floor";
  EXPECT_FALSE(selection.may_validate_then_run(0.5, 0)) << "no cycle";
  EXPECT_FALSE(selection.may_validate_then_run(0.0, 1));
  // SIM selected: 0.1 is allowed for Home, still not for ValidateThenRun.
  ASSERT_TRUE(selection.select(Target::SIM));
  EXPECT_TRUE(selection.may_home(0.1));
  EXPECT_FALSE(selection.may_validate_then_run(0.1, 1));
  EXPECT_TRUE(selection.may_validate_then_run(1.0, 1));
}

TEST(PanelSelection, ValidateThenRunFollowsTheConsolesOfferAndTheTwinsStart)
{
  ConsoleState state = ready();
  state.validate_then_run_offered = false;
  PanelSelection selection;
  selection.apply(view_from(state, FIRST));
  EXPECT_FALSE(selection.buttons().validate_then_run) << "not offered";
  EXPECT_FALSE(selection.may_validate_then_run(1.0, 1));

  state.validate_then_run_offered = true;
  state.startable_targets = {ConsoleState::TARGET_SIM};
  selection.apply(view_from(state, FIRST));
  EXPECT_FALSE(selection.buttons().validate_then_run) << "the twin is not startable";

  state.startable_targets = BOTH_SIDES;
  selection.apply(view_from(state, FIRST));
  EXPECT_TRUE(selection.buttons().validate_then_run);
  selection.forget();
  EXPECT_FALSE(selection.buttons().validate_then_run) << "the console left";
}

// R-03 / S-02: a dropped Real arm or Twin pick is said in the event log; the
// panel's own default (Simulation) replaced, or a pick kept, is not.
TEST(PanelSelection, ADroppedRealArmOrTwinPickIsNoted)
{
  EXPECT_EQ(dropped_pick_note(Target::TWIN, Target::SIM), "Console changed: now Simulation");
  EXPECT_EQ(dropped_pick_note(Target::REAL, Target::NONE), "Console changed: now none");
  EXPECT_EQ(dropped_pick_note(Target::TWIN, Target::TWIN), "");
  EXPECT_EQ(dropped_pick_note(Target::SIM, Target::NONE), "");
  EXPECT_EQ(dropped_pick_note(Target::NONE, Target::SIM), "");

  PanelSelection selection;
  selection.apply(view_from(ready(), FIRST));
  ASSERT_TRUE(selection.select(Target::REAL));
  const Target before = selection.selected();
  selection.apply(view_from(ready(PLANT_ONLY), FIRST));
  EXPECT_EQ(dropped_pick_note(before, selection.selected()), "Console changed: now Simulation");
}
