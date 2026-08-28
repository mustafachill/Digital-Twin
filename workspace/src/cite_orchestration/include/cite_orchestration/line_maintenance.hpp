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

// Everything the line does that is not a station acting.
//
// Expiring handoffs, confirming on a sink's behalf, counting what arrives, and
// publishing the line's state. It is here rather than inside `main` so that a
// test can drive the REAL one: a test that reimplemented "what happens when a
// handoff times out" would be asserting that two copies of the rule agree, which
// is the shape of test this project has already shipped once and does not want
// again.

#ifndef CITE_ORCHESTRATION__LINE_MAINTENANCE_HPP_
#define CITE_ORCHESTRATION__LINE_MAINTENANCE_HPP_

#include <deque>
#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/line_state.hpp>
#include <cite_interfaces/msg/station_state.hpp>
#include <cite_interfaces/qos.hpp>

#include "cite_orchestration/line_nodes.hpp"
#include "cite_orchestration/line_plan.hpp"

namespace cite_orchestration
{

using cite_interfaces::msg::LineState;

/// The stations that are waiting on a trigger nothing can produce. Empty when none is.
///
/// THE DEFECT THIS EXISTS FOR, OBSERVED RATHER THAN PREDICTED (ADR-0039). A
/// work-piece fails the friction grasp, the station retries, and its `Repeat`
/// returns it to `AwaitTrigger` on a beam THE PART IS ALREADY BREAKING — so no edge
/// can ever arrive, because `TriggerWatch::take` requires `previous_state != state`.
/// The inbound belt was stopped by that same edge and is started again only by
/// `ResumeBelt`, reachable only after `CompleteHandoff`, reachable only after the
/// trigger that will not come. Closed loop. And a line whose stations are all
/// waiting publishes `STATE_RUNNING`, so the line is permanently dead and reports
/// itself healthy. That is the third time this repository has shipped "the system
/// reported it was doing the thing and the thing was not happening"; ADR-0038 names
/// the other two.
///
/// IT IS `AwaitReArm`'s QUESTION, ASKED ON THE NOMINAL PATH. The rule is the same
/// `untriggerable_reason` (`line_nodes.hpp`), so the fault path and the running line
/// cannot answer differently, and neither of them names an asset (P1, P5).
///
/// A STATE PREDICATE AND NOT A TIMEOUT (P4). Nothing below is a duration, a tick
/// count or a deadline. A station WAITING for a part that is still coming is not
/// stalled; a station that CANNOT be triggered is. Those are different questions and
/// only the second is asked here.
///
/// THE THREE CONDITIONS BEYOND THE RULE, AND THE LAST ONE IS THE WHOLE OF THE
/// NEGATIVE DIRECTION:
///
///   * The station is IDLE or WAITING. Those are the two states the tree writes
///     while a station sits at its trigger — WAITING initially and after a retry
///     verdict, IDLE at the end of a completed cycle. A WORKING station is one that
///     will reach `ResumeBelt` and start its own belt again, and a BLOCKED or
///     FAULTED one belongs to `LineState`'s higher precedence, not here.
///   * Its inbound belt is at a commanded standstill, or was never commanded —
///     `untriggerable_reason` above.
///   * IT HAS ALREADY CONSUMED EVERY EDGE THAT STOPPED THAT BELT. Without this the
///     detector fires on every work-piece the line ever handles: the first two
///     conditions are both true for as long as it takes an arriving part's edge to
///     reach the station, and the belt learns of that edge through a DIFFERENT
///     subscription to the same topic, dispatched independently and under load
///     milliseconds apart. `ConveyorIndex::stop_edges` counts the edges that stopped
///     the belt and is incremented before the standstill is recorded, under the same
///     lock; `TriggerWatch::consumed` counts the edges handed to a station. While an
///     arrival is in flight the first exceeds the second and nothing is reported.
///     After a retry has returned the station to its trigger they are equal, the
///     belt is still stopped, and it is.
///
/// IT COMMANDS NOTHING. It reads a plan, a setpoint record and two counters. It does
/// not restart a belt, plan, touch a gripper, write a station state, release a claim
/// or move ownership — and the belt restart is exactly the fix this must not be read
/// as being one line away from. ADR-0038 decision 5 and ADR-0039 decision 5 both say
/// why: the retry's first physical act would be `Pick` OPENING THE GRIPPER at the
/// home pose (`skill_server.cpp:937-940`), dropping a part that nothing has attached
/// as an `AttachedCollisionObject`, so the planner does not know it is there.
/// Re-arming is a decision about what is where, and it is not decided yet.
inline std::vector<std::string> stalled_stations(
  const std::map<std::string, StationRuntime> & stations,
  const std::shared_ptr<ConveyorIndex> & conveyors,
  const std::shared_ptr<TriggerWatch> & triggers)
{
  std::vector<std::string> stalled;
  for (const auto & [id, runtime] : stations) {
    if (runtime.state != StationState::STATE_IDLE &&
      runtime.state != StationState::STATE_WAITING)
    {
      continue;
    }
    const auto reason = untriggerable_reason(id, runtime, conveyors);
    if (!reason) {
      continue;
    }
    if (triggers && conveyors &&
      triggers->consumed(runtime.trigger_topic) <
      conveyors->stop_edges(runtime.inbound_belt))
    {
      // An arrival is in flight: the edge that stopped this belt has not reached
      // the station yet. Not stalled, and this is the branch that keeps the signal
      // from being noise.
      continue;
    }
    stalled.push_back(*reason);
  }
  return stalled;
}

/// Everything the tick loop does that is not ticking the tree.
///
/// Run from the tick loop on purpose. As a timer callback it would race every
/// leaf for the registry and the ledger and need a lock around both; in the loop
/// it is simply the other half of one thread's work, and "only the tick thread
/// touches the line's state" stays a true sentence.
class LineMaintenance
{
public:
  LineMaintenance(LineContext line, const LinePlan & plan, const std::string & state_topic)
  : line_(std::move(line)), plan_(plan)
  {
    // The STATE profile: periodic, reliable, volatile. A late subscriber gets
    // the next publication rather than a stale one, which is right for something
    // republished several times a second.
    publisher_ = line_.node->create_publisher<LineState>(state_topic, cite::qos::state());
  }

