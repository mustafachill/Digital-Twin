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

An interrupt is not the initializer's end (ADR-0071, S-02): after it the
answer is still awaited within the call's own ceiling, and the track is
stopped a second time once it comes, so nothing reports the stop done while
the initializer may still be moving the carriage.
"""

from __future__ import annotations

import _thread
import os
from pathlib import Path
import signal
import sys
import threading
import time

from cite_bringup.program import home
from cite_bringup.program.steps import Interrupted, StepFailed
from cite_interfaces.srv import InitializeAsset
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cite_hardware" / "test"))
from vendor_fakes import FakeTrack, Harness  # noqa: E402

DOMAIN = 10 + os.getpid() % 80
VENDOR = "/test_vendor/xarm"
SERVICE = "/test/picker/initialize"
STOP = (f"{VENDOR}/{FakeTrack.STOP}", 2.0)

#: The fake initializer's release and its answers, for the case that answers it.
_SHARED: dict = {}


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
    _SHARED["release"], _SHARED["answered"] = release, answered
    try:
        yield track, interrupt, received
    finally:
        release.set()
        Harness.wait_for(lambda: len(answered) == len(received), "the fake released")
        signal.signal(signal.SIGINT, previous)
        harness.close()


def test_a_console_stop_awaits_the_initializers_answer_between_two_track_stops(rig) -> None:
    """S-02: the stop is not reported while the initializer may still move the carriage.

    First in this file, so that no earlier case's request still holds one of
    the fake's executor threads.
    """
    track, interrupt, received = rig
    interrupt.clear()
    calls, stops, answered = len(received), track.stops, len(_SHARED["answered"])
    order: list[str] = []

    def answer_after_the_first_stop() -> None:
        Harness.wait_for(lambda: track.stops == stops + 1, "the first track stop")
        order.append("first stop")
        # The initializer answers only now: until then the client must wait.
        _SHARED["release"].set()

    helper = threading.Thread(target=answer_after_the_first_stop)
    helper.start()
    try:
        with pytest.raises(Interrupted):
            home._call_on_domain(
                SERVICE, DOMAIN, 30.0, STOP, interrupted=lambda: len(received) > calls
            )
        order.append("re-raised")
    finally:
        helper.join(timeout=30.0)
        _SHARED["release"].clear()
    assert order == ["first stop", "re-raised"]
    assert len(_SHARED["answered"]) > answered, "re-raised before the initializer answered"
    assert track.stops == stops + 2, "the track was stopped again after the answer"


def test_an_unanswered_initialization_stops_the_track(rig) -> None:
    track, interrupt, received = rig
    interrupt.clear()
    stops, calls = track.stops, len(received)
    with pytest.raises(StepFailed, match="did not answer"):
        home._call_on_domain(SERVICE, DOMAIN, 1.0, STOP)
    assert len(received) == calls + 1, "the request was sent"
    Harness.wait_for(lambda: track.stops == stops + 1, "the track stopped")


def test_an_interrupted_initialization_stops_the_track_then_re_raises(rig) -> None:
    """Ctrl-C: stopped at once, the answer awaited to the ceiling, stopped again."""
    track, interrupt, received = rig
    interrupt.set()
    stops = track.stops
    with pytest.raises(KeyboardInterrupt):
        home._call_on_domain(SERVICE, DOMAIN, 3.0, STOP)
    assert track.stops == stops + 2, "stopped twice before the interrupt was re-raised"


def test_what_an_interrupt_comes_to_is_said_where_the_caller_says_things(rig) -> None:
    """R2-06: the console shows the outcome, not only a terminal it does not have."""
    track, interrupt, received = rig
    interrupt.clear()
    calls = len(received)
    said: list[str] = []
    with pytest.raises(Interrupted):
        home._call_on_domain(
            SERVICE, DOMAIN, 1.0, STOP, interrupted=lambda: len(received) > calls,
            say=said.append,
        )
    assert f"{SERVICE} did not answer within 1 s of its call" in said
    sent = [line for line in said if line.startswith("interrupted during an initialization")]
    assert len(sent) == 2, said


def test_a_shutdown_deadline_ends_the_answer_wait_and_still_stops_twice(rig) -> None:
    """R2-02: past the console's shutdown deadline the answer is not awaited, the stop is."""
    track, interrupt, received = rig
    interrupt.clear()
    calls, stops = len(received), track.stops
    said: list[str] = []
    started = time.monotonic()
    with pytest.raises(Interrupted):
        home._call_on_domain(
            SERVICE, DOMAIN, 30.0, STOP, interrupted=lambda: len(received) > calls,
            say=said.append, stop_deadline=lambda: started,
        )
    assert time.monotonic() - started < 10.0, "the answer was awaited past the deadline"
    assert any("shutdown deadline" in line for line in said), said
    assert track.stops == stops + 2
