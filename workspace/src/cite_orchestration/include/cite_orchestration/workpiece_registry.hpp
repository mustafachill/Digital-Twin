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

// Which work-piece is where, and which station owns it.
//
// ADR-0024 rule 1: "a work-piece has exactly one owner at any instant, and
// ownership transfers atomically". This class is the one place that owner is
// recorded, which is what makes "two robots think they hold it" unrepresentable
// rather than merely unlikely. Nothing else in L4 may keep a second copy of it.
//
// ATOMICITY IS STRUCTURAL, NOT CAREFUL. `transfer` is the only operation that
// changes an owner, it checks the current owner before it writes, and it writes
// once. A handoff that fails partway therefore cannot leave a work-piece owned
// by two stations or by none: the ledger in `handoff_ledger.hpp` calls this only
// at the moment the upstream robot has physically let go, and a handoff that
// times out before then never calls it at all. That ordering is the whole reason
// the timeout has a defined outcome (rule 3) rather than an ambiguous one.
//
// Pure logic, no ROS. The line's ownership rules are exactly the kind of thing
// that must be provable without standing up a cell.

#ifndef CITE_ORCHESTRATION__WORKPIECE_REGISTRY_HPP_
#define CITE_ORCHESTRATION__WORKPIECE_REGISTRY_HPP_

