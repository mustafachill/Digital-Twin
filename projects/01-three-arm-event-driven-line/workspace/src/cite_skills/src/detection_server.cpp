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

// L3 `Detect`: the layer that turns a sensor's level into the line's events.
//
// One node per zone, not per arm. The break beams watch a belt, not a robot;
// three arms each running this would be three views of one conveyor, and the
// first question anyone asked — "did the piece pass beam 2" — would have three
// answers. It commands no motion, so it needs neither the planner nor the
// gripper, and it shares nothing with `skill_server`'s one-goal-at-a-time gate on
// the arm.
//
// ## Why the typing happens here and not in the plugin
//
// `cite_simulation/src/break_beam.cpp` publishes a raw boolean level on the
// Gazebo transport and nothing else, deliberately, and its header says why: a
// plugin that published a ROS message directly would be a second,
// simulation-only route into the system. The physical sensor will arrive as a
// level too — that is what a through-beam is. So both paths deliver a level, and
// this is the single place either of them becomes a `DetectionEvent`. That is
// what keeps the interface above the sensor identical on both paths (P2), and it
// is why there is no `if simulation` here or anywhere below it.
//
// ## Edges are made here, because level is what a beam has
//
// The plugin publishes state, not change, and republishes it periodically so a
// subscriber that starts late learns where the beam stands without waiting for
// the next transition. The rising edge is the event the line acts on, and
// building it is this node's job — see `cite_skills/detection.hpp`, where the
// rule lives as a state machine that can be tested without a simulator.
//
// ## Every name arrives as data
//
// Not one topic, frame or asset id is composed here. `/cite/<zone>/<asset>/...`
// is generated from the L0 model by `ids.py`, and a name built in this file would
// be a second place a name is made, outside the reach of the tests that cover
// that one. The node refuses to start rather than guess.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <geometry_msgs/msg/pose_stamped.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>
#include <std_msgs/msg/bool.hpp>
#include "tf2_ros/buffer.h"
#include "tf2_ros/transform_listener.h"

#include <cite_interfaces/action/detect.hpp>
#include <cite_interfaces/msg/detection.hpp>
#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/msg/result_code.hpp>
#include <cite_interfaces/qos.hpp>

#include "cite_skills/detection.hpp"
#include "cite_skills/exclusive_goal.hpp"
#include "cite_skills/observation.hpp"

namespace
{

using cite_interfaces::action::Detect;
using cite_interfaces::msg::Detection;
using cite_interfaces::msg::DetectionEvent;
using cite_interfaces::msg::ResultCode;

//: How often a `Detect` goal that is waiting on a silent sensor looks up to see
//: whether it has been cancelled. A poll period on a condition, not a guess at
//: how long anything takes (P4).
constexpr std::chrono::milliseconds kCancelPollPeriod{20};
//: How long a goal thread waits for an accepted cancel to reach the goal handle
//: before reporting the result. Bounded, so a cancel that is never completed
//: cannot hold a goal open.
constexpr std::chrono::milliseconds kCancelHandshake{2000};

ResultCode make_result(uint8_t code, const std::string & detail = "")
{
  ResultCode result;
  result.code = code;
  result.detail = detail;
  return result;
}

/// One break beam: where its level arrives, where its events go, and where it is.
struct Sensor
{
  std::string asset_id;
  //: The ROS topic carrying the bridged boolean level. Supplied, never derived —
  //: the bridge from Gazebo transport into ROS is `cite_bringup`'s to declare,
  //: and it lands the level on `level_topic`, deliberately NOT on the name the
  //: plugin publishes the event under. Composing it here would hard-code one
  //: package's choice into another's source.
  std::string state_topic;
  //: Where this beam's typed events are published.
  std::string event_topic;
  //: The beam's own TF frame, generated from the same L0 frame that places the
  //: sensor housing.
  std::string frame_id;

