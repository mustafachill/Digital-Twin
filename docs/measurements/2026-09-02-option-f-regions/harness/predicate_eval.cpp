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

/// A batch front end for the SHIPPED grasp arithmetic at `d3eeac4`, and nothing else.
///
/// DERIVED FROM
/// `docs/measurements/2026-09-01-grasp-discrimination/harness/predicate_eval.cpp`,
/// copied at commit `eeaf903`. That directory is FROZEN
/// (`docs/measurements/README.md`) and nothing in it is edited from here.
///
/// WHAT CHANGED FROM THE SOURCE FILE, and why:
///
///   * `GripperTravel` gained `stall_band_narrow_m` and `stall_band_wide_m`, and the
///     facility's `WorkpieceWidths` arrives on its own two flags. Option F judges a
///     stall against those four numbers, so a front end that could not be given them
///     could not evaluate the shipped predicate at all.
///   * `holding` therefore passes `parts` through. It still passes the commanded width,
///     because `GripperReport` still carries it -- the predicate deliberately does not
///     read it (ADR-0052 option F), and this program does not decide that.
///   * three verbs were added, each a shipped function this campaign needs and none of
///     them arithmetic of this file's own:
///       - `resolve`     -> `cite_skills::resolve_grasp_width`, which is `criteria.md`
///                          instrument I6. The permitted range is read from the shipped
///                          function; the 47.8769 mm in section 2 is never used as one.
///       - `margin`      -> `cite_skills::gripper_discrimination_margin_m`, reported
///                          beside I6 so a refusal can be read rather than believed.
///       - `padoffset`   -> `cite_skills::gripper_pad_plane_offset_m`, which arms C and
///                          D need to place the tip link where `Pick` would have put it
///                          when they reach the part through `MoveTo` and `Grasp`.
///
/// WHY THIS EXISTS RATHER THAN A PYTHON COPY. This campaign measures a predicate. A
/// campaign that answered questions about it with a second implementation of it would be
/// measuring itself. So every arithmetic figure it reports comes from
/// `workspace/src/cite_skills/src/gripper.cpp`, compiled UNMODIFIED and linked here;
/// `build.sh` names that path, and there is no copy of the arithmetic in this file.
///
/// WHAT IS NOT SHIPPED ABOUT IT. `cite_skills` exports no library -- `gripper.cpp` is
/// compiled straight into `skill_server` -- so this program compiles the same translation
/// unit rather than linking a built artefact. Same source at the same commit; not the
/// same object file, and that is stated here rather than left to be discovered.
///
/// THE VERDICT `holding_F` IN `ANALYSIS.md` DOES NOT COME FROM HERE. It is read off the
/// running node, out of `Grasp.Result.holding` (`criteria.md` section 3, I1). What this
/// program contributes is I6, the derived quantities, and the sweep arithmetic.
///
/// PROTOCOL. Travel and facility parameters arrive on argv, one `--key=value` each, so
/// that they come from the generated bring-up plan rather than from this file. Requests
/// arrive one per line on stdin and answers leave one per line on stdout, in order:
///
///   width      <q_rad>                                 -> opening in metres
///   position   <width_m>                               -> drive position in rad
///   tolerance  <q_rad>                                 -> gripper_width_tolerance_m
///   padoffset  <q_rad>                                 -> gripper_pad_plane_offset_m
///   margin     <width_m>                               -> gripper_discrimination_margin_m
///   maxwidth                                           -> gripper_max_width_m
///   minwidth                                           -> gripper_min_width_m
///   holding    <commanded_m> <q_rad> <stalled> <goal>  -> 1 or 0
///   resolve    <requested_m> <default_m>               -> "<source> <width_m>"
///   travel                                             -> the parameters in force
///   parts                                              -> the facility interval in force
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

/// Apply one `--key=value`, or return false if the key is unknown.
///
/// Unknown keys are refused rather than ignored. A typo in a driver's flag would
/// otherwise silently fall back to the header's default -- which for the two bands is
/// the sentinel 0.0, a zero-width window that admits nothing -- and the campaign would
/// report a figure computed from a value nobody passed.
bool apply(
  cite_skills::GripperTravel & travel, cite_skills::WorkpieceWidths & parts,
  const std::string & key, double value)
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
  if (key == "stall_band_narrow_m") {travel.stall_band_narrow_m = value; return true;}
  if (key == "stall_band_wide_m") {travel.stall_band_wide_m = value; return true;}
  if (key == "narrowest_m") {parts.narrowest_m = value; return true;}
  if (key == "widest_m") {parts.widest_m = value; return true;}
  return false;
}

const char * name_of(cite_skills::GraspWidthSource source)
{
  switch (source) {
    case cite_skills::GraspWidthSource::Goal: return "Goal";
    case cite_skills::GraspWidthSource::Default: return "Default";
    case cite_skills::GraspWidthSource::Unknown: return "Unknown";
    case cite_skills::GraspWidthSource::Refused: return "Refused";
  }
  return "Unknown";
}

}  // namespace

int main(int argc, char ** argv)
{
  cite_skills::GripperTravel travel;
  cite_skills::WorkpieceWidths parts;

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
    if (!apply(travel, parts, key, value)) {
      std::cerr << "unknown parameter '" << key << "'\n";
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
    } else if (verb == "padoffset") {
      double q = 0.0;
      request >> q;
      std::cout << cite_skills::gripper_pad_plane_offset_m(q, travel) << "\n";
    } else if (verb == "margin") {
      double w = 0.0;
      request >> w;
      std::cout << cite_skills::gripper_discrimination_margin_m(w, travel) << "\n";
    } else if (verb == "maxwidth") {
      std::cout << cite_skills::gripper_max_width_m(travel) << "\n";
    } else if (verb == "minwidth") {
      std::cout << cite_skills::gripper_min_width_m(travel) << "\n";
    } else if (verb == "holding") {
      double commanded = 0.0;
      double q = 0.0;
      int stalled = 0;
      int reached_goal = 0;
      request >> commanded >> q >> stalled >> reached_goal;
      const cite_skills::GripperReport report{
        commanded, q, stalled != 0, reached_goal != 0};
      std::cout << (cite_skills::gripper_is_holding(report, travel, parts) ? 1 : 0) << "\n";
    } else if (verb == "resolve") {
      double requested = 0.0;
      double configured = 0.0;
      request >> requested >> configured;
      const auto resolved =
        cite_skills::resolve_grasp_width(requested, configured, parts, travel);
      std::cout << name_of(resolved.source) << " " << resolved.width_m << "\n";
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
        << " goal_tolerance=" << travel.goal_tolerance
        << " stall_band_narrow_m=" << travel.stall_band_narrow_m
        << " stall_band_wide_m=" << travel.stall_band_wide_m << "\n";
    } else if (verb == "parts") {
      std::cout
        << "narrowest_m=" << parts.narrowest_m
        << " widest_m=" << parts.widest_m << "\n";
    } else {
      std::cerr << "unknown verb '" << verb << "'\n";
      return 3;
    }
    std::cout.flush();
  }
  return 0;
}
