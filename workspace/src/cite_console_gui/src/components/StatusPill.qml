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

// A rounded status label. `tone` is "normal" (grey), "alarm", "warning" or
// "attention" (Theme, ISA-101). Static: nothing in it moves or flashes.

import QtQuick 2.9

Rectangle {
  id: pill
  property string label: ""
  property string value: ""
  property string tone: "normal"
  property bool dot: true

  readonly property color toneColour: tone === "alarm" ? Theme.alarm :
    tone === "warning" ? Theme.warning : tone === "attention" ? Theme.attention :
    Theme.textSecondary

  implicitHeight: 28
  implicitWidth: row.implicitWidth + 20
  radius: height / 2
  color: tone === "alarm" ? Theme.alarmFill : tone === "warning" ? Theme.warningFill :
    tone === "attention" ? Theme.attentionFill : Theme.card
  border.width: 1
  border.color: tone === "alarm" ? Theme.alarmBorder : tone === "warning" ?
    Theme.warningBorder : tone === "attention" ? Theme.attentionBorder : Theme.divider
  Behavior on color { ColorAnimation { duration: Theme.normal } }
  Behavior on border.color { ColorAnimation { duration: Theme.normal } }

  Row {
    id: row
    anchors.centerIn: parent
    spacing: 7
    Rectangle {
      id: led
      visible: pill.dot
      anchors.verticalCenter: parent.verticalCenter
      width: 8
      height: 8
      radius: 4
      color: pill.toneColour
    }
    UiText {
      visible: pill.label !== ""
      anchors.verticalCenter: parent.verticalCenter
      text: pill.label
      size: Theme.caption
      color: Theme.muted
    }
    UiText {
      visible: pill.value !== ""
      anchors.verticalCenter: parent.verticalCenter
      text: pill.value
      size: Theme.caption
      strong: true
      color: pill.tone === "normal" ? Theme.text : pill.toneColour
    }
  }
}