  cite_skills::BeamEdgeDetector edges;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr subscription;
  rclcpp::Publisher<DetectionEvent>::SharedPtr publisher;
};

/// The zone's detection server.
class DetectionServer : public rclcpp::Node
{
public:
  DetectionServer()
  : Node("detection_server")
  {
    // Empty defaults, as `skill_server` declares its own: a default that
    // silently worked would hide a bring-up plan that failed to deliver the
    // value, and the node would then watch a topic nothing publishes and report
    // an empty belt forever.
    declare_parameter("zone", "");
    declare_parameter("sensors", std::vector<std::string>{});
    declare_parameter("tf_timeout_s", 5.0);
    // How long a `Detect` goal waits for a sensor that has not reported yet.
    //
    // A grace period, not a schedule. Every beam republishes its level
    // periodically, so in a healthy cell every sensor is known within one period
    // and no goal ever waits; this exists so that a `Detect` issued in the
    // moments after start-up does not fail for want of a sample that is about to
    // arrive. When it does expire, that is a diagnosis — the bridge is not
    // delivering — and it is reported as one rather than as an empty belt.
    declare_parameter("detect_timeout_s", 5.0);
  }

  ~DetectionServer() override
  {
    shutdown();
  }

  /// Read parameters and build the sensor table. Returns false with a reason.
  bool configure()
  {
    zone_ = get_parameter("zone").as_string();
    if (zone_.empty()) {
      RCLCPP_ERROR(
        get_logger(),
        "parameter 'zone' is empty. Every name this node uses comes from the generated "
        "bring-up plan; an empty one means the plan did not deliver it.");
      return false;
    }
    tf_timeout_s_ = get_parameter("tf_timeout_s").as_double();
    detect_timeout_s_ = get_parameter("detect_timeout_s").as_double();
    if (detect_timeout_s_ < 0.0) {
      RCLCPP_ERROR(get_logger(), "detect_timeout_s must not be negative");
      return false;
    }

    const auto asset_ids = get_parameter("sensors").as_string_array();
    if (asset_ids.empty()) {
      RCLCPP_ERROR(
        get_logger(),
        "no sensors were declared. This node exists to turn sensor levels into typed "
        "events; with none it would advertise 'detect' and answer every goal with an "
        "empty list, which reads as an empty belt rather than as a missing "
        "configuration.");
      return false;
    }

    for (const auto & asset_id : asset_ids) {
      // Per-sensor keys, declared as they are met rather than up front: the set
      // of sensors is a fact about the zone, which is L0 data, and this node
      // learns it from the plan rather than carrying its own copy (P1).
      const std::string prefix = "sensor." + asset_id + ".";
      declare_parameter(prefix + "state_topic", "");
      declare_parameter(prefix + "event_topic", "");
      declare_parameter(prefix + "frame_id", "");

      auto sensor = std::make_shared<Sensor>();
      sensor->asset_id = asset_id;
      sensor->state_topic = get_parameter(prefix + "state_topic").as_string();
      sensor->event_topic = get_parameter(prefix + "event_topic").as_string();
      sensor->frame_id = get_parameter(prefix + "frame_id").as_string();

      for (const auto & [key, value] :
        {std::pair{"state_topic", sensor->state_topic},
          std::pair{"event_topic", sensor->event_topic},
          std::pair{"frame_id", sensor->frame_id}})
      {
        if (value.empty()) {
          RCLCPP_ERROR(
            get_logger(),
            "sensor '%s' has no '%s'. The bring-up plan carries the beam's bridged "
            "topic, its event topic and its frame; a name invented here would be a "
            "second place that name is made, and it would point somewhere nothing "
            "looks.",
            asset_id.c_str(), key);
          return false;
        }
      }
      sensors_.push_back(sensor);
    }

    tf_buffer_ = std::make_shared<tf2_ros::Buffer>(get_clock());
    tf_listener_ = std::make_shared<tf2_ros::TransformListener>(*tf_buffer_);
    return true;
  }

