"""A linear track's rail, generated inside the type's collision box (ADR-0079).

WHAT IT DRAWS. A UFACTORY-style linear rail: a light-grey aluminium profile with
dark T-slot lines along its sides, two steel guide rails on top with a dark dust
strip between them, black plastic end caps, and a dark motor housing at the -x
end with a cable gland on its side. The carriage plate is not drawn here: it
moves, and it belongs to the arm's description (see the type).

WHAT IT READS. The envelope is the rail's collision box, read from the L0 type
and never restated (P1). The origin is the box centre, where the scene template
places a body's visual. The guide rails' tops are the box top, which is where the
carriage rides; nothing drawn rises above it.

WHAT IT DOES NOT DO. It touches no collision, inertia, frame, joint or plugin.
The profile is appearance, not the vendor's drawing.

Regenerate or check with ``python -m cite_tools.visuals`` (see ``bodies``).
"""

from __future__ import annotations

from cite_tools.visuals.parts import Finish, Parts, box, cylinder, empty

# --------------------------------------------------------------------------- #
# Proportions. Appearance only; every one is checked to fit the envelope.
# --------------------------------------------------------------------------- #
END_CAP_M = 0.012  # along the rail
PROFILE_INSET_Y_M = 0.005  # the profile's side faces, in from the envelope
GUIDE_WIDTH_M = 0.012
GUIDE_HEIGHT_M = 0.012
GUIDE_OFFSET_Y_FRACTION = 0.32  # guide centres, as a fraction of the width from the axis
DUST_STRIP_WIDTH_M = 0.030
DUST_STRIP_PROUD_M = 0.002  # above the profile's top face
SLOT_HEIGHT_M = 0.006
SLOT_PROUD_M = 0.001  # outside the profile's side face
SLOT_LEVELS = (-0.25, 0.25)  # slot centres, as a fraction of the profile height
MOTOR_LENGTH_M = 0.070
MOTOR_INSET_Y_M = 0.008  # the motor housing's side faces, in from the envelope
GLAND_RADIUS_M = 0.008

ALUMINIUM = Finish("rail_aluminium", (0.75, 0.76, 0.78, 1.0), 0.0, 0.50)
GUIDE = Finish("guide_steel", (0.55, 0.57, 0.60, 1.0), 0.0, 0.35)
DUST = Finish("dust_strip", (0.10, 0.10, 0.11, 1.0), 0.0, 0.80)
PLASTIC = Finish("end_cap_plastic", (0.06, 0.06, 0.06, 1.0), 0.0, 0.60)
MOTOR = Finish("motor_housing", (0.25, 0.26, 0.28, 1.0), 0.0, 0.50)

#: Export order. Fixed, so the GLB's node and buffer order cannot drift.
FINISHES = (ALUMINIUM, GUIDE, DUST, PLASTIC, MOTOR)


def parts(size_m: tuple[float, float, float]) -> Parts:
    """Every part, grouped by finish, in the box-centred frame."""
    length, width, height = size_m
    hx, hy, hz = length / 2.0, width / 2.0, height / 2.0
    drawn = empty(FINISHES)

    inner_x = hx - END_CAP_M  # the profile and guides run between the caps
    profile_top = hz - GUIDE_HEIGHT_M
    profile_height = profile_top + hz
    profile_y = hy - PROFILE_INSET_Y_M
    motor_end = -inner_x + MOTOR_LENGTH_M  # the profile starts where the motor ends

    # Profile, between the motor housing and the +x cap.
    drawn[ALUMINIUM].append(
        box(
            (inner_x - motor_end, 2.0 * profile_y, profile_height),
            ((inner_x + motor_end) / 2.0, 0.0, -hz + profile_height / 2.0),
        )
    )

    # Guide rails, over the whole run including the motor housing, so the
    # carriage's stroke-zero end is over rail.
    guide_y = GUIDE_OFFSET_Y_FRACTION * width
    for side in (-1.0, 1.0):
        drawn[GUIDE].append(
            box(
                (2.0 * inner_x, GUIDE_WIDTH_M, GUIDE_HEIGHT_M),
                (0.0, side * guide_y, profile_top + GUIDE_HEIGHT_M / 2.0),
            )
        )

    # Dust strip between the guides, just proud of the profile.
    drawn[DUST].append(
        box(
            (inner_x - motor_end, DUST_STRIP_WIDTH_M, DUST_STRIP_PROUD_M),
            ((inner_x + motor_end) / 2.0, 0.0, profile_top + DUST_STRIP_PROUD_M / 2.0),
        )
    )
    # T-slot lines along both sides of the profile.
    for side in (-1.0, 1.0):
        for level in SLOT_LEVELS:
            drawn[DUST].append(
                box(
                    (inner_x - motor_end, SLOT_PROUD_M, SLOT_HEIGHT_M),
                    (
                        (inner_x + motor_end) / 2.0,
                        side * (profile_y + SLOT_PROUD_M / 2.0),
                        -hz + profile_height / 2.0 + level * profile_height,
                    ),
                )
            )

    # End caps, the full envelope section up to the profile top.
    for side in (-1.0, 1.0):
        drawn[PLASTIC].append(
            box(
                (END_CAP_M, width, profile_height),
                (side * (hx - END_CAP_M / 2.0), 0.0, -hz + profile_height / 2.0),
            )
        )

    # Motor housing at -x, and a cable gland on its -y side reaching the envelope.
    motor_y = hy - MOTOR_INSET_Y_M
    motor_x = (-inner_x + motor_end) / 2.0
    drawn[MOTOR].append(
        box(
            (MOTOR_LENGTH_M, 2.0 * motor_y, profile_height),
            (motor_x, 0.0, -hz + profile_height / 2.0),
        )
    )
    drawn[PLASTIC].append(
        cylinder(
            GLAND_RADIUS_M,
            MOTOR_INSET_Y_M,
            (motor_x, -(motor_y + MOTOR_INSET_Y_M / 2.0), -hz + profile_height / 2.0),
            "y",
        )
    )
    return drawn
