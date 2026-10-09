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

#include "cite_console_gui/health.hpp"

#include <string>

namespace cite_console_gui
{

Link boundary_link(const HeartbeatView & heartbeat, double stale_after_s)
{
  if (!heartbeat.publisher_present || !heartbeat.heard) {
    return Link::ABSENT;
  }
  return heartbeat.age_s > stale_after_s ? Link::STALE : Link::LIVE;
}

SideHealth side_health(
  const std::string & side, const SidesView & sides, Link boundary, bool was_running)
{
  SideHealth health;
  health.physical = sides.heard && sides.physical.count(side) == 1;
  health.stationary = sides.heard && sides.stationary.count(side) == 1;
  if (boundary == Link::ABSENT) {
    health.why = "No twin boundary heartbeat is heard on this domain.";
    return health;
  }
  if (!sides.heard) {
    health.why = "The twin boundary has published no TwinSides.";
    return health;
  }
  if (sides.running.count(side) == 0) {
    if (was_running) {
      health.why = "Was running; the twin boundary no longer lists it as running.";
      return health;
    }
    health.link = Link::NOT_STARTED;
    health.why = "Not started in this deployment.";
    return health;
  }
  if (boundary == Link::STALE) {
    health.link = Link::STALE;
    health.why = "The twin boundary's heartbeat is late; what it last said may be old.";
    return health;
  }
  if (sides.commandable.count(side) == 0) {
    health.link = Link::NOT_READY;
    health.why = sides.detail.empty() ?
      "The twin boundary does not judge this side commandable." : sides.detail;
    return health;
  }
  health.link = Link::LIVE;
  return health;
}

bool link_abnormal(Link link)
{
  return link != Link::LIVE && link != Link::NOT_STARTED;
}

void BoundaryState::twin_mode_heard(const std::string & name, bool is_sim)
{
  mode_name_ = name;
  mode_heard_ = true;
  mode_is_sim_ = is_sim;
}

void BoundaryState::twin_mode_lost()
{
  mode_name_ = "unknown";
  mode_heard_ = false;
  mode_is_sim_ = false;
}

void BoundaryState::sides_heard(const SidesView & sides)
{
  sides_ = sides;
  ever_running_.insert(sides.running.begin(), sides.running.end());
}

void BoundaryState::sides_lost()
{
  sides_ = SidesView{};
}

SideHealth BoundaryState::side(const std::string & side, Link boundary) const
{
  return side_health(side, sides_, boundary, ever_running_.count(side) == 1);
}

bool physical_side_commanded(bool has_physical_side, bool mode_heard, bool mode_is_sim)
{
  return has_physical_side && !(mode_heard && mode_is_sim);
}

const char * link_name(Link link)
{
  switch (link) {
    case Link::LIVE:
      return "live";
    case Link::STALE:
      return "stale";
    case Link::NOT_READY:
      return "not ready";
    case Link::NOT_STARTED:
      return "not started";
    case Link::ABSENT:
      break;
  }
  return "absent";
}

}  // namespace cite_console_gui
