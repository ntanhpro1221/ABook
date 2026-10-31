// Backend start limit with a fake host: a real Python process that says Ready late, at once, or never.
#include "backend.h"
#include "bench.h"

#include <QDir>
#include <QFile>
#include <QTemporaryDir>
#include <QtTest>

void Bench::mark(const QString &) {}

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
        // ABOOK_TEST_HOST: silent = never Ready (hung start), late = Ready after 1.5 s, ready = Ready at once. Quits on stdin "quit" or EOF.
        write(QStringLiteral("abook/webui/host.py"),
              "import os, sys, time\n"
              "mode = os.environ.get('ABOOK_TEST_HOST')\n"
              "if mode == 'late':\n"
              "    time.sleep(1.5)\n"
              "if mode in ('late', 'ready'):\n"
              "    print('{\"ready\": \"http://127.0.0.1:9/?t=fixture\"}', flush=True)\n"
              "for line in sys.stdin:\n"
              "    if 'quit' in line:\n"
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
        QTest::qWait(3500); // fixed: proves the limit does not fire after Ready
        QCOMPARE(backend.state(), Backend::Ready);
    }
};
QTEST_GUILESS_MAIN(BackendTests)
#include "test_backend.moc"
