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

// The leaves that make a line out of stations.
//
// `skill_nodes.hpp` holds the leaves that call L3. These hold the ones that do
// not: waiting for a sensor edge, taking custody of a work-piece, claiming a
// shared thing, negotiating a handoff, and deciding what to do about a failure.
// None of them commands a robot. All of them go through the single copies of the
// line's state that `LineContext` carries.
//
// WHY THESE ARE LEAVES AND NOT CODE IN THE NODE. L4's rule is that recovery and
// coordination are *expressed*, not implied. A handoff negotiated in C++ inside
// the coordinator is a handoff nobody can see; the same handoff as four leaves in
// a tree is one a person reads off the XML and Groot2 draws. It also means the
// protocol is exercised by ticking a tree, which is how ADR-0024's "testable in
// isolation" is actually achieved rather than asserted.
//
// THREADING, STATED ONCE. Every leaf here runs on the tick thread. The executor
// spinning the node runs on another thread and touches exactly one thing in this
// file — `TriggerWatch`, whose queue is behind a mutex because a subscription
// callback fills it. The registry, the ledger and the arbiter are touched only
// from the tick thread and from the coordinator's maintenance step, which the
// coordinator deliberately runs in its tick loop rather than in a timer callback
// so that "only the tick thread touches them" stays true and needs no lock.

#ifndef CITE_ORCHESTRATION__LINE_NODES_HPP_
#define CITE_ORCHESTRATION__LINE_NODES_HPP_

#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/msg/station_state.hpp>
#include <cite_interfaces/qos.hpp>

#include "behaviortree_cpp/bt_factory.h"
#include "cite_orchestration/handoff_ledger.hpp"
#include "cite_orchestration/recovery_policy.hpp"
#include "cite_orchestration/resource_arbiter.hpp"
#include "cite_orchestration/skill_nodes.hpp"
#include "cite_orchestration/workpiece_registry.hpp"

namespace cite_orchestration
{

using cite_interfaces::msg::DetectionEvent;
using cite_interfaces::msg::StationState;

/// Sensor edges, kept until a station takes them.
///
/// A QUEUE, not a latest-value. `DetectionEvent` is published on the EVENT
/// profile — reliable, keep-all — because "a missed transition is a work-piece
/// the line never notices, and the station downstream then waits forever". A
/// watch that only remembered the newest edge would throw that guarantee away on
/// the consumer side, which is the more common half of that mistake: the
/// publisher is careful and the subscriber overwrites.
class TriggerWatch
{
public:
  explicit TriggerWatch(rclcpp::Node::SharedPtr node)
  : node_(std::move(node))
  {
  }

  /// Start watching a topic. Idempotent — several stations may share a sensor.
  void watch(const std::string & topic)
  {
    if (topic.empty()) {
      return;
    }
    const std::lock_guard<std::mutex> lock(mutex_);
    if (subscriptions_.count(topic) != 0) {
      return;
    }
    // The EVENT profile, by name. A `rclcpp::QoS` literal outside
    // `cite_interfaces/qos.hpp` is a review finding, and an improvised profile
    // here would connect to the publisher silently and deliver nothing.
    subscriptions_[topic] = node_->create_subscription<DetectionEvent>(
      topic, cite::qos::event(),
      [this, topic](DetectionEvent::SharedPtr event) {
        const std::lock_guard<std::mutex> callback_lock(mutex_);
        auto & queue = pending_[topic];
        if (queue.size() >= kMaxPending) {
          // Bounded, and the drop is announced. An unbounded queue behind a
          // station that has stopped consuming is a slow leak that presents as
          // the coordinator being killed by the OOM killer hours later.
          RCLCPP_WARN(
            node_->get_logger(),
            "dropping the oldest sensor edge on %s: %zu are already unconsumed, which "
            "means a station is not taking its work",
            topic.c_str(), queue.size());
          queue.pop_front();
        }
        queue.push_back(*event);
      });
  }

