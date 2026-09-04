#!/usr/bin/env python3
"""The compute stage: forward kinematics, distances under BOTH mesh sets, steps, tunnelling.

`criteria.md` section 4. The campaign has two stages and separating them is deliberate: the
capture stage runs a cell and is not reproducible; **this stage runs no cell and is** (REPRO1).
It is a pure function of what was captured and of two committed mesh sets, so a reviewer can
re-run it without a cell, on a different interpreter, and get the same numbers.

WRITTEN FOR THIS CAMPAIGN. Nothing is copied from another campaign directory -- section 2.5
records that ADR-0028's audit script was never committed, so there is no instrument to
inherit. The record shape and the provenance discipline come from `common.py`, whose own
header names its frozen source.

**NOTHING HERE FLIPS A GEOMETRY.** Section 5.2: measuring both sets by setting
`description.collision.select` to `vendor_meshes` would edit `model/` and
`workspace/src/cite_generated/`, both watched by V1, and would move `MODEL_HASH`. The
substitution happens **here**, by reading a different file at the same relative path below the
collision root -- section 2.3's property, which this module CHECKS rather than assumes. The
cell ran on hulls and `v1_clean` holds throughout.

WHAT THIS STAGE READS, AND WHAT IT REFUSES TO READ.
  * The description is the one **read back off the running node** (I3), saved beside the
    record by `capture.py`. Not a fresh `xacro` expansion: that would be a different tree's
    description wearing this block's name.
  * The object poses are I4's **read-back**, in the frame `move_group` reported -- not the
    generated file's (section 2.2). The file is V5's cross-check and a disagreement is
    reported, never reconciled.
  * The two mesh roots are read straight off disk. They are committed files and V1 watches
    both of the paths they live under.

THE PRINT IS PROGRESS, NOT THE PRODUCT. `analyse.py` is the product. This stage writes
`<label>_computed.json` and `<label>_fk_sample.json` and prints what it is doing.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import geometry as geo  # noqa: E402

#: `moveit_msgs`' `SolidPrimitive.BOX`. Named rather than imported, because this stage runs on
#: a host with no ROS (REPRO1's second interpreter). Section 2.2 records that **every one of
#: the twelve scene objects is a box**, and a non-box read back is a loud failure here.
SOLID_PRIMITIVE_BOX = 1


# ---------------------------------------------------------------------------
# The two mesh sets
# ---------------------------------------------------------------------------
def mesh_sets(model: geo.RobotModel, root: Path) -> dict:
    """Load each collision link's mesh under BOTH roots, and CHECK section 2.3's property.

    Section 2.3: the collision root is the only thing that differs between the two sets and
    the relative path beneath it is identical either way -- which is what makes an offline
    substitution exact. That is a claim about the tree, so it is verified here: a relative
    path that does not resolve under the vendor root is a hard failure, not a fallback.

    The origin radius and the AABB are compared between the two sets and the residual is
    REPORTED. Section 2.3 verifies both agree to 0.000e+00 m on the committed files; that is
    the property the broad phase's symmetry rests on, and a campaign that assumed it without
    looking would have no way to notice a re-derivation that broke it.
    """
    hull_root = root / common.HULL_ROOT
    vendor_root = root / common.VENDOR_ROOT
    loaded: dict[str, dict] = {}
    residuals = []
    for link, entry in sorted(model.collision.items()):
        relative = geo.mesh_relative_path(entry["uri"], common.HULL_COLLISION_REFERENCE)
        if relative is None:
            raise AssertionError(
                f"{link}'s collision mesh {entry['uri']!r} is not under "
                f"{common.HULL_COLLISION_REFERENCE}; the substitution of section 2.3 is not "
                f"available for it and this stage refuses to guess a root"
            )
        hull_path = hull_root / relative
        vendor_path = vendor_root / relative
        for path, which in ((hull_path, "hull"), (vendor_path, "vendor")):
            if not path.exists():
                raise AssertionError(
                    f"{link}: the {which} set has no file at the relative path {relative!r}. "
                    f"Section 2.3's identical-relative-path property does not hold for this "
                    f"tree and the comparison this campaign makes is not defined."
                )
        meshes = {"hull": geo.Mesh(hull_path), "vendor": geo.Mesh(vendor_path)}
        aabb_residual = max(
            float(np.abs(meshes["hull"].aabb[index] - meshes["vendor"].aabb[index]).max())
            for index in (0, 1)
        )
        radius_residual = abs(meshes["hull"].radius - meshes["vendor"].radius)
        residuals.append(
            {
                "link": link,
                "relative": relative,
                "hull_triangles": meshes["hull"].triangles,
                "vendor_triangles": meshes["vendor"].triangles,
                "aabb_corner_residual_m": aabb_residual,
                "origin_radius_residual_m": radius_residual,
                "radius_m": meshes["hull"].radius,
            }
        )
        loaded[link] = {
            "meshes": meshes,
            "relative": relative,
            "origin": entry,
            # Section 2.3 verifies the radius is identical under both sets; the broad phase
            # uses ONE number so that censoring is provably symmetric rather than merely
            # expected to be.
            "radius": max(meshes["hull"].radius, meshes["vendor"].radius),
        }
    return {
        "links": loaded,
        "provenance": {
            "hull_root": str(hull_root),
            "vendor_root": str(vendor_root),
            "per_link": residuals,
            "worst_aabb_corner_residual_m": max(row["aabb_corner_residual_m"] for row in residuals),
            "worst_origin_radius_residual_m": max(
                row["origin_radius_residual_m"] for row in residuals
            ),
            "hull_triangles_total": sum(row["hull_triangles"] for row in residuals),
            "vendor_triangles_total": sum(row["vendor_triangles"] for row in residuals),
            "collision_links": len(residuals),
        },
    }


# ---------------------------------------------------------------------------
# The scene, as `move_group` held it
# ---------------------------------------------------------------------------
class SceneObject:
    __slots__ = ("name", "centre", "rotation", "half", "frame")

    def __init__(self, name: str, centre, rotation, half, frame: str) -> None:
        self.name = name
        self.centre = np.asarray(centre, dtype=float)
        self.rotation = np.asarray(rotation, dtype=float)
        self.half = np.asarray(half, dtype=float)
        self.frame = frame


def scene_from_readback(reading: dict) -> tuple[list[SceneObject], dict]:
    """I4's read-back as boxes in the frame `move_group` reported.

    Section 2.2: every one of the twelve objects is a `box`. A primitive that is not a box, or
    an object carrying more than one primitive, is refused rather than approximated -- this
    campaign's distance is exact and there is no box-shaped answer for a shape it did not
    expect.
    """
    objects: list[SceneObject] = []
    notes = {"frames": {}, "refused": []}
    for name, entry in sorted(reading.get("objects", {}).items()):
        primitives = entry.get("primitives") or []
        poses = entry.get("primitive_poses") or []
        if len(primitives) != 1 or len(poses) != 1:
            notes["refused"].append(
                {"object": name, "why": f"{len(primitives)} primitive(s), {len(poses)} pose(s)"}
            )
            continue
        primitive, pose = primitives[0], poses[0]
        if int(primitive["type"]) != SOLID_PRIMITIVE_BOX:
            notes["refused"].append(
                {"object": name, "why": f"primitive type {primitive['type']} is not a box"}
            )
            continue
        dimensions = [float(value) for value in primitive["dimensions"]]
        # The object's own pose composes with the primitive's, exactly as MoveIt composes
        # them; both are recorded and both are applied.
        object_pose = entry.get("pose") or {"xyz": [0.0, 0.0, 0.0],
                                            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]}
        outer_rotation = geo.quaternion_to_rotation(*object_pose["quaternion_xyzw"])
        outer_translation = np.array(object_pose["xyz"], dtype=float)
        inner_rotation = geo.quaternion_to_rotation(*pose["quaternion_xyzw"])
        inner_translation = np.array(pose["xyz"], dtype=float)
        rotation = outer_rotation @ inner_rotation
        centre = outer_rotation @ inner_translation + outer_translation
        objects.append(
            SceneObject(name, centre, rotation, np.array(dimensions) / 2.0,
                        entry.get("frame_id", ""))
        )
        notes["frames"][name] = entry.get("frame_id", "")
    return objects, notes


def v5_scene_agreement(objects: list[SceneObject], generated: dict, transforms: dict,
                       root_link: str) -> dict:
    """V5 -- the scene that actually planned, against the file the generator wrote.

    **The accounting choice registered in V5 is implemented here and nowhere else.** The frame
    is accounted for with **the generated static transform's own value** -- yaw `1.570796327`,
    read from `cell_a_static_tf.yaml` -- which is the value `move_group` itself was given, so
    the round trip cancels to double precision. V5's own arithmetic records that writing this
    against `pi/2` instead would fire on exactly three of the 36 (arm, object) pairs, the
    largest by 1.273e-9 m, and that such a firing would be arithmetic rather than a scene
    defect. Nothing here rounds and nothing substitutes `pi/2`.

    **V5 only reports.** A disagreement is stated with the pair, the residual and which value
    was used; no tolerance is widened (V9) and the block's distances stand against the
    read-back.
    """
    scene_frame = generated["frame_id"]
    observed = {obj.name: obj for obj in objects}
    planning_frames = {obj.frame for obj in objects}
    key = f"{scene_frame}|{root_link}"
    transform = transforms.get(key)

    if not objects:
        return {"evaluated": False, "why": "the read-back held no object", "v5_ok": None,
                "empty_readback": True}
    if len(planning_frames) != 1:
        return {"evaluated": False, "v5_ok": None,
                "why": f"the read-back mixes frames {sorted(planning_frames)}"}
    frame = next(iter(planning_frames))

    if frame == scene_frame:
        rotation, translation = np.eye(3), np.zeros(3)
        accounting = f"identity: the read-back is already in {scene_frame}"
    elif transform is not None and frame == root_link:
        # inv(cite_world -> root) applied to each generated pose.
        forward = geo.rotation_from_rpy(*transform["rpy_rad"])
        offset = np.array(transform["xyz_m"], dtype=float)
        rotation, translation = forward.T, -forward.T @ offset
        accounting = (
            f"the generated static transform {scene_frame} -> {root_link}, inverted, using "
            f"its own yaw value {transform['rpy_rad'][2]!r} and not pi/2 (criteria.md V5)"
        )
    else:
        return {"evaluated": False, "v5_ok": None,
                "why": f"no generated transform from {scene_frame} to the read-back frame "
                       f"{frame!r}"}

    rows = []
    worst = 0.0
    for name, body in sorted(generated["objects"].items()):
        if name not in observed:
            rows.append({"object": name, "present": False})
            continue
        seen = observed[name]
        expected_centre = rotation @ np.array(body["xyz_m"], dtype=float) + translation
        expected_half = np.array(body["dimensions_m"], dtype=float) / 2.0
        pose_residual = float(np.abs(expected_centre - seen.centre).max())
        size_residual = float(np.abs(expected_half - seen.half).max())
        worst = max(worst, pose_residual, size_residual)
        rows.append(
            {
                "object": name,
                "present": True,
                "pose_residual_m": pose_residual,
                "dimension_residual_m": size_residual,
                "above_tolerance": max(pose_residual, size_residual) > common.V5_TOLERANCE_M,
            }
        )
    missing = sorted(set(generated["objects"]) - set(observed))
    extra = sorted(set(observed) - set(generated["objects"]))
    return {
        "evaluated": True,
        "accounting": accounting,
        "read_back_frame": frame,
        "tolerance_m": common.V5_TOLERANCE_M,
        "worst_residual_m": worst,
        "objects_missing_from_readback": missing,
        "objects_only_in_readback": extra,
        "rows": rows,
        "pairs_above_tolerance": sum(1 for row in rows if row.get("above_tolerance")),
        "v5_ok": (not missing) and (not extra) and worst <= common.V5_TOLERANCE_M,
    }


# ---------------------------------------------------------------------------
# Rule C -- is this trajectory usable at all
# ---------------------------------------------------------------------------
def rule_c_clauses(row: dict, model: geo.RobotModel) -> dict:
    """Rule C's clauses iii and iv, per trajectory, as POSITIVE findings.

    A trajectory failing any clause is an INSTRUMENT LOSS: excluded from every distribution,
    counted and reported separately from every other exclusion, and **never counted as a
    trajectory that stayed clear**.
    """
    points = row.get("points") or []
    names = row.get("joint_names") or []
    start = row.get("trajectory_start") or {"name": [], "position": []}
    known = {joint.name for joint in model.joints}

    enough = len(points) >= common.MIN_WAYPOINTS
    times = [point["time_from_start"] for point in points]
    increasing = all(b > a for a, b in zip(times, times[1:])) if len(times) > 1 else False
    widths = all(len(point["positions"]) == len(names) for point in points)
    named_known = all(name in known for name in names)

    supplied = set(names) | set(start.get("name") or [])
    # C-iv is stated over the joints the MODEL has, and a model joint in neither the
    # trajectory nor the start state makes the trajectory inadmissible rather than silently
    # defaulted to zero. `<mimic>` followers are excluded from the requirement because
    # section 5.4's coupling supplies them from the leader by construction -- but they are
    # counted, so a reader can see that the completion was a coupling and not a default.
    required = {
        joint.name
        for joint in model.joints
        if joint.type in ("revolute", "continuous", "prismatic") and joint.mimic_joint is None
    }
    missing = sorted(required - supplied)
    mimics_supplied_by_coupling = sorted(
        name for name, leader in model.mimics.items()
        if name not in supplied and leader in supplied
    )
    return {
        "c_iii_two_waypoints": enough,
        "c_iii_time_strictly_increasing": increasing,
        "c_iii_position_widths_match": widths,
        "c_iii_joints_in_description": named_known,
        "c_iv_configuration_complete": not missing,
        "c_iv_missing_joints": missing,
        "c_iv_mimics_supplied_by_coupling": mimics_supplied_by_coupling,
        "waypoints": len(points),
        "instrument_loss": not (
            enough and increasing and widths and named_known and not missing
        ),
        "failed_clauses": [
            clause
            for clause, ok in (
                ("C-iii: at least two waypoints", enough),
                ("C-iii: time_from_start strictly increasing", increasing),
                ("C-iii: position width equals the joint-name list", widths),
                ("C-iii: every named joint is in the expanded description", named_known),
                ("C-iv: the configuration is complete", not missing),
            )
            if not ok
        ],
    }


def configurations(row: dict, model: geo.RobotModel) -> list[dict]:
    """Section 5.4 -- one full configuration per waypoint.

    The point's `positions` for the joints named in the message, **completed** by
    `trajectory_start.joint_state` for every other joint in the model, and then passed through
    `RobotModel.resolve` so that every `<mimic>` follower carries its leader's value. Section
    5.4: a configuration that moves the drive joint and leaves the five followers behind is
    not a pose this gripper can take.
    """
    start = row.get("trajectory_start") or {"name": [], "position": []}
    base = dict(zip(start.get("name") or [], start.get("position") or []))
    names = row.get("joint_names") or []
    out = []
    for point in row.get("points") or []:
        configuration = dict(base)
        configuration.update(dict(zip(names, point["positions"])))
        out.append(model.resolve(configuration))
    return out


# ---------------------------------------------------------------------------
# The per-pair accumulator
# ---------------------------------------------------------------------------
class PairAccumulator:
    """One (arm, link, object) pair's distribution, under both geometries.

    Section 2.2.1's standing pair is one of these rows like any other and is **excluded from
    every aggregate by name** downstream. It is accumulated rather than dropped because
    section 7.2 requires it reported as its own row with its measured distance.
    """

    __slots__ = ("arm", "link", "object", "standing", "hull", "vendor", "delta",
                 "censored", "penetrating_hull", "penetrating_vendor", "close_band",
                 "closest_hull", "largest_delta", "flip_hull_only", "flip_reversed",
                 "grip_change", "evaluations")

    def __init__(self, arm: str, link: str, obj: str) -> None:
        self.arm = arm
        self.link = link
        self.object = obj
        self.standing = common.is_standing_pair(link, obj)
        self.hull: list[float] = []
        self.vendor: list[float] = []
        self.delta: list[float] = []
        self.censored = 0
        self.penetrating_hull = 0
        self.penetrating_vendor = 0
        self.close_band = 0
        self.closest_hull: dict | None = None
        self.largest_delta: dict | None = None
        self.flip_hull_only: list[dict] = []
        self.flip_reversed: list[dict] = []
        self.grip_change: dict | None = None
        self.evaluations = 0

    def add(self, hull: float, vendor: float, hull_pen: bool, vendor_pen: bool,
            where: dict) -> None:
        self.evaluations += 1
        self.hull.append(hull)
        self.vendor.append(vendor)
        difference = vendor - hull
        self.delta.append(difference)
        if hull_pen:
            self.penetrating_hull += 1
        if vendor_pen:
            self.penetrating_vendor += 1
        if hull <= common.CLOSE_BAND_M:
            self.close_band += 1
        if self.closest_hull is None or hull < self.closest_hull["distance_m"]:
            self.closest_hull = {"distance_m": hull, "vendor_m": vendor, **where}
        if self.largest_delta is None or difference > self.largest_delta["delta_m"]:
            self.largest_delta = {"delta_m": difference, "hull_m": hull, "vendor_m": vendor,
                                  **where}
        # FLIP1, section 7.2. HULL-ONLY CONTACT is a finding about GEOMETRY; REVERSED is the
        # direction containment forbids and is a DISAGREEMENT under rule E.
        if hull <= 0.0 < vendor:
            self.flip_hull_only.append({"hull_m": hull, "vendor_m": vendor, **where})
        if vendor <= 0.0 < hull:
            self.flip_reversed.append({"hull_m": hull, "vendor_m": vendor, **where})

    def note_grip(self, change: float, where: dict) -> None:
        if self.grip_change is None or change > self.grip_change["change_m"]:
            self.grip_change = {"change_m": change, **where}

    def summarise(self) -> dict:
        return {
            "arm": self.arm,
            "link": self.link,
            "object": self.object,
            "standing_pair": self.standing,
            "evaluations": self.evaluations,
            "censored": self.censored,
            "hull": common.distribution(self.hull),
            "vendor": common.distribution(self.vendor),
            "delta_vendor_minus_hull": common.distribution(self.delta),
            "penetrating_hull": self.penetrating_hull,
            "penetrating_vendor": self.penetrating_vendor,
            "within_close_band_hull": self.close_band,
            "closest_hull": self.closest_hull,
            "largest_delta": self.largest_delta,
            "flip_hull_only_contact": self.flip_hull_only[:50],
            "flip_hull_only_contact_count": len(self.flip_hull_only),
            "flip_reversed": self.flip_reversed[:50],
            "flip_reversed_count": len(self.flip_reversed),
            "grip1_largest_change": self.grip_change,
        }


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------
def transforms_for(model: geo.RobotModel, poses: dict, link: str, entry: dict,
                   obj: SceneObject) -> tuple[np.ndarray, np.ndarray]:
    """The matrix and offset carrying a link's MESH frame into a box's own frame."""
    rotation, translation = poses[link]
    mesh_rotation = rotation @ entry["origin"]["rotation"]
    mesh_translation = rotation @ entry["origin"]["xyz"] + translation
    matrix = mesh_rotation.T @ obj.rotation
    offset = (mesh_translation - obj.centre) @ obj.rotation
    del model
    return matrix, offset


def evaluate(pairs, model, meshes, poses, objects, links, where, gripper_links=None,
             gripper_reference=None):
    """Every (link, object) distance at ONE configuration, under BOTH geometries.

    Rule M's broad phase is applied first, from the link's enclosing sphere, whose radius
    section 2.3 verifies is identical under both sets -- so a censored pair is censored
    identically under both and censoring can never manufacture or hide a difference.
    """
    for link in links:
        entry = meshes["links"][link]
        rotation, translation = poses[link]
        origin = rotation @ entry["origin"]["xyz"] + translation
        for obj in objects:
            bound = geo.censoring_bound(origin, entry["radius"], obj.centre, obj.half)
            accumulator = pairs[(link, obj.name)]
            if bound > common.CENSOR_M:
                accumulator.censored += 1
                continue
            matrix, offset = transforms_for(model, poses, link, entry, obj)
            hull, hull_pen, _ = geo.mesh_box_distance(
                entry["meshes"]["hull"], matrix, offset, obj.half
            )
            vendor, vendor_pen, _ = geo.mesh_box_distance(
                entry["meshes"]["vendor"], matrix, offset, obj.half
            )
            accumulator.add(hull, vendor, hull_pen, vendor_pen, where)
            if gripper_links is not None and link in gripper_links:
                reference = gripper_reference.get((link, obj.name))
                if reference is not None:
                    accumulator.note_grip(abs(hull - reference), where)


def link_distances(model, meshes, poses, links, objects, geometry_name):
    """The per-pair distance map at one configuration under ONE geometry. TUNNEL1's kernel."""
    out = {}
    for link in links:
        entry = meshes["links"][link]
        rotation, translation = poses[link]
        origin = rotation @ entry["origin"]["xyz"] + translation
        for obj in objects:
            if geo.censoring_bound(origin, entry["radius"], obj.centre, obj.half) > common.CENSOR_M:
                continue
            matrix, offset = transforms_for(model, poses, link, entry, obj)
            distance, _, _ = geo.mesh_box_distance(
                entry["meshes"][geometry_name], matrix, offset, obj.half
            )
            out[(link, obj.name)] = distance
    return out


