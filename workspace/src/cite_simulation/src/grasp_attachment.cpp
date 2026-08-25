// Contact-triggered grasp attachment (ADR-0023).
//
// A parallel gripper holding a box by friction alone is one of the least
// reliable things a rigid-body simulator does. It depends on contact stiffness,
// friction coefficients, solver iterations and the physics timestep, and it
// fails by the object sliding out or being flung across the cell. That behaviour
// is timestep-sensitive, which collides directly with the requirement that a
// scenario be deterministic under a fixed seed — and a non-deterministic
// scenario is worse than no scenario, because it teaches people to re-run until
// green.
//
// So this plugin creates a fixed joint between the gripper and a graspable model
// when the pads are in contact AND the gripper is closing, and breaks it when the
// gripper opens.
//
// THE PROPERTY THAT MUST NOT BE ERODED: nothing above ros2_control knows this
// exists. The Grasp skill commands the gripper's controller and nothing else, in
// simulation and on hardware alike. This plugin observes the *result* of that
// command inside the simulator, exactly as the physical world would. There is no
// sim-only branch in any skill, and no topic that exists on one path and not the
// other — which is what keeps ADR-0005 intact.
//
// It also means the simulation flatters us about grasping: a grasp that would
// slip in reality will hold here. That is a real fidelity loss and it is stated
// in ADR-0023 rather than hidden. No claim about grasp reliability can rest on
// this plugin.

#include <mutex>
#include <string>
#include <unordered_set>
#include <vector>

#include <gz/plugin/Register.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/JointPosition.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>

namespace cite_simulation
{

/// Attach a graspable model to a gripper while the gripper holds it.
class GraspAttachment
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
      gzerr << "[cite_grasp] attached to something that is not a model; doing nothing\n";
      return;
    }

    // Which link the work-piece is attached to, and which joint reports whether
    // the gripper is closed. Both are supplied by the generated world rather than
    // assumed: a plugin that guessed a link name would be a second place a name
    // is made (P1), and it would break silently on a different end-effector.
    attach_link_ = sdf->Get<std::string>("attach_link", attach_link_).first;
    drive_joint_ = sdf->Get<std::string>("drive_joint", drive_joint_).first;
    closed_threshold_rad_ =
      sdf->Get<double>("closed_threshold_rad", closed_threshold_rad_).first;
    open_threshold_rad_ = sdf->Get<double>("open_threshold_rad", open_threshold_rad_).first;

    if (attach_link_.empty() || drive_joint_.empty()) {
      gzerr << "[cite_grasp] both <attach_link> and <drive_joint> are required; "
            << "without them this plugin cannot tell what is holding what\n";
      return;
    }

    // The set of models this gripper may pick up. Declared, not inferred: a
    // gripper that attached to whatever it touched would grab the table.
    for (auto element = sdf->FindElement("graspable"); element;
         element = element->GetNextElement("graspable")) {
      graspable_.insert(element->Get<std::string>());
    }
    if (graspable_.empty()) {
      gzwarn << "[cite_grasp] no <graspable> models declared; this gripper will "
             << "never attach to anything\n";
    }

    attach_link_entity_ = model_.LinkByName(ecm, attach_link_);
    drive_joint_entity_ = model_.JointByName(ecm, drive_joint_);
    if (attach_link_entity_ == gz::sim::kNullEntity ||
        drive_joint_entity_ == gz::sim::kNullEntity)
    {
      gzerr << "[cite_grasp] model '" << model_.Name(ecm) << "' has no link '"
            << attach_link_ << "' or no joint '" << drive_joint_ << "'\n";
      return;
    }

    // The joint position is what tells us the gripper is closing. Enabling the
    // component here rather than assuming it is present: without it the position
    // reads as empty every step and the gripper never appears to close.
    ecm.CreateComponent(drive_joint_entity_, gz::sim::components::JointPosition());

    configured_ = true;
    gzmsg << "[cite_grasp] watching '" << drive_joint_ << "' on model '"
          << model_.Name(ecm) << "', attaching to '" << attach_link_ << "'\n";
  }

  void PreUpdate(
    const gz::sim::UpdateInfo & info, gz::sim::EntityComponentManager & ecm) override
  {
    if (!configured_ || info.paused) {
      return;
    }

    const auto * position = ecm.Component<gz::sim::components::JointPosition>(
      drive_joint_entity_);
    if (position == nullptr || position->Data().empty()) {
      return;
    }
    const double opening = position->Data().front();

    if (attached_ == gz::sim::kNullEntity) {
      // Attach only while the gripper is CLOSING onto something. Attaching on
      // contact alone would let the arm pick things up by brushing past them.
      if (opening >= closed_threshold_rad_) {
        const auto candidate = FindGraspable(ecm);
        if (candidate != gz::sim::kNullEntity) {
          Attach(ecm, candidate);
        }
      }
      return;
    }

    // Detach on opening, with hysteresis: a single threshold would make the
    // object drop and re-attach repeatedly while the gripper sits near it.
    if (opening <= open_threshold_rad_) {
      Detach(ecm);
    }
  }

