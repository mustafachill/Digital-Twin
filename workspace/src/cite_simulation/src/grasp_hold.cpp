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

// A rigid grasp hold, as a Gazebo Sim system plugin (ADR-0061), told what to
// hold by the cell (ADR-0065).
//
// WHAT THIS REPLACED. Nothing simulated a grasp mechanism at all: ADR-0029
// removed ADR-0023's contact-triggered attachment plugin and left friction to
// hold a box in the jaws alone, on the evidence of an 84-trial campaign
// (`docs/measurements/2026-08-25-friction-grasp/`) that friction stops the jaws
// in the right place (68/68) but cannot hold the box STILL — up to 34.3 degrees
// of roll between the pads, worsening as the physics timestep got finer. That
// coupling made the cell less repeatable than the machine it models: two runs
// of `pick_and_place`, one seed, minutes apart, put the box 0.763 mm apart.
//
// THE FIDELITY COST, stated rather than hidden. While this plugin holds a part,
// that part is rigid in the gripper frame: it cannot slip, rotate against the
// pads, or be dropped by an inadequate clamping force. No claim about grasp
// reliability, slip margin, or required clamping force may rest on this plugin —
// the same sentence the conveyor's own header carries for belt transport, for
// the same reason. What it buys is that the one thing friction did well
// (stopping the jaws in the right place, which is still friction's job — this
// plugin never touches the joint) survives without the one thing it did badly.
//
// MECHANISM. Two messages, and nothing else decides:
//
//   - on `attach_topic_`, the nearest declared graspable model whose own origin
//     lies within `attach_radius_m_` of `attach_link_`'s origin is fixed to that
//     link;
//   - on `detach_topic_`, whatever is held is let go.
//
// Both carry an EMPTY message, because that is the shape Gazebo Harmonic's own
// `DetachableJoint` system takes on its `<attach_topic>` and `<detach_topic>`.
// This plugin uses the same `components::DetachableJoint` that system uses; it
// now takes its trigger from the same place too, rather than supplying its own.
//
// WHAT THE CELL KNOWS AND THIS PLUGIN DOES NOT. Whether the jaws are holding
// something is decided once, by `cite_skills::gripper_is_holding`, against the
// facility's declared work-piece interval widened by a stall band (ADR-0052
// option F). The L3 skill server publishes that verdict on
// `/cite/<zone>/<asset_id>/state`, and a simulation-only bridge in
// `cite_bringup` turns each change of it into one of the two messages above.
//
// WHY RE-DERIVING IT HERE WAS THE DEFECT, AND IT COST TWO DECISIONS IN A WEEK.
// This plugin used to decide for itself: the drive joint still for as long as
// the `GripperActionController`'s own `stall_timeout`, resting inside the
// part-width window, a graspable within radius — and, for the release, a margin
// past the held position plus that same window's open end. Every one of those
// re-derived the judgement `cite_skills` already makes, which is exactly the
// "one value, two places" P1 exists to forbid; and a threshold in two packages
// can only be kept honest by tuning, which is what was tried.
// [ADR-0062](docs/adr/0062-the-clamp-is-modelled-end-to-end.md) stopped the
// drive joint at the declared width and was refuted by measurement;
// [ADR-0064](docs/adr/0064-let-go-once-the-pads-are-clear.md) moved the release
// threshold to the window's open end and was refuted by its own promotion
// condition. Both records carry their tables; they are not restated here (P1).
//
// WHAT IT KEEPS is the one question the cell cannot answer: WHICH declared
// graspable is in the jaws. That is `attach_radius_m_` and `<graspable>`, and it
// is a fact about the world rather than about the gripper — L3 is never told
// which part it has (ADR-0052 §A.5), and it has no way to be.
//
// HELD IN THE GRIPPER FRAME, NEVER TO A FINGER. ADR-0023 welded the box to a
// finger, the box then followed that finger, stopped being the obstacle the
// jaws were stopping against, and the jaws closed through it to the commanded
// width "feeling nothing" — `Pick` reported `EXECUTION_FAILED` 8 times out of
// 8 while the weld carried the box 0.576 m anyway. `attach_link_` is `link5`,
// the arm's own last revolute link, chosen for the opposite property: nothing
// this plugin does moves it. `GraspSpec.attach_link_suffix`'s own docstring has
// the fuller account of why the gripper's OWN base link is not a link this
// plugin could target even if it wanted to — it does not survive the
// URDF-to-SDF conversion as an entity at all.
//
// LETTING GO IS PART OF CARRYING, and `conveyor.cpp` already paid for learning
// that the hard way: a `DetachableJoint` is removed on an explicit
// `RequestRemoveEntity`, on the entity it was created on, and nothing here
// leaves a component standing that would keep commanding a body once this
// plugin has stopped meaning to.
//
// IT NOW SPEAKS GAZEBO TRANSPORT, AND IT DELIBERATELY DID NOT BEFORE. The
// property claimed here until ADR-0065 was that it reads the ECM and nothing
// else — no contact sensor, no ROS, no transport in or out — so nothing it acted
// on could be late or lost. That property is gone, and the cost goes in beside
// it rather than in a record nobody reads at this line: a subscription can miss
// a message, and a missed attach is a box the arm carries on friction alone
// while everything above reports a grasp. Two things bound it. The state topic
// this chain starts from is LATCHED, so a bridge that starts late is told the
// present value rather than waiting for the next change; and the bridge logs
// when it publishes to a topic with no connections, so a message sent into an
// empty partition is visible rather than silent. Neither makes the transport
// lossless, and nothing here pretends otherwise.
//
// THE PROPERTY THAT MUST NOT BE ERODED: nothing above ros2_control knows this
// exists. The jaws still close, still meet the part's collision, still stop at
// its width, and the controller still reports `stalled=true, reached_goal=false`
// exactly as before — this plugin reads none of that and writes none of it, and
// it writes no limit, position or velocity to the drive joint, which has one
// owner (ADR-0063). It is a simulation-side aid absent from the hardware path,
// where a real gripper clamps hard enough that nothing needs to help it hold on.

