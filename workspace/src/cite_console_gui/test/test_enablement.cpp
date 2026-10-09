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
// Two halves. The exhaustive half walks all 9 phases x 2^6 flags and holds each
// button to an INDEPENDENT statement of the rule: a table of named rows, each
// one situation in which one button is offered (P-R03). A button is expected
// enabled exactly when some row for it matches, so the expectation is read off
// data written as an operator would say it, never off a restated formula; a
// failure names the view, and the rows say what should have been offered. The
// named half pins the rows an operator meets, so that a failure reads as a
// situation.

#include <gtest/gtest.h>

#include <set>
#include <string>
#include <vector>

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
  bool twin_in_sim = true, bool has_physical_side = false)
{
  ConsoleView v;
  v.heard = true;
  v.phase = phase;
  v.robot_started = robot_started;
  v.busy = busy;
  v.at_start = at_start;
  v.twin_in_sim = twin_in_sim;
  v.has_physical_side = has_physical_side;
  return v;
}

std::string describe(const ConsoleView & v)
{
  return std::string(phase_name(v.phase)) + " heard=" + std::to_string(v.heard) +
         " started=" + std::to_string(v.robot_started) + " busy=" + std::to_string(v.busy) +
         " at_start=" + std::to_string(v.at_start) + " sim=" + std::to_string(v.twin_in_sim) +
         " physical=" + std::to_string(v.has_physical_side);
}

enum class Button { START_ROBOT, HOME, START_PROGRAM, STOP, CONFIRM };

/// A flag a row requires: either way, set, or clear.
enum class Need { ANY, YES, NO };

bool satisfies(Need need, bool value)
{
  return need == Need::ANY || (need == Need::YES) == value;
}

/// One situation in which one button is offered.
struct Row
{
  const char * situation;
  Button button;
  std::set<Phase> phases;  // empty: every phase
  Need started;
  Need busy;
  Need at_start;
  Need twin_in_sim;
  Need physical;
};

constexpr Need ANY = Need::ANY;
constexpr Need YES = Need::YES;
constexpr Need NO = Need::NO;

/// The rule, as ADR-0071 and StopCell.srv state it, one situation per row.
const std::vector<Row> & rows()
{
  static const std::vector<Row> table = {
    {"a console not started, idle, offers Start robot", Button::START_ROBOT,
      {Phase::NOT_STARTED}, ANY, NO, ANY, ANY, ANY},
    {"a READY console, idle, may be started again", Button::START_ROBOT,
      {Phase::READY}, ANY, NO, ANY, ANY, ANY},
    {"a FAULT, idle, is left by Start robot", Button::START_ROBOT,
      {Phase::FAULT}, ANY, NO, ANY, ANY, ANY},
    {"a started robot, READY and idle, may Home", Button::HOME,
      {Phase::READY}, YES, NO, ANY, ANY, ANY},
    {"a started robot, READY, idle and at the start, may run", Button::START_PROGRAM,
      {Phase::READY}, YES, NO, YES, ANY, ANY},
    {"a request in progress, in any phase, may be stopped", Button::STOP,
      {}, ANY, YES, ANY, ANY, ANY},
    {"a FAULT out of SIM with a physical side: Stop asks for SIM again", Button::STOP,
      {Phase::FAULT}, ANY, ANY, ANY, NO, YES},
    {"the console asks the operator: Confirm", Button::CONFIRM,
      {Phase::AWAITING_OPERATOR}, ANY, ANY, ANY, ANY, ANY},
  };
  return table;
}

bool expected(Button button, const ConsoleView & v)
{
  if (!v.heard) {
    return false;
  }
  for (const Row & row : rows()) {
    if (row.button == button && (row.phases.empty() || row.phases.count(v.phase) == 1) &&
      satisfies(row.started, v.robot_started) && satisfies(row.busy, v.busy) &&
      satisfies(row.at_start, v.at_start) && satisfies(row.twin_in_sim, v.twin_in_sim) &&
      satisfies(row.physical, v.has_physical_side))
    {
      return true;
    }
  }
  return false;
}

}  // namespace

TEST(Enablement, EveryPhaseAndEveryFlagFollowsTheTableOfSituations)
{
  int rows_walked = 0;
  for (const Phase phase : ALL_PHASES) {
    for (int bits = 0; bits < 64; ++bits) {
      ConsoleView v;
      v.phase = phase;
      v.heard = bits & 1;
      v.robot_started = bits & 2;
      v.busy = bits & 4;
      v.at_start = bits & 8;
      v.twin_in_sim = bits & 16;
      v.has_physical_side = bits & 32;
      const ButtonStates got = enabled_for(v);
      ++rows_walked;
      EXPECT_EQ(got.start_robot, expected(Button::START_ROBOT, v)) << describe(v);
      EXPECT_EQ(got.home, expected(Button::HOME, v)) << describe(v);
      EXPECT_EQ(got.start_program, expected(Button::START_PROGRAM, v)) << describe(v);
      EXPECT_EQ(got.stop, expected(Button::STOP, v)) << describe(v);
      EXPECT_EQ(got.confirm, expected(Button::CONFIRM, v)) << describe(v);
    }
  }
  EXPECT_EQ(rows_walked, 9 * 64);
}

TEST(Enablement, EveryRowOfTheTableIsReachable)
{
  // A row no view matches would be a situation the walk never checks.
  for (const Row & row : rows()) {
    bool reached = false;
    for (const Phase phase : ALL_PHASES) {
      for (int bits = 0; bits < 32 && !reached; ++bits) {
        const ConsoleView v = view(
          phase, bits & 1, bits & 2, bits & 4, bits & 8, bits & 16);
        reached = (row.phases.empty() || row.phases.count(phase) == 1) &&
          satisfies(row.started, v.robot_started) && satisfies(row.busy, v.busy) &&
          satisfies(row.at_start, v.at_start) && satisfies(row.twin_in_sim, v.twin_in_sim) &&
          satisfies(row.physical, v.has_physical_side);
      }
    }
    EXPECT_TRUE(reached) << row.situation;
  }
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
  // StopCell.srv: in FAULT while the twin is not in SIM, on a pair with a
  // physical side, Stop asks for SIM.
  EXPECT_TRUE(enabled_for(view(Phase::FAULT, false, false, false, false, true)).stop);
  EXPECT_FALSE(enabled_for(view(Phase::FAULT, false, false, false, true, true)).stop);
  // P-R03: on an all-simulated pair the console refuses that Stop; not offered.
  EXPECT_FALSE(enabled_for(view(Phase::FAULT, false, false, false, false, false)).stop);
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
