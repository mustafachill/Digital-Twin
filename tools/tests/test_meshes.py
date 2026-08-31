"""The hull pipeline (ADR-0028 decision 1).

Three properties earn their tests here, and they are the three the decision rests
on rather than three that happen to be easy:

* the hull is a **hull** — it contains every input point and adds no vertex that
  was not one;
* the bytes are **deterministic**, because a committed derived asset is only
  checkable if a fresh derivation reproduces it exactly;
* the ordering Qhull happens to produce **cannot reach the file**, which is what
  makes the previous property survive a permutation of the input.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from cite_tools import meshes

#: The eight corners of a unit cube, as twelve triangles. Deliberately not a
#: random cloud: a cube's hull is the cube, so a wrong answer is visible by
#: inspection rather than only by comparison with another run.
CUBE = np.array(
    [
        [[0, 0, 0], [1, 0, 0], [1, 1, 0]],
        [[0, 0, 0], [1, 1, 0], [0, 1, 0]],
        [[0, 0, 1], [1, 1, 1], [1, 0, 1]],
        [[0, 0, 1], [0, 1, 1], [1, 1, 1]],
        [[0, 0, 0], [0, 1, 1], [0, 0, 1]],
        [[0, 0, 0], [0, 1, 0], [0, 1, 1]],
        [[1, 0, 0], [1, 0, 1], [1, 1, 1]],
        [[1, 0, 0], [1, 1, 1], [1, 1, 0]],
        [[0, 0, 0], [0, 0, 1], [1, 0, 1]],
        [[0, 0, 0], [1, 0, 1], [1, 0, 0]],
        [[0, 1, 0], [1, 1, 1], [0, 1, 1]],
        [[0, 1, 0], [1, 1, 0], [1, 1, 1]],
    ],
    dtype=np.float64,
)


def _write_binary_stl(path: Path, triangles: np.ndarray, header: bytes = b"probe") -> None:
    out = bytearray()
    out += header.ljust(80, b"\0")
    out += struct.pack("<I", len(triangles))
    for face in triangles:
        out += struct.pack("<3f", 0.0, 0.0, 0.0)
        for vertex in face:
            out += struct.pack("<3f", *np.asarray(vertex, dtype=np.float32))
        out += struct.pack("<H", 0)
    path.write_bytes(bytes(out))


class TestReading:
    def test_binary_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "cube.stl"
        _write_binary_stl(path, CUBE)
        assert np.allclose(meshes.read_stl(path), CUBE)

    def test_ascii_is_read_too(self, tmp_path: Path) -> None:
        lines = ["solid probe"]
        for face in CUBE:
            lines.append("facet normal 0 0 0")
            lines.append("  outer loop")
            lines += [f"    vertex {v[0]} {v[1]} {v[2]}" for v in face]
            lines += ["  endloop", "endfacet"]
        lines.append("endsolid probe")
        path = tmp_path / "cube_ascii.stl"
        path.write_text("\n".join(lines))
        assert np.allclose(meshes.read_stl(path), CUBE)

    def test_a_file_that_is_neither_is_an_error(self, tmp_path: Path) -> None:
        path = tmp_path / "not_a_mesh.stl"
        path.write_text("this is not a mesh")
        with pytest.raises(meshes.MeshError):
            meshes.read_stl(path)


class TestTheHullIsAHull:
    def test_a_cube_hulls_to_its_own_corners(self) -> None:
        hull = meshes.convex_hull(CUBE)
        corners = {tuple(v) for v in hull.reshape(-1, 3)}
        assert corners == {tuple(v) for v in CUBE.reshape(-1, 3)}

    def test_an_interior_point_is_dropped(self) -> None:
        """A hull is not a decimation: a point inside the solid contributes nothing."""
        with_interior = np.vstack([CUBE, np.array([[[0.5, 0.5, 0.5]] * 3])])
        assert np.array_equal(meshes.convex_hull(CUBE), meshes.convex_hull(with_interior))

    def test_every_input_point_is_inside_the_result(self) -> None:
        """The property that makes a hull safe to collide against.

        A collision shape that does not contain the geometry it replaces lets the
        arm pass through its own surface. Checked against a shape with a genuine
        concavity, so that "contains" is not trivially true.
        """
        notched = np.vstack([CUBE, np.array([[[0.5, 0.5, 0.4]] * 3])])
        hull = meshes.convex_hull(notched)
        vertices = hull.reshape(-1, 3)
        centre = vertices.mean(axis=0)
        for point in notched.reshape(-1, 3):
            for face in hull:
                normal = np.cross(face[1] - face[0], face[2] - face[0])
                if np.dot(normal, centre - face[0]) > 0:
                    normal = -normal
                assert np.dot(normal, point - face[0]) <= 1e-9

    def test_faces_wind_outward(self) -> None:
        hull = meshes.convex_hull(CUBE)
        centre = hull.reshape(-1, 3).mean(axis=0)
        for face in hull:
            normal = np.cross(face[1] - face[0], face[2] - face[0])
            assert np.dot(normal, face[0] - centre) > 0


class TestDeterminism:
    """The property a committed derived asset is checkable by.

    ADR-0028 decision 1: "a regenerated hull is byte-identical or the change is
    real." Everything about the `--check` mode, and about a stale hull being
    detectable at all, rests on this.
    """

    def test_the_same_mesh_twice(self, tmp_path: Path) -> None:
        path = tmp_path / "cube.stl"
        _write_binary_stl(path, CUBE)
        assert meshes.hull_bytes(path)[0] == meshes.hull_bytes(path)[0]

    def test_a_permuted_input_gives_the_same_bytes(self, tmp_path: Path) -> None:
        """The one that would fail without canonical ordering.

        Qhull's face order follows its input order. Reordering the triangles of a
        mesh describes the same solid, so the hull must be the same file — and
        without the sort in `convex_hull` it would not be.
        """
        first = tmp_path / "a.stl"
        second = tmp_path / "b.stl"
        _write_binary_stl(first, CUBE)
        _write_binary_stl(second, CUBE[::-1])
        assert meshes.hull_bytes(first)[0] == meshes.hull_bytes(second)[0]

    def test_the_header_carries_nothing_machine_specific(self, tmp_path: Path) -> None:
        """A path or a date in the header would break byte-identity across machines."""
        path = tmp_path / "cube.stl"
        _write_binary_stl(path, CUBE, header=b"some other producer")
        payload = meshes.hull_bytes(path)[0]
        assert payload[:80] == meshes.STL_HEADER.ljust(80, b"\0")

    def test_the_source_header_does_not_reach_the_output(self, tmp_path: Path) -> None:
        """Two identical meshes with different headers hull to identical bytes."""
        first = tmp_path / "a.stl"
        second = tmp_path / "b.stl"
        _write_binary_stl(first, CUBE, header=b"vendor one")
        _write_binary_stl(second, CUBE, header=b"vendor two")
        assert meshes.hull_bytes(first)[0] == meshes.hull_bytes(second)[0]

    def test_a_facet_is_fanned_from_its_own_vertices_not_from_their_order(self) -> None:
        """The property that made the hull reproduce on a second platform.

        This is the local half of a failure that only showed up across machines:
        with the same pinned scipy, three of the thirteen vendor meshes hashed
        differently on macOS and in the Linux container, because Qhull split their
        flat faces along different diagonals. The vertex sets and the face counts
        agreed; only the diagonals did not.

        A unit test cannot run on two platforms, so it asserts the property the fix
        rests on instead: the triangulation of a facet is a function of that
        facet's vertex SET. Here the same square is presented with its corners in
        two different orders, and the fan comes out the same.
        """
        normal = np.array([0.0, 0.0, 1.0])
        square = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float64)
        rolled = np.roll(square, 2, axis=0)[::-1]
        assert np.array_equal(
            np.asarray(meshes._fan(square, normal)),
            np.asarray(meshes._fan(rolled, normal)),
        )

    def test_a_fanned_facet_winds_outward(self) -> None:
        """A fan wound the wrong way turns every face's normal into the solid."""
        normal = np.array([0.0, 0.0, 1.0])
        square = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float64)
        for face in meshes._fan(square, normal):
            assert np.dot(np.cross(face[1] - face[0], face[2] - face[0]), normal) > 0


class TestBuild:
    def test_the_relative_layout_is_mirrored(self, tmp_path: Path) -> None:
        """The mirror IS the mechanism, so it is asserted rather than assumed.

        The binding replaces one collision-mesh root with another. That only
        resolves if the relative path under the new root is the path the vendor
        description names.
        """
        source = tmp_path / "vendor"
        (source / "arm" / "visual").mkdir(parents=True)
        _write_binary_stl(source / "arm" / "visual" / "link1.stl", CUBE)
        dest = tmp_path / "hulls"

        records = meshes.build(source, dest, ["arm/visual/link1.stl"])

        assert (dest / "arm" / "visual" / "link1.stl").is_file()
        assert [r.path for r in records] == ["arm/visual/link1.stl"]
        assert records[0].source_triangles == 12
        assert records[0].triangles == 12

    def test_a_missing_source_is_an_error_not_a_skip(self, tmp_path: Path) -> None:
        source = tmp_path / "vendor"
        source.mkdir()
        with pytest.raises(meshes.MeshError):
            meshes.build(source, tmp_path / "hulls", ["arm/visual/gone.stl"])
