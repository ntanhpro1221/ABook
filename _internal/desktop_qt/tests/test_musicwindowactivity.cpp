#include "musicwindowactivity.h"
#include "graphicsidle.h"
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QSGRendererInterface>
#include <qpa/qwindowsysteminterface.h>
#include <qpa/qwindowsysteminterface_p.h>

#include <QtTest>
#include <memory>

class MusicWindowActivityTests : public QObject {
    Q_OBJECT
private slots:
    void releaseAfterObscurityPreservesStatePixelsAndVisibleMotion() {
        GraphicsIdle idle;
        QQmlEngine engine; QQmlComponent component(&engine);
        component.setData("import QtQuick\nRectangle { width: 80; height: 60; color: '#c12345'; property int saved: 7; property real phase: 0; property bool awake: true; NumberAnimation on phase { from: 0; to: 1; duration: 200; loops: Animation.Infinite; running: awake } }",QUrl());
        QQuickWindow window;window.setPosition(-10000,-10000);window.setFlag(Qt::WindowDoesNotAcceptFocus);window.setProperty("_q_showWithoutActivating",true);window.resize(80,60);
        auto *rect=qobject_cast<QQuickItem *>(component.create());QVERIFY2(rect,qPrintable(component.errorString()));
        rect->setParent(window.contentItem());rect->setParentItem(window.contentItem());
        struct Exposure final : QWindowSystemEventHandler {
            QWindow *window;
            bool visible = false;
            const bool native = QGuiApplication::platformName()==QStringLiteral("windows");
            explicit Exposure(QWindow *window) : window(window) { if(native) QWindowSystemInterfacePrivate::installWindowSystemEventHandler(this); }
            ~Exposure() { if(native) QWindowSystemInterfacePrivate::removeWindowSystemEventhandler(this); }
            bool sendEvent(QWindowSystemInterfacePrivate::WindowSystemEvent *event) override {
                if(event->type==QWindowSystemInterfacePrivate::Expose) {
                    auto *expose=static_cast<QWindowSystemInterfacePrivate::ExposeEvent *>(event);
                    if(expose->window==window) expose->isExposed=visible;
                }
                return QWindowSystemEventHandler::sendEvent(event);
            }
        } exposure(&window);
        const auto expose=[&](bool visible) {
            // A never-switched native test desktop is intentionally not exposed by
            // DWM. Exercise Qt's native RHI with synthetic TEST-ONLY exposure.
            if(QGuiApplication::platformName()==QStringLiteral("windows")) {
                // handleExposeEvent derives exposure from the actual platform
                // window, so a nonempty region alone does not expose it.
                exposure.visible=visible;
                QWindowSystemInterface::handleExposeEvent(&window,visible ? QRegion(0,0,80,60) : QRegion());
                QWindowSystemInterface::flushWindowSystemEvents();
            }
        };
        window.show();QCoreApplication::processEvents();expose(true);
        QTRY_VERIFY(window.isSceneGraphInitialized());
        QCOMPARE(window.grabWindow().pixelColor(20,20),QColor(QStringLiteral("#c12345")));
        const double phase=rect->property("phase").toDouble();QTest::qWait(60);QVERIFY(rect->property("phase").toDouble()!=phase);
        rect->setProperty("awake",false);window.showMinimized();expose(false);QCoreApplication::processEvents();idle.update();
        QVERIFY(!window.isPersistentGraphics());QVERIFY(!window.isPersistentSceneGraph());
        if(window.rendererInterface()->graphicsApi()!=QSGRendererInterface::Software) QTRY_VERIFY(!window.isSceneGraphInitialized());
        rect->setProperty("saved",42);rect->setProperty("color",QColor(QStringLiteral("#3456ab")));
        window.hide();window.showNormal();QCoreApplication::processEvents();expose(true);
        QTRY_VERIFY(window.isSceneGraphInitialized());QCOMPARE(rect->property("saved").toInt(),42);
        QCOMPARE(window.grabWindow().pixelColor(20,20),QColor(QStringLiteral("#3456ab")));
        rect->setProperty("awake",true);const double restored=rect->property("phase").toDouble();QTest::qWait(60);QVERIFY(rect->property("phase").toDouble()!=restored);
        QVERIFY(window.isPersistentGraphics());QVERIFY(window.isPersistentSceneGraph());
    }
    void miniReusesMainWindow() {
        bool relaxed = false;
        MusicWindowActivity activity([&relaxed](bool value) { relaxed = value; });
        QWindow window;
        window.setProperty("_q_showWithoutActivating",true);
        window.setFlag(Qt::WindowDoesNotAcceptFocus); window.setPosition(-10000,-10000);
        window.show();
        QTRY_VERIFY(!relaxed);
        // WindowMode changes the main window's flags and geometry for mini mode.
        window.setFlag(Qt::WindowStaysOnTopHint, true);
        window.resize(360, 112);
        window.showNormal();
        QTRY_VERIFY(!relaxed);
        window.hide();
        QTRY_VERIFY(relaxed);
        window.showNormal();
        QTRY_VERIFY(!relaxed);
        window.setFlag(Qt::WindowStaysOnTopHint, false);
        window.resize(1280, 800);
        window.showNormal();
        QTRY_VERIFY(!relaxed);
        window.showMinimized();
        QTRY_VERIFY(relaxed);
    }
    void allWindowsIncludingLateMini() {
        bool relaxed = false;
        MusicWindowActivity activity([&relaxed](bool value) { relaxed = value; });
        QVERIFY(relaxed);
        QWindow main;
        main.setProperty("_q_showWithoutActivating",true);
        main.setFlag(Qt::WindowDoesNotAcceptFocus); main.setPosition(-10000,-10000);
        main.show();
        QTRY_VERIFY(!relaxed);
        main.showMinimized();
        QTRY_VERIFY(relaxed);

        // Simulate a mini created after the main window was already minimized.
        auto mini = std::make_unique<QWindow>();
        mini->setProperty("_q_showWithoutActivating",true);
        mini->setFlag(Qt::WindowDoesNotAcceptFocus);
        mini->setPosition(-10000,-10000);
        mini->show();
        QTRY_VERIFY(!relaxed);
        main.hide();
        QCoreApplication::processEvents();
        QVERIFY(!relaxed);
        mini->showMinimized();
        QTRY_VERIFY(relaxed);
        mini->showNormal();
        QTRY_VERIFY(!relaxed);
        main.show();
        mini->hide();
        QCoreApplication::processEvents();
        QVERIFY(!relaxed);
        main.hide();
        QTRY_VERIFY(relaxed);
        mini->show();
        QTRY_VERIFY(!relaxed);
        mini.reset();
        QTRY_VERIFY(relaxed);
    }
};

int main(int argc,char **argv) {
    if(qgetenv("QT_QPA_PLATFORM")=="offscreen") qputenv("QT_QUICK_BACKEND","software");
    QQuickWindow::setDefaultAlphaBuffer(true);
    QGuiApplication app(argc,argv);MusicWindowActivityTests tests;return QTest::qExec(&tests,argc,argv);
}
#include "test_musicwindowactivity.moc"
