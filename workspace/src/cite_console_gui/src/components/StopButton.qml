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

// Stop (ADR-0071 decision 4): a SOFTWARE stop over the command path, never an
// E-stop, and labelled so - the label is part of the decision. Dark grey, not
// red: red is the physical E-stop's, and colour is for the abnormal. Always on
// screen at the deck's far right, the deck's full height. Once the console has
// accepted a Stop, and until another command is pressed, it reads "Stopped"
// in amber, keeps its subtitle, and still stops when pressed.

import QtQuick 2.9
import QtQuick.Controls 2.2

Button {
  id: control
  objectName: "stopButton"
  /// The console accepted the last Stop (`CellConsole.stoppedShown`).
  property bool stoppedShown: false
  text: (stoppedShown ? "Stopped" : "Stop") + " — software stop, not an E-stop"
  hoverEnabled: true
  // Mouse only, as every deck button (S-04).
  focusPolicy: Qt.NoFocus
  font.family: Theme.fontFamily
  font.capitalization: Font.MixedCase
  topInset: 0
  bottomInset: 0
  leftInset: 0
  rightInset: 0

  background: Rectangle {
    radius: Theme.radius
    color: control.stoppedShown ?
      (control.down ? Theme.stoppedPressed : control.hovered && control.enabled ?
      Theme.stoppedHover : Theme.stopped) :
      (control.down ? Theme.stopPressed : control.hovered && control.enabled ?
      Theme.stopHover : Theme.stop)
    opacity: control.enabled ? 1.0 : 0.55
    border.width: control.visualFocus || control.stoppedShown ? 3 : 1
    border.color: control.visualFocus ? Theme.brand :
      control.stoppedShown ? Theme.stoppedBorder : Theme.stopBorder
    Behavior on color { ColorAnimation { duration: Theme.fast } }
  }

  // The label as written above, its first word large, centred in the button.
  padding: 12
  contentItem: Item {
    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
    Column {
      id: label
      readonly property var parts: control.text.split(" — ")
      anchors.verticalCenter: parent.verticalCenter
      width: parent.width
      spacing: 6
      GlyphIcon {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 26
        height: 26
        kind: "stop"
        color: control.stoppedShown ? Theme.stoppedBorder : Theme.textOnStrong
      }
      Text {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: label.parts[0]
        textFormat: Text.PlainText
        font.family: Theme.fontFamily
        font.pixelSize: Theme.display
        font.weight: Font.Bold
        color: Theme.textOnStrong
      }
      // The rest of the label, on one line where it fits and otherwise
      // broken after its comma only: never inside "E-stop", which a word wrap
      // breaks at its hyphen (T-05).
      Text {
        id: subtitle
        objectName: "stopSubtitle"
        readonly property string whole: label.parts.slice(1).join(" — ")
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        visible: label.parts.length > 1
        text: oneLine.width <= width ? whole : whole.replace(", ", ",\n")
        textFormat: Text.PlainText
        wrapMode: Text.NoWrap
        font.family: Theme.fontFamily
        font.pixelSize: Theme.caption + 1
        color: Theme.textOnStrong
        TextMetrics {
          id: oneLine
          font: subtitle.font
          text: subtitle.whole
        }
      }
    }
  }
}
