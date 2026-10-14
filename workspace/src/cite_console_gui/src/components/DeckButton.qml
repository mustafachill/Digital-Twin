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

// A button of the command deck. `variant` is "normal" (an action: grey, the
// normal state) or "subdued" (the view buttons: quieter, they move no robot).
// Its focus ring is the brand colour (identity, not state). The label wraps
// to two lines rather than leaving the deck.

import QtQuick 2.9
import QtQuick.Controls 2.2

Button {
  id: control
  property string variant: "normal"
  property string iconKind: ""
  property bool iconOnly: false
  readonly property bool subdued: variant === "subdued"

  implicitHeight: subdued ? 40 : 44
  // Material insets its background and capitalizes its label; the deck draws
  // the whole button and keeps the label as written.
  topInset: 0
  bottomInset: 0
  leftInset: 0
  rightInset: 0
  padding: 6
  font.capitalization: Font.MixedCase
  implicitWidth: iconOnly ? 44 : Math.max(88, content.implicitWidth + 24)
  font.family: Theme.fontFamily
  font.pixelSize: subdued ? Theme.caption + 1 : Theme.body
  font.weight: subdued ? Font.Normal : Font.DemiBold
  hoverEnabled: true

  ToolTip.visible: iconOnly && hovered
  ToolTip.text: text
  ToolTip.delay: 400

  background: Rectangle {
    radius: Theme.radiusSmall
    color: !control.enabled ? (control.subdued ? "transparent" : Theme.controlDisabled) :
      control.down ? Theme.controlPressed : control.hovered ? Theme.controlHover :
      control.subdued ? "transparent" : Theme.control
    border.width: control.visualFocus ? 2 : 1
    border.color: control.visualFocus ? Theme.brand :
      control.subdued ? Theme.divider : Theme.controlBorder
    Behavior on color { ColorAnimation { duration: Theme.fast } }
  }

  contentItem: Item {
    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight
    Row {
      id: content
      anchors.centerIn: parent
      width: Math.min(implicitWidth, parent.width)
      spacing: 8
      GlyphIcon {
        id: glyph
        visible: control.iconKind !== ""
        anchors.verticalCenter: parent.verticalCenter
        width: 18
        height: 18
        kind: control.iconKind
        color: label.color
      }
      Text {
        id: label
        visible: !control.iconOnly
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(implicitWidth,
          control.availableWidth - (glyph.visible ? glyph.width + content.spacing : 0))
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignHCenter
        color: !control.enabled ? Theme.disabledText :
          control.subdued ? Theme.textSecondary : Theme.text
        Behavior on color { ColorAnimation { duration: Theme.fast } }
      }
    }
  }
}
