#include "desktopapi.h"
#include "backend.h"
#include "hostcall.h"
#include "hostnet.h"
#include "hostwait.h"
#include "fakes.h"
#include "feedback.h"
#include "hostmessage.h"
#include "librarymodel.h"
#include <QFile>
#include <QImage>
#include <QTemporaryDir>
#include <QtEndian>
#include <cmath>
#include <QtTest>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTimer>
#include <QJsonDocument>
#include <QSignalSpy>

namespace { Backend::Endpoint testEndpoint; }
Backend::Endpoint Backend::endpoint() { return testEndpoint; }
Backend *Backend::instance() { return nullptr; }
void Backend::refreshLibrary() {}

class DesktopApiTests : public QObject {
    Q_OBJECT
    QTcpServer host;
    QByteArray received;
    QByteArray answer;
    bool hold = false;
    int holdFirst = 0;     // the first N requests get no answer (a silent host), later ones the answer
    int requests = 0;      // requests the host received in full
    int dripMs = 0;        // > 0: the answer goes out a few bytes at a time, one piece every dripMs
    QQmlEngine engine;
    std::unique_ptr<QObject> owner;
    DesktopApi *api = nullptr;
    QJSValue done() { return engine.evaluate(QStringLiteral("(function(status, data) { result = {status:status,data:data}; })")); }
    void clear() { received.clear(); requests = holdFirst = dripMs = 0; HostCall::s_idleOverrideMs = 0; engine.globalObject().setProperty(QStringLiteral("result"), QJSValue(QJSValue::NullValue)); }
private slots:
    void libraryPreservesHostFields() {
        LibraryModel library;
        const auto progress = QJsonObject{{QStringLiteral("finished"), false}, {QStringLiteral("caughtUp"), true}, {QStringLiteral("heardSeconds"), 120}, {QStringLiteral("fraction"), 0.5}};
        QJsonObject book{{QStringLiteral("id"), QStringLiteral("book")}, {QStringLiteral("title"), QStringLiteral("Tên sách")},
            {QStringLiteral("stage"), QStringLiteral("text")}, {QStringLiteral("progress"), progress},
            {QStringLiteral("series"), QJsonObject{{QStringLiteral("root"), QStringLiteral("first")}, {QStringLiteral("part"), 2}}},
            {QStringLiteral("remote"), QJsonObject{{QStringLiteral("computer"), QStringLiteral("Máy của bạn")}}}};
        QSignalSpy revisions(&library, &LibraryModel::revisionChanged);
        library.setBooks({book});
        QCOMPARE(library.rowCount(), 1);
        const auto row = library.book(0);
        QCOMPARE(row.value(QStringLiteral("stage")).toString(), QStringLiteral("text"));
        QCOMPARE(row.value(QStringLiteral("bookId")).toString(), QStringLiteral("book"));
        QCOMPARE(row.value(QStringLiteral("progress")).toDouble(), 0.5);
        QCOMPARE(row.value(QStringLiteral("listeningProgress")).toMap().value(QStringLiteral("caughtUp")).toBool(), true);
        QCOMPARE(row.value(QStringLiteral("series")).toMap().value(QStringLiteral("part")).toInt(), 2);
        QCOMPARE(row.value(QStringLiteral("source")).toString(), QStringLiteral("Máy của bạn"));
        book.insert(QStringLiteral("title"), QStringLiteral("Tên đã đổi"));
        library.setBooks({book});
        QCOMPARE(revisions.size(), 2);
        QCOMPARE(library.book(0).value(QStringLiteral("title")).toString(), QStringLiteral("Tên đã đổi"));
        QVERIFY(library.book(-1).isEmpty());
    }
    void initTestCase() {
        QVERIFY(host.listen(QHostAddress::LocalHost));
        testEndpoint = {host.serverPort(), QByteArray("fixture-token")};
        connect(&host, &QTcpServer::newConnection, this, [this] {
            auto *socket = host.nextPendingConnection();
            auto bytes = std::make_shared<QByteArray>();
            connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            connect(socket, &QTcpSocket::readyRead, this, [this,socket,bytes] {
                *bytes += socket->readAll();
                const int header = bytes->indexOf("\r\n\r\n");
                if (header < 0) return;
                int length = 0;
                for (auto line : bytes->left(header).split('\n'))
                    if (line.toLower().startsWith("content-length:")) length = line.mid(15).trimmed().toInt();
                if (bytes->size() < header + 4 + length) return;
                received = *bytes;
                bytes->clear();
                ++requests;
                if (hold || requests <= holdFirst) return;
                const QByteArray reply = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: " + QByteArray::number(answer.size()) + "\r\n\r\n" + answer;
                if (!dripMs) {
                    socket->write(reply);
                    socket->disconnectFromHost();
                    return;
                }
                // Like the host's streamed answers: the head at once, then the body a few bytes at a time
                // (Qt reports no progress inside a half-received head, so HostCall's limit counts body bytes).
                const qsizetype head = reply.indexOf("\r\n\r\n") + 4;
                socket->write(reply.left(head));
                auto *pieces = new QTimer(socket);
                auto left = std::make_shared<QByteArray>(reply.mid(head));
                connect(pieces, &QTimer::timeout, socket, [socket, pieces, left] {
                    socket->write(left->left(8)); left->remove(0, 8);
                    if (left->isEmpty()) { pieces->stop(); socket->disconnectFromHost(); }
                });
                pieces->start(dripMs);
            });
        });
        qmlRegisterType<DesktopApi>("ApiTest",1,0,"DesktopApi");
        QQmlComponent component(&engine);
        component.setData("import QtQml\nimport ApiTest 1.0\nQtObject { property DesktopApi api: DesktopApi {} }",QUrl());
        owner.reset(component.create());
        QVERIFY2(owner, qPrintable(component.errorString()));
        api = qobject_cast<DesktopApi *>(owner->property("api").value<QObject *>());
        QVERIFY(api);
        clear();
    }
    void jsonArrayAndHeader() {
        clear(); answer = "[{\"id\":\"voice\"}]";
        api->request(QStringLiteral("GET"),QStringLiteral("/api/readaloud/voices"),QJSValue(QJSValue::NullValue),done());
        QTRY_VERIFY(!engine.globalObject().property(QStringLiteral("result")).isNull());
        QVERIFY(received.startsWith("GET /api/readaloud/voices "));
        QVERIFY(received.toLower().contains("x-ebook-token: fixture-token"));
        QVERIFY(engine.globalObject().property(QStringLiteral("result")).property(QStringLiteral("data")).isArray());
    }
    void writes_data() {
        QTest::addColumn<QString>("path");
        QTest::addColumn<QByteArray>("method");
        QTest::addColumn<QString>("json");
        QTest::newRow("settings") << QStringLiteral("/api/preferences") << QByteArray("PUT") << QStringLiteral("{\"sleepSchedule\":{\"from\":\"22:00\",\"to\":\"06:00\",\"minutes\":30}}");
        QTest::newRow("add") << QStringLiteral("/api/listen/import") << QByteArray("POST") << QStringLiteral("{\"path\":\"D:/Sách/Truyện.epub\",\"title\":\"Tên không cắt\",\"sourceFingerprint\":\"fixture\",\"chapters\":[{\"index\":2}]}");
        QTest::newRow("edit") << QStringLiteral("/api/books/fixture/title") << QByteArray("PUT") << QStringLiteral("{\"title\":\"Tên sách dài không cắt\"}");
        QTest::newRow("cover") << QStringLiteral("/api/books/fixture/cover") << QByteArray("DELETE") << QStringLiteral("null");
    }
    void writes() {
        QFETCH(QString,path); QFETCH(QByteArray,method); QFETCH(QString,json);
        clear(); answer = "{\"saved\":true}";
        const auto body = engine.evaluate(QStringLiteral("(") + json + QStringLiteral(")"));
        api->request(QString::fromLatin1(method),path,body,done());
        QTRY_VERIFY(!engine.globalObject().property(QStringLiteral("result")).isNull());
        QVERIFY(received.startsWith(method + " " + path.toUtf8() + " "));
        const auto payload = received.mid(received.indexOf("\r\n\r\n") + 4);
        if (json != QStringLiteral("null")) QCOMPARE(QJsonDocument::fromJson(payload),QJsonDocument::fromJson(json.toUtf8()));
        else QVERIFY(payload.isEmpty());
    }
    // ---- kênh của vỏ: dòng JSON host gửi lên (D3) ----
    void hostMessages() {
        using HostMessage::Kind;
        const auto ready = HostMessage::parse("{\"ready\": \"http://127.0.0.1:47123/?t=abc\"}");
        QCOMPARE(ready.kind, Kind::Ready);
        QCOMPARE(ready.address, QStringLiteral("http://127.0.0.1:47123/?t=abc"));
        const auto update = HostMessage::parse("{\"event\": \"abook-update\", \"detail\": {\"version\": \"0.4.148\", \"notes\": \"Sửa lỗi\"}}");
        QCOMPARE(update.kind, Kind::Event);
        QCOMPARE(update.event, QStringLiteral("abook-update"));
        QCOMPARE(update.detail.toMap().value(QStringLiteral("version")).toString(), QStringLiteral("0.4.148"));
        const auto gone = HostMessage::parse("{\"event\": \"abook-update\", \"detail\": null}");
        QCOMPARE(gone.kind, Kind::Event);
        QVERIFY(gone.detail.isNull());
        QCOMPARE(HostMessage::parse("{\"check_update\": true}").kind, Kind::CheckUpdate);
        QCOMPARE(HostMessage::parse("{\"install_update\": true}").kind, Kind::InstallUpdate);
        QCOMPARE(HostMessage::parse("{\"dialog\": 3}").kind, Kind::None);
        QCOMPARE(HostMessage::parse("không phải JSON").kind, Kind::None);
        // Vỏ Qt chưa có bộ cập nhật: nút có lời ngay, đúng câu máy chủ dùng cho bản không tự cập nhật
        const QVariantMap checked = HostMessage::updateCheckedWithoutUpdater();
        QCOMPARE(checked.value(QStringLiteral("state")).toString(), QStringLiteral("failed"));
        QCOMPARE(checked.value(QStringLiteral("message")).toString(), QStringLiteral("Bản chạy từ mã nguồn không tự cập nhật"));
    }

