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

#include "cite_skills/detection.hpp"

#include <algorithm>
#include <cmath>

namespace cite_skills
{

BeamEdgeDetector::Report BeamEdgeDetector::observe(bool blocked, double stamp_s)
{
  Report report;
  report.state = blocked;

  if (!known_) {
    known_ = true;
    state_ = blocked;
    entered_state_s_ = stamp_s;
    report.kind = BeamReport::Initial;
    // Equal, so that a consumer applying the ordinary edge test — state differs
    // from previous_state — does not see a transition here. There was none to
    // see; this is where the beam was found.
    report.previous_state = blocked;
    report.duration_in_previous_state_s = 0.0;
    return report;
  }

  if (blocked == state_) {
    report.kind = BeamReport::None;
    report.previous_state = state_;
    return report;
  }

  report.kind = BeamReport::Edge;
  report.previous_state = state_;
  // Clamped at zero rather than reported negative. Samples can arrive out of
  // order across a bridge, and a negative duration is a number no consumer has a
  // meaning for; the edge itself is still true and is the part that matters.
  report.duration_in_previous_state_s = std::max(0.0, stamp_s - entered_state_s_);

  state_ = blocked;
  entered_state_s_ = stamp_s;
  return report;
}

bool inside_region(
  double x, double y, double z, double size_x, double size_y, double size_z)
{
  return std::abs(x) <= size_x / 2.0 &&
         std::abs(y) <= size_y / 2.0 &&
         std::abs(z) <= size_z / 2.0;
}

}  // namespace cite_skills
