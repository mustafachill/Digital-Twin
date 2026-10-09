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

// CellConsole: the operator console's panel in the Gazebo window (ADR-0071).
//
// A gz-gui plugin that shows `cell_console`'s latched ConsoleState and sends its
// requests. It holds no logic: what the buttons enable is `enabled_for`
// (enablement.hpp), which target stays selected is `settled_selection`, what
// each side's connection shows is `side_health` (health.hpp), and every refusal
// is the console's own. The operator's selected target (ADR-0072) is held in
// `PanelSelection` (selection.hpp), not here and not in QML, so that the
// sequences that keep or clear it are the tested ones. Everything ROS is in
// `ConsoleClient`, on a thread of its own; each thing it hears is queued onto
// this object's (the Qt) thread, so no property is touched from two threads and
// nothing on the Qt thread ever waits for the graph. The view buttons - Reset
// view, the presets and Follow robot - are the things it asks of the window
// rather than the console: `CameraClient`, over gz transport, on a thread of its
// own as well, its answer queued back the same way.
//
// ONE TIMER, FOR A DISPLAY. How long ago the twin boundary's heartbeat arrived
// is timed on this object's steady clock and re-read by a Qt timer, so that a
// heartbeat that stops turns the display stale without anything arriving. It
// sequences nothing and gates nothing (P4): it only repaints.
//
// Its names are this plugin's XML parameters, written by the generated GUI
// configuration (generate/gui.py) under the keys of the plan's `console:` block.
// A configuration missing any of them is reported in the panel, and the panel
// stays disabled: a guessed name is a panel that commands nothing.

#ifndef CELL_CONSOLE_HPP_
#define CELL_CONSOLE_HPP_

#include <QElapsedTimer>
#include <QString>
#include <QStringList>
#include <QTimer>
#include <QVariantList>

#include <memory>
#include <cstdint>
#include <string>
#include <vector>

#include <gz/gui/Plugin.hh>

#include "cite_console_gui/camera_client.hpp"
#include "cite_console_gui/console_client.hpp"
#include "cite_console_gui/console_config.hpp"
#include "cite_console_gui/enablement.hpp"
#include "cite_console_gui/health.hpp"
#include "cite_console_gui/selection.hpp"

namespace cite_console_gui
{

class CellConsole : public gz::gui::Plugin
{
  Q_OBJECT

  // What the console last said; one notification for all of it.
  Q_PROPERTY(bool heard READ heard NOTIFY viewChanged)
  Q_PROPERTY(QString configError READ configError NOTIFY viewChanged)
  Q_PROPERTY(QString stateName READ stateName NOTIFY viewChanged)
  Q_PROPERTY(bool faulted READ faulted NOTIFY viewChanged)
  Q_PROPERTY(QString step READ step NOTIFY viewChanged)
  Q_PROPERTY(QString prompt READ prompt NOTIFY viewChanged)
  Q_PROPERTY(QString lastError READ lastError NOTIFY viewChanged)
  Q_PROPERTY(bool robotStarted READ robotStarted NOTIFY viewChanged)
  Q_PROPERTY(bool plantAtStart READ plantAtStart NOTIFY viewChanged)
  Q_PROPERTY(bool counterpartAtStart READ counterpartAtStart NOTIFY viewChanged)
  Q_PROPERTY(bool counterpartRunning READ counterpartRunning NOTIFY viewChanged)
  Q_PROPERTY(QStringList physicalSides READ physicalSides NOTIFY viewChanged)
  Q_PROPERTY(double minimumSpeedScale READ minimumSpeedScale NOTIFY viewChanged)
  Q_PROPERTY(double speedScale READ speedScale NOTIFY viewChanged)
  // The validate-then-run phase in progress, as the operator reads it; empty
  // when none is (ConsoleState.phase, ADR-0073).
  Q_PROPERTY(QString validationPhase READ validationPhase NOTIFY viewChanged)

