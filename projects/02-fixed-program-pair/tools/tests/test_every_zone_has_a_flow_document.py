"""A zone with no flow document generates nothing, and says nothing.

ADR-0056's promotion clause 7. This is the likeliest way `cell_b` could validate
clean while being non-functional, and the reason it is a test rather than a
sentence in the model is that **every instrument in the repository stays quiet
for it**:

* `cite_tools.generate.topology.generate` returns `[]` when no flow names the
  zone, so the zone's `topology/<zone>_flow.yaml` is simply absent. It is not an
  error, because a zone legitimately generates nothing when it has no process —
  the generator has no way to tell "no line here" from "somebody deleted the flow
  document".
* `referential._flow_is_consistent` walks `model.flows` and reports orphan
  stations *per flow*. With no flow for the zone there is no flow to walk, so the
  `unreachable-station` check never runs for that zone's stations at all.
* `./scripts/validate-model` therefore exits 0.

What the cell then does is come up with every arm, every controller and every
skill server active, and no line: `line_orchestrator` has no topology to derive a
station tree from. Bring-up looks perfect.

The check itself is trivial. Its value is entirely in the second test below,
which demonstrates that removing the document is silent — because a guard whose
subject nothing else would notice is worth exactly as much as the demonstration
that nothing else would notice.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cite_tools import generate as gen
from cite_tools.model.loader import load
from cite_tools.validate import Severity, referential


def _topologies(model_path: Path) -> set[str]:
    return {
        artifact.path
        for artifact in gen.generate(load(model_path))
        if artifact.path.startswith("topology/")
    }


def test_every_declared_zone_has_a_flow(real_model: Path) -> None:
    model = load(real_model)
    with_flow = {flow.zone for flow in model.flows}
    missing = sorted(zone.id for zone in model.zones if zone.id not in with_flow)
    assert missing == [], (
        f"{missing} declare no flow document. A zone with no flow generates no topology, "
        "silently, and its stations are never checked for reachability."
    )


def test_every_declared_zone_generates_a_topology(real_model: Path) -> None:
    """The same claim at the other end, against what the generator actually emits.

    Separate from the test above rather than folded into it: that one reads the
    model and this one reads the output, and the gap between them is the whole
    subject of this file. A flow whose `zone` names a zone that does not exist
    would satisfy neither, but a flow the generator ignored for some other reason
    would satisfy only the first.
    """
    expected = {f"topology/{zone.id}_flow.yaml" for zone in load(real_model).zones}
    assert _topologies(real_model) == expected


def test_removing_a_zones_flow_document_is_caught_here_and_nowhere_else(
    real_model: Path, remove_flow: Callable
) -> None:
    """Delete `cell_b`'s flow document and watch four instruments stay quiet.

    This is the test. The two above would pass just as happily against a model
    that could not lose a flow document at all; this one establishes that it can,
    that the loss is invisible, and that the guard above is what makes it visible.

    Asserting the silence, and not only the catch, is deliberate. If a later
    change makes the generator or a validator refuse a flow-less zone, this test
    fails on the silence assertions rather than passing quietly — and that is the
    right outcome, because at that point the guard above has been superseded by
    something better and the next reader should be told so rather than left
    maintaining both.
    """
    zone = remove_flow(real_model, "cell_b")

    # 1. The model still loads. No schema error: a zone is not required to name
    #    a flow, and no document is missing as far as the loader is concerned.
    model = load(real_model)
    assert zone in {z.id for z in model.zones}
    assert zone not in {flow.zone for flow in model.flows}

    # 2. The referential level reports nothing. In particular `unreachable-station`
    #    does not fire for this zone's three stations, which are now reachable
    #    from nothing at all — the rule iterates flows, and there is no flow.
    findings = referential.check(model)
    assert [f for f in findings if f.severity is Severity.ERROR] == []
    assert not [f for f in findings if zone in f.where]

    # 3. The generator emits no topology for it, and no error either.
    assert f"topology/{zone}_flow.yaml" not in _topologies(real_model)

    # 4. And it still emits everything else the zone owns, which is what makes
    #    the loss so hard to see: the world, the description, the controllers,
    #    the MoveIt configuration and the bring-up plan are all still there.
    remaining = {a.path for a in gen.generate(model)}
    assert f"worlds/{zone}.sdf" in remaining
    assert f"bringup/{zone}_plan.yaml" in remaining

    # 5. The guard is the only thing that says so.
    with_flow = {flow.zone for flow in model.flows}
    assert [z.id for z in model.zones if z.id not in with_flow] == [zone]
