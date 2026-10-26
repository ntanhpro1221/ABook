// Bộ thử của bộ phát (Player): điểm nghe tiếp, tự sang chương, hết sách, hẹn giờ (phút và hết chương), tốc độ riêng từng cuốn,
// lưu chỗ nghe khi dừng / đóng, hộp thư đi gửi lại. Đồ giả ở fakes.h; đồng hồ tường là g_now (ms), thử điều khiển nó bằng tay.
#include "fakes.h"
#include "player.h"

#include <QSignalSpy>
#include <QTemporaryDir>
#include <QtTest>

namespace {
qint64 g_now = 1'800'000'000'000; // 2027-01, ms
qint64 fakeNow() { return g_now; }
} // namespace

class PlayerTest : public QObject {
    Q_OBJECT

    struct Rig {
        QTemporaryDir dir;
        FakeOut out;
        FakeNet net;
        std::unique_ptr<Player> player;
        explicit Rig(bool loadBooks = true) {
            net.serverNow = g_now;
            if (loadBooks) {
                net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true));
                net.books.insert(QStringLiteral("b"), makeBook(QStringLiteral("b"), 2, false));
            }
            player = std::make_unique<Player>(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr, fakeNow);
            player->setFreshSpotMs(0);
        }
        /// Chạy `seconds` giây đồng hồ giả, mỗi bước 100 ms: vị trí nguồn tiến theo tốc độ khi đang kêu, Player.tick() chạy.
        void run(double seconds) {
            for (int i = 0; i < int(seconds * 10 + 0.5); ++i) {
                g_now += 100;
                if (out.isPlaying)
                    out.pos = qMin(out.dur, out.pos + 0.1 * out.rate);
                player->tick();
            }
        }
    };

