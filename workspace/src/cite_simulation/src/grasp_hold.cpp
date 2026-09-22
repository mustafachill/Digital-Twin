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

// A rigid grasp hold, as a Gazebo Sim system plugin (ADR-0061).
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
// THE FIDELITY COST, stated rather than hidden. While the drive joint is
// judged stalled, the box is rigid in the gripper frame: it cannot slip,
// rotate against the pads, or be dropped by an inadequate clamping force. No
// claim about grasp reliability, slip margin, or required clamping force may
// rest on this plugin — the same sentence the conveyor's own header carries for
// belt transport, for the same reason. What it buys is that the one thing
// friction did well (stopping the jaws in the right place, which is still
// friction's job — this plugin never touches the joint) survives without the
// one thing it did badly.
//
// MECHANISM. Two independent conditions, both read from the ECM and nothing
// else — no contact sensor, no ROS, no Gazebo transport in or out:
//
//   1. `drive_joint_`'s own velocity has not exceeded `stall_velocity_threshold_`
//      for `stall_timeout_s_` of SIMULATED time, and the joint's own position
//      lies inside [`hold_position_min_rad_`, `hold_position_max_rad_`]. The
//      first half is the identical rule `GripperActionController::checkForSuccess`
//      already applies — read from the same controller configuration rather
//      than restated (P1), so the two can never disagree about what "stalled"
//      means.
//
//      THIS USED TO BE A RAIL EXCLUSION — refusing a joint resting AT either
//      declared end of its stroke — rather than a window, on the reasoning
//      that a genuine stall always settles strictly between the two rails and
//      that jaws closing on empty air always settle AT one of them. Both
//      halves of that reasoning were wrong, and a tester's measurement is what
//      found it: this gripper's ordinary close target,
//      `gripper_default_grasp_width_m`, is mid-stroke, nowhere near either
//      rail, and a `Grasp` on empty air was observed settling mid-stroke too
//      — `commanded 45.0 mm, reached 46.0 mm, stalled=false, reached_goal=true`
//      — which the rail exclusion did not reject. The window this plugin now
//      tests against is the one `cite_skills::gripper_is_holding` already
//      judges a stall inside (ADR-0052 option F): the facility's declared part
//      interval, widened by the stall band at each edge, inverted through the
//      end effector's own linkage into two drive-joint positions AT
//      GENERATION TIME — `cite_simulation` does not link against
//      `cite_skills`, so the width arithmetic is resolved once, in
//      `tools/cite_tools/generate/world.py`, and delivered here as radians
//      rather than reimplemented. On the shipped model the window rejects the
//      measured 46.0 mm free-air rest position by 1.6 mm of margin.
//
//      This still needs a case the controller does not decide for this
//      plugin: a `Place` that opens the jaws to release a part leaves the
//      joint's velocity sitting at zero at `open_position_`. That position is
//      the gripper's own fully-open rest — the widest opening it reaches —
//      which is wider than any declared part's window, or the gripper could
//      never close past a released part on its way to the next one; likewise
//      `closed_position_` is narrower than the window, or a part in that
//      window could never be gripped at all. Neither rail is declared to be
//      outside the window; both are outside it because the window is a part
//      of the stroke a graspable part occupies and the rails are its two
//      ends. So a release is rejected by the SAME test a stall on a part
//      passes, and needs no test of its own.
//
//   2. A declared graspable model's own origin lies within `attach_radius_m_`
//      of `attach_link_`'s own origin. This is what keeps a stall from some
//      unrelated cause — the arm wedged against a fixture, say — from
//      attaching a box sitting elsewhere in the cell.
//
// Both together, on the SAME step, are what triggers an attach. Neither alone
// does. This is deliberately not the trigger ADR-0023 used and is not a milder
// version of it: that plugin fired on contact alone, before any force had
// developed, and armed at a position the pads reach on the way to grasping
// ANYTHING — including nothing. Firing this late — after the joint has already
// been still for `stall_timeout_s_`, exactly as long as the real controller
// waits before calling it a stall — means every attach this plugin ever makes
// coincides with the evidence `cite_skills::gripper_is_holding` already reads.
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
// DETACH. While attached, the joint's position is compared against
// `held_position_` — the position it was AT when the attach happened, not
// either declared rail. The jaws move back towards `open_position_` from
// there; the instant that movement exceeds `detach_margin_rad_`, the joint is
// released. `detach_margin_rad_` is `goal_tolerance` from the SAME gripper
// controller — not a value invented for this plugin, but the one number that
// controller already treats as "close enough to be the same position", asked
// here of the same joint for the same reason.
//
// THE PROPERTY THAT MUST NOT BE ERODED: nothing above ros2_control knows this
// exists. The jaws still close, still meet the part's collision, still stop at
// its width, and the controller still reports `stalled=true, reached_goal=false`
// exactly as before — this plugin reads none of that and writes none of it. It
// is a Gazebo-transport-side aid absent from the hardware path, where a real
// gripper clamps hard enough that nothing needs to help it hold on.

