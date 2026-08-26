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

// Who may use a shared thing, and in what order.
//
// Two arms wanting the same conveyor slot is the case this exists for. L4 holds
// the allocation; L2's limits and collision checking are what prevent a
// collision. That division is written down because confusing the two is how a
// coordination bug becomes an injury: **nothing here is a safety mechanism**. It
// prevents deadlock and thrash, which is a throughput property, and it would be
// a defect to rely on it for anything else.
//
// WHAT THE RESOURCES ARE IS NOT DECIDED HERE. This class knows about names and
// capacities; `line_plan.hpp` derives both from the L0 topology. A conveyor, a
// station's reach frame and a buffer between two stations are all the same thing
// to this file, which is the property that lets a fourth arm arrive without
// touching it (P5, P9).
//
// FAIRNESS IS FIFO, ON PURPOSE. A "try again next tick" arbiter with no queue
// lets one station win repeatedly while another never does — that is the thrash
// L4 names, and it is invisible in a two-station test. Requests join a queue and
// are granted in arrival order, so a waiting claimant is guaranteed to be served
// once enough releases happen.
//
// DEADLOCK IS PREVENTED BY ORDER, NOT BY TIMEOUT. A station needs more than one
// resource at once — its reach frame and the buffer it is about to fill — and
// two stations acquiring an overlapping pair in opposite orders is the textbook
// circular wait. `request_all` sorts the names before acquiring them, so no two
// claimants can ever hold the pieces of a cycle. A timeout would only ever
// *notice* the deadlock afterwards, and a line that recovers from deadlock by
// timing out is a line that spends its time deadlocked.

#ifndef CITE_ORCHESTRATION__RESOURCE_ARBITER_HPP_
#define CITE_ORCHESTRATION__RESOURCE_ARBITER_HPP_

#include <algorithm>
#include <cstdint>
#include <deque>
#include <map>
#include <string>
#include <vector>

namespace cite_orchestration
{

/// The answer to a request, as a value the caller branches on.
enum class Grant : uint8_t
{
  //: The claimant now holds it. Requesting again while holding returns this too,
  //: so a behaviour-tree leaf can re-ask on every tick without special-casing
  //: its own success.
  GRANTED,
  //: The claimant is in the queue and will be granted in arrival order. A leaf
  //: that sees this returns RUNNING.
  QUEUED,
  //: Nothing declared a resource by that name. Refused rather than created on
  //: demand: a typo that silently created a private resource would grant every
  //: request and arbitrate nothing.
  UNDECLARED,
};

/// Grants exclusive or counted access to named resources.
class ResourceArbiter
{
public:
  /// Declare a resource and how many claimants it admits at once.
  ///
  /// Idempotent in the name, not in the capacity: re-declaring with a different
  /// capacity replaces it, because the topology is the authority on capacity and
  /// a re-published topology has to be able to change it.
  void declare_resource(const std::string & name, std::size_t capacity)
  {
    resources_[name].capacity = capacity;
  }

  bool declared(const std::string & name) const {return resources_.count(name) != 0;}

  /// Ask for one resource.
  Grant request(const std::string & name, const std::string & claimant)
  {
    const auto entry = resources_.find(name);
    if (entry == resources_.end()) {
      return Grant::UNDECLARED;
    }
    Resource & resource = entry->second;

    if (is_holder(resource, claimant)) {
      return Grant::GRANTED;
    }
    if (!is_waiting(resource, claimant)) {
      resource.waiting.push_back(claimant);
    }
    promote(resource);
    return is_holder(resource, claimant) ? Grant::GRANTED : Grant::QUEUED;
  }

  /// Ask for several resources at once, in a canonical order.
  ///
  /// GRANTED only when every one of them is held. Sorting is what prevents the
  /// circular wait: two claimants asking for {A, B} and {B, A} would otherwise
  /// each hold one and wait for the other forever, and no amount of retrying
  /// breaks that — retrying is what a deadlock survives.
  ///
  /// A claimant that ends up holding some but not all keeps them and stays
  /// queued for the rest. That is hold-and-wait, which is safe here precisely
  /// because the acquisition order is total: a cycle needs two claimants
  /// disagreeing about order, and sorted names give them no way to disagree.
  Grant request_all(std::vector<std::string> names, const std::string & claimant)
  {
    std::sort(names.begin(), names.end());
    names.erase(std::unique(names.begin(), names.end()), names.end());

    Grant worst = Grant::GRANTED;
    for (const auto & name : names) {
      const Grant answer = request(name, claimant);
      if (answer == Grant::UNDECLARED) {
        return Grant::UNDECLARED;
      }
      if (answer == Grant::QUEUED) {
        worst = Grant::QUEUED;
      }
    }
    return worst;
  }