  /// Take the oldest edge into `state` on `topic`, if there is one.
  ///
  /// An EDGE, not a level: `previous_state` must differ, which the message
  /// carries precisely "so a consumer can detect an edge without keeping its own
  /// history". A station triggered on a level would fire continuously for as long
  /// as a part sat in the beam.
  std::optional<DetectionEvent> take(const std::string & topic, uint8_t state)
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    const auto entry = pending_.find(topic);
    if (entry == pending_.end()) {
      return std::nullopt;
    }
    auto & queue = entry->second;
    while (!queue.empty()) {
      const DetectionEvent event = queue.front();
      queue.pop_front();
      if (event.state == state && event.previous_state != event.state) {
        return event;
      }
    }
    return std::nullopt;
  }

private:
  static constexpr std::size_t kMaxPending = 64;

  rclcpp::Node::SharedPtr node_;
  std::mutex mutex_;
  std::map<std::string, rclcpp::Subscription<DetectionEvent>::SharedPtr> subscriptions_;
  std::map<std::string, std::deque<DetectionEvent>> pending_;
};

/// What one station is doing, as the line reports it.
struct StationRuntime
{
  uint8_t state{StationState::STATE_IDLE};
  std::string current_workpiece_id;
  uint32_t capacity{1};
  //: Consecutive failed cycles. Reset by a cycle that completes. This is what
  //: the retry budget is spent from, and it is per station because a budget
  //: shared across the line would let one bad station exhaust another's.
  uint32_t consecutive_failures{0};
  std::string blocked_reason;
};

/// The single copies of everything L4 owns, handed to the leaves that need them.
///
/// One registry, one ledger, one arbiter, for the whole line. That is not a
/// convenience: ADR-0024's first rule is that ownership lives in exactly one
/// place, and a second copy of any of these would be a second answer to a
/// question that must have one.
struct LineContext
{
  rclcpp::Node::SharedPtr node;
  std::shared_ptr<WorkpieceRegistry> registry;
  std::shared_ptr<HandoffLedger> ledger;
  std::shared_ptr<ResourceArbiter> arbiter;
  std::shared_ptr<TriggerWatch> triggers;
  std::shared_ptr<std::map<std::string, StationRuntime>> stations;

  //: How long a handoff may sit unconfirmed or unfinished. A FAILURE deadline
  //: with a defined outcome (ADR-0024 rule 3), never a schedule.
  rclcpp::Duration handoff_timeout{rclcpp::Duration::from_seconds(120.0)};

  //: How many consecutive failures a station may retry through before the
  //: failure is escalated instead. Bounded so that "the line works while
  //: silently degrading" is not reachable.
  uint32_t retry_budget{2};

  rclcpp::Time now() const {return node->get_clock()->now();}

  StationRuntime & station(const std::string & id) {return (*stations)[id];}
};

/// Base for a leaf that needs the line's state but commands nothing.
class LineNode : public BT::SyncActionNode
{
public:
  LineNode(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::SyncActionNode(name, config), line_(std::move(line))
  {
  }

protected:
  std::string station_id() const {return getInput<std::string>("station").value_or("");}
  rclcpp::Logger logger() const {return line_.node->get_logger();}

  LineContext line_;
};

/// Wait for the sensor that tells this station a work-piece has arrived.
///
/// A station with no trigger topic is "sequenced by its upstream station
/// instead", in the message's own words, so it does not wait here at all. Which
/// of the two a station is comes from the topology and appears in no branch
/// anybody wrote: the port is either empty or it is not.
class AwaitTrigger : public BT::StatefulActionNode
{
public:
  AwaitTrigger(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<std::string>("topic", "the DetectionEvent topic, from the topology"),
      BT::InputPort<int>("state", "the DetectionEvent state that fires this station"),
      BT::OutputPort<std::string>(
        "sensed_workpiece", "what the sensor called it; empty when it cannot tell"),
    };
  }

  BT::NodeStatus onStart() override
  {
    topic_ = getInput<std::string>("topic").value_or("");
    state_ = static_cast<uint8_t>(getInput<int>("state").value_or(0));
    if (topic_.empty()) {
      setOutput("sensed_workpiece", std::string{});
      return BT::NodeStatus::SUCCESS;
    }
    line_.triggers->watch(topic_);
    return onRunning();
  }

  BT::NodeStatus onRunning() override
  {
    const auto event = line_.triggers->take(topic_, state_);
    if (!event) {
      // RUNNING, for as long as it takes. Waiting for work is not a failure and
      // must not be given a deadline: a deadline here would put every station
      // into recovery the moment the line ran out of parts.
      return BT::NodeStatus::RUNNING;
    }
    setOutput("sensed_workpiece", event->workpiece_id);
    return BT::NodeStatus::SUCCESS;
  }

