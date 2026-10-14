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

// The frame's event log (ADR-0074): the last transitions of the console's
// state, kept on the panel's side for display only, with no Qt and no ROS.
//
// A TRANSITION is a ConsoleState whose state, step or last error differs from
// the last one recorded; a re-publication of the same state is not one. The
// log forgets nothing on its own but its oldest entry once it is full: what the
// console said is history, and a console that leaves is recorded as one more
// transition ("No console") rather than by clearing what it said before. It is
// not a record of the cell (that is L6's, not built), and nothing reads it but
// the panel's display.

#ifndef CITE_CONSOLE_GUI__EVENT_LOG_HPP_
#define CITE_CONSOLE_GUI__EVENT_LOG_HPP_

#include <cstddef>
#include <deque>
#include <string>

namespace cite_console_gui
{

/// How many transitions the frame keeps.
constexpr std::size_t EVENT_LOG_CAPACITY = 50;

/// One transition, as the console said it.
struct EventEntry
{
  /// When the panel heard it, as the caller wrote it (wall clock, for display).
  std::string time;
  std::string state;
  std::string step;
  std::string last_error;
};

class EventLog
{
public:
  explicit EventLog(std::size_t capacity = EVENT_LOG_CAPACITY);

  /// Record what the console says now, heard at `time`. Returns whether it
  /// was a transition and was recorded; the same state, step and last error as
  /// the newest entry are not recorded again.
  bool record(
    const std::string & time, const std::string & state, const std::string & step,
    const std::string & last_error);

  /// Newest first; at most `capacity` of them.
  const std::deque<EventEntry> & entries() const {return entries_;}

  std::size_t capacity() const {return capacity_;}

private:
  std::size_t capacity_;
  std::deque<EventEntry> entries_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__EVENT_LOG_HPP_
