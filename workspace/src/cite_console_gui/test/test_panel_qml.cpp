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

// The panel's QML, instantiated as gz-gui instantiates it (ADR-0071 decision 5).
//
// Every other test of this package tests what the panel computes; none of them
// ever loaded the QML, so a panel that gz-gui could not instantiate at all -
// `Cannot assign a value to a signal`, for a theme colour named `on<Upper>`
// (T-01) - passed every gate, and the window showed no panel and no Stop.
//
// This test loads the QML from the plugin library's own embedded resource, into
// a context whose `CellConsole` is the real plugin object, the way gz-gui's
// `Plugin::Load` does: a context property named after the plugin's filename.
// The plugin is built without `LoadConfig`, so it is what a window shows before
// the console is heard: no ROS, no gz transport. It fails on any component error
// and on any warning the engine reports while creating and laying the item out,
// headlessly (`offscreen` platform, `software` Quick backend).
//
// The frame (ADR-0074) is laid out at every supported window size and held to
// its rules: every command in the deck and inside the window, none hidden by
// another, nothing clickable in the header or the rail, and the middle of the
// 3D view taking no input. What it cannot hold is the real card's mouse
// pass-through and the toolbar hiding: neither gz-gui card nor main window
// exists here. It also writes a picture of the frame at each size, for a
// person to judge; that part is not a gate.

#include <gtest/gtest.h>
#include <gz/msgs/world_stats.pb.h>
#include <tinyxml2.h>
#include <unistd.h>

#include <QByteArray>
#include <QDir>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QImage>
#include <QGuiApplication>
#include <QList>
#include <QObject>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlError>
#include <QPointF>
#include <QQuickItem>
#include <QQuickWindow>
#include <QQuickItemGrabResult>
#include <QRectF>
#include <QSignalSpy>
#include <QSizeF>
#include <QTimer>
#include <QString>
#include <QStringList>
#include <QTest>
#include <QtGlobal>
#include <QUrl>
#include <QVariant>

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <utility>
#include <memory>
#include <string>
#include <vector>

#include <gz/transport/Node.hh>

#include "../src/cell_console.hpp"
#include "cell_console_test_access.hpp"
#include "cite_interfaces/msg/console_state.hpp"
#include "cite_interfaces/msg/twin_mode.hpp"


namespace
{

// The resource gz-gui loads for `<plugin filename="CellConsole">`, named as
// gz-gui names it: a resource PATH, not a `qrc:` URL. The difference is not
// cosmetic - under a `qrc:` URL the file's own directory is an implicit import,
// its type `CellConsole` shadows the context property, and every binding reads
// undefined.
const char kPanel[] = ":/CellConsole/CellConsole.qml";

QStringList describe(const QList<QQmlError> & errors)
{
  QStringList lines;
  for (const QQmlError & error : errors) {
    lines << error.toString();
  }
  return lines;
}

}  // namespace

TEST(PanelQml, TheEmbeddedPanelInstantiatesWithoutAnyError)
{
  QStringList warnings;
  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  QObject::connect(
    &engine, &QQmlEngine::warnings, [&warnings](const QList<QQmlError> & errors) {
      warnings << describe(errors);
    });
  QQmlContext context(engine.rootContext());
  context.setContextProperty("CellConsole", &plugin);

  QQmlComponent component(&engine, QString(kPanel));
  ASSERT_FALSE(component.isError()) << describe(component.errors()).join("\n").toStdString();
  ASSERT_TRUE(component.isReady()) << "the panel's resource is not loaded synchronously";

  std::unique_ptr<QObject> created(component.create(&context));
  ASSERT_FALSE(component.isError()) << describe(component.errors()).join("\n").toStdString();
  ASSERT_NE(created, nullptr) << "the panel was not instantiated";
  auto * item = qobject_cast<QQuickItem *>(created.get());
  ASSERT_NE(item, nullptr) << "the panel's root is not a QQuickItem, which gz-gui requires";

  // What is queued while the item is built - bindings, the layout - runs here.
  QCoreApplication::processEvents();
  EXPECT_TRUE(warnings.isEmpty()) << warnings.join("\n").toStdString();
}

namespace
{

// The window sizes the frame is laid out for (ADR-0074): the primary display
// first, down to the smallest supported.
struct WindowSize
{
  int width;
  int height;
};
const WindowSize kSizes[] = {{1920, 1080}, {1600, 900}, {1366, 768}, {1280, 720}};

/// Every console and view button the deck must hold, by objectName.
const char * const kDeckButtons[] = {
  "startRobotButton", "homeButton", "startProgramButton", "validateThenRunButton",
  "stopButton", "resetViewButton", "followButton"};

const char kStopLabel[] = "Stop — software stop, not an E-stop";

bool is_button(const QQuickItem * item)
{
  for (const QMetaObject * meta = item->metaObject(); meta != nullptr;
    meta = meta->superClass())
  {
    if (std::strcmp(meta->className(), "QQuickAbstractButton") == 0) {
      return true;
    }
  }
  return false;
}

/// Every item under `root`, depth first.
QList<QQuickItem *> descendants(QQuickItem * root)
{
  QList<QQuickItem *> all;
  for (QQuickItem * child : root->childItems()) {
    all << child;
    all << descendants(child);
  }
  return all;
}

/// Whether `item` and every ancestor up to `root` is visible.
bool shown(QQuickItem * item, QQuickItem * root)
{
  for (QQuickItem * at = item; at != nullptr && at != root; at = at->parentItem()) {
    if (!at->isVisible() || at->opacity() <= 0.0) {
      return false;
    }
  }
  return true;
}

QRectF rect_in(QQuickItem * item, QQuickItem * root)
{
  return item->mapRectToItem(root, QRectF(0.0, 0.0, item->width(), item->height()));
}

/// What of `item` is on screen: its rectangle, less what any clipping
/// ancestor cuts away.
QRectF visible_rect(QQuickItem * item, QQuickItem * root)
{
  QRectF rect = rect_in(item, root);
  for (QQuickItem * at = item->parentItem(); at != nullptr && at != root; at = at->parentItem()) {
    if (at->clip()) {
      rect = rect.intersected(rect_in(at, root));
    }
  }
  return rect;
}

std::string describe(const QRectF & rect)
{
  return "(" + std::to_string(rect.x()) + ", " + std::to_string(rect.y()) + ", " +
         std::to_string(rect.width()) + "x" + std::to_string(rect.height()) + ")";
}

/// The panel, laid out in a window of its own at one size, as gz-gui's card
/// would put it: filling the 3D view.
class Framed
{
public:
  explicit Framed(const WindowSize & size)
  {
    QObject::connect(
      &engine, &QQmlEngine::warnings, [this](const QList<QQmlError> & errors) {
        warnings << describe(errors);
      });
    context = std::make_unique<QQmlContext>(engine.rootContext());
    context->setContextProperty("CellConsole", &plugin);
    window.resize(size.width, size.height);
    QQmlComponent component(&engine, QString(kPanel));
    EXPECT_TRUE(component.isReady()) << describe(component.errors()).join("\n").toStdString();
    created.reset(component.beginCreate(context.get()));
    panel = qobject_cast<QQuickItem *>(created.get());
    if (panel == nullptr) {
      ADD_FAILURE() << describe(component.errors()).join("\n").toStdString();
      return;
    }
    panel->setParentItem(window.contentItem());
    component.completeCreate();
    window.show();
    QCoreApplication::processEvents();
  }

  /// The item named `name`: by QObject child, or, for one a Repeater made,
  /// by visual descendant.
  QQuickItem * find(const char * name) const
  {
    if (auto * item = panel->findChild<QQuickItem *>(name)) {
      return item;
    }
    for (QQuickItem * item : descendants(panel)) {
      if (item->objectName() == QLatin1String(name)) {
        return item;
      }
    }
    return nullptr;
  }

  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  std::unique_ptr<QQmlContext> context;
  QQuickWindow window;
  std::unique_ptr<QObject> created;
  QQuickItem * panel{nullptr};
  QStringList warnings;
};

/// Where the frame's header ends, in the panel's coordinates.
double Theme_header_bottom(QQuickItem * panel)
{
  for (QQuickItem * child : panel->childItems()) {
    if (QString(child->metaObject()->className()).startsWith("HeaderBar")) {
      return rect_in(child, panel).bottom();
    }
  }
  ADD_FAILURE() << "the frame has no header";
  return 0.0;
}

std::string size_name(const WindowSize & size)
{
  return std::to_string(size.width) + "x" + std::to_string(size.height);
}

}  // namespace

// gz-gui puts the panel's root in a card the generated configuration anchors
// to the 3D view's four edges. A root that neither fills its parent nor has an
// implicit size is 0x0 there, and the rail is laid out with no height at all.
TEST(PanelQml, ThePanelFillsTheCardItIsPutIn)
{
  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  QQmlContext context(engine.rootContext());
  context.setContextProperty("CellConsole", &plugin);

  QQuickItem card;
  card.setSize(QSizeF(1280.0, 720.0));

  QQmlComponent component(&engine, QString(kPanel));
  ASSERT_TRUE(component.isReady()) << describe(component.errors()).join("\n").toStdString();
  std::unique_ptr<QObject> created(component.beginCreate(&context));
  auto * panel = qobject_cast<QQuickItem *>(created.get());
  ASSERT_NE(panel, nullptr) << describe(component.errors()).join("\n").toStdString();
  panel->setParentItem(&card);
  component.completeCreate();
  QCoreApplication::processEvents();

  EXPECT_DOUBLE_EQ(panel->width(), 1280.0) << "the panel does not fill its card";
  EXPECT_DOUBLE_EQ(panel->height(), 720.0) << "the panel does not fill its card";
  auto * body = panel->findChild<QQuickItem *>("body");
  ASSERT_NE(body, nullptr) << "the panel has no item named `body`";
  EXPECT_GT(body->height(), 200.0) << "the rail is laid out with no room";
}

