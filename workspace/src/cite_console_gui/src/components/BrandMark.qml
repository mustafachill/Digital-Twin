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

// The facility's mark: two offset hexagons, the physical and the virtual. The
// brand colour is identity, never state (Theme).

import QtQuick 2.9

Canvas {
  id: mark
  implicitWidth: 36
  implicitHeight: 36
  antialiasing: true

  onPaint: {
    var c = getContext("2d");
    c.reset();
    function hexagon(cx, cy, r) {
      c.beginPath();
      for (var i = 0; i < 6; ++i) {
        var a = Math.PI / 6 + i * Math.PI / 3;
        var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
        if (i === 0) { c.moveTo(x, y); } else { c.lineTo(x, y); }
      }
      c.closePath();
    }
    var r = Math.min(width, height) * 0.34;
    hexagon(width * 0.4, height * 0.5, r);
    c.fillStyle = Theme.brand;
    c.fill();
    hexagon(width * 0.62, height * 0.5, r);
    c.lineWidth = Math.max(1.5, r / 6);
    c.strokeStyle = Theme.text;
    c.stroke();
  }
}
