# The state of one conveyor.
#
# Speed is reported as commanded and as measured so that the two can disagree
# visibly. A conveyor that is commanded to run and is not moving is a fault the
# line must notice; reporting only the setpoint hides it.

std_msgs/Header header
string asset_id

uint8 MODE_STOPPED=0
uint8 MODE_RUNNING=1
uint8 MODE_FAULTED=2
uint8 mode

float64 commanded_speed_mps   # m/s, signed: negative runs the belt in reverse
float64 measured_speed_mps    # m/s, signed
uint32 workpieces_on_belt     # count currently carried
