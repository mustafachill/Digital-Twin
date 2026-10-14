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

// One figure of the frame's header: its caption, a note beside it, and its
// value below. `stale` dims the value: it is the last heard, not current.

import QtQuick 2.9
import QtQuick.Layouts 1.3

Column {
  property string caption: ""
  property string note: ""
  property string value: ""
  property bool stale: false
  Layout.alignment: Qt.AlignVCenter
  spacing: 0
  UiText {
    text: parent.caption.toUpperCase() + (parent.note !== "" ? " · " + parent.note : "")
    size: Theme.caption
    color: Theme.muted
    font.letterSpacing: 0.8
  }
  UiText {
    text: parent.value
    size: Theme.subtitle
    strong: true
    color: parent.stale ? Theme.muted : Theme.text
  }
}