#include <gz/msgs/empty.pb.h>

#include <atomic>
#include <string>
#include <unordered_set>

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/CanonicalLink.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>

namespace cite_simulation
{

/// Rigidly attach a declared graspable model to an arm's own wrist when the cell
/// says the jaws are holding, and let go when it says they are not (ADR-0065).
class GraspHold
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
    // L0 model. A plugin that guessed a link name, a radius or a topic would be
    // a second place a name or a number is made (P1).
    attach_link_ = sdf->Get<std::string>("attach_link", attach_link_).first;
    attach_radius_m_ = sdf->Get<double>("attach_radius_m", attach_radius_m_).first;
    attach_topic_ = sdf->Get<std::string>("attach_topic", attach_topic_).first;
    detach_topic_ = sdf->Get<std::string>("detach_topic", detach_topic_).first;

    if (attach_link_.empty()) {
      gzerr << "[cite_grasp_hold] <attach_link> is required; without it this plugin "
            << "cannot tell what to hold a part against\n";
      return;
    }
    if (attach_topic_.empty() || detach_topic_.empty()) {
      gzerr << "[cite_grasp_hold] <attach_topic> and <detach_topic> are both required; "
            << "this plugin no longer decides when a grasp begins or ends and would "
            << "otherwise never attach anything (ADR-0065)\n";
      return;
    }
    if (attach_topic_ == detach_topic_) {
      gzerr << "[cite_grasp_hold] <attach_topic> and <detach_topic> are the same topic ("
            << attach_topic_ << "); taking hold and letting go would be one message\n";
      return;
    }
    if (attach_radius_m_ <= 0.0) {
      gzerr << "[cite_grasp_hold] <attach_radius_m> must be positive; got "
            << attach_radius_m_ << "\n";
      return;
    }

    // What this plugin may attach to. Declared, not inferred: a gripper that
    // attached to whatever stood within its radius would grab a station's
    // fixture the first time the cell said it was holding something.
    for (auto element = sdf->FindElement("graspable"); element;
      element = element->GetNextElement("graspable"))
    {
      graspable_.insert(element->Get<std::string>());
    }
    if (graspable_.empty()) {
      gzwarn << "[cite_grasp_hold] no <graspable> models declared; this plugin will never "
             << "attach anything\n";
    }

