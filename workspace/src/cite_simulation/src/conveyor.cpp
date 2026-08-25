// A belt conveyor as a Gazebo Sim system plugin.
//
// Written rather than adopted, and ADR-0003 records why after evaluating
// `mzahana/conveyor_sim_ros2`: that package works on this stack, but it is
// commanded by publishing a `std_msgs/Float64` to a fixed `/conveyor/cmd_vel`.
// An untyped scalar carrying a command is a standing prohibition (CLAUDE.md §4),
// a hardcoded global topic cannot be instantiated three times under
// /cite/<zone>/<asset_id>, and it reports no state — so a belt commanded to run
// and not moving is invisible. The belt physics is the small part; the contract
// is the point.
//
// Mechanism: the belt surface is given a linear velocity, and anything resting on
// it is carried by friction. This is the standard approach and it keeps the
// contact behaviour physical — unlike grasping, transport by friction is stable,
// because the object is pressed into the surface by gravity rather than pinched
// between two moving pads.

#include <mutex>
#include <string>

#include <gz/msgs/double.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/components/AngularVelocityCmd.hh>
#include <gz/sim/components/LinearVelocityCmd.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

namespace cite_simulation
{

/// Drive a belt surface at a commanded speed.
class Conveyor
  : public gz::sim::System,
    public gz::sim::ISystemConfigure,
    public gz::sim::ISystemPreUpdate
{
public:
  void Configure(
    const gz::sim::Entity & entity,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager & ecm,
    gz::sim::EventManager &) override
  {
    model_ = gz::sim::Model(entity);
    if (!model_.Valid(ecm)) {
      gzerr << "[cite_conveyor] attached to something that is not a model\n";
      return;
    }

    // Both names come from the generated world. A plugin that assumed a link
    // name would be a second place a name is made (P1) and would break silently
    // on a differently-shaped conveyor.
    belt_link_ = sdf->Get<std::string>("belt_link", belt_link_).first;
    command_topic_ = sdf->Get<std::string>("command_topic", command_topic_).first;
    state_topic_ = sdf->Get<std::string>("state_topic", state_topic_).first;
    installed_speed_ = sdf->Get<double>("installed_speed_mps", installed_speed_).first;

    if (belt_link_.empty() || command_topic_.empty() || state_topic_.empty()) {
      gzerr << "[cite_conveyor] <belt_link>, <command_topic> and <state_topic> are all "
            << "required\n";
      return;
    }

    belt_entity_ = model_.LinkByName(ecm, belt_link_);
    if (belt_entity_ == gz::sim::kNullEntity) {
      gzerr << "[cite_conveyor] model '" << model_.Name(ecm) << "' has no link '"
            << belt_link_ << "'. Note that converting URDF to SDF lumps links joined "
            << "by fixed joints into their parent, so a link that exists in the "
            << "description may not exist here.\n";
      return;
    }

    node_.Subscribe(command_topic_, &Conveyor::OnCommand, this);
    state_publisher_ = node_.Advertise<gz::msgs::Double>(state_topic_);

    configured_ = true;
    gzmsg << "[cite_conveyor] '" << model_.Name(ecm) << "' driving link '" << belt_link_
          << "', commanded on '" << command_topic_ << "'\n";
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info, gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    double commanded = 0.0;
    {
      const std::lock_guard<std::mutex> lock(mutex_);
      commanded = commanded_speed_;
    }

    // The belt runs along its own X. Setting the link's velocity rather than
    // moving it keeps the surface where it is while still dragging what rests on
    // it — a belt that translated would drive off into the cell.
    gz::sim::Link belt(belt_entity_);
    belt.SetLinearVelocity(ecm, gz::math::Vector3d(commanded, 0.0, 0.0));

    // Report the commanded speed. Measured speed — which is what makes a stuck
    // belt visible — is the bridge's job in Phase 1.D, and until it exists this
    // deliberately publishes only what it was told, not what happened.
    gz::msgs::Double message;
    message.set_data(commanded);
    state_publisher_.Publish(message);
  }

private:
  void OnCommand(const gz::msgs::Double & message)
  {
    const double requested = message.data();

    // The installed speed is a physical fact about the drive (L0). A command
    // beyond it is clamped rather than obeyed: a simulation that accelerates a
    // belt past what the real one can do is modelling a different facility.
    const double limit = std::abs(installed_speed_);
    const double clamped = std::max(-limit, std::min(limit, requested));
    if (clamped != requested) {
      gzwarn << "[cite_conveyor] commanded " << requested << " m/s, clamped to " << clamped
             << " m/s by the installed drive speed\n";
    }

    const std::lock_guard<std::mutex> lock(mutex_);
    commanded_speed_ = clamped;
  }

  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Entity belt_entity_{gz::sim::kNullEntity};

  std::string belt_link_;
  std::string command_topic_;
  std::string state_topic_;
  double installed_speed_{0.15};

  gz::transport::Node node_;
  gz::transport::Node::Publisher state_publisher_;

  std::mutex mutex_;
  double commanded_speed_{0.0};

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::Conveyor,
  gz::sim::System,
  cite_simulation::Conveyor::ISystemConfigure,
  cite_simulation::Conveyor::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::Conveyor, "cite_simulation::Conveyor")
