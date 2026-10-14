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

// The alarm band (ADR-0074): shown only while the console is in FAULT or says
// a last error, in the console's own words, as plain text. INFORMATION ONLY.
// It does not flash (ISA-101).

import QtQuick 2.9
import QtQuick.Layouts 1.3

Rectangle {
  id: band
  readonly property bool shown: CellConsole.faulted || CellConsole.lastError !== ""
  visible: shown
  color: Theme.alarmFill
  implicitHeight: shown ? Math.max(44, text.implicitHeight + 20) : 0

  InputShield {}

  Rectangle {
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: 4
    color: Theme.alarm
  }
  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.alarmBorder
  }

  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: Theme.gutter + 4
    anchors.rightMargin: Theme.gutter
    spacing: 12
    Rectangle {
      Layout.preferredWidth: 22
      Layout.preferredHeight: 22
      radius: 11
      color: "transparent"
      border.width: 2
      border.color: Theme.alarm
      UiText {
        anchors.centerIn: parent
        text: "!"
        strong: true
        color: Theme.alarm
      }
    }
    UiText {
      visible: CellConsole.faulted
      text: "FAULT"
      strong: true
      size: Theme.subtitle
      color: Theme.alarm
    }
    UiText {
      id: text
      Layout.fillWidth: true
      text: CellConsole.lastError !== "" ? "Last error: " + CellConsole.lastError :
        "The console is in FAULT."
      wrapMode: Text.WordWrap
      maximumLineCount: 3
      elide: Text.ElideRight
      color: Theme.text
    }
  }
}
