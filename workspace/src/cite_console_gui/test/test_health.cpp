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

// What the panel shows of each side's connection (health.hpp), as tables of
// independent rows: each one situation an operator would name, and what the
// panel shows in it. A display only - nothing here is a gate.

#include <gtest/gtest.h>

#include <set>
#include <string>
#include <vector>

#include "cite_console_gui/health.hpp"

using cite_console_gui::boundary_link;
using cite_console_gui::BoundaryState;
using cite_console_gui::HeartbeatView;
using cite_console_gui::Link;
using cite_console_gui::link_abnormal;
using cite_console_gui::link_name;
using cite_console_gui::physical_side_commanded;
using cite_console_gui::side_health;
using cite_console_gui::SidesView;

namespace
{

constexpr double STALE_AFTER_S = 0.5;

struct BoundaryRow
{
  const char * situation;
  HeartbeatView heartbeat;
  Link expected;
};

const std::vector<BoundaryRow> BOUNDARY_ROWS = {
  {"no heartbeat publisher on the domain", {false, false, 0.0}, Link::ABSENT},
  {"a publisher matched, nothing heard yet", {true, false, 0.0}, Link::ABSENT},
  {"a heartbeat just arrived", {true, true, 0.0}, Link::LIVE},
  {"the last one is just inside the threshold", {true, true, 0.5}, Link::LIVE},
  {"the last one is past the threshold", {true, true, 0.51}, Link::STALE},
  {"heard long ago, publisher still matched", {true, true, 60.0}, Link::STALE},
  {"heard, then its publisher left", {false, true, 0.0}, Link::ABSENT},
};

/// Both sides running, the counterpart physical, both commandable.
SidesView both_live()
{
  SidesView sides;
  sides.heard = true;
  sides.running = {"plant", "counterpart"};
  sides.physical = {"counterpart"};
  sides.commandable = {"plant", "counterpart"};
  sides.stationary = {"counterpart"};
  return sides;
}

struct SideRow
{
  const char * situation;
  std::string side;
  SidesView sides;
  Link boundary;
  /// TwinSides listed the side as running at some point before.
  bool was_running;
  Link expected;
  /// A fragment the reason must contain; empty: the reason must be empty.
  std::string why;
};

std::vector<SideRow> side_rows()
{
  SidesView unheard;
  SidesView plant_only = both_live();
  plant_only.running = {"plant"};
  plant_only.physical = {};
  plant_only.commandable = {"plant"};
  plant_only.stationary = {};
  SidesView not_commandable = both_live();
  not_commandable.commandable = {"plant"};
  not_commandable.detail = "counterpart: deadman TRIPPED";
  SidesView not_commandable_silent = not_commandable;
  not_commandable_silent.detail = "";

  return {
    {"both sides live", "plant", both_live(), Link::LIVE, true, Link::LIVE, ""},
    {"the physical side live", "counterpart", both_live(), Link::LIVE, true, Link::LIVE, ""},
    {"no boundary at all", "plant", both_live(), Link::ABSENT, false, Link::ABSENT, "heartbeat"},
    {"no TwinSides heard", "counterpart", unheard, Link::LIVE, false, Link::ABSENT,
      "TwinSides"},
    // R-04: a side this deployment never started is normal, not absent.
    {"a plant-only deployment's counterpart", "counterpart", plant_only, Link::LIVE, false,
      Link::NOT_STARTED, "Not started"},
    {"a plant-only deployment's plant", "plant", plant_only, Link::LIVE, true, Link::LIVE, ""},
    {"a side that ran and is no longer listed", "counterpart", plant_only, Link::LIVE, true,
      Link::ABSENT, "no longer lists"},
    {"the boundary's heartbeat is late", "plant", both_live(), Link::STALE, true, Link::STALE,
      "late"},
    {"late heartbeat, side never started", "counterpart", plant_only, Link::STALE, false,
      Link::NOT_STARTED, "Not started"},
    {"late heartbeat, side ran and has gone", "counterpart", plant_only, Link::STALE, true,
      Link::ABSENT, "no longer lists"},
    // R-03: connected and on time, but not commandable, is readiness.
    {"running, not commandable: the boundary's reason", "counterpart", not_commandable,
      Link::LIVE, true, Link::NOT_READY, "deadman TRIPPED"},
    {"running, not commandable, no reason given", "counterpart", not_commandable_silent,
      Link::LIVE, true, Link::NOT_READY, "does not judge"},
    {"late heartbeat beats not ready", "counterpart", not_commandable, Link::STALE, true,
      Link::STALE, "late"},
    {"the other side is unaffected", "plant", not_commandable, Link::LIVE, true, Link::LIVE,
      ""},
    {"a side name nobody runs", "elsewhere", both_live(), Link::LIVE, false,
      Link::NOT_STARTED, "Not started"},
  };
}

}  // namespace

