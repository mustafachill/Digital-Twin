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

#include "cite_test_hardware/joint_stop_system.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <unordered_map>
#include <vector>

#include <hardware_interface/lexical_casts.hpp>
#include <hardware_interface/types/hardware_interface_type_values.hpp>
#include <pluginlib/class_list_macros.hpp>
#include <rclcpp/logging.hpp>

namespace
{

/// Read one required `<hardware>` parameter as a finite double.
///
/// Every failure is a refusal rather than a default, because a default here would
/// be a stop the description did not ask for, standing where nothing declared it.
bool read_finite(
  const std::unordered_map<std::string, std::string> & parameters, const std::string & key,
  double & out)
{
  const auto entry = parameters.find(key);
  if (entry == parameters.end()) {
    return false;
  }
  try {
    out = hardware_interface::stod(entry->second);
  } catch (const std::exception &) {
    return false;
  }
  return std::isfinite(out);
}

/// Whether `component` declares an interface of this name.
bool declares(
  const std::vector<hardware_interface::InterfaceInfo> & interfaces,
  const std::string & name)
{
  return std::any_of(
    interfaces.begin(), interfaces.end(),
    [&name](const hardware_interface::InterfaceInfo & interface) {
      return interface.name == name;
    });
}

}  // namespace

namespace cite_test_hardware
{

hardware_interface::CallbackReturn JointStopSystem::on_init(
  const hardware_interface::HardwareComponentInterfaceParams & params)
{
  const auto base = mock_components::GenericSystem::on_init(params);
  if (base != hardware_interface::CallbackReturn::SUCCESS) {
    return base;
  }

  // THE REFUSALS BELOW ARE THE POINT, not defensive noise. They are what stops
  // this class from being usable as a general stand-in for hardware: it cannot
  // start without a stop, and a stop has nowhere to be declared in the L0 model
  // (ADR-0040 decision 2).
  const auto & parameters = info_.hardware_parameters;
  const auto named = parameters.find(kStopJointParameter);
  if (named == parameters.end() || named->second.empty()) {
    RCLCPP_ERROR(
      get_logger(),
      "'%s' declares no '%s'. This is a TEST FIXTURE and refuses to run as a hardware "
      "backend: without a joint to stop it would be an ordinary mock, loaded under a name "
      "that says it is not one.",
      info_.name.c_str(), kStopJointParameter);
    return hardware_interface::CallbackReturn::ERROR;
  }

  if (!read_finite(parameters, kStopLowerParameter, stop_lower_) ||
    !read_finite(parameters, kStopUpperParameter, stop_upper_))
  {
    RCLCPP_ERROR(
      get_logger(), "'%s' needs finite '%s' and '%s' parameters.", info_.name.c_str(),
      kStopLowerParameter, kStopUpperParameter);
    return hardware_interface::CallbackReturn::ERROR;
  }
  if (!(stop_lower_ < stop_upper_)) {
    RCLCPP_ERROR(
      get_logger(), "'%s' declares %s=%f at or above %s=%f, which is not an interval.",
      info_.name.c_str(), kStopLowerParameter, stop_lower_, kStopUpperParameter, stop_upper_);
    return hardware_interface::CallbackReturn::ERROR;
  }

  // The stop joint must be commandable in position and readable in position.
  // Stopping a joint the controller cannot drive would produce a rig that never
  // mistracks, and one whose position cannot be read cannot be clamped at all.
  const auto stopped = std::find_if(
    info_.joints.begin(), info_.joints.end(),
    [&named](const hardware_interface::ComponentInfo & joint) {
      return joint.name == named->second;
    });
  if (stopped == info_.joints.end() ||
    !declares(stopped->command_interfaces, hardware_interface::HW_IF_POSITION) ||
    !declares(stopped->state_interfaces, hardware_interface::HW_IF_POSITION))
  {
    RCLCPP_ERROR(
      get_logger(),
      "'%s' names '%s' as the stopped joint, but this component declares no such joint with "
      "both a position command and a position state interface.",
      info_.name.c_str(), named->second.c_str());
    return hardware_interface::CallbackReturn::ERROR;
  }
  stop_position_interface_ =
    stopped->name + "/" + std::string(hardware_interface::HW_IF_POSITION);

  differentiated_.clear();
  for (const auto & joint : info_.joints) {
    if (declares(joint.state_interfaces, hardware_interface::HW_IF_POSITION) &&
      declares(joint.state_interfaces, hardware_interface::HW_IF_VELOCITY))
    {
      differentiated_.push_back(
        DifferentiatedJoint{
          joint.name + "/" + std::string(hardware_interface::HW_IF_POSITION),
          joint.name + "/" + std::string(hardware_interface::HW_IF_VELOCITY), 0.0});
    }
  }

  RCLCPP_WARN(
    get_logger(),
    "'%s' is the ADR-0040 TEST FIXTURE. '%s' has hard stops at [%f, %f] and %zu joint(s) "
    "report a differentiated velocity. Nothing about this component describes real hardware.",
    info_.name.c_str(), named->second.c_str(), stop_lower_, stop_upper_, differentiated_.size());

  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn JointStopSystem::on_activate(
  const rclcpp_lifecycle::State & previous_state)
{
  // Re-baselined on every activation rather than once per process, so a component
  // that is deactivated and activated again does not report one huge first
  // difference across the gap.
  sampled_ = false;
  announced_ = false;
  return mock_components::GenericSystem::on_activate(previous_state);
}

hardware_interface::return_type JointStopSystem::read(
  const rclcpp::Time & time, const rclcpp::Duration & period)
{
  const auto base = mock_components::GenericSystem::read(time, period);
  if (base != hardware_interface::return_type::OK) {
    return base;
  }

  const double tracked = get_state<double>(stop_position_interface_);

  if (!sampled_ && (tracked < stop_lower_ || tracked > stop_upper_)) {
    // Refused rather than clamped. Clamping from outside would move the joint on
    // the first control cycle, and every abort the rig then produced would be one
    // the fixture caused by starting in the wrong place — a rig reporting a fault
    // it manufactured, which is worse than having no rig at all (P6).
    RCLCPP_ERROR(
      get_logger(),
      "'%s' starts at %f, outside its declared stops [%f, %f]. Refusing: a stop that has to "
      "move the arm to take effect manufactures the fault it is supposed to detect.",
      stop_position_interface_.c_str(), tracked, stop_lower_, stop_upper_);
    return hardware_interface::return_type::ERROR;
  }

  const double clamped = std::clamp(tracked, stop_lower_, stop_upper_);
  if (clamped != tracked) {
    set_state(stop_position_interface_, clamped);
    if (!announced_) {
      announced_ = true;
      RCLCPP_WARN(
        get_logger(),
        "'%s' has reached a declared stop at %f and is being held there while the trajectory "
        "advances without it.",
        stop_position_interface_.c_str(), clamped);
    }
  }

  // Velocity last, so that it differentiates the position the controller will
  // actually read — the clamped one — rather than the position before the stop
  // was applied. A held joint must report that it is not moving.
  const double seconds = period.seconds();
  for (auto & joint : differentiated_) {
    const double position = get_state<double>(joint.position);
    const double velocity =
      (sampled_ && seconds > 0.0) ? (position - joint.previous_position) / seconds : 0.0;
    set_state(joint.velocity, velocity);
    joint.previous_position = position;
  }
  sampled_ = true;

  return hardware_interface::return_type::OK;
}

}  // namespace cite_test_hardware

PLUGINLIB_EXPORT_CLASS(cite_test_hardware::JointStopSystem, hardware_interface::SystemInterface)
