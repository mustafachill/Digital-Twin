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

// "Reset view" against a fake CameraTracking: a replier on the same service
// name, on a gz-transport partition of this test's own, in this process - as
// the real one is in the window's process.

#include <gtest/gtest.h>
#include <unistd.h>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/gui_camera.pb.h>

#include <chrono>
#include <cstdlib>
#include <future>
#include <mutex>
#include <optional>
#include <string>

#include <gz/math/Pose3.hh>
#include <gz/msgs/Utility.hh>
#include <gz/transport/Node.hh>

#include "cite_console_gui/camera_client.hpp"

using cite_console_gui::CameraClient;
using cite_console_gui::CameraPose;
using cite_console_gui::MOVE_TO_POSE_SERVICE;

namespace
{

// Before any node exists: gz transport reads the partition once per process,
// and a test must never reach a window or a simulator someone else has open.
const bool PRIVATE_PARTITION = []() {
    const std::string partition = "cite_test_camera_client_" + std::to_string(::getpid());
    ::setenv("GZ_PARTITION", partition.c_str(), 1);
    ::setenv("GZ_IP", "127.0.0.1", 1);
    return true;
  }();

constexpr auto ANSWER_WAIT = std::chrono::seconds(10);

struct Answer
{
  bool ok{false};
  std::string detail;
};

/// A client whose answer is a future.
struct Probe
{
  std::promise<Answer> promise;
  std::future<Answer> answer{promise.get_future()};
  std::once_flag once;

  CameraClient::Done done()
  {
    return [this](bool ok, const std::string & detail) {
             std::call_once(once, [&]() {promise.set_value(Answer{ok, detail});});
           };
  }
};

/// The fake CameraTracking: records the request, answers `accept`.
struct FakeCameraTracking
{
  explicit FakeCameraTracking(bool accept_moves, const std::string & service = MOVE_TO_POSE_SERVICE)
  : accept(accept_moves)
  {
    EXPECT_TRUE(
      node.Advertise(service, &FakeCameraTracking::on_move_to, this)) << service;
  }

  bool on_move_to(const gz::msgs::GUICamera & request, gz::msgs::Boolean & reply)
  {
    std::lock_guard<std::mutex> lock(mutex);
    received = request;
    reply.set_data(accept);
    return true;
  }

  bool accept;
  std::mutex mutex;
  std::optional<gz::msgs::GUICamera> received;
  gz::transport::Node node;
};

}  // namespace

TEST(CameraClient, TheRequestCarriesTheHomePose)
{
  ASSERT_TRUE(PRIVATE_PARTITION);
  FakeCameraTracking tracking(true);
  Probe probe;
  CameraClient client(probe.done());

  const CameraPose home{0.88, 1.24756522, 1.84284919, 0.0, 0.575958653, 1.57079633};
  client.move_to(home);

  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  const Answer answer = probe.answer.get();
  EXPECT_TRUE(answer.ok) << answer.detail;

  std::lock_guard<std::mutex> lock(tracking.mutex);
  ASSERT_TRUE(tracking.received.has_value());
  ASSERT_TRUE(tracking.received->has_pose());
  // Both parts set: CameraTracking keeps whatever part a request leaves out.
  ASSERT_TRUE(tracking.received->pose().has_position());
  ASSERT_TRUE(tracking.received->pose().has_orientation());
  const gz::math::Pose3d sent = gz::msgs::Convert(tracking.received->pose());
  const gz::math::Pose3d expected(home.x, home.y, home.z, home.roll, home.pitch, home.yaw);
  EXPECT_TRUE(sent.Pos().Equal(expected.Pos(), 1e-9)) << sent;
  EXPECT_TRUE(sent.Rot().Equal(expected.Rot(), 1e-9)) << sent;
  EXPECT_NEAR(sent.Rot().Pitch(), home.pitch, 1e-9);
  EXPECT_NEAR(sent.Rot().Yaw(), home.yaw, 1e-9);
}

TEST(CameraClient, ARefusedMoveIsReported)
{
  const std::string service = "/cite_test/refusing/move_to/pose";
  FakeCameraTracking tracking(false, service);
  Probe probe;
  CameraClient client(probe.done(), service);

  client.move_to(CameraPose{});

  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  const Answer answer = probe.answer.get();
  EXPECT_FALSE(answer.ok);
  EXPECT_NE(answer.detail.find("refused"), std::string::npos) << answer.detail;
}

TEST(CameraClient, AnAbsentServiceIsReportedNotWaitedFor)
{
  // Nothing serves this name on this partition.
  const std::string service = "/cite_test/absent/move_to/pose";
  Probe probe;
  CameraClient client(probe.done(), service, 200);

  client.move_to(CameraPose{});
  // `move_to` has returned: the wait is the worker's, never the caller's.

  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  const Answer answer = probe.answer.get();
  EXPECT_FALSE(answer.ok);
  EXPECT_NE(answer.detail.find(service), std::string::npos) << answer.detail;
  EXPECT_NE(answer.detail.find("nothing answered"), std::string::npos) << answer.detail;
}

TEST(CameraClient, ItGoesAwayWithoutBeingAsked)
{
  // No request ever made: the worker is woken and joined, not left waiting.
  Probe probe;
  {
    CameraClient client(probe.done(), "/cite_test/never/move_to/pose", 200);
  }
  EXPECT_EQ(probe.answer.wait_for(std::chrono::seconds(0)), std::future_status::timeout);
}
