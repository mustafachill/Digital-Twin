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

// The operator reset: clear one station's block, and command nothing.
//
// ADR-0037 decision 5. `Recovery::ESCALATE` sets `STATE_BLOCKED` and logs that
// the station "is blocked and needs an operator" — and until this existed, that
// operator had no control at all. `cite_interfaces/srv/` held two services,
// neither of them this one, and `cite_orchestration` contained no
// `create_service` call whatsoever. The only exit was restarting the process.
//
// That was survivable while `ESCALATE` was rare. ADR-0037 makes it routine:
// `MOTION_INTERRUPTED -> ESCALATE` means the first path-tolerance abort blocks a
// station. Without a reset, that change stops the line correctly and never starts
// it again — trading a diagnosis gap for an availability gap, and this project's
// history says an availability gap gets the detector exempted rather than fixed.
//
// ## RESET IS NOT START
//
// Clearing the block returns the station to `STATE_WAITING` — awaiting its own
// trigger — and that is the whole effect. Nothing here plans, sends a `MoveTo`
// goal, drives the arm home or resumes a belt. If the arm has to be cleared out
// of the way, that is a separate, deliberate operator action.
//
// The safety argument is the obvious one. The diagnostic argument is the one
// usually forgotten, and it is the reason Universal Robots' own Product Alert
// gives: automatic acknowledgement masks the faults that predict a failure. A
// reset that silently re-drives the arm destroys the evidence of why it stopped.
// Restarting the process — the previous recourse — did exactly that, more slowly.
//
// NONE OF THIS IS A PROTECTIVE MEASURE. It removes an automatic resumption. What
// stops an arm remains the vendor controller's torque limiting and physical
// guarding (charter §3.2).
//
// ## Three things the obvious implementation gets wrong
//
//  1. `SetStationState` clears `blocked_reason` whenever the new state is neither
//     BLOCKED nor FAULTED, so a reset written as "set the station to WAITING"
//     destroys the reason as its first act. The state is therefore cleared
//     EXPLICITLY below, never as a side effect of that leaf.
//  2. `LineState` cannot carry the reason afterwards — it is volatile and says of
//     itself that it is "a periodic report of the present, not a record",
//     `StationState` has no reason field, and `LineMaintenance` publishes only the
//     FIRST blocked station's reason. So the reason is echoed in the typed
//     response and logged at WARN.
//  3. Scope is ONE station, and a faulted line refuses everything.

#ifndef CITE_ORCHESTRATION__STATION_RESET_HPP_
#define CITE_ORCHESTRATION__STATION_RESET_HPP_

#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <utility>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/msg/station_state.hpp>
#include <cite_interfaces/srv/reset_station.hpp>

#include "cite_orchestration/line_nodes.hpp"
#include "cite_orchestration/line_plan.hpp"