  /// Subscribe, advertise, and start accepting goals.
  bool activate(const rclcpp::Node::SharedPtr & self)
  {
    for (const auto & sensor : sensors_) {
      // EVENT profile, which `DetectionEvent.msg` names in its own header and
      // this does not get to second-guess: keep-all and reliable, because a
      // missed transition is a work-piece the line never notices and the station
      // downstream then waits forever.
      sensor->publisher = create_publisher<DetectionEvent>(
        sensor->event_topic, cite::qos::event());

      // SENSOR profile on the way in, and the two are deliberately different.
      //
      // This is a level, not an event: the beam republishes its current state
      // every period, so only the newest sample matters and a dropped one is
      // recovered by the next. It is the TRANSITION that must not be lost, and
      // the transition is made here and published reliably — a level dropped in
      // transit still shows up as an edge on the following sample, one period
      // late, because the detector compares against the last level it saw rather
      // than against the last one sent.
      //
      // Best-effort on this side is also what makes the subscription compatible
      // with whatever `cite_bringup` configures the bridge to publish: a
      // best-effort reader matches a reliable writer, while a reliable reader
      // would silently fail to match a best-effort one — connecting, showing up
      // in `ros2 topic info`, and delivering nothing.
      auto sensor_ptr = sensor;
      sensor->subscription = create_subscription<std_msgs::msg::Bool>(
        sensor->state_topic, cite::qos::sensor(),
        [this, sensor_ptr](const std_msgs::msg::Bool::SharedPtr level) {
          observe(*sensor_ptr, level->data);
        });

      RCLCPP_INFO(
        get_logger(), "watching '%s' on '%s', publishing events on '%s'",
        sensor->asset_id.c_str(), sensor->state_topic.c_str(),
        sensor->event_topic.c_str());
    }

    detect_server_ = rclcpp_action::create_server<Detect>(
      self, "detect",
      [this](const rclcpp_action::GoalUUID & uuid, std::shared_ptr<const Detect::Goal>) {
        return claim(uuid);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Detect>> handle) {
        return cancel(handle);
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<Detect>> handle) {
        start([this, handle] {execute_detect(handle);});
      });

    RCLCPP_INFO(
      get_logger(), "detection for zone '%s' is accepting goals over %zu sensor(s)",
      zone_.c_str(), sensors_.size());
    return true;
  }

  /// Let the goal thread finish before anything it holds is destroyed.
  void shutdown()
  {
    if (shutting_down_.exchange(true)) {
      return;
    }
    std::thread worker;
    {
      const std::lock_guard<std::mutex> lock(worker_mutex_);
      worker = std::move(worker_);
    }
    if (worker.joinable()) {
      worker.join();
    }
  }

private:
  // ---------------------------------------------------------------------------
  // The sensor stream
  // ---------------------------------------------------------------------------

