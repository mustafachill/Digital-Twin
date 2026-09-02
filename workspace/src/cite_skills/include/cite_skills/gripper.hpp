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
  /// property of the mechanism but of how the controller decides a goal is done.
  ///
  /// `gripper_is_holding` no longer reads it (ADR-0052 option F): the window it
  /// judges a stall inside is declared, not derived from this. What still reads
  /// it is `gripper_discrimination_margin_m`, which is the same policy the
  /// validator applies to the declared default, applied here to a width the
  /// caller supplied.
  double goal_tolerance{0.01};

  /// How far NARROWER and WIDER than a declared part a genuine stall on that
  /// part may land and still be a grasp, in metres between the pads.
  ///
  /// Declared on the L0 end-effector type and delivered by the generated
  /// bring-up plan (ADR-0052 §A.6). ZERO MEANS "NOT SUPPLIED" and is a sentinel
  /// rather than a band: a zero-width window admits nothing, so a skill server
  /// that never received these refuses to configure rather than reporting every
  /// grasp empty. Nothing here invents one.
  double stall_band_narrow_m{0.0};
  double stall_band_wide_m{0.0};
};

/// How wide the parts this FACILITY handles are, as one interval.
///
/// The reference `gripper_is_holding` judges a stall against, delivered at
/// facility level by the generated bring-up plan (ADR-0052 §A.4).
///
/// AN INTERVAL, AND NEVER WHICH PART, and that is a decision rather than a
/// simplification (§A.5). `Pick.Goal.workpiece_id` is an instance id minted by
/// L4's registry and no map from one to an L0 work-piece type exists anywhere in
/// this repository, so no per-part rule is buildable today — and building one
/// would put "which part am I picking" inside a skill P9 requires to be
/// replaceable without touching orchestration. This keeps L3 knowing only the
/// RANGE of part widths the facility handles, which is a fact about the facility
/// and not about the goal, so a second part changes data and not code.
///
/// WHAT IT COSTS. The discrimination IS the width of the admitting window, and
/// the window widens with the declared spread: a facility declaring a 20 mm part
/// beside an 80 mm one gets a window every stall in that range falls inside.
/// That is not left to be noticed — `stall-band-admits-a-stall-on-nothing` in
/// `cite_tools.validate.physical` refuses such a model, and §A.5 is what it says
/// to reopen.
///
/// Both zero means "not supplied", the same sentinel `GripperTravel`'s band
/// carries and for the same reason.
struct WorkpieceWidths
{
  double narrowest_m{0.0};
  double widest_m{0.0};
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

/// How much narrower than a part a commanded width has to be before a close on
/// that part can evidence anything, in metres.
///
/// ---------------------------------------------------------------------------
/// ONE POLICY, TWO LANGUAGES, ONE DERIVATION — and this comment is half of what
/// keeps it that way. The other half is `_grasp_discrimination_margin_m` in
/// `tools/cite_tools/validate/physical.py`, which computes this same quantity
/// for the DECLARED default and refuses a model whose default does not clear it.
/// This computes it for whatever width a caller actually supplied, and refuses
/// the goal. ADR-0052 §A.7 required the factor of two to be given one home or
/// for both places to say why they are different quantities; they are not
/// different quantities, so this is the one home, stated twice because no
/// mechanism in this repository shares an expression between C++ and Python.
///
/// It is the SAME EXPRESSION and not a paraphrase: the position the width
/// commands, biased by two goal tolerances towards `closed_position`, and the
/// opening at each read back through the linkage. That is deliberately NOT
/// `2 * gripper_width_tolerance_m`, which linearises the map — the two differ by
/// 0.005 mm at the shipped 45 mm command, immaterial at this gripper's scale and
/// still two answers to one question, which is what §A.7 forbids.
/// `GripperDiscrimination.MatchesTheValidatorsOwnDerivation` pins the number the
/// validator computes, so a change to either without the other fails a test
/// rather than drifting.
///
/// (ADR-0052 §A.11 records the two arithmetics as 0.017 mm apart. That is a
/// DIFFERENT quantity and both are right: it compares the validator's floor at
/// the commanded width against the old predicate's FIXED POINT, which evaluated
/// the tolerance at the position the jaws REACHED rather than at the one they
/// were sent to. Under F nothing evaluates it at the reached position any more,
/// so the only remaining gap is the 0.005 mm above.)
/// ---------------------------------------------------------------------------
///
/// WHY TWO TOLERANCES AND NOT ONE. `GripperActionController` ends a goal the
/// instant `|error| < goal_tolerance`, so a command within one tolerance of the
/// part terminates on that branch, reports `reached_goal`, and evidences
/// nothing whatever the jaws hold. One tolerance is what that argument needs;
/// the second is margin against the position being sampled a cycle early, and it
/// is kept rather than halved because halving it would loosen a bound by about a
/// millimetre on a question nothing has measured (ADR-0052 §A.7).
double gripper_discrimination_margin_m(double width_m, const GripperTravel & travel);

/// Where a commanded grasp width came from, or why it was refused.
enum class GraspWidthSource
{
  Goal,      ///< The caller asked for a specific width.
  Default,   ///< Resolved from the configured end-effector default.
  Unknown,   ///< Nothing supplied one; the caller must say so rather than assume.
  /// The width resolved, and it does not clear the narrowest declared part by
  /// enough for the close to evidence anything (ADR-0052 §A.8). A TYPED refusal
  /// rather than a width that is executed and then judged: the close would end
  /// on the controller's goal-tolerance branch, `reached_goal` would be true,
  /// and the predicate would report empty by its first condition with the part
  /// in the jaws — a false negative by a route no band can catch.
  Refused,
};

struct GraspWidth
{
  double width_m{0.0};
  GraspWidthSource source{GraspWidthSource::Unknown};
};

/// Resolve the width a `Pick` should close to, and refuse one that cannot work.
///
/// `Pick.Goal.grasp_width_m` documents "0 means use the object type's default",
/// so zero is a request for a default and not a request to close completely.
/// `configured_default_m` is that default as delivered by configuration; when it
/// is also unset the width is `Unknown`, and the skill closes against its effort
/// limit *and says so* rather than silently reporting a resolved width it never
/// had.
///
/// ---------------------------------------------------------------------------
/// THE CALLER'S WIDTH IS CHECKED, AND THAT IS NEW (ADR-0052 §A.8).
///
/// ADR-0052's option F stops the predicate reading the commanded width, which
/// closes one half of a door the 2026-09-01 campaign demonstrated: a
/// caller-supplied width can no longer move the band, because there is no band
/// keyed to the command. The other half is a different failure and stays open
/// without this. A width that is too WIDE — too close to the part, or wider than
/// it — ends the close on `GripperActionController`'s goal-tolerance branch;
/// `reached_goal` comes back true; and F reports empty by its first condition
/// with the part in the jaws. No window catches that, because the stall the
/// window judges never happens.
///
/// So a resolved width from EITHER SOURCE that does not clear
/// `parts.narrowest_m` by `gripper_discrimination_margin_m` is `Refused`. One
/// policy, two layers, one number: the validator applies the identical bound to
/// the declared default at model time, and this applies it to whatever a goal
/// supplied at call time. Nothing validates a goal-supplied width anywhere else.
///
/// ITS COST IS REAL AND IS NOT HIDDEN. On the shipped model this refuses a
/// goal-supplied 48.0 mm, and the campaign shows this cell handles 48.0 mm — all
/// seven of those trials stalled and none reached goal. The refusal is
/// conservative in the direction that fails safe, and what would justify
/// relaxing it to one tolerance is that campaign's own 47.0 and 48.0 mm columns
/// re-run at an n large enough to resolve 0.1 mm.
///
/// A zero-width part means "the facility declared none", and then there is no
/// bound to apply and nothing is refused — the model-time rule
/// `workpiece-width-unstated-for-a-grasping-facility` is what refuses that
/// state, before a plan exists.
/// ---------------------------------------------------------------------------
GraspWidth resolve_grasp_width(
  double requested_m, double configured_default_m, const WorkpieceWidths & parts,
  const GripperTravel & travel);

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
///     holding  <=>  stalled
///                   and not reached_goal
///                   and w_reached  >  narrowest - stall_band_narrow_m
///                   and w_reached  <  widest    + stall_band_wide_m
///
/// Two independent kinds of signal have to agree, and each covers the other's
/// blind spot.
///
///   1. The goal was NOT reached, and the joint stopped. A gripper closing on
///      nothing arrives where it was sent. One stopped by a part never gets
///      there. This needs no threshold at all, which is exactly why it is here:
///      it cannot be miscalibrated.
///   2. The pads stopped where A PART THIS FACILITY HANDLES would stop them —
///      inside a declared window around the interval of declared part widths.
///
/// ---------------------------------------------------------------------------
/// DO NOT JUDGE THIS AGAINST THE COMMANDED WIDTH. THAT WAS THE DEFECT.
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
/// The fix that followed — demand a margin of twice the controller's tolerance
/// ABOVE the command — separated those two, and was wrong in a way that took a
/// campaign to see: THE COMMAND IS A POLICY VALUE AND THE ERROR IS ABOUT WHERE
/// THE PART IS. Both directions were then measured (ADR-0052, and the campaign
/// it cites): a real grasp reported empty, witnessed by the work-piece's own
/// contact sensor, and a stall on nothing reported as a grasp.
///
/// SO THE REFERENCE MOVED TO THE PART, AND THE FREE-AIR CASE IS STILL REJECTED
/// — by a bound that does not move when the command does. On this facility's
/// 50 mm part with the shipped band the window is [47.615, 52.385] mm, and the
/// measured free-air settle at 45.852 mm falls BELOW it. It falls below it at
/// every command, which is the property the old form did not have.
///
/// WHY THE BAND IS DECLARED AND NOT DERIVED FROM `goal_tolerance`. Reusing
/// `2 * gripper_width_tolerance_m` as the window is the tempting form: it needs
/// no new declaration, it is already delivered, and on the shipped values it
/// brackets the measured distribution. It is rejected because that window
/// *widens* as the declared tolerance loosens, which INVERTS THE SAFETY
/// DIRECTION. At a `goal_tolerance` of 0.02 rad — twice the shipped value — the
/// derived window on a 50 mm part is [45.79, 54.21] mm, and it ADMITS the
/// 45.852 mm free-air settle this block exists to reject. A threshold whose
/// direction flips with an unrelated setting is a coincidence, not a derivation.
/// `GripperHolding.DoesNotWidenItsWindowWhenTheControllerToleranceIsLooser`
/// asserts exactly that, and replaces the test that asserted the inverse.
///
/// NEITHER EDGE MAY BE WIDENED TO MAKE A RUN PASS. The narrow edge sits inside a
/// measured interval whose lower bound is "a real grasp reads empty" and whose
/// upper bound is "a stall on nothing reads as a grasp"; there is no slack in it
/// that is not one of those two failures. The wide edge has no measurement
/// behind it at all and nothing has ever exercised it (ADR-0052 §A.9.5).
/// ---------------------------------------------------------------------------
///
/// `parts` with both widths at zero means the facility declared none, and then
/// there is no reference: this returns false rather than guessing, and the
/// caller has already refused to configure. That state is refused at L0 by
/// `workpiece-width-unstated-for-a-grasping-facility`.
///
/// Identical on hardware. It reads only fields `GripperCommand.Result` carries on
/// both paths — and FEWER of them than it used to, since the commanded width has
/// left the decision — and asks a question about the mechanism rather than about
/// the simulator (P2). The band is one declaration serving both sides (ADR-0041):
/// if the two ever need different values that is a P2 finding and an ESCALATE,
/// never a branch here.
bool gripper_is_holding(
  const GripperReport & report, const GripperTravel & travel,
  const WorkpieceWidths & parts);

}  // namespace cite_skills

#endif  // CITE_SKILLS__GRIPPER_HPP_
