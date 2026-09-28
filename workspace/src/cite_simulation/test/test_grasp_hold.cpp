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

// Does the rigid grasp hold take hold of the right thing when it is told to,
// and let go when it is told to? (ADR-0061, ADR-0065)
//
// WHAT THIS FILE USED TO TEST, AND WHY IT DOES NOT ANY MORE. Until ADR-0065 the
// plugin decided for itself that a grasp had begun — the drive joint still for
// the gripper controller's own `stall_timeout`, resting inside the declared
// part-width window, a graspable within radius — and that it had ended, from a
// release margin and that window's open end. Most of this file was that
// decision: an apparatus that drove the jaw joint directly through
// `JointVelocityCmd` and asserted on where the joint came to rest. Every one of
// those thresholds re-derived `cite_skills::gripper_is_holding`, tuning them
// refuted two decisions in a week, and none of them exists now. Tests that drove
// a joint to a position and asserted on what the plugin made of it are therefore
// not adapted, they are DELETED — a test kept alive against a mechanism that is
// gone asserts its own apparatus. The implementation report for ADR-0065 names
// each one and the property it held.
//
// WHAT IS LEFT IS WHAT THE PLUGIN STILL DECIDES, which is the one question the
// cell cannot answer: WHICH declared graspable is in the jaws, and what it is
// welded to. That is exercised here against a real physics step through
// `gz::sim::TestFixture`, exactly as `test_conveyor_carry.cpp` exercises the
// belt, with the attach and detach driven over the same Gazebo transport the
// generated world names — because that, since ADR-0065, is the only thing that
// makes this plugin do anything at all.
//
// `test/worlds/hold.sdf` has the full layout: a fixed wrist with a jaw hanging
// off it, and three boxes — one declared and in reach, one NEARER and not
// declared, one declared and out of reach.

#include <gz/msgs/empty.pb.h>

#include <chrono>
#include <cstdint>
#include <set>
#include <string>
#include <thread>

#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/Server.hh>
#include <gz/sim/TestFixture.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/transport/Node.hh>

#include "gtest/gtest.h"

namespace
{

// --- What test/worlds/hold.sdf describes. One place, so a test cannot assert
// --- against a topic, a link or a model the world does not have.
constexpr const char * kAttachTopic = "/test/hold/grasp/attach";
constexpr const char * kDetachTopic = "/test/hold/grasp/detach";
constexpr const char * kAttachLink = "wrist";
constexpr const char * kJawLink = "jaw";
constexpr const char * kNearBox = "box";
constexpr const char * kNearerUndeclaredBox = "box_undeclared";
constexpr const char * kFarBox = "box_far";

//: How long to let the world run while requiring that NOTHING happens. Long
//: enough that any timer, stall clock or settling rule the plugin might still
//: have would have expired several times over.
constexpr uint64_t kQuietSteps = 2000;  // 2 s at the world's 1 ms step

//: A cap on a bounded wait, never a schedule (P4). Every wait below ends on the
//: event it is waiting for; this only stops a broken build from hanging.
constexpr uint64_t kWaitStepCap = 5000;

//: How often a wait for gz-transport discovery looks again. A poll period on an
//: event — the publisher reporting a connection — and not a guess at how long
//: discovery takes.
constexpr std::chrono::milliseconds kDiscoveryPoll{1};
constexpr int kDiscoveryPolls = 5000;

/// The whole apparatus: the world, the two topics that drive it, and a sampler
/// of what the plugin did.
class Cell
{
public:
  Cell()
  : fixture_(kWorldPath)
  {
    fixture_.OnPostUpdate(
      [this](const gz::sim::UpdateInfo &, const gz::sim::EntityComponentManager & ecm) {
        this->Sample(ecm);
      });
    fixture_.Finalize();
    attach_ = node_.Advertise<gz::msgs::Empty>(kAttachTopic);
    detach_ = node_.Advertise<gz::msgs::Empty>(kDetachTopic);
  }