// The frame at every supported size (ADR-0074): every command in the deck and
// inside the window, none overlapping another, Stop and the console's
// question never scrolled; nothing clickable in the header or the rail; and
// the middle of the 3D view taking no input, so the scene gets the mouse.
TEST(PanelQml, TheFrameHoldsEveryCommandInItsDeckAtEverySize)
{
  for (const WindowSize & size : kSizes) {
    SCOPED_TRACE(size_name(size));
    Framed framed(size);
    ASSERT_NE(framed.panel, nullptr);
    QQuickItem * panel = framed.panel;
    const QRectF window(0.0, 0.0, size.width, size.height);
    EXPECT_DOUBLE_EQ(panel->width(), size.width);
    EXPECT_DOUBLE_EQ(panel->height(), size.height);

    auto * commands = framed.find("commands");
    auto * confirmation = framed.find("confirmation");
    auto * body = framed.find("body");
    ASSERT_NE(commands, nullptr) << "the panel has no item named `commands`";
    ASSERT_NE(confirmation, nullptr) << "the panel has no item named `confirmation`";
    ASSERT_NE(body, nullptr) << "the panel has no item named `body`";

    // The console's question is shown only while it asks; no console is heard
    // here, so it is shown by hand to see where it would be.
    confirmation->setVisible(true);
    QCoreApplication::processEvents();

    for (const char * name : kDeckButtons) {
      auto * item = framed.find(name);
      ASSERT_NE(item, nullptr) << "the panel has no item named `" << name << "`";
      EXPECT_TRUE(commands->isAncestorOf(item)) << name << " is not in the command deck";
      EXPECT_FALSE(body->isAncestorOf(item)) << name << " is inside the scrolled rail";
      EXPECT_TRUE(shown(item, panel)) << name << " is not visible";
      const QRectF rect = rect_in(item, panel);
      EXPECT_GT(rect.width(), 0.0) << name;
      EXPECT_GT(rect.height(), 0.0) << name;
      EXPECT_TRUE(window.contains(rect)) << name << " at " << describe(rect) << " is outside";
    }
    EXPECT_FALSE(body->isAncestorOf(confirmation)) << "the question is inside the scrolled rail";
    EXPECT_TRUE(window.contains(rect_in(confirmation, panel)))
      << "the question at " << describe(rect_in(confirmation, panel)) << " is outside";
    EXPECT_LE(rect_in(confirmation, panel).bottom(), rect_in(commands, panel).top() + 0.5)
      << "the question is not above the deck";

    // Every clickable item: in the deck or the question, inside the window,
    // and overlapping no other.
    QList<QQuickItem *> buttons;
    for (QQuickItem * item : descendants(panel)) {
      if (!is_button(item) || !shown(item, panel)) {
        continue;
      }
      EXPECT_TRUE(commands->isAncestorOf(item) || confirmation->isAncestorOf(item))
        << "a clickable " << item->metaObject()->className() << " '"
        << item->property("text").toString().toStdString()
        << "' is outside the deck and the question";
      EXPECT_TRUE(window.contains(rect_in(item, panel)))
        << "'" << item->property("text").toString().toStdString() << "' at "
        << describe(rect_in(item, panel)) << " is outside the window";
      EXPECT_EQ(visible_rect(item, panel), rect_in(item, panel))
        << "'" << item->property("text").toString().toStdString() << "' is clipped";
      buttons << item;
    }
    EXPECT_GE(buttons.size(), 7);
    for (int a = 0; a < buttons.size(); ++a) {
      for (int b = a + 1; b < buttons.size(); ++b) {
        if (buttons[a]->isAncestorOf(buttons[b]) || buttons[b]->isAncestorOf(buttons[a])) {
          continue;
        }
        const QRectF overlap =
          rect_in(buttons[a], panel).intersected(rect_in(buttons[b], panel));
        EXPECT_TRUE(overlap.width() < 0.5 || overlap.height() < 0.5)
          << "'" << buttons[a]->property("text").toString().toStdString() << "' overlaps '"
          << buttons[b]->property("text").toString().toStdString() << "'";
      }
    }

    // The middle of the 3D view: nothing there takes the mouse.
    const QRectF rail = rect_in(body, panel);
    const double top = rect_in(framed.find("viewLabel"), panel).bottom();
    const QPointF middle(rail.left() / 2.0, (top + rect_in(confirmation, panel).top()) / 2.0);
    for (QQuickItem * item : descendants(panel)) {
      if (!shown(item, panel) || item->acceptedMouseButtons() == Qt::NoButton) {
        continue;
      }
      EXPECT_FALSE(rect_in(item, panel).contains(middle))
        << "a " << item->metaObject()->className() << " at " << describe(rect_in(item, panel))
        << " takes the mouse in the middle of the 3D view";
    }
    EXPECT_EQ(panel->acceptedMouseButtons(), Qt::NoButton) << "the frame's root takes the mouse";

    // The opaque parts take it, so the wheel does not zoom the scene through
    // them: the header's and the rail's middles, and the deck's corner.
    for (const QPointF & point : {
      QPointF(size.width / 2.0, 20.0), QPointF(rail.center().x(), rail.bottom() - 4.0),
      QPointF(4.0, size.height - 4.0)})
    {
      bool taken = false;
      for (QQuickItem * item : descendants(panel)) {
        if (shown(item, panel) && item->acceptedMouseButtons() != Qt::NoButton &&
          rect_in(item, panel).contains(point))
        {
          taken = true;
        }
      }
      EXPECT_TRUE(taken) << "nothing takes the mouse at (" << point.x() << ", " << point.y()
                         << "), over the frame";
    }

    // No caveat text beside Validate then run (ADR-0073 decision 5, amended
    // 2026-10-15).
    EXPECT_EQ(framed.find("validateThenRunCaveat"), nullptr) << "the caveat is back";

    // Stop: its label exactly (ADR-0071 decision 4).
    auto * stop = framed.find("stopButton");
    ASSERT_NE(stop, nullptr);
    EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));

    // The target: with no console heard, nothing to select and nothing
    // selected; the hint is for a heard console only (ADR-0072 decision 3).
    EXPECT_FALSE(framed.find("targetHint")->isVisible()) << "a hint with no console";
    auto * target = framed.find("targetSelector");
    ASSERT_NE(target, nullptr) << "the panel has no item named `targetSelector`";
    int targets = 0;
    for (QQuickItem * item : descendants(target)) {
      if (is_button(item)) {
        ++targets;
        EXPECT_FALSE(item->property("selected").toBool())
          << "the target '" << item->property("text").toString().toStdString()
          << "' is selected with no console";
      }
    }
    EXPECT_EQ(targets, 3);

    // The speed: the program's own, 1.0, preselected (ADR-0071 decision 2).
    auto * speed = framed.find("speedSelector");
    ASSERT_NE(speed, nullptr) << "the panel has no item named `speedSelector`";
    QStringList checked;
    for (QQuickItem * item : descendants(speed)) {
      if (is_button(item) && item->property("selected").toBool()) {
        checked << item->property("text").toString();
      }
    }
    EXPECT_EQ(checked, QStringList{QString::fromUtf8("1.0×")});

    // With no console heard, every console button is disabled.
    for (const char * name :
      {"startRobotButton", "homeButton", "startProgramButton", "validateThenRunButton",
        "stopButton"})
    {
      EXPECT_FALSE(framed.find(name)->isEnabled()) << name << " is enabled with no console";
    }

    QCoreApplication::processEvents();
    EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
  }
}

// Below the smallest supported size the deck runs short, but never Stop: it
// stays inside the window and clear of every other control.
TEST(PanelQml, StopStaysOnScreenBelowTheSupportedSizes)
{
  for (const WindowSize & size : {WindowSize{1024, 600}, WindowSize{800, 600}}) {
    SCOPED_TRACE(size_name(size));
    Framed framed(size);
    ASSERT_NE(framed.panel, nullptr);
    auto * stop = framed.find("stopButton");
    ASSERT_NE(stop, nullptr);
    const QRectF stop_rect = rect_in(stop, framed.panel);
    EXPECT_TRUE(shown(stop, framed.panel));
    EXPECT_TRUE(QRectF(0.0, 0.0, size.width, size.height).contains(stop_rect))
      << "Stop at " << describe(stop_rect) << " is outside the window";
    for (QQuickItem * item : descendants(framed.panel)) {
      if (item == stop || stop->isAncestorOf(item) || !is_button(item) ||
        !shown(item, framed.panel))
      {
        continue;
      }
      const QRectF overlap = visible_rect(item, framed.panel).intersected(stop_rect);
      EXPECT_TRUE(overlap.width() < 0.5 || overlap.height() < 0.5)
        << "'" << item->property("text").toString().toStdString() << "' overlaps Stop";
    }
  }
}

namespace
{

/// A left click at the centre of `item`, as the window would deliver it.
void click(QQuickWindow & window, QQuickItem * item)
{
  const QPointF centre = item->mapToScene(QPointF(item->width() / 2.0, item->height() / 2.0));
  QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier, centre.toPoint());
  QCoreApplication::processEvents();
}

/// The segments of a `SegmentedSelector`, in order.
QList<QQuickItem *> segments(QQuickItem * selector)
{
  QList<QQuickItem *> found;
  for (QQuickItem * item : descendants(selector)) {
    if (is_button(item)) {
      found << item;
    }
  }
  return found;
}

/// A console READY to run on the simulation alone, as `cell_console` says it:
/// Start robot succeeded for the simulation (ADR-0075).
cite_interfaces::msg::ConsoleState ready_on_the_simulation()
{
  cite_interfaces::msg::ConsoleState state;
  state.state = cite_interfaces::msg::ConsoleState::READY;
  state.robot_started = true;
  state.plant_at_start = true;
  state.available_targets = {cite_interfaces::msg::ConsoleState::TARGET_SIM};
  state.started_targets = {cite_interfaces::msg::ConsoleState::TARGET_SIM};
  state.startable_targets = {cite_interfaces::msg::ConsoleState::TARGET_SIM};
  state.twin_mode = cite_interfaces::msg::TwinMode::MODE_SIM;
  state.step = "ok";
  return state;
}

}  // namespace

