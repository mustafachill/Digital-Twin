// The five named QoS profiles, in C++ (ADR-0025).
//
// Incompatible QoS between a publisher and a subscriber CONNECTS SILENTLY AND
// DELIVERS NOTHING. `ros2 topic list` shows the topic, `ros2 topic info` shows
// both endpoints, and no error is produced anywhere. It is the most-misdiagnosed
// failure in ROS 2, and v1's handoff protocol died of exactly it.
//
// The defence is to never improvise a profile. Use one of these, every time.
// A `rclcpp::QoS` literal anywhere outside this file is a review finding.
//
// See docs/interfaces/qos-profiles.md; a test asserts that this file, the Python
// module beside it, and that document all state the same numbers.

#ifndef CITE_INTERFACES__QOS_HPP_
#define CITE_INTERFACES__QOS_HPP_

#include <rclcpp/rclcpp.hpp>

namespace cite::qos
{

/// High-rate sensor streams where only the newest value matters.
inline rclcpp::QoS sensor()
{
  return rclcpp::QoS(rclcpp::KeepLast(5)).best_effort().durability_volatile();
}

/// Periodic state — joint state, line state, divergence metrics.
inline rclcpp::QoS state()
{
  return rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
}

/// Commands that must arrive.
inline rclcpp::QoS command()
{
  return rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
}

/// Configuration a late joiner must receive immediately: the robot description,
/// the model version, the current mode. Transient local is what makes a node
/// that starts late receive the current value rather than waiting for the next
/// publication — and its absence is why a controller manager can wait forever on
/// a description that was published before it existed.
inline rclcpp::QoS latched()
{
  return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
}

/// Discrete events that must not be dropped — faults, transitions, handoffs,
/// sensor edges. Keep-all, because a missed edge is a work-piece the line never
/// notices.
inline rclcpp::QoS event()
{
  return rclcpp::QoS(rclcpp::KeepAll()).reliable().durability_volatile();
}

}  // namespace cite::qos

#endif  // CITE_INTERFACES__QOS_HPP_