def scene_from_generated(generated: dict, transforms: dict, root_link: str
                         ) -> tuple[list[SceneObject], dict]:
    """DIAGNOSTIC ONLY -- the generated file's objects, carried into the model root frame.

    **THIS IS NOT A CAMPAIGN PATH AND IT NEVER PRODUCES A `_computed.json`.** `criteria.md`
    I4 is explicit that the object poses the compute stage uses are the ones read back off the
    running `move_group`, in the frame it reports, so that no frame convention of the
    generated file has to be trusted; the file is V5's cross-check and nothing else.

    It exists because `criteria.md` section 10 permits the capture harness ONE shakedown run,
    that run read I4 before bring-up had applied the scene, and section 10 grants no second
    run to prove the fixed harness. Shipping a distance computation that has never been
    exercised on a real captured waypoint against real scene geometry would be worse than
    saying so. This is how it was exercised, and its output is labelled NOT DATA at every step.
    """
    transform = transforms.get(f"{generated['frame_id']}|{root_link}")
    if transform is None:
        return [], {"why": f"no generated transform to {root_link}"}
    forward = geo.rotation_from_rpy(*transform["rpy_rad"])
    offset = np.array(transform["xyz_m"], dtype=float)
    rotation, translation = forward.T, -forward.T @ offset
    objects = [
        SceneObject(
            name,
            rotation @ np.array(body["xyz_m"], dtype=float) + translation,
            rotation @ geo.rotation_from_rpy(*body["rpy_rad"]),
            np.array(body["dimensions_m"], dtype=float) / 2.0,
            root_link,
        )
        for name, body in sorted(generated["objects"].items())
    ]
    return objects, {"diagnostic": True, "frame": root_link, "objects": len(objects)}


