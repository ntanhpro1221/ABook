#include "musicwindowactivity.h"

#include <QtTest>
#include <memory>

class MusicWindowActivityTests : public QObject {
    Q_OBJECT
private slots:
    void miniReusesMainWindow() {
        bool relaxed = false;
        MusicWindowActivity activity([&relaxed](bool value) { relaxed = value; });
        QWindow window;
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
        main.show();
        QTRY_VERIFY(!relaxed);
        main.showMinimized();
        QTRY_VERIFY(relaxed);

        // Simulate a mini created after the main window was already minimized.
        auto mini = std::make_unique<QWindow>();
        mini->setFlag(Qt::WindowDoesNotAcceptFocus);
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

QTEST_MAIN(MusicWindowActivityTests)
#include "test_musicwindowactivity.moc"
