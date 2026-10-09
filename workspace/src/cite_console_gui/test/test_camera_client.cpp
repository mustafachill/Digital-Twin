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
#include <gz/msgs/stringmsg.pb.h>

#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include <gz/math/Pose3.hh>
#include <gz/msgs/Utility.hh>
#include <gz/transport/Node.hh>

#include "cite_console_gui/camera_client.hpp"

using cite_console_gui::CameraClient;
using cite_console_gui::CameraCommand;
using cite_console_gui::CameraPose;
using cite_console_gui::FOLLOW_SERVICE;
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

/// The fake CameraTracking: records every request, answers `accept`. Its pose
/// service can be held shut (`hold`), as a window that has not answered yet:
/// a request then waits inside it until `release`.
struct FakeCameraTracking
{
  explicit FakeCameraTracking(
    bool accept_moves, const std::string & service = MOVE_TO_POSE_SERVICE,
    const std::string & follow_service = FOLLOW_SERVICE)
  : accept(accept_moves)
  {
    EXPECT_TRUE(
      node.Advertise(service, &FakeCameraTracking::on_move_to, this)) << service;
    EXPECT_TRUE(
      node.Advertise(follow_service, &FakeCameraTracking::on_follow, this)) << follow_service;
  }

  bool on_move_to(const gz::msgs::GUICamera & request, gz::msgs::Boolean & reply)
  {
    std::unique_lock<std::mutex> lock(mutex);
    poses.push_back(request);
    received = request;
    changed.notify_all();
    changed.wait_for(lock, std::chrono::seconds(20), [this]() {return !held;});
    reply.set_data(accept);
    return true;
  }

  bool on_follow(const gz::msgs::StringMsg & request, gz::msgs::Boolean & reply)
  {
    std::lock_guard<std::mutex> lock(mutex);
    follows.push_back(request.data());
    changed.notify_all();
    reply.set_data(accept);
    return true;
  }

  /// Wait until `predicate` holds, under the lock; false on the bound.
  template<typename Predicate>
  bool wait_for(Predicate predicate)
  {
    std::unique_lock<std::mutex> lock(mutex);
    return changed.wait_for(lock, std::chrono::seconds(10), predicate);
  }

  void hold()
  {
    std::lock_guard<std::mutex> lock(mutex);
    held = true;
  }

  void release()
  {
    {
      std::lock_guard<std::mutex> lock(mutex);
      held = false;
    }
    changed.notify_all();
  }

  bool accept;
  bool held{false};
  std::mutex mutex;
  std::condition_variable changed;
  std::optional<gz::msgs::GUICamera> received;
  std::vector<gz::msgs::GUICamera> poses;
  std::vector<std::string> follows;
  gz::transport::Node node;
};

/// Distinct service names for one test, on this test's partition.
struct Services
{
  explicit Services(const std::string & test)
  : pose("/cite_test/" + test + "/move_to/pose"), follow("/cite_test/" + test + "/follow") {}
  std::string pose;
  std::string follow;
};

/// Where a pose request asked the camera to go, as x.
double x_of(const gz::msgs::GUICamera & request)
{
  return gz::msgs::Convert(request.pose()).Pos().X();
}

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
  const Services services("refusing");
  FakeCameraTracking tracking(false, services.pose, services.follow);
  Probe probe;
  CameraClient client(probe.done(), services.pose, 1000, services.follow);

  client.move_to(CameraPose{});

  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  const Answer answer = probe.answer.get();
  EXPECT_FALSE(answer.ok);
  EXPECT_NE(answer.detail.find("refused"), std::string::npos) << answer.detail;
}

TEST(CameraClient, AnAbsentServiceIsReportedNotWaitedFor)
{
  // Nothing serves these names on this partition.
  const Services services("absent");
  const std::string service = services.follow;
  Probe probe;
  CameraClient client(probe.done(), services.pose, 200, services.follow);

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
    const Services services("never");
    CameraClient client(probe.done(), services.pose, 200, services.follow);
  }
  EXPECT_EQ(probe.answer.wait_for(std::chrono::seconds(0)), std::future_status::timeout);
}