#include <cstdint>
#include <cstdio>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace cite_orchestration
{

/// What a work-piece is doing, in the line's terms rather than the robot's.
enum class WorkpiecePhase : uint8_t
{
  //: Resting at a station, not held by anything.
  AT_STATION,
  //: In an arm's gripper.
  HELD,
  //: On a conveyor between two stations. Owned by the DOWNSTREAM station: the
  //: upstream one let go of it, and something has to be accountable for it.
  IN_TRANSIT,
};

/// One work-piece as the line understands it.
struct WorkpieceRecord
{
  std::string id;
  //: Never empty while the work-piece is in the line. That is the invariant.
  std::string owner_station_id;
  //: Where it physically is: a station id, or the asset carrying it. Distinct
  //: from the owner, because a piece on a conveyor is owned by the station that
  //: will take it and located on the belt that is moving it.
  std::string location_id;
  WorkpiecePhase phase{WorkpiecePhase::AT_STATION};
};

/// Every outcome the caller can act on, as a value rather than a bool.
///
/// A bool would collapse "there is no such work-piece" and "you are not its
/// owner" into one answer, and those call for opposite responses: the first is a
/// tracking failure, the second is a protocol violation.
enum class RegistryOutcome : uint8_t
{
  OK,
  UNKNOWN_WORKPIECE,
  ALREADY_PRESENT,
  //: The caller named an owner that is not the recorded one. Refused rather
  //: than overwritten — an overwrite here is how a work-piece gains a second
  //: owner.
  NOT_THE_OWNER,
  //: A station was named that this call requires to be different from another.
  SAME_STATION,
};

/// The line's record of every work-piece it is accountable for.
class WorkpieceRegistry
{
public:
  /// Admit a work-piece entering the line.
  ///
  /// The first station to observe a piece is the one that becomes accountable
  /// for it, which is why admission takes an owner rather than defaulting to
  /// none.
  RegistryOutcome admit(
    const std::string & id, const std::string & owner_station_id,
    const std::string & location_id)
  {
    if (id.empty() || owner_station_id.empty()) {
      return RegistryOutcome::UNKNOWN_WORKPIECE;
    }
    if (records_.count(id) != 0) {
      return RegistryOutcome::ALREADY_PRESENT;
    }
    records_[id] = WorkpieceRecord{id, owner_station_id, location_id, WorkpiecePhase::AT_STATION};
    ++admitted_;
    return RegistryOutcome::OK;
  }

  /// Move ownership from one station to another, atomically.
  ///
  /// The only operation in the system that changes an owner. `from` is passed in
  /// and checked rather than inferred, so a caller that has lost track of who
  /// owns the piece is told so instead of quietly becoming right.
  RegistryOutcome transfer(
    const std::string & id, const std::string & from_station_id,
    const std::string & to_station_id, const std::string & location_id,
    WorkpiecePhase phase)
  {
    const auto entry = records_.find(id);
    if (entry == records_.end()) {
      return RegistryOutcome::UNKNOWN_WORKPIECE;
    }
    if (entry->second.owner_station_id != from_station_id) {
      return RegistryOutcome::NOT_THE_OWNER;
    }
    if (from_station_id == to_station_id) {
      return RegistryOutcome::SAME_STATION;
    }
    if (to_station_id.empty()) {
      return RegistryOutcome::NOT_THE_OWNER;
    }
    // One write. There is no window in which the piece is owned by both or by
    // neither, because there is no second statement to fail between.
    entry->second.owner_station_id = to_station_id;
    entry->second.location_id = location_id;
    entry->second.phase = phase;
    return RegistryOutcome::OK;
  }

  /// Record that the owner has picked the piece up, put it down, or moved it.
  /// Ownership is untouched: only `transfer` changes that.
  RegistryOutcome relocate(
    const std::string & id, const std::string & owner_station_id,
    const std::string & location_id, WorkpiecePhase phase)
  {
    const auto entry = records_.find(id);
    if (entry == records_.end()) {
      return RegistryOutcome::UNKNOWN_WORKPIECE;
    }
    if (entry->second.owner_station_id != owner_station_id) {
      return RegistryOutcome::NOT_THE_OWNER;
    }
    entry->second.location_id = location_id;
    entry->second.phase = phase;
    return RegistryOutcome::OK;
  }

  /// A work-piece has left the line at a sink. It stops being tracked and starts
  /// being a number — `LineState.workpieces_completed`.
  RegistryOutcome retire(const std::string & id, const std::string & owner_station_id)
  {
    const auto entry = records_.find(id);
    if (entry == records_.end()) {
      return RegistryOutcome::UNKNOWN_WORKPIECE;
    }
    if (entry->second.owner_station_id != owner_station_id) {
      return RegistryOutcome::NOT_THE_OWNER;
    }
    records_.erase(entry);
    ++completed_;
    return RegistryOutcome::OK;
  }

  std::optional<WorkpieceRecord> find(const std::string & id) const
  {
    const auto entry = records_.find(id);
    if (entry == records_.end()) {
      return std::nullopt;
    }
    return entry->second;
  }

  std::optional<std::string> owner_of(const std::string & id) const
  {
    const auto record = find(id);
    return record ? std::optional<std::string>(record->owner_station_id) : std::nullopt;
  }

  /// Every work-piece a station is accountable for, in id order so that a caller
  /// iterating them behaves the same on every run.
  std::vector<std::string> owned_by(const std::string & station_id) const
  {
    std::vector<std::string> owned;
    for (const auto & [id, record] : records_) {
      if (record.owner_station_id == station_id) {
        owned.push_back(id);
      }
    }
    return owned;
  }

  /// What `StationState.buffer_occupancy` reports.
  std::size_t occupancy(const std::string & station_id) const
  {
    return owned_by(station_id).size();
  }

  std::size_t in_line() const {return records_.size();}
  std::size_t completed() const {return completed_;}
  std::size_t admitted() const {return admitted_;}

  /// An identity for a work-piece nothing else has named.
  ///
  /// `DetectionEvent.workpiece_id` is documented as "empty when the sensor cannot
  /// identify what it saw", and a break beam never can. The line still has to be
  /// able to say which piece it is talking about, so it mints one — and this is
  /// the ONLY identifier L4 invents. It is not an asset name: no asset name is
  /// ever written by hand twice (CLAUDE.md §8), and this names a thing the
  /// facility model does not describe, because the model describes the cell and
  /// not the parts flowing through it.
  ///
  /// Unique within one coordinator's lifetime, which is the scope over which the
  /// line reasons about a piece. A piece that outlives a coordinator restart is
  /// re-admitted under a new identity, and that is stated rather than papered
  /// over: reconciling identities across a restart needs somewhere durable to
  /// reconcile against, which is L6's business and does not exist yet.
  std::string mint_id()
  {
    char buffer[24] = {};
    snprintf(buffer, sizeof(buffer), "wp_%06u", ++minted_);
    return std::string(buffer);
  }

private:
  std::map<std::string, WorkpieceRecord> records_;
  std::size_t completed_{0};
  std::size_t admitted_{0};
  uint32_t minted_{0};
};

/// A name for a log line. Never parsed.
inline const char * describe(RegistryOutcome outcome)
{
  switch (outcome) {
    case RegistryOutcome::OK:
      return "ok";
    case RegistryOutcome::UNKNOWN_WORKPIECE:
      return "the line is not tracking that work-piece";
    case RegistryOutcome::ALREADY_PRESENT:
      return "that work-piece is already in the line";
    case RegistryOutcome::NOT_THE_OWNER:
      return "that station does not own the work-piece";
    case RegistryOutcome::SAME_STATION:
      return "a work-piece cannot be handed to the station that already owns it";
  }
  return "unknown outcome";
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__WORKPIECE_REGISTRY_HPP_
