#include "mediacontrols.h"
#include "player.h"
#include "fakes.h"
#include <QTemporaryDir>
#include <QThread>
#include <QNetworkReply>
#include <QtTest>
#include <thread>
#include <cstring>
#include <algorithm>

class FakeMediaSink final : public MediaSink {
public:
    MediaState last;
    QByteArray lastCover;
    int displays = 0, timelines = 0, playbacks = 0;
    void display(const MediaState &s, const QByteArray &cover) override { last = s; lastCover = cover; ++displays; }
    void playback(const MediaState &s) override { last = s; ++playbacks; }
    void timeline(const MediaState &s) override { last = s; ++timelines; }
};

class CoverReply final : public QNetworkReply {
public:
    CoverReply() { open(QIODevice::ReadOnly); }
    void abort() override {}
    void finish(const QByteArray &bytes) { data = bytes; setFinished(true); emit finished(); }
protected:
    qint64 readData(char *target, qint64 max) override {
        const auto count = std::min(max, qint64(data.size()));
        if (!count) return -1;
        std::memcpy(target, data.constData(), size_t(count)); data.remove(0, count); return count;
    }
private:
    QByteArray data;
};

class MediaControlsTests : public QObject {
    Q_OBJECT
private slots:
    void coversAreAsyncCachedAndIgnoreStaleReplies() {
        QTemporaryDir dir;
        FakeOut out; FakeNet net;
        Player player(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        auto fake = std::make_unique<FakeMediaSink>(); auto *sink = fake.get();
        QList<CoverReply *> replies; QStringList paths;
        MediaControls media(&player, &out, std::move(fake), [&](const QString &path) {
            paths << path; auto *reply = new CoverReply; replies << reply; return reply;
        });
        net.books[QStringLiteral("a")] = makeBook(QStringLiteral("a"));
        net.books[QStringLiteral("b")] = makeBook(QStringLiteral("b"));
        player.open(QStringLiteral("a"), 1, 0, false);
        QCOMPARE(paths, QStringList{QStringLiteral("/media/books/a/cover?v=7")});
        player.next(); QCOMPARE(paths.size(), 1);
        player.open(QStringLiteral("b"), 1, 0, true);
        QCOMPARE(paths.size(), 2);
        replies[0]->finish("cover-a");
        QVERIFY(sink->lastCover.isEmpty());
        replies[1]->finish("cover-b"); QCOMPARE(sink->lastCover, QByteArray("cover-b"));
        player.open(QStringLiteral("a"), 1, 0, true);
        QCOMPARE(paths.size(), 2); QCOMPARE(sink->lastCover, QByteArray("cover-a"));
        auto noCover = makeBook(QStringLiteral("c")); noCover.remove(QStringLiteral("cover"));
        net.books[QStringLiteral("c")] = noCover;
        player.open(QStringLiteral("c"), 1, 0, true);
        QCOMPARE(paths.size(), 2); QVERIFY(sink->lastCover.isEmpty());
        player.close(); QVERIFY(sink->lastCover.isEmpty());
    }
    void mapping() {
        QTemporaryDir dir;
        FakeOut out; FakeNet net;
        Player player(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        auto s = fromPlayer(player);
        QCOMPARE(s.status, MediaState::Stopped);
        QVERIFY(!s.loaded && !s.canNext && !s.canPrevious);
        auto book = makeBook(QStringLiteral("a"), 3);
        auto chapters = book.value(QStringLiteral("chapters")).toArray();
        auto first = chapters[0].toObject();
        for (const auto &key : {QStringLiteral("title"), QStringLiteral("fullTitle"), QStringLiteral("subtitle")}) first[key] = QString();
        chapters[0] = first; book[QStringLiteral("chapters")] = chapters;
        net.books[QStringLiteral("a")] = book;
        player.open(QStringLiteral("a"), 1, 0, false);
        s = fromPlayer(player);
        QCOMPARE(s.title, QStringLiteral("Chương 1"));
        QCOMPARE(s.artist, QStringLiteral("Sách a"));
        QCOMPARE(s.album, s.artist);
        QCOMPARE(s.status, MediaState::Paused);
        QVERIFY(s.loaded);
        QCOMPARE(s.canNext, player.canNext());
        QCOMPARE(s.canPrevious, player.canPrevious());
        player.resume(); QCOMPARE(fromPlayer(player).status, MediaState::Playing);
        player.jumpTo(3);
        s = fromPlayer(player);
        QVERIFY(!s.canNext && s.canPrevious);
        player.pause(); QCOMPARE(fromPlayer(player).status, MediaState::Paused);
        player.close(); QCOMPARE(fromPlayer(player).status, MediaState::Stopped);
    }
    void eventDrivenTimeline() {
        QTemporaryDir dir;
        FakeOut out; FakeNet net;
        qint64 now = 1'000'000;
        Player player(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr, [&] { return now; });
        auto fake = std::make_unique<FakeMediaSink>(); auto *sink = fake.get();
        MediaControls media(&player, &out, std::move(fake));
        net.books[QStringLiteral("a")] = makeBook(QStringLiteral("a"));
        player.open(QStringLiteral("a"), 1, 0, true);
        QCOMPARE(player.clock()->watchers(), 0);
        const int before = sink->timelines, displays = sink->displays;
        // 60 giây mô phỏng, kể cả nhịp đồng hồ khi có giao diện: SMTC không được theo nhịp ấy.
        for (int i = 1; i <= 60; ++i) {
            now += 1000; out.pos = i;
            player.clock()->refresh(); player.tick();
        }
        QCOMPARE(sink->timelines, before);
        QCOMPARE(sink->displays, displays);
        QCOMPARE(player.clock()->watchers(), 0);
        player.seek(12);
        QVERIFY(sink->timelines > before); QCOMPARE(sink->last.position, 12.0);
        int count = sink->timelines;
        player.setRate(1.5);
        QVERIFY(sink->timelines > count); QCOMPARE(sink->last.rate, 1.5);
        count = sink->timelines;
        player.next();
        QVERIFY(sink->timelines > count); QVERIFY(sink->displays > displays);
        count = sink->timelines;
        out.dur = 130; emit out.durationChanged(130);
        QVERIFY(sink->timelines > count); QCOMPARE(sink->last.duration, 130.0);
        count = sink->timelines;
        player.pause(); QVERIFY(sink->timelines > count);
        QCOMPARE(sink->last.status, MediaState::Paused);
    }
    void commandsUseUiThread() {
        QTemporaryDir dir;
        FakeOut out; FakeNet net;
        Player player(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        MediaControls media(&player, &out);
        net.books[QStringLiteral("a")] = makeBook(QStringLiteral("a"));
        player.open(QStringLiteral("a"), 1, 0, false);
        int count = 0;
        connect(&media, &MediaControls::commandExecuted, this, [&] {
            QCOMPARE(QThread::currentThread(), player.thread()); ++count;
        }, Qt::DirectConnection);
        auto send = [&](MediaCommand command, double seconds = 0) {
            const int before = count;
            std::thread worker([&] { media.dispatch(command, seconds); }); worker.join();
            QCOMPARE(count, before);
            QTRY_COMPARE(count, before + 1);
        };
        send(MediaCommand::Play); QVERIFY(player.playing());
        send(MediaCommand::Pause); QVERIFY(!player.playing());
        send(MediaCommand::Seek, 30); QCOMPARE(out.pos, 30.0);
        send(MediaCommand::Next); QCOMPARE(player.chapterId(), 2);
        send(MediaCommand::Previous); QCOMPARE(player.chapterId(), 1);
        // Lệnh đang đợi phải bị bỏ khi đối tượng nhận đã huỷ.
        auto doomed = std::make_unique<MediaControls>(&player, &out);
        doomed->dispatch(MediaCommand::Play); doomed.reset();
        player.pause();
        QCoreApplication::processEvents(); QVERIFY(!player.playing());
    }
};
QTEST_GUILESS_MAIN(MediaControlsTests)
#include "test_mediacontrols.moc"