private:
  /// The nearest graspable model whose links are in contact with this gripper.
  gz::sim::Entity FindGraspable(const gz::sim::EntityComponentManager & ecm) const
  {
    gz::sim::Entity found = gz::sim::kNullEntity;

    ecm.Each<gz::sim::components::ContactSensorData>(
      [&](const gz::sim::Entity &, const gz::sim::components::ContactSensorData * contacts)
        -> bool {
        for (const auto & contact : contacts->Data().contact()) {
          for (const auto * collision : {&contact.collision1(), &contact.collision2()}) {
            const auto model = TopLevelModelName(ecm, collision->id());
            if (!model.empty() && graspable_.count(model) > 0) {
              found = TopLevelModelEntity(ecm, collision->id());
              return false;
            }
          }
        }
        return true;
      });

    return found;
  }

  static std::string TopLevelModelName(
    const gz::sim::EntityComponentManager & ecm, gz::sim::Entity entity)
  {
    const auto model = gz::sim::topLevelModel(entity, ecm);
    const auto * name = ecm.Component<gz::sim::components::Name>(model);
    return name != nullptr ? name->Data() : std::string{};
  }

  static gz::sim::Entity TopLevelModelEntity(
    const gz::sim::EntityComponentManager & ecm, gz::sim::Entity entity)
  {
    return gz::sim::topLevelModel(entity, ecm);
  }

  void Attach(gz::sim::EntityComponentManager & ecm, gz::sim::Entity target)
  {
    const auto * name = ecm.Component<gz::sim::components::Name>(target);
    ecm.CreateComponent(
      target, gz::sim::components::DetachableJoint(
                {attach_link_entity_, target, "fixed"}));
    attached_ = target;
    gzmsg << "[cite_grasp] attached '" << (name != nullptr ? name->Data() : "?")
          << "'\n";
  }

  void Detach(gz::sim::EntityComponentManager & ecm)
  {
    ecm.RemoveComponent<gz::sim::components::DetachableJoint>(attached_);
    gzmsg << "[cite_grasp] released\n";
    attached_ = gz::sim::kNullEntity;
  }

  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Entity attach_link_entity_{gz::sim::kNullEntity};
  gz::sim::Entity drive_joint_entity_{gz::sim::kNullEntity};
  gz::sim::Entity attached_{gz::sim::kNullEntity};

  std::string attach_link_;
  std::string drive_joint_;
  std::unordered_set<std::string> graspable_;

  //: The xArm gripper's drive joint opens towards zero and closes towards its
  //: upper limit, so "closed" is a LARGE value. Both thresholds come from the
  //: world so that a different end-effector needs no code change, and the gap
  //: between them is hysteresis: a single threshold makes the object drop and
  //: re-attach repeatedly while the gripper rests near it.
  double closed_threshold_rad_{0.30};
  double open_threshold_rad_{0.15};

  bool configured_{false};
};

}  // namespace cite_simulation

GZ_ADD_PLUGIN(
  cite_simulation::GraspAttachment,
  gz::sim::System,
  cite_simulation::GraspAttachment::ISystemConfigure,
  cite_simulation::GraspAttachment::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(cite_simulation::GraspAttachment, "cite_simulation::GraspAttachment")
