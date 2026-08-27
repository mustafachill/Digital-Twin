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

// Indexing the belt (ADR-0032), driven through real topics.
//
// WHAT IS ACTUALLY UNDER TEST. Not that `stop()` publishes a zero — that half was
// never in doubt. What is in doubt, and what a plausible wrong implementation
// gets wrong, is the DECISION: which edge stops which belt, which belt is left
// running, whether a level is mistaken for a transition, and whether the speed
// that comes back out is the model's or one the code invented. So every
// assertion below reads the setpoint off the command topic, which is the only
// place the rest of the system can see it, and every stimulus is a real
// `DetectionEvent` on a real subscription.
//
// FIXTURE NAMES, outside `/cite/`, where no generated name can ever land. A test
// that used a realistic topic would be squatting on the topic the bridge carries,
// and `colcon` runs packages concurrently on one ROS domain.

#include <chrono>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float64.hpp>

#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/qos.hpp>

#include "gtest/gtest.h"
#include "cite_orchestration/conveyor_index.hpp"

namespace
{

using cite_interfaces::msg::DetectionEvent;
using cite_orchestration::ConveyorDrive;
using cite_orchestration::ConveyorDrivesByAsset;
using cite_orchestration::ConveyorIndex;
using namespace std::chrono_literals;

constexpr const char * kIndexedBelt = "conveyor_indexed";
constexpr const char * kFreeBelt = "conveyor_free";
constexpr const char * kIndexedCommand = "/conveyor_index_test/indexed/command";
constexpr const char * kFreeCommand = "/conveyor_index_test/free/command";
constexpr const char * kBeam = "/conveyor_index_test/beam/detection";
constexpr const char * kOtherBeam = "/conveyor_index_test/other_beam/detection";

//: The declared drive speed. One number, and the test reads it back rather than
//: comparing against a second copy written into an assertion.
constexpr double kInstalledSpeed = 0.15;

ConveyorDrivesByAsset fixture_drives()
{
  ConveyorDrivesByAsset drives;
  drives[kIndexedBelt] = ConveyorDrive{kIndexedCommand, kInstalledSpeed};
  drives[kFreeBelt] = ConveyorDrive{kFreeCommand, kInstalledSpeed};
  return drives;
}

/// A `DetectionEvent` carrying a transition, or carrying none.
DetectionEvent edge(uint8_t state, uint8_t previous)
{
  DetectionEvent event;
  event.state = state;
  event.previous_state = previous;
  return event;
}

/// One belt's command topic, read from the outside.
class Setpoint
{
public:
  Setpoint(rclcpp::Node::SharedPtr node, const std::string & topic)
  {
    subscription_ = node->create_subscription<std_msgs::msg::Float64>(
      topic, cite::qos::command(),
      [this](std_msgs::msg::Float64::SharedPtr message) {
        received_.push_back(message->data);
      });
  }

  std::size_t count() const {return received_.size();}
  std::optional<double> latest() const
  {
    return received_.empty() ? std::nullopt : std::optional<double>(received_.back());
  }
  const std::vector<double> & all() const {return received_;}

private:
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr subscription_;
  std::vector<double> received_;
};

class IndexedBelts : public ::testing::Test
{
protected:
  void SetUp() override
  {
    node_ = std::make_shared<rclcpp::Node>("conveyor_index_test");
    indexed_ = std::make_unique<Setpoint>(node_, kIndexedCommand);
    free_ = std::make_unique<Setpoint>(node_, kFreeCommand);
    beam_ = node_->create_publisher<DetectionEvent>(kBeam, cite::qos::event());
    other_beam_ = node_->create_publisher<DetectionEvent>(kOtherBeam, cite::qos::event());

    index_ = std::make_shared<ConveyorIndex>(node_, fixture_drives());
    // Only the belt that feeds a station with an actor is indexed. `kFreeBelt`
    // stands in for `conveyor_3`, which feeds a sink.
    index_->index_on(kBeam, DetectionEvent::STATE_BLOCKED, kIndexedBelt);

    settle();
  }

  /// Let discovery and delivery happen. A BOUND on how long the test will wait,
  /// not a schedule: every assertion is about what was received, and a message
  /// that has not arrived by the end of this has not arrived.
  void settle(std::chrono::milliseconds budget = 500ms)
  {
    const auto deadline = std::chrono::steady_clock::now() + budget;
    while (std::chrono::steady_clock::now() < deadline) {
      rclcpp::spin_some(node_);
      std::this_thread::sleep_for(5ms);
    }
  }

