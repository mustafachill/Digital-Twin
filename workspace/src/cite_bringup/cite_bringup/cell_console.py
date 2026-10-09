#!/usr/bin/env python3
# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""`ros2 run cite_bringup cell_console.py --zone cell_b`: the operator console (ADR-0071).

The installed program the pair supervisor starts (`pair.console_spec`). The
node and everything it does are `cite_bringup.program.console`; this file only
gives `ros2 run` something to execute.
"""

import sys

from cite_bringup.program.console import main

if __name__ == "__main__":
    sys.exit(main())
