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

"""The names L5 owns, checked against the names the two sides own.

**This file is ADR-0050 decision 1 clause 3 as a test:** *nothing is republished
across the boundary, and no L5 endpoint carries a name a side already owns.*
Both sides carry byte-identical names by rule (ADR-0044 clause 1), so an L5
publisher on a side-owned name would be a second publisher of a name that
already has one, feeding every consumer on that side a mixture of two cells.

It is a static check over the generated plan and the frozen contracts, so it
runs without bringing anything up — which is the point: the defect it guards
against produces no symptom at run time.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from ament_index_python.packages import get_package_share_directory
from cite_bringup.plan import default_plan_path, load, SkillActions
import cite_twin
from cite_twin.boundary import (
    asset_namespace,
    BoundaryError,
    operator_endpoint,
    ROOT,
    SKILL_ACTION_TYPES,
    twin_endpoints,
    TWIN_SCOPE,
)
from cite_twin.twin_boundary import _refuse_sim_time
import pytest

PLAN = load(default_plan_path("cell_a"))

#: This package's own source, read from where it was installed from.
PACKAGE_SOURCE = Path(cite_twin.__file__).resolve().parent


def side_owned_names() -> set[str]:
    """Every ROS name the generated plan states for a side.

    Read off the plan rather than listed, so a name the model grows is included
    here without anyone remembering to add it.
    """
    names: set[str] = set()
    for manager in PLAN.controller_managers:
        names.add(manager.node)
        names.add(manager.description_topic)
        for optional in (manager.trajectory_action, manager.gripper_action):
            if optional:
                names.add(optional)
        if manager.skills is not None:
            names.update(
                getattr(manager.skills, field)
                for field in SkillActions.__dataclass_fields__
            )
    for conveyor in PLAN.conveyors:
        names.update({conveyor.state_topic, conveyor.command_topic})
    for sensor in PLAN.sensors:
        names.update({sensor.detection_topic, sensor.level_topic})
    if PLAN.detection is not None:
        names.add(PLAN.detection.detect_action)
    return names


def l5_owned_names() -> set[str]:
    """Every name L5 advertises: its own products, plus one endpoint per skill."""
    names = set(twin_endpoints())
    for manager in PLAN.controller_managers:
        if manager.skills is None:
            continue
        for field in SKILL_ACTION_TYPES:
            names.add(operator_endpoint(getattr(manager.skills, field)))
    return names


class TestNothingIsRepublishedOntoANameASideOwns:
    def test_the_two_name_sets_are_disjoint(self) -> None:
        overlap = side_owned_names() & l5_owned_names()
        assert overlap == set(), (
            f"L5 would advertise {sorted(overlap)}, which the sides already own. "
            "Both sides carry identical names, so this is a second publisher of a "
            "name that already has one on whichever side it lands (ADR-0050, "
            "decision 1 clause 3)."
        )

    def test_every_l5_name_is_under_the_reserved_scope(self) -> None:
        for name in sorted(l5_owned_names()):
            assert name.startswith(f"{TWIN_SCOPE}/"), name

    def test_no_side_owns_anything_under_the_reserved_scope(self) -> None:
        """`/cite/twin/...` is reserved for L5 (`naming-and-namespaces.md`)."""
        for name in sorted(side_owned_names()):
            assert not name.startswith(f"{TWIN_SCOPE}/"), name

    def test_the_plan_actually_carried_some_names(self) -> None:
        """A guard on the guard: an empty set is disjoint from everything."""
        assert len(side_owned_names()) > 10
        assert len(l5_owned_names()) > 10


class TestTheOperatorEndpointIsDerivedRatherThanComposed:
    def test_the_reserved_scope_is_the_only_thing_it_adds(self) -> None:
        assert (
            operator_endpoint("/cite/cell_a/arm_1/move_to")
            == "/cite/twin/cell_a/arm_1/move_to"
        )

    def test_a_name_this_system_did_not_form_is_refused(self) -> None:
        with pytest.raises(BoundaryError):
            operator_endpoint("/somebody_elses/topic")

    def test_the_root_is_not_decided_here(self) -> None:
        """Read the root back off a name rather than composing one.

        A generated name that stopped starting with `/cite` then fails here
        rather than producing a plausible endpoint under a scope nobody
        reserved.
        """
        assert TWIN_SCOPE.startswith(f"{ROOT}/")


class TestTheAssetNamespaceIsReadOffTheModel:
    def test_it_is_a_prefix_of_every_other_name_the_plan_states_for_that_asset(
        self,
    ) -> None:
        """What makes taking the controller manager's parent a derivation.

        The zone and the asset are stated once, in L0, and reach here inside
        every generated name. If the namespace taken here were not a prefix of
        the asset's own action and topic names, it would be a guess.
        """
        for manager in PLAN.controller_managers:
            namespace = asset_namespace(manager)
            owned = [manager.description_topic]
            if manager.skills is not None:
                owned += [
                    getattr(manager.skills, field) for field in SKILL_ACTION_TYPES
                ]
            for name in owned:
                assert name.startswith(f"{namespace}/"), (namespace, name)

    def test_it_names_the_asset(self) -> None:
        for manager in PLAN.controller_managers:
            assert asset_namespace(manager).endswith(f"/{manager.asset}")

    def test_the_joint_state_topic_comes_from_the_plan(self) -> None:
        """**R-04.** The one leaf this package used to write by hand.

        `JOINT_STATE_INTERFACE = "joint_states"` was guarded by nothing:
        renaming it to `"joint_state"` left every test green, and the failure
        mode is a monitor that reports UNMEASURED forever - which is exactly
        what a healthy monitor reports before a side is up, and exactly what
        the launch test asserts is correct. The generator now emits the topic
        beside `description_topic` and L5 reads it.
        """
        for manager in PLAN.controller_managers:
            assert manager.joint_state_topic.startswith(
                f"{asset_namespace(manager)}/"
            ), manager.asset
            assert manager.joint_state_topic != manager.description_topic


class TestL5StartsNothingAndNothingStartsL5:
    """ADR-0047 clause 2 in both directions, checked by reading source.

    That record gives process supervision to a component holding no ROS context
    and defines L5 by *deciding what crosses*. A promise that a component starts
    no processes is not reviewable; a scan is. `cite_bringup` already has the
    same shape of guard for its own supervisor, and its reasoning is that one.

    **WHAT THE FIRST VERSION OF THIS GUARD MISSED**, each verified by mutation
    on 2026-08-31 - every one of them was inserted into a module of this package
    and left the suite green:

    * `from os import system`, which the import branch classified as an import
      of `os` and the call branch never saw, because `system(...)` has no dot.
    * `import os as _o` followed by `_o.system(...)`, for the same reason in
      reverse: the dotted name did not match a list written in terms of `os`.
    * `os.execl` and `os.posix_spawnp`, siblings of names the list did contain.
      A list of nine functions from a module that has thirty is a list that will
      be wrong again, so the rule is now a shape and not a roster.
    * `importlib.import_module` and `__import__`, which fetch a module the
      scanner cannot see the name of.
    * `asyncio.create_subprocess_exec`.

    **And it followed nothing.** L5 imports `cite_bringup`, and two modules of
    that package - `pair.py` and `gz.py` - import `subprocess` because starting
    processes is their job. Importing one of them would have given L5 the
    ability while every module of this package stayed clean. The scan now walks
    the first-party import graph from this package's own modules, so what is
    checked is what L5 can reach rather than what L5 contains.
    """

    #: Imports that would mean this package had grown the ability to start a
    #: process. `launch` and `launch_ros` are here because a
    #: `launch_ros.actions.Node` inside L5 is the tidiest possible way to break
    #: the clause; `asyncio` because `create_subprocess_exec` is in it.
    FORBIDDEN_IMPORTS = frozenset(
        {
            "subprocess",
            "multiprocessing",
            "launch",
            "launch_ros",
            "pty",
            "asyncio",
        }
    )

    #: Names in `os` that start a process, as a SHAPE rather than a roster.
    #:
    #: Every one of `os`'s process-starting functions is `system`, or begins
    #: with one of these. A roster of nine was wrong about `execl` and
    #: `posix_spawnp` on the day it was written.
    FORBIDDEN_OS_PREFIXES = ("exec", "spawn", "fork", "posix_spawn", "popen")
    FORBIDDEN_OS_NAMES = frozenset({"system", "startfile"})

    #: Ways to fetch a module whose name this scanner cannot read.
    OPAQUE_IMPORTS = frozenset({"__import__", "importlib.import_module"})

    #: The first-party packages a module of this one may import. Anything else
    #: is third-party or standard library and is judged by the rules above.
    FIRST_PARTY = ("cite_bringup", "cite_facility", "cite_interfaces", "cite_runtime")

    def test_no_module_l5_can_reach_is_able_to_start_a_process(self) -> None:
        """Parsed rather than grepped, so a mention in prose is not a finding.

        A `grep` for these names fails on the comment that explains why they are
        forbidden, which is how a guard gets deleted for being wrong.
        """
        for module, reached_from in sorted(_reachable_modules(self.FIRST_PARTY)):
            self._check(module, reached_from)

    def test_the_walk_reaches_beyond_this_package(self) -> None:
        """A guard on the guard: a walk that resolved nothing would pass silently.

        L5 imports `cite_bringup.plan` and `cite_facility.model_info`, so both
        must be in the set the scan covers. If they are not, the resolver has
        stopped following imports and the check above is checking one package.
        """
        reached = {module.name for module, _ in _reachable_modules(self.FIRST_PARTY)}
        assert "plan.py" in reached
        assert "model_info.py" in reached

    def test_it_would_catch_a_module_that_can_start_a_process(self) -> None:
        """The anti-vacuous half, stated against `cite_bringup.pair` itself.

        That module imports `subprocess` because supervising processes is its
        job (ADR-0047), and nothing here may import it. Asserting that the
        scanner objects to it is what shows the scanner objects to anything.
        """
        pair = (
            Path(__file__).resolve().parents[2]
            / "cite_bringup/cite_bringup/pair.py"
        )
        assert pair.is_file(), pair
        with pytest.raises(AssertionError):
            self._check(pair, "a deliberate probe")

    @pytest.mark.parametrize(
        "source",
        [
            "from os import system\nsystem('true')\n",
            "import os as _o\n_o.system('true')\n",
            "import os\nos.execl('/bin/true', 'true')\n",
            "import os\nos.posix_spawnp('true', [], {})\n",
            "import importlib\nimportlib.import_module('subprocess')\n",
            "__import__('subprocess')\n",
            "import asyncio\n",
            "import subprocess\n",
            "from launch_ros.actions import Node\n",
        ],
    )
    def test_each_way_around_the_guard_is_now_caught(self, source: str) -> None:
        """One case per hole the review found, driven through the scanner itself."""
        with pytest.raises(AssertionError):
            self._check_source(source, "a probe", "probe.py")

    def test_the_scanner_permits_what_this_package_actually_does(self) -> None:
        """It must not object to `os.environ`, which L5 reads on every start."""
        self._check_source(
            "import os\nfrom pathlib import Path\nvalue = os.environ.get('X')\n",
            "a probe",
            "probe.py",
        )

    def _check(self, module: Path, reached_from: str) -> None:
        self._check_source(
            module.read_text(encoding="utf-8"), reached_from, module.name
        )

    def _check_source(self, source: str, reached_from: str, name: str) -> None:
        where = f"{name} (reached from {reached_from})"
        tree = ast.parse(source, filename=name)
        #: Which local name refers to `os`, so that `import os as _o` is not a
        #: way past a rule written in terms of the word "os".
        os_aliases = {"os"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in self.FORBIDDEN_IMPORTS, (
                        f"{where} imports {root}. L5 may not start processes "
                        "(ADR-0047 clause 2), and a mode may not instantiate "
                        "anything (ADR-0050 decision 4)."
                    )
                    if alias.name == "os":
                        os_aliases.add(alias.asname or "os")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                assert root not in self.FORBIDDEN_IMPORTS, (
                    f"{where} imports from {root}. L5 may not start processes "
                    "(ADR-0047 clause 2)."
                )
                if node.module == "os":
                    for alias in node.names:
                        assert not self._starts_a_process(alias.name), (
                            f"{where} imports os.{alias.name} directly, which is "
                            "how a call with no dot in it gets past a scanner "
                            "that only reads dotted names."
                        )
            elif isinstance(node, ast.Call):
                called = _dotted(node.func)
                assert called not in self.OPAQUE_IMPORTS, (
                    f"{where} calls {called}, which fetches a module this scan "
                    "cannot read the name of. L5 may not start processes "
                    "(ADR-0047 clause 2), and a guard that can be stepped around "
                    "by spelling a name at runtime is not a guard."
                )
                head, _, attribute = called.rpartition(".")
                assert not (
                    head in os_aliases and self._starts_a_process(attribute)
                ), (
                    f"{where} calls {called}. L5 may not start processes "
                    "(ADR-0047 clause 2), and a mode may not instantiate "
                    "anything (ADR-0050 decision 4)."
                )

    def _starts_a_process(self, name: str) -> bool:
        return name in self.FORBIDDEN_OS_NAMES or name.startswith(
            self.FORBIDDEN_OS_PREFIXES
        )

    def test_no_bring_up_starts_the_twin_boundary(self) -> None:
        """A solo bring-up must be exactly what it was before this package existed.

        L5 is a paired component: it needs a zone declaring two sides, and the
        shipped model declares one. A launch graph that started it would fail
        every single-sided bring-up, which is every bring-up anyone runs.
        """
        launch_file = (
            Path(get_package_share_directory("cite_bringup"))
            / "launch"
            / "simulation.launch.py"
        )
        assert launch_file.is_file(), launch_file
        assert "cite_twin" not in launch_file.read_text(encoding="utf-8")


def _dotted(node: ast.expr) -> str:
    """Render `os.system` from the AST node that calls it, or "" for anything else."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))




