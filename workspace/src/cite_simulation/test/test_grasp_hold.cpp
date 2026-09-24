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

// Does the rigid grasp hold actually hold, and does it actually let go at the
// right moment? (ADR-0061, ADR-0064)
//
// WHY THIS FILE EXISTS. `grasp_hold.cpp`'s decision — stalled, resting inside
// the declared hold-position window, and a graspable model within radius — is
// stateful over simulated time and reads three ECM components together, so it
// does not factor into a `zone_rules`-style pure function the way the belt's
// and the beam's geometry do. This is that decision exercised against a real
// physics step through `gz::sim::TestFixture`, exactly as
// `test_conveyor_carry.cpp` exercises the belt.
//
// The drive joint here is driven directly by the test, through
// `JointVelocityCmd`, rather than by a `GripperActionController` — there is no
// controller manager in this fixture and none is needed: what is under test is
// what this plugin does with a joint's own position and velocity, not how a
// controller produces them. `test/worlds/hold.sdf` has the full layout, with
// `hold_position_min_rad`/`hold_position_max_rad` standing in for the window a
// real cell resolves from L0 at generation time (ADR-0061's 2026-09-22
// correction).

#include <chrono>
#include <cmath>
#include <cstdint>
#include <optional>
#include <string>

#include <gz/math/Vector3.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/Server.hh>
#include <gz/sim/TestFixture.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/Joint.hh>
#include <gz/sim/components/JointPosition.hh>
#include <gz/sim/components/JointVelocityCmd.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>

#include "gtest/gtest.h"

namespace
{

// --- What test/worlds/hold.sdf describes. One place, so a test cannot assert
// --- against a joint or a radius the world does not have.
constexpr const char * kJawJoint = "jaw_joint";
constexpr const char * kNearBox = "box";
constexpr const char * kFarBox = "box_far";

//: Comfortably above <stall_velocity_threshold> (0.05 rad/s) and comfortably
//: below the joint's own 10 rad/s limit.
constexpr double kDriveRadS = 1.0;

//: <stall_timeout_s> in the world, plus margin: how long to hold a commanded
//: velocity of zero before asserting on whether a stall was recognised.
constexpr uint64_t kSettleSteps = 200;  // 0.2 s at the world's 1 ms step

//: How long to drive the joint before settling it, and how far that moves it —
//: 0.4 rad, comfortably inside the declared hold-position window
//: ([0.3, 0.6]) and clear of both declared rails (0.0 and 1.0).
constexpr uint64_t kDriveSteps = 400;  // 0.4 s * 1.0 rad/s = 0.4 rad

//: <hold_position_min_rad> and <detach_margin_rad> in the world. This gripper
//: opens towards SMALLER joint values (<open_position> 0.0, <closed_position>
//: 1.0), exactly as the shipped one does, so the window's OPEN end is its
//: minimum — which is what the release now has to be driven past (ADR-0064).
constexpr double kWindowOpenEnd = 0.3;
constexpr double kDetachMarginRad = 0.02;

/// The whole apparatus: the world and a sampler of what the plugin did to it.
class Cell
{
public:
  Cell()
  : fixture_(kWorldPath)
  {
    fixture_.OnPreUpdate(
      [this](const gz::sim::UpdateInfo &, gz::sim::EntityComponentManager & ecm) {
        this->DriveJoint(ecm);
      });
    fixture_.OnPostUpdate(
      [this](const gz::sim::UpdateInfo &, const gz::sim::EntityComponentManager & ecm) {
        this->Sample(ecm);
      });
    fixture_.Finalize();
  }

  /// Advance an exact number of physics steps.
  void Step(uint64_t steps) {fixture_.Server()->Run(true, steps, false);}

  /// Hold a commanded joint velocity for `steps`, then leave it commanded.
  void Drive(double velocity, uint64_t steps)
  {
    commanded_velocity_ = velocity;
    Step(steps);
  }

  /// Drive at `velocity` one step at a time until the joint reaches `target`,
  /// then command zero. Bounded rather than open-ended — `max_steps` is a
  /// safety cap on a broken build, never a schedule (P4): every step this
  /// actually takes is a function of `target`, `velocity` and the physics step,
  /// not of a guessed duration.
  void DriveTo(double target, double velocity, uint64_t max_steps = 5000)
  {
    commanded_velocity_ = velocity;
    for (uint64_t i = 0; i < max_steps; ++i) {
      Step(1);
      if (jaw_position_.has_value() &&
        ((velocity > 0.0 && *jaw_position_ >= target) ||
        (velocity < 0.0 && *jaw_position_ <= target)))
      {
        break;
      }
    }
    commanded_velocity_ = 0.0;
    Step(1);
  }

