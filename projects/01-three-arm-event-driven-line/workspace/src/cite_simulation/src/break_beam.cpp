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
// The beam is a SEGMENT tested against the watched bodies' collision shapes, not
// a box tested against their model origins. That distinction is the whole
// behaviour of the sensor: a through beam breaks on a part's leading edge and
// stays broken until its trailing edge is past, at any height the part reaches.
// Testing the origin instead made the beam report a 50 mm cube 45 mm after its
// leading edge arrived — a belt indexed on that edge parked every piece short of
// the pick point — and gave the sensor a 20 mm-to-100 mm height window that no
// physical beam has. `zone_rules::segment_reaches_box` carries the full account.
//
// Nothing here declares how big a work-piece is. The shapes come from the
// simulator's own collision geometry, which is generated from L0, so a part
// whose size changes in the model changes what the beam sees with no second
// value to keep in step (P1, P5).
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
#include <optional>
#include <string>
#include <unordered_set>

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/Geometry.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

#include <sdf/Box.hh>
#include <sdf/Cylinder.hh>
#include <sdf/Geometry.hh>
#include <sdf/Sphere.hh>

#include "gz/msgs/boolean.pb.h"

#include "cite_simulation/zone_rules.hpp"

namespace cite_simulation
{
namespace
{

/// Half the extents of a collision shape, in the shape's own axes.
///
/// Box, cylinder and sphere are the shapes this facility authors, and each has
/// extents this layer can read exactly. Anything else — a mesh above all — has
/// its extents in a file L1 owns and this plugin deliberately does not read, so
/// it yields nothing and the caller reports the part as unseen rather than
/// guessing a size for it. That is the same refusal `Body.horizontal_extents_m`
/// makes in the model tooling, and it is the honest half of the trade: a beam
/// that silently invented a bounding box for a mesh would report detections
/// nobody could account for.
std::optional<gz::math::Vector3d> collision_half_extents(const sdf::Geometry & geometry)
{
  switch (geometry.Type()) {
    case sdf::GeometryType::BOX:
      if (const auto * box = geometry.BoxShape()) {
        return box->Size() / 2.0;
      }
      break;
    case sdf::GeometryType::CYLINDER:
      if (const auto * cylinder = geometry.CylinderShape()) {
        // The circumscribing box. A beam crossing a cylinder's corner region
        // reports a touch fractionally early; the alternative is a shape test
        // this cell has no cylindrical work-piece to justify.
        return gz::math::Vector3d(
          cylinder->Radius(), cylinder->Radius(), cylinder->Length() / 2.0);
      }
      break;
    case sdf::GeometryType::SPHERE:
      if (const auto * sphere = geometry.SphereShape()) {
        return gz::math::Vector3d(sphere->Radius(), sphere->Radius(), sphere->Radius());
      }
      break;
    default:
      break;
  }
  return std::nullopt;
}

}  // namespace

/// Report whether anything watchable is standing in the beam.
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
    const auto unit = zone_rules::beam_axis_unit(beam_axis_);
    if (unit == gz::math::Vector3d::Zero || beam_length_ <= 0.0 || beam_width_ <= 0.0) {
      gzerr << "[cite_beam] <beam_axis> must be x, y or z and <beam_length_m> and "
            << "<beam_width_m> must both be positive; got axis '" << beam_axis_
            << "', length " << beam_length_ << ", width " << beam_width_ << "\n";
      return;
    }
    // The beam's two ends, resolved once: the housing never moves, so neither do
    // they, and recomputing them every step would be the same arithmetic at
    // 1 kHz. `beam_offset_` slides the middle of the segment away from the
    // housing, which is what makes the housing an END of the beam rather than
    // its centre.
    const auto centre = zone_rules::beam_centre_offset(beam_axis_, beam_offset_);
    const auto half_span = unit * (beam_length_ / 2.0);
    beam_start_ = (beam_pose_ *
      gz::math::Pose3d(centre - half_span, gz::math::Quaterniond::Identity)).Pos();
    beam_end_ = (beam_pose_ *
      gz::math::Pose3d(centre + half_span, gz::math::Quaterniond::Identity)).Pos();
    beam_radius_ = beam_width_ / 2.0;

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
    // `gzwarn` rather than `gzmsg` for something that is not a warning: the cell
    // runs the simulator at verbosity 2 and `gzmsg` is level 3, so this line —
    // the only evidence that the beam exists at all — was never printed. A beam
    // that failed to load and a beam that nothing has crossed both produced
    // silence.
    gzwarn << "[cite_beam] beam at " << beam_pose_ << " reporting on '" << state_topic_
           << "'\n";
  }

  void PostUpdate(
    const gz::sim::UpdateInfo & info, const gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    // Every collision shape of every watched model, against the beam. Shapes
    // rather than models, because a model's origin is not its body: the origin
    // of a 50 mm cube is 25 mm behind its leading edge, and a beam that waited
    // for the origin waited 25 mm too long.
    bool blocked = false;
    ecm.Each<gz::sim::components::Collision, gz::sim::components::Geometry>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::Collision *,
      const gz::sim::components::Geometry * geometry) -> bool {
        if (!Watched(entity, ecm)) {
          return true;
        }
        const auto half_extents = collision_half_extents(geometry->Data());
        if (!half_extents.has_value()) {
          WarnUnreadableShape();
          return true;
        }
        if (zone_rules::segment_reaches_box(
            gz::sim::worldPose(entity, ecm), *half_extents, beam_start_, beam_end_,
            beam_radius_))
        {
          blocked = true;
          return false;
        }
        return true;
      });

    Publish(info, blocked);
  }

