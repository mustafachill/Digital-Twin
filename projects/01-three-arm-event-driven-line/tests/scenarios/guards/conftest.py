"""Local pytest configuration for the scenario guards.

The guards execute the scenario modules, and those modules decorate their launch
entry point with `@pytest.mark.launch_test` — a real mark owned by
`launch_testing`, registered by its own plugin, which is not loaded here because
this suite is deliberately ROS-free. Without this, every guard run prints
"Unknown pytest.mark.launch_test - is this a typo?" against a mark that is
neither unknown nor a typo, which trains readers to skim warnings.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "launch_test: owned by launch_testing; marks a scenario's launch description",
    )
