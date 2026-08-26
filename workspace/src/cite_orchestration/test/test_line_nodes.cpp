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

// A line, end to end, in one process.
//
// `test_line_logic.cpp` proves each rule on its own. This proves the tree wires
// them together — which is the half a unit test cannot reach, and the half v1's
// handoff failed in: its protocol was individually plausible and collectively
// published to a topic nothing subscribed to.
//
// WHAT IS REAL HERE AND WHAT IS A FIXTURE. Real: the shipped station subtree read
// from `trees/line_station.xml` (not a copy — a copy would keep passing after the
// shipped tree changed), the generated root tree, every leaf, the registry, the
// ledger, the arbiter, and the same `LineMaintenance` the coordinator runs.
// Fixtures: the four L3 action servers, which are in-process and immediate, and
// the sensor that fires the second station.
//
// FIXTURE NAMES LIVE OUTSIDE `/cite/`. `colcon` runs packages concurrently on one
// ROS domain, and a fixture that advertised a production action name once made
// two servers answer one action — it cost four agents a false "known-red" belief.
//
// `TransferTo` is deliberately NOT registered here. It is ADR-0024's motion half
// for a DIRECT arm-to-arm handoff, the shipped station tree does not use it —
// `line_plan.hpp` refuses direct handoffs until a grasp holds an orientation —
// and registering a node the tree never names would prove nothing while costing
// this translation unit a whole action's worth of template instantiation. What it
// sends is covered in `test_skill_goals.cpp`, against the contract, with one arm.
//
// WHAT THIS DOES NOT PROVE, stated because the report has to say it: no arm
// moves here, no physics runs, and nothing is picked up. The action servers
// succeed because they are told to. What is under test is the SEQUENCE and the
// OWNERSHIP — that a work-piece is admitted once, owned by exactly one station at
// every instant, handed over only after both parties confirmed, and counted once
// when it arrives. The simulation-in-the-loop scenario that drives real arms does
// not exist yet.

#include <chrono>
#include <map>
#include <memory>
#include <set>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float64.hpp>

#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/msg/line_topology.hpp>
#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/msg/station_edge.hpp>
#include <cite_interfaces/msg/station_topology.hpp>
#include <cite_interfaces/qos.hpp>

#include "gtest/gtest.h"
#include "behaviortree_cpp/bt_factory.h"
#include "cite_orchestration/line_maintenance.hpp"
#include "cite_orchestration/line_nodes.hpp"
#include "cite_orchestration/line_plan.hpp"
#include "cite_orchestration/line_tree.hpp"
#include "cite_orchestration/skill_nodes.hpp"
#include "fake_arm.hpp"

