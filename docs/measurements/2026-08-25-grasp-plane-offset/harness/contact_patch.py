#!/usr/bin/env python3
"""What the commanded height does to the contact patch, as plane geometry.

The pad face is a 29.5 x 37.5 mm rectangle (`left_finger.stl`, the y = -0.026003
plane) pressed against a 50 x 50 mm face of the work-piece. The twist rotates the
part about the pad-to-pad axis, which is normal to both — so in that plane the
pad is a fixed rectangle and the part is a square rotating under it, and the
overlap is what the two bodies actually share.

Two quantities matter, and the height changes both, which is why the blocks alone
cannot separate the two mechanisms:

  * the AREA of the overlap, which sets how much torsional friction is available;
  * the height of its CENTROID above the centre of mass, which is the lever arm
    turning any horizontal acceleration of the carry into a torque about exactly
    the axis the rotation is measured about.

The third result is the one worth reading twice: with the pads centred the pad
rectangle lies wholly inside the part's face, so the overlap is **invariant under
the rotation**. Uncorrected it is not — the pad overhangs the part's top edge,
and the overlap changes as the part turns.

No simulator involved. Sutherland-Hodgman clipping of two convex polygons.
"""

from __future__ import annotations

import math
import sys

PAD_HALF_WIDTH_MM = 14.75      # left_finger.stl pad face, x extent
PAD_HALF_HEIGHT_MM = 18.75     # ... z extent: 37.5 mm tall
PART_HALF_MM = 25.0            # 50 mm cube


def pad_rectangle(offset_mm: float):
    """The pad face, in millimetres relative to the part's centre of mass."""
    return [(-PAD_HALF_WIDTH_MM, offset_mm - PAD_HALF_HEIGHT_MM),
            (PAD_HALF_WIDTH_MM, offset_mm - PAD_HALF_HEIGHT_MM),
            (PAD_HALF_WIDTH_MM, offset_mm + PAD_HALF_HEIGHT_MM),
            (-PAD_HALF_WIDTH_MM, offset_mm + PAD_HALF_HEIGHT_MM)]


def part_square(theta_deg: float):
    r = PART_HALF_MM * math.sqrt(2.0)
    return [(r * math.cos(math.radians(a + theta_deg)),
             r * math.sin(math.radians(a + theta_deg)))
            for a in (45.0, 135.0, 225.0, 315.0)]


def clip(subject, clipper):
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

    def cross(p, q, a, b):
        x1, y1 = p
        x2, y2 = q
        x3, y3 = a
        x4, y4 = b
        d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(d) < 1e-15:
            return q
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

    out = list(subject)
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        prev, out = out, []
        for j in range(len(prev)):
            p, q = prev[j - 1], prev[j]
            if inside(q, a, b):
                if not inside(p, a, b):
                    out.append(cross(p, q, a, b))
                out.append(q)
            elif inside(p, a, b):
                out.append(cross(p, q, a, b))
        if not out:
            return []
    return out


def area_and_centroid(poly):
    if len(poly) < 3:
        return 0.0, 0.0
    a = cy = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        cr = x1 * y2 - x2 * y1
        a += cr
        cy += (y1 + y2) * cr
    a /= 2.0
    if abs(a) < 1e-12:
        return 0.0, 0.0
    return abs(a), cy / (6.0 * a)


def report(offset_mm: float, label: str) -> None:
    print(f"--- {label}: pad centre {offset_mm:+.2f} mm from the centre of mass ---")
    print(f"  {'twist':>7} {'overlap mm2':>12} {'lever arm mm':>13}")
    for theta in (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 45.0):
        area, centroid = area_and_centroid(clip(part_square(theta),
                                                pad_rectangle(offset_mm)))
        print(f"  {theta:6.1f}° {area:12.1f} {centroid:13.2f}")


if __name__ == "__main__":
    offsets = [float(v) for v in sys.argv[1:]] or [24.44, 0.10]
    for off in offsets:
        report(off, "uncorrected" if off > 5 else "corrected")
        print()
