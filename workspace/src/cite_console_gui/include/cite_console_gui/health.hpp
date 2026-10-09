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

// What the panel shows of each side's connection: live, stale or absent - as
// one pure function of what it has heard on its own domain, with no Qt, no ROS
// and no clock in it.
//
// A MONITORING DISPLAY, NEVER A SAFETY FUNCTION. Nothing here gates a request
// or stops a motion: the physical side's deadman does that, on that side's
// domain (ADR-0070 item 5), and the twin boundary decides every transition at
// the transition. A side the panel shows as live can stop being commandable
// before the next thing the panel hears.
//
// WHAT THE PANEL CAN READ, AND WHAT IT CANNOT. The panel holds one ROS context,
// on the plant's domain (ADR-0044's L7 clause). On that domain it reads:
//   - the twin boundary's `TwinHeartbeat`, which the boundary publishes onto
//     EACH side's own domain from that side's executor: the plant's copy says
//     the boundary process is up and its plant-side executor is turning. Its
//     arrival is timed on the panel's own steady clock (TwinHeartbeat.msg:
//     "what a receiver may conclude from it is ARRIVAL, never age").
//   - `TwinSides`, latched and published on change: which sides run, which are
//     physical, which the boundary judges commandable and stationary, and why
//     not (`detail`).
// The counterpart's own heartbeat is on the counterpart's domain, which the
// panel does not open; how fresh that side is, is the boundary's `commandable`
// verdict, which carries no age of its own.

#ifndef CITE_CONSOLE_GUI__HEALTH_HPP_
#define CITE_CONSOLE_GUI__HEALTH_HPP_

#include <set>
#include <string>

namespace cite_console_gui
{

/// What the panel shows of one connection.
enum class Link
{
  /// Heard, recently, and (for a side) judged commandable by the boundary.
  LIVE,
  /// Heard before but late, or running and not commandable: what was last
  /// said may no longer hold.
  STALE,
  /// Not heard at all: no boundary, no TwinSides, or a side not started.
  ABSENT,
};

/// TwinSides as the panel last heard it.
struct SidesView
{
  /// A TwinSides has been heard from a publisher that is still there.
  bool heard{false};
  std::set<std::string> running;
  std::set<std::string> physical;
  std::set<std::string> commandable;
  std::set<std::string> stationary;
  std::string detail;
};

/// The boundary's heartbeat on the panel's domain, as the panel heard it.
struct HeartbeatView
{
  /// A heartbeat publisher is matched with the panel's subscription.
  bool publisher_present{false};
  /// At least one heartbeat arrived since it matched.
  bool heard{false};
  /// Seconds since the last one arrived, on the panel's steady clock.
  double age_s{0.0};
};

/// The boundary's own link: ABSENT with no publisher or none heard yet, STALE
/// once the last heartbeat is older than `stale_after_s`, LIVE otherwise.
Link boundary_link(const HeartbeatView & heartbeat, double stale_after_s);

/// One side, as the panel shows it.
struct SideHealth
{
  Link link{Link::ABSENT};
  /// TwinSides lists the side as physical.
  bool physical{false};
  /// TwinSides lists the side as stationary (meaningful for a physical side).
  bool stationary{false};
  /// Why the side is not LIVE, as the operator reads it; empty when it is.
  std::string why;
};

/// The side named `side` (by the plan's side names, which TwinSides uses):
/// ABSENT while the boundary is absent, TwinSides is unheard or the side is not
/// running; STALE while the boundary's heartbeat is late (what it last said may
/// be old) or the boundary does not judge the side commandable (with
/// TwinSides' `detail` as the reason); LIVE otherwise.
SideHealth side_health(const std::string & side, const SidesView & sides, Link boundary);

/// Whether a physical side may be being commanded: the pair has a physical
/// side and the twin's mode is not known to be SIM (ADR-0072 decision 2: in SIM
/// nothing reaches the physical side). An unknown mode counts: the panel
/// cannot show that nothing reaches it. For the panel's colour, nothing else.
bool physical_side_commanded(bool has_physical_side, bool mode_heard, bool mode_is_sim);

/// The link as the operator reads it: "live", "stale", "absent".
const char * link_name(Link link);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__HEALTH_HPP_
