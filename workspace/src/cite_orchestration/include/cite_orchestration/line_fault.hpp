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

// The fault branch: what the line does after a station has escalated (ADR-0038).
//
// NONE OF THIS IS A PROTECTIVE MEASURE, and it must never be described as one.
// What stops an arm is the vendor controller's torque limiting and the cell's
// physical guarding (charter §3.2). This is a state machine. What it buys is that
// the coordinator is still there to be asked a question, and that it stops
// commanding belts it has stopped supervising — both coordination properties.
//
// WHAT ALREADY HAPPENED BY THE TIME THE FIRST LEAF HERE RUNS, because it is the
// part that is easiest to attribute to the wrong thing. Every station subtree
// that was RUNNING has already been halted, by the root `Parallel` reaching
// `failure_count="1"`: `ParallelNode` calls `resetChildren()` before it returns
// FAILURE, `ControlNode::resetChildren()` calls `haltNode()` on every RUNNING
// child, and that reaches `SkillNode::onHalted`, which cancels the outstanding
// action goal. So no arm is left moving under a goal nobody is holding — and that
// is a property of the `Parallel`, not of anything in this file and not of the
// process exiting. Nothing here touches the `Parallel`, which is how the property
// survives.
//
// THE ONE RULE THAT MAKES THE SHAPE WORK: NO LEAF HERE MAY EVER RETURN FAILURE.
// The fault branch is a `<Sequence>` and the second child of a `<Fallback>` whose
// first child has already failed. A FAILURE here fails the Sequence, fails the
// Fallback, ends the coordinator's tick loop, and reinstates the process exit
// ADR-0038 removes — taking the arm's pose, the part's position, the planning
// scene and the reset service with it, which is the evidence a person needs in
// order to say why the station stopped. A refusal is LOGGED, never returned.
//
// AND RETURNING IS NOT THE ONLY WAY OUT OF A LEAF. The rule above is necessary
// and it is not sufficient: an exception thrown out of a `tick()` here — and
// `StopAll` calls `publish()` once per belt, which can throw `RCLError` — walks
// past every status the rule is about. Out of `main` that is `std::terminate`,
// which is not the exit ADR-0038 removed but a signal death, and strictly worse
// than it: nothing is halted, no goal is cancelled, and the exit status says
// nothing about what happened. `line_orchestrator.cpp` catches around the tick so
// that the way out is an orderly halt and a status of 1 rather than an abort.
// SURVIVING an exception is a different question and ADR-0038 does not decide it.
//
// AND NO LEAF HERE MAY RETURN SUCCESS OUT OF THE LAST ONE, today. `AwaitReArm` is
// RUNNING for ever on purpose: without a `<Repeat>` over the root `Fallback`, a
// fault Sequence that returned SUCCESS would make the Fallback return SUCCESS,
// end the tick loop with `outcome == SUCCESS`, and exit the coordinator quietly
// with status 0. Both halves — the SUCCESS edge and the `Repeat` — land together
// when re-arming is decided, and they are deliberately not built here
// (ADR-0038 decision 5).
//
// NOTHING HERE TAKES A PORT. These four act on the whole line, through
// `LineContext`, which is already derived from L0 — so a fourth arm still changes
// `model/` and nothing else. A port would be a station name in a generated tree,
// and the station whose escalation stopped the line is not a name anything writes
// down: it is read off the runtime the tree has just finished writing.

#ifndef CITE_ORCHESTRATION__LINE_FAULT_HPP_
#define CITE_ORCHESTRATION__LINE_FAULT_HPP_

#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/msg/station_state.hpp>

#include "behaviortree_cpp/bt_factory.h"
#include "cite_orchestration/conveyor_index.hpp"
#include "cite_orchestration/line_nodes.hpp"