  /// Advance an exact number of physics steps.
  void Step(uint64_t steps) {fixture_.Server()->Run(true, steps, false);}

  /// Whether both publishers have reached the plugin's subscribers.
  ///
  /// Waited for rather than assumed. gz-transport discovery is asynchronous, and
  /// a message published before the plugin's subscription is matched reaches
  /// nobody — the same class of silence CLAUDE.md §10 records for ROS QoS, and
  /// the reason the cell's own state topic is latched. A test that published
  /// into that gap would fail for a reason that has nothing to do with the
  /// plugin.
  bool Connected()
  {
    for (int i = 0; i < kDiscoveryPolls; ++i) {
      if (attach_.HasConnections() && detach_.HasConnections()) {
        return true;
      }
      std::this_thread::sleep_for(kDiscoveryPoll);
    }
    return false;
  }

  /// Tell the plugin to take hold, and step until it has (or give up).
  bool TellItToTakeHold()
  {
    if (!attach_.Publish(gz::msgs::Empty())) {
      return false;
    }
    return StepUntil([this] {return attached_count_ > 0;});
  }

  /// Tell the plugin to let go, and step until it has (or give up).
  bool TellItToLetGo()
  {
    if (!detach_.Publish(gz::msgs::Empty())) {
      return false;
    }
    return StepUntil([this] {return attached_count_ == 0;});
  }

  /// Step one at a time until `done`, bounded by `kWaitStepCap`.
  template<typename Predicate>
  bool StepUntil(Predicate done)
  {
    for (uint64_t i = 0; i < kWaitStepCap; ++i) {
      Step(1);
      if (done()) {
        return true;
      }
    }
    return false;
  }

  /// How many `DetachableJoint` entities exist right now. Zero, one, or (were
  /// this plugin broken) more than one — never assumed, always counted.
  int AttachedCount() const {return attached_count_;}

  /// Whether `name`'s model is the child of a `DetachableJoint` right now.
  bool IsAttached(const std::string & name) const {return attached_child_ == name;}

  /// The name of the link the weld's PARENT side is on. This is the property
  /// ADR-0023's failure is about: a box welded to a finger follows the finger,
  /// stops being the obstacle the jaws stall against, and the jaws close
  /// straight through it while the weld carries it anyway.
  std::string AttachedTo() const {return attached_parent_;}

  /// Whether the count has ever fallen back to zero since the first attach —
  /// sampled every step, rather than read at the moments a test happens to look.
  /// A test asserting only at the end cannot tell "never let go" from "let go
  /// and took it back".
  bool EverReleased() const {return ever_released_;}

  /// Which model this plugin is holding, by name, or empty. Reported alongside
  /// the assertions that name a different one, so a failure says what was taken.
  std::string AttachedChild() const {return attached_child_;}

  /// Whether a model of this name is in the world at all. Asserted rather than
  /// assumed by the discrimination tests: a rig that renamed a box would make
  /// "it never took the far one" true for the wrong reason.
  ///
  /// Answered from the same post-update sampler everything else here is, because
  /// that is the one place this apparatus is allowed to read the ECM.
  bool HasModel(const std::string & name)
  {
    Step(1);
    return models_.count(name) > 0;
  }

private:
  void Sample(const gz::sim::EntityComponentManager & ecm)
  {
    int count = 0;
    std::string child_name;
    std::string parent_name;
    ecm.Each<gz::sim::components::DetachableJoint>(
      [&](const gz::sim::Entity &, const gz::sim::components::DetachableJoint * joint) -> bool {
        ++count;
        // The child link's own name is "link" (every box shares it) — read the
        // MODEL's name instead, which is what `<graspable>` and this test's
        // assertions both address. The PARENT side is a link of the rig and is
        // read as a link, because which link it is is the whole point.
        const auto model = gz::sim::topLevelModel(joint->Data().childLink, ecm);
        const auto * model_name = ecm.Component<gz::sim::components::Name>(model);
        if (model_name != nullptr) {
          child_name = model_name->Data();
        }
        const auto * link_name =
        ecm.Component<gz::sim::components::Name>(joint->Data().parentLink);
        if (link_name != nullptr) {
          parent_name = link_name->Data();
        }
        return true;
      });
    attached_count_ = count;
    attached_child_ = child_name;
    attached_parent_ = parent_name;

    models_.clear();
    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
      [&](const gz::sim::Entity &, const gz::sim::components::Model *,
      const gz::sim::components::Name * name) -> bool {
        models_.insert(name->Data());
        return true;
      });
    if (count > 0) {
      ever_attached_ = true;
    } else if (ever_attached_) {
      ever_released_ = true;
    }
  }

