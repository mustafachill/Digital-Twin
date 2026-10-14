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

// One connection as the header shows it (health.hpp): live, stale, absent,
// not ready or not started. Monitoring only, never a safety function. A live
// link is grey with a softly pulsing dot; an abnormal one is amber; a side
// never started is grey and still (ISA-101).

import QtQuick 2.9

StatusPill {
  property string link: "absent"
  property bool abnormal: link !== "live" && link !== "not started"
  tone: abnormal ? "warning" : "normal"
  pulse: link === "live"
  value: compact ? "" : link
}
