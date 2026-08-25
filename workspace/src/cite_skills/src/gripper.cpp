#include "cite_skills/gripper.hpp"

#include <algorithm>

namespace cite_skills
{

double gripper_position_for(double width_m, const GripperTravel & travel)
{
  const double clamped = std::max(0.0, std::min(travel.max_width_m, width_m));
  const double fraction = travel.max_width_m > 0.0 ? clamped / travel.max_width_m : 0.0;
  return travel.closed_position + (travel.open_position - travel.closed_position) * fraction;
}

double gripper_width_for(double position, const GripperTravel & travel)
{
  const double span = travel.open_position - travel.closed_position;
  if (span == 0.0) {
    return 0.0;
  }
  const double fraction = (position - travel.closed_position) / span;
  return std::max(0.0, std::min(1.0, fraction)) * travel.max_width_m;
}

GraspWidth resolve_grasp_width(double requested_m, double configured_default_m)
{
  if (requested_m > 0.0) {
    return GraspWidth{requested_m, GraspWidthSource::Goal};
  }
  if (configured_default_m > 0.0) {
    return GraspWidth{configured_default_m, GraspWidthSource::Default};
  }
  return GraspWidth{0.0, GraspWidthSource::Unknown};
}

bool gripper_is_holding(const GripperReport & report)
{
  return report.stalled && report.reached_width_m > report.commanded_width_m;
}

}  // namespace cite_skills
