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

// The console's question (ADR-0071), directly above the deck and only while
// it asks: its prompt VERBATIM, as plain text - the operator confirms exactly
// this - with Confirm and its cancel, which is Stop.
//
// It is never taller than `maximumHeight`, the room the frame gives it above
// the deck and below the header (S-03): a prompt longer than that scrolls
// inside the banner, and the title and both buttons stay on screen.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3

Rectangle {
  id: banner
  objectName: "confirmation"
  visible: CellConsole.confirmEnabled
  color: Theme.attentionFill
  // The room the frame leaves it; unbounded until the frame says.
  property real maximumHeight: Number.POSITIVE_INFINITY
  readonly property real naturalHeight:
    Math.max(64, title.implicitHeight + 2 + promptText.implicitHeight + 20)
  implicitHeight: Math.min(maximumHeight, naturalHeight)
  // The frame judges that a press on each reaches it (S-02).
  readonly property Item confirmButton: confirmButtonItem
  readonly property Item cancelButton: cancelButtonItem

  InputShield {}

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: 2
    color: Theme.attention
  }

  RowLayout {
    id: content
    anchors.fill: parent
    anchors.leftMargin: Theme.gutter
    anchors.rightMargin: Theme.gutter
    spacing: 16
    Rectangle {
      Layout.preferredWidth: 26
      Layout.preferredHeight: 26
      radius: 13
      color: "transparent"
      border.width: 2
      border.color: Theme.attention
      UiText {
        anchors.centerIn: parent
        text: "?"
        strong: true
        color: Theme.attention
      }
    }
    ColumnLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      Layout.topMargin: 10
      Layout.bottomMargin: 10
      spacing: 2
      UiText {
        id: title
        objectName: "confirmationTitle"
        text: "The console asks:"
        strong: true
        color: Theme.attention
      }
      Flickable {
        id: promptView
        objectName: "confirmationPrompt"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        contentWidth: width
        contentHeight: promptText.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {
          policy: promptView.contentHeight > promptView.height ?
            ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        }
        UiText {
          id: promptText
          width: promptView.width - 12
          // Verbatim: the operator confirms exactly this text.
          text: CellConsole.prompt
          wrapMode: Text.WordWrap
          color: Theme.text
        }
      }
    }
    DeckButton {
      id: confirmButtonItem
      objectName: "confirmButton"
      Layout.preferredWidth: 140
      text: "Confirm"
      enabled: CellConsole.confirmEnabled
      onClicked: CellConsole.confirm()
    }
    DeckButton {
      id: cancelButtonItem
      objectName: "cancelButton"
      Layout.preferredWidth: 140
      text: "Cancel (Stop)"
      onClicked: CellConsole.stop()
    }
  }
}