#include <chrono>
#include <cmath>
#include <optional>
#include <string>
#include <unordered_set>

#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/CanonicalLink.hh>
#include <gz/sim/components/Joint.hh>
#include <gz/sim/components/JointPosition.hh>
#include <gz/sim/components/JointVelocity.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>

namespace cite_simulation
{

/// Rigidly attach a graspable model to an arm's own wrist while its gripper's
/// drive joint is stalled on it, and let go the instant that joint is
/// commanded back open (ADR-0061).
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
    // Every value below comes from the generated world, which builds it from
    // the L0 model and, for the stall threshold and timeout, from the SAME
    // controller configuration the gripper's own GripperActionController
    // loads (P1). A plugin that restated either would be a second place for it
    // to be wrong, and one that guessed a link or joint name would be a second
    // place a name is made.
    attach_link_ = sdf->Get<std::string>("attach_link", attach_link_).first;
    drive_joint_ = sdf->Get<std::string>("drive_joint", drive_joint_).first;
    stall_velocity_threshold_ =
      sdf->Get<double>("stall_velocity_threshold", stall_velocity_threshold_).first;
    stall_timeout_s_ = sdf->Get<double>("stall_timeout_s", stall_timeout_s_).first;
    detach_margin_rad_ = sdf->Get<double>("detach_margin_rad", detach_margin_rad_).first;
    open_position_ = sdf->Get<double>("open_position", open_position_).first;
    closed_position_ = sdf->Get<double>("closed_position", closed_position_).first;
    attach_radius_m_ = sdf->Get<double>("attach_radius_m", attach_radius_m_).first;
    // The drive-joint position window a genuine stall on a declared part rests
    // inside — resolved from L0's part interval and the end effector's own
    // linkage at generation time, never here (ADR-0061's 2026-09-22
    // correction; see the file header).
    hold_position_min_rad_ =
      sdf->Get<double>("hold_position_min_rad", hold_position_min_rad_).first;
    hold_position_max_rad_ =
      sdf->Get<double>("hold_position_max_rad", hold_position_max_rad_).first;

    if (attach_link_.empty() || drive_joint_.empty()) {
      gzerr << "[cite_grasp_hold] <attach_link> and <drive_joint> are both required; "
            << "without them this plugin cannot tell what to hold or what to watch\n";
      return;
    }
    if (stall_timeout_s_ <= 0.0 || attach_radius_m_ <= 0.0 || detach_margin_rad_ <= 0.0) {
      gzerr << "[cite_grasp_hold] <stall_timeout_s>, <attach_radius_m> and "
            << "<detach_margin_rad> must all be positive; got " << stall_timeout_s_ << ", "
            << attach_radius_m_ << ", " << detach_margin_rad_ << "\n";
      return;
    }
    if (open_position_ == closed_position_) {
      gzerr << "[cite_grasp_hold] <open_position> and <closed_position> are equal ("
            << open_position_ << "); a gripper with no stroke has nothing to hold\n";
      return;
    }
    if (hold_position_min_rad_ >= hold_position_max_rad_) {
      gzerr << "[cite_grasp_hold] <hold_position_min_rad> (" << hold_position_min_rad_
            << ") is not below <hold_position_max_rad> (" << hold_position_max_rad_
            << "); the window a genuine stall must rest inside is empty or inverted\n";
      return;
    }

