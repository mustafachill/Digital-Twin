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

// The panel's enablement table, over every phase, every flag and every target
// (ADR-0071, ADR-0072).
//
// Two halves. The exhaustive half walks all 9 phases x 2^10 flags x 4
// selections and holds each button to an INDEPENDENT statement of the rule: a
// table of named rows, each one situation in which one button is offered
// (P-R03). A button is expected enabled exactly when some row for it matches,
// so the expectation is read off data written as an operator would say it,
// never off a restated formula; a failure names the view, and the rows say
// what should have been offered. The named half pins the rows an operator
// meets, so that a failure reads as a situation.

#include <gtest/gtest.h>

#include <set>
#include <string>
#include <utility>
#include <vector>

#include "cite_console_gui/enablement.hpp"

using cite_console_gui::ALL_PHASES;
using cite_console_gui::ALL_TARGETS;
using cite_console_gui::ButtonStates;
using cite_console_gui::ConsoleView;
using cite_console_gui::counterpart_running;
using cite_console_gui::enabled_for;
using cite_console_gui::includes_counterpart;
using cite_console_gui::includes_plant;
using cite_console_gui::Phase;
using cite_console_gui::phase_name;
using cite_console_gui::settled_selection;
using cite_console_gui::SPEED_CHOICES;
using cite_console_gui::speed_choice_enabled;
using cite_console_gui::Target;
using cite_console_gui::target_choice_enabled;
using cite_console_gui::target_name;

