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

// The rules the line is made of.
//
// Ownership, the two-party handoff and its timeout, buffer and reach
// arbitration, the recovery policy, and the translation from an L0 topology into
// a plan and a tree. All of it is pure logic with no ROS runtime, which is the
// point: ADR-0024 requires a handoff to be testable in isolation, and v1's
// handoff defect survived precisely because nothing could exercise the protocol
// without a cell.
//
// WHAT THESE TESTS TRY NOT TO BE. A test that constructs the answer it expects
// and then asserts the code produced it proves only that two pieces of arithmetic
// agree. So the assertions below are about PROPERTIES that a plausible wrong
// implementation breaks: that a station cannot take a work-piece it does not own,
// that a topology whose array order disagrees with its flow order comes out in
// flow order, that two claimants asking for the same pair of resources in
// opposite orders both finish. Where a literal is unavoidable it is one from the
// L0 model, named as such.

#include <string>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/line_topology.hpp>
#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/msg/station_edge.hpp>
#include <cite_interfaces/msg/station_topology.hpp>

#include "gtest/gtest.h"
#include "cite_orchestration/handoff_ledger.hpp"
#include "cite_orchestration/line_plan.hpp"
#include "cite_orchestration/line_tree.hpp"
#include "cite_orchestration/recovery_policy.hpp"
#include "cite_orchestration/resource_arbiter.hpp"
#include "cite_orchestration/workpiece_registry.hpp"

namespace
{

using cite_interfaces::msg::DetectionEvent;
using cite_interfaces::msg::LineTopology;
using cite_interfaces::msg::ResultCode;
using cite_interfaces::msg::StationEdge;
using cite_interfaces::msg::StationTopology;
using cite_orchestration::Grant;
using cite_orchestration::HandoffLedger;
using cite_orchestration::HandoffPhase;
using cite_orchestration::HandoffReply;
using cite_orchestration::LinePlan;
using cite_orchestration::Recovery;
using cite_orchestration::RegistryOutcome;
using cite_orchestration::ResourceArbiter;
using cite_orchestration::SkillActions;
using cite_orchestration::SkillActionsByAsset;
using cite_orchestration::WorkpiecePhase;
using cite_orchestration::WorkpieceRegistry;

rclcpp::Time at(double seconds)
{
  return rclcpp::Time(static_cast<int64_t>(seconds * 1e9), RCL_ROS_TIME);
}

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

/// The shape of `cell_a_flow.yaml`: a source, three transfer stations each served
/// by its own arm, and a sink, joined by conveyors.
///
/// THE STATIONS ARE LISTED IN THE ORDER THE GENERATED ARTIFACT LISTS THEM, which
/// is alphabetical and therefore starts with the SINK. That is not a detail of
/// this fixture: it is what the topology server publishes, and a coordinator that
/// trusted the array order would run the line backwards while looking correct.
LineTopology cell_a_shaped()
{
  LineTopology topology;
  topology.zone = "cell_a";
  topology.flow_id = "cell_a_serial_transfer";

  topology.stations.push_back(station("station_accumulation", StationTopology::TYPE_SINK));
  topology.stations.back().capacity = 12;
  topology.stations.push_back(station("station_infeed", StationTopology::TYPE_SOURCE));
  topology.stations.back().capacity = 6;
  topology.stations.push_back(
    station("station_transfer_1", StationTopology::TYPE_TRANSFER, "arm_1", "pick_1", "place_1"));
  // The infeed station has a sensor of its own. It did not, and that was the
  // Critical defect: it fell through the wait for work and came to rest polling
  // `Detect` against a region no sensor was in. `beam_pick` in
  // `model/assets/instances/sensors.yaml` is what it observes with now, and this
  // fixture mirrors the model rather than the shape that hung.
  topology.stations.back().trigger_topic = "/fixture/beam_pick/detection";
  topology.stations.back().trigger_state = StationTopology::TRIGGER_ON_BLOCKED;
  topology.stations.push_back(
    station("station_transfer_2", StationTopology::TYPE_TRANSFER, "arm_2", "pick_2", "place_2"));
  topology.stations.back().trigger_topic = "/fixture/beam_c1_out/detection";
  topology.stations.back().trigger_state = StationTopology::TRIGGER_ON_BLOCKED;
  topology.stations.push_back(
    station("station_transfer_3", StationTopology::TYPE_TRANSFER, "arm_3", "pick_3", "place_3"));
  topology.stations.back().trigger_topic = "/fixture/beam_c2_out/detection";
  topology.stations.back().trigger_state = StationTopology::TRIGGER_ON_BLOCKED;

  topology.edges.push_back(edge("station_infeed", "station_transfer_1", "", 6));
  topology.edges.push_back(edge("station_transfer_1", "station_transfer_2", "conveyor_1", 4));
  topology.edges.push_back(edge("station_transfer_2", "station_transfer_3", "conveyor_2", 4));
  topology.edges.push_back(edge("station_transfer_3", "station_accumulation", "conveyor_3", 12));
  return topology;
}

SkillActionsByAsset fixture_actions()
{
  // Fixture names, outside `/cite/`, where no generated name can ever land. A
  // test that used a realistic action name would be squatting on the action a
  // real skill server serves, and `colcon` runs packages concurrently on one ROS
  // domain — which has already cost this project four agents' time.
  SkillActionsByAsset actions;
  for (const char * asset : {"arm_1", "arm_2", "arm_3"}) {
    SkillActions skills;
    const std::string prefix = std::string("/line_logic_test/") + asset;
    skills.move_to = prefix + "/move_to";
    skills.pick = prefix + "/pick";
    skills.place = prefix + "/place";
    skills.detect = prefix + "/detect";
    actions[asset] = skills;
  }
  return actions;
}

}  // namespace

