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
  if (!entries_.empty()) {
    const EventEntry & newest = entries_.front();
    if (newest.state == state && newest.step == step && newest.last_error == last_error) {
      return false;
    }
  }
  entries_.push_front(EventEntry{time, state, step, last_error});
  while (entries_.size() > capacity_) {
    entries_.pop_back();
  }
  return true;
}

}  // namespace cite_console_gui