  void run()
  {
    expire_handoffs();
    confirm_for_sinks();
    retire_at_sinks();
    line_.ledger->forget_terminal();
  }

  /// Publish the line's state. Separate from `run` so it can be paced without
  /// slowing the protocol down: the protocol runs every tick, the report does
  /// not need to.
  void publish()
  {
    LineState message;
    message.header.stamp = line_.now();
    message.asset_id = plan_.zone;
    message.workpieces_completed = static_cast<uint32_t>(line_.registry->completed());

    bool any_faulted = false;
    bool any_blocked = false;
    bool any_working = false;
    std::string reason;
    for (const auto & station : plan_.stations) {
      const StationRuntime & runtime = line_.station(station.id);
      StationState state;
      state.station_id = station.id;
      state.actor_asset_id = station.actor_asset_id;
      state.state = runtime.state;
      state.buffer_occupancy =
        static_cast<uint32_t>(line_.registry->occupancy(station.id));
      state.buffer_capacity = station.capacity;
      state.current_workpiece_id = runtime.current_workpiece_id;
      message.stations.push_back(state);

      any_faulted = any_faulted || runtime.state == StationState::STATE_FAULTED;
      any_blocked = any_blocked || runtime.state == StationState::STATE_BLOCKED;
      any_working = any_working || runtime.state == StationState::STATE_WORKING;
      if (reason.empty() && !runtime.blocked_reason.empty()) {
        reason = station.id + ": " + runtime.blocked_reason;
      }
    }

    if (any_faulted) {
      message.state = LineState::STATE_FAULTED;
      message.blocked_reason = reason;
    } else if (any_blocked) {
      message.state = LineState::STATE_BLOCKED;
      message.blocked_reason = reason;
    } else {
      // ASKED ONLY WHEN NOTHING IS FAULTED OR BLOCKED, and the order is ADR-0039
      // decision 2 rather than an efficiency. `STATE_BLOCKED` has exactly one
      // author — the station's own tree, by way of the state copied above
      // (ADR-0038 decision 4) — and a stall that could outrank it would be a
      // second author for it by another route.
      const auto stalled = stalled_stations(*line_.stations, line_.conveyors, line_.triggers);
      announce_the_stall(stalled);
      if (!stalled.empty()) {
        // ABOVE THE WORKING CASE, deliberately. A station that can never be
        // triggered again will never be triggered again whether or not a neighbour
        // is still finishing its current piece, and this line is serial, so that
        // neighbour finishing is the last thing that will happen on it. A line that
        // went on reporting RUNNING because one arm was still moving is exactly the
        // report this value exists to stop.
        message.state = LineState::STATE_STALLED;
        message.stall_reasons = stalled;
      } else if (any_working) {
        message.state = LineState::STATE_RUNNING;
      } else {
        // Every station idle is still a running line — it is a line with nothing
        // to do, and now a line that has been ASKED whether it could take any.
        // STOPPED would say the coordinator is not ticking, which is a different
        // and much more serious statement.
        message.state = LineState::STATE_RUNNING;
      }
    }

    const auto [cycle_time, throughput] = rates();
    message.cycle_time_s = cycle_time;
    message.throughput_per_hour = throughput;
    publisher_->publish(message);
  }

private:
  /// Say a stall out loud, once per distinct set of reasons.
  ///
  /// `LineState` is volatile and says of itself that it is a report of the present
  /// rather than a record, so once a run is over nothing on the wire says the line
  /// ever stalled. The log is what a person reads afterwards, and ADR-0038 already
  /// settled the shape for `AwaitReArm`: a refusal that names the station and the
  /// belt, and one that refuses SILENTLY is what would make the whole idea
  /// unacceptable.
  ///
  /// ON CHANGE, NEVER ON A TIMER, for `AwaitReset`'s reason. This runs several
  /// times a second; a line every publication would bury the stall under thousands
  /// of copies of it, and a line on a period would be a schedule in a method whose
  /// whole subject is not having one (P4).
  void announce_the_stall(const std::vector<std::string> & stalled)
  {
    std::string stated;
    for (const auto & refusal : stalled) {
      stated += (stated.empty() ? "" : "; ") + refusal;
    }
    if (stated == announced_) {
      return;
    }
    announced_ = stated;
    if (stated.empty()) {
      // A stall that cleared. It is said because the only thing that can clear one
      // today is a belt somebody started, and nothing in this repository does that
      // — so this line arriving is either the re-arm path being built or a hand on
      // the command topic, and both are worth a person seeing.
      RCLCPP_INFO(
        line_.node->get_logger(),
        "every station that could not be triggered can be again; the line is running");
      return;
    }
    RCLCPP_WARN(
      line_.node->get_logger(),
      "the line reports RUNNING no longer: %s. Nothing here restarts anything — "
      "re-arming is a decision about where the part is and is not wired (ADR-0038 "
      "decision 5, ADR-0039)",
      stated.c_str());
  }

