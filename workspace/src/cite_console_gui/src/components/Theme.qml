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

// Every colour, size and duration of the operator window (ADR-0074), and
// nowhere else.
//
// ISA-101. Normal is grey: the surfaces, the text and every state that is as
// it should be. Colour is only for the abnormal - `alarm` (a FAULT, a refusal,
// a view failure), `warning` (a connection stale, absent or not ready; a
// physical side that may be commanded; no console) and `attention` (the
// console asks the operator to act) - and nothing flashes. `brand` (SHSU
// orange) is identity only: the mark, the title's accent and the focus ring;
// it never says anything about the cell's state.
//
// Contrast. Text on its surface is WCAG AA (4.5:1) or better: `text` and
// `textSecondary` on every surface below, `muted` on `panel` and `card`.
//
// No name here starts with `on` and a capital: QML reads one as a signal
// handler, refuses the assignment, and the panel is never instantiated (T-01).

pragma Singleton
import QtQuick 2.9

QtObject {
  // ------------------------------------------------------------- surfaces
  readonly property color window: "#0f141b"
  readonly property color panel: "#151c25"
  readonly property color card: "#1c2530"
  readonly property color cardRaised: "#232e3b"
  readonly property color divider: "#2a3542"
  readonly property color shadow: "#66000000"

  // ---------------------------------------------------------------- text
  readonly property color text: "#e6edf3"
  readonly property color textSecondary: "#b4c0cd"
  readonly property color muted: "#8a9bb0"
  readonly property color disabledText: "#5d6d80"

  // ------------------------------------------- controls (normal: greys only)
  readonly property color control: "#2a3542"
  readonly property color controlHover: "#334050"
  readonly property color controlPressed: "#3b4a5c"
  readonly property color controlBorder: "#3a4757"
  readonly property color controlDisabled: "#1f2833"
  readonly property color selected: "#d5dee8"
  readonly property color textOnSelected: "#0f141b"
  // Stop: dark grey, never red. Red is the physical E-stop's, and Stop is not
  // an E-stop (ADR-0071 decision 4).
  readonly property color stop: "#3d4652"
  readonly property color stopHover: "#4a5461"
  readonly property color stopPressed: "#58636f"
  readonly property color stopBorder: "#6b7684"

  // -------------------------------------------- the meanings kept from v0.1
  readonly property color background: window
  readonly property color surface: card
  readonly property color border: divider
  readonly property color strong: stop
  readonly property color textOnStrong: "#ffffff"
  readonly property color textOnColour: "#ffffff"

  // ------------------------------------------------- abnormal only (ISA-101)
  readonly property color alarm: "#ff6369"
  readonly property color alarmFill: "#3d1519"
  readonly property color alarmBorder: "#a3343a"
  readonly property color warning: "#f5b14a"
  readonly property color warningFill: "#3a2a0e"
  readonly property color warningBorder: "#8f6a22"
  readonly property color attention: "#6cb2ff"
  readonly property color attentionFill: "#11294a"
  readonly property color attentionBorder: "#2f6db8"

  // --------------------------------------------------------- identity only
  readonly property color brand: "#f76800"

  // ----------------------------------------------------------- typography
  // Open Sans ships in the container (fonts-open-sans); where it is absent Qt
  // substitutes the default sans family. Its figures are tabular by default,
  // so numbers that change do not shift the text around them.
  readonly property string fontFamily: "Open Sans"
  readonly property int caption: 12
  readonly property int body: 14
  readonly property int subtitle: 16
  readonly property int title: 20
  readonly property int display: 28

  // --------------------------------------------------------------- shape
  readonly property int radius: 10
  readonly property int radiusSmall: 8
  readonly property int gutter: 16
  readonly property int gap: 8

  // --------------------------------------------------------------- layout
  readonly property int headerHeight: 64
  readonly property int deckHeight: 180
  // Where the window is tall enough, the deck takes a little more, so the
  // validate-then-run caveat has room beside its button.
  readonly property int deckHeightTall: 196
  readonly property int tallFrom: 900
  readonly property int railWide: 380
  readonly property int railNarrow: 300
  readonly property int railCompact: 260
  // Window widths at which the layout steps down.
  readonly property int wideFrom: 1600
  readonly property int compactBelow: 1280

  // --------------------------------------------------------------- motion
  readonly property int fast: 150
  readonly property int normal: 200
}
