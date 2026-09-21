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

// Choosing between joint angles that are the same tool pose. Pure arithmetic,
// tested without a planner, a robot model or a simulator.
//
// Every case below pins a property a plausible reimplementation gets wrong. The
// dangerous one is the second block: a version that clamps instead of refusing,
// or that normalises into `[-pi, pi]` the way a hundred tutorials do, passes the
// first block and hands the planner an angle outside the joint's declared limit.

#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#include "cite_skills/joint_turn.hpp"

namespace
{

constexpr double kTurn = 2.0 * M_PI;

//: Whole turns of a double are exact enough that the only error here is the
//: subtraction itself.
constexpr double kTolerance = 1e-12;

//: The arm this was measured on. `joint1` and `joint5` are declared over two
//: whole revolutions, which is what gives every pose a wound twin.
constexpr double kWideLower = -kTurn;
constexpr double kWideUpper = kTurn;

}  // namespace

// -----------------------------------------------------------------------------
// The case this exists for, measured on the running cell
// -----------------------------------------------------------------------------

TEST(JointTurn, TakesTheShortWayRoundTheMeasuredPlacePose)
{
  // The arm reached a place pose at joint1 = 5.253 rad (301 degrees) with the
  // joint standing at 1.007 rad. `5.253 - 2*pi` is -1.030 rad: the identical
  // tool pose, 59 degrees away instead of 244.
  EXPECT_NEAR(
    cite_skills::nearest_turn(5.253, 1.007, kWideLower, kWideUpper),
    5.253 - kTurn, kTolerance);
}

TEST(JointTurn, TurnsUpwardsAsReadilyAsDownwards)
{
  // The same defect with the sign reversed. A one-directional fix — "subtract a
  // turn when the angle is large" — passes the case above and leaves this one.
  EXPECT_NEAR(
    cite_skills::nearest_turn(-5.743, 0.0, kWideLower, kWideUpper),
    -5.743 + kTurn, kTolerance);
}

// -----------------------------------------------------------------------------
// The safety invariant: the interval given is never left
// -----------------------------------------------------------------------------

TEST(JointTurn, RefusesANearerAngleThatWouldLeaveTheBounds)
{
  // -3.0 against a reference of 3.0 is 6.0 rad away, and +3.283 is 0.283 rad
  // away — but +3.283 is outside the joint's declared upper limit, so the far
  // angle is the only legal one. Refused, NOT clamped to the limit: clamping
  // would return 3.0, which is a different tool pose and a silent lie about
  // where the arm is going.
  //
  // The span here is 7.0 rad, wider than a turn, so the inert-span rule below
  // is not what produces this answer.
  EXPECT_NEAR(cite_skills::nearest_turn(-3.0, 3.0, -4.0, 3.0), -3.0, kTolerance);
}

TEST(JointTurn, RefusesANearerAngleBelowTheLowerBound)
{
  // The same refusal downwards. Bounds are two numbers and a fix that respects
  // one of them looks correct until the joint is asked to turn the other way.
  EXPECT_NEAR(cite_skills::nearest_turn(3.0, -3.0, -3.0, 4.0), 3.0, kTolerance);
}

TEST(JointTurn, AcceptsTheNearerAngleWhenItIsInsideAnAsymmetricInterval)
{
  // The control for the two refusals above. Identical shape, bounds widened by
  // half a radian, and now the shift is legal — so the refusals are the bounds
  // doing work and not the function declining to shift anything.
  EXPECT_NEAR(cite_skills::nearest_turn(-3.0, 3.0, -4.0, 3.5), -3.0 + kTurn, kTolerance);
}

// -----------------------------------------------------------------------------
// A joint that cannot have a second solution is left alone
// -----------------------------------------------------------------------------

TEST(JointTurn, AJointSpanningOneTurnOrLessIsInert)
{
  // `[-pi, pi]` spans exactly one turn, so every shift leaves it by
  // construction. The boundary is `<=`, and a `<` would admit a shift that
  // lands exactly on a limit — an angle the planner is entitled to reject.
  EXPECT_NEAR(cite_skills::nearest_turn(-3.0, 3.0, -M_PI, M_PI), -3.0, kTolerance);
  EXPECT_NEAR(cite_skills::nearest_turn(3.0, -3.0, -M_PI, M_PI), 3.0, kTolerance);
  EXPECT_NEAR(cite_skills::nearest_turn(0.5, -2.5, -M_PI, M_PI), 0.5, kTolerance);
  // Narrower than a turn, which is what most joints on this arm are.
  EXPECT_NEAR(cite_skills::nearest_turn(1.0, -1.0, -2.0, 2.0), 1.0, kTolerance);
  // Degenerate, and it must not divide by anything or loop for ever.
  EXPECT_NEAR(cite_skills::nearest_turn(0.0, 3.0, 0.0, 0.0), 0.0, kTolerance);
}

