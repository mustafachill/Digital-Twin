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
// MECHANISM, and it is not the one an earlier draft of this file claimed.
//
// That draft called `gz::sim::Link::SetLinearVelocity` on a "belt link" and said
// it "keeps the surface where it is while still dragging what rests on it".
// Gazebo Harmonic does not work that way. `SetLinearVelocity` writes a
// `LinearVelocityCmd` component, which the Physics system consumes by MOVING the
// link at that velocity — on a non-static link that is exactly the belt
// translating away into the cell that the comment said it avoided. Gazebo
// Harmonic offers no surface-velocity primitive at all: the ODE `fdir1`/`motion1`
// pair that Gazebo Classic used has no DART equivalent, and nothing in
// gz-sim 8.11 exposes one. Verified against the installed headers rather than
// assumed.
//
// So the belt does not move, and neither does any link of it. This plugin
// carries what rests on the belt: a work-piece inside the belt's carry volume is
// commanded along the belt at the belt's speed, and released the moment it
// leaves that volume. The belt geometry stays exactly where the L0 model put it,
// which is also what lets the cell furniture remain one static body.
//
// THE FIDELITY COST, stated rather than hidden: transport here is kinematic,
// not frictional. A part that would slip, tumble, jam against a neighbour or
// fail to be driven at all in reality is carried smoothly here. No claim about
// belt handling, accumulation pressure or singulation can rest on this plugin. What it is for
// is making a station act because a work-piece ARRIVED — which is what the break
// beam observes and what makes the line sensor-driven rather than timed.
//
// THE PROPERTY THAT MUST NOT BE ERODED: nothing above ros2_control knows this
// exists. It speaks Gazebo transport only; the ROS-side name and type are a
// bridge's business, above this boundary and identical on the hardware path,
// where a real belt needs no help.
//
// A belt that has not been commanded carries nothing. That is not an
// optimisation: an idle belt must be inert, because a plugin that nudged parts
// around while no one had asked for a belt to run would be a source of motion
// nobody could attribute.

#include <algorithm>
#include <cmath>
#include <mutex>
#include <string>
#include <unordered_set>

#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/CanonicalLink.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/transport/Node.hh>

#include "gz/msgs/double.pb.h"

#include "cite_simulation/zone_rules.hpp"

