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

// The belt setpoint, and its owner (ADR-0032).
//
// A station cannot pick from a running belt, and the beam that starts it leaves
// no margin at all. It stands 0.027 m DOWNSTREAM of the point the station picks
// from — half a part length plus half a beam width, derived by
// `cite_tools.model.resolve.index_offset_m` from the work-piece's own geometry
// rather than authored (ADR-0033) — so a part breaks it exactly when the part's
// centre reaches the pick point. The instant of the edge is the instant the part
// is where it is wanted; there is no travel time to spend, and every further
// metre of belt is displacement. At the declared 0.150 m/s the part clears its
// own 0.050 m length in 0.333 s, against a pick-and-place cycle of 106 to 119 s.
// So the belt is INDEXED: it stops when the station it feeds is triggered, and
// runs again when that station reports `CompleteHandoff`.
//
// WHICH BELT IS NEVER NAMED HERE. A belt is the `via_asset_id` of the inbound
// edge of a station that has a robot actor — the same derivation `line_plan.hpp`
// already does for the outbound edge. Its command topic and its speed arrive as
// parameters resolved from L0 (`cell_a_plan.yaml` carries `command_topic` and
// `installed_speed_mps` per conveyor). There is no conveyor name and no speed in
// this file, and `installed_speed_mps` is not copied into a second place: what
// `run()` publishes is what the model declared (P1, P5).
//
// WHY THE STOP IS HERE AND NOT A LEAF IN THE STATION SUBTREE. ADR-0032 says both
// ends are events, and names them separately: "a `DetectionEvent` transition in,
// an ADR-0024 protocol leaf out". That asymmetry is load-bearing rather than
// stylistic.
//
// A leaf can only act when its station's cycle reaches it, and a station's cycle
// reaches the top of its loop once every 106 to 119 s. A work-piece that arrives
// at the beam while the station is still placing the PREVIOUS piece would not be
// stopped until the station came back round — by which time it has travelled the
// length of the belt and off the end, which is the exact failure this decision
// exists to remove. The edge that stops the belt therefore has to be observed
// where every edge is observed, not where the station happens to be standing.
// `buffer_capacity` is 4 on both belt-mediated edges in `model/topology/flow.yaml`,
// so a second piece on a belt is something the model permits and not a
// hypothetical.
//
// The RESTART has no such problem: it is a statement about one station's own
// cycle, made at the one point in that cycle where the statement is true, so it
// is a leaf (`ResumeBelt` in `line_nodes.hpp`) and is read off the XML.
//
// OPEN LOOP, AND SAID SO. Nothing here waits for a belt to confirm it stopped.
// `ConveyorState` exists in `cite_interfaces` to make commanded and measured
// speed disagree visibly and is published by nothing at this commit — the bridge
// carries a bare `std_msgs/Float64` each way, which is a scalar setpoint and not
// structured data in a `std_msgs` wrapper. So a belt that fails to stop, or fails
// to restart, is a stalled or a spilling line and nothing here would notice.
// ADR-0032 records that cost. Closing it needs a publisher of `ConveyorState` in
// the simulation plugin and on the hardware drive, which is L1/L2 work; when it
// exists, `stop()` and `run()` are what grow a confirmation.
//
// NOTHING BRANCHES ON BEING IN SIMULATION (P2). A VFD-driven belt starts and
// stops on the same two events and the same setpoint; only the far side of the
// command topic differs.
//
// THREADING. The tables are filled during set-up, before the tree is created,
// and read afterwards from two places: the executor's threads, in the sensor
// callback, and the tick thread, in `ResumeBelt`. A mutex guards them for the
// same reason `TriggerWatch`'s queue has one. Nothing blocks inside the callback:
// it publishes a setpoint and returns.

#ifndef CITE_ORCHESTRATION__CONVEYOR_INDEX_HPP_
#define CITE_ORCHESTRATION__CONVEYOR_INDEX_HPP_

#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/float64.hpp>

#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/qos.hpp>

