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

// The handoff protocol, L4's half of it (ADR-0024).
//
// L4 owns ownership; L3 owns motion. This file is ownership. It issues the
// rendezvous token, performs the two-party confirmation, and enforces the
// timeout with its defined outcome. It never sends a goal and never names a
// robot — the ADR is explicit that `Transfer` takes a pose and a token, "not a
// peer identity", so that a skill never knows which robot, if any, is on the
// other side.
//
// THE FOUR RULES, AND WHERE EACH ONE LIVES.
//
// 1. One owner, transferring atomically. Not here — `WorkpieceRegistry`. This
//    ledger calls `transfer` exactly once, from `complete`, at the moment the
//    upstream robot has physically let go. Every other path leaves the registry
//    untouched, so no failure of this protocol can produce a piece owned by two
//    stations or by none.
// 2. Both parties confirm before physical transfer begins. `offer` is the
//    upstream's confirmation — it is the owner and would not offer otherwise —
//    and `accept` is the downstream's. `may_begin_motion` is false until both
//    have happened, and that predicate is what the behaviour tree gates on.
// 3. A timeout is an outcome, not an expiry. `expire` moves a handoff to
//    TIMED_OUT and hands the caller a record saying who still owns the piece.
//    The upstream retains ownership — structurally, per rule 1 — and its own tree
//    is what reports what that means for it. The maintenance pass writes no
//    station state (ADR-0038 decision 4); this comment said it reported the
//    station blocked, and that stopped being true when `STATE_BLOCKED` was given
//    one author.
// 4. Testable in isolation. Nothing here needs a second robot, a cell, or a ROS
//    graph. A test issues a token and drives one side.
//
// WHY V1 DIED HERE, kept in view because this is the same code path. Its
// coordinator published handoff commands to a topic nothing subscribed to, every
// transaction timed out forever, and no test noticed. The defence is not care:
// it is that this file is a value type with no I/O in it, so "the message went
// nowhere" is not a state it can be in.
//
// TIME ARRIVES FROM OUTSIDE. Every entry point takes `now`. The node feeds it
// `get_clock()->now()`, which honours `use_sim_time`; a clock read inside this
// file would be wall time, and a handoff timing out in wall time while the cell
// runs on simulated time is the mixed-time system that produces plausible, wrong
// results.

#ifndef CITE_ORCHESTRATION__HANDOFF_LEDGER_HPP_
#define CITE_ORCHESTRATION__HANDOFF_LEDGER_HPP_

#include <cstdint>
#include <cstdio>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include <rclcpp/duration.hpp>
#include <rclcpp/time.hpp>

#include "cite_orchestration/workpiece_registry.hpp"

