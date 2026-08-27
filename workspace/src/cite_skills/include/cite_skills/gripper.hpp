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

// End-effector arithmetic: task-space widths against the gripper's own units.
//
// Separated from the skill server so the mapping is tested without a controller.
// A unit confusion here is silent — `GripperCommand.position` is passed straight
// to the drive joint, so for a revolute drive a width in metres is commanded as
// an angle, and 0.085 is a perfectly valid angle.

#ifndef CITE_SKILLS__GRIPPER_HPP_
#define CITE_SKILLS__GRIPPER_HPP_

namespace cite_skills
{

/// The gripper's travel and the linkage that turns it into an opening. Every
/// field comes from the end-effector type in the L0 model, delivered by the
/// generated bring-up plan; nothing here invents one.
struct GripperTravel
{
  double open_position{0.0};
  double closed_position{0.85};

  /// The seven dimensions of the parallel linkage — four that open the jaws, and
  /// three more that place the pad face on the tool axis. See
  /// `gripper_width_for` and `gripper_pad_plane_offset_m`.
  double drive_pivot_y_m{0.035};
  double drive_pivot_z_m{0.059098};
  double finger_offset_y_m{0.035465};
  double finger_offset_z_m{0.042039};
  double pad_inset_m{0.026};
  double tip_link_z_m{0.172};
  double pad_face_centre_z_m{0.041003};