namespace cite_orchestration
{

/// One belt's drive, exactly as the model records it.
///
/// Both values come from `cell_a_plan.yaml`, which resolves them from
/// `model/assets/instances/conveyors.yaml`. `installed_speed_mps` is the drive's
/// installed setting — a physical fact about the machine — and the model says in
/// as many words that the runtime setpoint is L4's decision. This is L4 making
/// it, out of the declared value rather than out of a number of its own.
struct ConveyorDrive
{
  std::string command_topic;
  double installed_speed_mps{0.0};
};

using ConveyorDrivesByAsset = std::map<std::string, ConveyorDrive>;

/// Owns what every belt in the zone is commanded to do.
class ConveyorIndex
{
public:
  ConveyorIndex(rclcpp::Node::SharedPtr node, ConveyorDrivesByAsset drives)
  : node_(std::move(node)), drives_(std::move(drives))
  {
    for (const auto & [asset, drive] : drives_) {
      // THE SETPOINT IS RE-SENT TO A SUBSCRIBER THAT ARRIVES AFTER IT, and
      // without that this class commands nothing at start-up.
      //
      // Reliable delivery is a promise to subscribers this publisher has been
      // MATCHED with, and matching is a discovery event. These publishers are
      // created in the topology callback and `run_all()` publishes from the same
      // callback a tree-construction later, so at that instant the count of
      // matched subscribers is zero and the message is delivered to nobody —
      // however long the bridge has been up, and however reliable the profile.
      // Measured: with the continuous-line scenario's own publisher removed, a
      // subscriber that had been up for a hundred seconds received nothing for
      // the following three hundred. The scenario used to publish the same
      // setpoint ten times over a second, and that is what actually started the
      // belts; ADR-0032's `run_all()` never has.
      //
      // So the arrival of a subscriber is treated as what it is — an event — and
      // the belt's CURRENT commanded setpoint is sent to it. Not a retry and not
      // a delay (P4): nothing here waits for a duration, and the value sent is
      // whatever this class last decided, so a bridge that restarts mid-run
      // learns the state of the belt rather than the state it started in.
      rclcpp::PublisherOptions options;
      options.event_callbacks.matched_callback =
        [this, asset](rclcpp::MatchedInfo & info) {on_subscriber_matched(asset, info);};

      // The COMMAND profile by name — reliable, so a setpoint reaches a
      // subscriber that is already connected. A `rclcpp::QoS` literal outside
      // `cite_interfaces/qos.hpp` is a review finding, and an improvised profile
      // here would connect to the bridge silently and deliver nothing.
      publishers_[asset] = node_->create_publisher<std_msgs::msg::Float64>(
        drive.command_topic, cite::qos::command(), options);
    }
  }

  /// Is this belt one the model declared a drive for?
  bool declares(const std::string & asset) const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return drives_.count(asset) != 0;
  }

  /// Does this belt stop on a station's trigger, or run continuously?
  ///
  /// `station_accumulation` is a sink: it has a trigger and no actor, so it has
  /// no `CompleteHandoff` to run its belt again on. Its belt is declared here and
  /// is never indexed, which is why the rule is keyed on the actor and not on the
  /// trigger — a rule that keyed on the trigger alone would stop that belt for
  /// ever.
  bool indexes(const std::string & asset) const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return indexed_.count(asset) != 0;
  }

  /// Stop `asset` whenever `topic` reports a transition into `state`.
  ///
  /// Idempotent per belt, and several belts may watch one topic. Called during
  /// set-up, before the tree exists.
  void index_on(const std::string & topic, uint8_t state, const std::string & asset)
  {
    if (topic.empty() || asset.empty()) {
      return;
    }
    const std::lock_guard<std::mutex> lock(mutex_);
    if (drives_.count(asset) == 0 || indexed_.count(asset) != 0) {
      return;
    }
    indexed_.insert(asset);
    watched_[topic].emplace_back(state, asset);
    if (subscriptions_.count(topic) != 0) {
      return;
    }
    // The EVENT profile, as `TriggerWatch` uses for the same stream. This is a
    // SECOND subscriber to that topic and deliberately so: `TriggerWatch` CONSUMES
    // an edge into the station whose turn it is, and a belt has to stop on every
    // edge whether or not a station is ready to take one. Two subscriptions each
    // receive every message; they do not divide them.
    subscriptions_[topic] = node_->create_subscription<cite_interfaces::msg::DetectionEvent>(
      topic, cite::qos::event(),
      [this, topic](cite_interfaces::msg::DetectionEvent::SharedPtr event) {
        on_edge(topic, *event);
      });
  }

  /// Command every declared belt to its installed speed.
  ///
  /// This is what gives the setpoint an owner. Before ADR-0032 nothing in the
  /// running system commanded a conveyor and `tests/scenarios/continuous_line.py`
  /// supplied one, reporting itself as a gap rather than a boundary. That
  /// scenario now reads the command topics instead of writing them and asserts a
  /// non-zero setpoint on every belt, so this call is the only writer and its
  /// absence is a scenario failure rather than an invisible one.
  void run_all()
  {
    for (const auto & asset : assets()) {
      run(asset);
    }
  }

  /// Command one belt to the speed its drive is installed at. False when
  /// the model declared no such belt.
  bool run(const std::string & asset)
  {
    double speed = 0.0;
    {
      const std::lock_guard<std::mutex> lock(mutex_);
      const auto drive = drives_.find(asset);
      if (drive == drives_.end()) {
        return false;
      }
      speed = drive->second.installed_speed_mps;
    }
    return command(asset, speed);
  }

  /// Command one belt to a standstill. False when the model declared no such belt.
  bool stop(const std::string & asset) {return declares(asset) ? command(asset, 0.0) : false;}

  /// What this belt was last commanded to, or nothing when it never has been.
  ///
  /// THE DISTINCTION IS THE POINT, and it is why this returns an optional rather
  /// than a double. "Not commanded yet" and "commanded to a standstill" are
  /// different facts about the plant and only one of them is a decision — the
  /// member's own comment says so, and a reader that flattened them would read a
  /// belt nobody has spoken to as a belt somebody stopped.
  ///
  /// A READER, NOT A MEASUREMENT. This is what L4 last DECIDED, which is the only
  /// thing this class knows: nothing publishes `ConveyorState`, so no belt on this
  /// line has ever confirmed anything. A caller that treats the answer as the
  /// belt's speed is making the mistake this whole file says it cannot make.
  ///
  /// Added for `AwaitReArm` (ADR-0038 decision 3), which asks whether a station
  /// could ever be triggered again and answers it from the setpoint of the belt
  /// that would carry work to it. That question needs the last decision and not a
  /// measurement, which is why it can be answered at all today.
  std::optional<double> commanded(const std::string & asset) const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    const auto entry = commanded_.find(asset);
    if (entry == commanded_.end()) {
      return std::nullopt;
    }
    return entry->second;
  }

  /// Every belt the model declared, in a stable order.
  std::vector<std::string> assets() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    std::vector<std::string> names;
    names.reserve(drives_.size());
    for (const auto & [asset, drive] : drives_) {
      static_cast<void>(drive);
      names.push_back(asset);
    }
    return names;
  }