namespace cite_orchestration
{

/// How far a handoff has got.
enum class HandoffPhase : uint8_t
{
  //: The upstream owner has offered the work-piece and is waiting for the
  //: downstream station to confirm. No motion may begin.
  OFFERED,
  //: Both parties have confirmed. The physical transfer may begin, and only now.
  CONFIRMED,
  //: The upstream robot has let go and ownership has moved. Terminal.
  COMPLETED,
  //: The deadline passed. The upstream still owns the work-piece. Terminal.
  TIMED_OUT,
  //: Called off before it completed — a station whose cycle failed gives back
  //: what it offered rather than leaving a live token behind. Terminal.
  ABANDONED,
};

/// One handoff, as the line records it.
struct Handoff
{
  //: Opaque to L3 by contract: `Transfer.Goal.rendezvous_token` carries it and
  //: nothing below this layer may interpret it.
  std::string token;
  std::string workpiece_id;
  std::string from_station_id;
  std::string to_station_id;
  HandoffPhase phase{HandoffPhase::OFFERED};
  rclcpp::Time offered_at;
  //: A FAILURE deadline, never a schedule. Nothing waits until it to act;
  //: reaching it is the failure.
  rclcpp::Time deadline;
};

/// Every answer a party can get, as a value.
enum class HandoffReply : uint8_t
{
  OK,
  //: No live handoff carries that token. A token that was never issued and one
  //: that has already reached a terminal phase are deliberately the same answer
  //: to a caller: in both cases there is nothing to act on.
  UNKNOWN_TOKEN,
  //: The station calling is not the party this step belongs to. Refused rather
  //: than tolerated: a downstream station confirming its own offer would satisfy
  //: rule 2 with one party.
  WRONG_PARTY,
  //: The right party, at the wrong point — confirming a handoff that is already
  //: confirmed, or completing one nobody has confirmed.
  WRONG_PHASE,
  //: The deadline has passed. Answered rather than silently accepted, because
  //: accepting a late confirmation is how an arm ends up moving toward a
  //: rendezvous the other side has already given up on.
  EXPIRED,
};

/// The live handoffs, and the rules that move them along.
class HandoffLedger
{
public:
  /// Offer a work-piece to the downstream station.
  ///
  /// Returns the rendezvous token, or an empty string when the offer is refused.
  /// An offer is refused when the offering station does not own the work-piece —
  /// checked against the registry rather than trusted — or when that work-piece
  /// already has a live handoff. Two live handoffs on one piece is two stations
  /// preparing to receive it, which rule 1 exists to make impossible.
  std::string offer(
    const WorkpieceRegistry & registry, const std::string & workpiece_id,
    const std::string & from_station_id, const std::string & to_station_id,
    const rclcpp::Time & now, const rclcpp::Duration & timeout)
  {
    if (workpiece_id.empty() || from_station_id.empty() || to_station_id.empty()) {
      return {};
    }
    if (from_station_id == to_station_id) {
      return {};
    }
    const auto owner = registry.owner_of(workpiece_id);
    if (!owner || *owner != from_station_id) {
      return {};
    }
    if (live_for_workpiece(workpiece_id)) {
      return {};
    }

    Handoff handoff;
    handoff.token = mint_token();
    handoff.workpiece_id = workpiece_id;
    handoff.from_station_id = from_station_id;
    handoff.to_station_id = to_station_id;
    handoff.phase = HandoffPhase::OFFERED;
    handoff.offered_at = now;
    handoff.deadline = now + timeout;
    handoffs_[handoff.token] = handoff;
    return handoff.token;
  }

  /// The downstream station's confirmation. The second of the two parties.
  HandoffReply accept(
    const std::string & token, const std::string & by_station_id, const rclcpp::Time & now)
  {
    const auto entry = handoffs_.find(token);
    if (entry == handoffs_.end() || is_terminal(entry->second.phase)) {
      return HandoffReply::UNKNOWN_TOKEN;
    }
    Handoff & handoff = entry->second;
    if (handoff.to_station_id != by_station_id) {
      return HandoffReply::WRONG_PARTY;
    }
    if (handoff.phase != HandoffPhase::OFFERED) {
      return HandoffReply::WRONG_PHASE;
    }
    if (now > handoff.deadline) {
      handoff.phase = HandoffPhase::TIMED_OUT;
      return HandoffReply::EXPIRED;
    }
    handoff.phase = HandoffPhase::CONFIRMED;
    return HandoffReply::OK;
  }

  /// Whether physical transfer may begin. The predicate rule 2 names.
  ///
  /// A behaviour tree gates its motion leaf on this, so "both parties confirmed"
  /// is a thing the tree asks rather than a thing the tree assumes.
  bool may_begin_motion(const std::string & token) const
  {
    const auto handoff = find(token);
    return handoff && handoff->phase == HandoffPhase::CONFIRMED;
  }