  /// How many `DetachableJoint` entities exist right now. Zero, one, or (were
  /// this plugin broken) more than one — never assumed, always counted.
  int AttachedCount() const {return attached_count_;}

  /// Whether `name`'s model is the child of a `DetachableJoint` right now.
  bool IsAttached(const std::string & name) const
  {
    return attached_child_ == name;
  }

  /// Whether the count has ever fallen back to zero since the first attach —
  /// sampled every step, on every step, rather than read at the moments a test
  /// happens to look.
  ///
  /// WHY THIS EXISTS RATHER THAN A COUNT AT THE END. A release puts the box
  /// back inside the plugin's own attach conditions: the joint is still inside
  /// the hold-position window and the box is still within the attach radius,
  /// so a wrong release is followed by a fresh attach as soon as the joint has
  /// been still for `stall_timeout_s` again. `AttachedCount()` then reads 1 at
  /// the end of a settle having been 0 in the middle, and a test asserting only
  /// on the end cannot tell "never let go" from "let go and grabbed it back".
  /// That is not hypothetical: it is exactly what the pre-ADR-0064 condition
  /// does to this rig, and it made the first draft of
  /// `OpeningPastTheMarginButNotPastTheWindowDoesNotRelease` pass against the
  /// very code it exists to reject. In the cell the box would have been a free
  /// body for that interval with a pad still against it, which is the whole
  /// defect.
  bool EverReleased() const {return ever_released_;}

  std::optional<double> JawPosition() const {return jaw_position_;}

private:
  void DriveJoint(gz::sim::EntityComponentManager & ecm)
  {
    if (jaw_joint_ == gz::sim::kNullEntity) {
      jaw_joint_ = ecm.EntityByComponents(
        gz::sim::components::Joint(), gz::sim::components::Name(kJawJoint));
      if (jaw_joint_ == gz::sim::kNullEntity) {
        return;
      }
      ecm.CreateComponent(jaw_joint_, gz::sim::components::JointVelocityCmd({0.0}));
    }
    auto * cmd = ecm.Component<gz::sim::components::JointVelocityCmd>(jaw_joint_);
    if (cmd != nullptr && !cmd->Data().empty()) {
      cmd->Data()[0] = commanded_velocity_;
    }
  }

  void Sample(const gz::sim::EntityComponentManager & ecm)
  {
    if (jaw_joint_ != gz::sim::kNullEntity) {
      const auto * position =
        ecm.Component<gz::sim::components::JointPosition>(jaw_joint_);
      if (position != nullptr && !position->Data().empty()) {
        jaw_position_ = position->Data().front();
      }
    }

    int count = 0;
    std::string child_name;
    ecm.Each<gz::sim::components::DetachableJoint>(
      [&](const gz::sim::Entity &, const gz::sim::components::DetachableJoint * joint) -> bool {
        ++count;
        const auto * name = ecm.Component<gz::sim::components::Name>(joint->Data().childLink);
        if (name != nullptr) {
          // The child link's own name is "link" (both boxes share it) — read
          // the MODEL's name instead, which is what `<graspable>` and this
          // test's assertions both address.
          const auto model = gz::sim::topLevelModel(joint->Data().childLink, ecm);
          const auto * model_name = ecm.Component<gz::sim::components::Name>(model);
          if (model_name != nullptr) {
            child_name = model_name->Data();
          }
        }
        return true;
      });
    attached_count_ = count;
    attached_child_ = child_name;
    if (count > 0) {
      ever_attached_ = true;
    } else if (ever_attached_) {
      ever_released_ = true;
    }
  }

  static constexpr const char * kWorldPath = CITE_HOLD_WORLD;

  gz::sim::TestFixture fixture_;

  gz::sim::Entity jaw_joint_{gz::sim::kNullEntity};
  double commanded_velocity_{0.0};
  std::optional<double> jaw_position_;

  int attached_count_{0};
  std::string attached_child_;
  bool ever_attached_{false};
  bool ever_released_{false};
};

}  // namespace