  /// Fold one level sample in and publish the event, if it is one.
  void observe(Sensor & sensor, bool blocked)
  {
    // The node's clock, which follows `use_sim_time` like every other clock here.
    //
    // It is a RECEIVE time, and that is a limitation worth naming rather than
    // hiding: `std_msgs/Bool` carries no header, so the moment the beam actually
    // broke is not in the message and cannot be recovered. What is recorded is
    // when this node saw it, which trails the physical edge by the bridge's
    // latency plus up to one publish period. Durations between edges are
    // differences of receive times and inherit the same offset at both ends, so
    // they are the more trustworthy of the two numbers.
    const auto stamp = now();

    cite_skills::BeamEdgeDetector::Report report;
    {
      const std::lock_guard<std::mutex> lock(sensors_mutex_);
      report = sensor.edges.observe(blocked, stamp.seconds());
    }
    if (report.kind == cite_skills::BeamReport::None) {
      return;
    }

    DetectionEvent event;
    // The beam's own frame, so `position` is its origin — which is exactly true
    // and needs no transform to say. The beam IS the place the detection
    // happened; expressing it somewhere else is TF's job and the consumer's
    // choice, not a name for this node to compose.
    event.header.stamp = stamp;
    event.header.frame_id = sensor.frame_id;
    event.asset_id = sensor.asset_id;
    event.state = report.state ? DetectionEvent::STATE_BLOCKED : DetectionEvent::STATE_CLEAR;
    event.previous_state =
      report.previous_state ? DetectionEvent::STATE_BLOCKED : DetectionEvent::STATE_CLEAR;
    event.duration_in_previous_state =
      rclcpp::Duration::from_seconds(report.duration_in_previous_state_s);
    // Left empty, which `DetectionEvent.msg` provides for: "empty when the sensor
    // cannot identify what it saw". A through-beam reports that its volume is
    // occupied and nothing whatever about by what. Filling in the goal's
    // requested type here would turn an assumption into a reading.
    event.workpiece_id = "";

    if (report.kind == cite_skills::BeamReport::Initial) {
      RCLCPP_INFO(
        get_logger(), "'%s' first reported %s", sensor.asset_id.c_str(),
        report.state ? "BLOCKED" : "CLEAR");
    } else {
      RCLCPP_INFO(
        get_logger(), "'%s' %s after %.2f s", sensor.asset_id.c_str(),
        report.state ? "BLOCKED" : "CLEARED", report.duration_in_previous_state_s);
    }
    sensor.publisher->publish(event);
  }

  // ---------------------------------------------------------------------------
  // Goal admission
  // ---------------------------------------------------------------------------
  rclcpp_action::GoalResponse claim(const rclcpp_action::GoalUUID & uuid)
  {
    if (shutting_down_.load()) {
      return rclcpp_action::GoalResponse::REJECT;
    }
    if (gate_.claim(uuid, "detect")) {
      cancel_requested_.store(false);
      return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
    }
    // One goal at a time, for the same reason the arm server runs one: a goal
    // per caller would be a thread per caller, unbounded and unjoinable at
    // teardown. A `Detect` reads a cache and returns, so the window a second
    // caller can land in is the time it takes to consult TF — and the only case
    // that waits at all is a sensor which has not reported, which is a fault
    // rather than normal running.
    RCLCPP_WARN(
      get_logger(),
      "rejecting a 'detect' goal: another one is still in flight. It will not be long; "
      "a detect that waits is a detect whose sensor has gone quiet.");
    return rclcpp_action::GoalResponse::REJECT;
  }

  template<typename Handle>
  rclcpp_action::CancelResponse cancel(const Handle & handle)
  {
    if (!gate_.owns(handle->get_goal_id())) {
      return rclcpp_action::CancelResponse::REJECT;
    }
    // Recorded as well as accepted: `is_canceling()` only becomes true once this
    // callback has returned, so a goal thread that consulted only the handle
    // could miss its own cancellation entirely.
    cancel_requested_.store(true);
    return rclcpp_action::CancelResponse::ACCEPT;
  }

  template<typename Work>
  void start(Work work)
  {
    std::thread previous;
    {
      const std::lock_guard<std::mutex> lock(worker_mutex_);
      previous = std::move(worker_);
      worker_ = std::thread([this, work] {
            work();
            gate_.release();
      });
    }
    // The previous goal released the gate before this one was admitted, so this
    // join reaps a finished thread rather than waiting for work.
    if (previous.joinable()) {
      previous.join();
    }
  }

  template<typename Handle>
  bool cancelled(const Handle & handle) const
  {
    return handle->is_canceling() || cancel_requested_.load() ||
           shutting_down_.load() || !rclcpp::ok();
  }

