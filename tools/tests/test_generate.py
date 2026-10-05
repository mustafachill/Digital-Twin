"""Generation. The properties tested here are what the architecture rests on.

ADR-0004 requires byte-identical output because the hand-edit check compares a
committed artifact against a fresh run; ADR-0021 commits the artifacts so that
check can exist at all. Neither is worth anything unless determinism actually
holds, so it is asserted rather than assumed.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from cite_tools import generate as gen
from cite_tools.model import ids
from cite_tools.model.geometry import Pose
from cite_tools.model.loader import load
from cite_tools.model.resolve import resolve


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


def per_zone(path: Path, template: str) -> list[str]:
    """One artifact path per declared zone, sorted, from ``template``.

    Three assertions below are of the form "exactly one of this artifact exists,
    per zone", and each of them used to spell the answer as a one-element list
    naming the one zone there was. That made them assertions about how many cells
    the facility declares as well as about the property they were written for,
    and declaring a second zone (ADR-0056) falsified all three at once while the
    property each was protecting held perfectly.

    Derived from the model rather than listed, so the next zone falsifies none of
    them. The sort is on the formatted path and not on the zone id: they coincide
    while every template has a constant prefix, and relying on that would be a
    coincidence rather than a reason.
    """
    return sorted(template.format(zone=zone.id) for zone in load(path).zones)


#: The zone and the arm the single-zone model declares. Named once here so that a
#: test asserting on "the arm" reads which one, and so that the day a second zone
#: or arm is declared moves one line rather than every test.
ZONE = "cell_b"
ARM = "picker"


def robot_ids(path: Path) -> list[str]:
    """Every arm the model declares in `ZONE`, sorted — asked, never listed."""
    return sorted(asset.id for asset in resolve(load(path), ZONE).of_category("robot"))


class TestDeterminism:
    def test_two_runs_are_byte_identical(self, real_model: Path) -> None:
        assert artifacts(real_model) == artifacts(real_model)

    def test_ten_runs_agree(self, real_model: Path) -> None:
        model = load(real_model)
        digests = {
            tuple(sorted((a.path, a.content) for a in gen.generate(model))) for _ in range(10)
        }
        assert len(digests) == 1

    def test_no_timestamp_leaks_into_output(self, real_model: Path) -> None:
        # A timestamp would make every artifact differ on every run, which turns
        # the hand-edit check into noise and gets it ignored.
        import re

        blob = "\n".join(artifacts(real_model).values())
        for pattern in (r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", r"\b\d{10}\.\d+\b"):
            assert not re.search(pattern, blob), f"a timestamp matching {pattern} was emitted"

    def test_the_model_source_path_does_not_leak_into_output(self, real_model: Path) -> None:
        # `real_model` is a temporary copy, so if any generator embedded the path
        # it read from, that path appears here and would differ on every machine
        # and every run. This is the check that catches an absolute path leak,
        # which a hostname or username check cannot — "cite" is both this
        # project's name and the container's user.
        blob = "\n".join(artifacts(real_model).values())
        assert str(real_model) not in blob
        assert str(real_model.parent) not in blob

    def test_splitting_a_model_file_changes_nothing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Ordering comes from sorting by id, never from the filesystem, so how
        # the model is divided across files must be invisible downstream.
        before = artifacts(real_model)

        # The fixtures file, because it is a file with more than one asset to
        # split: a document may not be empty.
        instances = real_model / "assets/instances/fixtures.yaml"
        import yaml

        document = yaml.safe_load(instances.read_text())
        first, rest = document["assets"][:1], document["assets"][1:]
        instances.write_text(yaml.safe_dump({**document, "assets": first}, sort_keys=False))
        (real_model / "assets/instances/fixtures_more.yaml").write_text(
            yaml.safe_dump({**document, "assets": rest}, sort_keys=False)
        )

        assert artifacts(real_model) == before

    def test_renaming_a_model_file_changes_nothing(self, real_model: Path) -> None:
        before = artifacts(real_model)
        source = real_model / "assets/instances/arms.yaml"
        source.rename(real_model / "assets/instances/zzz_manipulators.yaml")
        assert artifacts(real_model) == before


class TestHandEditDetection:
    def test_a_clean_tree_reports_nothing(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        assert gen.differences(produced, out) == []

    def test_a_changed_byte_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        target = out / "worlds/cell_b.sdf"
        target.write_text(target.read_text().replace("0.001", "0.002", 1))
        assert any(
            "differs from a fresh generator run" in p for p in gen.differences(produced, out)
        )

    def test_a_missing_file_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds/cell_b.sdf").unlink()
        assert any("missing" in p for p in gen.differences(produced, out))

    def test_a_stale_file_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds" / "left_over.sdf").write_text("stale\n")
        assert any("stale" in p for p in gen.differences(produced, out))

    def test_write_removes_stale_files(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds" / "left_over.sdf").write_text("stale\n")
        gen.write(produced, out)
        assert not (out / "worlds" / "left_over.sdf").exists()


class TestModelHash:
    def test_is_stable_for_the_same_content(self, real_model: Path) -> None:
        assert gen.model_hash(load(real_model)) == gen.model_hash(load(real_model))

    def test_changes_when_the_facility_changes(self, real_model: Path, edit_yaml: Callable) -> None:
        before = gen.model_hash(load(real_model))
        edit_yaml(
            real_model / "assets/instances/conveyors.yaml",
            lambda d: d["assets"][0]["pose"].__setitem__("xyz_m", [1.4, 0.0, 0.0]),
        )
        assert gen.model_hash(load(real_model)) != before

    def test_does_not_change_when_only_the_file_layout_changes(self, real_model: Path) -> None:
        # A recording is stamped with this hash (L6). It must identify the
        # facility that was described, not the files it was written in.
        before = gen.model_hash(load(real_model))
        (real_model / "assets/instances/arms.yaml").rename(
            real_model / "assets/instances/manipulators.yaml"
        )
        assert gen.model_hash(load(real_model)) == before

    def test_does_not_change_when_a_template_changes(
        self, real_model: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The digest is over the model, and a generator edit is not a model edit.

        Stated as a property rather than as a recorded value, because the value
        is what a stale record quotes. ADR-0048's *Consequences* said that
        removing a key from the bring-up plan would land "a `cite_generated/`
        diff and a new `MODEL_HASH`"; the diff is real and the new hash is not,
        and this is what says so for every future template edit rather than for
        that one.

        Driven by editing the bring-up template on a copy and rendering through
        it: the plan artifact must move and the hash must not. Asserting the
        first is what stops this passing because the edit reached nothing.
        """
        import shutil

        from jinja2 import FileSystemLoader

        from cite_tools import render
        from cite_tools.generate import bringup

        model = load(real_model)
        before_hash = gen.model_hash(model)
        before = artifacts(real_model)

        templates = Path(render.__file__).parent / "templates"
        copied = tmp_path / "templates"
        shutil.copytree(templates, copied)
        plan_template = copied / "bringup" / "plan.yaml.j2"
        plan_template.write_text(plan_template.read_text() + "  # a line no model ever stated\n")

        def through_the_copy() -> object:
            env = render.environment()
            env.loader = FileSystemLoader(str(copied))
            return env

        monkeypatch.setattr(bringup, "environment", through_the_copy)
        after = artifacts(real_model)

        assert after["bringup/cell_b_plan.yaml"] != before["bringup/cell_b_plan.yaml"], (
            "the template edit reached no artifact, so this test would pass "
            "whatever the hash did"
        )
        assert gen.model_hash(load(real_model)) == before_hash
        assert after["MODEL_HASH"] == before["MODEL_HASH"]


class TestGrowingTheLineIsDataOnly:
    """The Phase 1 exit criterion, in miniature.

    "The entire cell layout is changeable by editing the facility model alone."
    Adding an arm must change generated artifacts and nothing else — if it ever
    requires editing a launch file or a controller config by hand, P1 has been
    broken somewhere upstream.
    """

    def test_a_second_arm_needs_no_code_change(self, real_model: Path, add_arm: Callable) -> None:
        arm = add_arm(real_model, "arm_new")

        produced = artifacts(real_model)
        controllers = f"control/{ZONE}_{arm}_controllers.yaml"
        description = f"description/{ZONE}_{arm}.urdf.xacro"
        assert controllers in produced
        assert f"{arm}_joint_trajectory_controller" in produced[controllers]
        assert description in produced
        assert f"/cite/{ZONE}/{arm}" in produced[description]
        assert arm in produced[f"bringup/{ZONE}_plan.yaml"]


#: One macro argument per line, which is what lets the parity test below account
#: for a differing line by NAME rather than by position or by count.
_MACRO_ARGUMENT = re.compile(r'^\s*([a-z_][a-z0-9_]*)=".*"\s*$')


def _argument_name(line: str) -> str | None:
    """The macro argument a generated line declares, or None if it declares none."""
    match = _MACRO_ARGUMENT.match(line)
    return match.group(1) if match else None


#: An address for tests, from RFC 5737's TEST-NET-3 block, which is reserved for
#: documentation and routes nowhere. No real robot address is ever written into
#: this tree (ADR-0070 item 2).
TEST_ADDRESS = "203.0.113.7"


