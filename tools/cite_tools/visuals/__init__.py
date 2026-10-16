"""Parametric visual meshes for authored furniture (ADR-0079).

A visual mesh here is *generated*, never modelled by hand: its dimensions are
read from the L0 type that wears it, so the envelope it fills is stated once,
in the model (P1). Each module renders one category of furniture.

**Visual only.** Nothing in this package touches collision geometry, inertia,
frames or plugins. Those stay the primitives the model declares, and every
check that reasons about the body still reasons about them.

The package is named ``visuals`` rather than ``meshes`` because
``cite_tools.meshes`` already exists and derives *collision* hulls (ADR-0028);
the two pipelines must not be mistaken for one another.
"""

from __future__ import annotations

from pathlib import Path

#: The one package that installs ``assets/meshes`` (see
#: ``workspace/src/cite_description/CMakeLists.txt``), and the two spellings by
#: which a model URI reaches a file under it. Nothing else is resolvable to a
#: committed file, so a URI outside these is not something this package writes.
ASSET_PACKAGE = "cite_description"
_URI_PREFIXES = (
    f"file://$(find {ASSET_PACKAGE})/meshes/",
    f"package://{ASSET_PACKAGE}/meshes/",
)


class VisualMeshError(Exception):
    """The model asks for a visual mesh this package cannot place on disk."""


def asset_path(repo_root: Path, uri: str) -> Path:
    """The committed file a model mesh URI resolves to once installed.

    ``cite_description`` installs ``assets/meshes`` as ``share/cite_description/meshes``,
    so the relative part of the URI is the same on both sides of the install.
    """
    for prefix in _URI_PREFIXES:
        if uri.startswith(prefix):
            return repo_root / "assets" / "meshes" / uri[len(prefix) :]
    raise VisualMeshError(
        f"{uri!r} does not name a file under {ASSET_PACKAGE}'s installed meshes; "
        f"expected one of {', '.join(_URI_PREFIXES)}"
    )
