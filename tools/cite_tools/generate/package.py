"""Generate the generated package's own build files.

`cite_generated` is generated in its entirety, including `package.xml` and
`CMakeLists.txt`. That is what makes the hand-edit check a single whole-tree
diff: an added file, a missing file, or one changed byte anywhere fails it.

The dependency list is derived from the model, so a component library entry that
starts referencing a new vendor package brings the dependency with it instead of
being discovered as a missing package at build time on someone else's machine.
"""

from __future__ import annotations

from cite_tools.generate import Artifact
from cite_tools.model.loader import FacilityModel
from cite_tools.render import environment

#: Directories the package installs. Listed rather than globbed so that CMake
#: fails loudly if a generator stops emitting one, instead of installing nothing.
DIRECTORIES = (
    "bringup",
    "control",
    "description",
    "frames",
    "moveit",
    "topology",
    "worlds",
)


def generate(model: FacilityModel) -> list[Artifact]:
    # Derived from the model, so a component library entry that starts
    # referencing a new vendor package brings the dependency with it instead of
    # being discovered as a missing package on someone else's machine.
    packages: set[str] = set()
    for asset_type in model.types:
        if asset_type.description.package:
            packages.add(asset_type.description.package)
        if asset_type.planning and asset_type.planning.srdf_package:
            packages.add(asset_type.planning.srdf_package)
    dependencies = sorted(packages)

    env = environment()
    return [
        Artifact(
            "package.xml",
            env.get_template("package/package.xml.j2").render(dependencies=dependencies),
        ),
        Artifact(
            "CMakeLists.txt",
            env.get_template("package/CMakeLists.txt.j2").render(directories=DIRECTORIES),
        ),
    ]
