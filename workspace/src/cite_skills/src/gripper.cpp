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

#include "cite_skills/gripper.hpp"

#include <algorithm>
#include <cmath>

namespace cite_skills
{
namespace
{

/// Half the opening the crank swings about: the drive pivot, less the pad inset.
double pivot_m(const GripperTravel & travel)
{
  return travel.drive_pivot_y_m - travel.pad_inset_m;
}

/// The crank the finger joint's offset forms, and where it starts. Writing the
/// linkage as one cosine rather than a sine and a cosine is what makes the
/// inverse a single `acos` instead of a numerical solve.
double crank_m(const GripperTravel & travel)
{
  return std::hypot(travel.finger_offset_y_m, travel.finger_offset_z_m);
}

double phase_rad(const GripperTravel & travel)
{
  return std::atan2(travel.finger_offset_z_m, travel.finger_offset_y_m);
}

}  // namespace

double gripper_width_for(double position, const GripperTravel & travel)
{
  return 2.0 * (pivot_m(travel) + crank_m(travel) * std::cos(position + phase_rad(travel)));
}

double gripper_position_for(double width_m, const GripperTravel & travel)
{
  const double crank = crank_m(travel);
  if (crank <= 0.0) {
    return travel.closed_position;
  }
  // Clamped before `acos`, not after: a width outside the linkage's reach is a
  // caller error, but returning NaN would propagate it into a joint command.
  const double cosine = std::clamp((width_m / 2.0 - pivot_m(travel)) / crank, -1.0, 1.0);
  const double position = std::acos(cosine) - phase_rad(travel);

  const double lower = std::min(travel.open_position, travel.closed_position);
  const double upper = std::max(travel.open_position, travel.closed_position);
  return std::clamp(position, lower, upper);
}

double gripper_max_width_m(const GripperTravel & travel)
{
  return gripper_width_for(travel.open_position, travel);
}

double gripper_min_width_m(const GripperTravel & travel)
{
  return gripper_width_for(travel.closed_position, travel);
}

double gripper_pad_plane_offset_m(double position, const GripperTravel & travel)
{
  // The constant term is derived, never carried: the campaign's 0.0718988 m is
  // these three dimensions, and a fourth field holding their sum would be a
  // second place for one fact to live.
  const double axial_reach_m =
    travel.tip_link_z_m - travel.drive_pivot_z_m - travel.pad_face_centre_z_m;
  return axial_reach_m - crank_m(travel) * std::sin(position + phase_rad(travel));
}

double gripper_width_tolerance_m(double position, const GripperTravel & travel)
{
  // d(opening)/dq = -2 * crank * sin(q + phase). Magnitude only: the tolerance is
  // a distance either side of where the joint stopped, and its sign is not one.
  const double slope = 2.0 * crank_m(travel) * std::sin(position + phase_rad(travel));
  return std::abs(slope * travel.goal_tolerance);
}

GraspWidth resolve_grasp_width(double requested_m, double configured_default_m)
{
  if (requested_m > 0.0) {
    return GraspWidth{requested_m, GraspWidthSource::Goal};
  }
  if (configured_default_m > 0.0) {
    return GraspWidth{configured_default_m, GraspWidthSource::Default};
  }
  return GraspWidth{0.0, GraspWidthSource::Unknown};
}

bool gripper_is_holding(const GripperReport & report, const GripperTravel & travel)
{
  if (!report.stalled || report.reached_goal) {
    return false;
  }
  // Read where the joint actually stopped, then ask whether that is further open
  // than commanded by more than the controller's own end-of-goal bias can
  // account for. See the header: a bare `>` here is true in free air.
  const double reached_width_m = gripper_width_for(report.reached_position, travel);
  const double margin_m = reached_width_m - report.commanded_width_m;
  return margin_m > 2.0 * gripper_width_tolerance_m(report.reached_position, travel);
}

}  // namespace cite_skills
