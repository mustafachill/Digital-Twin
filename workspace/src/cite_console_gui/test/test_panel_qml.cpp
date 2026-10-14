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
#include <QQuickItem>
#include <QString>
#include <QStringList>
#include <QtGlobal>

#include <memory>

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