namespace cite_orchestration
{

/// The stations that are holding the line stopped, in a stable order.
///
/// BLOCKED and FAULTED, and nothing else. Those are the two states
/// `RecoverFromFailure` writes when it refuses a station a retry — every other
/// state is a station the line may run with. A free function rather than a branch
/// inside the leaf, for the reason `recovery_policy.hpp` and `station_reset.hpp`
/// give for themselves: the rule can then be proved without standing up a node.
///
/// It is the SAME predicate the ADR-0037 reset's precondition uses, deliberately.
/// `STATE_BLOCKED` has one author now — the station's own tree — so "blocked"
/// means one thing to the operator control that clears it and to the leaf that
/// waits for it to be cleared.
inline std::vector<std::string> stations_holding_the_line(
  const std::map<std::string, StationRuntime> & stations)
{
  std::vector<std::string> holding;
  for (const auto & [id, runtime] : stations) {
    if (runtime.state == StationState::STATE_BLOCKED ||
      runtime.state == StationState::STATE_FAULTED)
    {
      holding.push_back(id);
    }
  }
  return holding;
}

/// Why this line cannot be re-armed. Empty when nothing refuses.
///
/// THE RULE, DERIVED AND NOT HARD-CODED (ADR-0038 decision 3): for every station
/// that has a trigger topic and an inbound belt, if that belt's last commanded
/// setpoint is a standstill, the line cannot be re-armed — because the station
/// triggers on a beam BREAKING, and the only thing that can break its beam again
/// is a part the stopped belt is not bringing.
///
/// Both halves are already data. The trigger topic and the inbound belt come from
/// the topology by way of the plan; the setpoint is what `ConveyorIndex` last
/// decided. Nothing here names a station, a belt or a speed.
///
/// IT CLEARS ITSELF. The day someone builds a path that re-arms a station — a
/// belt restart that does not put a part on the floor, an operator jog that
/// clears the pick point, a re-observation that lets a station start from where
/// the part actually is — these refusals stop being produced on their own,
/// because the setpoint read here will not be a standstill. Nothing has to
/// remember to delete a rule.
///
/// A STATION FED BY A TABLE IS SKIPPED, and that is the rule working rather than
/// an exception to it: nothing carries work to it, so no belt can be the reason it
/// cannot be triggered. Today's model gives exactly one station that shape.
inline std::vector<std::string> rearm_refusals(
  const std::map<std::string, StationRuntime> & stations,
  const std::shared_ptr<ConveyorIndex> & conveyors)
{
  std::vector<std::string> refusals;
  for (const auto & [id, runtime] : stations) {
    if (runtime.trigger_topic.empty() || runtime.inbound_belt.empty()) {
      continue;
    }
    if (!conveyors) {
      refusals.push_back(
        "station '" + id + "' is fed by belt '" + runtime.inbound_belt +
        "' and this line has no conveyor drives at all, so nothing can start it");
      continue;
    }
    const auto setpoint = conveyors->commanded(runtime.inbound_belt);
    if (!setpoint) {
      // Never commanded is not the same fact as commanded to zero, and both are
      // refusals. Said apart because they are diagnosed apart: one is a belt
      // nobody has spoken to, the other is a belt somebody stopped.
      refusals.push_back(
        "station '" + id + "' waits on a break in beam '" + runtime.trigger_topic +
        "', and belt '" + runtime.inbound_belt +
        "' has never been commanded, so no part can arrive to break it");
      continue;
    }
    if (*setpoint == 0.0) {
      refusals.push_back(
        "station '" + id + "' waits on a break in beam '" + runtime.trigger_topic +
        "', and belt '" + runtime.inbound_belt +
        "' is commanded to a standstill, so no part can arrive to break it");
    }
  }
  return refusals;
}

/// Record the fault the line stopped on. Commands nothing.
///
/// A SYNC LEAF THAT ALWAYS SUCCEEDS. It is the first child of the fault Sequence
/// and it must never be the reason the branch ends — see this file's header.
///
/// IT LATCHES ON EVERY ROUTE INTO THIS BRANCH. Reaching it means the root
/// `Parallel` returned FAILURE; the latch records that, and the station and code
/// when a station owned it. Latching only the classified route would leave a root
/// failure nothing carries into the exit status, because the tick loop no longer
/// ends on one — which is the same "reports healthy, does nothing" shape this
/// branch exists to make impossible, reached through the exit code instead of
/// through `LineState`.
///
/// WHAT IT DOES NOT DO, and each absence is a decision:
///
///   * It writes no station state. The station that escalated is already BLOCKED
///     or FAULTED, written by its own tree; the halted siblings keep whatever
///     they held. `STATE_BLOCKED` has one author (ADR-0038 decision 4) and this
///     is not it.
///   * It does not route the reason through `SetStationState`, which clears
///     `blocked_reason` as a side effect of a state change. The reason is the
///     evidence; latching it by way of a leaf that destroys it is how the reset
///     service already lost one mid-motion.
///   * It releases no claim and moves no ownership. The escalating station is
///     still standing in the frames it reached into (ADR-0037 correction 3, as
///     amended), and telling the arbiter otherwise would be a statement about the
///     world that the failure has just contradicted.
///
/// WHAT IT DOES DO BESIDES RECORDING: it settles the ledger. Every live handoff is
/// abandoned, because a handoff clock left running through the fault expires
/// during it — and `LineMaintenance` would then report the upstream station
/// blocked again, AFTER the operator has reset it, holding `AwaitReset` open with
/// no reason anybody could see. Abandoning leaves the work-piece exactly where it
/// is, with whoever already owned it (ADR-0024 rule 3): nothing touches the
/// registry, so ownership is untouched by construction rather than by care.
class OnFault : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts() {return {};}

