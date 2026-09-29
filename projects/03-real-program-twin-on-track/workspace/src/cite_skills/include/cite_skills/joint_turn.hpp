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

// Choosing between joint angles that are the same tool pose.
//
// Separated from the skill server, and stated in plain doubles, so that the
// rule can be tested without a planner, a robot model or a simulator — the
// same treatment `approach.hpp` and `pose_goal.hpp` get, and for the reason
// `cross-cutting-testing.md` gives: push the test down to the arithmetic.
//
// Nothing in this header knows what a joint is. It is told a value, a
// reference, and the interval the value is allowed to live in.

#ifndef CITE_SKILLS__JOINT_TURN_HPP_
#define CITE_SKILLS__JOINT_TURN_HPP_

namespace cite_skills
{

//: One whole revolution, in radians. The quantity a revolute joint may be
//: shifted by without moving any link it carries.
//:
//: Exposed rather than kept private to the implementation because the adapter
//: in the skill server needs the same quantity to VERIFY a rewrite — every
//: joint it changed must have moved by a whole number of these — and to say in
//: a log line which whole-turn angle the bounds refused. Two statements of a
//: turn would be a value written twice (P1), and the one that drifted would be
//: the one nothing runs.
constexpr double kWholeTurnRad = 2.0 * 3.14159265358979323846;

/// `value` shifted by whole turns to sit as near `reference` as the bounds allow.
///
/// ## What this is for
///
/// A joint declared over more than one revolution — `joint1` and `joint5` on
/// this arm are `[-2*pi, +2*pi]` — reaches every tool pose at more than one
/// angle, and the angles differ by whole multiples of `2*pi`. They are the SAME
/// tool pose: a revolute joint turned a whole turn puts every link back where
/// it was. An IK solver is free to return either, and this one returns whichever
/// its own seed happened to land near, so a reachable pose was being reached at
/// `joint1 = 5.253 rad` where `-1.030 rad` is the identical pose — a 301 degree
/// sweep in place of a 59 degree one, measured on the running cell.
///
/// ## The rule
///
/// Among `value + 2*pi*k` for integer `k`, return the one nearest `reference`
/// that still lies within `[lower, upper]`. If no shift is both nearer and in
/// bounds, return `value` unchanged.
///
/// ## Three properties that are the whole of it
///
/// * **THIS FUNCTION NEVER PUTS AN ANGLE OUTSIDE `[lower, upper]`.** A nearer
///   angle outside the interval is refused, not clamped. This is the safety
///   invariant: the interval is the joint's declared limit, and an angle
///   outside it is one the planner rejects and the hardware would refuse — or
///   worse, one nothing checks.
///
///   Stated that precisely because the shorter wording — *the bounds are never
///   left* — was **false as written**, and it stood here unqualified while an
///   input more than a whole turn outside the interval came back with an
///   out-of-bounds answer. Exactly: **every return is either `value` itself or
///   a whole-turn shift of `value` that lies inside `[lower, upper]`.** A
///   `value` handed in already outside the interval — `setFromIK` can produce
///   one — comes back either unchanged or pulled INTO the interval, never
///   pushed further out and never clamped to a limit.
/// * **A span of `2*pi` or less is inert**, whatever the inputs. There is no
///   second solution inside such an interval, so shifting could only leave it.
///   That is also why the caller does not have to test the span itself.
/// * **IT REACHES PAST THE FIRST TURN.** A `[-2*pi, +2*pi]` joint admits `k` in
///   `{-2, -1, 0, 1, 2}`, and the nearest in-bounds shift can be two turns
///   away. A single `+/- 2*pi` comparison gets the common case right and the
///   far one wrong. It does not WALK there: the shift is computed, so no input
///   makes the search long and none makes it fail to end.
///
/// Ties go to the smaller shift, so `value` itself wins every tie it is in and
/// a joint is never turned to buy nothing. `nearest_turn` is idempotent: its own
/// output is already the nearest in-bounds member of the family.
///
/// Non-finite bounds are treated as no bounds at all and the value is returned
/// unchanged. An interval nobody stated is not a licence to shift: the interval
/// is the whole of what makes a shift safe, and a joint that genuinely has none
/// is a CONTINUOUS one, whose second solution is the same solution.
double nearest_turn(double value, double reference, double lower, double upper);

}  // namespace cite_skills

#endif  // CITE_SKILLS__JOINT_TURN_HPP_
