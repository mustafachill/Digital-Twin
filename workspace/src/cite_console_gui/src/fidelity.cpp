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

#include "cite_console_gui/fidelity.hpp"

#include <cmath>
#include <cstdio>
#include <string>

namespace cite_console_gui
{

namespace
{

constexpr const char * NOT_COMPUTED = "not computed";
constexpr double PI = 3.14159265358979323846;

}  // namespace

std::string format_angle(double radians)
{
  if (std::isnan(radians)) {
    return NOT_COMPUTED;
  }
  char text[64];
  std::snprintf(text, sizeof(text), "%.4f rad (%.2f°)", radians, radians * 180.0 / PI);
  return text;
}

std::string format_length(double metres)
{
  if (std::isnan(metres)) {
    return NOT_COMPUTED;
  }
  char text[64];
  std::snprintf(text, sizeof(text), "%.1f mm", metres * 1000.0);
  return text;
}

FidelityView fidelity_view(const DivergenceSample & sample)
{
  FidelityView view;
  view.asset_id = sample.asset_id;
  if (!sample.valid) {
    view.headline = "Not measured";
    return view;
  }
  view.measured = true;
  view.headline = sample.far_side_physical ?
    "Measured" : "Instrument test: both sides simulated";
  view.rows = {
    {"Joint error, RMS", format_angle(sample.joint_error_rms_rad)},
    {"Joint error, max", format_angle(sample.joint_error_max_rad)},
    {"TCP position error", format_length(sample.tcp_position_error_m)},
    {"TCP orientation error", format_angle(sample.tcp_orientation_error_rad)},
  };
  return view;
}

}  // namespace cite_console_gui
