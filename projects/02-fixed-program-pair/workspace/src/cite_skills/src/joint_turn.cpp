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

#include "cite_skills/joint_turn.hpp"

#include <algorithm>
#include <cmath>
#include <iterator>

namespace cite_skills
{

double nearest_turn(double value, double reference, double lower, double upper)
{
  // A value that is not a number has no nearest anything, and shifting it would
  // hand the caller a NaN dressed as a decision.
  if (!std::isfinite(value) || !std::isfinite(reference)) {
    return value;
  }
  // An unbounded interval is never left, so there is no range of shifts to
  // choose inside. Treated as "no second solution is authorised" rather than as
  // "every shift is authorised", because the interval is what makes a shift
  // safe and an interval nobody stated is not a licence.
  if (!std::isfinite(lower) || !std::isfinite(upper)) {
    return value;
  }
  // A span of one turn or less holds at most one member of the family, so there
  // is nothing to choose between. Tested HERE rather than at the call site so
  // that a caller cannot forget it — and so that the property is pinned by a
  // unit test rather than by a comment in the skill server.
  if (upper - lower <= kWholeTurnRad) {
    return value;
  }

  // The family is `value + kWholeTurnRad * k` over integer `k`, and the distance
  // from a member to `reference` is a V in `k` with its minimum at the real
  // number `ideal`. So the nearest member is `round(ideal)`, and the nearest
  // member THE BOUNDS ADMIT is that one clamped into the range of `k` the
  // interval allows. Computed, not walked — constant work whatever the span.
  //
  // WHAT THIS REPLACED WAS BOTH WRONG AND UNBOUNDED, AND THE TWO DEFECTS WERE
  // ONE LOOP. Two walks stepped outwards from `value`, one per direction, and
  // each stopped on the bound it was walking TOWARDS while never testing the
  // other. An input more than a whole turn outside the interval could therefore
  // win with a candidate that was outside it too: `nearest_turn(20.0, 13.7,
  // -2*pi, +2*pi)` returned 13.716815 against an upper bound of 6.283185 — the
  // one thing this function promises not to do, contradicting the invariant its
  // own header states, with nothing but a downstream `setJointValueTarget`
  // between it and a joint command. The same walks also fail to TERMINATE above
  // roughly 2^53 turns, where `candidate -= kWholeTurnRad` rounds to a no-op,
  // and in between cost one iteration per turn of declared span.
  const double ideal = (reference - value) / kWholeTurnRad;
  const double lowest = std::ceil((lower - value) / kWholeTurnRad);
  const double highest = std::floor((upper - value) / kWholeTurnRad);
  const double centre = std::min(std::max(std::round(ideal), lowest), highest);

  // The clamped shift AND ITS TWO NEIGHBOURS. `round`, `ceil` and `floor` over a
  // ratio of doubles can each land one short where a candidate falls exactly on
  // a limit, and a clamp is only as correct as the range it clamps into; three
  // candidates cost nothing and put that rounding beyond reach of the answer.
  double shifts[] = {centre - 1.0, centre, centre + 1.0};
  // Smallest shift first, so the ties resolve the way the header promises:
  // `value` is the incumbent and is displaced only by a STRICTLY nearer angle,
  // and among equally near shifts the smaller one arrives first and keeps the
  // answer. Ordering by magnitude and not by sign is the whole of that rule.
  std::sort(
    std::begin(shifts), std::end(shifts),
    [](double left, double right) {
      if (std::fabs(left) != std::fabs(right)) {
        return std::fabs(left) < std::fabs(right);
      }
      return left < right;
    });

  double best = value;
  double best_distance = std::fabs(value - reference);
  for (const double turns : shifts) {
    const double candidate = value + kWholeTurnRad * turns;
    // BOTH BOUNDS, ON EVERY CANDIDATE. Testing one bound per direction is the
    // defect described above, and it read as complete because each walk did
    // test a bound — just never the one it was moving away from.
    if (candidate < lower || candidate > upper) {
      continue;
    }
    const double distance = std::fabs(candidate - reference);
    if (distance < best_distance) {
      best = candidate;
      best_distance = distance;
    }
  }

  return best;
}

}  // namespace cite_skills
