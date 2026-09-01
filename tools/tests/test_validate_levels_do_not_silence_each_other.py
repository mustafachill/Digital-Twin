"""One validation level's error must not switch another level off.

R-02. `cite_tools.cli.validate` runs five levels — schema, referential, physical,
geometric, and the committed-vs-fresh generated-artifact diff — and two of them
were gated on "no ERROR has been reported yet". That gate is correct for exactly
one reason and it is a narrow one: the geometric level and the generators both
**resolve** poses and types, and resolving against a dangling reference raises a
traceback instead of producing a finding. A *referential* error therefore has to
stop them.

A **physical** error stops nothing. The model still resolves, the generators
still run, and their output is still comparable against what is committed. Gating
on the combined set meant a physical error silenced the fifth level, which is the
hand-edit detector ADR-0021 rests on, and the change that promoted
`collision-reuses-visual-mesh` to an ERROR put a physical error in the path of
every contributor who reverts it: put `select: vendor_meshes` back without
regenerating and `validate-model` reported the collision error and said nothing
at all about three stale descriptions and a stale `MODEL_HASH`.

**A check that switches itself off in the presence of an unrelated finding is
worse than a missing one**, because its silence is indistinguishable from a pass
— which is the same lesson the pre-flight check in the campaign behind ADR-0051
taught, and this file is the second time this project has paid for it.

These tests drive the real `validate` command against a real checkout-shaped
tree, because the gate is in the command and not in any level.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from cite_tools import cli
from cite_tools import generate as gen
from cite_tools.model.loader import load

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A tree shaped like this repository: `model/` beside `workspace/src/`.

    `cli.generated_dir` derives the generated package's location from the model
    directory rather than taking it as an option, so a test that wants the fifth
    level to run has to give it both halves. The generated half is written from
    the model itself, so the tree starts *consistent* and each test breaks
    exactly one thing.
    """
    shutil.copytree(REPO_ROOT / "model", tmp_path / "model")
    model = load(tmp_path / "model")
    gen.write(gen.generate(model), cli.generated_dir(tmp_path / "model"))
    return tmp_path


def _validate(checkout: Path) -> int:
    """Run the command as `./scripts/validate-model` does, returning its exit code."""
    try:
        cli.validate(model=checkout / "model")
    except typer.Exit as exit_:
        return exit_.exit_code
    return 0


def _select_vendor_meshes(checkout: Path, edit_yaml: Callable) -> None:
    """The one-line revert that reaches this defect, and nothing else.

    It is a physical ERROR (`collision-reuses-visual-mesh`, ADR-0028 decision 4)
    and it changes the generated descriptions, the generated `package.xml` and
    `MODEL_HASH` — so a tree edited this way and not regenerated is stale in five
    files while carrying one unrelated-looking finding.
    """
    edit_yaml(
        checkout / "model" / "assets/types/robots/xarm5.yaml",
        lambda d: d["asset_type"]["description"]["collision"].__setitem__(
            "select", "vendor_meshes"
        ),
    )


class TestTheHandEditDetectorSurvivesAPhysicalError:
    def test_the_consistent_checkout_validates(self, checkout: Path) -> None:
        """The premise. Without it, every assertion below could pass vacuously."""
        assert _validate(checkout) == 0

    def test_a_stale_generated_tree_is_reported_beside_the_physical_error(
        self, checkout: Path, edit_yaml: Callable, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The finding: both are reported, not one instead of the other.

        Before the fix this run printed `collision-reuses-visual-mesh` and exited
        1, with no mention of `MODEL_HASH` or of the three descriptions the edit
        had just made stale.
        """
        _select_vendor_meshes(checkout, edit_yaml)
        assert _validate(checkout) != 0

        output = capsys.readouterr()
        printed = output.out + output.err
        assert "collision-reuses-visual-mesh" in printed
        assert "MODEL_HASH" in printed, (
            "the generated-artifact diff did not run: a physical error silenced "
            "the hand-edit detector"
        )
        assert "cell_a_arm_1.urdf.xacro" in printed

    def test_the_error_count_carries_both(
        self, checkout: Path, edit_yaml: Callable, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A count that reports one error for five stale files is a wrong count.

        Asserted on the summary line rather than on the exit code, because the
        exit code was already non-zero when the detector was silent — which is
        precisely why nobody noticed.
        """
        _select_vendor_meshes(checkout, edit_yaml)
        _validate(checkout)
        printed = capsys.readouterr().err
        summary = next(line for line in printed.splitlines() if "error(s)." in line)
        count = int(summary.split()[0])
        assert count > 1, summary


class TestAReferentialErrorStillStopsTheLevelsThatResolve:
    """The other direction, and it is why the gate was not simply deleted.

    A dangling reference makes `resolve` raise rather than report, so the
    geometric level and the generators genuinely cannot run. The fix narrows the
    gate to that cause; it must not remove it, or `validate` answers a broken
    model with a traceback instead of a finding.
    """

    def test_a_dangling_asset_type_is_a_finding_and_not_a_traceback(
        self, checkout: Path, edit_yaml: Callable, capsys: pytest.CaptureFixture[str]
    ) -> None:
        edit_yaml(
            checkout / "model" / "assets/instances/arms.yaml",
            lambda d: d["assets"][0].__setitem__("type", "no_such_type"),
        )
        assert _validate(checkout) != 0
        printed = capsys.readouterr()
        assert "unknown" in (printed.out + printed.err).lower()
