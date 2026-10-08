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

"""The one statement of the model a work-piece is spawned as.

WHY THIS MODULE EXISTS. A work-piece has no instances in L0 by design (ADR-0030):
where a part is at any moment is the process's business, and the layout describes
what is bolted down. So it appears in no generated description and no generated
world, and anything that wants one puts it into a running simulation itself. Two
scenarios did, each from its own hand-written copy of the same SDF string — one
model, two places, free to disagree with nothing to report it, which is the shape
CLAUDE.md section 4 prohibits. A third caller was about to be written.

WHY IT IS HERE AND NOT UNDER `tests/`. The callers are not all tests. `cite_bringup`
is the package that already owns the one door into Gazebo transport (`gz.py`), and
it is importable by a scenario, by `./scripts/program` and by anything else that brings this
cell up. A shared helper under `tests/scenarios/` would have been reachable by the
scenarios alone.

WHAT IS AND IS NOT DERIVED FROM L0, stated plainly because the split is not
obvious and reading it the wrong way would be worse than not knowing.

* The APPEARANCE is derived. It is read from the generated appearance artifact,
  which the generator writes from the facility's material library, so the box is
  the colour L0 declares and that colour is stated exactly once for the whole
  facility.
* The GEOMETRY and the MASS are derived too, since 2026-09-29 (ADR-0067). They
  were literals here — a 50 mm box and 0.2 kg, carried over from the scenarios —
  while L0 stated the same part, which is one fact in two places. The part then
  changed size, to the 66 mm cube the real program's gripper command obliges,
  and the literal would have gone on spawning the old one. They are now read
  from the bring-up plan, which states each declared box part's size and mass.
* The INERTIA is computed from those two, as a solid box, rather than copied from
  L0's rounded tensor; and the FRICTION is still the literal below, because L0
  declares none. Every grasp figure this project published before 2026-09-29
  was measured against the 50 mm box and does not describe the 66 mm one.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

from cite_bringup.gz import run
from cite_bringup.plan import Plan, resolve_uri, WorkpieceModel

import yaml

#: Where the generator puts the facility's appearance. Composed as a package URI
#: rather than taken from the bring-up plan, because the plan lists what bring-up
#: LOADS and bring-up does not load this: a plan entry for it would be a key
#: nothing reads.
APPEARANCE_URI = "package://cite_generated/materials/appearance.yaml"

#: Coulomb friction between the box and everything it touches.
#:
#: It no longer describes the whole of what holds the box in the jaws. Friction
#: alone stops the jaws in the right place — the pads meet the part, the drive
#: joint stalls, and `cite_skills::gripper_is_holding` reads that — but ADR-0029
#: measured it also unable to keep the box STILL once gripped, up to 34.3 degrees
#: of roll between the pads. ADR-0061's `cite_simulation::GraspHold`, a world
#: plugin, now fixes the box rigidly to the arm's own wrist link for exactly as
#: long as the CELL says the jaws are holding it (ADR-0065), and it never touches
#: this collision or its friction. This stays, unchanged, because it still governs
#: everything ADR-0061 does not: the box resting and sliding on the pick table and
#: the belts.
FRICTION_MU = 1.0

#: How far above the pick surface a work-piece is released when it is spawned.
#: Small enough that it settles rather than bounces, and non-zero so it is not
#: spawned interpenetrating the table.
SPAWN_DROP_M = 0.005


class WorkpieceError(Exception):
    """A work-piece model could not be built from what the facility declares."""


def appearance(name: str, path: Path | None = None) -> tuple[tuple[float, ...], ...]:
    """Return the ambient and diffuse colour a body of type ``name`` wears.

    ``path`` is for a caller that has the artifact and not the package — the unit
    test, which must run without a built overlay. A caller inside a built
    workspace passes nothing and the package URI is resolved.

    Raises rather than falling back to a colour of its own. A default here would
    be a second statement of an appearance, in the one layer that exists to stop
    there being one, and it would make a model that says nothing indistinguishable
    from a model that says grey.
    """
    source = path if path is not None else resolve_uri(APPEARANCE_URI)
    document = yaml.safe_load(source.read_text())["appearance"]
    material = (document.get("bodies") or {}).get(name)
    if material is None:
        raise WorkpieceError(
            f"{source}: no body of type {name!r} declares a material. A work-piece is "
            "spawned under the id of its L0 type, which is also the name the belts "
            "carry and the beams watch, so the name asked for here has to be one of "
            f"those. Declared: {', '.join(sorted((document.get('bodies') or {}))) or '(none)'}."
        )
    entry = (document.get("materials") or {}).get(material)
    if entry is None:
        raise WorkpieceError(
            f"{source}: body {name!r} wears material {material!r}, which the library in "
            "the same document does not declare. Regenerate; the validator reports this "
            "as `unknown-material`."
        )
    return tuple(entry["ambient"]), tuple(entry["diffuse"])


def part_of(plan: Plan, name: str) -> WorkpieceModel:
    """Return the box and mass the plan states for the work-piece type ``name``, or refuse."""
    models = plan.workpieces.models if plan.workpieces is not None else {}
    part = models.get(name)
    if part is None:
        raise WorkpieceError(
            f"the {plan.zone} plan states no box work-piece named {name!r}; it states "
            f"{', '.join(sorted(models)) or 'none'}. Regenerate from L0: "
            "./scripts/validate-model --write, then ./scripts/build."
        )
    return part


def workpiece_sdf(part: WorkpieceModel, appearance_path: Path | None = None) -> str:
    """Build the SDF for one work-piece, spawned into a running world under its name.

    ``part.name`` is both the Gazebo model name and the L0 work-piece type id. Those
    are one string by rule, not by coincidence: `Facility.workpiece_models`
    reaches the generated world as each belt's `<carry>` list and each beam's
    `<watch>` list, both of which match on the Gazebo model name, so a part
    spawned under any other name rides through the cell untouched and unseen.

    The inertia is computed, not guessed — a wrong tensor here would make the pick
    behave oddly for reasons that look like a controller fault (L1).

    It used to carry a `<sensor type="contact">`, which existed for exactly one
    reader: `GraspAttachment::FindGraspable` iterated every `ContactSensorData` in
    the world, and no pad link declares a sensor, so without one here the
    attachment plugin could not fire at all. That plugin is removed (ADR-0029), so
    the sensor has no reader and is gone with it.
    """
    ambient, diffuse = appearance(part.name, appearance_path)
    x, y, z = part.size_m
    mass = part.mass_kg
    size = f"{x:g} {y:g} {z:g}"
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{part.name}">
    <link name="link">
      <inertial>
        <mass>{mass:g}</mass>
        <inertia>
          <ixx>{mass * (y * y + z * z) / 12.0}</ixx>
          <iyy>{mass * (x * x + z * z) / 12.0}</iyy>
          <izz>{mass * (x * x + y * y) / 12.0}</izz>
          <ixy>0</ixy><ixz>0</ixz><iyz>0</iyz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry><box><size>{size}</size></box></geometry>
        <surface><friction><ode>{_friction()}</ode></friction></surface>
      </collision>
      <visual name="visual">
        <geometry><box><size>{size}</size></box></geometry>
        <material><ambient>{_rgba(ambient)}</ambient><diffuse>{_rgba(diffuse)}</diffuse></material>
      </visual>
    </link>
  </model>
</sdf>
"""


