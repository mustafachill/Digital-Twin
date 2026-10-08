# What the operator console is doing, latched (ADR-0071).
#
# Published by `cell_console` (`cite_bringup.program.console`) on the plant's
# domain, with the LATCHED profile (`cite_interfaces.qos`): a panel that starts
# late receives the current state at once, and a panel that hears none disables
# every button. The console enforces every refusal itself; a panel only shows
# this message and sends requests.
#
# NAMES. The console serves a zone, so its names carry the zone and cannot be a
# whole constant the way `/cite/twin/...` names are. What is constant is stated
# here once: every console name is `/cite/<zone>/<SCOPE>/<leaf>`, where the leaf
# is the `NAME` constant of the definition it serves - `state` below for this
# topic, `StartRobot.Request.NAME`, `ConfirmPart.Request.NAME`,
# `StopCell.Request.NAME`, `HomeRobot.Goal.NAME`, `RunProgram.Goal.NAME`. One
# helper composes them (`cite_bringup.program.console.console_name`).

string SCOPE="console"
string NAME="state"

uint8 NOT_STARTED=0     # Start robot has not succeeded; only Start robot is accepted
uint8 STARTING=1        # Start robot in progress: physical arms initialized, custody read
uint8 READY=2           # started and idle; Home and Start program are accepted
uint8 HOMING=3          # Home in progress
uint8 AWAITING_PART=4   # waiting for ConfirmPart: the operator places the part by hand
                        # and clears the cell. Asked only once the twin's mode was
                        # READ as SIM, so nothing crosses to a physical side meanwhile
uint8 RUNNING=5         # the program is running
uint8 STOPPING=6        # a Stop or a cancel was accepted; the goal in flight is being
                        # cancelled and the track held. Never a homing move (ADR-0037)
uint8 FAULT=7           # the last request failed, or a stop could not be confirmed;
                        # `last_error` says why. Start robot is the way back to READY

uint8 TWIN_MODE_UNKNOWN=255  # no TwinMode heard on its topic yet

builtin_interfaces/Time stamp

uint8 state             # one of the constants above
bool robot_started      # Start robot succeeded and nothing since has undone it
bool busy               # a request is in progress; Stop is accepted only now
string step             # what is being done now, or what the operator is asked
string last_error       # why the last request failed, empty if it did not
uint8 twin_mode         # TwinMode.MODE_* as last heard, or TWIN_MODE_UNKNOWN
string[] physical_sides # the sides whose hardware is physical, from the plan
float64 speed_scale     # the scale of the goal in flight or last run, 0 if none yet
