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

/// A batch front end for the SUPERSEDED grasp predicate at `4ef2d7c`, and nothing else.
///
/// DERIVED FROM
/// `docs/measurements/2026-09-02-option-f-regions/harness/predicate_eval_superseded.cpp`,
/// copied at commit `3235cbc`. That directory is FROZEN
/// (`docs/measurements/README.md`) and nothing in it is edited from here. **Everything
/// below this header block is byte-identical to that file**; the header is rewritten
/// because it made claims about that campaign's `criteria.md` and not about this one's.
///
/// The ARITHMETIC below is untouched, because the API that file was written against is
/// exactly the API `4ef2d7c` presents: a `GripperTravel` without the two stall bands, a
/// `gripper_is_holding` of two arguments, and no `WorkpieceWidths` anywhere.
///
/// WHY IT IS A BUILD AND NOT A REWRITE. `criteria.md` V12: `holding_S` and `flip_S_lo`
/// contribute only if `raw/provenance.txt` records the `4ef2d7c` worktree commit and the
/// sha256 of the binary that produced them. `build_superseded.sh` creates a detached
/// `git worktree` at that commit, compiles `gripper.cpp` out of it unmodified, and writes
/// both. A transcription of the superseded arithmetic into this harness would be a third
/// derivation of the policy the campaign exists to measure.
///
/// WHAT THIS CAMPAIGN SPENDS IT ON. `holding_S` beside `holding_F` on every trial, and
/// `flip_S_lo` -- this campaign's own re-derivation, on this rig at this command, of the
/// floor ADR-0052 section A.6 states (`criteria.md` sections 2.1, 4.3 and 7.2). It is
/// also what section 2.2's closed-form floor is solved against before any trial, by
/// bisection on THIS program's answer rather than on a Python restatement of it.
///
/// `holding_S` ENTERS NO VERDICT OF ARM LO OR ARM HI (`criteria.md` section 4.3). A
/// disagreement between the two predicates is a datum and not a defect, in either
/// direction, and deciding what to do about one is ADR-0052's and the owner's.
///
/// PROTOCOL. Travel parameters arrive on argv, one `--key=value` per L0 field, so that
/// they come from the generated bring-up plan rather than from this file. Requests
/// arrive one per line on stdin and answers leave one per line on stdout, in order:
///
///   width     <q_rad>                                  -> opening in metres
///   position  <width_m>                                -> drive position in rad
///   tolerance <q_rad>                                  -> gripper_width_tolerance_m
///   holding   <commanded_m> <q_rad> <stalled> <goal>   -> 1 or 0
///   travel                                             -> the parameters in force
///
/// `stalled` and `goal` are 0 or 1. Any other verb is an error and exits non-zero:
/// silently skipping a request would leave a hole in a numbered sweep.

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

#include "cite_skills/gripper.hpp"

namespace
{

/// Apply one `--key=value` to the travel, or return false if the key is unknown.
///
/// Unknown keys are refused rather than ignored. A typo in a driver's flag would
/// otherwise silently fall back to the header's default, which is the L0 value today
/// and need not stay that way -- and the campaign would report a figure computed from a
/// constant nobody passed.
bool apply(cite_skills::GripperTravel & travel, const std::string & key, double value)
{
  if (key == "open_position") {travel.open_position = value; return true;}
  if (key == "closed_position") {travel.closed_position = value; return true;}
  if (key == "drive_pivot_y_m") {travel.drive_pivot_y_m = value; return true;}
  if (key == "drive_pivot_z_m") {travel.drive_pivot_z_m = value; return true;}
  if (key == "finger_offset_y_m") {travel.finger_offset_y_m = value; return true;}
  if (key == "finger_offset_z_m") {travel.finger_offset_z_m = value; return true;}
  if (key == "pad_inset_m") {travel.pad_inset_m = value; return true;}
  if (key == "tip_link_z_m") {travel.tip_link_z_m = value; return true;}
  if (key == "pad_face_centre_z_m") {travel.pad_face_centre_z_m = value; return true;}
  if (key == "goal_tolerance") {travel.goal_tolerance = value; return true;}
  return false;
}

}  // namespace

int main(int argc, char ** argv)
{
  cite_skills::GripperTravel travel;

  for (int i = 1; i < argc; ++i) {
    const std::string argument = argv[i];
    if (argument.rfind("--", 0) != 0) {
      std::cerr << "unexpected argument '" << argument << "'\n";
      return 2;
    }
    const auto equals = argument.find('=');
    if (equals == std::string::npos) {
      std::cerr << "expected --key=value, got '" << argument << "'\n";
      return 2;
    }
    const std::string key = argument.substr(2, equals - 2);
    // The WHOLE value has to be a number, and this is not defensive noise. `strtod`
    // stops at the first character it cannot read and reports success, so a value that
    // picked up trailing text -- a shell that did not split a variable, a quoted list
    // arriving as one argument -- would set this key from its numeric prefix and leave
    // every later key at its header default. Two of those defaults are the band's
    // zero-width sentinel, so the program would answer every question with a predicate
    // that admits nothing, and answer it silently. Caught here instead.
    char * end = nullptr;
    const char * begin = argument.c_str() + equals + 1;
    const double value = std::strtod(begin, &end);
    if (end == begin || *end != '\0') {
      std::cerr << "'" << begin << "' is not a number, in argument '" << argument << "'\n";
      return 2;
    }
    if (!apply(travel, key, value)) {
      std::cerr << "unknown travel parameter '" << key << "'\n";
      return 2;
    }
  }

  // Seventeen significant digits round-trips an IEEE 754 double exactly. The point of
  // this program is that the campaign reads what the predicate read, so nothing may be
  // lost on the way out of it.
  std::cout << std::setprecision(17);

  std::string line;
  while (std::getline(std::cin, line)) {
    std::istringstream request(line);
    std::string verb;
    if (!(request >> verb) || verb.empty()) {
      continue;
    }
    if (verb == "width") {
      double q = 0.0;
      request >> q;
      std::cout << cite_skills::gripper_width_for(q, travel) << "\n";
    } else if (verb == "position") {
      double w = 0.0;
      request >> w;
      std::cout << cite_skills::gripper_position_for(w, travel) << "\n";
    } else if (verb == "tolerance") {
      double q = 0.0;
      request >> q;
      std::cout << cite_skills::gripper_width_tolerance_m(q, travel) << "\n";
    } else if (verb == "holding") {
      double commanded = 0.0;
      double q = 0.0;
      int stalled = 0;
      int reached_goal = 0;
      request >> commanded >> q >> stalled >> reached_goal;
      const cite_skills::GripperReport report{
        commanded, q, stalled != 0, reached_goal != 0};
      std::cout << (cite_skills::gripper_is_holding(report, travel) ? 1 : 0) << "\n";
    } else if (verb == "travel") {
      std::cout
        << "open_position=" << travel.open_position
        << " closed_position=" << travel.closed_position
        << " drive_pivot_y_m=" << travel.drive_pivot_y_m
        << " drive_pivot_z_m=" << travel.drive_pivot_z_m
        << " finger_offset_y_m=" << travel.finger_offset_y_m
        << " finger_offset_z_m=" << travel.finger_offset_z_m
        << " pad_inset_m=" << travel.pad_inset_m
        << " tip_link_z_m=" << travel.tip_link_z_m
        << " pad_face_centre_z_m=" << travel.pad_face_centre_z_m
        << " goal_tolerance=" << travel.goal_tolerance << "\n";
    } else {
      std::cerr << "unknown verb '" << verb << "'\n";
      return 3;
    }
    std::cout.flush();
  }
  return 0;
}
