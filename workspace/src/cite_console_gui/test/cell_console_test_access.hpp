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

// The panel tests' way into the plugin (test_panel_qml, test_panel_in_gz_gui):
// what it would hold once it had heard a console, the twin boundary and its
// divergence, and what reached it from a press.

#ifndef CELL_CONSOLE_TEST_ACCESS_HPP_
#define CELL_CONSOLE_TEST_ACCESS_HPP_

#include <QTimer>

#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <utility>
#include <vector>

#include "../src/cell_console.hpp"
#include "cite_interfaces/msg/console_state.hpp"

namespace cite_console_gui
{

/// What the plugin would hold once it had heard a console, the twin boundary
/// and its divergence: set through the plugin's own handlers where it has them.
struct CellConsoleTestAccess
{
  static void hear(CellConsole & plugin, const cite_interfaces::msg::ConsoleState & state)
  {
    plugin.apply_state(state, std::vector<std::uint8_t>(16, 7));
  }

  /// A pair whose boundary is heard live, both sides running, and one
  /// divergence sample for `asset`.
  static void hear_boundary(CellConsole & plugin, const std::string & asset)
  {
    plugin.view_config_.twin_sides = {"plant", "counterpart"};
    plugin.view_config_.heartbeat_stale_after_s = 0.5;
    plugin.boundary_.twin_mode_heard("SIM", true);
    SidesView sides;
    sides.heard = true;
    sides.running = {"plant", "counterpart"};
    sides.commandable = {"plant", "counterpart"};
    plugin.boundary_.sides_heard(sides);
    plugin.heartbeat_present_ = true;
    plugin.heartbeat_heard_ = true;
    plugin.last_heartbeat_.restart();
    plugin.refresh_health();
    DivergenceSample sample;
    sample.asset_id = asset;
    sample.valid = false;
    plugin.divergence_[asset] = sample;
    emit plugin.twinModeChanged();
    emit plugin.healthChanged();
    emit plugin.fidelityChanged();
    emit plugin.viewChanged();
  }

  /// World statistics heard, and whether the last is older than allowed.
  static void hear_world_stats(CellConsole & plugin, bool stale)
  {
    plugin.world_stats_heard_ = true;
    plugin.world_stats_.sim_time_s = 657.5;
    plugin.world_stats_.real_time_factor = 1.0;
    plugin.world_stats_stale_ = stale;
    emit plugin.worldStatsChanged();
  }

  /// What the configuration names the followed node.
  static void name_follow(CellConsole & plugin, const std::string & label)
  {
    plugin.view_config_.follow_label = label;
    emit plugin.viewChanged();
  }

  /// The running request's position, as the client would report it.
  static void report_run(CellConsole & plugin, const RunProgress & position)
  {
    plugin.run_progress_ = position;
    emit plugin.runProgressChanged();
  }

  /// The steady clock the plugin reads the world statistics' age on (R2-01).
  static void set_clock(CellConsole & plugin, std::function<std::int64_t()> now_ms)
  {
    plugin.now_ms_ = std::move(now_ms);
  }

  /// The plugin's one display timer, whose ticks re-read both ages.
  static QTimer & display_timer(CellConsole & plugin) {return plugin.health_timer_;}

  /// How many times a press reached the plugin's Stop and Confirm (S-01).
  static std::size_t stops_pressed(const CellConsole & plugin) {return plugin.stops_pressed_;}
  static std::size_t confirms_pressed(const CellConsole & plugin)
  {
    return plugin.confirms_pressed_;
  }
};

}  // namespace cite_console_gui

#endif  // CELL_CONSOLE_TEST_ACCESS_HPP_
