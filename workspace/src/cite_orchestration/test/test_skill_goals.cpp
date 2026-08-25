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

// What these leaves actually put in a goal.
//
// An L4 leaf's whole job is to turn ports into one typed goal, so what it fills
// in IS its behaviour — and it was wrong in a way no test could see. `PickAt`
// wrote `object_pose.position.z = 0.030` into a field the action documents as
// "where the object is", against a work-piece whose centre is at 0.025. The extra
// 5.00 mm was this file guessing at where the tool should go, which is a question
// about the END EFFECTOR and not about the line; the 40-trial campaign in
// `docs/measurements/2026-08-25-grasp-plane-offset/` measured it as part of a
// 24.4 mm error that rotated the work-piece past 20 degrees in 12 of 20 trials.
//
// Driven against a real action server, in-process, for the same reason
// `test_skill_cancellation.cpp` is: what a leaf sends is only observable from the
// far side of the action, and a mock would let the goal be asserted in the shape
// this file believes it built rather than the shape that arrives.

#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>

#include <rclcpp/rclcpp.hpp>
#include <rclcpp_action/rclcpp_action.hpp>

#include <cite_interfaces/action/pick.hpp>
#include <cite_interfaces/action/place.hpp>
#include <cite_interfaces/msg/result_code.hpp>

#include "gtest/gtest.h"
#include "cite_orchestration/skill_nodes.hpp"

namespace
{

using cite_interfaces::action::Pick;
using cite_interfaces::action::Place;
using cite_interfaces::msg::ResultCode;
using cite_orchestration::Context;
using cite_orchestration::PickAt;
using cite_orchestration::PlaceAt;
using namespace std::chrono_literals;

//: Fixture names, outside `/cite/` where no generated name can land. A test that
//: stands up a fake server must not squat on an action the real cell serves: the
//: suites run concurrently on one ROS domain, and two servers on one action name
//: make each other fail in ways that read as unrelated defects.
constexpr char kPickAction[] = "/skill_goals_test/pick";
constexpr char kPlaceAction[] = "/skill_goals_test/place";

//: A frame name, by contrast, is only ever copied into a goal and read back here,
//: so the realistic one costs nothing and shows what a station actually sends.
constexpr char kFrame[] = "cell_a__table_pick__surface";

/// A server that records the goal it was sent and succeeds immediately.
///
/// Succeeding rather than hanging is deliberate: the leaf has to reach its own
/// success path for the goal it sent to be the goal a working cycle sends.
template<typename ActionT>
class RecordingServer
{
public:
  explicit RecordingServer(const std::string & action)
  : node_(std::make_shared<rclcpp::Node>("recording_skill_server_" + std::to_string(++count_)))
  {
    server_ = rclcpp_action::create_server<ActionT>(
      node_, action,
      [this](const rclcpp_action::GoalUUID &, std::shared_ptr<const typename ActionT::Goal> goal) {
        const std::lock_guard<std::mutex> lock(mutex_);
        received_ = *goal;
        return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
      },
      [](const std::shared_ptr<rclcpp_action::ServerGoalHandle<ActionT>>) {
        return rclcpp_action::CancelResponse::ACCEPT;
      },
      [](const std::shared_ptr<rclcpp_action::ServerGoalHandle<ActionT>> handle) {
        std::thread(
          [handle]() {
            auto result = std::make_shared<typename ActionT::Result>();
            result->result.code = ResultCode::SUCCESS;
            handle->succeed(result);
          }).detach();
      });

    executor_.add_node(node_);
    spinner_ = std::thread([this]() {executor_.spin();});
  }

  ~RecordingServer()
  {
    executor_.cancel();
    if (spinner_.joinable()) {
      spinner_.join();
    }
  }

  std::optional<typename ActionT::Goal> received() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return received_;
  }

private:
  static inline std::atomic<int> count_{0};
  rclcpp::Node::SharedPtr node_;
  typename rclcpp_action::Server<ActionT>::SharedPtr server_;
  rclcpp::executors::SingleThreadedExecutor executor_;
  std::thread spinner_;
  mutable std::mutex mutex_;
  std::optional<typename ActionT::Goal> received_;
};

BT::NodeConfig ports(const std::string & action)
{
  BT::NodeConfig config;
  config.blackboard = BT::Blackboard::create();
  config.input_ports["asset"] = "arm_1";
  config.input_ports["action"] = action;
  config.input_ports["frame"] = kFrame;
  config.input_ports["workpiece"] = "workpiece";
  return config;
}

Context context_for(const rclcpp::Node::SharedPtr & node)
{
  Context context;
  context.node = node;
  context.skill_deadline = 20s;
  context.cancel_deadline = 10s;
  return context;
}

}  // namespace