  /// Rule 3, applied. A handoff past its deadline is retired and the work-piece
  /// stays with the station that already owned it — structurally, because nothing
  /// touched the registry.
  ///
  /// IT WRITES NO STATION STATE, and that is ADR-0038 decision 4 rather than an
  /// omission. `STATE_BLOCKED` has exactly one author now: the station's own tree.
  /// The expiry still reaches `LineState`, one tick later and through the station
  /// that owns the fact, by ONE OF TWO ROUTES depending on where in its cycle the
  /// station is when the deadline passes — and the routes have to be named
  /// together, because the window this closed spans the boundary between them:
  ///
  ///   * BEFORE the transfer, `AwaitHandoffConfirmed` (`line_station.xml:106`)
  ///     sees the terminal handoff.
  ///   * AFTER it — the `PlaceAt` at `:108`, which is the window the paragraph
  ///     below is about — the station is already past that leaf, and it is
  ///     `CompleteHandoff` at `:110` that finds the handoff gone.
  ///
  /// Either way it records `TIMEOUT` and fails into the recovery branch, so the
  /// state arrives with the code that caused it instead of with a sentence
  /// composed here.
  ///
  /// WHAT THAT CLOSED, because it was a live defect and not a tidy-up. The expiry
  /// window opens at `OfferHandoff` and closes at `CompleteHandoff`, and `PlaceAt`
  /// sits between them — so this pass could report a station BLOCKED while its arm
  /// was placing, for as long as a `PlaceAt` takes. `station_reset.hpp` tests only
  /// `state != STATE_BLOCKED`, so the operator reset would ACCEPT a reset for that
  /// station and clear `blocked_reason` mid-motion. After this, `STATE_BLOCKED`
  /// means one thing, which both that precondition and `AwaitReset` already assume.
  ///
  /// AND WHAT IT WOULD HAVE BROKEN. `AwaitReset` keys on the same state, so a
  /// handoff clock still running through a fault would expire during it and
  /// re-block a station the operator had already reset — holding the fault branch
  /// open with no reason anybody could see. `OnFault` abandons every live handoff
  /// for that reason; this pass no longer has a way to undo it.
  void expire_handoffs()
  {
    for (const auto & handoff : line_.ledger->expire(line_.now())) {
      RCLCPP_ERROR(
        line_.node->get_logger(),
        "handoff %s of %s from %s to %s timed out. %s keeps the work-piece; its own tree "
        "reports what that means for it.",
        handoff.token.c_str(), handoff.workpiece_id.c_str(),
        handoff.from_station_id.c_str(), handoff.to_station_id.c_str(),
        handoff.from_station_id.c_str());
    }
  }