  /// Give a resource up, whether it was held or only queued for.
  ///
  /// Safe to call for something never requested, because that is what a
  /// behaviour tree's recovery branch does: it releases everything the station
  /// might have taken, without knowing how far the failed attempt got.
  void release(const std::string & name, const std::string & claimant)
  {
    const auto entry = resources_.find(name);
    if (entry == resources_.end()) {
      return;
    }
    Resource & resource = entry->second;
    resource.holders.erase(
      std::remove(resource.holders.begin(), resource.holders.end(), claimant),
      resource.holders.end());
    resource.waiting.erase(
      std::remove(resource.waiting.begin(), resource.waiting.end(), claimant),
      resource.waiting.end());
    promote(resource);
  }

  /// Give up everything one claimant holds or waits for.
  void release_all(const std::string & claimant)
  {
    for (auto & [name, resource] : resources_) {
      static_cast<void>(name);
      resource.holders.erase(
        std::remove(resource.holders.begin(), resource.holders.end(), claimant),
        resource.holders.end());
      resource.waiting.erase(
        std::remove(resource.waiting.begin(), resource.waiting.end(), claimant),
        resource.waiting.end());
      promote(resource);
    }
  }

  bool holds(const std::string & name, const std::string & claimant) const
  {
    const auto entry = resources_.find(name);
    return entry != resources_.end() && is_holder(entry->second, claimant);
  }

  std::size_t capacity(const std::string & name) const
  {
    const auto entry = resources_.find(name);
    return entry == resources_.end() ? 0 : entry->second.capacity;
  }

  std::size_t occupancy(const std::string & name) const
  {
    const auto entry = resources_.find(name);
    return entry == resources_.end() ? 0 : entry->second.holders.size();
  }

  std::vector<std::string> holders(const std::string & name) const
  {
    const auto entry = resources_.find(name);
    return entry == resources_.end() ? std::vector<std::string>{} : entry->second.holders;
  }

  /// Who is waiting, in the order they will be served. Exposed so that a line
  /// state can say why a station is blocked rather than only that it is.
  std::vector<std::string> waiting(const std::string & name) const
  {
    const auto entry = resources_.find(name);
    if (entry == resources_.end()) {
      return {};
    }
    return {entry->second.waiting.begin(), entry->second.waiting.end()};
  }

private:
  struct Resource
  {
    std::size_t capacity{0};
    std::vector<std::string> holders;
    std::deque<std::string> waiting;
  };

  static bool is_holder(const Resource & resource, const std::string & claimant)
  {
    return std::find(resource.holders.begin(), resource.holders.end(), claimant) !=
           resource.holders.end();
  }

  static bool is_waiting(const Resource & resource, const std::string & claimant)
  {
    return std::find(resource.waiting.begin(), resource.waiting.end(), claimant) !=
           resource.waiting.end();
  }

  /// Grant to the front of the queue while there is room. Strictly in order, so
  /// a claimant behind a large request is never skipped over by a smaller one
  /// that happens to fit — being skippable is being starvable.
  static void promote(Resource & resource)
  {
    while (!resource.waiting.empty() && resource.holders.size() < resource.capacity) {
      resource.holders.push_back(resource.waiting.front());
      resource.waiting.pop_front();
    }
  }

  std::map<std::string, Resource> resources_;
};

/// A name for a log line. Never parsed.
inline const char * describe(Grant grant)
{
  switch (grant) {
    case Grant::GRANTED:
      return "granted";
    case Grant::QUEUED:
      return "queued";
    case Grant::UNDECLARED:
      return "no such resource was declared";
  }
  return "unknown grant";
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__RESOURCE_ARBITER_HPP_