def _controller_configuration(text: str) -> dict:
    """A generated controller configuration, parsed: what a controller manager reads."""
    document = yaml.safe_load(text)
    assert isinstance(document, dict), text
    return document


def _without_controllers(document: dict, names: set[str]) -> dict:
    """``document`` with every trace of the controllers ``names`` removed.

    A controller appears twice in a configuration: as a `type` entry under the
    controller manager's parameters, and as its own top-level block keyed by its
    namespaced name. Both go, and nothing else does.
    """
    trimmed = yaml.safe_load(yaml.safe_dump(document))
    for key, block in trimmed.items():
        if key.endswith("/controller_manager"):
            for name in names:
                block["ros__parameters"].pop(name)
    return {key: block for key, block in trimmed.items() if key.rsplit("/", 1)[-1] not in names}


#: The vendor driver's node, as the physical backend's plugin constructs it
#: (`uf_robot_system_hardware.cpp:53`), in the asset's namespace.
_DRIVER_NODE = "/cite/cell_b/picker/ufactory_driver"


def _without_vendor_driver(document: dict) -> dict:
    """``document`` less the physical backend's vendor-driver block, which must be there.

    The one thing a physical side's configuration ADDS: the services its
    embedded vendor driver is to create (ADR-0070). It carries no controller,
    joint or interface name, so it is not a P2 difference; it is removed by name
    and only after asserting it is present, so this cannot hide a block that
    went missing.
    """
    trimmed = yaml.safe_load(yaml.safe_dump(document))
    block = trimmed.pop(_DRIVER_NODE)
    assert set(block["ros__parameters"]) == {"services"}, block
    return trimmed


def _with_sim_time(document: dict, value: bool) -> dict:
    flipped = yaml.safe_load(yaml.safe_dump(document))
    for key, block in flipped.items():
        if key.endswith("/controller_manager"):
            block["ros__parameters"]["use_sim_time"] = value
    return flipped


class TestSimRealParity:
    """P2, asserted on the generator rather than hoped for at run time."""

    def test_only_the_plugin_differs_between_backends(
        self, real_model: Path, edit_yaml: Callable, add_arm: Callable
    ) -> None:
        # A second arm that stays `sim`, so that "a backend is a per-instance
        # choice" has an instance to be asked of (ADR-0069 left one arm).
        other = add_arm(real_model)
        sim = artifacts(real_model)

        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0].__setitem__(
                "hardware",
                {"backend": "real", "params": {"real": {"robot_ip": TEST_ADDRESS}}},
            ),
        )
        real = artifacts(real_model)

        # Controller and joint names are identical. If this ever fails, P2 is
        # broken and everything above L2 becomes unfounded. Two differences are
        # allowed and both are named: `use_sim_time`, and the gripper controller,
        # which the `real` backend does not load because the vendor's physical
        # component exports no gripper joint (`exports_end_effector_joints:
        # false`, ADR-0070 item 4) — its action name is served by a relay.
        sim_controllers = _controller_configuration(sim["control/cell_b_picker_controllers.yaml"])
        real_controllers = _controller_configuration(real["control/cell_b_picker_controllers.yaml"])
        assert _with_sim_time(
            _without_controllers(sim_controllers, {f"{ARM}_gripper_controller"}), False
        ) == _without_vendor_driver(real_controllers)
        assert _DRIVER_NODE not in sim_controllers

        # The description differs in exactly two lines, and the second of them
        # arrived on 2026-09-01 when the shipped collision selection moved to the
        # derived hulls (ADR-0028). Only the shipped arm was switched, so the
        # second arm's description must be untouched — a backend is a
        # per-instance choice, not a global mode.
        #
        # WHY A SECOND DIFFERING LINE IS NOT A P2 BREAK, checked below rather than
        # asserted here. `xarm_device_macro.xacro` resolves its OWN mesh root as
        # `file://$(find xarm_description)/meshes` under a Gazebo plugin and
        # `package://xarm_description/meshes` under anything else, so the root
        # that REPLACES it has to branch the same way or the two halves of one
        # description resolve differently (ADR-0028's correction of 2026-08-31,
        # and `CollisionSpec.root_uri_scheme`). That asymmetry has always been in
        # the vendor's expansion; binding a derived root is what made it visible
        # in an artifact this test can read. **The geometry is identical on both
        # backends** — same package, same root, same thirteen meshes — and P2's
        # subjects (topic, action, controller, joint and frame names) are
        # untouched. So the assertion is tightened rather than widened: the
        # collision line has to differ in its URI SCHEME and in nothing else.
        # The two descriptions no longer have the same number of lines, and how
        # that is reconciled is the whole of this block. `arm.urdf.xacro.j2`
        # emits one macro argument per line, so a backend that declares an
        # instance parameter adds one line to its arm's description and none to
        # the other's (ADR-0053). Every such line is accounted for BY MACRO
        # ARGUMENT NAME below and then removed, so the comparison that follows is
        # still line-for-line under `strict=True` over equal-length lists.
        #
        # WIDENING THIS IS THE FAILURE MODE, not the fix. Dropping `strict=True`,
        # or relaxing `len(rest) == 1` to a bound, makes the mismatch go away and
        # retires the property this test exists for — that between two backends
        # NOTHING differs except the plugin, the collision root's URI scheme and
        # the arguments named here. The length equality is therefore asserted
        # explicitly as well, so that removing the keyword cannot quietly retire
        # it either.
        sim_lines = sim["description/cell_b_picker.urdf.xacro"].splitlines()
        real_lines = real["description/cell_b_picker.urdf.xacro"].splitlines()

        accounted = ("robot_ip",)
        surplus = [line for line in real_lines if _argument_name(line) in accounted]
        assert tuple(_argument_name(line) for line in surplus) == accounted, real_lines
        assert [line for line in sim_lines if _argument_name(line) in accounted] == []
        trimmed_real = [line for line in real_lines if _argument_name(line) not in accounted]
        assert len(trimmed_real) == len(sim_lines), (
            "the `real` description carries a line the `sim` one does not, and it is not "
            "one of the macro arguments accounted for above"
        )

        differing = [(a, b) for a, b in zip(sim_lines, trimmed_real, strict=True) if a != b]
        plugin = [pair for pair in differing if "ros2_control_plugin" in pair[0]]
        rest = [pair for pair in differing if "ros2_control_plugin" not in pair[0]]
        assert len(plugin) == 1, differing
        assert len(rest) == 1, differing

        sim_line, real_line = rest[0]
        assert "collision_mesh_path" in sim_line, differing
        assert sim_line.replace("file://$(find cite_description)", "") == real_line.replace(
            "package://cite_description", ""
        ), (sim_line, real_line)

        key = f"description/{ZONE}_{other}.urdf.xacro"
        assert sim[key] == real[key], f"{other} changed when only {ARM} was switched"


