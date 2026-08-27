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

// L4 behaviour-tree leaves: one L3 skill each.
//
// In a header rather than beside `main` so that the leaves can be driven by a
// test against a real action server. What needed testing was not the happy path
// but the giving-up path — see `SkillNode` below — and that path was unreachable
// from outside while these lived in an anonymous namespace inside an executable.
//
// Nothing here plans a trajectory or commands a controller. Every leaf calls an
// L3 skill as a ROS 2 action, and nothing else — that separation is what lets an
// arm be swapped without touching orchestration (P9).
//
// THESE ARE NOW STATEFUL, AND THAT WAS THE PRICE OF A LINE. They used to be
// `BT::SyncActionNode`, each one spinning the node inside its own tick until its
// goal finished. One station at a time, that is honest. Three stations under a
// Parallel, it is fatal twice over: a blocking leaf stops its two siblings from
// being ticked at all, and a second leaf spinning a node another leaf is already
// spinning is not allowed. So a leaf now sends its goal in `onStart`, returns
// RUNNING, and polls in `onRunning` without ever spinning anything. The node is
// spun by an executor on its own thread — see `line_orchestrator.cpp`, and see
// the note on `Context::node`, which is where that requirement is written down.
//
// THE GIVING-UP RULE IS UNCHANGED AND MUST STAY THAT WAY. Every path that
// abandons a goal cancels it first and waits for it to actually end. Returning
// FAILURE while the goal is still EXECUTING is not "giving up" — it is losing
// track of a moving arm, and because the skill servers admit one goal at a time
// the recovery branch's next goal is then *rejected* while the abandoned one
// still runs. That made the recovery branch unreachable, for a reason that
// appeared in no file. `BT::SyncActionNode` had no halt, which is what made this
// subtle; `BT::StatefulActionNode` does, so the rule now also has a place to
// live for the case where a sibling's failure halts this leaf mid-goal.

#ifndef CITE_ORCHESTRATION__SKILL_NODES_HPP_
#define CITE_ORCHESTRATION__SKILL_NODES_HPP_

#include <chrono>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <utility>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/exceptions.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/detect.hpp>
#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/action/transfer.hpp>
#include <cite_interfaces/msg/result_code.hpp>
// L3's rule for reading the unobserved-pose convention, beside its rule for
// writing one. Downward and therefore legal; see `PickAt::onStart`.
#include <cite_skills/observation.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>

#include "behaviortree_cpp/bt_factory.h"

namespace cite_orchestration
{

using cite_interfaces::action::Detect;
using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::action::Transfer;
using cite_interfaces::msg::ResultCode;

/// Where a leaf records the code its skill came back with.
///
/// A blackboard key rather than a port, and a named constant rather than a
/// string written twice. It lives on the subtree's OWN blackboard, and in
/// BT.CPP v4 a subtree's blackboard is private to it — so this is per station by
/// construction, and one station's failure cannot be read as another's. That is
/// the difference between this and the "blackboard as a global store" that L4
/// names as a failure mode.
///
/// The recovery leaf reads it and chooses from `recovery_policy.hpp`. It is a
/// CODE. `ResultCode.detail` is prose for a person and nothing parses it.
constexpr char kLastResultCode[] = "last_result_code";

/// Shared context every leaf needs. Passed in rather than looked up, so a leaf
/// cannot quietly acquire a dependency nobody declared.
struct Context
{
  /// The node the leaves' action clients live on.
  ///
  /// IT MUST BE SPUN BY AN EXECUTOR ON ANOTHER THREAD. No leaf spins it: a leaf
  /// polls its futures and returns. Nothing here works if nobody is spinning,
  /// and a leaf would simply sit at RUNNING for ever, which is a failure that
  /// looks exactly like a skill server taking a long time.
  rclcpp::Node::SharedPtr node;

  //: How long a skill may take before this leaf gives up on it. A FAILURE
  //: deadline, never a schedule: nothing waits for it in order to proceed, and
  //: reaching it is the failure rather than the plan.
  std::chrono::seconds skill_deadline{180};

  //: How long to wait for a server to appear, for it to acknowledge a
  //: cancellation, and for an abandoned goal to reach a terminal state. Also a
  //: failure deadline, and expiry is reported rather than proceeded past.
  std::chrono::seconds cancel_deadline{30};

  /// Action clients, kept between cycles.
  ///
  /// A line ticks the same station cycle for as long as it runs, and building a
  /// fresh client for every goal means re-running discovery for every goal. The
  /// map is keyed by action name because one action name has exactly one type —
  /// that is what an action name IS — so the cast back out is sound.
  ///
  /// Shared through a `shared_ptr` so that a `Context` copied into each leaf at
  /// registration shares one cache rather than accumulating one per leaf.
  std::shared_ptr<std::map<std::string, std::shared_ptr<void>>> clients{
    std::make_shared<std::map<std::string, std::shared_ptr<void>>>()};
};

/// Base for a leaf that calls one L3 action.
template<typename ActionT>
class SkillNode : public BT::StatefulActionNode
{
public:
  SkillNode(const std::string & name, const BT::NodeConfig & config, Context context)
  : BT::StatefulActionNode(name, config), context_(std::move(context))
  {
  }

protected:
  using GoalHandle = typename rclcpp_action::ClientGoalHandle<ActionT>::SharedPtr;
  using Client = typename rclcpp_action::Client<ActionT>::SharedPtr;
  using WrappedResult = typename rclcpp_action::ClientGoalHandle<ActionT>::WrappedResult;

