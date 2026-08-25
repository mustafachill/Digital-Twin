"""The QoS table exists in three places. This keeps them identical.

ADR-0025 puts the profiles in code so the table is not improvised per publisher.
But ROS 2 has two client libraries, so there are unavoidably two implementations,
plus the document that explains them. Two copies of one table drift; a test is
the strongest available mitigation, and it belongs here because this package owns
all three.
"""

from __future__ import annotations

import re
from pathlib import Path

from cite_interfaces import qos

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
HEADER = PACKAGE_ROOT / "include" / "cite_interfaces" / "qos.hpp"
DOCUMENT = PACKAGE_ROOT.parents[2] / "docs" / "interfaces" / "qos-profiles.md"

#: The table, stated once for the test to compare against. Reliability,
#: durability, history, depth — exactly as docs/interfaces/qos-profiles.md.
EXPECTED = {
    "sensor": ("best_effort", "volatile", "keep_last", 5),
    "state": ("reliable", "volatile", "keep_last", 10),
    "command": ("reliable", "volatile", "keep_last", 10),
    "latched": ("reliable", "transient_local", "keep_last", 1),
    "event": ("reliable", "volatile", "keep_all", 100),
}


def test_python_profiles_match_the_table() -> None:
    for name, (reliability, durability, history, depth) in EXPECTED.items():
        profile = getattr(qos, name)()
        assert profile.reliability.name.lower() == reliability, name
        assert profile.durability.name.lower() == durability, name
        assert profile.history.name.lower() == history, name
        if history == "keep_last":
            assert profile.depth == depth, name


def test_cpp_header_defines_every_profile() -> None:
    text = HEADER.read_text()
    for name in EXPECTED:
        assert f"rclcpp::QoS {name}()" in text, f"{name} missing from qos.hpp"


def test_cpp_header_matches_the_table() -> None:
    text = HEADER.read_text()
    bodies = dict(re.findall(r"rclcpp::QoS (\w+)\(\)\s*\{\s*return ([^;]+);", text))
    for name, (reliability, durability, history, depth) in EXPECTED.items():
        body = bodies[name]
        assert reliability in body, f"{name}: expected {reliability} in {body!r}"
        if durability == "transient_local":
            assert "transient_local" in body, name
        else:
            assert "durability_volatile" in body, name
        if history == "keep_all":
            assert "KeepAll()" in body, name
        else:
            assert f"KeepLast({depth})" in body, name


def test_the_document_matches_the_code() -> None:
    """The document is where a reader learns the table, so it must not drift."""
    text = DOCUMENT.read_text()
    rows = re.findall(
        r"^\| `(SENSOR|STATE|COMMAND|LATCHED|EVENT)` \| ([^|]+)\| ([^|]+)\| ([^|]+)\| ([^|]+)\|",
        text,
        re.MULTILINE,
    )
    assert len(rows) == len(EXPECTED), "qos-profiles.md no longer has one row per profile"

    for name, reliability, durability, history, depth in rows:
        expected = EXPECTED[name.lower()]
        assert reliability.strip().lower().replace(" ", "_") == expected[0], name
        assert durability.strip().lower().replace(" ", "_") == expected[1], name
        assert history.strip().lower().replace(" ", "_") == expected[2], name
        assert int(depth.strip()) == expected[3], name
