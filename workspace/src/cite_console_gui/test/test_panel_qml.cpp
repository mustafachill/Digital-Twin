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
#include <QSizeF>
#include <QString>
#include <QStringList>
#include <QTest>
#include <QtGlobal>
#include <QUrl>

#include <cmath>
#include <cstring>
#include <utility>
#include <memory>
#include <string>
#include <vector>

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

/// The validate-then-run caveat as an offered console shows it: its longest.
const char kCaveat[] =
  "Passing in simulation is not evidence that the real arm's cycle is safe: "
  "every twin gate still applies. One cycle on the simulation first; the twin "
  "runs only if it passed there. Needs both arms at the start and a speed at "
  "or above the real arm floor.";

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

    // The validate-then-run caveat at its longest, as an offered console says
    // it: beside its button, inside the deck (ADR-0073 decision 5).
    auto * caveat = framed.find("validateThenRunCaveat");
    ASSERT_NE(caveat, nullptr) << "the panel has no item named `validateThenRunCaveat`";
    caveat->setProperty("text", QString::fromUtf8(kCaveat));
    QCoreApplication::processEvents();
    const QRectF deck_rect = rect_in(commands, panel);
    const QRectF caveat_rect = rect_in(caveat, panel);
    EXPECT_TRUE(deck_rect.contains(caveat_rect))
      << "the caveat at " << describe(caveat_rect) << " leaves the deck at "
      << describe(deck_rect);
    // Fewer lines than it may show: a caveat at its maximum may be cut short.
    EXPECT_LT(
      caveat->property("lineCount").toInt(), caveat->property("maximumLineCount").toInt())
      << "the caveat is cut short";
    const QRectF validate = rect_in(framed.find("validateThenRunButton"), panel);
    EXPECT_LT(std::abs(caveat_rect.top() - validate.top()), 1.0)
      << "the caveat is not beside its button";

    // Stop: its label exactly (ADR-0071 decision 4).
    auto * stop = framed.find("stopButton");
    ASSERT_NE(stop, nullptr);
    EXPECT_EQ(stop->property("text").toString(), QString::fromUtf8(kStopLabel));

    // The target: never preselected (ADR-0072 decision 3, R-18).
    auto * target = framed.find("targetSelector");
    ASSERT_NE(target, nullptr) << "the panel has no item named `targetSelector`";
    int targets = 0;
    for (QQuickItem * item : descendants(target)) {
      if (is_button(item)) {
        ++targets;
        EXPECT_FALSE(item->property("selected").toBool())
          << "the target '" << item->property("text").toString().toStdString()
          << "' is preselected";
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

/// A console READY to run on the simulation alone, as `cell_console` says it.
cite_interfaces::msg::ConsoleState ready_on_the_simulation()
{
  cite_interfaces::msg::ConsoleState state;
  state.state = cite_interfaces::msg::ConsoleState::READY;
  state.robot_started = true;
  state.plant_at_start = true;
  state.available_targets = {cite_interfaces::msg::ConsoleState::TARGET_SIM};
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
    // The first click selects the target (never preselected); the speed is.
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
        // As a console that asks and offers validate-then-run would show it.
        framed.find("confirmation")->setVisible(true);
        framed.find("validateThenRunCaveat")->setProperty("text", QString::fromUtf8(kCaveat));
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
  QGuiApplication app(argc, argv);
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