  void onHalted() override {}

private:
  LineContext line_;
  std::string topic_;
  uint8_t state_{0};
};

/// Say yes to a handoff offered to this station. The second of ADR-0024's two
/// parties.
///
/// Never succeeds — it runs alongside the wait for work, under a Parallel, and
/// is halted when the wait ends. That shape is deliberate: a station confirms
/// while it is IDLE, because confirming is a promise about room rather than
/// about attention, and a station that could only confirm while it was free to
/// act would stall the whole line behind its own cycle.
class AcceptOffers : public BT::StatefulActionNode
{
public:
  AcceptOffers(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {BT::InputPort<std::string>("station")};
  }

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const std::string station = getInput<std::string>("station").value_or("");
    if (station.empty()) {
      return BT::NodeStatus::FAILURE;
    }
    const auto offer = line_.ledger->offer_awaiting(station);
    if (offer) {
      const auto & runtime = line_.station(station);
      // Room is the whole content of the confirmation. Saying yes without it is
      // how a station ends up owning two work-pieces and dropping one.
      if (line_.registry->occupancy(station) < runtime.capacity) {
        const HandoffReply reply =
          line_.ledger->accept(offer->token, station, line_.now());
        RCLCPP_INFO(
          line_.node->get_logger(), "%s accepted handoff %s for %s: %s", station.c_str(),
          offer->token.c_str(), offer->workpiece_id.c_str(), describe(reply));
      }
    }
    return BT::NodeStatus::RUNNING;
  }

  void onHalted() override {}

private:
  LineContext line_;
};

/// Establish which work-piece this station is now accountable for.
///
/// Three cases, and the third is a refusal:
///
///  * The station already owns exactly one piece — it was handed one, and the
///    sensor has just told it that piece has arrived. That is the piece.
///  * The station owns none and work enters the line here. The piece is admitted
///    under a minted identity and this station becomes its first owner.
///  * The station owns none and work does not enter here. Something is at this
///    station that nobody handed it, which is a tracking failure and is reported
///    as one rather than adopted.
///
/// WHY THE DETECTOR'S OWN ID IS NOT USED AS THE LINE'S. `Detection.workpiece_id`
/// is whatever the detector calls the object, and in Phase 1 that comes from the
/// simulator's own knowledge — it is not an identity the line issued and there is
/// nothing to reconcile the two against. So the line keeps its own, and a
/// capacity-1 station that was triggered for a piece it owns identifies what it
/// sees as that piece. Reconciling a detector's identities with the line's needs
/// somewhere durable to reconcile against, which is L6 and does not exist yet.
/// Stated here so that the day it does, this is the code that changes.
class TakeCustody : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<bool>(
        "admits_work", false, "true when work enters the line at this station"),
      BT::OutputPort<std::string>("workpiece"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string station = station_id();
    if (station.empty()) {
      return BT::NodeStatus::FAILURE;
    }

    const auto owned = line_.registry->owned_by(station);
    if (owned.size() == 1) {
      setOutput("workpiece", owned.front());
      line_.station(station).current_workpiece_id = owned.front();
      return BT::NodeStatus::SUCCESS;
    }
    if (owned.size() > 1) {
      RCLCPP_ERROR(
        logger(),
        "%s owns %zu work-pieces and is capacity-1; the line has lost track of which one "
        "it is handling",
        station.c_str(), owned.size());
      return BT::NodeStatus::FAILURE;
    }

    if (!getInput<bool>("admits_work").value_or(false)) {
      RCLCPP_ERROR(
        logger(),
        "a work-piece is at %s but the line does not own one there, and work does not "
        "enter the line at this station. Nothing handed it this piece.",
        station.c_str());
      return BT::NodeStatus::FAILURE;
    }

    const std::string minted = line_.registry->mint_id();
    const RegistryOutcome admitted = line_.registry->admit(minted, station, station);
    if (admitted != RegistryOutcome::OK) {
      RCLCPP_ERROR(
        logger(), "could not admit %s at %s: %s", minted.c_str(), station.c_str(),
        describe(admitted));
      return BT::NodeStatus::FAILURE;
    }
    RCLCPP_INFO(logger(), "%s admitted %s into the line", station.c_str(), minted.c_str());
    setOutput("workpiece", minted);
    line_.station(station).current_workpiece_id = minted;
    return BT::NodeStatus::SUCCESS;
  }
};

