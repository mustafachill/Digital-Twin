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

// L4: the line.
//
// One behaviour subtree per station, instantiated from the L0 process topology,
// with the coordinator knowing nothing about what a station is. It reads
// `LineTopology`, turns it into a plan, declares the shared resources the plan
// names, generates the root tree, and ticks it. **There is no station name in
// this file, and no station count.** Adding a fourth arm changes `model/`.
//
// WHAT IT OWNS, all of it in one copy: which work-piece is where and who owns it
// (`WorkpieceRegistry`), the handoff protocol (`HandoffLedger`), buffer and reach
// arbitration (`ResourceArbiter`), and throughput accounting. ADR-0024 puts
// ownership here on purpose — L3 executes motion and never learns who is on the
// other side of a handoff.
//
// WHAT IT DOES NOT OWN. It plans no trajectory and commands no controller; every
// leaf that moves anything is an L3 action. It is **not a safety mechanism**:
// L2's limits and collision checking prevent collisions, and this prevents
// deadlock and thrash. Confusing the two is how a coordination bug becomes an
// injury.
//
// IT BUILDS NO NAME. Every action it calls arrives as a parameter, exactly as the
// frames and the assets arrive in the topology — CLAUDE.md §8 puts name
// construction in the model and says no asset name is ever written by hand twice,
// and this project has removed a hand-composed `/cite/<zone>/<asset>/<skill>`
// from three separate files. The names now come from the model end to end: the
// generated bring-up plan carries a `skills:` block per arm, `cite_bringup`
// reads it and passes the parallel arrays below, and no string is composed
// anywhere in between.
//
// THREADING. An executor spins the node on its own thread; the tree is ticked on
// this one. No leaf spins, and no leaf blocks except on the cancellation path,
// which is the tick thread and not a callback. The registry, ledger and arbiter
// are touched only from the tick thread — `maintain()` below runs in the tick
// loop rather than in a timer callback precisely so that stays true and needs no
// lock.
//
// TIME. Every deadline in this node and in the leaves below it is read from the
// node's clock, which honours `use_sim_time`. All of them are FAILURE deadlines:
// nothing waits for one in order to proceed, and reaching one is the failure.

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <rclcpp/rclcpp.hpp>

#include <cite_interfaces/msg/line_state.hpp>
#include <cite_interfaces/msg/line_topology.hpp>
#include <cite_interfaces/msg/station_state.hpp>
#include <cite_interfaces/qos.hpp>
#include <cite_interfaces/srv/reset_station.hpp>

#include "behaviortree_cpp/bt_factory.h"
#include "cite_orchestration/conveyor_index.hpp"
#include "cite_orchestration/line_maintenance.hpp"
#include "cite_orchestration/line_nodes.hpp"
#include "cite_orchestration/line_plan.hpp"
#include "cite_orchestration/line_tree.hpp"
#include "cite_orchestration/skill_nodes.hpp"
#include "cite_orchestration/station_reset.hpp"