TEST(CameraClient, EveryPoseStopsFollowingFirst)
{
  // A camera that follows a model is put back on it every frame: a pose would
  // not hold unless following stops first.
  const Services services("unfollow");
  FakeCameraTracking tracking(true, services.pose, services.follow);
  Probe probe;
  CameraClient client(probe.done(), services.pose, 1000, services.follow);
  client.move_to(CameraPose{1.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  EXPECT_TRUE(probe.answer.get().ok);
  std::lock_guard<std::mutex> lock(tracking.mutex);
  EXPECT_EQ(tracking.follows, (std::vector<std::string>{""}));
  ASSERT_EQ(tracking.poses.size(), 1u);
}

TEST(CameraClient, FollowAsksForTheNamedModelAndMovesNothing)
{
  const Services services("follow");
  FakeCameraTracking tracking(true, services.pose, services.follow);
  Probe probe;
  CameraClient client(probe.done(), services.pose, 1000, services.follow);
  client.request(CameraCommand::following("picker"));
  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  EXPECT_TRUE(probe.answer.get().ok);
  std::lock_guard<std::mutex> lock(tracking.mutex);
  EXPECT_EQ(tracking.follows, (std::vector<std::string>{"picker"}));
  EXPECT_TRUE(tracking.poses.empty());
}

TEST(CameraClient, ARefusedFollowIsReportedWithTheModel)
{
  const Services services("follow_refused");
  FakeCameraTracking tracking(false, services.pose, services.follow);
  Probe probe;
  CameraClient client(probe.done(), services.pose, 1000, services.follow);
  client.request(CameraCommand::following("picker"));
  ASSERT_EQ(probe.answer.wait_for(ANSWER_WAIT), std::future_status::ready);
  const Answer answer = probe.answer.get();
  EXPECT_FALSE(answer.ok);
  EXPECT_NE(answer.detail.find("picker"), std::string::npos) << answer.detail;
}

TEST(CameraClient, PressesDuringABlockedRequestSendExactlyOneMoreWithTheLastPose)
{
  // R-03: the latest press wins. However many presses arrive while one
  // request is held, exactly two pose requests reach the window, and the
  // second carries the last pose pressed.
  const Services services("blocked");
  FakeCameraTracking tracking(true, services.pose, services.follow);
  std::mutex answers_mutex;
  std::condition_variable answered;
  int answers = 0;
  CameraClient client(
    [&](bool, const std::string &) {
      {
        std::lock_guard<std::mutex> lock(answers_mutex);
        ++answers;
      }
      answered.notify_all();
    },
    services.pose, 30000, services.follow);

  tracking.hold();
  client.move_to(CameraPose{1.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  ASSERT_TRUE(tracking.wait_for([&]() {return tracking.poses.size() == 1;}))
    << "the first request never reached the window";
  constexpr int PRESSES = 7;
  for (int press = 2; press <= PRESSES; ++press) {
    client.move_to(CameraPose{static_cast<double>(press), 0.0, 0.0, 0.0, 0.0, 0.0});
  }
  tracking.release();

  {
    std::unique_lock<std::mutex> lock(answers_mutex);
    ASSERT_TRUE(answered.wait_for(lock, ANSWER_WAIT, [&]() {return answers == 2;}));
  }
  // Nothing else is waiting: a third request would be a press sent twice.
  client.move_to(CameraPose{100.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  {
    std::unique_lock<std::mutex> lock(answers_mutex);
    ASSERT_TRUE(answered.wait_for(lock, ANSWER_WAIT, [&]() {return answers == 3;}));
  }
  std::lock_guard<std::mutex> lock(tracking.mutex);
  ASSERT_EQ(tracking.poses.size(), 3u);
  EXPECT_DOUBLE_EQ(x_of(tracking.poses[0]), 1.0);
  EXPECT_DOUBLE_EQ(x_of(tracking.poses[1]), static_cast<double>(PRESSES));
  EXPECT_DOUBLE_EQ(x_of(tracking.poses[2]), 100.0);
}

TEST(CameraClient, DestroyedDuringABlockedRequestItJoinsAfterThatRequestOnly)
{
  // R-03: going away waits for the one call in flight and sends nothing that
  // was still waiting behind it.
  const Services services("destroyed");
  FakeCameraTracking tracking(true, services.pose, services.follow);
  Probe probe;
  auto client =
    std::make_unique<CameraClient>(probe.done(), services.pose, 30000, services.follow);

  tracking.hold();
  client->move_to(CameraPose{1.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  ASSERT_TRUE(tracking.wait_for([&]() {return tracking.poses.size() == 1;}));
  client->move_to(CameraPose{2.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  client->request(CameraCommand::following("picker"));

  // Destruction's first half, which the destructor runs itself; called here
  // first so that the release below cannot overtake it.
  client->close();
  client->move_to(CameraPose{3.0, 0.0, 0.0, 0.0, 0.0, 0.0});
  std::promise<void> destroyed;
  std::future<void> done = destroyed.get_future();
  std::thread destroyer([&]() {
      client.reset();
      destroyed.set_value();
    });
  // The destructor waits on the held request alone; releasing it ends both.
  EXPECT_EQ(done.wait_for(std::chrono::milliseconds(0)), std::future_status::timeout)
    << "the destructor did not wait for the call in flight";
  tracking.release();
  EXPECT_EQ(done.wait_for(ANSWER_WAIT), std::future_status::ready);
  destroyer.join();

  std::lock_guard<std::mutex> lock(tracking.mutex);
  EXPECT_EQ(tracking.poses.size(), 1u) << "a press waiting behind it was sent";
  EXPECT_EQ(tracking.follows, (std::vector<std::string>{""}))
    << "only the held request's own unfollow was sent";
}
