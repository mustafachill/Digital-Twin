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

#include <QList>
#include <QMetaObject>
#include <QPointF>
#include <QRectF>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTime>
#include <QVariantMap>
#include <QtGlobal>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <gz/gui/Application.hh>
#include <gz/gui/MainWindow.hh>
#include <gz/plugin/Register.hh>

#include "cite_console_gui/console_config.hpp"
#include "cite_console_gui/console_view.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"

namespace cite_console_gui
{

namespace
{

/// Whether `item` is an ApplicationWindow's popup overlay that would keep a
/// press: Qt Quick hands it every press first, and it lets one by unless a
/// modal popup is open in it.
bool overlay_keeps_the_press(const QQuickItem * item)
{
  if (std::strcmp(item->metaObject()->className(), "QQuickOverlay") != 0) {
    return false;
  }
  for (const QQuickItem * popup : item->childItems()) {
    if (popup->isVisible() && popup->parent() != nullptr &&
      popup->parent()->property("modal").toBool())
    {
      return true;
    }
  }
  return false;
}

/// The item a left press at `scene` goes to first, under `item`; nullptr for
/// none. Qt Quick 5.15's order (`QQuickWindowPrivate::pointerTargets`): a
/// clipping item that does not contain the point hides its children; children
/// in reverse paint order (z, then declaration), each visible and enabled;
/// then the item itself if it contains the point and takes the left button.
/// A MouseArea's own `enabled` shadows the item's: one set false is still
/// handed the press, lets it go by, and the next item gets it; so does the
/// popup overlay while no modal popup is open. `target`, and
/// the items it is in, are walked whether enabled or not: what is asked is
/// whether anything else would take its press.
QQuickItem * first_press_target(QQuickItem * item, const QPointF & scene, QQuickItem * target)
{
  const QPointF local = item->mapFromScene(scene);
  if (item->clip() && !item->contains(local)) {
    return nullptr;
  }
  QList<QQuickItem *> children = item->childItems();
  std::stable_sort(
    children.begin(), children.end(),
    [](const QQuickItem * a, const QQuickItem * b) {return a->z() < b->z();});
  for (auto child = children.rbegin(); child != children.rend(); ++child) {
    const bool on_the_way = *child == target || (*child)->isAncestorOf(target);
    if (!(*child)->isVisible() || (!(*child)->isEnabled() && !on_the_way)) {
      continue;
    }
    if (QQuickItem * found = first_press_target(*child, scene, target)) {
      return found;
    }
  }
  if (!item->contains(local)) {
    return nullptr;
  }
  if (std::strcmp(item->metaObject()->className(), "QQuickOverlay") == 0) {
    return overlay_keeps_the_press(item) ? item : nullptr;
  }
  const bool takes_it = (item->acceptedMouseButtons() & Qt::LeftButton) &&
    item->property("enabled").toBool();
  return item == target || takes_it ? item : nullptr;
}

}  // namespace

CellConsole::CellConsole()
: state_name_("No console")
{
}

CellConsole::~CellConsole()
{
  // Joins the spin thread first, so nothing is queued onto this object once it
  // starts going away; anything already queued is dropped with it by Qt. The
  // camera client's worker likewise, after at most the one call in flight.
  health_timer_.stop();
  world_stats_client_.reset();
  client_.reset();
  camera_.reset();
}

void CellConsole::LoadConfig(const tinyxml2::XMLElement * plugin_element)
{
  if (this->title.empty()) {
    this->title = "Cell console";
  }
  frame_window_when_shown();

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
  // The header's labels and the world's statistics (ADR-0074): display only,
  // so a problem here is said on the view's line and disables nothing.
  const std::string frame_problem = read_frame_config(plugin_element, frame_config_);
  if (frame_problem.empty()) {
    try {
      // Called on gz transport's thread, and queued onto this object's.
      world_stats_client_ = std::make_unique<WorldStatsClient>(
        frame_config_.world_stats_topic, [this](const WorldStats & stats) {
          QMetaObject::invokeMethod(
            this, [this, stats]() {
              world_stats_ = stats;
              world_stats_heard_ = true;
              emit worldStatsChanged();
            }, Qt::QueuedConnection);
        });
    } catch (const std::exception & error) {
      if (view_config_error_.isEmpty()) {
        view_config_error_ = QString("The header cannot show sim time: ") + error.what();
      }
    }
  } else if (view_config_error_.isEmpty()) {
    view_config_error_ = QString::fromStdString(frame_problem);
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
          boundary_.twin_mode_heard(name.toStdString(), is_sim);
          emit twinModeChanged();
          emit healthChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_twin_mode_lost = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          boundary_.twin_mode_lost();
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
          boundary_.sides_heard(sides);
          emit healthChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_twin_sides_lost = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          boundary_.sides_lost();
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
  callbacks.on_divergence = [this](const cite_interfaces::msg::DivergenceMetrics & message) {
      const DivergenceSample sample = divergence_sample_from(message);
      QMetaObject::invokeMethod(
        this, [this, sample]() {
          divergence_[sample.asset_id] = sample;
          emit fidelityChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_divergence_lost = [this]() {
      QMetaObject::invokeMethod(
        this, [this]() {
          divergence_.clear();
          emit fidelityChanged();
        }, Qt::QueuedConnection);
    };
  callbacks.on_run_progress = [this](const RunProgress & position) {
      QMetaObject::invokeMethod(
        this, [this, position]() {
          run_progress_ = position;
          emit runProgressChanged();
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
  log_transition();
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
  // The twin's mode is the boundary's, not the console's: it stays until
  // TwinMode's own publisher leaves (R-02).
  boundary_.console_lost();
  emit healthChanged();
  set_progress(QString());
  set_outcome(QString());
  // The console that left can report nothing more about its request.
  run_progress_ = RunProgress{};
  emit runProgressChanged();
  log_transition();
}

void CellConsole::log_transition()
{
  const QString now = QTime::currentTime().toString("HH:mm:ss");
  if (event_log_.record(
      now.toStdString(), state_name_.toStdString(), step_.toStdString(),
      last_error_.toStdString()))
  {
    emit eventLogChanged();
  }
}

QVariantList CellConsole::eventLog() const
{
  QVariantList rows;
  for (const EventEntry & entry : event_log_.entries()) {
    QVariantMap row;
    row["time"] = QString::fromStdString(entry.time);
    row["state"] = QString::fromStdString(entry.state);
    row["step"] = QString::fromStdString(entry.step);
    row["lastError"] = QString::fromStdString(entry.last_error);
    rows << row;
  }
  return rows;
}

QVariantList CellConsole::fidelity() const
{
  QVariantList cards;
  for (const auto & [asset, sample] : divergence_) {
    const FidelityView view = fidelity_view(sample);
    QVariantList rows;
    for (const FidelityRow & figure : view.rows) {
      QVariantMap row;
      row["label"] = QString::fromStdString(figure.label);
      row["value"] = QString::fromStdString(figure.value);
      rows << row;
    }
    QVariantMap card;
    card["asset"] = QString::fromStdString(asset);
    card["measured"] = view.measured;
    card["headline"] = QString::fromStdString(view.headline);
    card["rows"] = rows;
    cards << card;
  }
  return cards;
}

QString CellConsole::simTime() const
{
  return world_stats_heard_ ?
         QString::fromStdString(format_sim_time(world_stats_.sim_time_s)) : QString("--:--:--");
}

QString CellConsole::realTimeFactor() const
{
  return world_stats_heard_ ?
         QString::fromStdString(format_real_time_factor(world_stats_.real_time_factor)) :
         QString("--");
}

void CellConsole::frame_window_when_shown()
{
  // The panel's item exists once gz-gui has created it from the QML, before
  // this plugin's configuration is loaded; it reaches a window when its card is
  // added to gz-gui's main window. Each step is an event, never a timer (P4).
  QQuickItem * item = this->PluginItem();
  if (item == nullptr) {
    return;
  }
  if (item->window() != nullptr) {
    frame_window(item->window());
  }
  connect(item, &QQuickItem::windowChanged, this, [this](QQuickWindow * window) {
      frame_window(window);
    });
}

void CellConsole::frame_window(QQuickWindow * window)
{
  if (window == nullptr || window_framed_) {
    return;
  }
  // Only gz-gui's own main window, never a window a test put the panel in.
  gz::gui::Application * app = gz::gui::App();
  gz::gui::MainWindow * main = app == nullptr ? nullptr : app->findChild<gz::gui::MainWindow *>();
  if (main == nullptr || main->QuickWindow() != window) {
    return;
  }
  if (!window->isVisible()) {
    if (!waiting_for_shown_) {
      waiting_for_shown_ = true;
      connect(
        window, &QWindow::visibleChanged, this, [this, window](bool visible) {
          if (visible) {
            frame_window(window);
          }
        });
    }
    return;
  }
  window_framed_ = true;
  // gz-gui's title toolbar: ApplicationWindow's `header`, a gz-gui internal
  // (ADR-0074, "What this costs us"). Its absence is said, not fatal.
  auto * header = window->property("header").value<QQuickItem *>();
  if (header != nullptr) {
    header->setVisible(false);
  } else {
    qWarning("CellConsole: gz-gui's window has no header to hide (ADR-0074)");
  }
  // Maximized, not fullscreen: the desktop's title bar and close stay.
  window->showMaximized();
  emit windowShown();
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
    const SideHealth health = boundary_.side(side, shown_boundary_);
    QVariantMap row;
    row["name"] = QString::fromStdString(side);
    row["link"] = QString::fromUtf8(link_name(health.link));
    row["abnormal"] = link_abnormal(health.link);
    row["physical"] = health.physical;
    row["stationary"] = health.stationary;
    row["why"] = QString::fromStdString(health.why);
    rows << row;
  }
  return rows;
}

bool CellConsole::physicalCommanded() const
{
  const bool has_physical = !boundary_.sides().physical.empty() || !physical_sides_.isEmpty();
  return physical_side_commanded(
    has_physical, boundary_.twin_mode_heard(), boundary_.twin_mode_is_sim());
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

bool CellConsole::pressReaches(QQuickItem * target) const
{
  if (target == nullptr || target->window() == nullptr || target->width() <= 0.0 ||
    target->height() <= 0.0)
  {
    return true;
  }
  const QPointF centre =
    target->mapToScene(QPointF(target->width() / 2.0, target->height() / 2.0));
  QQuickItem * root = target->window()->contentItem();
  if (!QRectF(0.0, 0.0, root->width(), root->height()).contains(centre)) {
    // Outside the window: a layout on its way somewhere, not one to judge.
    return true;
  }
  QQuickItem * found = first_press_target(root, centre, target);
  return found != nullptr && (found == target || target->isAncestorOf(found));
}

void CellConsole::followRobot()
{
  if (followEnabled()) {
    camera_->request(CameraCommand::following(view_config_.follow_target));
  }
}

}  // namespace cite_console_gui

GZ_ADD_PLUGIN(cite_console_gui::CellConsole, gz::gui::Plugin)
