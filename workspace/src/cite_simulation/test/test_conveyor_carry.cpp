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

// Does the belt actually carry a part, and does it let go?
//
// WHY THIS FILE EXISTS. Until it did, nothing at any level commanded a belt and
// then looked at a part: `test_zone_rules` proves the geometry decision in
// isolation, the bring-up scenario never sends a belt command, and the belt
// plugin's only other evidence was a scripted probe run by hand. The defect this
// file locks down — a part carried once and then pinned at zero velocity for the
// rest of the run, unable to fall, be pushed or be lifted — was invisible to
// every one of those, and would have been caught on the first run of the belt
// with a part on it.
//
// It runs a real physics step against the real plugins through
// `gz::sim::TestFixture`, in-process and headless, with no simulator to start and
// no wall-clock schedule: `Server::Run(blocking, steps, unpaused)` advances an
// exact number of 1 ms steps, so every measurement below is a function of the
// step count and nothing else.
//
// Waiting for gz-transport to connect this test to the plugins is the one thing
// that cannot be counted in steps, because discovery is a wall-clock process
// outside the simulation. It is done as a bounded poll on an observable
// condition — a publisher having connections, the belt echoing the speed it was
// given — never as a sleep for a guessed duration (P4).

#include <chrono>
#include <cmath>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <thread>

#include <gz/math/Pose3.hh>
#include <gz/sim/Entity.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/Server.hh>
#include <gz/sim/TestFixture.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/CanonicalLink.hh>
#include <gz/sim/components/LinearVelocityCmd.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>

#include "gtest/gtest.h"
#include "gz/msgs/boolean.pb.h"
#include "gz/msgs/double.pb.h"

namespace
{

// --- What test/worlds/carry.sdf describes. One place, so a test cannot assert
// --- against a belt the world does not have.
constexpr const char * kCommandTopic = "/test/belt/command";
constexpr const char * kStateTopic = "/test/belt/state";
constexpr const char * kBeamTopic = "/test/beam/detection";
constexpr const char * kHighBeamTopic = "/test/beam_high/detection";
constexpr const char * kPart = "workpiece";

constexpr double kBeltSpeedMps = 0.15;
constexpr double kStartX = -0.4;
constexpr double kRestZ = 0.525;
constexpr double kBeltEndX = 0.5;
constexpr double kBeamX = 0.3;

//: Half `<beam_width_m>` in the world, and half the cube. Together they say
//: where a beam that breaks on a leading edge changes state.
constexpr double kBeamRadiusM = 0.002;
constexpr double kPartHalfM = 0.025;

//: The part's ORIGIN when its leading edge first reaches the beam, and when its
//: trailing edge finally leaves it. These are the two numbers the fix is about.
constexpr double kLeadingEdgeX = kBeamX - kBeamRadiusM - kPartHalfM;
constexpr double kTrailingEdgeX = kBeamX + kBeamRadiusM + kPartHalfM;

//: Where the defect used to put the break: the origin test reported the part
//: only once its CENTRE reached the beam, a quarter of the part late. It is
//: written down so that the assertion below is visibly a discriminator and not
//: just a number — 25 mm separates the two, and the tolerance is 10.
constexpr double kOriginTestX = kBeamX - kBeamRadiusM;

//: How far a measured edge may sit from where the geometry says it is. The part
//: advances 0.15 mm per step and the state arrives over transport rather than
//: on the step it changed, so a few millimetres are not attributable; 25 mm,
//: which is what the defect was worth, is.
constexpr double kEdgeToleranceM = 0.010;

//: 1 ms, matching <max_step_size> in the world.
constexpr double kStepS = 0.001;
constexpr uint64_t kStepsPerSecond = 1000;

//: How far a measured distance may sit from the distance the belt was asked to
//: move the part. Transport delivers the command between two steps rather than
//: on one, so the first millimetre of travel is not attributable to a step
//: count; everything after it is.
constexpr double kTravelToleranceM = 0.01;

//: What counts as "did not move" for a belt that was never commanded, and for a
//: belt commanded to zero. A part released by the belt coasts to a stop under
//: friction rather than stopping dead, so this is not zero.
constexpr double kStationaryToleranceM = 0.01;

/// Poll a condition until it holds, or give up. Returns whether it held.
///
/// A deadline on an observable condition, not a sleep: the loop exits the
/// instant the condition is true, and the bound exists only so that a broken
/// build fails instead of hanging.
bool WaitFor(const std::function<bool()> & condition, int attempts = 500)
{
  for (int attempt = 0; attempt < attempts; ++attempt) {
    if (condition()) {
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return condition();
}

/// The part's pose and whether anything still commands its velocity.
///
/// Sampled in post-update, which runs on the thread that called `Run`, so the
/// test body reads it between runs without synchronisation.
struct PartState
{
  gz::math::Pose3d pose;
  bool found{false};
  bool velocity_commanded{false};
};

/// The whole apparatus: the world, the part sampler, and the two transport ends.
class Cell
{
public:
  Cell()
  : fixture_(kWorldPath)
  {
    fixture_.OnPostUpdate(
      [this](const gz::sim::UpdateInfo &, const gz::sim::EntityComponentManager & ecm) {
        this->Sample(ecm);
      }).Finalize();

    command_ = node_.Advertise<gz::msgs::Double>(kCommandTopic);
    node_.Subscribe(
      kStateTopic, std::function<void(const gz::msgs::Double &)>(
        [this](const gz::msgs::Double & message) {
          const std::lock_guard<std::mutex> lock(mutex_);
          reported_speed_ = message.data();
        }));
    node_.Subscribe(
      kBeamTopic, std::function<void(const gz::msgs::Boolean &)>(
        [this](const gz::msgs::Boolean & message) {
          const std::lock_guard<std::mutex> lock(mutex_);
          beam_ = message.data();
          beam_ever_broken_ = beam_ever_broken_ || message.data();
        }));
    node_.Subscribe(
      kHighBeamTopic, std::function<void(const gz::msgs::Boolean &)>(
        [this](const gz::msgs::Boolean & message) {
          const std::lock_guard<std::mutex> lock(mutex_);
          high_beam_ever_broken_ = high_beam_ever_broken_ || message.data();
        }));
  }

  /// Advance an exact number of physics steps.
  void Step(uint64_t steps) {fixture_.Server()->Run(true, steps, false);}

  const PartState & Part() const {return part_;}

  bool Beam() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return beam_;
  }

  bool BeamEverBroken() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return beam_ever_broken_;
  }

  bool HighBeamEverBroken() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return high_beam_ever_broken_;
  }

