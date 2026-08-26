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

// The L0 topology, turned into what the line needs to run — and nothing else.
//
// This file is the reason `line_orchestrator.cpp` contains no station name, no
// station count and no ordering. It reads `LineTopology`, works out the order
// work flows in, and lists the shared things that need arbitrating. Adding a
// fourth arm changes the model; it does not change a line of code here or above.
//
// THE ORDER IS DERIVED, NOT DECLARED. Stations come out in flow order from a
// topological sort of the edges. The topology's own array order is not the flow
// order — in `cell_a_flow.yaml` the sink is listed first — and a coordinator that
// trusted the array order would run the line backwards while looking correct.
//
// WHAT IS REFUSED, AND WHY REFUSING IS THE POINT. A topology this code cannot
// run correctly produces a refusal with a reason, at plan time, before anything
// moves. The alternative is a coordinator that starts, looks healthy and does
// something subtly wrong — which is the failure mode L4 lists first, "publishing
// to a topic nobody consumes: silent no-op". A refusal is loud and is attached to
// the station that caused it.

#ifndef CITE_ORCHESTRATION__LINE_PLAN_HPP_
#define CITE_ORCHESTRATION__LINE_PLAN_HPP_

#include <algorithm>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

#include <cite_interfaces/msg/detection_event.hpp>
#include <cite_interfaces/msg/line_topology.hpp>
#include <cite_interfaces/msg/station_edge.hpp>
#include <cite_interfaces/msg/station_topology.hpp>

namespace cite_orchestration
{

/// One station, as the line needs to run it.
///
/// Every field is copied from the topology or derived from the edges. Nothing is
/// invented, and nothing is a default that a missing model value falls back to:
/// a station the model under-describes is refused rather than completed with
/// guesses.
struct StationPlan
{
  std::string id;
  std::string actor_asset_id;
  std::string pick_frame;
  std::string place_frame;

  //: Empty when this station has no sensor of its own and is sequenced by the
  //: station upstream instead. `StationTopology` says so in as many words.
  std::string trigger_topic;
  //: The `DetectionEvent.STATE_*` value this station fires on — NOT the
  //: `StationTopology.TRIGGER_ON_*` value it was declared with. The two happen
  //: to carry the same numbers today, and translating them anyway is the point:
  //: a coincidence between two independently versioned messages is not a
  //: contract, and the day one of them grows a third constant the coincidence
  //: ends silently, with a station waiting for an edge that never comes.
  uint8_t trigger_detection_state{0};

  std::string upstream_id;
  std::string downstream_id;
  //: How many work-pieces this station may be accountable for at once, from the
  //: model. It is what a station checks before confirming a handoff: confirming
  //: is a promise about room.
  uint32_t capacity{1};
  //: The asset that carries a work-piece away from this station — a conveyor id,
  //: or empty when nothing carries it. It is where the piece physically IS
  //: between the two stations, which is a different question from who owns it.
  std::string outbound_via_asset_id;
  //: True when the downstream station is a sink — the end of the line, with no
  //: actor to confirm a handoff. See `line_orchestrator.cpp` for who confirms
  //: on its behalf and why that is not a bypass of the two-party rule.
  bool downstream_is_sink{false};
  //: True when the upstream station is a source — work enters the line here, so
  //: nothing hands this station anything and it admits what it observes.
  bool upstream_is_source{false};

  //: The arbitration keys for the buffers either side of this station. Internal
  //: to L4 and never published: an arbitration key is not an interface name, and
  //: a consumer that needed one would be reaching into L4's bookkeeping.
  std::string inbound_buffer;
  std::string outbound_buffer;
};

/// A sink: where work-pieces leave the line.
///
/// It has no actor and so no subtree, but the line still has to reason about it —
/// something has to confirm a handoff into it and something has to count what
/// arrives. See `line_orchestrator.cpp` for who does, and why that is not a
/// bypass of the two-party rule.
struct SinkPlan
{
  std::string id;
  uint32_t capacity{0};
  std::string inbound_buffer;
};

/// A shared thing and how many claimants it admits.
struct ResourceDeclaration
{
  std::string name;
  std::size_t capacity{0};
};

/// The whole line, ready to instantiate.
struct LinePlan
{
  std::string zone;
  std::string flow_id;
  //: Transfer stations only, in flow order. Sources and sinks have no actor and
  //: therefore no subtree — they are ends of edges, not things that act.
  std::vector<StationPlan> stations;
  //: Where work leaves. Not stations that act; ends of edges that count.
  std::vector<SinkPlan> sinks;
  std::vector<ResourceDeclaration> resources;
  //: One line per thing this code will not run, naming the station or edge. A
  //: plan with any refusal is not run at all: a line missing a station in the
  //: middle is not a shorter line, it is a line that drops work-pieces.
  std::vector<std::string> refusals;

