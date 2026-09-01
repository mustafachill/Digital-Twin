# Shakedown — two vendor-geometry trials, taken before `criteria.md` was frozen

**Not campaign data.** These two trials exist for one purpose: to establish, before any
threshold was written, that the instrument can resolve the quantities ADR-0028 predicts.
They are the source of the resolution table in `criteria.md` §4 and appear in no figure
in §7. Both ran on the **shipped `vendor_meshes`** geometry, so nothing here is a
comparison and nothing here could have set a threshold to suit an outcome.

They were also what found two defects in the harness, both fixed before the campaign ran
and both recorded here rather than in a silent edit:

1. **The triad's `ey` ran right-pad-to-left-pad**, not left-to-right — measured as
   179.697°, i.e. anti-parallel to within 0.30°. `gripper_axes` now orients `ey` against
   the measured pad-to-pad vector, so `d_close_mm`'s sign means the same thing in both
   arms of the A/B. The sign of `d_close_mm` in `SHAKEDOWN_VENDOR_trials.json` is
   therefore **the pre-fix convention** and is not comparable with the campaign's.
2. **The contacts file was 131 MB per trial**, almost all of it the work-piece resting on
   the pick surface. It is now filtered to finger contacts inside the closure window.
   The two shakedown `*_contacts.csv` files were produced by the unfiltered writer and are
   **deleted rather than published**: 262 MB of table contacts is not evidence of
   anything, and the finger contacts inside them are reproduced in `*_patch.csv`.