  template<typename Handle, typename Result>
  void terminate(
    const Handle & handle, const std::shared_ptr<Result> & result, const ResultCode & outcome)
  {
    try {
      if (outcome.code == ResultCode::SUCCESS) {
        handle->succeed(result);
      } else if (outcome.code == ResultCode::CANCELLED && wait_until_cancelling(handle)) {
        handle->canceled(result);
      } else {
        handle->abort(result);
      }
    } catch (const std::exception & error) {
      RCLCPP_WARN(get_logger(), "could not report a goal's result: %s", error.what());
    }
  }

  /// Wait for an accepted cancel to reach the goal handle.
  ///
  /// The state machine reaches CANCELING only after the cancel callback returns,
  /// and the goal thread can get there first — in which case the result would be
  /// reported with `abort()` on a goal the caller cancelled.
  template<typename Handle>
  bool wait_until_cancelling(const Handle & handle)
  {
    if (!cancel_requested_.load()) {
      return false;
    }
    const auto deadline = std::chrono::steady_clock::now() + kCancelHandshake;
    while (!handle->is_canceling() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(kCancelPollPeriod);
    }
    return handle->is_canceling();
  }

  // ---------------------------------------------------------------------------
  // Detect
  // ---------------------------------------------------------------------------
  void execute_detect(const std::shared_ptr<rclcpp_action::ServerGoalHandle<Detect>> handle)
  {
    const auto goal = handle->get_goal();
    auto result = std::make_shared<Detect::Result>();

    const auto finish = [&](const ResultCode & outcome) {
        result->result = outcome;
        terminate(handle, result, outcome);
      };

    if (goal->region_frame.empty()) {
      finish(make_result(
        ResultCode::PRECONDITION_FAILED,
        "region_frame is empty; a region has to be expressed in some frame"));
      return;
    }
    // Refused rather than answered with an empty list. A default-constructed goal
    // has a zero-sized region, and an empty detection list from one would read as
    // "nothing is on the belt" — a wrong answer that looks exactly like a right
    // one, which is the failure class this repository keeps finding.
    if (goal->region_size_m.x <= 0.0 || goal->region_size_m.y <= 0.0 ||
      goal->region_size_m.z <= 0.0)
    {
      finish(make_result(
        ResultCode::PRECONDITION_FAILED,
        "region_size_m must be positive on every axis; a region with no volume would "
        "match nothing, and an empty result reads as an empty belt"));
      return;
    }
    // A through-beam cannot tell a work-piece from a hand. Filtering on type
    // would mean either ignoring the filter — answering a narrower question than
    // was asked — or inventing the type from the goal, which is the caller's
    // assumption handed back as a reading. Neither is acceptable, so the
    // unimplementable path says so in a code L4 can branch on (P7).
    if (!goal->workpiece_type.empty()) {
      finish(make_result(
        ResultCode::NOT_IMPLEMENTED,
        "this zone detects with break beams, which report that their volume is "
        "occupied and nothing about by what, so a detection cannot be filtered to "
        "workpiece_type '" + goal->workpiece_type +
          "'. Send an empty workpiece_type to match anything. Identifying a type needs "
          "perception, which the Detect contract is shaped for and Phase 1 does not "
          "have"));
      return;
    }

    // Which beams the caller is asking about. Resolved through TF rather than
    // from any table here: where a beam stands is L0 data, published as a static
    // transform generated from the same frame that places the housing, and a copy
    // of it in this node would be a second place it lives (P1).
    std::vector<std::shared_ptr<Sensor>> in_region;
    for (const auto & sensor : sensors_) {
      geometry_msgs::msg::TransformStamped where;
      try {
        where = tf_buffer_->lookupTransform(
          goal->region_frame, sensor->frame_id, tf2::TimePointZero,
          tf2::durationFromSec(tf_timeout_s_));
      } catch (const std::exception & error) {
        finish(make_result(
          ResultCode::PRECONDITION_FAILED,
          "TF could not place sensor '" + sensor->asset_id + "' (frame '" +
            sensor->frame_id + "') in the region frame '" + goal->region_frame +
            "': " + error.what()));
        return;
      }
      if (cite_skills::inside_region(
          where.transform.translation.x, where.transform.translation.y,
          where.transform.translation.z, goal->region_size_m.x, goal->region_size_m.y,
          goal->region_size_m.z))
      {
        in_region.push_back(sensor);
      }
    }

    if (in_region.empty()) {
      // Not an error. A region with no sensor in it genuinely has nothing to say,
      // and the empty list is the honest answer — but it is said out loud,
      // because "no sensor watches here" and "nothing is here" are different
      // facts and the caller cannot tell them apart from an empty list alone.
      finish(make_result(
        ResultCode::SUCCESS,
        "no sensor in this zone lies inside the requested region, so nothing is "
        "observed there. This is not a report that the region is empty"));
      return;
    }

    // Wait, briefly and cancellably, for any beam that has not spoken yet.
    const auto silent = await_first_reports(in_region, handle);
    if (silent.code != ResultCode::SUCCESS) {
      finish(silent);
      return;
    }

    uint32_t found = 0;
    for (const auto & sensor : in_region) {
      if (cancelled(handle)) {
        finish(make_result(ResultCode::CANCELLED, "cancelled while reading the sensors"));
        return;
      }
      bool blocked = false;
      {
        const std::lock_guard<std::mutex> lock(sensors_mutex_);
        blocked = sensor->edges.blocked();
      }
      if (!blocked) {
        continue;
      }

      Detection detection;
      // All three left unset, and all three for the same reason `DetectionEvent`
      // leaves `workpiece_id` empty: a break beam observes occupancy, and
      // occupancy is the whole of what it observes.
      detection.workpiece_id = "";
      detection.workpiece_type = "";
      // POSITION IS THE THIRD THING IT CANNOT REPORT, and the one that used to be
      // filled in anyway — with the sensor's own placement in the region frame.
      // That is a measured fact about where the BEAM is, and `Detection.pose` is
      // documented as where the OBJECT is, so it answered a question nobody
      // asked with a number that looked like an answer to the one they did. For
      // `beam_c1_out` the two differ by 0.250 m across the belt, 0.050 m along it
      // and 0.030 m up: a station picking at it would reach for the housing
      // rather than for the work-piece.
      //
      // What the beam knows is that something is inside its volume. Where inside
      // — and how turned — it does not know, in simulation or on hardware, so
      // there is no pose to report and none is reported. See
      // `cite_skills/observation.hpp` for how absence is spelled and why it is
      // spelled more than once.
      cite_skills::mark_pose_unobserved(detection.pose);
      // Ground truth, which is what this scale is for: in simulation the beam is
      // a geometric test against the world's own state, and a physical
      // through-beam is a threshold on a photodiode. Neither is an estimate.
      //
      // It is confidence in the DETECTION — that the volume is occupied — and
      // there is nothing else here for it to be confidence in, now that the pose
      // is not claimed. Reading it as confidence in a position is the misreading
      // the unset pose above exists to make impossible.
      detection.confidence = 1.0;

      result->detections.push_back(detection);
      ++found;

      auto feedback = std::make_shared<Detect::Feedback>();
      feedback->detections_so_far = found;
      try {
        handle->publish_feedback(feedback);
      } catch (const std::exception & error) {
        RCLCPP_WARN(get_logger(), "could not publish feedback: %s", error.what());
      }
    }

    // Said out loud on the SUCCESS path, for the same reason the empty-region
    // case above says its piece: the caller cannot tell an unset pose from one it
    // simply forgot to read, and a `Detect` that answers "yes, something is
    // there" while silently declining the follow-up question is exactly the kind
    // of half-answer that gets acted on as a whole one.
    finish(
      make_result(
        ResultCode::SUCCESS,
        found == 0 ?
        "" :
        "occupancy only: these detections carry NO pose. A through-beam reports that "
        "its volume is occupied; it does not report where in that volume the "
        "work-piece lies, and it reports nothing at all about how the work-piece is "
        "turned. Detection.pose is therefore left unset — empty frame_id, NaN "
        "position — rather than filled with the sensor's own mounting pose, which is "
        "a fact about the beam and not about the part. Resolve the pick point from "
        "the station's own frame in L0"));
  }