  /// The upstream robot has let go. Ownership moves, once, here.
  ///
  /// `location_id` and `phase` say where the work-piece now physically is: on
  /// the belt between the two stations for a conveyor-mediated handoff, in the
  /// receiving gripper for a direct one. Ownership is the same either way, which
  /// is why one protocol covers both.
  HandoffReply complete(
    WorkpieceRegistry & registry, const std::string & token, const std::string & location_id,
    WorkpiecePhase phase, const rclcpp::Time & now)
  {
    const auto entry = handoffs_.find(token);
    if (entry == handoffs_.end() || is_terminal(entry->second.phase)) {
      return HandoffReply::UNKNOWN_TOKEN;
    }
    Handoff & handoff = entry->second;
    if (handoff.phase != HandoffPhase::CONFIRMED) {
      // Completing an unconfirmed handoff is exactly the rule-2 violation: the
      // upstream would be letting go of a work-piece the downstream never agreed
      // to take.
      return HandoffReply::WRONG_PHASE;
    }
    if (now > handoff.deadline) {
      handoff.phase = HandoffPhase::TIMED_OUT;
      return HandoffReply::EXPIRED;
    }
    const RegistryOutcome moved = registry.transfer(
      handoff.workpiece_id, handoff.from_station_id, handoff.to_station_id, location_id, phase);
    if (moved != RegistryOutcome::OK) {
      // The registry refused, so ownership did not move and this handoff is not
      // complete. Reported rather than recorded as done: a ledger that says
      // "completed" while the registry says otherwise is the ambiguity rule 1
      // forbids.
      return HandoffReply::WRONG_PARTY;
    }
    handoff.phase = HandoffPhase::COMPLETED;
    return HandoffReply::OK;
  }

  /// Called off by either party. The work-piece stays where it is, with whoever
  /// already owned it.
  HandoffReply abandon(const std::string & token, const std::string & by_station_id)
  {
    const auto entry = handoffs_.find(token);
    if (entry == handoffs_.end() || is_terminal(entry->second.phase)) {
      return HandoffReply::UNKNOWN_TOKEN;
    }
    Handoff & handoff = entry->second;
    if (handoff.from_station_id != by_station_id && handoff.to_station_id != by_station_id) {
      return HandoffReply::WRONG_PARTY;
    }
    handoff.phase = HandoffPhase::ABANDONED;
    return HandoffReply::OK;
  }

  /// Retire every handoff whose deadline has passed, and say which they were.
  ///
  /// Rule 3 in one call. The returned records name the station that still owns
  /// each work-piece — which is the upstream one, because nothing moved — so the
  /// caller can say exactly whose clock ran out. A caller that had to work
  /// out for itself who still owned the piece would be keeping a second copy of
  /// the answer.
  ///
  /// THE CALLER REPORTS NOTHING BLOCKED, and this comment used to say it did.
  /// `STATE_BLOCKED` has one author — the station's own tree (ADR-0038 decision
  /// 4) — so `LineMaintenance` logs the expiry and writes no state; the station
  /// observes the terminal handoff itself, at `AwaitHandoffConfirmed` or at
  /// `CompleteHandoff` depending on where in its cycle it is.
  std::vector<Handoff> expire(const rclcpp::Time & now)
  {
    std::vector<Handoff> timed_out;
    for (auto & [token, handoff] : handoffs_) {
      static_cast<void>(token);
      if (is_terminal(handoff.phase)) {
        continue;
      }
      if (now > handoff.deadline) {
        handoff.phase = HandoffPhase::TIMED_OUT;
        timed_out.push_back(handoff);
      }
    }
    return timed_out;
  }

  /// The live offer addressed to one station, if there is one.
  ///
  /// How a downstream station discovers that it has been offered something,
  /// without either side naming the other's skills or topics.
  std::optional<Handoff> offer_awaiting(const std::string & to_station_id) const
  {
    for (const auto & [token, handoff] : handoffs_) {
      static_cast<void>(token);
      if (handoff.phase == HandoffPhase::OFFERED && handoff.to_station_id == to_station_id) {
        return handoff;
      }
    }
    return std::nullopt;
  }