// T-01: the deck shows the plugin's selection, never the click. A click on the
// segment already selected leaves it shown selected, for the target and the
// speed alike; the highlight follows the property, whatever was clicked.
TEST(PanelQml, ASegmentShowsTheSelectionNotTheClick)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, ready_on_the_simulation());
  QCoreApplication::processEvents();

  for (const char * name : {"targetSelector", "speedSelector"}) {
    SCOPED_TRACE(name);
    auto * selector = framed.find(name);
    ASSERT_NE(selector, nullptr);
    const QList<QQuickItem *> choices = segments(selector);
    ASSERT_GE(choices.size(), 2);
    ASSERT_TRUE(choices[0]->isEnabled());
    // The simulation and the program's speed are preselected; a click on
    // the segment already selected leaves it so.
    for (int again = 0; again < 3; ++again) {
      click(framed.window, choices[0]);
      EXPECT_EQ(selector->property("checkedIndex").toInt(), 0) << "click " << again + 1;
      EXPECT_TRUE(choices[0]->property("selected").toBool())
        << "the selection in force is not shown after click " << again + 1;
    }
    // The owner of the selection says another: the highlight follows it.
    selector->setProperty("checkedIndex", 1);
    QCoreApplication::processEvents();
    EXPECT_FALSE(choices[0]->property("selected").toBool());
    EXPECT_TRUE(choices[1]->property("selected").toBool());
    // AbstractButton's own `checked` is never what is drawn, and never set.
    for (QQuickItem * choice : choices) {
      EXPECT_FALSE(choice->property("checked").toBool());
    }
  }
}

namespace
{

/// Whether the target segment named `label` is shown selected.
bool target_shown_selected(Framed & framed, const char * label)
{
  for (QQuickItem * item : segments(framed.find("targetSelector"))) {
    if (item->property("text").toString() == QLatin1String(label)) {
      return item->property("selected").toBool();
    }
  }
  ADD_FAILURE() << "no target segment '" << label << "'";
  return false;
}

}  // namespace

// ADR-0072 decision 3, amended 2026-10-15: where the console serves the
// simulation, the panel opens with it selected, and never the real arm or
// the twin; the operator is not asked to pick and Start robot may be sent.
TEST(PanelQml, WithTheSimulationServedItIsSelectedAndNothingElse)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.available_targets = {
    cite_interfaces::msg::ConsoleState::TARGET_SIM, cite_interfaces::msg::ConsoleState::TARGET_REAL,
    cite_interfaces::msg::ConsoleState::TARGET_TWIN};
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  QCoreApplication::processEvents();

  EXPECT_EQ(framed.find("targetSelector")->property("checkedIndex").toInt(), 0);
  EXPECT_TRUE(target_shown_selected(framed, "Simulation"));
  EXPECT_FALSE(target_shown_selected(framed, "Real arm"));
  EXPECT_FALSE(target_shown_selected(framed, "Twin"));
  EXPECT_TRUE(framed.find("startRobotButton")->isEnabled());
  EXPECT_FALSE(framed.find("targetHint")->isVisible()) << "the hint with a target selected";
  EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
}

// Without the simulation nothing is preselected: Start robot waits, and the
// deck says "Select a target", inside the deck and near the selector, at
// every size. A pick takes the hint away.
TEST(PanelQml, WithoutTheSimulationTheDeckAsksForATargetUntilOneIsPicked)
{
  for (const WindowSize & size : kSizes) {
    SCOPED_TRACE(size_name(size));
    Framed framed(size);
    ASSERT_NE(framed.panel, nullptr);
    cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
    state.state = cite_interfaces::msg::ConsoleState::NOT_STARTED;
    state.robot_started = false;
    state.available_targets = {cite_interfaces::msg::ConsoleState::TARGET_REAL};
    state.started_targets = {};
    state.startable_targets = {};
    cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
    QCoreApplication::processEvents();

    auto * hint = framed.find("targetHint");
    auto * commands = framed.find("commands");
    auto * selector = framed.find("targetSelector");
    ASSERT_NE(hint, nullptr) << "the panel has no item named `targetHint`";
    EXPECT_EQ(selector->property("checkedIndex").toInt(), -1);
    for (const char * label : {"Simulation", "Real arm", "Twin"}) {
      EXPECT_FALSE(target_shown_selected(framed, label)) << label << " is preselected";
    }
    EXPECT_FALSE(framed.find("startRobotButton")->isEnabled())
      << "Start robot is enabled with no target";
    EXPECT_TRUE(shown(hint, framed.panel)) << "no hint with no target";
    EXPECT_EQ(hint->property("text").toString(), QString("Select a target"));
    const QRectF hint_rect = rect_in(hint, framed.panel);
    EXPECT_TRUE(commands->isAncestorOf(hint)) << "the hint is not in the deck";
    EXPECT_TRUE(rect_in(commands, framed.panel).contains(hint_rect))
      << "the hint at " << describe(hint_rect) << " leaves the deck";
    EXPECT_EQ(visible_rect(hint, framed.panel), hint_rect) << "the hint is clipped";
    EXPECT_LE(hint->property("contentWidth").toDouble(), hint->width() + 0.5)
      << "the hint is cut short";
    const QRectF selector_rect = rect_in(selector, framed.panel);
    EXPECT_LE(hint_rect.bottom(), selector_rect.top() + 0.5) << "the hint is not above the target";
    EXPECT_LT(selector_rect.top() - hint_rect.bottom(), 24.0) << "the hint is far from the target";

    // The operator picks the real arm: Start robot may be sent, and the hint
    // in the same place now names it (ADR-0075).
    click(framed.window, segments(selector)[1]);
    EXPECT_EQ(selector->property("checkedIndex").toInt(), 1);
    EXPECT_TRUE(shown(hint, framed.panel));
    EXPECT_EQ(hint->property("text").toString(), QString("Start robot for this target"));
    EXPECT_LE(hint->property("contentWidth").toDouble(), hint->width() + 0.5)
      << "the start hint is cut short";
    EXPECT_TRUE(framed.find("startRobotButton")->isEnabled());
    EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
  }
}

// ADR-0075 decision 5: the deck follows the target. With the simulation
// started, selecting the twin enables Start robot again, disables Home until
// the twin is started, and says "Start robot for this target"; back on the
// simulation, Home is offered and the hint goes.
TEST(PanelQml, TheDeckFollowsTheSelectedTarget)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.available_targets = {
    cite_interfaces::msg::ConsoleState::TARGET_SIM, cite_interfaces::msg::ConsoleState::TARGET_REAL,
    cite_interfaces::msg::ConsoleState::TARGET_TWIN};
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  QCoreApplication::processEvents();

  auto * selector = framed.find("targetSelector");
  auto * hint = framed.find("targetHint");
  auto * start = framed.find("startRobotButton");
  auto * home = framed.find("homeButton");
  ASSERT_NE(selector, nullptr);
  ASSERT_NE(hint, nullptr);
  ASSERT_NE(start, nullptr);
  ASSERT_NE(home, nullptr);
  EXPECT_EQ(selector->property("checkedIndex").toInt(), 0);
  EXPECT_TRUE(home->isEnabled()) << "Home on the started simulation";
  EXPECT_FALSE(hint->isVisible());

  click(framed.window, segments(selector)[2]);
  EXPECT_EQ(selector->property("checkedIndex").toInt(), 2);
  EXPECT_TRUE(start->isEnabled()) << "Start robot for the twin";
  EXPECT_FALSE(home->isEnabled()) << "Home for a twin not started";
  EXPECT_FALSE(framed.find("startProgramButton")->isEnabled());
  EXPECT_TRUE(shown(hint, framed.panel));
  EXPECT_EQ(hint->property("text").toString(), QString("Start robot for this target"));

  click(framed.window, segments(selector)[0]);
  EXPECT_TRUE(home->isEnabled());
  EXPECT_FALSE(hint->isVisible());
  EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
}

// R-01: the cycles field shows the number a button would send, and no other.
// Text that is not a number in range is put back to the value at once, and a
// number in range is the value the moment it is typed.
TEST(PanelQml, TheCyclesShownAreTheCyclesSent)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  auto * deck = framed.find("commands");
  auto * input = framed.find("cyclesInput");
  ASSERT_NE(deck, nullptr);
  ASSERT_NE(input, nullptr);
  const auto shown_is_sent = [&]() {
      return input->property("text").toString() ==
             QString::number(deck->property("cycles").toInt());
    };

  input->setProperty("text", QString("3"));
  EXPECT_EQ(deck->property("cycles").toInt(), 3);
  for (const char * typed : {"", "0", "7", "-2", "1001", "12"}) {
    input->setProperty("text", QString(typed));
    QCoreApplication::processEvents();
    EXPECT_TRUE(shown_is_sent()) << "typed '" << typed << "': shown '"
                                 << input->property("text").toString().toStdString()
                                 << "', sent " << deck->property("cycles").toInt();
  }
  EXPECT_EQ(deck->property("cycles").toInt(), 12);

  // As the operator types it: the field takes focus and its text is replaced;
  // erasing it leaves the value shown, and a digit is taken at once.
  input->forceActiveFocus();
  QTest::keyClick(&framed.window, Qt::Key_Backspace);
  QCoreApplication::processEvents();
  EXPECT_TRUE(shown_is_sent()) << "erased: shown '"
                               << input->property("text").toString().toStdString() << "'";
  EXPECT_EQ(deck->property("cycles").toInt(), 12);
  QTest::keyClick(&framed.window, Qt::Key_7);
  QCoreApplication::processEvents();
  EXPECT_EQ(deck->property("cycles").toInt(), 7);
  EXPECT_TRUE(shown_is_sent());
}

