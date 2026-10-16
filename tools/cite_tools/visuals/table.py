"""A work table's visual mesh, generated inside the type's collision box (ADR-0079).

WHAT IT DRAWS. A light-wood bench: a solid top with a small chamfer on its upper
edge, overhanging four square legs; an apron rail under the top on all four
sides; stretcher rails near the floor carrying a lower shelf. The top is a
lighter wood than the frame, as a sanded top over a stained frame would be.

WHAT IT READS. The envelope is the body's collision box, read from the L0 type
and never restated (P1). The origin is the box centre, where the scene template
places a body's visual. The top face is the box's top face, ``+size_z / 2``,
which is the type's ``surface`` frame: a part placed there rests on the drawn
top, and nothing drawn rises above it.

WHAT IT DOES NOT DO. It touches no collision, inertia, frame or plugin. The
proportions are appearance, not a survey of the lab's tables.

Regenerate or check with ``python -m cite_tools.visuals`` (see ``bodies``).
"""

from __future__ import annotations

from cite_tools.visuals.parts import Finish, Parts, box, empty, frustum

# --------------------------------------------------------------------------- #
# Proportions. Appearance only; every one is checked to fit the envelope.
# --------------------------------------------------------------------------- #
TOP_THICKNESS_M = 0.030
TOP_CHAMFER_M = 0.004  # the upper edge's chamfer, both legs of the bevel
OVERHANG_M = 0.030  # from the top's edge to the legs' outer faces
LEG_M = 0.050  # square legs
APRON_DEPTH_M = 0.080
APRON_THICKNESS_M = 0.020
APRON_SETBACK_M = 0.010  # from the legs' outer faces
STRETCHER_M = 0.030  # square rails near the floor
STRETCHER_HEIGHT_M = 0.100  # rail centre above the floor
SHELF_THICKNESS_M = 0.015

TOP = Finish("light_wood_top", (0.78, 0.62, 0.42, 1.0), 0.0, 0.70)
FRAME = Finish("light_wood_frame", (0.70, 0.54, 0.36, 1.0), 0.0, 0.70)

#: Export order. Fixed, so the GLB's node and buffer order cannot drift.
FINISHES = (TOP, FRAME)


def parts(size_m: tuple[float, float, float]) -> Parts:
    """Every part, grouped by finish, in the box-centred frame."""
    length, width, height = size_m
    hx, hy, hz = length / 2.0, width / 2.0, height / 2.0
    drawn = empty(FINISHES)

    # Top: a slab with a chamfered band above it; the band's top face is the box top.
    top_bottom = hz - TOP_THICKNESS_M
    band_bottom = hz - TOP_CHAMFER_M
    drawn[TOP].append(
        box(
            (length, width, TOP_THICKNESS_M - TOP_CHAMFER_M),
            (0.0, 0.0, (top_bottom + band_bottom) / 2.0),
        )
    )
    drawn[TOP].append(
        frustum(
            (length, width),
            (length - 2.0 * TOP_CHAMFER_M, width - 2.0 * TOP_CHAMFER_M),
            band_bottom,
            hz,
        )
    )

    # Legs: floor to the underside of the top.
    leg_x = hx - OVERHANG_M - LEG_M / 2.0
    leg_y = hy - OVERHANG_M - LEG_M / 2.0
    leg_length = top_bottom + hz
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            drawn[FRAME].append(
                box((LEG_M, LEG_M, leg_length), (sx * leg_x, sy * leg_y, -hz + leg_length / 2.0))
            )

    # Apron: under the top, between the legs, set back from their outer faces.
    apron_z = top_bottom - APRON_DEPTH_M / 2.0
    span_x = 2.0 * leg_x - LEG_M
    span_y = 2.0 * leg_y - LEG_M
    apron_x = leg_x + LEG_M / 2.0 - APRON_SETBACK_M - APRON_THICKNESS_M / 2.0
    apron_y = leg_y + LEG_M / 2.0 - APRON_SETBACK_M - APRON_THICKNESS_M / 2.0
    for side in (-1.0, 1.0):
        drawn[FRAME].append(
            box((span_x, APRON_THICKNESS_M, APRON_DEPTH_M), (0.0, side * apron_y, apron_z))
        )
        drawn[FRAME].append(
            box((APRON_THICKNESS_M, span_y, APRON_DEPTH_M), (side * apron_x, 0.0, apron_z))
        )

    # Stretchers on all four sides near the floor, centred on the legs, and a
    # shelf resting on them.
    rail_z = -hz + STRETCHER_HEIGHT_M
    for side in (-1.0, 1.0):
        drawn[FRAME].append(box((span_x, STRETCHER_M, STRETCHER_M), (0.0, side * leg_y, rail_z)))
        drawn[FRAME].append(box((STRETCHER_M, span_y, STRETCHER_M), (side * leg_x, 0.0, rail_z)))
    shelf_z = rail_z + STRETCHER_M / 2.0 + SHELF_THICKNESS_M / 2.0
    # To the rails' centre lines, so it visibly rests on them; its corners run
    # into the legs, as a notched shelf would.
    drawn[TOP].append(box((2.0 * leg_x, 2.0 * leg_y, SHELF_THICKNESS_M), (0.0, 0.0, shelf_z)))
    return drawn