// ---------------------------------------------------------------------------
// Ownership — ADR-0024 rule 1.
// ---------------------------------------------------------------------------

TEST(WorkpieceRegistryTest, AWorkpieceHasExactlyOneOwner)
{
  WorkpieceRegistry registry;
  ASSERT_EQ(registry.admit("part", "station_a", "station_a"), RegistryOutcome::OK);

  EXPECT_EQ(registry.owner_of("part").value(), "station_a");
  EXPECT_EQ(registry.occupancy("station_a"), 1u);
  EXPECT_EQ(registry.occupancy("station_b"), 0u);

  ASSERT_EQ(
    registry.transfer("part", "station_a", "station_b", "belt", WorkpiecePhase::IN_TRANSIT),
    RegistryOutcome::OK);

  // The property, stated as both halves. A transfer that only added an owner
  // would pass the first and fail the second.
  EXPECT_EQ(registry.owner_of("part").value(), "station_b");
  EXPECT_EQ(registry.occupancy("station_a"), 0u)
    << "the upstream station still owns a work-piece it has handed over";
  EXPECT_EQ(registry.occupancy("station_b"), 1u);
}

TEST(WorkpieceRegistryTest, AStationCannotHandOverWhatItDoesNotOwn)
{
  WorkpieceRegistry registry;
  ASSERT_EQ(registry.admit("part", "station_a", "station_a"), RegistryOutcome::OK);

  // The defect this keeps out: a station that has lost track quietly becoming
  // right by asserting ownership it never had.
  EXPECT_EQ(
    registry.transfer("part", "station_c", "station_b", "belt", WorkpiecePhase::IN_TRANSIT),
    RegistryOutcome::NOT_THE_OWNER);
  EXPECT_EQ(registry.owner_of("part").value(), "station_a")
    << "a refused transfer changed the owner anyway";
}

TEST(WorkpieceRegistryTest, RetiringCountsAndOnlyTheOwnerMay)
{
  WorkpieceRegistry registry;
  ASSERT_EQ(registry.admit("part", "sink", "sink"), RegistryOutcome::OK);
  EXPECT_EQ(registry.retire("part", "not_the_sink"), RegistryOutcome::NOT_THE_OWNER);
  EXPECT_EQ(registry.completed(), 0u);
  EXPECT_EQ(registry.retire("part", "sink"), RegistryOutcome::OK);
  EXPECT_EQ(registry.completed(), 1u);
  EXPECT_EQ(registry.in_line(), 0u);
  EXPECT_EQ(registry.retire("part", "sink"), RegistryOutcome::UNKNOWN_WORKPIECE)
    << "a retired work-piece was counted twice";
}

TEST(WorkpieceRegistryTest, MintedIdentitiesAreDistinct)
{
  WorkpieceRegistry registry;
  const std::string first = registry.mint_id();
  const std::string second = registry.mint_id();
  EXPECT_NE(first, second);
  EXPECT_EQ(registry.admit(first, "station", "station"), RegistryOutcome::OK);
  EXPECT_EQ(registry.admit(first, "station", "station"), RegistryOutcome::ALREADY_PRESENT);
}

// ---------------------------------------------------------------------------
// Arbitration.
// ---------------------------------------------------------------------------

TEST(ResourceArbiterTest, CapacityIsRespectedAndTheQueueIsFirstInFirstOut)
{
  ResourceArbiter arbiter;
  arbiter.declare_resource("belt", 2);

  EXPECT_EQ(arbiter.request("belt", "part_a"), Grant::GRANTED);
  EXPECT_EQ(arbiter.request("belt", "part_b"), Grant::GRANTED);
  EXPECT_EQ(arbiter.request("belt", "part_c"), Grant::QUEUED);
  EXPECT_EQ(arbiter.request("belt", "part_d"), Grant::QUEUED);

  // Asking again while holding is not a second claim. A behaviour-tree leaf
  // re-asks on every tick, and an arbiter that counted those would fill its own
  // capacity with one claimant.
  EXPECT_EQ(arbiter.request("belt", "part_a"), Grant::GRANTED);
  EXPECT_EQ(arbiter.occupancy("belt"), 2u);

  arbiter.release("belt", "part_a");
  EXPECT_TRUE(arbiter.holds("belt", "part_c"))
    << "the slot went to someone other than the longest waiter, which is how a "
       "station starves";
  EXPECT_FALSE(arbiter.holds("belt", "part_d"));
}