namespace
{

/// A stand-in for gz-gui 8's GzCard as far as the frame touches it: a Pane
/// whose content item holds a wheel-stopping MouseArea and a right-button
/// MouseArea under a content Rectangle that offers `card()`. `%1` is whether
/// the Pane clips its children to its shape - GzCard's does not.
const char kStandInCard[] =
  R"(
import QtQuick 2.9
import QtQuick.Controls 2.2
Pane {
  id: cardPane
  padding: 0
  clip: %1
  background: Rectangle { color: "transparent" }
  MouseArea { anchors.fill: parent; onWheel: wheel.accepted = true }
  MouseArea { anchors.fill: content; acceptedButtons: Qt.RightButton }
  Rectangle {
    objectName: "content"
    id: content
    anchors.fill: parent
    clip: true
    color: "transparent"
    function card() { return cardPane; }
  }
}
)";

/// The panel inside a stand-in card, the card filling a window of 1920x1080.
class Carded
{
public:
  explicit Carded(bool clipping)
  {
    context = std::make_unique<QQmlContext>(engine.rootContext());
    context->setContextProperty("CellConsole", &plugin);
    window.resize(1920, 1080);
    QQmlComponent card_component(&engine);
    card_component.setData(
      QString::fromUtf8(kStandInCard).arg(clipping ? "true" : "false").toUtf8(), QUrl());
    card_created.reset(card_component.create(context.get()));
    card = qobject_cast<QQuickItem *>(card_created.get());
    if (card == nullptr) {
      ADD_FAILURE() << describe(card_component.errors()).join("\n").toStdString();
      return;
    }
    card->setParentItem(window.contentItem());
    card->setSize(QSizeF(1920.0, 1080.0));
    // The 3D view under the card: what takes a press the panel lets through.
    QQmlComponent scene_component(&engine);
    scene_component.setData(
      "import QtQuick 2.9\nMouseArea { property int presses: 0; onPressed: presses++ }",
      QUrl());
    scene_created.reset(scene_component.create(context.get()));
    scene = qobject_cast<QQuickItem *>(scene_created.get());
    if (scene == nullptr) {
      ADD_FAILURE() << describe(scene_component.errors()).join("\n").toStdString();
      return;
    }
    scene->setParentItem(window.contentItem());
    scene->setZ(-1.0);
    scene->setSize(QSizeF(1920.0, 1080.0));
    window.show();
    QCoreApplication::processEvents();

    QQmlComponent component(&engine, QString(kPanel));
    created.reset(component.beginCreate(context.get()));
    panel = qobject_cast<QQuickItem *>(created.get());
    if (panel == nullptr) {
      ADD_FAILURE() << describe(component.errors()).join("\n").toStdString();
      return;
    }
    // As gz-gui adds a plugin's item to its card's content.
    panel->setParentItem(card->findChild<QQuickItem *>("content"));
    component.completeCreate();
    QCoreApplication::processEvents();
    // As the plugin says once gz-gui's main window is shown with it.
    emit plugin.windowShown();
    QCoreApplication::processEvents();
  }

  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  std::unique_ptr<QQmlContext> context;
  QQuickWindow window;
  std::unique_ptr<QObject> card_created;
  std::unique_ptr<QObject> scene_created;
  std::unique_ptr<QObject> created;
  QQuickItem * card{nullptr};
  QQuickItem * scene{nullptr};
  QQuickItem * panel{nullptr};
};

/// A console running a request: Stop is enabled.
cite_interfaces::msg::ConsoleState running_a_request()
{
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.state = cite_interfaces::msg::ConsoleState::RUNNING;
  state.busy = true;
  return state;
}

/// A left click in the middle of the 3D view, as the window delivers it.
void click_the_middle(QQuickWindow & window, QQuickItem * panel)
{
  const QPointF middle = panel->mapToScene(QPointF(panel->width() / 4.0, panel->height() / 2.0));
  QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier, middle.toPoint());
  QCoreApplication::processEvents();
}

/// Whether `item` is a MouseArea that handles a press: MouseArea's own
/// `enabled`, which shadows the item's.
bool enabled_mouse_area(const QQuickItem * item)
{
  return QString(item->metaObject()->className()).startsWith("QQuickMouseArea") &&
         item->property("enabled").toBool();
}

}  // namespace

// S-02: in a card shaped like gz-gui's, the mouse is passed through to the
// scene and a press on Stop still reaches Stop.
TEST(PanelQml, InACardLikeGzGuisStopTakesItsPressAndTheMiddleIsPassedThrough)
{
  Carded carded(false);
  ASSERT_NE(carded.panel, nullptr);
  auto * stop = carded.panel->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_TRUE(carded.plugin.pressReaches(stop));
  EXPECT_NE(carded.card->property("containmentMask").value<QObject *>(), nullptr)
    << "the card was not given its empty mask";
  EXPECT_EQ(carded.panel->property("passCard").value<QObject *>(), carded.card);
  for (QQuickItem * item : descendants(carded.card)) {
    if (item != carded.panel && !carded.panel->isAncestorOf(item)) {
      EXPECT_FALSE(enabled_mouse_area(item)) << "a card MouseArea still takes the mouse";
    }
  }

  // S-01: what the judge said, held against Qt's own delivery. A real click
  // at Stop's centre, through the window, reaches the plugin's stop(); one in
  // the middle of the view reaches the scene under the card and no panel item.
  using cite_console_gui::CellConsoleTestAccess;
  CellConsoleTestAccess::hear(carded.plugin, running_a_request());
  QCoreApplication::processEvents();
  ASSERT_TRUE(stop->isEnabled());
  EXPECT_TRUE(carded.plugin.pressReaches(stop));
  click(carded.window, stop);
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(carded.plugin), 1u)
    << "a real press on Stop did not reach the plugin's stop()";
  EXPECT_EQ(carded.scene->property("presses").toInt(), 0) << "Stop's press reached the scene";
  click_the_middle(carded.window, carded.panel);
  EXPECT_EQ(carded.scene->property("presses").toInt(), 1)
    << "a press in the middle of the view did not reach the scene";
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(carded.plugin), 1u);
}

// S-02: a card that clips its children to its shape takes, once masked, every
// press from every button in it. The frame finds Stop unreachable, puts the
// card back as it was and says so: Stop over camera interaction.
TEST(PanelQml, InACardThatWouldHideStopThePassThroughIsUndone)
{
  Carded carded(true);
  ASSERT_NE(carded.panel, nullptr);
  auto * stop = carded.panel->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_EQ(carded.card->property("containmentMask").value<QObject *>(), nullptr)
    << "the mask that hides Stop was kept";
  EXPECT_EQ(carded.panel->property("passCard").value<QObject *>(), nullptr);
  EXPECT_TRUE(carded.plugin.pressReaches(stop)) << "Stop does not take its press";
  int areas = 0;
  for (QQuickItem * item : descendants(carded.card)) {
    if (item != carded.panel && !carded.panel->isAncestorOf(item) && enabled_mouse_area(item)) {
      ++areas;
    }
  }
  EXPECT_EQ(areas, 2) << "the card's own MouseAreas were not put back";

  // S-01: after the undo a real click on Stop reaches the plugin's stop().
  using cite_console_gui::CellConsoleTestAccess;
  CellConsoleTestAccess::hear(carded.plugin, running_a_request());
  QCoreApplication::processEvents();
  ASSERT_TRUE(stop->isEnabled());
  click(carded.window, stop);
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(carded.plugin), 1u)
    << "a real press on Stop did not reach the plugin's stop() after the undo";
}

namespace
{

/// A console asking the operator, with a request in progress: the question
/// is shown, and its Confirm and Cancel (Stop) with it.
cite_interfaces::msg::ConsoleState asking_the_operator()
{
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.state = cite_interfaces::msg::ConsoleState::AWAITING_OPERATOR;
  state.busy = true;
  state.prompt = "Put a work-piece on the plant's pick table, then confirm.";
  return state;
}

/// An item that takes the left button over `rect` of the window, above the card.
std::unique_ptr<QQuickItem> cover(QQuickWindow & window, const QRectF & rect)
{
  auto item = std::make_unique<QQuickItem>();
  item->setParentItem(window.contentItem());
  item->setZ(10.0);
  item->setPosition(rect.topLeft());
  item->setSize(rect.size());
  item->setAcceptedMouseButtons(Qt::LeftButton);
  return item;
}

bool passed_through(const Carded & carded)
{
  return carded.panel->property("passCard").value<QObject *>() == carded.card;
}

}  // namespace

// S-02: Stop is not the only control that stops. While the console asks, the
// question's Cancel (Stop) and Confirm are judged too, and a real click on
// each reaches the plugin.
TEST(PanelQml, WhileTheConsoleAsksCancelAndConfirmTakeTheirPresses)
{
  using cite_console_gui::CellConsoleTestAccess;
  Carded carded(false);
  ASSERT_NE(carded.panel, nullptr);
  CellConsoleTestAccess::hear(carded.plugin, asking_the_operator());
  QCoreApplication::processEvents();
  auto * banner = carded.panel->findChild<QQuickItem *>("confirmation");
  auto * cancel = carded.panel->findChild<QQuickItem *>("cancelButton");
  auto * confirm = carded.panel->findChild<QQuickItem *>("confirmButton");
  ASSERT_NE(banner, nullptr);
  ASSERT_NE(cancel, nullptr);
  ASSERT_NE(confirm, nullptr);
  ASSERT_TRUE(banner->isVisible());
  EXPECT_TRUE(passed_through(carded));
  EXPECT_TRUE(carded.plugin.pressReaches(cancel));
  EXPECT_TRUE(carded.plugin.pressReaches(confirm));
  click(carded.window, cancel);
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(carded.plugin), 1u)
    << "a real press on Cancel (Stop) did not reach the plugin's stop()";
  click(carded.window, confirm);
  EXPECT_EQ(CellConsoleTestAccess::confirms_pressed(carded.plugin), 1u)
    << "a real press on Confirm did not reach the plugin's confirm()";
}