namespace
{

using cite_interfaces::msg::LineState;
using cite_interfaces::msg::LineTopology;
using cite_interfaces::msg::StationState;
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
using cite_orchestration::StationReset;
using cite_orchestration::StationRuntime;
using cite_orchestration::TriggerWatch;
using cite_orchestration::WorkpieceRegistry;

/// Read a parameter that must be supplied, collecting the missing ones.
std::string required(
  const rclcpp::Node::SharedPtr & node, const std::string & name,
  std::vector<std::string> & missing)
{
  node->declare_parameter(name, "");
  const auto value = node->get_parameter(name).as_string();
  if (value.empty()) {
    missing.push_back(name);
  }
  return value;
}

/// Read the per-asset action names.
///
/// PARALLEL ARRAYS, and the shape is deliberate. The alternative — declaring
/// `skills.<asset>.pick` once the topology has arrived — reads better in a launch
/// file and hides a whole class of mistake: a parameter whose name nothing checks
/// is a parameter that is silently absent when it is misspelled. Here a
/// mismatched length is refused at start-up with both lengths named, and every
/// value is discoverable with `ros2 param get` before anything moves.
///
/// `transfer_actions` may be short or absent. Only a direct arm-to-arm handoff
/// calls `Transfer`, and `line_plan.hpp` refuses those until a grasp holds an
/// orientation, so a line legitimately runs without one.
bool read_skill_actions(
  const rclcpp::Node::SharedPtr & node, SkillActionsByAsset & actions, std::string & complaint)
{
  const std::vector<std::string> empty;
  node->declare_parameter("skill_assets", empty);
  node->declare_parameter("move_to_actions", empty);
  node->declare_parameter("pick_actions", empty);
  node->declare_parameter("place_actions", empty);
  node->declare_parameter("detect_actions", empty);
  node->declare_parameter("transfer_actions", empty);

  const auto assets = node->get_parameter("skill_assets").as_string_array();
  const auto move_to = node->get_parameter("move_to_actions").as_string_array();
  const auto pick = node->get_parameter("pick_actions").as_string_array();
  const auto place = node->get_parameter("place_actions").as_string_array();
  const auto detect = node->get_parameter("detect_actions").as_string_array();
  const auto transfer = node->get_parameter("transfer_actions").as_string_array();

  if (assets.empty()) {
    complaint =
      "skill_assets is empty. The topology says which arm serves which station; this "
      "parameter says what each arm's skill actions are called. Those names are in the "
      "generated bring-up plan, under each controller manager's `skills:` block, and "
      "whoever launches this node reads them from there — an empty array means the "
      "launch mechanism did not, not that the model is silent.";
    return false;
  }
  for (const auto & [label, values] :
    std::vector<std::pair<const char *, const std::vector<std::string> *>>{
      {"move_to_actions", &move_to}, {"pick_actions", &pick},
      {"place_actions", &place}, {"detect_actions", &detect}})
  {
    if (values->size() != assets.size()) {
      complaint = std::string(label) + " has " + std::to_string(values->size()) +
        " entries against " + std::to_string(assets.size()) +
        " in skill_assets; they are read in parallel and must line up";
      return false;
    }
  }

  for (std::size_t index = 0; index < assets.size(); ++index) {
    SkillActions skills;
    skills.move_to = move_to[index];
    skills.pick = pick[index];
    skills.place = place[index];
    skills.detect = detect[index];
    if (index < transfer.size()) {
      skills.transfer = transfer[index];
    }
    actions[assets[index]] = skills;
  }
  return true;
}

/// Read the per-belt drives, in the same parallel-array shape as the skills.
///
/// OPTIONAL AS A SET, REQUIRED PER BELT. A zone whose flow names no conveyor
/// needs none of these, so an empty set is not an error here — but a belt the
/// TOPOLOGY names and this table does not is refused below, where the plan says
/// which belts the line actually indexes. Accepting the gap silently would give a
/// line that stops a belt it cannot start, or never stops one at all: the
/// "publishing to a topic nobody consumes" failure, with a work-piece on the
/// floor at the end of it.
///
/// Every value is L0's. `command_topic` and `installed_speed_mps` are resolved by
/// the generator into `cell_a_plan.yaml` from
/// `model/assets/instances/conveyors.yaml`, and are passed through rather than
/// recomputed, so the speed the belt runs at exists in exactly one place (P1).
bool read_conveyor_drives(
  const rclcpp::Node::SharedPtr & node, ConveyorDrivesByAsset & drives, std::string & complaint)
{
  const std::vector<std::string> empty;
  const std::vector<double> no_speeds;
  node->declare_parameter("conveyor_assets", empty);
  node->declare_parameter("conveyor_command_topics", empty);
  node->declare_parameter("conveyor_speeds_mps", no_speeds);

  const auto assets = node->get_parameter("conveyor_assets").as_string_array();
  const auto topics = node->get_parameter("conveyor_command_topics").as_string_array();
  const auto speeds = node->get_parameter("conveyor_speeds_mps").as_double_array();

  if (topics.size() != assets.size() || speeds.size() != assets.size()) {
    complaint =
      "conveyor_command_topics has " + std::to_string(topics.size()) +
      " entries and conveyor_speeds_mps has " + std::to_string(speeds.size()) +
      ", against " + std::to_string(assets.size()) +
      " in conveyor_assets; they are read in parallel and must line up";
    return false;
  }
  for (std::size_t index = 0; index < assets.size(); ++index) {
    if (topics[index].empty()) {
      complaint = "conveyor '" + assets[index] + "' was given no command topic";
      return false;
    }
    if (!(speeds[index] > 0.0)) {
      // A belt declared at zero would be indexed to a standstill and then
      // "restarted" to a standstill, which is a stalled line reported as a
      // running one.
      complaint = "conveyor '" + assets[index] +
        "' was given an installed speed of " + std::to_string(speeds[index]) +
        " m/s; a belt that cannot run cannot be indexed";
      return false;
    }
    ConveyorDrive drive;
    drive.command_topic = topics[index];
    drive.installed_speed_mps = speeds[index];
    drives[assets[index]] = drive;
  }
  return true;
}

/// Waits for the latched topology, and says so when it does not arrive.
///
/// AN EVENT, WITH A FAILURE DEADLINE. It does not sleep for a guessed duration
/// and then hope; it blocks on a condition variable that the subscription
/// callback signals, and the deadline exists only so that a topology which never
/// comes is reported instead of waited on for ever. The LATCHED profile is what
/// makes this work at all for a coordinator that starts after the topology
/// server: a VOLATILE publisher would connect to this subscription silently and
/// deliver nothing, which is the failure CLAUDE.md §10 names first.
class TopologyWait
{
public:
  explicit TopologyWait(rclcpp::Node::SharedPtr node)
  {
    subscription_ = node->create_subscription<LineTopology>(
      LineTopology::TOPIC, cite::qos::latched(),
      [this](LineTopology::SharedPtr message) {
        {
          const std::lock_guard<std::mutex> lock(mutex_);
          topology_ = *message;
          arrived_ = true;
        }
        signal_.notify_all();
      });
  }