/// Claim the places this station reaches into, before it reaches into them.
///
/// Both at once and in a canonical order — see `ResourceArbiter::request_all`.
/// Claiming them one at a time is the textbook circular wait, and a line that
/// deadlocks recovers by being restarted.
class ClaimReach : public BT::StatefulActionNode
{
public:
  ClaimReach(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<std::string>("pick_frame"),
      BT::InputPort<std::string>("place_frame"),
    };
  }

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const std::string station = getInput<std::string>("station").value_or("");
    std::vector<std::string> frames;
    for (const char * port : {"pick_frame", "place_frame"}) {
      const auto frame = getInput<std::string>(port);
      if (frame && !frame->empty()) {
        frames.push_back(frame.value());
      }
    }
    if (station.empty() || frames.empty()) {
      return BT::NodeStatus::FAILURE;
    }

    const Grant grant = line_.arbiter->request_all(frames, station);
    if (grant == Grant::UNDECLARED) {
      RCLCPP_ERROR(
        line_.node->get_logger(),
        "%s asked for a frame no resource was declared for; resources come from the "
        "topology and this station's do not appear in it",
        station.c_str());
      return BT::NodeStatus::FAILURE;
    }
    // QUEUED is not a failure and must never be one: it is another station
    // holding the frame, which is the arbitration working.
    return grant == Grant::GRANTED ? BT::NodeStatus::SUCCESS : BT::NodeStatus::RUNNING;
  }

  void onHalted() override
  {
    // Leave the queue on the way out. A claimant that is halted mid-wait and
    // stays queued is granted a frame it is no longer using, and the next
    // station in line waits behind a ghost.
    const std::string station = getInput<std::string>("station").value_or("");
    if (!station.empty()) {
      line_.arbiter->release_all(station);
    }
  }

private:
  LineContext line_;
};

/// Claim a slot on the link this station is about to put a work-piece onto.
///
/// The claimant is the WORK-PIECE, not the station: a piece occupies a slot from
/// the moment it goes onto the belt to the moment it comes off, which may be long
/// after the station that put it there has moved on. The number of claimants is
/// therefore the number of pieces the link is carrying, and the capacity is the
/// model's own `buffer_capacity`.
class ClaimBufferSlot : public BT::StatefulActionNode
{
public:
  ClaimBufferSlot(const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("buffer"),
      BT::InputPort<std::string>("workpiece"),
    };
  }

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const std::string buffer = getInput<std::string>("buffer").value_or("");
    const std::string workpiece = getInput<std::string>("workpiece").value_or("");
    if (buffer.empty() || workpiece.empty()) {
      return BT::NodeStatus::FAILURE;
    }
    const Grant grant = line_.arbiter->request(buffer, workpiece);
    if (grant == Grant::UNDECLARED) {
      RCLCPP_ERROR(
        line_.node->get_logger(), "no buffer '%s' was declared by the topology",
        buffer.c_str());
      return BT::NodeStatus::FAILURE;
    }
    return grant == Grant::GRANTED ? BT::NodeStatus::SUCCESS : BT::NodeStatus::RUNNING;
  }

  void onHalted() override {}

private:
  LineContext line_;
};

/// Give up one claim. `claimant` is a station for a frame and a work-piece for a
/// buffer, which is why it is a port rather than assumed.
class ReleaseClaim : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("resource"),
      BT::InputPort<std::string>("claimant"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string resource = getInput<std::string>("resource").value_or("");
    const std::string claimant = getInput<std::string>("claimant").value_or("");
    if (!resource.empty() && !claimant.empty()) {
      line_.arbiter->release(resource, claimant);
    }
    // SUCCESS even for a claim that was never held: a recovery branch releases
    // everything the station might have taken without knowing how far the failed
    // attempt got, and making that an error would fail the recovery.
    return BT::NodeStatus::SUCCESS;
  }
};

