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
// Two halves. The exhaustive half walks all 9 phases x 2^12 flags x 4
// selections and holds each button to an INDEPENDENT statement of the rule: a
// table of named rows, each one situation in which one button is offered
// (P-R03). A button is expected enabled exactly when some row for it matches,
// so the expectation is read off data written as an operator would say it,
// never off a restated formula; a failure names the view, and the rows say
// what should have been offered. The named half pins the rows an operator
// meets, so that a failure reads as a situation.
//
// The panel knows NOTHING about which sides a target commands (review R-02):
// whether a target may be started, and whether the speed floor applies to it,
// are the console's published verdicts (`startable_targets`,
// `floored_targets`), and the rows below are stated in those terms only.

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
using cite_console_gui::floor_applies;
using cite_console_gui::Phase;
using cite_console_gui::phase_name;
using cite_console_gui::settled_selection;
using cite_console_gui::SPEED_CHOICES;
using cite_console_gui::speed_choice_enabled;
using cite_console_gui::Target;
using cite_console_gui::target_choice_enabled;
using cite_console_gui::target_name;
using cite_console_gui::validation_phase_name;
using cite_console_gui::ValidationPhase;

namespace
{

/// Every selection the panel can hold, the empty one included.
const std::vector<Target> SELECTIONS = {Target::NONE, Target::SIM, Target::REAL, Target::TWIN};

/// The two deployments ADR-0072 decision 4 names.
const std::set<Target> PLANT_ONLY = {Target::SIM};
const std::set<Target> BOTH_SIDES = {Target::SIM, Target::REAL, Target::TWIN};

ConsoleView view(
  Phase phase, bool robot_started = false, bool busy = false,
  std::set<Target> available = BOTH_SIDES, std::set<Target> startable = {},
  bool twin_in_sim = true, bool has_physical_side = false)
{
  ConsoleView v;
  v.heard = true;
  v.phase = phase;
  v.robot_started = robot_started;
  v.busy = busy;
  v.available_targets = std::move(available);
  v.startable_targets = std::move(startable);
  v.twin_in_sim = twin_in_sim;
  v.has_physical_side = has_physical_side;
  return v;
}

/// A READY, started, idle console serving both sides, `startable` startable.
ConsoleView ready(std::set<Target> startable = {})
{
  return view(Phase::READY, true, false, BOTH_SIDES, std::move(startable));
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

std::string names_of(const std::set<Target> & targets)
{
  std::string names;
  for (const Target target : targets) {
    names += std::string(target_name(target)) + ",";
  }
  return names;
}

std::string describe(const ConsoleView & v, Target selected)
{
  return std::string(phase_name(v.phase)) + " heard=" + std::to_string(v.heard) +
         " started=" + std::to_string(v.robot_started) + " busy=" + std::to_string(v.busy) +
         " sim=" + std::to_string(v.twin_in_sim) +
         " physical=" + std::to_string(v.has_physical_side) +
         " offered=" + std::to_string(v.validate_then_run_offered) +
         " available=[" + names_of(v.available_targets) +
         "] startable=[" + names_of(v.startable_targets) +
         "] selected=" + target_name(selected);
}

enum class Button { START_ROBOT, HOME, START_PROGRAM, STOP, CONFIRM, VALIDATE_THEN_RUN };

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
  Need selected_startable;    // the selection is one of startable_targets
  Need offered = Need::ANY;   // validate_then_run_offered
  Need twin_startable = Need::ANY;  // the twin is one of startable_targets
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
      {Phase::NOT_STARTED}, ANY, NO, ANY, ANY, {}, ANY, ANY},
    {"a READY console, idle, may be started again", Button::START_ROBOT,
      {Phase::READY}, ANY, NO, ANY, ANY, {}, ANY, ANY},
    {"a FAULT, idle, is left by Start robot", Button::START_ROBOT,
      {Phase::FAULT}, ANY, NO, ANY, ANY, {}, ANY, ANY},
    {"a started robot, READY and idle, with a served target selected, may Home", Button::HOME,
      {Phase::READY}, YES, NO, ANY, ANY, {}, YES, ANY},
    {"... and with a target the console says is startable selected, may run",
      Button::START_PROGRAM,
      {Phase::READY}, YES, NO, ANY, ANY, {}, YES, YES},
    {"a request in progress, in any phase, may be stopped", Button::STOP,
      {}, ANY, YES, ANY, ANY, {}, ANY, ANY},
    {"a FAULT out of SIM with a physical side: Stop asks for SIM again", Button::STOP,
      {Phase::FAULT}, ANY, ANY, NO, YES, {}, ANY, ANY},
    {"the console asks the operator: Confirm", Button::CONFIRM,
      {Phase::AWAITING_OPERATOR}, ANY, ANY, ANY, ANY, {}, ANY, ANY},
    {"a started robot, READY and idle, the console offering it and the twin startable, "
      "may validate then run - whatever target is selected", Button::VALIDATE_THEN_RUN,
      {Phase::READY}, YES, NO, ANY, ANY, {}, ANY, ANY, YES, YES},
  };
  return table;
}

