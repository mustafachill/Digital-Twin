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

// One card of the status rail: a title, an optional one-line summary on the
// right, and its content. In `compact` the summary alone is shown.

import QtQuick 2.9
import QtQuick.Layouts 1.3

Rectangle {
  id: card
  property string title: ""
  property string summary: ""
  property string summaryTone: "normal"
  property bool compact: false
  default property alias content: body.data

  color: Theme.card
  radius: Theme.radius
  border.width: 1
  border.color: Theme.divider
  implicitHeight: column.implicitHeight + 2 * 10
  Layout.fillWidth: true

  // A soft shadow: a darker plate below the card, no blur.
  Rectangle {
    z: -1
    anchors.fill: parent
    anchors.topMargin: 2
    anchors.bottomMargin: -2
    radius: parent.radius
    color: Theme.shadow
  }

  ColumnLayout {
    id: column
    anchors.fill: parent
    anchors.margins: 10
    spacing: 6

    RowLayout {
      Layout.fillWidth: true
      spacing: 8
      UiText {
        text: card.title.toUpperCase()
        size: Theme.caption
        strong: true
        color: Theme.muted
        font.letterSpacing: 1.0
      }
      Item { Layout.fillWidth: true }
      UiText {
        visible: card.summary !== ""
        Layout.maximumWidth: card.width * 0.6
        text: card.summary
        size: Theme.caption
        strong: true
        horizontalAlignment: Text.AlignRight
        color: card.summaryTone === "alarm" ? Theme.alarm :
          card.summaryTone === "warning" ? Theme.warning :
          card.summaryTone === "attention" ? Theme.attention : Theme.textSecondary
      }
    }
    ColumnLayout {
      id: body
      visible: !card.compact
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: 4
    }
  }
}