/// Give up everything this station holds. The recovery branch's first act.
class ReleaseStationClaims : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts() {return {BT::InputPort<std::string>("station")};}

  BT::NodeStatus tick() override
  {
    const std::string station = station_id();
    if (!station.empty()) {
      line_.arbiter->release_all(station);
    }
    return BT::NodeStatus::SUCCESS;
  }
};

/// Offer the work-piece to the downstream station. The first of the two parties.
class OfferHandoff : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<std::string>("downstream"),
      BT::InputPort<std::string>("workpiece"),
      BT::OutputPort<std::string>("token"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string station = station_id();
    const std::string downstream = getInput<std::string>("downstream").value_or("");
    const std::string workpiece = getInput<std::string>("workpiece").value_or("");
    const std::string token = line_.ledger->offer(
      *line_.registry, workpiece, station, downstream, line_.now(), line_.handoff_timeout);
    if (token.empty()) {
      RCLCPP_ERROR(
        logger(),
        "%s could not offer %s to %s. An offer is refused when the offering station does "
        "not own the piece or when that piece already has a live handoff — either way the "
        "line's record and this station disagree.",
        station.c_str(), workpiece.c_str(), downstream.c_str());
      return BT::NodeStatus::FAILURE;
    }
    setOutput("token", token);
    RCLCPP_INFO(
      logger(), "%s offered %s to %s as %s", station.c_str(), workpiece.c_str(),
      downstream.c_str(), token.c_str());
    return BT::NodeStatus::SUCCESS;
  }
};

/// Wait until both parties have confirmed. The gate rule 2 names.
///
/// Nothing physical happens before this returns SUCCESS. That is the whole
/// content of "both parties must confirm before physical transfer begins": it is
/// a gate in the tree, in front of the motion, rather than a comment.
class AwaitHandoffConfirmed : public BT::StatefulActionNode
{
public:
  AwaitHandoffConfirmed(
    const std::string & name, const BT::NodeConfig & config, LineContext line)
  : BT::StatefulActionNode(name, config), line_(std::move(line))
  {
  }

  static BT::PortsList providedPorts() {return {BT::InputPort<std::string>("token")};}

  BT::NodeStatus onStart() override {return onRunning();}

  BT::NodeStatus onRunning() override
  {
    const std::string token = getInput<std::string>("token").value_or("");
    if (token.empty()) {
      return BT::NodeStatus::FAILURE;
    }
    const auto handoff = line_.ledger->find(token);
    if (!handoff) {
      return BT::NodeStatus::FAILURE;
    }
    if (handoff->phase == HandoffPhase::CONFIRMED) {
      return BT::NodeStatus::SUCCESS;
    }
    if (HandoffLedger::is_terminal(handoff->phase)) {
      // The defined outcome. A handoff that timed out leaves the work-piece with
      // the station that already had it — structurally, because nothing touched
      // the registry — and this station reports itself blocked through its own
      // recovery branch.
      RCLCPP_WARN(
        line_.node->get_logger(), "handoff %s ended before it was confirmed: %s",
        token.c_str(), describe(handoff->phase));
      config().blackboard->set(
        kLastResultCode, static_cast<int>(cite_interfaces::msg::ResultCode::TIMEOUT));
      return BT::NodeStatus::FAILURE;
    }
    return BT::NodeStatus::RUNNING;
  }

  void onHalted() override {}

private:
  LineContext line_;
};

/// The upstream robot has let go. Ownership moves, here and nowhere else.
class CompleteHandoff : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<std::string>("token"),
      BT::InputPort<std::string>(
        "location", "where the piece now physically is: the carrying asset, or the "
        "receiving station when nothing carries it"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string token = getInput<std::string>("token").value_or("");
    const std::string location = getInput<std::string>("location").value_or("");
    const HandoffReply reply = line_.ledger->complete(
      *line_.registry, token, location,
      // On a belt between two stations, in the phase that says so. The receiving
      // station owns it from this instant even though it has not touched it,
      // which is the point of the rule: something is always accountable.
      WorkpiecePhase::IN_TRANSIT, line_.now());
    if (reply != HandoffReply::OK) {
      RCLCPP_ERROR(
        logger(), "could not complete handoff %s: %s", token.c_str(), describe(reply));
      config().blackboard->set(
        kLastResultCode, static_cast<int>(cite_interfaces::msg::ResultCode::TIMEOUT));
      return BT::NodeStatus::FAILURE;
    }
    const std::string station = station_id();
    line_.station(station).current_workpiece_id.clear();
    line_.station(station).consecutive_failures = 0;
    return BT::NodeStatus::SUCCESS;
  }
};

