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

// The operator reset (ADR-0037 decision 5).
//
// What is under test is a set of REFUSALS, and refusals are the part of an
// operator control that a happy-path test never reaches. The service exists so a
// blocked station can be cleared without restarting the process; it must not
// become a general "make it go" button, and it must not command motion.
//
// The rules are exercised through the real `reset_station` and the real
// `StationReset::handle`, not through a copy. A test that reimplemented the
// decision would be asserting that two copies of a rule agree — which is the
// failure mode `line_maintenance.hpp` records for itself.

#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/msg/station_state.hpp>
#include <cite_interfaces/srv/reset_station.hpp>

#include "gtest/gtest.h"

#include "cite_orchestration/station_reset.hpp"

namespace
{

using cite_interfaces::msg::ResultCode;
using cite_interfaces::msg::StationState;
using cite_interfaces::srv::ResetStation;
using cite_orchestration::ResetOutcome;
using cite_orchestration::StationRuntime;
using cite_orchestration::reset_station;

constexpr char kBlockedReason[] = "result code 10: escalated to an operator";

std::set<std::string> known()
{
  return {"station_one", "station_two"};
}

std::map<std::string, StationRuntime> blocked_line()
{
  std::map<std::string, StationRuntime> stations;
  StationRuntime one;
  one.state = StationState::STATE_BLOCKED;
  one.blocked_reason = kBlockedReason;
  one.consecutive_failures = 3;
  stations["station_one"] = one;

  StationRuntime two;
  two.state = StationState::STATE_WAITING;
  stations["station_two"] = two;
  return stations;
}

}  // namespace

TEST(StationResetTest, ABlockedStationReturnsToWaitingAndTheReasonIsEchoed)
{
  auto stations = blocked_line();
  const ResetOutcome outcome = reset_station(stations, known(), "station_one");

  EXPECT_TRUE(outcome.accepted);
  EXPECT_EQ(outcome.result_code, ResultCode::SUCCESS);
  EXPECT_EQ(outcome.station_state, StationState::STATE_WAITING);

  // The reason survives in the RESPONSE, and this is the only place it can.
  // `LineState` is volatile and publishes only the first blocked station's
  // reason; `StationState` has no reason field at all. A reset that cleared it
  // without returning it would destroy the evidence of why the station stopped.
  EXPECT_EQ(outcome.cleared_reason, kBlockedReason);

  EXPECT_EQ(stations["station_one"].state, StationState::STATE_WAITING);
  EXPECT_TRUE(stations["station_one"].blocked_reason.empty())
    << "the reason must be cleared on the station, having been reported to the caller";
}

TEST(StationResetTest, TheReasonIsClearedExplicitlyAndNotAsASideEffect)
{
  // `SetStationState` clears `blocked_reason` whenever the new state is neither
  // BLOCKED nor FAULTED, so a reset written as "set the station to WAITING"
  // destroys the reason as its FIRST act and returns an empty string. This
  // asserts the ordering that avoids it: capture, then clear.
  auto stations = blocked_line();
  const ResetOutcome outcome = reset_station(stations, known(), "station_one");
  ASSERT_TRUE(outcome.accepted);
  EXPECT_FALSE(outcome.cleared_reason.empty())
    << "the reason was cleared before it was read, which is the defect this ordering exists "
    "to avoid";
}

TEST(StationResetTest, AStationThatIsNotBlockedIsRefusedRatherThanQuietlyAccepted)
{
  // Accepting this would make the service a general "make it go" button, and a
  // button that is safe to press when nothing is wrong gets pressed when
  // something is.
  for (const uint8_t state :
    {StationState::STATE_IDLE, StationState::STATE_WAITING, StationState::STATE_WORKING})
  {
    auto stations = blocked_line();
    stations["station_one"].state = state;
    const ResetOutcome outcome = reset_station(stations, known(), "station_one");

    EXPECT_FALSE(outcome.accepted) << "state " << static_cast<int>(state);
    EXPECT_EQ(outcome.result_code, ResultCode::PRECONDITION_FAILED);
    EXPECT_EQ(outcome.station_state, state) << "the refusal still reports where the station is";
    EXPECT_TRUE(outcome.cleared_reason.empty());
    EXPECT_EQ(stations["station_one"].state, state) << "a refused reset changed the station";
  }
}

