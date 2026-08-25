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

// The geometry both simulation aids decide on, exercised without a simulator.
//
// A break beam that never trips and a belt that carries nothing look identical
// from outside: silence. These are the tests that tell the two apart before a
// world is ever launched.

#include <cmath>

#include <gz/math/Pose3.hh>
#include <gz/math/Vector3.hh>

#include "gtest/gtest.h"
#include "cite_simulation/zone_rules.hpp"

namespace
{

using cite_simulation::zone_rules::beam_centre_offset;
using cite_simulation::zone_rules::beam_half_extents;
using cite_simulation::zone_rules::inside_box;

const gz::math::Vector3d kNoOffset{0.0, 0.0, 0.0};

gz::math::Pose3d at(double x, double y, double z)
{
  return gz::math::Pose3d(x, y, z, 0.0, 0.0, 0.0);
}

}  // namespace

TEST(ZoneRules, a_body_at_the_centre_is_inside)
{
  EXPECT_TRUE(inside_box(at(0, 0, 0), at(0, 0, 0), kNoOffset, {1.0, 1.0, 1.0}));
}

TEST(ZoneRules, a_body_beyond_any_extent_is_outside)
{
  const auto half = gz::math::Vector3d(1.0, 1.0, 1.0);
  EXPECT_FALSE(inside_box(at(0, 0, 0), at(1.01, 0, 0), kNoOffset, half));
  EXPECT_FALSE(inside_box(at(0, 0, 0), at(0, 1.01, 0), kNoOffset, half));
  EXPECT_FALSE(inside_box(at(0, 0, 0), at(0, 0, 1.01), kNoOffset, half));
}

TEST(ZoneRules, the_box_is_measured_in_the_frames_own_axes)
{
  // A belt or a sensor mounted at an angle must measure across itself, not
  // across the building. Rotated a quarter turn about z, the frame's own +x
  // points along the world's +y.
  const gz::math::Pose3d rotated(0.0, 0.0, 0.0, 0.0, 0.0, M_PI / 2.0);
  const auto half = gz::math::Vector3d(2.0, 0.1, 0.1);
  EXPECT_TRUE(inside_box(rotated, at(0.0, 1.5, 0.0), kNoOffset, half));
  EXPECT_FALSE(inside_box(rotated, at(1.5, 0.0, 0.0), kNoOffset, half));
}

TEST(ZoneRules, a_degenerate_box_contains_nothing)
{
  // A zero extent is what a missing model value would produce. It must make the
  // volume empty, never universal: a belt with no declared length would
  // otherwise carry the whole cell.
  EXPECT_FALSE(inside_box(at(0, 0, 0), at(0, 0, 0), kNoOffset, {0.0, 1.0, 1.0}));
  EXPECT_FALSE(inside_box(at(0, 0, 0), at(0, 0, 0), kNoOffset, {1.0, -1.0, 1.0}));
}

TEST(ZoneRules, the_belts_carry_volume_sits_on_the_surface_and_extends_upward)
{
  // The conveyor's volume: 1.2 m x 0.4 m footprint, 0.1 m of headroom above the
  // surface frame. A part resting on the belt is inside it; the same part held
  // well above the belt, or below it, is not.
  const double carry = 0.1;
  const gz::math::Vector3d centre(0.0, 0.0, carry / 2.0);
  const gz::math::Vector3d half(0.6, 0.2, carry / 2.0);
  const auto surface = at(1.05, 0.0, 0.6);

  EXPECT_TRUE(inside_box(surface, at(1.05, 0.0, 0.625), centre, half));   // resting
  EXPECT_FALSE(inside_box(surface, at(1.05, 0.0, 0.78), centre, half));   // lifted clear
  EXPECT_FALSE(inside_box(surface, at(1.05, 0.0, 0.55), centre, half));   // under the belt
  EXPECT_FALSE(inside_box(surface, at(1.75, 0.0, 0.625), centre, half));  // past the end
}

TEST(ZoneRules, a_beam_is_long_along_its_axis_and_thin_across_it)
{
  const auto y = beam_half_extents("y", 0.5, 0.04);
  EXPECT_DOUBLE_EQ(y.Y(), 0.25);
  EXPECT_DOUBLE_EQ(y.X(), 0.02);
  EXPECT_DOUBLE_EQ(y.Z(), 0.02);

  const auto x = beam_half_extents("x", 0.5, 0.04);
  EXPECT_DOUBLE_EQ(x.X(), 0.25);
  const auto z = beam_half_extents("z", 0.5, 0.04);
  EXPECT_DOUBLE_EQ(z.Z(), 0.25);
}

TEST(ZoneRules, an_unreadable_beam_axis_yields_no_volume)
{
  // Reporting nothing is the safe answer for a misconfigured beam. Reporting
  // everything would make every station believe a part had arrived.
  EXPECT_EQ(beam_half_extents("q", 0.5, 0.04), gz::math::Vector3d::Zero);
  EXPECT_EQ(beam_half_extents("", 0.5, 0.04), gz::math::Vector3d::Zero);
}

TEST(ZoneRules, a_part_crossing_the_beam_breaks_it)
{
  // The real geometry: beam_c1_out sits 50 mm back from conveyor_1's outfeed,
  // 250 mm to the side, 30 mm above the belt surface, pointing along y. The
  // beam is emitted from that housing and crosses the belt, so its middle lies
  // 250 mm back along its own axis.
  const auto housing = at(1.6, 0.25, 0.63);
  const auto half = beam_half_extents("y", 0.5, 0.04);
  const auto centre = beam_centre_offset("y", -0.25);

  // A 50 mm part on the belt centreline, level with the beam, breaks it.
  EXPECT_TRUE(inside_box(housing, at(1.6, 0.0, 0.63), centre, half));
  // So does one at either edge of the 0.4 m belt, with margin to spare.
  EXPECT_TRUE(inside_box(housing, at(1.6, -0.2, 0.63), centre, half));
  EXPECT_TRUE(inside_box(housing, at(1.6, 0.2, 0.63), centre, half));
  // The same part further along the belt has not reached the beam.
  EXPECT_FALSE(inside_box(housing, at(1.4, 0.0, 0.63), centre, half));
  // And a part beyond the beam's span does not break it.
  EXPECT_FALSE(inside_box(housing, at(1.6, -0.4, 0.63), centre, half));
}

TEST(ZoneRules, a_beam_centred_on_its_housing_barely_reaches_the_belt)
{
  // The defect the offset above removes, kept as a test so that dropping the
  // offset cannot pass silently. Centred on a housing 250 mm to the side, a
  // 500 mm beam has its near EDGE on the belt centreline: a part one millimetre
  // to the far side is invisible to it.
  const auto housing = at(1.6, 0.25, 0.63);
  const auto half = beam_half_extents("y", 0.5, 0.04);

  EXPECT_TRUE(inside_box(housing, at(1.6, 0.0, 0.63), kNoOffset, half));
  EXPECT_FALSE(inside_box(housing, at(1.6, -0.001, 0.63), kNoOffset, half));
}

TEST(ZoneRules, a_beam_with_no_offset_is_centred_on_its_housing)
{
  EXPECT_EQ(beam_centre_offset("y", 0.0), gz::math::Vector3d::Zero);
  EXPECT_EQ(beam_centre_offset("x", -0.25), gz::math::Vector3d(-0.25, 0.0, 0.0));
  EXPECT_EQ(beam_centre_offset("z", 0.25), gz::math::Vector3d(0.0, 0.0, 0.25));
  EXPECT_EQ(beam_centre_offset("q", 0.25), gz::math::Vector3d::Zero);
}
