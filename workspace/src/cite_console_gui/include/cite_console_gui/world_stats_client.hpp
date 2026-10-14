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

// The frame header's sim time and real-time factor (ADR-0074): the window's
// own world statistics, over gz transport, with no Qt and no ROS in it.
//
// WHERE IT COMES FROM. gz-sim publishes gz.msgs.WorldStatistics on
// `/world/<world>/stats`; the panel is handed that topic by the generated GUI
// configuration (`world_stats_topic`, generate/gui.py), and builds no name. The
// topic is scoped by the gz-transport partition, and this client's node lives in
// the window's process, so it carries the window's GZ_PARTITION - the same one
// the world publishes on (CLAUDE.md §10).
//
// DISPLAY ONLY. What it hears is shown and nothing else: it gates nothing and
// times nothing. `on_stats` runs on gz transport's own thread; the owner moves
// it to its own before touching anything it shares.

#ifndef CITE_CONSOLE_GUI__WORLD_STATS_CLIENT_HPP_
#define CITE_CONSOLE_GUI__WORLD_STATS_CLIENT_HPP_

#include <functional>
#include <mutex>
#include <string>

#include <gz/transport/Node.hh>

namespace gz::msgs
{
class WorldStatistics;
}  // namespace gz::msgs

namespace cite_console_gui
{

/// The part of one WorldStatistics the header shows.
struct WorldStats
{
  double sim_time_s{0.0};
  double real_time_factor{0.0};
  bool paused{false};
};

/// Sim time as the header shows it, "HH:MM:SS.s"; "--:--:--" for a value that
/// is not a time (negative, NaN or infinite).
std::string format_sim_time(double seconds);

/// The real-time factor as the header shows it, "0.98"; "--" for a value that
/// is not one (negative, NaN or infinite).
std::string format_real_time_factor(double factor);

/// The fields the header reads, from one message.
WorldStats world_stats_from(const gz::msgs::WorldStatistics & message);

class WorldStatsClient
{
public:
  using OnStats = std::function<void(const WorldStats &)>;

  /// Subscribe to `topic`. Throws std::runtime_error when gz transport refuses
  /// the subscription (a malformed topic).
  WorldStatsClient(const std::string & topic, OnStats on_stats);
  ~WorldStatsClient();

  WorldStatsClient(const WorldStatsClient &) = delete;
  WorldStatsClient & operator=(const WorldStatsClient &) = delete;

private:
  void on_message(const gz::msgs::WorldStatistics & message);

  std::string topic_;
  OnStats on_stats_;
  std::mutex mutex_;
  bool closed_{false};
  gz::transport::Node node_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__WORLD_STATS_CLIENT_HPP_
