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
#include <functional>
#include <memory>
#include <string>
#include <utility>

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

/// A skill server that accepts, succeeds, and counts.
template<typename ActionT>
class ImmediateServer
{
public:
  ImmediateServer(
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
        auto result = std::make_shared<typename ActionT::Result>();
        result->result.code = ResultCode::SUCCESS;
        if (fill_) {
          fill_(*result);
        }
        handle->succeed(result);
      });
  }

  int accepted() const {return accepted_;}

private:
  typename rclcpp_action::Server<ActionT>::SharedPtr server_;
  std::function<void(typename ActionT::Result &)> fill_;
  std::atomic<int> accepted_{0};
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
        // One detection, with a FULL POSE. This is the observation that makes a
        // grasp orientation-safe: a station that picks at a detected pose has
        // measured the part's yaw, and one that picks at a frame has assumed it.
        // A grasp holds a position and not an orientation (ADR-0029), so the
        // difference is the whole reason `DetectAt` sits in front of `PickAt`.
        cite_interfaces::msg::Detection seen;
        seen.workpiece_id = "detector_calls_it_this";
        seen.workpiece_type = "cube";
        seen.pose.header.frame_id = "observed_frame";
        seen.pose.pose.position.z = 0.025;
        seen.pose.pose.orientation.x = 1.0;
        seen.pose.pose.orientation.w = 0.0;
        seen.confidence = 1.0;
        result.detections.push_back(seen);
      })
  {
  }

  ImmediateServer<MoveTo> move_to;
  ImmediateServer<Pick> pick;
  ImmediateServer<Place> place;
  ImmediateServer<Detect> detect;
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

}  // namespace cite_orchestration_test