  void ForgetBeamHistory()
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    beam_ever_broken_ = false;
  }

  /// Command the belt and return once it has said so on its state topic.
  ///
  /// The belt's acknowledgement is the event this waits on. Publishing and
  /// assuming delivery is what makes a test like this flaky; publishing and
  /// waiting for the belt to report the value makes the wait a fact about the
  /// system rather than about the machine it runs on.
  bool Command(double speed)
  {
    if (!WaitFor([this] {return command_.HasConnections();})) {
      return false;
    }
    gz::msgs::Double message;
    message.set_data(speed);
    for (int attempt = 0; attempt < 40; ++attempt) {
      command_.Publish(message);
      Step(50);
      const std::lock_guard<std::mutex> lock(mutex_);
      if (reported_speed_.has_value() && std::abs(*reported_speed_ - speed) < 1e-9) {
        return true;
      }
    }
    return false;
  }

private:
  void Sample(const gz::sim::EntityComponentManager & ecm)
  {
    const auto model = ecm.EntityByComponents(
      gz::sim::components::Model(), gz::sim::components::Name(kPart));
    if (model == gz::sim::kNullEntity) {
      part_.found = false;
      return;
    }
    part_.found = true;
    part_.pose = gz::sim::worldPose(model, ecm);

    part_.velocity_commanded = false;
    ecm.Each<gz::sim::components::CanonicalLink, gz::sim::components::ParentEntity>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::CanonicalLink *,
      const gz::sim::components::ParentEntity * parent) -> bool {
        if (parent->Data() != model) {
          return true;
        }
        part_.velocity_commanded =
        ecm.Component<gz::sim::components::LinearVelocityCmd>(entity) != nullptr;
        return false;
      });
  }

  static constexpr const char * kWorldPath = CITE_CARRY_WORLD;

  gz::sim::TestFixture fixture_;
  PartState part_;

  gz::transport::Node node_;
  gz::transport::Node::Publisher command_;

  mutable std::mutex mutex_;
  std::optional<double> reported_speed_;
  bool beam_{false};
  bool beam_ever_broken_{false};
  bool high_beam_ever_broken_{false};
};

}  // namespace


