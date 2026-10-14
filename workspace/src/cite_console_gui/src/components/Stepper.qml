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

// How many cycles the next request carries: at least `from`, at most `to`,
// typed or stepped.

import QtQuick 2.9
import QtQuick.Controls 2.2

Rectangle {
  id: stepper
  property int value: 1
  property int from: 1
  property int to: 1000
  implicitWidth: 132
  implicitHeight: 38
  radius: Theme.radiusSmall
  color: Theme.window
  border.width: input.activeFocus ? 2 : 1
  border.color: input.activeFocus ? Theme.brand : Theme.controlBorder

  function set(number) {
    stepper.value = Math.max(stepper.from, Math.min(stepper.to, number));
    input.text = String(stepper.value);
  }

  DeckButton {
    id: down
    objectName: "cyclesDown"
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.margins: 2
    width: 34
    implicitHeight: 34
    text: "−"
    enabled: stepper.value > stepper.from
    onClicked: stepper.set(stepper.value - 1)
  }
  TextInput {
    id: input
    anchors.left: down.right
    anchors.right: up.left
    anchors.verticalCenter: parent.verticalCenter
    horizontalAlignment: TextInput.AlignHCenter
    text: String(stepper.value)
    color: Theme.text
    selectionColor: Theme.controlPressed
    font.family: Theme.fontFamily
    font.pixelSize: Theme.subtitle
    font.weight: Font.DemiBold
    validator: IntValidator { bottom: stepper.from; top: stepper.to }
    onEditingFinished: stepper.set(parseInt(text, 10) || stepper.from)
  }
  DeckButton {
    id: up
    objectName: "cyclesUp"
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.margins: 2
    width: 34
    implicitHeight: 34
    text: "+"
    enabled: stepper.value < stepper.to
    onClicked: stepper.set(stepper.value + 1)
  }
}