  /// Start a goal. Call from `onStart`; returns RUNNING when it is on its way.
  BT::NodeStatus begin(const std::string & action_name, const typename ActionT::Goal & goal)
  {
    action_name_ = action_name;
    handle_.reset();
    result_.reset();
    started_at_ = now();

    client_ = client_for(action_name);
    if (!client_->action_server_is_ready()) {
      // Not fatal yet: a station may tick before its arm's skill server has
      // finished coming up. Polled in `onRunning` against the same failure
      // deadline everything else uses, rather than slept on.
      goal_ = goal;
      waiting_for_server_ = true;
      return BT::NodeStatus::RUNNING;
    }
    return dispatch(goal);
  }

  /// Poll the goal. Call from `onRunning`.
  BT::NodeStatus poll()
  {
    if (waiting_for_server_) {
      if (!client_->action_server_is_ready()) {
        if (past(elapsed_since(started_at_), context_.cancel_deadline)) {
          RCLCPP_ERROR(
            context_.node->get_logger(), "no skill server at %s", action_name_.c_str());
          // Nothing was sent, so there is nothing to cancel.
          record(ResultCode::TIMEOUT);
          return BT::NodeStatus::FAILURE;
        }
        return BT::NodeStatus::RUNNING;
      }
      waiting_for_server_ = false;
      return dispatch(goal_);
    }

    if (!handle_) {
      if (!ready(goal_future_)) {
        if (past(elapsed_since(started_at_), context_.cancel_deadline)) {
          RCLCPP_ERROR(
            context_.node->get_logger(), "%s never accepted the goal", action_name_.c_str());
          // The acceptance never arrived, so this node has no handle to cancel
          // with — but the server may still have accepted it and be executing.
          // Cancelling everything on that action is the only way to be sure the
          // arm is not left moving under a goal nobody is holding.
          cancel_all();
          record(ResultCode::TIMEOUT);
          return BT::NodeStatus::FAILURE;
        }
        return BT::NodeStatus::RUNNING;
      }
      handle_ = goal_future_.get();
      if (!handle_) {
        RCLCPP_ERROR(
          context_.node->get_logger(), "%s rejected the goal", action_name_.c_str());
        record(ResultCode::PRECONDITION_FAILED);
        return BT::NodeStatus::FAILURE;
      }
      result_future_ = client_->async_get_result(handle_);
    }

    if (!ready(result_future_)) {
      if (past(elapsed_since(started_at_), context_.skill_deadline)) {
        RCLCPP_ERROR(
          context_.node->get_logger(), "%s did not finish in time", action_name_.c_str());
        abandon();
        record(ResultCode::TIMEOUT);
        return BT::NodeStatus::FAILURE;
      }
      return BT::NodeStatus::RUNNING;
    }

    result_ = result_future_.get();
    const auto outcome = result_->result->result;
    record(outcome.code);
    if (outcome.code != ResultCode::SUCCESS) {
      // The code, not the text, is what a recovery branch reacts to. v1 could
      // only retry generically because its failures were prose. The goal has
      // already reached a terminal state here, so there is nothing to cancel.
      RCLCPP_WARN(
        context_.node->get_logger(), "%s returned code %u: %s", action_name_.c_str(),
        outcome.code, outcome.detail.c_str());
      return BT::NodeStatus::FAILURE;
    }
    return BT::NodeStatus::SUCCESS;
  }

  /// The result, once `poll` has returned SUCCESS. Empty at every other point.
  const std::optional<WrappedResult> & result() const {return result_;}

  /// Cancel whatever is outstanding. Call from `onHalted`.
  ///
  /// A sibling station failing halts this one mid-goal, and an arm left running
  /// a goal nobody is holding is precisely what the giving-up rule exists to
  /// prevent. This is the one place in a leaf that blocks — bounded by
  /// `cancel_deadline` — and it can, because the executor spinning this node
  /// runs on another thread: this is the tick thread, not a callback.
  void halt_goal()
  {
    if (goal_is_outstanding()) {
      abandon();
    } else if (client_ && !waiting_for_server_) {
      cancel_all();
    }
    handle_.reset();
    result_.reset();
    waiting_for_server_ = false;
  }

  /// Whether this node is holding a goal it has not yet seen the end of.
  bool goal_is_outstanding() const {return static_cast<bool>(handle_);}

  /// Whether the goal this node is holding has already reached a terminal state.
  ///
  /// A ready result future and a handle the client has forgotten are THE SAME
  /// FACT. `rclcpp_action::Client::make_result_aware` installs a response
  /// callback that does `goal_handle->set_result(...)` and then
  /// `goal_handles_.erase(...)`, in that order — so by the time this returns true
  /// the client either has already dropped the handle or is about to, and every
  /// `Client` method that takes a handle answers with
  /// `UnknownGoalHandleError` from then on.
  ///
  /// It is a RACE and not a state. The result can arrive between this check and
  /// the next line, which is why `abandon` catches as well as asks: this is the
  /// common path, the catch is the correctness.
  bool goal_already_ended() const
  {
    return result_future_.valid() &&
           result_future_.wait_for(std::chrono::seconds(0)) == std::future_status::ready;
  }

