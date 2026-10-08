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

// The contract's constants into the panel's view, read from the generated
// headers: a constant renumbered in ConsoleState.msg or TwinMode.msg moves
// here with it, and a new state the panel does not know reads as UNKNOWN.

#include <gtest/gtest.h>

#include <cstdint>
#include <set>
#include <string>

#include "cite_console_gui/console_view.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"

using cite_console_gui::Phase;
using cite_console_gui::phase_from;
using cite_console_gui::twin_mode_name;
using cite_console_gui::view_from;
using cite_interfaces::msg::ConsoleState;
using cite_interfaces::msg::TwinMode;

TEST(ConsoleView, EveryContractStateIsAKnownPhase)
{
  const std::set<std::uint8_t> states = {
    ConsoleState::NOT_STARTED, ConsoleState::STARTING, ConsoleState::READY,
    ConsoleState::HOMING, ConsoleState::AWAITING_OPERATOR, ConsoleState::RUNNING,
    ConsoleState::STOPPING, ConsoleState::FAULT,
  };
  std::set<Phase> phases;
  for (const auto state : states) {
    const Phase phase = phase_from(state);
    EXPECT_NE(phase, Phase::UNKNOWN) << static_cast<int>(state);
    phases.insert(phase);
  }
  EXPECT_EQ(phases.size(), states.size()) << "two states read as one phase";
}

TEST(ConsoleView, EachStateIsTheNamedPhase)
{
  EXPECT_EQ(phase_from(ConsoleState::NOT_STARTED), Phase::NOT_STARTED);
  EXPECT_EQ(phase_from(ConsoleState::READY), Phase::READY);
  EXPECT_EQ(phase_from(ConsoleState::AWAITING_OPERATOR), Phase::AWAITING_OPERATOR);
  EXPECT_EQ(phase_from(ConsoleState::FAULT), Phase::FAULT);
}

TEST(ConsoleView, AStateTheContractDoesNotDefineIsUnknown)
{
  EXPECT_EQ(phase_from(200), Phase::UNKNOWN);
}

TEST(ConsoleView, TheViewCarriesTheFlagsAndReadsSimFromTheMode)
{
  ConsoleState state;
  state.state = ConsoleState::READY;
  state.robot_started = true;
  state.busy = false;
  state.at_start = true;
  state.twin_mode = TwinMode::MODE_SIM;
  auto view = view_from(state);
  EXPECT_TRUE(view.heard);
  EXPECT_EQ(view.phase, Phase::READY);
  EXPECT_TRUE(view.robot_started);
  EXPECT_FALSE(view.busy);
  EXPECT_TRUE(view.at_start);
  EXPECT_TRUE(view.twin_in_sim);

  state.twin_mode = TwinMode::MODE_VALIDATED;
  EXPECT_FALSE(view_from(state).twin_in_sim);
  // Not heard yet is not SIM.
  state.twin_mode = ConsoleState::TWIN_MODE_UNKNOWN;
  EXPECT_FALSE(view_from(state).twin_in_sim);
}

TEST(ConsoleView, EveryTwinModeHasADistinctName)
{
  const std::set<std::uint8_t> modes = {
    TwinMode::MODE_SIM, TwinMode::MODE_REAL, TwinMode::MODE_SHADOW, TwinMode::MODE_VALIDATED,
    TwinMode::MODE_CLOSED_LOOP, TwinMode::MODE_VIRTUAL_LEAD, ConsoleState::TWIN_MODE_UNKNOWN,
  };
  std::set<std::string> names;
  for (const auto mode : modes) {
    names.insert(twin_mode_name(mode));
  }
  EXPECT_EQ(names.size(), modes.size());
  EXPECT_EQ(twin_mode_name(TwinMode::MODE_SIM), "SIM");
}