bool matches(const Row & row, const ConsoleView & v, Target selected)
{
  const bool served = selected != Target::NONE && v.available_targets.count(selected) == 1;
  const bool startable =
    selected != Target::NONE && v.startable_targets.count(selected) == 1;
  return (row.phases.empty() || row.phases.count(v.phase) == 1) &&
         satisfies(row.started, v.robot_started) && satisfies(row.busy, v.busy) &&
         satisfies(row.twin_in_sim, v.twin_in_sim) &&
         satisfies(row.physical, v.has_physical_side) &&
         (row.selected.empty() || row.selected.count(selected) == 1) &&
         satisfies(row.selected_served, served) &&
         satisfies(row.selected_startable, startable) &&
         satisfies(row.offered, v.validate_then_run_offered) &&
         satisfies(row.twin_startable, v.startable_targets.count(Target::TWIN) == 1);
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

constexpr int FLAG_BITS = 12;

/// The view for one combination of the flags `bits` encodes.
ConsoleView walked(Phase phase, int bits)
{
  ConsoleView v;
  v.phase = phase;
  v.heard = bits & 1;
  v.robot_started = bits & 2;
  v.busy = bits & 4;
  v.twin_in_sim = bits & 8;
  v.has_physical_side = bits & 16;
  v.available_targets = targets_of((bits >> 5) & 7);
  v.startable_targets = targets_of((bits >> 8) & 7);
  v.validate_then_run_offered = bits & 2048;
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
        EXPECT_EQ(got.validate_then_run, expected(Button::VALIDATE_THEN_RUN, v, selected))
          << describe(v, selected);
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
  ConsoleView v = ready(BOTH_SIDES);
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
      enabled_for(view(Phase::READY, true, false, available, available), Target::NONE);
    EXPECT_FALSE(got.home);
    EXPECT_FALSE(got.start_program);
    EXPECT_TRUE(got.start_robot);
  }
}

TEST(Enablement, ATargetTheConsoleDoesNotServeIsNotSent)
{
  // Plant-only: the real arm and the twin are not running.
  const ConsoleView v = view(Phase::READY, true, false, PLANT_ONLY, PLANT_ONLY);
  EXPECT_TRUE(enabled_for(v, Target::SIM).home);
  EXPECT_FALSE(enabled_for(v, Target::REAL).home);
  EXPECT_FALSE(enabled_for(v, Target::TWIN).home);
  EXPECT_FALSE(enabled_for(v, Target::TWIN).start_program);
}

