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

// The status rail (ADR-0074). INFORMATION ONLY: nothing here is clickable.
// Cards in order of priority - the robot, the running request's progress,
// the sides, the twin's fidelity and the event log. At the primary display
// every card fits without scrolling the rail (T-02); the rail scrolls only
// when the window is shorter, and then shows its scroll bar. The event log takes the room left below the
// other cards, never less than a few rows, and scrolls inside itself.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3

Rectangle {
  id: rail
  // The deck's speed state, for the robot card's hints.
  property string selectedSpeedText: ""
  property bool selectedSpeedAllowed: true
  property bool compact: false
  color: Theme.panel

  InputShield {}

  Rectangle {
    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: 1
    color: Theme.divider
  }

  ScrollView {
    id: body
    objectName: "body"
    anchors.fill: parent
    anchors.leftMargin: 1
    clip: true
    contentWidth: availableWidth
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    // Shown whenever the cards are taller than the rail, so that a rail cut
    // at its bottom is seen to scroll rather than read as clipped.
    ScrollBar.vertical.objectName: "railScrollBar"
    ScrollBar.vertical.policy: body.contentHeight > body.availableHeight + 0.5 ?
      ScrollBar.AlwaysOn : ScrollBar.AsNeeded

    ColumnLayout {
      id: cards
      width: body.availableWidth
      spacing: 8

      Item { Layout.preferredHeight: 4 }

      // ------------------------------------------------------------- robot
      StatusCard {
        id: robotCard
        objectName: "robotCard"
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        title: "Robot"
        compact: rail.compact
        summary: rail.compact ? CellConsole.stateName : (CellConsole.busy ? "busy" : "")
        summaryTone: !CellConsole.heard ? "warning" : CellConsole.faulted ? "alarm" :
          CellConsole.confirmEnabled ? "attention" : "normal"

        UiText {
          Layout.fillWidth: true
          text: CellConsole.stateName
          size: Theme.title + 2
          strong: true
          color: CellConsole.faulted ? Theme.alarm : CellConsole.confirmEnabled ?
            Theme.attention : !CellConsole.heard ? Theme.warning : Theme.text
        }
        // No console, or a configuration the panel cannot use: said here.
        Rectangle {
          Layout.fillWidth: true
          visible: !CellConsole.heard
          color: Theme.warningFill
          border.color: Theme.warningBorder
          border.width: 1
          radius: Theme.radiusSmall
          implicitHeight: noConsole.implicitHeight + 16
          UiText {
            id: noConsole
            anchors.fill: parent
            anchors.margins: 8
            wrapMode: Text.WordWrap
            size: Theme.caption + 1
            text: CellConsole.configError !== "" ? CellConsole.configError :
              "No console. Nothing can be sent until the console publishes its state " +
              "(./scripts/sim --pair --console)."
          }
        }
        // Two lines at most; the event log carries every step whole.
        FieldRow {
          objectName: "stepRow"
          label: "Step"
          value: CellConsole.step !== "" ? CellConsole.step : "-"
          maximumLineCount: 2
        }
        FieldRow {
          visible: CellConsole.validationPhase !== ""
          label: "Phase"
          value: CellConsole.validationPhase
          strong: true
        }
        // At the program's start, per side (ADR-0072 decision 3), and only for
        // a side that runs.
        FieldRow {
          label: "Simulation at start"
          value: CellConsole.heard ? (CellConsole.plantAtStart ? "yes" : "no") : "-"
        }
        FieldRow {
          visible: CellConsole.counterpartRunning
          label: "Real arm at start"
          value: CellConsole.counterpartAtStart ? "yes" : "no"
        }
        // What the commands need, in words: the target, the speed chosen and
        // the real arm's floor (ADR-0071 decision 2).
        UiText {
          Layout.fillWidth: true
          visible: CellConsole.heard && CellConsole.selectedTarget < 0
          wrapMode: Text.WordWrap
          size: Theme.caption + 1
          color: Theme.textSecondary
          text: "Choose a target to Home or Start program."
        }
        UiText {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          size: Theme.caption + 1
          color: Theme.textSecondary
          text: "Selected: " + rail.selectedSpeedText + " of the program's own speed" +
            (rail.selectedSpeedAllowed || !CellConsole.heard ? "" :
              " - not allowed for this target; choose another")
        }
        UiText {
          Layout.fillWidth: true
          visible: CellConsole.minimumSpeedScale > 0
          wrapMode: Text.WordWrap
          size: Theme.caption + 1
          color: Theme.textSecondary
          text: "Real arm floor: " + CellConsole.minimumSpeedScale + "×. " +
            (CellConsole.floorApplies ?
              "It applies to this target: slower choices are disabled." :
              "It does not apply to this target.")
        }
        UiText {
          Layout.fillWidth: true
          visible: CellConsole.outcome !== ""
          wrapMode: Text.WordWrap
          size: Theme.caption + 1
          color: Theme.text
          text: CellConsole.outcome
        }
      }

      // --------------------------------------------------- cycle progress
      StatusCard {
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        objectName: "progressCard"
        title: "Cycle progress"
        compact: rail.compact
        summary: CellConsole.runActive ?
          "Cycle " + CellConsole.runCycle + "/" + CellConsole.runCycles +
          " · step " + CellConsole.runStepIndex + "/" + CellConsole.runStepCount :
          CellConsole.runStarting !== "" ? "Starting" : "Idle"

        RowLayout {
          Layout.fillWidth: true
          spacing: 16
          ProgressRing {
            Layout.preferredWidth: 60
            Layout.preferredHeight: 60
            value: CellConsole.runActive ? CellConsole.runFraction : 0
            Column {
              anchors.centerIn: parent
              spacing: 0
              UiText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: CellConsole.runActive && CellConsole.runCycles > 0 ?
                  CellConsole.runCycle + "/" + CellConsole.runCycles : "-"
                size: Theme.subtitle
                strong: true
              }
              UiText {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "cycle"
                size: Theme.caption
                color: Theme.muted
              }
            }
          }
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            // A request sent that has not reported yet is starting, not idle.
            UiText {
              objectName: "runTitle"
              Layout.fillWidth: true
              text: CellConsole.runActive ?
                (CellConsole.runPhase !== "" ? CellConsole.runPhase : "Start program") :
                CellConsole.runStarting !== "" ? CellConsole.runStarting + " — starting…" :
                "No request running"
              strong: true
            }
            UiText {
              Layout.fillWidth: true
              visible: CellConsole.runActive && CellConsole.runStepCount > 0
              text: "Step " + CellConsole.runStepIndex + " of " + CellConsole.runStepCount
              color: Theme.textSecondary
            }
            UiText {
              Layout.fillWidth: true
              visible: CellConsole.progress !== ""
              text: CellConsole.progress
              size: Theme.caption
              color: Theme.muted
              wrapMode: Text.WordWrap
              maximumLineCount: 3
              elide: Text.ElideRight
            }
          }
        }
      }

      // ------------------------------------------------------------ sides
      // What the panel hears of the twin boundary and each side, on its own
      // domain (health.hpp). Monitoring only, not a safety function.
      StatusCard {
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        objectName: "sidesCard"
        title: "Sides"
        compact: rail.compact
        summary: CellConsole.physicalCommanded ? "real arm may be commanded" :
          CellConsole.healthShown ? "boundary " + CellConsole.boundaryLink : ""
        summaryTone: CellConsole.physicalCommanded ||
          (CellConsole.healthShown && CellConsole.boundaryLink !== "live") ? "warning" : "normal"

        // A physical side may be commanded whenever the twin is not known to
        // be in SIM (ADR-0072 decision 2): abnormal, so coloured.
        FieldRow {
          label: "Twin mode"
          value: CellConsole.twinMode +
            (CellConsole.physicalCommanded ? " - the real arm may be commanded" : "")
          strong: CellConsole.physicalCommanded
          valueColour: CellConsole.physicalCommanded ? Theme.warning : Theme.text
        }
        RowLayout {
          Layout.fillWidth: true
          spacing: 12
          UiText {
            Layout.preferredWidth: 132
            text: "Physical sides"
            color: Theme.muted
            size: Theme.caption + 1
          }
          Flow {
            Layout.fillWidth: true
            spacing: 6
            UiText {
              visible: CellConsole.physicalSides.length === 0
              text: CellConsole.heard ? "all simulated" : "-"
            }
            Repeater {
              model: CellConsole.physicalSides
              // Grey while nothing may reach it; coloured once something may.
              StatusPill {
                dot: false
                value: modelData + " PHYSICAL"
                tone: CellConsole.physicalCommanded ? "warning" : "normal"
              }
            }
          }
        }
        UiText {
          Layout.fillWidth: true
          visible: CellConsole.healthShown
          text: "Connections - monitoring only, not a safety function"
          size: Theme.caption
          color: Theme.muted
          wrapMode: Text.WordWrap
        }
        RowLayout {
          Layout.fillWidth: true
          visible: CellConsole.healthShown
          UiText {
            Layout.fillWidth: true
            text: "Twin boundary"
          }
          ConnectionPill {
            implicitHeight: 22
            link: CellConsole.boundaryLink
          }
        }
        Repeater {
          model: CellConsole.healthShown ? CellConsole.sideHealth : []
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            RowLayout {
              Layout.fillWidth: true
              UiText {
                Layout.fillWidth: true
                text: (modelData.physical ? "Real arm" : "Simulation") +
                  " (" + modelData.name + ")"
              }
              StatusPill {
                visible: modelData.physical
                implicitHeight: 22
                dot: false
                value: "PHYSICAL"
              }
              ConnectionPill {
                implicitHeight: 22
                link: modelData.link
                abnormal: modelData.abnormal
              }
            }
            UiText {
              Layout.fillWidth: true
              visible: modelData.physical && modelData.link === "live"
              text: modelData.stationary ? "stationary" : "moving or unknown"
              size: Theme.caption
              color: Theme.textSecondary
            }
            UiText {
              Layout.fillWidth: true
              visible: modelData.why !== ""
              text: modelData.why
              size: Theme.caption
              color: Theme.muted
              wrapMode: Text.WordWrap
            }
          }
        }
      }

      // --------------------------------------------------------- fidelity
      // DivergenceMetrics (P8). "Not measured" and no number while a sample
      // is not valid (`fidelity_view`).
      StatusCard {
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        objectName: "fidelityCard"
        title: "Twin fidelity"
        compact: rail.compact
        summary: {
          var cards = CellConsole.fidelity;
          for (var i = 0; i < cards.length; ++i) {
            if (cards[i].measured) {
              return cards[i].headline;
            }
          }
          return "Not measured";
        }

        UiText {
          Layout.fillWidth: true
          visible: CellConsole.fidelity.length === 0
          text: "Not measured"
          size: Theme.subtitle
          strong: true
          color: Theme.textSecondary
        }
        UiText {
          Layout.fillWidth: true
          visible: CellConsole.fidelity.length === 0
          text: "No divergence sample heard from the twin boundary."
          size: Theme.caption
          color: Theme.muted
          wrapMode: Text.WordWrap
        }
        Repeater {
          model: CellConsole.fidelity
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            RowLayout {
              Layout.fillWidth: true
              UiText {
                Layout.fillWidth: true
                text: modelData.asset
                color: Theme.muted
                size: Theme.caption + 1
              }
              UiText {
                text: modelData.headline
                strong: true
                color: modelData.measured ? Theme.text : Theme.textSecondary
              }
            }
            Repeater {
              model: modelData.rows
              FieldRow {
                label: modelData.label
                value: modelData.value
              }
            }
          }
        }
        UiText {
          Layout.fillWidth: true
          text: "A figure is shown only for a sample the twin marks valid."
          size: Theme.caption
          color: Theme.muted
          wrapMode: Text.WordWrap
        }
      }

      // ---------------------------------------------------------- events
      StatusCard {
        id: eventCard
        objectName: "eventCard"
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        visible: !rail.compact
        title: "Event log"
        summary: CellConsole.eventLog.length > 0 ? CellConsole.eventLog.length + " recent" : ""
        // The room left below the other cards, but never less than a few rows.
        Layout.preferredHeight: Math.max(
          160, body.availableHeight - (eventCard.y - cards.y) - 8)
        EventLog {
          Layout.fillWidth: true
          Layout.fillHeight: true
          Layout.minimumHeight: 96
        }
      }

    }
  }
}
