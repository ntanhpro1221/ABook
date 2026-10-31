// Backend start limit with a fake host: a real Python process that says Ready late, at once, or never.
#include "backend.h"
#include "bench.h"

#include <QCloseEvent>
#include <QDir>
#include <QFile>
#include <QTemporaryDir>
#include <QWindow>
#include <QtTest>

void Bench::mark(const QString &) {}

// Main.qml with closeToTray: a close request hides the window and is refused.
class TrayWindow : public QWindow {
protected:
    void closeEvent(QCloseEvent *event) override { event->ignore(); }
};

class BackendTests : public QObject {
    Q_OBJECT
    QTemporaryDir dir;

    void write(const QString &relative, const QByteArray &text) {
        QDir().mkpath(QFileInfo(dir.filePath(relative)).absolutePath());
        QFile file(dir.filePath(relative));
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write(text);
    }
    void startWith(Backend &backend, const char *mode, int limitMs) {
        qputenv("ABOOK_TEST_HOST", mode);
        Backend::s_startLimitMs = limitMs;
        backend.start();
        QCOMPARE(backend.state(), Backend::Starting);
    }

private slots:
    void initTestCase() {
        QVERIFY(dir.isValid());
        write(QStringLiteral("abook/__init__.py"), "");
        write(QStringLiteral("abook/webui/__init__.py"), "");
        // ABOOK_TEST_HOST: silent = never Ready (hung start), late = Ready after 1.5 s, ready = Ready at once, installer = Ready
        // then, in one write, asks the shell to run an "installer" (this Python, touching installer-ran) followed by an event,
        // the way webui/updater.py does after a good signature. Quits on stdin "quit" (writing host-quit) or EOF.
        write(QStringLiteral("abook/webui/host.py"),
              "import json, os, pathlib, sys, time\n"
              "root = pathlib.Path(__file__).resolve().parents[2]\n"
              "mode = os.environ.get('ABOOK_TEST_HOST')\n"
              "if mode == 'late':\n"
              "    time.sleep(1.5)\n"
              "if mode in ('late', 'ready', 'installer'):\n"
              "    print('{\"ready\": \"http://127.0.0.1:9/?t=fixture\"}', flush=True)\n"
              "if mode == 'installer':\n"
              "    touch = f'import pathlib; pathlib.Path({str(root / \"installer-ran\")!r}).write_text(\"x\")'\n"
              "    sys.stdout.write(json.dumps({'run_installer': sys.executable, 'args': ['-c', touch]}) + '\\n'\n"
              "                     + json.dumps({'event': 'abook-update-checked', 'detail': {}}) + '\\n')\n"
              "    sys.stdout.flush()\n"
              "for line in sys.stdin:\n"
              "    if 'quit' in line:\n"
              "        if mode == 'installer':\n"
              "            (root / 'host-quit').write_text('x')\n"
              "        break\n");
        QString python = qEnvironmentVariable("ABOOK_PYTHON");
        if (python.isEmpty()) python = QStringLiteral("D:/Novels/ABook/_internal/runtime/.venv/Scripts/python.exe");
        QVERIFY2(QFileInfo(python).isFile(), qPrintable(python));
        qputenv("ABOOK_HOST_PYTHON", python.toUtf8());
        qputenv("ABOOK_HOST_APP", dir.path().toUtf8());
        qputenv("LOCALAPPDATA", dir.filePath(QStringLiteral("local")).toUtf8());    // host.log under the test folder, never the user's
    }
    void hostThatNeverSaysReadyFails() {
        Backend backend(nullptr);
        startWith(backend, "silent", 800);
        QTRY_COMPARE_WITH_TIMEOUT(backend.state(), Backend::Failed, 10000);
        QCOMPARE(backend.message(), QStringLiteral("ABook chưa mở được. Bạn thử lại; nếu vẫn lỗi, xem nhật ký trong Cài đặt."));
        // "Thử lại" (LibraryScreen, ConnectionPopover) = restart: a working host opens the app.
        qputenv("ABOOK_TEST_HOST", "ready");
        Backend::s_startLimitMs = 60'000;
        backend.restart();
        QCOMPARE(backend.state(), Backend::Starting);
        QTRY_COMPARE_WITH_TIMEOUT(backend.state(), Backend::Ready, 15000);
        QCOMPARE(backend.port(), 9);
    }
    void lateReadyStillOpens() {
        Backend backend(nullptr);
        startWith(backend, "late", 300);
        QTRY_COMPARE_WITH_TIMEOUT(backend.state(), Backend::Failed, 10000);
        QTRY_COMPARE_WITH_TIMEOUT(backend.state(), Backend::Ready, 10000);
    }
    void quickHostIsNotCut() {
        Backend backend(nullptr);
        startWith(backend, "ready", 3000);
        QTRY_COMPARE_WITH_TIMEOUT(backend.state(), Backend::Ready, 10000);
        QTest::qWait(3500); // fixed: proves absence (the start limit does not fire after Ready)
        QCOMPARE(backend.state(), Backend::Ready);
    }
    // Q7: after starting the installer the app leaves even though its window refuses to close (closeToTray hides the window
    // instead). QGuiApplication::quit() asks the windows first, so the app used to hide in the tray until the installer's
    // process stop killed it (exit -1, test_installer). The host is asked to quit and quits on its own, no kill.
    void runInstallerLeavesEvenWhenTheWindowStaysOpen() {
        QFile::remove(dir.filePath(QStringLiteral("installer-ran")));
        QFile::remove(dir.filePath(QStringLiteral("host-quit")));
        TrayWindow window;
        window.show();
        QEventLoop loop;    // stands in for app.exec()
        QTimer::singleShot(20000, &loop, [&loop] { loop.exit(42); });
        Backend backend(nullptr);
        startWith(backend, "installer", 60'000);
        QCOMPARE(loop.exec(), 0);
        QVERIFY(QFileInfo::exists(dir.filePath(QStringLiteral("host-quit"))));
        QTRY_VERIFY_WITH_TIMEOUT(QFileInfo::exists(dir.filePath(QStringLiteral("installer-ran"))), 15000);
    }
};
QTEST_MAIN(BackendTests)
#include "test_backend.moc"
