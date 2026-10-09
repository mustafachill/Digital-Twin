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

"""Each side's custody, answered by the boundary as a verdict (`Holding.srv`; R-01).

The custody of a side other than the plant used to be read by the program on
that side's own domain, which ADR-0044 clause 3 reserves to the boundary. Pure
logic: what the boundary heard goes in, a verdict per side comes out.
"""

from __future__ import annotations

from cite_twin.custody import holding

ASSETS = ("picker",)


def test_a_side_heard_empty_is_heard_and_not_holding() -> None:
    (answer,) = holding(["plant"], ASSETS, {("plant", "picker"): (False, "")})
    assert answer.heard and not answer.holding and answer.detail == ""


def test_a_side_holding_says_what() -> None:
    (answer,) = holding(["counterpart"], ASSETS, {("counterpart", "picker"): (True, "box_7")})
    assert answer.heard and answer.holding
    assert "picker holds box_7" in answer.detail


def test_a_side_never_heard_is_unheard_never_empty() -> None:
    """An unheard custody is never assumed empty; a side that does not run is unheard."""
    plant, counterpart = holding(
        ["plant", "counterpart"], ASSETS, {("plant", "picker"): (False, "")}
    )
    assert plant.heard
    assert not counterpart.heard and not counterpart.holding
    assert "no RobotState heard from picker" in counterpart.detail


def test_every_arm_on_a_side_must_be_heard() -> None:
    (answer,) = holding(["plant"], ("a", "b"), {("plant", "a"): (False, "")})
    assert not answer.heard and "from b" in answer.detail


def test_answers_keep_the_order_asked() -> None:
    custody = {(side, "picker"): (False, "") for side in ("plant", "counterpart")}
    assert [a.side for a in holding(["counterpart", "plant"], ASSETS, custody)] == [
        "counterpart",
        "plant",
    ]


def test_no_arm_is_never_heard() -> None:
    (answer,) = holding(["plant"], (), {})
    assert not answer.heard
