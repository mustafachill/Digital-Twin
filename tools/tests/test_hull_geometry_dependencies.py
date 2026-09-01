"""Two facts the derived collision geometry depends on, held by checks not comments.

Both come from the safety audit of 2026-09-01, and both are the same shape: a
property of the **hull** that something in another file could silently break,
where the person breaking it has no reason to read the collision block.

* **S-03.** Enabling Gazebo self-collision jams the gripper in every
  configuration under hulls. The generator refuses to emit the combination.
* **S-02.** The vendor's self-collision matrix was computed against geometry this
  model no longer binds. L0 has to declare that, in the shape ADR-0028 decision 4
  established for the identical hole one layer down.

**Neither check makes the arm safe and neither may be read as saying so.** The
first refuses a combination; the second requires a sentence. What they buy is
that the dependency is stated where the change would be made.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, physical

ARM = "assets/types/robots/xarm5.yaml"
RULE = "vendor-self-collision-matrix-unacknowledged"


def physical_rules(path: Path, severity: Severity = Severity.ERROR) -> set[str]:
    return {f.rule for f in physical.check(load(path)) if f.severity is severity}


def _acknowledgement(document: dict) -> dict:
    return document["asset_type"]["planning"]["vendor_self_collision_matrix"]


class TestSelfCollisionStaysOffWhileHullsAreBound:
    """S-03, and the sharpest hazard either review found.

    On the vendor geometry the gripper linkage keeps a minimum internal gap of
    1.57 mm. On the shipped hulls `left_inner_knuckle` and `left_outer_knuckle`
    interpenetrate at **every one of 200 drive angles across the full stroke**,
    as do `left_outer_knuckle` and `xarm_gripper_base_link`; the hull fills the
    linkage's own concavities, so there is no configuration in which they are
    apart, and the right side mirrors the left by construction.

    It is inert only because SDFormat defaults `<self_collide>` to false on a
    model and nothing in this tree sets it. Adding it is an ordinary fidelity
    improvement nobody here argues against — and under hulls it would stall the
    drive joint at spawn, report every grasp empty, and do none of that on the
    hardware backend, which makes it a **P2 divergence with the simulation as the
    broken half**.

    The interpenetration is measured and exhaustive over the sampled stroke; the
    consequence is reasoned from SDFormat's documented semantics and has not been
    observed on a running cell. Neither this class nor the code it guards claims
    otherwise.
    """

    def test_the_shipped_model_generates(self, real_model: Path) -> None:
        """The premise. A refusal that fires on the shipped tree is a blocker."""
        assert gen.generate(load(real_model))

    def test_nothing_generated_enables_self_collision_today(self, real_model: Path) -> None:
        """Stated as an assertion because the refusal below rests on it.

        If some artifact already enabled self-collision, the generator would be
        refusing to produce the tree that is committed, and every other test here
        would be describing a state that does not exist.
        """
        for artifact in gen.generate(load(real_model)):
            assert "self_collide" not in artifact.content, artifact.path

    @pytest.mark.parametrize(
        "spelling",
        ["<self_collide>true</self_collide>", "<self_collide>1</self_collide>"],
    )
    def test_a_world_that_enables_it_is_refused(
        self, real_model: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
    ) -> None:
        """Injected into the emitted world, which is where a fidelity change lands.

        Mutating the generator's *output* rather than a template: the refusal has
        to hold for whichever emitter a future change puts it in, and a test
        keyed on one template would pass while the next one shipped it.
        """
        real_generate = gen.world.generate

        def with_self_collision(cell):  # type: ignore[no-untyped-def]
            return [
                gen.Artifact(a.path, a.content.replace("<world ", f"{spelling}\n<world ", 1))
                if a.path.endswith(".sdf")
                else a
                for a in real_generate(cell)
            ]

        monkeypatch.setattr(gen.world, "generate", with_self_collision)
        with pytest.raises(gen.GeneratorError, match="self-collision is enabled"):
            gen.generate(load(real_model))

    def test_the_refusal_names_the_artifact_and_the_reason(
        self, real_model: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A refusal nobody can act on gets deleted by whoever hits it."""
        real_generate = gen.world.generate

        def with_self_collision(cell):  # type: ignore[no-untyped-def]
            return [
                gen.Artifact(a.path, "<self_collide>true</self_collide>\n" + a.content)
                if a.path.endswith(".sdf")
                else a
                for a in real_generate(cell)
            ]

        monkeypatch.setattr(gen.world, "generate", with_self_collision)
        with pytest.raises(gen.GeneratorError) as raised:
            gen.generate(load(real_model))
        message = str(raised.value)
        assert "xarm5" in message
        assert ".sdf" in message
        assert "1.57 mm" in message
        assert "P2" in message

    def test_it_does_not_fire_on_the_vendor_geometry(
        self, real_model: Path, edit_yaml: Callable, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The condition is the HULL, not self-collision, and that is the point.

        With the vendor's meshes bound, the linkage clears itself by 1.57 mm and
        enabling self-collision is an ordinary fidelity change. A refusal that
        fired anyway would be a rule about `<self_collide>`, which is not a rule
        this project has any evidence for.
        """
        edit_yaml(
            real_model / ARM,
            lambda d: d["asset_type"]["description"]["collision"].__setitem__(
                "select", "vendor_meshes"
            ),
        )
        real_generate = gen.world.generate

        def with_self_collision(cell):  # type: ignore[no-untyped-def]
            return [
                gen.Artifact(a.path, "<self_collide>true</self_collide>\n" + a.content)
                if a.path.endswith(".sdf")
                else a
                for a in real_generate(cell)
            ]

        monkeypatch.setattr(gen.world, "generate", with_self_collision)
        assert gen.generate(load(real_model))


class TestTheVendorMatrixIsAcknowledgedAgainstTheSetActuallyBound:
    """S-02, built in ADR-0028 decision 4's shape rather than the one it named.

    The record asks for "a check that fails when a derived set is selected while
    the SRDF's matrix names the vendor's". Written that way it fails on the
    shipped configuration the moment it exists — a **blocker** with no passing
    state, which gets reverted rather than answered. Keyed on an L0 declaration
    it becomes a **guard**: the model states what the vendor's matrix was audited
    against, and changing either side reopens it.

    That is not a new idea here. Decision 4 closed the identical structural hole
    for collision meshes by making L0 declare what the vendor does, because a
    vendor description is invoked and never ingested and no rule may open a
    vendor file.
    """

    def test_the_shipped_model_carries_the_acknowledgement(self, real_model: Path) -> None:
        assert RULE not in physical_rules(real_model)
        matrix = load(real_model).asset_type("xarm5").planning.vendor_self_collision_matrix
        assert matrix is not None
        assert matrix.audited_for == "convex_hull"

    def test_dropping_it_is_an_error(self, real_model: Path, edit_yaml: Callable) -> None:
        """The case the rule exists for, and it is an ERROR.

        Nothing else in the validator has an opinion about the SRDF, so before
        2026-09-01 this state was reported by nothing at all.
        """
        edit_yaml(
            real_model / ARM,
            lambda d: d["asset_type"]["planning"].pop("vendor_self_collision_matrix"),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)

    def test_the_vendor_selection_needs_no_acknowledgement(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """Nothing to acknowledge: the matrix and the geometry pair again.

        This is what makes the finding actionable rather than a tax — and it is
        the same escape the range rule leaves open, for the same reason.
        """

        def mutate(document: dict) -> None:
            document["asset_type"]["description"]["collision"]["select"] = "vendor_meshes"
            document["asset_type"]["planning"].pop("vendor_self_collision_matrix")

        edit_yaml(real_model / ARM, mutate)
        assert RULE not in physical_rules(real_model, Severity.ERROR)

    def test_an_acknowledgement_for_another_set_does_not_cover_this_one(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The property that stops it becoming a sentence nobody re-reads.

        An acknowledgement that survived a geometry change would read as coverage
        and would not be: its figures were measured against the set it names.
        """
        edit_yaml(
            real_model / ARM,
            lambda d: _acknowledgement(d).__setitem__("audited_for", "vendor_meshes"),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)

    def test_an_acknowledgement_naming_an_undeclared_set_is_refused(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """A set id nobody declares cannot have been audited against anything."""
        edit_yaml(
            real_model / ARM,
            lambda d: _acknowledgement(d).__setitem__("audited_for", "no_such_set"),
        )
        assert RULE in physical_rules(real_model, Severity.ERROR)

    def test_a_type_that_invokes_no_vendor_srdf_is_not_judged(
        self, real_model: Path, edit_yaml: Callable
    ) -> None:
        """The condition is the vendor's MACRO, not the presence of a hull.

        A type whose SRDF this project generated itself carries a matrix computed
        against whatever geometry the generator used, so there is no mismatch to
        acknowledge and no rule here.
        """

        def mutate(document: dict) -> None:
            document["asset_type"]["planning"].pop("srdf_macro")
            document["asset_type"]["planning"].pop("vendor_self_collision_matrix")

        edit_yaml(real_model / ARM, mutate)
        assert RULE not in physical_rules(real_model, Severity.ERROR)

    def test_the_finding_says_what_to_do(self, real_model: Path, edit_yaml: Callable) -> None:
        """Including the answer that is NOT available.

        Regenerating the matrix against hulls is the obvious next step and it is
        wrong: a hull fills concavities, so it would disable pairs on the strength
        of material that does not exist. On this arm nothing is lost — the
        always-interpenetrating hull pairs are the gripper linkage the vendor
        already disables, whose real gap is 1.57 mm — but that is a measured fact
        about this robot, not a general one.
        """
        edit_yaml(
            real_model / ARM,
            lambda d: d["asset_type"]["planning"].pop("vendor_self_collision_matrix"),
        )
        finding = next(f for f in physical.check(load(real_model)) if f.rule == RULE)
        assert finding.where == "types.xarm5.planning.vendor_self_collision_matrix"
        assert "ADR-0028" in (finding.hint or "")
        assert "regenerating the matrix" in (finding.hint or "")
