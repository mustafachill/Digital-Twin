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
// Every label that shows a string the console or the configuration sent is
// `Text.PlainText` (P-R05): it is shown, never interpreted as markup.
//
// COLOUR IS FOR THE ABNORMAL (ISA-101). Everything normal is grey; colour
// appears only for a FAULT or a refusal (alarm), a side that is stale, absent
// or not ready (`link_abnormal`; a side never started is normal), and a
// physical side that may be commanded (warning), and the
// console asking the operator to act (attention). Every colour is in `theme`,
// and nowhere else.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Controls.Material 2.1
import QtQuick.Layouts 1.3

// The root fills the card gz-gui puts it in (sized by the generated
// `gui.config`, 380x640), and has an implicit size equal to its minimums so it
// is never 0x0 before a parent sizes it: a 0x0 root lays the `fillHeight` body
// out with no height, and the window shows a title and nothing else.
Rectangle {
  id: panel
  anchors.fill: parent
  Layout.minimumWidth: 360
  Layout.minimumHeight: 600
  implicitWidth: Layout.minimumWidth
  implicitHeight: Layout.minimumHeight
  color: theme.background
  border.color: theme.border

  QtObject {
    id: theme
    // No name here starts with `on` and a capital: QML reads one as a signal
    // handler, refuses the assignment, and the panel is never instantiated.
    // Normal: greys only.
    readonly property color background: "#ececec"
    readonly property color surface: "#f5f5f5"
    readonly property color border: "#b8b8b8"
    readonly property color text: "#1c1c1c"
    readonly property color muted: "#5c5c5c"
    readonly property color strong: "#3a3a3a"
    readonly property color textOnStrong: "#ffffff"
    // Abnormal only.
    readonly property color alarm: "#c62828"      // FAULT, a refusal, a view failure
    readonly property color warning: "#e65100"    // a side abnormal; a physical side commanded
    readonly property color attention: "#1565c0"  // the console asks the operator to act
    readonly property color textOnColour: "#ffffff"
  }

  // The program's own speed, preselected (ADR-0071 decision 2).
  property real selectedSpeed: CellConsole.speedChoices[0]
  // A choice that stopped being allowed is not sent: the buttons that would
  // send it disable until the operator picks one that is.
  readonly property bool selectedSpeedAllowed: {
    var index = CellConsole.speedChoices.indexOf(selectedSpeed);
    return index >= 0 && CellConsole.speedChoicesEnabled[index] === true;
  }
  // The same for the twin target, whose floor ValidateThenRun applies to both
  // phases (ADR-0073).
  readonly property bool selectedSpeedAllowedForTwin: {
    var index = CellConsole.speedChoices.indexOf(selectedSpeed);
    return index >= 0 && CellConsole.twinSpeedChoicesEnabled[index] === true;
  }

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: 12
    spacing: 8

    // ----------------------------------------------------------- title, views
    Label {
      Layout.fillWidth: true
      text: "Cell console"
      font.pixelSize: 20
      font.bold: true
      color: theme.text
    }
    // The 3D view only: none of these moves a robot, so none is gated on the
    // console - only on the configuration having given the panel what it needs.
    Flow {
      Layout.fillWidth: true
      spacing: 2
      Button {
        text: "Reset view"
        flat: true
        enabled: CellConsole.resetViewEnabled
        onClicked: CellConsole.resetView()
      }
      Repeater {
        model: CellConsole.viewPresets
        Button {
          text: modelData
          flat: true
          onClicked: CellConsole.selectPreset(index)
        }
      }
      Button {
        text: "Follow robot"
        flat: true
        enabled: CellConsole.followEnabled
        onClicked: CellConsole.followRobot()
      }
    }
    Label {
      Layout.fillWidth: true
      visible: CellConsole.viewError !== ""
      text: CellConsole.viewError
      textFormat: Text.PlainText
      wrapMode: Text.WordWrap
      color: theme.alarm
    }

    ScrollView {
      id: body
      objectName: "body"
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      contentWidth: availableWidth

      ColumnLayout {
        width: body.availableWidth
        spacing: 8

        // ------------------------------------------------------------ no console
        Rectangle {
          Layout.fillWidth: true
          visible: !CellConsole.heard
          color: theme.surface
          border.color: theme.warning
          border.width: 2
          radius: 4
          implicitHeight: noConsole.implicitHeight + 16
          Label {
            id: noConsole
            anchors.fill: parent
            anchors.margins: 8
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            color: theme.text
            text: CellConsole.configError !== "" ? CellConsole.configError :
              "No console. Nothing can be sent until the console publishes its state " +
              "(./scripts/sim --pair --console)."
          }
        }

        // ---------------------------------------------------------------- status
        GridLayout {
          Layout.fillWidth: true
          columns: 2
          columnSpacing: 12
          rowSpacing: 4

          Label { text: "State"; color: theme.muted }
          Label {
            text: CellConsole.stateName
            textFormat: Text.PlainText
            font.bold: true
            color: CellConsole.faulted ? theme.alarm : theme.text
          }

          Label { text: "Step"; color: theme.muted }
          Label {
            Layout.fillWidth: true
            text: CellConsole.step !== "" ? CellConsole.step : "-"
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: theme.text
          }

          // A physical side may be commanded whenever the twin is not known to
          // be in SIM (ADR-0072 decision 2): abnormal, so coloured.
          Label { text: "Twin mode"; color: theme.muted }
          Label {
            text: CellConsole.twinMode +
              (CellConsole.physicalCommanded ? "  - the real arm may be commanded" : "")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            font.bold: CellConsole.physicalCommanded
            color: CellConsole.physicalCommanded ? theme.warning : theme.text
          }

          Label {
            visible: CellConsole.validationPhase !== ""
            text: "Phase"
            color: theme.muted
          }
          Label {
            visible: CellConsole.validationPhase !== ""
            text: CellConsole.validationPhase
            textFormat: Text.PlainText
            font.bold: true
            color: theme.text
          }

          // At the program's start, per side (ADR-0072 decision 3), and only
          // for a side that runs: the plant whenever a console is heard, the
          // real arm only where the console says its side runs.
          Label { text: "Simulation at start"; color: theme.muted }
          Label {
            text: CellConsole.heard ? (CellConsole.plantAtStart ? "yes" : "no") : "-"
            color: theme.text
          }

          Label {
            visible: CellConsole.counterpartRunning
            text: "Real arm at start"
            color: theme.muted
          }
          Label {
            visible: CellConsole.counterpartRunning
            text: CellConsole.counterpartAtStart ? "yes" : "no"
            color: theme.text
          }

          Label { text: "Sides"; color: theme.muted }
          Flow {
            Layout.fillWidth: true
            spacing: 6
            Label {
              visible: CellConsole.physicalSides.length === 0
              text: CellConsole.heard ? "all simulated" : "-"
              color: theme.text
            }
            Repeater {
              model: CellConsole.physicalSides
              // Grey while nothing may reach it; coloured once something may.
              Rectangle {
                color: CellConsole.physicalCommanded ? theme.warning : theme.strong
                radius: 3
                implicitWidth: badge.implicitWidth + 12
                implicitHeight: badge.implicitHeight + 6
                Label {
                  id: badge
                  anchors.centerIn: parent
                  color: theme.textOnStrong
                  font.bold: true
                  textFormat: Text.PlainText
                  text: modelData + " PHYSICAL"
                }
              }
            }
          }

          Label { text: "Last error"; color: theme.muted }
          Label {
            Layout.fillWidth: true
            text: CellConsole.lastError !== "" ? CellConsole.lastError : "-"
            textFormat: Text.PlainText
            color: CellConsole.lastError !== "" ? theme.alarm : theme.text
            wrapMode: Text.WordWrap
          }
        }

        // ----------------------------------------------------------- connections
        // What the panel hears of the twin boundary and each side, on its own
        // domain (health.hpp). A display: it gates nothing and stops nothing.
        ColumnLayout {
          Layout.fillWidth: true
          visible: CellConsole.healthShown
          spacing: 2
          Label {
            text: "Connections (monitoring only, not a safety function)"
            color: theme.muted
          }
          RowLayout {
            Layout.fillWidth: true
            Label { text: "Twin boundary"; color: theme.text; Layout.preferredWidth: 140 }
            Label {
              text: CellConsole.boundaryLink
              font.bold: CellConsole.boundaryLink !== "live"
              color: CellConsole.boundaryLink !== "live" ? theme.warning : theme.text
            }
          }
          Repeater {
            model: CellConsole.sideHealth
            ColumnLayout {
              Layout.fillWidth: true
              spacing: 0
              RowLayout {
                Layout.fillWidth: true
                Label {
                  Layout.preferredWidth: 140
                  text: modelData.name + (modelData.physical ? " (physical)" : "")
                  textFormat: Text.PlainText
                  color: theme.text
                }
                Label {
                  text: modelData.link +
                    (modelData.physical && modelData.link === "live" ?
                      (modelData.stationary ? ", stationary" : ", moving or unknown") : "")
                  font.bold: modelData.abnormal
                  color: modelData.abnormal ? theme.warning : theme.text
                }
              }
              Label {
                Layout.fillWidth: true
                visible: modelData.why !== ""
                text: modelData.why
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: theme.muted
                font.pixelSize: 11
              }
            }
          }
        }

        // What the fixed commands below need, said in words: the target hint,
        // the speed chosen and the real arm's floor (ADR-0071 decision 2).
        Label {
          Layout.fillWidth: true
          visible: CellConsole.heard && CellConsole.selectedTarget < 0
          wrapMode: Text.WordWrap
          text: "Choose a target to Home or Start program."
          color: theme.muted
        }
        Label {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          color: theme.text
          text: "Selected: " + panel.selectedSpeed + "× of the program's own speed" +
            (panel.selectedSpeedAllowed || !CellConsole.heard ? "" :
              " - not allowed for this target; choose another")
        }
        Label {
          Layout.fillWidth: true
          visible: CellConsole.minimumSpeedScale > 0
          wrapMode: Text.WordWrap
          color: theme.text
          text: "Real arm floor: " + CellConsole.minimumSpeedScale + "×. " +
            (CellConsole.floorApplies ?
              "It applies to this target: slower choices are disabled." :
              "It does not apply to this target.")
        }
        Label {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          color: theme.muted
          font.pixelSize: 11
          text: !CellConsole.heard ? "" :
            !CellConsole.validateThenRunOffered ?
              "Offered only when the twin target runs (both sides, the real arm ready)." :
              "One cycle on the simulation first; the twin runs only if it passed there. " +
              "Passing in simulation is not evidence that the real arm's cycle is safe: " +
              "every twin gate still applies. Needs both arms at the start and a speed " +
              "at or above the real arm floor."
        }

        // --------------------------------------------------- progress, outcome
        Label {
          Layout.fillWidth: true
          visible: CellConsole.progress !== ""
          text: CellConsole.progress
          textFormat: Text.PlainText
          wrapMode: Text.WordWrap
          color: theme.text
        }
        Label {
          Layout.fillWidth: true
          visible: CellConsole.outcome !== ""
          text: CellConsole.outcome
          textFormat: Text.PlainText
          wrapMode: Text.WordWrap
          color: theme.strong
        }
      }
    }

    // ------------------------------------------------------------- commands
    // Outside the scrolled body, with Stop below them: every command, its
    // target and speed, and the console's question when it asks one, are on
    // screen in the 380x640 card without scrolling (ADR-0071 decision 5).
    ColumnLayout {
      id: commands
      objectName: "commands"
      Layout.fillWidth: true
      spacing: 0

      // ---------------------------------------------------- operator go-ahead
      Rectangle {
        objectName: "confirmation"
        Layout.fillWidth: true
        visible: CellConsole.confirmEnabled
        color: theme.surface
        border.color: theme.attention
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
            color: theme.attention
          }
          Label {
            Layout.fillWidth: true
            // Verbatim: the operator confirms exactly this text.
            text: CellConsole.prompt
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: theme.text
          }
          RowLayout {
            Layout.fillWidth: true
            Button {
              Layout.fillWidth: true
              text: "Confirm"
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

      // Where the signal goes (ADR-0072 decision 3). The selection is the
      // plugin's (`settled_selection`): never preselected, not even when one
      // target alone is served, and cleared whenever the served set changes
      // or the console leaves (R-18). Each button re-binds its `checked`
      // after a click, so the plugin's selection, not the click, is what it
      // shows.
      RowLayout {
        Layout.fillWidth: true
        spacing: 4
        Label { text: "Target"; color: theme.muted; Layout.preferredWidth: 46 }
        Flow {
          Layout.fillWidth: true
          spacing: 0
          Repeater {
            model: CellConsole.targetChoices
            RadioButton {
              readonly property bool served: CellConsole.targetChoicesEnabled[index] === true
              autoExclusive: false
              text: modelData + (served || !CellConsole.heard ? "" : " (not running)")
              checked: CellConsole.selectedTarget === index
              enabled: served
              onClicked: {
                CellConsole.selectTarget(index);
                checked = Qt.binding(function() { return CellConsole.selectedTarget === index; });
              }
            }
          }
        }
      }

      // The speed the next request carries (ADR-0071 decision 2); the body
      // says which is selected and the real arm's floor. A choice, not a live
      // override.
      RowLayout {
        Layout.fillWidth: true
        spacing: 4
        Label { text: "Speed"; color: theme.muted; Layout.preferredWidth: 46 }
        Flow {
          Layout.fillWidth: true
          spacing: 0
          Repeater {
            model: CellConsole.speedChoices
            RadioButton {
              text: modelData + "×"
              checked: panel.selectedSpeed === modelData
              enabled: CellConsole.speedChoicesEnabled[index] === true
              onClicked: panel.selectedSpeed = modelData
            }
          }
        }
      }

      RowLayout {
        Layout.fillWidth: true
        Button {
          objectName: "startRobotButton"
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          text: "Start robot"
          enabled: CellConsole.startRobotEnabled
          onClicked: CellConsole.startRobot()
        }
        Button {
          objectName: "homeButton"
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          text: "Home"
          enabled: CellConsole.homeEnabled && panel.selectedSpeedAllowed
          onClicked: CellConsole.home(panel.selectedSpeed)
        }
      }

      RowLayout {
        Layout.fillWidth: true
        Button {
          objectName: "startProgramButton"
          Layout.fillWidth: true
          text: "Start program"
          enabled: CellConsole.startProgramEnabled && panel.selectedSpeedAllowed
          onClicked: CellConsole.startProgram(panel.selectedSpeed, cycles.value)
        }
        Label { text: "Cycles"; color: theme.muted }
        SpinBox {
          id: cycles
          Layout.preferredWidth: 120
          from: 1
          to: 1000
          value: 1
          editable: true
        }
      }

      // ADR-0073: one cycle on the simulation alone and, only if it passed
      // there in this same request, the cycles on the twin with every twin
      // gate unchanged. It carries no target. Its caveat, part of decision 5,
      // is in the body: a pass is "passed in simulation", nothing more.
      Button {
        objectName: "validateThenRunButton"
        Layout.fillWidth: true
        text: "Validate in sim, then run twin"
        enabled: CellConsole.validateThenRunEnabled && panel.selectedSpeedAllowedForTwin
        onClicked: CellConsole.validateThenRun(panel.selectedSpeed, cycles.value)
      }
    }

    // ---------------------------------------------------------------------- stop
    // Outside the scrolled body, so it is always on screen. A SOFTWARE stop over
    // the command path, never an E-stop: the label is part of ADR-0071 decision
    // 4. Not red: red is the physical E-stop's, and colour is for the abnormal.
    Button {
      objectName: "stopButton"
      Layout.fillWidth: true
      Layout.preferredHeight: 64
      text: "Stop — software stop, not an E-stop"
      font.bold: true
      enabled: CellConsole.stopEnabled
      Material.background: theme.strong
      Material.foreground: theme.textOnStrong
      onClicked: CellConsole.stop()
    }
  }
}
