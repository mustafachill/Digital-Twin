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

"""A fixed program for the cell: taught joint poses and timed belt runs (ADR-0066).

The way a UFACTORY Studio Blockly program drives a real xArm: move to a taught
pose, close the gripper, move, open it, run the belt for a while, stop it. The
program is a readable list of steps (`cell_b_pick_place`), the steps are a small
vocabulary (`steps`), and `python3 -m cite_bringup.program` runs it.

It is an operator-level client. Through the twin boundary (`--via twin`, the
default) one program drives both sides of the pair; `--via plant` drives the
plant's own servers, for a single side and for the `program_cycle` scenario.
The beam-triggered line is parked beside it, not replaced; see ADR-0066.
"""
