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

#include "fake_arm.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/detect.hpp>
#include <cite_interfaces/action/move_to.hpp>
#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/msg/result_code.hpp>

namespace cite_orchestration_test
{

namespace
{

using cite_interfaces::action::Detect;
using cite_interfaces::action::MoveTo;
using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::msg::ResultCode;

/// A skill server that accepts and counts, and answers immediately unless it is
/// told to hold.
///
/// IMMEDIATE BY DEFAULT, because what most of these tests are about is sequence
/// and ownership rather than duration, and a server that took time would make them
/// slower without making them stricter.
///
/// HOLDING IS THE EXCEPTION THAT ONE PROPERTY NEEDS. A cancellation can only be
/// observed on a goal that is still running, so a test that asserts a SIBLING
/// station's goal was cancelled when another station escalated has to be able to
/// leave a goal outstanding. A held goal runs on its own thread — the accepted
/// callback is the executor's, and blocking it would stop the very cancellation
/// this exists to receive — and it ends in exactly one of three ways: cancelled,
/// released, or aborted when the fixture is torn down. It never simply leaks,
/// which is why the destructor joins.
template<typename ActionT>
class FixtureServer
{
public:
  FixtureServer(
    const rclcpp::Node::SharedPtr & node, const std::string & action,
    std::function<void(typename ActionT::Result &)> fill = nullptr)
  : fill_(std::move(fill))
  {
    server_ = rclcpp_action::create_server<ActionT>(
      node, action,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const typename ActionT::Goal>) {
        ++accepted_;
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](const std::shared_ptr<rclcpp_action::ServerGoalHandle<ActionT>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [this](const std::shared_ptr<rclcpp_action::ServerGoalHandle<ActionT>> handle) {
        if (!holding_.load()) {
          handle->succeed(answer());
          return;
        }
        const std::lock_guard<std::mutex> lock(mutex_);
        if (stopping_.load()) {
          // The fixture is going away. Tested UNDER THE LOCK the destructor takes
          // to empty `workers_`, and not before it: a goal accepted between the
          // flag and the swap would otherwise re-populate the vector after it had
          // been drained, and `~FixtureServer` would destroy it holding a joinable
          // thread. Answered rather than dropped, so `rclcpp_action` is not left
          // with an executing goal whose server is being destroyed.
          handle->abort(answer());
          return;
        }
        workers_.emplace_back([this, handle]() {hold_until_it_ends(handle);});
      });
  }

  ~FixtureServer()
  {
    std::vector<std::thread> workers;
    {
      // The flag and the swap under ONE lock, because the accepted-goal callback
      // reads the flag under the same one. Setting it outside would leave the
      // window this closes: accept sees "not stopping", the destructor drains,
      // accept then pushes a thread into a vector that is about to be destroyed.
      const std::lock_guard<std::mutex> lock(mutex_);
      stopping_.store(true);
      workers.swap(workers_);
    }
    for (auto & worker : workers) {
      if (worker.joinable()) {
        worker.join();
      }
    }
  }

  FixtureServer(const FixtureServer &) = delete;
  FixtureServer & operator=(const FixtureServer &) = delete;

  int accepted() const {return accepted_;}

  /// How many goals this server saw a cancellation through to the end.
  ///
  /// Counted on the SERVER side on purpose. What is under test is whether the
  /// tree's halt reached the far side of the action; a client-side count would be
  /// the leaf agreeing with itself.
  int cancelled() const {return cancelled_;}

  /// What this server answers from now on. Atomic because the executor thread
  /// reads it while the test thread sets it.
  void set_code(uint8_t code) {code_.store(code);}

  /// Whether goals accepted from now on are held open rather than answered.
  void hold(bool holding) {holding_.store(holding);}

private:
  std::shared_ptr<typename ActionT::Result> answer()
  {
    auto result = std::make_shared<typename ActionT::Result>();
    result->result.code = code_.load();
    if (fill_) {
      fill_(*result);
    }
    return result;
  }