/// A joint that has never moved, resting exactly at `open_position`, must
/// never be read as a stall — however long it sits there and however close a
/// graspable model stands. THE REGRESSION THIS LOCKS DOWN: a `Place` that
/// opens the jaws to release a part would otherwise have this plugin
/// re-attach the very box it was just told to let go of, the instant the
/// joint finished opening and settled at zero. `open_position` (0.0) sits
/// outside the declared hold-position window ([0.3, 0.6] here), so this is
/// the window test rejecting it, not a rail exclusion — see
/// `RestingMidStrokeButOutsideTheWindowIsNeverAStallEither` below for the case
/// a rail exclusion could not reject at all.
TEST(GraspHold, RestingAtTheOpenRailIsNeverAStall)
{
  Cell cell;
  cell.Step(1);
  ASSERT_TRUE(cell.JawPosition().has_value()) << "the jaw joint was never found in the world";
  cell.Step(5 * kSettleSteps);
  EXPECT_NEAR(*cell.JawPosition(), 0.0, 1e-6)
    << "the joint moved on its own with nothing driving it";
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "a joint that has sat at open_position since the world started was read as a stall";
}


/// THE REGRESSION THIS LOCKS DOWN (ADR-0061's 2026-09-22 correction). A rail
/// exclusion — refusing only a joint resting AT `open_position` or
/// `closed_position` — does not reject a rest position that is mid-stroke but
/// still outside the declared part window: exactly the shape of a `Grasp` on
/// empty air, whose ordinary close target is itself mid-stroke. This drives
/// the jaw to 0.15 rad — clear of the open rail's own `detach_margin_rad`
/// (0.02) and clear of the declared window's own lower edge (0.3) — with the
/// near box still well inside `attach_radius_m`, and requires nothing to
/// attach. `AttachesTheNearBoxAndNeverTheFarOne` below is the same rig driven
/// to a position INSIDE the window, where it must attach; the two together
/// are what proves the window, not the rails, decides.
TEST(GraspHold, RestingMidStrokeButOutsideTheWindowIsNeverAStallEither)
{
  Cell cell;
  cell.Drive(kDriveRadS, 150);  // 0.15 s * 1.0 rad/s = 0.15 rad
  ASSERT_TRUE(cell.JawPosition().has_value());
  const double held_at = *cell.JawPosition();
  ASSERT_GT(held_at, 0.02) << "the joint never left the open rail's own margin";
  ASSERT_LT(held_at, 0.3) << "the joint drifted into the declared hold-position window";

  cell.Drive(0.0, kSettleSteps);
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "the joint sat still for longer than stall_timeout_s, well clear of both "
    << "rails but outside the declared hold-position window, with a graspable box "
    << "well inside attach_radius_m — and it attached anyway";
}


/// The whole mechanism, end to end: drive the jaw into the declared
/// hold-position window, let it settle there, and require BOTH the near box
/// to be picked up and the far one to be left alone — proving the radius
/// discriminates and not merely that a stall does something.
TEST(GraspHold, AttachesTheNearBoxAndNeverTheFarOne)
{
  Cell cell;
  cell.Drive(kDriveRadS, kDriveSteps);
  ASSERT_TRUE(cell.JawPosition().has_value());
  const double held_at = *cell.JawPosition();
  ASSERT_GT(held_at, 0.3) << "the joint never reached the declared hold-position window";
  ASSERT_LT(held_at, 0.6) << "the joint overshot the declared hold-position window";

  cell.Drive(0.0, kSettleSteps);
  EXPECT_EQ(cell.AttachedCount(), 1)
    << "the joint sat still for longer than stall_timeout_s with box well inside "
    << "attach_radius_m, and nothing attached";
  EXPECT_TRUE(cell.IsAttached(kNearBox))
    << "something attached, but it was not '" << kNearBox << "'";
  EXPECT_FALSE(cell.IsAttached(kFarBox))
    << "'" << kFarBox << "' is 2.0 m from the attach link against a 0.5 m radius, "
    << "and it was attached anyway";
}


/// Continuing to close further must not detach — a stall that tightens is
/// still the same grasp, and only movement back towards OPEN counts.
TEST(GraspHold, ClosingFurtherAfterTheStallDoesNotRelease)
{
  Cell cell;
  cell.Drive(kDriveRadS, kDriveSteps);
  cell.Drive(0.0, kSettleSteps);
  ASSERT_EQ(cell.AttachedCount(), 1) << "the setup for this test did not attach";

  cell.Drive(kDriveRadS, 50);
  EXPECT_EQ(cell.AttachedCount(), 1)
    << "driving the joint further CLOSED released the box; only opening should";
}