class TestSideParity:
    """ADR-0048 clause 2's invariant, on the side axis, against the shipped model.

    The backend-axis test above switches ONE side of one arm between backends.
    This one reads what the shipped model actually generates for its two sides —
    a simulated plant and a physical counterpart (ADR-0070) — and requires that
    the counterpart's two artifacts differ from the plant's in exactly the ways
    listed, each with its reason, and in no other. "The sides carry identical
    names" is a diff this test takes, not a rule someone has to remember.
    """

    def test_the_counterpart_differs_from_the_plant_only_in_its_hardware(
        self, real_model: Path
    ) -> None:
        """The description: what differs, line by line, and why each is not a P2 break.

        ADR-0070 item 1 states the invariant as "only `ros2_control_plugin`
        lines". What the generated text actually shows is that plus four more,
        and every one is a consequence of a decision already taken rather than a
        name that moved:

        1. **`ros2_control_plugin`** — the hardware, which is the point.
        2. **`robot_ip="$(arg robot_ip)"`**, one line the plant does not have:
           the `real` backend declares the parameter and the `sim` one does not
           (ADR-0053), and its value is an environment reference resolved at
           launch (ADR-0070 item 2), so the description carries an xacro
           argument and never an address.
        3. **`collision_mesh_path`**, scheme only: the root's URI scheme is L0
           data per backend because the vendor's own mesh root branches on the
           plugin (`CollisionSpec.root_uri_scheme`, ADR-0028). Same package, same
           root, same meshes.
        4. **The `<parameters>` line of the Gazebo block** names the side's own
           controller configuration. Inert on a side that starts no Gazebo, and
           correct on one that does.
        5. **The track's `<ros2_control>` block, absent**: the physical track's
           backend declares no plugin, because the vendor serves it only through
           `xarm_api` services (ADR-0070 item 3). The track's JOINT stays — the
           prismatic joint, its limits and its carriage are identical — so every
           frame and joint name is unchanged.

        **And one thing that does not show here, on purpose.** The vendor macro
        itself omits the gripper's `<ros2_control>` block for
        `uf_robot_hardware/UFRobotSystemHardware` (`xarm_gripper_macro.xacro`),
        and it decides that from the plugin argument in item 1, so the generated
        text carries no line for it. The expanded description does differ there;
        `cite_description`'s plugin test expands both sides and checks what each
        `<ros2_control>` block loads.
        """
        generated = artifacts(real_model)
        plant_path = gen.arm_description_path(ZONE, ARM, ids.PLANT_SIDE)
        counterpart_path = gen.arm_description_path(ZONE, ARM, ids.COUNTERPART_SIDE)
        plant = generated[plant_path].splitlines()
        counterpart = generated[counterpart_path].splitlines()

        # (2) the argument the plant does not have, read from the environment.
        accounted = [line for line in counterpart if _argument_name(line) == "robot_ip"]
        assert [line.strip() for line in accounted] == ['robot_ip="$(arg robot_ip)"']
        assert not [line for line in plant if _argument_name(line) == "robot_ip"]
        counterpart = [line for line in counterpart if _argument_name(line) != "robot_ip"]

        # (5) the track's hardware block, removed from the plant as one run. Its
        # boundaries are found, not counted, and what is inside is checked.
        track_joint = ids.joint("picker_track", "joint")
        opening = next(
            i
            for i, line in enumerate(plant)
            if f'<ros2_control name="{track_joint}_system"' in line
        )
        # Its comment opens the run: the last comment opening before the block,
        # with nothing but comment text between the two.
        start = max(i for i in range(opening) if plant[i].strip().startswith("<!--"))
        assert all("<" not in line for line in plant[start + 1 : opening]), plant[start:opening]
        end = next(i for i in range(opening, len(plant)) if "</ros2_control>" in plant[i])
        block = plant[start : end + 1]
        assert block[0].strip().startswith("<!-- One hardware component for the track"), block
        assert f'<joint name="{track_joint}">' in "\n".join(block)
        assert not [line for line in counterpart if "<ros2_control" in line], (
            "the counterpart's description claims a joint with a <ros2_control> block "
            "it should not have"
        )
        plant = plant[:start] + plant[end + 1 :]

        assert len(plant) == len(counterpart), (
            "the counterpart's description has a line the plant's does not, and it is "
            "not one of the differences accounted for above"
        )
        differing = [(a, b) for a, b in zip(plant, counterpart, strict=True) if a != b]
        by_kind: dict[str, list[tuple[str, str]]] = {}
        for pair in differing:
            kind = next(
                (
                    k
                    for k in ("ros2_control_plugin", "collision_mesh_path", "<parameters>")
                    if k in pair[0] and k in pair[1]
                ),
                "unaccounted",
            )
            by_kind.setdefault(kind, []).append(pair)
        assert sorted(by_kind) == [
            "<parameters>",
            "collision_mesh_path",
            "ros2_control_plugin",
        ], differing
        assert all(len(pairs) == 1 for pairs in by_kind.values()), differing

        # (1) only the plugin string moves on its line.
        ((sim_line, real_line),) = by_kind["ros2_control_plugin"]
        model = load(real_model)
        arm_type = model.asset_type("xarm5")
        assert arm_type is not None
        backends = arm_type.hardware_backends
        assert sim_line.replace(str(backends["sim"].ros2_control_plugin), "") == real_line.replace(
            str(backends["real"].ros2_control_plugin), ""
        )
        # (3) the scheme and nothing else.
        ((sim_line, real_line),) = by_kind["collision_mesh_path"]
        assert sim_line.replace("file://$(find cite_description)", "") == real_line.replace(
            "package://cite_description", ""
        )
        # (4) the side's own configuration and nothing else.
        ((sim_line, real_line),) = by_kind["<parameters>"]
        assert sim_line.replace(gen.controllers_path(ZONE, ARM, ids.PLANT_SIDE), "") == (
            real_line.replace(gen.controllers_path(ZONE, ARM, ids.COUNTERPART_SIDE), "")
        )

    def test_the_counterpart_loads_the_plants_controllers_less_the_unserved_ones(
        self, real_model: Path
    ) -> None:
        """The controller configuration: `use_sim_time`, and two absences, each named.

        ADR-0070 item 1 allows `use_sim_time` and "what item 4 removes", the
        gripper controller. The track's trajectory controller is absent as well,
        and that is item 3 rather than an omission from item 1: no hardware on
        the physical side exports the track joint, so a controller claiming it
        would fail to configure, and the track adapter serves that controller's
        `joint_trajectory` topic under the same name instead. Every remaining
        controller, joint, interface, tolerance and rate is the plant's.
        """
        generated = artifacts(real_model)
        plant = _controller_configuration(
            generated[gen.controllers_path(ZONE, ARM, ids.PLANT_SIDE)]
        )
        counterpart = _controller_configuration(
            generated[gen.controllers_path(ZONE, ARM, ids.COUNTERPART_SIDE)]
        )
        unserved = {f"{ARM}_gripper_controller", "picker_track_trajectory_controller"}
        assert _with_sim_time(_without_controllers(plant, unserved), False) == (
            _without_vendor_driver(counterpart)
        )
        # And the absences are absences, not renames: neither name is anywhere in
        # the counterpart's configuration.
        text = generated[gen.controllers_path(ZONE, ARM, ids.COUNTERPART_SIDE)]
        assert not [name for name in unserved if name in text]


class TestBindings:
    def test_an_unknown_binding_is_an_error_not_a_default(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Silently handing the vendor macro its own default would produce a
        # description that loads and is wrong.
        from cite_tools.generate.description import BindingError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["description"]["bound_args"].__setitem__(
                "prefix", "instance.prefxi"
            ),
        )
        with pytest.raises(BindingError, match="instance.prefxi"):
            artifacts(real_model)


class TestOneCoordinatePerFrame:
    """P1 across the two representations a frame can appear in.

    An L0 frame reaches the running system twice: as a link in the scene
    description, published by `robot_state_publisher`, and as a row in the static
    transform table. Both are live. When they disagree the system does not fail —
    it carries two answers for one name and hands out whichever the consumer
    happened to ask for.

    That is not hypothetical. The description generator subtracted half a body
    height from every type frame, which would only have been right if the link
    origin were the box centre; it is the foot. A pedestal's `top` was published
    at z = 0.300 as a URDF link and at z = 0.600 as a static transform, 0.3 m
    below where the arm was actually bolted, and nothing consumed the URDF-side
    name yet — which is exactly what made it dangerous.
    """

    @staticmethod
    def _urdf_world_poses(scene_xml: str) -> dict[str, Pose]:
        """Every named-frame link in the scene, resolved into `cite_world`."""
        root = ElementTree.fromstring(scene_xml)
        joints = {}
        for joint in root.findall("joint"):
            origin = joint.find("origin")
            xyz = tuple(float(v) for v in (origin.get("xyz") or "0 0 0").split())
            rpy = tuple(float(v) for v in (origin.get("rpy") or "0 0 0").split())
            parent = joint.find("parent").get("link")
            child = joint.find("child").get("link")
            joints[child] = (parent, Pose(xyz_m=xyz, rpy_rad=rpy))

        poses: dict[str, Pose] = {}
        for child, (parent, local) in joints.items():
            # Walk to the root, composing parent-then-child. Frame links hang off
            # a body's base_link, which hangs off cite_world.
            pose = local
            current = parent
            while current in joints:
                grandparent, up = joints[current]
                pose = up.compose(pose)
                current = grandparent
            if current == ids.WORLD_FRAME:
                poses[child] = pose
        return poses

    def test_every_frame_has_the_same_world_pose_in_both_representations(
        self, real_model: Path
    ) -> None:
        model = load(real_model)
        produced = artifacts(real_model)
        table = yaml.safe_load(produced["frames/cell_b_static_tf.yaml"])
        urdf = self._urdf_world_poses(produced["description/cell_b_scene.urdf.xacro"])

        static = {
            row["child"]: Pose(xyz_m=tuple(row["xyz_m"]), rpy_rad=tuple(row["rpy_rad"]))
            for row in table["static_transforms"]
        }

        checked = 0
        for asset in resolve(model, "cell_b").assets:
            for named in asset.asset_type.frames:
                link_name = ids.link(asset.id, named.id)
                frame_name = ids.frame("cell_b", asset.id, named.id)
                if named.link is not None:
                    # Published by robot_state_publisher from a vendor
                    # description. Neither generator may emit a second copy.
                    assert link_name not in urdf, f"{link_name} duplicates a vendor link"
                    assert frame_name not in static, f"{frame_name} duplicates a vendor link"
                    continue
                assert link_name in urdf, f"{link_name} is missing from the scene description"
                assert frame_name in static, f"{frame_name} is missing from the static TF table"
                assert urdf[link_name].approx_equal(static[frame_name], tol=1e-9), (
                    f"{named.id} on {asset.id} resolves to "
                    f"{urdf[link_name].xyz_m} as a URDF link and "
                    f"{static[frame_name].xyz_m} as a static transform"
                )
                checked += 1
        # A test that silently checked nothing would pass forever. The tables, the
        # belt and the beams carry seven authored frames between them.
        assert checked >= 5, f"only {checked} frames were compared"

    def test_a_reintroduced_half_height_offset_is_caught(self, real_model: Path) -> None:
        # The exact defect, re-injected: raise the table's own frame without
        # touching its body. The two representations must stop agreeing.
        import yaml as _yaml

        target = real_model / "assets/types/fixtures/work_table_600.yaml"
        document = _yaml.safe_load(target.read_text())
        document["asset_type"]["frames"][0]["xyz_m"] = [0.0, 0.0, 0.3]
        target.write_text(_yaml.safe_dump(document, sort_keys=False))

        produced = artifacts(real_model)
        urdf = self._urdf_world_poses(produced["description/cell_b_scene.urdf.xacro"])
        table = yaml.safe_load(produced["frames/cell_b_static_tf.yaml"])
        static = {
            row["child"]: Pose(xyz_m=tuple(row["xyz_m"]), rpy_rad=tuple(row["rpy_rad"]))
            for row in table["static_transforms"]
        }
        # Both representations must move together, so they still agree with each
        # other — and both must show the new height rather than the old one.
        assert urdf["infeed_table_surface"].approx_equal(static["cell_b__infeed_table__surface"])
        assert round(urdf["infeed_table_surface"].xyz_m[2], 6) == 0.3