/// An uncommanded belt is inert.
///
/// Not an optimisation and not a nicety: a plugin that nudged parts around while
/// nobody had asked for a belt to run would be a source of motion no report
/// could attribute.
TEST(ConveyorCarry, AnUncommandedBeltCarriesNothing)
{
  Cell cell;
  cell.Step(500);
  ASSERT_TRUE(cell.Part().found);
  const double settled = cell.Part().pose.Pos().X();
  EXPECT_NEAR(settled, kStartX, kStationaryToleranceM);
  EXPECT_NEAR(cell.Part().pose.Pos().Z(), kRestZ, 0.005)
    << "the part is not resting on the belt, so nothing below measures carrying";

  cell.Step(2 * kStepsPerSecond);
  EXPECT_NEAR(cell.Part().pose.Pos().X(), settled, kStationaryToleranceM)
    << "an idle belt moved the part";
  EXPECT_FALSE(cell.Beam()) << "the beam reports a part it cannot see";
}


/// WHERE the beam changes state, not merely that it does.
///
/// THE DEFECT THIS LOCKS DOWN. The beam was a box tested against the
/// work-piece's model ORIGIN, so it reported a 50 mm cube only once the cube's
/// centre reached it — a quarter of a part late in both directions. Two measured
/// consequences, one recorded per axis and both the same bug:
///
///   * along the belt, `continuous_line` stopped `conveyor_1` on that late edge
///     and parked every piece 69 mm short of `arm_2`'s grasp. The arm closed on
///     air — `commanded 45.0 mm, reached 46.0 mm, stalled=false` — and the line
///     stopped at milestone 4 of 10 on four runs out of four;
///   * across it, the sensor had a window of part-CENTRE heights instead of a
///     line, so it saw a part between 20 mm and 100 mm tall and missed anything
///     outside that, while the physical cell saw all of it.
///
/// `test_zone_rules` proves the geometry decides this correctly. This proves the
/// plugin asks it the right question, against a real body in a real physics
/// step — which is the half that was wrong, since the geometry it used to ask
/// about was a point.
///
/// The tempting repair was to slide the beam until the line passed. It was
/// refused twice before this fix and is refused here: a real through beam breaks
/// on a leading edge, so compensating for a point test would have tuned the
/// layout to a simulator artefact and left the physical cell parking its parts
/// 25 mm elsewhere (P2).
TEST(ConveyorCarry, TheBeamBreaksOnTheLeadingEdgeAndClearsOnTheTrailing)
{
  Cell cell;
  cell.Step(500);
  ASSERT_TRUE(cell.Part().found);
  ASSERT_FALSE(cell.Beam());
  ASSERT_LT(cell.Part().pose.Pos().X(), kLeadingEdgeX)
    << "the part is already inside the beam before the belt has been commanded";

  ASSERT_TRUE(cell.Command(kBeltSpeedMps)) << "the belt never acknowledged the command";

  // Sampled every five steps so that the recorded position is a function of the
  // step count, not of how fast the machine ran. Both edges are collected in one
  // pass: a beam that latched on would never produce the second.
  std::optional<double> broke_at;
  std::optional<double> cleared_at;
  bool was_blocked = false;
  while (cell.Part().pose.Pos().X() < kTrailingEdgeX + 0.1 &&
    cell.Part().pose.Pos().X() < kBeltEndX)
  {
    cell.Step(5);
    const double x = cell.Part().pose.Pos().X();
    const bool blocked = cell.Beam();
    if (blocked && !was_blocked && !broke_at.has_value()) {
      broke_at = x;
    }
    if (!blocked && was_blocked && broke_at.has_value() && !cleared_at.has_value()) {
      cleared_at = x;
    }
    was_blocked = blocked;
  }

  ASSERT_TRUE(broke_at.has_value()) << "the part was carried through the beam and it never broke";
  EXPECT_NEAR(*broke_at, kLeadingEdgeX, kEdgeToleranceM)
    << "the beam broke with the part's origin at " << *broke_at << " m. A beam at x = "
    << kBeamX << " is reached by the leading edge of a 50 mm part when the origin is at "
    << kLeadingEdgeX << " m; testing the origin instead would put it at " << kOriginTestX
    << " m, which is the defect";

  ASSERT_TRUE(cleared_at.has_value()) << "the beam never cleared: it latched on the first part";
  EXPECT_NEAR(*cleared_at, kTrailingEdgeX, kEdgeToleranceM)
    << "the beam cleared with the part's origin at " << *cleared_at
    << " m, rather than once the trailing edge was through at " << kTrailingEdgeX << " m";

  // The height half, and the case the cell itself has no instance of: a beam
  // mounted 150 mm above the belt is passed under by a 50 mm cube and must stay
  // clear the whole way. Under the old window this was decided by where the
  // part's CENTRE was, which is not what a beam measures.
  EXPECT_FALSE(cell.HighBeamEverBroken())
    << "a beam 150 mm above the belt reported a 50 mm part that passed underneath it";
}


