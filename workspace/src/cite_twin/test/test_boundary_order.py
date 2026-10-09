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

"""Two of the boundary's orderings, held on its own methods (ADR-0072, R-11, R-08).

* `TwinSides` is published under the lock its snapshot was taken under, so two
  overlapping publishers on the reentrant group cannot leave an older snapshot
  latched (R-11).
* The operator receives feedback from a side the mode commands: the plant's
  where it is commanded, the counterpart's in REAL (R-08).

Each method is called on a stand-in for the boundary that carries only what the
method reads; nothing is brought up.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from cite_bringup.plan import COUNTERPART_SIDE, PLANT_SIDE
from cite_twin.twin_boundary import TwinBoundary


class _Clock:
    def now(self):
        return SimpleNamespace(to_msg=lambda: _stamp())


def _stamp():
    from builtin_interfaces.msg import Time

    return Time()


def _sides_boundary(snapshots, published, during_publish=lambda: None):
    lock = threading.Lock()

    def publish(message) -> None:
        # The lock the snapshot was taken under is still held here.
        published.append((message.detail, lock.locked()))
        during_publish()

    boundary = SimpleNamespace(
        _lock=lock,
        _sides_published=None,
        _sides_now=lambda: snapshots.pop(0),
        _plant=SimpleNamespace(node=SimpleNamespace(get_clock=_Clock)),
        _sides_publisher=SimpleNamespace(publish=publish),
    )
    return boundary


def _snapshot(detail: str):
    return (("plant",), (), ("plant",), (), detail)


def test_twin_sides_is_published_under_the_snapshot_lock() -> None:
    """R-11: the order snapshots are taken in is the order they are published in."""
    published: list = []
    boundary = _sides_boundary([_snapshot("first"), _snapshot("second")], published)
    TwinBoundary._publish_sides(boundary)
    TwinBoundary._publish_sides(boundary)
    assert published == [("first", True), ("second", True)]


def test_an_overlapping_publisher_waits_for_the_one_in_progress() -> None:
    """R-11: a second caller cannot take a newer snapshot until the older one is out."""
    published: list = []
    snapshots = [_snapshot("older"), _snapshot("newer")]
    second: list[threading.Thread] = []

    def overlap() -> None:
        # The divergence timer's publish is still in progress when the
        # liveness tick starts another on the reentrant group.
        thread = threading.Thread(target=TwinBoundary._publish_sides, args=(boundary,))
        thread.start()
        second.append(thread)
        thread.join(timeout=0.2)
        # Blocked on the lock rather than publishing ahead of this one.
        assert thread.is_alive()

    boundary = _sides_boundary(
        snapshots, published, during_publish=lambda: None if second else overlap()
    )
    TwinBoundary._publish_sides(boundary)
    second[0].join(timeout=5.0)
    assert not second[0].is_alive()
    assert [detail for detail, _ in published] == ["older", "newer"]
    # The latched one is the newer.
    assert boundary._sides_published[-1] == "newer"


class _Client:
    def __init__(self) -> None:
        self.feedback = "unsent"

    def wait_for_server(self, timeout_sec: float) -> bool:
        return True

    def send_goal_async(self, goal, feedback_callback=None):
        self.feedback = feedback_callback
        return object()


def _dispatch(sides: tuple[str, ...]) -> dict[str, _Client]:
    clients = {(side, "move_to"): _Client() for side in (PLANT_SIDE, COUNTERPART_SIDE)}
    boundary = SimpleNamespace(_clients=clients, _forward_feedback=lambda *args: None)
    skill = SimpleNamespace(side_name="move_to")
    handle = SimpleNamespace(request=object())
    TwinBoundary._dispatch(boundary, skill, handle, sides)
    return {side: clients[(side, "move_to")] for side in (PLANT_SIDE, COUNTERPART_SIDE)}


def test_real_forwards_the_counterparts_feedback() -> None:
    """R-08: in REAL the plant runs nothing, so the counterpart's feedback is forwarded."""
    sent = _dispatch((COUNTERPART_SIDE,))
    assert callable(sent[COUNTERPART_SIDE].feedback)
    assert sent[PLANT_SIDE].feedback == "unsent"


def test_a_mode_commanding_the_plant_forwards_the_plants_feedback_alone() -> None:
    sent = _dispatch((PLANT_SIDE, COUNTERPART_SIDE))
    assert callable(sent[PLANT_SIDE].feedback)
    assert sent[COUNTERPART_SIDE].feedback is None
    assert callable(_dispatch((PLANT_SIDE,))[PLANT_SIDE].feedback)