  Context context_;

private:
  BT::NodeStatus dispatch(const typename ActionT::Goal & goal)
  {
    // Restarted here. Waiting for a server to appear and waiting for it to
    // accept are two different deadlines, and charging the first against the
    // second would make a slow-to-discover server look like one that refused to
    // answer.
    started_at_ = now();
    goal_future_ = client_->async_send_goal(goal);
    return BT::NodeStatus::RUNNING;
  }

  Client client_for(const std::string & action_name)
  {
    auto & cache = *context_.clients;
    const auto entry = cache.find(action_name);
    if (entry != cache.end()) {
      return std::static_pointer_cast<rclcpp_action::Client<ActionT>>(entry->second);
    }
    auto client = rclcpp_action::create_client<ActionT>(context_.node, action_name);
    cache[action_name] = client;
    return client;
  }

  /// Record the code this leaf's skill came back with.
  ///
  /// SUCCESS IS NOT WRITTEN TO THE BLACKBOARD, and that omission is the fix for
  /// a defect that made the recovery policy dead code (ADR-0037).
  ///
  /// This used to write unconditionally. `kLastResultCode` has exactly one
  /// reader — `RecoverFromFailure` — and the recovery branch of
  /// `line_station.xml` ran `MoveToHome` before it. So on the common path the
  /// recovery motion SUCCEEDED, wrote SUCCESS over the code the policy was about
  /// to read, `recovery_for(SUCCESS)` answered `Recovery::NONE`, the station was
  /// set back to WAITING and the enclosing `<Repeat num_cycles="-1">` tried
  /// again. `ESCALATE` and `STOP_LINE` were unreachable on that path: every
  /// failure became a retry, including `SAFETY_BLOCKED`, whose own policy comment
  /// says L4 must never treat a refusal as a transient.
  ///
  /// ADR-0037 reorders that branch so the policy decides first. THIS IS THE
  /// OTHER HALF, and it is here rather than left to the ordering because a leaf
  /// added to the branch later would silently reintroduce the defect and no
  /// test of the ordering would catch it. Together with `RecoverFromFailure`
  /// consuming the key as it reads it, the code the policy acts on is correct
  /// under ANY leaf ordering.
  ///
  /// `last_code_` is still set on success: it is this node's own memory of its
  /// own outcome, private to the instance, and nothing chooses a recovery from
  /// it.
  void record(uint8_t code)
  {
    last_code_ = code;
    if (code != ResultCode::SUCCESS && config().blackboard) {
      config().blackboard->set(kLastResultCode, static_cast<int>(code));
    }
  }

  rclcpp::Time now() const {return context_.node->get_clock()->now();}

  /// Elapsed on the NODE's clock, which honours `use_sim_time`. A cell running
  /// on simulated time and a deadline running on wall time is the mixed-time
  /// system that produces plausible, wrong results.
  ///
  /// Seconds as a double, not as an integer count: truncating to whole seconds
  /// made a two-second deadline fire somewhere in the third second, which is not
  /// a deadline anybody can reason about or test.
  double elapsed_since(const rclcpp::Time & mark) const
  {
    return (now() - mark).seconds();
  }

  static bool past(double elapsed_s, std::chrono::seconds deadline)
  {
    return elapsed_s > static_cast<double>(deadline.count());
  }

  template<typename FutureT>
  static bool ready(FutureT & future)
  {
    return future.valid() &&
           future.wait_for(std::chrono::seconds(0)) == std::future_status::ready;
  }