def world_name(world: Path) -> str:
    """Return the Gazebo world's NAME, read from the world the plan names.

    Read rather than assumed to equal the zone. They agree today, and that is a
    property of the generator rather than a rule: a zone whose world were named
    anything else would leave a caller addressing `/world/<wrong>/...`, where
    nothing answers, and an unpartitioned or misaddressed Gazebo query does not
    fail — it waits. Reading it from the generated world is what keeps this from
    being a second statement of a generated name (P1).
    """
    element = ElementTree.parse(world).getroot().find("world")
    if element is None or not element.get("name"):
        raise ValueError(f"{world} declares no named <world>")
    return str(element.get("name"))


def frame(plan: Plan, name: str) -> tuple[float, float, float]:
    """Where one generated static frame stands, read from the plan's own file.

    The generated frames document is what the static transform publisher itself
    is given, so reading it is not a second statement of the geometry — it is the
    same statement, read in the same place (P1).
    """
    document = yaml.safe_load(plan.static_frames.read_text())
    for transform in document["static_transforms"]:
        if transform["child"] == name:
            x, y, z = transform["xyz_m"]
            return (float(x), float(y), float(z))
    raise KeyError(f"{plan.zone} declares no frame named {name!r}")


def spawn(zone: str, side: str, name: str, at: tuple[float, float, float],
          sdf: Path, timeout_s: float,
          interrupted: Callable[[], bool] | None = None) -> str | None:
    """Put one work-piece into one side's world. Returns None on success, else why not.

    Returns rather than raises: a caller that cannot spawn should say so and go on
    to tear the cell down, not traceback over a running pair. Through
    `cite_bringup.gz.run`, the one door into Gazebo transport (ADR-0042), which
    raises `gz.CommandInterrupted` once ``interrupted`` says to stop.
    """
    result = run(
        ["ros2", "run", "ros_gz_sim", "create", "-file", str(sdf), "-name", name,
         "-x", f"{at[0]}", "-y", f"{at[1]}", "-z", f"{at[2]}"],
        zone=zone, side=side, timeout=timeout_s, interrupted=interrupted,
    )
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or "no output").strip().splitlines()[-1]


def _friction() -> str:
    """Render the isotropic Coulomb pair, as SDF spells it.

    A function only so that the line it produces fits: `mu` and `mu2` carry one
    value and must keep carrying one, which is what stating it once here says.
    """
    return f"<mu>{FRICTION_MU}</mu><mu2>{FRICTION_MU}</mu2>"


def _rgba(colour: tuple[float, ...]) -> str:
    """Four numbers, space separated, as SDF spells a colour."""
    if len(colour) != 4:
        raise WorkpieceError(f"a colour is red, green, blue and alpha; got {colour!r}")
    return " ".join(f"{component:g}" for component in colour)