class TestFramesOfVendorLinks:
    """H2: `NamedFrame.link` is read, not merely documented."""

    def test_a_link_backed_frame_is_not_published_as_a_static_transform(
        self, real_model: Path
    ) -> None:
        # `tcp` on the xArm names `link_tcp`, which robot_state_publisher
        # publishes at wherever forward kinematics puts it. Emitting it here as
        # well produced a STATIC transform at the arm's mount — the canonical
        # name for the tool centre point, answering with a constant.
        table = yaml.safe_load(artifacts(real_model)["frames/cell_b_static_tf.yaml"])
        children = {row["child"] for row in table["static_transforms"]}
        assert "cell_b__picker__tcp" not in children
        assert "cell_b__picker__base" not in children
        # The mount is still there: nothing else ties the arm's own model to the
        # facility, and without it TF has two disconnected trees.
        assert "picker_mount" in children

    def test_clearing_the_link_makes_the_frame_appear(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The complement, so the test above cannot pass by the rule never firing.
        def mutate(document: dict) -> None:
            for frame in document["asset_type"]["frames"]:
                frame.pop("link", None)

        edit_yaml(real_model / "assets/types/robots/xarm5.yaml", mutate)
        table = yaml.safe_load(artifacts(real_model)["frames/cell_b_static_tf.yaml"])
        children = {row["child"] for row in table["static_transforms"]}
        assert "cell_b__picker__tcp" in children


class TestMassIsWhereTheGeometryIs:
    """M-07: a centroidal tensor declared at the body's foot is a lie."""

    def test_the_inertial_origin_carries_the_same_half_height_as_the_geometry(
        self, real_model: Path
    ) -> None:
        scene = artifacts(real_model)["description/cell_b_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        checked = 0
        for link in root.findall("link"):
            inertial = link.find("inertial")
            collision = link.find("collision")
            if inertial is None or collision is None:
                continue
            mass_z = float((inertial.find("origin").get("xyz")).split()[2])
            box_z = float((collision.find("origin").get("xyz")).split()[2])
            assert mass_z == box_z, (
                f"{link.get('name')} declares its mass at z={mass_z} while its "
                f"collision box is centred at z={box_z}"
            )
            checked += 1
        assert checked >= 4, f"only {checked} bodies were compared"

    def test_a_centre_of_mass_offset_is_applied_from_the_box_centre(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # `com_m` is measured from the collision box centre, which is the same
        # reference validate.physical uses. A table whose mass sits 0.25 m low
        # must land at z = 0.05 in the link frame, not at z = -0.25 below it.
        edit_yaml(
            real_model / "assets/types/fixtures/work_table_600.yaml",
            lambda d: d["asset_type"]["description"]["body"]["inertial"].__setitem__(
                "com_m", [0.0, 0.0, -0.25]
            ),
        )
        scene = artifacts(real_model)["description/cell_b_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        links = root.findall("link")
        link = next(e for e in links if e.get("name") == "infeed_table_base_link")
        z = float(link.find("inertial").find("origin").get("xyz").split()[2])
        assert round(z, 9) == 0.05


class TestEverythingIsAnchored:
    """H3: nothing in the cell stands on the ground by friction alone."""

    def test_the_scene_is_static(self, real_model: Path) -> None:
        scene = artifacts(real_model)["description/cell_b_scene.urdf.xacro"]
        root = ElementTree.fromstring(scene)
        statics = [
            element.text
            for gazebo in root.findall("gazebo")
            for element in gazebo.findall("static")
        ]
        assert statics == ["true"], (
            "the cell furniture lumps into one free rigid body without this; three "
            "arms' reaction torques then slide it and the symptom reads as drift"
        )

    def test_every_arm_is_bolted_to_the_world(self, real_model: Path) -> None:
        produced = artifacts(real_model)
        arms = robot_ids(real_model)
        assert arms, "the model declares no arm, so this would check nothing"
        for arm in arms:
            root = ElementTree.fromstring(produced[f"description/{ZONE}_{arm}.urdf.xacro"])
            anchors = [
                joint
                for gazebo in root.findall("gazebo")
                for joint in gazebo.findall("joint")
                if joint.get("type") == "fixed"
            ]
            assert len(anchors) == 1, f"{arm} has {len(anchors)} world anchors"
            assert anchors[0].find("parent").text == "world"
            assert anchors[0].find("child").text == f"{arm}_mount"
            # No pose: the spawn pose in the bring-up plan places the model, and
            # a pose here would apply the same displacement twice.
            assert anchors[0].find("pose") is None

    def test_the_arm_anchor_is_invisible_to_robot_state_publisher(self, real_model: Path) -> None:
        # The anchor lives inside <gazebo> precisely so TF never sees it. A URDF
        # joint from a link named `world` would give picker_mount a second parent
        # alongside the generated static transform table.
        #
        # The arm rides a track (ADR-0067), so its description does carry URDF
        # joints — the prismatic carriage joint among them. What may not exist is
        # one that reaches `world`: the mount is the description's root, and
        # nothing in it is parented to a link the static transform table owns.
        root = ElementTree.fromstring(artifacts(real_model)["description/cell_b_picker.urdf.xacro"])
        links = [link.get("name") for link in root.findall("link")]
        children = {joint.find("child").get("link") for joint in root.findall("joint")}
        parents = {joint.find("parent").get("link") for joint in root.findall("joint")}
        assert "world" not in links
        assert "world" not in parents
        assert "picker_mount" in links and "picker_mount" not in children


class TestPlanningSceneIsGenerated:
    """M-08: the planner is told what the cell contains."""

    def test_every_authored_body_becomes_a_collision_object(self, real_model: Path) -> None:
        produced = artifacts(real_model)
        scene = yaml.safe_load(produced["moveit/cell_b_planning_scene.yaml"])
        objects = {o["id"]: o for o in scene["planning_scene"]["collision_objects"]}
        # DERIVED FROM THE MODEL, not listed again here. The list that used to be
        # written out was a second copy of the cell's inventory, and adding
        # `beam_pick` to L0 failed this test for saying so — a test that has to be
        # edited whenever the model gains an asset is testing the editor, not the
        # generator. What the generator promises is that every AUTHORED body
        # becomes a collision object, which is what the name says and what this
        # now asserts.
        expected = {
            asset.id
            for asset in resolve(load(real_model), "cell_b").assets
            if asset.asset_type.description.body is not None
        }
        assert expected, "no authored body was found, so this test asserted nothing"
        assert set(objects) == expected
        # Arms are deliberately absent: an articulated robot frozen at a pose is
        # confidently wrong wherever it actually is.
        assert not set(robot_ids(real_model)) & set(objects)

    def test_a_collision_object_agrees_with_the_scene_description(self, real_model: Path) -> None:
        # Same geometry, same place — the planner's cell and the simulator's cell
        # come from one resolved body, so they cannot drift.
        produced = artifacts(real_model)
        scene = yaml.safe_load(produced["moveit/cell_b_planning_scene.yaml"])
        table = next(
            o for o in scene["planning_scene"]["collision_objects"] if o["id"] == "infeed_table"
        )
        assert table["primitive"]["dimensions_m"] == [0.6, 0.6, 0.6]
        # MoveIt primitive poses are CENTRES; the L0 pose is the foot.
        assert table["pose"]["xyz_m"] == [-0.5, 2.924, 0.3]

    def test_it_tracks_the_model(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            real_model / "assets/instances/fixtures.yaml",
            lambda d: next(a for a in d["assets"] if a["id"] == "infeed_table")["pose"].__setitem__(
                "xyz_m", [-0.6, 2.924, 0.0]
            ),
        )
        scene = yaml.safe_load(artifacts(real_model)["moveit/cell_b_planning_scene.yaml"])
        table = next(
            o for o in scene["planning_scene"]["collision_objects"] if o["id"] == "infeed_table"
        )
        assert table["pose"]["xyz_m"][0] == -0.6


class TestPhysicalConstantsComeFromTheModel:
    """M-12: code encodes how, the model encodes which (P5)."""

    def test_the_acceleration_ceiling_is_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("max_acceleration_rad_s2", 3.5),
        )
        limits = artifacts(real_model)["moveit/cell_b_picker_joint_limits.yaml"]
        assert "max_acceleration: 3.5" in limits
        assert "max_acceleration: 2.0" not in limits

    def test_the_deceleration_ceiling_is_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Pilz brakes on its own ceiling rather than on the acceleration one
        # (ADR-0027), so this is a second physical fact about the arm and not a
        # restatement of the first. MoveIt's sign convention is applied by the
        # template; the model states a magnitude.
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("max_deceleration_rad_s2", 3.5),
        )
        limits = artifacts(real_model)["moveit/cell_b_picker_joint_limits.yaml"]
        assert "has_deceleration_limits: true" in limits
        assert "max_deceleration: -3.5" in limits
        assert "max_deceleration: -2.0" not in limits

    def test_the_cartesian_ceilings_are_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The four values Pilz's LIN and CIRC generators read. They are ceilings
        # for a particular arm, so a constant in generate/moveit.py would apply
        # one arm's task-space limits to every type the generator ever sees (P5).
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].update(
                {
                    "max_cartesian_velocity_m_s": 0.11,
                    "max_cartesian_acceleration_m_s2": 0.22,
                    "max_cartesian_deceleration_m_s2": 0.33,
                    "max_cartesian_rotational_velocity_rad_s": 0.44,
                }
            ),
        )
        limits = yaml.safe_load(
            artifacts(real_model)["moveit/cell_b_picker_cartesian_limits.yaml"]
        )["cartesian_limits"]
        assert limits == {
            "max_trans_vel": 0.11,
            "max_trans_acc": 0.22,
            # Negative, which is MoveIt's convention and not the model's.
            "max_trans_dec": -0.33,
            "max_rot_vel": 0.44,
        }

    def test_the_controller_manager_rate_is_the_types_own(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["control"].__setitem__("update_rate_hz", 250),
        )
        controllers = artifacts(real_model)["control/cell_b_picker_controllers.yaml"]
        assert "update_rate: 250" in controllers

    def test_a_type_with_controllers_and_no_rate_is_an_error_not_a_default(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        from cite_tools.generate.control import MissingControlSpecError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"].pop("control"),
        )
        with pytest.raises(MissingControlSpecError, match="update_rate_hz"):
            artifacts(real_model)


