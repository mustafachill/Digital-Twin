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

// What the panel shows of each side's connection: live, stale, absent, not
// ready or not started - as one pure function of what it has heard on its own
// domain, and the twin boundary's latched state as one holder (`BoundaryState`),
// with no Qt, no ROS and no clock in either.
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

/// What the panel shows of one connection. Freshness (LIVE, STALE, ABSENT)
/// and readiness (NOT_READY) are different things: a side the boundary hears
/// on time but does not judge commandable is NOT_READY, never STALE.
enum class Link
{
  /// Heard, recently, and (for a side) judged commandable by the boundary.
  LIVE,
  /// Heard before but late: what was last said may no longer hold.
  STALE,
  /// Not heard at all: no boundary, no TwinSides, or a side that was running
  /// and that TwinSides no longer lists as running.
  ABSENT,
  /// A side running, the boundary on time, but not judged commandable
  /// (TwinSides' `detail` says why): connected, not ready.
  NOT_READY,
  /// A side TwinSides has never listed as running since the panel started: not
  /// part of this deployment (a plant-only run's counterpart). Normal.
  NOT_STARTED,
};

/// Whether `link` is abnormal, for the panel's colour (ISA-101: colour only
/// for the abnormal): everything but LIVE and NOT_STARTED.
bool link_abnormal(Link link);

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
/// ABSENT while the boundary is absent or TwinSides is unheard; when TwinSides
/// does not list the side as running, ABSENT if it `was_running` (it was
/// listed before and has gone) and NOT_STARTED if it never was; STALE while the
/// boundary's heartbeat is late (what it last said may be old); NOT_READY while
/// the boundary does not judge the side commandable (with TwinSides' `detail`
/// as the reason); LIVE otherwise.
SideHealth side_health(
  const std::string & side, const SidesView & sides, Link boundary, bool was_running);

/// What the panel has heard of the twin boundary's latched state - its mode
/// and its sides - and what it remembers of it, with no Qt, no ROS and no clock.
///
/// EACH THING IS FORGOTTEN ONLY WHEN ITS OWN PUBLISHER LEAVES. TwinMode and
/// TwinSides are the boundary's latched, published-on-change topics: a value
/// cleared for any other reason is never delivered again while the boundary
/// stays up, and the panel would show "unknown" beside a twin that is in SIM.
/// So the console leaving (`console_lost`) clears nothing here; the mode is
/// cleared when TwinMode's publisher unmatches (`twin_mode_lost`), and the
/// sides when TwinSides' does (`sides_lost`).
class BoundaryState
{
public:
  /// A TwinMode was heard: `name` as the operator reads it, `is_sim` when the
  /// twin is in SIM and not on its way out of it.
  void twin_mode_heard(const std::string & name, bool is_sim);
  /// TwinMode's publisher left the graph: the mode is unknown again.
  void twin_mode_lost();
  /// TwinSides was heard. Every side it lists as running is remembered as
  /// having run, for as long as the panel lives.
  void sides_heard(const SidesView & sides);
  /// TwinSides' publisher left the graph: the sides are unheard again. What
  /// ran is still remembered.
  void sides_lost();
  /// The console's state publisher left the graph. Nothing here is the
  /// console's, so nothing is cleared (R-02).
  void console_lost() {}

  /// The mode's name, or "unknown" while none is heard.
  const std::string & twin_mode_name() const {return mode_name_;}
  bool twin_mode_heard() const {return mode_heard_;}
  bool twin_mode_is_sim() const {return mode_heard_ && mode_is_sim_;}
  const SidesView & sides() const {return sides_;}
  /// `side_health` of `side`, with what this holder remembers of it.
  SideHealth side(const std::string & side, Link boundary) const;

private:
  std::string mode_name_{"unknown"};
  bool mode_heard_{false};
  bool mode_is_sim_{false};
  SidesView sides_;
  std::set<std::string> ever_running_;
};

/// Whether a physical side may be being commanded: the pair has a physical
/// side and the twin's mode is not known to be SIM (ADR-0072 decision 2: in SIM
/// nothing reaches the physical side). An unknown mode counts: the panel
/// cannot show that nothing reaches it. For the panel's colour, nothing else.
bool physical_side_commanded(bool has_physical_side, bool mode_heard, bool mode_is_sim);

/// The link as the operator reads it: "live", "stale", "absent", "not ready",
/// "not started".
const char * link_name(Link link);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__HEALTH_HPP_