  /// Wait for every sensor in the region to have reported at least once.
  ///
  /// A sensor that has never reported is not a sensor reporting CLEAR. Treating
  /// the two the same would let a bridge that is not running present itself as an
  /// empty belt, and the line would run into the piece it was told was not there.
  template<typename Handle>
  ResultCode await_first_reports(
    const std::vector<std::shared_ptr<Sensor>> & sensors, const Handle & handle)
  {
    const auto deadline =
      std::chrono::steady_clock::now() +
      std::chrono::duration_cast<std::chrono::steady_clock::duration>(
      std::chrono::duration<double>(detect_timeout_s_));

    while (true) {
      std::vector<std::string> silent;
      {
        const std::lock_guard<std::mutex> lock(sensors_mutex_);
        for (const auto & sensor : sensors) {
          if (!sensor->edges.known()) {
            silent.push_back(sensor->asset_id + " (on '" + sensor->state_topic + "')");
          }
        }
      }
      if (silent.empty()) {
        return make_result(ResultCode::SUCCESS);
      }
      if (cancelled(handle)) {
        return make_result(
          ResultCode::CANCELLED, "cancelled while waiting for a sensor to report");
      }
      if (std::chrono::steady_clock::now() >= deadline) {
        std::string names;
        for (size_t i = 0; i < silent.size(); ++i) {
          names += (i == 0 ? "" : ", ") + silent[i];
        }
        return make_result(
          ResultCode::TIMEOUT,
          "no level has arrived from: " + names + ". These are bridged topics; a beam "
          "that is running republishes its state periodically, so silence means the "
          "level is not reaching ROS rather than that the belt is clear. Reported as a "
          "fault, because an empty detection list would read as an empty belt");
      }
      std::this_thread::sleep_for(kCancelPollPeriod);
    }
  }

