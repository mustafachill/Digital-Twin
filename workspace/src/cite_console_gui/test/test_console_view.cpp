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
#include <vector>

#include "cite_console_gui/console_view.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"

using cite_console_gui::Phase;
using cite_console_gui::phase_from;
using cite_console_gui::Target;
using cite_console_gui::target_from;
using cite_console_gui::target_value;
using cite_console_gui::twin_mode_name;
using cite_console_gui::validate_then_run_outcome;
using cite_console_gui::validation_phase_from;
using cite_console_gui::ValidationPhase;
using cite_console_gui::view_from;
using cite_interfaces::action::ValidateThenRun;
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
  state.plant_at_start = true;
  state.counterpart_at_start = false;
  state.minimum_speed_scale = 0.25;
  state.twin_mode = TwinMode::MODE_SIM;
  auto view = view_from(state);
  EXPECT_TRUE(view.heard);
  EXPECT_EQ(view.phase, Phase::READY);
  EXPECT_TRUE(view.robot_started);
  EXPECT_FALSE(view.busy);
  EXPECT_TRUE(view.plant_at_start);
  EXPECT_FALSE(view.counterpart_at_start);
  EXPECT_DOUBLE_EQ(view.minimum_speed_scale, 0.25);
  EXPECT_TRUE(view.twin_in_sim);

  // Each side is its own flag, not one read for the other.
  state.plant_at_start = false;
  state.counterpart_at_start = true;
  EXPECT_FALSE(view_from(state).plant_at_start);
  EXPECT_TRUE(view_from(state).counterpart_at_start);

  state.twin_mode = TwinMode::MODE_VALIDATED;
  EXPECT_FALSE(view_from(state).twin_in_sim);
  // Not heard yet is not SIM.
  state.twin_mode = ConsoleState::TWIN_MODE_UNKNOWN;
  EXPECT_FALSE(view_from(state).twin_in_sim);
}

TEST(ConsoleView, TheViewCarriesTheConsolesTargetVerdicts)
{
  // R-02: startable and floored targets, and whether the counterpart runs, are
  // the console's published facts; the view carries them and derives nothing.
  ConsoleState state;
  state.state = ConsoleState::READY;
  state.available_targets = {
    ConsoleState::TARGET_SIM, ConsoleState::TARGET_REAL, ConsoleState::TARGET_TWIN};
  state.startable_targets = {ConsoleState::TARGET_REAL};
  state.floored_targets = {ConsoleState::TARGET_SIM};
  state.counterpart_running = true;
  const auto view = view_from(state);
  EXPECT_EQ(view.startable_targets, std::set<Target>{Target::REAL});
  EXPECT_EQ(view.floored_targets, std::set<Target>{Target::SIM});
  EXPECT_TRUE(view.counterpart_running);
  state.counterpart_running = false;
  state.startable_targets = {};
  state.floored_targets = {};
  const auto none = view_from(state);
  EXPECT_TRUE(none.startable_targets.empty());
  EXPECT_TRUE(none.floored_targets.empty());
  EXPECT_FALSE(none.counterpart_running);
}

