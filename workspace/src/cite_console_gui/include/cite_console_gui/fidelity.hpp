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

// What the frame's "Twin fidelity" card shows of a DivergenceMetrics sample
// (ADR-0074), as one pure function with no Qt and no ROS.
//
// HONEST BY CONSTRUCTION (P7, P8). A sample whose `valid` is false shows "Not
// measured" and no number at all: its comparison fields are zeroed by the
// contract, and a zero shown as a figure would read as a perfect twin. A field
// carrying NaN was not computed by anybody, and says so rather than showing a
// number. A valid sample whose far side is not physical compares two
// simulations generated from one model; it is shown as a test of the
// instrument, never as a fidelity result (DivergenceMetrics.msg, ADR-0041).
// Nothing in this tree publishes a valid sample today, so the card's normal
// state is "Not measured".

#ifndef CITE_CONSOLE_GUI__FIDELITY_HPP_
#define CITE_CONSOLE_GUI__FIDELITY_HPP_

#include <string>
#include <vector>

namespace cite_console_gui
{

/// The fields of one DivergenceMetrics sample the card reads.
struct DivergenceSample
{
  std::string asset_id;
  bool valid{false};
  double joint_error_rms_rad{0.0};
  double joint_error_max_rad{0.0};
  double tcp_position_error_m{0.0};
  double tcp_orientation_error_rad{0.0};
  bool far_side_physical{false};
};

/// One labelled figure, with its unit in the value.
struct FidelityRow
{
  std::string label;
  std::string value;
};

/// One asset's card.
struct FidelityView
{
  std::string asset_id;
  /// The sample is valid: the rows hold figures.
  bool measured{false};
  /// "Not measured", "Measured" or "Instrument test: both sides simulated".
  std::string headline;
  /// Empty unless `measured`.
  std::vector<FidelityRow> rows;
};

/// The card for `sample`.
FidelityView fidelity_view(const DivergenceSample & sample);

/// An angle in radians as the card shows it, "0.0123 rad (0.70°)"; "not
/// computed" for NaN.
std::string format_angle(double radians);

/// A length in metres as the card shows it, in millimetres, "12.3 mm"; "not
/// computed" for NaN.
std::string format_length(double metres);

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__FIDELITY_HPP_
