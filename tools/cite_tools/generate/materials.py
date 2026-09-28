"""Generate the facility's appearance: the material library, and who wears what.

WHY AN ARTIFACT AT ALL, when every body that stands in a cell already carries its
colour in the generated scene. One visible object in this cell is not in any
description: the work-piece. It has no instances by design (ADR-0030) — where a
part is at any moment is the process's business — so it is spawned into a running
world from a model built in code, and there is nothing for it to read a colour
out of. Before this artifact existed, the two scenarios that spawn one each
carried their own hand-written `<material>` block: one value, two places, and
neither of them L0.

WHY IT IS EMITTED ONCE AND NOT PER ZONE. A material is facility-scoped in L0, and
so is `Facility.workpiece_models`. A per-zone copy would state one colour once per
cell, which is the duplication the library removes.
"""

from __future__ import annotations

from cite_tools.generate import Artifact
from cite_tools.model.loader import FacilityModel
from cite_tools.render import environment

#: Where the artifact lands inside the generated package. Named here because
#: `generate.package` installs the directory and `cite_bringup.workpiece`
#: composes the same path as a `package://` URI.
PATH = "materials/appearance.yaml"


def _bodies(model: FacilityModel) -> tuple[tuple[str, str], ...]:
    """Which material each authored body wears, by asset type id, sorted.

    Types only, never instances: `Body` belongs to the type, so two pedestals
    cannot be two colours and there is nothing per-instance to say.

    A type whose body declares no material is absent rather than present with a
    null. The absence is the model saying nobody has decided yet, and a consumer
    that finds no entry has to decide what to do about it — which is better than
    being handed a null it may read as a colour.
    """
    return tuple(
        (asset_type.id, asset_type.description.body.material)
        for asset_type in sorted(model.types, key=lambda t: t.id)
        if asset_type.description.body is not None
        and asset_type.description.body.material is not None
    )


def generate(model: FacilityModel) -> list[Artifact]:
    env = environment()
    return [
        Artifact(
            PATH,
            env.get_template("materials/appearance.yaml.j2").render(
                materials=model.materials,
                bodies=_bodies(model),
            ),
        )
    ]