class TestThePlannerChoiceIsData:
    """ADR-0027: which pipeline plans is model data, not a constant in code.

    The split these tests pin down is P5's. The MODEL chooses which pipeline
    plans and which one a refusal falls back to; the GENERATOR knows what a
    pipeline is made of — its plugin class and its adapter chain — because that
    is a fact about MoveIt rather than about this facility.
    """

    def test_both_pipelines_are_declared(self, real_model: Path) -> None:
        pipelines = yaml.safe_load(
            artifacts(real_model)["moveit/cell_b_picker_planning_pipelines.yaml"]
        )
        assert pipelines["planning_pipelines"] == [
            "pilz_industrial_motion_planner",
            "ompl",
        ]
        assert pipelines["pilz_industrial_motion_planner"]["planning_plugins"] == [
            "pilz_industrial_motion_planner/CommandPlanner"
        ]
        assert pipelines["ompl"]["planning_plugins"] == ["ompl_interface/OMPLPlanner"]

    def test_every_pipeline_gets_upstreams_request_adapter_chain(self, real_model: Path) -> None:
        # Both pipelines get all four, which is what MoveIt's own
        # `moveit_configs_utils/default_configs/*_planning.yaml` ships for each
        # of them. An earlier version declared none for Pilz and justified it
        # with "Pilz wants no request adapters", which was wrong about
        # ResolveConstraintFrames — nothing else performs it, and the day a goal
        # names a frame its absence is a plan against the wrong frame rather than
        # an error.
        pipelines = yaml.safe_load(
            artifacts(real_model)["moveit/cell_b_picker_planning_pipelines.yaml"]
        )
        expected = [
            "default_planning_request_adapters/ResolveConstraintFrames",
            "default_planning_request_adapters/ValidateWorkspaceBounds",
            "default_planning_request_adapters/CheckStartStateBounds",
            "default_planning_request_adapters/CheckStartStateCollision",
        ]
        for name in pipelines["planning_pipelines"]:
            assert pipelines[name]["request_adapters"] == expected, name

    def test_the_declared_list_is_every_pipeline_the_generator_can_configure(
        self, real_model: Path
    ) -> None:
        # R-08. The name set used to live in the generator's guard AND in the
        # template's hardcoded list, so a third name passed the guard and
        # generated a file whose list omitted it — the exact failure the guard
        # exists to prevent. Both now come from one mapping, and this is what
        # says so.
        from cite_tools.generate.moveit import PIPELINES

        pipelines = yaml.safe_load(
            artifacts(real_model)["moveit/cell_b_picker_planning_pipelines.yaml"]
        )
        assert pipelines["planning_pipelines"] == list(PIPELINES)
        for name in PIPELINES:
            assert name in pipelines, f"{name} is declared and has no block"

    def test_only_the_searching_pipeline_states_a_segment_resolution(
        self, real_model: Path
    ) -> None:
        # `longest_valid_segment_fraction` is what a pipeline that INTERPOLATES
        # between checked states is allowed to skip. The other one checks the
        # waypoints its own sampling time produced and interpolates nothing, so
        # the key would be an unread number in its block rather than a stricter
        # check — see the note the generator renders above it.
        produced = artifacts(real_model)["moveit/cell_b_picker_planning_pipelines.yaml"]
        pipelines = yaml.safe_load(produced)
        assert pipelines["ompl"]["picker_xarm5"]["longest_valid_segment_fraction"] == 0.005
        assert "longest_valid_segment_fraction" not in str(
            pipelines["pilz_industrial_motion_planner"]
        )

    def test_the_default_pipeline_follows_the_model(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].update(
                {
                    "default_pipeline": "ompl",
                    "default_planner_id": "RRTConnectkConfigDefault",
                    "fallback_pipeline": "pilz_industrial_motion_planner",
                    "fallback_planner_id": "PTP",
                }
            ),
        )
        produced = artifacts(real_model)
        pipelines = yaml.safe_load(produced["moveit/cell_b_picker_planning_pipelines.yaml"])
        assert pipelines["default_planning_pipeline"] == "ompl"
        # And the same choice reaches L3 through the bring-up plan, because a
        # planner named only in the MoveIt configuration is one the skill server
        # cannot ask for.
        plan = yaml.safe_load(produced["bringup/cell_b_plan.yaml"])
        arm = next(m for m in plan["plan"]["controller_managers"] if m["asset"] == "picker")
        assert arm["moveit"]["default_pipeline"] == "ompl"
        assert arm["moveit"]["fallback_pipeline"] == "pilz_industrial_motion_planner"
        assert arm["moveit"]["fallback_planner_id"] == "PTP"

    def test_the_plan_carries_the_planner_the_model_names(self, real_model: Path) -> None:
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])
        planned = 0
        for manager in plan["plan"]["controller_managers"]:
            if manager.get("moveit") is None:
                continue
            planned += 1
            moveit = manager["moveit"]
            assert moveit["default_pipeline"] == "pilz_industrial_motion_planner"
            assert moveit["default_planner_id"] == "PTP"
            assert moveit["fallback_pipeline"] == "ompl"
            # Empty means "the pipeline's own default", which for the generated
            # OMPL block is its single planner configuration.
            assert moveit["fallback_planner_id"] == ""
        assert (
            planned == len(robot_ids(real_model)) and planned
        ), "the plan's planned arms are not the model's arms, or there are none"

    def test_a_pipeline_the_generator_cannot_configure_is_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Not a file that generates cleanly and leaves move_group dying with
        # "Exception while loading planner", which names a plugin and not the
        # model line that asked for it.
        from cite_tools.generate.moveit import UnknownPipelineError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("default_pipeline", "stomp"),
        )
        with pytest.raises(UnknownPipelineError, match="stomp"):
            artifacts(real_model)

    def test_a_fallback_that_is_the_default_is_rejected(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # A refusal retried by the planner that produced it is not a fallback,
        # and it would name one pipeline twice in `planning_pipelines`.
        from cite_tools.model.loader import ModelError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__(
                "fallback_pipeline", "pilz_industrial_motion_planner"
            ),
        )
        with pytest.raises(ModelError, match="fall back"):
            artifacts(real_model)

    def test_an_empty_default_planner_id_is_rejected_by_the_model(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # M-03. It used to be schema-legal, and it failed at LAUNCH — after
        # `validate-model` had already called the model valid, which is the worst
        # possible place for it. Pilz answers "No ContextLoader for planner_id
        # ''" to a request with an empty id.
        from cite_tools.model.loader import ModelError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("default_planner_id", ""),
        )
        with pytest.raises(ModelError):
            artifacts(real_model)

    def test_a_planner_the_pipeline_does_not_register_is_an_error(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Same failure shape as the missing deceleration limit ADR-0027 already
        # met once: the pipeline loads perfectly and then refuses every request.
        from cite_tools.generate.moveit import UnknownPlannerError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("default_planner_id", "PTP2"),
        )
        with pytest.raises(UnknownPlannerError, match="PTP2"):
            artifacts(real_model)

    def test_a_cartesian_planner_may_not_be_an_arms_default(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Not a taste question and not hardcoded to this arm: a Cartesian planner
        # interpolates the tool POSE and solves full six-degree-of-freedom IK at
        # every sample, so on a group with fewer than six joints the reachable
        # poses are a surface and most straight paths have no solution in the
        # middle (ADR-0026). Measured in cite_skills' planning-pipeline launch
        # test, which plans a vertical approach with LIN and is refused a motion
        # that turns the base.
        from cite_tools.generate.moveit import UnknownPlannerError

        edit_yaml(
            real_model / "assets/types/robots/xarm5.yaml",
            lambda d: d["asset_type"]["planning"].__setitem__("default_planner_id", "LIN"),
        )
        with pytest.raises(UnknownPlannerError, match="Cartesian"):
            artifacts(real_model)

    def test_the_plan_names_the_planners_that_define_a_path(self, real_model: Path) -> None:
        # S-04. The L3 server refuses to let the fallback answer a request whose
        # contract is the SHAPE of the path — a sampling planner would return a
        # curve through the same endpoints and the skill would report success.
        # Which ids those are is a fact about MoveIt, stated once in the
        # generator and carried to the server as data rather than compiled into
        # it twice.
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])
        named = 0
        for manager in plan["plan"]["controller_managers"]:
            if manager.get("moveit") is None:
                continue
            named += 1
            assert manager["moveit"]["cartesian_planner_ids"] == ["LIN", "CIRC"]
        assert (
            named == len(robot_ids(real_model)) and named
        ), "the plan's planned arms are not the model's arms, or there are none"


