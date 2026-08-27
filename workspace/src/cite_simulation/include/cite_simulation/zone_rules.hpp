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

#include <algorithm>
#include <cmath>
#include <string>
#include <utility>

#include <gz/math/Pose3.hh>
#include <gz/math/Quaternion.hh>
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

/// The direction a beam points, in its housing's own axes.
///
/// Returns a zero vector for an axis that is not `x`, `y` or `z`. Every caller
/// below treats that as "no beam", so an unreadable axis makes the sensor report
/// nothing rather than report everything — the same refusal the degenerate box
/// above makes, for the same reason.
inline gz::math::Vector3d beam_axis_unit(const std::string & axis)
{
  if (axis == "x") {
    return {1.0, 0.0, 0.0};
  }
  if (axis == "y") {
    return {0.0, 1.0, 0.0};
  }
  if (axis == "z") {
    return {0.0, 0.0, 1.0};
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
inline gz::math::Vector3d beam_centre_offset(const std::string & axis, double offset)
{
  return beam_axis_unit(axis) * offset;
}

/// Whether a beam of finite thickness reaches into a body.
///
/// WHAT THIS REPLACED AND WHY, because the difference is the whole point. The
/// beam used to be a box and the body a single point — its model origin — and
/// `inside_box` asked whether that one point was inside that box. That is not
/// what a through beam measures. A real beam is broken by ANY part of a body
/// that crosses it, which means it breaks on the LEADING EDGE of a part
/// travelling towards it, and it goes on being broken until the trailing edge
/// has passed. The point test was wrong in two directions at once and both were
/// measured on this line:
///
///   * across the beam — a part taller than 100 mm passed over the window and a
///     part shorter than 20 mm passed under it, and both are detected on
///     hardware. Here the beam sees a body of any height whose extents reach the
///     beam's line, so the only bound left is the real one: a beam mounted
///     30 mm above a belt cannot see a part 20 mm tall, exactly as on hardware.
///   * along the belt — the beam reported a 50 mm cube when its CENTRE came
///     within half a beam width, which is 45 mm later than its leading edge
///     arrives. A belt indexed on that edge parked every piece short of the
///     pick point.
///
/// `start` and `end` are the beam's two ends in the world; `radius` is half its
/// thickness. The body is the box `box_half_extents` about the origin of
/// `box_frame`, which is a collision shape read from the simulator rather than a
/// dimension declared to this plugin — no work-piece size is written down here
/// or passed in (P5), so a part whose geometry changes in L0 changes what the
/// beam sees with nothing to keep in step.
///
/// Thickness is applied by growing the body rather than the beam. That is the
/// standard equivalence — a segment of radius r against a box is a segment of no
/// radius against the box grown by r — and it keeps the test exact instead of
/// approximating a thick beam by its centreline.
///
/// A non-positive extent, or a zero-length segment, means "nothing to test" and
/// reports false, for the reason `inside_box` gives above: a missing value must
/// not make a degenerate shape swallow the world.
inline bool segment_reaches_box(
  const gz::math::Pose3d & box_frame,
  const gz::math::Vector3d & box_half_extents,
  const gz::math::Vector3d & start,
  const gz::math::Vector3d & end,
  double radius)
{
  if (box_half_extents.X() <= 0.0 || box_half_extents.Y() <= 0.0 ||
    box_half_extents.Z() <= 0.0 || radius < 0.0)
  {
    return false;
  }

  // Both ends into the body's own axes, so a part sitting at any yaw is measured
  // across itself — the same reason `inside_box` works in the frame rather than
  // in the world.
  const gz::math::Pose3d inverse = box_frame.Inverse();
  const gz::math::Vector3d p0 =
    (inverse * gz::math::Pose3d(start, gz::math::Quaterniond::Identity)).Pos();
  const gz::math::Vector3d p1 =
    (inverse * gz::math::Pose3d(end, gz::math::Quaterniond::Identity)).Pos();
  const gz::math::Vector3d direction = p1 - p0;
  const gz::math::Vector3d half =
    box_half_extents + gz::math::Vector3d(radius, radius, radius);

  // Slab clipping. `entry` and `exit` bracket the portion of the segment still
  // able to be inside the box; each axis narrows the bracket, and the segment
  // misses the moment the bracket closes. Bounded to [0, 1] because this is a
  // segment and not an infinite line — a beam that stops short of a part must
  // not report it.
  double entry = 0.0;
  double exit = 1.0;
  for (int axis = 0; axis < 3; ++axis) {
    const double from = p0[axis];
    const double along = direction[axis];
    if (std::abs(along) < 1e-12) {
      // Parallel to this pair of faces: either the whole segment is between them
      // or none of it is.
      if (std::abs(from) > half[axis]) {
        return false;
      }
      continue;
    }
    double near = (-half[axis] - from) / along;
    double far = (half[axis] - from) / along;
    if (near > far) {
      std::swap(near, far);
    }
    entry = std::max(entry, near);
    exit = std::min(exit, far);
    if (entry > exit) {
      return false;
    }
  }
  return true;
}

}  // namespace zone_rules
}  // namespace cite_simulation

#endif  // CITE_SIMULATION__ZONE_RULES_HPP_
