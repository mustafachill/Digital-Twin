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

// The panel's view buttons - Reset view, the presets and Follow robot: ask the
// window's 3D view to move its camera, with no Qt and no ROS in it.
//
// WHO MOVES THE CAMERA. gz-gui 8's CameraTracking plugin, which the generated
// GUI configuration loads. It serves, among others (read off the vendor's
// libCameraTracking.so, gz-gui 8):
//   - `MOVE_TO_POSE_SERVICE` (gz.msgs.GUICamera in, gz.msgs.Boolean out): move
//     the user camera to the request's pose on its next render;
//   - `FOLLOW_SERVICE` (gz.msgs.StringMsg in, gz.msgs.Boolean out): follow the
//     named rendering node from then on (looked up by `Scene::NodeByName`); an
//     empty name stops following.
//
// `/gui/follow` IS DEPRECATED in gz-gui 8.4 (CameraTracking logs it as such)
// in favour of the `/gui/track` topic (gz.msgs.CameraTrack). It is kept here
// because, read off gz-gui 8.4.0's CameraTracking.cc, `/gui/track` cannot do
// what the panel needs: an empty `follow_target` is ignored rather than
// clearing the target, and `track_mode: NONE` leaves a camera that is already
// following on its target, so nothing sent on it stops following before a
// move to a pose. It is also a topic, which answers nothing, so a window
// without CameraTracking could not be told from one that obeyed. Revisit when
// gz-gui removes `/gui/follow` or `/gui/track` gains a way to stop.
// gz-gui 8 has no in-process event that does either (gz/gui/GuiEvents.hh has
// none), so the services are the documented way. Their names are not scoped by
// the world; they are scoped by the gz-transport partition, and this client's
// node is in the GUI process, so it carries the process's GZ_PARTITION - the
// same one the window's CameraTracking advertises on.
//
// A camera that is following a model is put back on it every frame, so a move
// to a pose would not hold: every pose this client sends is preceded by an
// empty follow, which stops any following first (`CameraCommand::to_pose`).
//
// NOTHING HERE BLOCKS THE CALLER. `request` hands the command to a worker
// thread of this object's own and returns; the worker makes each call with a
// bounded wait, so a window without CameraTracking is reported as an answer
// that did not come, never waited for on the caller's thread. A press while a
// command is in flight replaces any command still waiting (the latest one
// wins): N presses during one command are at most one more. `done` runs on the
// worker thread: the owner moves it to its own.

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

/// gz-gui 8's CameraTracking: follow a rendering node by name; an empty name
/// stops. Deprecated in gz-gui 8.4; see the header for why it is still used.
constexpr const char * FOLLOW_SERVICE = "/gui/follow";

/// How long one call may wait for its answer, on the worker thread. The
/// service is in the same process when it exists, and answers at once; the
/// bound only decides when an absent one is reported.
constexpr unsigned int MOVE_TO_POSE_TIMEOUT_MS = 1000;

/// One press of a view button: what to follow, then where to move.
struct CameraCommand
{
  /// Sent first, when set: the node to follow; empty stops following.
  std::optional<std::string> follow;
  /// Sent next, when set: the pose to move the camera to.
  std::optional<CameraPose> pose;

  /// Stop following, then move to `pose`: Reset view and every preset.
  static CameraCommand to_pose(const CameraPose & pose)
  {
    return CameraCommand{std::string(), pose};
  }

  /// Follow the rendering node `target` from now on: Follow robot.
  static CameraCommand following(const std::string & target)
  {
    return CameraCommand{target, std::nullopt};
  }
};

class CameraClient
{
public:
  /// `ok` is the services' answer; `detail` says what went wrong when not ok.
  /// Called once per command that was sent.
  using Done = std::function<void(bool ok, const std::string & detail)>;

  explicit CameraClient(
    Done done, std::string pose_service = MOVE_TO_POSE_SERVICE,
    unsigned int timeout_ms = MOVE_TO_POSE_TIMEOUT_MS,
    std::string follow_service = FOLLOW_SERVICE);
  ~CameraClient();

  CameraClient(const CameraClient &) = delete;
  CameraClient & operator=(const CameraClient &) = delete;

  /// Ask for `command`. Returns at once.
  void request(const CameraCommand & command);

  /// Stop following and move the camera to `pose`. Returns at once.
  void move_to(const CameraPose & pose) {request(CameraCommand::to_pose(pose));}

  /// What destruction does first, callable before it: drop the command still
  /// waiting, refuse any later one, and let the call in flight be the last.
  /// Returns at once; the destructor then joins after that call only.
  void close();

private:
  void run();
  /// Make one command's calls in order; the first that fails ends it. Returns
  /// what went wrong, or an empty string.
  std::string send(const CameraCommand & command);

  Done done_;
  std::string pose_service_;
  unsigned int timeout_ms_;
  std::string follow_service_;
  gz::transport::Node node_;
  std::mutex mutex_;
  std::condition_variable wake_;
  std::optional<CameraCommand> pending_;
  bool stopping_{false};
  std::thread worker_;
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CAMERA_CLIENT_HPP_