  static constexpr const char * kWorldPath = CITE_HOLD_WORLD;

  gz::sim::TestFixture fixture_;
  gz::transport::Node node_;
  gz::transport::Node::Publisher attach_;
  gz::transport::Node::Publisher detach_;

  int attached_count_{0};
  std::set<std::string> models_;
  std::string attached_child_;
  std::string attached_parent_;
  bool ever_attached_{false};
  bool ever_released_{false};
};

}  // namespace


/// THE PROPERTY ADR-0065 IS ABOUT. The plugin decides nothing on its own any
/// more: with a declared graspable box sitting well inside the attach radius and
/// nothing said to it, it must take nothing, for as long as the world runs.
///
/// THE REGRESSION THIS LOCKS DOWN is every threshold that used to be here. A
/// stall clock, a part-width window or any other rule that fired on the world's
/// own state would fire in this test, because the box is in reach the whole
/// time and the only thing missing is the message.
TEST(GraspHold, NothingIsTakenUntilTheCellSaysSo)
{
  Cell cell;
  ASSERT_TRUE(cell.HasModel(kNearBox)) << "the rig has no '" << kNearBox << "' to take";
  cell.Step(kQuietSteps);
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "a declared graspable stood inside the attach radius for " << kQuietSteps
    << " steps with nothing published, and the plugin took hold of it anyway";
}


/// An attach message takes the nearest DECLARED graspable within the radius, and
/// neither of the two boxes that fail one of those two tests.
///
/// Both negatives are needed and they fail different rules. `box_far` is
/// declared and out of reach, so it tests `attach_radius_m`.
/// `box_undeclared` is NEARER than the box that must be taken, so it tests the
/// `<graspable>` list and nothing else: a plugin that had stopped reading the
/// list would take it in preference, because it is closer.
TEST(GraspHold, AnAttachMessageTakesTheNearestDeclaredGraspable)
{
  Cell cell;
  ASSERT_TRUE(cell.HasModel(kNearBox));
  ASSERT_TRUE(cell.HasModel(kNearerUndeclaredBox))
    << "the rig has no undeclared box, so this test cannot tell the <graspable> "
    << "list from the radius";
  ASSERT_TRUE(cell.HasModel(kFarBox));
  ASSERT_TRUE(cell.Connected()) << "the plugin never subscribed to " << kAttachTopic;

  EXPECT_TRUE(cell.TellItToTakeHold())
    << "the cell said it was holding and the plugin took nothing";
  EXPECT_EQ(cell.AttachedCount(), 1);
  EXPECT_TRUE(cell.IsAttached(kNearBox))
    << "something was taken, and it was '" << cell.AttachedChild() << "' rather than '"
    << kNearBox << "'";
  EXPECT_FALSE(cell.IsAttached(kNearerUndeclaredBox))
    << "'" << kNearerUndeclaredBox << "' is nearer than '" << kNearBox
    << "' and is not a declared graspable, and it was taken anyway";
  EXPECT_FALSE(cell.IsAttached(kFarBox))
    << "'" << kFarBox << "' is 2.0 m from the attach link against a 0.5 m radius, "
    << "and it was taken anyway";
}


