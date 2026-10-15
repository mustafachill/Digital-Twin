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

// The panel in gz-gui's own main window and card (S-02).
//
// The frame passes the mouse through to the 3D view by masking the card gz-gui
// puts it in (ADR-0074), which leans on how gz-gui 8 builds that card
// (GzCard.qml, an internal). test_panel_qml holds the frame's own rules with a
// stand-in card; this test loads the plugin through `gz::gui::Application`, as
// `gz sim` does, so the card is gz-gui's real one: the pass-through is applied
// to it, and a press at Stop's centre is still Stop's.
//
// Headless (`offscreen` platform, `software` Quick backend, half scale so that
// the maximized window holds the whole frame). The configuration
// carries the panel and nothing else: no 3D view to render, and no console,
// camera or world names, so the panel joins neither ROS nor gz transport.

#include <gtest/gtest.h>

#include <QByteArray>
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QEventLoop>
#include <QList>
#include <QPointF>
#include <QRectF>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScreen>
#include <QString>
#include <QTemporaryDir>
#include <QTest>
#include <QtGlobal>

#include <dlfcn.h>

#include <fstream>
#include <memory>
#include <string>

#include <gz/gui/Application.hh>
#include <gz/gui/MainWindow.hh>
#include <gz/gui/Plugin.hh>

#include "../src/cell_console.hpp"
#include "cell_console_test_access.hpp"
#include "cite_interfaces/msg/console_state.hpp"

namespace
{

int argc_ = 1;
char arg0_[] = "test_panel_in_gz_gui";
char * argv_[] = {arg0_, nullptr};

/// The panel alone, in the card the generated configuration describes for it,
/// less the anchors to a 3D view this window does not have.
const char kConfig[] =
  R"(<?xml version="1.0"?>
<window>
  <width>1920</width>
  <height>1080</height>
  <style material_theme="Dark"/>
</window>
<plugin filename="CellConsole" name="Cell console">
  <gz-gui>
    <title>Cell console</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="bool" key="resizable">false</property>
    <property type="string" key="cardBackground">#00000000</property>
    <property type="double" key="z">2</property>
    <property type="string" key="state">floating</property>
  </gz-gui>
</plugin>
)";

/// The directory of the libCellConsole.so this process linked. gz-gui must
/// load that very file: another copy - the installed one, when the
/// workspace is not built with --symlink-install - is a second library that
/// gz-gui fails to load next to the first (R2-04).
std::string linked_plugin_dir()
{
  Dl_info info;
  if (dladdr(&cite_console_gui::CellConsole::staticMetaObject, &info) == 0 ||
    info.dli_fname == nullptr)
  {
    return "";
  }
  return QFileInfo(QString::fromLocal8Bit(info.dli_fname)).absolutePath().toStdString();
}

/// Whether `item` is a MouseArea that handles a press (its own `enabled`).
bool enabled_mouse_area(const QQuickItem * item)
{
  return QString(item->metaObject()->className()).startsWith("QQuickMouseArea") &&
         item->property("enabled").toBool();
}

}  // namespace

