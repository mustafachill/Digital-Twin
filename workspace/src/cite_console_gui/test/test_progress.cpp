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

// The progress ring's share (ADR-0074): steps reached over the phase's steps.

#include <gtest/gtest.h>

#include "cite_console_gui/progress.hpp"

using cite_console_gui::progress_fraction;
using cite_console_gui::RunProgress;

namespace
{

RunProgress at(unsigned cycle, unsigned cycles, unsigned step, unsigned steps)
{
  RunProgress progress;
  progress.active = true;
  progress.cycle = cycle;
  progress.cycles = cycles;
  progress.step_index = step;
  progress.step_count = steps;
  return progress;
}

}  // namespace

TEST(Progress, NothingKnownIsNothingReached)
{
  EXPECT_DOUBLE_EQ(progress_fraction(RunProgress{}), 0.0);
  RunProgress inactive = at(1, 1, 5, 10);
  inactive.active = false;
  EXPECT_DOUBLE_EQ(progress_fraction(inactive), 0.0);
  // A phase's opening report: cycle and step 0 (ValidateThenRun.action).
  EXPECT_DOUBLE_EQ(progress_fraction(at(0, 1, 0, 0)), 0.0);
  EXPECT_DOUBLE_EQ(progress_fraction(at(1, 0, 1, 10)), 0.0);
}

TEST(Progress, StepsAreCountedAcrossCycles)
{
  EXPECT_DOUBLE_EQ(progress_fraction(at(1, 1, 5, 10)), 0.5);
  EXPECT_DOUBLE_EQ(progress_fraction(at(1, 2, 10, 10)), 0.5);
  EXPECT_DOUBLE_EQ(progress_fraction(at(2, 2, 5, 10)), 0.75);
  EXPECT_DOUBLE_EQ(progress_fraction(at(2, 2, 10, 10)), 1.0);
}

TEST(Progress, CountsThatOverrunAreClamped)
{
  EXPECT_DOUBLE_EQ(progress_fraction(at(3, 2, 10, 10)), 1.0);
  EXPECT_DOUBLE_EQ(progress_fraction(at(1, 1, 12, 10)), 1.0);
}