    // What this plugin may attach to. Declared, not inferred: a gripper that
    // attached to whatever stood within its radius would grab a station's
    // fixture the first time it stalled against one.
    for (auto element = sdf->FindElement("graspable"); element;
      element = element->GetNextElement("graspable"))
    {
      graspable_.insert(element->Get<std::string>());
    }
    if (graspable_.empty()) {
      gzwarn << "[cite_grasp_hold] no <graspable> models declared; this plugin will never "
             << "attach anything\n";
    }

    configured_ = true;
    // `gzwarn` rather than `gzmsg` for something that is not a warning: the
    // cell runs the simulator at verbosity 2 and `gzmsg` is level 3, so this
    // line — the only evidence this plugin exists at all — would otherwise
    // never print, and a plugin that failed to load and one that never fired
    // would look identical. The same defect cost the belt and the beam their
    // own visibility before their headers were corrected the same way.
    gzwarn << "[cite_grasp_hold] watching '" << drive_joint_ << "', attaching to '"
           << attach_link_ << "' within " << attach_radius_m_ << " m\n";
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info, gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    if (!ResolveEntities(ecm)) {
      // The arm has not been spawned yet — this is a world plugin and the
      // world loads before `simulation.launch.py` spawns the arm's own
      // description. Nothing to do until both names resolve to something.
      return;
    }

    const auto * position = ecm.Component<gz::sim::components::JointPosition>(drive_joint_entity_);
    const auto * velocity = ecm.Component<gz::sim::components::JointVelocity>(drive_joint_entity_);
    if (position == nullptr || position->Data().empty() ||
      velocity == nullptr || velocity->Data().empty())
    {
      return;
    }
    const double q = position->Data().front();
    const double v = velocity->Data().front();
    const double now = std::chrono::duration<double>(info.simTime).count();

    if (!last_moving_s_.has_value() || std::abs(v) > stall_velocity_threshold_) {
      // Either the first sample this plugin has ever seen of this joint, or a
      // genuine move: both restart the stall clock, the first so that a joint
      // already at rest when the world starts is not read as having been
      // stalled since before time began.
      last_moving_s_ = now;
    }

    if (attached_ != gz::sim::kNullEntity) {
      // --- Attached: watch for the release. ---------------------------------
      // How far the joint has moved from where it was holding, towards
      // OPEN rather than towards closed — `open_direction_` is which way that
      // is, derived once in Configure from the two declared rails. Moving
      // further CLOSED than the held position is not a release and is not
      // tested for: a stall that tightens further is still the same grasp.
      const double opened_by = (q - held_position_) * open_direction_;
      if (opened_by > detach_margin_rad_) {
        Detach(ecm);
      }
      return;
    }

    // --- Not attached: watch for a stall on something. -----------------------
    if (now - *last_moving_s_ < stall_timeout_s_) {
      return;
    }
    // The joint's own position must lie inside the part window — the reason
    // is the file header's, not "resting at a rail": a rail exclusion is
    // neither necessary nor sufficient, since the ordinary close target is
    // mid-stroke and a measured free-air rest position is too. This is what
    // stops a `Place` release from being read as a fresh grasp of the box
    // just set down (`open_position_` sits outside the window by
    // construction) exactly as it rejects a stall on empty air.
    if (q < hold_position_min_rad_ || q > hold_position_max_rad_) {
      return;
    }

    const auto candidate = NearestGraspable(ecm);
    if (candidate != gz::sim::kNullEntity) {
      Attach(ecm, candidate, q);
    }
  }

