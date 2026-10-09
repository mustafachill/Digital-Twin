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
// (enablement.hpp), which target stays selected is `settled_selection`, and
// every refusal is the console's own. The operator's selected target (ADR-0072)
// is held in `PanelSelection` (selection.hpp), not here and not in QML, so that
// the sequences that keep or clear it are the tested ones. Everything ROS is
// in `ConsoleClient`, on a thread of its own; each thing it hears is queued onto
// this object's (the Qt) thread, so no property is touched from two threads and
// nothing on the Qt thread ever waits for the graph.
//
// Its names are this plugin's XML parameters, written by the generated GUI
// configuration (generate/gui.py) under the keys of the plan's `console:` block.
// A configuration missing any of them is reported in the panel, and the panel
// stays disabled: a guessed name is a panel that commands nothing.

#ifndef CELL_CONSOLE_HPP_
#define CELL_CONSOLE_HPP_

#include <QString>
#include <QStringList>
#include <QVariantList>

#include <memory>
#include <cstdint>
#include <string>
#include <vector>

#include <gz/gui/Plugin.hh>

#include "cite_console_gui/console_client.hpp"
#include "cite_console_gui/enablement.hpp"
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

  // The twin's mode, as the twin boundary publishes it (ADR-0044: L7 reads
  // L5's published state).
  Q_PROPERTY(QString twinMode READ twinMode NOTIFY twinModeChanged)

  // What the buttons may do: `enabled_for`, and nothing else.
  Q_PROPERTY(bool startRobotEnabled READ startRobotEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool homeEnabled READ homeEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool startProgramEnabled READ startProgramEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool stopEnabled READ stopEnabled NOTIFY viewChanged)
  Q_PROPERTY(bool confirmEnabled READ confirmEnabled NOTIFY viewChanged)
  Q_PROPERTY(QVariantList speedChoices READ speedChoices CONSTANT)
  Q_PROPERTY(QVariantList speedChoicesEnabled READ speedChoicesEnabled NOTIFY viewChanged)
  // Where the signal goes (ADR-0072): the choices by name, which of them the
  // console serves, and the index of the selected one (-1 for none).
  Q_PROPERTY(QStringList targetChoices READ targetChoices CONSTANT)
  Q_PROPERTY(QVariantList targetChoicesEnabled READ targetChoicesEnabled NOTIFY viewChanged)
  Q_PROPERTY(int selectedTarget READ selectedTarget NOTIFY viewChanged)

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
  QString twinMode() const {return twin_mode_;}
  bool startRobotEnabled() const {return selection_.buttons().start_robot;}
  bool homeEnabled() const {return selection_.buttons().home;}
  bool startProgramEnabled() const {return selection_.buttons().start_program;}
  bool stopEnabled() const {return selection_.buttons().stop;}
  bool confirmEnabled() const {return selection_.buttons().confirm;}
  QVariantList speedChoices() const;
  QVariantList speedChoicesEnabled() const;
  QStringList targetChoices() const;
  QVariantList targetChoicesEnabled() const;
  int selectedTarget() const;
  QString progress() const {return progress_;}
  QString outcome() const {return outcome_;}

  /// Select `ALL_TARGETS[index]`; ignored unless the console serves it.
  Q_INVOKABLE void selectTarget(int index);
  Q_INVOKABLE void startRobot();
  Q_INVOKABLE void home(double speed_scale);
  Q_INVOKABLE void startProgram(double speed_scale, int cycles);
  Q_INVOKABLE void stop();
  Q_INVOKABLE void confirm();

signals:
  void viewChanged();
  void twinModeChanged();
  void progressChanged();
  void outcomeChanged();

private:
  void apply_state(
    const cite_interfaces::msg::ConsoleState & state, const std::vector<std::uint8_t> & publisher);
  void forget_state();
  void set_progress(const QString & text);
  void set_outcome(const QString & text);

  std::unique_ptr<ConsoleClient> client_;
  PanelSelection selection_;
  QString config_error_;
  QString state_name_;
  QString step_;
  QString prompt_;
  QString last_error_;
  QStringList physical_sides_;
  double speed_scale_{0.0};
  QString twin_mode_;
  QString progress_;
  QString outcome_;
};

}  // namespace cite_console_gui

#endif  // CELL_CONSOLE_HPP_
