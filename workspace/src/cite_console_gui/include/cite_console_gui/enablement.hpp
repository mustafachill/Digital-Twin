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

// Which of the panel's buttons may be pressed, as one pure function of what the
// console last said and the target the operator selected (ADR-0071 decision 5,
// ADR-0072 decision 3).
//
// The panel holds no logic: `cell_console` enforces every refusal itself, and a
// button the panel enables that the console refuses costs a refusal message,
// nothing more. What is decided here is only what the panel MIRRORS, and it is
// decided once, in this file, so that the table can be tested for what it is
// without a window, a QML engine or a ROS graph. Nothing here knows a message
// type: `console_view.hpp` turns the contract's constants into a `ConsoleView`,
// so no constant is restated here.

#ifndef CITE_CONSOLE_GUI__ENABLEMENT_HPP_
#define CITE_CONSOLE_GUI__ENABLEMENT_HPP_

#include <array>
#include <cstdint>
#include <set>
#include <vector>

namespace cite_console_gui
{

/// ConsoleState.state, as the panel reads it. `UNKNOWN` is a value the panel
/// does not recognise: a newer console than this panel. Nothing is enabled for
/// it but Stop while a request is in progress.
enum class Phase
{
  UNKNOWN,
  NOT_STARTED,
  STARTING,
  READY,
  HOMING,
  AWAITING_OPERATOR,
  RUNNING,
  STOPPING,
  FAULT,
};

/// Every phase, for whoever has to walk them all.
constexpr std::array<Phase, 9> ALL_PHASES = {
  Phase::UNKNOWN, Phase::NOT_STARTED, Phase::STARTING, Phase::READY, Phase::HOMING,
  Phase::AWAITING_OPERATOR, Phase::RUNNING, Phase::STOPPING, Phase::FAULT,
};

/// Where the operator sends the signal (ADR-0072): ConsoleState.TARGET_*, as the
/// panel reads it. `NONE` is no selection - the panel never defaults one when
/// more than one is available - and also a value the panel does not recognise.
enum class Target
{
  NONE,
  SIM,
  REAL,
  TWIN,
};

/// Every target the operator can choose, in the order the panel offers them.
///
/// The panel does NOT know which sides a target commands (review R-02): the
/// console derives every fact that depends on it from its one target table and
/// publishes it (`startable_targets`, `floored_targets`, `counterpart_running`).
constexpr std::array<Target, 3> ALL_TARGETS = {Target::SIM, Target::REAL, Target::TWIN};

/// The phase of a validate-then-run request (ADR-0073): ConsoleState.PHASE_*,
/// and the ValidateThenRun feedback's and result's `phase` / `ended_in`, as
/// the panel reads them. `UNKNOWN` is a value the contract this panel was
/// built against does not define.
enum class ValidationPhase
{
  NONE,
  VALIDATING,
  RUNNING,
  UNKNOWN,
};

/// What the panel knows, reduced to what the buttons depend on.
struct ConsoleView
{
  /// A ConsoleState has been heard from a console that is still there. False
  /// before the first one and after its publisher has gone: the panel then
  /// disables every button and says "No console".
  bool heard{false};
  Phase phase{Phase::UNKNOWN};
  bool robot_started{false};
  bool busy{false};
  /// ConsoleState.plant_at_start / counterpart_at_start: each side's arm at
  /// the program's start, as the console knows it (ADR-0072 decision 3).
  /// Shown, never decided on: `startable_targets` is the console's verdict.
  bool plant_at_start{false};
  bool counterpart_at_start{false};
  /// ConsoleState.counterpart_running: the pair runs the counterpart's side,
  /// so its start status describes a side that exists.
  bool counterpart_running{false};
  /// ConsoleState.available_targets, as targets this panel recognises. Only
  /// these may be chosen, and a goal naming any other is refused.
  std::set<Target> available_targets;
  /// ConsoleState.available_targets exactly as received, values this panel
  /// does not recognise included. Only `available_targets` is offered, but the
  /// selection is settled against this: a change to the served set the panel
  /// cannot read is still a change (R-18).
  std::set<std::uint8_t> served_values;
  /// ConsoleState.startable_targets, as targets this panel recognises: every
  /// side of each is at the program's start, so Start program may be sent.
  std::set<Target> startable_targets;
  /// ConsoleState.floored_targets, as targets this panel recognises: those a
  /// physical side is commanded by, to which `minimum_speed_scale` applies.
  std::set<Target> floored_targets;
  /// An opaque identity of the publisher that said it (its rmw GID); empty
  /// when unknown. A different publisher is a console that came back, even if
  /// its predecessor's unmatch was never seen.
  std::vector<std::uint8_t> publisher;
  /// ConsoleState.minimum_speed_scale: the floor of a target in `floored_targets`.
  double minimum_speed_scale{0.0};
  /// ConsoleState.twin_mode is MODE_SIM. Unknown counts as not SIM.
  bool twin_in_sim{false};
  /// ConsoleState.physical_sides is not empty. Only then does Stop in FAULT
  /// ask the twin for SIM again; on an all-simulated pair the console refuses
  /// that Stop (StopCell.srv), so the panel does not offer it.
  bool has_physical_side{false};
  /// ConsoleState.validate_then_run_offered: the console accepts
  /// ValidateThenRun on this deployment (ADR-0073 decision 6). The console's
  /// verdict; the panel does not restate the rule behind it.
  bool validate_then_run_offered{false};
  /// ConsoleState.phase: the phase of the validate-then-run request in
  /// progress, NONE for any other request or none. Shown, never decided on.
  ValidationPhase validation_phase{ValidationPhase::NONE};
};

struct ButtonStates
{
  bool start_robot{false};
  bool home{false};
  bool start_program{false};
  bool stop{false};
  /// The operator's go-ahead: shown only while the console asks for it.
  bool confirm{false};
  /// "Validate in simulation, then run twin" (ADR-0073).
  bool validate_then_run{false};