// S-02: a question whose Cancel (Stop) a press would not reach undoes the
// pass-through when it is shown, though the deck's Stop is still reachable.
TEST(PanelQml, AQuestionWhoseCancelWouldLoseItsPressUndoesThePassThrough)
{
  using cite_console_gui::CellConsoleTestAccess;
  Carded carded(false);
  ASSERT_NE(carded.panel, nullptr);
  auto * deck = carded.panel->findChild<QQuickItem *>("commands");
  ASSERT_NE(deck, nullptr);
  ASSERT_TRUE(passed_through(carded));
  // Over the strip the question takes above the deck, and nothing of the deck.
  const double deck_top = deck->mapToScene(QPointF(0.0, 0.0)).y();
  const auto strip = cover(carded.window, QRectF(0.0, deck_top - 64.0, 1920.0, 64.0));
  QCoreApplication::processEvents();
  EXPECT_TRUE(passed_through(carded)) << "nothing that stops was covered yet";
  CellConsoleTestAccess::hear(carded.plugin, asking_the_operator());
  QCoreApplication::processEvents();
  EXPECT_FALSE(passed_through(carded))
    << "the question's Cancel (Stop) would lose its press and the pass-through was kept";
  auto * stop = carded.panel->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_TRUE(carded.plugin.pressReaches(stop));
}

// S-03: a Stop that cannot be pressed at all - its centre outside the window -
// is a failure, never a pass.
TEST(PanelQml, AStopOutsideTheWindowUndoesThePassThrough)
{
  Carded carded(false);
  ASSERT_NE(carded.panel, nullptr);
  ASSERT_TRUE(passed_through(carded));
  // The card, and the frame in it, larger than the window: Stop, at the
  // frame's bottom right, is outside it.
  carded.card->setSize(QSizeF(2600.0, 1500.0));
  QCoreApplication::processEvents();
  auto * stop = carded.panel->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_FALSE(carded.plugin.pressReaches(stop));
  EXPECT_FALSE(passed_through(carded)) << "Stop is outside the window and the pass-through stayed";
}

// S-03: the card's z and the frame's visibility change what a press reaches,
// so each is judged again: a card put under an item that takes Stop's press,
// or shown again with one over Stop, undoes the pass-through.
TEST(PanelQml, TheCardsZAndVisibilityAreJudgedAgain)
{
  {
    SCOPED_TRACE("z");
    Carded carded(false);
    ASSERT_NE(carded.panel, nullptr);
    carded.card->setZ(20.0);
    const auto over = cover(carded.window, QRectF(0.0, 0.0, 1920.0, 1080.0));
    QCoreApplication::processEvents();
    EXPECT_TRUE(passed_through(carded)) << "the card is above the item";
    carded.card->setZ(0.0);
    QCoreApplication::processEvents();
    EXPECT_FALSE(passed_through(carded)) << "the card went under an item and was not judged";
  }
  {
    SCOPED_TRACE("visibility");
    Carded carded(false);
    ASSERT_NE(carded.panel, nullptr);
    carded.card->setVisible(false);
    QCoreApplication::processEvents();
    EXPECT_TRUE(passed_through(carded)) << "a hidden frame is not judged";
    const auto over = cover(carded.window, QRectF(0.0, 0.0, 1920.0, 1080.0));
    carded.card->setVisible(true);
    QCoreApplication::processEvents();
    EXPECT_FALSE(passed_through(carded)) << "the frame was shown again and not judged";
  }
}

// R2-02: while a modal popup holds every press, nothing is judged and the
// pass-through stays; once it closes, the frame is judged again.
TEST(PanelQml, AModalPopupDefersTheJudgementUntilItCloses)
{
  Carded carded(false);
  ASSERT_NE(carded.panel, nullptr);
  ASSERT_TRUE(passed_through(carded));
  QQmlComponent popup_component(&carded.engine);
  popup_component.setData(
    "import QtQuick 2.9\nimport QtQuick.Controls 2.2\n"
    "Popup { modal: true; width: 200; height: 100; enter: Transition {} exit: Transition {} }",
    QUrl());
  std::unique_ptr<QObject> popup(popup_component.create(carded.context.get()));
  ASSERT_NE(popup, nullptr) << describe(popup_component.errors()).join("\n").toStdString();
  popup->setProperty("parent", QVariant::fromValue(carded.window.contentItem()));
  QMetaObject::invokeMethod(popup.get(), "open");
  QCoreApplication::processEvents();
  ASSERT_TRUE(popup->property("visible").toBool());
  auto * stop = carded.panel->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_NE(carded.plugin.modalOverlay(stop), nullptr);
  // A relayout while it is open: not judged, so not undone.
  carded.card->setSize(QSizeF(1900.0, 1060.0));
  QCoreApplication::processEvents();
  EXPECT_TRUE(passed_through(carded)) << "the open modal popup was judged as the layout";
  // An item over Stop, then the popup closes: judged again, and undone.
  const auto over = cover(carded.window, QRectF(0.0, 0.0, 1920.0, 1080.0));
  QMetaObject::invokeMethod(popup.get(), "close");
  QCoreApplication::processEvents();
  QCoreApplication::processEvents();
  EXPECT_EQ(carded.plugin.modalOverlay(stop), nullptr);
  EXPECT_FALSE(passed_through(carded)) << "the frame was not judged again once the popup closed";
}

// The judge itself: an item laid over Stop that takes the left button is what
// a press reaches, and one that takes no button is not.
TEST(PanelQml, APressReachesTheItemOnTopThatTakesIt)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  auto * stop = framed.find("stopButton");
  ASSERT_NE(stop, nullptr);
  EXPECT_TRUE(framed.plugin.pressReaches(stop));

  QQuickItem cover;
  cover.setParentItem(framed.window.contentItem());
  cover.setZ(10.0);
  cover.setSize(QSizeF(1920.0, 1080.0));
  EXPECT_TRUE(framed.plugin.pressReaches(stop)) << "an item that takes no button took it";
  cover.setAcceptedMouseButtons(Qt::LeftButton);
  EXPECT_FALSE(framed.plugin.pressReaches(stop)) << "the item on top was not seen";
  // A MouseArea whose own `enabled` is false is handed the press and lets it
  // go by: it does not keep the press from Stop.
  QQmlComponent area_component(&framed.engine);
  area_component.setData(
    "import QtQuick 2.9\nMouseArea { width: 1920; height: 1080; z: 11; enabled: false }",
    QUrl());
  std::unique_ptr<QObject> area_created(area_component.create(framed.context.get()));
  auto * area = qobject_cast<QQuickItem *>(area_created.get());
  ASSERT_NE(area, nullptr);
  cover.setVisible(false);
  area->setParentItem(framed.window.contentItem());
  EXPECT_TRUE(framed.plugin.pressReaches(stop)) << "a disabled MouseArea was taken for a taker";
  area->setProperty("enabled", true);
  EXPECT_FALSE(framed.plugin.pressReaches(stop)) << "an enabled MouseArea on top was not seen";
  area->setVisible(false);
  cover.setVisible(false);
  EXPECT_TRUE(framed.plugin.pressReaches(stop));
  // S-03: what cannot be pressed at all is never said to take the press.
  EXPECT_FALSE(framed.plugin.pressReaches(nullptr));
  QQuickItem sizeless;
  sizeless.setParentItem(framed.window.contentItem());
  EXPECT_FALSE(framed.plugin.pressReaches(&sizeless)) << "an item with no size";
  QQuickItem windowless;
  windowless.setSize(QSizeF(10.0, 10.0));
  EXPECT_FALSE(framed.plugin.pressReaches(&windowless)) << "an item in no window";
}

namespace
{

/// A step as long as the console may say one.
const char kLongStep[] =
  "plant: move to blockly_04 at 0.111 of full speed, then wait for the gripper to report "
  "closed on the work-piece before the track carries it to the belt's far end, where the "
  "next step opens it again";

/// Let the window lay out what changed: the layouts are polished before a
/// frame is drawn, so one is drawn.
void settle(Framed & framed)
{
  QCoreApplication::processEvents();
  framed.window.grabWindow();
  QCoreApplication::processEvents();
}

/// A console that has heard a refusal: READY, with every display the frame
/// has filled - the alarm band (a last error), a long step, the boundary live
/// with both sides, a divergence sample and the world's statistics.
void hear_everything(Framed & framed)
{
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.step = kLongStep;
  state.last_error = "refused: the counterpart is not at the program's start";
  cite_console_gui::CellConsoleTestAccess::hear_boundary(framed.plugin, "picker");
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  cite_console_gui::CellConsoleTestAccess::hear_world_stats(framed.plugin, false);
  settle(framed);
}

/// Every pair of `items` that overlaps, as text.
QStringList overlaps(const QList<QQuickItem *> & items, QQuickItem * root)
{
  QStringList found;
  for (int a = 0; a < items.size(); ++a) {
    if (!items[a]->isVisible()) {
      continue;
    }
    for (int b = a + 1; b < items.size(); ++b) {
      const QRectF overlap = rect_in(items[a], root).intersected(rect_in(items[b], root));
      if (overlap.width() >= 0.5 && overlap.height() >= 0.5) {
        found << items[a]->objectName() + " overlaps " + items[b]->objectName();
      }
    }
  }
  return found;
}

}  // namespace

