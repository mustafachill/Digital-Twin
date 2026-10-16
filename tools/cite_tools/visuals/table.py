"""A work table's visual mesh, generated inside the type's collision box (ADR-0079).

WHAT IT DRAWS. A lab bench like the lab's own: a solid wooden top with a small
chamfer on its upper edge and a wooden apron rail under it on all four sides, on
four orange powder-coated square steel tube legs at its corners, with dark
levelling feet; the apron runs the full length of each side, however long. The
top's face and its sawn edges take two tones of the same wood, and the apron
takes the darker one, which is the cheap, texture-free way to read as timber
rather than a painted board.

WHAT IT READS. The envelope is the body's collision box, read from the L0 type
and never restated (P1). The origin is the box centre, where the scene template
places a body's visual. The top face is the box's top face, ``+size_z / 2``,
which is the type's ``surface`` frame: a part placed there rests on the drawn
top, and nothing drawn rises above it.

WHAT IT DOES NOT DO. It touches no collision, inertia, frame or plugin. The
proportions are appearance, not a survey of the lab's tables. The legs' steel is
non-metallic like every finish here (see ``parts``): powder coat is a dielectric
surface in any case.

Regenerate or check with ``python -m cite_tools.visuals`` (see ``bodies``).
"""

from __future__ import annotations

from cite_tools.visuals.parts import Finish, Parts, box, cylinder, empty, frustum

# --------------------------------------------------------------------------- #
# Proportions. Appearance only; every one is checked to fit the envelope.
# --------------------------------------------------------------------------- #
TOP_THICKNESS_M = 0.030
TOP_CHAMFER_M = 0.004  # the upper edge's chamfer, both legs of the bevel
OVERHANG_M = 0.030  # from the top's edge to the legs' outer faces
LEG_M = 0.040  # square steel tube
APRON_DEPTH_M = 0.070
APRON_THICKNESS_M = 0.020
APRON_SETBACK_M = 0.005  # from the legs' outer faces
FOOT_PAD_RADIUS_M = 0.018
FOOT_PAD_HEIGHT_M = 0.010
FOOT_STEM_RADIUS_M = 0.006
FOOT_STEM_HEIGHT_M = 0.015

#: The top's face and chamfer: a warm oak or beech.
WOOD_FACE = Finish("wood_top_face", (0.72, 0.50, 0.28, 1.0), 0.0, 0.70)
#: The top's sawn edges and the apron: the same wood a shade darker and warmer.
WOOD_EDGE = Finish("wood_top_edge", (0.60, 0.38, 0.19, 1.0), 0.0, 0.75)
#: The legs: safety-orange powder-coated steel tube.
STEEL = Finish("orange_powder_coat", (0.90, 0.40, 0.08, 1.0), 0.0, 0.45)
#: Levelling feet: dark rubber pads on zinc-grey stems, drawn as one dark finish.
FEET = Finish("foot_dark", (0.12, 0.12, 0.12, 1.0), 0.0, 0.70)

#: Export order. Fixed, so the GLB's node and buffer order cannot drift.
FINISHES = (WOOD_FACE, WOOD_EDGE, STEEL, FEET)


def parts(size_m: tuple[float, float, float]) -> Parts:
    """Every part, grouped by finish, in the box-centred frame."""
    length, width, height = size_m
    hx, hy, hz = length / 2.0, width / 2.0, height / 2.0
    drawn = empty(FINISHES)

    # Top: a slab whose sides are the edge tone, under a chamfered band whose top
    # face is the box top. The two meet on one plane, inside the top.
    top_bottom = hz - TOP_THICKNESS_M
    band_bottom = hz - TOP_CHAMFER_M
    drawn[WOOD_EDGE].append(
        box(
            (length, width, TOP_THICKNESS_M - TOP_CHAMFER_M),
            (0.0, 0.0, (top_bottom + band_bottom) / 2.0),
        )
    )
    drawn[WOOD_FACE].append(
        frustum(
            (length, width),
            (length - 2.0 * TOP_CHAMFER_M, width - 2.0 * TOP_CHAMFER_M),
            band_bottom,
            hz,
        )
    )

    # Legs: four, at the corners, from the top of the levelling foot to the
    # underside of the top.
    leg_x = hx - OVERHANG_M - LEG_M / 2.0
    leg_y = hy - OVERHANG_M - LEG_M / 2.0
    xs = (-leg_x, leg_x)
    ys = (-leg_y, leg_y)
    foot_top = -hz + FOOT_PAD_HEIGHT_M + FOOT_STEM_HEIGHT_M
    leg_length = top_bottom - foot_top
    for x in xs:
        for y in ys:
            drawn[STEEL].append(
                box((LEG_M, LEG_M, leg_length), (x, y, foot_top + leg_length / 2.0))
            )
            drawn[FEET].append(
                cylinder(
                    FOOT_PAD_RADIUS_M, FOOT_PAD_HEIGHT_M, (x, y, -hz + FOOT_PAD_HEIGHT_M / 2.0), "z"
                )
            )
            drawn[FEET].append(
                cylinder(
                    FOOT_STEM_RADIUS_M,
                    FOOT_STEM_HEIGHT_M,
                    (x, y, -hz + FOOT_PAD_HEIGHT_M + FOOT_STEM_HEIGHT_M / 2.0),
                    "z",
                )
            )

    # Apron: one wooden rail along each side under the top, between the corner
    # legs and set back from their outer faces.
    apron_z = top_bottom - APRON_DEPTH_M / 2.0
    apron_x = leg_x + LEG_M / 2.0 - APRON_SETBACK_M - APRON_THICKNESS_M / 2.0
    apron_y = leg_y + LEG_M / 2.0 - APRON_SETBACK_M - APRON_THICKNESS_M / 2.0
    for side in (-1.0, 1.0):
        drawn[WOOD_EDGE].append(
            box(
                (2.0 * leg_x - LEG_M, APRON_THICKNESS_M, APRON_DEPTH_M),
                (0.0, side * apron_y, apron_z),
            )
        )
        drawn[WOOD_EDGE].append(
            box(
                (APRON_THICKNESS_M, 2.0 * leg_y - LEG_M, APRON_DEPTH_M),
                (side * apron_x, 0.0, apron_z),
            )
        )
    return drawn
