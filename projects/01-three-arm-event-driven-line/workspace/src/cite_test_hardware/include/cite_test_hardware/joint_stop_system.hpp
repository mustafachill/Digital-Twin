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

// A pair of hard stops on one joint, so a trajectory can be made to mistrack
// PART WAY along its path rather than at its first point (ADR-0040).
//
// ## Why this exists
//
// ADR-0037 classifies a failed execution by asking where the arm is standing
// relative to the trajectory it was given: at the start, at the goal, or
// somewhere in between. "In between" is `MOTION_INTERRUPTED`, which stops a
// station for an operator instead of retrying it unattended — the one answer the
// classification exists to produce, and the one no fixture in this repository
// could produce on demand. ADR-0037 records that gap against its own decision 8.
//
// The nearest thing, `mock_components/GenericSystem`'s `disable_commands`, stops
// command propagation outright from the first control cycle. The joint never
// leaves `initial_value`, so an abort leaves the arm exactly at the trajectory's
// first point and the classification answers AT_START — the opposite case.
//
// ## What it is
//
// `GenericSystem`, with two differences, both declared in the description rather
// than compiled in here:
//
//   1. one named joint's POSITION STATE is clamped into a declared interval, so
//      the arm tracks its trajectory normally until it reaches the stop and then
//      stands there while the trajectory advances without it;
//   2. every joint that declares a velocity state interface gets one that is a
//      function of its motion — see the note on that below, it is not a detail.
//
// ## Why the stop is TWO-SIDED and stated in absolute joint coordinates
//
// A single threshold has to know which way the joint is travelling. Where an arm
// goes is decided by an IK solve, and a solver that returns the equivalent branch
// on the other side of zero would leave a one-sided stop un-hit and the rig
// silently green — a fixture reporting a healthy run it did not produce. Two
// stops in joint coordinates cannot be missed by a sign.
//
// ## Why a CLAMP rather than a latch that freezes the joint where it stood
//
// A latch steps the state backwards by up to one cycle's travel at the instant it
// engages. That is a spurious negative velocity sample injected into the exact
// measurement this fixture exists to make possible. The clamp is monotone: the
// joint approaches the stop, reaches it, and stays — no discontinuity, and the
// resting position is known in advance because the description declares it.
//
// ## P4: this is a state, not a duration
//
// Nothing here reads a clock to decide when to engage. A slower machine engages
// the stop at the same joint angle, and the rig's behaviour does not depend on
// how long anything took.
//
// ## THIS IS NOT A BACKEND AND CANNOT BECOME ONE
//
// `on_init` REFUSES unless it is given a joint to stop and an interval to stop it
// in. Those parameters have no home in the L0 model — the facility model has no
// concept of a hard stop at a joint angle — so a generated description cannot
// carry them, and a plugin that will not start without them cannot be loaded by a
// production bring-up even if its class name were named. The library, its install
// rule and its pluginlib export also all sit inside `if(BUILD_TESTING)`, so a
// build with testing off contains no loadable class at all. See ADR-0040
// decision 2 for which parts of that are structural and which are merely checked.

#ifndef CITE_TEST_HARDWARE__JOINT_STOP_SYSTEM_HPP_
#define CITE_TEST_HARDWARE__JOINT_STOP_SYSTEM_HPP_

#include <string>
#include <vector>

#include <mock_components/generic_system.hpp>
#include <hardware_interface/types/hardware_component_interface_params.hpp>
#include <hardware_interface/types/hardware_interface_return_values.hpp>
#include <rclcpp/duration.hpp>
#include <rclcpp/time.hpp>
#include <rclcpp_lifecycle/state.hpp>

namespace cite_test_hardware
{

/// The `<hardware>` parameter naming the joint that has stops. Required.
inline constexpr const char * kStopJointParameter = "stop_joint";
/// The lower stop, in the joint's own units. Required.
inline constexpr const char * kStopLowerParameter = "stop_lower_rad";
/// The upper stop, in the joint's own units. Required, and strictly above the lower.
inline constexpr const char * kStopUpperParameter = "stop_upper_rad";

class JointStopSystem : public mock_components::GenericSystem
{
public:
  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareComponentInterfaceParams & params) override;

  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  /// The full interface name — `<joint>/position` — of the joint that has stops.
  std::string stop_position_interface_;
  double stop_lower_{0.0};
  double stop_upper_{0.0};

  /// Interface names of every joint that declares BOTH position and velocity
  /// state, paired so that the velocity is written from the position beside it.
  ///
  /// WHY THE VELOCITY IS WRITTEN HERE AT ALL, because it looks like scope creep
  /// and is not. `GenericSystem::read()` mirrors a command to its state interface
  /// by interface: with the position-only command interfaces this cell's
  /// controllers claim, NOTHING EVER WRITES VELOCITY, and the state interface
  /// holds its initial value for the life of the process. The generated
  /// `JointTrajectoryController` configuration declares
  /// `state_interfaces: [position, velocity]`, so both that controller and
  /// `joint_state_broadcaster` read a permanent zero. A rig meant to answer
  /// "is the joint still moving?" would answer "no" for an arm travelling at any
  /// speed at all.
  ///
  /// What is written is the first difference of the joint's POSITION STATE over
  /// the control period. On this backend the state is a mirror of the command, so
  /// this is the rate of change of the controller's own command stream — which is
  /// the honest scope of anything measured with it, and is stated in ADR-0040's
  /// costs rather than left for a reader to infer.
  struct DifferentiatedJoint
  {
    std::string position;
    std::string velocity;
    double previous_position{0.0};
  };
  std::vector<DifferentiatedJoint> differentiated_;

  /// False until the first `read` after activation has established a baseline for
  /// the first difference and checked the stop joint against its stops.
  bool sampled_{false};
  /// Logged once, so a rig whose stop engaged says so in its own output.
  bool announced_{false};
};

}  // namespace cite_test_hardware

#endif  // CITE_TEST_HARDWARE__JOINT_STOP_SYSTEM_HPP_
