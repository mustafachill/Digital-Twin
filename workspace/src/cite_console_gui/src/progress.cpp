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

#include "cite_console_gui/progress.hpp"

#include <algorithm>

namespace cite_console_gui
{

double progress_fraction(const RunProgress & progress)
{
  if (!progress.active || progress.cycles == 0 || progress.step_count == 0 ||
    progress.cycle == 0 || progress.step_index == 0)
  {
    return 0.0;
  }
  const double total = static_cast<double>(progress.cycles) * progress.step_count;
  const double reached =
    static_cast<double>(progress.cycle - 1) * progress.step_count + progress.step_index;
  return std::clamp(reached / total, 0.0, 1.0);
}

}  // namespace cite_console_gui
