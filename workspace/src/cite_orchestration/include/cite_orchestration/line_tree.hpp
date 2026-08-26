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

// The line-level tree: one station subtree per station, built from the plan.
//
// L4's structure diagram puts a Parallel of per-station subtrees under the root
// and says they are "instantiated from L0 topology". BT.CPP's XML cannot express
// "one of these per station" — there is no loop in it — so the root tree is
// assembled here, from data, while the station subtree itself stays a file that
// a person reads and reviews (`trees/line_station.xml`).
//
// THAT SPLIT IS THE WHOLE POINT. What a station DOES is written down once, by
// hand, in one reviewable tree. HOW MANY there are, what each is called, which
// arm serves it and what it is connected to is data, and appears nowhere in any
// file a person edits. A fourth arm changes `model/`; it changes nothing here.
// If this file ever enumerates a station, it is wrong.
//
// SUBTREE BLACKBOARDS ARE ISOLATED, and that is load-bearing. "Blackboard used
// as a global store — untraceable coupling between subtrees" is a named L4
// failure mode. In BT.CPP v4 a subtree gets its own blackboard and sees only what
// is remapped into it, so a station's work-piece, its rendezvous token and the
// pose it detected are private to it by construction rather than by discipline.
// Everything a station shares with the rest of the line goes through the ledger
// and the registry, where the rules live.

#ifndef CITE_ORCHESTRATION__LINE_TREE_HPP_
#define CITE_ORCHESTRATION__LINE_TREE_HPP_

#include <map>
#include <string>
#include <vector>

#include "cite_orchestration/line_plan.hpp"

