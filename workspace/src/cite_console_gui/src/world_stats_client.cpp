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

#include "cite_console_gui/world_stats_client.hpp"

#include <gz/msgs/world_stats.pb.h>

#include <cmath>
#include <cstdio>
#include <mutex>
#include <stdexcept>
#include <string>
#include <utility>

namespace cite_console_gui
{

std::string format_sim_time(double seconds)
{
  if (!std::isfinite(seconds) || seconds < 0.0) {
    return "--:--:--";
  }
  // Tenths, rounded down, so the shown clock never runs ahead of the world's.
  const auto tenths = static_cast<long long>(std::floor(seconds * 10.0));
  const long long hours = tenths / 36000;
  const long long minutes = (tenths / 600) % 60;
  const long long secs = (tenths / 10) % 60;
  const long long tenth = tenths % 10;
  char text[48];
  std::snprintf(text, sizeof(text), "%02lld:%02lld:%02lld.%lld", hours, minutes, secs, tenth);
  return text;
}

std::string format_real_time_factor(double factor)
{
  if (!std::isfinite(factor) || factor < 0.0) {
    return "--";
  }
  char text[32];
  std::snprintf(text, sizeof(text), "%.2f", factor);
  return text;
}

WorldStats world_stats_from(const gz::msgs::WorldStatistics & message)
{
  WorldStats stats;
  stats.sim_time_s = static_cast<double>(message.sim_time().sec()) +
    static_cast<double>(message.sim_time().nsec()) * 1e-9;
  stats.real_time_factor = message.real_time_factor();
  stats.paused = message.paused();
  return stats;
}

WorldStatsClient::WorldStatsClient(const std::string & topic, OnStats on_stats)
: topic_(topic), on_stats_(std::move(on_stats))
{
  if (!node_.Subscribe(topic_, &WorldStatsClient::on_message, this)) {
    throw std::runtime_error("gz transport refused a subscription to " + topic_);
  }
}

WorldStatsClient::~WorldStatsClient()
{
  {
    // Waits for a callback in flight, and none starts once this is set: the
    // owner is never called while, or after, it goes away.
    std::lock_guard<std::mutex> lock(mutex_);
    closed_ = true;
  }
  node_.Unsubscribe(topic_);
}

void WorldStatsClient::on_message(const gz::msgs::WorldStatistics & message)
{
  std::lock_guard<std::mutex> lock(mutex_);
  if (!closed_ && on_stats_) {
    on_stats_(world_stats_from(message));
  }
}

}  // namespace cite_console_gui
