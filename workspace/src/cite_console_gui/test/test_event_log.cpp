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

// The frame's event log (ADR-0074): transitions only, newest first, at most
// its capacity, the oldest forgotten first.

#include <gtest/gtest.h>

#include <string>

#include "cite_console_gui/event_log.hpp"

using cite_console_gui::EVENT_LOG_CAPACITY;
using cite_console_gui::EventLog;

TEST(EventLog, ItKeepsFiftyByDefault)
{
  EXPECT_EQ(EVENT_LOG_CAPACITY, 50u);
  EXPECT_EQ(EventLog().capacity(), 50u);
}

TEST(EventLog, TheSameStateHeardAgainIsNotATransition)
{
  EventLog log;
  EXPECT_TRUE(log.record("10:00:00", "READY", "", ""));
  EXPECT_FALSE(log.record("10:00:01", "READY", "", ""));
  ASSERT_EQ(log.entries().size(), 1u);
  EXPECT_EQ(log.entries().front().time, "10:00:00");
}

TEST(EventLog, AChangeOfStateStepOrErrorIsOneNewestFirst)
{
  EventLog log;
  log.record("10:00:00", "READY", "", "");
  EXPECT_TRUE(log.record("10:00:01", "RUNNING", "", ""));
  EXPECT_TRUE(log.record("10:00:02", "RUNNING", "Pick", ""));
  EXPECT_TRUE(log.record("10:00:03", "RUNNING", "Pick", "refused: busy"));
  ASSERT_EQ(log.entries().size(), 4u);
  EXPECT_EQ(log.entries()[0].last_error, "refused: busy");
  EXPECT_EQ(log.entries()[1].step, "Pick");
  EXPECT_EQ(log.entries()[2].state, "RUNNING");
  EXPECT_EQ(log.entries()[3].state, "READY");
}

TEST(EventLog, AStateThatComesBackIsRecordedAgain)
{
  EventLog log;
  log.record("10:00:00", "READY", "", "");
  log.record("10:00:01", "No console", "", "");
  EXPECT_TRUE(log.record("10:00:02", "READY", "", ""));
  EXPECT_EQ(log.entries().size(), 3u);
}

TEST(EventLog, WhenFullTheOldestIsForgotten)
{
  EventLog log(3);
  for (int index = 0; index < 5; ++index) {
    log.record(std::to_string(index), "STATE " + std::to_string(index), "", "");
  }
  ASSERT_EQ(log.entries().size(), 3u);
  EXPECT_EQ(log.entries().front().time, "4");
  EXPECT_EQ(log.entries().back().time, "2");
}

TEST(EventLog, ACapacityOfZeroStillKeepsTheNewest)
{
  EventLog log(0);
  log.record("1", "A", "", "");
  log.record("2", "B", "", "");
  ASSERT_EQ(log.entries().size(), 1u);
  EXPECT_EQ(log.entries().front().state, "B");
}

// R-03: the panel's own note (a dropped target pick) is shown, and the
// console's same state heard after it is still not a new transition.
TEST(EventLog, ANoteIsShownButIsNotTheConsolesLastState)
{
  EventLog log;
  log.record("10:00:00", "READY", "", "");
  log.note("10:00:00", "Target selection dropped", "Console changed: now Simulation");
  ASSERT_EQ(log.entries().size(), 2u);
  EXPECT_EQ(log.entries().front().state, "Target selection dropped");
  EXPECT_EQ(log.entries().front().step, "Console changed: now Simulation");
  EXPECT_FALSE(log.record("10:00:01", "READY", "", "")) << "a re-publication after a note";
  EXPECT_TRUE(log.record("10:00:02", "RUNNING", "", ""));
}