namespace cite_orchestration
{

/// The L3 actions one arm serves.
///
/// Every one of these is a NAME, and a name is never built here. They arrive as
/// parameters, exactly as the frames and the assets do: CLAUDE.md §8 puts name
/// construction in the model and says no asset name is ever written by hand
/// twice, and this project has removed a hand-composed `/cite/<zone>/<asset>/
/// <skill>` from three separate files. When the generated bring-up plan declares
/// a station's skill actions, whoever launches this node reads them from there;
/// until then the launcher writes them, and that is a gap to report rather than
/// a licence to compose one.
struct SkillActions
{
  std::string move_to;
  std::string pick;
  std::string place;
  std::string detect;
  //: ADR-0024's motion half. Only a direct arm-to-arm handoff calls it, and the
  //: plan refuses those until a grasp holds an orientation, so a line may
  //: legitimately run without one. Absence is therefore not an error here.
  std::string transfer;
};

using SkillActionsByAsset = std::map<std::string, SkillActions>;

/// A generated root tree, or the reasons there is none.
struct LineTree
{
  std::string xml;
  std::vector<std::string> refusals;
};

namespace detail
{

/// XML-escape an attribute value.
///
/// Station ids and frame names come from the model and contain nothing exotic
/// today. Escaping them anyway costs nothing and means a model that one day
/// carries an ampersand produces a tree rather than a parse error a long way
/// from its cause.
inline std::string escaped(const std::string & value)
{
  std::string out;
  out.reserve(value.size());
  for (const char character : value) {
    switch (character) {
      case '&':
        out += "&amp;";
        break;
      case '<':
        out += "&lt;";
        break;
      case '>':
        out += "&gt;";
        break;
      case '"':
        out += "&quot;";
        break;
      case '\'':
        out += "&apos;";
        break;
      default:
        out += character;
        break;
    }
  }
  return out;
}

inline std::string attribute(const std::string & name, const std::string & value)
{
  return " " + name + "=\"" + escaped(value) + "\"";
}

}  // namespace detail

/// Build the root tree for a plan.
///
/// `station_subtree_id` is the ID of the hand-written subtree in
/// `trees/line_station.xml`; the factory must already have registered that file.
inline LineTree line_tree_xml(
  const LinePlan & plan, const SkillActionsByAsset & actions,
  const std::string & station_subtree_id = "LineStation",
  const std::string & root_tree_id = "Line")
{
  LineTree tree;
  if (plan.stations.empty()) {
    tree.refusals.push_back("the plan has no station to instantiate a subtree for");
    return tree;
  }

  std::string body;
  for (const auto & station : plan.stations) {
    const auto entry = actions.find(station.actor_asset_id);
    if (entry == actions.end()) {
      tree.refusals.push_back(
        "no skill actions were supplied for asset '" + station.actor_asset_id +
        "', which serves station '" + station.id +
        "'. Names arrive as parameters; this node does not build one");
      continue;
    }
    const SkillActions & skills = entry->second;
    if (skills.move_to.empty() || skills.pick.empty() || skills.place.empty() ||
      skills.detect.empty())
    {
      tree.refusals.push_back(
        "asset '" + station.actor_asset_id + "' is missing one of the move_to, pick, place "
        "or detect action names its station needs");
      continue;
    }

    // Every value below is a static remap: BT.CPP v4 reads an attribute not
    // wrapped in braces as a literal to write into the subtree's own blackboard.
    // So each station's subtree starts life knowing exactly what it is, and
    // knowing nothing about any other station.
    body += "    <SubTree ID=\"" + detail::escaped(station_subtree_id) + "\"";
    body += detail::attribute("name", station.id);
    body += detail::attribute("station", station.id);
    body += detail::attribute("asset", station.actor_asset_id);
    body += detail::attribute("pick_frame", station.pick_frame);
    body += detail::attribute("place_frame", station.place_frame);
    body += detail::attribute("trigger_topic", station.trigger_topic);
    body += detail::attribute(
      "trigger_state", std::to_string(static_cast<unsigned>(station.trigger_detection_state)));
    body += detail::attribute("downstream", station.downstream_id);
    // Where the piece physically goes when this station lets go of it: the belt
    // that carries it, or the receiving station when nothing does. Distinct from
    // who owns it, which the ledger decides.
    body += detail::attribute(
      "outbound_location",
      station.outbound_via_asset_id.empty() ?
      station.downstream_id : station.outbound_via_asset_id);
    // Whether an empty Detect result is a fault or an idle line. A station with a
    // sensor has been TOLD a part is there, so finding none is a disagreement
    // worth reporting; a station fed from a source has been told nothing, so
    // finding none means there is no work yet. Both come from the topology.
    body += detail::attribute("require_immediate", station.trigger_topic.empty() ? "0" : "1");
    body += detail::attribute("admits_work", station.upstream_is_source ? "1" : "0");
    body += detail::attribute("inbound_buffer", station.inbound_buffer);
    body += detail::attribute("outbound_buffer", station.outbound_buffer);
    body += detail::attribute("move_to_action", skills.move_to);
    body += detail::attribute("pick_action", skills.pick);
    body += detail::attribute("place_action", skills.place);
    body += detail::attribute("detect_action", skills.detect);
    body += " />\n";
  }

  if (!tree.refusals.empty()) {
    return tree;
  }

  // `failure_count="1"` — one station failing past its own recovery fails the
  // line. That is deliberate and is not the same as one station having a bad
  // cycle: the station subtree handles a bad cycle itself and only returns
  // FAILURE once its recovery policy has escalated. When it does, Parallel halts
  // its siblings, which calls `onHalted` on whatever leaf each was running, which
  // cancels the goal that leaf was waiting on. A line that stops leaves no arm
  // moving under a goal nobody is holding.
  //
  // `success_count="-1"` — every station must finish for the line to finish, and
  // a station subtree does not finish: it repeats. So this Parallel stays RUNNING
  // for as long as the line runs, which is what "the line is running" means.
  tree.xml =
    "<root BTCPP_format=\"4\" main_tree_to_execute=\"" + detail::escaped(root_tree_id) + "\">\n"
    "  <BehaviorTree ID=\"" + detail::escaped(root_tree_id) + "\">\n"
    "    <Parallel name=\"stations\" success_count=\"-1\" failure_count=\"1\">\n" +
    body +
    "    </Parallel>\n"
    "  </BehaviorTree>\n"
    "</root>\n";
  return tree;
}

}  // namespace cite_orchestration

#endif  // CITE_ORCHESTRATION__LINE_TREE_HPP_
