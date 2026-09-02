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

double gripper_discrimination_margin_m(double width_m, const GripperTravel & travel)
{
  // The SAME expression `_grasp_discrimination_margin_m` evaluates in
  // `tools/cite_tools/validate/physical.py`, on the same declared facts, and not
  // a linearisation of it. See the header for why the two are one derivation
  // rather than two answers, and for what pins them together.
  const double towards_closed = travel.closed_position >= travel.open_position ? 1.0 : -1.0;
  const double position = gripper_position_for(width_m, travel);
  const double biased = position + towards_closed * 2.0 * travel.goal_tolerance;
  return std::abs(gripper_width_for(position, travel) - gripper_width_for(biased, travel));
}

GraspWidth resolve_grasp_width(
  double requested_m, double configured_default_m, const WorkpieceWidths & parts,
  const GripperTravel & travel)
{
  const auto resolved = [&]() -> GraspWidth {
      if (requested_m > 0.0) {
        return GraspWidth{requested_m, GraspWidthSource::Goal};
      }
      if (configured_default_m > 0.0) {
        return GraspWidth{configured_default_m, GraspWidthSource::Default};
      }
      return GraspWidth{0.0, GraspWidthSource::Unknown};
    }();

  if (resolved.source == GraspWidthSource::Unknown) {
    return resolved;
  }
  // No declared part means no bound to apply, not a bound of zero. The state is
  // refused at L0 rather than invented here.
  if (parts.narrowest_m <= 0.0) {
    return resolved;
  }
  // A grasp is evidenced by FAILING to reach where the jaws were sent, and a
  // command this close to the part terminates on the controller's own
  // goal-tolerance branch instead — which the predicate below reports as empty
  // by its first condition, with the part in the jaws. Refused rather than
  // executed and then judged. See the header for what this costs.
  if (parts.narrowest_m - resolved.width_m <
    gripper_discrimination_margin_m(resolved.width_m, travel))
  {
    return GraspWidth{resolved.width_m, GraspWidthSource::Refused};
  }
  return resolved;
}

bool gripper_is_holding(
  const GripperReport & report, const GripperTravel & travel,
  const WorkpieceWidths & parts)
{
  if (!report.stalled || report.reached_goal) {
    return false;
  }
  // No declared part is no reference at all, and a window around zero would
  // admit a fully closed gripper. Refused at L0; answered honestly here.
  if (parts.narrowest_m <= 0.0 || parts.widest_m <= 0.0) {
    return false;
  }
  // Where the joint actually stopped, against where a part THIS FACILITY
  // HANDLES would have stopped it. `report.commanded_width_m` is deliberately
  // not read: it is a policy value, and the error is about where the part is.
  // See the header — judging against the command is the defect ADR-0052 records.
  const double reached_width_m = gripper_width_for(report.reached_position, travel);
  return reached_width_m > parts.narrowest_m - travel.stall_band_narrow_m &&
         reached_width_m < parts.widest_m + travel.stall_band_wide_m;
}

}  // namespace cite_skills