  bool wait_for(std::chrono::milliseconds deadline, LineTopology & topology)
  {
    std::unique_lock<std::mutex> lock(mutex_);
    if (!signal_.wait_for(lock, deadline, [this] {return arrived_;})) {
      return false;
    }
    topology = topology_;
    return true;
  }

private:
  rclcpp::Subscription<LineTopology>::SharedPtr subscription_;
  std::mutex mutex_;
  std::condition_variable signal_;
  bool arrived_{false};
  LineTopology topology_;
};

void complain(const rclcpp::Logger & logger, const std::vector<std::string> & refusals)
{
  for (const auto & refusal : refusals) {
    RCLCPP_FATAL(logger, "  - %s", refusal.c_str());
  }
}

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("line_orchestrator");

  std::vector<std::string> missing;
  const auto zone = required(node, "zone", missing);
  const auto station_tree = required(node, "station_tree", missing);
  // THE NAME IS THE MESSAGE'S, NOT THIS FILE'S. `LineState::TOPIC` is the one
  // place it is written — the asymmetry with `LineTopology` that this comment
  // used to report is closed — so the default comes off the constant and a
  // string literal here would be a value in two places (P1). It stays a
  // parameter so a test rig can publish somewhere private, which is the same
  // shape `LineState.msg` prescribes and `cite_bringup`'s
  // `test_the_line_state_topic_comes_off_the_message` already checks on the
  // launch side. Reading the constant is what makes it a compile dependency
  // rather than a comment about another package.
  node->declare_parameter(
    "line_state_topic", std::string(cite_interfaces::msg::LineState::TOPIC));
  const auto line_state_topic = node->get_parameter("line_state_topic").as_string();

  // Same shape and the same reason as `line_state_topic` above: the name is
  // written once, on the `.srv` itself, and stays a parameter so a test rig can
  // serve somewhere private. A string literal here would be a value in two
  // places (P1) and would not be discoverable with `ros2 interface show` (P3).
  node->declare_parameter(
    "reset_station_service",
    std::string(cite_interfaces::srv::ResetStation::Request::SERVICE));
  const auto reset_service = node->get_parameter("reset_station_service").as_string();

  node->declare_parameter("topology_deadline_s", 30.0);
  node->declare_parameter("handoff_timeout_s", 120.0);
  node->declare_parameter("skill_deadline_s", 180.0);
  node->declare_parameter("cancel_deadline_s", 30.0);
  node->declare_parameter("retry_budget", 2);
  // A POLL PERIOD, not a schedule. Nothing is sequenced by it and no state
  // transition waits for it: it is how often the tree looks at futures and
  // queues that are filled by other threads. The same distinction the skill
  // server draws for its own cancel poll.
  node->declare_parameter("tick_period_ms", 50);
  node->declare_parameter("state_period_ms", 200);

