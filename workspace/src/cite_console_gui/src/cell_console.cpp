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
#include <QtGlobal>

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

namespace cite_console_gui
{

CellConsole::CellConsole()
: state_name_("No console"), twin_mode_("unknown")
{
}

CellConsole::~CellConsole()
{
  // Joins the spin thread first, so nothing is queued onto this object once it
  // starts going away; anything already queued is dropped with it by Qt.
  client_.reset();
}

void CellConsole::LoadConfig(const tinyxml2::XMLElement * plugin_element)
{
  if (this->title.empty()) {
    this->title = "Cell console";
  }

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
      QMetaObject::invokeMethod(
        this, [this, name]() {
          twin_mode_ = name;
          emit twinModeChanged();
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
  emit twinModeChanged();
  set_progress(QString());
  set_outcome(QString());
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

}  // namespace cite_console_gui

GZ_ADD_PLUGIN(cite_console_gui::CellConsole, gz::gui::Plugin)