  std::string zone_;
  double tf_timeout_s_{5.0};
  double detect_timeout_s_{5.0};

  std::vector<std::shared_ptr<Sensor>> sensors_;
  //: Guards each sensor's edge detector, which the subscription callbacks write
  //: and the goal thread reads.
  std::mutex sensors_mutex_;
  cite_skills::ExclusiveGoal<rclcpp_action::GoalUUID> gate_;
  std::mutex worker_mutex_;
  std::thread worker_;
  std::atomic<bool> shutting_down_{false};
  std::atomic<bool> cancel_requested_{false};

  rclcpp_action::Server<Detect>::SharedPtr detect_server_;
  std::shared_ptr<tf2_ros::Buffer> tf_buffer_;
  std::shared_ptr<tf2_ros::TransformListener> tf_listener_;
};

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<DetectionServer>();

  if (!node->configure()) {
    RCLCPP_FATAL(
      node->get_logger(),
      "refusing to start. Failing here stops bring-up with a diagnosis rather than "
      "advertising detection that cannot work.");
    rclcpp::shutdown();
    return 1;
  }
  if (!node->activate(node)) {
    node->shutdown();
    rclcpp::shutdown();
    return 1;
  }

  // Multi-threaded because the goal thread waits on samples the executor has to
  // deliver: on a single-threaded executor a `Detect` waiting for a first report
  // would block the very callback that would have provided it, and the wait could
  // only ever end in the timeout.
  rclcpp::executors::MultiThreadedExecutor executor;
  executor.add_node(node);
  executor.spin();

  // `spin()` returns on SIGINT while a goal may still be inside its wait. Join it
  // before anything the node owns is destroyed.
  node->shutdown();
  rclcpp::shutdown();
  return 0;
}