  // The twin's mode, as the twin boundary publishes it (ADR-0044: L7 reads
  // L5's published state).
  Q_PROPERTY(QString twinMode READ twinMode NOTIFY twinModeChanged)
  // A physical side runs and the twin is not known to be in SIM: something
  // may reach the real arm. Abnormal, for the panel's colour; never a gate.
  Q_PROPERTY(bool physicalCommanded READ physicalCommanded NOTIFY healthChanged)

  // What the buttons may do: `enabled_for`, and nothing else.
  Q_PROPERTY(bool startRobotEnabled READ startRobotEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool homeEnabled READ homeEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool startProgramEnabled READ startProgramEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool stopEnabled READ stopEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool confirmEnabled READ confirmEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool validateThenRunEnabled READ validateThenRunEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool validateThenRunOffered READ validateThenRunOffered NOTIFY viewChanged)
  Q_PROPERTY(QVariantList speedChoices READ speedChoices CONSTANT)
  Q_PROPERTY(QVariantList speedChoicesEnabled READ speedChoicesEnabled NOTIFY viewChanged)
  // The same choices for the twin target, whose floor ValidateThenRun applies
  // to both of its phases.
  Q_PROPERTY(
    QVariantList twinSpeedChoicesEnabled READ twinSpeedChoicesEnabled NOTIFY viewChanged)
  // The real arm's floor applies to the selected target (`floor_applies`).
  Q_PROPERTY(bool floorApplies READ floorApplies NOTIFY viewChanged)
  // Where the signal goes (ADR-0072): the choices by name, which of them the
  // console serves, and the index of the selected one (-1 for none).
  Q_PROPERTY(QStringList targetChoices READ targetChoices CONSTANT)
  Q_PROPERTY(QVariantList targetChoicesEnabled READ targetChoicesEnabled NOTIFY viewChanged)
  Q_PROPERTY(int selectedTarget READ selectedTarget NOTIFY viewChanged)

  // The view buttons (ADR-0071): the 3D view's camera, moved by the window's
  // CameraTracking. Enabled whenever the configuration gave the panel what each
  // needs; they move no robot, so neither the console's state nor its absence
  // touches them.
  Q_PROPERTY(bool resetViewEnabled READ resetViewEnabled NOTIFY viewChanged)
  Q_PROPERTY(QStringList viewPresets READ viewPresets NOTIFY viewChanged)
  Q_PROPERTY(bool followEnabled READ followEnabled NOTIFY viewChanged)
  // What is wrong with the view buttons: their configuration, or the last
  // request the window refused or did not answer. Never the console's.
  Q_PROPERTY(QString viewError READ viewError NOTIFY viewChanged)

  // Each side's connection (health.hpp), a monitoring display only.
  Q_PROPERTY(bool healthShown READ healthShown NOTIFY healthChanged)
  Q_PROPERTY(QString boundaryLink READ boundaryLink NOTIFY healthChanged)
  // One map per side: name, link, abnormal, physical, stationary, why. `link`
  // is "live", "stale", "absent", "not ready" or "not started"; `abnormal` is
  // `link_abnormal`.
  Q_PROPERTY(QVariantList sideHealth READ sideHealth NOTIFY healthChanged)

  // The last request's progress and how it ended.
  Q_PROPERTY(QString progress READ progress NOTIFY progressChanged)
  Q_PROPERTY(QString outcome READ outcome NOTIFY outcomeChanged)

public:
  CellConsole();
  ~CellConsole() override;

  void LoadConfig(const tinyxml2::XMLElement * plugin_element) override;

