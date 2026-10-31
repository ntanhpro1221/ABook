// Một bản chạy (src/singleinstance.cpp, Q4), không cửa sổ nào: mỗi ca một tên kênh riêng, không bao giờ là kênh của app thật.
// Bản mới gửi đúng danh sách file cho bản đang chạy rồi thoát; không ai nghe thì tự làm bản đang chạy; bản đang chạy chết thì
// lần mở sau tự lên thay.
#include "singleinstance.h"

#include <QElapsedTimer>
#include <QProcess>
#include <QSignalSpy>
#include <QTest>
#include <QThread>
#include <QUuid>

namespace {

QString uniqueName() { return QStringLiteral("ABookDeskTest-") + QUuid::createUuid().toString(QUuid::Id128); }

// handOff chặn chờ trả lời, còn bản đang chạy cần vòng sự kiện để đáp: chạy handOff ở luồng khác.
bool handOffFromThread(const QString &name, const QStringList &files, int timeoutMs = 3000) {
    bool result = false;
    QThread *thread = QThread::create([&] {
        SingleInstance second(name);
        result = second.handOff(files, timeoutMs);
    });
    thread->start();
    while (!thread->wait(10))
        QCoreApplication::processEvents();
    delete thread;
    return result;
}

} // namespace

class SingleInstanceTests : public QObject {
    Q_OBJECT
private slots:
    void secondLaunchHandsItsFilesToTheRunningOne() {
        const QString name = uniqueName();
        SingleInstance first(name);
        QVERIFY(first.listen());
        QSignalSpy launched(&first, &SingleInstance::launched);
        const QStringList files{QStringLiteral("C:\\Sách nói\\Truyện mới.abook"), QStringLiteral("D:\\b c\\x.abookproj")};
        QVERIFY(handOffFromThread(name, files));
        QTRY_COMPARE(launched.count(), 1);
        QCOMPARE(launched.first().first().toStringList(), files);
        // Lần mở trần (bấm lối tắt khi app đang mở): vẫn báo, danh sách rỗng - bản đang chạy chỉ hiện cửa sổ.
        QVERIFY(handOffFromThread(name, {}));
        QTRY_COMPARE(launched.count(), 2);
        QVERIFY(launched.at(1).first().toStringList().isEmpty());
    }

    void nobodyListeningMeansThisOneRuns() {
        SingleInstance alone(uniqueName());
        QElapsedTimer timer;
        timer.start();
        QVERIFY(!alone.handOff({QStringLiteral("x.abook")}, 2000));
        QVERIFY2(timer.elapsed() < 1500, "không có ai nghe thì trả lời ngay, không chờ hết hạn");
        QVERIFY(alone.listen());
    }

    void aSecondServerOnTheSameNameIsRefused() {
        const QString name = uniqueName();
        SingleInstance first(name);
        QVERIFY(first.listen());
        SingleInstance second(name);
        QVERIFY(!second.listen());
    }

    void whenTheRunningOneDiesTheNextLaunchTakesOver() {
        const QString name = uniqueName();
        {
            SingleInstance first(name);
            QVERIFY(first.listen());
        }
        SingleInstance next(name);
        QVERIFY(!next.handOff({}, 1000));
        QVERIFY(next.listen());
        QSignalSpy launched(&next, &SingleInstance::launched);
        QVERIFY(handOffFromThread(name, {QStringLiteral("y.abook")}));
        QTRY_COMPARE(launched.count(), 1);
    }

    void aKilledRunningProcessDoesNotBlockTheName() {
        // Bản đang chạy chết đột ngột (bị giết, sập): Windows đóng ống theo tiến trình, tên trống ngay.
        const QString name = uniqueName();
        QProcess holder;
        holder.start(QCoreApplication::applicationFilePath(), {QStringLiteral("--hold"), name});
        QVERIFY(holder.waitForReadyRead(10000));
        QCOMPARE(holder.readLine().trimmed(), QByteArray("listening"));
        SingleInstance probe(name);
        QVERIFY(!probe.listen());
        holder.kill();
        QVERIFY(holder.waitForFinished(10000));
        QVERIFY(probe.listen());
    }

    void namesDependOnUserAndDataFolder() {
        const QString sid = QStringLiteral("S-1-5-21-1-2-3-1001");
        const QString a = SingleInstance::nameFor(sid, QStringLiteral("C:\\Users\\a\\AppData\\Local"));
        QCOMPARE(SingleInstance::nameFor(sid, QStringLiteral("c:/users/A/AppData/Local/")), a);
        QVERIFY(SingleInstance::nameFor(sid, QStringLiteral("C:\\Temp\\abook-inst\\local")) != a);
        QVERIFY(SingleInstance::nameFor(QStringLiteral("S-1-5-21-1-2-3-1002"), QStringLiteral("C:\\Users\\a\\AppData\\Local")) != a);
        QVERIFY(a.startsWith(QStringLiteral("ABookDesk-")));
        QVERIFY(SingleInstance::defaultName().startsWith(QStringLiteral("ABookDesk-")));
    }
};

int main(int argc, char *argv[]) {
    QCoreApplication app(argc, argv);
    // Tiến trình con của aKilledRunningProcessDoesNotBlockTheName: giữ tên cho tới khi bị giết.
    if (argc == 3 && QByteArray(argv[1]) == "--hold") {
        SingleInstance holder(QString::fromLocal8Bit(argv[2]));
        if (!holder.listen())
            return 2;
        std::fputs("listening\n", stdout);
        std::fflush(stdout);
        return app.exec();
    }
    SingleInstanceTests tests;
    return QTest::qExec(&tests, argc, argv);
}

#include "test_singleinstance.moc"
