#include "speechout.h"
#include "outputdevices.h"
#include "fakes.h"
#include "textscript.h"
#include <QtTest>
#include <cmath>
#include <limits>

// An online voice that is slow in proportion to length, like Edge (listen audit §20: a 22.2 s clip took ~10.7 s): each clip arrives
// LATENCY + PER_SECOND x its length later on the test's fake clock. Clip length = characters / CHARS_PER_SECOND.
class SlowNet final : public PlayerNet {
public:
    static constexpr double LATENCY = 0.5, PER_SECOND = 0.45, CHARS_PER_SECOND = 14;
    struct Pending { qint64 at; std::function<void()> reply; };
    SlowNet(const qint64 &now, QString text) : m_now(now), m_text(std::move(text)) {}
    QUrl audioUrl(const QString &, int) const override { return {}; }
    void request(const QByteArray &method, const QString &, const QJsonObject &body, Done done, bool) override {
        if (method == "GET") { done(200, QJsonObject{{QStringLiteral("text"), m_text}}); return; }
        ++clips;
        const double length = body.value(QStringLiteral("text")).toString().size() / CHARS_PER_SECOND;
        const QString url = QStringLiteral("/media/%1.wav").arg(clips);
        seconds.insert(url, length);
        pending.append({m_now + qint64((LATENCY + PER_SECOND * length) * 1000), [done, url, length] {
            done(200, QJsonObject{{QStringLiteral("url"), url}, {QStringLiteral("duration_ms"), length * 1000}}); }});
    }
    QList<Pending> pending;
    QHash<QString, double> seconds;
    int clips = 0;
private:
    const qint64 &m_now;
    QString m_text;
};

