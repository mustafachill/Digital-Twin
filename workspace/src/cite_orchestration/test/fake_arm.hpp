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

// The four L3 skill servers one arm serves, as a test fixture.
//
// REAL ACTION SERVERS, not mocks. What the line tests are about is the order
// goals arrive in and who owns the work-piece while they do, and both of those
// are only observable from the far side of the action. A mock would let the
// sequence be asserted in the shape the test believes it built.
//
// BEHIND A POINTER TO AN IMPLEMENTATION, which is not a style preference. The
// four `rclcpp_action` server templates plus BehaviorTree.CPP in one translation
// unit exceed the per-job memory budget `./scripts/build` derives, and the OOM
// killer reports it as `c++: fatal error: Killed signal terminated program
// cc1plus` — which names neither memory nor the file. Splitting the servers into
// their own translation unit is what keeps this package buildable on a machine
// that is also running something else.
//
// EVERY NAME IT ADVERTISES IS OUTSIDE `/cite/`. `colcon` runs packages
// concurrently on one ROS domain, and a fixture that once advertised a
// production action name made two servers answer one action — each suite passed
// alone, both failed together, and it cost four agents a false "known-red"
// belief.

#ifndef FAKE_ARM_HPP_
#define FAKE_ARM_HPP_

#include <memory>
#include <string>

#include <rclcpp/rclcpp.hpp>

namespace cite_orchestration_test
{

/// The prefix every fixture in these tests advertises under.
extern const char * const kFixturePrefix;

/// The four actions one arm's skill server serves, all succeeding immediately.
///
/// Immediate rather than slow: a server that took time would make the tests
/// slower without making them stricter, because what is under test is sequence
/// and ownership rather than duration.
class FakeArm
{
public:
  FakeArm(const rclcpp::Node::SharedPtr & node, const std::string & asset);
  ~FakeArm();

  FakeArm(const FakeArm &) = delete;
  FakeArm & operator=(const FakeArm &) = delete;

  /// The action name prefix for one asset. The tests hand the same string to the
  /// coordinator as a parameter, so what the leaves call and what this serves
  /// cannot drift apart.
  static std::string prefix(const std::string & asset);

  int move_to_goals() const;
  int pick_goals() const;
  int place_goals() const;
  int detect_goals() const;

private:
  struct Servers;
  std::unique_ptr<Servers> servers_;
};

}  // namespace cite_orchestration_test

#endif  // FAKE_ARM_HPP_
