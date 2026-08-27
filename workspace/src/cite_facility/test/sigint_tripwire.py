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

"""Run a node with SIGINT forced into the message-conversion window.

Sending SIGINT from outside reaches this window only sometimes — measured at 3
of 30 teardowns with `/clock` saturated, which is a flake, not a test. This
script makes the same instant deterministic.

The generated `rosgraph_msgs__msg__clock__convert_to_py` builds its Python
message with `PyObject_CallObject(Clock)`. Raising SIGINT from inside that
constructor leaves the pending Python handler to run while the interpreter is
still inside that C call, which is precisely where a handler that raises
destroys the message pointer that rclpy does not check.

Usage: sigint_tripwire.py <module-with-main> [--ros-args ...]
"""

from __future__ import annotations

import importlib
import signal
import sys

import rosgraph_msgs.msg._clock as clock_module

_REAL_CLOCK = clock_module.Clock

#: Fired once only. Every later message must convert normally, or the node would
#: be stopped by something other than the shutdown being tested.
_FIRED: list[bool] = []


class SignalOnFirstConstruction(_REAL_CLOCK):  # type: ignore[misc, valid-type]
    """A `Clock` whose first construction takes SIGINT before it returns."""

    def __init__(self, **kwargs) -> None:
        """Build the message, then interrupt this thread inside this frame."""
        super().__init__(**kwargs)
        if _FIRED:
            return
        _FIRED.append(True)
        signal.raise_signal(signal.SIGINT)
        # CPython 3.12 checks the eval breaker on backward jumps, so this loop
        # is what guarantees the pending handler runs before the frame returns
        # rather than after `PyObject_CallObject` has already succeeded.
        for _ in range(100000):
            pass


def main() -> None:
    """Patch the message class, then hand over to the node's own entry point."""
    clock_module.Clock = SignalOnFirstConstruction
    module = importlib.import_module(sys.argv[1])
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    module.main()


if __name__ == "__main__":
    main()
