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

// The operator console's panel (ADR-0071 decision 5), which frames the 3D view
// (ADR-0074). Layout only: every "enabled" is a property the plugin computes
// with `enabled_for`, and every button calls the plugin, which asks the
// console. Nothing here decides. Every label that shows a string the console
// or the configuration sent is plain text (P-R05): shown, never interpreted
// as markup.
//
// THE FRAME. The generated configuration anchors this panel's card to all
// four edges of the 3D view. From top to bottom: the header and, only while
// the console reports one, the alarm band; then the live 3D view on the left,
// left empty here, with the status rail on the right; then the console's
// question, only while it asks, and the command deck. The header, the alarm
// band and the rail hold no clickable control: every one is in the deck, or
// in the question above it. The deck and the question never scroll; the rail
// does when the window is short.
//
// THE MOUSE REACHES THE SCENE through the middle. The card's own Pane and its
// MouseAreas would take every press over the whole card, so once this item
// is put in its card, the card is given an empty containment mask and its own
// MouseAreas are disabled (gz-gui 8 internals, ADR-0074). This root accepts no
// input; each opaque part takes the presses and the wheel that land on it.
//
// STOP COMES FIRST (S-02). That mask leans on how gz-gui builds its card: a
// card that clipped its children to its shape would, masked, take every press
// from every button in it. So once gz-gui's window is shown - every card in
// its place; gz-gui docks a card off the window before it floats it - and
// whenever the frame is laid out again after that, the card's z or the
// frame's visibility changes, or the question comes or goes, the plugin
// judges whether a press at the centre of each control that stops or answers
// the console reaches it (`pressReaches`): the deck's Stop and, while the
// question is shown, its Cancel (Stop) and Confirm. Each judgement runs once
// the layout has settled (`Qt.callLater`, an event, not a timer), and one that
// cannot be pressed at all - outside the window, no size - fails. While a
// modal popup holds every press, nothing is judged; it is judged again when
// the popup goes. If one fails, the mask and the MouseAreas are put back as
// gz-gui made them and a warning is printed: the scene loses the mouse over
// the middle, and the panel stays usable.
//
// COLOUR IS FOR THE ABNORMAL (ISA-101). Every colour is in `Theme`.

import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Controls.Material 2.1
import QtQuick.Layouts 1.3
import "qrc:/CellConsole/components"