/// Say what this station is doing, so the line can report it.
class SetStationState : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<int>("state", "a StationState.STATE_* value"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string station = station_id();
    if (station.empty()) {
      return BT::NodeStatus::FAILURE;
    }
    auto & runtime = line_.station(station);
    runtime.state = static_cast<uint8_t>(getInput<int>("state").value_or(StationState::STATE_IDLE));
    if (runtime.state != StationState::STATE_BLOCKED &&
      runtime.state != StationState::STATE_FAULTED)
    {
      runtime.blocked_reason.clear();
    }
    return BT::NodeStatus::SUCCESS;
  }
};

/// Decide what to do about the failure that just happened.
///
/// The station's recovery branch ends here. It reads the CODE the failed skill
/// returned — never the text — and asks `recovery_policy.hpp`, which is where
/// the policy is written down and tested. SUCCESS means the station may try
/// again, and the enclosing Repeat does exactly that. FAILURE means it may not,
/// and the failure propagates to the line tree, whose Parallel halts the other
/// stations — cancelling whatever goal each was running, because a line that
/// stops must not leave an arm moving.
class RecoverFromFailure : public LineNode
{
public:
  using LineNode::LineNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("station"),
      BT::InputPort<std::string>("workpiece"),
      BT::InputPort<std::string>("token"),
    };
  }

  BT::NodeStatus tick() override
  {
    const std::string station = station_id();
    auto & runtime = line_.station(station);
    ++runtime.consecutive_failures;

    // A handoff this station offered and did not finish is called off, so the
    // downstream station is not left holding a promise. The work-piece stays
    // where it is, with whoever already owned it.
    const std::string token = getInput<std::string>("token").value_or("");
    if (!token.empty()) {
      line_.ledger->abandon(token, station);
    }

    // Read defensively. A recovery branch can be reached by a leaf that failed
    // before it ever sent a goal — a missing action name, an empty frame — and
    // that leaf recorded no code. Treating "no code" as SUCCESS would make the
    // policy answer NONE and the station retry for ever; PRECONDITION_FAILED is
    // what it actually is, and it is bounded by the budget like anything else.
    int code = static_cast<int>(cite_interfaces::msg::ResultCode::PRECONDITION_FAILED);
    if (!config().blackboard->get<int>(kLastResultCode, code)) {
      code = static_cast<int>(cite_interfaces::msg::ResultCode::PRECONDITION_FAILED);
    }
    const Recovery response = recovery_for(
      static_cast<uint8_t>(code), runtime.consecutive_failures - 1, line_.retry_budget);

    runtime.blocked_reason = std::string("result code ") + std::to_string(code) + ": " +
      describe(response);

    switch (response) {
      case Recovery::NONE:
      case Recovery::RETRY_SAME:
      case Recovery::RETRY_DIFFERENTLY:
        // The next cycle re-observes before it acts — the station's tree always
        // detects before it picks — so RETRY_SAME and RETRY_DIFFERENTLY reach
        // the same place here. They are kept distinct in the policy because they
        // will not once a station gains a second way to approach a part, and
        // collapsing them there would lose the distinction permanently.
        runtime.state = StationState::STATE_WAITING;
        RCLCPP_WARN(
          logger(), "%s: %s (failure %u of %u allowed)", station.c_str(), describe(response),
          runtime.consecutive_failures, line_.retry_budget + 1);
        return BT::NodeStatus::SUCCESS;

      case Recovery::ESCALATE:
        runtime.state = StationState::STATE_BLOCKED;
        RCLCPP_ERROR(
          logger(), "%s is blocked and needs an operator: %s", station.c_str(),
          runtime.blocked_reason.c_str());
        return BT::NodeStatus::FAILURE;

      case Recovery::STOP_LINE:
        runtime.state = StationState::STATE_FAULTED;
        RCLCPP_FATAL(
          logger(), "%s: %s", station.c_str(), runtime.blocked_reason.c_str());
        return BT::NodeStatus::FAILURE;
    }
    return BT::NodeStatus::FAILURE;
  }
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__LINE_NODES_HPP_