TEST(Health, TheBoundaryLinkFollowsItsTable)
{
  for (const BoundaryRow & row : BOUNDARY_ROWS) {
    EXPECT_EQ(boundary_link(row.heartbeat, STALE_AFTER_S), row.expected) << row.situation;
  }
}

TEST(Health, EachSideFollowsItsTable)
{
  for (const SideRow & row : side_rows()) {
    const auto health = side_health(row.side, row.sides, row.boundary, row.was_running);
    EXPECT_EQ(health.link, row.expected) << row.situation;
    if (row.why.empty()) {
      EXPECT_EQ(health.why, "") << row.situation;
    } else {
      EXPECT_NE(health.why.find(row.why), std::string::npos)
        << row.situation << ": '" << health.why << "'";
    }
  }
}

TEST(Health, ASideIsLiveOnlyWithALiveBoundaryRunningAndCommandable)
{
  // Over every boundary link, every membership: LIVE requires all three.
  const std::vector<Link> links = {Link::LIVE, Link::STALE, Link::ABSENT};
  for (const Link boundary : links) {
    for (int bits = 0; bits < 16; ++bits) {
      SidesView sides;
      sides.heard = bits & 1;
      if (bits & 2) {
        sides.running.insert("s");
      }
      if (bits & 4) {
        sides.commandable.insert("s");
      }
      if (bits & 8) {
        sides.physical.insert("s");
      }
      const auto health = side_health("s", sides, boundary, true);
      const bool live = boundary == Link::LIVE && sides.heard && (bits & 2) && (bits & 4);
      EXPECT_EQ(health.link == Link::LIVE, live) << link_name(boundary) << " bits " << bits;
      EXPECT_EQ(health.why.empty(), live) << link_name(boundary) << " bits " << bits;
      EXPECT_EQ(health.physical, sides.heard && (bits & 8)) << bits;
    }
  }
}

TEST(Health, PhysicalAndStationaryAreReadOffTwinSides)
{
  const auto counterpart = side_health("counterpart", both_live(), Link::LIVE, true);
  EXPECT_TRUE(counterpart.physical);
  EXPECT_TRUE(counterpart.stationary);
  const auto plant = side_health("plant", both_live(), Link::LIVE, true);
  EXPECT_FALSE(plant.physical);
  EXPECT_FALSE(plant.stationary);
}

TEST(Health, APhysicalSideIsCommandedUnlessTheModeIsKnownToBeSim)
{
  struct Row
  {
    const char * situation;
    bool physical;
    bool heard;
    bool sim;
    bool expected;
  };
  const std::vector<Row> rows = {
    {"all simulated, mode unknown", false, false, false, false},
    {"all simulated, not SIM", false, true, false, false},
    {"physical side, SIM", true, true, true, false},
    {"physical side, another mode", true, true, false, true},
    {"physical side, mode unknown", true, false, false, true},
    {"physical side, unheard but 'sim' stale flag", true, false, true, true},
  };
  for (const Row & row : rows) {
    EXPECT_EQ(physical_side_commanded(row.physical, row.heard, row.sim), row.expected)
      << row.situation;
  }
}

TEST(Health, EveryLinkHasADistinctName)
{
  const std::set<std::string> names = {
    link_name(Link::LIVE), link_name(Link::STALE), link_name(Link::ABSENT),
    link_name(Link::NOT_READY), link_name(Link::NOT_STARTED)};
  EXPECT_EQ(names.size(), 5u);
}