  /// Cancel a goal this node has given up on, and wait for it to end.
  ///
  /// Both waits are deadlines, and expiry is reported rather than ignored: a
  /// server that will not acknowledge a cancellation is a fault worth naming,
  /// and the arm may genuinely still be moving.
  ///
  /// A GOAL THAT HAS ALREADY ENDED IS NOT AN ERROR HERE. It is this function's
  /// own post-condition, arriving early. `async_cancel_goal` and
  /// `async_get_result` both throw `UnknownGoalHandleError` for a handle the
  /// client has forgotten, and the client forgets a handle the instant the result
  /// response lands — which is on the executor's thread, not this one. So the
  /// window is: the last `poll` found the result future not ready, the result
  /// arrived, and then a halt reached this leaf. Nothing caught the throw and it
  /// crossed the tick thread's stack into `std::terminate`:
  ///
  ///     terminate called after throwing an instance of
  ///       'rclcpp_action::exceptions::UnknownGoalHandleError'
  ///       Goal handle is not known to this client
  ///
  /// It was measured on 1 run in 4 of the continuous-line scenario, and it is
  /// reachable on EVERY halt — a sibling station failing, a preemption, a
  /// recovery branch starting — not only at shutdown. That is what made it worth
  /// more than a teardown note: the tree halts a leaf in order to RECOVER from
  /// something, so a crash here is a crash on the path that has to work when
  /// something else has already gone wrong.
  void abandon()
  {
    if (goal_already_ended()) {
      RCLCPP_INFO(
        context_.node->get_logger(),
        "%s: the abandoned goal had already ended, so there was nothing to cancel",
        action_name_.c_str());
      return;
    }
    try {
      auto cancel_future = client_->async_cancel_goal(handle_);
      if (cancel_future.wait_for(context_.cancel_deadline) != std::future_status::ready) {
        RCLCPP_ERROR(
          context_.node->get_logger(),
          "%s did not answer the cancellation; the abandoned goal may still be executing",
          action_name_.c_str());
        return;
      }

      // Then wait for the goal to actually END. Acknowledgement means the server
      // accepted the request, not that the arm has stopped; sending the recovery
      // branch's next goal before then races exactly the motion this cancellation
      // exists to stop.
      if (!result_future_.valid()) {
        result_future_ = client_->async_get_result(handle_);
      }
      if (result_future_.wait_for(context_.cancel_deadline) != std::future_status::ready) {
        RCLCPP_ERROR(
          context_.node->get_logger(),
          "%s acknowledged the cancellation but the goal has not ended; the arm may "
          "still be moving",
          action_name_.c_str());
        return;
      }
      RCLCPP_INFO(
        context_.node->get_logger(), "%s: abandoned goal cancelled", action_name_.c_str());
    } catch (const rclcpp_action::exceptions::UnknownGoalHandleError &) {
      // The goal ended between the check above and one of the calls in the block.
      // The arm is not moving under a goal nobody is holding — which is the whole
      // property the giving-up rule exists to establish — so this is the good
      // outcome, and it is said out loud rather than swallowed, because a leaf
      // that reports this often is a leaf whose deadline is tuned wrong.
      RCLCPP_INFO(
        context_.node->get_logger(),
        "%s: the goal reached a terminal state while it was being abandoned, so the "
        "client had already forgotten the handle and there was nothing left to cancel",
        action_name_.c_str());
    }
  }

  /// Cancel every goal on one action, for the case where no handle was received.
  void cancel_all()
  {
    auto cancel_future = client_->async_cancel_all_goals();
    if (cancel_future.wait_for(context_.cancel_deadline) != std::future_status::ready) {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "%s did not answer a blanket cancellation; a goal it accepted without telling "
        "us may still be executing",
        action_name_.c_str());
    }
  }

  std::string action_name_;
  typename ActionT::Goal goal_;
  Client client_;
  GoalHandle handle_;
  std::shared_future<GoalHandle> goal_future_;
  std::shared_future<WrappedResult> result_future_;
  std::optional<WrappedResult> result_;
  rclcpp::Time started_at_{0, 0, RCL_ROS_TIME};
  bool waiting_for_server_{false};
  uint8_t last_code_{ResultCode::SUCCESS};
};

/// Read an action name from a port, refusing an empty one.
///
/// Names arrive as data. A leaf that was given none must refuse rather than
/// invent one — the defect being kept out is a node composing
/// "/cite/<zone>/<asset>/<skill>" from a format string of its own, which this
/// project has removed from three separate files.
inline bool action_name_from(
  const BT::TreeNode & node, const rclcpp::Logger & logger, const char * leaf,
  std::string & action)
{
  const auto value = node.getInput<std::string>("action");
  if (!value || value->empty()) {
    RCLCPP_ERROR(
      logger,
      "%s was given no action name. Names come from the generated model; this node does "
      "not build one.",
      leaf);
    return false;
  }
  action = value.value();
  return true;
}

class MoveToHome : public SkillNode<MoveTo>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("action", "the MoveTo action this station's arm serves"),
    };
  }

  BT::NodeStatus onStart() override
  {
    std::string action;
    if (!action_name_from(*this, context_.node->get_logger(), "MoveToHome", action)) {
      return BT::NodeStatus::FAILURE;
    }
    MoveTo::Goal goal;
    // "home" resolves against the L0 model inside the skill server, not here:
    // where an arm rests between cycles is a fact about the facility.
    goal.named_configuration = "home";
    return begin(action, goal);
  }

  BT::NodeStatus onRunning() override {return poll();}
  void onHalted() override {halt_goal();}
};