    // Subscribed before `configured_` is set, so a message arriving between the
    // two cannot be acted on by a plugin that has not finished reading its own
    // declaration.
    if (!node_.Subscribe(attach_topic_, &GraspHold::OnAttachRequest, this) ||
      !node_.Subscribe(detach_topic_, &GraspHold::OnDetachRequest, this))
    {
      gzerr << "[cite_grasp_hold] could not subscribe to '" << attach_topic_ << "' and '"
            << detach_topic_ << "'; nothing would ever tell this plugin to hold a part\n";
      return;
    }

    configured_ = true;
    // `gzwarn` rather than `gzmsg` for something that is not a warning: the
    // cell runs the simulator at verbosity 2 and `gzmsg` is level 3, so this
    // line — the only evidence this plugin exists at all — would otherwise
    // never print, and a plugin that failed to load and one that never fired
    // would look identical. The same defect cost the belt and the beam their
    // own visibility before their headers were corrected the same way.
    gzwarn << "[cite_grasp_hold] attaching to '" << attach_link_ << "' within "
           << attach_radius_m_ << " m, on '" << attach_topic_ << "' / '"
           << detach_topic_ << "'\n";
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info, gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      // A request that arrives while the world is paused is NOT dropped: the
      // flags below are left standing and are served on the first stepping
      // update. Clearing them here would lose a grasp because somebody paused
      // the simulator to look at it.
      return;
    }

    if (!ResolveEntities(ecm)) {
      // The arm has not been spawned yet — this is a world plugin and the
      // world loads before `simulation.launch.py` spawns the arm's own
      // description. Nothing to do until the attach link resolves. Any pending
      // request stays pending, for the reason above.
      return;
    }

    // Detach first, so that a release and a fresh grasp arriving in the same
    // step are served in the only order that can be right: a plugin already
    // holding something ignores an attach, so serving the attach first would
    // drop the new part and keep the old one.
    if (detach_requested_.exchange(false)) {
      if (attached_ != gz::sim::kNullEntity) {
        Detach(ecm);
      }
    }

    if (attach_requested_.exchange(false)) {
      if (attached_ != gz::sim::kNullEntity) {
        // Already holding. The cell said "holding" while this plugin already
        // has a part, which is what a repeat or a re-established custody looks
        // like; taking a second one would weld two boxes to one wrist.
        return;
      }
      const auto candidate = NearestGraspable(ecm);
      if (candidate == gz::sim::kNullEntity) {
        // The cell reports a grasp and no declared graspable is within reach.
        // Reported rather than passed over: on a running cell it means the
        // work-piece is somewhere other than where the arm believes it is, and
        // the arm will now carry nothing while everything above says otherwise.
        gzwarn << "[cite_grasp_hold] told to take hold, and no declared graspable model "
               << "is within " << attach_radius_m_ << " m of '" << attach_link_ << "'\n";
        return;
      }
      Attach(ecm, candidate);
    }
  }

