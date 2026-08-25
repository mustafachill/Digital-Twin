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

/// What the gripper controller reported at the end of one close.
///
/// `GripperCommand.Result` in task-space terms, with the width that was asked
/// for kept alongside the width that came back — because neither number means
/// anything on its own.
struct GripperReport
{
  double commanded_width_m{0.0};
  double reached_width_m{0.0};
  bool stalled{false};
  bool reached_goal{false};
};

/// Whether the gripper is holding something, judged from what it reported.
///
/// This is the "real width check" ADR-0022 names as `Grasp`'s own work, and it
/// is deliberately not `stalled` on its own. A stall says the joint stopped
/// short of its command and then stopped moving; it does not say *why*. A
/// gripper that jams, or one whose fingers foul each other, stalls just as
/// truthfully as one holding a part, and `stalled` alone reports both as a
/// successful grasp.
///
/// What distinguishes them is *where* it stopped. A closing command travels from
/// open towards closed, so the only way to stall on the open side of the width
/// that was commanded is for something to occupy the space between the pads. The
/// part's own width is what holds the joint there. Stalling at or beyond the
/// commanded width means nothing was in the way — the gripper closed on itself.
///
/// No tolerance term is needed, and adding one would be a second place to get a
/// number wrong: the controller only reports a stall once the position error has
/// exceeded its own `goal_tolerance`, so a stall already guarantees a margin.
/// The one thing it does not tell us is the sign, and the sign is the answer.
///
/// Identical on hardware. It reads only fields `GripperCommand.Result` carries on
/// both paths, and asks a question about the mechanism rather than about the
/// simulator (P2).
bool gripper_is_holding(const GripperReport & report);

}  // namespace cite_skills

#endif  // CITE_SKILLS__GRIPPER_HPP_