class PickAt : public SkillNode<Pick>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("frame"),
      BT::InputPort<std::string>("action", "the Pick action this station's arm serves"),
      BT::InputPort<std::string>("workpiece", "which work-piece this station handles"),
      // Where the work-piece actually is, when something can say.
      //
      // THIS PORT IS EMPTY IN THIS CELL, AND THE FALLBACK IS THE NORMAL PATH.
      // It used to say that this port is what makes a grasp orientation-safe,
      // and that "the line uses the pose". Neither is true of any detector that
      // exists: the zone detects with break beams, a through-beam reports
      // occupancy and not position, and `Detect` now says so by leaving
      // `Detection.pose` explicitly unobserved rather than returning the
      // housing's placement. Before that, this port carried the beam's own pose
      // — for `station_transfer_1` that is 0.7267 m from arm_1 against a 0.700 m
      // envelope, so the pick failed with "inverse kinematics found no solution
      // from any of 8 seeds" and never reached a grasp at all.
      //
      // So the frame fallback below is what the line runs on today, and it
      // carries the assumption the fallback has always carried: that the part is
      // square to its frame. That is true of a part fed onto the pick table from
      // outside the cell and NOT true of one that has just been through a
      // gripper — up to 18.7 degrees of residual survives a grasp (ADR-0029,
      // docs/measurements/2026-08-25-grasp-plane-offset/). Nothing in Phase 1
      // measures that residual away; see the note on the orientation gate in
      // `line_plan.hpp`, which is escalated rather than resolved here.
      //
      // The port stays because the contract is right and a detector that can
      // answer will arrive. What is removed is the claim that one already has.
      BT::InputPort<geometry_msgs::msg::PoseStamped>(
        "pose", "where the work-piece was observed to be; falls back to `frame` when unset"),
      // How far above the station's frame the work-piece's centre sits, for the
      // frame fallback only.
      //
      // A WORK-PIECE FACT, and nothing else. This port used to be
      // `grasp_height_m` at 0.030 — the height to put the TOOL at, which is a
      // different question and one L4 has no business answering. The cell's
      // reference work-piece is a 50 mm cube resting on the frame, so its centre
      // is at 0.025; the extra 5.00 mm was this file guessing at the gripper's
      // geometry, and guessing low. `Pick.Goal.object_pose` is "where the object
      // is", the L3 skill server offsets it onto the pad plane using the end
      // effector's own declared linkage, and the two questions are now asked in
      // the two places that can answer them (P5, P9).
      BT::InputPort<double>(
        "workpiece_height_m", 0.025, "the work-piece's centre above the frame"),
      BT::InputPort<double>("approach_m", 0.10, "standoff before grasping"),
      BT::InputPort<double>("retreat_m", 0.12, "lift after grasping"),
      // The jaw width commanded on the part, and a stand-in in the same sense:
      // L0 records no work-piece geometry, so nothing can derive it yet.
      //
      // WHERE THIS NUMBER COMES FROM. Against the WORK-PIECE, which is the only
      // datum it has ever really been about: a parallel gripper evidences a grasp
      // by failing to reach where it was sent (ADR-0022), so the command has to be
      // narrower than the part. The scenario's part is a 50 mm cube, and 0.045
      // leaves 5.00 mm of margin — against the ~2.11 mm that `gripper_is_holding`
      // needs to tell a real grasp from the controller's own end-of-goal position
      // bias. Wider than the part and the jaws arrive on target and learn nothing;
      // much narrower and the jaws close through nothing at all.
      //
      // THE VALUE IS ALSO IN L0, as `default_grasp_width_m` on the end-effector
      // type, and `Pick.Goal.grasp_width_m == 0` means "use that". Sending 0 from
      // here is where this belongs and is deliberately NOT done yet: the
      // generated bring-up plan carries the default, but the launch mechanism
      // does not pass it to the skill server, so a 0 sent today resolves to no
      // width at all and closes the gripper against its effort limit. Sending the
      // number keeps the cell working; it is a duplicate until that delivery is
      // fixed, and it is named as one here rather than left to be discovered.
      BT::InputPort<double>("grasp_width_m", 0.045, "commanded jaw width on the part"),
    };
  }

  BT::NodeStatus onStart() override
  {
    std::string action;
    if (!action_name_from(*this, context_.node->get_logger(), "PickAt", action)) {
      return BT::NodeStatus::FAILURE;
    }

    Pick::Goal goal;
    const auto observed = getInput<geometry_msgs::msg::PoseStamped>("pose");
    // `cite_skills::pose_is_observed` IS THE TEST, CALLED RATHER THAN RESTATED.
    // `cite_skills/observation.hpp` holds the rule for reading the unobserved
    // convention beside the rule for writing it, so the two cannot drift; a
    // predicate spelled out again here would be exactly the drift that header
    // exists to prevent. Depending on L3 from L4 is downward and therefore legal
    // (CLAUDE.md §5), and `cite_skills` exports its include directory — so
    // this is a compile dependency rather than a comment asserting the state of
    // another package's build, which is what stood here and stopped being true.
    //
    // It is strictly stronger than the `header.frame_id.empty()` test it
    // replaces: that one admitted a pose with a frame set over NaN components and
    // handed it to the planner as an object pose. `mark_pose_unobserved` writes
    // the empty frame AND the NaNs, and this reads both.
    if (observed && cite_skills::pose_is_observed(observed.value())) {
      // Measured, not assumed — position and orientation both. NO DETECTOR IN
      // THIS CELL PRODUCES ONE. Every sensor here is a through-beam: it reports
      // occupancy, cannot know where along itself the part lies, and knows
      // nothing whatever about its yaw. `Detect` says so by leaving the pose
      // explicitly unobserved, so the fallback below is this cell's NORMAL path
      // and this branch is the contract the day a detector that measures arrives.
      goal.object_pose = observed.value();
    } else {
      const auto frame = getInput<std::string>("frame");
      if (!frame || frame->empty()) {
        RCLCPP_ERROR(
          context_.node->get_logger(),
          "PickAt has neither an observed pose nor a frame to fall back to");
        return BT::NodeStatus::FAILURE;
      }
      // The pose is a frame the station named in L0, resolved through TF. No
      // world coordinate is written here, which is what stopped v1's pick tables
      // from diverging from the cell they described.
      goal.object_pose.header.frame_id = frame.value();
      goal.object_pose.pose.position.z =
        getInput<double>("workpiece_height_m").value_or(0.025);

      // Pointing DOWN — a half turn about X. This is not cosmetic: the skill
      // stands off along the tool's own -Z, so with an identity orientation the
      // approach pose would be *below* the table rather than above it, and the
      // plan would fail with an inverse-kinematics error that says nothing about
      // orientation.
      goal.object_pose.pose.orientation.x = 1.0;
      goal.object_pose.pose.orientation.y = 0.0;
      goal.object_pose.pose.orientation.z = 0.0;
      goal.object_pose.pose.orientation.w = 0.0;
    }

    // What the skill records as held on success. Left empty, the server warns
    // about a work-piece named `''` and the line has no idea what it is carrying.
    goal.workpiece_id = getInput<std::string>("workpiece").value_or("");
    goal.approach_distance_m = getInput<double>("approach_m").value_or(0.10);
    goal.retreat_distance_m = getInput<double>("retreat_m").value_or(0.12);
    goal.grasp_width_m = getInput<double>("grasp_width_m").value_or(0.045);
    return begin(action, goal);
  }

  BT::NodeStatus onRunning() override {return poll();}
  void onHalted() override {halt_goal();}
};