TEST(StationResetTest, AFaultedStationIsRefusedWithADifferentCodeFromNothingToReset)
{
  // The refusal carries a CODE and not a bare false, because "there was nothing
  // to reset" and "this station is faulted and you may not" want opposite next
  // actions from an operator.
  auto stations = blocked_line();
  stations["station_one"].state = StationState::STATE_FAULTED;
  const ResetOutcome outcome = reset_station(stations, known(), "station_one");

  EXPECT_FALSE(outcome.accepted);
  EXPECT_EQ(outcome.result_code, ResultCode::HARDWARE_FAULT);
  EXPECT_NE(outcome.result_code, ResultCode::PRECONDITION_FAILED);
  EXPECT_EQ(stations["station_one"].state, StationState::STATE_FAULTED)
    << "clearing STATE_FAULTED is out of scope and must not happen by accident";
}

TEST(StationResetTest, NoStationMayBeResetWhileAnyOtherStationIsFaulted)
{
  // One faulted station is a faulted line — `line_maintenance.hpp` says so — and
  // STOP_LINE is set only by the two codes that mean the cell itself cannot be
  // commanded. Resuming one station of such a cell would be resuming a cell that
  // is not commandable.
  auto stations = blocked_line();
  stations["station_two"].state = StationState::STATE_FAULTED;
  const ResetOutcome outcome = reset_station(stations, known(), "station_one");

  EXPECT_FALSE(outcome.accepted);
  EXPECT_EQ(outcome.result_code, ResultCode::HARDWARE_FAULT);
  EXPECT_EQ(stations["station_one"].state, StationState::STATE_BLOCKED)
    << "the blocked station was reset while the line was faulted";
  EXPECT_EQ(stations["station_one"].blocked_reason, kBlockedReason);
}

TEST(StationResetTest, AnUnknownStationIsRefusedAndNoPhantomStationIsInvented)
{
  // `LineContext::station` is `operator[]` on a `std::map`, so asking it about an
  // unknown id DEFAULT-CONSTRUCTS one and returns a reference to it. A reset that
  // trusted the map would invent a station, report success, and change nothing
  // anybody can observe — the phantom appears in no `LineState`, because
  // `LineMaintenance` iterates the plan.
  auto stations = blocked_line();
  const std::size_t before = stations.size();
  const ResetOutcome outcome = reset_station(stations, known(), "station_nine");

  EXPECT_FALSE(outcome.accepted);
  EXPECT_EQ(outcome.result_code, ResultCode::PRECONDITION_FAILED);
  EXPECT_EQ(stations.size(), before) << "a station was invented by asking about it";

  const ResetOutcome empty = reset_station(stations, known(), "");
  EXPECT_FALSE(empty.accepted);
  EXPECT_EQ(stations.size(), before);
}

TEST(StationResetTest, AResetReturnsTheRetryBudgetSoTheStationCanActuallyTryAgain)
{
  // Left standing, the consecutive-failure count would put the station back over
  // its budget on its very next failure with no attempt spent — a reset that does
  // not reset. Clearing it commands no motion, which is the only property this
  // service has to preserve.
  auto stations = blocked_line();
  ASSERT_GT(stations["station_one"].consecutive_failures, 0u);
  ASSERT_TRUE(reset_station(stations, known(), "station_one").accepted);
  EXPECT_EQ(stations["station_one"].consecutive_failures, 0u);
}

TEST(StationResetTest, AResetTouchesNothingBeyondTheStationItNames)
{
  auto stations = blocked_line();
  stations["station_two"].current_workpiece_id = "wp_000007";
  stations["station_two"].state = StationState::STATE_WORKING;

  ASSERT_TRUE(reset_station(stations, known(), "station_one").accepted);

  EXPECT_EQ(stations["station_two"].state, StationState::STATE_WORKING);
  EXPECT_EQ(stations["station_two"].current_workpiece_id, "wp_000007");
}

