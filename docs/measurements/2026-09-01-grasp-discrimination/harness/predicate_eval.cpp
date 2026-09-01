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

/// A batch front end for the SHIPPED grasp predicate, and nothing else.
///
/// WHY THIS EXISTS RATHER THAN A PYTHON COPY. This campaign's whole subject is two
/// derivations of one policy disagreeing (ADR-0052 section 5, P1). A campaign that
/// answered that with a third derivation of its own would be measuring itself. So
/// every C++-side figure this campaign reports comes from
/// `workspace/src/cite_skills/src/gripper.cpp`, compiled UNMODIFIED and linked here.
/// `build.sh` names that path; there is no copy of the arithmetic in this file.
///
/// WHAT IS NOT SHIPPED ABOUT IT. `cite_skills` exports no library — `gripper.cpp` is
/// compiled straight into `skill_server` and `detection_server` — so this program
/// compiles the same translation unit rather than linking a built artefact. It is the
/// same source at the same commit; it is not the same object file, and that is stated
/// here rather than left to be discovered.
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
/// and need not stay that way — and the campaign would report a figure computed from a
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
    const double value = std::strtod(argument.c_str() + equals + 1, nullptr);
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