TEST(ResourceArbiterTest, AnUndeclaredResourceIsRefusedRatherThanInvented)
{
  ResourceArbiter arbiter;
  // Creating it on demand would grant every request and arbitrate nothing, which
  // is worse than failing: the line would look coordinated and not be.
  EXPECT_EQ(arbiter.request("typo", "claimant"), Grant::UNDECLARED);
}

TEST(ResourceArbiterTest, OppositeOrdersDoNotDeadlock)
{
  // The textbook circular wait, and the reason `request_all` sorts. Two stations
  // want the same two frames. Asked in opposite orders and granted one each, they
  // would wait for each other for ever and no retry would break it.
  ResourceArbiter arbiter;
  arbiter.declare_resource("frame_x", 1);
  arbiter.declare_resource("frame_y", 1);

  const Grant first = arbiter.request_all({"frame_x", "frame_y"}, "station_a");
  const Grant second = arbiter.request_all({"frame_y", "frame_x"}, "station_b");

  EXPECT_EQ(first, Grant::GRANTED);
  EXPECT_EQ(second, Grant::QUEUED);
  // The decisive assertion: one of them holds BOTH, so one of them can make
  // progress and then release. A deadlock is exactly the state where each holds
  // one.
  EXPECT_TRUE(arbiter.holds("frame_x", "station_a") && arbiter.holds("frame_y", "station_a"));
  EXPECT_FALSE(arbiter.holds("frame_x", "station_b"));
  EXPECT_FALSE(arbiter.holds("frame_y", "station_b"));

  arbiter.release_all("station_a");
  EXPECT_EQ(arbiter.request_all({"frame_y", "frame_x"}, "station_b"), Grant::GRANTED);
}

// ---------------------------------------------------------------------------
// The handoff protocol — ADR-0024 rules 2 and 3.
// ---------------------------------------------------------------------------

TEST(HandoffLedgerTest, OnlyTheOwnerMayOffer)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "station_a", "station_a"), RegistryOutcome::OK);

  EXPECT_TRUE(
    ledger.offer(
      registry, "part", "station_b", "station_c", at(0.0),
      rclcpp::Duration::from_seconds(10.0)).empty())
    << "a station offered a work-piece it does not own";
  EXPECT_EQ(ledger.live(), 0u);
}

TEST(HandoffLedgerTest, NoMotionUntilBothPartiesHaveConfirmed)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);

  const std::string token =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_FALSE(token.empty());

  // One party. The offer is the upstream's confirmation; the downstream has said
  // nothing yet.
  EXPECT_FALSE(ledger.may_begin_motion(token));

  // The wrong party confirming does not count, which is what stops rule 2 being
  // satisfied by one station twice.
  EXPECT_EQ(ledger.accept(token, "up", at(1.0)), HandoffReply::WRONG_PARTY);
  EXPECT_FALSE(ledger.may_begin_motion(token));

  EXPECT_EQ(ledger.accept(token, "down", at(1.0)), HandoffReply::OK);
  EXPECT_TRUE(ledger.may_begin_motion(token));
}

TEST(HandoffLedgerTest, CompletingBeforeConfirmationIsRefusedAndMovesNothing)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string token =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_FALSE(token.empty());

  EXPECT_EQ(
    ledger.complete(registry, token, "belt", WorkpiecePhase::IN_TRANSIT, at(1.0)),
    HandoffReply::WRONG_PHASE);
  EXPECT_EQ(registry.owner_of("part").value(), "up")
    << "ownership moved for a handoff the receiving station never agreed to";
}

TEST(HandoffLedgerTest, OwnershipMovesOnceAndOnlyOnCompletion)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string token =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_EQ(ledger.accept(token, "down", at(1.0)), HandoffReply::OK);

  EXPECT_EQ(registry.owner_of("part").value(), "up")
    << "confirming a handoff moved ownership; only completing it may";

  ASSERT_EQ(
    ledger.complete(registry, token, "conveyor_1", WorkpiecePhase::IN_TRANSIT, at(2.0)),
    HandoffReply::OK);
  EXPECT_EQ(registry.owner_of("part").value(), "down");
  EXPECT_EQ(registry.find("part")->location_id, "conveyor_1");

  // A completed handoff is terminal. Replaying its token must not move anything
  // a second time.
  EXPECT_EQ(
    ledger.complete(registry, token, "conveyor_1", WorkpiecePhase::IN_TRANSIT, at(3.0)),
    HandoffReply::UNKNOWN_TOKEN);
}