private:
  /// Whether this entity belongs to a model this beam was told to watch.
  ///
  /// Walks the whole ancestry rather than checking one level, so a collision
  /// inside a nested model still resolves to the top-level name the `<watch>`
  /// list carries — which is the name the simulator spawns a work-piece under.
  bool Watched(const gz::sim::Entity & entity, const gz::sim::EntityComponentManager & ecm) const
  {
    gz::sim::Entity current = entity;
    while (current != gz::sim::kNullEntity) {
      const auto * parent = ecm.Component<gz::sim::components::ParentEntity>(current);
      if (parent == nullptr) {
        return false;
      }
      current = parent->Data();
      if (ecm.Component<gz::sim::components::Model>(current) == nullptr) {
        continue;
      }
      const auto * name = ecm.Component<gz::sim::components::Name>(current);
      if (name != nullptr && watched_.count(name->Data()) > 0) {
        return true;
      }
    }
    return false;
  }

  /// Say once that a watched body has geometry this beam cannot measure.
  ///
  /// Once, because this runs at every physics step and a per-step warning would
  /// bury the log it is trying to be visible in. It is a warning and not an
  /// error because the beam keeps working for every shape it can read; what it
  /// must not do is stay silent, since the symptom otherwise is a sensor that
  /// simply never fires.
  void WarnUnreadableShape()
  {
    if (warned_unreadable_) {
      return;
    }
    warned_unreadable_ = true;
    gzwarn << "[cite_beam] a watched body on '" << state_topic_ << "' has collision geometry "
           << "that is not a box, cylinder or sphere; this beam cannot measure it and will "
           << "not report it\n";
  }

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

  //: How thick the beam is across its axis, as the model declares it. A through
  //: beam has a real, small width — a few millimetres of lensed spot — and this
  //: is now that number rather than an inflated one. It used to be widened to
  //: 40 mm so that a part could not cross the beam between two physics steps
  //: while only its origin was being tested; a segment against a body is
  //: occluded for the whole length of the part instead, which is hundreds of
  //: steps, so the inflation has no job left and its 20 mm of early trigger was
  //: costing the indexed belt its pick position.
  double beam_width_{0.0};

  //: How far along its own axis the middle of the beam lies from the housing.
  //: A through beam is emitted from its housing and crosses the belt, so the
  //: housing is one END of the segment. Treating it as the middle instead put
  //: half the beam in the empty air beside the belt and left its near edge
  //: exactly on the belt's centreline — a sensor that could only be broken by a
  //: part that had not drifted by a millimetre.
  double beam_offset_{0.0};

  //: The beam's two ends in the world, and half its thickness. Resolved in
  //: `Configure` from the pose, axis, length and offset above.
  gz::math::Vector3d beam_start_{gz::math::Vector3d::Zero};
  gz::math::Vector3d beam_end_{gz::math::Vector3d::Zero};
  double beam_radius_{0.0};

  double publish_period_{0.0};

  std::unordered_set<std::string> watched_;
  gz::transport::Node node_;
  gz::transport::Node::Publisher publisher_;

  bool published_{false};
  bool last_published_{false};
  double last_published_s_{0.0};

  bool configured_{false};
  bool warned_unreadable_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::BreakBeam,
  gz::sim::System,
  cite_simulation::BreakBeam::ISystemConfigure,
  cite_simulation::BreakBeam::ISystemPostUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::BreakBeam, "cite_simulation::BreakBeam")
