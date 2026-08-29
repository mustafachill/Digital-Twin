"""Guard: every scenario module loads the way `launch_test` loads it.

Why this exists, because the failure it catches is invisible to the obvious check.

`launch_test` does not import a scenario. It loads it *by path*:

    spec = importlib.util.spec_from_file_location(test_module_name, python_file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

(`launch_testing/launch_test.py`, `_load_python_file_as_module`). The module is
never registered in `sys.modules`, and `test_module_name` is the file's stem. Any
module-level construct that resolves its own module through `sys.modules` — the
one that bit us is `@dataclass` over a string annotation, see `CycleOutcome` in
`pick_and_place.py` — therefore works under `import scenario` and explodes under
`launch_test scenario.py`. The explosion happens during argument parsing, before
a test runs, with a message naming neither the file nor the line:

    launch_test: error: 'NoneType' object has no attribute '__dict__'

"the module imports cleanly" was offered as evidence that this file was fine. It
was a true statement about the wrong loader. This guard tests the right one.

It runs in the ROS-free host suite, so it must not need ROS and must not launch
anything. On a machine with ROS (the container) the scenario's dependencies
import for real and this is an exact rehearsal of what `launch_test` does. On a
machine without ROS (the tooling virtualenv, `./scripts/test --host-only`) the
ROS distributions listed in `ROS_PROVIDED` are replaced by stubs, and everything
else — the class bodies, the decorators, the constant expressions, which is where
this class of defect lives — executes for real. Either way it takes milliseconds
and starts no process.

The stub list is an allowlist and not "stub whatever fails to import" on purpose:
fail-closed means a typo in a scenario's import line fails this guard instead of
being quietly papered over on the host and rediscovered in the container.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import inspect
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

#: The scenario directory, discovered exactly as `./scripts/scenario` discovers
#: it: top-level `*.py`, no recursion. This file lives one level down precisely so
#: that it is not itself offered as a runnable scenario.
SCENARIO_DIR = Path(__file__).resolve().parents[1]

#: Top-level modules supplied by ROS 2, MoveIt, or a workspace package, which are
#: absent from the ROS-free host virtualenv (ADR-0013) and are stubbed there. A
#: scenario that reaches for a ROS package not named here fails this guard with
#: an ImportError; the fix is to add the name, not to widen the rule.
ROS_PROVIDED = frozenset(
    {
        "action_msgs",
        "ament_index_python",
        "builtin_interfaces",
        "cite_bringup",
        "cite_interfaces",
        "control_msgs",
        "controller_manager_msgs",
        "diagnostic_msgs",
        "geometry_msgs",
        "launch",
        "launch_ros",
        "launch_testing",
        "launch_testing_ros",
        "lifecycle_msgs",
        "moveit_msgs",
        "rclpy",
        "ros_gz_interfaces",
        "sensor_msgs",
        "shape_msgs",
        "std_msgs",
        "std_srvs",
        "tf2_geometry_msgs",
        "tf2_ros",
        "trajectory_msgs",
    }
)


def scenario_paths() -> list[Path]:
    return sorted(path for path in SCENARIO_DIR.glob("*.py") if not path.name.startswith("_"))


class _Stub:
    """Stands in for any attribute of a stubbed ROS module.

    Callable, because scenarios call these names at module level — as decorators.
    A call with a single positional callable and nothing else returns that
    callable unchanged, so `@launch_testing.markers.keep_alive` and
    `@launch_testing.post_shutdown_test()` decorate rather than erase what they
    are applied to. Without that, the module would load but
    `generate_test_description` would have been replaced by a stub and the
    assertion below would be testing nothing.
    """

    def __init__(self, path: str) -> None:
        self._path = path

    def __call__(self, *args: object, **kwargs: object) -> object:
        if len(args) == 1 and not kwargs and callable(args[0]):
            return args[0]
        return _Stub(f"{self._path}()")

    def __getattr__(self, name: str) -> _Stub:
        return _Stub(f"{self._path}.{name}")

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<stub {self._path}>"


class _StubModule(types.ModuleType):
    def __getattr__(self, name: str) -> _Stub:
        return _Stub(f"{self.__name__}.{name}")


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Fabricates a module for any name rooted in `ROS_PROVIDED`.

    Only consulted after the real finders have failed, because it is appended to
    `sys.meta_path` rather than prepended: where ROS is actually installed, the
    real package always wins and nothing here is used.
    """

    def __init__(self) -> None:
        self.stubbed: set[str] = set()

    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.split(".")[0] not in ROS_PROVIDED:
            return None
        return importlib.util.spec_from_loader(fullname, self, is_package=True)

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        module = _StubModule(spec.name)
        module.__path__ = []  # type: ignore[attr-defined]
        self.stubbed.add(spec.name)
        return module

    def exec_module(self, module: types.ModuleType) -> None:
        return None