TEST(ConsoleView, TheViewKeepsTheServedSetAsReceivedAndThePublisher)
{
  std::uint8_t unknown = 0xFE;
  while (target_from(unknown) != Target::NONE) {
    --unknown;
  }
  ConsoleState state;
  state.state = ConsoleState::READY;
  state.available_targets = {ConsoleState::TARGET_SIM, unknown};
  const std::vector<std::uint8_t> publisher = {9, 8, 7};
  const auto view = view_from(state, publisher);
  // Offered: only what this panel recognises.
  EXPECT_EQ(view.available_targets, std::set<Target>{Target::SIM});
  // Settled against: everything received (R-03).
  EXPECT_EQ(view.served_values, (std::set<std::uint8_t>{ConsoleState::TARGET_SIM, unknown}));
  EXPECT_EQ(view.publisher, publisher);
  EXPECT_TRUE(view_from(state).publisher.empty());
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

TEST(ConsoleView, EveryContractTargetIsAKnownTargetAndBack)
{
  const std::set<std::uint8_t> values = {
    ConsoleState::TARGET_SIM, ConsoleState::TARGET_REAL, ConsoleState::TARGET_TWIN,
  };
  std::set<Target> targets;
  for (const auto value : values) {
    const Target target = target_from(value);
    EXPECT_NE(target, Target::NONE) << static_cast<int>(value);
    EXPECT_EQ(target_value(target), value);
    targets.insert(target);
  }
  EXPECT_EQ(targets.size(), values.size()) << "two targets read as one";
  EXPECT_EQ(target_from(ConsoleState::TARGET_SIM), Target::SIM);
  EXPECT_EQ(target_from(ConsoleState::TARGET_REAL), Target::REAL);
  EXPECT_EQ(target_from(ConsoleState::TARGET_TWIN), Target::TWIN);
}

TEST(ConsoleView, UnsetOrUnknownTargetsAreNone)
{
  EXPECT_EQ(target_from(0), Target::NONE);
  EXPECT_EQ(target_from(200), Target::NONE);
  // NONE is sent as the unset value, which the console rejects.
  EXPECT_EQ(target_value(Target::NONE), 0);
}

TEST(ConsoleView, TheServedTargetsAreReadAndAnUnknownOneIsNotOffered)
{
  ConsoleState state;
  state.state = ConsoleState::READY;
  EXPECT_TRUE(view_from(state).available_targets.empty());

  state.available_targets = {ConsoleState::TARGET_SIM};
  EXPECT_EQ(view_from(state).available_targets, std::set<Target>{Target::SIM});

  state.available_targets = {
    ConsoleState::TARGET_SIM, ConsoleState::TARGET_REAL, ConsoleState::TARGET_TWIN, 0, 200};
  const std::set<Target> all = {Target::SIM, Target::REAL, Target::TWIN};
  EXPECT_EQ(view_from(state).available_targets, all);
}

TEST(ConsoleView, APhysicalSideIsReadFromTheListOfThem)
{
  ConsoleState state;
  state.state = ConsoleState::FAULT;
  EXPECT_FALSE(view_from(state).has_physical_side);
  state.physical_sides.push_back("counterpart");
  EXPECT_TRUE(view_from(state).has_physical_side);
}

TEST(ConsoleView, EveryContractPhaseIsAKnownValidationPhase)
{
  EXPECT_EQ(validation_phase_from(ConsoleState::PHASE_NONE), ValidationPhase::NONE);
  EXPECT_EQ(validation_phase_from(ConsoleState::PHASE_VALIDATING), ValidationPhase::VALIDATING);
  EXPECT_EQ(validation_phase_from(ConsoleState::PHASE_RUNNING), ValidationPhase::RUNNING);
  EXPECT_EQ(validation_phase_from(200), ValidationPhase::UNKNOWN);
}

TEST(ConsoleView, TheViewCarriesTheOfferAndThePhase)
{
  ConsoleState state;
  state.state = ConsoleState::RUNNING;
  state.validate_then_run_offered = true;
  state.phase = ConsoleState::PHASE_RUNNING;
  auto view = view_from(state);
  EXPECT_TRUE(view.validate_then_run_offered);
  EXPECT_EQ(view.validation_phase, ValidationPhase::RUNNING);
  state.validate_then_run_offered = false;
  state.phase = ConsoleState::PHASE_NONE;
  view = view_from(state);
  EXPECT_FALSE(view.validate_then_run_offered);
  EXPECT_EQ(view.validation_phase, ValidationPhase::NONE);
}

TEST(ConsoleView, AValidateThenRunRefusedBeforeEitherPhaseSaysSo)
{
  // ValidateThenRun.action: PHASE_NONE is a request refused before either
  // phase began - at the goal's checks, or phase 1 measuring the plant away.
  ValidateThenRun::Result result;
  result.success = false;
  result.detail = "the plant is not at the program's start";
  result.ended_in = ConsoleState::PHASE_NONE;
  result.cycles_completed = 0;
  EXPECT_EQ(
    validate_then_run_outcome(result),
    "Validate then run: refused or failed. the plant is not at the program's start "
    "Refused before either phase began. Cycles completed on the twin: 0.");
}

TEST(ConsoleView, AValidateThenRunResultNamesThePhaseItEndedIn)
{
  ValidateThenRun::Result failed;
  failed.success = false;
  failed.detail = "stopped";
  failed.ended_in = ConsoleState::PHASE_VALIDATING;
  EXPECT_EQ(
    validate_then_run_outcome(failed),
    "Validate then run: refused or failed. stopped Ended in: Validating in simulation. "
    "Cycles completed on the twin: 0.");

  ValidateThenRun::Result passed;
  passed.success = true;
  passed.detail = "passed in simulation; 2 cycles on the twin";
  passed.ended_in = ConsoleState::PHASE_RUNNING;
  passed.cycles_completed = 2;
  EXPECT_EQ(
    validate_then_run_outcome(passed),
    "Validate then run: done. passed in simulation; 2 cycles on the twin "
    "Ended in: Running twin. Cycles completed on the twin: 2.");
}

TEST(ConsoleView, AValidateThenRunPhaseTheContractDoesNotProduceIsNotARefusal)
{
  // A success that names no phase is not said as a refusal, and a phase this
  // panel does not know is said as unrecognised, never guessed.
  ValidateThenRun::Result odd;
  odd.success = true;
  odd.ended_in = ConsoleState::PHASE_NONE;
  const std::string none = validate_then_run_outcome(odd);
  EXPECT_EQ(none.find("Refused"), std::string::npos) << none;
  EXPECT_NE(none.find("named no phase"), std::string::npos) << none;

  std::uint8_t undefined = 0;
  const std::set<std::uint8_t> defined = {
    ConsoleState::PHASE_NONE, ConsoleState::PHASE_VALIDATING, ConsoleState::PHASE_RUNNING};
  while (defined.count(undefined) == 1) {
    ++undefined;
  }
  ValidateThenRun::Result unknown;
  unknown.ended_in = undefined;
  const std::string line = validate_then_run_outcome(unknown);
  EXPECT_NE(line.find("Unrecognised phase"), std::string::npos) << line;
  // Never the words ADR-0073 decision 5 forbids.
  for (const std::string & text : {none, line}) {
    for (const char * word : {"safe", "verified", "validated"}) {
      EXPECT_EQ(text.find(word), std::string::npos) << text;
    }
  }
}
