"""Generation. The properties tested here are what the architecture rests on.

ADR-0004 requires byte-identical output because the hand-edit check compares a
committed artifact against a fresh run; ADR-0021 commits the artifacts so that
check can exist at all. Neither is worth anything unless determinism actually
holds, so it is asserted rather than assumed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools import generate as gen
from cite_tools.model.loader import load


def artifacts(path: Path) -> dict[str, str]:
    return {a.path: a.content for a in gen.generate(load(path))}


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

        instances = real_model / "assets/instances/conveyors.yaml"
        import yaml

        document = yaml.safe_load(instances.read_text())
        first, rest = document["assets"][:1], document["assets"][1:]
        instances.write_text(yaml.safe_dump({**document, "assets": first}, sort_keys=False))
        (real_model / "assets/instances/conveyors_more.yaml").write_text(
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
        target = out / "worlds/cell_a.sdf"
        target.write_text(target.read_text().replace("0.001", "0.002", 1))
        assert any(
            "differs from a fresh generator run" in p for p in gen.differences(produced, out)
        )

    def test_a_missing_file_is_caught(self, real_model: Path, tmp_path: Path) -> None:
        out = tmp_path / "cite_generated"
        produced = gen.generate(load(real_model))
        gen.write(produced, out)
        (out / "worlds/cell_a.sdf").unlink()
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


class TestGrowingTheLineIsDataOnly:
    """The Phase 1 exit criterion, in miniature.

    "The entire cell layout is changeable by editing the facility model alone."
    Adding an arm must change generated artifacts and nothing else — if it ever
    requires editing a launch file or a controller config by hand, P1 has been
    broken somewhere upstream.
    """

    def test_a_fourth_arm_needs_no_code_change(self, real_model: Path, edit_yaml: Callable) -> None:
        import yaml

        fixtures = real_model / "assets/instances/fixtures.yaml"
        document = yaml.safe_load(fixtures.read_text())
        pedestal = dict(document["assets"][0])
        pedestal["id"] = "pedestal_4"
        pedestal["pose"] = {"frame": "cite_world", "xyz_m": [6.3, -0.35, 0.0]}
        document["assets"].append(pedestal)
        fixtures.write_text(yaml.safe_dump(document, sort_keys=False))

        arms = real_model / "assets/instances/arms.yaml"
        document = yaml.safe_load(arms.read_text())
        arm = dict(document["assets"][0])
        arm["id"] = "arm_4"
        arm["pose"] = dict(arm["pose"], frame="pedestal_4/top")
        document["assets"].append(arm)
        arms.write_text(yaml.safe_dump(document, sort_keys=False))

        produced = artifacts(real_model)
        assert "control/cell_a_arm_4_controllers.yaml" in produced
        assert (
            "arm_4_joint_trajectory_controller" in produced["control/cell_a_arm_4_controllers.yaml"]
        )
        assert "/cite/cell_a/arm_4" in produced["description/cell_a.urdf.xacro"]
        assert "arm_4" in produced["bringup/cell_a_plan.yaml"]


class TestSimRealParity:
    """P2, asserted on the generator rather than hoped for at run time."""

    def test_only_the_plugin_differs_between_backends(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        sim = artifacts(real_model)

        edit_yaml(
            real_model / "assets/instances/arms.yaml",
            lambda d: d["assets"][0].__setitem__(
                "hardware", {"backend": "real", "params": {"robot_ip": "192.168.1.100"}}
            ),
        )
        real = artifacts(real_model)

        # Controller and joint names are identical. If this ever fails, P2 is
        # broken and everything above L2 becomes unfounded.
        assert (
            sim["control/cell_a_arm_1_controllers.yaml"].replace(
                "use_sim_time: true", "use_sim_time: false"
            )
            == real["control/cell_a_arm_1_controllers.yaml"]
        )

        # The description differs in exactly one respect: the plugin class.
        differing = [
            line
            for a, b in zip(
                sim["description/cell_a.urdf.xacro"].splitlines(),
                real["description/cell_a.urdf.xacro"].splitlines(),
                strict=True,
            )
            if a != b
            for line in (a,)
        ]
        assert all("ros2_control_plugin" in line for line in differing), differing


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