@contextmanager
def _ros_stubs() -> Iterator[_StubFinder]:
    """Install the stub finder, and take out exactly what it put in.

    Only the fabricated modules are evicted afterwards, never the real ones. On a
    machine with ROS the scenarios import genuine `rclpy` and friends, and
    dropping those from `sys.modules` on the way out would force every later test
    to re-import a C extension for no reason.
    """
    finder = _StubFinder()
    sys.meta_path.append(finder)
    try:
        yield finder
    finally:
        sys.meta_path.remove(finder)
        for name in finder.stubbed:
            sys.modules.pop(name, None)


def _load_like_launch_test(path: Path) -> types.ModuleType:
    """Load `path` exactly as `launch_testing.launch_test` does.

    Three lines copied deliberately rather than imported: this guard must keep
    reproducing the loader even if the private upstream helper is renamed.
    `test_scenario_loader_still_matches_upstream` below is what catches the copy
    going stale. Note what is absent — the module is never inserted into
    `sys.modules`, and that absence is the whole defect.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None, f"no import spec for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path", scenario_paths(), ids=lambda path: path.stem)
def test_scenario_loads_by_path(path: Path) -> None:
    """The module executes under a by-path load and exposes its launch entry point."""
    dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        with _ros_stubs() as finder:
            try:
                module = _load_like_launch_test(path)
            except Exception as error:  # the point of this guard is to report any of them
                stubbed = ", ".join(sorted(finder.stubbed)) or "none"
                pytest.fail(
                    f"{path.name} fails to load the way `launch_test` loads it "
                    f"({type(error).__name__}: {error}).\n"
                    f"`import {path.stem}` may well succeed — `launch_test` does not "
                    f"import, it execs the file by path with no `sys.modules` entry, "
                    f"so anything resolving its own module through `sys.modules` "
                    f"(a `@dataclass` over a string annotation, most often) raises "
                    f"here and `./scripts/scenario {path.stem}` dies before its first "
                    f"test.\nROS modules stubbed for this load: {stubbed}"
                )
    finally:
        sys.dont_write_bytecode = dont_write_bytecode

    entry_point = getattr(module, "generate_test_description", None)
    assert entry_point is not None, (
        f"{path.name} defines no `generate_test_description`; `launch_test` has "
        f"nothing to launch and `./scripts/scenario {path.stem}` cannot run it"
    )
    assert callable(entry_point), f"{path.name}: `generate_test_description` is not callable"


def test_at_least_one_scenario_is_checked() -> None:
    """A guard that silently checks nothing is not a guard.

    If the scenario directory moves, the parametrization above collects zero
    cases and the suite still reports green. This is the tripwire for that.
    """
    assert scenario_paths(), f"no scenario modules found under {SCENARIO_DIR}"


def test_scenario_loader_still_matches_upstream() -> None:
    """`_load_like_launch_test` still reflects what `launch_test` actually does.

    Skipped where ROS is absent, so it never runs in `--host-only`; it earns its
    keep in the container run, where it fails if upstream starts registering the
    module in `sys.modules` (which would make the defect above unreachable and
    this guard misleading) or otherwise changes how it loads.
    """
    launch_test = pytest.importorskip(
        "launch_testing.launch_test", reason="ROS is not available in this environment"
    )
    loader = getattr(launch_test, "_load_python_file_as_module", None)
    assert loader is not None, (
        "launch_testing.launch_test._load_python_file_as_module is gone; re-read "
        "how launch_test loads a scenario and update _load_like_launch_test"
    )
    source = inspect.getsource(loader)
    for expected in ("spec_from_file_location", "module_from_spec", "exec_module"):
        assert expected in source, f"upstream loader no longer calls {expected}: {source}"
    assert "sys.modules" not in source, (
        "upstream now registers the scenario in sys.modules; the by-path hazard this "
        f"guard exists for may be gone, and this guard should be re-derived: {source}"
    )