private:
  void on_edge(const std::string & topic, const cite_interfaces::msg::DetectionEvent & event)
  {
    // AN EDGE, NOT A LEVEL — the same test `TriggerWatch::take` applies, and for
    // the same reason. `previous_state` is carried precisely so a consumer can
    // detect a transition without keeping its own history, and the detector's
    // first report sets it equal on purpose so that a beam already broken at
    // start-up is not read as an arrival.
    if (event.previous_state == event.state) {
      return;
    }
    for (const auto & asset : belts_for(topic, event.state)) {
      // A belt already stopped is commanded to stop again. That is a repeated
      // setpoint and not a state change, and it is cheaper than remembering a
      // state this node cannot observe: the command path has no confirmation,
      // so a cached "already stopped" would be a belief rather than a fact.
      command(asset, 0.0);
      RCLCPP_INFO(
        node_->get_logger(),
        "indexing '%s': %s reported the transition this belt's station acts on, so the "
        "belt is stopped until that station completes its handoff",
        asset.c_str(), topic.c_str());
    }
  }

  std::vector<std::string> belts_for(const std::string & topic, uint8_t state) const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    std::vector<std::string> assets;
    const auto entry = watched_.find(topic);
    if (entry == watched_.end()) {
      return assets;
    }
    for (const auto & [watched_state, asset] : entry->second) {
      if (watched_state == state) {
        assets.push_back(asset);
      }
    }
    return assets;
  }

  /// A subscriber appeared on this belt's command topic: tell it where the belt is.
  ///
  /// Only when the count went UP, and only when this class has already decided
  /// something. Before the first command there is no intent to state, and a zero
  /// sent then would be this class asserting a standstill it never chose.
  void on_subscriber_matched(const std::string & asset, const rclcpp::MatchedInfo & info)
  {
    if (info.current_count_change <= 0) {
      return;
    }
    double setpoint = 0.0;
    {
      const std::lock_guard<std::mutex> lock(mutex_);
      const auto entry = commanded_.find(asset);
      if (entry == commanded_.end()) {
        return;
      }
      setpoint = entry->second;
    }
    RCLCPP_INFO(
      node_->get_logger(),
      "a subscriber appeared on '%s' after it was last commanded; re-sending %.3f m/s so "
      "it learns where the belt is rather than waiting for the next change",
      asset.c_str(), setpoint);
    static_cast<void>(command(asset, setpoint));
  }

  bool command(const std::string & asset, double speed)
  {
    rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr publisher;
    {
      const std::lock_guard<std::mutex> lock(mutex_);
      const auto entry = publishers_.find(asset);
      if (entry == publishers_.end()) {
        return false;
      }
      publisher = entry->second;
      // Recorded before publishing, so a subscriber that matches during the
      // publish below is answered with this value rather than the previous one.
      commanded_[asset] = speed;
    }
    std_msgs::msg::Float64 message;
    message.data = speed;
    publisher->publish(message);
    return true;
  }

  rclcpp::Node::SharedPtr node_;
  mutable std::mutex mutex_;
  ConveyorDrivesByAsset drives_;
  std::map<std::string, rclcpp::Publisher<std_msgs::msg::Float64>::SharedPtr> publishers_;
  std::map<std::string, rclcpp::Subscription<cite_interfaces::msg::DetectionEvent>::SharedPtr>
  subscriptions_;
  std::map<std::string, std::vector<std::pair<uint8_t, std::string>>> watched_;
  std::set<std::string> indexed_;
  //: What each belt was last commanded to, which is this class's whole state
  //: about the plant. Absent until the first command: "not commanded yet" and
  //: "commanded to a standstill" are different, and only one of them is a
  //: decision.
  std::map<std::string, double> commanded_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__CONVEYOR_INDEX_HPP_
