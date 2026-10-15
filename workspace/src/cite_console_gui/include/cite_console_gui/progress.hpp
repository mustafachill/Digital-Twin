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

// How far a running request has got, for the frame's progress ring (ADR-0074),
// as a pure function with no Qt and no ROS. Display only: it is read off the
// action's feedback and gates nothing.

#ifndef CITE_CONSOLE_GUI__PROGRESS_HPP_
#define CITE_CONSOLE_GUI__PROGRESS_HPP_

#include <cstdint>
#include <string>

namespace cite_console_gui
{

/// A RunProgram or ValidateThenRun request's position, from its feedback.
struct RunProgress
{
  /// A request is running and has reported.
  bool active{false};
  /// The request ("Start program", "Validate then run") sent, or accepted,
  /// that has not reported yet; empty once it has, and when none is sent.
  std::string starting;
  /// The phase as the operator reads it ("Validating in simulation", "Running
  /// twin"); empty for Start program.
  std::string phase;
  /// 1-based cycle in progress, of `cycles` in this phase; 0 before any step.
  std::uint32_t cycle{0};
  std::uint32_t cycles{0};
  /// 1-based step in progress, of `step_count` in one cycle; 0 before any.
  std::uint32_t step_index{0};
  std::uint32_t step_count{0};
};

/// The share of the phase's steps reached, in [0, 1]: 0 when nothing is known,
/// before any step, or for counts that do not describe a run.
double progress_fraction(const RunProgress & progress);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__PROGRESS_HPP_