  /// The gripper controller's own `goal_tolerance`, in drive-joint units. Not a
  /// property of the mechanism but of how the controller decides a goal is done,
  /// which `gripper_is_holding` has to account for.
  double goal_tolerance{0.01};
};

/// What opening a reported drive position corresponds to, in metres.
///
///     opening(q) = 2 * (drive_pivot_y - pad_inset
///                       + finger_offset_y*cos(q) - finger_offset_z*sin(q))
///
/// Exact, not a fit. The drive joint rotates the outer knuckle about +x and the
/// finger joint mimics it about -x, so the two rotations cancel: the pad stays
/// parallel to the tool axis and only translates, and its distance from the
/// centreline is the rotated finger offset plus the drive pivot, less the pad's
/// own inset. Doubled, because there are two jaws.
///
/// This replaced a linear interpolation across the stroke. That was not a
/// harmless simplification: it read 85.00 mm fully open against a true 88.93 mm,
/// and 45.00 mm at q=0.400 against a true 50.59 mm — an error the size of the
/// entire clearance a 50 mm grasp works within, which is why the gripper spent
/// Phase 1.C closing on air while every layer above reported success.
///
/// This is also what makes `Grasp.Result.reached_width_m` a measurement rather
/// than the request echoed back — the two differ by the object's width whenever
/// the gripper stalls on something, which is the case that matters.
double gripper_width_for(double position, const GripperTravel & travel);

/// The inverse: the drive position that opens the pads to `width_m`.
///
/// Clamped to the gripper's own travel, so a width it cannot reach becomes the
/// nearest end of the stroke rather than a NaN out of `acos`.
double gripper_position_for(double width_m, const GripperTravel & travel);

/// The widest and narrowest the pads go, derived from the travel and linkage.
///
/// Derived rather than configured. A declared maximum would be the same fact in
/// a second place, and when it was one it disagreed with the linkage.
double gripper_max_width_m(const GripperTravel & travel);
double gripper_min_width_m(const GripperTravel & travel);

/// How far PROXIMAL of the planning tip link the centre of the pad face sits, at
/// drive position `position`, in metres.
///
///     offset(q) = tip_link_z - drive_pivot_z - pad_face_centre_z
///                 - (finger_offset_y*sin(q) + finger_offset_z*cos(q))
///
/// The same crank as `gripper_width_for`, projected along the tool axis instead
/// of across it — hence a sine where that has a cosine. Both come from one
/// translation of the finger link, so they cannot disagree.
///
/// ---------------------------------------------------------------------------
/// WHY A SKILL MUST NOT PLAN AN OBJECT'S POSE TO THE TIP LINK.
///
/// `link_tcp`, which `planning.tip_link_suffix` names and which every skill here
/// plans to, is the FINGERTIP plane. The pads grip with their faces, whose centre
/// sits this far back up the tool axis. A `Pick` that sent `object_pose` straight
/// to the planner therefore parked the pad face above the object by exactly this
/// much, and the 40-trial interleaved campaign in
/// `docs/measurements/2026-08-25-grasp-plane-offset/` measured what that costs:
/// 19.3 mm of a 37.5 mm pad face engaged, the contact patch 15.35 mm off the
/// part's centre of mass, and a couple that rotated the work-piece past 20
/// degrees in 12 of 20 trials. Corrected, 0 of 20, p < 0.0001.
///
/// NOT A CONSTANT. It runs from 29.86 mm fully open to 18.58 mm at the 45 mm
/// default grasp — 11.3 mm across the stroke. A deleted `grasp` frame in the L0
/// model once declared a single 0.172 m for this and was wrong twice over: that
/// is the fingertip, and no single number can be right at more than one width.
/// ---------------------------------------------------------------------------
///
/// Planning-side and therefore identical on hardware (P2): it is arithmetic on
/// the end effector's declared geometry, and reads nothing from the simulator.
double gripper_pad_plane_offset_m(double position, const GripperTravel & travel);

/// How much apparent width the controller's `goal_tolerance` is worth at
/// `position`, in metres.
///
/// The opening is not linear in the drive angle, so the tolerance is worth a
/// different number of millimetres at each point of the stroke; this evaluates it
/// where the gripper actually stopped rather than assuming a constant.
double gripper_width_tolerance_m(double position, const GripperTravel & travel);

/// Where a commanded grasp width came from.
enum class GraspWidthSource
{
  Goal,      ///< The caller asked for a specific width.
  Default,   ///< Resolved from the configured end-effector default.
  Unknown,   ///< Nothing supplied one; the caller must say so rather than assume.
};

struct GraspWidth
{
  double width_m{0.0};
  GraspWidthSource source{GraspWidthSource::Unknown};
};

/// Resolve the width a `Pick` should close to.
///
/// `Pick.Goal.grasp_width_m` documents "0 means use the object type's default",
/// so zero is a request for a default and not a request to close completely.
/// `configured_default_m` is that default as delivered by configuration; when it
/// is also unset the width is `Unknown`, and the skill closes against its effort
/// limit *and says so* rather than silently reporting a resolved width it never
/// had.
GraspWidth resolve_grasp_width(double requested_m, double configured_default_m);

/// What the gripper controller reported at the end of one close.
///
/// `GripperCommand.Result` alongside the width that was asked for, because
/// neither means anything on its own. `reached_position` is kept in the drive
/// joint's own units exactly as the controller reported it, rather than as a
/// width: the width is derived from it through `gripper_width_for`, and storing
/// both would be one fact in two places, free to disagree after an edit to the
/// linkage.
struct GripperReport
{
  double commanded_width_m{0.0};
  double reached_position{0.0};
  bool stalled{false};
  bool reached_goal{false};
};

/// Whether the gripper is holding something, judged from what it reported.
///
/// This is the "real width check" ADR-0022 names as `Grasp`'s own work, and it
/// is deliberately not `stalled` on its own. A stall says the joint stopped short
/// of its command and then stopped moving; it does not say *why*. A gripper that
/// jams, or one whose fingers foul each other, stalls just as truthfully as one
/// holding a part.
///
/// Two independent signals have to agree, and each covers the other's blind spot.
///
///   1. The goal was NOT reached. A gripper closing on nothing arrives where it
///      was sent. One stopped by a part never gets there. This needs no threshold
///      at all, which is exactly why it is here: it cannot be miscalibrated.
///   2. The pads stopped WIDER than commanded, by more than the controller's own
///      end-of-goal bias. A closing command travels from open towards closed, so
///      stopping on the open side of the commanded width means something occupies
///      the space between the pads.
///
/// ---------------------------------------------------------------------------
/// DO NOT SIMPLIFY THE MARGIN AWAY. It is the whole point of this function.
///
/// The obvious predicate — `reached_width_m > commanded_width_m` — is TRUE IN
/// FREE AIR, and this was shipped and measured before anyone noticed.
/// `GripperActionController` ends a goal the instant `|error| < goal_tolerance`,
/// so the position it reports is systematically short of the command, which
/// through the map above reads as *phantom width* that was never there:
///
///     free air, commanded 45.0 mm   ->  reports 45.85 mm   (+0.85 mm, no part)
///     50 mm part, commanded 45.0 mm ->  reports 50.00 mm   (+5.00 mm, a part)
///
/// A bare `>` calls both of those a grasp. The margin must therefore clear the
/// bias, not merely be positive. `goal_tolerance` is worth about 1.05 mm of
/// width here, so requiring twice it separates 0.85 mm from 5.00 mm with roughly
/// 2.4x of headroom on each side.
///
/// The factor of two, and not some other number: one tolerance is the largest
/// bias the controller can produce, so anything above it is real; doubling it
/// buys margin against the position being sampled a cycle early. It is derived
/// from the declared tolerance rather than written as a millimetre count, so a
/// gripper configured with a looser tolerance widens this automatically instead
/// of quietly reporting phantom grasps.
/// ---------------------------------------------------------------------------
///
/// Identical on hardware. It reads only fields `GripperCommand.Result` carries on
/// both paths, and asks a question about the mechanism rather than about the
/// simulator (P2).
bool gripper_is_holding(const GripperReport & report, const GripperTravel & travel);

}  // namespace cite_skills

#endif  // CITE_SKILLS__GRIPPER_HPP_