  BT::NodeStatus tick() override
  {
    const auto holding = stations_holding_the_line(*line_.stations);

    // LATCHED ON EVERY ROUTE INTO THIS BRANCH, INCLUDING THE UNCLASSIFIED ONE.
    // Reaching this leaf at all means the root `Parallel` returned FAILURE, and
    // that is the whole of what the latch records: the tick loop no longer ends on
    // it, so this is the only thing left that can carry a root failure into the
    // exit status. Latching only the classified route left one way for the line to
    // stop with `status` still 0 — `AwaitReset` succeeds immediately when nothing
    // is holding, `AwaitReArm` then runs for ever, and the coordinator sits there
    // reporting nothing wrong. That is the "reports healthy, does nothing" shape
    // this branch exists to make impossible, arriving through the exit code.
    //
    // IT IS REACHABLE, and by an ordinary path rather than a contrived one:
    // `RecoverFromFailure` on a retry verdict sets WAITING and returns SUCCESS, so
    // the recover `Sequence` runs on to `MoveToHome` (`line_station.xml`), and a
    // `MoveToHome` that fails there fails the Sequence, the Fallback, the Repeat
    // and the subtree — with no station BLOCKED and none FAULTED.
    if (line_.fault && !line_.fault->latched) {
      line_.fault->latched = true;
      line_.fault->at = line_.now();
      if (holding.empty()) {
        // No reason is INVENTED. What is recorded is the only fact there is: the
        // root failed and nothing classified it. The station id stays empty, which
        // is what tells a reader that no station owned this.
        line_.fault->station_id.clear();
        line_.fault->result_code = cite_interfaces::msg::ResultCode::SUCCESS;
        line_.fault->reason =
          "the root tree failed and no station was blocked or faulted, so nothing "
          "classified it";
      } else {
        // The FIRST one, and there can only be one: by the time this runs the
        // `Parallel` has halted every sibling, so no second station can escalate
        // behind it. The latch refuses a second write anyway, so what a run reports
        // is the fault it stopped on and not the last thing that happened to it.
        const std::string & station = holding.front();
        const StationRuntime & runtime = line_.station(station);
        line_.fault->station_id = station;
        line_.fault->result_code = runtime.blocked_code;
        line_.fault->reason = runtime.blocked_reason;
      }
    }

    if (holding.empty()) {
      // The `Parallel` failed and no station says why. Reported rather than
      // ignored: it means a station subtree returned FAILURE without going
      // through the recovery policy, which is a defect in that subtree and not
      // something this leaf can fix by inventing a reason.
      RCLCPP_ERROR(
        logger(),
        "the line stopped and no station is blocked or faulted. A station subtree "
        "returned FAILURE without its recovery policy classifying anything, so there is "
        "no reason to record — the fault is latched all the same, so the run still "
        "exits non-zero");
    } else {
      for (const auto & station : holding) {
        const StationRuntime & runtime = line_.station(station);
        RCLCPP_ERROR(
          logger(), "the line stopped at '%s' (result code %u): %s", station.c_str(),
          static_cast<unsigned>(runtime.blocked_code),
          runtime.blocked_reason.empty() ? "(no reason recorded)" :
          runtime.blocked_reason.c_str());
      }
    }

    for (const auto & handoff : line_.ledger->live_handoffs()) {
      // Abandoned by the station that offered it, which is the party that still
      // owns the piece. The downstream station stops holding a promise, and the
      // clock that would have expired during the fault is gone with it.
      line_.ledger->abandon(handoff.token, handoff.from_station_id);
      RCLCPP_WARN(
        logger(),
        "handoff %s of %s from %s to %s is called off because the line stopped. %s keeps "
        "the work-piece; nothing about where it is has changed",
        handoff.token.c_str(), handoff.workpiece_id.c_str(),
        handoff.from_station_id.c_str(), handoff.to_station_id.c_str(),
        handoff.from_station_id.c_str());
    }

    return BT::NodeStatus::SUCCESS;
  }
};