TEST(HandoffLedgerTest, ATimeoutLeavesTheUpstreamStationHoldingTheWorkpiece)
{
  // Rule 3 in full: "a timeout has a defined outcome, not merely an expiry: the
  // upstream robot retains ownership and the line reports a blocked station".
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string token =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_EQ(ledger.accept(token, "down", at(1.0)), HandoffReply::OK);

  const auto expired = ledger.expire(at(11.0));
  ASSERT_EQ(expired.size(), 1u);
  EXPECT_EQ(expired.front().from_station_id, "up")
    << "the record does not say who still owns the piece, so the line cannot report "
       "the right station blocked";
  EXPECT_EQ(expired.front().phase, HandoffPhase::TIMED_OUT);

  EXPECT_EQ(registry.owner_of("part").value(), "up");
  EXPECT_FALSE(ledger.may_begin_motion(token));
  // And it cannot be resurrected: an arm must not move toward a rendezvous the
  // other side has given up on.
  EXPECT_EQ(
    ledger.complete(registry, token, "belt", WorkpiecePhase::IN_TRANSIT, at(12.0)),
    HandoffReply::UNKNOWN_TOKEN);
}

TEST(HandoffLedgerTest, ALateConfirmationIsRefused)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string token =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  EXPECT_EQ(ledger.accept(token, "down", at(11.0)), HandoffReply::EXPIRED);
  EXPECT_FALSE(ledger.may_begin_motion(token));
}

TEST(HandoffLedgerTest, OneWorkpieceCannotHaveTwoLiveHandoffs)
{
  // Two live handoffs on one piece is two stations preparing to receive it,
  // which is the ambiguity rule 1 exists to make unrepresentable.
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string first =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_FALSE(first.empty());
  const std::string second = ledger.offer(
    registry, "part", "up", "elsewhere", at(0.0), rclcpp::Duration::from_seconds(10.0));
  EXPECT_TRUE(second.empty());
  EXPECT_EQ(ledger.live(), 1u);
}

TEST(HandoffLedgerTest, AnAbandonedHandoffFreesTheWorkpieceToBeOfferedAgain)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  const std::string first =
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0));
  ASSERT_EQ(ledger.abandon(first, "up"), HandoffReply::OK);
  EXPECT_EQ(registry.owner_of("part").value(), "up");

  const std::string second =
    ledger.offer(registry, "part", "up", "down", at(1.0), rclcpp::Duration::from_seconds(10.0));
  EXPECT_FALSE(second.empty());
  EXPECT_NE(first, second) << "a reissued token collided with the one it replaced";
}

TEST(HandoffLedgerTest, ADownstreamStationFindsTheOfferAddressedToIt)
{
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "up", "up"), RegistryOutcome::OK);
  ASSERT_FALSE(
    ledger.offer(registry, "part", "up", "down", at(0.0), rclcpp::Duration::from_seconds(10.0))
    .empty());

  EXPECT_FALSE(ledger.offer_awaiting("somebody_else").has_value());
  const auto offer = ledger.offer_awaiting("down");
  ASSERT_TRUE(offer.has_value());
  EXPECT_EQ(offer->workpiece_id, "part");
}

TEST(HandoffLedgerTest, ATokenNamesNeitherPartyNorZone)
{
  // ADR-0024 requires L3 to be unable to tell who is on the other side. A token
  // spelling out the peer would hand it that knowledge through the back door.
  WorkpieceRegistry registry;
  HandoffLedger ledger;
  ASSERT_EQ(registry.admit("part", "station_transfer_1", "station_transfer_1"),
    RegistryOutcome::OK);
  const std::string token = ledger.offer(
    registry, "part", "station_transfer_1", "station_transfer_2", at(0.0),
    rclcpp::Duration::from_seconds(10.0));
  ASSERT_FALSE(token.empty());
  EXPECT_EQ(token.find("station_transfer_1"), std::string::npos);
  EXPECT_EQ(token.find("station_transfer_2"), std::string::npos);
  EXPECT_EQ(token.find("cell_a"), std::string::npos);
  EXPECT_EQ(token.find("part"), std::string::npos);
}

// ---------------------------------------------------------------------------
// Recovery.
// ---------------------------------------------------------------------------

TEST(RecoveryPolicyTest, EveryDeclaredCodeHasAResponse)
{
  using cite_orchestration::recovery_for;
  EXPECT_EQ(recovery_for(ResultCode::SUCCESS), Recovery::NONE);
  EXPECT_EQ(recovery_for(ResultCode::CANCELLED), Recovery::NONE);
  EXPECT_EQ(recovery_for(ResultCode::PLANNING_FAILED), Recovery::RETRY_DIFFERENTLY);
  EXPECT_EQ(recovery_for(ResultCode::PRECONDITION_FAILED), Recovery::RETRY_DIFFERENTLY);
  EXPECT_EQ(recovery_for(ResultCode::EXECUTION_FAILED), Recovery::RETRY_SAME);
  EXPECT_EQ(recovery_for(ResultCode::TIMEOUT), Recovery::RETRY_SAME);
  EXPECT_EQ(recovery_for(ResultCode::MOTION_INTERRUPTED), Recovery::ESCALATE);
  EXPECT_EQ(recovery_for(ResultCode::UNREACHABLE), Recovery::ESCALATE);
  EXPECT_EQ(recovery_for(ResultCode::NOT_IMPLEMENTED), Recovery::ESCALATE);
  EXPECT_EQ(recovery_for(ResultCode::SAFETY_BLOCKED), Recovery::STOP_LINE);
  EXPECT_EQ(recovery_for(ResultCode::HARDWARE_FAULT), Recovery::STOP_LINE);
}