  bool operator==(const ButtonStates & other) const
  {
    return start_robot == other.start_robot && home == other.home &&
           start_program == other.start_program && stop == other.stop &&
           confirm == other.confirm && validate_then_run == other.validate_then_run;
  }
};

/// The one enablement rule, for the target the operator selected (`NONE` if
/// none is).
///
/// - Start robot: NOT_STARTED, READY or FAULT, and nothing in progress.
/// - Home: started, READY, nothing in progress, and the selected target is one
///   the console serves.
/// - Start program: as Home, and the console says the selected target is
///   startable - every side of it at the program's start (ADR-0072 decision 3).
/// - Stop: a request is in progress; or FAULT while the twin is not in SIM on
///   a pair with a physical side, where Stop asks the twin for SIM again
///   (StopCell.srv).
/// - Confirm: AWAITING_OPERATOR.
/// - Validate then run: started, READY, nothing in progress, the console offers
///   it (`validate_then_run_offered`) and says the twin is startable (both arms
///   at the program's start; ValidateThenRun.action). It carries no target, so
///   the operator's selection does not touch it.
///
/// Nothing at all before a ConsoleState is heard.
ButtonStates enabled_for(const ConsoleView & view, Target selected);

/// Whether the operator may choose `target`: a console is heard and serves it.
bool target_choice_enabled(const ConsoleView & view, Target target);

/// The selection the panel holds once `now` is heard, given the view it
/// replaces (`before`) and the operator's `selected` target.
///
/// The panel NEVER selects a target itself, not even the only one offered
/// (ADR-0072 decision 3; safety audit R-18): the operator always picks. A
/// selection stays only while a console is heard, the same publisher said
/// both views, the set of targets it serves (as received, unrecognised values
/// included) is unchanged from `before`, and it serves the selection. Anything
/// else - no console, a console that came back (a different publisher), a set
/// of targets that changed in any way - clears it, and Home and Start program
/// stay disabled until the operator picks again. Selecting is
/// `settled_selection(view, view, target)`.
Target settled_selection(const ConsoleView & before, const ConsoleView & now, Target selected);

/// Whether the console says the pair runs the counterpart's side. The panel
/// shows a side's start status only for a side that runs.
bool counterpart_running(const ConsoleView & view);

/// The scales the panel offers, the program's own speed first and preselected.
constexpr std::array<double, 4> SPEED_CHOICES = {1.0, 0.5, 0.25, 0.1};

/// Whether a goal at `scale` toward `target` is one the console accepts: a
/// console is heard, the scale is in (0, 1], and, for a target the console
/// lists in `floored_targets`, not below ConsoleState.minimum_speed_scale
/// (ADR-0071 decision 2, ADR-0072 decision 3). With no target selected the
/// floor is applied: the panel offers nothing it might have to take back.
bool speed_choice_enabled(double scale, const ConsoleView & view, Target target);

/// Whether the real arm's floor (ConsoleState.minimum_speed_scale) applies to a
/// goal toward `target`: a console is heard, it states a floor, and the target
/// is one it floors - or none is selected, when the floor is assumed. What the
/// panel shows beside the speed choices, and what `speed_choice_enabled` applies.
bool floor_applies(const ConsoleView & view, Target target);

/// The target as the operator reads it.
const char * target_name(Target target);

/// The validate-then-run phase as the operator reads it: "Validating in
/// simulation", "Running twin", an empty string for NONE. Never "validated",
/// "verified" or "safe" (ADR-0073 decision 5).
const char * validation_phase_name(ValidationPhase phase);

/// The phase as the operator reads it, which is the constant's own name.
const char * phase_name(Phase phase);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__ENABLEMENT_HPP_
