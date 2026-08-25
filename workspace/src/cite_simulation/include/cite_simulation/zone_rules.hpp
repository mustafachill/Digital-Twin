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

#ifndef CITE_SIMULATION__ZONE_RULES_HPP_
#define CITE_SIMULATION__ZONE_RULES_HPP_

#include <string>

#include <gz/math/Pose3.hh>
#include <gz/math/Vector3.hh>

namespace cite_simulation
{
namespace zone_rules
{

/// Whether `body` lies inside a box fixed to `frame`.
///
/// `centre_offset` is where the box's centre sits in the frame's OWN axes, and
/// `half_extents` are its half sizes along those same axes. Everything is
/// expressed in the frame rather than in the world, so a belt or a sensor
/// mounted at an angle measures across itself instead of across the building —
/// which is the whole reason the test is written this way rather than as an
/// axis-aligned world-space comparison.
///
/// A non-positive half extent means "no box", and nothing is ever inside it.
/// That matters: a zero extent arriving from a missing model value would
/// otherwise make a degenerate plane report everything as contained.
inline bool inside_box(
  const gz::math::Pose3d & frame,
  const gz::math::Pose3d & body,
  const gz::math::Vector3d & centre_offset,
  const gz::math::Vector3d & half_extents)
{
  if (half_extents.X() <= 0.0 || half_extents.Y() <= 0.0 || half_extents.Z() <= 0.0) {
    return false;
  }
  const auto local = frame.Inverse() * body;
  const auto p = local.Pos() - centre_offset;
  return std::abs(p.X()) <= half_extents.X() &&
         std::abs(p.Y()) <= half_extents.Y() &&
         std::abs(p.Z()) <= half_extents.Z();
}

/// The half extents of a through beam, given which of its own axes it points
/// along.
///
/// `length` runs along the beam; `width` is how thick it is across the other
/// two. Returns a zero vector for an axis that is not `x`, `y` or `z`, which
/// `inside_box` above then treats as "no box" — an unreadable axis must make
/// the beam report nothing rather than report everything.
inline gz::math::Vector3d beam_half_extents(
  const std::string & axis, double length, double width)
{
  const double half_length = length / 2.0;
  const double half_width = width / 2.0;
  if (axis == "x") {
    return {half_length, half_width, half_width};
  }
  if (axis == "y") {
    return {half_width, half_length, half_width};
  }
  if (axis == "z") {
    return {half_width, half_width, half_length};
  }
  return {0.0, 0.0, 0.0};
}

/// Where the middle of a beam sits relative to its housing, in the housing's own
/// axes.
///
/// A through beam is emitted from its housing and crosses something; the housing
/// is one end of the segment, not its middle. `offset` is how far along the beam
/// axis the middle lies, and the generator derives it from where the sensor is
/// mounted. Zero means the housing IS the middle, which is what a beam mounted
/// on the centreline of what it watches would give.
///
/// An unreadable axis yields no offset. That is safe here in a way it is not in
/// `beam_half_extents`: the extents will already be zero, so the beam reports
/// nothing either way.
inline gz::math::Vector3d beam_centre_offset(const std::string & axis, double offset)
{
  if (axis == "x") {
    return {offset, 0.0, 0.0};
  }
  if (axis == "y") {
    return {0.0, offset, 0.0};
  }
  if (axis == "z") {
    return {0.0, 0.0, offset};
  }
  return {0.0, 0.0, 0.0};
}

}  // namespace zone_rules
}  // namespace cite_simulation

#endif  // CITE_SIMULATION__ZONE_RULES_HPP_
