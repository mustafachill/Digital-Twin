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

// The contract's constants, turned into the panel's view - in one place.
//
// Every value compared here is a constant from the generated message headers
// (ConsoleState, TwinMode); none is written as a number. A state this panel
// does not recognise becomes `Phase::UNKNOWN`, and a target it does not
// recognise is not offered, rather than a guess.

#ifndef CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_
#define CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_

#include <cstdint>
#include <string>
#include <vector>

#include "cite_console_gui/enablement.hpp"
#include "cite_console_gui/fidelity.hpp"
#include "cite_interfaces/action/run_program.hpp"
#include "cite_interfaces/action/validate_then_run.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/divergence_metrics.hpp"

namespace cite_console_gui
{

/// ConsoleState.state as a phase; `UNKNOWN` for a value the contract this
/// panel was built against does not define.
Phase phase_from(std::uint8_t state);

/// ConsoleState.TARGET_* as a target; `NONE` for 0 and for a value the
/// contract this panel was built against does not define.
Target target_from(std::uint8_t value);

/// The ConsoleState.TARGET_* a goal carries for `target`; 0 (unset, which the
/// console rejects) for `NONE`.
std::uint8_t target_value(Target target);

/// ConsoleState.PHASE_* (ConsoleState.phase, and ValidateThenRun's feedback
/// `phase` and result `ended_in`) as a validation phase; `UNKNOWN` for a value
/// the contract this panel was built against does not define.
ValidationPhase validation_phase_from(std::uint8_t value);

/// What the buttons depend on, from a ConsoleState that was just heard from
/// the publisher identified by `publisher` (its rmw GID; empty if unknown).
ConsoleView view_from(
  const cite_interfaces::msg::ConsoleState & state, std::vector<std::uint8_t> publisher = {});

/// The outcome line for a ValidateThenRun result: the console's success and
/// detail, the phase it ended in (`ended_in`), and phase 2's completed cycles.
/// `PHASE_NONE` on a failed result is a request refused before either phase
/// began (ValidateThenRun.action); on a successful one, which the contract does
/// not produce, it is said as no phase rather than as a refusal. A value the
/// contract does not define is said as unrecognised. In the console's words:
/// never "safe", "verified" or "validated for the real cell" (ADR-0073).
/// `after_stop`: as for `outcome_opening`.
std::string validate_then_run_outcome(
  const cite_interfaces::action::ValidateThenRun::Result & result, bool after_stop = false);

/// How a request ended, as its outcome line opens: "<request>: done. ",
/// "<request>: ended after a Stop request. " for one that did not complete
/// and that a Stop the console accepted, or a cancel of its goal, came before
/// the end of (`after_stop`, from `ConsoleClient`), or "<request>: refused or
/// failed. ". Neither of the last two says WHY it ended: the console's result
/// carries no field that tells a stop from a fault (cell_console ends both
/// aborted), so a fault that races a Stop is never relabelled a stop. The
/// console's own detail, which does say, always follows the opening (S-04).
std::string outcome_opening(const std::string & request, bool success, bool after_stop);

/// The console's `detail` as the outcome line after "<request>: done. " (or
/// the other openings) says it: trimmed at its start, without a leading
/// "<request>:" that would repeat the opening ("Home: done. Home: the arm is
/// at the program's start" reads "Home: done. The arm is ..."), and with its
/// first letter a capital, as a sentence's is. For display only: the
/// console's detail is not changed, only the line the panel composes from it.
std::string outcome_detail(const std::string & request, const std::string & detail);

/// The outcome line for a RunProgram result: the opening, the console's
/// detail as a sentence of its own, and - for a request that did not
/// complete - how many cycles did. A completed request's detail already
/// names its cycles (cell_console, "<n> cycle(s) completed"), so the count
/// is not said twice (T-02). `after_stop`: as for `outcome_opening`.
std::string run_program_outcome(
  const cite_interfaces::action::RunProgram::Result & result, bool after_stop = false);

/// `text` as a line of the Robot card shows it (T-03), the same words:
/// every run of whitespace one space, none at either end, and the space
/// between a number and the unit after it ("0.5 m/s", "1.00 / s") a no-break
/// space, so that a line never breaks between them. For display only: what
/// the event log and the outcome's sources hold is unchanged, and the
/// console's prompt is never passed through it (the operator confirms
/// exactly that text).
std::string display_text(const std::string & text);

/// `text` as a sentence of its own: trimmed, and ended with a full stop
/// unless it ends in one, "!" or "?". Empty for blank text.
std::string as_sentence(const std::string & text);

/// The fields of a DivergenceMetrics sample the "Twin fidelity" card reads.
DivergenceSample divergence_sample_from(const cite_interfaces::msg::DivergenceMetrics & sample);

/// A TwinMode.MODE_* value (or ConsoleState.TWIN_MODE_UNKNOWN) by its name.
std::string twin_mode_name(std::uint8_t mode);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CONSOLE_VIEW_HPP_
