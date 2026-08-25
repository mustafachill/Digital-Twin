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

#ifndef CITE_SIMULATION__GRASP_RULES_HPP_
#define CITE_SIMULATION__GRASP_RULES_HPP_

#include <string>
#include <unordered_set>

namespace cite_simulation
{
namespace grasp_rules
{

/// Which half of a contact pair — if either — is a work-piece being grasped.
enum class PairSide
{
  kNeither,
  kFirst,
  kSecond
};

/// Decide whether one contact pair is a grasp candidate for this gripper.
///
/// A contact is a PAIR, and both halves carry meaning. The defect this rule
/// replaces tested only whether *either* side belonged to a declared graspable
/// model, which every contact the work-piece has satisfies — including simply
/// resting on the table it was spawned on. The contact test therefore
/// contributed nothing at all, the attach condition reduced to "this gripper's
/// drive joint is past its closed threshold", and an arm closing on empty air
/// at the far end of the line attached a box it was nowhere near.
///
/// The pair must now be (a declared graspable model, THIS gripper's own model):
/// something this gripper is touching, not something anything is touching.
///
/// Both halves are required to be non-empty and distinct. An unnamed entity
/// tells us nothing, and a self-contact — a model touching itself — is never a
/// grasp.
inline PairSide graspable_of_pair(
  const std::string & first_model,
  const std::string & second_model,
  const std::unordered_set<std::string> & graspable,
  const std::string & own_model)
{
  if (own_model.empty() || first_model.empty() || second_model.empty()) {
    return PairSide::kNeither;
  }
  if (first_model == second_model) {
    return PairSide::kNeither;
  }
  if (second_model == own_model && graspable.count(first_model) > 0) {
    return PairSide::kFirst;
  }
  if (first_model == own_model && graspable.count(second_model) > 0) {
    return PairSide::kSecond;
  }
  return PairSide::kNeither;
}

}  // namespace grasp_rules
}  // namespace cite_simulation

#endif  // CITE_SIMULATION__GRASP_RULES_HPP_
