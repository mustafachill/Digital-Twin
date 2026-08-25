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

/// The gripper's travel and what opening it corresponds to. All three come from
/// the end-effector type in the L0 model; nothing here invents one.
struct GripperTravel
{
  double open_position{0.0};
  double closed_position{0.85};
  double max_width_m{0.085};
};

/// A task-space opening in metres, in the gripper's own command units.
///
/// Linear across the stroke. That is an approximation for a linkage gripper —
/// the true relation is not linear — but it is a stated approximation with the
/// numbers in the model, rather than a unit confusion in the code.
double gripper_position_for(double width_m, const GripperTravel & travel);

/// The inverse: what opening a reported drive position corresponds to.
///
/// This is what makes `Grasp.Result.reached_width_m` a measurement rather than
/// the request echoed back — the two differ by exactly the object's width
/// whenever the gripper stalls on something, which is the case that matters.
double gripper_width_for(double position, const GripperTravel & travel);

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

}  // namespace cite_skills

#endif  // CITE_SKILLS__GRIPPER_HPP_