/// The whole point of the belt, end to end: it carries, the beam sees the part
/// pass, it stops, and — the part that was broken — it lets go.
TEST(ConveyorCarry, CarriesBreaksTheBeamStopsAndReleases)
{
  Cell cell;
  cell.Step(500);
  ASSERT_TRUE(cell.Part().found);
  ASSERT_FALSE(cell.Beam());

  // --- It carries. ---------------------------------------------------------
  ASSERT_TRUE(cell.Command(kBeltSpeedMps)) << "the belt never acknowledged the command";
  const double from = cell.Part().pose.Pos().X();
  ASSERT_LT(from, kBeamX) << "the part is already past the beam before the run starts";

  constexpr uint64_t kRunSteps = kStepsPerSecond;
  cell.Step(kRunSteps);
  const double travelled = cell.Part().pose.Pos().X() - from;
  EXPECT_NEAR(travelled, kBeltSpeedMps * kRunSteps * kStepS, kTravelToleranceM)
    << "the belt was commanded " << kBeltSpeedMps << " m/s and moved the part " << travelled
    << " m in " << kRunSteps * kStepS << " s";
  EXPECT_NEAR(cell.Part().pose.Pos().Z(), kRestZ, 0.005)
    << "the part left the belt surface while being carried";

  // --- The beam sees it pass. ----------------------------------------------
  // Carried on until the part is clear of the beam, so that both edges are
  // observed: a beam that latched on would pass the first half of this.
  while (cell.Part().pose.Pos().X() < kBeamX + 0.1 && cell.Part().pose.Pos().X() < kBeltEndX) {
    cell.Step(100);
  }
  EXPECT_TRUE(cell.BeamEverBroken())
    << "the part was carried through the beam at x = " << kBeamX << " and the beam never saw it";
  EXPECT_FALSE(cell.Beam()) << "the beam is still broken with the part past it";

  // --- It stops. -----------------------------------------------------------
  ASSERT_TRUE(cell.Command(0.0)) << "the belt never acknowledged being stopped";
  const double stopped_at = cell.Part().pose.Pos().X();
  cell.Step(2 * kStepsPerSecond);
  EXPECT_NEAR(cell.Part().pose.Pos().X(), stopped_at, kStationaryToleranceM)
    << "the part kept moving after the belt was commanded to zero";

  // --- It lets go. ---------------------------------------------------------
  // The regression. A part that has been carried and then released must be an
  // ordinary free body again: the belt must not still be holding its velocity
  // at whatever it last wrote. It was, and the symptom was a part that could not
  // fall — it left the end of the belt and descended at about 12 mm/s, which no
  // reading of the pose alone would explain.
  ASSERT_TRUE(cell.Command(kBeltSpeedMps));
  cell.Step(4 * kStepsPerSecond);
  EXPECT_LT(cell.Part().pose.Pos().X(), kBeltEndX + 0.5)
    << "the part is nowhere near where leaving the belt would put it";
  EXPECT_LT(cell.Part().pose.Pos().Z(), 0.1)
    << "the part was carried off the end of the belt and did not fall: it is "
    << (kRestZ - cell.Part().pose.Pos().Z()) << " m below the belt surface after 4 s, "
    << "and free fall from there reaches the floor in under half a second";
  EXPECT_FALSE(cell.Part().velocity_commanded)
    << "the belt is still commanding the velocity of a part it no longer carries";
}