private:
  /// Find both named entities once and cache them. Returns whether both are
  /// known.
  ///
  /// Neither is expected to disappear once found — the arm is not despawned
  /// mid-run — so re-resolving every step the way `Carry` walks candidate
  /// work-pieces would be wasted work for a fact that does not change.
  bool ResolveEntities(gz::sim::EntityComponentManager & ecm)
  {
    if (attach_link_entity_ == gz::sim::kNullEntity) {
      attach_link_entity_ = ecm.EntityByComponents(
        gz::sim::components::Link(), gz::sim::components::Name(attach_link_));
    }
    if (drive_joint_entity_ == gz::sim::kNullEntity) {
      drive_joint_entity_ = ecm.EntityByComponents(
        gz::sim::components::Joint(), gz::sim::components::Name(drive_joint_));
      if (drive_joint_entity_ != gz::sim::kNullEntity) {
        // Enabled here rather than assumed present: without these two
        // components Physics never populates the joint's position or
        // velocity, and every read below would silently see nothing.
        ecm.CreateComponent(drive_joint_entity_, gz::sim::components::JointPosition());
        ecm.CreateComponent(drive_joint_entity_, gz::sim::components::JointVelocity());
        // Which way OPEN is, in this joint's own units. Computed once, here,
        // rather than every step: it is a fact about the two rails, and both
        // arrived fixed in Configure.
        open_direction_ = open_position_ >= closed_position_ ? 1.0 : -1.0;
      }
    }
    return attach_link_entity_ != gz::sim::kNullEntity &&
           drive_joint_entity_ != gz::sim::kNullEntity;
  }

  /// The nearest declared graspable model within `attach_radius_m_` of the
  /// attach link's own origin, or `kNullEntity` if none is that close.
  ///
  /// Nearest rather than first found: `continuous_line` may have more than one
  /// work-piece on the belt at once, and a stall must never attach whichever
  /// one this loop happened to visit first.
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

  void Attach(gz::sim::EntityComponentManager & ecm, gz::sim::Entity target, double held_position)
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
    held_position_ = held_position;
    const auto * name = ecm.Component<gz::sim::components::Name>(target);
    gzwarn << "[cite_grasp_hold] attached '" << (name != nullptr ? name->Data() : "?")
           << "' at " << held_position << " rad on '" << drive_joint_ << "'\n";
  }

  void Detach(gz::sim::EntityComponentManager & ecm)
  {
    if (joint_entity_ != gz::sim::kNullEntity) {
      ecm.RequestRemoveEntity(joint_entity_);
      joint_entity_ = gz::sim::kNullEntity;
    }
    gzwarn << "[cite_grasp_hold] released\n";
    attached_ = gz::sim::kNullEntity;
    // A fresh episode starts the stall clock over, exactly as it does at
    // world start: the joint is about to move (that is what a detach IS), so
    // treating "just now" as the last known movement is correct rather than
    // carrying a stale timestamp from before the release forward.
    last_moving_s_.reset();
  }

  std::string attach_link_;
  std::string drive_joint_;
  double stall_velocity_threshold_{0.0};
  double stall_timeout_s_{0.0};
  double detach_margin_rad_{0.0};
  double open_position_{0.0};
  double closed_position_{0.0};
  double attach_radius_m_{0.0};

  //: The drive-joint position window a genuine stall on a declared part rests
  //: inside — resolved from L0's part interval, the stall band and the end
  //: effector's own linkage at generation time, never here (ADR-0061's
  //: 2026-09-22 correction). Neither is a rail: see the file header.
  double hold_position_min_rad_{0.0};
  double hold_position_max_rad_{0.0};

  //: Which way, in the drive joint's own units, is towards `open_position_`.
  //: +1 or -1, resolved once the two rails are known.
  double open_direction_{1.0};

  std::unordered_set<std::string> graspable_;

  gz::sim::Entity attach_link_entity_{gz::sim::kNullEntity};
  gz::sim::Entity drive_joint_entity_{gz::sim::kNullEntity};
  gz::sim::Entity attached_{gz::sim::kNullEntity};
  gz::sim::Entity joint_entity_{gz::sim::kNullEntity};

  //: The drive joint's position at the moment it was judged stalled. Held
  //: rather than either declared rail, because a real stall can land anywhere
  //: strictly between them and a release is measured from wherever that was.
  double held_position_{0.0};

  //: The simulated time, in seconds, the drive joint was last seen moving
  //: faster than `stall_velocity_threshold_`. Unset until the first sample.
  std::optional<double> last_moving_s_;

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::GraspHold,
  gz::sim::System,
  cite_simulation::GraspHold::ISystemConfigure,
  cite_simulation::GraspHold::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::GraspHold, "cite_simulation::GraspHold")
