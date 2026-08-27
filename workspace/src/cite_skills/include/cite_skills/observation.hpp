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

// What a `Detection` says about position when the sensor that made it cannot
// say anything about position.
//
// A through-beam reports OCCUPANCY, not POSITION. It knows something crossed
// it; it does not know where along the beam, and it knows nothing whatever
// about how that something is turned. `Detection.pose` is documented as the
// pose of the DETECTED OBJECT, so a break beam has no value to put in it.
//
// This is the same reasoning that already leaves `Detection.workpiece_id` empty
// and answers a `workpiece_type` filter with `NOT_IMPLEMENTED` — a beam reports
// that its volume is occupied and nothing about by what. Position is the third
// thing it cannot report, and it was the one being filled in anyway: with the
// SENSOR's own mounting pose, which for `beam_c1_out` stands 0.250 m off the
// belt centreline from the pick point a station reaches for.
//
// ## Absence has to be spelled out, because `PoseStamped` has no absent state
//
// It is spelled three ways, and the three are not redundant — each answers a
// different consumer.
//
//   * `header.frame_id` EMPTY — the semantic marker, and the one to test
//     against. It is the convention this very message already uses for
//     `workpiece_id`; `tf2` refuses an empty frame rather than resolving it; and
//     it is already exactly what `cite_orchestration`'s `PickAt` reads as "no
//     observation, fall back to the station's own frame".
//   * `header.stamp` ZERO — a header whose frame is unset is not a header.
//     Stamping it would date an observation that was never made.
//   * every position and orientation component NaN — the guard, for a consumer
//     that ignores the frame and reads the numbers anyway. NaN fails loudly in
//     TF and in inverse kinematics; it cannot be planned to. Zeroes cannot do
//     that job: (0, 0, 0) with an identity rotation is a perfectly real place in
//     whatever frame it is later stamped with, and this branch has already had
//     to remove one field that read as a measurement precisely because it was
//     permanently 0.0.
//
// ## What this is NOT
//
// It is not a way of saying "the pose is uncertain". A beam constrains the two
// axes across it to the beam's own width — ±0.020 m for the cell's beams — and
// leaves the third unconstrained over the beam's whole length, ±0.250 m. That
// anisotropy is a real and useful thing to report, and `Detection` cannot carry
// it: `confidence` is one scalar and is already spoken for by the detection
// itself, and there is no covariance and no field separating a measured axis
// from an inferred one. Reporting the constrained pose without the shape of its
// uncertainty would put a number that looks measured back into the same field,
// which is the defect this replaces. So until `Detection` gains
//
//   float64[36] pose_covariance   — or a `geometry_msgs/PoseWithCovariance`
//   uint8       pose_source       — UNKNOWN / MEASURED / CONSTRAINED
//   string      observed_by       — which asset saw it
//
// the honest answer is that no pose is reported at all. `cite_interfaces` is
// where those go; they are not improvised here.
//
// Nothing below branches on simulation. A physical through-beam is exactly as
// blind to position as the simulated one, and the mounting pose of a real
// sensor is exactly as much not the work-piece's pose (P2).

#ifndef CITE_SKILLS__OBSERVATION_HPP_
#define CITE_SKILLS__OBSERVATION_HPP_

#include <cmath>
#include <limits>

#include <geometry_msgs/msg/pose_stamped.hpp>

namespace cite_skills
{

/// Mark `pose` as carrying no observation, in every way the message allows.
inline void mark_pose_unobserved(geometry_msgs::msg::PoseStamped & pose)
{
  constexpr double unknown = std::numeric_limits<double>::quiet_NaN();

  pose.header.stamp.sec = 0;
  pose.header.stamp.nanosec = 0u;
  pose.header.frame_id.clear();

  pose.pose.position.x = unknown;
  pose.pose.position.y = unknown;
  pose.pose.position.z = unknown;
  // Not an identity quaternion. Identity is a rotation — "square to the frame" —
  // and asserting it is the assumption ADR-0029 records as unsafe after a grasp.
  pose.pose.orientation.x = unknown;
  pose.pose.orientation.y = unknown;
  pose.pose.orientation.z = unknown;
  pose.pose.orientation.w = unknown;
}

/// Whether `pose` carries an observation a consumer may act on.
///
/// The test a consumer should make, provided here so that the rule for reading
/// the convention lives beside the rule for writing it rather than being
/// restated — differently — at each caller.
inline bool pose_is_observed(const geometry_msgs::msg::PoseStamped & pose)
{
  if (pose.header.frame_id.empty()) {
    return false;
  }
  return std::isfinite(pose.pose.position.x) &&
         std::isfinite(pose.pose.position.y) &&
         std::isfinite(pose.pose.position.z) &&
         std::isfinite(pose.pose.orientation.x) &&
         std::isfinite(pose.pose.orientation.y) &&
         std::isfinite(pose.pose.orientation.z) &&
         std::isfinite(pose.pose.orientation.w);
}

}  // namespace cite_skills

#endif  // CITE_SKILLS__OBSERVATION_HPP_
