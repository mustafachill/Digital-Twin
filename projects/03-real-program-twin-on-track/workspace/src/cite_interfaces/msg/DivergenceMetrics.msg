# How far the model is from reality (P8).
#
# The twin's central claim is that measurements transfer. Every such claim is
# backed by a published number, and this is that number.
#
# THE RULE, which is the part to read: `valid` is false whenever the sample's
# own conditions do not hold, and when it is false a comparison field is zero
# rather than absent or silently stale. The rule decides every mode, including
# modes added after this file was written.
#
# A SECOND RULE, on a different axis, and reading one for the other is how a
# number nobody measured gets believed: a comparison field carrying NaN was not
# computed at all, by anybody, valid or not. See the comparison block below.
#
# TOPIC below is the ONE place this name is written, for the same reason
# LineState and LineTopology carry theirs: it was in prose in
# docs/operations/bring-up.md and docs/operations/recording-and-replay.md and
# nowhere in the contract, which is one value in two documents waiting for a
# third (ADR-0050, decision 5d).
#
# `valid` IS A CONJUNCTION, and ADR-0050 decision 3 is where it is decided
# rather than here. Its five terms: the mode defines the comparison; both
# operands were present and paired within a stated window on the WALL clock;
# both sides' clock deficit over that window was measured and is within
# ADR-0049's bound; both sides report the same model_version; and the two frames
# correspond. A term with no instrument makes `valid` false, which is the gate
# ADR-0049 decision 3 stated in prose made arithmetic.
#
# The rule applied, per mode, and the list is the decision rather than an
# illustration: SIM and REAL false, because one side is idle and there is no
# second evaluation; SHADOW false, because the virtual side's state is DERIVED
# from the physical side's and the comparison would measure the mirror;
# VALIDATED is the only mode in which it may be true; VIRTUAL_LEAD false,
# because the mode is defined by there being no reverse flow, so the metric's
# second operand does not exist; CLOSED_LOOP false by default, because its
# validation gate is undefined.
#
# This file said until 2026-08-31 that the metric is "meaningful in SHADOW and
# VALIDATED" and filed VIRTUAL_LEAD as an open L5 question. SHADOW is removed on
# ADR-0050 decision 3's reason, which was in ADR-0011's own level table the whole
# time: its L1 Shadow row is real -> virtual and "divergence measured" appears
# one row down at L2 Validated, as the refinement that distinguishes them.
#
# `valid` DOES NOT MEAN "true of reality". It means the arithmetic was defined
# and its terms were measured in this window. Whether a defined number is a
# FIDELITY number is a separate predicate and `far_side_physical` is what
# answers it; where both sides are simulations generated from one L0 model, a
# comparison is a thing with itself and may not be published as a fidelity
# result (P8, ADR-0041).

string TOPIC="/cite/twin/divergence"

std_msgs/Header header
string asset_id             # never empty. There is no facility-level divergence
                            # number: validity is per asset, so an aggregate
                            # would average numbers whose terms differ
                            # (ADR-0050, decision 3)

bool valid                  # the conjunction above

# The comparison. Zeroed whenever `valid` is false.
#
# NaN IN ANY OF THESE MEANS THE FIELD WAS NOT COMPUTED AT ALL, by any producer,
# in any mode - which is a different statement from the zeroing rule above and
# is not covered by it. Zero is a measurement of zero and is the strongest claim
# a field here can carry; a field nothing computes must not make it.
#
# This distinction was in a package README and not in this file until
# 2026-08-31, and the header said only "zeroed whenever valid is false" - so the
# day the clock-deficit instrument ADR-0049 owes arrives and `valid` turns true,
# a sample would have published tcp_position_error_m = 0.0 as a measurement.
# This file is what `ros2 interface show` returns and what L6 records beside the
# numbers, so the marker is declared here.
#
# In this tree today, `cite_twin` computes the two joint-space fields and marks
# the other four NaN in every sample: a TCP pose error needs one TF buffer per
# side (ADR-0050 clause 1c) and forward kinematics for each, and the two timing
# deviations need L4 line state from both sides. A producer that computes one of
# them stops marking that one, and no producer may report zero for a quantity it
# did not measure.
float64 joint_error_rms_rad     # rad, root mean square over the arm's joints
float64 joint_error_max_rad     # rad, worst single joint
float64 tcp_position_error_m    # m, tool centre point
float64 tcp_orientation_error_rad  # rad, angle of the relative rotation
float64 cycle_time_deviation_s  # s, signed: positive means the real cell is slower
float64 event_timing_deviation_s  # s, signed, for discrete transitions

string model_version        # the L0 model hash these numbers were measured against;
                            # a comparison across model versions is not valid

# The conditions, which are NOT zeroed when `valid` is false. They are how a
# reader learns which conjunct failed, and an invalid sample whose terms were
# also zeroed would be indistinguishable from a dead publisher (ADR-0050, 5c).
#
# A sample must carry the terms that decide its own validity for the same reason
# it already carries model_version: a recording outlives the tree it was taken
# from, and L6 records this.
float64 plant_sample_age_s        # wall-clock age of the plant's operand at the
float64 counterpart_sample_age_s  # comparison instant, and the counterpart's.
                                  # NEGATIVE means the operand was absent.
                                  #
                                  # NOT the one-way transport latency, and never
                                  # to be labelled as one: that quantity needs a
                                  # common source clock and the two sides do not
                                  # have one (ADR-0043). The DIFFERENCE between
                                  # the two ages is the pair's wall-clock skew,
                                  # which is what separates mirroring lag from a
                                  # model error.
float64 plant_clock_deficit_s     # wall time minus simulated time, per side,
float64 counterpart_clock_deficit_s   # over window_s (ADR-0049 decision 1).
                                  # NEGATIVE means unmeasured: nothing in the
                                  # tree measures it and ADR-0049 leaves its
                                  # bound unset, so this term is what makes
                                  # `valid` false for every sample published
                                  # today.
float64 window_s                  # the window the deficits were measured over
bool far_side_physical            # whether this asset's far side actuates
                                  # hardware. False for both sides of a Phase
                                  # 2.A pair, which is what makes every number
                                  # taken there a test of the instrument.
bool counterpart_observed         # whether the twin is still WATCHING the far
                                  # side: false means the observer itself has
                                  # ended, not that the far side is quiet.
                                  #
                                  # The ages above cannot tell those apart - an
                                  # operand that never arrives and an observer
                                  # that died are the same hole - and a twin
                                  # whose far half has stopped must say so in a
                                  # field rather than by an absence. There is no
                                  # plant equivalent because this sample is
                                  # published by a timer on the plant's own
                                  # executor: a sample exists only where the
                                  # plant is being observed.
