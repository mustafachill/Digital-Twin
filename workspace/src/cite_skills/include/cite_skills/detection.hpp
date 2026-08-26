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

// Turning a level into an event, and deciding what lies inside a region.
//
// The break-beam plugin publishes the beam's STATE, not its changes, and that is
// deliberate: `cite_simulation/src/break_beam.cpp` says so in its header, and the
// reason is P2. A plugin that published edges — or published a ROS message at
// all — would be a second, simulation-only route into the system, and the
// physical sensor would then arrive through a different one. Both paths publish a
// level; this is the single place either of them becomes a `DetectionEvent`.
//
// Kept free of ROS types so that the edge rule can be tested for what it is — a
// state machine over samples — without a bridge, a simulator or any waiting.
// `cross-cutting-testing.md` asks for exactly this: push the test down, and do
// not spend the scenario suite on something a unit test could have caught.

#ifndef CITE_SKILLS__DETECTION_HPP_
#define CITE_SKILLS__DETECTION_HPP_

namespace cite_skills
{

/// What one level sample means for the event stream.
enum class BeamReport
{
  //: The level is what it already was. The plugin republishes the current state
  //: periodically so that a subscriber which starts late learns it without
  //: waiting for the next transition, so most samples land here. Publishing a
  //: `DetectionEvent` for each of them would turn a keep-all event topic into a
  //: telemetry stream and bury the transitions it exists to carry.
  None,

  //: The first sample from this sensor. Reported, but NOT as an edge: nothing
  //: here knows what the beam read before this node existed, and a first sample
  //: of BLOCKED published with previous_state CLEAR is a transition that was
  //: invented rather than observed.
  //:
  //: It is still published, with `state == previous_state`, because the
  //: alternative is worse. `DetectionEvent` carries `previous_state` precisely so
  //: a consumer can tell an edge from a level without keeping its own history, so
  //: a report of "this is where the beam stands, and I did not see it arrive" is
  //: expressible — and a work-piece already sitting in the beam at start-up is
  //: otherwise invisible until it leaves.
  Initial,

  //: The level changed. This is the event the line acts on.
  Edge,
};

/// One sensor's level history, reduced to what the event stream needs.
///
/// Deliberately per-sensor and deliberately stateful. L3's "skills are stateless
/// between goals" rule is about goal memory — a skill that behaves differently
/// because of what it was asked last time. This is sensor state, which is the one
/// thing an edge detector cannot do without: an edge is a fact about two samples.
class BeamEdgeDetector
{
public:
  struct Report
  {
    BeamReport kind{BeamReport::None};
    bool state{false};
    bool previous_state{false};
    //: How long the beam sat in the state it just left. Zero on the first
    //: sample, where the answer is unknown rather than zero — and `kind` is what
    //: says which of those it is, so no consumer has to read zero as a duration.
    double duration_in_previous_state_s{0.0};
  };

  /// Fold one level sample in, and say what it means.
  ///
  /// `stamp_s` is the sample's own time, not the wall clock: with `use_sim_time`
  /// the two differ by whatever the real-time factor happens to be, and a
  /// duration measured against the wrong one is a plausible wrong number.
  Report observe(bool blocked, double stamp_s);

  /// Whether any sample has arrived at all. A sensor that has never reported is
  /// not a sensor reporting CLEAR, and the two must not be confused: the first
  /// would mean the bridge is not delivering, the second that the belt is empty.
  bool known() const {return known_;}

  bool blocked() const {return state_;}

private:
  bool known_{false};
  bool state_{false};
  double entered_state_s_{0.0};
};

/// Whether a point lies inside an axis-aligned box centred on the region frame.
///
/// `Detect.Goal.region_size_m` is documented as extents ABOUT the frame, so the
/// box is centred rather than cornered, and each half-extent is half the size.
///
/// The boundary is inclusive. A beam sitting exactly on the face of a region a
/// caller sized to contain it is inside it; excluding it would make a region
/// derived from the model's own dimensions fail to contain the thing it was
/// derived from.
bool inside_region(
  double x, double y, double z, double size_x, double size_y, double size_z);

}  // namespace cite_skills

#endif  // CITE_SKILLS__DETECTION_HPP_