namespace
{

/// Every selection the panel can hold, the empty one included.
const std::vector<Target> SELECTIONS = {Target::NONE, Target::SIM, Target::REAL, Target::TWIN};

/// The two deployments ADR-0072 decision 4 names.
const std::set<Target> PLANT_ONLY = {Target::SIM};
const std::set<Target> BOTH_SIDES = {Target::SIM, Target::REAL, Target::TWIN};

ConsoleView view(
  Phase phase, bool robot_started = false, bool busy = false,
  std::set<Target> available = BOTH_SIDES, bool plant_at_start = false,
  bool counterpart_at_start = false, bool twin_in_sim = true, bool has_physical_side = false)
{
  ConsoleView v;
  v.heard = true;
  v.phase = phase;
  v.robot_started = robot_started;
  v.busy = busy;
  v.available_targets = std::move(available);
  v.plant_at_start = plant_at_start;
  v.counterpart_at_start = counterpart_at_start;
  v.twin_in_sim = twin_in_sim;
  v.has_physical_side = has_physical_side;
  return v;
}

/// A READY, started, idle console serving both sides.
ConsoleView ready(bool plant_at_start = false, bool counterpart_at_start = false)
{
  return view(Phase::READY, true, false, BOTH_SIDES, plant_at_start, counterpart_at_start);
}

/// A view serving exactly the targets `bits` names, one bit per ALL_TARGETS.
std::set<Target> targets_of(int bits)
{
  std::set<Target> targets;
  for (std::size_t i = 0; i < ALL_TARGETS.size(); ++i) {
    if (bits & (1 << i)) {
      targets.insert(ALL_TARGETS[i]);
    }
  }
  return targets;
}

std::string describe(const ConsoleView & v, Target selected)
{
  std::string available;
  for (const Target target : v.available_targets) {
    available += std::string(target_name(target)) + ",";
  }
  return std::string(phase_name(v.phase)) + " heard=" + std::to_string(v.heard) +
         " started=" + std::to_string(v.robot_started) + " busy=" + std::to_string(v.busy) +
         " plant_at_start=" + std::to_string(v.plant_at_start) +
         " counterpart_at_start=" + std::to_string(v.counterpart_at_start) +
         " sim=" + std::to_string(v.twin_in_sim) +
         " physical=" + std::to_string(v.has_physical_side) + " available=[" + available +
         "] selected=" + target_name(selected);
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
  Need twin_in_sim;
  Need physical;
  std::set<Target> selected;  // empty: any selection, none included
  Need selected_served;       // the selection is one of available_targets
  Need plant_at_start;
  Need counterpart_at_start;
};

constexpr Need ANY = Need::ANY;
constexpr Need YES = Need::YES;
constexpr Need NO = Need::NO;

/// The rule, as ADR-0071, ADR-0072 and StopCell.srv state it, one situation
/// per row.
const std::vector<Row> & rows()
{
  static const std::vector<Row> table = {
    {"a console not started, idle, offers Start robot", Button::START_ROBOT,
      {Phase::NOT_STARTED}, ANY, NO, ANY, ANY, {}, ANY, ANY, ANY},
    {"a READY console, idle, may be started again", Button::START_ROBOT,
      {Phase::READY}, ANY, NO, ANY, ANY, {}, ANY, ANY, ANY},
    {"a FAULT, idle, is left by Start robot", Button::START_ROBOT,
      {Phase::FAULT}, ANY, NO, ANY, ANY, {}, ANY, ANY, ANY},
    {"a started robot, READY and idle, with a served target selected, may Home", Button::HOME,
      {Phase::READY}, YES, NO, ANY, ANY, {}, YES, ANY, ANY},
    {"... and with the simulation selected and at the start, may run", Button::START_PROGRAM,
      {Phase::READY}, YES, NO, ANY, ANY, {Target::SIM}, YES, YES, ANY},
    {"... and with the real arm selected and at the start, may run", Button::START_PROGRAM,
      {Phase::READY}, YES, NO, ANY, ANY, {Target::REAL}, YES, ANY, YES},
    {"... and with the twin selected and both arms at the start, may run",
      Button::START_PROGRAM,
      {Phase::READY}, YES, NO, ANY, ANY, {Target::TWIN}, YES, YES, YES},
    {"a request in progress, in any phase, may be stopped", Button::STOP,
      {}, ANY, YES, ANY, ANY, {}, ANY, ANY, ANY},
    {"a FAULT out of SIM with a physical side: Stop asks for SIM again", Button::STOP,
      {Phase::FAULT}, ANY, ANY, NO, YES, {}, ANY, ANY, ANY},
    {"the console asks the operator: Confirm", Button::CONFIRM,
      {Phase::AWAITING_OPERATOR}, ANY, ANY, ANY, ANY, {}, ANY, ANY, ANY},
  };
  return table;
}

bool matches(const Row & row, const ConsoleView & v, Target selected)
{
  const bool served = selected != Target::NONE && v.available_targets.count(selected) == 1;
  return (row.phases.empty() || row.phases.count(v.phase) == 1) &&
         satisfies(row.started, v.robot_started) && satisfies(row.busy, v.busy) &&
         satisfies(row.twin_in_sim, v.twin_in_sim) &&
         satisfies(row.physical, v.has_physical_side) &&
         (row.selected.empty() || row.selected.count(selected) == 1) &&
         satisfies(row.selected_served, served) &&
         satisfies(row.plant_at_start, v.plant_at_start) &&
         satisfies(row.counterpart_at_start, v.counterpart_at_start);
}

bool expected(Button button, const ConsoleView & v, Target selected)
{
  if (!v.heard) {
    return false;
  }
  for (const Row & row : rows()) {
    if (row.button == button && matches(row, v, selected)) {
      return true;
    }
  }
  return false;
}

constexpr int FLAG_BITS = 10;

/// The view for one combination of the flags `bits` encodes.
ConsoleView walked(Phase phase, int bits)
{
  ConsoleView v;
  v.phase = phase;
  v.heard = bits & 1;
  v.robot_started = bits & 2;
  v.busy = bits & 4;
  v.plant_at_start = bits & 8;
  v.counterpart_at_start = bits & 16;
  v.twin_in_sim = bits & 32;
  v.has_physical_side = bits & 64;
  v.available_targets = targets_of(bits >> 7);
  return v;
}

}  // namespace

TEST(Enablement, EveryPhaseFlagAndSelectionFollowsTheTableOfSituations)
{
  int rows_walked = 0;
  for (const Phase phase : ALL_PHASES) {
    for (int bits = 0; bits < (1 << FLAG_BITS); ++bits) {
      const ConsoleView v = walked(phase, bits);
      for (const Target selected : SELECTIONS) {
        const ButtonStates got = enabled_for(v, selected);
        ++rows_walked;
        EXPECT_EQ(got.start_robot, expected(Button::START_ROBOT, v, selected))
          << describe(v, selected);
        EXPECT_EQ(got.home, expected(Button::HOME, v, selected)) << describe(v, selected);
        EXPECT_EQ(got.start_program, expected(Button::START_PROGRAM, v, selected))
          << describe(v, selected);
        EXPECT_EQ(got.stop, expected(Button::STOP, v, selected)) << describe(v, selected);
        EXPECT_EQ(got.confirm, expected(Button::CONFIRM, v, selected)) << describe(v, selected);
      }
    }
  }
  EXPECT_EQ(rows_walked, 9 * (1 << FLAG_BITS) * 4);
}

