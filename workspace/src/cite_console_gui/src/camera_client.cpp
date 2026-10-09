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

#include <string>
#include <utility>

#include <gz/math/Pose3.hh>
#include <gz/msgs/Utility.hh>

namespace cite_console_gui
{

CameraClient::CameraClient(Done done, std::string service, unsigned int timeout_ms)
: done_(std::move(done)), service_(std::move(service)), timeout_ms_(timeout_ms),
  worker_([this]() {run();})
{
}

CameraClient::~CameraClient()
{
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stopping_ = true;
    pending_.reset();
  }
  wake_.notify_all();
  // At most one request's bounded wait.
  worker_.join();
}

void CameraClient::move_to(const CameraPose & pose)
{
  {
    std::lock_guard<std::mutex> lock(mutex_);
    pending_ = pose;
  }
  wake_.notify_all();
}

void CameraClient::run()
{
  while (true) {
    CameraPose pose;
    {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait(lock, [this]() {return stopping_ || pending_.has_value();});
      if (stopping_) {
        return;
      }
      pose = *pending_;
      pending_.reset();
    }

    gz::msgs::GUICamera request;
    // Read as MinimalScene reads `<camera_pose>`: roll, pitch, yaw. A pose with
    // an orientation is a full move; CameraTracking keeps whatever part of the
    // pose a request leaves unset, and this sets both.
    gz::msgs::Set(
      request.mutable_pose(),
      gz::math::Pose3d(pose.x, pose.y, pose.z, pose.roll, pose.pitch, pose.yaw));
    gz::msgs::Boolean reply;
    bool result = false;
    const bool answered = node_.Request(service_, request, timeout_ms_, reply, result);

    if (!answered) {
      done_(
        false, "Reset view: nothing answered on " + service_ + " within " +
        std::to_string(timeout_ms_) + " ms; the window's CameraTracking plugin serves it.");
    } else if (!result || !reply.data()) {
      done_(false, "Reset view: " + service_ + " refused the move.");
    } else {
      done_(true, "");
    }
  }
}

}  // namespace cite_console_gui