def _reachable_modules(first_party: tuple[str, ...]) -> set[tuple[Path, str]]:
    """Every source file L5 can reach, by following first-party imports.

    Starts at this package's own modules and follows any `import cite_*` or
    `from cite_*.x import y` to the file behind it, transitively. A module that
    cannot be resolved to a file - an interface package's generated Python, for
    instance - is skipped rather than guessed at, and the guard above asserts
    that the walk still reaches the two modules L5 is known to import, so a
    resolver that silently stopped resolving fails.
    """
    sources = Path(__file__).resolve().parents[2]
    found: set[tuple[Path, str]] = set()
    seen: set[Path] = set()
    queue = [(module, "cite_twin") for module in sorted(PACKAGE_SOURCE.glob("*.py"))]
    while queue:
        module, reached_from = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        found.add((module, reached_from))
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # Both spellings: `from cite_bringup.plan import load` names the
                # module, and `from cite_facility import model_info` names it in
                # the alias. Reading only the first missed every module imported
                # the second way.
                module_name = node.module or ""
                names = [module_name] + [
                    f"{module_name}.{alias.name}" for alias in node.names
                ]
            else:
                continue
            for name in names:
                parts = name.split(".")
                if parts[0] not in first_party or len(parts) < 2:
                    continue
                candidate = sources / parts[0] / parts[0] / f"{parts[-1]}.py"
                if candidate.is_file():
                    queue.append((candidate, module.name))
    return found


