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

#include "cite_console_gui/event_log.hpp"

#include <algorithm>
#include <string>

namespace cite_console_gui
{

EventLog::EventLog(std::size_t capacity)
: capacity_(std::max<std::size_t>(capacity, 1))
{
}

bool EventLog::record(
  const std::string & time, const std::string & state, const std::string & step,
  const std::string & last_error)
{
  if (has_transition_ && last_transition_.state == state && last_transition_.step == step &&
    last_transition_.last_error == last_error)
  {
    return false;
  }
  last_transition_ = EventEntry{time, state, step, last_error};
  has_transition_ = true;
  push(last_transition_);
  return true;
}

void EventLog::note(const std::string & time, const std::string & state, const std::string & detail)
{
  push(EventEntry{time, state, detail, ""});
}

void EventLog::push(const EventEntry & entry)
{
  entries_.push_front(entry);
  while (entries_.size() > capacity_) {
    entries_.pop_back();
  }
}

}  // namespace cite_console_gui