  rclcpp::Node::SharedPtr node_;
  std::unique_ptr<Setpoint> indexed_;
  std::unique_ptr<Setpoint> free_;
  rclcpp::Publisher<DetectionEvent>::SharedPtr beam_;
  rclcpp::Publisher<DetectionEvent>::SharedPtr other_beam_;
  std::shared_ptr<ConveyorIndex> index_;
};

TEST_F(IndexedBelts, ARunAllStartsEveryBeltAtTheSpeedTheModelDeclares)
{
  // The setpoint's owner. Before ADR-0032 nothing in the running system commanded
  // a conveyor and a scenario supplied the value, which it reported as a gap.
  index_->run_all();
  settle();

  ASSERT_TRUE(indexed_->latest().has_value());
  ASSERT_TRUE(free_->latest().has_value());
  EXPECT_DOUBLE_EQ(indexed_->latest().value(), kInstalledSpeed);
  EXPECT_DOUBLE_EQ(free_->latest().value(), kInstalledSpeed);
}

TEST_F(IndexedBelts, ABeltStopsOnTheEdgeItsStationActsOn)
{
  index_->run_all();
  settle();
  ASSERT_DOUBLE_EQ(indexed_->latest().value(), kInstalledSpeed);

  beam_->publish(edge(DetectionEvent::STATE_BLOCKED, DetectionEvent::STATE_CLEAR));
  settle();

  ASSERT_TRUE(indexed_->latest().has_value());
  EXPECT_DOUBLE_EQ(indexed_->latest().value(), 0.0)
    << "the belt kept running through the transition that starts the station that picks "
       "from it, so the work-piece rides past the pick point";
}

TEST_F(IndexedBelts, ABeltThatFeedsNoActorIsNeverStopped)
{
  // `station_accumulation` is a sink: a trigger and no actor, so no
  // `CompleteHandoff` to run its belt again on. A rule keyed on the trigger
  // alone would stop `conveyor_3` for ever.
  index_->run_all();
  settle();
  const std::size_t before = free_->count();

  beam_->publish(edge(DetectionEvent::STATE_BLOCKED, DetectionEvent::STATE_CLEAR));
  other_beam_->publish(edge(DetectionEvent::STATE_BLOCKED, DetectionEvent::STATE_CLEAR));
  settle();

  EXPECT_FALSE(index_->indexes(kFreeBelt));
  EXPECT_TRUE(index_->indexes(kIndexedBelt));
  EXPECT_EQ(free_->count(), before) << "a belt nothing indexes was commanded anyway";
  ASSERT_TRUE(free_->latest().has_value());
  EXPECT_DOUBLE_EQ(free_->latest().value(), kInstalledSpeed);
}

TEST_F(IndexedBelts, ALevelIsNotAnEdgeAndDoesNotStopTheBelt)
{
  // `previous_state` is carried so a consumer can detect a transition without
  // keeping its own history, and the detector's FIRST report sets it equal on
  // purpose — a beam already broken at start-up is not an arrival. A belt stopped
  // by that report would be stopped before the line had begun.
  index_->run_all();
  settle();
  const std::size_t before = indexed_->count();

  index_->run(kIndexedBelt);
  settle();
  const std::size_t after_run = indexed_->count();
  ASSERT_GT(after_run, before);

  beam_->publish(edge(DetectionEvent::STATE_BLOCKED, DetectionEvent::STATE_BLOCKED));
  settle();

  EXPECT_EQ(indexed_->count(), after_run) << "a level was mistaken for a transition";
  EXPECT_DOUBLE_EQ(indexed_->latest().value(), kInstalledSpeed);
}

TEST_F(IndexedBelts, TheOppositeEdgeDoesNotStopTheBelt)
{
  // The station acts on BLOCKED. The piece clearing the beam is the piece having
  // left, and a belt stopped by it would stop for a work-piece that is gone.
  index_->run_all();
  settle();
  const std::size_t before = indexed_->count();

  beam_->publish(edge(DetectionEvent::STATE_CLEAR, DetectionEvent::STATE_BLOCKED));
  settle();

  EXPECT_EQ(indexed_->count(), before);
  EXPECT_DOUBLE_EQ(indexed_->latest().value(), kInstalledSpeed);
}

TEST_F(IndexedBelts, RunPutsTheBeltBackToTheDeclaredSpeedAndNotToOneOfItsOwn)
{
  // The restart speed is `installed_speed_mps` — the value the model already
  // carries — rather than a second copy of it (P1). Read back from the topic
  // because a constant compared against itself proves nothing.
  index_->run_all();
  settle();
  beam_->publish(edge(DetectionEvent::STATE_BLOCKED, DetectionEvent::STATE_CLEAR));
  settle();
  ASSERT_DOUBLE_EQ(indexed_->latest().value(), 0.0);

  EXPECT_TRUE(index_->run(kIndexedBelt));
  settle();
  EXPECT_DOUBLE_EQ(indexed_->latest().value(), kInstalledSpeed);
}

TEST_F(IndexedBelts, ABeltTheModelNeverDeclaredIsRefusedRatherThanInvented)
{
  EXPECT_FALSE(index_->declares("conveyor_that_does_not_exist"));
  EXPECT_FALSE(index_->run("conveyor_that_does_not_exist"));
  EXPECT_FALSE(index_->stop("conveyor_that_does_not_exist"));
}

TEST_F(IndexedBelts, IndexingIsRefusedForABeltWithNoDeclaredDrive)
{
  // Nothing is invented: a belt with no drive cannot be indexed, and asking for
  // it does not create a subscription that would stop a belt this object cannot
  // start again.
  index_->index_on(kOtherBeam, DetectionEvent::STATE_BLOCKED, "conveyor_that_does_not_exist");
  EXPECT_FALSE(index_->indexes("conveyor_that_does_not_exist"));
}

TEST(ConveyorIndexDelivery, TheStartingSetpointReachesASubscriberThatWasNotMatchedYet)
{
  // THE DEFECT EVERY TEST ABOVE IS BLIND TO, and it kept the line's belts still.
  //
  // `IndexedBelts` creates its subscribers first and then lets discovery settle,
  // so by the time it calls `run_all()` the publishers are matched and the
  // message lands. Production does the opposite: `line_orchestrator` constructs
  // the `ConveyorIndex` inside the topology callback and calls `run_all()` from
  // the same callback a tree-construction later, with a matched-subscriber count
  // of zero. Reliable QoS is a promise about MATCHED subscribers, so that
  // publication went nowhere — for as long as ADR-0032 has existed. It was
  // invisible because `tests/scenarios/continuous_line.py` published the same
  // setpoint ten times itself and was starting the belts.
  //
  // This orders it the way production does: index first, command immediately,
  // subscribe afterwards. A subscriber appearing is an event, and the belt's
  // current setpoint is sent when it does — so the value arrives without anything
  // here retrying or waiting for a guessed duration.
  auto node = std::make_shared<rclcpp::Node>("conveyor_index_late_subscriber_test");

  constexpr const char * kBelt = "conveyor_late";
  constexpr const char * kCommand = "/conveyor_index_test/late/conveyor/command";
  ConveyorDrivesByAsset drives;
  drives[kBelt] = ConveyorDrive{kCommand, kInstalledSpeed};

  auto index = std::make_shared<ConveyorIndex>(node, drives);
  index->run_all();

  Setpoint late(node, kCommand);
  const auto deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < deadline && late.count() == 0) {
    rclcpp::spin_some(node);
    std::this_thread::sleep_for(5ms);
  }