TEST(RecoveryPolicyTest, AnInterruptedMotionIsNeverRetriedAndDoesNotStopTheLine)
{
  // ADR-0037. `MOTION_INTERRUPTED` says the arm stopped part-way and is holding a
  // position no part of the commanded motion asked for, and that nothing on this
  // stack reports why. Replanning from a model of the world the abort itself
  // contradicted is the one thing that must not happen.
  using cite_orchestration::recovery_for;
  EXPECT_NE(recovery_for(ResultCode::MOTION_INTERRUPTED), Recovery::RETRY_SAME);
  EXPECT_NE(recovery_for(ResultCode::MOTION_INTERRUPTED), Recovery::RETRY_DIFFERENTLY);
  EXPECT_NE(recovery_for(ResultCode::MOTION_INTERRUPTED), Recovery::NONE);

  // A budget cannot soften it into a retry either, at any spend.
  EXPECT_EQ(recovery_for(ResultCode::MOTION_INTERRUPTED, 0, 5), Recovery::ESCALATE);

  // ESCALATE AND NOT STOP_LINE: one station is compromised, the cell is not.
  // `STOP_LINE` stays reserved for the two codes that say the cell itself cannot
  // be commanded, and widening it here would make every path-tolerance abort a
  // line-wide fault.
  EXPECT_NE(recovery_for(ResultCode::MOTION_INTERRUPTED), Recovery::STOP_LINE);
  EXPECT_NE(
    recovery_for(ResultCode::MOTION_INTERRUPTED), recovery_for(ResultCode::SAFETY_BLOCKED));
  EXPECT_NE(
    recovery_for(ResultCode::MOTION_INTERRUPTED), recovery_for(ResultCode::HARDWARE_FAULT));
}

TEST(RecoveryPolicyTest, AnInterruptedMotionIsAnsweredDifferentlyFromAnEndpointFailure)
{
  // The whole point of splitting `EXECUTION_FAILED` (ADR-0037). Before the split
  // both arrived under one code and both were retried; if these two ever agree
  // again the split has been undone and the arm that stopped mid-path is being
  // replanned around unattended.
  using cite_orchestration::recovery_for;
  EXPECT_NE(
    recovery_for(ResultCode::MOTION_INTERRUPTED), recovery_for(ResultCode::EXECUTION_FAILED));
}

TEST(RecoveryPolicyTest, AnUnreachablePoseIsNeverRetried)
{
  // The distinction the code set was widened for. `UNREACHABLE` means no IK
  // solution exists AT ALL, so the same goal cannot succeed however often it is
  // sent; `PLANNING_FAILED` means one exists and no path to it was found.
  // Collapsing the two would send the line round the same loop for ever.
  using cite_orchestration::recovery_for;
  EXPECT_NE(recovery_for(ResultCode::UNREACHABLE), Recovery::RETRY_SAME);
  EXPECT_NE(recovery_for(ResultCode::UNREACHABLE), Recovery::RETRY_DIFFERENTLY);
  EXPECT_NE(recovery_for(ResultCode::UNREACHABLE), recovery_for(ResultCode::PLANNING_FAILED));
}

TEST(RecoveryPolicyTest, ASafetyRefusalStopsTheLineRatherThanRetrying)
{
  using cite_orchestration::recovery_for;
  // Retrying through a safety refusal is how a coordination bug becomes an
  // injury. The budget must not soften it into a retry either.
  EXPECT_EQ(recovery_for(ResultCode::SAFETY_BLOCKED, 0, 5), Recovery::STOP_LINE);
}

TEST(RecoveryPolicyTest, AnUnknownCodeEscalatesRatherThanRetrying)
{
  using cite_orchestration::recovery_for;
  // A `ResultCode` extended by a newer producer. The one thing worse than not
  // knowing what went wrong is retrying through it.
  EXPECT_EQ(recovery_for(200), Recovery::ESCALATE);
}

TEST(RecoveryPolicyTest, RetriesAreBoundedAndThenEscalate)
{
  using cite_orchestration::recovery_for;
  EXPECT_EQ(recovery_for(ResultCode::EXECUTION_FAILED, 0, 2), Recovery::RETRY_SAME);
  EXPECT_EQ(recovery_for(ResultCode::EXECUTION_FAILED, 1, 2), Recovery::RETRY_SAME);
  EXPECT_EQ(recovery_for(ResultCode::EXECUTION_FAILED, 2, 2), Recovery::ESCALATE)
    << "an unbounded retry is how a line works while silently degrading";
  EXPECT_EQ(recovery_for(ResultCode::PLANNING_FAILED, 9, 2), Recovery::ESCALATE);
}