TEST(Health, OnlyLiveAndNotStartedAreNormal)
{
  // R-04: a side the deployment never started is grey; R-03: not ready is
  // still abnormal, like stale and absent.
  EXPECT_FALSE(link_abnormal(Link::LIVE));
  EXPECT_FALSE(link_abnormal(Link::NOT_STARTED));
  EXPECT_TRUE(link_abnormal(Link::STALE));
  EXPECT_TRUE(link_abnormal(Link::ABSENT));
  EXPECT_TRUE(link_abnormal(Link::NOT_READY));
}

namespace
{

/// TwinSides of a deployment running `running`, every one commandable.
SidesView running(const std::set<std::string> & sides)
{
  SidesView view;
  view.heard = true;
  view.running = sides;
  view.commandable = sides;
  return view;
}

}  // namespace

TEST(BoundaryState, TheModeOutlivesTheConsoleLeavingAndComingBack)
{
  // R-02: TwinMode is latched and published on change, so a mode cleared when
  // the console leaves is never heard again while the boundary stays up.
  BoundaryState state;
  EXPECT_EQ(state.twin_mode_name(), "unknown");
  EXPECT_FALSE(state.twin_mode_heard());
  state.twin_mode_heard("SIM", true);
  state.console_lost();
  EXPECT_EQ(state.twin_mode_name(), "SIM");
  EXPECT_TRUE(state.twin_mode_heard());
  EXPECT_TRUE(state.twin_mode_is_sim());
  // And the physical side is not shown as commanded because of it.
  EXPECT_FALSE(
    physical_side_commanded(true, state.twin_mode_heard(), state.twin_mode_is_sim()));
}

TEST(BoundaryState, TheModeIsUnknownOnceTwinModesPublisherLeaves)
{
  BoundaryState state;
  state.twin_mode_heard("SIM", true);
  state.twin_mode_lost();
  EXPECT_EQ(state.twin_mode_name(), "unknown");
  EXPECT_FALSE(state.twin_mode_heard());
  EXPECT_FALSE(state.twin_mode_is_sim());
  EXPECT_TRUE(
    physical_side_commanded(true, state.twin_mode_heard(), state.twin_mode_is_sim()));
  // Heard again: shown again.
  state.twin_mode_heard("REAL", false);
  EXPECT_EQ(state.twin_mode_name(), "REAL");
  EXPECT_FALSE(state.twin_mode_is_sim());
}

TEST(BoundaryState, TheSidesOutliveTheConsoleAndGoWithTheirPublisher)
{
  BoundaryState state;
  state.sides_heard(running({"plant", "counterpart"}));
  state.console_lost();
  EXPECT_EQ(state.side("counterpart", Link::LIVE).link, Link::LIVE);
  state.sides_lost();
  EXPECT_FALSE(state.sides().heard);
  EXPECT_EQ(state.side("counterpart", Link::LIVE).link, Link::ABSENT);
}

TEST(BoundaryState, ASideNeverStartedIsNotStartedAndOneThatLeftIsAbsent)
{
  // R-04: a plant-only deployment's counterpart is grey "not started" from the
  // start; a side that ran and is then dropped from `running` is "absent".
  BoundaryState plant_only;
  plant_only.sides_heard(running({"plant"}));
  EXPECT_EQ(plant_only.side("counterpart", Link::LIVE).link, Link::NOT_STARTED);
  EXPECT_FALSE(link_abnormal(plant_only.side("counterpart", Link::LIVE).link));

  BoundaryState pair;
  pair.sides_heard(running({"plant", "counterpart"}));
  pair.sides_heard(running({"plant"}));
  EXPECT_EQ(pair.side("counterpart", Link::LIVE).link, Link::ABSENT);
  EXPECT_TRUE(link_abnormal(pair.side("counterpart", Link::LIVE).link));
  // Remembered across the boundary's own restart.
  pair.sides_lost();
  pair.sides_heard(running({"plant"}));
  EXPECT_EQ(pair.side("counterpart", Link::LIVE).link, Link::ABSENT);
  // And back: live again.
  pair.sides_heard(running({"plant", "counterpart"}));
  EXPECT_EQ(pair.side("counterpart", Link::LIVE).link, Link::LIVE);
}
