#include "musicwindowactivity.h"

#include <QtTest>
#include <memory>

class MusicWindowActivityTests : public QObject {
    Q_OBJECT
private slots:
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
