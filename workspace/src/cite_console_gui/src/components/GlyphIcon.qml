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

// A small line icon drawn here, so that no third-party icon file is copied
// into the tree (CLAUDE.md §4). `kind` is one of: home, top, side, front,
// follow, stop.

import QtQuick 2.9

Canvas {
  id: icon
  property string kind: "home"
  property color color: Theme.text
  implicitWidth: 20
  implicitHeight: 20
  antialiasing: true
  onColorChanged: requestPaint()
  onKindChanged: requestPaint()

  onPaint: {
    var c = getContext("2d");
    var w = width, h = height, s = Math.min(w, h);
    c.reset();
    c.strokeStyle = icon.color;
    c.fillStyle = icon.color;
    c.lineWidth = Math.max(1.5, s / 12);
    c.lineJoin = "round";
    c.lineCap = "round";
    var x0 = (w - s) / 2, y0 = (h - s) / 2;
    function p(fx, fy) { return [x0 + fx * s, y0 + fy * s]; }
    function line(a, b) { c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); }
    c.beginPath();
    if (kind === "home") {
      line(p(0.15, 0.5), p(0.5, 0.17)); line(p(0.5, 0.17), p(0.85, 0.5));
      c.moveTo(p(0.27, 0.42)[0], p(0.27, 0.42)[1]);
      c.lineTo(p(0.27, 0.85)[0], p(0.27, 0.85)[1]);
      c.lineTo(p(0.73, 0.85)[0], p(0.73, 0.85)[1]);
      c.lineTo(p(0.73, 0.42)[0], p(0.73, 0.42)[1]);
      c.stroke();
    } else if (kind === "top") {
      c.rect(p(0.18, 0.18)[0], p(0.18, 0.18)[1], 0.64 * s, 0.64 * s);
      c.stroke();
      c.beginPath();
      c.arc(p(0.5, 0.5)[0], p(0.5, 0.5)[1], 0.09 * s, 0, 2 * Math.PI);
      c.fill();
    } else if (kind === "side") {
      c.rect(p(0.12, 0.3)[0], p(0.12, 0.3)[1], 0.46 * s, 0.4 * s);
      line(p(0.9, 0.5), p(0.68, 0.5)); line(p(0.68, 0.5), p(0.76, 0.42));
      line(p(0.68, 0.5), p(0.76, 0.58));
      c.stroke();
    } else if (kind === "front") {
      c.rect(p(0.3, 0.12)[0], p(0.3, 0.12)[1], 0.4 * s, 0.46 * s);
      line(p(0.5, 0.9), p(0.5, 0.68)); line(p(0.5, 0.68), p(0.42, 0.76));
      line(p(0.5, 0.68), p(0.58, 0.76));
      c.stroke();
    } else if (kind === "follow") {
      c.arc(p(0.5, 0.5)[0], p(0.5, 0.5)[1], 0.26 * s, 0, 2 * Math.PI);
      line(p(0.5, 0.06), p(0.5, 0.24)); line(p(0.5, 0.76), p(0.5, 0.94));
      line(p(0.06, 0.5), p(0.24, 0.5)); line(p(0.76, 0.5), p(0.94, 0.5));
      c.stroke();
      c.beginPath();
      c.arc(p(0.5, 0.5)[0], p(0.5, 0.5)[1], 0.07 * s, 0, 2 * Math.PI);
      c.fill();
    } else if (kind === "stop") {
      c.rect(p(0.2, 0.2)[0], p(0.2, 0.2)[1], 0.6 * s, 0.6 * s);
      c.fill();
    }
  }
}
