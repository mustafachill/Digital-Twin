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

#include "cell_console.hpp"

#include <QMetaObject>
#include <QVariantMap>
#include <QtGlobal>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <gz/plugin/Register.hh>

#include "cite_console_gui/console_config.hpp"
#include "cite_console_gui/console_view.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"

namespace cite_console_gui
{

CellConsole::CellConsole()
: state_name_("No console"), twin_mode_("unknown")
{
}

CellConsole::~CellConsole()
{
  // Joins the spin thread first, so nothing is queued onto this object once it
  // starts going away; anything already queued is dropped with it by Qt. The
  // camera client's worker likewise, after at most the one call in flight.
  health_timer_.stop();
  client_.reset();
  camera_.reset();
}

void CellConsole::LoadConfig(const tinyxml2::XMLElement * plugin_element)
{
  if (this->title.empty()) {
    this->title = "Cell console";
  }

  // The view buttons first, and on their own: they move no robot, so a
  // configuration whose console names are wrong still lets the operator find
  // the cell again. Reset view needs only its home pose; the presets, Follow
  // robot and the connection display need the rest (`read_view_config`).
  const std::string view_problem = read_home_camera_pose(plugin_element, home_camera_pose_);
  if (view_problem.empty()) {
    try {
      // Called on the client's worker thread, and queued onto this object's.
      // Its answer is the view's, said on the view's own line (`viewError`),
      // never on the console's outcome line (R-02).
      camera_ = std::make_unique<CameraClient>(
        [this](bool ok, const std::string & detail) {
          const QString line = ok ? QString() : QString::fromStdString(detail);
          QMetaObject::invokeMethod(
            this, [this, line]() {
              if (view_request_error_ != line) {
                view_request_error_ = line;
                emit viewChanged();
              }
            }, Qt::QueuedConnection);
        });
    } catch (const std::exception & error) {
      view_config_error_ = QString("The view buttons could not join gz transport: ") +
        error.what();
    }
  } else {
    view_config_error_ = QString::fromStdString(view_problem);
  }
  const std::string config_problem = read_view_config(plugin_element, view_config_);
  if (!config_problem.empty() && view_config_error_.isEmpty()) {
    view_config_error_ = QString::fromStdString(config_problem);
  }
  if (!view_config_error_.isEmpty()) {
    qWarning("CellConsole: %s", qUtf8Printable(view_config_error_));
  }
  if (healthShown()) {
    // A repaint, at twice the rate the threshold needs to be seen crossed.
    health_timer_.setInterval(
      std::max(50, static_cast<int>(view_config_.heartbeat_stale_after_s * 500.0)));
    connect(&health_timer_, &QTimer::timeout, this, [this]() {refresh_health();});
    health_timer_.start();
  }
  emit viewChanged();
  emit healthChanged();

  // The keys, and the refusal of a child the panel does not read, are
  // `read_console_names`' (console_config.hpp), tested without a window.
  ConsoleNames names;
  const std::string problem = read_console_names(plugin_element, names);
  if (!problem.empty()) {
    config_error_ = QString::fromStdString(problem);
    qWarning("CellConsole: %s", qUtf8Printable(config_error_));
    emit viewChanged();
    return;
  }

  // Every callback below runs on the client's spin thread. Each one only
  // queues its work onto this object's thread; `this` as the context object
  // means a queued call is dropped if the panel is gone by then.
  ConsoleCallbacks callbacks;
  callbacks.on_state = [this](
    const cite_interfaces::msg::ConsoleState & state, const std::vector<std::uint8_t> & publisher) {
      QMetaObject::invokeMethod(
        this, [this, state, publisher]() {apply_state(state, publisher);}, Qt::QueuedConnection);
    };
  callbacks.on_state_lost = [this]() {
      QMetaObject::invokeMethod(this, [this]() {forget_state();}, Qt::QueuedConnection);
    };
  callbacks.on_twin_mode = [this](const cite_interfaces::msg::TwinMode & mode) {
      const QString name = QString::fromStdString(twin_mode_name(mode.mode)) +
        (mode.transition_in_progress ?
        QString::fromStdString(" (to " + twin_mode_name(mode.requested_mode) + ")") :
        QString());
      // In SIM only when it is there and not on its way out of it.
      const bool is_sim = mode.mode == cite_interfaces::msg::TwinMode::MODE_SIM &&
        !mode.transition_in_progress;
      QMetaObject::invokeMethod(
        this, [this, name, is_sim]() {
          twin_mode_ = name;
          twin_mode_heard_ = true;
          twin_mode_is_sim_ = is_sim;
          emit twinModeChanged();
          emit healthChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_twin_sides = [this](const cite_interfaces::msg::TwinSides & message) {
      SidesView sides;
      sides.heard = true;
      sides.running.insert(message.running.begin(), message.running.end());
      sides.physical.insert(message.physical.begin(), message.physical.end());
      sides.commandable.insert(message.commandable.begin(), message.commandable.end());
      sides.stationary.insert(message.stationary.begin(), message.stationary.end());
      sides.detail = message.detail;
      QMetaObject::invokeMethod(
        this, [this, sides]() {
          sides_ = sides;
          emit healthChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_twin_sides_lost = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          sides_ = SidesView{};
          emit healthChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_heartbeat = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          heartbeat_present_ = true;
          heartbeat_heard_ = true;
          last_heartbeat_.restart();
          refresh_health();
        }, Qt::QueuedConnection);
    };
  callbacks.on_heartbeat_lost = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          heartbeat_present_ = false;
          heartbeat_heard_ = false;
          refresh_health();
        }, Qt::QueuedConnection);
    };
  callbacks.on_progress = [this](const std::string & text) {
      const QString line = QString::fromStdString(text);
      QMetaObject::invokeMethod(this, [this, line]() {set_progress(line);}, Qt::QueuedConnection);
    };
  callbacks.on_outcome = [this](const std::string & text) {
      const QString line = QString::fromStdString(text);
      QMetaObject::invokeMethod(this, [this, line]() {set_outcome(line);}, Qt::QueuedConnection);
    };

  try {
    client_ = std::make_unique<ConsoleClient>(names, std::move(callbacks));
  } catch (const std::exception & error) {
    config_error_ = QString("The panel could not join the ROS graph: ") + error.what();
    qWarning("CellConsole: %s", qUtf8Printable(config_error_));
    emit viewChanged();
  }
}

void CellConsole::apply_state(
  const cite_interfaces::msg::ConsoleState & state, const std::vector<std::uint8_t> & publisher)
{
  selection_.apply(view_from(state, publisher));
  state_name_ = QString::fromUtf8(phase_name(selection_.view().phase));
  step_ = QString::fromStdString(state.step);
  prompt_ = QString::fromStdString(state.prompt);
  last_error_ = QString::fromStdString(state.last_error);
  physical_sides_.clear();
  for (const auto & side : state.physical_sides) {
    physical_sides_ << QString::fromStdString(side);
  }
  speed_scale_ = state.speed_scale;
  emit viewChanged();
  emit healthChanged();
}

void CellConsole::forget_state()
{
  selection_.forget();
  state_name_ = "No console";
  step_.clear();
  prompt_.clear();
  last_error_.clear();
  physical_sides_.clear();
  speed_scale_ = 0.0;
  emit viewChanged();
  // Nothing said while the console was there stands for one that is gone.
  twin_mode_ = "unknown";
  twin_mode_heard_ = false;
  twin_mode_is_sim_ = false;
  emit twinModeChanged();
  emit healthChanged();
  set_progress(QString());
  set_outcome(QString());
}

HeartbeatView CellConsole::heartbeat_now() const
{
  HeartbeatView heartbeat;
  heartbeat.publisher_present = heartbeat_present_;
  heartbeat.heard = heartbeat_heard_ && last_heartbeat_.isValid();
  heartbeat.age_s = heartbeat.heard ? static_cast<double>(last_heartbeat_.elapsed()) / 1000.0 : 0.0;
  return heartbeat;
}

void CellConsole::refresh_health()
{
  const Link now = boundary_link(heartbeat_now(), view_config_.heartbeat_stale_after_s);
  if (now != shown_boundary_) {
    shown_boundary_ = now;
    emit healthChanged();
  }
}

QString CellConsole::boundaryLink() const
{
  return QString::fromUtf8(link_name(shown_boundary_));
}

QVariantList CellConsole::sideHealth() const
{
  QVariantList rows;
  for (const std::string & side : view_config_.twin_sides) {
    const SideHealth health = side_health(side, sides_, shown_boundary_);
    QVariantMap row;
    row["name"] = QString::fromStdString(side);
    row["link"] = QString::fromUtf8(link_name(health.link));
    row["abnormal"] = health.link != Link::LIVE;
    row["physical"] = health.physical;
    row["stationary"] = health.stationary;
    row["why"] = QString::fromStdString(health.why);
    rows << row;
  }
  return rows;
}

bool CellConsole::physicalCommanded() const
{
  const bool has_physical = !sides_.physical.empty() || !physical_sides_.isEmpty();
  return physical_side_commanded(has_physical, twin_mode_heard_, twin_mode_is_sim_);
}

QString CellConsole::validationPhase() const
{
  return QString::fromUtf8(validation_phase_name(selection_.view().validation_phase));
}

QString CellConsole::viewError() const
{
  return view_config_error_.isEmpty() ? view_request_error_ : view_config_error_;
}

QStringList CellConsole::viewPresets() const
{
  QStringList labels;
  if (camera_) {
    for (const auto & preset : view_config_.presets) {
      labels << QString::fromStdString(preset.first);
    }
  }
  return labels;
}

void CellConsole::set_progress(const QString & text)
{
  progress_ = text;
  emit progressChanged();
}

void CellConsole::set_outcome(const QString & text)
{
  outcome_ = text;
  emit outcomeChanged();
}

QVariantList CellConsole::speedChoices() const
{
  QVariantList choices;
  for (const double scale : SPEED_CHOICES) {
    choices << scale;
  }
  return choices;
}

QVariantList CellConsole::speedChoicesEnabled() const
{
  QVariantList enabled;
  for (const double scale : SPEED_CHOICES) {
    enabled << speed_choice_enabled(scale, selection_.view(), selection_.selected());
  }
  return enabled;
}

QVariantList CellConsole::twinSpeedChoicesEnabled() const
{
  QVariantList enabled;
  for (const double scale : SPEED_CHOICES) {
    enabled << speed_choice_enabled(scale, selection_.view(), Target::TWIN);
  }
  return enabled;
}

QStringList CellConsole::targetChoices() const
{
  QStringList choices;
  for (const Target target : ALL_TARGETS) {
    choices << QString::fromUtf8(target_name(target));
  }
  return choices;
}

QVariantList CellConsole::targetChoicesEnabled() const
{
  QVariantList enabled;
  for (const Target target : ALL_TARGETS) {
    enabled << target_choice_enabled(selection_.view(), target);
  }
  return enabled;
}

int CellConsole::selectedTarget() const
{
  for (std::size_t index = 0; index < ALL_TARGETS.size(); ++index) {
    if (ALL_TARGETS[index] == selection_.selected()) {
      return static_cast<int>(index);
    }
  }
  return -1;
}

void CellConsole::selectTarget(int index)
{
  if (index < 0 || static_cast<std::size_t>(index) >= ALL_TARGETS.size()) {
    return;
  }
  if (selection_.select(ALL_TARGETS[static_cast<std::size_t>(index)])) {
    emit viewChanged();
  }
}

void CellConsole::startRobot()
{
  if (client_ && selection_.buttons().start_robot) {
    client_->start_robot();
  }
}

void CellConsole::home(double speed_scale)
{
  if (client_ && selection_.may_home(speed_scale)) {
    client_->home(speed_scale, target_value(selection_.selected()));
  }
}

void CellConsole::startProgram(double speed_scale, int cycles)
{
  if (client_ && selection_.may_run(speed_scale, cycles)) {
    client_->run_program(
      speed_scale, target_value(selection_.selected()), static_cast<std::uint32_t>(cycles));
  }
}

void CellConsole::validateThenRun(double speed_scale, int cycles)
{
  if (client_ && selection_.may_validate_then_run(speed_scale, cycles)) {
    client_->validate_then_run(speed_scale, static_cast<std::uint32_t>(cycles));
  }
}

void CellConsole::stop()
{
  // Sent whenever there is a client, enabled or not: Stop is also the cancel
  // of the operator's confirmation, and a refused Stop costs a refusal.
  if (client_) {
    client_->stop();
  }
}

void CellConsole::confirm()
{
  if (client_ && selection_.buttons().confirm) {
    client_->confirm_operator();
  }
}

void CellConsole::resetView()
{
  // Independent of the console: no state, no target, no "No console" gates it.
  if (camera_) {
    camera_->move_to(home_camera_pose_);
  }
}

void CellConsole::selectPreset(int index)
{
  if (camera_ && index >= 0 && static_cast<std::size_t>(index) < view_config_.presets.size()) {
    camera_->move_to(view_config_.presets[static_cast<std::size_t>(index)].second);
  }
}

void CellConsole::followRobot()
{
  if (followEnabled()) {
    camera_->request(CameraCommand::following(view_config_.follow_model));
  }
}

}  // namespace cite_console_gui

GZ_ADD_PLUGIN(cite_console_gui::CellConsole, gz::gui::Plugin)