TEST(StationResetTest, TheServiceNameIsTheOneTheInterfaceDeclares)
{
  // P1 and P3: the name is written once, on the `.srv`, and is discoverable with
  // `ros2 interface show`. A literal in the orchestrator would be a value in two
  // places, and a client would have to repeat it a third time.
  //
  // EXPECT_EQ and not EXPECT_STREQ: rosidl renders a `.srv` string constant as a
  // `std::basic_string`, not a `const char *`, so `STREQ` does not compile
  // against it at all.
  EXPECT_EQ(ResetStation::Request::SERVICE, "/cite/line/reset_station");
}

/// The real service object, driven through its real handler.
///
/// `handle` is called directly rather than through a client, deliberately: a
/// client blocking on a future served by the same executor is the deadlock every
/// service test in this repository has to avoid, and what is under test is the
/// decision and the response it fills in, not `rclcpp`'s request routing.
class StationResetService : public ::testing::Test
{
protected:
  void SetUp() override
  {
    node_ = std::make_shared<rclcpp::Node>("station_reset_test");
    stations_ = std::make_shared<std::map<std::string, StationRuntime>>(blocked_line());

    cite_orchestration::LineContext line;
    line.node = node_;
    line.stations = stations_;

    cite_orchestration::LinePlan plan;
    cite_orchestration::StationPlan one;
    one.id = "station_one";
    cite_orchestration::StationPlan two;
    two.id = "station_two";
    plan.stations = {one, two};

    // Outside `/cite/`, where no generated name can land: the suites run
    // concurrently on one ROS domain, and two servers on one service name make
    // each other fail in ways that read as unrelated defects.
    reset_ = std::make_unique<cite_orchestration::StationReset>(
      line, plan, "/station_reset_test/reset_station", std::make_shared<std::mutex>());
  }

  rclcpp::Node::SharedPtr node_;
  std::shared_ptr<std::map<std::string, StationRuntime>> stations_;
  std::unique_ptr<cite_orchestration::StationReset> reset_;
};

TEST_F(StationResetService, TheResponseCarriesAcceptanceTheCodeTheStateAndTheClearedReason)
{
  ResetStation::Request request;
  ResetStation::Response response;
  request.station_id = "station_one";
  reset_->handle(request, response);

  EXPECT_TRUE(response.accepted);
  EXPECT_EQ(response.result.code, ResultCode::SUCCESS);
  EXPECT_EQ(response.station_state, StationState::STATE_WAITING);
  EXPECT_EQ(response.cleared_reason, kBlockedReason);
  EXPECT_FALSE(response.result.detail.empty()) << "a refusal or an acceptance explains itself";
  EXPECT_EQ((*stations_)["station_one"].state, StationState::STATE_WAITING);
}

TEST_F(StationResetService, ARefusalFillsInTheCodeAndLeavesTheClearedReasonEmpty)
{
  ResetStation::Request request;
  ResetStation::Response response;
  request.station_id = "station_two";
  reset_->handle(request, response);

  EXPECT_FALSE(response.accepted);
  EXPECT_EQ(response.result.code, ResultCode::PRECONDITION_FAILED);
  EXPECT_TRUE(response.cleared_reason.empty());
  EXPECT_EQ(response.station_state, StationState::STATE_WAITING);
}

TEST_F(StationResetService, ASecondResetOfTheSameStationIsRefused)
{
  // Idempotence would be the wrong answer here. After the first reset there is
  // nothing to reset, and saying so is what stops this becoming a button that is
  // always safe to press.
  ResetStation::Request request;
  ResetStation::Response first;
  ResetStation::Response second;
  request.station_id = "station_one";
  reset_->handle(request, first);
  reset_->handle(request, second);

  EXPECT_TRUE(first.accepted);
  EXPECT_FALSE(second.accepted);
  EXPECT_EQ(second.result.code, ResultCode::PRECONDITION_FAILED);
  EXPECT_TRUE(second.cleared_reason.empty());
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int status = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return status;
}