namespace
{

using cite_interfaces::msg::DetectionEvent;
using cite_interfaces::msg::LineTopology;
using cite_interfaces::msg::ResultCode;
using cite_interfaces::msg::StationEdge;
using cite_interfaces::msg::StationTopology;
using cite_orchestration::Context;
using cite_orchestration::ConveyorDrive;
using cite_orchestration::ConveyorDrivesByAsset;
using cite_orchestration::ConveyorIndex;
using cite_orchestration::HandoffLedger;
using cite_orchestration::LineContext;
using cite_orchestration::LineMaintenance;
using cite_orchestration::LinePlan;
using cite_orchestration::ResourceArbiter;
using cite_orchestration::SkillActions;
using cite_orchestration::SkillActionsByAsset;
using cite_orchestration::StationRuntime;
using cite_orchestration::TriggerWatch;
using cite_orchestration::WorkpieceRegistry;
using cite_orchestration_test::FakeArm;
using namespace std::chrono_literals;

//: Everything this test advertises sits under `FakeArm`'s fixture prefix, which
//: is outside `/cite/` where no generated name can ever land.
constexpr char kBeam[] = "/line_nodes_test/beam/detection";
constexpr char kStateTopic[] = "/line_nodes_test/line/state";
//: The belt `station_two` picks from, and the speed its drive is installed at.
//: Both are what the model would supply; the test reads the setpoint back off the
//: topic rather than comparing a constant against itself.
constexpr char kBeltCommand[] = "/line_nodes_test/conveyor_fixture/command";
constexpr double kBeltSpeed = 0.15;

StationTopology station(
  const std::string & id, uint8_t type, const std::string & actor = "",
  const std::string & pick = "", const std::string & place = "")
{
  StationTopology entry;
  entry.id = id;
  entry.type = type;
  entry.actor_asset_id = actor;
  entry.pick_frame = pick;
  entry.place_frame = place;
  entry.capacity = 1;
  return entry;
}

StationEdge edge(
  const std::string & from, const std::string & to, const std::string & via, uint32_t buffer)
{
  StationEdge entry;
  entry.from_station_id = from;
  entry.to_station_id = to;
  entry.via_asset_id = via;
  entry.buffer_capacity = buffer;
  return entry;
}

/// Source -> station_one (arm_1) -> conveyor -> station_two (arm_2) -> sink.
///
/// The smallest topology that contains a handoff between two robots, which is
/// what ADR-0024 is about. Conveyor-mediated, because a direct arm-to-arm handoff
/// is refused until a grasp holds an orientation.
LineTopology two_station_line()
{
  LineTopology topology;
  topology.zone = "fixture_zone";
  topology.flow_id = "fixture_flow";
  topology.stations.push_back(station("sink", StationTopology::TYPE_SINK));
  topology.stations.back().capacity = 4;
  topology.stations.push_back(station("source", StationTopology::TYPE_SOURCE));
  topology.stations.push_back(
    station("station_one", StationTopology::TYPE_TRANSFER, "arm_1", "frame_pick_1",
    "frame_place_1"));
  topology.stations.push_back(
    station("station_two", StationTopology::TYPE_TRANSFER, "arm_2", "frame_pick_2",
    "frame_place_2"));
  topology.stations.back().trigger_topic = kBeam;
  topology.stations.back().trigger_state = StationTopology::TRIGGER_ON_BLOCKED;

  topology.edges.push_back(edge("source", "station_one", "", 4));
  topology.edges.push_back(edge("station_one", "station_two", "conveyor_fixture", 2));
  topology.edges.push_back(edge("station_two", "sink", "conveyor_out", 4));
  return topology;
}

SkillActionsByAsset actions_for(const std::vector<std::string> & assets)
{
  SkillActionsByAsset actions;
  for (const auto & asset : assets) {
    SkillActions skills;
    skills.move_to = FakeArm::prefix(asset) + "/move_to";
    skills.pick = FakeArm::prefix(asset) + "/pick";
    skills.place = FakeArm::prefix(asset) + "/place";
    skills.detect = FakeArm::prefix(asset) + "/detect";
    actions[asset] = skills;
  }
  return actions;
}

}  // namespace