  ASSERT_TRUE(late.latest().has_value())
    << "the belt was commanded before any subscriber had been matched and the setpoint "
       "was never delivered, so the belt stands still and nothing reports it";
  EXPECT_DOUBLE_EQ(late.latest().value(), kInstalledSpeed);
}

TEST(ConveyorIndexDelivery, ASubscriberThatArrivesAfterAStopIsToldTheBeltIsStopped)
{
  // The re-send states the CURRENT setpoint, not the starting one. A bridge that
  // restarts while a station is picking must learn that its belt is stopped;
  // being told the installed speed instead would run a belt out from under an arm
  // that is reaching into it.
  auto node = std::make_shared<rclcpp::Node>("conveyor_index_late_stop_test");

  constexpr const char * kBelt = "conveyor_late_stop";
  constexpr const char * kCommand = "/conveyor_index_test/late/stopped/command";
  ConveyorDrivesByAsset drives;
  drives[kBelt] = ConveyorDrive{kCommand, kInstalledSpeed};

  auto index = std::make_shared<ConveyorIndex>(node, drives);
  index->run_all();
  EXPECT_TRUE(index->stop(kBelt));

  Setpoint late(node, kCommand);
  const auto deadline = std::chrono::steady_clock::now() + 2s;
  while (std::chrono::steady_clock::now() < deadline && late.count() == 0) {
    rclcpp::spin_some(node);
    std::this_thread::sleep_for(5ms);
  }

  ASSERT_TRUE(late.latest().has_value());
  EXPECT_DOUBLE_EQ(late.latest().value(), 0.0)
    << "a subscriber that arrived after the belt was stopped was told the installed "
       "speed, which would run the belt while a station is picking from it";
}

}  // namespace

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
