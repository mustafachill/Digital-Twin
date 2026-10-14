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

// The view buttons (ADR-0071): they move the 3D view's camera through the
// window's CameraTracking and move no robot, so neither the console's state
// nor its absence touches them. Subdued, and icon-only below the wide layout.

import QtQuick 2.9
import QtQuick.Layouts 1.3

GridLayout {
  id: views
  property bool iconOnly: false
  // The view the operator last chose, as the middle's label names it.
  signal chosen(string name)

  columns: 3
  rowSpacing: 6
  columnSpacing: 6
  // Three columns whatever the configuration offers, so the deck is laid out
  // the same with and without the presets.
  readonly property int buttonWidth: iconOnly ? 44 : 120
  Layout.preferredWidth: 3 * buttonWidth + 2 * columnSpacing

  function kindOf(label) {
    var kind = String(label).toLowerCase();
    return ["top", "side", "front"].indexOf(kind) >= 0 ? kind : "top";
  }

  DeckButton {
    objectName: "resetViewButton"
    Layout.preferredWidth: views.buttonWidth
    variant: "subdued"
    iconKind: "home"
    iconOnly: views.iconOnly
    text: "Reset view"
    enabled: CellConsole.resetViewEnabled
    onClicked: {
      CellConsole.resetView();
      views.chosen("Home");
    }
  }
  Repeater {
    model: CellConsole.viewPresets
    DeckButton {
      Layout.preferredWidth: views.buttonWidth
      variant: "subdued"
      iconKind: views.kindOf(modelData)
      iconOnly: views.iconOnly
      text: modelData
      onClicked: {
        CellConsole.selectPreset(index);
        views.chosen(modelData);
      }
    }
  }
  DeckButton {
    objectName: "followButton"
    Layout.preferredWidth: views.buttonWidth
    variant: "subdued"
    iconKind: "follow"
    iconOnly: views.iconOnly
    text: "Follow robot"
    enabled: CellConsole.followEnabled
    onClicked: {
      CellConsole.followRobot();
      views.chosen("Following carriage");
    }
  }
}
