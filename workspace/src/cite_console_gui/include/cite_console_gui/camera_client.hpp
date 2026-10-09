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

// The panel's "Reset view": ask the window's 3D view to move its camera, with
// no Qt and no ROS in it.
//
// WHO MOVES THE CAMERA. gz-gui 8's CameraTracking plugin, which the generated
// GUI configuration loads, serves `MOVE_TO_POSE_SERVICE` (gz.msgs.GUICamera in,
// gz.msgs.Boolean out) and moves the 3D view's user camera to the request's
// pose on its next render. gz-gui 8 has no in-process event that does this
// (gz/gui/GuiEvents.hh has none), so the service is the documented way. Its
// name is not scoped by the world; it is scoped by the gz-transport partition,
// and this client's node is in the GUI process, so it carries the process's
// GZ_PARTITION - the same one the window's CameraTracking advertises on.
//
// NOTHING HERE BLOCKS THE CALLER. `move_to` hands the pose to a worker thread
// of this object's own and returns; the worker makes the request with a
// bounded wait, so a window without CameraTracking is reported as an answer
// that did not come, never waited for on the caller's thread. A press while a
// request is in flight replaces any pose still waiting (the latest one wins).
// `done` runs on the worker thread: the owner moves it to its own.

#ifndef CITE_CONSOLE_GUI__CAMERA_CLIENT_HPP_
#define CITE_CONSOLE_GUI__CAMERA_CLIENT_HPP_

#include <condition_variable>
#include <functional>
#include <mutex>
#include <optional>
#include <string>
#include <thread>

#include <gz/transport/Node.hh>

#include "cite_console_gui/camera_pose.hpp"

namespace cite_console_gui
{

/// gz-gui 8's CameraTracking: move the user camera to a pose.
constexpr const char * MOVE_TO_POSE_SERVICE = "/gui/move_to/pose";

/// How long a request may wait for its answer, on the worker thread. The
/// service is in the same process when it exists, and answers at once; the
/// bound only decides when an absent one is reported.
constexpr unsigned int MOVE_TO_POSE_TIMEOUT_MS = 1000;

class CameraClient
{
public:
  /// `ok` is the service's answer; `detail` says what went wrong when not ok.
  using Done = std::function<void(bool ok, const std::string & detail)>;

  explicit CameraClient(
    Done done, std::string service = MOVE_TO_POSE_SERVICE,
    unsigned int timeout_ms = MOVE_TO_POSE_TIMEOUT_MS);
  ~CameraClient();

  CameraClient(const CameraClient &) = delete;
  CameraClient & operator=(const CameraClient &) = delete;

  /// Ask for the camera to move to `pose`. Returns at once.
  void move_to(const CameraPose & pose);

private:
  void run();

  Done done_;
  std::string service_;
  unsigned int timeout_ms_;
  gz::transport::Node node_;
  std::mutex mutex_;
  std::condition_variable wake_;
  std::optional<CameraPose> pending_;
  bool stopping_{false};
  std::thread worker_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CAMERA_CLIENT_HPP_