// R-04, T-04: the frame with everything heard, at the primary and the smallest
// supported size. The header's pills each keep their status word and overlap
// nothing; the alarm band shows below the header; the deck's controls stay
// whole and apart; the Robot card's long step takes two lines at most.
TEST(PanelQml, WithEverythingHeardTheHeaderAndTheDeckHoldTheirRules)
{
  for (const WindowSize & size : {kSizes[0], kSizes[3]}) {
    SCOPED_TRACE(size_name(size));
    Framed framed(size);
    ASSERT_NE(framed.panel, nullptr);
    hear_everything(framed);
    QQuickItem * panel = framed.panel;
    const QRectF window(0.0, 0.0, size.width, size.height);

    // The alarm band, under the header.
    auto * alarm = framed.find("alarmBand");
    ASSERT_NE(alarm, nullptr);
    EXPECT_TRUE(shown(alarm, panel)) << "a last error and no alarm band";
    EXPECT_GE(rect_in(alarm, panel).top(), Theme_header_bottom(panel) - 0.5);

    // The header: every pill shown whole, with its status word, apart.
    QList<QQuickItem *> header_items;
    for (const char * name : {"twinModePill", "consoleStatePill", "boundaryPill",
        "sidePill_plant", "sidePill_counterpart", "simTimeFigure", "rtfFigure"})
    {
      auto * item = framed.find(name);
      ASSERT_NE(item, nullptr) << name;
      EXPECT_TRUE(shown(item, panel)) << name;
      EXPECT_TRUE(window.contains(rect_in(item, panel))) << name << " leaves the window";
      EXPECT_GE(item->width() + 0.5, item->implicitWidth()) << name << " is squeezed";
      header_items << item;
    }
    EXPECT_TRUE(overlaps(header_items, panel).isEmpty())
      << overlaps(header_items, panel).join("; ").toStdString();
    for (const char * name : {"boundaryPill", "sidePill_plant", "sidePill_counterpart"}) {
      EXPECT_EQ(framed.find(name)->property("value").toString().toStdString(), "live")
        << name << " shows no status word";
    }
    // Named by side, never by position (R-05).
    EXPECT_EQ(framed.find("sidePill_counterpart")->property("label").toString(),
      QString("Counterpart"));

    // The deck: every clickable whole, inside the window, apart.
    QList<QQuickItem *> buttons;
    for (QQuickItem * item : descendants(panel)) {
      if (is_button(item) && shown(item, panel)) {
        EXPECT_TRUE(window.contains(rect_in(item, panel)))
          << item->property("text").toString().toStdString() << " leaves the window";
        EXPECT_EQ(visible_rect(item, panel), rect_in(item, panel))
          << item->property("text").toString().toStdString() << " is clipped";
        buttons << item;
      }
    }
    QStringList apart;
    for (const QString & line : overlaps(buttons, panel)) {
      apart << line;
    }
    // Segments and the stepper's buttons sit inside their own selector or
    // stepper, which are not buttons, so any overlap here is two controls.
    EXPECT_TRUE(apart.isEmpty()) << apart.join("; ").toStdString();

    // The Robot card's step: two lines at most, the rest elided.
    auto * step = framed.find("stepRow");
    ASSERT_NE(step, nullptr);
    auto * value = step->findChild<QQuickItem *>("fieldValue");
    ASSERT_NE(value, nullptr);
    EXPECT_LE(value->property("lineCount").toInt(), 2);
    EXPECT_TRUE(value->property("truncated").toBool()) << "the long step was not cut short";

    QCoreApplication::processEvents();
    EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
  }
}

// T-02: at the primary display every card of the rail is on screen at once,
// the event log included, without scrolling the rail.
TEST(PanelQml, AtTheprimaryDisplayTheRailShowsEveryCardWithoutScrolling)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  hear_everything(framed);
  auto * body = framed.find("body");
  ASSERT_NE(body, nullptr);
  const QRectF rail = rect_in(body, framed.panel);
  for (const char * name : {"robotCard", "progressCard", "sidesCard", "fidelityCard",
      "eventCard"})
  {
    auto * card = framed.find(name);
    ASSERT_NE(card, nullptr) << name;
    EXPECT_TRUE(shown(card, framed.panel)) << name;
    const QRectF at = rect_in(card, framed.panel);
    EXPECT_GE(at.top(), rail.top() - 0.5) << name;
    EXPECT_LE(at.bottom(), rail.bottom() + 0.5)
      << name << " ends at " << at.bottom() << ", below the rail's " << rail.bottom();
  }
  // The event log has rows' worth of room, and scrolls inside itself.
  EXPECT_GE(framed.find("eventCard")->height(), 160.0);
}

// At the smallest supported size the rail cuts no line short but the Robot
// card's step (two lines at most, by design), and what does not fit below is
// reached by scrolling the rail, not clipped away (ADR-0074).
TEST(PanelQml, AtTheSmallestSizeTheRailElidesNothingAndScrollsToItsEnd)
{
  Framed framed(kSizes[3]);
  ASSERT_NE(framed.panel, nullptr);
  hear_everything(framed);
  auto * body = framed.find("body");
  ASSERT_NE(body, nullptr);
  auto * step = framed.find("stepRow")->findChild<QQuickItem *>("fieldValue");
  ASSERT_NE(step, nullptr);
  QStringList elided;
  for (QQuickItem * item : descendants(body)) {
    if (item != step && item->property("truncated").toBool() && shown(item, framed.panel)) {
      elided << item->property("text").toString();
    }
  }
  EXPECT_TRUE(elided.isEmpty()) << "elided in the rail: " << elided.join(" | ").toStdString();

  // The rail's content is taller than the rail here, and its end is in view
  // once the rail is scrolled to it.
  auto * flick = qvariant_cast<QQuickItem *>(body->property("contentItem"));
  ASSERT_NE(flick, nullptr);
  const double content = flick->property("contentHeight").toDouble();
  const double room = flick->height();
  ASSERT_GT(content, room) << "nothing to scroll at the smallest size";
  flick->setProperty("contentY", content - room);
  settle(framed);
  const QRectF rail = rect_in(body, framed.panel);
  auto * events = framed.find("eventCard");
  ASSERT_NE(events, nullptr);
  const QRectF at = rect_in(events, framed.panel);
  EXPECT_LE(at.bottom(), rail.bottom() + 0.5)
    << "the event log ends at " << at.bottom() << ", below the scrolled rail's " << rail.bottom();
  EXPECT_GE(at.top(), rail.top() - 0.5);
  // And the operator can see that it scrolls: its scroll bar is shown.
  auto * indicator = framed.find("railScrollBar");
  ASSERT_NE(indicator, nullptr);
  EXPECT_TRUE(shown(indicator, framed.panel)) << "the rail scrolls and shows no scroll bar";
}

// R-06: world statistics not heard for longer than the configuration allows
// are shown as the last heard, dimmed and said "stale".
TEST(PanelQml, StaleWorldStatisticsAreSaidStale)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  auto * figure = framed.find("simTimeFigure");
  ASSERT_NE(figure, nullptr);
  cite_console_gui::CellConsoleTestAccess::hear_world_stats(framed.plugin, false);
  QCoreApplication::processEvents();
  EXPECT_FALSE(figure->property("stale").toBool());
  EXPECT_EQ(figure->property("note").toString(), QString());
  cite_console_gui::CellConsoleTestAccess::hear_world_stats(framed.plugin, true);
  QCoreApplication::processEvents();
  EXPECT_TRUE(figure->property("stale").toBool());
  EXPECT_EQ(figure->property("note").toString(), QString("stale"));
  EXPECT_EQ(framed.find("rtfFigure")->property("note").toString(), QString("stale"));
}

// R-01 (second round): the stale flag through the plugin's real wiring. A
// world statistics message published over gz transport reaches the plugin's
// own subscription; with the plugin's clock advanced past the threshold its
// own timer says them stale; the next message says them current at once, and
// they stay current.
TEST(PanelQml, WorldStatisticsTurnStaleOnThePluginsTimerAndCurrentOnArrival)
{
  using cite_console_gui::CellConsoleTestAccess;
  cite_console_gui::CellConsole plugin;
  std::int64_t now_ms = 1000;
  CellConsoleTestAccess::set_clock(plugin, [&now_ms]() {return now_ms;});
  const std::string topic = "/world/stale_test/stats";
  tinyxml2::XMLDocument config;
  const std::string xml = "<plugin filename=\"CellConsole\">"
    "<facility_label>CITE</facility_label><zone_label>Cell B</zone_label>"
    "<world_stats_topic>" + topic + "</world_stats_topic>"
    "<world_stats_stale_after_s>0.1</world_stats_stale_after_s></plugin>";
  ASSERT_EQ(config.Parse(xml.c_str()), tinyxml2::XML_SUCCESS);
  plugin.LoadConfig(config.RootElement());

  // Every notification, with the flag it said.
  std::vector<bool> said;
  QObject::connect(
    &plugin, &cite_console_gui::CellConsole::worldStatsChanged,
    [&]() {said.push_back(plugin.worldStatsStale());});

  gz::transport::Node world;
  auto publisher = world.Advertise<gz::msgs::WorldStatistics>(topic);
  // Published until the plugin shows it: discovery is an event this test
  // cannot see, and a hang detector bounds the wait.
  const auto deliver = [&](std::int64_t sim_s) {
      const QString before = plugin.simTime();
      gz::msgs::WorldStatistics message;
      message.mutable_sim_time()->set_sec(sim_s);
      message.set_real_time_factor(1.0);
      QElapsedTimer waited;
      waited.start();
      while (plugin.simTime() == before && waited.elapsed() < 5000) {
        publisher.Publish(message);
        QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
      }
      return plugin.simTime() != before;
    };
  // The clock moved past the threshold until the plugin's own timer has said
  // them stale; bounded the same way. Moved on each turn, because copies of
  // the message `deliver` published while discovery ran may still arrive,
  // and each is an arrival.
  const auto until_stale = [&]() {
      QElapsedTimer waited;
      waited.start();
      while (!plugin.worldStatsStale() && waited.elapsed() < 5000) {
        now_ms += 200;
        QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
      }
      return plugin.worldStatsStale();
    };

  ASSERT_TRUE(deliver(10)) << "the plugin never heard the world statistics";
  EXPECT_FALSE(plugin.worldStatsStale());
  EXPECT_TRUE(until_stale()) << "past the threshold, the plugin's timer never said them stale";

  said.clear();
  ASSERT_TRUE(deliver(20));
  ASSERT_FALSE(said.empty());
  EXPECT_FALSE(said.front()) << "the message that arrived was said stale";
  // The clock stands still: three of the plugin's timer ticks later they are
  // still current.
  QSignalSpy ticks(&CellConsoleTestAccess::display_timer(plugin), &QTimer::timeout);
  QElapsedTimer waited;
  waited.start();
  while (ticks.count() < 3 && waited.elapsed() < 5000) {
    ticks.wait(1000);
  }
  ASSERT_GE(ticks.count(), 3) << "the plugin's display timer did not tick";
  EXPECT_FALSE(plugin.worldStatsStale()) << "the arrival did not restart the age";
}