namespace cite_simulation
{

/// Carry what rests on one belt, at a commanded speed.
class Conveyor
  : public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate
{
public:
  void Configure(
    const gz::sim::Entity &,
    const std::shared_ptr<const sdf::Element> & sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &) override
  {
    // Every value below comes from the generated world, which builds it from the
    // L0 model. A plugin that assumed a belt length, a topic or a speed would be
    // a second place a fact is stated (P1), and would break silently on a
    // differently-shaped conveyor.
    command_topic_ = sdf->Get<std::string>("command_topic", command_topic_).first;
    state_topic_ = sdf->Get<std::string>("state_topic", state_topic_).first;
    surface_pose_ = sdf->Get<gz::math::Pose3d>("surface_pose", surface_pose_).first;
    belt_length_ = sdf->Get<double>("belt_length_m", belt_length_).first;
    belt_width_ = sdf->Get<double>("belt_width_m", belt_width_).first;
    carry_height_ = sdf->Get<double>("carry_height_m", carry_height_).first;
    installed_speed_ = sdf->Get<double>("installed_speed_mps", installed_speed_).first;
    publish_period_ = sdf->Get<double>("publish_period_s", publish_period_).first;

    const auto direction = sdf->Get<std::string>("direction", std::string{"forward"}).first;
    if (direction != "forward" && direction != "reverse") {
      gzerr << "[cite_conveyor] <direction> must be forward or reverse; got '" << direction
            << "'\n";
      return;
    }
    // The belt runs along its surface frame's own +x. `reverse` is L0's word for
    // a drive installed the other way round, and this is the single place that
    // word becomes a sign.
    travel_sign_ = direction == "forward" ? 1.0 : -1.0;

    if (command_topic_.empty() || state_topic_.empty()) {
      gzerr << "[cite_conveyor] <command_topic> and <state_topic> are both required\n";
      return;
    }
    if (belt_length_ <= 0.0 || belt_width_ <= 0.0 || carry_height_ <= 0.0) {
      gzerr << "[cite_conveyor] <belt_length_m>, <belt_width_m> and <carry_height_m> must "
            << "all be positive; this belt would otherwise carry either nothing or "
            << "everything\n";
      return;
    }

    // What the belt may carry. Declared, not inferred: a belt that carried
    // whatever entered its volume would drag the gripper reaching into it.
    for (auto element = sdf->FindElement("carry"); element;
      element = element->GetNextElement("carry"))
    {
      carried_.insert(element->Get<std::string>());
    }
    if (carried_.empty()) {
      gzwarn << "[cite_conveyor] no <carry> models declared; this belt will transport "
             << "nothing\n";
    }

    node_.Subscribe(command_topic_, &Conveyor::OnCommand, this);
    state_publisher_ = node_.Advertise<gz::msgs::Double>(state_topic_);

    configured_ = true;
    // `gzwarn` rather than `gzmsg` for something that is not a warning: the cell
    // runs the simulator at verbosity 2 and `gzmsg` is level 3, so this line —
    // the only evidence that the belt exists at all — was never printed. A belt
    // that failed to load and a belt that loaded and was never commanded both
    // produced silence.
    gzwarn << "[cite_conveyor] belt at " << surface_pose_ << " commanded on '" << command_topic_
           << "', reporting on '" << state_topic_ << "'\n";
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

    if (commanded != 0.0) {
      Carry(ecm, commanded * travel_sign_);
    }
    PublishState(info, commanded);
  }

private:
  /// Command every carried model inside the belt's volume along the belt.
  void Carry(gz::sim::EntityComponentManager & ecm, double signed_speed)
  {
    // The carry volume sits ON the belt surface and extends upward only, so its
    // centre is half a carry height above the frame rather than on it.
    const gz::math::Vector3d centre(0.0, 0.0, carry_height_ / 2.0);
    const gz::math::Vector3d half(belt_length_ / 2.0, belt_width_ / 2.0, carry_height_ / 2.0);

    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::Model *,
      const gz::sim::components::Name * name) -> bool {
        if (carried_.count(name->Data()) == 0) {
          return true;
        }
        if (!zone_rules::inside_box(
            surface_pose_, gz::sim::worldPose(entity, ecm), centre, half))
        {
          return true;
        }
        Drive(ecm, entity, signed_speed);
        return true;
      });
  }

  /// Drive one model's canonical link along the belt.
  void Drive(
    gz::sim::EntityComponentManager & ecm, gz::sim::Entity model, double signed_speed)
  {
    const auto link_entity = CanonicalLinkOf(ecm, model);
    if (link_entity == gz::sim::kNullEntity) {
      return;
    }
    gz::sim::Link link(link_entity);

    // Velocity along the belt, in the WORLD frame.
    const gz::math::Vector3d along_world =
      surface_pose_.Rot().RotateVector(gz::math::Vector3d(signed_speed, 0.0, 0.0));

    // A part that is falling onto the belt keeps falling. Without this the
    // command would pin its vertical velocity at zero — `SetLinearVelocity`
    // makes Physics ignore wrenches on the link for the step, gravity included —
    // and a part released above the belt would hang in the air and slide.
    link.EnableVelocityChecks(ecm, true);
    const auto measured = link.WorldLinearVelocity(ecm);
    const double vertical = measured.has_value() ? measured->Z() : 0.0;
    const gz::math::Vector3d world_velocity(along_world.X(), along_world.Y(), vertical);

    // `SetLinearVelocity` takes the velocity in the LINK's own frame, so a part
    // that has rotated on the belt would otherwise be driven off at an angle.
    const auto link_pose = gz::sim::worldPose(link_entity, ecm);
    link.SetLinearVelocity(ecm, link_pose.Rot().Inverse().RotateVector(world_velocity));
  }

  static gz::sim::Entity CanonicalLinkOf(
    const gz::sim::EntityComponentManager & ecm, gz::sim::Entity model)
  {
    gz::sim::Entity link = gz::sim::kNullEntity;
    ecm.Each<gz::sim::components::CanonicalLink, gz::sim::components::ParentEntity>(
      [&](const gz::sim::Entity & entity, const gz::sim::components::CanonicalLink *,
      const gz::sim::components::ParentEntity * parent) -> bool {
        if (parent->Data() == model) {
          link = entity;
          return false;
        }
        return true;
      });
    return link;
  }

  /// Report the belt's speed: immediately when it changes, and periodically so a
  /// subscriber that starts late learns the current value without waiting for
  /// the next change.
  ///
  /// The period is a publication rate, not a schedule — nothing in the system is
  /// sequenced by it, and no behaviour depends on its value (P4). The previous
  /// version published every physics step, which at a 1 ms step is 1 kHz per
  /// belt for a value that changes when a person asks it to.
  void PublishState(const gz::sim::UpdateInfo & info, double commanded)
  {
    const double now = std::chrono::duration<double>(info.simTime).count();
    const bool changed = !published_ || commanded != last_published_speed_;
    const bool due = !published_ || (now - last_published_s_) >= publish_period_;
    if (!changed && !due) {
      return;
    }

    // The COMMANDED speed. Measured speed — which is what makes a stuck belt
    // visible — needs a measurement this plugin does not have, and publishing a
    // command dressed as a measurement would be the more dishonest of the two.
    gz::msgs::Double message;
    message.set_data(commanded);
    state_publisher_.Publish(message);

    published_ = true;
    last_published_speed_ = commanded;
    last_published_s_ = now;
  }

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

  //: Where the belt's working surface is, in the world. Generated from the same
  //: L0 frame the stations pick and place against, so the surface a part is
  //: carried on and the surface a station reaches for cannot disagree.
  gz::math::Pose3d surface_pose_;
  double belt_length_{0.0};
  double belt_width_{0.0};

  //: How far above the surface a part still counts as resting on the belt.
  double carry_height_{0.0};

  double travel_sign_{1.0};
  double installed_speed_{0.0};
  double publish_period_{0.0};

  std::string command_topic_;
  std::string state_topic_;
  std::unordered_set<std::string> carried_;

  gz::transport::Node node_;
  gz::transport::Node::Publisher state_publisher_;

  std::mutex mutex_;
  double commanded_speed_{0.0};

  bool published_{false};
  double last_published_speed_{0.0};
  double last_published_s_{0.0};

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::Conveyor,
  gz::sim::System,
  cite_simulation::Conveyor::ISystemConfigure,
  cite_simulation::Conveyor::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::Conveyor, "cite_simulation::Conveyor")