  /// Confirm, on a sink's behalf.
  ///
  /// A sink has no actor. Something still has to be the second party, because
  /// rule 2 says both must confirm before physical transfer begins, and a
  /// handoff into a full accumulation buffer is exactly the case the rule exists
  /// for. So the coordinator's model of the sink confirms, against the sink's own
  /// declared capacity. Stated plainly rather than skipped quietly: there is no
  /// robot to ask, and pretending the confirmation happened somewhere else would
  /// be worse than saying it happens here.
  void confirm_for_sinks()
  {
    for (const auto & sink : plan_.sinks) {
      const auto offer = line_.ledger->offer_awaiting(sink.id);
      if (!offer) {
        continue;
      }
      if (line_.registry->occupancy(sink.id) >= sink.capacity) {
        continue;
      }
      line_.ledger->accept(offer->token, sink.id, line_.now());
    }
  }

  /// Count what has arrived, and free the belt it arrived on.
  ///
  /// A work-piece owned by a sink has left the line. It stops being tracked and
  /// starts being a number.
  ///
  /// COUNTED WHEN THE UPSTREAM ROBOT LETS GO, not when the part physically
  /// reaches the accumulation table — because the model gives the sink nothing to
  /// observe with. `beam_c3_out` exists in the bring-up plan and no station
  /// references it, so there is no arrival signal to count on. Reported as a gap
  /// rather than hidden: a sink with a trigger topic would make this exact.
  void retire_at_sinks()
  {
    for (const auto & sink : plan_.sinks) {
      for (const auto & id : line_.registry->owned_by(sink.id)) {
        if (!sink.inbound_buffer.empty()) {
          line_.arbiter->release(sink.inbound_buffer, id);
        }
        if (line_.registry->retire(id, sink.id) == RegistryOutcome::OK) {
          completions_.push_back(line_.now());
          while (completions_.size() > kRateWindow) {
            completions_.pop_front();
          }
          RCLCPP_INFO(
            line_.node->get_logger(), "%s reached %s; %zu completed", id.c_str(),
            sink.id.c_str(), line_.registry->completed());
        }
      }
    }
  }

  /// Mean cycle time and throughput over the last few completions.
  ///
  /// Over a WINDOW, not over all time: a line that was blocked for an hour and
  /// then ran well has an all-time mean that describes neither state. Reported as
  /// zero until there are two completions to measure between, rather than as a
  /// number derived from one.
  std::pair<double, double> rates() const
  {
    if (completions_.size() < 2) {
      return {0.0, 0.0};
    }
    const double span = (completions_.back() - completions_.front()).seconds();
    const auto intervals = static_cast<double>(completions_.size() - 1);
    if (span <= 0.0) {
      return {0.0, 0.0};
    }
    const double cycle_time = span / intervals;
    return {cycle_time, 3600.0 / cycle_time};
  }

  static constexpr std::size_t kRateWindow = 10;

  LineContext line_;
  LinePlan plan_;
  rclcpp::Publisher<LineState>::SharedPtr publisher_;
  std::deque<rclcpp::Time> completions_;
  //: The stall this pass has already said out loud, so it says each one once. It
  //: is also cleared by a line that stops stalling, so a stall that comes back is
  //: reported again rather than swallowed.
  std::string announced_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__LINE_MAINTENANCE_HPP_
