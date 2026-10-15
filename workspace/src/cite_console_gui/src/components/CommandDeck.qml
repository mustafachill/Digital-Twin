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

// The command deck (ADR-0074): EVERY clickable control of the window, in one
// place and never scrolled. Left to right - the view buttons (subdued), the
// target (with "Select a target" while none is), speed and cycles, the
// actions, and Stop at the far right.
//
// Layout only. Every "enabled" below is a property the plugin computes with
// `enabled_for`, and every button calls the plugin, which asks the console.
// Nothing here decides (ADR-0071).

import QtQuick 2.9
import QtQuick.Layouts 1.3

Rectangle {
  id: deck
  objectName: "commands"
  property bool wide: true
  // Below the smallest supported width: narrower choices and Stop.
  property bool compact: false

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
  readonly property int cycles: cyclesStepper.value
  // A scale as the deck and the rail write it: 1.0, not 1.
  function speedText(scale) {
    return (scale === Math.round(scale) ? scale.toFixed(1) : String(scale)) + "×";
  }
  readonly property string selectedSpeedText: speedText(selectedSpeed)
  signal viewChosen(string name)
  // For the frame's check that a press on Stop reaches Stop (S-02).
  readonly property alias stopButton: stop

  color: Theme.panel
  implicitHeight: Theme.deckHeight

  InputShield {}

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: 1
    color: Theme.divider
  }

  // Stop is anchored to the deck's right edge on its own, so that whatever
  // the width, it is the rest of the deck that runs short, never Stop.
  StopButton {
    id: stop
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.rightMargin: Theme.gutter
    anchors.topMargin: 12
    anchors.bottomMargin: 12
    width: deck.wide ? 224 : deck.compact ? 168 : 196
    enabled: CellConsole.stopEnabled
    onClicked: CellConsole.stop()
  }

  RowLayout {
    anchors.left: parent.left
    anchors.right: stop.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.leftMargin: Theme.gutter
    anchors.rightMargin: deck.wide ? 24 : 16
    anchors.topMargin: 12
    anchors.bottomMargin: 12
    spacing: deck.wide ? 24 : 16
    clip: true

    // ---------------------------------------------------------------- view
    ColumnLayout {
      Layout.alignment: Qt.AlignTop
      spacing: 6
      GroupTitle { text: "View" }
      ViewGroup {
        iconOnly: !deck.wide
        onChosen: deck.viewChosen(name)
      }
    }

    Rectangle {
      Layout.fillHeight: true
      Layout.preferredWidth: 1
      color: Theme.divider
    }

    // --------------------------------------------------------------- setup
    ColumnLayout {
      Layout.alignment: Qt.AlignTop
      spacing: 6
      RowLayout {
        spacing: 10
        GroupTitle { text: "Setup" }
        // No target selected while a console is heard (`target_hint_shown`):
        // Start robot, Home and Start program wait for one (ADR-0072 decision
        // 3, amended 2026-10-15). Text, not a control; the attention colour,
        // never the alarm's (ISA-101).
        UiText {
          objectName: "targetHint"
          visible: CellConsole.targetHintShown
          text: "Select a target"
          size: Theme.caption
          strong: true
          color: Theme.attention
        }
      }
      GridLayout {
        columns: 2
        rowSpacing: 8
        columnSpacing: 10

        UiText { text: "Target"; color: Theme.muted; size: Theme.caption + 1 }
        // Where the signal goes (ADR-0072 decision 3, amended 2026-10-15). The
        // selection is the plugin's (`settled_selection`): Simulation where it
        // is served, the real arm and the twin never preselected, an
        // operator's pick dropped whenever the served set changes or the
        // console leaves (R-18). The selector shows the plugin's selection,
        // never the click.
        SegmentedSelector {
          objectName: "targetSelector"
          segmentWidth: deck.wide ? 98 : deck.compact ? 76 : 88
          labels: CellConsole.targetChoices
          enabledChoices: CellConsole.targetChoicesEnabled
          sublabels: {
            var notes = [];
            for (var i = 0; i < CellConsole.targetChoices.length; ++i) {
              notes.push(CellConsole.targetChoicesEnabled[i] === true || !CellConsole.heard ?
                "" : "not running");
            }
            return notes;
          }
          checkedIndex: CellConsole.selectedTarget
          onActivated: CellConsole.selectTarget(index)
        }

        UiText { text: "Speed"; color: Theme.muted; size: Theme.caption + 1 }
        // The speed the next request carries (ADR-0071 decision 2): a choice,
        // not a live override. The rail states the selection and the floor.
        SegmentedSelector {
          objectName: "speedSelector"
          segmentWidth: deck.wide ? 73 : deck.compact ? 58 : 65
          labels: {
            var names = [];
            for (var i = 0; i < CellConsole.speedChoices.length; ++i) {
              names.push(deck.speedText(CellConsole.speedChoices[i]));
            }
            return names;
          }
          enabledChoices: CellConsole.speedChoicesEnabled
          sublabels: {
            var notes = [];
            for (var i = 0; i < CellConsole.speedChoices.length; ++i) {
              notes.push(CellConsole.speedChoicesEnabled[i] === true || !CellConsole.heard ?
                "" : "below the floor");
            }
            return notes;
          }
          checkedIndex: CellConsole.speedChoices.indexOf(deck.selectedSpeed)
          onActivated: deck.selectedSpeed = CellConsole.speedChoices[index]
        }

        UiText { text: "Cycles"; color: Theme.muted; size: Theme.caption + 1 }
        Stepper {
          id: cyclesStepper
          objectName: "cyclesStepper"
          from: 1
          to: 1000
          value: 1
        }
      }
    }

    Rectangle {
      Layout.fillHeight: true
      Layout.preferredWidth: 1
      color: Theme.divider
    }

    // ------------------------------------------------------------- actions
    ColumnLayout {
      Layout.alignment: Qt.AlignTop
      Layout.fillWidth: true
      Layout.minimumWidth: deck.compact ? 280 : 360
      spacing: 6
      GroupTitle { text: "Actions" }
      GridLayout {
        Layout.fillWidth: true
        columns: 3
        rowSpacing: 8
        columnSpacing: 8

        DeckButton {
          objectName: "startRobotButton"
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          text: "Start robot"
          enabled: CellConsole.startRobotEnabled
          onClicked: CellConsole.startRobot()
        }
        DeckButton {
          objectName: "homeButton"
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          text: "Home"
          enabled: CellConsole.homeEnabled && deck.selectedSpeedAllowed
          onClicked: CellConsole.home(deck.selectedSpeed)
        }
        DeckButton {
          objectName: "startProgramButton"
          Layout.fillWidth: true
          Layout.preferredWidth: 1
          text: "Start program"
          enabled: CellConsole.startProgramEnabled && deck.selectedSpeedAllowed
          onClicked: CellConsole.startProgram(deck.selectedSpeed, deck.cycles)
        }

        // ADR-0073: one cycle on the simulation alone and, only if it passed
        // there in this same request, the cycles on the twin with every twin
        // gate unchanged. It carries no target. No caveat text beside it
        // (decision 5, amended 2026-10-15): the outcome still says "passed in
        // simulation", never "safe" or "verified", and the twin's own prompt
        // says the pass is no evidence of physical safety. It takes the row.
        DeckButton {
          objectName: "validateThenRunButton"
          Layout.fillWidth: true
          Layout.columnSpan: 3
          text: "Validate in sim, then run twin"
          enabled: CellConsole.validateThenRunEnabled && deck.selectedSpeedAllowedForTwin
          onClicked: CellConsole.validateThenRun(deck.selectedSpeed, deck.cycles)
        }
      }
    }

  }
}
