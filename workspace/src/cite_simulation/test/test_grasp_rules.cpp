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

// The test ADR-0023 names and did not have: "a near-miss does not attach, not
// only that a correct grasp does".
//
// The defect these lock down was live on this branch. `FindGraspable` accepted a
// contact if EITHER side was a graspable model, and the only contact sensor in
// the tree sits on the work-piece — so the work-piece resting on the table
// satisfied the test, the contact condition contributed nothing, and every arm
// attached the box the moment it closed on empty air.

#include <string>
#include <unordered_set>

#include "gtest/gtest.h"
#include "cite_simulation/grasp_rules.hpp"

namespace
{

using cite_simulation::grasp_rules::PairSide;
using cite_simulation::grasp_rules::graspable_of_pair;

const std::unordered_set<std::string> kGraspable{"workpiece"};
const char kMine[] = "arm_1";

}  // namespace

TEST(GraspRules, a_workpiece_touching_this_gripper_is_a_grasp)
{
  EXPECT_EQ(graspable_of_pair("workpiece", "arm_1", kGraspable, kMine), PairSide::kFirst);
  EXPECT_EQ(graspable_of_pair("arm_1", "workpiece", kGraspable, kMine), PairSide::kSecond);
}

TEST(GraspRules, a_workpiece_resting_on_the_table_is_not_a_grasp)
{
  // The exact defect: this pair is reported continuously from the moment the
  // work-piece is spawned, and it names a graspable model on one side.
  EXPECT_EQ(
    graspable_of_pair("workpiece", "cell_a_scene", kGraspable, kMine), PairSide::kNeither);
}

TEST(GraspRules, another_arm_holding_the_workpiece_is_not_this_grippers_grasp)
{
  // arm_3 closing on empty air at the far end of the line used to attach the box
  // arm_1 was holding, and fling it across the cell.
  EXPECT_EQ(graspable_of_pair("workpiece", "arm_2", kGraspable, kMine), PairSide::kNeither);
  EXPECT_EQ(graspable_of_pair("arm_2", "workpiece", kGraspable, kMine), PairSide::kNeither);
}

TEST(GraspRules, touching_something_that_is_not_declared_graspable_is_not_a_grasp)
{
  EXPECT_EQ(graspable_of_pair("cell_a_scene", "arm_1", kGraspable, kMine), PairSide::kNeither);
  EXPECT_EQ(graspable_of_pair("ground_plane", "arm_1", kGraspable, kMine), PairSide::kNeither);
}

TEST(GraspRules, a_model_touching_itself_is_never_a_grasp)
{
  // Self-collision between an arm's own links is reported like any other
  // contact. If a graspable model ever collided with itself, accepting it would
  // attach the work-piece to a gripper that is nowhere near it.
  EXPECT_EQ(graspable_of_pair("arm_1", "arm_1", kGraspable, kMine), PairSide::kNeither);
  EXPECT_EQ(
    graspable_of_pair("workpiece", "workpiece", {"workpiece", "arm_1"}, kMine),
    PairSide::kNeither);
}

TEST(GraspRules, an_unnamed_entity_is_never_a_grasp)
{
  // An entity with no Name component reads as an empty string. Treating that as
  // a match would make every unnamed collision in the world a grasp candidate.
  EXPECT_EQ(graspable_of_pair("", "arm_1", kGraspable, kMine), PairSide::kNeither);
  EXPECT_EQ(graspable_of_pair("workpiece", "", kGraspable, kMine), PairSide::kNeither);
  EXPECT_EQ(graspable_of_pair("workpiece", "arm_1", kGraspable, ""), PairSide::kNeither);
}

TEST(GraspRules, nothing_is_graspable_when_nothing_is_declared)
{
  EXPECT_EQ(graspable_of_pair("workpiece", "arm_1", {}, kMine), PairSide::kNeither);
}
