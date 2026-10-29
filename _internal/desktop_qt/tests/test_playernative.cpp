#include "speechout.h"
#include "outputdevices.h"
#include "fakes.h"
#include "textscript.h"
#include <QtTest>

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
        QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2); // one paragraph lookahead
        QSignalSpy ended(&speech, &AudioOut::ended); audio.finish(); QCOMPARE(ended.size(), 1);
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
        net.hold = true; speech.play(); net.releaseHeld();
        QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2);
        QCOMPARE(net.callsTo(QStringLiteral("/clip"))[0].body.value(QStringLiteral("rank")).toInt(), 0);
        QCOMPARE(net.callsTo(QStringLiteral("/clip"))[1].body.value(QStringLiteral("rank")).toInt(), 1);
        audio.finish(); QVERIFY(!audio.isPlaying);
        net.hold = false; net.releaseHeld();
        QVERIFY(audio.isPlaying); QCOMPARE(net.callsTo(QStringLiteral("/clip")).size(), 2);
        QCOMPARE(speech.position(), 2.5);
    }
    void absentVoiceAndServerFailure() {
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net); QSignalSpy failed(&speech, &AudioOut::failed);
        speech.loadText(QStringLiteral("b"), 1, 0, {}); QCOMPARE(failed.size(), 1);
        QCOMPARE(failed[0][0].toString(), QStringLiteral("Máy này chưa có giọng đọc."));
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); QCOMPARE(failed.size(), 2);
    }
    void clipProblemsOfferTheSameVoiceRecovery_data() {
        QTest::addColumn<QString>("reason"); QTest::addColumn<QString>("message");
        QTest::newRow("offline") << QStringLiteral("offline") << QStringLiteral("Không có mạng - giọng đang chọn cần mạng.");
        QTest::newRow("quota") << QStringLiteral("quota") << QStringLiteral("Giọng đang chọn đang không dùng được.");
        QTest::newRow("empty") << QStringLiteral("empty") << QStringLiteral("Đoạn này không đọc được.");
    }
    void clipProblemsOfferTheSameVoiceRecovery() {
        QFETCH(QString, reason); QFETCH(QString, message);
        FakeOut audio; FakeNet net; SpeechOut speech(&audio, &net); QSignalSpy failed(&speech, &AudioOut::failed);
        net.answers.insert(QStringLiteral("GET /api/listen/books/b/chapters/1/text"), QJsonObject{{QStringLiteral("text"), QStringLiteral("Một đoạn văn.")}});
        net.answers.insert(QStringLiteral("POST /api/readaloud/clip"), QJsonObject{{QStringLiteral("error"), QStringLiteral("Đoạn này không đọc được.")}, {QStringLiteral("reason"), reason}});
        net.statuses.insert(QStringLiteral("POST /api/readaloud/clip"), 503);
        speech.loadText(QStringLiteral("b"), 1, 0, QStringLiteral("local")); speech.play();
        QCOMPARE(failed.size(), 1); QCOMPARE(failed[0][0].toString(), message); QVERIFY(!speech.playing());
    }
};
QTEST_GUILESS_MAIN(PlayerNativeTests)
#include "test_playernative.moc"