/// Put every declared belt down. The only thing the fault branch commands.
///
/// A SYNC LEAF THAT ALWAYS SUCCEEDS, for the same reason as `OnFault`, and it
/// commands NO ARM: every station's outstanding goal was cancelled by the
/// `Parallel` before this leaf was reached, so there is nothing left to stop and
/// sending anything would be new motion after an unclassified failure.
///
/// WHY THE BELTS NEED SAYING AT ALL, AND WHY IT IS A P2 MATTER. In simulation the
/// belts stop by accident today: the coordinator exits, the launch tears the cell
/// down, Gazebo dies, and there is no belt left to run. Nothing decided that. On a
/// physical line the belt is a VFD taking a speed setpoint, and A SETPOINT
/// PERSISTS — the coordinator exits, nothing publishes zero, and three belts keep
/// running with nobody supervising them. Identical command path, divergent
/// consequence. L4 owns the setpoint (ADR-0032), so L4 is the layer that has to
/// put it down, deliberately, in both.
///
/// OPEN LOOP, AND SAID SO. Nothing publishes `ConveyorState`; the bridge carries a
/// bare `std_msgs/Float64` each way. So this leaf states an intent and returns
/// SUCCESS with no evidence that any belt slowed, and a belt that ignores the zero
/// is a spilling line that L4 still does not notice. THE CONDITION UNDER WHICH
/// THAT CHANGES, named here so it is not re-derived: when something publishes
/// `ConveyorState` — a publisher in the simulation plugin and on the hardware
/// drive, which is L1/L2 work — this becomes a `BT::StatefulActionNode` that
/// returns RUNNING until every belt's MEASURED speed has reached zero, and SUCCESS
/// when it has. That is an event, not a duration: P4 is not satisfied by waiting a
/// plausible number of seconds for a belt to coast.
class StopAll : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts() {return {};}

  BT::NodeStatus tick() override
  {
    if (!line_.conveyors) {
      RCLCPP_INFO(
        logger(), "the line stopped and this zone declares no belt, so there is none to stop");
      return BT::NodeStatus::SUCCESS;
    }

    for (const auto & asset : line_.conveyors->assets()) {
      // EVERY DECLARED BELT, not only the indexed ones. A belt feeding a sink has
      // no station to stop it and is exactly the belt that would go on carrying
      // work past a line that is not taking any.
      const bool commanded = line_.conveyors->stop(asset);
      RCLCPP_WARN(
        logger(),
        "the line stopped: '%s' is commanded to a standstill. This is an intent and not "
        "an observation — nothing publishes ConveyorState, so no belt confirms it%s",
        asset.c_str(), commanded ? "" : ", and this one has no drive to command");
    }
    return BT::NodeStatus::SUCCESS;
  }
};

/// Hold the branch open until an operator has cleared every blocked station.
///
/// A STATE PREDICATE, EVALUATED ONCE PER TICK, exactly as `AwaitTrigger` reads its
/// queue: RUNNING while any station is BLOCKED or FAULTED, SUCCESS when none is.
/// There is no duration anywhere in it (P4).
///
/// AND NO DEADLINE, deliberately. Every other wait in this package is a FAILURE
/// deadline with a defined outcome, and this one has none because waiting for a
/// person must not have one — a deadline here would decide, on its own and while
/// nobody was looking, that the operator had taken too long, and the only thing it
/// could do about it is fail the branch, which reinstates the process exit that
/// destroys the evidence they were coming to read.
///
/// NEVER FAILURE. Not on an empty station map, not on a station id it does not
/// recognise. See this file's header for what a FAILURE here costs.
class AwaitReset : public BT::StatefulActionNode
{
public:
  AwaitReset(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts() {return {};}

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const auto holding = stations_holding_the_line(*line_.stations);
    if (holding.empty()) {
      RCLCPP_WARN(
        line_.node->get_logger(),
        "every station that was holding the line has been reset. That is an "
        "acknowledgement and not a restart: whether the line can run is the next leaf's "
        "question");
      return BT::NodeStatus::SUCCESS;
    }

    // ON CHANGE, NEVER ON A TIMER. A log line every tick would bury the reset that
    // matters under fifty thousand copies of the reason for it; a log line on a
    // period would be a schedule in a file whose whole subject is not having one.
    const std::string waiting_on = joined(holding);
    if (waiting_on != announced_) {
      announced_ = waiting_on;
      RCLCPP_WARN(
        line_.node->get_logger(),
        "the line is stopped and waiting for an operator to reset: %s. It is served by "
        "the ResetStation service and nothing here has a deadline",
        waiting_on.c_str());
    }
    return BT::NodeStatus::RUNNING;
  }