TEST(Enablement, EveryRowOfTheTableIsReachable)
{
  // A row no heard view matches would be a situation the walk never checks.
  for (const Row & row : rows()) {
    bool reached = false;
    for (const Phase phase : ALL_PHASES) {
      for (int bits = 1; bits < (1 << FLAG_BITS) && !reached; bits += 2) {
        for (const Target selected : SELECTIONS) {
          reached = reached || matches(row, walked(phase, bits), selected);
        }
      }
    }
    EXPECT_TRUE(reached) << row.situation;
  }
}

TEST(Enablement, NothingBeforeTheConsoleIsHeard)
{
  ConsoleView v = ready(true, true);
  v.heard = false;
  EXPECT_EQ(enabled_for(v, Target::TWIN), ButtonStates{});
  EXPECT_EQ(enabled_for(ConsoleView{}, Target::NONE), ButtonStates{});
}

TEST(Enablement, NotStartedOffersOnlyStartRobot)
{
  ButtonStates expected;
  expected.start_robot = true;
  EXPECT_EQ(enabled_for(view(Phase::NOT_STARTED), Target::SIM), expected);
}

TEST(Enablement, HomeNeedsAStartedRobot)
{
  // READY without robot_started: a console that never started cannot home.
  EXPECT_FALSE(enabled_for(view(Phase::READY, false), Target::SIM).home);
  EXPECT_TRUE(enabled_for(view(Phase::READY, true), Target::SIM).home);
}

TEST(Enablement, HomeAndStartProgramNeedASelectedTarget)
{
  // ADR-0072 decision 3: never defaulted. No selection, nothing to send -
  // even where the plant is the only target served (R-18).
  for (const auto & available : {BOTH_SIDES, PLANT_ONLY}) {
    const ButtonStates got =
      enabled_for(view(Phase::READY, true, false, available, true, true), Target::NONE);
    EXPECT_FALSE(got.home);
    EXPECT_FALSE(got.start_program);
    EXPECT_TRUE(got.start_robot);
  }
}

TEST(Enablement, ATargetTheConsoleDoesNotServeIsNotSent)
{
  // Plant-only: the real arm and the twin are not running.
  const ConsoleView v = view(Phase::READY, true, false, PLANT_ONLY, true, true);
  EXPECT_TRUE(enabled_for(v, Target::SIM).home);
  EXPECT_FALSE(enabled_for(v, Target::REAL).home);
  EXPECT_FALSE(enabled_for(v, Target::TWIN).home);
  EXPECT_FALSE(enabled_for(v, Target::TWIN).start_program);
}

TEST(Enablement, StartProgramNeedsEverySideOfTheTargetAtTheStart)
{
  // Simulation only: the real arm's position is not its business.
  EXPECT_TRUE(enabled_for(ready(true, false), Target::SIM).start_program);
  EXPECT_FALSE(enabled_for(ready(false, true), Target::SIM).start_program);
  // Real arm only: the simulation's position is not its business.
  EXPECT_TRUE(enabled_for(ready(false, true), Target::REAL).start_program);
  EXPECT_FALSE(enabled_for(ready(true, false), Target::REAL).start_program);
  // Twin: both, so a single-side run that left them apart needs a Home first.
  EXPECT_FALSE(enabled_for(ready(true, false), Target::TWIN).start_program);
  EXPECT_FALSE(enabled_for(ready(false, true), Target::TWIN).start_program);
  EXPECT_TRUE(enabled_for(ready(true, true), Target::TWIN).start_program);
  // Home never waits for the start: it is what brings the arms there.
  EXPECT_TRUE(enabled_for(ready(false, false), Target::TWIN).home);
}

TEST(Enablement, WhileRunningOnlyStopIsOffered)
{
  ButtonStates expected;
  expected.stop = true;
  EXPECT_EQ(enabled_for(view(Phase::RUNNING, true, true), Target::TWIN), expected);
  EXPECT_EQ(enabled_for(view(Phase::HOMING, true, true), Target::SIM), expected);
}

TEST(Enablement, AwaitingTheOperatorOffersConfirmAndStop)
{
  const ButtonStates got = enabled_for(view(Phase::AWAITING_OPERATOR, true, true), Target::REAL);
  EXPECT_TRUE(got.confirm);
  EXPECT_TRUE(got.stop);
  EXPECT_FALSE(got.start_robot || got.home || got.start_program);
}

TEST(Enablement, FaultOutOfSimOffersStopToAskForSimAgain)
{
  // StopCell.srv: in FAULT while the twin is not in SIM, on a pair with a
  // physical side, Stop asks for SIM.
  const auto fault = [](bool twin_in_sim, bool physical) {
      return view(Phase::FAULT, false, false, BOTH_SIDES, false, false, twin_in_sim, physical);
    };
  EXPECT_TRUE(enabled_for(fault(false, true), Target::NONE).stop);
  EXPECT_FALSE(enabled_for(fault(true, true), Target::NONE).stop);
  // P-R03: on an all-simulated pair the console refuses that Stop; not offered.
  EXPECT_FALSE(enabled_for(fault(false, false), Target::NONE).stop);
  // And Start robot is the way back to READY either way.
  EXPECT_TRUE(enabled_for(fault(false, false), Target::NONE).start_robot);
}

