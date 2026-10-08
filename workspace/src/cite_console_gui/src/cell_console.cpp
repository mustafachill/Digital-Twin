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

#include <exception>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <gz/plugin/Register.hh>

#include "cite_console_gui/console_view.hpp"

namespace cite_console_gui
{

namespace
{

/// The plugin element's text under `key`, or empty when it has none.
std::string parameter(const tinyxml2::XMLElement * plugin_element, const char * key)
{
  if (plugin_element == nullptr) {
    return "";
  }
  const auto * element = plugin_element->FirstChildElement(key);
  if (element == nullptr || element->GetText() == nullptr) {
    return "";
  }
  return element->GetText();
}

}  // namespace

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

  ConsoleNames names;
  const std::vector<std::pair<const char *, std::string *>> keys = {
    {"state", &names.state},
    {"start_robot", &names.start_robot},
    {"confirm_operator", &names.confirm_operator},
    {"stop", &names.stop},
    {"home", &names.home},
    {"run_program", &names.run_program},
  };
  QStringList missing;
  for (const auto & [key, target] : keys) {
    *target = parameter(plugin_element, key);
    if (target->empty()) {
      missing << QString::fromUtf8(key);
    }
  }
  if (!missing.isEmpty()) {
    config_error_ = "The GUI configuration names no " + missing.join(", ") +
      " for this panel. Regenerate it: ./scripts/validate-model --write";
    qWarning("CellConsole: %s", qUtf8Printable(config_error_));
    emit viewChanged();
    return;
  }

  // Every callback below runs on the client's spin thread. Each one only
  // queues its work onto this object's thread; `this` as the context object
  // means a queued call is dropped if the panel is gone by then.
  ConsoleCallbacks callbacks;
  callbacks.on_state = [this](const cite_interfaces::msg::ConsoleState & state) {
      QMetaObject::invokeMethod(this, [this, state]() {apply_state(state);}, Qt::QueuedConnection);
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

void CellConsole::apply_state(const cite_interfaces::msg::ConsoleState & state)
{
  view_ = view_from(state);
  buttons_ = enabled_for(view_);
  state_name_ = QString::fromUtf8(phase_name(view_.phase));
  step_ = QString::fromStdString(state.step);
  prompt_ = QString::fromStdString(state.prompt);
  last_error_ = QString::fromStdString(state.last_error);
  physical_sides_.clear();
  for (const auto & side : state.physical_sides) {
    physical_sides_ << QString::fromStdString(side);
  }
  minimum_speed_scale_ = state.minimum_speed_scale;
  speed_scale_ = state.speed_scale;
  emit viewChanged();
}

void CellConsole::forget_state()
{
  view_ = ConsoleView{};
  buttons_ = enabled_for(view_);
  state_name_ = "No console";
  step_.clear();
  prompt_.clear();
  last_error_.clear();
  physical_sides_.clear();
  minimum_speed_scale_ = 0.0;
  speed_scale_ = 0.0;
  emit viewChanged();
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
    enabled << (view_.heard && speed_choice_enabled(scale, minimum_speed_scale_));
  }
  return enabled;
}

void CellConsole::startRobot()
{
  if (client_ && buttons_.start_robot) {
    client_->start_robot();
  }
}

void CellConsole::home(double speed_scale)
{
  if (client_ && buttons_.home) {
    client_->home(speed_scale);
  }
}

void CellConsole::startProgram(double speed_scale, int cycles)
{
  if (client_ && buttons_.start_program && cycles >= 1) {
    client_->run_program(speed_scale, static_cast<std::uint32_t>(cycles));
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
  if (client_ && buttons_.confirm) {
    client_->confirm_operator();
  }
}

}  // namespace cite_console_gui

GZ_ADD_PLUGIN(cite_console_gui::CellConsole, gz::gui::Plugin)