  void onHalted() override {announced_.clear();}

private:
  static std::string joined(const std::vector<std::string> & names)
  {
    std::string joined_names;
    for (const auto & name : names) {
      joined_names += (joined_names.empty() ? "" : ", ") + name;
    }
    return joined_names;
  }

  LineContext line_;
  //: The refusal this leaf has already said out loud, so it says each one once.
  std::string announced_;
};

/// Ask whether the line could run again, and refuse for a reason.
///
/// THIS IS THE HEART OF ADR-0038 AND THE LEAF A READER WILL WANT TO DELETE.
///
/// `AwaitReset` answers acknowledgement: a person looked, and used the ADR-0037
/// service. That says nothing about whether the line can run. This answers the
/// different question — IS THERE A STATION THAT COULD EVER BE TRIGGERED AGAIN? —
/// and today the answer is no, for a reason it derives rather than for one anybody
/// wrote down. Every recovery this line has returns a station to a state from
/// which nothing can trigger it: the part that failed is either still at the pick
/// point (and a station triggers on the beam BREAKING, so a part already there
/// produces no edge) or already off the belt (and a clearing edge is not this
/// station's trigger). Either way the belt that would bring the next part is
/// stopped, and the only leaf that runs it again is `ResumeBelt`, reachable only
/// after a `CompleteHandoff` that is reachable only after the trigger that will
/// not come.
///
/// WHY THAT MATTERS ENOUGH TO BE A LEAF. `LineMaintenance` publishes
/// `STATE_RUNNING` for a line whose stations are all WAITING, because a line with
/// nothing to do is a running line. So a change that stopped the process from
/// exiting, restored the nominal branch after a reset, and stopped there would
/// convert a process that exits 1 into a process that reports a healthy running
/// line, for ever. This repository has paid for that exact shape twice — v1's
/// handoff published to a topic nothing subscribed to, and the belt setpoint that
/// a test harness was quietly supplying — and both times the system reported it
/// was doing the thing while the thing was not happening. This leaf is what makes
/// the third instance say so.
///
/// IT COMMANDS NOTHING, EVER. It reads a plan and a setpoint record. It is a
/// condition wearing an action's clothes, because it has to hold the branch open.
///
/// IT NEVER RETURNS SUCCESS TODAY, and that absence is decision 5 rather than an
/// oversight — see this file's header for what a SUCCESS out of here would do
/// without the `<Repeat>` that is deliberately not built. Whoever wires resumption
/// adds the SUCCESS edge and the `Repeat` together, and touches nothing else.
class AwaitReArm : public BT::StatefulActionNode
{
public:
  AwaitReArm(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts() {return {};}

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const auto refusals = rearm_refusals(*line_.stations, line_.conveyors);
    std::string stated;
    for (const auto & refusal : refusals) {
      stated += (stated.empty() ? "" : "; ") + refusal;
    }
    if (stated.empty()) {
      // No station on this line is belt-fed, so the rule finds nothing to refuse
      // on. The branch is still held, because the resumption edge does not exist
      // — and saying which of the two it is matters: one is a line that could be
      // re-armed and has nothing to re-arm it, the other is a line whose belts
      // are stopped.
      stated =
        "no station on this line is both sensor-triggered and belt-fed, so there is no "
        "derived reason to refuse — and no path that re-arms a station exists either, so "
        "the line is held here regardless (ADR-0038 decision 5)";
    }

    // ON CHANGE, NEVER ON A TIMER, for `AwaitReset`'s reason. A leaf that can run
    // for ever must not log for ever.
    if (stated != announced_) {
      announced_ = stated;
      RCLCPP_WARN(
        line_.node->get_logger(),
        "the line is stopped and cannot be re-armed: %s. Resumption is not wired; the "
        "line stays here until this leaf is given a SUCCESS edge and the root Fallback a "
        "Repeat (ADR-0038 decision 5)",
        stated.c_str());
    }
    return BT::NodeStatus::RUNNING;
  }

  void onHalted() override {announced_.clear();}

private:
  LineContext line_;
  //: The refusal this leaf has already said out loud, so it says each one once.
  std::string announced_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__LINE_FAULT_HPP_