class PlayerNativeTests : public QObject {
    Q_OBJECT
private slots:
    void onlineVoiceWaitsBeforeSendingText() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        speech.configure({QVariantMap{{QStringLiteral("id"), QStringLiteral("edge")}, {QStringLiteral("provider"), QStringLiteral("edge")}, {QStringLiteral("online"), true}}}, {});
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn chữ.")}});
        QSignalSpy consent(&speech, &SpeechOut::consentRequested);
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("edge")); speech.play();
        QCOMPARE(consent.size(), 1); QVERIFY(net.callsTo(QStringLiteral("/clip")).isEmpty());
        speech.authorize(QStringLiteral("wrong")); QVERIFY(net.callsTo(QStringLiteral("/clip")).isEmpty());
        speech.authorize(QStringLiteral("edge")); QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 1);
        speech.loadText(QStringLiteral("b"), 2, 0, QStringLiteral("edge")); QCOMPARE(consent.size(), 1);
    }
    void sourceParagraphsRetainBoundariesAndSceneRanks() {
        const auto parts = TextScript::paragraphs(QStringLiteral("Dòng bị bẻ\nở giữa câu.\n\n***\n\nMột đoạn trọn.\nĐoạn trọn nữa! [note123]"));
        QCOMPARE(parts.size(), 4);
        QCOMPARE(parts[0], QStringLiteral("Dòng bị bẻ ở giữa câu."));
        QCOMPARE(parts[3], QStringLiteral("Đoạn trọn nữa!"));
        QVERIFY(TextScript::scene(parts[1], true));
        QVERIFY(!TextScript::scene(QStringLiteral("..."), true));
        QVERIFY(TextScript::scene(QStringLiteral("◆"), false));
    }
    void deviceSelectionAndRollback() {
        bool selecting = false; QString wanted;
        OutputDevices devices([&](bool select, const QString &id) { selecting = select; wanted = id; });
        const QVariantList list{QVariantMap{{QStringLiteral("id"), QStringLiteral("speaker")}, {QStringLiteral("name"), QStringLiteral("Loa ngoài")}}};
        devices.refresh(); QVERIFY(devices.busy()); QVERIFY(!selecting);
        devices.complete(list, {}, true); QCOMPARE(devices.devices(), list);
        devices.select(QStringLiteral("speaker")); QVERIFY(selecting); QCOMPARE(wanted, QStringLiteral("speaker"));
        QCOMPARE(devices.selected(), QString());
        devices.complete(list, wanted, true); QCOMPARE(devices.selected(), wanted); QVERIFY(devices.error().isEmpty());
        devices.select(QStringLiteral("gone"));
        devices.complete(list, QStringLiteral("speaker"), false);
        QCOMPARE(devices.selected(), QStringLiteral("speaker")); QVERIFY(!devices.error().isEmpty()); QVERIFY(!devices.busy());
    }
    void paragraphAudioAndContinuation() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Buổi sáng ấy.\n\nChúng tôi đi học.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("url"), QStringLiteral("/media/clip.wav")}, {QStringLiteral("duration_ms"), 2500}});
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); speech.play();
        QVERIFY(speech.playing()); QCOMPARE(audio.url.path(), QStringLiteral("/media/clip.wav"));
        QCOMPARE(net.calls.last().body.value(QStringLiteral("voice")).toString(), QStringLiteral("local"));
        speech.setRate(1.5); QCOMPARE(audio.rate, 1.5);
        speech.pause(); QVERIFY(!speech.playing());
        speech.play(); audio.finish(); QVERIFY(speech.playing());
        QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2); // the second paragraph is inside the read-ahead window
        QSignalSpy ended(&speech, &AudioOut::ended); audio.finish(); QCOMPARE(ended.size(), 1);
    }
    // The next paragraph is the chapter playing on, not a seek: Music re-aligned the bed to the narration position at every
    // paragraph (the 50-100 ms music dips of the listen audit). Only an open and a seek report seeked().
    void nextParagraphIsNotASeek() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Buổi sáng ấy.\n\nChúng tôi đi học.\n\nTrời mưa.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("url"), QStringLiteral("/media/clip.wav")}, {QStringLiteral("duration_ms"), 2500}});
        QSignalSpy seeked(&speech, &AudioOut::seeked);
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); speech.play();
        QVERIFY(speech.playing());
        const qsizetype opened = seeked.size();
        QVERIFY(opened >= 1);
        audio.finish(); QVERIFY(audio.isPlaying); QCOMPARE(speech.position(), 2.5);
        QCOMPARE(seeked.size(), opened);
        speech.seek(6); QVERIFY(audio.isPlaying); QCOMPARE(seeked.size(), opened + 1);
        audio.finish(); QCOMPARE(seeked.size(), opened + 1);
    }
    void discardedChapterCannotStartAudio() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.hold = true;
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); speech.play(); speech.stop();
        net.releaseHeld(); QCOMPARE(audio.loads, 0); QVERIFY(!speech.playing());
    }
    void pausedTextDoesNotRequestClipsAndPendingAudioStaysPaused() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn văn.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("url"), QStringLiteral("/media/clip.wav")}, {QStringLiteral("duration_ms"), 2500}});
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local"));
        QVERIFY(net.callsTo(QStringLiteral("/clip")).isEmpty());
        net.hold = true; speech.play(); speech.pause();
        net.hold = false; net.releaseHeld();
        QVERIFY(!audio.isPlaying); QVERIFY(!speech.playing());
        speech.play(); QVERIFY(audio.isPlaying);
    }
    void pendingLookaheadIsReusedWhenPlaybackReachesIt() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn văn.\n\nĐoạn tiếp theo.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("url"), QStringLiteral("/media/clip.wav")}, {QStringLiteral("duration_ms"), 2500}});
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local"));
        net.hold = true; speech.play(); // the read-ahead is asked for at open, not when the first clip starts
        QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2);
        QCOMPARE(net.callsTo(QStringLiteral("/clip"))[0].body.value(QStringLiteral("rank")).toInt(), 0);
        QCOMPARE(net.callsTo(QStringLiteral("/clip"))[1].body.value(QStringLiteral("rank")).toInt(), 1);
        net.releaseFirst(); QVERIFY(audio.isPlaying);
        audio.finish(); QVERIFY(!audio.isPlaying);
        net.hold = false; net.releaseHeld();
        QVERIFY(audio.isPlaying); QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2);
        QCOMPARE(speech.position(), 2.5);
    }
    // Seconds of voice ready ahead of the listener (the music bed warms the next chapter only when there are enough): the rest of the paragraph
    // playing plus the ready paragraphs right after it; nothing while the current one is loading; infinite once the rest of the chapter is ready.
    void voiceAheadCountsReadyParagraphs() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn văn.\n\nĐoạn tiếp theo.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("url"), QStringLiteral("/media/clip.wav")}, {QStringLiteral("duration_ms"), 2500}});
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local"));
        net.hold = true; speech.play();
        QCOMPARE(speech.voiceAhead(), 0.0);
        net.releaseFirst();
        QCOMPARE(speech.voiceAhead(), 2.5);
        audio.pos = 1;
        QCOMPARE(speech.voiceAhead(), 1.5);
        net.hold = false; net.releaseHeld();
        QVERIFY(std::isinf(speech.voiceAhead()));
        FakeOut chapter; SpeechOut file(&chapter, &net);
        file.load(QUrl(QStringLiteral("/media/books/b/chapters/2")), 0);
        QVERIFY(std::isinf(file.voiceAhead())); // chapter audio: no voice to give way to
    }
    // Read-ahead in SECONDS, not paragraphs: a few short dialogue lines, then a long narration paragraph, which must be asked for early enough
    // (the old single lookahead stood ~8.5 s before every long paragraph here; 2.4 s in listen audit §20). Each paragraph is asked for once.
    void slowVoiceAsksForLongParagraphsEarlyEnough() {
        QStringList parts{QStringLiteral("Một câu mở đầu chương, đọc chừng mười giây. ").repeated(3)};
        for (int block = 0; block < 4; ++block) {
            for (int line = 0; line < 6; ++line) parts << QStringLiteral("Dòng thoại ngắn số %1.").arg(block * 10 + line);
            parts << QStringLiteral("Một câu kể dài về buổi chiều ở làng. ").repeated(8);
        }
        qint64 now = 0;
        SlowNet net(now, parts.join(QStringLiteral("\n\n")));
        FakeOut audio; SpeechOut speech(&audio, &net, nullptr, [&now] { return now; });
        QSignalSpy ended(&speech, &AudioOut::ended);
        qint64 started = -1, waitFrom = -1, worst = 0; double length = 0; int plays = 0;
        connect(&audio, &AudioOut::playingChanged, this, [&](bool on) {
            if (!on) return;
            started = now; length = net.seconds.value(audio.url.path()); audio.dur = length; ++plays;
            if (waitFrom >= 0) worst = std::max(worst, now - waitFrom);
            waitFrom = -1;
        });
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("edge")); speech.play();
        for (int step = 0; step < 1000 && ended.isEmpty(); ++step) {
            const auto first = std::min_element(net.pending.begin(), net.pending.end(), [](const auto &a, const auto &b) { return a.at < b.at; });
            const qint64 arrive = first == net.pending.end() ? std::numeric_limits<qint64>::max() : first->at;
            const qint64 finish = audio.isPlaying ? started + qint64(length * 1000) : std::numeric_limits<qint64>::max();
            QVERIFY(arrive != finish || arrive != std::numeric_limits<qint64>::max());
            if (arrive <= finish) { now = arrive; const auto reply = first->reply; net.pending.erase(first); reply(); }
            else { now = finish; audio.finish(); if (!audio.isPlaying && ended.isEmpty()) waitFrom = now; }
        }
        QCOMPARE(ended.size(), 1);
        QCOMPARE(plays, int(parts.size()));
        QCOMPARE(net.clips, int(parts.size()));
        QVERIFY2(worst <= 300, qPrintable(QStringLiteral("narration stood %1 ms waiting for a clip").arg(worst)));
    }
    void absentVoiceAndServerFailure() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net); QSignalSpy failed(&speech, &AudioOut::failed);
        speech.loadText(QStringLiteral("b"), 1, 0, {}); QCOMPARE(failed.size(), 1);
        QCOMPARE(failed[0][0].toString(), QStringLiteral("Máy này chưa có giọng đọc."));
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); QCOMPARE(failed.size(), 2);
    }
    void clipProblemsOfferTheSameVoiceRecovery_data() {
        QTest::addColumn<QString>("reason"); QTest::addColumn<int>("status"); QTest::addColumn<QString>("message");
        QTest::newRow("offline") << QStringLiteral("offline") << 503 << QStringLiteral("Không có mạng - giọng đang chọn cần mạng.");
        QTest::newRow("quota") << QStringLiteral("quota") << 502 << QStringLiteral("Giọng đang chọn đang không dùng được.");
        // A handshake past its deadline is the voice, not the network (host 8fef2b33: Edge / Azure / own key say "timeout").
        QTest::newRow("host timeout") << QStringLiteral("timeout") << 504 << QStringLiteral("Giọng đang chọn đang không dùng được.");
        // HostCall gave up on a silent host (HostWait): no HTTP status, same sentence.
        QTest::newRow("silent host") << QStringLiteral("timeout") << 0 << QStringLiteral("Giọng đang chọn đang không dùng được.");
        QTest::newRow("empty") << QStringLiteral("empty") << 422 << QStringLiteral("Đoạn này không đọc được.");
    }
    void clipProblemsOfferTheSameVoiceRecovery() {
        QFETCH(QString, reason); QFETCH(int, status); QFETCH(QString, message);
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net); QSignalSpy failed(&speech, &AudioOut::failed);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn văn.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("error"), QStringLiteral("Đoạn này không đọc được.")}, {QStringLiteral("reason"), reason}});
        net.statuses.insert(QStringLiteral("POST /api/readaloud/clip"), status);
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); speech.play();
        QCOMPARE(failed.size(), 1); QCOMPARE(failed[0][0].toString(), message); QVERIFY(!speech.playing());
    }
};
QTEST_GUILESS_MAIN(PlayerNativeTests)
#include "test_playernative.moc"
