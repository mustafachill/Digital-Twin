# What the operator console is doing, latched (ADR-0071).
#
# Published by `cell_console` (`cite_bringup.program.console`) on the plant's
# domain, with the LATCHED profile (`cite_interfaces.qos`): a panel that starts
# late receives the current state at once, and a panel that hears none disables
# every button. The console enforces every refusal itself; a panel only shows
# this message and sends requests.
#
# NAMES. The console serves a zone, so its names carry the zone. They are formed
# once, by the generator (`cite_tools.model.ids.zone_scope`), and emitted into
# the zone's bring-up plan under `console:` - `/cite/<zone>/console/<leaf>` -
# where the console and any panel read them. No definition here restates them.
#
# STOP IS A SOFTWARE STOP (StopCell.srv). It cancels the goal in flight through
# the twin and holds the track; a gripper motion already in progress on a
# physical side is NOT stopped by a cancel (ADR-0070 item 4) and runs to its end.

uint8 NOT_STARTED=0       # Start robot has not succeeded; only Start robot is accepted
uint8 STARTING=1          # Start robot in progress: physical arms initialized, custody read
uint8 READY=2             # started and idle; Home and Start program are accepted
uint8 HOMING=3            # Home in progress
uint8 AWAITING_OPERATOR=4 # waiting for ConfirmOperator: the operator does what `prompt`
                          # says (clear the cell; place the part by hand). Asked only
                          # once the twin's mode was READ as SIM, and the confirmation is
                          # refused unless the twin is still in SIM when it arrives
uint8 RUNNING=5           # the program is running
uint8 STOPPING=6          # a Stop or a cancel was accepted; the goal in flight is being
                          # cancelled and the track held, and its end is awaited; or, in
                          # FAULT, the twin is being asked for SIM again. Never a homing
                          # move (ADR-0037)
uint8 FAULT=7             # the last request failed, or a stop could not be confirmed;
                          # `last_error` says why. Start robot is the way back to READY

uint8 TWIN_MODE_UNKNOWN=255  # no TwinMode heard on its topic yet

# WHERE THE SIGNAL GOES (ADR-0072). Sent by the operator with every HomeRobot and
# RunProgram goal (`target`), never defaulted: 0 is unset and REJECTED. Stated
# here once; the goals refer to these values. The console maps each to a twin
# mode in one place (`cite_bringup.program.targets`).
uint8 TARGET_SIM=1   # the simulation (the plant) only: the twin in SIM
uint8 TARGET_REAL=2  # the real arm (the counterpart) only: the twin in REAL
uint8 TARGET_TWIN=3  # both sides with one signal: the twin in VALIDATED

builtin_interfaces/Time stamp

uint8 state                 # one of the constants above
bool robot_started          # Start robot succeeded and nothing since has undone it
bool busy                   # a request is in progress
bool plant_at_start         # the plant's arm was brought to, or ended a full cycle at,
                            # the program's start, and nothing has moved it since as far
                            # as the console knows
bool counterpart_at_start   # the same, for the counterpart's arm. Start program is
                            # refused unless every side of its target is at the start
uint8[] available_targets   # the TARGET_* the running deployment can serve: [TARGET_SIM]
                            # when only the plant runs, all three when both sides run.
                            # A goal naming any other target is rejected
string step                 # what is being done now
string prompt               # in AWAITING_OPERATOR, exactly what the operator confirms;
                            # empty otherwise
string last_error           # why the last request failed, empty if it did not
uint8 twin_mode             # TwinMode.MODE_* as last heard, or TWIN_MODE_UNKNOWN
string[] physical_sides     # the RUNNING sides whose hardware is physical, from the plan
float64 speed_scale         # the scale of the goal in flight or last run, 0 if none yet
float64 minimum_speed_scale # the lowest scale a goal is accepted at: where a side is
                            # physical, the slowest the physical track carries the
                            # program's slowest slide at (`sides.minimum_speed_scale`);
                            # 0 where only (0, 1] applies