class PlaceAt : public SkillNode<Place>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("frame"),
      BT::InputPort<std::string>("action", "the Place action this station's arm serves"),
      // Where the WORK-PIECE's centre is left, above the station's frame — not
      // where the tool goes. `Place.Goal.target_pose` is the object's target and
      // the L3 skill server offsets it onto the pad plane, exactly as `Pick`
      // does; this port names a height in the same terms the pick side does.
      //
      // 0.040 against a 50 mm part resting at 0.025 is a deliberate 15 mm drop:
      // the arm lets go slightly above the surface rather than pressing the part
      // into it, which is what it did while this number was read as a tool height
      // and the pad plane was a stroke-dependent distance below it.
      BT::InputPort<double>(
        "release_height_m", 0.04, "the work-piece's centre at release, above the frame"),
      BT::InputPort<double>("approach_m", 0.10, "standoff before releasing"),
      BT::InputPort<double>("retreat_m", 0.12, "lift after releasing"),
    };
  }

  BT::NodeStatus onStart() override
  {
    std::string action;
    if (!action_name_from(*this, context_.node->get_logger(), "PlaceAt", action)) {
      return BT::NodeStatus::FAILURE;
    }
    const auto frame = getInput<std::string>("frame");
    if (!frame || frame->empty()) {
      RCLCPP_ERROR(context_.node->get_logger(), "PlaceAt needs a frame");
      return BT::NodeStatus::FAILURE;
    }

    Place::Goal goal;
    goal.target_pose.header.frame_id = frame.value();
    goal.target_pose.pose.position.z = getInput<double>("release_height_m").value_or(0.04);
    // Pointing down, for the same reason Pick does: the skill stands off along
    // the tool's own -Z, so an identity orientation would put the approach below
    // the belt rather than above it.
    goal.target_pose.pose.orientation.x = 1.0;
    goal.target_pose.pose.orientation.w = 0.0;
    goal.approach_distance_m = getInput<double>("approach_m").value_or(0.10);
    goal.retreat_distance_m = getInput<double>("retreat_m").value_or(0.12);
    // Refuse to mime a place with an empty gripper: the line would believe a
    // work-piece arrived somewhere it never did, and the failure would surface
    // at the next station instead.
    goal.require_holding = true;
    return begin(action, goal);
  }

  BT::NodeStatus onRunning() override {return poll();}
  void onHalted() override {halt_goal();}
};