/// One line, built and ticked the way the coordinator builds and ticks it.
class RunningLine : public ::testing::Test
{
protected:
  void SetUp() override
  {
    node_ = std::make_shared<rclcpp::Node>("line_nodes_test");
    arm_one_ = std::make_unique<FakeArm>(node_, "arm_1");
    arm_two_ = std::make_unique<FakeArm>(node_, "arm_2");
    beam_ = node_->create_publisher<DetectionEvent>(kBeam, cite::qos::event());
    // The belt setpoint, read from the outside. This is the only place the rest
    // of the system can see what L4 decided a belt should do.
    belt_ = node_->create_subscription<std_msgs::msg::Float64>(
      kBeltCommand, cite::qos::command(),
      [this](std_msgs::msg::Float64::SharedPtr message) {
        const std::lock_guard<std::mutex> lock(belt_mutex_);
        belt_setpoints_.push_back(message->data);
      });

    executor_.add_node(node_);
    spinner_ = std::thread([this]() {executor_.spin();});

    plan_ = cite_orchestration::plan_line(two_station_line());
    ASSERT_TRUE(plan_.usable()) << (plan_.refusals.empty() ? "" : plan_.refusals.front());

    line_.node = node_;
    line_.registry = std::make_shared<WorkpieceRegistry>();
    line_.ledger = std::make_shared<HandoffLedger>();
    line_.arbiter = std::make_shared<ResourceArbiter>();
    line_.triggers = std::make_shared<TriggerWatch>(node_);
    line_.stations = std::make_shared<std::map<std::string, StationRuntime>>();
    line_.handoff_timeout = rclcpp::Duration::from_seconds(30.0);
    line_.retry_budget = 1;

    // The belt indexing, wired exactly as `line_orchestrator` wires it: the
    // drives arrive as data, and which station stops which belt is derived from
    // the plan rather than named here.
    ConveyorDrivesByAsset drives;
    drives["conveyor_fixture"] = ConveyorDrive{kBeltCommand, kBeltSpeed};
    line_.conveyors = std::make_shared<ConveyorIndex>(node_, drives);

    for (const auto & resource : plan_.resources) {
      line_.arbiter->declare_resource(resource.name, resource.capacity);
    }
    for (const auto & entry : plan_.stations) {
      StationRuntime runtime;
      runtime.capacity = entry.capacity;
      (*line_.stations)[entry.id] = runtime;
      line_.conveyors->index_on(
        entry.trigger_topic, entry.trigger_detection_state, entry.inbound_via_asset_id);
    }

    Context context;
    context.node = node_;
    context.skill_deadline = 20s;
    context.cancel_deadline = 10s;

    BT::BehaviorTreeFactory factory;
    factory.registerNodeType<cite_orchestration::MoveToHome>("MoveToHome", context);
    factory.registerNodeType<cite_orchestration::PickAt>("PickAt", context);
    factory.registerNodeType<cite_orchestration::PlaceAt>("PlaceAt", context);
    factory.registerNodeType<cite_orchestration::DetectAt>("DetectAt", context);
    factory.registerNodeType<cite_orchestration::ReportBlocked>("ReportBlocked", node_);
    factory.registerNodeType<cite_orchestration::AwaitTrigger>("AwaitTrigger", line_);
    factory.registerNodeType<cite_orchestration::AcceptOffers>("AcceptOffers", line_);
    factory.registerNodeType<cite_orchestration::TakeCustody>("TakeCustody", line_);
    factory.registerNodeType<cite_orchestration::ClaimReach>("ClaimReach", line_);
    factory.registerNodeType<cite_orchestration::ClaimBufferSlot>("ClaimBufferSlot", line_);
    factory.registerNodeType<cite_orchestration::ReleaseClaim>("ReleaseClaim", line_);
    factory.registerNodeType<cite_orchestration::ReleaseStationClaims>(
      "ReleaseStationClaims", line_);
    factory.registerNodeType<cite_orchestration::OfferHandoff>("OfferHandoff", line_);
    factory.registerNodeType<cite_orchestration::AwaitHandoffConfirmed>(
      "AwaitHandoffConfirmed", line_);
    factory.registerNodeType<cite_orchestration::CompleteHandoff>("CompleteHandoff", line_);
    factory.registerNodeType<cite_orchestration::ResumeBelt>("ResumeBelt", line_);
    factory.registerNodeType<cite_orchestration::SetStationState>("SetStationState", line_);
    factory.registerNodeType<cite_orchestration::RecoverFromFailure>(
      "RecoverFromFailure", line_);

    const auto generated = cite_orchestration::line_tree_xml(plan_, actions_for({"arm_1",
          "arm_2"}));
    ASSERT_TRUE(generated.refusals.empty()) << generated.refusals.front();

    // The tree that ships, read from the source tree. Registering it here is
    // also the strongest check that every node type the XML names is one this
    // package registers — BT.CPP refuses to build a tree naming an unknown node,
    // so a leaf added to the XML and not to the factory fails right here.
    factory.registerBehaviorTreeFromFile(CITE_STATION_TREE);
    factory.registerBehaviorTreeFromText(generated.xml);
    tree_ = std::make_unique<BT::Tree>(factory.createTree("Line"));
    maintenance_ = std::make_unique<LineMaintenance>(line_, plan_, kStateTopic);
  }

