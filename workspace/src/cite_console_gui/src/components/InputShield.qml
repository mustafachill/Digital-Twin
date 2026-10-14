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

// What makes an opaque part of the frame opaque to the mouse (ADR-0074): the
// card around the panel lets every press through to the 3D view, so the
// header, the alarm band, the rail, the confirmation band and the deck each
// take the presses and the wheel that land on them, rather than orbiting or
// zooming the scene through them. The first child of each, below its content.

import QtQuick 2.9

MouseArea {
  anchors.fill: parent
  acceptedButtons: Qt.AllButtons
  onWheel: wheel.accepted = true
}