  SkillActionsByAsset actions;
  std::string complaint;
  const bool actions_ok = read_skill_actions(node, actions, complaint);

  ConveyorDrivesByAsset drives;
  std::string drive_complaint;
  const bool drives_ok = read_conveyor_drives(node, drives, drive_complaint);

  if (!missing.empty()) {
    std::string names;
    for (const auto & name : missing) {
      names += (names.empty() ? "" : ", ") + name;
    }
    RCLCPP_FATAL(
      node->get_logger(),
      "these parameters are required and were not supplied: %s. They come from the model "
      "and from whoever launches this node, not from this node's own initiative — refusing "
      "to start rather than guessing.",
      names.c_str());
    rclcpp::shutdown();
    return 1;
  }
  if (!actions_ok) {
    RCLCPP_FATAL(node->get_logger(), "%s", complaint.c_str());
    rclcpp::shutdown();
    return 1;
  }
  if (!drives_ok) {
    RCLCPP_FATAL(node->get_logger(), "%s", drive_complaint.c_str());
    rclcpp::shutdown();
    return 1;
  }

  // Spun on its own thread from here on. Multi-threaded because the topology
  // wait, the sensor subscriptions and the action clients all have to make
  // progress while the tick thread is inside a leaf.
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  std::thread spinner([&executor]() {executor.spin();});