// T-03: the Robot card shows the console's step and outcome without stray
// spaces, and a number with its unit is one unbreakable piece.
TEST(PanelQml, TheRobotCardShowsAStepWithoutStraySpacesOrALoneUnit)
{
  Framed framed(kSizes[3]);
  ASSERT_NE(framed.panel, nullptr);
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.step = "  ok  plant: conveyor at 0 m/s";
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  settle(framed);
  auto * step = framed.find("stepRow");
  ASSERT_NE(step, nullptr);
  auto * value = step->findChild<QQuickItem *>("fieldValue");
  ASSERT_NE(value, nullptr);
  EXPECT_EQ(
    value->property("text").toString(),
    QString::fromUtf8("ok plant: conveyor at 0\u00a0m/s"));
}

// A request sent, or accepted, that has not reported yet is shown starting,
// not idle; its first feedback shows its position, and its end idle again.
TEST(PanelQml, CycleProgressShowsASentRequestStartingNotIdle)
{
  Framed framed(kSizes[3]);
  ASSERT_NE(framed.panel, nullptr);
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, ready_on_the_simulation());
  settle(framed);
  auto * card = framed.find("progressCard");
  auto * title = framed.find("runTitle");
  ASSERT_NE(card, nullptr);
  ASSERT_NE(title, nullptr);
  EXPECT_EQ(title->property("text").toString(), QString("No request running"));
  EXPECT_EQ(card->property("summary").toString(), QString("Idle"));

  cite_console_gui::RunProgress sent;
  sent.starting = "Start program";
  cite_console_gui::CellConsoleTestAccess::report_run(framed.plugin, sent);
  settle(framed);
  EXPECT_EQ(title->property("text").toString(), QString::fromUtf8("Start program — starting…"));
  EXPECT_EQ(card->property("summary").toString(), QString("Starting"));

  cite_console_gui::RunProgress running;
  running.active = true;
  running.cycle = 1;
  running.cycles = 2;
  running.step_index = 3;
  running.step_count = 9;
  cite_console_gui::CellConsoleTestAccess::report_run(framed.plugin, running);
  settle(framed);
  EXPECT_EQ(title->property("text").toString(), QString("Start program"));
  EXPECT_EQ(card->property("summary").toString(), QString::fromUtf8("Cycle 1/2 · step 3/9"));

  cite_console_gui::CellConsoleTestAccess::report_run(
    framed.plugin, cite_console_gui::RunProgress{});
  settle(framed);
  EXPECT_EQ(title->property("text").toString(), QString("No request running"));
}

// The event log shows a step and a last error as the Robot card shows a
// line (`display_text`): no stray spaces, no unit alone.
TEST(PanelQml, TheEventLogShowsItsLinesAsTheRobotCardDoes)
{
  Framed framed(kSizes[3]);
  ASSERT_NE(framed.panel, nullptr);
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.step = "  ok  plant: transfer_belt at 0 m/s";
  state.last_error = "  the belt  stalled at 0.2 m/s ";
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  settle(framed);
  const QVariantList rows = framed.plugin.eventLog();
  ASSERT_FALSE(rows.isEmpty());
  const QVariantMap newest = rows.front().toMap();
  EXPECT_EQ(
    newest["step"].toString(), QString::fromUtf8("ok plant: transfer_belt at 0\u00a0m/s"));
  EXPECT_EQ(
    newest["lastError"].toString(), QString::fromUtf8("the belt stalled at 0.2\u00a0m/s"));
  // And that is the text on screen.
  bool shown_step = false;
  for (QQuickItem * item : descendants(framed.find("eventCard"))) {
    if (item->property("text").toString() == newest["step"].toString()) {
      shown_step = true;
    }
  }
  EXPECT_TRUE(shown_step) << "the event log does not show the step as displayed";
}

// R-03 / S-02: when a change of the console drops the operator's Twin pick,
// the event log says so, and says what is selected now.
TEST(PanelQml, ADroppedPickIsSaidInTheEventLog)
{
  Framed framed(kSizes[3]);
  ASSERT_NE(framed.panel, nullptr);
  cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
  state.available_targets = {
    cite_interfaces::msg::ConsoleState::TARGET_SIM,
    cite_interfaces::msg::ConsoleState::TARGET_TWIN};
  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
  settle(framed);
  const int logged = framed.plugin.eventLog().size();
  framed.plugin.selectTarget(2);
  ASSERT_EQ(framed.plugin.selectedTarget(), 2);

  cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, ready_on_the_simulation());
  settle(framed);
  EXPECT_EQ(framed.plugin.selectedTarget(), 0);
  const QVariantList rows = framed.plugin.eventLog();
  ASSERT_EQ(rows.size(), logged + 1)
    << "the console's state did not change; only the note is new";
  const QVariantMap newest = rows.front().toMap();
  EXPECT_EQ(newest["state"].toString(), QString("Target selection dropped"));
  EXPECT_EQ(newest["step"].toString(), QString("Console changed: now Simulation"));
  bool shown = false;
  for (QQuickItem * item : descendants(framed.find("eventCard"))) {
    if (item->property("text").toString() == newest["step"].toString()) {
      shown = true;
    }
  }
  EXPECT_TRUE(shown) << "the note is not on screen";
}

// R-05: the view label names what Follow robot follows in the configuration's
// words, never a literal of its own.
TEST(PanelQml, FollowingIsNamedByTheConfiguration)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  cite_console_gui::CellConsoleTestAccess::name_follow(framed.plugin, "picker carriage");
  QCoreApplication::processEvents();
  auto * follow = framed.find("followButton");
  ASSERT_NE(follow, nullptr);
  ASSERT_TRUE(QMetaObject::invokeMethod(follow, "clicked"));
  QCoreApplication::processEvents();
  EXPECT_EQ(framed.find("viewText")->property("text").toString(),
    QString("View: Following picker carriage"));
}

// S-04: no control of the deck or the question takes keyboard focus, so a
// stray key cannot press one again.
TEST(PanelQml, NoControlTakesKeyboardFocus)
{
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  framed.find("confirmation")->setVisible(true);
  QCoreApplication::processEvents();
  int buttons = 0;
  for (QQuickItem * item : descendants(framed.panel)) {
    if (is_button(item)) {
      ++buttons;
      EXPECT_EQ(item->property("focusPolicy").toInt(), static_cast<int>(Qt::NoFocus))
        << "'" << item->property("text").toString().toStdString() << "' takes focus";
    }
  }
  EXPECT_GE(buttons, 15);
}

// S-03: a prompt longer than the room above the deck scrolls inside the
// question; the title and Confirm stay on screen, and the header is not
// covered.
TEST(PanelQml, ALongQuestionNeverCoversTheHeader)
{
  // 600 characters, and far more than the room above the deck holds.
  for (const std::size_t length : {600u, 4000u}) {
    SCOPED_TRACE(length);
    Framed framed(kSizes[3]);
    ASSERT_NE(framed.panel, nullptr);
    cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
    state.state = cite_interfaces::msg::ConsoleState::AWAITING_OPERATOR;
    state.last_error = "refused: an earlier request";
    state.prompt = std::string(
    "Clear the cell: nobody inside the fence, the gripper's path free, and the part on the "
    "table where the program expects it. ");
    while (state.prompt.size() < length) {
      state.prompt += "Confirm only once every person is outside and the E-stop is in reach. ";
    }
    cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
    QCoreApplication::processEvents();
    auto * confirmation = framed.find("confirmation");
    ASSERT_NE(confirmation, nullptr);
    ASSERT_TRUE(shown(confirmation, framed.panel)) << "the console asks and no question shows";
    const QRectF question = rect_in(confirmation, framed.panel);
    EXPECT_GE(question.top(), Theme_header_bottom(framed.panel) - 0.5)
      << "the question covers the header";
    EXPECT_LE(question.bottom(), rect_in(framed.find("commands"), framed.panel).top() + 0.5);
    const QRectF window(0.0, 0.0, 1280.0, 720.0);
    for (const char * name : {"confirmationTitle", "confirmButton", "cancelButton"}) {
      auto * item = framed.find(name);
      ASSERT_NE(item, nullptr) << name;
      EXPECT_TRUE(window.contains(rect_in(item, framed.panel))) << name;
      EXPECT_TRUE(question.contains(rect_in(item, framed.panel))) << name << " leaves the question";
      EXPECT_EQ(visible_rect(item, framed.panel), rect_in(item, framed.panel)) << name;
    }
  // Below the alarm band too, which the last error shows.
    EXPECT_GE(question.top(), rect_in(framed.find("alarmBand"), framed.panel).bottom() - 0.5);
    auto * prompt = framed.find("confirmationPrompt");
    ASSERT_NE(prompt, nullptr);
    if (length > 600u) {
      EXPECT_GT(prompt->property("contentHeight").toDouble(), prompt->height())
        << "the longest prompt was not left to scroll";
    } else {
      EXPECT_LE(prompt->property("contentHeight").toDouble(), prompt->height() + 0.5)
        << "a prompt with room enough was cut";
    }
  }
}

// R2-05: the question's room is up to the alarm band only while the band is
// shown; with none, it is up to the header. A hidden band takes no room.
TEST(PanelQml, ALongQuestionTakesTheRoomAHiddenAlarmBandLeaves)
{
  for (const bool alarm : {false, true}) {
    SCOPED_TRACE(alarm ? "alarm band shown" : "no alarm band");
    Framed framed(kSizes[3]);
    ASSERT_NE(framed.panel, nullptr);
    cite_interfaces::msg::ConsoleState state = ready_on_the_simulation();
    state.state = cite_interfaces::msg::ConsoleState::AWAITING_OPERATOR;
    state.last_error = alarm ? "refused: an earlier request" : "";
    while (state.prompt.size() < 4000u) {
      state.prompt += "Confirm only once every person is outside and the E-stop is in reach. ";
    }
    cite_console_gui::CellConsoleTestAccess::hear(framed.plugin, state);
    settle(framed);
    auto * band = framed.find("alarmBand");
    auto * confirmation = framed.find("confirmation");
    ASSERT_NE(band, nullptr);
    ASSERT_NE(confirmation, nullptr);
    ASSERT_EQ(band->isVisible(), alarm);
    const double above = alarm ? rect_in(band, framed.panel).bottom() :
      Theme_header_bottom(framed.panel);
    EXPECT_NEAR(rect_in(confirmation, framed.panel).top(), above, 0.5)
      << "the question does not take the room up to the "
      << (alarm ? "alarm band" : "header");
  }
}