// The root fills the card gz-gui puts it in, and has an implicit size equal to
// its minimums so it is never 0x0 before a parent sizes it.
Item {
  id: frame
  anchors.fill: parent
  Layout.minimumWidth: 1024
  Layout.minimumHeight: 600
  implicitWidth: 1280
  implicitHeight: 720

  Material.theme: Material.Dark
  Material.accent: Theme.brand

  readonly property bool wide: width >= Theme.wideFrom
  readonly property bool compact: width < Theme.compactBelow
  // The view the operator last chose with a view button. A mouse drag in the
  // scene is not seen here, so it names the last choice, not the camera.
  property string viewName: "Home"

  // ------------------------------------------------------- mouse pass-through
  Item {
    id: noInput
    width: 0
    height: 0
  }
  // The card the pass-through is applied to, and the MouseAreas of it that
  // were disabled; null and empty while none is.
  property var passCard: null
  property var passAreas: []
  // gz-gui's main window has been shown with this panel in it.
  property bool windowShown: false
  function passMouseThrough() {
    // gz-gui's content item exposes its card (GzCard.qml); a parent that does
    // not - an offscreen test's - is left alone.
    if (!frame.parent || typeof frame.parent.card !== "function") {
      return;
    }
    var card = frame.parent.card();
    if (!card || card === frame.passCard) {
      return;
    }
    var areas = [];
    var kids = card.contentItem ? card.contentItem.children : [];
    for (var i = 0; i < kids.length; ++i) {
      if (String(kids[i]).indexOf("MouseArea") >= 0 && kids[i].enabled) {
        kids[i].enabled = false;
        areas.push(kids[i]);
      }
    }
    card.containmentMask = noInput;
    frame.passCard = card;
    frame.passAreas = areas;
    card.zChanged.connect(frame.checkStopReachable);
    checkStopReachable();
  }
  // Every control whose press asks the console to stop or answers it: the
  // deck's Stop always, the question's Cancel (Stop) and Confirm while shown.
  function pressTargets() {
    var targets = [{name: "Stop", item: deck.stopButton}];
    if (confirmation.visible) {
      targets.push({name: "Cancel (Stop)", item: confirmation.cancelButton});
      targets.push({name: "Confirm", item: confirmation.confirmButton});
    }
    return targets;
  }
  // The overlay a modal popup holds every press in, while the check waits for
  // it to close; null while none does.
  property var waitingOverlay: null
  function stopWaitingForOverlay() {
    if (frame.waitingOverlay !== null) {
      frame.waitingOverlay.childrenChanged.disconnect(frame.checkStopReachable);
      frame.waitingOverlay = null;
    }
  }
  function checkStopReachable() {
    Qt.callLater(frame.judgeStopReachable);
  }
  function judgeStopReachable() {
    if (!frame.windowShown || frame.passCard === null || !frame.visible) {
      return;
    }
    var overlay = CellConsole.modalOverlay(deck.stopButton);
    if (overlay !== null) {
      if (frame.waitingOverlay !== overlay) {
        frame.stopWaitingForOverlay();
        overlay.childrenChanged.connect(frame.checkStopReachable);
        frame.waitingOverlay = overlay;
      }
      return;
    }
    frame.stopWaitingForOverlay();
    var targets = frame.pressTargets();
    for (var t = 0; t < targets.length; ++t) {
      if (!CellConsole.pressReaches(targets[t].item)) {
        frame.undoPassThrough(targets[t].name);
        return;
      }
    }
  }
  function undoPassThrough(name) {
    frame.passCard.zChanged.disconnect(frame.checkStopReachable);
    frame.passCard.containmentMask = null;
    for (var i = 0; i < frame.passAreas.length; ++i) {
      frame.passAreas[i].enabled = true;
    }
    frame.passCard = null;
    frame.passAreas = [];
    console.warn("CellConsole: A PRESS ON " + name.toUpperCase() + " DID NOT REACH IT with " +
      "the mouse passed through to the 3D view, so the pass-through is undone: the panel " +
      "takes the mouse over the whole view, and the scene gets none (ADR-0074, S-02).");
  }
  onParentChanged: passMouseThrough()
  onWidthChanged: checkStopReachable()
  onHeightChanged: checkStopReachable()
  onVisibleChanged: checkStopReachable()
  // Connected here rather than with Connections, whose function handlers
  // need a newer QtQml than this file imports.
  function onWindowShown() {
    frame.windowShown = true;
    frame.checkStopReachable();
  }
  Component.onCompleted: CellConsole.windowShown.connect(frame.onWindowShown)

  // -------------------------------------------------------------- the frame
  HeaderBar {
    id: header
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    height: Theme.headerHeight
    wide: frame.wide
  }

  AlarmBand {
    id: alarm
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: header.bottom
    height: implicitHeight
  }

  StatusRail {
    id: rail
    anchors.right: parent.right
    anchors.top: alarm.bottom
    anchors.bottom: confirmation.visible ? confirmation.top : deck.top
    width: frame.wide ? Theme.railWide : frame.compact ? Theme.railCompact : Theme.railNarrow
    compact: frame.compact
    selectedSpeedText: deck.selectedSpeedText
    selectedSpeedAllowed: deck.selectedSpeedAllowed
  }

  // The middle: the live 3D view shows through. Its label and a view failure
  // are information only and take no input.
  Column {
    anchors.left: parent.left
    anchors.top: alarm.bottom
    anchors.leftMargin: Theme.gutter
    anchors.topMargin: Theme.gutter
    spacing: 8
    Rectangle {
      objectName: "viewLabel"
      color: "#cc151c25"
      radius: Theme.radiusSmall
      border.width: 1
      border.color: Theme.divider
      implicitWidth: viewText.implicitWidth + 24
      implicitHeight: 30
      width: implicitWidth
      height: implicitHeight
      UiText {
        id: viewText
        objectName: "viewText"
        anchors.centerIn: parent
        text: "View: " + frame.viewName
        size: Theme.caption + 1
        color: Theme.textSecondary
      }
    }
    Rectangle {
      visible: CellConsole.viewError !== ""
      color: Theme.alarmFill
      radius: Theme.radiusSmall
      border.width: 1
      border.color: Theme.alarmBorder
      width: Math.min(viewError.implicitWidth + 24, frame.width - rail.width - 2 * Theme.gutter)
      height: viewError.implicitHeight + 12
      UiText {
        id: viewError
        anchors.fill: parent
        anchors.margins: 6
        anchors.leftMargin: 12
        text: CellConsole.viewError
        wrapMode: Text.WordWrap
        size: Theme.caption + 1
        color: Theme.alarm
      }
    }
  }

  ConfirmBanner {
    id: confirmation
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: deck.top
    height: implicitHeight
    // Never over the header or the alarm band (S-03): the band's room only
    // while it is shown (R2-05).
    maximumHeight: Math.max(64, deck.y - alarm.y - (alarm.visible ? alarm.height : 0))
    onVisibleChanged: frame.checkStopReachable()
    onHeightChanged: frame.checkStopReachable()
  }

  CommandDeck {
    id: deck
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: Theme.deckHeight
    wide: frame.wide
    compact: frame.compact
    onViewChosen: frame.viewName = name
  }
}
