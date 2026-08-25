// Copyright 2026 Sam Houston State University
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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
//
// It is a WORLD plugin, and that is forced rather than chosen. The sensor
// housing is one of the cell's authored bodies, and every authored body is
// joined to the cell root by a fixed joint — so converting the scene from URDF
// to SDF lumps all of them into a single link. There is no `beam_c1_out` model
// in the spawned world to attach a model plugin to, and a plugin attached to the
// scene would see the scene's origin rather than the sensor's. The beam's pose
// therefore arrives as data, resolved by the generator from the same L0 frame
// that positions the housing, so the two cannot describe different places.

#include <chrono>
#include <string>
#include <unordered_set>

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

#include "gz/msgs/boolean.pb.h"

#include "cite_simulation/zone_rules.hpp"

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
    const gz::sim::Entity &,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &) override
  {
    state_topic_ = sdf->Get<std::string>("state_topic", state_topic_).first;
    beam_pose_ = sdf->Get<gz::math::Pose3d>("beam_pose", beam_pose_).first;
    beam_axis_ = sdf->Get<std::string>("beam_axis", beam_axis_).first;
    beam_length_ = sdf->Get<double>("beam_length_m", beam_length_).first;
    beam_width_ = sdf->Get<double>("beam_width_m", beam_width_).first;
    beam_offset_ = sdf->Get<double>("beam_offset_m", beam_offset_).first;
    publish_period_ = sdf->Get<double>("publish_period_s", publish_period_).first;

    if (state_topic_.empty()) {
      gzerr << "[cite_beam] <state_topic> is required\n";
      return;
    }
    half_extents_ = zone_rules::beam_half_extents(beam_axis_, beam_length_, beam_width_);
    centre_offset_ = zone_rules::beam_centre_offset(beam_axis_, beam_offset_);
    if (half_extents_ == gz::math::Vector3d::Zero) {
      gzerr << "[cite_beam] <beam_axis> must be x, y or z and <beam_length_m> and "
            << "<beam_width_m> must both be positive; got axis '" << beam_axis_
            << "', length " << beam_length_ << ", width " << beam_width_ << "\n";
      return;
    }

    // What the beam is allowed to notice. Declared rather than inferred: a beam
    // that reported every model would be broken by the conveyor it watches.
    for (auto element = sdf->FindElement("watch"); element;
      element = element->GetNextElement("watch"))
    {
      watched_.insert(element->Get<std::string>());
    }
    if (watched_.empty()) {
      gzwarn << "[cite_beam] no <watch> models declared; this beam will never report "
             << "anything\n";
    }

    publisher_ = node_.Advertise<gz::msgs::Boolean>(state_topic_);
    configured_ = true;
    gzmsg << "[cite_beam] beam at " << beam_pose_ << " reporting on '" << state_topic_
          << "'\n";
  }

  void PostUpdate(
    const gz::sim::UpdateInfo & info, const gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    bool blocked = false;
    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::Model *,
      const gz::sim::components::Name * name) -> bool {
        if (watched_.count(name->Data()) == 0) {
          return true;
        }
        if (zone_rules::inside_box(
            beam_pose_, gz::sim::worldPose(entity, ecm), centre_offset_, half_extents_))
        {
          blocked = true;
          return false;
        }
        return true;
      });

    Publish(info, blocked);
  }

private:
  /// Publish immediately on a transition, and periodically otherwise.
  ///
  /// Both halves matter and for different reasons. A transition is the event the
  /// line acts on, so it must never wait for a period to elapse — that would be
  /// exactly the elapsed-time sequencing P4 forbids, reintroduced under the
  /// sensor. The period exists so that a subscriber which starts late learns the
  /// current state without waiting for the next transition; it sequences
  /// nothing, and no behaviour depends on its value.
  ///
  /// Edge detection stays with the consumer, which is why the current state is
  /// published rather than the change.
  void Publish(const gz::sim::UpdateInfo & info, bool blocked)
  {
    const double now = std::chrono::duration<double>(info.simTime).count();
    const bool changed = !published_ || blocked != last_published_;
    const bool due = !published_ || (now - last_published_s_) >= publish_period_;
    if (!changed && !due) {
      return;
    }

    gz::msgs::Boolean message;
    message.set_data(blocked);
    publisher_.Publish(message);

    published_ = true;
    last_published_ = blocked;
    last_published_s_ = now;
  }

  //: Where the beam is, in the world. Resolved by the generator from the same L0
  //: frame that places the sensor housing.
  gz::math::Pose3d beam_pose_;
  std::string state_topic_;
  std::string beam_axis_{"y"};
  double beam_length_{0.0};

  //: How thick the beam is across its axis. A real through beam is a few
  //: millimetres; the model's value is deliberately wider so that a work-piece
  //: travelling at belt speed cannot cross it between two physics steps and go
  //: unnoticed.
  double beam_width_{0.0};

  //: How far along its own axis the middle of the beam lies from the housing.
  //: A through beam is emitted from its housing and crosses the belt, so the
  //: housing is one END of the segment. Treating it as the middle instead put
  //: half the beam in the empty air beside the belt and left its near edge
  //: exactly on the belt's centreline — a sensor that could only be broken by a
  //: part that had not drifted by a millimetre.
  double beam_offset_{0.0};

  gz::math::Vector3d half_extents_{gz::math::Vector3d::Zero};
  gz::math::Vector3d centre_offset_{gz::math::Vector3d::Zero};

  double publish_period_{0.0};

  std::unordered_set<std::string> watched_;
  gz::transport::Node node_;
  gz::transport::Node::Publisher publisher_;

  bool published_{false};
  bool last_published_{false};
  double last_published_s_{0.0};

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::BreakBeam,
  gz::sim::System,
  cite_simulation::BreakBeam::ISystemConfigure,
  cite_simulation::BreakBeam::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::BreakBeam, "cite_simulation::BreakBeam")