TEST(Enablement, AnUnrecognisedStateOffersNothingButStopWhileBusy)
{
  ButtonStates expected;
  EXPECT_EQ(
    enabled_for(view(Phase::UNKNOWN, true, false, BOTH_SIDES, true, true), Target::SIM),
    expected);
  expected.stop = true;
  EXPECT_EQ(
    enabled_for(view(Phase::UNKNOWN, true, true, BOTH_SIDES, true, true), Target::SIM),
    expected);
}

TEST(Targets, EachTargetCommandsTheSidesItNames)
{
  // ADR-0072: SIM -> the plant, REAL -> the counterpart, TWIN -> both.
  EXPECT_TRUE(includes_plant(Target::SIM));
  EXPECT_FALSE(includes_counterpart(Target::SIM));
  EXPECT_FALSE(includes_plant(Target::REAL));
  EXPECT_TRUE(includes_counterpart(Target::REAL));
  EXPECT_TRUE(includes_plant(Target::TWIN));
  EXPECT_TRUE(includes_counterpart(Target::TWIN));
  EXPECT_FALSE(includes_plant(Target::NONE));
  EXPECT_FALSE(includes_counterpart(Target::NONE));
}

TEST(Targets, OnlyAServedTargetMayBeChosen)
{
  const ConsoleView plant_only = view(Phase::READY, true, false, PLANT_ONLY);
  EXPECT_TRUE(target_choice_enabled(plant_only, Target::SIM));
  EXPECT_FALSE(target_choice_enabled(plant_only, Target::REAL));
  EXPECT_FALSE(target_choice_enabled(plant_only, Target::TWIN));
  for (const Target target : ALL_TARGETS) {
    EXPECT_TRUE(target_choice_enabled(ready(), target)) << target_name(target);
  }
  EXPECT_FALSE(target_choice_enabled(ready(), Target::NONE));
  ConsoleView unheard = ready();
  unheard.heard = false;
  EXPECT_FALSE(target_choice_enabled(unheard, Target::SIM));
  // Choosing is not gated on the phase: the operator may pick while busy.
  EXPECT_TRUE(target_choice_enabled(view(Phase::RUNNING, true, true), Target::REAL));
}

TEST(Selection, NothingIsPreselectedOnLoad)
{
  // The panel starts with no console heard and no selection; the first state
  // it hears selects nothing, however many targets it serves (R-18).
  const ConsoleView loaded{};
  EXPECT_EQ(settled_selection(loaded, ready(), Target::NONE), Target::NONE);
  const ConsoleView plant_only = view(Phase::READY, true, false, PLANT_ONLY);
  EXPECT_EQ(settled_selection(loaded, plant_only, Target::NONE), Target::NONE);
}

TEST(Selection, NothingIsPreselectedEvenWhenOnlyOneTargetIsServed)
{
  // R-18: a plant-only deployment still waits for the operator to pick.
  const ConsoleView plant_only = view(Phase::READY, true, false, PLANT_ONLY);
  EXPECT_EQ(settled_selection(plant_only, plant_only, Target::NONE), Target::NONE);
}

TEST(Selection, TheOperatorsPickStaysWhileTheServedSetIsUnchanged)
{
  for (const Target target : ALL_TARGETS) {
    // Picking: the view does not change.
    EXPECT_EQ(settled_selection(ready(), ready(), target), target) << target_name(target);
    // A new state with the same targets served (the phase or a flag moved).
    EXPECT_EQ(
      settled_selection(ready(), view(Phase::RUNNING, true, true), target), target)
      << target_name(target);
  }
}

TEST(Selection, AnyChangeToTheServedSetClearsIt)
{
  // The real arm's side went away: even SIM, still served, is cleared, and
  // the plant's sole target is not chosen for the operator (R-18).
  const ConsoleView plant_only = view(Phase::READY, true, false, PLANT_ONLY);
  for (const Target target : SELECTIONS) {
    EXPECT_EQ(settled_selection(ready(), plant_only, target), Target::NONE)
      << target_name(target);
  }
  // The real arm's side came up: the plant-only selection is cleared too.
  EXPECT_EQ(settled_selection(plant_only, ready(), Target::SIM), Target::NONE);
}

