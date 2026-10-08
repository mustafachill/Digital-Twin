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

"""An initialization interrupted or unanswered once sent stops the track (S-01, ADR-0070).

`InitializeAsset` may home the track and bring the carriage to the start, so a
Ctrl-C (or SIGTERM) or a ceiling passed while the request is in flight is
followed by the vendor's `set_linear_motor_stop` on that side's domain before
the failure is re-raised (`program.home._call_on_domain`). The initializer and
the vendor's stop are faked in this test's node, on a domain of its own; an
initializer that never answers is what an in-flight motion looks like from the
client. **Nothing here reaches hardware.**
"""

from __future__ import annotations

import _thread
import os
from pathlib import Path
import signal
import sys
import threading

from cite_bringup.program import home
from cite_bringup.program.steps import StepFailed
from cite_interfaces.srv import InitializeAsset
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cite_hardware" / "test"))
from vendor_fakes import FakeTrack, Harness  # noqa: E402

DOMAIN = 10 + os.getpid() % 80
VENDOR = "/test_vendor/xarm"
SERVICE = "/test/picker/initialize"
STOP = (f"{VENDOR}/{FakeTrack.STOP}", 2.0)


@pytest.fixture(scope="module")
def rig():
    os.environ["ROS_DOMAIN_ID"] = str(DOMAIN)
    harness = Harness("initialize_interrupted_test")
    # What `steps.install_interrupt_handlers` makes of Ctrl-C in the program.
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    track = FakeTrack(harness, VENDOR, serve=(FakeTrack.STOP,))
    release = threading.Event()
    #: Set by a case to interrupt this process once the request has arrived.
    interrupt = threading.Event()
    received = []
    answered = []

    def never_answers(_request, response):
        received.append(1)
        if interrupt.is_set():
            _thread.interrupt_main()
        release.wait(timeout=30.0)
        response.success, response.detail = False, "released"
        answered.append(1)
        return response

    harness.node.create_service(
        InitializeAsset, SERVICE, never_answers, callback_group=harness.group
    )
    try:
        yield track, interrupt, received
    finally:
        release.set()
        Harness.wait_for(lambda: len(answered) == len(received), "the fake released")
        signal.signal(signal.SIGINT, previous)
        harness.close()


def test_an_unanswered_initialization_stops_the_track(rig) -> None:
    track, interrupt, received = rig
    interrupt.clear()
    stops, calls = track.stops, len(received)
    with pytest.raises(StepFailed, match="did not answer"):
        home._call_on_domain(SERVICE, DOMAIN, 1.0, STOP)
    assert len(received) == calls + 1, "the request was sent"
    Harness.wait_for(lambda: track.stops == stops + 1, "the track stopped")


def test_an_interrupted_initialization_stops_the_track_then_re_raises(rig) -> None:
    track, interrupt, received = rig
    interrupt.set()
    stops = track.stops
    with pytest.raises(KeyboardInterrupt):
        home._call_on_domain(SERVICE, DOMAIN, 30.0, STOP)
    assert track.stops == stops + 1, "stopped before the interrupt was re-raised"