TEST(Enablement, StartProgramFollowsTheConsolesStartableTargets)
{
  // R-02: the console says which targets have every side at the start; the
  // panel follows it and computes nothing about sides itself.
  for (const Target target : ALL_TARGETS) {
    EXPECT_TRUE(enabled_for(ready({target}), target).start_program) << target_name(target);
    EXPECT_FALSE(enabled_for(ready(), target).start_program) << target_name(target);
    for (const Target other : ALL_TARGETS) {
      if (other != target) {
        EXPECT_FALSE(enabled_for(ready({other}), target).start_program)
          << target_name(target) << " with only " << target_name(other) << " startable";
      }
    }
  }
  // Startable but not served (a stale list): not sent.
  EXPECT_FALSE(
    enabled_for(view(Phase::READY, true, false, PLANT_ONLY, {Target::TWIN}), Target::TWIN)
    .start_program);
  // Home never waits for the start: it is what brings the arms there.
  EXPECT_TRUE(enabled_for(ready(), Target::TWIN).home);
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
      return view(Phase::FAULT, false, false, BOTH_SIDES, {}, twin_in_sim, physical);
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
    enabled_for(view(Phase::UNKNOWN, true, false, BOTH_SIDES, BOTH_SIDES), Target::SIM),
    expected);
  expected.stop = true;
  EXPECT_EQ(
    enabled_for(view(Phase::UNKNOWN, true, true, BOTH_SIDES, BOTH_SIDES), Target::SIM),
    expected);
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