  int status = 0;
  {
    TopologyWait wait(node);
    LineTopology topology;
    const auto deadline = std::chrono::milliseconds(
      static_cast<int64_t>(node->get_parameter("topology_deadline_s").as_double() * 1000.0));
    if (!wait.wait_for(deadline, topology)) {
      RCLCPP_FATAL(
        node->get_logger(),
        "no LineTopology arrived on %s within the deadline. It is published on the LATCHED "
        "profile, so a topology server that is already up delivers it immediately — this "
        "means either no server is running or it has not been activated.",
        std::string(LineTopology::TOPIC).c_str());
      status = 1;
    } else if (topology.zone != zone) {
      RCLCPP_FATAL(
        node->get_logger(),
        "this coordinator was configured for zone '%s' and the topology describes '%s'. "
        "Running the wrong zone's flow would command the wrong arms.",
        zone.c_str(), topology.zone.c_str());
      status = 1;
    } else {
      LinePlan plan = cite_orchestration::plan_line(topology);

      // THE BELTS THIS LINE INDEXES (ADR-0032), checked against the drives it was
      // given. A belt is indexed when it is the inbound carrier of a station WITH
      // A ROBOT ACTOR — which is exactly what `plan.stations` contains, so the
      // actor condition needs no test of its own here. `station_accumulation` is
      // a sink: it has a trigger and no actor, so its belt is declared, started,
      // and never stopped. A rule keyed on the trigger alone would stop it for
      // ever.
      //
      // A refusal rather than a warning, and collected alongside the plan's own
      // so that one report names everything wrong at once. A line that indexed a
      // belt it could not command would stop that belt on the first work-piece
      // and never start it again — a stall that looks, from every topic this node
      // publishes, exactly like a line waiting for work.
      for (const auto & station : plan.stations) {
        if (!station.inbound_via_asset_id.empty() &&
          drives.count(station.inbound_via_asset_id) == 0)
        {
          plan.refusals.push_back(
            "station '" + station.id + "' picks from belt '" + station.inbound_via_asset_id +
            "', and no `conveyor_assets` entry declares a drive for it. The belt would be "
            "stopped on this station's trigger and never started again");
        }
      }

      if (!plan.usable()) {
        RCLCPP_FATAL(
          node->get_logger(),
          "the topology for zone '%s' cannot be run as published:", zone.c_str());
        complain(node->get_logger(), plan.refusals);
        status = 1;
      } else {
        LineContext line;
        line.node = node;
        line.registry = std::make_shared<WorkpieceRegistry>();
        line.ledger = std::make_shared<HandoffLedger>();
        line.arbiter = std::make_shared<ResourceArbiter>();
        line.triggers = std::make_shared<TriggerWatch>(node);
        line.conveyors = std::make_shared<ConveyorIndex>(node, drives);
        line.stations = std::make_shared<std::map<std::string, StationRuntime>>();
        line.handoff_timeout = rclcpp::Duration::from_seconds(
          node->get_parameter("handoff_timeout_s").as_double());
        line.retry_budget =
          static_cast<uint32_t>(node->get_parameter("retry_budget").as_int());

        for (const auto & resource : plan.resources) {
          line.arbiter->declare_resource(resource.name, resource.capacity);
        }
        for (const auto & station : plan.stations) {
          StationRuntime runtime;
          runtime.capacity = station.capacity;
          runtime.state = StationState::STATE_WAITING;
          (*line.stations)[station.id] = runtime;
          // The stop half of indexing, bound to the sensor edge rather than to a
          // point in this station's cycle — see `conveyor_index.hpp` for why the
          // two halves are not symmetrical. Nothing here is a station name or a
          // belt name: both come out of the plan, which came out of L0.
          line.conveyors->index_on(
            station.trigger_topic, station.trigger_detection_state,
            station.inbound_via_asset_id);
        }

        const auto tree_xml = cite_orchestration::line_tree_xml(plan, actions);
        if (!tree_xml.refusals.empty()) {
          RCLCPP_FATAL(node->get_logger(), "the line tree cannot be built:");
          complain(node->get_logger(), tree_xml.refusals);
          status = 1;
        } else {
          Context context;
          context.node = node;
          context.skill_deadline = std::chrono::seconds(
            static_cast<int64_t>(node->get_parameter("skill_deadline_s").as_double()));
          context.cancel_deadline = std::chrono::seconds(
            static_cast<int64_t>(node->get_parameter("cancel_deadline_s").as_double()));

          BT::BehaviorTreeFactory factory;
          factory.registerNodeType<cite_orchestration::MoveToHome>("MoveToHome", context);
          factory.registerNodeType<cite_orchestration::PickAt>("PickAt", context);
          factory.registerNodeType<cite_orchestration::PlaceAt>("PlaceAt", context);
          factory.registerNodeType<cite_orchestration::DetectAt>("DetectAt", context);
          factory.registerNodeType<cite_orchestration::TransferTo>("TransferTo", context);
          factory.registerNodeType<cite_orchestration::ReportBlocked>("ReportBlocked", node);
          factory.registerNodeType<cite_orchestration::AwaitTrigger>("AwaitTrigger", line);
          factory.registerNodeType<cite_orchestration::AcceptOffers>("AcceptOffers", line);
          factory.registerNodeType<cite_orchestration::TakeCustody>("TakeCustody", line);
          factory.registerNodeType<cite_orchestration::ClaimReach>("ClaimReach", line);
          factory.registerNodeType<cite_orchestration::ClaimBufferSlot>(
            "ClaimBufferSlot", line);
          factory.registerNodeType<cite_orchestration::ReleaseClaim>("ReleaseClaim", line);
          factory.registerNodeType<cite_orchestration::ReleaseStationClaims>(
            "ReleaseStationClaims", line);
          factory.registerNodeType<cite_orchestration::OfferHandoff>("OfferHandoff", line);
          factory.registerNodeType<cite_orchestration::AwaitHandoffConfirmed>(
            "AwaitHandoffConfirmed", line);
          factory.registerNodeType<cite_orchestration::CompleteHandoff>(
            "CompleteHandoff", line);
          factory.registerNodeType<cite_orchestration::ResumeBelt>("ResumeBelt", line);
          factory.registerNodeType<cite_orchestration::SetStationState>(
            "SetStationState", line);
          factory.registerNodeType<cite_orchestration::RecoverFromFailure>(
            "RecoverFromFailure", line);

          // The station subtree is a file a person wrote and reviewed; the root
          // tree above it is generated from the plan. That split is the whole
          // design: what a station does is written once, how many there are is
          // data.
          factory.registerBehaviorTreeFromFile(station_tree);
          factory.registerBehaviorTreeFromText(tree_xml.xml);

          RCLCPP_INFO(
            node->get_logger(),
            "running flow '%s' in zone '%s': %zu station(s), %zu sink(s), %zu arbitrated "
            "resource(s)",
            plan.flow_id.c_str(), plan.zone.c_str(), plan.stations.size(),
            plan.sinks.size(), plan.resources.size());

          auto tree = factory.createTree("Line");
          LineMaintenance maintenance(line, plan, line_state_topic);

          // The operator's only control over a blocked station (ADR-0037). It
          // clears a block and commands nothing: no plan, no `MoveTo`, no belt.
          //
          // The mutex is held across a whole tick below, so a reset lands between
          // ticks rather than inside one - which is what lets every other reader
          // of `StationRuntime` go on assuming it runs on the tick thread alone.
          auto tick_mutex = std::make_shared<std::mutex>();
          StationReset reset(line, plan, reset_service, tick_mutex);

          // START THE PLANT. Every belt the model declares goes to its installed
          // speed, once, before the first tick — the indexed ones will be stopped
          // again by the first work-piece that reaches their beam, and the ones
          // that feed a sink simply run.
          //
          // AFTER the tree has been built, deliberately. Everything that can
          // refuse to run this line has refused by here, so a coordinator that
          // exits does not leave three belts moving with nothing supervising
          // them. The cost is a window between the sensor subscriptions above and
          // this line in which an edge would stop a belt that is then started
          // here; it is the length of a tree construction, and at start-up there
          // is no work-piece on a belt to produce that edge.
          //
          // This is where the belt setpoint acquires an owner. Until ADR-0032
          // nothing in the running system commanded a conveyor and the
          // continuous-line scenario supplied one, reporting itself as a gap
          // rather than a boundary. It no longer publishes: it subscribes to the
          // same command topics and asserts a non-zero setpoint arrives, so
          // deleting this line fails
          // `continuous_line::_assert_the_line_started_the_belts` rather than
          // being covered by the harness that was standing in for it.
          //
          // ONE PUBLICATION, NOT A LOOP — AND IT IS NOT ENOUGH ON ITS OWN. This
          // comment used to argue that it was: the COMMAND profile is reliable,
          // the bridge has been up since long before the topology arrived, so a
          // repeated send would only be covering a race this ordering had closed.
          // That is wrong, and it was wrong in the direction that leaves three
          // belts stationary. Reliability is a promise to subscribers this
          // publisher has been MATCHED with, and the publishers were created a few
          // lines above, inside this same callback: at this instant the matched
          // count is zero and the message goes nowhere, no matter how long the
          // bridge has been running. The scenario's own publisher — ten sends over
          // a second — is what actually started the belts, and removing it is how
          // this surfaced.
          //
          // What closes it is in `conveyor_index.hpp`: a subscriber appearing is
          // an event, and the belt's current setpoint is sent when it does. So
          // this call states the intent once, and the intent reaches whoever turns
          // up. Still no retry and still no delay (P4).
          line.conveyors->run_all();

          const auto tick_period = std::chrono::milliseconds(
            node->get_parameter("tick_period_ms").as_int());
          const auto state_period = rclcpp::Duration(
            std::chrono::milliseconds(node->get_parameter("state_period_ms").as_int()));

          rclcpp::Time last_report = node->get_clock()->now();
          BT::NodeStatus outcome = BT::NodeStatus::RUNNING;
          while (rclcpp::ok() && outcome == BT::NodeStatus::RUNNING) {
            {
              // Held across the tick and the maintenance pass, and released
              // before the sleep. The only other holder is the reset service, so
              // this is a boundary marker rather than contention: it makes
              // "touched only from the tick thread" true again now that one thing
              // is not on the tick thread.
              const std::lock_guard<std::mutex> lock(*tick_mutex);
              outcome = tree.tickOnce();
              maintenance.run();
              const rclcpp::Time now = node->get_clock()->now();
              if (now - last_report >= state_period) {
                maintenance.publish();
                last_report = now;
              }
            }
            // BT.CPP's own wait: it returns early when a leaf signals a wake-up,
            // so this is a ceiling on latency rather than a fixed cadence.
            tree.sleep(tick_period);
          }

          // Whatever ends this, no arm is left moving under a goal nobody is
          // holding: halting the tree halts every RUNNING leaf, and a skill leaf
          // that is halted cancels its goal and waits for it to end.
          tree.haltTree();
          maintenance.publish();

          if (outcome == BT::NodeStatus::FAILURE) {
            RCLCPP_ERROR(
              node->get_logger(),
              "the line stopped: a station escalated past its recovery policy. Its reason "
              "is in the LineState published on %s.", line_state_topic.c_str());
            status = 1;
          }
        }
      }
    }
  }

  executor.cancel();
  if (spinner.joinable()) {
    spinner.join();
  }
  rclcpp::shutdown();
  return status;
}
