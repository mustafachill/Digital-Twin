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


def _collision_packages(asset_type) -> set[str]:
    """The package the SELECTED collision set is installed from, if any (ADR-0028).

    The invariant this module's docstring states -- a description that starts
    referencing a package brings the dependency with it -- had exactly one hole,
    and ADR-0028's binding fell straight into it. `description.package` and
    `planning.srdf_package` are not the only packages a generated description can
    name: selecting a derived collision set emits
    `$(find <package>)` into every arm description, and until this function
    existed the generated `package.xml` said nothing about it. A build scoped with
    `--packages-up-to cite_bringup` then succeeds and `robot_state_publisher` dies
    at run time with `PackageNotFoundError`, which is the failure the derivation
    exists to prevent.

    The **selected** set only, never every declared one. A set that is declared and
    not bound reaches no description, so depending on it would be a dependency on
    geometry nothing loads -- and, worse, it would make the shipped default emit
    different bytes from the ones it emitted before the field existed, which is the
    property `_collision_args` and the binding tests are built around.
    """
    spec = asset_type.description.collision
    if spec is None:
        return set()
    selected = spec.selected
    if selected.kind == "vendor_meshes" or not selected.package:
        return set()
    return {selected.package}


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
        packages |= _collision_packages(asset_type)
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
