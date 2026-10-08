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

// The panel's enablement table, over every phase and every flag (ADR-0071).
//
// Two halves. The exhaustive half walks all 9 phases x 2^5 flags and holds each
// button to the rule as ADR-0071 and the task state it, written here as sets of
// phases rather than by calling the function under test. The named half pins
// the rows an operator meets, so that a failure reads as a situation.

#include <gtest/gtest.h>

#include <set>
#include <string>

#include "cite_console_gui/enablement.hpp"

using cite_console_gui::ALL_PHASES;
using cite_console_gui::ButtonStates;
using cite_console_gui::ConsoleView;
using cite_console_gui::enabled_for;
using cite_console_gui::Phase;
using cite_console_gui::phase_name;
using cite_console_gui::SPEED_CHOICES;
using cite_console_gui::speed_choice_enabled;

namespace
{

ConsoleView view(
  Phase phase, bool robot_started = false, bool busy = false, bool at_start = false,
  bool twin_in_sim = true)
{
  ConsoleView v;
  v.heard = true;
  v.phase = phase;
  v.robot_started = robot_started;
  v.busy = busy;
  v.at_start = at_start;
  v.twin_in_sim = twin_in_sim;
  return v;
}

std::string describe(const ConsoleView & v)
{
  return std::string(phase_name(v.phase)) + " heard=" + std::to_string(v.heard) +
         " started=" + std::to_string(v.robot_started) + " busy=" + std::to_string(v.busy) +
         " at_start=" + std::to_string(v.at_start) + " sim=" + std::to_string(v.twin_in_sim);
}

}  // namespace

TEST(Enablement, EveryPhaseAndEveryFlagFollowsTheRule)
{
  const std::set<Phase> start_robot_phases = {Phase::NOT_STARTED, Phase::READY, Phase::FAULT};
  int rows = 0;
  for (const Phase phase : ALL_PHASES) {
    for (int bits = 0; bits < 32; ++bits) {
      ConsoleView v;
      v.phase = phase;
      v.heard = bits & 1;
      v.robot_started = bits & 2;
      v.busy = bits & 4;
      v.at_start = bits & 8;
      v.twin_in_sim = bits & 16;
      const ButtonStates got = enabled_for(v);
      ++rows;

      if (!v.heard) {
        EXPECT_EQ(got, ButtonStates{}) << describe(v);
        continue;
      }
      const bool idle = !v.busy;
      EXPECT_EQ(got.start_robot, idle && start_robot_phases.count(phase) == 1) << describe(v);
      EXPECT_EQ(got.home, idle && v.robot_started && phase == Phase::READY) << describe(v);
      EXPECT_EQ(
        got.start_program, idle && v.robot_started && phase == Phase::READY && v.at_start) <<
        describe(v);
      EXPECT_EQ(got.stop, v.busy || (phase == Phase::FAULT && !v.twin_in_sim)) << describe(v);
      EXPECT_EQ(got.confirm, phase == Phase::AWAITING_OPERATOR) << describe(v);
    }
  }
  EXPECT_EQ(rows, 9 * 32);
}

TEST(Enablement, NothingBeforeTheConsoleIsHeard)
{
  ConsoleView v = view(Phase::READY, true, false, true);
  v.heard = false;
  EXPECT_EQ(enabled_for(v), ButtonStates{});
  EXPECT_EQ(enabled_for(ConsoleView{}), ButtonStates{});
}

TEST(Enablement, NotStartedOffersOnlyStartRobot)
{
  ButtonStates expected;
  expected.start_robot = true;
  EXPECT_EQ(enabled_for(view(Phase::NOT_STARTED)), expected);
}

TEST(Enablement, HomeNeedsAStartedRobot)
{
  // READY without robot_started: a console that never started cannot home.
  EXPECT_FALSE(enabled_for(view(Phase::READY, false)).home);
  EXPECT_TRUE(enabled_for(view(Phase::READY, true)).home);
}

TEST(Enablement, StartProgramNeedsTheArmAtTheStart)
{
  EXPECT_FALSE(enabled_for(view(Phase::READY, true, false, false)).start_program);
  EXPECT_TRUE(enabled_for(view(Phase::READY, true, false, true)).start_program);
}

TEST(Enablement, WhileRunningOnlyStopIsOffered)
{
  ButtonStates expected;
  expected.stop = true;
  EXPECT_EQ(enabled_for(view(Phase::RUNNING, true, true, false)), expected);
  EXPECT_EQ(enabled_for(view(Phase::HOMING, true, true, false)), expected);
}

TEST(Enablement, AwaitingTheOperatorOffersConfirmAndStop)
{
  const ButtonStates got = enabled_for(view(Phase::AWAITING_OPERATOR, true, true));
  EXPECT_TRUE(got.confirm);
  EXPECT_TRUE(got.stop);
  EXPECT_FALSE(got.start_robot || got.home || got.start_program);
}

TEST(Enablement, FaultOutOfSimOffersStopToAskForSimAgain)
{
  // StopCell.srv: in FAULT while the twin is not in SIM, Stop asks for SIM.
  EXPECT_TRUE(enabled_for(view(Phase::FAULT, false, false, false, false)).stop);
  EXPECT_FALSE(enabled_for(view(Phase::FAULT, false, false, false, true)).stop);
  // And Start robot is the way back to READY either way.
  EXPECT_TRUE(enabled_for(view(Phase::FAULT, false, false, false, false)).start_robot);
}

TEST(Enablement, AnUnrecognisedStateOffersNothingButStopWhileBusy)
{
  ButtonStates expected;
  EXPECT_EQ(enabled_for(view(Phase::UNKNOWN, true, false, true)), expected);
  expected.stop = true;
  EXPECT_EQ(enabled_for(view(Phase::UNKNOWN, true, true, true)), expected);
}

TEST(SpeedChoices, TheProgramsOwnSpeedComesFirst)
{
  EXPECT_DOUBLE_EQ(SPEED_CHOICES.front(), 1.0);
  for (const double scale : SPEED_CHOICES) {
    EXPECT_GT(scale, 0.0);
    EXPECT_LE(scale, 1.0);
  }
}

TEST(SpeedChoices, NothingBelowTheConsolesFloorIsOffered)
{
  EXPECT_TRUE(speed_choice_enabled(1.0, 0.0));
  EXPECT_TRUE(speed_choice_enabled(0.1, 0.0));
  EXPECT_TRUE(speed_choice_enabled(0.25, 0.25));
  EXPECT_FALSE(speed_choice_enabled(0.1, 0.25));
  EXPECT_TRUE(speed_choice_enabled(1.0, 0.9));
  // Outside (0, 1] is never offered, whatever the floor.
  EXPECT_FALSE(speed_choice_enabled(0.0, 0.0));
  EXPECT_FALSE(speed_choice_enabled(1.5, 0.0));
}

TEST(PhaseNames, EveryPhaseHasADistinctName)
{
  std::set<std::string> names;
  for (const Phase phase : ALL_PHASES) {
    names.insert(phase_name(phase));
  }
  EXPECT_EQ(names.size(), ALL_PHASES.size());
}
