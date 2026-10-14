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

// The frame's header (ADR-0074). INFORMATION ONLY: nothing here is clickable.
// Who this window is (the facility and the zone, from the configuration), the
// twin's mode, the console's state, the connections the panel hears on its own
// domain, and the world's sim time and RTF beside the wall clock.

import QtQuick 2.9
import QtQuick.Layouts 1.3

Rectangle {
  id: header
  property bool wide: true
  color: Theme.panel
  implicitHeight: Theme.headerHeight

  // The wall clock, for display only: it sequences nothing (P4).
  property string clock: Qt.formatTime(new Date(), "HH:mm:ss")
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: header.clock = Qt.formatTime(new Date(), "HH:mm:ss")
  }

  InputShield {}

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.divider
  }

  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: Theme.gutter
    anchors.rightMargin: Theme.gutter
    spacing: 12

    BrandMark {
      Layout.preferredWidth: 36
      Layout.preferredHeight: 36
    }
    Column {
      Layout.alignment: Qt.AlignVCenter
      spacing: 0
      Row {
        spacing: 6
        UiText {
          visible: CellConsole.facilityLabel !== ""
          text: CellConsole.facilityLabel
          size: Theme.title
          strong: true
          color: Theme.text
        }
        UiText {
          text: "Digital Twin"
          size: Theme.title
          color: Theme.textSecondary
        }
      }
      Row {
        spacing: 6
        // The brand's accent on the title: identity, not state.
        Rectangle {
          anchors.verticalCenter: parent.verticalCenter
          width: 14
          height: 2
          radius: 1
          color: Theme.brand
        }
        UiText {
          text: (CellConsole.zoneLabel !== "" ? CellConsole.zoneLabel + " " : "") +
            "Control Center"
          size: Theme.caption
          color: Theme.muted
          font.letterSpacing: 0.5
        }
      }
    }

    Item { Layout.fillWidth: true }

    // The twin's mode, read from the boundary. A physical side that may be
    // commanded (the mode not known to be SIM) is abnormal.
    StatusPill {
      objectName: "twinModePill"
      label: "Twin"
      value: CellConsole.twinMode
      dot: false
      tone: CellConsole.physicalCommanded ? "warning" : "normal"
    }
    StatusPill {
      objectName: "consoleStatePill"
      label: "Console"
      value: CellConsole.stateName
      dot: false
      tone: !CellConsole.heard ? "warning" : CellConsole.faulted ? "alarm" :
        CellConsole.confirmEnabled ? "attention" : "normal"
    }

    Rectangle {
      visible: CellConsole.healthShown
      Layout.preferredWidth: 1
      Layout.preferredHeight: 28
      color: Theme.divider
    }
    // Each pill keeps its status word at every width (T-04): status is never
    // colour alone. A side is named by its name, never by where it sits in
    // the list (R-05).
    ConnectionPill {
      objectName: "boundaryPill"
      visible: CellConsole.healthShown
      label: "Boundary"
      link: CellConsole.boundaryLink
    }
    Repeater {
      model: CellConsole.healthShown ? CellConsole.sideHealth : []
      ConnectionPill {
        objectName: "sidePill_" + modelData.name
        label: modelData.physical ? "Real arm" :
          modelData.name.charAt(0).toUpperCase() + modelData.name.slice(1)
        link: modelData.link
        abnormal: modelData.abnormal
      }
    }

    Rectangle {
      Layout.preferredWidth: 1
      Layout.preferredHeight: 28
      color: Theme.divider
    }
    // Sim time and RTF beside the wall clock. Static items, not a model built
    // from them, so a statistics message repaints two labels and rebuilds
    // nothing (R-06). Figures not heard for longer than the configuration
    // allows are the last heard, not current: dimmed and said "stale".
    HeaderFigure {
      objectName: "simTimeFigure"
      caption: "Sim time"
      note: CellConsole.worldStatsStale ? "stale" : CellConsole.worldPaused ? "paused" : ""
      value: CellConsole.simTime
      stale: CellConsole.worldStatsStale
    }
    HeaderFigure {
      objectName: "rtfFigure"
      caption: "RTF"
      note: CellConsole.worldStatsStale ? "stale" : ""
      value: CellConsole.realTimeFactor
      stale: CellConsole.worldStatsStale
    }
    HeaderFigure {
      caption: "Local"
      value: header.clock
    }
  }
}