class TestTheDeterminismCheckCanSeeWhatItClaimsTo:
    """R-17: the check has to run somewhere its own failure mode can occur.

    `PYTHONHASHSEED` is fixed for the life of a process, so generating twice in
    one interpreter cannot observe set-iteration order changing — which is the
    single most likely way byte-identical output breaks. The check ran that way
    and its docstring named a property it could not have detected.
    """

    def test_the_second_run_is_a_fresh_interpreter_under_a_different_seed(
        self, real_model: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        from cite_tools import cli

        seen: dict[str, object] = {}
        real_run = subprocess.run

        def capture(command, **kwargs):  # type: ignore[no-untyped-def]
            seen["command"] = command
            seen["seed"] = kwargs["env"]["PYTHONHASHSEED"]
            return real_run(command, **kwargs)

        monkeypatch.setattr(cli.subprocess, "run", capture)
        monkeypatch.setenv("PYTHONHASHSEED", "0")

        produced = gen.generate(load(real_model))
        assert cli._determinism_problems(real_model, produced) == []

        assert seen["command"][0] == sys.executable, "regeneration must be a real interpreter"
        assert seen["seed"] != "0", "the second run must not inherit this process's hash seed"

    def test_a_difference_between_the_two_runs_is_reported(self, real_model: Path) -> None:
        # Proves the comparison is against what the subprocess actually produced
        # rather than against the list handed in.
        from cite_tools import cli

        produced = gen.generate(load(real_model))
        tampered = [
            gen.Artifact(a.path, a.content + "\n# tampered\n") if a.path == "MODEL_HASH" else a
            for a in produced
        ]
        problems = cli._determinism_problems(real_model, tampered)
        assert any("MODEL_HASH" in problem for problem in problems), problems

    def test_a_failing_subprocess_is_reported_rather_than_raised(self, real_model: Path) -> None:
        # A check that crashes on its own machinery tells nobody anything.
        from cite_tools import cli

        produced = gen.generate(load(real_model))
        problems = cli._determinism_problems(real_model / "does_not_exist", produced)
        assert problems and "subprocess" in problems[0]


class TestGraspPolicyReachesTheBringUpPlan:
    """The grasp default is L0 data, and the plan is how L3 receives it.

    Written once in the end-effector type, delivered to every arm that carries
    one. A value the model states but the plan does not carry is a value the
    skill server never sees, and the visible symptom is a gripper closing against
    its effort limit while the model looks correct.
    """

    EFFECTOR = "assets/types/end_effectors/xarm_parallel_gripper.yaml"

    def test_the_default_width_is_delivered_to_every_arm(self, real_model: Path) -> None:
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        managers = [m for m in plan["controller_managers"] if m.get("gripper_action")]
        assert managers, "no arm in the plan has a gripper; this test would prove nothing"
        for manager in managers:
            assert manager["gripper_default_grasp_width_m"] == 0.060915, manager["asset"]

    def test_the_value_comes_from_the_model_and_is_not_a_generator_constant(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        edit_yaml(
            real_model / self.EFFECTOR,
            lambda d: d["asset_type"]["grasp"].__setitem__("default_grasp_width_m", 0.031),
        )
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        widths = {
            m["gripper_default_grasp_width_m"]
            for m in plan["controller_managers"]
            if m.get("gripper_action")
        }
        assert widths == {0.031}

    def test_an_unset_default_emits_no_key_rather_than_a_zero(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Absent, not 0.0. Zero is what `Pick.Goal.grasp_width_m` uses to mean
        "no width supplied", so emitting it as the *default* would turn "nobody
        configured one" into a configured value meaning the same thing — and the
        skill server's warning about the missing datum would never fire."""
        edit_yaml(
            real_model / self.EFFECTOR,
            lambda d: d["asset_type"]["grasp"].pop("default_grasp_width_m", None),
        )
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        for manager in plan["controller_managers"]:
            assert "gripper_default_grasp_width_m" not in manager

    def test_a_stall_is_reported_by_the_controller_rather_than_aborted(
        self, real_model: Path, add_arm: Callable
    ) -> None:
        """ADR-0022: a stall is reported, not interpreted.

        `GripperActionController` defaults `allow_stalling` to false, and false
        makes it call `setAborted` on the one outcome a parallel gripper exists to
        report — pads closed onto a part. The skill would then have to read
        success out of a failed action. This is model data so that simulation and
        hardware are configured identically (P2).
        """
        add_arm(real_model)
        produced = artifacts(real_model)
        arms = robot_ids(real_model)
        assert len(arms) == 2, arms
        for asset in arms:
            controllers = yaml.safe_load(produced[f"control/{ZONE}_{asset}_controllers.yaml"])
            gripper = controllers[f"/cite/{ZONE}/{asset}/{asset}_gripper_controller"]
            assert gripper["ros__parameters"]["allow_stalling"] is True


def test_the_shipped_zone_is_paired(real_model: Path) -> None:
    """The premise `TestTwinSidesAndTheGazeboPartition` inverts, held on its own.

    That class unpairs the zone before every test so that pairing it measures
    something. Without this, a model that stopped pairing the zone would leave
    every one of those tests green and nothing would say the shipped cell had
    changed (ADR-0059).
    """
    plan = yaml.safe_load(artifacts(real_model)[f"bringup/{ZONE}_plan.yaml"])["plan"]
    assert [side["name"] for side in plan["sides"]] == list(ids.SIDES)


def test_no_plan_carries_a_detection_block(real_model: Path) -> None:
    """The detection server left the main tree with the line (ADR-0069).

    A `detection:` block names a server nothing starts, and a reader would take it
    for an interface the cell provides.
    """
    for path in per_zone(real_model, "bringup/{zone}_plan.yaml"):
        assert "detection" not in yaml.safe_load(artifacts(real_model)[path])["plan"], path


class TestTwinSidesAndTheGazeboPartition:
    """What pairing a zone changes, and — more importantly — what it does not.

    ADR-0041 accepts that `twin.sides` is read by generators and therefore that
    pairing produces a committed `cite_generated/` diff and a new `MODEL_HASH`.
    That is only acceptable if the untwinned case is left exactly where it was,
    so the first two tests below are the regression the whole L0 change rests on:
    introducing the field, and writing `counterpart_backend` where it agrees with
    `backend`, must change nothing at all.

    **EVERY TEST HERE STARTS FROM THE ZONE UNPAIRED, and that is an inversion
    rather than a convenience.** The shipped zone is paired (ADR-0059), so a test
    that paired it and compared would compare a model with itself and pass
    whatever pairing did. `_start_unpaired` sets the zone `single` on the copy
    first, which is the model these assertions were written against; that the
    shipped zone really is paired is asserted separately, by
    `test_the_shipped_zone_is_paired`, so the fixture cannot hide a change.

    **AND EVERY ASSET STARTS WITH ONE BACKEND ON BOTH SIDES**, for the same
    reason. Since ADR-0070 the shipped counterpart is physical, and these are the
    2.A properties — what pairing a zone whose two sides load one backend does
    and does not change. The fixture removes each `counterpart_backend`, which is
    the model they were written against; what a DIFFERING counterpart adds is
    asserted by the tests that write one back, at the end of this class.
    """

    @pytest.fixture(autouse=True)
    def _start_unpaired(self, real_model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            real_model / "facility/zones.yaml",
            lambda d: d["zones"][0].__setitem__("twin", {"sides": "single"}),
        )

        def one_backend(document: dict) -> None:
            for asset in document["assets"]:
                asset["hardware"].pop("counterpart_backend", None)

        for instances in sorted((real_model / "assets/instances").glob("*.yaml")):
            edit_yaml(instances, one_backend)

    @staticmethod
    def _make_the_counterpart_physical(model: Path, edit_yaml: Callable) -> None:
        """Write back what the shipped model declares: the arm and its track, `real`."""

        def physical(document: dict) -> None:
            for asset in document["assets"]:
                if asset["id"] in (ARM, "picker_track"):
                    asset["hardware"]["counterpart_backend"] = "real"

        for instances in ("arms.yaml", "tracks.yaml"):
            edit_yaml(model / "assets/instances" / instances, physical)

    @staticmethod
    def _pair(model: Path, edit_yaml: Callable) -> None:
        edit_yaml(
            model / "facility/zones.yaml",
            lambda d: d["zones"][0].__setitem__("twin", {"sides": "pair"}),
        )

    def test_writing_the_counterpart_backend_it_already_has_changes_nothing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # `counterpart_backend` absent means the same value as `backend`, and
        # this is that sentence made mechanical: instances that say so
        # explicitly generate the same bytes as instances that stay silent. The
        # property matters because it is what lets the field be optional without
        # the omission meaning something different from the value.
        before = artifacts(real_model)

        def annotate(document: dict) -> None:
            for asset in document["assets"]:
                asset["hardware"]["counterpart_backend"] = asset["hardware"]["backend"]

        for instances in sorted((real_model / "assets/instances").glob("*.yaml")):
            edit_yaml(instances, annotate)

        assert artifacts(real_model) == before

    def test_an_untwinned_zone_says_nothing_about_a_counterpart(self, real_model: Path) -> None:
        # No artifact mentions a side the zone does not have. This is what makes
        # the `single` output the same output it was before the field existed,
        # apart from the one partition line ADR-0042 deliberately adds.
        #
        # Asked per zone, and derived from the model rather than naming one. It
        # was one `not in` over every artifact joined together, which asserted
        # the property AND that no shipped zone is paired at all -- and ADR-0059
        # removed that second premise by pairing `cell_b` while the property
        # itself held perfectly. That is exactly the breakage `per_zone` above
        # was written for, in a fourth assertion, and the fix is the same one:
        # take the answer from the model.
        #
        # It degenerates to the original assertion on an all-`single` facility,
        # where `paired` is empty and nothing may mention a counterpart at all.
        #
        # Named artifact by artifact rather than by an allowlist over a paired
        # zone's whole tree, and the difference is measured rather than stylistic:
        # an allowlist keyed on the zone in the path admits the word into any of
        # that zone's artifacts -- its world, its description, its controllers --
        # and a review demonstrated exactly that by injecting it into each in
        # turn. What is being protected is ADR-0044 clause 1: pairing emits **no
        # per-side artifact**, so the counterpart is a bring-up fact and may
        # appear in the bring-up plan and NOWHERE else. That is the same shape,
        # and the same spelling, as `test_only_the_bring_up_plan_carries_a_
        # partition` four assertions below.
        paired = {zone.id for zone in load(real_model).zones if zone.twin.sides == "pair"}
        mentions = sorted(
            path for path, text in artifacts(real_model).items() if "counterpart" in text
        )
        assert mentions == sorted(f"bringup/{zone}_plan.yaml" for zone in paired)

    def test_only_the_bring_up_plan_carries_a_partition(self, real_model: Path) -> None:
        # A partition is a bring-up fact, not a description or a world fact. If
        # it ever appears elsewhere it is a second statement of the same name.
        carrying = sorted(
            path for path, text in artifacts(real_model).items() if "gz_partition" in text
        )
        assert carrying == per_zone(real_model, "bringup/{zone}_plan.yaml")

    def test_an_untwinned_zone_still_declares_one_fully_isolated_side(
        self, real_model: Path
    ) -> None:
        # Never defaulted, and never absent. An isolation that appeared only when
        # someone paired a cell would be untested on every run that does not.
        # Both isolations, because they are two halves of one rule: a process
        # belonging to a side carries the partition AND the domain, resolved from
        # the same side identity and read from this one block (ADR-0044,
        # clause 2).
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        assert plan["sides"] == [
            {
                "name": ids.PLANT_SIDE,
                "gz_partition": ids.partition("cell_b", ids.PLANT_SIDE),
                "domain_offset": 0,
            }
        ]

    def test_pairing_a_zone_emits_a_second_side_with_its_own_partition(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        self._pair(real_model, edit_yaml)
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        assert [side["name"] for side in plan["sides"]] == list(ids.SIDES)
        partitions = [side["gz_partition"] for side in plan["sides"]]
        # The entire decision reduces to this inequality: two sides that shared a
        # partition would subscribe to each other's belt commands with nothing
        # logged at either end.
        assert len(set(partitions)) == 2

    def test_pairing_a_zone_changes_the_model_hash(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # Accepted rather than avoided: `twin.sides` DESCRIBES the system, in the
        # same class as adding a fourth arm, so it costs a regeneration. The
        # runtime knob is `TwinMode`, which regenerates nothing. This test is the
        # tripwire on that distinction — if pairing ever stops changing the hash,
        # something has started deriving a second side outside the model.
        before = gen.model_hash(load(real_model))
        self._pair(real_model, edit_yaml)
        assert gen.model_hash(load(real_model)) != before

    def test_a_paired_zone_states_every_asset_backend_on_both_sides(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # With the fallback already applied, so the plan describes the sides that
        # exist rather than repeating a key the model left out. `require_hardware_
        # opt_in` reads these, which is how a physical counterpart is refused
        # without a second gate.
        self._pair(real_model, edit_yaml)
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        for manager in plan["controller_managers"]:
            assert manager["counterpart_backend"] == manager["backend"]

    def test_pairing_a_zone_changes_nothing_but_the_bring_up_plan(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """What actually differs between the two sides, asserted rather than argued.

        In Phase 2.A: **nothing in the generated content.** Both sides load the
        same world, the same descriptions, the same controller configuration, the
        same MoveIt configuration, the same planning scene, the same static
        frames and the same topology, and both present byte-identical names
        (ADR-0044, clause 1). What separates them is not a file, it is the
        environment their processes are started in — `GZ_PARTITION` and
        `ROS_DOMAIN_ID`.

        So this test is a P1 tripwire and not a convenience. The generator call
        sites that branch on a backend — `ros2_control_plugin` into the
        description, the collision scheme in `generate/description.py` and
        `use_sim_time` in `generate/control.py`; ask
        `grep -rn "instance.hardware.backend" tools/cite_tools` rather than
        trusting a count written here, and note that the first of those three
        lives in `model/resolve.py` and so is outside any glob over
        `generate/*.py` — all read the PLANT's backend,
        and under ADR-0041's Decision 3 a paired zone's plant must be `sim` and a
        2.A counterpart writes no `counterpart_backend` at all, so they answer
        identically for both sides. The site this test used to name fourth left
        the generator entirely: ADR-0048 clause 3 removed it, because it was a
        total function of a backend the plan already states per side and nothing
        read it. A generator that emitted a
        second world, a second description or a second controller config for that
        pair would be emitting a byte-identical copy of a file already in the
        tree, which is a value in two places.

        Should this ever fail because a genuinely side-specific artifact was
        added, do not relax it: state which fact made the sides differ and why
        the copy is not a copy.

        **What it protects against is reflex duplication**, and the case it
        does not cover has a test of its own. Every generator site that branches
        on a backend now asks the side it generates for (ADR-0048 clause 2, built
        by ADR-0070), and a side that loads the plant's backend gets no artifact
        of its own — which is what this asserts. A counterpart that loads a
        DIFFERENT backend gets exactly two, and
        `test_a_differing_counterpart_adds_its_two_artifacts_and_moves_no_other`
        below is what says which two and that nothing else moves.
        """
        before = artifacts(real_model)
        self._pair(real_model, edit_yaml)
        after = artifacts(real_model)

        # No file appears and none disappears: pairing generates no second tree.
        assert sorted(after) == sorted(before)
        # And of the files that exist, exactly two have different bytes. The plan
        # is the substance - a second `sides:` entry and each asset's
        # `counterpart_backend`. `MODEL_HASH` is the hash of the model that
        # produced the tree, so it moves whenever the model does; that it moves
        # is asserted deliberately by `test_pairing_a_zone_changes_the_model_hash`
        # below, which is the tripwire on `twin.sides` describing the system
        # rather than running it.
        differing = sorted(path for path in before if before[path] != after[path])
        assert differing == ["MODEL_HASH", "bringup/cell_b_plan.yaml"]

    def test_a_differing_counterpart_adds_its_two_artifacts_and_moves_no_other(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """ADR-0048 clause 2 as a diff: the description and the controller config, nothing else.

        From a paired zone whose sides load one backend, make the counterpart
        physical, as the shipped model does. Exactly two files appear — that
        side's description and controller configuration, under the side's
        directory — and of the files that already existed only the plan (which
        names them) and `MODEL_HASH` change. Every plant artifact is
        byte-identical: making the far side physical moves nothing the plant
        loads.
        """
        self._pair(real_model, edit_yaml)
        before = artifacts(real_model)
        self._make_the_counterpart_physical(real_model, edit_yaml)
        after = artifacts(real_model)

        assert sorted(set(after) - set(before)) == [
            gen.controllers_path("cell_b", ARM, ids.COUNTERPART_SIDE),
            gen.arm_description_path("cell_b", ARM, ids.COUNTERPART_SIDE),
        ]
        assert set(before) - set(after) == set()
        differing = sorted(path for path in before if before[path] != after[path])
        assert differing == ["MODEL_HASH", "bringup/cell_b_plan.yaml"]

    def test_the_side_is_in_the_path_and_in_no_name(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The P2 answer ADR-0048 clause 2 fixes: a file a launch loads is not a name.

        The counterpart's two artifacts sit under `<kind>/counterpart/` with the
        plant's filename, and neither contains the word `counterpart` except in
        the one place a file names another file: the description's pointer to
        its own controller configuration.
        """
        self._pair(real_model, edit_yaml)
        self._make_the_counterpart_physical(real_model, edit_yaml)
        after = artifacts(real_model)
        description = gen.arm_description_path("cell_b", ARM, ids.COUNTERPART_SIDE)
        controllers = gen.controllers_path("cell_b", ARM, ids.COUNTERPART_SIDE)
        assert description == f"description/counterpart/cell_b_{ARM}.urdf.xacro"
        assert controllers == f"control/counterpart/cell_b_{ARM}_controllers.yaml"
        assert "counterpart" not in after[controllers]
        mentions = [line for line in after[description].splitlines() if "counterpart" in line]
        assert mentions == [f"      <parameters>$(find cite_generated)/{controllers}</parameters>"]

    def test_the_plan_names_each_sides_files_only_where_they_differ(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        self._pair(real_model, edit_yaml)
        same = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        for manager in same["controller_managers"]:
            assert "counterpart_description" not in manager
            assert "counterpart_parameters" not in manager
            assert "counterpart_description_args" not in manager
            assert "counterpart_controllers" not in manager

        self._make_the_counterpart_physical(real_model, edit_yaml)
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        (manager,) = (m for m in plan["controller_managers"] if m["asset"] == ARM)
        assert manager["counterpart_description"] == (
            f"package://cite_generated/{gen.arm_description_path('cell_b', ARM, 'counterpart')}"
        )
        assert manager["counterpart_parameters"] == (
            f"package://cite_generated/{gen.controllers_path('cell_b', ARM, 'counterpart')}"
        )
        # The reference, never a value (ADR-0070 item 2).
        assert manager["counterpart_description_args"] == {"robot_ip": {"env": "CITE_XARM_IP"}}
        assert "description_args" not in manager

    def test_a_counterpart_on_an_untwinned_zone_generates_nothing(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Inert where there is no side for it to describe.

        `divergent-counterpart-backend` used to refuse this with its own hint;
        ADR-0070 deleted that rule, so the value is now legal on a `single` zone
        and must reach no artifact at all — not a second description, not a key
        in the plan.
        """
        before = artifacts(real_model)
        self._make_the_counterpart_physical(real_model, edit_yaml)
        after = artifacts(real_model)
        differing = sorted(path for path in after if before.get(path) != after[path])
        assert sorted(after) == sorted(before)
        assert differing == ["MODEL_HASH"]

    def test_a_paired_zone_still_generates_exactly_one_world(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The same claim as the test above, aimed at the artifact most likely to
        # be duplicated by reflex. A second world would be the same bytes under a
        # second name; what makes two `gz sim` servers on one host separate is
        # the partition each is started with, not a second file (ADR-0042).
        #
        # ONE PER ZONE, WHICH IS THE CLAIM — not one in total. A zone genuinely
        # has its own world, so the quantity that must not move when a zone is
        # paired is the count per zone, and this used to state it as a literal
        # one-element list. Pairing a zone must leave BOTH sides of that
        # equality alone.
        before = sorted(
            p for p in artifacts(real_model) if p.startswith("worlds/") and p.endswith(".sdf")
        )
        self._pair(real_model, edit_yaml)
        worlds = sorted(
            p for p in artifacts(real_model) if p.startswith("worlds/") and p.endswith(".sdf")
        )
        assert worlds == per_zone(real_model, "worlds/{zone}.sdf")
        assert worlds == before, "pairing a zone emitted a world it did not have unpaired"

    def test_unpairing_a_zone_returns_the_tree_on_disk_to_exactly_where_it_was(
        self, real_model: Path, edit_yaml: Callable, tmp_path: Path
    ) -> None:
        """Through `gen.write`, because the residue this is about is on a disk.

        **What it proves, exactly.** Generating into a directory that already
        holds the unpaired tree, pairing, and unpairing again returns that
        directory — every file, every byte, and the set of filenames — to what it
        held before. That is a round trip through the writer, not through
        `generate`, so `write`'s overwrite and its stale-file prune are both in
        the path.

        **What it does not prove, stated because the earlier version of this test
        claimed it.** It compared two `generate()` results, and `generate` is
        pure while `model_hash` digests the object graph rather than file bytes,
        so it reduced to `f(m) == f(m)` and stayed green under a mutation that
        injected a second world — both its siblings caught that and it did not.
        Writing through `write` fixes the shape but not the reach: **pairing adds
        no file today**, so the prune has nothing to remove at this commit and
        deleting the prune loop would not fail this test. The prune's own
        regression is `TestHandEditDetection::test_write_removes_stale_files`. This becomes a
        second guard on it the moment a per-side artifact exists — which is
        exactly when a `single` zone could start shipping a `pair`'s residue.

        The paired plan is asserted to differ, so that a generator ignoring
        `twin.sides` cannot satisfy the round trip by doing nothing. It names the
        plan and not the whole tree deliberately: `MODEL_HASH` digests the model,
        so it moves the moment `twin.sides` changes even in a generator that
        ignores the field entirely, and a whole-tree inequality would be answered
        by that alone.
        """
        out = tmp_path / "generated"

        def on_disk() -> dict[str, str]:
            gen.write(gen.generate(load(real_model)), out)
            return {
                path.relative_to(out).as_posix(): path.read_text()
                for path in sorted(out.rglob("*"))
                if path.is_file()
            }

        before = on_disk()
        self._pair(real_model, edit_yaml)
        paired = on_disk()
        edit_yaml(
            real_model / "facility/zones.yaml",
            lambda d: d["zones"][0].__setitem__("twin", {"sides": "single"}),
        )

        plan = "bringup/cell_b_plan.yaml"
        assert paired[plan] != before[plan], "pairing changed no plan; the round trip is vacuous"
        assert on_disk() == before

    def test_the_two_sides_take_the_two_domain_offsets(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The plant at 0 is what makes an untwinned zone resolve to exactly the
        # domain it uses today, so nothing in Phase 1 moves; the counterpart at 1
        # is the only other value a two-wide pair can take. Distinctness is the
        # property that matters — two sides sharing a domain collide on every
        # node name, because both sides carry identical names by rule.
        self._pair(real_model, edit_yaml)
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        by_name = {side["name"]: side["domain_offset"] for side in plan["sides"]}
        assert by_name == {ids.PLANT_SIDE: 0, ids.COUNTERPART_SIDE: 1}

    def test_no_generated_artifact_carries_an_absolute_domain(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """An absolute domain in a committed, hashed tree fails both ways it could be derived.

        From the deployment it differs in every clone, so `./scripts/validate-model`
        — which requires a fresh generator run to be byte-identical to what is on
        disk — would fail in every checkout but the one that wrote it. From the
        model it is identical everywhere, so two checkouts of one commit resolve
        the same domain and discover each other, which is the exact defect the
        per-checkout derivation exists to prevent. Those two are jointly
        exhaustive, which is why the offset is the only shape left (ADR-0044,
        clause 4).
        """
        self._pair(real_model, edit_yaml)
        produced = artifacts(real_model)

        # Read from the parsed document rather than from the text, because the
        # plan's own comments discuss the domain variable at length and a
        # substring search would be answered by the prose instead of by the data.
        plan = yaml.safe_load(produced["bringup/cell_b_plan.yaml"])["plan"]
        for side in plan["sides"]:
            assert set(side) == {"name", "gz_partition", "domain_offset"}
            # An offset is a small index into the sides, not a domain: anything
            # large enough to be usable as one has stopped being an offset.
            assert side["domain_offset"] in range(len(ids.SIDES))

        # And no other artifact says anything about a domain at all. A domain is
        # a fact about a deployment; a description, a world or a controller
        # config that carried one would be a second statement of it.
        carrying = sorted(path for path, text in produced.items() if "domain_offset" in text)
        assert carrying == per_zone(real_model, "bringup/{zone}_plan.yaml")

    def test_a_paired_zone_generates_byte_identically_across_runs(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        # The determinism property the whole committed-artifact scheme rests on,
        # asserted under pairing as well. `TestDeterminism` covers the shipped
        # `single` zone; a second side is exactly the kind of addition that
        # introduces set iteration or dictionary ordering into the output.
        self._pair(real_model, edit_yaml)
        model = load(real_model)
        digests = {
            tuple(sorted((a.path, a.content) for a in gen.generate(model))) for _ in range(10)
        }
        assert len(digests) == 1

    def test_a_physical_counterpart_reaches_the_plan(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The plan states the counterpart's backend, per asset, on the right manager.

        Its comment said "Phase 2.B as a data change" until ADR-0048 clause 1
        landed, then that the model below was refused. ADR-0070 built clause 2
        and deleted the refusal, so the model is valid again; what this asserts
        is still only the emission — that the backend is per asset and reaches
        the manager it belongs to. What the counterpart's own artifacts contain
        is `TestSideParity`'s.
        """
        self._pair(real_model, edit_yaml)
        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0]["hardware"].__setitem__("counterpart_backend", "real"),
        )
        plan = yaml.safe_load(artifacts(real_model)["bringup/cell_b_plan.yaml"])["plan"]
        physical = {
            m["asset"]: m["counterpart_backend"]
            for m in plan["controller_managers"]
            if m["counterpart_backend"] != "sim"
        }
        assert physical == {"picker": "real"}
