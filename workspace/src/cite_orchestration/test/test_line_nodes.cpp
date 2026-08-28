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
// when it arrives. Motion is `tests/scenarios/continuous_line.py`'s to show — it
// drives the three-arm line against real arms in Gazebo — and nothing green here
// is evidence for it.

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
#include "cite_orchestration/line_fault.hpp"
#include "cite_orchestration/line_maintenance.hpp"
#include "cite_orchestration/line_nodes.hpp"
#include "cite_orchestration/line_plan.hpp"
#include "cite_orchestration/line_tree.hpp"
#include "cite_orchestration/skill_nodes.hpp"
#include "cite_orchestration/station_reset.hpp"
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
using cite_orchestration::LineFault;
using cite_orchestration::LineMaintenance;
using cite_orchestration::LinePlan;
using cite_orchestration::ResourceArbiter;
using cite_orchestration::SkillActions;
using cite_orchestration::SkillActionsByAsset;
using cite_orchestration::StationReset;
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
//: The operator control, served somewhere private for the reason every other
//: fixture name here is: `colcon` runs packages concurrently on one ROS domain.
constexpr char kResetService[] = "/line_nodes_test/line/reset_station";
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
    // Where the fault branch records what the line stopped on (ADR-0038). The
    // coordinator reads it for its exit status; here it is what a test reads to
    // see that `OnFault` latched the classification rather than re-deriving it.
    line_.fault = std::make_shared<LineFault>();
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
      // Wired exactly as `line_orchestrator` wires it: what would wake this
      // station up and what carries work to it, both straight out of the plan.
      // `AwaitReArm` derives its refusal from the pair, so a fixture that left
      // them empty would make that leaf silently find nothing to refuse on.
      runtime.trigger_topic = entry.trigger_topic;
      runtime.inbound_belt = entry.inbound_via_asset_id;
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
    factory.registerNodeType<cite_orchestration::OnFault>("OnFault", line_);
    factory.registerNodeType<cite_orchestration::StopAll>("StopAll", line_);
    factory.registerNodeType<cite_orchestration::AwaitReset>("AwaitReset", line_);
    factory.registerNodeType<cite_orchestration::AwaitReArm>("AwaitReArm", line_);

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
    // The real operator control (ADR-0037), driven through its real handler. Its
    // happy path has never been reachable: until the fault branch existed the
    // process was gone by the time anybody could call it.
    tick_mutex_ = std::make_shared<std::mutex>();
    reset_ = std::make_unique<StationReset>(line_, plan_, kResetService, tick_mutex_);
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

  /// One tick of the line, and what the root tree answered.
  ///
  /// `run_until` hides the status because most tests are about what the line did;
  /// this exposes it, because the fault branch's central property is that the
  /// root goes on returning RUNNING after a station has escalated.
  BT::NodeStatus tick_once()
  {
    const auto status = tree_->tickOnce();
    maintenance_->run();
    observe();
    return status;
  }

  /// Ask the real reset service's real handler to clear a station.
  cite_interfaces::srv::ResetStation::Response reset(const std::string & station)
  {
    cite_interfaces::srv::ResetStation::Request request;
    request.station_id = station;
    cite_interfaces::srv::ResetStation::Response response;
    reset_->handle(request, response);
    return response;
  }

  /// Has the belt been run and then stopped, in that order?
  ///
  /// The mirror of `belt_stopped_then_ran`, and the order is again the whole
  /// assertion: what is under test is that a running belt was put down by the
  /// fault branch, which a belt that was never started could not show.
  bool belt_ran_then_stopped() const
  {
    bool ran = false;
    for (const double setpoint : belt_setpoints()) {
      if (setpoint == kBeltSpeed) {
        ran = true;
      } else if (ran && setpoint == 0.0) {
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
  std::shared_ptr<std::mutex> tick_mutex_;
  std::unique_ptr<StationReset> reset_;
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

TEST_F(RunningLine, AStationThatEscalatesCommandsNothingAndKeepsWhatItIsStandingIn)
{
  // ADR-0037 decision 1, and the half of it that only a running tree can show:
  // "a station whose classification is ESCALATE or STOP_LINE performs no motion
  // at all. It stops where it is."
  //
  // `MOTION_INTERRUPTED` is the code that makes this routine rather than rare —
  // it says the arm stopped part-way and is holding a position nothing has
  // established. `test_recovery_ordering.py` reads the leaf ORDER out of the
  // shipped XML; this drives the shipped XML and asserts the two consequences of
  // that order, both of which a state-only test would miss.
  ASSERT_EQ(plan_.stations.front().id, "station_one");
  const auto & station = plan_.stations.front();
  arm_one_->fail_pick_with(ResultCode::MOTION_INTERRUPTED);

  const auto blocked = [this]() {
      const uint8_t state = (*line_.stations)["station_one"].state;
      return state == cite_interfaces::msg::StationState::STATE_BLOCKED;
    };
  ASSERT_TRUE(run_until(blocked))
    << "the station never blocked, so MOTION_INTERRUPTED did not reach the policy";

  // NOTHING MOVED. `MoveToHome` is the only motion leaf on the retry path and
  // the last leaf of the nominal one, so a station that escalated before
  // reaching either has commanded no trajectory at all. Before the reorder this
  // count was one: the arm planned and drove home while the failure was still
  // unclassified.
  EXPECT_EQ(arm_one_->move_to_goals(), 0)
    << "an escalating station sent a MoveTo goal, so a failure nobody classified was "
    "answered by moving the arm";

  // AND IT KEEPS ITS CLAIMS. `ReleaseStationClaims` is the second leaf of a
  // `<Sequence>` whose first leaf returns FAILURE on ESCALATE, so it does not
  // run — and that is the decided behaviour, not an accident of the ordering.
  // The claims are the line's record of what this station occupies, and the arm
  // is still standing in the frames it reached into. Releasing them would tell
  // the arbiter a frame is free while an arm holds a position nothing has
  // established, which is the same class of statement about the world that
  // ADR-0037 exists to stop being made.
  //
  // Read after the tree has settled and before `TearDown` halts it:
  // `ClaimReach::onHalted` releases, and only a RUNNING node is ever halted.
  EXPECT_TRUE(line_.arbiter->holds(station.pick_frame, station.id))
    << "an escalating station gave up the frame its arm is standing in";
  EXPECT_TRUE(line_.arbiter->holds(station.place_frame, station.id))
    << "an escalating station gave up the frame its arm is standing in";
}

TEST_F(RunningLine, AStationThatIsAllowedToRetryGivesItsFramesBackFirst)
{
  // The other answer, and the reason `ReleaseStationClaims` is on the retry path
  // rather than deleted. `EXECUTION_FAILED` says the arm is at one of the
  // trajectory's endpoints — a place the next attempt can be planned from — so
  // the policy answers RETRY_SAME, the branch continues past the policy, and the
  // station lets go of everything it took before starting again.
  //
  // `retry_budget` is 1 in this fixture, so the first failure retries and the
  // second escalates. What is asserted is the FIRST answer: the frames come back
  // to the arbiter, which is what stops a retrying station starving the line.
  arm_one_->fail_pick_with(ResultCode::EXECUTION_FAILED);
  const auto & station = plan_.stations.front();

  ASSERT_TRUE(
    run_until(
      [this] {
        return (*line_.stations)["station_one"].consecutive_failures >= 1;
      }))
    << "the station never failed at all";

  ASSERT_TRUE(
    run_until(
      [this, &station] {
        return !line_.arbiter->holds(station.pick_frame, station.id);
      }))
    << "a station the policy allowed to retry never released the frames it reached into, so "
    "the leaf that releases them is unreachable on both answers rather than on one";
}

// ---------------------------------------------------------------------------
// The fault branch, on the running line — ADR-0038.
// ---------------------------------------------------------------------------

TEST_F(RunningLine, AStationEscalatingCancelsASiblingsOutstandingGoal)
{
  // THE PROPERTY THE WHOLE DESIGN RESTS ON, AND THE ONE NOTHING ASSERTED.
  // `line_tree.hpp` has said in prose since the root tree existed that a station
  // failing halts its SIBLINGS, and that halting a skill leaf cancels the goal it
  // was waiting on — "a line that stops leaves no arm moving under a goal nobody
  // is holding". Every test of the escalation until now looked only at the station
  // that escalated, and every fake server answered immediately, so no sibling ever
  // had an outstanding goal for a halt to reach.
  //
  // It rests on two properties of BehaviorTree.CPP that this repository asserts
  // nowhere else: a `ParallelNode` halts its running children BEFORE returning
  // FAILURE, and a plain `Fallback` does not re-tick a child that has failed. Both
  // were read from the 4.9.1 source for ADR-0038 and both hold; an upstream change
  // to either would break the line's cancellation guarantee silently, which is
  // what this is here to stop.
  //
  // The staging is deliberate rather than incidental. Both arms hold their
  // `detect` goal, so both stations park with a goal outstanding; then only
  // `arm_1` is released, so `station_one` alone walks on to the `PickAt` that
  // fails. Without that, the two stations race and the test would pass or fail on
  // which of them reached its leaf first.
  arm_one_->hold_detect(true);
  arm_two_->hold_detect(true);
  arm_one_->fail_pick_with(ResultCode::UNREACHABLE);

  // THE BEAM IS NOT FIRED UNTIL THE STATION IS LISTENING, and waiting for the
  // MATCH rather than for a duration is this project's own lesson: reliable
  // delivery is a promise to subscribers a publisher has been matched with, and
  // `AwaitTrigger` creates its subscription on its first tick — so an edge
  // published before then reaches nobody, however reliable the profile. Two
  // subscribers, because `ConveyorIndex` watches the same topic for the belt.
  ASSERT_TRUE(
    run_until(
      [this] {
        return arm_one_->detect_goals() >= 1 && beam_->get_subscription_count() >= 2;
      }))
    << "the first station never reached its Detect, or the second never began watching "
    "its beam";

  fire_beam();
  ASSERT_TRUE(run_until([this] {return arm_two_->detect_goals() >= 1;}))
    << "the sibling never reached its Detect, so there was no outstanding goal for a "
    "halt to cancel";
  ASSERT_EQ(arm_two_->detect_cancellations(), 0)
    << "the sibling's goal was cancelled before anything had failed";

  arm_one_->hold_detect(false);
  ASSERT_TRUE(
    run_until(
      [this] {
        return (*line_.stations)["station_one"].state ==
               cite_interfaces::msg::StationState::STATE_BLOCKED;
      }))
    << "the station never escalated, so nothing ever failed the root Parallel";

  EXPECT_GE(arm_two_->detect_cancellations(), 1)
    << "a station escalated and its SIBLING's outstanding goal was never cancelled, so "
    "the line stopped with an arm still moving under a goal nobody is holding";
}

TEST_F(RunningLine, TheLineGoesOnRunningAfterAStationEscalatesAndLatchesWhy)
{
  // ADR-0038's decision in one test. The station's FAILURE fails the root
  // `Parallel`, the `Fallback` advances to the fault branch, and no leaf there
  // returns FAILURE — so the root stays RUNNING, the tick loop does not end, and
  // the coordinator is still there to be asked a question. Before this, the same
  // FAILURE reached the tick loop, the process exited 1, and `_fatal_on_exit` took
  // the arm's pose, the part's position, the planning scene and the reset service
  // down with it.
  arm_one_->fail_pick_with(ResultCode::UNREACHABLE);
  ASSERT_TRUE(
    run_until(
      [this] {
        return (*line_.stations)["station_one"].state ==
               cite_interfaces::msg::StationState::STATE_BLOCKED;
      }))
    << "the station never escalated";

  for (int tick = 0; tick < 20; ++tick) {
    ASSERT_EQ(tick_once(), BT::NodeStatus::RUNNING)
      << "the root tree stopped returning RUNNING after a station escalated, so the "
      "coordinator's tick loop ends and the process exits — which is exactly what the "
      "fault branch exists to remove";
  }

  ASSERT_TRUE(line_.fault->latched)
    << "nothing recorded the fault, so the coordinator would exit 0 for a run in which "
    "a station escalated and CI would lose the signal it has today";
  EXPECT_EQ(line_.fault->station_id, "station_one");
  EXPECT_EQ(line_.fault->result_code, ResultCode::UNREACHABLE)
    << "the latched classification is not the one the policy acted on";
  // Copied, not composed: the station's own recorded reason, which is what an
  // operator reading the exit will be shown.
  EXPECT_EQ(line_.fault->reason, (*line_.stations)["station_one"].blocked_reason);
  EXPECT_FALSE(line_.fault->reason.empty())
    << "the reason was destroyed on its way into the latch, which is what routing it "
    "through SetStationState would do";
}

TEST_F(RunningLine, AStoppedLinePutsEveryBeltDown)
{
  // THE P2 HALF, and the reason `StopAll` is not optional. In simulation the belts
  // stop by accident today — the coordinator exits, the launch tears the cell
  // down, Gazebo dies. On a physical line the belt is a VFD taking a setpoint, and
  // a setpoint PERSISTS: the coordinator exits, nothing publishes zero, and the
  // belts keep running with nobody supervising them. Identical command path,
  // divergent consequence.
  //
  // Read off the command topic, which is the only place the rest of the system can
  // see what L4 decided. The belt is STARTED first, exactly as the coordinator
  // starts it before the first tick, so what this shows is a running belt being
  // put down rather than a belt that was never moving.
  //
  // The beam is deliberately not fired: indexing would stop this belt for its own
  // reason, and a test that could not tell the two apart would pass with `StopAll`
  // deleted.
  line_.conveyors->run_all();
  arm_one_->fail_pick_with(ResultCode::UNREACHABLE);

  ASSERT_TRUE(run_until([this] {return belt_ran_then_stopped();}))
    << "the belt was commanded " << belt_setpoints().size()
    << " time(s) and never went running-then-stopped, so a line that has stopped "
    "supervising its belts is still commanding them to run";

  EXPECT_DOUBLE_EQ(belt_setpoints().back(), 0.0);
  EXPECT_EQ(arm_two_->move_to_goals(), 0)
    << "the fault branch commanded an arm. Every station's goal was already cancelled "
    "by the Parallel, so anything sent here is new motion after a failure the policy "
    "refused to retry";
}

TEST_F(RunningLine, TheResetIsAcceptedAndTheLineStillDoesNotRestart)
{
  // THE HAPPY PATH THE ADR-0037 RESET HAS NEVER HAD. It shipped one commit before
  // the fault branch, and there was no window in which to call it: the service
  // existed and the process that served it was already gone.
  //
  // And then the second half, which is the whole of ADR-0038 decision 3. The reset
  // is ACKNOWLEDGEMENT — a person looked. It says nothing about whether the line
  // can run, and it must not put the stations back: every recovery this line has
  // returns a station to a state nothing can trigger it out of, and
  // `LineMaintenance` publishes a line of stations that will wait for ever as
  // STATE_RUNNING. A reset that re-entered the nominal branch would convert a
  // process that exits 1 into a process that reports a healthy running line.
  line_.conveyors->run_all();
  arm_one_->fail_pick_with(ResultCode::UNREACHABLE);
  ASSERT_TRUE(
    run_until(
      [this] {
        return (*line_.stations)["station_one"].state ==
               cite_interfaces::msg::StationState::STATE_BLOCKED;
      }))
    << "the station never escalated";
  ASSERT_TRUE(run_until([this] {return belt_ran_then_stopped();}))
    << "the fault branch never reached StopAll";

  const auto answer = reset("station_one");
  EXPECT_TRUE(answer.accepted)
    << "the reset was refused on the one path it exists for: " << answer.result.detail;
  EXPECT_EQ(answer.station_state, cite_interfaces::msg::StationState::STATE_WAITING);
  EXPECT_FALSE(answer.cleared_reason.empty())
    << "the reset cleared a reason that was not there, so the evidence the operator "
    "was shown had already been destroyed";

  // `AwaitReset` stops being the blocker. Its predicate is exactly the reset's
  // precondition, which is what having one author for STATE_BLOCKED buys.
  EXPECT_TRUE(cite_orchestration::stations_holding_the_line(*line_.stations).empty());

  const int arm_one_goals = arm_one_->detect_goals();
  const int arm_two_goals = arm_two_->detect_goals();
  for (int tick = 0; tick < 200; ++tick) {
    ASSERT_EQ(tick_once(), BT::NodeStatus::RUNNING)
      << "the fault branch ended. A SUCCESS out of it exits the coordinator quietly "
      "with status 0; a FAILURE reinstates the process exit";
  }
  EXPECT_EQ(arm_one_->detect_goals(), arm_one_goals)
    << "the line re-entered its nominal branch after a reset, so it is now waiting for "
    "a trigger nothing can produce while reporting STATE_RUNNING";
  EXPECT_EQ(arm_two_->detect_goals(), arm_two_goals);

  // AND IT SAYS WHY, naming the station and the belt. A leaf that refused silently
  // would be the cost ADR-0038 says would make this unacceptable.
  const auto refusals =
    cite_orchestration::rearm_refusals(*line_.stations, line_.conveyors);
  ASSERT_EQ(refusals.size(), 1u)
    << "the re-arm rule found " << refusals.size()
    << " refusal(s); this fixture has exactly one belt-fed sensor-triggered station";
  EXPECT_NE(refusals.front().find("station_two"), std::string::npos) << refusals.front();
  EXPECT_NE(refusals.front().find("conveyor_fixture"), std::string::npos)
    << refusals.front();
}

/// The fault leaves on their own, over a station map and a ledger a test owns.
///
/// `RunningLine` above proves the branch is reached and that the line stays alive.
/// This proves the properties that only exist in states the running fixture cannot
/// be steered into on demand — a handoff still open at the instant the line stops
/// is the one that matters, and arranging it through the tree would mean holding
/// one station in a skill while another failed two leaves later. `RecoveryLeaf`
/// below is here for the same reason and says so.
class FaultBranch : public ::testing::Test
{
protected:
  void SetUp() override
  {
    node_ = std::make_shared<rclcpp::Node>("fault_branch_test");
    line_.node = node_;
    line_.registry = std::make_shared<WorkpieceRegistry>();
    line_.ledger = std::make_shared<HandoffLedger>();
    line_.arbiter = std::make_shared<ResourceArbiter>();
    line_.stations = std::make_shared<std::map<std::string, StationRuntime>>();
    line_.fault = std::make_shared<LineFault>();

    ConveyorDrivesByAsset drives;
    drives["conveyor_fixture"] = ConveyorDrive{"/fault_branch_test/conveyor/command", 0.2};
    line_.conveyors = std::make_shared<ConveyorIndex>(node_, drives);

    StationRuntime upstream;
    upstream.state = cite_interfaces::msg::StationState::STATE_WAITING;
    (*line_.stations)["station_one"] = upstream;

    StationRuntime downstream;
    downstream.state = cite_interfaces::msg::StationState::STATE_WAITING;
    downstream.trigger_topic = "/fault_branch_test/beam/detection";
    downstream.inbound_belt = "conveyor_fixture";
    (*line_.stations)["station_two"] = downstream;

    config_.blackboard = BT::Blackboard::create();
  }

  StationRuntime & station(const std::string & id) {return (*line_.stations)[id];}

  BT::NodeStatus on_fault()
  {
    cite_orchestration::OnFault leaf("OnFault", config_, line_);
    return leaf.executeTick();
  }

  BT::NodeStatus stop_all()
  {
    cite_orchestration::StopAll leaf("StopAll", config_, line_);
    return leaf.executeTick();
  }

  rclcpp::Node::SharedPtr node_;
  LineContext line_;
  BT::NodeConfig config_;
};

TEST_F(FaultBranch, OnFaultRecordsTheClassificationAndDestroysNothing)
{
  station("station_one").state = cite_interfaces::msg::StationState::STATE_BLOCKED;
  station("station_one").blocked_reason = "result code 9: escalate to an operator";
  station("station_one").blocked_code = ResultCode::UNREACHABLE;
  line_.arbiter->declare_resource("frame_pick_1", 1);
  ASSERT_EQ(
    line_.arbiter->request("frame_pick_1", "station_one"), cite_orchestration::Grant::GRANTED);

  ASSERT_EQ(on_fault(), BT::NodeStatus::SUCCESS)
    << "OnFault returned something other than SUCCESS, which fails the fault Sequence "
    "and reinstates the process exit";

  EXPECT_TRUE(line_.fault->latched);
  EXPECT_EQ(line_.fault->station_id, "station_one");
  EXPECT_EQ(line_.fault->result_code, ResultCode::UNREACHABLE);
  EXPECT_EQ(line_.fault->reason, "result code 9: escalate to an operator");

  // IT COMMANDS NOTHING AND GIVES NOTHING UP. The station is still standing in the
  // frame it reached into (ADR-0037 correction 3, as amended by ADR-0038), and its
  // state and reason are its own tree's to write.
  EXPECT_EQ(station("station_one").state, cite_interfaces::msg::StationState::STATE_BLOCKED);
  EXPECT_EQ(station("station_one").blocked_reason, "result code 9: escalate to an operator")
    << "the reason was cleared as a side effect, which is what routing the latch "
    "through SetStationState would do";
  EXPECT_TRUE(line_.arbiter->holds("frame_pick_1", "station_one"));
}

TEST_F(FaultBranch, OnFaultSettlesTheLedgerWithoutMovingAnything)
{
  // WHY THE LEDGER HAS TO BE SETTLED, and it is not tidiness. A handoff clock left
  // running through the fault expires during it; `LineMaintenance` retires it and
  // the upstream station's own tree then reports itself blocked AGAIN, after the
  // operator has already reset it — holding `AwaitReset` open for a reason nobody
  // could see, because the reset they performed was the last thing they did.
  ASSERT_EQ(
    line_.registry->admit("wp_1", "station_one", "station_one"),
    cite_orchestration::RegistryOutcome::OK);
  const std::string token = line_.ledger->offer(
    *line_.registry, "wp_1", "station_one", "station_two",
    node_->get_clock()->now(), rclcpp::Duration::from_seconds(120.0));
  ASSERT_FALSE(token.empty());
  ASSERT_EQ(line_.ledger->live(), 1u);

  station("station_one").state = cite_interfaces::msg::StationState::STATE_BLOCKED;
  ASSERT_EQ(on_fault(), BT::NodeStatus::SUCCESS);

  EXPECT_EQ(line_.ledger->live(), 0u)
    << "a handoff clock is still running through the fault, so it will expire during it "
    "and re-block a station the operator has already reset";

  // OWNERSHIP IS UNTOUCHED, structurally: abandoning does not reach the registry,
  // so the work-piece stays with whoever already had it (ADR-0024 rule 3).
  const auto owner = line_.registry->owner_of("wp_1");
  ASSERT_TRUE(owner.has_value());
  EXPECT_EQ(*owner, "station_one")
    << "settling the ledger moved a work-piece, so the line's record no longer says "
    "where the part is";
}

TEST_F(FaultBranch, OnFaultSaysSoWhenTheLineFailedAndNoStationWillSayWhy)
{
  // A `Parallel` that failed with nothing blocked means a station subtree returned
  // FAILURE without its recovery policy classifying anything. There is no reason to
  // latch and this leaf must not invent one — and it must still return SUCCESS,
  // because a FAILURE here would end the branch that exists to survive this.
  EXPECT_EQ(on_fault(), BT::NodeStatus::SUCCESS);
  EXPECT_FALSE(line_.fault->latched);
}

TEST_F(FaultBranch, StopAllCommandsEveryDeclaredBeltToAStandstill)
{
  ASSERT_TRUE(line_.conveyors->run("conveyor_fixture"));
  ASSERT_TRUE(line_.conveyors->commanded("conveyor_fixture").has_value());
  ASSERT_GT(*line_.conveyors->commanded("conveyor_fixture"), 0.0);

  EXPECT_EQ(stop_all(), BT::NodeStatus::SUCCESS);
  EXPECT_DOUBLE_EQ(*line_.conveyors->commanded("conveyor_fixture"), 0.0);
}

TEST_F(FaultBranch, AwaitResetHoldsWhileAnyStationIsBlockedOrFaultedAndNeverFails)
{
  // NEVER FAILURE, on any input. Asserted rather than left to the leaf's comment,
  // because the cost of a FAILURE here is not a wrong answer — it is the process
  // exit that destroys the evidence the operator was coming to read.
  cite_orchestration::AwaitReset leaf("AwaitReset", config_, line_);
  EXPECT_EQ(leaf.executeTick(), BT::NodeStatus::SUCCESS)
    << "nothing is blocked, so the acknowledgement gate has nothing to wait for";

  station("station_one").state = cite_interfaces::msg::StationState::STATE_BLOCKED;
  cite_orchestration::AwaitReset blocked("AwaitReset", config_, line_);
  EXPECT_EQ(blocked.executeTick(), BT::NodeStatus::RUNNING);

  station("station_one").state = cite_interfaces::msg::StationState::STATE_FAULTED;
  EXPECT_EQ(blocked.executeTick(), BT::NodeStatus::RUNNING)
    << "a faulted station does not hold the line, so the branch would advance past a "
    "cell that cannot be commanded at all";

  station("station_one").state = cite_interfaces::msg::StationState::STATE_WAITING;
  EXPECT_EQ(blocked.executeTick(), BT::NodeStatus::SUCCESS);
}

TEST_F(FaultBranch, AwaitReArmRefusesForADerivedReasonAndNeverPasses)
{
  // The rule is derived from the plan and the belts, so it names a station and a
  // belt that appear nowhere in `line_fault.hpp`. A station fed by a table is
  // SKIPPED — that is the rule working, not an exception to it — which is why
  // `station_one` never appears below.
  ASSERT_TRUE(line_.conveyors->run("conveyor_fixture"));
  EXPECT_TRUE(cite_orchestration::rearm_refusals(*line_.stations, line_.conveyors).empty())
    << "the belt is running and the rule still refuses, so it is not reading the "
    "setpoint at all";

  ASSERT_EQ(stop_all(), BT::NodeStatus::SUCCESS);
  const auto refusals = cite_orchestration::rearm_refusals(*line_.stations, line_.conveyors);
  ASSERT_EQ(refusals.size(), 1u);
  EXPECT_NE(refusals.front().find("station_two"), std::string::npos) << refusals.front();
  EXPECT_NE(refusals.front().find("conveyor_fixture"), std::string::npos) << refusals.front();
  EXPECT_EQ(refusals.front().find("station_one"), std::string::npos)
    << "a station fed by a table was refused for the state of a belt that does not feed "
    "it: " << refusals.front();

  // AND IT NEVER PASSES, in either state. The SUCCESS edge is deliberately not
  // built (ADR-0038 decision 5): without a `<Repeat>` over the root `Fallback`, a
  // SUCCESS here makes the Fallback return SUCCESS and the coordinator exit
  // quietly with status 0. The two land together or not at all.
  cite_orchestration::AwaitReArm leaf("AwaitReArm", config_, line_);
  EXPECT_EQ(leaf.executeTick(), BT::NodeStatus::RUNNING);
  ASSERT_TRUE(line_.conveyors->run("conveyor_fixture"));
  EXPECT_EQ(leaf.executeTick(), BT::NodeStatus::RUNNING)
    << "the re-arm gate passed. Nothing re-arms a station yet, and a fault branch that "
    "returns SUCCESS without a Repeat above it exits the coordinator with status 0";
}

/// The recovery leaf on its own, on a blackboard nothing else is writing.
///
/// `RunningLine` above proves the branch is wired and reached. This proves the
/// one property of it that no leaf ORDER can establish, because it is about what
/// survives BETWEEN recoveries rather than within one: `RecoverFromFailure`
/// consumes `kLastResultCode` as it reads it, so the code it acts on is the
/// failure that led to THIS recovery and never a previous one.
///
/// It needs its own fixture because the case only exists across two recoveries
/// where the second recorded nothing — a station whose second failure is a
/// `LineNode` refusal rather than a skill result, which is most of the leaves in
/// the nominal branch. Driving that through the whole line would mean arranging
/// two different failures two cycles apart; the leaf answers the question
/// directly.
class RecoveryLeaf : public ::testing::Test
{
protected:
  void SetUp() override
  {
    node_ = std::make_shared<rclcpp::Node>("recovery_leaf_test");
    line_.node = node_;
    line_.registry = std::make_shared<WorkpieceRegistry>();
    line_.ledger = std::make_shared<HandoffLedger>();
    line_.arbiter = std::make_shared<ResourceArbiter>();
    line_.stations = std::make_shared<std::map<std::string, StationRuntime>>();
    // Deliberately generous, so that the budget never decides an answer here.
    // What is under test is WHICH CODE the policy is handed, not what a spent
    // budget does with one — `RetriesAreBoundedAndThenEscalate` covers that.
    line_.retry_budget = 10;
    (*line_.stations)["station_one"] = StationRuntime{};

    config_.blackboard = BT::Blackboard::create();
    config_.input_ports["station"] = "station_one";
  }

  /// Tick the real leaf. A fresh node each time, sharing one blackboard — which
  /// is what the enclosing `<Repeat>` does to the recovery branch across cycles.
  BT::NodeStatus recover()
  {
    cite_orchestration::RecoverFromFailure leaf("RecoverFromFailure", config_, line_);
    return leaf.executeTick();
  }

  void record(uint8_t code)
  {
    config_.blackboard->set(cite_orchestration::kLastResultCode, static_cast<int>(code));
  }

  StationRuntime & station() {return (*line_.stations)["station_one"];}

  rclcpp::Node::SharedPtr node_;
  LineContext line_;
  BT::NodeConfig config_;
};

TEST_F(RecoveryLeaf, AConsumedFailureDoesNotDecideTheNextRecovery)
{
  // THE HALF THAT SURVIVED ITS OWN MUTATION UNTIL THIS TEST EXISTED. Suppressing
  // the success-write in `SkillNode::record` is caught by three tests in
  // `test_skill_goals.cpp`. Consuming the key on read was caught by none, while
  // the comment beside it claimed the pair is correct under any leaf ordering —
  // a claim the suite could not falsify.
  //
  // This is the case that needs it. A recovery branch is also reached by leaves
  // that record NOTHING: `TakeCustody` refusing custody, `OfferHandoff` failing,
  // `ClaimReach` finding an undeclared frame. None of them is a `SkillNode` and
  // none writes the key. So without the consume, the second recovery reads the
  // FIRST cycle's code — a stale failure deciding a live station's fate, and
  // deciding it as ESCALATE.
  record(ResultCode::UNREACHABLE);
  ASSERT_EQ(recover(), BT::NodeStatus::FAILURE);
  ASSERT_EQ(station().state, cite_interfaces::msg::StationState::STATE_BLOCKED);

  // The next recovery, reached by a leaf that recorded nothing. The station is
  // put back to work as a retry or an operator reset would leave it.
  station().state = cite_interfaces::msg::StationState::STATE_WORKING;
  EXPECT_EQ(recover(), BT::NodeStatus::SUCCESS)
    << "the second recovery inherited the first one's code, so a failure nobody "
    "classified was answered with the previous failure's policy row";
  EXPECT_EQ(station().state, cite_interfaces::msg::StationState::STATE_WAITING);
  EXPECT_EQ(
    station().blocked_reason.rfind(
      "result code " + std::to_string(static_cast<int>(ResultCode::PRECONDITION_FAILED)), 0),
    0u)
    << "the recorded reason names a code this recovery was never told about: "
    << station().blocked_reason;
}

TEST_F(RecoveryLeaf, AFreshFailureAfterAConsumedOneIsStillTheOneActedOn)
{
  // The other direction, and the reason consuming cannot simply be "erase the
  // key and stop reading it". A code written after a consume belongs to this
  // cycle and must reach the policy intact — including the two codes that stop
  // the line, which are exactly the ones a swallowed failure would hide.
  record(ResultCode::PRECONDITION_FAILED);
  ASSERT_EQ(recover(), BT::NodeStatus::SUCCESS);

  station().state = cite_interfaces::msg::StationState::STATE_WORKING;
  record(ResultCode::SAFETY_BLOCKED);
  EXPECT_EQ(recover(), BT::NodeStatus::FAILURE);
  EXPECT_EQ(station().state, cite_interfaces::msg::StationState::STATE_FAULTED)
    << "a refusal the policy must never treat as a transient did not reach it";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