// ---------------------------------------------------------------------------
// Topology to plan.
// ---------------------------------------------------------------------------

TEST(LinePlanTest, StationsComeOutInFlowOrderNotArrayOrder)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable()) << (plan.refusals.empty() ? "" : plan.refusals.front());

  ASSERT_EQ(plan.stations.size(), 3u);
  EXPECT_EQ(plan.stations[0].id, "station_transfer_1");
  EXPECT_EQ(plan.stations[1].id, "station_transfer_2");
  EXPECT_EQ(plan.stations[2].id, "station_transfer_3");

  // The fixture lists the sink first, so an implementation that filtered the
  // array in place would put the stations in the wrong order and this is what
  // catches it.
  EXPECT_EQ(plan.stations[0].upstream_id, "station_infeed");
  EXPECT_TRUE(plan.stations[0].upstream_is_source);
  EXPECT_EQ(plan.stations[2].downstream_id, "station_accumulation");
  EXPECT_TRUE(plan.stations[2].downstream_is_sink);
}

TEST(LinePlanTest, SourcesAndSinksGetNoSubtreeButTheSinkIsStillPlanned)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());

  for (const auto & entry : plan.stations) {
    EXPECT_FALSE(entry.actor_asset_id.empty())
      << entry.id << " has no actor, so nothing would ever tick its subtree";
  }
  ASSERT_EQ(plan.sinks.size(), 1u);
  EXPECT_EQ(plan.sinks.front().id, "station_accumulation");
  EXPECT_EQ(plan.sinks.front().capacity, 12u) << "the sink's capacity came from somewhere "
    "other than the model";
  EXPECT_EQ(
    plan.sinks.front().inbound_buffer,
    cite_orchestration::buffer_key("station_transfer_3", "station_accumulation"));
}

TEST(LinePlanTest, ResourcesAndCapacitiesComeFromTheModel)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());

  ResourceArbiter arbiter;
  for (const auto & resource : plan.resources) {
    arbiter.declare_resource(resource.name, resource.capacity);
  }

  // One buffer per edge, at the model's own capacity.
  EXPECT_EQ(
    arbiter.capacity(cite_orchestration::buffer_key("station_transfer_1", "station_transfer_2")),
    4u);
  EXPECT_EQ(
    arbiter.capacity(cite_orchestration::buffer_key("station_transfer_3",
    "station_accumulation")), 12u);
  // One reach claim per frame, exclusive. Two arms in one place at once is the
  // case this is for.
  EXPECT_EQ(arbiter.capacity("pick_1"), 1u);
  EXPECT_EQ(arbiter.capacity("place_3"), 1u);
}

TEST(LinePlanTest, TheTriggerStateIsTranslatedRatherThanCopied)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());

  // `StationTopology.TRIGGER_ON_*` and `DetectionEvent.STATE_*` are separate
  // contracts that happen to carry the same numbers today. The plan must emit the
  // one the subscriber compares against.
  EXPECT_EQ(plan.stations[1].trigger_detection_state, DetectionEvent::STATE_BLOCKED);
  EXPECT_EQ(plan.stations[0].trigger_detection_state, DetectionEvent::STATE_BLOCKED)
    << "the infeed station's own sensor was not translated; it is fed from outside the "
       "cell and a beam is the only thing that tells it a part has arrived";
  for (const auto & entry : plan.stations) {
    EXPECT_FALSE(entry.trigger_topic.empty())
      << "station '" << entry.id << "' acts and observes nothing. A station with no "
      "trigger falls through AwaitTrigger and comes to rest in DetectAt, which is "
      "how the line hung before `beam_pick` was added to the model";
  }
}

TEST(LinePlanTest, ACycleIsRefusedRatherThanRunInSomeOrder)
{
  LineTopology topology = cell_a_shaped();
  topology.edges.push_back(edge("station_transfer_3", "station_transfer_1", "conveyor_x", 1));
  const LinePlan plan = cite_orchestration::plan_line(topology);
  EXPECT_FALSE(plan.usable());
  ASSERT_FALSE(plan.refusals.empty());
  EXPECT_NE(plan.refusals.front().find("cycle"), std::string::npos);
}

TEST(LinePlanTest, AMergingFlowIsRefusedRatherThanResolvedByGuessing)
{
  LineTopology topology = cell_a_shaped();
  topology.stations.push_back(
    station("station_transfer_4", StationTopology::TYPE_TRANSFER, "arm_4", "pick_4", "place_4"));
  topology.edges.push_back(edge("station_infeed", "station_transfer_4", "", 6));
  topology.edges.push_back(edge("station_transfer_4", "station_transfer_2", "conveyor_4", 4));

  const LinePlan plan = cite_orchestration::plan_line(topology);
  EXPECT_FALSE(plan.usable())
    << "a flow that merges was run anyway, which sends work-pieces down one branch "
       "silently";
}