// -----------------------------------------------------------------------------
// It reaches past the first turn
// -----------------------------------------------------------------------------

TEST(JointTurn, WalksPastTheFirstTurnWhenTheSecondIsNearer)
{
  // 12.0 against 0.0 on a joint wide enough to hold it. One turn down is 5.717
  // and TWO turns down is -0.566, which is nearer. A single `+/- 2*pi` test
  // returns 5.717 and passes every other case in this file.
  EXPECT_NEAR(cite_skills::nearest_turn(12.0, 0.0, -20.0, 20.0), 12.0 - 2.0 * kTurn, kTolerance);
  // And upwards, for the same reason the sign is tested separately above.
  EXPECT_NEAR(
    cite_skills::nearest_turn(-12.0, 0.0, -20.0, 20.0), -12.0 + 2.0 * kTurn, kTolerance);
}

TEST(JointTurn, StopsAtTheBoundWhileWalking)
{
  // The reach and the bounds together, which is where an off-by-one turn hides:
  // 6.0 - 2*pi is -0.283 and in bounds, 6.0 - 4*pi is -6.566 and is NOT — it is
  // 0.283 rad below the limit. The nearer of the two legal answers wins.
  EXPECT_NEAR(
    cite_skills::nearest_turn(6.0, -6.0, kWideLower, kWideUpper), 6.0 - kTurn, kTolerance);
}

// -----------------------------------------------------------------------------
// Idempotence, and the tie
// -----------------------------------------------------------------------------

TEST(JointTurn, IsIdempotent)
{
  // Applying it twice must not turn the joint twice. The values are the
  // measured case, its mirror, and a two-turn walk.
  const double cases[][2] = {{5.253, 1.007}, {-5.743, 0.0}, {12.0, 0.0}, {-3.0, 3.0}};
  for (const auto & pair : cases) {
    const double once = cite_skills::nearest_turn(pair[0], pair[1], -20.0, 20.0);
    const double twice = cite_skills::nearest_turn(once, pair[1], -20.0, 20.0);
    EXPECT_NEAR(twice, once, kTolerance) << "value " << pair[0] << " reference " << pair[1];
  }
}

TEST(JointTurn, BreaksAnExactTieByLeavingTheJointWhereItIs)
{
  // A reference exactly `pi` above the value puts `value` and `value + 2*pi` the
  // same distance away. The tie is pinned rather than left to whichever
  // comparison the implementation happens to write, because an unpinned tie is
  // a value that changes when somebody rewrites `<` as `<=` and no test notices.
  //
  // It resolves towards NOT TURNING: a shift that buys nothing should not be
  // paid for.
  EXPECT_NEAR(cite_skills::nearest_turn(0.0, M_PI, kWideLower, kWideUpper), 0.0, kTolerance);
  EXPECT_NEAR(cite_skills::nearest_turn(0.0, -M_PI, kWideLower, kWideUpper), 0.0, kTolerance);
}

TEST(JointTurn, BreaksATieBetweenTwoShiftsByTakingTheSmallerOne)
{
  // The other tie, one turn out: with the reference `3*pi` above the value, one
  // turn up and two turns up are equidistant and both beat standing still. The
  // smaller shift wins, so the joint turns as little as the answer allows.
  EXPECT_NEAR(
    cite_skills::nearest_turn(0.0, 3.0 * M_PI, -20.0, 20.0), kTurn, kTolerance);
}

// -----------------------------------------------------------------------------
// Values a robot model can hand over
// -----------------------------------------------------------------------------

TEST(JointTurn, LeavesAnUnstatedIntervalAlone)
{
  // An unbounded joint is a CONTINUOUS one, and a continuous joint's second
  // solution is the same solution — there is no limit to keep it in, so the
  // search has nothing to terminate on. The caller filters these out by type,
  // and this is the second line of that defence rather than the first.
  const double infinity = std::numeric_limits<double>::infinity();
  EXPECT_NEAR(cite_skills::nearest_turn(5.253, 1.007, -infinity, infinity), 5.253, kTolerance);
  EXPECT_NEAR(cite_skills::nearest_turn(5.253, 1.007, -infinity, kTurn), 5.253, kTolerance);
}

TEST(JointTurn, DoesNotInventAnAnswerForANonNumber)
{
  const double nan = std::numeric_limits<double>::quiet_NaN();
  EXPECT_TRUE(std::isnan(cite_skills::nearest_turn(nan, 0.0, kWideLower, kWideUpper)));
  EXPECT_NEAR(cite_skills::nearest_turn(5.253, nan, kWideLower, kWideUpper), 5.253, kTolerance);
}

