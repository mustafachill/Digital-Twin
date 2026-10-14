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

// One line of text in the frame's type, shown as plain text: a string the
// console or the configuration sent is shown, never interpreted as markup.

import QtQuick 2.9
import QtQuick.Controls 2.2

Label {
  property int size: Theme.body
  property bool strong: false
  textFormat: Text.PlainText
  color: Theme.text
  font.family: Theme.fontFamily
  font.pixelSize: size
  font.weight: strong ? Font.DemiBold : Font.Normal
  elide: wrapMode === Text.NoWrap ? Text.ElideRight : Text.ElideNone
  Behavior on color { ColorAnimation { duration: Theme.fast } }
}
