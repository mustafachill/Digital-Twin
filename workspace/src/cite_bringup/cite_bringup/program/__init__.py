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

"""A fixed program for the cell: the real robot's program, step by step (ADR-0067).

The way a UFACTORY Studio Blockly program drives a real xArm — and since
ADR-0067 it IS that program: the real xArm 5's own, read from its program file
into the bring-up plan and mapped onto a small vocabulary (`steps`) by
`from_plan`. `python3 -m cite_bringup.program` runs it. The hand-written list of
taught poses ADR-0066 started with is gone (ADR-0069); the `belt` step it used is
kept, with the twin boundary's belt route, on the project owner's decision.

It is an operator-level client. Through the twin boundary (`--via twin`, the
default) one program drives both sides of the pair; `--via plant` drives the
plant's own servers, for a single side and for the `program_cycle` scenario.
The beam-triggered line it once stood beside runs as `projects/01` (ADR-0069).
"""