// -----------------------------------------------------------------------------
// A value that arrives ALREADY outside the interval
// -----------------------------------------------------------------------------
//
// The one input class this file did not cover, and the defect it was hiding was
// the safety invariant itself. The two walks this function used to do each
// stopped on the bound they were walking TOWARDS and never tested the other, so
// an input more than a whole turn outside the interval could be answered with a
// candidate that was outside it too — `nearest_turn(20.0, 13.7, -2*pi, +2*pi)`
// returned 13.716815 against an upper bound of 6.283185.
//
// It is reachable: `setFromIK` is under no obligation to respect joint limits,
// which is exactly why the call site tests the solution it gets back with
// `setJointValueTarget`. That test is downstream, in another library, and was
// the only thing standing between this and a joint target outside its declared
// limit. The header promised the invariant unconditionally; nothing checked it.

TEST(JointTurn, NeverAnswersAnOutOfBoundsInputWithAnOutOfBoundsAngle)
{
  // 20.0 is more than two turns above the upper limit. Every member of its
  // family that is IN bounds — 1.150 and -5.133 — stands further from the
  // reference than 20.0 itself does, so there is nothing to gain and the value
  // comes back untouched. Untouched is always allowed; a DIFFERENT angle that
  // is still out of bounds is not, and 13.716815 was what used to be returned.
  EXPECT_NEAR(cite_skills::nearest_turn(20.0, 13.7, kWideLower, kWideUpper), 20.0, kTolerance);
  // The mirror. Bounds are two numbers and this function got both of them
  // wrong in the same way, once per direction.
  EXPECT_NEAR(
    cite_skills::nearest_turn(-20.0, -13.7, kWideLower, kWideUpper), -20.0, kTolerance);
}

TEST(JointTurn, PullsAnOutOfBoundsInputINTOTheIntervalWhenThatIsNearer)
{
  // The control for the pair above, and it is what stops them being satisfied
  // by a function that gave up on every out-of-bounds input. 8.0 is above the
  // limit; 8.0 - 2*pi is 1.717, inside it, and nearer to the reference. So the
  // shift is taken and the answer is IN bounds — the refusals above are the
  // interval doing work rather than the input's position doing it.
  EXPECT_NEAR(
    cite_skills::nearest_turn(8.0, 0.0, kWideLower, kWideUpper), 8.0 - kTurn, kTolerance);
}

TEST(JointTurn, ReturnsTheInputOrAnInBoundsAngleOverEveryValueSwept)
{
  // The invariant as a property rather than as three examples, because the
  // examples are where it was already believed and the sweep is where it was
  // broken. Every return must be either the input untouched or a whole-turn
  // shift of it that lies inside the interval. Deliberately swept well past
  // both limits: inside them the old implementation was right.
  for (double value = -30.0; value <= 30.0; value += 0.013) {
    for (double reference = -8.0; reference <= 8.0; reference += 0.37) {
      const double answer = cite_skills::nearest_turn(value, reference, kWideLower, kWideUpper);
      if (answer == value) {
        continue;
      }
      EXPECT_GE(answer, kWideLower) << "value " << value << " reference " << reference;
      EXPECT_LE(answer, kWideUpper) << "value " << value << " reference " << reference;
      // And it really is a member of the family, not a clamp to the limit.
      const double turns = (answer - value) / kTurn;
      EXPECT_NEAR(turns, std::round(turns), 1e-9)
        << "value " << value << " reference " << reference;
    }
  }
}

// -----------------------------------------------------------------------------
// It ends, whatever it is given
// -----------------------------------------------------------------------------

TEST(JointTurn, EndsOnAJointWhoseSpanNoWalkCouldCross)
{
  // Two ways the walk this replaced did not end, and neither needs a wrong
  // input to reach — only a wide one.
  //
  // Above roughly 2^53 turns a subtraction of 2*pi ROUNDS TO A NO-OP, so the
  // walk stepped for ever without moving: `1e18 - 2*M_PI == 1e18` is true. And
  // below that it cost one iteration per turn of declared span, so a joint
  // stated over +/-1e7 rad cost about 3.2 million iterations PER SEED.
  //
  // The assertion is deliberately not a value. At 1e18 the spacing between
  // representable doubles is larger than a turn, so no exact answer is
  // meaningful; what is asserted is that the call RETURNS and honours the
  // invariant. A test that hangs reports nothing at all.
  const double answer = cite_skills::nearest_turn(1e18, 0.0, -2e18, 2e18);
  EXPECT_TRUE(answer == 1e18 || (answer >= -2e18 && answer <= 2e18));

  const double wide = cite_skills::nearest_turn(1.0e7 + 0.3, 0.0, -1.0e8, 1.0e8);
  EXPECT_NEAR(std::round((wide - (1.0e7 + 0.3)) / kTurn), (wide - (1.0e7 + 0.3)) / kTurn, 1e-6);
  EXPECT_LE(std::fabs(wide), 1.0e8);
}