  void TearDown() override
  {
    if (tree_) {
      tree_->haltTree();
    }
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  /// Tick the line until `done` holds, or until the tick budget runs out.
  ///
  /// A budget on ticks, not a wait on a duration: it exists so a test that will
  /// never finish reports rather than hangs, and nothing in the line is sequenced
  /// by it.
  bool run_until(const std::function<bool()> & done, int budget = 4000)
  {
    for (int tick = 0; tick < budget; ++tick) {
      if (done()) {
        return true;
      }
      const auto status = tree_->tickOnce();
      maintenance_->run();
      if (conveyor_running_) {
        carry_on_conveyor();
      }
      observe();
      if (status != BT::NodeStatus::RUNNING) {
        return done();
      }
      std::this_thread::sleep_for(2ms);
    }
    return done();
  }

  /// Record who owns the first work-piece, every tick.
  ///
  /// This is the ownership invariant's evidence. Sampling it on every tick is the
  /// closest a test can get to "at any instant", and what it catches is a handoff
  /// that briefly leaves a piece owned by nobody or by two stations — which is
  /// what a two-statement transfer would do.
  void observe()
  {
    const auto owner = line_.registry->owner_of("wp_000001");
    const std::string now = owner ? *owner : std::string("<none>");
    if (owners_.empty() || owners_.back() != now) {
      owners_.push_back(now);
    }
    if (line_.registry->in_line() > 1) {
      ++ticks_with_more_than_one_piece_;
    }
  }

  /// Stand in for the belt and the beam at the end of it.
  ///
  /// The line is sensor-driven: a station with a trigger topic does nothing until
  /// an edge arrives on it. In the cell that edge comes from a break beam the
  /// work-piece interrupts on its way down the conveyor; here nothing physical
  /// moves, so the test plays the conveyor's part — once per work-piece, when the
  /// line's own record says that piece is in transit toward that station.
  ///
  /// Deliberately OPT-IN. `TheSecondStationWaitsForItsSensorRatherThanForATimer`
  /// leaves it off, because its whole assertion is that nothing happens until an
  /// edge arrives.
  void carry_on_conveyor()
  {
    for (const auto & entry : plan_.stations) {
      if (entry.trigger_topic.empty()) {
        continue;
      }
      for (const auto & id : line_.registry->owned_by(entry.id)) {
        const auto record = line_.registry->find(id);
        if (!record || record->phase != cite_orchestration::WorkpiecePhase::IN_TRANSIT) {
          continue;
        }
        if (announced_.count(id) != 0) {
          continue;
        }
        announced_.insert(id);
        fire_beam();
      }
    }
  }

  void fire_beam()
  {
    DetectionEvent event;
    event.header.stamp = node_->get_clock()->now();
    event.asset_id = "beam_fixture";
    event.previous_state = DetectionEvent::STATE_CLEAR;
    event.state = DetectionEvent::STATE_BLOCKED;
    beam_->publish(event);
  }

  /// Every setpoint the line has commanded the belt to, in order.
  std::vector<double> belt_setpoints() const
  {
    const std::lock_guard<std::mutex> lock(belt_mutex_);
    return belt_setpoints_;
  }

  /// Has the belt been stopped and then run again, in that order?
  ///
  /// The ORDER is the assertion. A belt that stops and never runs again is a
  /// stalled line; one that runs again before it was stopped is a belt nothing
  /// indexed. Expressed as a predicate so `run_until` can wait for it rather than
  /// the test reading the setpoints at whatever instant the loop happened to
  /// leave — the publish and its delivery are on different threads.
  bool belt_stopped_then_ran() const
  {
    bool stopped = false;
    for (const double setpoint : belt_setpoints()) {
      if (setpoint == 0.0) {
        stopped = true;
      } else if (stopped && setpoint == kBeltSpeed) {
        return true;
      }
    }
    return false;
  }

  rclcpp::Node::SharedPtr node_;
  std::unique_ptr<FakeArm> arm_one_;
  std::unique_ptr<FakeArm> arm_two_;
  rclcpp::Publisher<DetectionEvent>::SharedPtr beam_;
  rclcpp::Subscription<std_msgs::msg::Float64>::SharedPtr belt_;
  mutable std::mutex belt_mutex_;
  std::vector<double> belt_setpoints_;
  rclcpp::executors::MultiThreadedExecutor executor_;
  std::thread spinner_;
  LinePlan plan_;
  LineContext line_;
  std::unique_ptr<BT::Tree> tree_;
  std::unique_ptr<LineMaintenance> maintenance_;
  std::vector<std::string> owners_;
  std::set<std::string> announced_;
  bool conveyor_running_{false};
  int ticks_with_more_than_one_piece_{0};
};

TEST_F(RunningLine, AWorkpieceIsAdmittedOnceAtTheStationFedByTheSource)
{
  // Nothing hands the first station anything: work enters the line there, so it
  // admits what it observes. A station whose upstream is not a source and which
  // owns nothing must refuse instead — that is `TakeCustody`'s third case.
  ASSERT_TRUE(
    run_until([this] {return line_.registry->in_line() == 1;}))
    << "no work-piece entered the line";

  const auto record = line_.registry->find("wp_000001");
  ASSERT_TRUE(record.has_value()) << "the admitted piece is not under the identity the "
    "line mints";
  EXPECT_EQ(record->owner_station_id, "station_one");
  EXPECT_EQ(line_.registry->admitted(), 1u);
}

TEST_F(RunningLine, TheUpstreamStationDoesNotLetGoBeforeTheDownstreamHasConfirmed)
{
  // Rule 2, observed on a running line rather than on the ledger alone: at the
  // moment ownership moves, the handoff must have been through CONFIRMED, and the
  // Place that physically let go must have happened after the confirmation.
  ASSERT_TRUE(
    run_until(
      [this] {
        const auto owner = line_.registry->owner_of("wp_000001");
        return owner && *owner == "station_two";
      }))
    << "the work-piece never reached the second station";

  EXPECT_GE(arm_one_->place_goals(), 1) << "ownership moved without the upstream arm "
    "ever being told to let go";
  EXPECT_GE(arm_one_->pick_goals(), 1);
  EXPECT_GE(arm_one_->detect_goals(), 1) << "the station picked without observing the "
    "part first, so it assumed an orientation instead of measuring one";
}

TEST_F(RunningLine, OwnershipPassesDownTheLineWithoutEverBeingSharedOrLost)
{
  conveyor_running_ = true;
  ASSERT_TRUE(run_until([this] {return line_.registry->completed() == 1;}))
    << "no work-piece reached the sink";

  // The sequence of owners, sampled every tick. It must be exactly: admitted at
  // the first station, then the second, then gone. Anything else — a repeat, a
  // gap in the middle, an out-of-order entry — is a work-piece that was owned by
  // the wrong station at some instant.
  ASSERT_GE(owners_.size(), 3u);
  EXPECT_EQ(owners_[0], "<none>") << "the sequence should start before admission";
  EXPECT_EQ(owners_[1], "station_one");
  EXPECT_EQ(owners_[2], "station_two")
    << "the work-piece was owned by something other than the two stations in order";
  EXPECT_EQ(owners_.back(), "<none>") << "the piece was never retired at the sink";

  EXPECT_EQ(line_.registry->completed(), 1u);
  // Counted once, not once per tick the sink held it.
  EXPECT_EQ(line_.registry->occupancy("sink"), 0u);
}

TEST_F(RunningLine, TheSecondStationWaitsForItsSensorRatherThanForATimer)
{
  // The station with a trigger topic must not proceed until an edge arrives on
  // it. If it did, the line would be timed rather than sensor-driven, which is
  // the property Phase 1.D exists to establish.
  ASSERT_TRUE(
    run_until(
      [this] {
        const auto owner = line_.registry->owner_of("wp_000001");
        return owner && *owner == "station_two";
      }))
    << "the handoff never completed";

  const int picks_before = arm_two_->pick_goals();
  EXPECT_EQ(picks_before, 0)
    << "the second station picked before its beam ever fired, so it is not sensor-driven";

  fire_beam();
  ASSERT_TRUE(run_until([this] {return arm_two_->pick_goals() >= 1;}))
    << "the second station did not act on its sensor edge";
}

TEST_F(RunningLine, ABufferSlotIsHeldByTheWorkpieceUntilItIsPickedOff)
{
  const std::string belt = cite_orchestration::buffer_key("station_one", "station_two");
  ASSERT_TRUE(
    run_until(
      [this] {
        const auto owner = line_.registry->owner_of("wp_000001");
        return owner && *owner == "station_two";
      }));

  EXPECT_TRUE(line_.arbiter->holds(belt, "wp_000001"))
    << "the piece is on the belt and occupies no slot, so the upstream station would "
       "keep filling it";

  fire_beam();
  ASSERT_TRUE(run_until([this] {return line_.registry->completed() == 1;}));
  EXPECT_FALSE(line_.arbiter->holds(belt, "wp_000001"))
    << "the slot was never freed, so the belt fills up with pieces that have left it";
}

TEST_F(RunningLine, AStationReleasesTheFramesItReachedIntoWhenItsCycleEnds)
{
  ASSERT_TRUE(
    run_until(
      [this] {
        const auto owner = line_.registry->owner_of("wp_000001");
        return owner && *owner == "station_two";
      }));
  // Ticked on a little so the first station finishes its cycle after the handoff.
  run_until([this] {return !line_.arbiter->holds("frame_pick_1", "station_one");}, 400);

  EXPECT_FALSE(line_.arbiter->holds("frame_pick_1", "station_one"))
    << "the first station still holds its pick frame, so nothing else could ever reach "
       "into it";
  EXPECT_FALSE(line_.arbiter->holds("frame_place_1", "station_one"));
}

TEST_F(RunningLine, TheLineKeepsRunningAndCountsMoreThanOnePiece)
{
  // N work-pieces, not one. A line that completes exactly one piece and stops has
  // proved a cycle rather than a line, and Phase 1.D's exit criterion is N pieces
  // arriving with no intervention.
  conveyor_running_ = true;
  ASSERT_TRUE(run_until([this] {return line_.registry->completed() >= 3;}, 12000))
    << "the line completed " << line_.registry->completed()
    << " work-piece(s) and did not keep going";

  EXPECT_GE(arm_one_->pick_goals(), 3);
  EXPECT_GE(arm_two_->place_goals(), 3);
  EXPECT_GT(ticks_with_more_than_one_piece_, 0)
    << "the line never had two work-pieces in it at once, so nothing was pipelined and "
       "the buffer arbitration was never exercised";
}

TEST_F(RunningLine, TheBeltStopsOnTheSensorEdgeAndRunsAgainOnTheCompletedHandoff)
{
  // ADR-0032, end to end through the tree that ships.
  //
  // This is the composed half: the logic tests prove that an edge stops a belt
  // and that `run()` sends the declared speed, and this proves the two are wired
  // to the right events in the real station subtree. The order is the whole
  // assertion — a belt that stops and never runs again is a stalled line, and one
  // that runs again before the handoff completes is the race indexing exists to
  // remove.
  conveyor_running_ = true;
  ASSERT_TRUE(run_until([this] {return belt_stopped_then_ran();}, 12000))
    << "the belt was commanded " << belt_setpoints().size() << " time(s) and never went "
    << "stopped-then-running. " << line_.registry->completed()
    << " work-piece(s) completed, so what failed is the indexing and not the line";

  const auto setpoints = belt_setpoints();
  ASSERT_FALSE(setpoints.empty())
    << "nothing commanded the belt. Before ADR-0032 the setpoint had no owner in the "
       "running system and a scenario supplied it";

  EXPECT_DOUBLE_EQ(setpoints.front(), 0.0)
    << "the first thing the line did to this belt was not stop it, so a station could "
       "have picked from a belt that was still moving";

  // And the speed it went back to is the one the drive is installed at, not one
  // the code chose. Read off the topic, so a second copy of the number would show
  // up here as a mismatch rather than agreeing with itself.
  for (const double setpoint : setpoints) {
    EXPECT_TRUE(setpoint == 0.0 || setpoint == kBeltSpeed)
      << "the belt was commanded to " << setpoint
      << " m/s, which is neither a standstill nor its installed speed";
  }
}

TEST_F(RunningLine, TheStationFedFromTheSourceIndexesNoBelt)
{
  // `station_one` picks off the source, which nothing carries to. Its
  // `inbound_belt` port is empty and `ResumeBelt` must read that as "nothing to
  // resume" rather than as a failure — otherwise the first station's cycle fails
  // every time and the line never starts.
  ASSERT_EQ(plan_.stations.front().id, "station_one");
  EXPECT_TRUE(plan_.stations.front().inbound_via_asset_id.empty());

  ASSERT_TRUE(run_until([this] {return arm_one_->place_goals() >= 1;}))
    << "the first station never completed a cycle, so an empty belt port was treated "
       "as an error";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
