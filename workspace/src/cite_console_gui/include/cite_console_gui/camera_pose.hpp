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

// Where "Reset view" returns the 3D view, with nothing else in it: read off the
// configuration by `read_home_camera_pose` (console_config.hpp) and sent by
// `CameraClient` (camera_client.hpp), neither of which needs the other's
// dependencies.

#ifndef CITE_CONSOLE_GUI__CAMERA_POSE_HPP_
#define CITE_CONSOLE_GUI__CAMERA_POSE_HPP_

namespace cite_console_gui
{

/// A camera pose as gz-gui's MinimalScene reads `<camera_pose>`: metres and
/// radians, in the world, roll-pitch-yaw.
struct CameraPose
{
  double x{0.0};
  double y{0.0};
  double z{0.0};
  double roll{0.0};
  double pitch{0.0};
  double yaw{0.0};
};

}  // namespace cite_console_gui

#endif  // CITE_CONSOLE_GUI__CAMERA_POSE_HPP_