TEST(Selection, AConsoleThatLeftOrCameBackClearsIt)
{
  ConsoleView gone = ready();
  gone.heard = false;
  // Gone: the publisher unmatched.
  EXPECT_EQ(settled_selection(ready(), ConsoleView{}, Target::TWIN), Target::NONE);
  // Back, serving exactly what it served before: still cleared.
  EXPECT_EQ(settled_selection(ConsoleView{}, ready(), Target::TWIN), Target::NONE);
  EXPECT_EQ(settled_selection(gone, ready(), Target::TWIN), Target::NONE);
}

TEST(Selection, OverEveryTransitionTheSelectionIsTheOperatorsOrNone)
{
  // Every served set before and after, heard or not, every prior selection:
  // the result is never a target the operator did not pick, never one that
  // is not served, and is kept only across an unchanged served set.
  for (int before_bits = 0; before_bits < 16; ++before_bits) {
    for (int now_bits = 0; now_bits < 16; ++now_bits) {
      ConsoleView before = ready();
      before.heard = before_bits & 8;
      before.available_targets = targets_of(before_bits & 7);
      ConsoleView now = ready();
      now.heard = now_bits & 8;
      now.available_targets = targets_of(now_bits & 7);
      for (const Target selected : SELECTIONS) {
        const Target settled = settled_selection(before, now, selected);
        const std::string where = describe(before, selected) + " -> " + describe(now, selected);
        EXPECT_TRUE(settled == Target::NONE || settled == selected) << where;
        EXPECT_TRUE(settled == Target::NONE || target_choice_enabled(now, settled)) << where;
        if (before.available_targets != now.available_targets || !before.heard) {
          EXPECT_EQ(settled, Target::NONE) << where;
        }
      }
    }
  }
}

TEST(Targets, TheRealArmsSideRunsOnlyWhereATargetCommandsIt)
{
  EXPECT_FALSE(counterpart_running(view(Phase::READY, true, false, PLANT_ONLY)));
  EXPECT_TRUE(counterpart_running(ready()));
  EXPECT_TRUE(counterpart_running(view(Phase::READY, true, false, {Target::TWIN})));
  EXPECT_FALSE(counterpart_running(ConsoleView{}));
}

TEST(Targets, EveryTargetHasADistinctName)
{
  std::set<std::string> names;
  for (const Target target : SELECTIONS) {
    names.insert(target_name(target));
  }
  EXPECT_EQ(names.size(), SELECTIONS.size());
}

TEST(SpeedChoices, TheProgramsOwnSpeedComesFirst)
{
  EXPECT_DOUBLE_EQ(SPEED_CHOICES.front(), 1.0);
  for (const double scale : SPEED_CHOICES) {
    EXPECT_GT(scale, 0.0);
    EXPECT_LE(scale, 1.0);
  }
}

TEST(SpeedChoices, TheFloorAppliesOnlyToATargetWithTheRealArm)
{
  ConsoleView v = ready();
  v.minimum_speed_scale = 0.25;
  // ADR-0072 decision 2: the physical speed floor is the real arm's.
  EXPECT_TRUE(speed_choice_enabled(0.1, v, Target::SIM));
  EXPECT_FALSE(speed_choice_enabled(0.1, v, Target::REAL));
  EXPECT_FALSE(speed_choice_enabled(0.1, v, Target::TWIN));
  EXPECT_TRUE(speed_choice_enabled(0.25, v, Target::REAL));
  EXPECT_TRUE(speed_choice_enabled(1.0, v, Target::TWIN));
  // No target yet: the floor holds, so nothing offered is taken back.
  EXPECT_FALSE(speed_choice_enabled(0.1, v, Target::NONE));
  EXPECT_TRUE(speed_choice_enabled(0.5, v, Target::NONE));
}

TEST(SpeedChoices, OutsideTheUnitIntervalOrWithNoConsoleNothingIsOffered)
{
  const ConsoleView v = ready();
  for (const Target target : SELECTIONS) {
    EXPECT_TRUE(speed_choice_enabled(1.0, v, target));
    EXPECT_TRUE(speed_choice_enabled(0.1, v, target));
    EXPECT_FALSE(speed_choice_enabled(0.0, v, target));
    EXPECT_FALSE(speed_choice_enabled(1.5, v, target));
  }
  EXPECT_FALSE(speed_choice_enabled(1.0, ConsoleView{}, Target::SIM));
}

TEST(PhaseNames, EveryPhaseHasADistinctName)
{
  std::set<std::string> names;
  for (const Phase phase : ALL_PHASES) {
    names.insert(phase_name(phase));
  }
  EXPECT_EQ(names.size(), ALL_PHASES.size());
}
