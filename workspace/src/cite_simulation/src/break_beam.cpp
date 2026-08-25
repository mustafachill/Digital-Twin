// A through-beam presence sensor, as a Gazebo Sim system plugin.
//
// This is what makes the line sensor-driven rather than timed: a station acts
// because a work-piece was detected, never because a duration elapsed. v1
// sequenced everything with timers, and the reason that failed is the same reason
// P4 exists.
//
// It publishes only the beam's state. Turning that into a typed `DetectionEvent`
// is `cite_hardware`'s job, in simulation and on physical hardware alike — which
// is what keeps the interface above the sensor identical on both paths (P2). A
// plugin that published a ROS message directly would be a second, simulation-only
// route into the system.
//
// Detection is geometric rather than contact-based: a beam is broken by anything
// that crosses it, including something sliding past without touching, and a
// contact test would miss exactly those cases.

#include <mutex>
#include <string>
#include <unordered_set>

#include <gz/msgs/boolean.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

namespace cite_simulation
{

/// Report whether anything watchable is inside the beam's volume.
class BreakBeam
  : public gz::sim::System,
    public gz::sim::ISystemConfigure,
    public gz::sim::ISystemPostUpdate
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
      gzerr << "[cite_beam] attached to something that is not a model\n";
      return;
    }

    state_topic_ = sdf->Get<std::string>("state_topic", state_topic_).first;
    beam_axis_ = sdf->Get<std::string>("beam_axis", beam_axis_).first;
    beam_length_ = sdf->Get<double>("beam_length_m", beam_length_).first;
    beam_width_ = sdf->Get<double>("beam_width_m", beam_width_).first;

    if (state_topic_.empty()) {
      gzerr << "[cite_beam] <state_topic> is required\n";
      return;
    }
    if (beam_axis_ != "x" && beam_axis_ != "y" && beam_axis_ != "z") {
      gzerr << "[cite_beam] <beam_axis> must be x, y or z; got '" << beam_axis_ << "'\n";
      return;
    }

    // What the beam is allowed to notice. Declared rather than inferred: a beam
    // that reported every model would be broken by the conveyor it is mounted on.
    for (auto element = sdf->FindElement("watch"); element;
         element = element->GetNextElement("watch")) {
      watched_.insert(element->Get<std::string>());
    }
    if (watched_.empty()) {
      gzwarn << "[cite_beam] no <watch> models declared; this beam will never report "
             << "anything\n";
    }

    publisher_ = node_.Advertise<gz::msgs::Boolean>(state_topic_);
    configured_ = true;
    gzmsg << "[cite_beam] '" << model_.Name(ecm) << "' reporting on '" << state_topic_
          << "'\n";
  }

  void PostUpdate(
    const gz::sim::UpdateInfo & info, const gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    const auto beam = gz::sim::worldPose(model_.Entity(), ecm);
    bool blocked = false;

    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::Model *,
          const gz::sim::components::Name * name) -> bool {
        if (watched_.count(name->Data()) == 0) {
          return true;
        }
        const auto pose = gz::sim::worldPose(entity, ecm);
        if (Crosses(beam, pose)) {
          blocked = true;
          return false;
        }
        return true;
      });

    // Publish every step, not only on change. A subscriber that starts late must
    // learn the current state without waiting for the next transition — and the
    // consumer, not this plugin, is where edge detection belongs.
    gz::msgs::Boolean message;
    message.set_data(blocked);
    publisher_.Publish(message);
  }

private:
  /// Whether `other` lies inside the beam's volume.
  ///
  /// The beam is a thin box: `beam_length_m` along its axis, `beam_width_m` across
  /// the other two. Expressed in the beam's own frame, so a sensor mounted at an
  /// angle still measures across itself rather than across the world.
  bool Crosses(const gz::math::Pose3d & beam, const gz::math::Pose3d & other) const
  {
    const auto local = beam.Inverse() * other;
    const auto & p = local.Pos();

    const double half_length = beam_length_ / 2.0;
    const double half_width = beam_width_ / 2.0;

    if (beam_axis_ == "x") {
      return std::abs(p.X()) <= half_length && std::abs(p.Y()) <= half_width &&
             std::abs(p.Z()) <= half_width;
    }
    if (beam_axis_ == "y") {
      return std::abs(p.Y()) <= half_length && std::abs(p.X()) <= half_width &&
             std::abs(p.Z()) <= half_width;
    }
    return std::abs(p.Z()) <= half_length && std::abs(p.X()) <= half_width &&
           std::abs(p.Y()) <= half_width;
  }

  gz::sim::Model model_{gz::sim::kNullEntity};
  std::string state_topic_;
  std::string beam_axis_{"y"};
  double beam_length_{0.5};

  //: How thick the beam is across its axis. A real through-beam is a few
  //: millimetres; this is deliberately wider so that a work-piece travelling at
  //: belt speed cannot cross it between two physics steps and go unnoticed.
  double beam_width_{0.04};

  std::unordered_set<std::string> watched_;
  gz::transport::Node node_;
  gz::transport::Node::Publisher publisher_;
  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::BreakBeam,
  gz::sim::System,
  cite_simulation::BreakBeam::ISystemConfigure,
  cite_simulation::BreakBeam::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::BreakBeam, "cite_simulation::BreakBeam")