// T-03: 1280 wide is a supported size and gets the medium layout; compact is
// for what is below every supported size.
TEST(PanelQml, TheLayoutStepsDownBelowTheSupportedSizesOnly)
{
  for (const auto & [width, compact] : std::vector<std::pair<int, bool>>{
    {1280, false}, {1264, false}, {1200, false}, {1199, true}, {1024, true}})
  {
    Framed framed(WindowSize{width, 720});
    ASSERT_NE(framed.panel, nullptr);
    EXPECT_EQ(framed.panel->property("compact").toBool(), compact) << width;
    EXPECT_FALSE(framed.panel->property("wide").toBool()) << width;
  }
}

// T-05: Stop's label never breaks inside "E-stop": on one line where it fits,
// and otherwise after its comma only. The label itself is exact.
TEST(PanelQml, StopsLabelNeverBreaksInsideEStop)
{
  for (const WindowSize & size :
    {kSizes[0], kSizes[1], kSizes[2], kSizes[3], WindowSize{1024, 600}, WindowSize{800, 600}})
  {
    SCOPED_TRACE(size_name(size));
    Framed framed(size);
    ASSERT_NE(framed.panel, nullptr);
    auto * stop = framed.find("stopButton");
    auto * subtitle = framed.find("stopSubtitle");
    ASSERT_NE(subtitle, nullptr);
    EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));
    const QString shown_text = subtitle->property("text").toString();
    EXPECT_EQ(QString(shown_text).replace("\n", " "), QString("software stop, not an E-stop"));
    EXPECT_EQ(subtitle->property("wrapMode").toInt(), 0) << "a word wrap may break at the hyphen";
    EXPECT_LE(subtitle->property("contentWidth").toDouble(), subtitle->width() + 0.5)
      << "'" << shown_text.toStdString() << "' does not fit";
    for (const QString & line : shown_text.split("\n")) {
      EXPECT_FALSE(line.endsWith("E-")) << line.toStdString();
    }
  }
}

// Stop shows "Stopped" once the console accepted it (owner request
// 2026-10-16): the subtitle stays, Stop still stops, a view button leaves it,
// any other command button clears it, and a refused Stop never shows it.
TEST(PanelQml, AnAcceptedStopIsShownUntilAnotherCommandIsPressed)
{
  using cite_console_gui::CellConsoleTestAccess;
  Framed framed(kSizes[0]);
  ASSERT_NE(framed.panel, nullptr);
  // A request running: Stop is enabled, as it is whenever it can stop.
  CellConsoleTestAccess::hear(framed.plugin, running_a_request());
  settle(framed);
  auto * stop = framed.find("stopButton");
  auto * subtitle = framed.find("stopSubtitle");
  ASSERT_NE(stop, nullptr);
  ASSERT_NE(subtitle, nullptr);
  ASSERT_TRUE(stop->isEnabled());
  const QString stopped_label = QString::fromUtf8("Stopped — software stop, not an E-stop");
  auto subtitle_text = [subtitle]() {
      return subtitle->property("text").toString().replace("\n", " ");
    };

  // Accepted: shown, the subtitle kept, Stop still pressable.
  framed.plugin.stop();
  CellConsoleTestAccess::answer_stop(framed.plugin, true);
  settle(framed);
  EXPECT_TRUE(framed.plugin.stoppedShown());
  EXPECT_EQ(stop->property("text").toString(), stopped_label);
  EXPECT_EQ(subtitle_text(), QString("software stop, not an E-stop"));
  EXPECT_TRUE(stop->isEnabled()) << "Stop is not pressable while it shows Stopped";

  // Pressed again, through the window, and accepted again: still shown.
  const std::size_t pressed = CellConsoleTestAccess::stops_pressed(framed.plugin);
  click(framed.window, stop);
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(framed.plugin), pressed + 1)
    << "a press on Stopped did not reach the plugin's stop()";
  CellConsoleTestAccess::answer_stop(framed.plugin, true);
  settle(framed);
  EXPECT_EQ(stop->property("text").toString(), stopped_label);

  // The view buttons move no robot and leave it.
  framed.plugin.resetView();
  framed.plugin.selectPreset(0);
  framed.plugin.followRobot();
  settle(framed);
  EXPECT_TRUE(framed.plugin.stoppedShown()) << "a view button cleared Stopped";

  // Each other command button clears it.
  const std::vector<std::pair<const char *, std::function<void()>>> commands = {
    {"Start robot", [&framed]() {framed.plugin.startRobot();}},
    {"Home", [&framed]() {framed.plugin.home(0.5);}},
    {"Start program", [&framed]() {framed.plugin.startProgram(0.5, 1);}},
    {"Validate then run", [&framed]() {framed.plugin.validateThenRun(0.5, 1);}},
    {"Confirm", [&framed]() {framed.plugin.confirm();}}};
  for (const auto & command : commands) {
    SCOPED_TRACE(command.first);
    framed.plugin.stop();
    CellConsoleTestAccess::answer_stop(framed.plugin, true);
    settle(framed);
    ASSERT_TRUE(framed.plugin.stoppedShown());
    command.second();
    settle(framed);
    EXPECT_FALSE(framed.plugin.stoppedShown());
    EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));
  }

  // A Stop accepted after another command was pressed is not shown.
  framed.plugin.stop();
  framed.plugin.home(0.5);
  CellConsoleTestAccess::answer_stop(framed.plugin, true);
  settle(framed);
  EXPECT_FALSE(framed.plugin.stoppedShown()) << "Stopped shown over a later command";

  // Refused: not shown; the outcome text is the client's, untouched here.
  framed.plugin.stop();
  CellConsoleTestAccess::answer_stop(framed.plugin, false);
  settle(framed);
  EXPECT_FALSE(framed.plugin.stoppedShown()) << "a refused Stop is shown as Stopped";
  EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));

  // The console leaving clears it.
  framed.plugin.stop();
  CellConsoleTestAccess::answer_stop(framed.plugin, true);
  ASSERT_TRUE(framed.plugin.stoppedShown());
  CellConsoleTestAccess::forget(framed.plugin);
  settle(framed);
  EXPECT_FALSE(framed.plugin.stoppedShown()) << "Stopped outlived the console";
  EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));
  EXPECT_TRUE(framed.warnings.isEmpty()) << framed.warnings.join("\n").toStdString();
}

// A picture of the frame at every size, for a person to look at: visual
// quality is judged on a display, not by a test (ADR-0074). Three of each: no
// console, a console asking its question, and a console heard with every
// display filled. Not a gate: it fails only when no picture could be written.
TEST(PanelQml, APictureOfTheFrameIsWrittenAtEverySize)
{
  QString directory = qEnvironmentVariable("CITE_PANEL_PNG_DIR");
  if (directory.isEmpty()) {
    directory = QStringLiteral(CITE_PANEL_PNG_DEFAULT_DIR);
  }
  QDir().mkpath(directory);
  for (const WindowSize & size : kSizes) {
    for (const char * variant : {"", "_question", "_heard"}) {
      Framed framed(size);
      ASSERT_NE(framed.panel, nullptr);
      if (std::strcmp(variant, "_question") == 0) {
        // As a console asking the operator its question would show it.
        framed.find("confirmation")->setVisible(true);
      } else if (std::strcmp(variant, "_heard") == 0) {
        hear_everything(framed);
      }
      // The colour transitions (Theme.fast, Theme.normal: at most 200 ms) run
      // to their end before the picture is taken; a picture, never a gate.
      QElapsedTimer settling;
      settling.start();
      while (settling.elapsed() < 400) {
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
      }
      // The offscreen window renders once it is exposed; a hang detector only.
      QElapsedTimer waited;
      waited.start();
      while (!framed.window.isExposed() && waited.elapsed() < 5000) {
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
      }
      // grabToImage, not grabWindow: the software backend's offscreen window
      // returns no image from the latter.
      auto result = framed.panel->grabToImage();
      ASSERT_TRUE(result) << size_name(size);
      bool ready = false;
      QObject::connect(result.data(), &QQuickItemGrabResult::ready, [&ready]() {ready = true;});
      QElapsedTimer grab;
      grab.start();
      while (!ready && grab.elapsed() < 5000) {
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
      }
      const QImage image = result->image();
      ASSERT_FALSE(image.isNull()) << size_name(size);
      const QString path = directory + "/panel_" + QString::fromStdString(size_name(size)) +
        variant + ".png";
      EXPECT_TRUE(image.save(path)) << path.toStdString();
      RecordProperty(("png_" + size_name(size) + variant).c_str(), path.toStdString());
    }
  }
}

int main(int argc, char ** argv)
{
  // Headless whatever the environment says; the CMake target sets them too.
  if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM")) {
    qputenv("QT_QPA_PLATFORM", QByteArray("offscreen"));
  }
  if (qEnvironmentVariableIsEmpty("QT_QUICK_BACKEND")) {
    qputenv("QT_QUICK_BACKEND", QByteArray("software"));
  }
  // The style gz-gui runs its window in, so the pictures look like the window.
  if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE")) {
    qputenv("QT_QUICK_CONTROLS_STYLE", QByteArray("Material"));
  }
  // Before any gz transport node exists: a partition of this test's own, so
  // the world statistics it publishes reach only itself.
  if (qEnvironmentVariableIsEmpty("GZ_PARTITION")) {
    qputenv("GZ_PARTITION", QByteArray("cite_test_panel_qml_") + QByteArray::number(getpid()));
  }
  QGuiApplication app(argc, argv);
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