    // ---- tiếng chạm (shared/feedback.ts, DESIGN 5.3) ----
    void feedbackNotesMatchTheWebTable() {
        QCOMPARE(Feedback::notes(QStringLiteral("toggle")).size(), 1);
        QCOMPARE(Feedback::notes(QStringLiteral("toggle"))[0].pitch, 1568.0);
        QCOMPARE(Feedback::notes(QStringLiteral("tick"))[0].level, -32.0);
        QCOMPARE(Feedback::notes(QStringLiteral("confirm")).size(), 2);
        QCOMPARE(Feedback::notes(QStringLiteral("done")).size(), 3);
        QCOMPARE(Feedback::notes(QStringLiteral("sleepWarn"))[0].pitch, 220.0);
        for (const char *silent : {"tap", "playPause", "reject", "longPress", "khác"})
            QVERIFY(Feedback::notes(QString::fromLatin1(silent)).isEmpty());
    }
    void feedbackWavIsShortQuietPcm() {
        const QByteArray wav = Feedback::wav(Feedback::notes(QStringLiteral("toggle")));
        QVERIFY(wav.startsWith("RIFF"));
        QCOMPARE(wav.mid(8, 8), QByteArray("WAVEfmt "));
        QCOMPARE(qFromLittleEndian<quint32>(wav.constData() + 24), 44100u);
        QCOMPARE(qFromLittleEndian<quint16>(wav.constData() + 34), quint16(16));
        const int samples = int(qFromLittleEndian<quint32>(wav.constData() + 40) / 2);
        QVERIFY(samples <= 44100 * 0.1);                  // 5 ms lặng + 60 ms nốt + 20 ms đuôi
        int peak = 0, firstLoud = -1;
        for (int i = 0; i < samples; ++i) {
            const int v = std::abs(int(qFromLittleEndian<qint16>(wav.constData() + 44 + 2 * i)));
            peak = std::max(peak, v);
            if (firstLoud < 0 && v > 100) firstLoud = i;
        }
        const double expected = std::pow(10.0, -30.0 / 20.0) * 32767;   // -30 dB
        QVERIFY2(peak > expected * 0.85 && peak <= expected * 1.02, qPrintable(QString::number(peak)));
        QVERIFY(firstLoud >= int(44100 * 0.005));          // 5 ms đầu lặng
        // Ba nốt của "done" dài hơn một nốt "tick"
        QVERIFY(Feedback::wav(Feedback::notes(QStringLiteral("done"))).size() > Feedback::wav(Feedback::notes(QStringLiteral("tick"))).size());
    }
    void feedbackPlaysOnlyWhenAllowed() {
        FakeOut *out = nullptr;
        int made = 0;
        Feedback feedback([&] { ++made; return out = new FakeOut; }, nullptr);
        feedback.play(QStringLiteral("tap"));                // nút thường: im, chưa mở bộ phát nào
        QCOMPARE(made, 0);
        feedback.play(QStringLiteral("toggle"));
        QCOMPARE(made, 1);
        QVERIFY(out->isPlaying);
        QCOMPARE(out->volume, 1.0);
        QVERIFY(out->url.isLocalFile());
        QFile file(out->url.toLocalFile());
        QVERIFY(file.open(QIODevice::ReadOnly));
        QVERIFY(file.read(4) == "RIFF");
        QCOMPARE(feedback.played(), 1);
        QCOMPARE(feedback.lastKind(), QStringLiteral("toggle"));
        // Sách đang phát: tiếng chạm im, trừ nốt báo hẹn giờ ngủ
        feedback.setBookPlaying(true);
        feedback.play(QStringLiteral("confirm"));
        QCOMPARE(feedback.played(), 1);
        feedback.play(QStringLiteral("sleepWarn"));
        QCOMPARE(feedback.played(), 2);
        QCOMPARE(out->loads, 2);
        // "Âm thanh chạm" tắt: im hết, kể cả hẹn giờ
        feedback.setBookPlaying(false);
        QSignalSpy changed(&feedback, &Feedback::soundsChanged);
        feedback.setSounds(false);
        QCOMPARE(changed.size(), 1);
        feedback.play(QStringLiteral("toggle"));
        feedback.play(QStringLiteral("sleepWarn"));
        QCOMPARE(feedback.played(), 2);
        QCOMPARE(made, 1);                                    // một bộ phát dùng lại cho mọi tiếng
    }
    // Nghe thử câu mẫu của nhân vật (trang sách › Nhân vật): QML biết clip bắt đầu / hết / hỏng qua ba tín hiệu của DesktopApi.
    void previewSignalsFollowTheOutput() {
        FakeOut out;
        DesktopApi::setPreviewOut(&out);
        QSignalSpy started(api, &DesktopApi::previewStarted);
        QSignalSpy ended(api, &DesktopApi::previewEnded);
        QSignalSpy failed(api, &DesktopApi::previewFailed);
        api->preview(QStringLiteral("/media/books/b/samples/3"));
        QCOMPARE(started.size(), 1);
        QCOMPARE(out.url.path(), QStringLiteral("/media/books/b/samples/3"));
        out.finish();
        QCOMPARE(ended.size(), 1);
        out.fail(QStringLiteral("404"));
        QCOMPARE(failed.size(), 1);
        QCOMPARE(failed.takeFirst().at(0).toString(), QStringLiteral("404"));
        DesktopApi::setPreviewOut(nullptr);
    }
    // Trình tạo sách của Studio máy khác: kể file / thư mục đã chọn (tên thư mục còn nguyên, tới tầng thứ hai) và đọc nguyên byte để gửi lên
    void sourceFilesListFilesAndFolders() {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        QDir root(dir.path());
        QVERIFY(root.mkpath(QStringLiteral("Lò rèn/Tập 1")));
        const auto touch = [&](const QString &relative, const QByteArray &bytes) {
            QFile file(root.filePath(relative));
            QVERIFY(file.open(QIODevice::WriteOnly));
            file.write(bytes);
        };
        touch(QStringLiteral("Lò rèn/001.txt"), "một");
        touch(QStringLiteral("Lò rèn/Tập 1/002.txt"), "hai");
        touch(QStringLiteral("lẻ.txt"), "ba");
        const auto list = api->sourceFiles({root.filePath(QStringLiteral("Lò rèn")), root.filePath(QStringLiteral("lẻ.txt")), root.filePath(QStringLiteral("không có"))});
        QCOMPARE(list.size(), 3);
        QCOMPARE(list.at(0).toMap().value(QStringLiteral("path")).toString(), QStringLiteral("Lò rèn/001.txt"));
        QCOMPARE(list.at(1).toMap().value(QStringLiteral("path")).toString(), QStringLiteral("Lò rèn/Tập 1/002.txt"));
        QCOMPARE(list.at(2).toMap().value(QStringLiteral("path")).toString(), QString());      // file lẻ: không có đường thư mục
        QCOMPARE(list.at(2).toMap().value(QStringLiteral("name")).toString(), QStringLiteral("lẻ.txt"));
        QCOMPARE(list.at(2).toMap().value(QStringLiteral("size")).toInt(), 2);
        QCOMPARE(api->fileBase64(list.at(0).toMap().value(QStringLiteral("local")).toString()), QStringLiteral("beG7mXQ="));
        QVERIFY(api->fileBase64(root.filePath(QStringLiteral("không có"))).isEmpty());
    }
    // Ảnh bìa: file -> data URL PNG (cạnh dài tối đa 1600); bộ nhớ tạm không có ảnh (hay không có cửa sổ) thì trả rỗng, không văng
    void coverImageDataAndClipboard() {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        QImage big(2400, 1200, QImage::Format_RGB32);
        big.fill(Qt::darkYellow);
        const QString path = QDir(dir.path()).filePath(QStringLiteral("bìa.png"));
        QVERIFY(big.save(path));
        const QString data = api->imageData(QUrl::fromLocalFile(path));
        QVERIFY(data.startsWith(QStringLiteral("data:image/png;base64,")));
        const QImage back = QImage::fromData(QByteArray::fromBase64(data.mid(22).toLatin1()), "PNG");
        QCOMPARE(back.width(), 1600);
        QCOMPARE(back.height(), 800);
        QVERIFY(api->imageData(QUrl(QStringLiteral("https://example.com/a.png"))).isEmpty());
        QVERIFY(api->imageData(QUrl::fromLocalFile(QDir(dir.path()).filePath(QStringLiteral("không có.png")))).isEmpty());
        QVERIFY(api->clipboardImage().isEmpty());
    }
    // ---- one wait policy for C++ and QML (hostwait.h): limit = no byte for N ms, one more attempt, then timeout ----
    void longWorkWaitsPastTheHostsOwnDeadline() {
        // Host Edge deadline: TOTAL_TIMEOUT 90 s + 1 s (abook/readaloud/edge.py): its error with a reason must come first.
        QVERIFY(HostWait::kLongIdleMs > 91'000);
        QVERIFY(HostWait::kStallMs > HostWait::kAttempts * HostWait::kLongIdleMs);
    }
    void longWorkMatchesWholeSegments_data() {
        QTest::addColumn<QString>("path");
        QTest::addColumn<int>("idle");
        const int longer = HostWait::kLongIdleMs, plain = HostWait::kIdleMs;
        for (const char *path : {"/api/readaloud/clip", "/api/readaloud/clip?x=1", "/api/books/b1/voice/preview",
                 "/api/books/b1/voice/preview?x=1", "/api/books/abc/pronunciation/preview", "/api/books/abc/music/rebuild",
                 "/api/books/abc/music", "/api/books/abc/edits/fold", "/api/scan", "/api/sources/split", "/api/first-person",
                 "/api/books", "/sync/v1/books/abc/edits"})
            QTest::newRow(path) << QString::fromLatin1(path) << longer;
        for (const char *path : {"/api/books/abc", "/api/books/a/b/voice/preview", "/api/scanx", "/api/cast/scan",
                 "/api/books/abc/music/track", "/api/listen/import/preview", "/api/readaloud/voices", "/sync/v1/books/abc"})
            QTest::newRow(path) << QString::fromLatin1(path) << plain;
    }
    void longWorkMatchesWholeSegments() {
        QFETCH(QString, path);
        QFETCH(int, idle);
        QCOMPARE(HostWait::idleMs(path), idle);
    }
    void silentHostIsAskedOnceMoreThenTimesOut() {
        clear(); hold = true; HostCall::s_idleOverrideMs = 150;
        api->request(QStringLiteral("POST"),QStringLiteral("/api/books/b1/voice/preview"),engine.evaluate(QStringLiteral("({voice:'v'})")),done());
        QTRY_VERIFY_WITH_TIMEOUT(!engine.globalObject().property(QStringLiteral("result")).isNull(), 3000);
        QCOMPARE(engine.globalObject().property(QStringLiteral("result")).property(QStringLiteral("status")).toInt(), 0);
        QCOMPARE(requests, HostWait::kAttempts);
        hold = false;
    }
    void secondAttemptCarriesTheAnswer() {
        clear(); holdFirst = 1; answer = "{\"url\":\"/media/readaloud/a.mp3\"}"; HostCall::s_idleOverrideMs = 150;
        api->request(QStringLiteral("POST"),QStringLiteral("/api/readaloud/clip"),engine.evaluate(QStringLiteral("({voice:'v',text:'t'})")),done());
        QTRY_VERIFY_WITH_TIMEOUT(!engine.globalObject().property(QStringLiteral("result")).isNull(), 3000);
        const auto result = engine.globalObject().property(QStringLiteral("result"));
        QCOMPARE(result.property(QStringLiteral("status")).toInt(), 200);
        QCOMPARE(result.property(QStringLiteral("data")).property(QStringLiteral("url")).toString(), QStringLiteral("/media/readaloud/a.mp3"));
        QCOMPARE(requests, 2);
    }
    void slowAnswerThatKeepsComingIsNotCut() {
        clear(); dripMs = 60; HostCall::s_idleOverrideMs = 250;
        answer = "{\"text\":\"" + QByteArray(120, 'a') + "\"}";    // ~16 body pieces over ~1 s: 4x the limit in total, never silent for it
        api->request(QStringLiteral("GET"),QStringLiteral("/api/listen/books/b1/chapters/1/text"),QJSValue(QJSValue::NullValue),done());
        QTRY_VERIFY_WITH_TIMEOUT(!engine.globalObject().property(QStringLiteral("result")).isNull(), 6000);
        const auto result = engine.globalObject().property(QStringLiteral("result"));
        QCOMPARE(result.property(QStringLiteral("status")).toInt(), 200);
        QCOMPARE(result.property(QStringLiteral("data")).property(QStringLiteral("text")).toString().size(), 120);
        QCOMPARE(requests, 1);
    }
    void hostNetReportsASilentHostAsTimeout() {
        clear(); hold = true; HostCall::s_idleOverrideMs = 150;
        QNetworkAccessManager net;
        HostNet host(&net);
        int status = -1; QJsonObject body;
        host.request("POST", QStringLiteral("/api/readaloud/clip"), {{QStringLiteral("text"), QStringLiteral("t")}}, [&](int code, const QJsonObject &answer) { status = code; body = answer; });
        QTRY_VERIFY_WITH_TIMEOUT(status >= 0, 3000);
        QCOMPARE(status, 0);
        QCOMPARE(requests, HostWait::kAttempts);
        QCOMPARE(body.value(QStringLiteral("reason")).toString(), QStringLiteral("timeout"));    // SpeechOut: "Giọng đang chọn đang không dùng được."
        hold = false;
    }
    void hostNetAbortCallsNothing() {
        clear(); hold = true;
        QNetworkAccessManager net;
        HostNet host(&net);
        bool called = false;
        const auto abort = host.requestCancelable("POST", QStringLiteral("/api/readaloud/clip"), {}, [&](int, const QJsonObject &) { called = true; });
        QTRY_VERIFY(!received.isEmpty());
        abort();
        QTest::qWait(80); // fixed: proves absence
        QVERIFY(!called);
        hold = false;
    }
    void abortDoesNotDeliverLateReply() {
        clear(); hold = true;
        const int id = api->request(QStringLiteral("GET"),QStringLiteral("/api/books/fixture/cover/search?q=old"),QJSValue(QJSValue::NullValue),done());
        QTRY_VERIFY(!received.isEmpty());
        api->cancel(id);
        QTest::qWait(80); // fixed: proves absence
        QVERIFY(engine.globalObject().property(QStringLiteral("result")).isNull());
        hold = false;
    }
};
QTEST_GUILESS_MAIN(DesktopApiTests)
#include "test_desktopapi.moc"