private:
  /// Serve an attach request. Runs on a gz-transport thread.
  ///
  /// It sets a flag and nothing else. The ECM may be touched only from the
  /// simulation's own update, so the work happens in `PreUpdate`; a plugin
  /// creating entities from a transport callback races the physics step.
  void OnAttachRequest(const gz::msgs::Empty &) {attach_requested_.store(true);}

  /// Serve a detach request. Runs on a gz-transport thread; see above.
  void OnDetachRequest(const gz::msgs::Empty &) {detach_requested_.store(true);}

  /// Find the attach link once and cache it. Returns whether it is known.
  ///
  /// It is not expected to disappear once found — the arm is not despawned
  /// mid-run — so re-resolving every step the way `Carry` walks candidate
  /// work-pieces would be wasted work for a fact that does not change.
  bool ResolveEntities(gz::sim::EntityComponentManager & ecm)
  {
    if (attach_link_entity_ == gz::sim::kNullEntity) {
      attach_link_entity_ = ecm.EntityByComponents(
        gz::sim::components::Link(), gz::sim::components::Name(attach_link_));
    }
    return attach_link_entity_ != gz::sim::kNullEntity;
  }

  /// The nearest declared graspable model within `attach_radius_m_` of the
  /// attach link's own origin, or `kNullEntity` if none is that close.
  ///
  /// Nearest rather than first found: `continuous_line` may have more than one
  /// work-piece on the belt at once, and a grasp must never take whichever one
  /// this loop happened to visit first.
  gz::sim::Entity NearestGraspable(const gz::sim::EntityComponentManager & ecm) const
  {
    const auto anchor = gz::sim::worldPose(attach_link_entity_, ecm).Pos();
    gz::sim::Entity nearest = gz::sim::kNullEntity;
    double nearest_distance = attach_radius_m_;
    for (const auto & name : graspable_) {
      const auto model = ecm.EntityByComponents(
        gz::sim::components::Model(), gz::sim::components::Name(name));
      if (model == gz::sim::kNullEntity) {
        continue;
      }
      const double distance = (gz::sim::worldPose(model, ecm).Pos() - anchor).Length();
      if (distance <= nearest_distance) {
        nearest = model;
        nearest_distance = distance;
      }
    }
    return nearest;
  }

  /// The link a detachable joint can attach to: the model's canonical link.
  ///
  /// `DetachableJointInfo` takes two LINK entities, not models. Passing a
  /// model entity produces a joint the physics engine silently never creates,
  /// so the gripper would go on reporting a stall while the part stayed
  /// exactly where it was — the same trap ADR-0023's own plugin recorded.
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

  void Attach(gz::sim::EntityComponentManager & ecm, gz::sim::Entity target)
  {
    const auto child_link = CanonicalLinkOf(ecm, target);
    if (child_link == gz::sim::kNullEntity) {
      gzerr << "[cite_grasp_hold] graspable model has no canonical link; not attaching\n";
      return;
    }

    // The component goes on a NEW entity rather than on either link — the same
    // shape gz-sim's own DetachableJoint system uses, and what gives Detach
    // something to remove without touching either link directly.
    joint_entity_ = ecm.CreateEntity();
    ecm.CreateComponent(
      joint_entity_,
      gz::sim::components::DetachableJoint({attach_link_entity_, child_link, "fixed"}));

    attached_ = target;
    const auto * name = ecm.Component<gz::sim::components::Name>(target);
    gzwarn << "[cite_grasp_hold] attached '" << (name != nullptr ? name->Data() : "?")
           << "' to '" << attach_link_ << "'\n";
  }

  void Detach(gz::sim::EntityComponentManager & ecm)
  {
    if (joint_entity_ != gz::sim::kNullEntity) {
      ecm.RequestRemoveEntity(joint_entity_);
      joint_entity_ = gz::sim::kNullEntity;
    }
    gzwarn << "[cite_grasp_hold] released\n";
    attached_ = gz::sim::kNullEntity;
  }

  std::string attach_link_;
  double attach_radius_m_{0.0};
  std::string attach_topic_;
  std::string detach_topic_;

  std::unordered_set<std::string> graspable_;

  gz::transport::Node node_;
  //: Set on a transport thread, served and cleared on the simulation's own
  //: update. Atomic rather than mutex-guarded because each is one bit and there
  //: is nothing to keep consistent between them: the update serves the detach
  //: first whatever order they arrived in, for the reason stated there.
  std::atomic<bool> attach_requested_{false};
  std::atomic<bool> detach_requested_{false};

  gz::sim::Entity attach_link_entity_{gz::sim::kNullEntity};
  gz::sim::Entity attached_{gz::sim::kNullEntity};
  gz::sim::Entity joint_entity_{gz::sim::kNullEntity};

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::GraspHold,
  gz::sim::System,
  cite_simulation::GraspHold::ISystemConfigure,
  cite_simulation::GraspHold::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::GraspHold, "cite_simulation::GraspHold")
