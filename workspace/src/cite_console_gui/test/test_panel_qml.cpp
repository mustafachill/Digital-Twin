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
#include <QtGlobal>

#include <cmath>
#include <cstring>
#include <memory>
#include <string>

#include "../src/cell_console.hpp"

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

  QQuickItem * find(const char * name) const
  {
    return panel->findChild<QQuickItem *>(name);
  }

  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  std::unique_ptr<QQmlContext> context;
  QQuickWindow window;
  std::unique_ptr<QObject> created;
  QQuickItem * panel{nullptr};
  QStringList warnings;
};

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
        EXPECT_FALSE(item->property("checked").toBool())
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
      if (is_button(item) && item->property("checked").toBool()) {
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

// A picture of the frame at every size, for a person to look at: visual
// quality is judged on a display, not by a test (ADR-0074). Not a gate: it
// fails only when no picture could be written.
TEST(PanelQml, APictureOfTheFrameIsWrittenAtEverySize)
{
  QString directory = qEnvironmentVariable("CITE_PANEL_PNG_DIR");
  if (directory.isEmpty()) {
    directory = QStringLiteral(CITE_PANEL_PNG_DEFAULT_DIR);
  }
  QDir().mkpath(directory);
  for (const WindowSize & size : kSizes) {
    for (const bool asking : {false, true}) {
      Framed framed(size);
      ASSERT_NE(framed.panel, nullptr);
      if (asking) {
        // As a console that asks and offers validate-then-run would show it.
        framed.find("confirmation")->setVisible(true);
        framed.find("validateThenRunCaveat")->setProperty("text", QString::fromUtf8(kCaveat));
      }
      QCoreApplication::processEvents();
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
        (asking ? "_question" : "") + ".png";
      EXPECT_TRUE(image.save(path)) << path.toStdString();
      RecordProperty(("png_" + size_name(size) + (asking ? "_question" : "")).c_str(),
        path.toStdString());
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
