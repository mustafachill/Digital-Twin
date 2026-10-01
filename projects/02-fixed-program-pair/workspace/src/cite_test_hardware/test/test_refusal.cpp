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

// What the fixture REFUSES, which is the half of ADR-0040 decision 2 that makes
// "not reachable from a production launch path" structural rather than a
// convention.
//
// The argument the ADR makes is: the parameters this component requires have no
// home in the L0 facility model, so a generated description cannot carry them,
// so a component that will not start without them cannot serve as a backend. The
// second clause of that is a property of this class, and this file is where it is
// asserted. Without it the argument rests on a comment.
//
// It is a unit test rather than part of the launch rig because a refusal is
// cheapest to check where nothing has to start: the launch rig can show the
// refusal once, at the cost of a controller manager and a planner, and it cannot
// enumerate the ways a description can be wrong.

#include <memory>
#include <string>
#include <vector>

#include <hardware_interface/hardware_info.hpp>
#include <hardware_interface/types/hardware_component_params.hpp>
#include <hardware_interface/types/hardware_interface_type_values.hpp>
#include <rclcpp/clock.hpp>
#include <rclcpp/logger.hpp>
#include <rclcpp/logging.hpp>

#include "cite_test_hardware/joint_stop_system.hpp"
#include "gtest/gtest.h"

namespace
{

using cite_test_hardware::JointStopSystem;
using hardware_interface::CallbackReturn;

constexpr const char * kJoint = "test_joint1";
constexpr const char * kOtherJoint = "test_joint2";

hardware_interface::InterfaceInfo interface_named(const std::string & name)
{
  hardware_interface::InterfaceInfo info;
  info.name = name;
  return info;
}

/// One joint declaring position command and position/velocity state, which is the
/// shape the generated arm description gives every joint this fixture stops.
hardware_interface::ComponentInfo joint_named(const std::string & name)
{
  hardware_interface::ComponentInfo joint;
  joint.name = name;
  joint.command_interfaces.push_back(interface_named(hardware_interface::HW_IF_POSITION));
  joint.state_interfaces.push_back(interface_named(hardware_interface::HW_IF_POSITION));
  joint.state_interfaces.push_back(interface_named(hardware_interface::HW_IF_VELOCITY));
  return joint;
}

/// A well-formed component, which each test then breaks in exactly one way.
///
/// Written as "start from something that works and break one thing" rather than
/// as five independent fixtures, because a test that builds a broken input from
/// scratch passes just as happily when it is broken in a second, unintended way.
hardware_interface::HardwareInfo well_formed()
{
  hardware_interface::HardwareInfo info;
  info.name = "test_fixture";
  info.type = "system";
  info.joints.push_back(joint_named(kJoint));
  info.joints.push_back(joint_named(kOtherJoint));
  info.hardware_parameters["stop_joint"] = kJoint;
  info.hardware_parameters["stop_lower_rad"] = "-0.1";
  info.hardware_parameters["stop_upper_rad"] = "0.1";
  return info;
}

CallbackReturn initialise(const hardware_interface::HardwareInfo & info)
{
  hardware_interface::HardwareComponentParams params;
  params.hardware_info = info;
  params.logger = rclcpp::get_logger("cite_test_hardware_refusal");
  params.clock = std::make_shared<rclcpp::Clock>(RCL_STEADY_TIME);

  JointStopSystem system;
  return system.init(params);
}

}  // namespace

TEST(JointStopSystemRefusalTest, AWellFormedFixtureInitialises)
{
  // The control. Without it every assertion below could be passing because the
  // component refuses everything, which is a different defect that looks the same
  // from the outside.
  EXPECT_EQ(initialise(well_formed()), CallbackReturn::SUCCESS);
}

TEST(JointStopSystemRefusalTest, NoStopJointIsRefused)
{
  // THE LOAD-BEARING ROW. This is the case a production description would
  // present: the L0 model cannot express a hard stop, so a generated
  // `<ros2_control>` block naming this plugin would carry no `stop_joint` at all.
  // Answering SUCCESS here would make the fixture an ordinary mock wearing a name
  // that says it is not one.
  auto info = well_formed();
  info.hardware_parameters.erase("stop_joint");
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, AnEmptyStopJointIsRefused)
{
  auto info = well_formed();
  info.hardware_parameters["stop_joint"] = "";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, AStopJointThisComponentDoesNotDeclareIsRefused)
{
  // A typo in the joint name would otherwise produce a fixture that loads, never
  // stops anything, and reports every motion as healthy — a rig that quietly
  // stops being a rig.
  auto info = well_formed();
  info.hardware_parameters["stop_joint"] = "a_joint_that_is_not_here";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, AStopJointWithNoPositionCommandIsRefused)
{
  // A joint the controller cannot drive cannot be made to mistrack, so a stop on
  // it can never fire. The mimic joints in this cell's gripper are exactly that
  // shape: state interfaces and no command.
  auto info = well_formed();
  info.joints.front().command_interfaces.clear();
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, MissingBoundsAreRefused)
{
  for (const auto * key : {"stop_lower_rad", "stop_upper_rad"}) {
    auto info = well_formed();
    info.hardware_parameters.erase(key);
    EXPECT_EQ(initialise(info), CallbackReturn::ERROR) << "missing " << key;
  }
}

TEST(JointStopSystemRefusalTest, BoundsThatAreNotNumbersAreRefused)
{
  auto info = well_formed();
  info.hardware_parameters["stop_lower_rad"] = "not a number";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, BoundsThatAreNotFiniteAreRefused)
{
  // `inf` parses. A stop at infinity is a stop that never fires, which is the
  // same silent non-rig as the misspelled joint above.
  auto info = well_formed();
  info.hardware_parameters["stop_upper_rad"] = "inf";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}

TEST(JointStopSystemRefusalTest, AnIntervalThatIsNotAnIntervalIsRefused)
{
  auto info = well_formed();
  info.hardware_parameters["stop_lower_rad"] = "0.1";
  info.hardware_parameters["stop_upper_rad"] = "-0.1";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);

  // And the degenerate case, which would clamp the joint to a single value from
  // the first control cycle — an arm frozen at its start, which is the answer
  // ADR-0037 says is NOT an interruption.
  info.hardware_parameters["stop_lower_rad"] = "0.1";
  info.hardware_parameters["stop_upper_rad"] = "0.1";
  EXPECT_EQ(initialise(info), CallbackReturn::ERROR);
}