TEST(PanelInGzGui, ThePassThroughIsAppliedToGzGuisCardAndStopStillTakesItsPress)
{
  gz::gui::Application app(argc_, argv_);
  app.AddPluginPath(linked_plugin_dir());
  QTemporaryDir directory;
  ASSERT_TRUE(directory.isValid());
  const std::string path = directory.filePath("panel.config").toStdString();
  std::ofstream(path) << kConfig;
  ASSERT_TRUE(app.LoadConfig(path)) << "gz-gui could not load the panel";

  auto * main = app.findChild<gz::gui::MainWindow *>();
  ASSERT_NE(main, nullptr);
  QQuickWindow * window = main->QuickWindow();
  ASSERT_NE(window, nullptr);
  window->show();
  // A hang detector, ended by the event it waits for.
  QElapsedTimer waited;
  waited.start();
  while (!window->isExposed() && waited.elapsed() < 5000) {
    QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
  }
  QCoreApplication::processEvents();

  auto plugins = app.findChildren<cite_console_gui::CellConsole *>();
  ASSERT_EQ(plugins.size(), 1) << "the panel's plugin was not loaded";
  cite_console_gui::CellConsole * plugin = plugins.front();
  QQuickItem * frame = plugin->PluginItem();
  QQuickItem * card = plugin->CardItem();
  ASSERT_NE(frame, nullptr);
  ASSERT_NE(card, nullptr);
  ASSERT_EQ(frame->window(), window) << "the panel is not in gz-gui's window";

  // gz-gui's real card carries the pass-through: masked, and the MouseAreas
  // it lays over its whole content (the wheel's and the context menu's) off.
  EXPECT_TRUE(frame->property("windowShown").toBool()) << "the window was never said shown";
  EXPECT_EQ(frame->property("passCard").value<QObject *>(), card)
    << "the pass-through was not applied to gz-gui's card, or was undone";
  EXPECT_NE(card->property("containmentMask").value<QObject *>(), nullptr);
  auto * content = card->property("contentItem").value<QQuickItem *>();
  ASSERT_NE(content, nullptr);
  int areas = 0;
  for (QQuickItem * item : content->childItems()) {
    if (QString(item->metaObject()->className()).startsWith("QQuickMouseArea")) {
      ++areas;
      EXPECT_FALSE(enabled_mouse_area(item)) << "a card MouseArea still takes the mouse";
    }
  }
  EXPECT_EQ(areas, 2) << "gz-gui's card is not built as the frame expects (GzCard.qml)";

  // Stop takes a press at its centre, and the card no longer takes the middle.
  // Inside the window: one outside it cannot be pressed at all (S-03).
  auto * stop = frame->findChild<QQuickItem *>("stopButton");
  ASSERT_NE(stop, nullptr);
  ASSERT_GT(stop->width(), 0.0);
  ASSERT_TRUE(
    QRectF(0.0, 0.0, window->width(), window->height()).contains(
      stop->mapRectToScene(QRectF(0.0, 0.0, stop->width(), stop->height()))))
    << "Stop is outside the " << window->width() << "x" << window->height() << " window";
  EXPECT_TRUE(plugin->pressReaches(stop)) << "a press on Stop does not reach Stop";
  const QPointF middle = frame->mapToItem(card,
    QPointF(frame->width() / 4.0, frame->height() / 2.0));
  EXPECT_FALSE(card->contains(middle)) << "gz-gui's card still takes the middle of the view";

  // S-01: the judge's answer held against Qt's own delivery, in gz-gui's real
  // window. A console running a request enables Stop; a real click at its
  // centre reaches the plugin's stop().
  using cite_console_gui::CellConsoleTestAccess;
  cite_interfaces::msg::ConsoleState running;
  running.state = cite_interfaces::msg::ConsoleState::RUNNING;
  running.busy = true;
  running.robot_started = true;
  CellConsoleTestAccess::hear(*plugin, running);
  QCoreApplication::processEvents();
  ASSERT_TRUE(stop->isEnabled());
  const QPointF stop_centre =
    stop->mapToScene(QPointF(stop->width() / 2.0, stop->height() / 2.0));
  QTest::mouseClick(window, Qt::LeftButton, Qt::NoModifier, stop_centre.toPoint());
  QCoreApplication::processEvents();
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(*plugin), 1u)
    << "a real press on Stop did not reach the plugin's stop()";
  // A real press in the middle of the view is taken by no item of the card.
  const QPointF middle_in_scene = frame->mapToScene(
    QPointF(frame->width() / 4.0, frame->height() / 2.0));
  QTest::mousePress(window, Qt::LeftButton, Qt::NoModifier, middle_in_scene.toPoint());
  QCoreApplication::processEvents();
  QQuickItem * grabber = window->mouseGrabberItem();
  EXPECT_TRUE(grabber == nullptr || (grabber != card && !card->isAncestorOf(grabber)))
    << "a press in the middle of the view was taken by the panel's card: "
    << grabber->metaObject()->className();
  QTest::mouseRelease(window, Qt::LeftButton, Qt::NoModifier, middle_in_scene.toPoint());
  QCoreApplication::processEvents();
  EXPECT_EQ(CellConsoleTestAccess::stops_pressed(*plugin), 1u);
  window->close();
}

// R-02: the window is maximized once gz-gui has applied its configuration,
// whose own resize (the configured 1920x1080) came after the panel was added
// and undid a maximize made then. The title toolbar is hidden.
TEST(PanelInGzGui, TheWindowIsMaximizedAfterGzGuiAppliesItsConfiguration)
{
  gz::gui::Application app(argc_, argv_);
  app.AddPluginPath(linked_plugin_dir());
  QTemporaryDir directory;
  ASSERT_TRUE(directory.isValid());
  const std::string path = directory.filePath("panel.config").toStdString();
  std::ofstream(path) << kConfig;
  ASSERT_TRUE(app.LoadConfig(path));
  auto * main = app.findChild<gz::gui::MainWindow *>();
  ASSERT_NE(main, nullptr);
  QQuickWindow * window = main->QuickWindow();
  ASSERT_NE(window, nullptr);
  window->show();
  QCoreApplication::processEvents();

  EXPECT_TRUE(window->windowStates() & Qt::WindowMaximized);
  ASSERT_NE(window->screen(), nullptr);
  EXPECT_EQ(window->frameGeometry().size(), window->screen()->availableGeometry().size())
    << "the window is " << window->width() << "x" << window->height()
    << ": the configured size was applied after the maximize, and undid it";
  auto * header = window->property("header").value<QQuickItem *>();
  ASSERT_NE(header, nullptr);
  EXPECT_FALSE(header->isVisible()) << "gz-gui's title toolbar is still shown";
  window->close();
}

int main(int argc, char ** argv)
{
  if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM")) {
    qputenv("QT_QPA_PLATFORM", QByteArray("offscreen"));
  }
  if (qEnvironmentVariableIsEmpty("QT_QUICK_BACKEND")) {
    qputenv("QT_QUICK_BACKEND", QByteArray("software"));
  }
  // The offscreen platform's one screen is 800x600, smaller than the frame's
  // minimum (1024x600): maximized there, the window would leave Stop outside
  // it. At half scale the screen is 1600x1200 in the window's own units.
  if (qEnvironmentVariableIsEmpty("QT_SCALE_FACTOR")) {
    qputenv("QT_SCALE_FACTOR", QByteArray("0.5"));
  }
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
