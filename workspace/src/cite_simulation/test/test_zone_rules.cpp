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
#include <string>

#include <gz/math/Pose3.hh>
#include <gz/math/Quaternion.hh>
#include <gz/math/Vector3.hh>

#include "gtest/gtest.h"
#include "cite_simulation/zone_rules.hpp"

namespace
{

using cite_simulation::zone_rules::beam_axis_unit;
using cite_simulation::zone_rules::beam_centre_offset;
using cite_simulation::zone_rules::inside_box;
using cite_simulation::zone_rules::segment_reaches_box;

const gz::math::Vector3d kNoOffset{0.0, 0.0, 0.0};

gz::math::Pose3d at(double x, double y, double z)
{
  return gz::math::Pose3d(x, y, z, 0.0, 0.0, 0.0);
}

//: Half a 50 mm cube — the facility's declared work-piece, and the body every
//: beam test below is broken by.
const gz::math::Vector3d kCubeHalf{0.025, 0.025, 0.025};

/// One end of a beam, in the world, exactly as the plugin resolves it.
///
/// Kept here rather than written out per test so that a change to how a beam is
/// described cannot leave these tests measuring a different beam from the one
/// `break_beam.cpp` builds.
gz::math::Vector3d beam_end(
  const gz::math::Pose3d & housing, const std::string & axis, double offset, double length,
  double sign)
{
  const auto point =
    beam_centre_offset(axis, offset) + beam_axis_unit(axis) * (sign * length / 2.0);
  return (housing * gz::math::Pose3d(point, gz::math::Quaterniond::Identity)).Pos();
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

TEST(ZoneRules, an_unreadable_beam_axis_yields_no_beam)
{
  // Reporting nothing is the safe answer for a misconfigured beam. Reporting
  // everything would make every station believe a part had arrived.
  EXPECT_EQ(beam_axis_unit("q"), gz::math::Vector3d::Zero);
  EXPECT_EQ(beam_axis_unit(""), gz::math::Vector3d::Zero);
  EXPECT_EQ(beam_axis_unit("x"), gz::math::Vector3d(1.0, 0.0, 0.0));
  EXPECT_EQ(beam_axis_unit("y"), gz::math::Vector3d(0.0, 1.0, 0.0));
  EXPECT_EQ(beam_axis_unit("z"), gz::math::Vector3d(0.0, 0.0, 1.0));
}

TEST(ZoneRules, a_beam_with_no_offset_is_centred_on_its_housing)
{
  EXPECT_EQ(beam_centre_offset("y", 0.0), gz::math::Vector3d::Zero);
  EXPECT_EQ(beam_centre_offset("x", -0.25), gz::math::Vector3d(-0.25, 0.0, 0.0));
  EXPECT_EQ(beam_centre_offset("z", 0.25), gz::math::Vector3d(0.0, 0.0, 0.25));
  EXPECT_EQ(beam_centre_offset("q", 0.25), gz::math::Vector3d::Zero);
}

TEST(ZoneRules, a_part_crossing_the_beam_breaks_it)
{
  // The real geometry: beam_c1_out now stands 27 mm PAST conveyor_1's outfeed at
  // x = 1.600 — half a work-piece plus half a beam width — 250 mm to the side,
  // 30 mm above the belt surface, pointing along y. The beam is emitted from
  // that housing and crosses the belt, so its middle lies 250 mm back along its
  // own axis.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);
  constexpr double kRadius = 0.002;

  // A cube parked on the pick point breaks the beam: its leading edge is in it.
  EXPECT_TRUE(segment_reaches_box(at(1.6, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  // So does one at either edge of the 0.4 m belt, with margin to spare.
  EXPECT_TRUE(segment_reaches_box(at(1.6, -0.2, 0.625), kCubeHalf, from, to, kRadius));
  EXPECT_TRUE(segment_reaches_box(at(1.6, 0.2, 0.625), kCubeHalf, from, to, kRadius));
  // A cube still well upstream has not reached it.
  EXPECT_FALSE(segment_reaches_box(at(1.4, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  // Nor has one beyond the beam's span, off the side of the belt.
  EXPECT_FALSE(segment_reaches_box(at(1.6, -0.4, 0.625), kCubeHalf, from, to, kRadius));
  // And one that has gone past is clear again — the beam does not latch.
  EXPECT_FALSE(segment_reaches_box(at(1.7, 0.0, 0.625), kCubeHalf, from, to, kRadius));
}

TEST(ZoneRules, the_beam_breaks_on_the_leading_edge_and_clears_on_the_trailing_one)
{
  // THE REGRESSION, and the reason this file changed at all.
  //
  // The beam used to be a box tested against the work-piece's model ORIGIN, so
  // it reported a 50 mm cube only once its CENTRE came within half a beam width
  // — 25 mm after the leading edge had actually arrived. `continuous_line`
  // stopped `conveyor_1` on that late edge and parked every piece 69 mm short of
  // `arm_2`'s grasp; the arm closed on air at 46 mm and the line stopped at
  // milestone 4 of 10.
  //
  // The geometry below is the shipped cell: the housing is derived to stand at
  // 1.627, and the assertion is that the break happens as the part's centre
  // reaches the pick point at 1.600 and not 25 mm later.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);
  constexpr double kRadius = 0.002;
  constexpr double kPickX = 1.600;

  // A hair before the pick point the leading edge has not reached the beam.
  EXPECT_FALSE(segment_reaches_box(at(kPickX - 0.001, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  // A hair after it, it has. That is the whole fix: the belt stops here.
  EXPECT_TRUE(segment_reaches_box(at(kPickX + 0.001, 0.0, 0.625), kCubeHalf, from, to, kRadius));

  // It stays broken while the body is passing, and clears once the trailing edge
  // is through — a beam that latched, or one that reported only an instant,
  // would fail one of these.
  // The trailing edge leaves the far side of the beam when the origin reaches
  // 1.654 — the pick point plus half a part plus half a beam, the mirror of the
  // break. Either side of it by a millimetre:
  EXPECT_TRUE(segment_reaches_box(at(kPickX + 0.025, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  EXPECT_TRUE(segment_reaches_box(at(kPickX + 0.053, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  EXPECT_FALSE(segment_reaches_box(at(kPickX + 0.055, 0.0, 0.625), kCubeHalf, from, to, kRadius));
}

TEST(ZoneRules, a_beam_sees_a_part_of_any_height_that_reaches_it)
{
  // The other face of the same defect. The origin test gave the sensor a window
  // of part-CENTRE heights, so it detected a part between 20 mm and 100 mm tall
  // and missed everything outside that — while the physical cell, whose beams
  // are broken by any body that crosses them, saw all of it. A tall part is the
  // case that was wrong in the dangerous direction: detected on hardware, missed
  // here.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);
  constexpr double kRadius = 0.002;
  constexpr double kSurfaceZ = 0.600;

  // 300 mm tall, resting on the belt: the old window cleared it entirely.
  const gz::math::Vector3d tall{0.025, 0.025, 0.150};
  EXPECT_TRUE(segment_reaches_box(at(1.6, 0.0, kSurfaceZ + 0.150), tall, from, to, kRadius));

  // 40 mm tall still reaches a beam mounted 30 mm up.
  const gz::math::Vector3d low{0.025, 0.025, 0.020};
  EXPECT_TRUE(segment_reaches_box(at(1.6, 0.0, kSurfaceZ + 0.020), low, from, to, kRadius));

  // 20 mm tall does not, and that is now CORRECT rather than a limitation: a
  // real beam 30 mm above the belt cannot see a part that only reaches 20 mm
  // either. `beam-cannot-see-workpiece` in cite_tools.validate.geometric rejects
  // such a pairing in the model instead of leaving it to be discovered here.
  const gz::math::Vector3d flat{0.025, 0.025, 0.010};
  EXPECT_FALSE(segment_reaches_box(at(1.6, 0.0, kSurfaceZ + 0.010), flat, from, to, kRadius));
}

TEST(ZoneRules, a_beam_centred_on_its_housing_barely_reaches_the_belt)
{
  // The defect the offset removes, kept as a test so that dropping the offset
  // cannot pass silently. Centred on a housing 250 mm to the side, a 500 mm beam
  // ENDS on the belt centreline: a part whose body lies wholly beyond it is
  // invisible.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", 0.0, 0.5, -1.0);
  const auto to = beam_end(housing, "y", 0.0, 0.5, +1.0);
  constexpr double kRadius = 0.002;

  EXPECT_TRUE(segment_reaches_box(at(1.6, 0.0, 0.625), kCubeHalf, from, to, kRadius));
  EXPECT_FALSE(segment_reaches_box(at(1.6, -0.030, 0.625), kCubeHalf, from, to, kRadius));
}

TEST(ZoneRules, a_beam_measures_a_part_in_the_parts_own_axes)
{
  // A part yawed on the belt is measured across itself, not across the building.
  // A 50 x 20 mm slab turned 90 degrees presents its short side to the beam, and
  // an axis-aligned world-space test would report the wrong extent for it.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);
  constexpr double kRadius = 0.002;

  const gz::math::Vector3d slab{0.025, 0.010, 0.025};
  const gz::math::Pose3d square(1.60, 0.0, 0.625, 0.0, 0.0, 0.0);
  const gz::math::Pose3d turned(1.60, 0.0, 0.625, 0.0, 0.0, M_PI / 2.0);

  // Square on, the 50 mm side faces the beam and its leading edge is in it.
  EXPECT_TRUE(segment_reaches_box(square, slab, from, to, kRadius));
  // Turned, only the 20 mm side does, and the part has not reached the beam yet.
  EXPECT_FALSE(segment_reaches_box(turned, slab, from, to, kRadius));
}

TEST(ZoneRules, a_degenerate_body_is_never_in_the_beam)
{
  // The same refusal `inside_box` makes, for the same reason: a missing extent
  // arriving from an unreadable shape must make the beam report nothing rather
  // than report everything.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);

  EXPECT_FALSE(segment_reaches_box(at(1.6, 0.0, 0.625), {0.0, 0.025, 0.025}, from, to, 0.002));
  EXPECT_FALSE(segment_reaches_box(at(1.6, 0.0, 0.625), {0.025, -1.0, 0.025}, from, to, 0.002));
  EXPECT_FALSE(segment_reaches_box(at(1.6, 0.0, 0.625), kCubeHalf, from, to, -0.001));
}

TEST(ZoneRules, a_beam_is_a_segment_and_not_an_infinite_line)
{
  // A part in line with the beam but past its far end must not break it. The
  // slab test is bounded to the segment for exactly this: an unbounded line
  // would have `beam_c1_out` reporting parts on the far side of the cell.
  const auto housing = at(1.627, 0.25, 0.63);
  const auto from = beam_end(housing, "y", -0.25, 0.5, -1.0);
  const auto to = beam_end(housing, "y", -0.25, 0.5, +1.0);

  EXPECT_TRUE(segment_reaches_box(at(1.6, -0.24, 0.625), kCubeHalf, from, to, 0.002));
  EXPECT_FALSE(segment_reaches_box(at(1.6, -0.30, 0.625), kCubeHalf, from, to, 0.002));
}
