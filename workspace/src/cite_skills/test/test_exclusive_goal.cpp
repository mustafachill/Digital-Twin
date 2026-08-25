// One arm, one goal at a time — the invariant that stops two skills sharing one
// planner, and stops a cancel addressed to one goal stopping another's motion.

#include <atomic>
#include <thread>
#include <vector>

#include <gtest/gtest.h>

#include "cite_skills/exclusive_goal.hpp"

using cite_skills::ExclusiveGoal;

TEST(ExclusiveGoal, AdmitsTheFirstGoal)
{
  ExclusiveGoal<int> gate;
  EXPECT_TRUE(gate.claim(1, "pick"));
  EXPECT_TRUE(gate.held());
  EXPECT_EQ(gate.skill(), "pick");
}

TEST(ExclusiveGoal, RefusesASecondGoalWhileOneIsInFlight)
{
  // The shipped recovery path reached this: the coordinator abandoned a goal on
  // its deadline without cancelling it, and the tree's fallback then sent a
  // MoveToHome to the same server while the first goal was still executing.
  ExclusiveGoal<int> gate;
  ASSERT_TRUE(gate.claim(1, "pick"));
  EXPECT_FALSE(gate.claim(2, "move_to"));
  // And the rejection can say what the arm is busy with.
  EXPECT_EQ(gate.skill(), "pick");
}

TEST(ExclusiveGoal, AdmitsTheNextGoalAfterTheFirstReleases)
{
  ExclusiveGoal<int> gate;
  ASSERT_TRUE(gate.claim(1, "pick"));
  gate.release();
  EXPECT_FALSE(gate.held());
  EXPECT_TRUE(gate.claim(2, "move_to"));
}

TEST(ExclusiveGoal, OwnsOnlyTheGoalItAdmitted)
{
  // What makes a cancel address its own goal: `move_group->stop()` stops
  // whatever is executing, so cancelling a Grasp must not stop an unrelated
  // Pick's trajectory.
  ExclusiveGoal<int> gate;
  ASSERT_TRUE(gate.claim(7, "pick"));
  EXPECT_TRUE(gate.owns(7));
  EXPECT_FALSE(gate.owns(8));
}

TEST(ExclusiveGoal, OwnsNothingOnceReleased)
{
  // A cancel arriving for a goal that has already finished must not stop the
  // motion of whatever started next.
  ExclusiveGoal<int> gate;
  ASSERT_TRUE(gate.claim(7, "pick"));
  gate.release();
  EXPECT_FALSE(gate.owns(7));
}

TEST(ExclusiveGoal, AdmitsExactlyOneOfManyConcurrentGoals)
{
  // Four action servers on a multi-threaded executor can call this at the same
  // instant. Exactly one of them may win.
  constexpr int kThreads = 16;
  ExclusiveGoal<int> gate;
  std::atomic<int> admitted{0};
  std::atomic<bool> go{false};
  std::vector<std::thread> threads;

  threads.reserve(kThreads);
  for (int i = 0; i < kThreads; ++i) {
    threads.emplace_back([&gate, &admitted, &go, i] {
      while (!go.load()) {
      }
      if (gate.claim(i, "pick")) {
        ++admitted;
      }
    });
  }
  go.store(true);
  for (auto & thread : threads) {
    thread.join();
  }

  EXPECT_EQ(admitted.load(), 1);
}
