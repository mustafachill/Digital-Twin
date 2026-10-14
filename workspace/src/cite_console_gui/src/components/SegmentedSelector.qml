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

// A row of mutually exclusive choices. The choice shown checked is
// `checkedIndex` and nothing else (-1 for none): a click only says
// `activated(index)`, and whoever owns the selection decides. Each choice may
// carry a second line (`sublabels`), such as why it is disabled.

import QtQuick 2.9
import QtQuick.Controls 2.2

Rectangle {
  id: selector
  property var labels: []
  property var enabledChoices: []
  property var sublabels: []
  property int checkedIndex: -1
  property int segmentWidth: 88
  signal activated(int index)

  implicitWidth: row.implicitWidth + 4
  implicitHeight: 38
  radius: Theme.radiusSmall
  color: Theme.window
  border.width: 1
  border.color: Theme.controlBorder

  Row {
    id: row
    anchors.fill: parent
    anchors.margins: 2
    spacing: 2
    Repeater {
      model: selector.labels
      AbstractButton {
        id: segment
        readonly property string sublabel:
          selector.sublabels.length > index ? selector.sublabels[index] : ""
        width: selector.segmentWidth
        height: row.height
        text: modelData
        checkable: false
        checked: selector.checkedIndex === index
        enabled: selector.enabledChoices.length > index &&
          selector.enabledChoices[index] === true
        hoverEnabled: true
        onClicked: selector.activated(index)

        background: Rectangle {
          radius: Theme.radiusSmall - 2
          color: segment.checked ? Theme.selected :
            segment.down ? Theme.controlPressed :
            segment.hovered && segment.enabled ? Theme.controlHover : "transparent"
          border.width: segment.visualFocus ? 2 : 0
          border.color: Theme.brand
          Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: Column {
          spacing: -1
          Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: segment.text
            textFormat: Text.PlainText
            font.family: Theme.fontFamily
            font.pixelSize: Theme.body - 1
            font.weight: segment.checked ? Font.DemiBold : Font.Normal
            elide: Text.ElideRight
            color: segment.checked ? Theme.textOnSelected :
              segment.enabled ? Theme.text : Theme.disabledText
          }
          Text {
            visible: segment.sublabel !== ""
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: segment.sublabel
            textFormat: Text.PlainText
            font.family: Theme.fontFamily
            font.pixelSize: 10
            elide: Text.ElideRight
            color: segment.checked ? Theme.textOnSelected : Theme.disabledText
          }
        }
        // The column is centred in the segment, one line or two.
        topPadding: sublabel !== "" ? 2 : 9
      }
    }
  }
}