TEST(LinePlanTest, ADirectArmToArmHandoffIsRefusedWithItsReason)
{
  // THE ORIENTATION GATE. A grasp holds a position and not an orientation: up to
  // 18.7 degrees of residual rotation between the jaws survives the grasp-plane
  // correction (ADR-0029). A conveyor-mediated handoff does not care, because the
  // receiving station re-observes the part with `Detect` after it has been let
  // go of. A direct one does, because nothing re-observes it.
  LineTopology topology = cell_a_shaped();
  for (auto & entry : topology.edges) {
    if (entry.from_station_id == "station_transfer_1") {
      entry.via_asset_id.clear();
    }
  }

  const LinePlan plan = cite_orchestration::plan_line(topology);
  EXPECT_FALSE(plan.usable()) << "a direct arm-to-arm handoff was planned as though the "
    "line knew how the part is held";
  ASSERT_FALSE(plan.refusals.empty());
  EXPECT_NE(plan.refusals.front().find("18.7"), std::string::npos)
    << "the refusal does not say why, so whoever hits it has to rediscover the "
       "measurement";
}

TEST(LinePlanTest, ASourceFeedingATransferStationIsNotADirectHandoff)
{
  // The edge from the source has no `via` either, and must NOT trip the gate:
  // there is no upstream gripper, so there is no unknown orientation. A gate that
  // fired on "no via" alone would refuse the whole of today's model.
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  EXPECT_TRUE(plan.usable()) << (plan.refusals.empty() ? "" : plan.refusals.front());
}

TEST(LinePlanTest, EachStationIndexesTheBeltItPicksFromAndNotTheOneItPlacesOnto)
{
  // ADR-0032. The belt a station stops is the `via_asset_id` of its INBOUND edge:
  // the one work arrives on. Stopping the outbound belt instead would freeze the
  // link the station is about to place onto, which is the same rule applied one
  // station too far along and looks identical until the line runs.
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable()) << (plan.refusals.empty() ? "" : plan.refusals.front());
  ASSERT_EQ(plan.stations.size(), 3u);

  EXPECT_EQ(plan.stations[0].id, "station_transfer_1");
  EXPECT_TRUE(plan.stations[0].inbound_via_asset_id.empty())
    << "the station fed from a table indexes a belt that does not carry to it";
  EXPECT_EQ(plan.stations[0].outbound_via_asset_id, "conveyor_1");

  EXPECT_EQ(plan.stations[1].id, "station_transfer_2");
  EXPECT_EQ(plan.stations[1].inbound_via_asset_id, "conveyor_1");
  EXPECT_EQ(plan.stations[2].inbound_via_asset_id, "conveyor_2");

  // `conveyor_3` carries into `station_accumulation`, which is a sink: a trigger
  // and no actor, so it has no `CompleteHandoff` to run the belt again on. It
  // must appear as no station's indexed belt at all, or it is stopped for ever.
  for (const auto & entry : plan.stations) {
    EXPECT_NE(entry.inbound_via_asset_id, "conveyor_3")
      << "station '" << entry.id << "' would index the belt that feeds the sink";
  }
}

TEST(LinePlanTest, AStationFedByABeltWithNoTriggerIsRefused)
{
  // Nothing would ever stop that belt, so the work-piece rides past the pick
  // point in under a second. Before ADR-0032 that was the line's behaviour and
  // nothing said so; now it is refused at plan time, before anything moves.
  LineTopology topology = cell_a_shaped();
  for (auto & entry : topology.stations) {
    if (entry.id == "station_transfer_2") {
      entry.trigger_topic.clear();
    }
  }

  const LinePlan plan = cite_orchestration::plan_line(topology);
  EXPECT_FALSE(plan.usable());
  ASSERT_FALSE(plan.refusals.empty());
  bool named = false;
  for (const auto & refusal : plan.refusals) {
    named = named || refusal.find("conveyor_1") != std::string::npos;
  }
  EXPECT_TRUE(named) << "the refusal does not name the belt that would never stop";
}

// ---------------------------------------------------------------------------
// Plan to tree.
// ---------------------------------------------------------------------------

TEST(LineTreeTest, OneSubtreePerStationAndNoStationNamedInCode)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());
  const auto tree = cite_orchestration::line_tree_xml(plan, fixture_actions());
  ASSERT_TRUE(tree.refusals.empty()) << tree.refusals.front();

  std::size_t subtrees = 0;
  for (std::size_t at_index = tree.xml.find("<SubTree"); at_index != std::string::npos;
    at_index = tree.xml.find("<SubTree", at_index + 1))
  {
    ++subtrees;
  }
  EXPECT_EQ(subtrees, plan.stations.size())
    << "the number of station subtrees is not the number of stations the model declares";

  for (const auto & entry : plan.stations) {
    EXPECT_NE(tree.xml.find("station=\"" + entry.id + "\""), std::string::npos);
    EXPECT_NE(tree.xml.find("asset=\"" + entry.actor_asset_id + "\""), std::string::npos);
  }
  // The conveyor, not the station, is where a piece physically is between two
  // stations.
  EXPECT_NE(tree.xml.find("outbound_location=\"conveyor_1\""), std::string::npos);
  // The last station hands to a sink over conveyor_3.
  EXPECT_NE(tree.xml.find("outbound_location=\"conveyor_3\""), std::string::npos);
}