TEST(Selection, AnotherPublisherOrAnUnreadableChangeClearsIt)
{
  // R-02: the same set from another publisher is a console that came back.
  ConsoleView first = ready();
  first.publisher = {1};
  ConsoleView second = ready();
  second.publisher = {2};
  EXPECT_EQ(settled_selection(first, first, Target::SIM), Target::SIM);
  EXPECT_EQ(settled_selection(first, second, Target::SIM), Target::NONE);
  // R-03: a served value this panel does not recognise appeared.
  ConsoleView with_unknown = first;
  with_unknown.served_values = {254};
  EXPECT_EQ(settled_selection(first, with_unknown, Target::SIM), Target::NONE);
  EXPECT_EQ(settled_selection(with_unknown, first, Target::SIM), Target::NONE);
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

TEST(Targets, TheRealArmsSideRunsWhereTheConsoleSaysItDoes)
{
  // R-02: read off ConsoleState.counterpart_running, never off the targets.
  ConsoleView v = ready();
  EXPECT_FALSE(counterpart_running(v));
  v.counterpart_running = true;
  EXPECT_TRUE(counterpart_running(v));
  // Served targets say nothing about it.
  ConsoleView plant_only = view(Phase::READY, true, false, PLANT_ONLY);
  plant_only.counterpart_running = true;
  EXPECT_TRUE(counterpart_running(plant_only));
  v.heard = false;
  EXPECT_FALSE(counterpart_running(v));
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

TEST(SpeedChoices, TheFloorAppliesOnlyToATargetTheConsoleFloors)
{
  // R-02: which targets command a physical side is the console's to say
  // (`floored_targets`); the panel assumes nothing about which side is real.
  ConsoleView v = ready();
  v.minimum_speed_scale = 0.25;
  v.floored_targets = {Target::REAL, Target::TWIN};
  EXPECT_TRUE(speed_choice_enabled(0.1, v, Target::SIM));
  EXPECT_FALSE(speed_choice_enabled(0.1, v, Target::REAL));
  EXPECT_FALSE(speed_choice_enabled(0.1, v, Target::TWIN));
  EXPECT_TRUE(speed_choice_enabled(0.25, v, Target::REAL));
  EXPECT_TRUE(speed_choice_enabled(1.0, v, Target::TWIN));
  // An all-simulated pair floors nothing.
  v.floored_targets = {};
  for (const Target target : ALL_TARGETS) {
    EXPECT_TRUE(speed_choice_enabled(0.1, v, target)) << target_name(target);
  }
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

TEST(ValidateThenRun, OfferedStartedReadyAndBothArmsAtTheStartEnablesIt)
{
  ConsoleView v = ready({Target::TWIN});
  v.validate_then_run_offered = true;
  // It carries no target: every selection, none included, enables it alike.
  for (const Target selected : SELECTIONS) {
    EXPECT_TRUE(enabled_for(v, selected).validate_then_run) << target_name(selected);
  }
}

TEST(ValidateThenRun, EachMissingConditionDisablesItAlone)
{
  // Independent rows: one condition removed from the enabling view each time.
  struct Row
  {
    const char * situation;
    void (* change)(ConsoleView &);
  };
  const std::vector<Row> rows = {
    {"not offered (a plant-only deployment)",
      [](ConsoleView & v) {v.validate_then_run_offered = false;}},
    {"the twin not startable (an arm away from the start)",
      [](ConsoleView & v) {v.startable_targets = {Target::SIM, Target::REAL};}},
    {"a request in progress", [](ConsoleView & v) {v.busy = true;}},
    {"Start robot has not succeeded", [](ConsoleView & v) {v.robot_started = false;}},
    {"not READY (FAULT)", [](ConsoleView & v) {v.phase = Phase::FAULT;}},
    {"not READY (NOT_STARTED)", [](ConsoleView & v) {v.phase = Phase::NOT_STARTED;}},
    {"no console heard", [](ConsoleView & v) {v.heard = false;}},
  };
  for (const Row & row : rows) {
    ConsoleView v = ready({Target::TWIN});
    v.validate_then_run_offered = true;
    row.change(v);
    EXPECT_FALSE(enabled_for(v, Target::TWIN).validate_then_run) << row.situation;
    EXPECT_FALSE(enabled_for(v, Target::NONE).validate_then_run) << row.situation;
  }
}

TEST(ValidateThenRun, WhileItRunsOnlyStopIsOffered)
{
  ConsoleView v = view(Phase::RUNNING, true, true, BOTH_SIDES, {Target::TWIN});
  v.validate_then_run_offered = true;
  v.validation_phase = ValidationPhase::VALIDATING;
  ButtonStates expected;
  expected.stop = true;
  EXPECT_EQ(enabled_for(v, Target::TWIN), expected);
}

TEST(ValidateThenRun, ThePhaseNamesClaimNoMoreThanASimulationPass)
{
  // ADR-0073 decision 5: never "safe", "verified" or "validated".
  EXPECT_STREQ(validation_phase_name(ValidationPhase::VALIDATING), "Validating in simulation");
  EXPECT_STREQ(validation_phase_name(ValidationPhase::RUNNING), "Running twin");
  EXPECT_STREQ(validation_phase_name(ValidationPhase::NONE), "");
  for (const ValidationPhase phase : {ValidationPhase::NONE, ValidationPhase::VALIDATING,
      ValidationPhase::RUNNING, ValidationPhase::UNKNOWN})
  {
    const std::string name = validation_phase_name(phase);
    for (const char * word : {"safe", "Safe", "verified", "Verified", "validated", "Validated"}) {
      EXPECT_EQ(name.find(word), std::string::npos) << name;
    }
  }
}

TEST(SpeedChoices, TheFloorIsShownWhereItApplies)
{
  ConsoleView v = ready();
  v.minimum_speed_scale = 0.25;
  v.floored_targets = {Target::REAL, Target::TWIN};
  EXPECT_FALSE(floor_applies(v, Target::SIM));
  EXPECT_TRUE(floor_applies(v, Target::REAL));
  EXPECT_TRUE(floor_applies(v, Target::TWIN));
  // No target selected: assumed, as `speed_choice_enabled` applies it.
  EXPECT_TRUE(floor_applies(v, Target::NONE));
  // No floor stated (no physical side running): nothing to show.
  v.minimum_speed_scale = 0.0;
  for (const Target target : SELECTIONS) {
    EXPECT_FALSE(floor_applies(v, target)) << target_name(target);
  }
  // No console: nothing.
  v.minimum_speed_scale = 0.25;
  v.heard = false;
  EXPECT_FALSE(floor_applies(v, Target::TWIN));
}

TEST(SpeedChoices, EveryChoiceBelowTheFloorIsDisabledExactlyWhereTheFloorApplies)
{
  ConsoleView v = ready();
  v.minimum_speed_scale = 0.25;
  v.floored_targets = {Target::REAL, Target::TWIN};
  for (const Target target : SELECTIONS) {
    for (const double scale : SPEED_CHOICES) {
      const bool below = scale < v.minimum_speed_scale;
      EXPECT_EQ(speed_choice_enabled(scale, v, target), !(below && floor_applies(v, target)))
        << target_name(target) << " " << scale;
    }
  }
}
