# ADR-0067: The real robot's program drives the twin, and the arm rides a track

- **Status:** Proposed
- **Date:** 2026-09-29
- **Deciders:** Project owner
- **Related:** [ADR-0066](0066-run-the-cell-from-a-fixed-program.md) (continued here),
  [ADR-0036](0036-execution-side-trajectory-tolerances.md),
  [ADR-0044](0044-one-ros-domain-per-side-identical-names.md),
  [ADR-0052](0052-what-separates-a-grasp-from-a-stall-on-nothing.md),
  [ADR-0065](0065-the-cell-says-what-it-holds.md), CLAUDE.md §3 (P1, P2, P4)

## Context

ADR-0066 runs `cell_b` from a fixed program whose four poses were taught in simulation. The
real xArm 5 already has a program: a UFACTORY Studio Blockly project the owner exported as
`blockly-xArm5-RealDemo.tar.gz`. It differs from the twin in three ways that matter. The
real arm **rides a UFACTORY linear track**: it picks at track 0, lifts, slides 650 mm and
places on the belt. Its **poses are other poses** (pick at J1 -28 degrees, place at +60
degrees). Its **gripper closes to `pos` 550**, which the vendor driver maps to 0.300 rad and
the L0 linkage to 60.9 mm between the pads, so the twin's 50 mm cube would never be gripped.

The owner decided on 2026-09-29: the real program is the source and is read, never
hand-copied; the arm rides a track in the twin; the box is sized from the program's gripper
command; the belt is **not** twinned at this stage; `cell_a` and the parked event-driven line
stay as they are.

## Options considered

### Option A — Hand-copy the angles into `poses_rad` and add a track step to the list
Smallest change, and it puts every number of the real program in a second place (P1): an edit
on the robot would silently diverge from the twin.

### Option B — Read the Blockly XML strictly, derive the layout and the box from it (chosen)
The exported `app.xml` is copied byte for byte into `model/programs/` and pinned by sha256. A
strict reader turns it into typed steps; the generator emits its poses and steps into the
bring-up plan; the layout and the part are derived from its pick and place poses and its
gripper command.

### Option C — Interpret the Blockly program at run time
Keeps the program out of the plan, and so out of `./scripts/validate-model`: a pose past a
joint limit, or a part the gripper cannot stall on, would be found by the cell mid-cycle.

## Decision

1. **The program is read-only data.** `model/programs/xarm5_real_demo.blockly.xml` is the
   archive's `./app.xml`, byte for byte, with its provenance beside it; a host test pins its
   sha256, and `real-robot-code/` stays out of git. `configuration.program` on the `picker`
   names it; the ADR-0066 poses are removed, because they described a layout that no longer
   exists.
2. **`cite_tools.model.blockly` reads it strictly.** Only the blocks the program uses are
   accepted; an unknown block, a blended move (`r != -1`) and a move or grip that does not
   wait are refused. It converts degrees to radians, millimetres to metres, gripper `pos` to a
   width (`q = (850 - pos)/1000` rad, then the L0 linkage) and the angle speed to a velocity
   scaling of the description's 3.14 rad/s limit (20 deg/s is 0.111). Each distinct move is a
   named pose (`blockly_NN`, and `zero` for `reset`) beside `poses_rad`, and the steps are the
   plan's `programs:` block. `MoveTo` is unchanged; it already takes a named pose.
3. **Validation.** A refused program, a pose outside the vendor joint limits (now copied into
   L0 with a test against the vendor source), a track move beyond the stroke or speed, and a
   closing grip that the declared part cannot evidence (ADR-0052's two rules, applied to the
   program's width) are errors. The reach check is track-aware.
4. **The linear track.** A new `linear_axis` category and a `ufactory_linear_motor` type:
   700 mm stroke and 1 m/s from the datasheet, everything else engineered and `PROVISIONAL`.
   `picker_track` replaces `picker_base`, and `picker` stands on its `carriage` frame. The rail
   is a scene body; the prismatic joint is emitted into the **arm's** description under its
   base, with its own `JointTrajectoryController` in the arm's controller manager, so MoveIt,
   TF and the collision checks see where the arm is. The planning group stays five joints.
5. **The track step** sends one trajectory point, `|dx| / speed` seconds away, on the track
   controller's own `joint_trajectory` topic, and ends when the arm's joint states report the
   carriage within the track's goal tolerance: no sleep (P4). **The twin boundary forwards it
   to both sides** under the routing table the belt setpoint uses, so one signal drives both
   tracks. **The hardware path is not implemented**: the real track is commanded through the
   vendor's `set_linear_motor_pos` service, and the type declares a `sim` backend only, so a
   `real` track is refused by the validator.
6. **The layout is derived by forward kinematics** on the generated description, from the
   base to the centre of the pads closed on the part. The track runs along +x and the arm faces
   -y on its carriage, so its left is the direction of travel: pick at (-0.500, 2.924) on a
   0.600 m table, place at the belt's infeed (0.765, 3.060), the belt raised 35 mm so the part
   drops 4 mm. The numbers and their derivation are in `model/assets/instances/tracks.yaml`.
7. **The box is a 66 mm cube**, the smallest whole millimetre over which the 60.9 mm close
   still evidences a grasp (60.9 + 2.03 mm margin + 2.385 mm band = 65.33 mm); 0.2 kg. It is
   stated once in L0 and reaches every spawn through the plan; `SIDE_M` is gone. The belt
   type's transfer points move from 50 to 55 mm inside the belt's ends, because the larger
   part needs 53 mm of support margin in both cells.
8. **The belt is not twinned.** The real program has no belt block, so the runner does not
   drive one; `./scripts/program` starts each side's belt on that side's own domain
   (`cite_bringup.program.belt`), and `program_cycle` starts the plant's after the program.

## Consequences

### What this gets us
The twin runs what the robot runs, from the robot's own file, and a program the twin cannot
run is refused by `./scripts/validate-model` rather than by the cell.

### What this costs us
- **`cell_a`'s generated artifacts change** although its L0 files do not: the part and the
  belt type are facility-wide, so its beams, planning scene and plan move with them. Its
  scenarios were not re-run here.
- The track's rail is 110 mm wide so that the pick table keeps 20 mm of clearance; the real
  profile is wider. The stand height (0.710 m) is derived from the pick pose, not measured.
- Arrival of a track move is observed on the **plant**; through the twin the counterpart's
  track is commanded and not read back, as the counterpart's custody is not (ADR-0066).
- Every grasp figure published before this record was measured with the 50 mm cube.
- The Blockly gripper `speed` and the track block's missing `wait` field are not modelled; the
  twin's gripper runs at its L0 rate and every track move waits.

### What has been observed, 2026-09-29
One machine, nothing registered in advance, not a rate. `./scripts/scenario program_cycle
--zone cell_b` passed once with the bare verdict (cycle and teardown): lifted, carried along
the track, placed at the belt's infeed and carried on by the belt; the program took 81 s of
wall time. `./scripts/program --zone cell_b --headless` ran all 22 steps once through the
boundary, both tracks sliding on the one command, and both boxes ended at x = 1.944 m,
y = 3.060 / 3.061 m, z = 0.631 m: carried past the belt's end (1.910 m) onto the edge of the
outfeed table, with each side's belt run on that side.

### What we will have to revisit
The hardware path of the track (Phase 2.B), and the layout when the building is scanned.
Promotion to `Accepted` wants `program_cycle` passing in CI and the program run on the pair
with both boxes placed and carried, recorded.