  void hold_until_it_ends(
    const std::shared_ptr<rclcpp_action::ServerGoalHandle<ActionT>> & handle)
  {
    while (rclcpp::ok() && !stopping_.load()) {
      if (handle->is_canceling()) {
        ++cancelled_;
        handle->canceled(answer());
        return;
      }
      if (!holding_.load()) {
        handle->succeed(answer());
        return;
      }
      // A POLL, NOT A SCHEDULE. Nothing is sequenced by it: it is how often this
      // thread looks at a flag two other threads write.
      std::this_thread::sleep_for(std::chrono::milliseconds(2));
    }
    // The fixture is going away with the goal still open. Ended rather than
    // abandoned, so `rclcpp_action` is not left holding an executing goal while
    // its server is destroyed.
    handle->abort(answer());
  }

  typename rclcpp_action::Server<ActionT>::SharedPtr server_;
  std::function<void(typename ActionT::Result &)> fill_;
  std::atomic<int> accepted_{0};
  std::atomic<int> cancelled_{0};
  std::atomic<uint8_t> code_{ResultCode::SUCCESS};
  std::atomic<bool> holding_{false};
  //: Atomic because the worker threads poll it without the lock, and WRITTEN
  //: under `mutex_` because the accepted-goal callback reads it under the lock
  //: that also guards `workers_` — the two decisions have to be one.
  std::atomic<bool> stopping_{false};
  std::mutex mutex_;
  std::vector<std::thread> workers_;
};

}  // namespace

const char * const kFixturePrefix = "/line_nodes_test";

struct FakeArm::Servers
{
  Servers(const rclcpp::Node::SharedPtr & node, const std::string & asset)
  : move_to(node, FakeArm::prefix(asset) + "/move_to"),
    pick(node, FakeArm::prefix(asset) + "/pick"),
    place(node, FakeArm::prefix(asset) + "/place"),
    detect(
      node, FakeArm::prefix(asset) + "/detect",
      [](Detect::Result & result) {
        // One detection, carrying NO POSE — which is what the only detector this
        // project has actually reports.
        //
        // It used to return a full pose, with a comment calling it "the
        // observation that makes a grasp orientation-safe". No detector ever
        // produced one. The zone detects with break beams; a through-beam knows
        // that something crossed it and nothing about where along the beam, and
        // `detection_server` now says so by marking the pose unobserved. A
        // fixture that returned a pose the real server cannot was testing a
        // branch the line never takes and leaving the branch it always takes
        // uncovered — so `PickAt`'s fall back to the station's L0 frame, which is
        // the whole of how the line picks today, was exercised by nothing.
        //
        // LEFT DEFAULT-CONSTRUCTED rather than filled with the NaN pattern
        // `cite_skills::mark_pose_unobserved` writes. Calling that would tie this
        // fixture to the convention it is imitating, which is what a fixture
        // should do — but `cite_skills` exports no include directory, so nothing
        // outside it can call the function. A default `PoseStamped` has an empty
        // frame_id, which is what every consumer tests first and what the real
        // server also produces, so the branch under test is the same one. The
        // stronger case — a frame set over NaN components — needs that export and
        // is reported rather than hand-rolled here.
        cite_interfaces::msg::Detection seen;
        seen.workpiece_id = "detector_calls_it_this";
        seen.workpiece_type = "cube";
        seen.confidence = 1.0;
        result.detections.push_back(seen);
      })
  {
  }

  FixtureServer<MoveTo> move_to;
  FixtureServer<Pick> pick;
  FixtureServer<Place> place;
  FixtureServer<Detect> detect;
};

FakeArm::FakeArm(const rclcpp::Node::SharedPtr & node, const std::string & asset)
: servers_(std::make_unique<Servers>(node, asset))
{
}

FakeArm::~FakeArm() = default;

std::string FakeArm::prefix(const std::string & asset)
{
  return std::string(kFixturePrefix) + "/" + asset;
}

int FakeArm::move_to_goals() const {return servers_->move_to.accepted();}
int FakeArm::pick_goals() const {return servers_->pick.accepted();}
int FakeArm::place_goals() const {return servers_->place.accepted();}
int FakeArm::detect_goals() const {return servers_->detect.accepted();}

int FakeArm::detect_cancellations() const {return servers_->detect.cancelled();}

void FakeArm::fail_pick_with(uint8_t code) {servers_->pick.set_code(code);}

void FakeArm::fail_move_to_with(uint8_t code) {servers_->move_to.set_code(code);}

void FakeArm::hold_detect(bool holding) {servers_->detect.hold(holding);}

}  // namespace cite_orchestration_test
