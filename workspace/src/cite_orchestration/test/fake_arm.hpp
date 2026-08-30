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

#include <cstdint>
#include <memory>
#include <string>

#include <rclcpp/rclcpp.hpp>

namespace cite_orchestration_test
{

/// The prefix every fixture in these tests advertises under.
extern const char * const kFixturePrefix;

/// The four actions one arm's skill server serves, succeeding immediately unless
/// a test asks for otherwise.
///
/// Immediate rather than slow: a server that took time would make the tests
/// slower without making them stricter, because what is under test is sequence
/// and ownership rather than duration. `hold_detect` is the one exception, and it
/// exists because a cancellation can only be observed on a goal that is still
/// running.
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

  /// Make every subsequent `pick` goal come back with `code` instead of SUCCESS.
  ///
  /// The result is still SUCCEEDED at the action layer, exactly as a real skill
  /// server reports a refusal: `ResultCode` is the channel a recovery branch
  /// reacts to, and an aborted goal would be testing `rclcpp_action`'s transport
  /// rather than L4's policy. The same shape `test_skill_goals.cpp` uses.
  ///
  /// It exists because the recovery branch is otherwise unreachable in this
  /// fixture: every server succeeds, so the tree never leaves its nominal
  /// branch, and what the branch does on an ESCALATE was evidenced by nothing.
  void fail_pick_with(uint8_t code);

  /// What this arm's `MoveTo` server answers from now on.
  ///
  /// It is how a station subtree is driven to FAILURE **without** anything
  /// classifying why, which is the one route into the fault branch that leaves no
  /// station BLOCKED or FAULTED: a retry verdict returns the station to WAITING
  /// and SUCCESS, the recover `Sequence` walks on to `MoveToHome`, and a
  /// `MoveToHome` that fails there fails the Sequence, the Fallback, the Repeat
  /// and the subtree. `OnFault` has to latch that too, or the run exits 0.
  void fail_move_to_with(uint8_t code);

  /// What this arm's `Detect` server answers from now on.
  ///
  /// The ONE failure a station subtree can suffer before it has taken custody of
  /// anything: `DetectAt` stands above `TakeCustody` in the shipped tree, so a
  /// station that fails here owns no work-piece and is the only case in which
  /// ADR-0046's custody precondition leaves the retry path reachable. Every leaf
  /// below `TakeCustody` — the pick, the claims, the handoff, the place — fails
  /// with the piece assigned to the station, and a retry there is refused.
  void fail_detect_with(uint8_t code);

  /// Hold every subsequent `detect` goal open, or stop holding.
  ///
  /// A HELD GOAL IS THE ONLY WAY TO OBSERVE A CANCELLATION. `line_tree.hpp` says
  /// in prose that a station's FAILURE halts its SIBLINGS and so cancels the goal
  /// each was waiting on, and the whole design of the fault branch rests on that
  /// — but every server here answers immediately, so no sibling ever had an
  /// outstanding goal for the halt to reach and the property was asserted nowhere.
  /// A held goal gives the test one, and `detect_cancellations` is where it is
  /// counted.
  ///
  /// `detect` rather than another action because it is the first skill in a
  /// station's cycle, so a station reaches it without needing anything else to
  /// have succeeded first.
  void hold_detect(bool holding);

  /// How many `detect` goals this arm saw cancelled through to the end.
  ///
  /// Counted on the SERVER side. The claim is that the tree's halt reached the far
  /// side of the action; a client-side count would be the leaf agreeing with
  /// itself.
  int detect_cancellations() const;

private:
  struct Servers;
  std::unique_ptr<Servers> servers_;
};

}  // namespace cite_orchestration_test

#endif  // FAKE_ARM_HPP_