  bool usable() const {return refusals.empty() && !stations.empty();}
};

/// The arbitration key for one edge. Not a ROS name and never published.
inline std::string buffer_key(const std::string & from_id, const std::string & to_id)
{
  return from_id + "->" + to_id;
}

namespace detail
{

/// Kahn's algorithm, with the queue kept sorted so the answer does not depend on
/// map iteration order or on how the topology happened to be serialised.
inline bool flow_order(
  const std::vector<std::string> & ids,
  const std::map<std::string, std::vector<std::string>> & downstream,
  std::vector<std::string> & ordered)
{
  std::map<std::string, std::size_t> incoming;
  for (const auto & id : ids) {
    incoming[id] = 0;
  }
  for (const auto & [from, to_ids] : downstream) {
    static_cast<void>(from);
    for (const auto & to : to_ids) {
      if (incoming.count(to) != 0) {
        ++incoming[to];
      }
    }
  }

  std::set<std::string> ready;
  for (const auto & [id, count] : incoming) {
    if (count == 0) {
      ready.insert(id);
    }
  }

  ordered.clear();
  while (!ready.empty()) {
    const std::string id = *ready.begin();
    ready.erase(ready.begin());
    ordered.push_back(id);
    const auto entry = downstream.find(id);
    if (entry == downstream.end()) {
      continue;
    }
    for (const auto & to : entry->second) {
      const auto counted = incoming.find(to);
      if (counted == incoming.end()) {
        continue;
      }
      if (--counted->second == 0) {
        ready.insert(to);
      }
    }
  }
  return ordered.size() == ids.size();
}

}  // namespace detail

/// Turn a published topology into a plan, or into the reasons it cannot be one.
inline LinePlan plan_line(const cite_interfaces::msg::LineTopology & topology)
{
  using cite_interfaces::msg::DetectionEvent;
  using cite_interfaces::msg::StationEdge;
  using cite_interfaces::msg::StationTopology;

  LinePlan plan;
  plan.zone = topology.zone;
  plan.flow_id = topology.flow_id;

  std::map<std::string, StationTopology> by_id;
  std::vector<std::string> ids;
  for (const auto & station : topology.stations) {
    if (station.id.empty()) {
      plan.refusals.push_back("a station in the topology has an empty id");
      continue;
    }
    if (by_id.count(station.id) != 0) {
      plan.refusals.push_back("station '" + station.id + "' appears twice in the topology");
      continue;
    }
    by_id[station.id] = station;
    ids.push_back(station.id);
  }
  if (ids.empty()) {
    plan.refusals.push_back("the topology declares no stations");
    return plan;
  }

  // Edges are the authority on the flow. `upstream_ids` and `downstream_ids` on
  // a station say the same thing, and a value must never exist in two places —
  // so they are checked against the edges rather than used alongside them.
  std::map<std::string, std::vector<std::string>> downstream;
  std::map<std::string, std::vector<std::string>> upstream;
  std::map<std::string, StationEdge> edge_by_key;
  for (const auto & edge : topology.edges) {
    if (by_id.count(edge.from_station_id) == 0 || by_id.count(edge.to_station_id) == 0) {
      plan.refusals.push_back(
        "edge '" + buffer_key(edge.from_station_id, edge.to_station_id) +
        "' names a station the topology does not declare");
      continue;
    }
    downstream[edge.from_station_id].push_back(edge.to_station_id);
    upstream[edge.to_station_id].push_back(edge.from_station_id);
    edge_by_key[buffer_key(edge.from_station_id, edge.to_station_id)] = edge;
  }

  std::vector<std::string> ordered;
  if (!detail::flow_order(ids, downstream, ordered)) {
    plan.refusals.push_back(
      "the flow contains a cycle, so there is no order to run the stations in");
    return plan;
  }

  for (const auto & id : ordered) {
    const StationTopology & station = by_id.at(id);

    const bool is_end_of_the_line = station.type == StationTopology::TYPE_SOURCE ||
      station.type == StationTopology::TYPE_SINK;
    if (is_end_of_the_line) {
      // Ends of edges, not actors. A source or sink with an actor is a
      // contradiction the model should not be able to express, and saying so
      // here is cheaper than discovering it as an unexplained idle arm.
      if (!station.actor_asset_id.empty()) {
        plan.refusals.push_back(
          "station '" + id + "' is a source or a sink but names an actor; neither acts");
      }
      if (station.type == StationTopology::TYPE_SINK) {
        SinkPlan sink;
        sink.id = id;
        sink.capacity = station.capacity;
        const auto & feeding = upstream[id];
        if (feeding.size() == 1) {
          sink.inbound_buffer = buffer_key(feeding.front(), id);
        }
        plan.sinks.push_back(sink);
      }
      continue;
    }
    if (station.type != StationTopology::TYPE_TRANSFER) {
      plan.refusals.push_back(
        "station '" + id + "' has a type this coordinator does not know how to run");
      continue;
    }

    StationPlan entry;
    entry.id = id;
    entry.actor_asset_id = station.actor_asset_id;
    entry.pick_frame = station.pick_frame;
    entry.place_frame = station.place_frame;
    entry.capacity = station.capacity == 0 ? 1 : station.capacity;
    entry.trigger_topic = station.trigger_topic;
    if (!entry.trigger_topic.empty()) {
      switch (station.trigger_state) {
        case StationTopology::TRIGGER_ON_CLEAR:
          entry.trigger_detection_state = DetectionEvent::STATE_CLEAR;
          break;
        case StationTopology::TRIGGER_ON_BLOCKED:
          entry.trigger_detection_state = DetectionEvent::STATE_BLOCKED;
          break;
        default:
          plan.refusals.push_back(
            "transfer station '" + id +
            "' triggers on a detection state this coordinator cannot map onto a "
            "DetectionEvent, so it would wait for an edge that never arrives");
          break;
      }
    }

    if (entry.actor_asset_id.empty()) {
      plan.refusals.push_back("transfer station '" + id + "' names no actor to serve it");
    }
    if (entry.pick_frame.empty() || entry.place_frame.empty()) {
      plan.refusals.push_back(
        "transfer station '" + id + "' does not declare both a pick frame and a place frame");
    }

    const auto & in = upstream[id];
    const auto & out = downstream[id];
    if (in.size() != 1 || out.size() != 1) {
      // Merging and splitting a flow needs a routing policy — which piece goes
      // which way — and there is none. Refused rather than resolved by taking
      // the first edge, which would silently send every work-piece down one
      // branch of a line the model says has two.
      plan.refusals.push_back(
        "transfer station '" + id + "' has " + std::to_string(in.size()) + " upstream and " +
        std::to_string(out.size()) +
        " downstream stations; this coordinator runs a serial flow and has no policy for "
        "merging or splitting one");
      continue;
    }
    entry.upstream_id = in.front();
    entry.downstream_id = out.front();
    entry.upstream_is_source = by_id.at(entry.upstream_id).type == StationTopology::TYPE_SOURCE;
    entry.downstream_is_sink = by_id.at(entry.downstream_id).type == StationTopology::TYPE_SINK;
    entry.inbound_buffer = buffer_key(entry.upstream_id, id);
    entry.outbound_buffer = buffer_key(id, entry.downstream_id);

    // ---------------------------------------------------------------------
    // THE ORIENTATION GATE. Read `docs/measurements/2026-08-25-grasp-plane-offset/`
    // before changing this.
    //
    // A grasp holds a position, not an orientation: after the grasp-plane
    // correction the work-piece still rotates between the jaws by up to 18.7°,
    // and that residual is a recorded open divergence in ADR-0029. So after a
    // Pick, the line does not know the part's yaw about the tool axis.
    //
    // A CONVEYOR-MEDIATED handoff IS PERMITTED AND THE REASON RECORDED HERE FOR
    // PERMITTING IT DOES NOT HOLD. Escalated, not resolved: the behaviour below
    // is unchanged, and what follows is what is actually known.
    //
    // What this said was: "the downstream station re-observes it with `Detect`,
    // whose `Detection.pose` is a full pose. The uncertainty is measured away
    // rather than assumed away." `Detect` reports no pose. This zone detects with
    // break beams, a through-beam reports occupancy and knows nothing about
    // position or yaw, and `Detection.pose` is now explicitly unobserved
    // (`cite_skills/observation.hpp`). Nothing re-observes the part between the
    // two grippers.
    //
    // It was never true. Before that change `Detection.pose` carried the beam
    // housing's static transform, whose rotation is a constant rpy (0,0,0) — so
    // the 18.7° residual was being "measured away" by a hard-coded identity,
    // which is the assumption this gate exists to refuse, wearing the costume of
    // a measurement.
    //
    // NOR DOES THE BELT RE-SEAT IT, which is the obvious physical replacement and
    // was checked rather than assumed. `belt_1200x400` declares one box body and
    // no rail, fence or funnel, and `cite_simulation/src/conveyor.cpp` carries a
    // part by writing `LinearVelocityCmd` — a pure translation that cannot rotate
    // what it moves. A part released onto the belt at some yaw arrives at the
    // outfeed at that same yaw.
    //
    // So the conveyor path faces the geometry the direct path is refused for: the
    // receiving jaws close on a part whose yaw is unknown to ±18.7°. The
    // difference between the two paths is who is holding the part at the time,
    // which is not the difference the refusal turns on.
    //
    // WHY THIS IS NOT SILENTLY TIGHTENED INTO A REFUSAL. Refusing conveyor edges
    // would refuse every edge in today's model and stop the line, and the
    // permission traces to ADR-0031's and ADR-0024's reasoning. Correcting a
    // locked decision is not a fixer's call, so this is reported for a human
    // (CLAUDE.md §11). What would settle it is a measurement that does not exist
    // yet: the yaw a part actually carries at a downstream outfeed, against the
    // width the jaws are commanded to.
    //
    // The ownership protocol in `handoff_ledger.hpp` never needed an orientation
    // in the first place, and that half is unaffected.
    //
    // A DIRECT arm-to-arm handoff does care, and cannot be built today. The
    // receiver picks at the rendezvous pose while the giver is still holding the
    // part, so nothing re-observes it: the receiving jaws close on a part whose
    // yaw is unknown to ±18.7°. Symmetry does not rescue it — the cell's
    // reference work-piece is a 50 mm cube, whose symmetry about the approach
    // axis has a period of 90°, and 18.7° is not a multiple of 90°. Across a
    // square section rotated that far the part measures 50·(cos+sin) = 63.4 mm,
    // wider than the 45 mm the jaws are commanded to, so the pads would meet the
    // part on a corner and cam it out rather than grip it.
    //
    // So it is refused, here, at plan time, with the reason attached — rather
    // than attempted and dropped on the floor, and rather than left as an
    // unstated assumption for someone to find. Today's L0 topology contains no
    // such edge (every transfer-to-transfer edge names a conveyor), so nothing
    // is lost by refusing; the day one appears, this is what says why it cannot
    // run yet. The `TransferTo` leaf that executes ADR-0024's motion half is
    // built and tested against the contract, so what stands between here and a
    // direct handoff is orientation certainty and not code.
    // ---------------------------------------------------------------------
    const auto outbound = edge_by_key.find(entry.outbound_buffer);
    if (outbound != edge_by_key.end()) {
      entry.outbound_via_asset_id = outbound->second.via_asset_id;
      const bool receiver_is_a_robot = !entry.downstream_is_sink &&
        !by_id.at(entry.downstream_id).actor_asset_id.empty();
      if (receiver_is_a_robot && outbound->second.via_asset_id.empty()) {
        plan.refusals.push_back(
          "edge '" + entry.outbound_buffer +
          "' is a direct arm-to-arm handoff, which needs to know how the part is held. A "
          "grasp holds a position and not an orientation: up to 18.7 degrees of residual "
          "rotation between the jaws survives the grasp-plane correction (ADR-0029, "
          "docs/measurements/2026-08-25-grasp-plane-offset/), and nothing re-observes the "
          "part between the two grippers. Refused rather than attempted");
      }
    }

    plan.stations.push_back(entry);
  }

  if (plan.stations.empty() && plan.refusals.empty()) {
    plan.refusals.push_back("the topology declares no transfer station, so nothing acts");
  }

  // Resources, declared from the model rather than from a list in this file.
  //
  // Two kinds, each with its own kind of claimant, and the difference is worth
  // stating because it is what makes the arbitration mean anything:
  //
  //   * A BUFFER is claimed by a WORK-PIECE. A piece occupies a slot from the
  //     moment the upstream robot puts it on the belt to the moment the
  //     downstream robot takes it off, so the number of claimants is the number
  //     of pieces the link is carrying and the capacity is the model's own
  //     `buffer_capacity`. An upstream station that cannot get a slot waits,
  //     which is precisely "the upstream station must wait before the link is
  //     over-filled".
  //
  //   * A FRAME is claimed by a STATION, one at a time. This is the two-arms-
  //     one-conveyor-slot case: where two stations reach into the same place,
  //     only one of them is there at a time. It prevents thrash and deadlock and
  //     it is NOT what prevents a collision — L2's limits and collision checking
  //     are, and relying on this for that is how a coordination bug becomes an
  //     injury.
  std::set<std::string> frames;
  for (const auto & station : plan.stations) {
    frames.insert(station.pick_frame);
    frames.insert(station.place_frame);
  }
  frames.erase("");
  for (const auto & frame : frames) {
    plan.resources.push_back(ResourceDeclaration{frame, 1});
  }
  for (const auto & [key, edge] : edge_by_key) {
    plan.resources.push_back(
      ResourceDeclaration{key, static_cast<std::size_t>(edge.buffer_capacity)});
  }

  return plan;
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__LINE_PLAN_HPP_
