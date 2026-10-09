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

#include "cite_console_gui/camera_client.hpp"

#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/gui_camera.pb.h>
#include <gz/msgs/stringmsg.pb.h>

#include <string>
#include <utility>

#include <gz/math/Pose3.hh>
#include <gz/msgs/Utility.hh>

namespace cite_console_gui
{

CameraClient::CameraClient(
  Done done, std::string pose_service, unsigned int timeout_ms, std::string follow_service)
: done_(std::move(done)), pose_service_(std::move(pose_service)), timeout_ms_(timeout_ms),
  follow_service_(std::move(follow_service)), worker_([this]() {run();})
{
}

CameraClient::~CameraClient()
{
  close();
  // After at most the one call in flight: `send` makes no further call once
  // `stopping_` is set.
  worker_.join();
}

void CameraClient::close()
{
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stopping_ = true;
    pending_.reset();
  }
  wake_.notify_all();
}

void CameraClient::request(const CameraCommand & command)
{
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (stopping_) {
      return;
    }
    pending_ = command;
  }
  wake_.notify_all();
}

void CameraClient::run()
{
  while (true) {
    CameraCommand command;
    {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait(lock, [this]() {return stopping_ || pending_.has_value();});
      if (stopping_) {
        return;
      }
      command = std::move(*pending_);
      pending_.reset();
    }
    const std::string problem = send(command);
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (stopping_) {
        // Going away: nobody is left to tell, and nothing more is sent.
        return;
      }
    }
    done_(problem.empty(), problem);
  }
}

std::string CameraClient::send(const CameraCommand & command)
{
  const auto unanswered = [this](const std::string & service) {
      return "View: nothing answered on " + service + " within " +
             std::to_string(timeout_ms_) + " ms; the window's CameraTracking plugin serves it.";
    };

  if (command.follow.has_value()) {
    gz::msgs::StringMsg request;
    request.set_data(*command.follow);
    gz::msgs::Boolean reply;
    bool result = false;
    if (!node_.Request(follow_service_, request, timeout_ms_, reply, result)) {
      return unanswered(follow_service_);
    }
    if (!result || !reply.data()) {
      return "View: " + follow_service_ + " refused to follow '" + *command.follow + "'.";
    }
  }

  if (command.pose.has_value()) {
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (stopping_) {
        return "";
      }
    }
    const CameraPose & pose = *command.pose;
    gz::msgs::GUICamera request;
    // Read as MinimalScene reads `<camera_pose>`: roll, pitch, yaw. A pose with
    // an orientation is a full move; CameraTracking keeps whatever part of the
    // pose a request leaves unset, and this sets both.
    gz::msgs::Set(
      request.mutable_pose(),
      gz::math::Pose3d(pose.x, pose.y, pose.z, pose.roll, pose.pitch, pose.yaw));
    gz::msgs::Boolean reply;
    bool result = false;
    if (!node_.Request(pose_service_, request, timeout_ms_, reply, result)) {
      return unanswered(pose_service_);
    }
    if (!result || !reply.data()) {
      return "View: " + pose_service_ + " refused the move.";
    }
  }
  return "";
}

}  // namespace cite_console_gui