/// Confirm a work-piece is where this station is about to reach, before it does.
///
/// IT DOES NOT ANSWER THE ORIENTATION QUESTION, and it used to say it did:
/// "`Detection.pose` is a full `PoseStamped`, so what comes out of here carries
/// the part's yaw as observed rather than as assumed — which is what makes a
/// conveyor-mediated handoff safe against the residual rotation between the
/// jaws". That was false for every detector that exists. This zone detects with
/// break beams; a through-beam knows that something crossed it and nothing about
/// where along the beam, still less about its yaw. `Detect` now says so, leaving
/// `Detection.pose` explicitly unobserved (`cite_skills/observation.hpp`), and
/// this leaf passes that on unchanged.
///
/// So what this leaf is actually for is the OTHER half of its name: the station's
/// sensor said a part arrived, and this confirms the part is still there before
/// an arm is sent for it. An empty result is a disagreement between the trigger
/// and the detector, and it is reported as one.
///
/// The orientation question is therefore open, not answered, and what depends on
/// it is the orientation gate in `line_plan.hpp` — see the note there, which is
/// escalated rather than settled in a comment.
class DetectAt : public SkillNode<Detect>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("action", "the Detect action this station's arm serves"),
      BT::InputPort<std::string>("frame", "the TF frame the search region is centred on"),
      BT::InputPort<std::string>(
        "workpiece_type", "", "empty matches any type, as the action documents"),
      // The region searched, about the station's frame. Still a stand-in with a
      // stated reason — L0 declares no detection region for a station, so nothing
      // here can derive it, and that gap is reported rather than left to be found.
      //
      // IT WAS 0.30 m AND NO SENSOR IN THIS CELL COULD EVER FALL INSIDE IT. The
      // extent is measured ABOUT the frame, so 0.30 m is a half-extent of 0.15 m
      // (`cite_skills::inside_region`), and every break beam in the zone stands
      // 0.250 m off its station's pick frame in y. So every `Detect` this leaf
      // sent came back SUCCESS with an empty list and the detail "no sensor in
      // this zone lies inside the requested region" — which is not a report that
      // the region is empty, and `Detect.action` carries no code that separates
      // the two. A station with a trigger read that as a disagreement with its own
      // sensor and failed; a station without one read it as an idle line and
      // polled for ever. Both were the same wrong number.
      //
      // WHY 0.60 AND NOT A LARGER OR SMALLER ONE. The lower bound is forced by
      // geometry that is not ours to move: a beam housing must clear the gripper's
      // descent, and `cite_tools.validate.geometric` enforces that mechanically as
      // a corridor of 0.100 m half-width about the pick point, which a 0.040 m
      // housing can only stand outside of at more than 0.120 m. The cell's beams
      // stand at 0.250 m, off the edge of a 0.400 m belt and a 0.600 m table. So
      // the half-extent has to exceed 0.250 m, and 0.60 m gives 0.300 m — 0.050 m
      // of margin on the placement rather than an exact tie with it.
      //
      // The upper bound is the next beam along, which is 2.025 m from the nearest
      // pick frame, so anything up to about 4 m would still select exactly one
      // sensor per station. 0.60 is a long way inside that, and
      // `test/test_detection_region.py` pins BOTH bounds against the GENERATED
      // frames, reading this number out of this line rather than restating it — so
      // a layout that moves a beam out of reach of it fails a unit test in
      // milliseconds instead of a scenario in seven minutes.
      BT::InputPort<double>("region_m", 0.60, "axis-aligned extent of the search region"),
      BT::OutputPort<geometry_msgs::msg::PoseStamped>("pose", "where the part was observed"),
      BT::OutputPort<std::string>("workpiece", "what the detector called it; may be empty"),
    };
  }

  BT::NodeStatus onStart() override
  {
    std::string action;
    if (!action_name_from(*this, context_.node->get_logger(), "DetectAt", action)) {
      return BT::NodeStatus::FAILURE;
    }
    const auto frame = getInput<std::string>("frame");
    if (!frame || frame->empty()) {
      RCLCPP_ERROR(context_.node->get_logger(), "DetectAt needs a frame to search about");
      return BT::NodeStatus::FAILURE;
    }
    frame_ = frame.value();
    return send_search();
  }

  BT::NodeStatus onRunning() override
  {
    const BT::NodeStatus status = poll();
    if (status != BT::NodeStatus::SUCCESS) {
      return status;
    }

    const auto & detections = result()->result->detections;
    if (detections.empty()) {
      // ALWAYS A FAILURE, AND THIS LEAF NO LONGER LOOKS AGAIN.
      //
      // It used to, when a `require_immediate="0"` port said the station had no
      // sensor and an empty result therefore meant an idle line. That branch was
      // the Critical hang: `Detect` answers an unobserved region and an empty one
      // with the same SUCCESS and the same empty list — its own detail says "this
      // is not a report that the region is empty" — and `Detect.action` carries
      // no code separating them. So a station polling for work against a region
      // no sensor was in re-sent for ever, reported itself WORKING with occupancy
      // 0/1, and the line never started. Measured on `station_transfer_1`.
      //
      // Waiting for work is `AwaitTrigger`'s job and it does it from a sensor the
      // topology names. This leaf's job is to say WHERE the part is, and a leaf
      // that cannot see one has failed at that — loudly, in a bounded time, with
      // a code the recovery policy branches on. The port is gone rather than
      // defaulted, so the polling path cannot be re-entered by setting an
      // attribute: it does not exist.
      RCLCPP_WARN(
        context_.node->get_logger(),
        "Detect observed nothing at %s. Either there is no work-piece there, or no "
        "sensor in this zone lies inside the region searched about that frame — the "
        "action reports both the same way, so the search region and the model's sensor "
        "placement are the first two things to check",
        frame_.c_str());
      config().blackboard->set(
        kLastResultCode, static_cast<int>(ResultCode::PRECONDITION_FAILED));
      return BT::NodeStatus::FAILURE;
    }

    // The first detection, which is the only one a capacity-1 station can act
    // on. A station that could see two parts at once needs a choice policy, and
    // there is none — so it takes the one it was triggered for and the rest are
    // seen again on the next cycle.
    //
    // WRITTEN UNCONDITIONALLY, INCLUDING WHEN IT CARRIES NO OBSERVATION. A break
    // beam's detection is unobserved by construction, and it would be tempting to
    // skip the write rather than put a NaN pose on the blackboard. That is the
    // wrong way round: this subtree repeats for as long as the line runs, so
    // skipping the write leaves the PREVIOUS cycle's pose in `{detected_pose}` and
    // `PickAt` reaches for where the last part was. An unobserved pose is refused
    // by `pose_is_observed` and routes the pick to the station's L0 frame; a stale
    // one is accepted and is wrong. Writing what was observed, every time, is what
    // keeps a blackboard a record rather than a cache.
    setOutput("pose", detections.front().pose);
    setOutput("workpiece", detections.front().workpiece_id);
    return BT::NodeStatus::SUCCESS;
  }

  void onHalted() override {halt_goal();}