/// THE REGRESSION THIS LOCKS DOWN (ADR-0023, ADR-0061). The weld's parent side
/// must be the declared `attach_link` — the arm's own last link, which nothing
/// this plugin does moves — and never a finger. ADR-0023 welded the box to a
/// finger: the box followed that finger, stopped being the obstacle the jaws
/// were stopping against, and the jaws closed through it to the commanded width
/// while the weld carried it 0.576 m anyway, with `Pick` reporting
/// `EXECUTION_FAILED` 8 times out of 8.
TEST(GraspHold, TheWeldGoesToTheAttachLinkAndNeverAJaw)
{
  Cell cell;
  ASSERT_TRUE(cell.Connected());
  ASSERT_TRUE(cell.TellItToTakeHold()) << "the setup for this test did not attach";

  EXPECT_EQ(cell.AttachedTo(), kAttachLink)
    << "the box is welded to '" << cell.AttachedTo() << "' rather than to the declared "
    << "attach link '" << kAttachLink << "'";
  EXPECT_NE(cell.AttachedTo(), kJawLink)
    << "the box is welded to the jaw, which is ADR-0023's measured failure";
}


/// A detach message releases, and nothing takes the box back afterwards.
///
/// The second half is the regression: the box is still exactly where it was, in
/// reach and declared, so a plugin with any rule of its own left in it would
/// pick it straight back up. Only another message may.
TEST(GraspHold, ADetachMessageReleasesAndNothingTakesItBack)
{
  Cell cell;
  ASSERT_TRUE(cell.Connected());
  ASSERT_TRUE(cell.TellItToTakeHold()) << "the setup for this test did not attach";

  EXPECT_TRUE(cell.TellItToLetGo()) << "the cell said it had let go and the plugin held on";
  EXPECT_EQ(cell.AttachedCount(), 0);
  EXPECT_TRUE(cell.EverReleased());

  cell.Step(kQuietSteps);
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "the box was released and then taken back with nothing published; the plugin "
    << "still has a rule of its own";
}


/// A second attach message while already holding changes nothing. It must not
/// weld a second body to the same wrist, and it must not swap the part.
///
/// This is not hypothetical: the cell republishes its state on every change of
/// custody, and custody becoming unknown and then established again while a part
/// is in the jaws produces exactly this sequence.
TEST(GraspHold, ASecondAttachMessageWhileHoldingChangesNothing)
{
  Cell cell;
  ASSERT_TRUE(cell.Connected());
  ASSERT_TRUE(cell.TellItToTakeHold()) << "the setup for this test did not attach";
  ASSERT_TRUE(cell.IsAttached(kNearBox));

  ASSERT_TRUE(cell.TellItToTakeHold()) << "the second message was never served";
  cell.Step(kQuietSteps);
  EXPECT_EQ(cell.AttachedCount(), 1) << "a second attach welded a second body to one wrist";
  EXPECT_TRUE(cell.IsAttached(kNearBox)) << "the held box changed identity mid-grasp";
  EXPECT_FALSE(cell.EverReleased()) << "a second attach let go of the part first";
}


/// A detach message with nothing held is harmless, and the plugin still works
/// afterwards. `Place` and `Transfer` both report "not holding" on paths where
/// nothing was ever held, so the bridge sends this on an ordinary cycle.
TEST(GraspHold, ADetachMessageWithNothingHeldIsHarmless)
{
  Cell cell;
  ASSERT_TRUE(cell.Connected());
  ASSERT_TRUE(cell.TellItToLetGo()) << "a detach with nothing held did not settle at zero";
  EXPECT_EQ(cell.AttachedCount(), 0);
  EXPECT_FALSE(cell.EverReleased()) << "nothing was ever held, so nothing can have been released";

  EXPECT_TRUE(cell.TellItToTakeHold())
    << "a detach with nothing held left the plugin unable to take hold afterwards";
  EXPECT_TRUE(cell.IsAttached(kNearBox));
}