class TestUseSimTimeIsRefused:
    """**R-12.** The refusal existed and nothing exercised it.

    L5 holds two contexts whose simulated clocks are independent and separate
    without bound (ADR-0043, ADR-0049), so there is no one simulated clock for
    this process to honour, and ADR-0050 decision 3 pairs two operands on the
    WALL clock for exactly that reason. Every other node in this system honours
    `use_sim_time`; this one refuses to start with it rather than quietly
    ignoring it — and a refusal no test drives is a refusal that will be
    deleted as dead code, or inverted, without anything noticing.

    Driven against a stub rather than a live node: the function reads one
    parameter and one side name, and building two ROS contexts to ask it a
    question would test rclpy.
    """

    class _Parameter:
        def __init__(self, value: bool) -> None:
            self.bool_value = value

    class _Node:
        def __init__(self, value: bool) -> None:
            self._value = value

        def get_parameter(self, name: str):
            assert name == "use_sim_time"
            return self

        def get_parameter_value(self):
            return TestUseSimTimeIsRefused._Parameter(self._value)

    class _Side:
        def __init__(self, value: bool, name: str = "counterpart") -> None:
            self.node = TestUseSimTimeIsRefused._Node(value)
            self.side = SimpleNamespace(name=name)

    def test_a_side_told_to_take_simulated_time_is_refused(self) -> None:
        with pytest.raises(BoundaryError) as refusal:
            _refuse_sim_time(self._Side(True))
        assert "use_sim_time" in str(refusal.value)
        assert "counterpart" in str(refusal.value)

    def test_a_side_on_the_wall_clock_starts(self) -> None:
        _refuse_sim_time(self._Side(False))


def test_every_skill_the_plan_declares_is_routable() -> None:
    """A skill L5 does not know about is one an operator cannot reach, silently.

    `cite_twin.boundary` refuses to import when the two lists differ; this
    states the same thing where a reader looking for the guarantee will find it.
    """
    assert set(SKILL_ACTION_TYPES) == set(SkillActions.__dataclass_fields__)
