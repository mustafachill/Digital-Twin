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

// A label and its value, one row of a rail card.

import QtQuick 2.9
import QtQuick.Layouts 1.3

RowLayout {
  property string label: ""
  property string value: ""
  property color valueColour: Theme.text
  property bool strong: false
  // Lines the value may take before it is elided; unbounded by default.
  property int maximumLineCount: 0
  Layout.fillWidth: true
  spacing: 12
  UiText {
    Layout.preferredWidth: 132
    Layout.alignment: Qt.AlignTop
    text: parent.label
    color: Theme.muted
    size: Theme.caption + 1
  }
  UiText {
    objectName: "fieldValue"
    Layout.fillWidth: true
    text: parent.value
    color: parent.valueColour
    strong: parent.strong
    wrapMode: Text.WordWrap
    maximumLineCount: parent.maximumLineCount > 0 ? parent.maximumLineCount : 1000
    elide: parent.maximumLineCount > 0 ? Text.ElideRight : Text.ElideNone
  }
}
