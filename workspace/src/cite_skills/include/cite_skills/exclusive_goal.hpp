// One arm, one goal at a time.
//
// Four action servers share one `MoveGroupInterface`, one gripper and one
// physical arm. `MoveGroupInterface` is not thread-safe and its target, start
// state and scaling factors are per-object, so two goals in flight means one
// goal can plan to the target the other just installed — and the arm executes
// it. Cancellation has the same shape: `move_group->stop()` stops whatever is
// executing, so a cancel that does not check whose goal it is stops somebody
// else's trajectory.
//
// This is the gate. It is kept free of ROS types so that the exclusion rule can
// be tested for what it is — a concurrency invariant — without an action server,
// a planner or a robot.

#ifndef CITE_SKILLS__EXCLUSIVE_GOAL_HPP_
#define CITE_SKILLS__EXCLUSIVE_GOAL_HPP_

#include <mutex>
#include <string>

namespace cite_skills
{

/// Admits one goal at a time and remembers which one it admitted.
template <typename Id>
class ExclusiveGoal
{
public:
  /// Take the arm for `id`. False means another goal already holds it, and the
  /// caller must reject rather than queue: a queued motion goal is a motion
  /// nobody is waiting for any more.
  bool claim(const Id & id, const std::string & skill)
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    if (held_) {
      return false;
    }
    held_ = true;
    id_ = id;
    skill_ = skill;
    return true;
  }

  /// Whether `id` is the goal currently holding the arm. This is what makes a
  /// cancel address its own goal rather than whatever happens to be moving.
  bool owns(const Id & id) const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return held_ && id_ == id;
  }

  bool held() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return held_;
  }

  /// The skill name of the holder, for a rejection message that says what the
  /// arm is busy with.
  std::string skill() const
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    return held_ ? skill_ : std::string{};
  }

  void release()
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    held_ = false;
    skill_.clear();
  }

private:
  mutable std::mutex mutex_;
  bool held_{false};
  Id id_{};
  std::string skill_;
};

}  // namespace cite_skills

#endif  // CITE_SKILLS__EXCLUSIVE_GOAL_HPP_
