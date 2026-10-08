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

// The operator console's panel (ADR-0071 decision 5). Layout only: every
// "enabled" below is a property the plugin computes with `enabled_for`, and
// every button calls the plugin, which asks the console. Nothing here decides.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Controls.Material 2.1
import QtQuick.Layouts 1.3

Rectangle {
  id: panel
  Layout.minimumWidth: 360
  Layout.minimumHeight: 600
  color: "#fafafa"
  border.color: "#cfd8dc"

  // The program's own speed, preselected (ADR-0071 decision 2).
  property real selectedSpeed: CellConsole.speedChoices[0]
  // A choice that stopped being allowed is not sent: the buttons that would
  // send it disable until the operator picks one that is.
  readonly property bool selectedSpeedAllowed: {
    var index = CellConsole.speedChoices.indexOf(selectedSpeed);
    return index >= 0 && CellConsole.speedChoicesEnabled[index] === true;
  }

  function speedLabel(scale) {
    return scale === 1.0 ? "Original speed" : scale + "×";
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 12
    spacing: 8

    Label {
      text: "Cell console"
      font.pixelSize: 20
      font.bold: true
    }

    // ---------------------------------------------------------------- no console
    Rectangle {
      Layout.fillWidth: true
      visible: !CellConsole.heard
      color: "#fff3e0"
      border.color: "#ef6c00"
      radius: 4
      implicitHeight: noConsole.implicitHeight + 16
      Label {
        id: noConsole
        anchors.fill: parent
        anchors.margins: 8
        wrapMode: Text.WordWrap
        text: CellConsole.configError !== "" ? CellConsole.configError :
          "No console. Nothing can be sent until the console publishes its state " +
          "(./scripts/sim --pair --console)."
      }
    }

    // -------------------------------------------------------------------- status
    GridLayout {
      Layout.fillWidth: true
      columns: 2
      columnSpacing: 12
      rowSpacing: 4

      Label { text: "State"; color: "#546e7a" }
      Label {
        text: CellConsole.stateName
        font.bold: true
        color: CellConsole.stateName === "FAULT" ? "#c62828" : "#212121"
      }

      Label { text: "Step"; color: "#546e7a" }
      Label {
        Layout.fillWidth: true
        text: CellConsole.step !== "" ? CellConsole.step : "-"
        wrapMode: Text.WordWrap
      }

      Label { text: "Twin mode"; color: "#546e7a" }
      Label { text: CellConsole.twinMode }

      Label { text: "At start"; color: "#546e7a" }
      Label { text: CellConsole.heard ? (CellConsole.atStart ? "yes" : "no") : "-" }

      Label { text: "Sides"; color: "#546e7a" }
      Flow {
        Layout.fillWidth: true
        spacing: 6
        Label {
          visible: CellConsole.physicalSides.length === 0
          text: CellConsole.heard ? "all simulated" : "-"
        }
        Repeater {
          model: CellConsole.physicalSides
          Rectangle {
            color: "#b71c1c"
            radius: 3
            implicitWidth: badge.implicitWidth + 12
            implicitHeight: badge.implicitHeight + 6
            Label {
              id: badge
              anchors.centerIn: parent
              color: "white"
              font.bold: true
              text: modelData + " PHYSICAL"
            }
          }
        }
      }

      Label { text: "Last error"; color: "#546e7a" }
      Label {
        Layout.fillWidth: true
        text: CellConsole.lastError !== "" ? CellConsole.lastError : "-"
        color: CellConsole.lastError !== "" ? "#c62828" : "#212121"
        wrapMode: Text.WordWrap
      }
    }

    // ------------------------------------------------------- operator go-ahead
    Rectangle {
      Layout.fillWidth: true
      visible: CellConsole.confirmEnabled
      color: "#e3f2fd"
      border.color: "#1565c0"
      border.width: 2
      radius: 4
      implicitHeight: confirmColumn.implicitHeight + 16
      ColumnLayout {
        id: confirmColumn
        anchors.fill: parent
        anchors.margins: 8
        Label {
          text: "The console asks:"
          font.bold: true
        }
        Label {
          Layout.fillWidth: true
          // Verbatim: the operator confirms exactly this text.
          text: CellConsole.prompt
          wrapMode: Text.WordWrap
        }
        RowLayout {
          Layout.fillWidth: true
          Button {
            Layout.fillWidth: true
            text: "Confirm"
            highlighted: true
            enabled: CellConsole.confirmEnabled
            onClicked: CellConsole.confirm()
          }
          Button {
            Layout.fillWidth: true
            text: "Cancel (Stop)"
            onClicked: CellConsole.stop()
          }
        }
      }
    }

    // ------------------------------------------------------------------ requests
    Button {
      Layout.fillWidth: true
      text: "Start robot"
      enabled: CellConsole.startRobotEnabled
      onClicked: CellConsole.startRobot()
    }

    Label {
      text: "Speed" + (CellConsole.minimumSpeedScale > 0 ?
        "  (slowest allowed " + CellConsole.minimumSpeedScale + "×)" : "")
      color: "#546e7a"
    }
    Flow {
      Layout.fillWidth: true
      spacing: 2
      Repeater {
        model: CellConsole.speedChoices
        RadioButton {
          text: panel.speedLabel(modelData)
          checked: panel.selectedSpeed === modelData
          enabled: CellConsole.speedChoicesEnabled[index] === true
          onClicked: panel.selectedSpeed = modelData
        }
      }
    }

    RowLayout {
      Layout.fillWidth: true
      Label { text: "Cycles"; color: "#546e7a" }
      SpinBox {
        id: cycles
        from: 1
        to: 1000
        value: 1
        editable: true
      }
    }

    RowLayout {
      Layout.fillWidth: true
      Button {
        Layout.fillWidth: true
        text: "Home"
        enabled: CellConsole.homeEnabled && panel.selectedSpeedAllowed
        onClicked: CellConsole.home(panel.selectedSpeed)
      }
      Button {
        Layout.fillWidth: true
        text: "Start program"
        enabled: CellConsole.startProgramEnabled && panel.selectedSpeedAllowed
        onClicked: CellConsole.startProgram(panel.selectedSpeed, cycles.value)
      }
    }

    // ------------------------------------------------------- progress, outcome
    Label {
      Layout.fillWidth: true
      visible: CellConsole.progress !== ""
      text: CellConsole.progress
      wrapMode: Text.WordWrap
    }
    Label {
      Layout.fillWidth: true
      visible: CellConsole.outcome !== ""
      text: CellConsole.outcome
      wrapMode: Text.WordWrap
      color: "#37474f"
    }

    Item { Layout.fillHeight: true }

    // ---------------------------------------------------------------------- stop
    // A SOFTWARE stop over the command path, never an E-stop: the label is part
    // of ADR-0071 decision 4.
    Button {
      Layout.fillWidth: true
      Layout.preferredHeight: 64
      text: "Stop — software stop, not an E-stop"
      font.bold: true
      enabled: CellConsole.stopEnabled
      Material.background: Material.Red
      Material.foreground: "white"
      onClicked: CellConsole.stop()
    }
  }
}