TEST(LineTreeTest, EachSubtreeIsToldWhichBeltItsStationIndexes)
{
  // The station subtree names no asset; the belt it resumes arrives as a static
  // remap generated from the topology, exactly as its frames and its actor do.
  // If this ever has to be written by hand, the model has stopped being the
  // single source of truth.
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());
  const auto tree = cite_orchestration::line_tree_xml(plan, fixture_actions());
  ASSERT_TRUE(tree.refusals.empty()) << tree.refusals.front();

  const std::size_t first = tree.xml.find("station=\"station_transfer_1\"");
  ASSERT_NE(first, std::string::npos);
  const std::string fed_by_a_table = tree.xml.substr(first, tree.xml.find("/>", first) - first);
  EXPECT_NE(fed_by_a_table.find("inbound_belt=\"\""), std::string::npos)
    << "the station that picks off a table was given a belt to resume";

  const std::size_t second = tree.xml.find("station=\"station_transfer_2\"");
  ASSERT_NE(second, std::string::npos);
  const std::string fed_by_a_belt = tree.xml.substr(second, tree.xml.find("/>", second) - second);
  EXPECT_NE(fed_by_a_belt.find("inbound_belt=\"conveyor_1\""), std::string::npos);
  // It PLACES onto conveyor_2 and must not index that one: freezing the outbound
  // link is the same rule applied one station too far along.
  EXPECT_EQ(fed_by_a_belt.find("inbound_belt=\"conveyor_2\""), std::string::npos);
}

TEST(LineTreeTest, WorkEntersTheLineOnlyWhereTheModelSaysItDoes)
{
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());
  const auto tree = cite_orchestration::line_tree_xml(plan, fixture_actions());
  ASSERT_TRUE(tree.refusals.empty());

  // Station 1 is fed by the source, so it admits what arrives; every station
  // after it is handed its work and must refuse to adopt anything else.
  const std::size_t first = tree.xml.find("station=\"station_transfer_1\"");
  ASSERT_NE(first, std::string::npos);
  const std::string element = tree.xml.substr(first, tree.xml.find("/>", first) - first);
  EXPECT_NE(element.find("admits_work=\"1\""), std::string::npos);

  const std::size_t second = tree.xml.find("station=\"station_transfer_2\"");
  ASSERT_NE(second, std::string::npos);
  const std::string later = tree.xml.substr(second, tree.xml.find("/>", second) - second);
  EXPECT_NE(later.find("admits_work=\"0\""), std::string::npos);
}

TEST(LineTreeTest, NoStationIsEverToldToTreatAnEmptyDetectionAsAnIdleLine)
{
  // THE CRITICAL DEFECT, LOCKED OUT AT THE POINT IT WAS GENERATED.
  //
  // `line_tree_xml` used to emit `require_immediate="0"` for a station with no
  // trigger, which told `DetectAt` that an empty result meant the line was idle
  // and to look again. `Detect` answers an UNOBSERVED region with the same
  // SUCCESS and the same empty list as an observed empty one, so that station
  // re-sent for ever: measured as `station_transfer_1` at WORKING with occupancy
  // 0/1 while the whole line waited behind it.
  //
  // The attribute is gone and so is the port it fed. This asserts the absence,
  // because the defect was an attribute being PRESENT with a particular value —
  // a test that only checked for `"1"` would pass again the day somebody
  // reintroduced the conditional.
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());
  const auto tree = cite_orchestration::line_tree_xml(plan, fixture_actions());
  ASSERT_TRUE(tree.refusals.empty());

  EXPECT_EQ(tree.xml.find("require_immediate"), std::string::npos)
    << "the generated tree still carries a require_immediate attribute. An empty "
       "detection is always a reported failure now; waiting for work is AwaitTrigger's "
       "job, from the sensor the topology names";
}

TEST(LineTreeTest, AMissingActionNameIsRefusedRatherThanComposed)
{
  // Names arrive as data. The defect kept out is a node composing
  // "/cite/<zone>/<asset>/<skill>" from a format string of its own, which this
  // project has removed from three separate files.
  const LinePlan plan = cite_orchestration::plan_line(cell_a_shaped());
  ASSERT_TRUE(plan.usable());

  SkillActionsByAsset incomplete = fixture_actions();
  incomplete.erase("arm_2");
  const auto tree = cite_orchestration::line_tree_xml(plan, incomplete);
  EXPECT_TRUE(tree.xml.empty());
  ASSERT_FALSE(tree.refusals.empty());
  EXPECT_NE(tree.refusals.front().find("arm_2"), std::string::npos);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
