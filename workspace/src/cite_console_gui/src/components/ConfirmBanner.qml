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

import QtQuick 2.9
import QtQuick.Layouts 1.3

Rectangle {
  id: banner
  objectName: "confirmation"
  visible: CellConsole.confirmEnabled
  color: Theme.attentionFill
  implicitHeight: Math.max(64, content.implicitHeight + 20)

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
      spacing: 2
      UiText {
        text: "The console asks:"
        strong: true
        color: Theme.attention
      }
      UiText {
        Layout.fillWidth: true
        // Verbatim: the operator confirms exactly this text.
        text: CellConsole.prompt
        wrapMode: Text.WordWrap
        color: Theme.text
      }
    }
    DeckButton {
      objectName: "confirmButton"
      Layout.preferredWidth: 140
      text: "Confirm"
      enabled: CellConsole.confirmEnabled
      onClicked: CellConsole.confirm()
    }
    DeckButton {
      objectName: "cancelButton"
      Layout.preferredWidth: 140
      text: "Cancel (Stop)"
      onClicked: CellConsole.stop()
    }
  }
}