/// THE REGRESSION THIS LOCKS DOWN (ADR-0064). Moving the joint by more than
/// `detach_margin_rad` used to be the WHOLE release test, and that number is
/// the gripper controller's own `goal_tolerance`: it answers "has this joint
/// moved meaningfully?", not "have the pads let go of the part?". At that much
/// past the grasp the jaws are still against the part, so the box became a
/// free body while a pad was still touching it and the opening pad flicked it
/// sideways — about a millimetre during its fall, on one side of every paired
/// run, against the 0.003 mm an undisturbed body travels (ADR-0064).
///
/// This drives the jaw back past `detach_margin_rad` several times over while
/// stopping SHORT of the window's open end, which is where the pads become
/// clear, and requires the box to still be held. Both preconditions are
/// asserted rather than assumed, so a rig that stopped somewhere else fails
/// loudly instead of passing for the wrong reason.
TEST(GraspHold, OpeningPastTheMarginButNotPastTheWindowDoesNotRelease)
{
  Cell cell;
  cell.Drive(kDriveRadS, kDriveSteps);
  cell.Drive(0.0, kSettleSteps);
  ASSERT_EQ(cell.AttachedCount(), 1) << "the setup for this test did not attach";
  ASSERT_TRUE(cell.JawPosition().has_value());
  const double held_at = *cell.JawPosition();

  // Halfway back to the window's open end: far enough past the margin that the
  // old single condition would fire, not far enough for a pad to be clear.
  const double part_way = 0.5 * (held_at + kWindowOpenEnd);
  cell.DriveTo(part_way, -kDriveRadS);
  cell.Drive(0.0, kSettleSteps);

  ASSERT_TRUE(cell.JawPosition().has_value());
  const double opened_to = *cell.JawPosition();
  ASSERT_GT(held_at - opened_to, kDetachMarginRad)
    << "this rig never moved the joint past detach_margin_rad, so it cannot "
    << "distinguish the two conditions at all";
  ASSERT_GT(opened_to, kWindowOpenEnd)
    << "this rig opened the jaws past the hold-position window's open end, "
    << "where a release is correct — it is asserting nothing";

  EXPECT_FALSE(cell.EverReleased())
    << "the jaws opened by " << (held_at - opened_to) << " rad, past "
    << "detach_margin_rad but only to " << opened_to << " rad — still inside the "
    << "hold-position window, so still on the part — and the box was let go anyway";
  EXPECT_EQ(cell.AttachedCount(), 1) << "the box is not held at the end of the move";
  EXPECT_TRUE(cell.IsAttached(kNearBox)) << "the held box changed identity mid-grasp";
}


/// Detach: commanding the jaws back open past the hold-position window's own
/// open end — where no pad can still reach the part — releases whatever was
/// attached, and settling at `open_position` afterwards does not grab it
/// straight back.
///
/// THIS WAS `OpeningReleasesAndSettlingAtOpenStaysReleased`, which drove the
/// joint back a fixed 0.1 rad from a grasp at about 0.4 rad and so landed
/// exactly ON the window's open end (0.3). Under ADR-0064's two conditions
/// that is the boundary itself rather than a case, so the travel is now
/// expressed as a position clear of that end rather than as a duration, and
/// the name says which of the two conditions it pins. Its second half — that a
/// release followed by a settle at `open_position` does not re-attach — is
/// unchanged and is still the regression it always was.
TEST(GraspHold, OpeningPastTheWindowReleasesAndSettlingAtOpenStaysReleased)
{
  Cell cell;
  cell.Drive(kDriveRadS, kDriveSteps);
  cell.Drive(0.0, kSettleSteps);
  ASSERT_EQ(cell.AttachedCount(), 1) << "the setup for this test did not attach";

  // Clear of the window's open end by more than a physics step's worth of
  // travel, so which side of it the joint stopped on is never a rounding
  // question.
  const double clear_of_the_part = kWindowOpenEnd - 0.05;
  cell.DriveTo(clear_of_the_part, -kDriveRadS);
  ASSERT_TRUE(cell.JawPosition().has_value());
  ASSERT_LT(*cell.JawPosition(), kWindowOpenEnd)
    << "this rig never opened the jaws past the hold-position window's open end";
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "the jaws opened to " << *cell.JawPosition() << " rad — past both "
    << "detach_margin_rad and the hold-position window's open end, so wider than "
    << "any opening the grasp predicate would call a grasp — and the box was still attached";

  // Keep going all the way to open_position, exactly as `Place` would, and
  // let it settle there. THE REGRESSION THIS LOCKS DOWN: a plugin that read
  // every mid-stroke stop as a stall would grab the box back the moment the
  // joint next stopped moving, wherever that was; only rest AT the rail is
  // excluded, so this drives all the way there rather than stopping partway.
  cell.DriveTo(0.0, -kDriveRadS);
  cell.Drive(0.0, kSettleSteps);
  EXPECT_EQ(cell.AttachedCount(), 0)
    << "the joint settled at open_position after a release and re-attached the same box";
}
