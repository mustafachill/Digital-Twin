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

// The header's sim time and RTF (ADR-0074): how they are written, and the
// client against a fake world publishing its statistics on a gz-transport
// partition of this test's own, in this process.

#include <gtest/gtest.h>
#include <unistd.h>
#include <gz/msgs/world_stats.pb.h>

#include <chrono>
#include <cstdint>
#include <condition_variable>
#include <cstdlib>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>

#include <gz/transport/Node.hh>

#include "cite_console_gui/world_stats_client.hpp"

using cite_console_gui::format_real_time_factor;
using cite_console_gui::format_sim_time;
using cite_console_gui::world_stats_from;
using cite_console_gui::WorldStats;
using cite_console_gui::WorldStatsClient;

namespace
{

// Before any node exists: gz transport reads the partition once per process,
// and a test must never reach a simulator someone else has open.
const bool PRIVATE_PARTITION = []() {
    const std::string partition = "cite_test_world_stats_" + std::to_string(::getpid());
    ::setenv("GZ_PARTITION", partition.c_str(), 1);
    ::setenv("GZ_IP", "127.0.0.1", 1);
    return true;
  }();

constexpr const char * TOPIC = "/world/test_world/stats";

gz::msgs::WorldStatistics message(double sim_time_s, double factor, bool paused)
{
  gz::msgs::WorldStatistics stats;
  const auto seconds = static_cast<std::int64_t>(sim_time_s);
  stats.mutable_sim_time()->set_sec(seconds);
  stats.mutable_sim_time()->set_nsec(
    static_cast<std::int32_t>((sim_time_s - static_cast<double>(seconds)) * 1e9));
  stats.set_real_time_factor(factor);
  stats.set_paused(paused);
  return stats;
}

}  // namespace

TEST(WorldStatsFormat, SimTimeIsHoursMinutesSecondsAndTenths)
{
  EXPECT_EQ(format_sim_time(0.0), "00:00:00.0");
  EXPECT_EQ(format_sim_time(83.46), "00:01:23.4");
  EXPECT_EQ(format_sim_time(3723.99), "01:02:03.9");
  EXPECT_EQ(format_sim_time(360000.0), "100:00:00.0");
}

TEST(WorldStatsFormat, ATimeThatIsNotOneIsDashes)
{
  EXPECT_EQ(format_sim_time(-1.0), "--:--:--");
  EXPECT_EQ(format_sim_time(std::numeric_limits<double>::quiet_NaN()), "--:--:--");
  EXPECT_EQ(format_sim_time(std::numeric_limits<double>::infinity()), "--:--:--");
}

TEST(WorldStatsFormat, TheRealTimeFactorHasTwoDecimals)
{
  EXPECT_EQ(format_real_time_factor(0.98765), "0.99");
  EXPECT_EQ(format_real_time_factor(1.0), "1.00");
  EXPECT_EQ(format_real_time_factor(-0.1), "--");
  EXPECT_EQ(format_real_time_factor(std::numeric_limits<double>::quiet_NaN()), "--");
}

TEST(WorldStatsFormat, StatisticsGoStaleOnlyOnceHeardAndPastTheThreshold)
{
  using cite_console_gui::world_stats_stale;
  EXPECT_FALSE(world_stats_stale(false, 100.0, 1.0)) << "stale before any was heard";
  EXPECT_FALSE(world_stats_stale(true, 0.5, 1.0));
  EXPECT_FALSE(world_stats_stale(true, 1.0, 1.0));
  EXPECT_TRUE(world_stats_stale(true, 1.01, 1.0));
  EXPECT_FALSE(world_stats_stale(true, 100.0, 0.0)) << "stale with no threshold";
}

TEST(WorldStatsFormat, TheMessageIsReadWhole)
{
  const WorldStats stats = world_stats_from(message(12.5, 0.75, true));
  EXPECT_NEAR(stats.sim_time_s, 12.5, 1e-6);
  EXPECT_DOUBLE_EQ(stats.real_time_factor, 0.75);
  EXPECT_TRUE(stats.paused);
}

TEST(WorldStatsClient, ItHearsTheWorldOnItsTopic)
{
  ASSERT_TRUE(PRIVATE_PARTITION);
  std::mutex mutex;
  std::condition_variable heard;
  WorldStats last;
  int count = 0;
  WorldStatsClient client(TOPIC, [&](const WorldStats & stats) {
      std::lock_guard<std::mutex> lock(mutex);
      last = stats;
      ++count;
      heard.notify_all();
    });

  gz::transport::Node world;
  auto publisher = world.Advertise<gz::msgs::WorldStatistics>(TOPIC);
  ASSERT_TRUE(publisher);
  // Discovery is asynchronous and a publication before it reaches nobody, so
  // the fake world publishes as gz-sim does, periodically, until heard.
  std::unique_lock<std::mutex> lock(mutex);
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
  while (count == 0 && std::chrono::steady_clock::now() < deadline) {
    lock.unlock();
    publisher.Publish(message(42.0, 0.5, false));
    lock.lock();
    heard.wait_for(lock, std::chrono::milliseconds(100), [&]() {return count > 0;});
  }
  ASSERT_GT(count, 0) << "no statistics heard on " << TOPIC;
  EXPECT_NEAR(last.sim_time_s, 42.0, 1e-6);
  EXPECT_DOUBLE_EQ(last.real_time_factor, 0.5);
  EXPECT_FALSE(last.paused);
}

TEST(WorldStatsClient, AMalformedTopicIsRefused)
{
  EXPECT_THROW(
    WorldStatsClient("not a topic with spaces", [](const WorldStats &) {}),
    std::runtime_error);
}