private slots:
    void init() { g_now = 1'800'000'000'000; }

    void resumePointRewindsAfterLongPause() {
        Rig rig;
        // Nghe dở chương 2 ở 40 s, cách đây 2 phút: lùi 5 giây (30 s < 2 phút <= 10 phút).
        rig.net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true, 2, 40, double(g_now) / 1000 - 120));
        rig.player->open(QStringLiteral("a"), -1, -1, false);
        QVERIFY(rig.player->loaded());
        QCOMPARE(rig.player->chapterId(), 2);
        QCOMPARE(rig.out.pos, 35.0);
        QVERIFY(!rig.player->playing());
        QVERIFY(!rig.out.log.contains(QStringLiteral("play")));
        QCOMPARE(rig.player->chapterTitle(), QStringLiteral("Chương 2"));
        QCOMPARE(rig.out.url.toString(), QStringLiteral("http://fake/media/books/a/chapters/2"));
    }

    void resumePointNearEndGoesToNextChapter() {
        Rig rig;
        rig.net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true, 2, 95, double(g_now) / 1000));
        rig.player->open(QStringLiteral("a"), -1, -1, false);
        QCOMPARE(rig.player->chapterId(), 3);
        QCOMPARE(rig.out.pos, 0.0);
    }

    void freshBookStartsAtFirstChapter() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QCOMPARE(rig.player->chapterId(), 1);
        QVERIFY(rig.player->playing());
        QVERIFY(rig.out.isPlaying);
        QCOMPARE(rig.out.pos, 0.0);
    }

    void restoreLastPicksNewestListening() {
        Rig rig;
        rig.net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true, 1, 10, double(g_now) / 1000 - 1000));
        rig.net.books.insert(QStringLiteral("b"), makeBook(QStringLiteral("b"), 2, true, 2, 20, double(g_now) / 1000 - 10));
        QJsonArray library;
        for (const QString &id : {QStringLiteral("a"), QStringLiteral("b")}) {
            QJsonObject item = rig.net.books.value(id);
            item.insert(QStringLiteral("chaptersAvailable"), 2);
            library.append(item);
        }
        rig.player->restoreLast(library);
        QCOMPARE(rig.player->bookId(), QStringLiteral("b"));
        QCOMPARE(rig.player->chapterId(), 2);
        QVERIFY(!rig.player->playing());
    }

    void autoAdvanceThenEndOfBook() {
        Rig rig;
        rig.player->open(QStringLiteral("b"), -1, -1, true); // 2 chương, cuốn chưa đủ
        QCOMPARE(rig.player->chapterId(), 1);
        rig.out.finish();
        QCOMPARE(rig.player->chapterId(), 2);
        QVERIFY(rig.player->playing());
        QCOMPARE(rig.out.pos, 0.0);
        rig.out.finish();
        QVERIFY(!rig.player->playing());
        QCOMPARE(rig.player->atEnd(), QStringLiteral("caughtUp"));
        QVERIFY(rig.player->notice().startsWith(QStringLiteral("Đã nghe hết phần đã có")));
        // Bấm phát khi đã hết: vẫn nói đúng, không phát gì.
        rig.player->toggle();
        QVERIFY(!rig.player->playing());
    }

    void finishedBookOffersRestart() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 4, 0, true);
        rig.out.finish();
        QCOMPARE(rig.player->atEnd(), QStringLiteral("finished"));
        QCOMPARE(rig.player->notice(), QStringLiteral("Đã nghe hết sách"));
        QCOMPARE(rig.player->noticeAction(), QStringLiteral("Nghe lại từ đầu"));
        rig.player->runNoticeAction();
        QCOMPARE(rig.player->chapterId(), 1);
        QVERIFY(rig.player->playing());
        QCOMPARE(rig.player->atEnd(), QStringLiteral("none"));
    }

    void previousRestartsChapterAfterFiveSeconds() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 3, 0, true);
        rig.out.pos = 12;
        rig.player->previous();
        QCOMPARE(rig.player->chapterId(), 3);
        QCOMPARE(rig.out.pos, 0.0);
        rig.player->previous();
        QCOMPARE(rig.player->chapterId(), 2);
        QVERIFY(rig.player->playing());
        rig.player->next();
        QCOMPARE(rig.player->chapterId(), 3);
    }

    void sleepMinutesStopsAndFades() {
        Rig rig;
        rig.player->setFadeSeconds(10);
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.player->setSleep(QStringLiteral("minutes"), 1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("minutes"));
        rig.run(1); // buffering báo "kêu" sau khi mở
        QVERIFY(rig.player->clock()->sleepLeft() > 55);
        rig.run(52); // còn ~7 giây: đang nhỏ dần
        QVERIFY(rig.player->fading());
        QVERIFY(rig.out.volume < 0.9);
        QVERIFY(rig.out.volume > 0);
        rig.run(9);
        QVERIFY(!rig.player->playing());
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        QVERIFY(!rig.player->fading());
        QCOMPARE(rig.out.volume, 0.9);
        QVERIFY(!rig.player->sleepStoppedText().isEmpty());
        // Chỗ nghe đã được lưu khi dừng.
        QVERIFY(!rig.net.callsTo(QStringLiteral("/progress")).isEmpty());
    }

    void sleepWarnsOnceThirtySecondsBefore() {
        Rig rig;
        rig.player->setFadeSeconds(10);
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.player->setSleep(QStringLiteral("minutes"), 1);
        QSignalSpy warned(rig.player.get(), &Player::sleepWarning);
        rig.run(25);
        QCOMPARE(warned.size(), 0);
        rig.run(10); // còn ~25 giây
        QCOMPARE(warned.size(), 1);
        rig.run(5);
        QCOMPARE(warned.size(), 1); // một lần
        rig.player->extendSleep(1); // thêm giờ quá mốc (còn ~80 giây): báo lại được
        rig.run(1);
        QCOMPARE(warned.size(), 1);
        rig.run(55);
        QCOMPARE(warned.size(), 2);
    }

    void muteKeyRemembersVolume() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QSignalSpy changed(rig.player.get(), &Player::volumeChanged);
        QCOMPARE(rig.player->volume(), 0.9);
        rig.player->toggleMute();
        QCOMPARE(rig.player->volume(), 0.0);
        QCOMPARE(rig.out.volume, 0.0);
        rig.player->toggleMute();
        QCOMPARE(rig.player->volume(), 0.9);
        QCOMPARE(rig.out.volume, 0.9);
        rig.player->setVolume(0.4);
        rig.player->toggleMute();
        rig.player->toggleMute();
        QCOMPARE(rig.player->volume(), 0.4);
        QCOMPARE(changed.size(), 5);
        rig.player->setVolume(3); // giữ trong 0..1
        QCOMPARE(rig.player->volume(), 1.0);
    }

    void sleepCountsOnlyWhilePlaying() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.player->setSleep(QStringLiteral("minutes"), 5);
        rig.run(10);
        const double before = rig.player->clock()->sleepLeft();
        rig.player->pause();
        rig.run(60); // dừng: đồng hồ hẹn giờ đứng yên
        QCOMPARE(rig.player->clock()->sleepLeft(), before);
        rig.player->resume();
        rig.run(10);
        QVERIFY(rig.player->clock()->sleepLeft() < before);
    }

    void sleepEndOfChapterPreparesNext() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 2, 0, true);
        rig.player->setSleep(QStringLiteral("chapter"));
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("chapter"));
        rig.out.finish();
        QVERIFY(!rig.player->playing());
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        QCOMPARE(rig.player->chapterId(), 3); // chương kế đã nạp, đứng ở 0:00
        QCOMPARE(rig.out.pos, 0.0);
        const auto saves = rig.net.callsTo(QStringLiteral("/progress"));
        QVERIFY(!saves.isEmpty());
        QCOMPARE(saves.last().body.value(QStringLiteral("chapterId")).toInt(), 3);
        QCOMPARE(saves.last().body.value(QStringLiteral("seconds")).toDouble(), 0.0);
    }

    void extendSleepAddsMinutes() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.player->setSleep(QStringLiteral("minutes"), 5);
        rig.player->extendSleep();
        QCOMPARE(rig.player->clock()->sleepLeft(), 900.0);
        QCOMPARE(rig.player->notice(), QStringLiteral("Nghe thêm 10 phút"));
    }

    // ---- Lịch đêm, lưới an toàn, tuỳ chọn Nghe / Hẹn giờ ngủ nạp từ Cài đặt (configure) ----

    static qint64 at(int hour, int minute) { return QDateTime(QDate(2027, 1, 15), QTime(hour, minute)).toMSecsSinceEpoch(); }
    // safetyStopHours = 0: các thử này nhảy đồng hồ hàng giờ, đừng để lưới an toàn ngủ quên hẹn giờ thay lịch đêm
    static QVariantMap night(const QString &from = QStringLiteral("22:00"), const QString &to = QStringLiteral("06:00"), int minutes = 30) {
        return {{QStringLiteral("safetyStopHours"), 0},
                {QStringLiteral("sleepSchedule"), QVariantMap{{QStringLiteral("from"), from}, {QStringLiteral("to"), to}, {QStringLiteral("minutes"), minutes}}}};
    }

    void nightScheduleArmsWhenListeningStartsInsideWindow() {
        g_now = at(23, 30);
        Rig rig;
        rig.player->configure(night());
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("minutes"));
        QVERIFY(rig.player->clock()->sleepLeft() > 29 * 60);
        QCOMPARE(rig.player->notice(), QStringLiteral("Lịch đêm 22:00-06:00: đã tự hẹn giờ 30 phút"));
        // Qua nửa đêm vẫn cùng một đêm: hẹn giờ tắt tay thì đêm ấy không tự bật lại, dù dừng rồi nghe tiếp.
        rig.player->setSleep(QStringLiteral("off"));
        rig.player->pause();
        g_now = at(0, 10) + 24 * 3'600'000;
        rig.player->resume();
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        // Đêm sau (khoá khác): dừng rồi nghe lại thì hẹn lại.
        rig.player->pause();
        g_now = at(22, 30) + 48 * 3'600'000;
        rig.player->resume();
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("minutes"));
    }

    void nightScheduleIgnoresOutsideWindowAndBadSchedules() {
        g_now = at(15, 0);
        Rig rig;
        rig.player->configure(night());
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        // Đang nghe qua giờ bắt đầu khung thì không tự hẹn giữa chừng (bản web chỉ xét lúc bắt đầu nghe).
        g_now = at(22, 30);
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        // Giờ lạ / số phút lạ = chưa có lịch.
        rig.player->configure(night(QStringLiteral("25:00")));
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        rig.player->configure(night(QStringLiteral("22:00"), QStringLiteral("06:00"), 20));
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        // Lịch hợp lệ mới (đổi lịch = xét lại): khung cùng ngày 22:00-23:00, 15 phút.
        rig.player->configure(night(QStringLiteral("22:00"), QStringLiteral("23:00"), 15));
        rig.run(1);
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("minutes"));
        QVERIFY(rig.player->clock()->sleepLeft() <= 15 * 60);
        QVERIFY(rig.player->clock()->sleepLeft() > 14 * 60);
    }

    void safetyStopArmsOneMinuteAfterIdleHours() {
        Rig rig;
        rig.player->configure({{QStringLiteral("safetyStopHours"), 1}});
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.player->setSleep(QStringLiteral("minutes"), 45);
        rig.player->setSleep(QStringLiteral("off"));
        rig.run(1);
        g_now += 59 * 60'000;
        rig.player->tick();
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
        g_now += 2 * 60'000;
        rig.player->tick();
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("minutes"));
        QCOMPARE(rig.player->notice(), QStringLiteral("Không thấy ai chạm máy suốt 1 giờ - sẽ tắt sau 1 phút"));
        QCOMPARE(rig.player->noticeAction(), QStringLiteral("Vẫn đang nghe"));
        QCOMPARE(rig.player->lastSleepMinutes(), 45); // nút hẹn giờ vẫn nhớ lần hẹn của người nghe
    }

    void safetyStopOffNeverArms() {
        Rig rig;
        rig.player->configure({{QStringLiteral("safetyStopHours"), 0}});
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(1);
        g_now += 5 * 3'600'000;
        rig.player->tick();
        QCOMPARE(rig.player->sleepKind(), QStringLiteral("off"));
    }

    void configuredExtendAndAutoRewind() {
        Rig rig;
        rig.player->configure({{QStringLiteral("sleepExtendMinutes"), 15}, {QStringLiteral("autoRewind"), false}});
        rig.player->open(QStringLiteral("a"), 1, 0, true);
        rig.player->setSleep(QStringLiteral("minutes"), 5);
        rig.player->extendSleep();
        QCOMPARE(rig.player->clock()->sleepLeft(), 1200.0);
        QCOMPARE(rig.player->notice(), QStringLiteral("Nghe thêm 15 phút"));
        rig.run(60);
        rig.player->pause();
        const double stopped = rig.out.pos;
        g_now += 5 * 60'000;
        rig.player->resume();
        QCOMPARE(rig.out.pos, stopped); // tắt Tự lùi: nghỉ 5 phút cũng không lùi
        // Giá trị ngoài các mức giao diện đưa ra bị kẹp vào khoảng hợp lệ.
        rig.player->configure({{QStringLiteral("sleepExtendMinutes"), 99}});
        rig.player->setSleep(QStringLiteral("minutes"), 5);
        rig.player->extendSleep();
        QCOMPARE(rig.player->clock()->sleepLeft(), 1200.0);
    }

    void rateIsPerBook() {
        Rig rig;
        rig.net.books.insert(QStringLiteral("b"), makeBook(QStringLiteral("b"), 2, true, 0, 0, 0, 1.5));
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QCOMPARE(rig.player->rate(), 1.0);
        rig.player->setRate(1.25);
        const auto rates = rig.net.callsTo(QStringLiteral("/rate"));
        QCOMPARE(rates.size(), 1);
        QCOMPARE(rates.first().path, QStringLiteral("/api/listen/books/a/rate"));
        QCOMPARE(rates.first().body.value(QStringLiteral("rate")).toDouble(), 1.25);
        QCOMPARE(rates.first().body.value(QStringLiteral("record")).toString(), QStringLiteral("r1"));
        QCOMPARE(rig.out.rate, 1.25);
        rig.player->open(QStringLiteral("b"), -1, -1, true);
        QCOMPARE(rig.player->rate(), 1.5);
        QCOMPARE(rig.out.rate, 1.5);
        // Về cuốn a: máy chủ đã nhớ 1.25 cho nó.
        rig.net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true, 0, 0, 0, 1.25));
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QCOMPARE(rig.player->rate(), 1.25);
        rig.player->stepRate(1);
        QCOMPARE(rig.player->rate(), 1.3);
    }

    void progressSavedOnPauseAndClose() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(12.3);
        rig.player->pause();
        auto saves = rig.net.callsTo(QStringLiteral("/progress"));
        QCOMPARE(saves.size(), 2); // một lần định kỳ ở giây 10, một lần khi dừng
        QCOMPARE(saves.last().body.value(QStringLiteral("chapterId")).toInt(), 1);
        QVERIFY(qAbs(saves.last().body.value(QStringLiteral("seconds")).toDouble() - 12.3) < 0.2);
        QCOMPARE(saves.last().body.value(QStringLiteral("record")).toString(), QStringLiteral("r1"));
        QCOMPARE(saves.last().body.value(QStringLiteral("revision")).toInt(), 2);
        // Bắt tay phiên trước lần lưu đầu.
        const auto session = rig.net.callsTo(QStringLiteral("/progress/session"));
        QCOMPARE(session.size(), 1);
        QCOMPARE(session.first().body.value(QStringLiteral("sessionId")), saves.last().body.value(QStringLiteral("sessionId")));
        // Đóng sách lưu lần nữa.
        rig.player->resume();
        rig.run(3);
        rig.player->close();
        saves = rig.net.callsTo(QStringLiteral("/progress"));
        QCOMPARE(saves.size(), 3);
        QVERIFY(!rig.player->loaded());
        QCOMPARE(saves.last().body.value(QStringLiteral("revision")).toInt(), 3);
    }

    void progressSavedEveryTenSecondsWhilePlaying() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(9);
        QCOMPARE(rig.net.callsTo(QStringLiteral("/progress")).size(), 0);
        rig.run(2);
        QCOMPARE(rig.net.callsTo(QStringLiteral("/progress")).size(), 1);
        rig.run(10);
        QCOMPARE(rig.net.callsTo(QStringLiteral("/progress")).size(), 2);
    }

    void chapterChangeSavesOldChapterThenMarksDone() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 1, 0, true);
        rig.run(5);
        rig.out.pos = 99; // còn 1 giây: máy chủ sẽ coi là xong
        rig.player->next();
        const auto saves = rig.net.callsTo(QStringLiteral("/progress"));
        QCOMPARE(saves.size(), 1);
        QCOMPARE(saves.first().body.value(QStringLiteral("chapterId")).toInt(), 1);
        QCOMPARE(rig.player->chapterId(), 2);
        // Lời đáp của máy chủ đánh dấu chương 1 đã nghe xong: danh sách chương theo.
        const QModelIndex row = rig.player->chapters()->index(0);
        QVERIFY(rig.player->chapters()->data(row, ChaptersModel::DoneRole).toBool());
        QVERIFY(rig.player->chapters()->data(rig.player->chapters()->index(1), ChaptersModel::CurrentRole).toBool());
    }

    void outboxRetriesAfterFailure() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(2);
        rig.net.offline = true;
        rig.player->pause();
        QCOMPARE(rig.player->outbox()->pending(), 1);
        rig.net.offline = false;
        const int before = rig.net.calls.size();
        rig.run(5); // chưa tới 10 giây: chưa gửi lại
        QCOMPARE(rig.player->outbox()->pending(), 1);
        rig.run(6);
        QCOMPARE(rig.player->outbox()->pending(), 0);
        QVERIFY(rig.net.calls.size() > before);
    }

    void outboxSurvivesRestartAndDropsStale() {
        QTemporaryDir dir;
        const QString path = dir.filePath(QStringLiteral("outbox.json"));
        {
            FakeOut out;
            FakeNet net;
            net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a")));
            net.offline = true;
            Player player(&out, &net, path, nullptr, fakeNow);
            player.open(QStringLiteral("a"), -1, -1, true); // GET cũng hỏng: không nạp được
            QVERIFY(!player.loaded());
            ProgressOutbox box([](const ProgressSpot &, ProgressOutbox::Done done) { done(0); }, nullptr, path);
            ProgressSpot spot;
            spot.bookId = QStringLiteral("a");
            spot.chapterId = 2;
            spot.seconds = 33;
            box.put(spot);
            QCOMPARE(box.pending(), 1);
        }
        // Lần chạy sau: bản chờ còn đó; máy chủ trả 409 (cửa sổ khác đã thay phiên) thì bỏ, không gửi mãi.
        FakeOut out;
        FakeNet net;
        net.progressStatus = 409;
        Player player(&out, &net, path, nullptr, fakeNow);
        QCOMPARE(player.outbox()->pending(), 1);
        player.outbox()->flush();
        QCOMPARE(player.outbox()->pending(), 0);
        QCOMPARE(net.callsTo(QStringLiteral("/progress")).size(), 1);
    }

    void errorThenRetryReloads() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 2, 30, true);
        rig.run(2);
        rig.out.fail(QStringLiteral("0x1"));
        QVERIFY(!rig.player->playing());
        QCOMPARE(rig.player->error(), QStringLiteral("Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại."));
        const int loads = rig.out.loads;
        rig.player->toggle(); // bấm phát khi có lỗi = nạp lại đúng chỗ
        QCOMPARE(rig.out.loads, loads + 1);
        QVERIFY(rig.player->error().isEmpty());
        QVERIFY(rig.player->playing());
    }

    void jumpFarOffersGoBack() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 1, 0, true);
        rig.run(3);
        rig.player->seek(70);
        QVERIFY(rig.player->canGoBack());
        QCOMPARE(rig.player->noticeAction(), QStringLiteral("Quay lại"));
        rig.player->runNoticeAction();
        QVERIFY(qAbs(rig.out.pos - 3.0) < 0.5);
        QVERIFY(!rig.player->canGoBack());
        // Nhảy ngắn không để lại dấu.
        rig.player->seek(10);
        QVERIFY(!rig.player->canGoBack());
    }

    void deviceElsewhereWinsOnResume() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 1, 0, false);
        // Máy kia vừa nghe tới chương 3 ở 50 giây (sau lần nạp của máy này).
        g_now += 5000;
        rig.net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true, 3, 50, double(g_now) / 1000));
        rig.player->resume();
        QCOMPARE(rig.player->chapterId(), 3);
        QCOMPARE(rig.out.pos, 50.0);
        QVERIFY(rig.player->notice().startsWith(QStringLiteral("Nghe tiếp từ chỗ thiết bị khác")));
        QVERIFY(rig.player->playing());
    }

    void rewindAfterPause() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), 1, 0, true);
        rig.run(60);
        rig.player->pause();
        const double at = rig.out.pos;
        g_now += 5 * 60'000; // dừng 5 phút: lùi 5 giây
        rig.player->resume();
        QVERIFY(qAbs(rig.out.pos - (at - 5)) < 0.2);
        rig.player->pause();
        g_now += 10'000; // dừng 10 giây: không lùi
        const double again = rig.out.pos;
        rig.player->resume();
        QCOMPARE(rig.out.pos, again);
    }

    void snapshotStaysStillWhilePlaying() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(1);
        const quint64 before = rig.player->snapshotChanges();
        QSignalSpy chapter(rig.player.get(), &Player::chapterChanged);
        QSignalSpy playing(rig.player.get(), &Player::playingChanged);
        QSignalSpy rate(rig.player.get(), &Player::rateChanged);
        rig.player->clock()->retain();
        rig.run(8);
        QCOMPARE(rig.player->snapshotChanges(), before);
        QCOMPARE(chapter.size(), 0);
        QCOMPARE(playing.size(), 0);
        QCOMPARE(rate.size(), 0);
        // Đồng hồ thì đổi theo nhịp.
        QVERIFY(rig.player->clock()->ticks() > 0);
        rig.player->clock()->release();
    }

    void textOnlyChapterIsNotPlayable() {
        Rig rig;
        QJsonObject book = makeBook(QStringLiteral("t"), 2, true);
        QJsonArray chapters = book.value(QStringLiteral("chapters")).toArray();
        for (int i = 0; i < chapters.size(); ++i) {
            QJsonObject item = chapters.at(i).toObject();
            item.insert(QStringLiteral("available"), false);
            item.insert(QStringLiteral("state"), QStringLiteral("text"));
            chapters.replace(i, item);
        }
        book.insert(QStringLiteral("chapters"), chapters);
        rig.net.books.insert(QStringLiteral("t"), book);
        rig.player->open(QStringLiteral("t"), -1, -1, true);
        QVERIFY(!rig.player->loaded());
        QVERIFY(!rig.player->notice().isEmpty());
    }

    void listeningSessionPostedAfterTwentySeconds() {
        Rig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.run(5);
        rig.player->pause();
        QCOMPARE(rig.net.callsTo(QStringLiteral("/sessions")).size(), 0);
        rig.player->resume();
        rig.run(30);
        rig.player->pause();
        const auto sessions = rig.net.callsTo(QStringLiteral("/sessions"));
        QCOMPARE(sessions.size(), 1);
        QCOMPARE(sessions.first().body.value(QStringLiteral("device")).toString(), QStringLiteral("desktop"));
        QVERIFY(sessions.first().body.value(QStringLiteral("listened")).toDouble() >= 30);
    }
};

QTEST_GUILESS_MAIN(PlayerTest)
#include "test_player.moc"
