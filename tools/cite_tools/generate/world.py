"""Generate the simulation world from L0.

The world holds only what belongs to the *world*: physics settings, lighting, the
ground, and the systems every model relies on. The cell itself is not in here —
it is spawned from the generated description, so that the description is the one
place the cell's contents are stated and the simulator and the planner cannot
disagree about what exists.
"""

from __future__ import annotations

from cite_tools.generate import Artifact
from cite_tools.model.resolve import ResolvedCell
from cite_tools.render import environment

#: 1 ms. Small enough for stable contact with a parallel gripper, and the value a
#: scenario's determinism depends on — changing it changes results, so it is a
#: generated constant rather than a launch argument someone can vary per run.
STEP_SIZE_S = 0.001

#: Unthrottled. Scenarios are graded on outcomes and wall-clock bounds, not on
#: matching real time, and throttling would only make them slower.
REAL_TIME_FACTOR = 0.0

GROUND_SIZE_M = 40.0


def generate(cell: ResolvedCell) -> list[Artifact]:
    text = (
        environment()
        .get_template("world/cell.sdf.j2")
        .render(
            cell=cell,
            step_size=STEP_SIZE_S,
            real_time_factor=REAL_TIME_FACTOR,
            ground_size=GROUND_SIZE_M,
        )
    )
    return [Artifact(f"worlds/{cell.zone}.sdf", text)]
