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

#include <gtest/gtest.h>

#include <QByteArray>
#include <QGuiApplication>
#include <QList>
#include <QObject>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlError>
#include <QPointF>
#include <QQuickItem>
#include <QRectF>
#include <QSizeF>
#include <QString>
#include <QStringList>
#include <QtGlobal>

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

// gz-gui puts the panel's root in a card it sizes from the generated
// `gui.config` (380x640). A root that neither fills its parent nor has an
// implicit size is 0x0 there, and the `Layout.fillHeight` body - status,
// selectors, every command but Stop - is laid out with no height at all.
TEST(PanelQml, ThePanelFillsTheCardItIsPutIn)
{
  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  QQmlContext context(engine.rootContext());
  context.setContextProperty("CellConsole", &plugin);

  QQuickItem card;
  card.setSize(QSizeF(380.0, 640.0));

  QQmlComponent component(&engine, QString(kPanel));
  ASSERT_TRUE(component.isReady()) << describe(component.errors()).join("\n").toStdString();
  std::unique_ptr<QObject> created(component.beginCreate(&context));
  auto * panel = qobject_cast<QQuickItem *>(created.get());
  ASSERT_NE(panel, nullptr) << describe(component.errors()).join("\n").toStdString();
  panel->setParentItem(&card);
  component.completeCreate();
  QCoreApplication::processEvents();

  EXPECT_GT(panel->width(), 0.0) << "the panel has no width in its card";
  EXPECT_GT(panel->height(), 0.0) << "the panel has no height in its card";
  auto * body = panel->findChild<QQuickItem *>("body");
  ASSERT_NE(body, nullptr) << "the panel has no item named `body`";
  EXPECT_GT(body->height(), 200.0) << "the panel's body is laid out with no room";
}

// Every command is on screen in the 380x640 card without scrolling: the owner,
// in the real window, never found Home or Start program below the scrolled
// body's fold. So each command - and the console's question, when it asks one
// - is laid out outside the scrolled body and inside the panel's own bounds.
TEST(PanelQml, EveryCommandIsOnScreenWithoutScrolling)
{
  cite_console_gui::CellConsole plugin;
  QQmlEngine engine;
  QQmlContext context(engine.rootContext());
  context.setContextProperty("CellConsole", &plugin);

  QQuickItem card;
  card.setSize(QSizeF(380.0, 640.0));

  QQmlComponent component(&engine, QString(kPanel));
  ASSERT_TRUE(component.isReady()) << describe(component.errors()).join("\n").toStdString();
  std::unique_ptr<QObject> created(component.beginCreate(&context));
  auto * panel = qobject_cast<QQuickItem *>(created.get());
  ASSERT_NE(panel, nullptr) << describe(component.errors()).join("\n").toStdString();
  panel->setParentItem(&card);
  component.completeCreate();
  QCoreApplication::processEvents();

  auto * body = panel->findChild<QQuickItem *>("body");
  ASSERT_NE(body, nullptr) << "the panel has no item named `body`";
  const QRectF visible(0.0, 0.0, panel->width(), panel->height());

  for (const char * name :
    {"startRobotButton", "homeButton", "startProgramButton", "validateThenRunButton",
      "stopButton", "confirmation"})
  {
    auto * item = panel->findChild<QQuickItem *>(name);
    ASSERT_NE(item, nullptr) << "the panel has no item named `" << name << "`";
    EXPECT_FALSE(body->isAncestorOf(item)) << name << " is inside the scrolled body";
    if (std::string(name) == "confirmation") {
      continue;  // Shown only while the console asks; no console is heard here.
    }
    const QRectF rect = item->mapRectToItem(panel, QRectF(0.0, 0.0, item->width(), item->height()));
    EXPECT_TRUE(item->isVisible()) << name << " is not visible";
    EXPECT_GT(rect.width(), 0.0) << name << " has no width";
    EXPECT_GT(rect.height(), 0.0) << name << " has no height";
    EXPECT_TRUE(visible.contains(rect))
      << name << " at (" << rect.x() << ", " << rect.y() << ", " << rect.width() << "x"
      << rect.height() << ") is outside the " << visible.width() << "x" << visible.height()
      << " panel";
  }
  RecordProperty("body_height", static_cast<int>(body->height()));
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
  QGuiApplication app(argc, argv);
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