def process_block(raw: Path, label: str, root: Path, verbose: bool,
                  diagnostic_scene: bool = False) -> dict:
    header = json.loads((raw / f"{label}_header.json").read_text())
    rows = json.loads((raw / f"{label}_trajectories.json").read_text())
    captures = json.loads((raw / f"{label}_captures.json").read_text())
    generated_scene = header["generated"]["planning_scene"]
    transforms = header["generated"]["static_transforms"]

    started = time.monotonic()
    residual = geo.self_test()
    print(f"   distance kernel residual vs the independent method: "
          f"{residual['worst_residual_m']:.3e} m ({residual['reference']})", flush=True)

    models: dict[str, geo.RobotModel] = {}
    mesh_cache: dict[str, dict] = {}
    scene_cache: dict[str, tuple] = {}
    pair_store: dict[str, dict] = {}
    trajectory_rows: list[dict] = []
    fk_samples: list[dict] = []
    tunnel_events: list[dict] = []
    v5_results: dict[str, dict] = {}
    ceiling_hits = 0
    sub_intervals_taken = 0
    achieved_sub_steps: list[float] = []

    by_capture: dict[str, list[dict]] = {}
    for row in rows:
        by_capture.setdefault(row.get("capture") or "<outside any capture>", []).append(row)

    for capture_name in sorted(by_capture):
        for index, row in enumerate(by_capture[capture_name]):
            arm = row["arm"]
            key = f"{capture_name}|{arm}"
            urdf_file = row.get("urdf_file")
            if not urdf_file or not (raw / urdf_file).exists():
                trajectory_rows.append(
                    {
                        "capture": capture_name, "arm": arm, "index": index,
                        "receive_index_in_arm": row.get("receive_index_in_arm"),
                        "computed": False,
                        "why": "no description was read back for this capture and arm, so "
                               "I11 has nothing to compute against",
                        "rule_c": {"instrument_loss": True,
                                   "failed_clauses": ["the description was never read back"]},
                    }
                )
                continue
            if key not in models:
                models[key] = geo.RobotModel((raw / urdf_file).read_text())
                mesh_cache[key] = mesh_sets(models[key], root)
                reading = next(
                    (record["i4_scene"].get(arm, {}) for record in captures
                     if record["capture"] == capture_name),
                    {},
                )
                objects, notes = scene_from_readback(reading)
                if diagnostic_scene and not objects:
                    objects, notes = scene_from_generated(
                        generated_scene, transforms, models[key].root
                    )
                scene_cache[key] = (objects, notes)
                v5_results[key] = v5_scene_agreement(
                    objects, generated_scene, transforms, models[key].root
                )
                if verbose:
                    print(f"   {key}: {len(models[key].collision)} collision link(s), "
                          f"{len(objects)} scene object(s), V5 ok={v5_results[key]['v5_ok']} "
                          f"worst={v5_results[key].get('worst_residual_m')}", flush=True)

            model = models[key]
            meshes = mesh_cache[key]
            objects, scene_notes = scene_cache[key]
            links = sorted(model.collision)
            pairs = pair_store.setdefault(
                capture_name,
                {},
            ).setdefault(arm, {(link, obj.name): PairAccumulator(arm, link, obj.name)
                               for link in links for obj in objects})

            clauses = rule_c_clauses(row, model)
            record = {
                "capture": capture_name,
                "arm": arm,
                "index": index,
                "receive_index_in_arm": row.get("receive_index_in_arm"),
                "model_id": row.get("model_id"),
                "waypoints": clauses["waypoints"],
                "rule_c": clauses,
                "computed": not clauses["instrument_loss"],
            }
            if clauses["instrument_loss"] or not objects:
                if not objects:
                    record["computed"] = False
                    record["why"] = "the scene read-back held no usable box"
                trajectory_rows.append(record)
                continue

            configurations_list = configurations(row, model)
            poses_list = [model.link_poses(configuration) for configuration in configurations_list]
            tip = header["generated"]["arms"][arm]["tip_link"]
            tool = [poses[tip][1] for poses in poses_list]
            steps = [float(np.linalg.norm(b - a)) for a, b in zip(tool, tool[1:])]
            intervals = [
                point_b["time_from_start"] - point_a["time_from_start"]
                for point_a, point_b in zip(row["points"], row["points"][1:])
            ]
            record["step_m"] = common.distribution(steps)
            record["steps_m"] = [round(step, 12) for step in steps]
            record["time_from_start_intervals_s"] = common.distribution(intervals)
            record["sampling_time_registered_s"] = common.SAMPLING_TIME_S
            record["intervals_disagreeing_with_registered_spacing"] = sum(
                1 for value in intervals if abs(value - common.SAMPLING_TIME_S) > 1e-6
            )

            gripper_links = sorted(
                link for link in links
                if any(name in link for name in
                       ("left_outer_knuckle", "left_finger", "left_inner_knuckle",
                        "right_outer_knuckle", "right_finger", "right_inner_knuckle"))
            )
            drive = next((name for name in model.movable if name.endswith("_drive_joint")), None)

            for waypoint, (configuration, poses) in enumerate(zip(configurations_list, poses_list)):
                where = {"capture": capture_name, "arm": arm, "trajectory": index,
                         "waypoint": waypoint}
                reference = {}
                if gripper_links and drive is not None:
                    reference = link_distances(model, meshes, poses, gripper_links, objects,
                                               "hull")
                evaluate(pairs, model, meshes, poses, objects, links, where,
                         gripper_links=set(gripper_links), gripper_reference=reference)
                # GRIP1, section 7.4: the SIX moving gripper links recomputed at both ends of
                # the drive joint's declared range, WITH ALL FIVE MIMIC FOLLOWERS MOVED WITH
                # IT (section 5.4). `RobotModel.resolve` enforces the coupling, so naming the
                # drive joint alone is exactly what produces the coupled pose.
                if gripper_links and drive is not None:
                    for value in common.GRIPPER_RANGE_RAD:
                        moved = model.link_poses({**configuration, drive: value})
                        alternative = link_distances(model, meshes, moved, gripper_links,
                                                     objects, "hull")
                        for pair_key, distance in alternative.items():
                            base = reference.get(pair_key)
                            if base is not None:
                                pairs[pair_key].note_grip(
                                    abs(distance - base), {**where, "drive_rad": value}
                                )

            # TUNNEL1, section 7.4. Per (link, object) pair, and per geometry.
            for interval, step in enumerate(steps):
                first, second = poses_list[interval], poses_list[interval + 1]
                deltas = {
                    name: configurations_list[interval + 1].get(name, 0.0)
                    - configurations_list[interval].get(name, 0.0)
                    for name in set(configurations_list[interval])
                    | set(configurations_list[interval + 1])
                }
                reach = model.joint_reach()
                for geometry_name in common.GEOMETRIES:
                    before = link_distances(model, meshes, first, links, objects, geometry_name)
                    after = link_distances(model, meshes, second, links, objects, geometry_name)
                    watch = []
                    for pair_key, distance_a in before.items():
                        if common.is_standing_pair(*pair_key):
                            continue
                        distance_b = after.get(pair_key)
                        if distance_b is None or distance_a <= 0.0 or distance_b <= 0.0:
                            continue
                        # `motion_bound` is a SOUND bound on how far any point of the link
                        # moves over the interval, so a pair whose bracketing distances both
                        # exceed it CANNOT reach contact between them. Skipping it is a
                        # proof, not a heuristic (see `geometry.motion_bound`).
                        travel = geo.motion_bound(model, pair_key[0], deltas, reach)
                        if min(distance_a, distance_b) > travel:
                            continue
                        watch.append((pair_key, distance_a, distance_b))
                    if not watch:
                        continue
                    count = min(common.SUB_CEILING,
                                max(1, int(math.ceil(step / common.SUB_STEP_M))))
                    if count >= common.SUB_CEILING:
                        ceiling_hits += 1
                    sub_intervals_taken += count
                    achieved_sub_steps.append(step / count if count else 0.0)
                    for sub in range(1, count):
                        fraction = sub / count
                        blended = {
                            name: configurations_list[interval].get(name, 0.0)
                            + fraction * deltas.get(name, 0.0)
                            for name in configurations_list[interval]
                        }
                        sub_poses = model.link_poses(model.resolve(blended))
                        watched_links = sorted({pair_key[0] for pair_key, _, _ in watch})
                        sampled = link_distances(model, meshes, sub_poses, watched_links,
                                                 objects, geometry_name)
                        for pair_key, distance_a, distance_b in watch:
                            value = sampled.get(pair_key)
                            if value is not None and value <= 0.0:
                                tunnel_events.append(
                                    {
                                        "capture": capture_name, "arm": arm,
                                        "trajectory": index, "interval": interval,
                                        "geometry": geometry_name,
                                        "link": pair_key[0], "object": pair_key[1],
                                        "sub_fraction": fraction,
                                        "sub_intervals": count,
                                        "bracketing_before_m": distance_a,
                                        "bracketing_after_m": distance_b,
                                        "sub_sample_m": value,
                                        "tool_step_m": step,
                                    }
                                )

            record["k_ii_intervals_at_or_above_step_mid"] = sum(
                1 for step in steps if step >= common.STEP_MID_M
            )
            trajectory_rows.append(record)
            if verbose:
                print(f"   {capture_name} {arm} #{index}: {clauses['waypoints']} waypoint(s), "
                      f"max step {record['step_m']['max']:.4f} m", flush=True)

    # FK1's sample, drawn with the registered seed over ADMISSIBLE waypoints (section 7.6).
    pool = [
        (row["capture"], row["arm"], row["index"], waypoint)
        for row in trajectory_rows
        if row.get("computed")
        for waypoint in range(row["waypoints"])
    ]
    rng = random.Random(common.FK1_SEED)
    drawn = rng.sample(pool, min(common.FK1_SAMPLE, len(pool))) if pool else []
    for capture_name, arm, index, waypoint in drawn:
        key = f"{capture_name}|{arm}"
        model = models[key]
        row = by_capture[capture_name][index]
        configuration = configurations(row, model)[waypoint]
        poses = model.link_poses(configuration)
        objects, _ = scene_cache[key]
        meshes = mesh_cache[key]
        distances = link_distances(model, meshes, poses, sorted(model.collision), objects,
                                   "hull")
        fk_samples.append(
            {
                "capture": capture_name, "arm": arm, "trajectory": index,
                "waypoint": waypoint,
                "configuration": {name: float(value) for name, value in configuration.items()},
                "i11_link_poses": {
                    link: {
                        "translation": [float(value) for value in poses[link][1]],
                        "rotation": [[float(value) for value in rowv] for rowv in poses[link][0]],
                    }
                    for link in sorted(model.collision)
                },
                # VALID1's reverse direction: the pairs the compute stage puts at `d <= 0`,
                # which MoveIt is expected to report among its contacts. The standing pair is
                # expected to violate it and is KNOWN-DIVERGENT, not an inconsistency.
                "nonpositive_pairs": [
                    {"link": link, "object": obj, "distance_m": distance,
                     "standing_pair": common.is_standing_pair(link, obj)}
                    for (link, obj), distance in sorted(distances.items())
                    if distance <= 0.0
                ],
                "all_pairs_positive": all(value > 0.0 for value in distances.values()),
                "uncensored_pairs": len(distances),
            }
        )

    computed = {
        "label": label,
        "block": header.get("block"),
        "is_shakedown": bool(header.get("is_shakedown")),
        "criteria_sha256": header.get("criteria_sha256"),
        "base_commit": common.BASE_COMMIT,
        # The validity flags are READ OFF THE RECORD and re-derived nowhere. V1's flag is the
        # conjunction of two `git` readings taken where the block was taken; re-deriving it
        # here would ask a tree that has since moved.
        "v1_clean_from_record": sorted({str(row.get("v1_clean")) for row in rows}),
        "distance_kernel_self_test": residual,
        "mesh_provenance": {
            key: value["provenance"] for key, value in sorted(mesh_cache.items())
        },
        "v5": v5_results,
        "scene_notes": {key: value[1] for key, value in sorted(scene_cache.items())},
        "trajectories": trajectory_rows,
        "pairs": {
            capture_name: {
                arm: [pair.summarise() for pair in accumulators.values() if pair.evaluations or pair.censored]
                for arm, accumulators in sorted(arms.items())
            }
            for capture_name, arms in sorted(pair_store.items())
        },
        "tunnel_events": tunnel_events,
        "tunnel_sub_sampling": {
            "sub_step_target_m": common.SUB_STEP_M,
            "sub_ceiling": common.SUB_CEILING,
            "intervals_hitting_the_ceiling": ceiling_hits,
            "sub_intervals_taken": sub_intervals_taken,
            "achieved_sub_step_m": common.distribution(achieved_sub_steps),
        },
        "fk_sample": fk_samples,
        "fk_sample_seed": common.FK1_SEED,
        "fk_sample_size_registered": common.FK1_SAMPLE,
        "fk_sample_pool": len(pool),
        "diagnostic_scene_from_generated_file": bool(diagnostic_scene),
        "compute_seconds": time.monotonic() - started,
        "numpy": np.__version__,
        "interpreter": sys.version,
    }
    return computed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=str(common.RAW), help="the raw/ directory to read")
    parser.add_argument("--block", action="append", default=None,
                        help="a block label to compute; repeatable. Default: every block "
                             "with a trajectories file at the top level of --raw")
    parser.add_argument("--suffix", default="",
                        help="written into the output file name. REPRO1 runs this stage "
                             "twice in the same interpreter and once in a second one, and "
                             "this is how the three outputs sit beside each other")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--diagnostic-scene-from-generated-file",
        action="store_true",
        help="DIAGNOSTIC, NOT DATA. Where I4's read-back held no object, take the scene from "
             "the GENERATED file instead. criteria.md I4 requires the read-back and this is "
             "not a campaign path: it writes <label>_diagnostic.json, never "
             "<label>_computed.json, so analyse.py cannot read it, and it prints a NOT-DATA "
             "banner. It exists to exercise the distance computation on real captured "
             "waypoints after the one permitted capture shakedown read I4 too early",
    )
    arguments = parser.parse_args()
    if arguments.diagnostic_scene_from_generated_file:
        print("#" * 100)
        print("## DIAGNOSTIC RUN -- THIS OUTPUT IS NOT DATA. The scene comes from the")
        print("## GENERATED FILE and not from I4's read-back, which criteria.md I4 requires.")
        print("## It writes <label>_diagnostic.json, which analyse.py does not read, and")
        print("## nothing it prints may appear in ANALYSIS.md or set or adjust any threshold.")
        print("#" * 100, flush=True)

    raw = Path(arguments.raw)
    root = common.repo_root()
    labels = arguments.block or sorted(
        path.name[: -len("_trajectories.json")]
        for path in raw.glob("*_trajectories.json")
    )
    if not labels:
        print(f"ABORT: no *_trajectories.json at the top level of {raw}", file=sys.stderr)
        return 2

    for label in labels:
        print(f"== compute: {label} ==", flush=True)
        computed = process_block(raw, label, root, arguments.verbose,
                                 arguments.diagnostic_scene_from_generated_file)
        name = (
            f"{label}_diagnostic{arguments.suffix}.json"
            if arguments.diagnostic_scene_from_generated_file
            else f"{label}_computed{arguments.suffix}.json"
        )
        (raw / name).write_text(json.dumps(computed, indent=2, sort_keys=True, default=str))
        print(f"== {label}: {len(computed['trajectories'])} trajectory record(s), "
              f"{sum(len(arms) for arms in computed['pairs'].values())} arm-capture(s), "
              f"{len(computed['tunnel_events'])} tunnel event(s), "
              f"{len(computed['fk_sample'])} FK sample(s) in "
              f"{computed['compute_seconds']:.1f}s -> {name} ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