  bool heard() const {return selection_.view().heard;}
  QString configError() const {return config_error_;}
  QString stateName() const {return state_name_;}
  bool faulted() const {return selection_.view().heard && selection_.view().phase == Phase::FAULT;}
  QString step() const {return step_;}
  QString prompt() const {return prompt_;}
  QString lastError() const {return last_error_;}
  bool robotStarted() const {return selection_.view().robot_started;}
  bool plantAtStart() const {return selection_.view().plant_at_start;}
  bool counterpartAtStart() const {return selection_.view().counterpart_at_start;}
  bool counterpartRunning() const {return counterpart_running(selection_.view());}
  QStringList physicalSides() const {return physical_sides_;}
  double minimumSpeedScale() const {return selection_.view().minimum_speed_scale;}
  double speedScale() const {return speed_scale_;}
  QString validationPhase() const;
  QString twinMode() const {return QString::fromStdString(boundary_.twin_mode_name());}
  bool physicalCommanded() const;
  bool startRobotEnabled() const {return selection_.buttons().start_robot;}
  bool homeEnabled() const {return selection_.buttons().home;}
  bool startProgramEnabled() const {return selection_.buttons().start_program;}
  bool stopEnabled() const {return selection_.buttons().stop;}
  bool confirmEnabled() const {return selection_.buttons().confirm;}
  bool validateThenRunEnabled() const {return selection_.buttons().validate_then_run;}
  bool validateThenRunOffered() const
  {
    return selection_.view().heard && selection_.view().validate_then_run_offered;
  }
  QVariantList speedChoices() const;
  QVariantList speedChoicesEnabled() const;
  QVariantList twinSpeedChoicesEnabled() const;
  bool floorApplies() const {return floor_applies(selection_.view(), selection_.selected());}
  QStringList targetChoices() const;
  QVariantList targetChoicesEnabled() const;
  int selectedTarget() const;
  bool resetViewEnabled() const {return static_cast<bool>(camera_);}
  QStringList viewPresets() const;
  bool followEnabled() const {return camera_ && !view_config_.follow_target.empty();}
  QString viewError() const;
  bool healthShown() const {return view_config_.heartbeat_stale_after_s > 0.0;}
  QString boundaryLink() const;
  QVariantList sideHealth() const;
  QString progress() const {return progress_;}
  QString outcome() const {return outcome_;}

  /// Select `ALL_TARGETS[index]`; ignored unless the console serves it.
  Q_INVOKABLE void selectTarget(int index);
  Q_INVOKABLE void startRobot();
  Q_INVOKABLE void home(double speed_scale);
  Q_INVOKABLE void startProgram(double speed_scale, int cycles);
  Q_INVOKABLE void validateThenRun(double speed_scale, int cycles);
  Q_INVOKABLE void stop();
  Q_INVOKABLE void confirm();
  Q_INVOKABLE void resetView();
  /// Move to `viewPresets[index]`; ignored for an index it does not have.
  Q_INVOKABLE void selectPreset(int index);
  Q_INVOKABLE void followRobot();

signals:
  void viewChanged();
  void twinModeChanged();
  void healthChanged();
  void progressChanged();
  void outcomeChanged();

private:
  void apply_state(
    const cite_interfaces::msg::ConsoleState & state, const std::vector<std::uint8_t> & publisher);
  void forget_state();
  void set_progress(const QString & text);
  void set_outcome(const QString & text);
  /// The heartbeat as heard now, its age read off `last_heartbeat_`.
  HeartbeatView heartbeat_now() const;
  /// Re-read the heartbeat's age; notify only if what is shown changed.
  void refresh_health();

  std::unique_ptr<ConsoleClient> client_;
  std::unique_ptr<CameraClient> camera_;
  CameraPose home_camera_pose_;
  ViewConfig view_config_;
  /// What is wrong with the view buttons' configuration, from LoadConfig.
  QString view_config_error_;
  /// The last view request the window refused or did not answer; cleared by
  /// one it carried out.
  QString view_request_error_;
  PanelSelection selection_;
  QString config_error_;
  QString state_name_;
  QString step_;
  QString prompt_;
  QString last_error_;
  QStringList physical_sides_;
  double speed_scale_{0.0};
  /// The twin boundary's mode and sides, each forgotten only when its own
  /// publisher leaves (health.hpp `BoundaryState`).
  BoundaryState boundary_;
  bool heartbeat_present_{false};
  bool heartbeat_heard_{false};
  QElapsedTimer last_heartbeat_;
  QTimer health_timer_;
  /// What the health display last showed, to notify only on a change.
  Link shown_boundary_{Link::ABSENT};
  QString progress_;
  QString outcome_;
};

}  // namespace cite_console_gui

#endif  // CELL_CONSOLE_HPP_