  /// Every handoff that has not yet reached a terminal phase.
  ///
  /// The records, not the count, and for one caller: the fault branch settles the
  /// ledger when the line stops (ADR-0038), which means calling `abandon` on each
  /// of them — and `abandon` names a party, deliberately, so the caller needs the
  /// record rather than the token. Returned by value because the caller abandons
  /// as it goes, and iterating a map while its entries change phase is a habit
  /// worth not forming here.
  ///
  /// It is NOT a way to act on somebody else's handoff. `abandon` still checks
  /// that the station named is a party to it, so what this widens is visibility
  /// and not authority.
  std::vector<Handoff> live_handoffs() const
  {
    std::vector<Handoff> open;
    for (const auto & [token, handoff] : handoffs_) {
      static_cast<void>(token);
      if (!is_terminal(handoff.phase)) {
        open.push_back(handoff);
      }
    }
    return open;
  }

  std::optional<Handoff> find(const std::string & token) const
  {
    const auto entry = handoffs_.find(token);
    if (entry == handoffs_.end()) {
      return std::nullopt;
    }
    return entry->second;
  }

  /// Drop terminal records. Called by the node so that a line running for a week
  /// does not accumulate one entry per work-piece for ever.
  std::size_t forget_terminal()
  {
    std::size_t dropped = 0;
    for (auto entry = handoffs_.begin(); entry != handoffs_.end(); ) {
      if (is_terminal(entry->second.phase)) {
        entry = handoffs_.erase(entry);
        ++dropped;
      } else {
        ++entry;
      }
    }
    return dropped;
  }

  std::size_t live() const
  {
    std::size_t count = 0;
    for (const auto & [token, handoff] : handoffs_) {
      static_cast<void>(token);
      if (!is_terminal(handoff.phase)) {
        ++count;
      }
    }
    return count;
  }

  static bool is_terminal(HandoffPhase phase)
  {
    return phase == HandoffPhase::COMPLETED || phase == HandoffPhase::TIMED_OUT ||
           phase == HandoffPhase::ABANDONED;
  }

private:
  bool live_for_workpiece(const std::string & workpiece_id) const
  {
    for (const auto & [token, handoff] : handoffs_) {
      static_cast<void>(token);
      if (handoff.workpiece_id == workpiece_id && !is_terminal(handoff.phase)) {
        return true;
      }
    }
    return false;
  }

  /// A token, unique within this ledger.
  ///
  /// It carries no asset name and no zone, which is not decoration: ADR-0024
  /// requires L3 to be unable to tell who is on the other side, and a token
  /// spelling out the peer would hand it that knowledge through the back door.
  /// A counter is enough — this ledger is the only issuer, and a token only has
  /// to be matchable.
  std::string mint_token()
  {
    char buffer[24] = {};
    snprintf(buffer, sizeof(buffer), "handoff_%06u", ++minted_);
    return std::string(buffer);
  }

  std::map<std::string, Handoff> handoffs_;
  uint32_t minted_{0};
};

/// A name for a log line. Never parsed.
inline const char * describe(HandoffReply reply)
{
  switch (reply) {
    case HandoffReply::OK:
      return "ok";
    case HandoffReply::UNKNOWN_TOKEN:
      return "no live handoff carries that token";
    case HandoffReply::WRONG_PARTY:
      return "that station is not a party to this handoff";
    case HandoffReply::WRONG_PHASE:
      return "the handoff is not at the point that step belongs to";
    case HandoffReply::EXPIRED:
      return "the handoff deadline has passed; the upstream station still owns the piece";
  }
  return "unknown reply";
}

/// A name for a log line. Never parsed.
inline const char * describe(HandoffPhase phase)
{
  switch (phase) {
    case HandoffPhase::OFFERED:
      return "offered";
    case HandoffPhase::CONFIRMED:
      return "confirmed by both parties";
    case HandoffPhase::COMPLETED:
      return "completed";
    case HandoffPhase::TIMED_OUT:
      return "timed out";
    case HandoffPhase::ABANDONED:
      return "abandoned";
  }
  return "unknown phase";
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__HANDOFF_LEDGER_HPP_
