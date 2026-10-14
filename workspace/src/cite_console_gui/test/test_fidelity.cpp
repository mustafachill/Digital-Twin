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

// The "Twin fidelity" card (ADR-0074): no number unless the sample is valid,
// "not computed" for a field nobody computed, and a valid comparison of two
// simulations never called a fidelity result (P7, P8).

#include <gtest/gtest.h>

#include <limits>
#include <string>

#include "cite_console_gui/fidelity.hpp"

using cite_console_gui::DivergenceSample;
using cite_console_gui::fidelity_view;
using cite_console_gui::format_angle;
using cite_console_gui::format_length;

namespace
{

DivergenceSample sample(bool valid, bool physical)
{
  DivergenceSample read;
  read.asset_id = "picker";
  read.valid = valid;
  read.joint_error_rms_rad = 0.0123;
  read.joint_error_max_rad = 0.05;
  read.tcp_position_error_m = std::numeric_limits<double>::quiet_NaN();
  read.tcp_orientation_error_rad = std::numeric_limits<double>::quiet_NaN();
  read.far_side_physical = physical;
  return read;
}

}  // namespace

TEST(Fidelity, AnInvalidSampleIsNotMeasuredAndShowsNoNumber)
{
  for (const bool physical : {false, true}) {
    const auto view = fidelity_view(sample(false, physical));
    EXPECT_FALSE(view.measured);
    EXPECT_EQ(view.headline, "Not measured");
    EXPECT_TRUE(view.rows.empty());
    EXPECT_EQ(view.asset_id, "picker");
  }
}

TEST(Fidelity, AValidSampleShowsEachFigureWithItsUnit)
{
  const auto view = fidelity_view(sample(true, true));
  EXPECT_TRUE(view.measured);
  EXPECT_EQ(view.headline, "Measured");
  ASSERT_EQ(view.rows.size(), 4u);
  EXPECT_EQ(view.rows[0].label, "Joint error, RMS");
  EXPECT_NE(view.rows[0].value.find("0.0123 rad"), std::string::npos) << view.rows[0].value;
  EXPECT_NE(view.rows[1].value.find("0.0500 rad"), std::string::npos) << view.rows[1].value;
  EXPECT_EQ(view.rows[2].value, "not computed");
  EXPECT_EQ(view.rows[3].value, "not computed");
}

TEST(Fidelity, TwoSimulationsAreAnInstrumentTestNotAFidelityResult)
{
  const auto view = fidelity_view(sample(true, false));
  EXPECT_TRUE(view.measured);
  EXPECT_EQ(view.headline, "Instrument test: both sides simulated");
}

TEST(Fidelity, UnitsAreStated)
{
  EXPECT_EQ(format_length(0.0123), "12.3 mm");
  EXPECT_EQ(format_length(0.0), "0.0 mm");
  EXPECT_EQ(format_angle(0.0).rfind("0.0000 rad (0.00", 0), 0u) << format_angle(0.0);
  EXPECT_NE(format_angle(3.14159265358979).find("(180.00"), std::string::npos);
  EXPECT_EQ(format_angle(std::numeric_limits<double>::quiet_NaN()), "not computed");
  EXPECT_EQ(format_length(std::numeric_limits<double>::quiet_NaN()), "not computed");
}
