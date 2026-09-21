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

#include <cmath>

namespace cite_skills
{

namespace
{

//: One whole revolution. The quantity a revolute joint may be shifted by
//: without moving any link it carries.
constexpr double kTurn = 2.0 * M_PI;

}  // namespace

double nearest_turn(double value, double reference, double lower, double upper)
{
  // A value that is not a number has no nearest anything, and shifting it would
  // hand the caller a NaN dressed as a decision.
  if (!std::isfinite(value) || !std::isfinite(reference)) {
    return value;
  }
  // An unbounded interval is never left, so the outward walks below would not
  // terminate. Treated as "no second solution is authorised" rather than as
  // "every shift is authorised", because the interval is what makes a shift
  // safe and an interval nobody stated is not a licence.
  if (!std::isfinite(lower) || !std::isfinite(upper)) {
    return value;
  }
  // A span of one turn or less holds at most one member of the family, so there
  // is nothing to choose between. Tested HERE rather than at the call site so
  // that a caller cannot forget it — and so that the property is pinned by a
  // unit test rather than by a comment in the skill server.
  if (upper - lower <= kTurn) {
    return value;
  }

  double best = value;
  double best_distance = std::fabs(value - reference);

  // Outwards from `value` in both directions, nearest shift first, stopping at
  // the first candidate that leaves the interval — every candidate beyond it is
  // further out still. Strictly-nearer wins, so the first candidate at a given
  // distance keeps the answer: `value` beats every tie it is in, and among
  // shifts the smaller one does.
  for (double candidate = value - kTurn; candidate >= lower; candidate -= kTurn) {
    const double distance = std::fabs(candidate - reference);
    if (distance < best_distance) {
      best = candidate;
      best_distance = distance;
    }
  }
  for (double candidate = value + kTurn; candidate <= upper; candidate += kTurn) {
    const double distance = std::fabs(candidate - reference);
    if (distance < best_distance) {
      best = candidate;
      best_distance = distance;
    }
  }

  return best;
}

}  // namespace cite_skills