namespace cite_orchestration
{

/// What a reset decided, before any of it is put on the wire.
struct ResetOutcome
{
  bool accepted{false};
  //: A `ResultCode.code`. Never a bare false: the caller must be able to tell
  //: "there was nothing to reset" from "this station is faulted and you may not",
  //: because those want opposite next actions from an operator.
  uint8_t result_code{cite_interfaces::msg::ResultCode::PRECONDITION_FAILED};
  //: A `StationState.STATE_*`, after the call.
  uint8_t station_state{cite_interfaces::msg::StationState::STATE_IDLE};
  std::string cleared_reason;
  //: Prose for a person, for `ResultCode.detail` and for the log. Nothing parses
  //: it, exactly as `ResultCode.msg` says of that field.
  std::string detail;
};

/// Decide and apply a reset for one station.
///
/// Free function over the station map rather than a method on the service, so
/// that the rules can be proved without standing up a node — the same reason
/// `recovery_policy.hpp` is a free function and not a branch inside a leaf.
///
/// `known` is the set of station ids the LINE PLAN declares. It is consulted
/// rather than the map, because `LineContext::station` is `operator[]` on a
/// `std::map`: asking it about an unknown id silently DEFAULT-CONSTRUCTS a
/// station and returns a reference to it, so a reset that trusted the map would
/// invent a phantom station, report success, and change nothing anybody can see.
inline ResetOutcome reset_station(
  std::map<std::string, StationRuntime> & stations, const std::set<std::string> & known,
  const std::string & station_id)
{
  using cite_interfaces::msg::ResultCode;
  using cite_interfaces::msg::StationState;

  ResetOutcome outcome;

  if (station_id.empty() || known.find(station_id) == known.end()) {
    outcome.result_code = ResultCode::PRECONDITION_FAILED;
    outcome.detail = "'" + station_id + "' is not a station on this line";
    return outcome;
  }

  // A FAULTED LINE REFUSES EVERYTHING, including a station that is merely
  // blocked. `line_maintenance.hpp` makes one faulted station a faulted line, and
  // `STOP_LINE` — the only thing that sets FAULTED — is reserved for
  // `SAFETY_BLOCKED` and `HARDWARE_FAULT`, the two codes that say the cell itself
  // cannot be commanded at all. Resuming one station of such a cell would be
  // resuming a cell that is not commandable.
  //
  // Clearing `STATE_FAULTED` is deliberately out of scope. It needs a decision
  // about what evidence makes a cell commandable again, and that belongs with the
  // safety layer that does not exist yet. Recording it as open is the honest
  // answer; implementing a line-wide reset here would be inventing that evidence
  // standard by accident.
  for (const auto & id : known) {
    const auto entry = stations.find(id);
    if (entry != stations.end() && entry->second.state == StationState::STATE_FAULTED) {
      const auto self = stations.find(station_id);
      outcome.result_code = ResultCode::HARDWARE_FAULT;
      outcome.station_state =
        self == stations.end() ? StationState::STATE_IDLE : self->second.state;
      outcome.detail = id == station_id ?
        "station '" + station_id + "' is faulted; clearing a fault is not this service's" :
        "station '" + id + "' is faulted, which makes the whole line faulted; no station "
        "may be reset while it is";
      return outcome;
    }
  }

  const auto entry = stations.find(station_id);
  if (entry == stations.end() || entry->second.state != StationState::STATE_BLOCKED) {
    // REFUSED, not silently accepted as a no-op. Accepting it would make this a
    // general "make it go" button, and a button that is safe to press when
    // nothing is wrong gets pressed when something is.
    outcome.result_code = ResultCode::PRECONDITION_FAILED;
    outcome.station_state =
      entry == stations.end() ? StationState::STATE_IDLE : entry->second.state;
    outcome.detail =
      "station '" + station_id + "' is not blocked, so there is nothing to reset";
    return outcome;
  }

  StationRuntime & runtime = entry->second;
  outcome.cleared_reason = runtime.blocked_reason;

  // EXPLICITLY, not by going through `SetStationState`, which would clear the
  // reason as a side effect of the state change and destroy it before it could be
  // reported. The reason is captured above and cleared here, in that order.
  runtime.blocked_reason.clear();
  runtime.state = StationState::STATE_WAITING;
  // The consecutive-failure count is the retry budget's spend, and an operator
  // acknowledging the block is the deliberate act that ends the run of failures it
  // was counting. Left standing, the station would escalate again on its very next
  // failure with no attempt spent, which is a reset that does not reset.
  //
  // ADR-0037 does not decide this either way; it is the implementation's call and
  // it commands no motion.
  runtime.consecutive_failures = 0;

  outcome.accepted = true;
  outcome.result_code = ResultCode::SUCCESS;
  outcome.station_state = StationState::STATE_WAITING;
  outcome.detail = "station '" + station_id + "' is no longer blocked and awaits its trigger";
  return outcome;
}

/// The reset, as a ROS 2 service on the line orchestrator's node.
///
/// A class beside `LineMaintenance` rather than a lambda in `main`, for the
/// reason `line_maintenance.hpp` gives for itself: a test can then drive the REAL
/// one, instead of asserting that two copies of a rule agree.
///
/// ## Threading, stated because this is the package's first cross-thread writer
///
/// Everything else that touches `StationRuntime` runs on the TICK thread —
/// `line_orchestrator.cpp` says so outright, and it is why the registry, ledger
/// and arbiter need no lock. A service callback runs on the EXECUTOR thread, so
/// it is the first thing that does not.
///
/// Two deliberate choices keep that honest:
///
///   * The callback takes `tick_mutex`, which the orchestrator's loop holds
///     across a whole tick. So a reset lands BETWEEN ticks and never inside one,
///     and the tick-thread-only invariant every other reader relies on still
///     holds. Serialising against the tick is what makes this safe, not a lock on
///     the map.
///   * The service is given its OWN callback group. Waiting on that mutex is a
///     bounded wait, but it is a wait, and on the node's default mutually
///     exclusive group it would sit in front of the trigger subscriptions that
///     tell stations a part has arrived. A reset must not be able to stall the
///     line it is trying to unblock.
class StationReset
{
public:
  using ResetService = cite_interfaces::srv::ResetStation;

  StationReset(
    LineContext line, const LinePlan & plan, const std::string & service_name,
    std::shared_ptr<std::mutex> tick_mutex)
  : line_(std::move(line)), tick_mutex_(std::move(tick_mutex))
  {
    for (const auto & station : plan.stations) {
      known_.insert(station.id);
    }
    callback_group_ = line_.node->create_callback_group(
      rclcpp::CallbackGroupType::MutuallyExclusive);
    service_ = line_.node->create_service<ResetService>(
      service_name,
      [this](
        const std::shared_ptr<ResetService::Request> request,
        std::shared_ptr<ResetService::Response> response) {
        handle(*request, *response);
      },
      rclcpp::ServicesQoS(), callback_group_);
  }

  /// The handler, exposed so a test can drive the real decision without a client.
  void handle(const ResetService::Request & request, ResetService::Response & response)
  {
    ResetOutcome outcome;
    {
      const std::lock_guard<std::mutex> lock(*tick_mutex_);
      outcome = reset_station(*line_.stations, known_, request.station_id);
    }

    response.accepted = outcome.accepted;
    response.result.code = outcome.result_code;
    response.result.detail = outcome.detail;
    response.station_state = outcome.station_state;
    response.cleared_reason = outcome.cleared_reason;

    // Logged at WARN and in a stable shape — station id, then the reason cleared
    // — so the record survives in the process log whether or not anyone was
    // subscribed. `LineState` cannot keep it: it is volatile, and it publishes
    // only the first blocked station's reason anyway.
    if (outcome.accepted) {
      RCLCPP_WARN(
        line_.node->get_logger(), "reset station '%s'; cleared blocked reason: %s",
        request.station_id.c_str(),
        outcome.cleared_reason.empty() ? "(none recorded)" : outcome.cleared_reason.c_str());
    } else {
      RCLCPP_WARN(
        line_.node->get_logger(), "refused to reset station '%s': %s",
        request.station_id.c_str(), outcome.detail.c_str());
    }
  }

private:
  LineContext line_;
  std::shared_ptr<std::mutex> tick_mutex_;
  std::set<std::string> known_;
  rclcpp::CallbackGroup::SharedPtr callback_group_;
  rclcpp::Service<ResetService>::SharedPtr service_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__STATION_RESET_HPP_