class SkillGoals : public ::testing::Test
{
protected:
  void SetUp() override
  {
    client_node_ = std::make_shared<rclcpp::Node>("skill_goals_test");
  }
  rclcpp::Node::SharedPtr client_node_;
};

TEST_F(SkillGoals, PickSendsTheWorkpiecesOwnHeightNotAToolHeight)
{
  RecordingServer<Pick> server(kPickAction);
  PickAt leaf("PickAt", ports(kPickAction), context_for(client_node_));
  ASSERT_EQ(leaf.tick(), BT::NodeStatus::SUCCESS);

  const auto goal = server.received();
  ASSERT_TRUE(goal.has_value()) << "the server never saw a goal, so nothing was tested";

  // 0.025, the centre of the cell's 50 mm reference cube resting on the frame —
  // and specifically NOT 0.030, which is what this leaf sent while it was
  // answering a question about the gripper that belongs one layer down. The
  // skill server offsets this onto the pad plane using the end effector's own
  // declared linkage, so a value here that anticipates the tool is now counted
  // twice.
  EXPECT_DOUBLE_EQ(goal->object_pose.pose.position.z, 0.025);
  EXPECT_EQ(goal->object_pose.header.frame_id, kFrame);
}

TEST_F(SkillGoals, PickPointsTheToolDown)
{
  // Not cosmetic: the skill stands off along the tool's own -Z, so with an
  // identity orientation the approach pose would be below the table and the plan
  // would fail with an inverse-kinematics error that says nothing about
  // orientation.
  RecordingServer<Pick> server(kPickAction);
  PickAt leaf("PickAt", ports(kPickAction), context_for(client_node_));
  ASSERT_EQ(leaf.tick(), BT::NodeStatus::SUCCESS);

  const auto goal = server.received();
  ASSERT_TRUE(goal.has_value());
  EXPECT_DOUBLE_EQ(goal->object_pose.pose.orientation.x, 1.0);
  EXPECT_DOUBLE_EQ(goal->object_pose.pose.orientation.w, 0.0);
}

TEST_F(SkillGoals, PickCommandsAWidthNarrowerThanTheWorkpiece)
{
  // A parallel gripper evidences a grasp by FAILING to reach where it was sent
  // (ADR-0022), so the command has to be narrower than the 50 mm part. This
  // bound is the one that has always been real; the bound written here until
  // now was derived from an L1 simulation plugin's own thresholds, which is a
  // layer violation that happened to produce the same number.
  RecordingServer<Pick> server(kPickAction);
  PickAt leaf("PickAt", ports(kPickAction), context_for(client_node_));
  ASSERT_EQ(leaf.tick(), BT::NodeStatus::SUCCESS);

  const auto goal = server.received();
  ASSERT_TRUE(goal.has_value());
  EXPECT_GT(goal->grasp_width_m, 0.0) << "0 means 'use the configured default', which the "
    "launch mechanism does not currently deliver, so the gripper would close on its "
    "effort limit";
  EXPECT_LT(goal->grasp_width_m, 0.050) << "a command at or above the part's own width "
    "lets the jaws arrive on target, and the skill learns nothing";
}

TEST_F(SkillGoals, PlaceSendsTheWorkpiecesTargetNotAToolTarget)
{
  // `Place.Goal.target_pose` is where the OBJECT should end up, and the skill
  // server applies the same pad-plane offset it applies to a pick. A height here
  // that anticipated the tool would be counted twice, exactly as on the pick
  // side. 0.040 against a part resting at 0.025 is a deliberate 15 mm drop.
  RecordingServer<Place> server(kPlaceAction);
  PlaceAt leaf("PlaceAt", ports(kPlaceAction), context_for(client_node_));
  ASSERT_EQ(leaf.tick(), BT::NodeStatus::SUCCESS);

  const auto goal = server.received();
  ASSERT_TRUE(goal.has_value()) << "the server never saw a goal, so nothing was tested";
  EXPECT_DOUBLE_EQ(goal->target_pose.pose.position.z, 0.040);
  EXPECT_GT(goal->target_pose.pose.position.z, 0.025)
    << "a place at or below the resting height presses the part into the surface";
}

TEST_F(SkillGoals, PlaceRefusesToMimeAPlaceWithAnEmptyGripper)
{
  RecordingServer<Place> server(kPlaceAction);
  PlaceAt leaf("PlaceAt", ports(kPlaceAction), context_for(client_node_));
  ASSERT_EQ(leaf.tick(), BT::NodeStatus::SUCCESS);

  const auto goal = server.received();
  ASSERT_TRUE(goal.has_value());
  EXPECT_TRUE(goal->require_holding) << "without this the line believes a work-piece "
    "arrived somewhere it never did, and the failure surfaces at the next station";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  rclcpp::init(argc, argv);
  const int result = RUN_ALL_TESTS();
  rclcpp::shutdown();
  return result;
}