private:
  BT::NodeStatus send_search()
  {
    Detect::Goal goal;
    goal.region_frame = frame_;
    const double extent = getInput<double>("region_m").value_or(0.60);
    goal.region_size_m.x = extent;
    goal.region_size_m.y = extent;
    goal.region_size_m.z = extent;
    goal.workpiece_type = getInput<std::string>("workpiece_type").value_or("");
    std::string action;
    static_cast<void>(action_name_from(*this, context_.node->get_logger(), "DetectAt", action));
    return begin(action, goal);
  }

  std::string frame_;
};

/// ADR-0024's motion half: bring a held work-piece to a handoff pose and wait to
/// be released.
///
/// It is handed a POSE and a TOKEN, never a peer's identity, so this leaf — like
/// the skill it calls — never knows which robot, if any, is on the other side.
/// L4 owns the ownership transfer and the two-party confirmation; see
/// `handoff_ledger.hpp`. That split is what makes a handoff testable with one
/// arm, which is what makes it testable at all.
///
/// Reachable only on a DIRECT arm-to-arm handoff, and `line_plan.hpp` refuses
/// those until a grasp holds an orientation. It is built and tested against the
/// contract anyway, because what stands between here and a direct handoff should
/// be the measurement and not the code.
class TransferTo : public SkillNode<Transfer>
{
public:
  using SkillNode::SkillNode;

  static BT::PortsList providedPorts()
  {
    return {
      BT::InputPort<std::string>("asset"),
      BT::InputPort<std::string>("action", "the Transfer action this station's arm serves"),
      BT::InputPort<geometry_msgs::msg::PoseStamped>("pose", "the rendezvous pose"),
      BT::InputPort<std::string>("token", "the rendezvous token L4 issued"),
      BT::InputPort<std::string>("workpiece"),
      // How long the arm holds at the rendezvous before giving up. Bounded with
      // a defined outcome, per the action: on expiry the piece is STILL HELD and
      // the result is TIMEOUT, never a silent drop. The upstream robot retains
      // ownership, which is the same outcome L4's own ledger reaches, because
      // both sides implement rule 3 rather than one trusting the other.
      BT::InputPort<double>("hold_timeout_s", 30.0, "bounded hold at the rendezvous"),
    };
  }

  BT::NodeStatus onStart() override
  {
    std::string action;
    if (!action_name_from(*this, context_.node->get_logger(), "TransferTo", action)) {
      return BT::NodeStatus::FAILURE;
    }
    const auto token = getInput<std::string>("token");
    if (!token || token->empty()) {
      RCLCPP_ERROR(
        context_.node->get_logger(),
        "TransferTo was given no rendezvous token. The token is what the receiving side "
        "matches on; without one the skill would hold for a rendezvous nobody can join.");
      return BT::NodeStatus::FAILURE;
    }
    const auto pose = getInput<geometry_msgs::msg::PoseStamped>("pose");
    if (!pose || pose->header.frame_id.empty()) {
      RCLCPP_ERROR(context_.node->get_logger(), "TransferTo needs a rendezvous pose");
      return BT::NodeStatus::FAILURE;
    }

    Transfer::Goal goal;
    goal.handoff_pose = pose.value();
    goal.rendezvous_token = token.value();
    goal.workpiece_id = getInput<std::string>("workpiece").value_or("");
    goal.hold_timeout = rclcpp::Duration::from_seconds(
      getInput<double>("hold_timeout_s").value_or(30.0));
    return begin(action, goal);
  }

  BT::NodeStatus onRunning() override {return poll();}
  void onHalted() override {halt_goal();}
};

/// Report a station as blocked. The recovery branch's terminal step.
class ReportBlocked : public BT::SyncActionNode
{
public:
  ReportBlocked(
    const std::string & name, const BT::NodeConfig & config, rclcpp::Node::SharedPtr node)
  : BT::SyncActionNode(name, config), node_(std::move(node))
  {
  }

  static BT::PortsList providedPorts()
  {
    return {BT::InputPort<std::string>("asset"), BT::InputPort<std::string>("reason")};
  }

  BT::NodeStatus tick() override
  {
    RCLCPP_ERROR(
      node_->get_logger(), "station blocked at %s: %s",
      getInput<std::string>("asset").value_or("?").c_str(),
      getInput<std::string>("reason").value_or("no reason given").c_str());
    // SUCCESS: reporting the blockage is what this node was asked to do. The
    // line's state, not this tick, is what says the station is not working.
    return BT::NodeStatus::SUCCESS;
  }

private:
  rclcpp::Node::SharedPtr node_;
};

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__SKILL_NODES_HPP_
