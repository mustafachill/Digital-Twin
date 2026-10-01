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

// The edge rule, tested as a state machine over samples — no bridge, no
// simulator, no waiting.

#include <gtest/gtest.h>

#include "cite_skills/detection.hpp"

using cite_skills::BeamEdgeDetector;
using cite_skills::BeamReport;

TEST(BeamEdgeDetector, ReportsNothingBeforeAnySampleArrives)
{
  const BeamEdgeDetector detector;
  // "Never reported" and "reported CLEAR" are different facts with different
  // causes — a bridge that is not delivering, versus an empty belt — and a
  // consumer that could not tell them apart would read a dead sensor as a clear
  // one and run the line into it.
  EXPECT_FALSE(detector.known());
}

TEST(BeamEdgeDetector, TheFirstSampleIsAStateReportAndNotAnEdge)
{
  BeamEdgeDetector detector;
  // A work-piece already sitting in the beam when this node starts. Nothing here
  // saw it arrive, so publishing previous_state CLEAR would be a transition
  // invented rather than observed.
  const auto report = detector.observe(true, 10.0);
  EXPECT_EQ(report.kind, BeamReport::Initial);
  EXPECT_TRUE(report.state);
  EXPECT_EQ(report.previous_state, report.state)
    << "the first sample must not read as an edge under the ordinary "
       "state != previous_state test";
  EXPECT_TRUE(detector.known());
  EXPECT_TRUE(detector.blocked());
}

TEST(BeamEdgeDetector, TheFirstSampleIsReportedEvenWhenTheBeamIsClear)
{
  BeamEdgeDetector detector;
  const auto report = detector.observe(false, 4.0);
  EXPECT_EQ(report.kind, BeamReport::Initial);
  EXPECT_FALSE(report.state);
  EXPECT_FALSE(detector.blocked());
}

TEST(BeamEdgeDetector, RepublishedLevelsAreNotEvents)
{
  BeamEdgeDetector detector;
  detector.observe(false, 0.0);
  // The plugin republishes the current state periodically so that a late
  // subscriber learns it without waiting for a transition. Turning each of those
  // into a DetectionEvent would bury the transitions the keep-all event topic
  // exists to carry.
  for (int sample = 1; sample <= 20; ++sample) {
    const auto report = detector.observe(false, static_cast<double>(sample) * 0.5);
    EXPECT_EQ(report.kind, BeamReport::None) << "sample " << sample;
  }
}

TEST(BeamEdgeDetector, ARisingEdgeIsTheEvent)
{
  BeamEdgeDetector detector;
  detector.observe(false, 0.0);
  detector.observe(false, 1.0);
  const auto report = detector.observe(true, 2.5);
  EXPECT_EQ(report.kind, BeamReport::Edge);
  EXPECT_TRUE(report.state);
  EXPECT_FALSE(report.previous_state);
  EXPECT_NEAR(report.duration_in_previous_state_s, 2.5, 1e-9);
}

TEST(BeamEdgeDetector, AFallingEdgeIsAlsoAnEvent)
{
  BeamEdgeDetector detector;
  detector.observe(true, 0.0);
  // The work-piece leaves. A line that only watched rising edges would never
  // learn the station had cleared, and the next piece would arrive into a beam
  // it believes is still occupied.
  const auto report = detector.observe(false, 3.0);
  EXPECT_EQ(report.kind, BeamReport::Edge);
  EXPECT_FALSE(report.state);
  EXPECT_TRUE(report.previous_state);
  EXPECT_NEAR(report.duration_in_previous_state_s, 3.0, 1e-9);
}

TEST(BeamEdgeDetector, DurationIsMeasuredBetweenEdgesAndNotSinceTheLastSample)
{
  BeamEdgeDetector detector;
  detector.observe(false, 0.0);
  detector.observe(false, 1.0);
  detector.observe(false, 2.0);
  const auto blocked = detector.observe(true, 6.0);
  // Six seconds clear, not the four since the previous republication. The
  // periodic sample must not reset the clock, or every dwell time the line
  // records becomes the publication period.
  EXPECT_NEAR(blocked.duration_in_previous_state_s, 6.0, 1e-9);

  detector.observe(true, 7.0);
  const auto cleared = detector.observe(false, 9.0);
  EXPECT_NEAR(cleared.duration_in_previous_state_s, 3.0, 1e-9);
}

TEST(BeamEdgeDetector, AnOutOfOrderSampleDoesNotProduceANegativeDuration)
{
  BeamEdgeDetector detector;
  detector.observe(false, 5.0);
  // Samples can arrive out of order across a bridge. The edge is still true; a
  // negative duration is a number no consumer has a meaning for.
  const auto report = detector.observe(true, 4.0);
  EXPECT_EQ(report.kind, BeamReport::Edge);
  EXPECT_GE(report.duration_in_previous_state_s, 0.0);
}

TEST(Region, ContainsAPointAtItsCentre)
{
  EXPECT_TRUE(cite_skills::inside_region(0.0, 0.0, 0.0, 1.0, 1.0, 1.0));
}

TEST(Region, IsCentredOnTheFrameRatherThanCorneredAtIt)
{
  // `region_size_m` is documented as extents ABOUT the frame. Read as a corner
  // the same numbers would describe a box entirely on one side of the sensor
  // they were meant to bracket, and a region derived from the model would stop
  // containing the thing it was derived from.
  EXPECT_TRUE(cite_skills::inside_region(-0.4, -0.4, -0.4, 1.0, 1.0, 1.0));
  EXPECT_TRUE(cite_skills::inside_region(0.4, 0.4, 0.4, 1.0, 1.0, 1.0));
}

TEST(Region, ExcludesAPointBeyondAnyOneAxis)
{
  EXPECT_FALSE(cite_skills::inside_region(0.6, 0.0, 0.0, 1.0, 1.0, 1.0));
  EXPECT_FALSE(cite_skills::inside_region(0.0, 0.6, 0.0, 1.0, 1.0, 1.0));
  EXPECT_FALSE(cite_skills::inside_region(0.0, 0.0, 0.6, 1.0, 1.0, 1.0));
}

TEST(Region, TreatsItsBoundaryAsInside)
{
  // A caller sizing a region from the model's own dimensions gets a beam exactly
  // on the face. Excluding it would make the region fail to contain the thing it
  // was sized around.
  EXPECT_TRUE(cite_skills::inside_region(0.5, 0.0, 0.0, 1.0, 1.0, 1.0));
}

TEST(Region, IsEmptyWhenAnExtentIsZero)
{
  // The caller's problem to avoid, not this function's to paper over: the skill
  // refuses a non-positive extent rather than returning an empty detection list,
  // because an empty list reads as "nothing is there".
  EXPECT_FALSE(cite_skills::inside_region(0.1, 0.0, 0.0, 0.0, 1.0, 1.0));
}
