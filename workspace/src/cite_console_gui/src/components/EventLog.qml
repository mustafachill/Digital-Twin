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

// The last transitions of the console's state, newest first (`EventLog` in
// the plugin): time, state, step and last error. INFORMATION ONLY.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3

ListView {
  id: log
  clip: true
  spacing: 2
  model: CellConsole.eventLog
  boundsBehavior: Flickable.StopAtBounds
  ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

  delegate: Rectangle {
    width: log.width - 8
    color: index % 2 === 0 ? "transparent" : Theme.cardRaised
    radius: 6
    implicitHeight: entry.implicitHeight + 10
    ColumnLayout {
      id: entry
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.leftMargin: 8
      anchors.rightMargin: 8
      spacing: 1
      RowLayout {
        Layout.fillWidth: true
        spacing: 10
        UiText {
          text: modelData.time
          size: Theme.caption
          color: Theme.muted
        }
        UiText {
          text: modelData.state
          size: Theme.caption
          strong: true
          color: modelData.state === "FAULT" ? Theme.alarm : Theme.text
        }
        Item { Layout.fillWidth: true }
      }
      // Whole, wrapped: the Robot card shows a step in two lines at most,
      // and this is where it is read in full (T-02).
      UiText {
        Layout.fillWidth: true
        visible: modelData.step !== ""
        text: modelData.step
        size: Theme.caption
        color: Theme.textSecondary
        wrapMode: Text.WordWrap
      }
      UiText {
        Layout.fillWidth: true
        visible: modelData.lastError !== ""
        text: modelData.lastError
        size: Theme.caption
        color: Theme.alarm
        wrapMode: Text.WordWrap
      }
    }
  }

  UiText {
    anchors.centerIn: parent
    visible: log.count === 0
    text: "Nothing heard from the console yet."
    size: Theme.caption
    color: Theme.muted
  }
}
