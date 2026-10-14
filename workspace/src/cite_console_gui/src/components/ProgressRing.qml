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

// A progress ring: `value` in [0, 1], animated as it moves, with whatever is
// put inside it centred.

import QtQuick 2.9

Item {
  id: ring
  property real value: 0.0
  property real thickness: 8
  property color trackColour: Theme.divider
  property color fillColour: Theme.textSecondary
  default property alias content: centre.data
  implicitWidth: 96
  implicitHeight: 96

  property real shown: value
  Behavior on shown { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
  onShownChanged: canvas.requestPaint()
  onFillColourChanged: canvas.requestPaint()

  Canvas {
    id: canvas
    anchors.fill: parent
    antialiasing: true
    onPaint: {
      var c = getContext("2d");
      c.reset();
      var r = Math.min(width, height) / 2 - ring.thickness / 2;
      var cx = width / 2, cy = height / 2;
      c.lineWidth = ring.thickness;
      c.lineCap = "round";
      c.strokeStyle = ring.trackColour;
      c.beginPath();
      c.arc(cx, cy, r, 0, 2 * Math.PI);
      c.stroke();
      var v = Math.max(0, Math.min(1, ring.shown));
      if (v > 0) {
        c.strokeStyle = ring.fillColour;
        c.beginPath();
        c.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + v * 2 * Math.PI);
        c.stroke();
      }
    }
  }
  Item {
    id: centre
    anchors.fill: parent
  }
}
