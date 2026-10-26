// Nhạc nền: phép tính thuần (cùng fixture với máy chủ, web và Android) + MusicBed với AudioOut giả, đồng hồ giả.
#include "fakes.h"
#include "music.h"
#include "musicbed.h"
#include "musiclogic.h"
#include "musictext.h"
#include "player.h"

#include <QFile>
#include <QJsonDocument>
#include <QPointer>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QtTest>

#include <memory>

using namespace MusicLogic;

namespace {

QJsonObject readJson(const QString &path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        qFatal("không đọc được %s", qPrintable(path));
    return QJsonDocument::fromJson(file.readAll()).object();
}

QJsonObject fixture(const QString &name) {
    return readJson(QStringLiteral(MUSIC_FIXTURES_DIR "/") + name + QStringLiteral(".json"));
}

bool near(double got, double want, double eps = 1e-6) {
    return std::abs(got - want) < eps;
}

double number(const QJsonValue &value) {
    return value.isNull() || value.isUndefined() ? INF : value.toDouble();
}

double db(double value) {
    return std::pow(10.0, value / 20);
}

/// Bài như máy chủ ghi trong fixture: độ dài + A/E + điểm vòng (thiếu = không có).
MusicCue trackCue(const QJsonObject &track) {
    MusicCue cue;
    cue.audibleStart = optionalNumber(track, "audibleStart");
    cue.audibleEnd = optionalNumber(track, "audibleEnd");
    cue.loopStart = optionalNumber(track, "loopStart");
    cue.loopEnd = optionalNumber(track, "loopEnd");
    return cue;
}

QString describe(const QString &name, int index, const char *what) {
    return QStringLiteral("%1 #%2: %3").arg(name).arg(index).arg(QString::fromUtf8(what));
}

/// MusicBed với AudioOut giả: ghi lại mọi phần tử đã tạo (QPointer: thành null khi bed nhả nó), mọi bài xin tải sẵn.
struct Rig {
    explicit Rig(double duration = 200) {
        bed = std::make_unique<MusicBed>(
            [this, duration] {
                auto *out = new FakeOut;
                out->dur = duration;
                made.append(out);
                return out;
            },
            [this](const QString &src) {
                sources << src;
                return QUrl(QStringLiteral("http://127.0.0.1:1") + src);
            },
            [this](const QString &link) { warmed << link; }, [this] { return clock; });
    }
    /// Cho các sự kiện của bộ phát (luôn tới sau lời gọi, như <audio>) chạy, rồi huỷ phần tử đã nhả.
    void settle() {
        QCoreApplication::processEvents();
        QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
    }
    int playing() const {
        int count = 0;
        for (const QPointer<FakeOut> &out : made)
            count += out && out->isPlaying ? 1 : 0;
        return count;
    }
    int alive() const {
        int count = 0;
        for (const QPointer<FakeOut> &out : made)
            count += out ? 1 : 0;
        return count;
    }

    std::unique_ptr<MusicBed> bed;
    QVector<QPointer<FakeOut>> made;
    QStringList sources;
    QStringList warmed;
    qint64 clock = 1000000;
};

MusicCue plain(double start, double end, const QString &link, std::optional<double> gainDb = std::nullopt) {
    MusicCue cue;
    cue.start = start;
    cue.end = end;
    cue.link = link;
    cue.key = QStringLiteral("1:1");
    cue.src = QStringLiteral("/") + link;
    cue.gainDb = gainDb;
    return cue;
}

/// Lời đáp GET /api/books/<id>/music/chapters/<n> có một mốc 0-90 của bài `link`.
QJsonObject chapterCues(const QString &link, const QString &title) {
    const QJsonObject cue{{QStringLiteral("start"), 0}, {QStringLiteral("end"), 90}, {QStringLiteral("link"), link},
                          {QStringLiteral("key"), QStringLiteral("1:1")}, {QStringLiteral("src"), QStringLiteral("/api/music/") + title}};
    const QJsonObject credit{{QStringLiteral("title"), title},
                             {QStringLiteral("creator"), QStringLiteral("Kevin MacLeod")},
                             {QStringLiteral("attribution"), title + QStringLiteral(" by Kevin MacLeod")},
                             {QStringLiteral("license"), QStringLiteral("by")},
                             {QStringLiteral("licenseUrl"), QStringLiteral("https://creativecommons.org/licenses/by/4.0/")},
                             {QStringLiteral("landing"), QStringLiteral("https://incompetech.com/x")}};
    return {{QStringLiteral("cues"), QJsonArray{cue}}, {QStringLiteral("levelDb"), -18}, {QStringLiteral("credits"), QJsonObject{{link, credit}}}};
}

/// Player + Music thật trên AudioOut / PlayerNet giả: cuốn "a" 4 chương, nhạc người làm sách gắn ở -18 dB.
struct BookRig {
    BookRig() {
        net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 4, true));
        net.answers.insert(QStringLiteral("GET /api/books/a/music"),
                           {{QStringLiteral("hasMusic"), true}, {QStringLiteral("enabled"), true}, {QStringLiteral("levelDb"), -18},
                            {QStringLiteral("defaultLevelDb"), -18}});
        for (int chapter = 1; chapter <= 4; ++chapter)
            net.answers.insert(QStringLiteral("GET /api/books/a/music/chapters/%1").arg(chapter),
                               chapterCues(QStringLiteral("https://x/%1").arg(chapter), QStringLiteral("Bai%1").arg(chapter)));
        player = std::make_unique<Player>(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr, [] { return qint64(1800000000000); });
        music = std::make_unique<Music>(player.get(), &net, [this] {
            auto *voice = new FakeOut;
            voices.append(voice);
            return voice;
        });
    }
    QStringList warmed() const {
        const QString prefix = QStringLiteral("/api/music/warm?link=");
        QStringList links;
        for (const FakeNet::Call &call : net.calls)
            if (call.method == "POST" && call.path.startsWith(prefix))
                links << QUrl::fromPercentEncoding(call.path.mid(int(prefix.size())).toLatin1());
        return links;
    }
    QTemporaryDir dir;
    FakeOut out;
    FakeNet net;
    std::unique_ptr<Player> player;
    std::unique_ptr<Music> music;
    QVector<QPointer<FakeOut>> voices;
};

/// Đủ nhịp để một lần mờ `seconds` giây đi hết.
int ticksFor(double seconds) {
    return int(std::ceil(seconds * 1000 / STEP_MS)) + 2;
}

} // namespace

class MusicTest : public QObject {
    Q_OBJECT
private slots:
    void mixConstantsComeFromSharedJson() {
        const QJsonObject mix = readJson(QStringLiteral(MUSIC_MIX_JSON));
        QCOMPARE(FADE_SECONDS, mix.value(QLatin1String("fadeSeconds")).toDouble());
        QCOMPARE(SIBLING_FADE_SECONDS, mix.value(QLatin1String("siblingFadeSeconds")).toDouble());
        QCOMPARE(STEP_RAMP_SECONDS, mix.value(QLatin1String("stepRampSeconds")).toDouble());
        QCOMPARE(LOOP_CROSSFADE_SECONDS, mix.value(QLatin1String("loopCrossfadeSeconds")).toDouble());
        QCOMPARE(LOOP_MIN_PERIOD_SECONDS, mix.value(QLatin1String("loopMinPeriodSeconds")).toDouble());
    }

    void cuesParseFromServerJson() {
        const QJsonObject json = QJsonDocument::fromJson( // moc không đọc được chuỗi R"(...)"
            "{\"cues\":[{\"start\":0,\"end\":120,\"link\":\"https://x/a\",\"key\":\"1:1\",\"src\":\"/api/music/a\","
            "\"gainDb\":-12,\"steps\":[{\"at\":30,\"db\":-3}],\"sibling\":true,\"audibleStart\":2}],\"levelDb\":-18,"
            "\"credits\":{\"https://x/a\":{\"title\":\"A\",\"creator\":\"B\",\"license\":\"CC BY 4.0\"}},\"pending\":false}").object();
        const MusicCues cues = cuesFromJson(json);
        QCOMPARE(cues.cues.size(), 1);
        QCOMPARE(cues.cues[0].gainDb.value_or(0), -12.0);
        QCOMPARE(cues.cues[0].steps.size(), 1);
        QVERIFY(cues.cues[0].sibling);
        QVERIFY(!cues.cues[0].tail);
        QCOMPARE(cues.cues[0].audibleStart.value_or(0), 2.0);
        QVERIFY(!cues.cues[0].audibleEnd);
        QCOMPARE(cues.levelDb, -18.0);
        QCOMPARE(cues.credits.value(QStringLiteral("https://x/a")).license, QStringLiteral("CC BY 4.0"));
    }

    void stepInEffectIsTheLastOneReached() {
        MusicCue cue = plain(0, 300, QStringLiteral("a"));
        cue.steps = {{60, -4}, {120, 2}};
        QCOMPARE(stepDbAt(cue, 10), 0.0);
        QCOMPARE(stepDbAt(cue, 60), -4.0);
        QCOMPARE(stepDbAt(cue, 200), 2.0);
    }

    // ---- dòng thời gian chung với máy chủ và Android (tests/fixtures/music_timeline) ----
    void sharedTimeline_data() {
        QTest::addColumn<QString>("name");
        for (const char *name : {"loop_crossfade", "sibling_tail", "stop_at", "chapter_end", "short_track", "loop_points"})
            QTest::newRow(name) << QString::fromLatin1(name);
    }
    void sharedTimeline() {
        QFETCH(QString, name);
        const double chapterEndFade = readJson(QStringLiteral(MUSIC_MIX_JSON)).value(QLatin1String("chapterEndFadeSeconds")).toDouble();
        const QJsonObject data = fixture(QStringLiteral("music_timeline/") + name);
        const double chapterSeconds = data.value(QLatin1String("chapterSeconds")).toDouble();
        const QJsonObject tracks = data.value(QLatin1String("tracks")).toObject();
        // Mốc như trình phát nhận (máy chủ đã kẹp cuối chương - music_plan.clamp_to_chapter).
        QVector<MusicCue> cues;
        QVector<QString> cueTrack;
        const double limit = chapterSeconds - chapterEndFade;
        for (const QJsonValue &value : data.value(QLatin1String("cues")).toArray()) {
            const QJsonObject o = value.toObject();
            const QString track = o.value(QLatin1String("track")).toString();
            MusicCue cue = trackCue(tracks.value(track).toObject());
            cue.start = o.value(QLatin1String("start")).toDouble();
            const double end = o.value(QLatin1String("end")).toDouble();
            cue.end = std::min(end, limit);
            cue.tail = end > limit ? false : o.value(QLatin1String("tail")).toBool();
            cue.sibling = o.value(QLatin1String("sibling")).toBool();
            cue.gainDb = optionalNumber(o, "gainDb");
            cue.link = cue.key = track;
            cue.src = QStringLiteral("/") + track;
            if (cue.end > cue.start) {
                cues.append(cue);
                cueTrack.append(track);
            }
        }
        const QJsonArray timeline = data.value(QLatin1String("timeline")).toArray();
        auto at = [](const QJsonObject &other, double seconds) {
            return other.value(QLatin1String("position")).toDouble() + seconds - other.value(QLatin1String("from")).toDouble();
        };
        auto seconds = [&](const QString &track) { return tracks.value(track).toObject().value(QLatin1String("seconds")).toDouble(); };
        for (int index = 0; index < timeline.size(); ++index) {
            const QJsonObject element = timeline[index].toObject();
            const int cueIndex = element.value(QLatin1String("cue")).toInt();
            const MusicCue &cue = cues[cueIndex];
            const QString track = element.value(QLatin1String("track")).toString();
            const QString enter = element.value(QLatin1String("enter")).toString();
            const double from = element.value(QLatin1String("from")).toDouble();
            const double to = element.value(QLatin1String("to")).toDouble();
            const double position = element.value(QLatin1String("position")).toDouble();
            const LoopBounds bounds = loopBounds(cue, seconds(track));
            QVERIFY2(element.value(QLatin1String("loop")).toBool() == !bounds.crossfade, qPrintable(describe(name, index, "lặp thường hay mờ chéo")));
            if (enter != QLatin1String("early"))
                QVERIFY2(near(alignedPosition(cue, from, bounds), position), qPrintable(describe(name, index, "vị trí căn")));
            const QJsonObject before = index > 0 ? timeline[index - 1].toObject() : QJsonObject();
            if (enter == QLatin1String("loop")) {
                const double pos = at(before, from);
                QVERIFY2(loopDue(bounds, pos), qPrintable(describe(name, index, "mở phần tử lặp ở loopEnd - X")));
                QVERIFY(!loopDue(bounds, pos - 0.05));
                QVERIFY2(!finalLoop(cue, from, pos, bounds), qPrintable(describe(name, index, "chưa phải vòng cuối")));
                QVERIFY(near(position, bounds.loopStart, 1e-9));
            }
            if (enter == QLatin1String("early")) {
                const int beforeCue = before.value(QLatin1String("cue")).toInt();
                const LoopBounds previous = loopBounds(cues[beforeCue], seconds(before.value(QLatin1String("track")).toString()));
                QVERIFY2(finished(previous, at(before, from), false), qPrintable(describe(name, index, "vào sớm khi bài trước tới E")));
                QVERIFY(!finished(previous, at(before, from) - 0.05, false));
                QCOMPARE(cues[beforeCue].end, cue.start);
                QVERIFY(from < cue.start);
                QVERIFY(near(position, bounds.start, 1e-9));
            }
            bool looped = false;
            for (int later = index + 1; later < timeline.size(); ++later) {
                const QJsonObject other = timeline[later].toObject();
                looped = looped || (other.value(QLatin1String("cue")).toInt() == cueIndex && other.value(QLatin1String("enter")).toString() == QLatin1String("loop"));
            }
            if (cue.tail && bounds.crossfade) {
                const double pos = bounds.loopEnd - LOOP_CROSSFADE_SECONDS;
                QVERIFY2(finalLoop(cue, from + pos - position, pos, bounds) == !looped, qPrintable(describe(name, index, "vòng cuối = không có phần tử lặp sau")));
            }
            if (cue.tail && !bounds.crossfade) {
                QVERIFY2(finalLoop(cue, to - bounds.period, 0, bounds), qPrintable(describe(name, index, "vòng cuối của lặp thường")));
                QVERIFY(!finalLoop(cue, to - 2 * bounds.period, 0, bounds));
            }
            const MusicCue *following = cueIndex + 1 < cues.size() ? &cues[cueIndex + 1] : nullptr;
            if (following && following->sibling && following->start == cue.end && to > cue.end && !looped)
                QVERIFY2(near(to - cue.end, siblingFadeSeconds(bounds, at(element, cue.end))), qPrintable(describe(name, index, "anh em cũ mờ trong phần còn lại")));
            if (!(following && following->sibling) && to > cue.end + 1e-9 && !looped)
                QVERIFY2(near(to - cue.end, FADE_SECONDS), qPrintable(describe(name, index, "mờ ra cuối mốc")));
            QVERIFY2(to <= chapterSeconds - 0.5, qPrintable(describe(name, index, "nhạc mờ xong trước khi giọng hết")));
        }
    }

    // ---- điểm vòng của bài có đoạn kết (tests/fixtures/music_loop) ----
    void sharedLoopPoints_data() {
        QTest::addColumn<QString>("name");
        for (const char *name : {"with_points", "without_points", "invalid_points"})
            QTest::newRow(name) << QString::fromLatin1(name);
    }
    void sharedLoopPoints() {
        QFETCH(QString, name);
        const QJsonObject data = fixture(QStringLiteral("music_loop/") + name);
        const QJsonObject track = data.value(QLatin1String("track")).toObject();
        const double length = track.value(QLatin1String("seconds")).toDouble();
        const LoopBounds bounds = loopBounds(trackCue(track), length);
        const QJsonObject want = data.value(QLatin1String("bounds")).toObject();
        QCOMPARE(bounds.start, number(want.value(QLatin1String("start"))));
        QCOMPARE(bounds.end, number(want.value(QLatin1String("end"))));
        QVERIFY(near(bounds.period, number(want.value(QLatin1String("period"))), 1e-9));
        QCOMPARE(bounds.crossfade, want.value(QLatin1String("crossfade")).toBool());
        QCOMPARE(bounds.loopStart, number(want.value(QLatin1String("loopStart"))));
        QCOMPARE(bounds.loopEnd, number(want.value(QLatin1String("loopEnd"))));
        QJsonObject plainTrack = track;
        plainTrack.remove(QLatin1String("loopStart"));
        plainTrack.remove(QLatin1String("loopEnd"));
        const LoopBounds plainBounds = loopBounds(trackCue(plainTrack), length);
        for (const QJsonValue &value : data.value(QLatin1String("invalidVariants")).toArray()) {
            QJsonObject variant = plainTrack;
            const QJsonObject change = value.toObject();
            for (auto it = change.begin(); it != change.end(); ++it)
                variant.insert(it.key(), it.value());
            const LoopBounds got = loopBounds(trackCue(variant), length);
            QVERIFY2(got.start == plainBounds.start && got.end == plainBounds.end && got.period == plainBounds.period
                         && got.crossfade == plainBounds.crossfade && got.loopStart == plainBounds.loopStart && got.loopEnd == plainBounds.loopEnd,
                     QJsonDocument(change).toJson(QJsonDocument::Compact).constData());
        }
        auto same = [&](const QVector<double> &got, const QJsonArray &expected, const QString &label) {
            QVERIFY2(got.size() == expected.size(), qPrintable(label));
            for (int i = 0; i < got.size(); ++i)
                QVERIFY2(near(got[i], expected[i].toDouble(), 5e-4), qPrintable(label + QStringLiteral(" #%1").arg(i)));
        };
        const QJsonArray ts = data.value(QLatin1String("ts")).toArray();
        QVector<double> positions;
        for (const QJsonValue &t : ts)
            positions.append(loopPosition(bounds, t.toDouble()));
        same(positions, data.value(QLatin1String("positions")).toArray(), name + QStringLiteral(": vị trí"));
        auto schedules = [&](const QJsonArray &list, const QString &label) {
            for (const QJsonValue &value : list) {
                const QJsonObject cue = value.toObject();
                const double seconds = cue.value(QLatin1String("seconds")).toDouble();
                const QString at = QStringLiteral("%1 %2 %3").arg(name, label).arg(seconds);
                same(loopSchedule(bounds, seconds).opens, cue.value(QLatin1String("opens")).toArray(), at + QStringLiteral(": mở phần tử"));
                const LoopSchedule tail = loopSchedule(bounds, seconds, true);
                const QJsonObject wantTail = cue.value(QLatin1String("tail")).toObject();
                same(tail.opens, wantTail.value(QLatin1String("opens")).toArray(), at + QStringLiteral(" tail: mở phần tử"));
                QVERIFY2(near(tail.end, wantTail.value(QLatin1String("seconds")).toDouble(), 5e-4), qPrintable(at + QStringLiteral(": hết vòng cuối")));
            }
        };
        schedules(data.value(QLatin1String("cues")).toArray(), QString());
        const QJsonObject legacy = data.value(QLatin1String("legacy")).toObject();
        if (!legacy.isEmpty()) {
            // Không có điểm vòng (hay không hợp lệ): trùng từng số với 0.4.89.
            const QJsonArray old = legacy.value(QLatin1String("positions")).toArray();
            QCOMPARE(positions.size(), old.size());
            for (int i = 0; i < positions.size(); ++i)
                QVERIFY(near(positions[i], old[i].toDouble(), 1e-9));
            schedules(legacy.value(QLatin1String("cues")).toArray(), QStringLiteral("như 0.4.89"));
        }
    }

    void loopHandoffByHand() {
        // ca số tính tay: loopStart 12, loopEnd 100, X 2
        LoopBounds b;
        b.start = 0;
        b.end = 110;
        b.period = 86;
        b.crossfade = true;
        b.loopStart = 12;
        b.loopEnd = 100;
        QCOMPARE(loopHandoffDelay(b, 90, 0.25), std::optional<double>());
        QVERIFY(near(*loopHandoffDelay(b, 97.8, 0.25), 0.2));
        QCOMPARE(*loopHandoffDelay(b, 98.3, 0.25), 0.0);
        QVERIFY(near(loopStartAt(b, 98.3), 12.3));
        QVERIFY(near(loopDrift(b, 98.5, 12.4), 0.1));
        b.crossfade = false;
        QCOMPARE(loopHandoffDelay(b, 98.3, 0.25), std::optional<double>());
    }

    // ---- MusicBed ----

    void switchesBySegmentAndFallsSilentBetween() {
        Rig rig;
        rig.bed->setCues({plain(0, 120, QStringLiteral("a")), plain(180, 300, QStringLiteral("b"))}, -20);
        rig.bed->sync(10, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("a"));
        rig.bed->sync(150, true);
        QCOMPARE(rig.bed->activeLink(), QString());
        rig.bed->sync(200, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("b"));
        rig.bed->sync(20, true, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("a"));
        QCOMPARE(rig.sources, QStringList({QStringLiteral("/a"), QStringLiteral("/b"), QStringLiteral("/a")}));
        rig.bed->stop();
        QCOMPARE(rig.bed->activeLink(), QString());
    }

    void announcesActiveSongOncePerChange() {
        Rig rig;
        QSignalSpy spy(rig.bed.get(), &MusicBed::activeChanged);
        MusicCue second = plain(120, 240, QStringLiteral("a"));
        second.key = QStringLiteral("1:9");
        rig.bed->setCues({plain(0, 120, QStringLiteral("a")), second, plain(240, 300, QStringLiteral("b"))}, -20);
        rig.bed->sync(10, true);
        rig.bed->sync(130, true); // cùng bài ở đoạn kề: chơi tiếp, không báo lại
        rig.bed->sync(250, true);
        QCOMPARE(spy.count(), 2);
        QCOMPARE(spy[0][0].toString(), QStringLiteral("a"));
        QCOMPARE(spy[1][0].toString(), QStringLiteral("b"));
        QCOMPARE(rig.made.size(), 2);
    }

    void fadedOutVoicesAreReleased() {
        Rig rig;
        rig.bed->setCues({plain(0, 120, QStringLiteral("a")), plain(180, 300, QStringLiteral("b"))}, -20);
        rig.bed->sync(10, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        rig.bed->sync(200, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        rig.settle();
        QVERIFY2(!rig.made[0], "bài mờ hết thì nhả bộ giải mã, không chỉ tạm dừng");
        QVERIFY(rig.made[1]);
        rig.bed->stop();
        rig.settle();
        QCOMPARE(rig.alive(), 0);
    }

    void pausedVoiceStaysPausedWhenTheBookSwitches() {
        Rig rig;
        rig.bed->setCues({plain(0, 120, QStringLiteral("a"))}, -20);
        rig.bed->sync(10, true);
        rig.settle();
        rig.bed->sync(10, false);
        QCOMPARE(rig.playing(), 0);
        rig.bed->setCues({plain(0, 120, QStringLiteral("z"))}, -20, 0);
        rig.bed->sync(0.5, true);
        QVERIFY2(!rig.made[0]->isPlaying, "bài của cuốn cũ (đang mờ đi) không bị chơi lại khi giọng mới chạy");
        QVERIFY(rig.made[1]->isPlaying);
    }

    void volumeFollowsCueGainAndUserVolume() {
        Rig rig;
        rig.bed->setCues({plain(0, 120, QStringLiteral("a"), -10), plain(120, 240, QStringLiteral("b"))}, -20);
        rig.bed->setVolume(0.5);
        rig.bed->sync(10, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        QVERIFY(near(rig.made[0]->volume, db(-10) * 0.5, 1e-4));
        rig.bed->sync(130, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        QVERIFY2(near(rig.made[1]->volume, db(-20) * 0.5, 1e-4), "mốc không có gainDb dùng mức chung levelDb");
        rig.bed->setVolume(30);
        QVERIFY2(rig.made[1]->volume <= 1, "không bao giờ vượt 1");
    }

    void stepRampsAndSeekJumps() {
        Rig rig;
        MusicCue cue = plain(0, 300, QStringLiteral("a"), -10);
        cue.steps = {{60, -6}};
        rig.bed->setCues({cue}, -20);
        rig.bed->sync(10, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        rig.bed->sync(61, true);
        rig.bed->tick(ticksFor(STEP_RAMP_SECONDS) / 2);
        const double mid = rig.made[0]->volume;
        QVERIFY2(mid < db(-10) && mid > db(-16), "sang bước mới thì trượt dần, không nhảy");
        rig.bed->tick(ticksFor(STEP_RAMP_SECONDS));
        QVERIFY(near(rig.made[0]->volume, db(-16), 1e-4));
        rig.bed->sync(20, true, true);
        QVERIFY2(near(rig.made[0]->volume, db(-10), 1e-4), "tua thì vào thẳng mức của bước tại chỗ tua");
    }

    void brokenSongIsSilentUntilRetry() {
        Rig rig;
        QSignalSpy results(rig.bed.get(), &MusicBed::loadResult);
        rig.bed->setCues({plain(0, 120, QStringLiteral("a")), plain(120, 240, QStringLiteral("b"))}, -20);
        rig.bed->sync(10, true);
        rig.made[0]->fail(QStringLiteral("mạng"));
        rig.settle();
        QVERIFY(!rig.made[0]);
        QCOMPARE(rig.bed->activeLink(), QString());
        QVERIFY(rig.bed->failing());
        QCOMPARE(results.last()[1].toBool(), false);
        rig.bed->sync(130, true); // mốc khác vẫn phát
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("b"));
        rig.clock += RETRY_MS - 1000;
        rig.bed->sync(20, true, true);
        QCOMPARE(rig.bed->activeLink(), QString());
        QCOMPARE(rig.made.size(), 2);
        rig.clock += 2000;
        rig.bed->sync(21, true, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("a"));
        QVERIFY(!rig.bed->failing());
        rig.settle();
        QCOMPARE(results.last()[1].toBool(), true);
    }

    void seekWithinTheSameSongMovesTheMusic() {
        Rig rig(120);
        MusicCue a = plain(0, 600, QStringLiteral("a"), -10);
        a.audibleStart = 2;
        a.audibleEnd = 110;
        rig.bed->setCues({a}, -20, 0);
        rig.bed->sync(0, true);
        rig.bed->sync(250, true, true);
        QCOMPARE(rig.made.size(), 1);
        QVERIFY(near(rig.made[0]->pos, 2 + std::fmod(250.0, 106)));
    }

    void loopCrossfadesFromAWithAPreparedVoice() {
        Rig rig(120);
        MusicCue a = plain(0, 600, QStringLiteral("a"), -10);
        a.audibleStart = 2;
        a.audibleEnd = 110;
        rig.bed->setCues({a}, -20, 0);
        rig.bed->sync(10, true);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS));
        FakeOut *first = rig.made[0];
        QVERIFY2(!first->loop, "không lặp bằng audio.loop (nối thẳng có tách / lỗ im)");
        first->pos = 107.9;
        rig.bed->sync(105.9, true);
        QCOMPARE(rig.made.size(), 2);
        QCOMPARE(rig.playing(), 1); // chưa tới hạn: phần tử lặp chỉ tạo sẵn, câm, chưa phát
        QCOMPARE(rig.made[1]->pos, 2.0);
        QCOMPARE(rig.made[1]->preloads, 1);
        first->pos = 110 - LOOP_CROSSFADE_SECONDS;
        rig.bed->sync(106, true);
        QCOMPARE(rig.made.size(), 2); // dùng chính phần tử đã sẵn
        FakeOut *second = rig.made[1];
        QVERIFY(second->isPlaying);
        QCOMPARE(second->pos, 2.0);
        rig.settle();
        rig.bed->tick(ticksFor(LOOP_CROSSFADE_SECONDS) / 2);
        QVERIFY(first->volume > 0.05);
        QVERIFY(second->volume > 0.05);
        rig.bed->tick(ticksFor(LOOP_CROSSFADE_SECONDS));
        rig.settle();
        QVERIFY(!rig.made[0]);
        QVERIFY(near(second->volume, db(-10), 1e-3));
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("a"));
    }

    void shortSongLoopsTheWholeFile() {
        Rig rig(5);
        MusicCue a = plain(0, 600, QStringLiteral("a"), -10);
        a.audibleStart = 0.2;
        a.audibleEnd = 4.9;
        rig.bed->setCues({a}, -20, 0);
        rig.bed->sync(10, true);
        rig.settle();
        QVERIFY(rig.made[0]->loop);
        rig.made[0]->pos = 4.95;
        rig.bed->sync(14.95, true);
        QCOMPARE(rig.made.size(), 1);
    }

    void preparedVoiceIsReleasedOnSeekAndStop() {
        Rig rig(120);
        MusicCue a = plain(0, 600, QStringLiteral("a"), -10);
        a.audibleStart = 2;
        a.audibleEnd = 110;
        rig.bed->setCues({a}, -20, 0);
        rig.bed->sync(10, true);
        rig.made[0]->pos = 107.9;
        rig.bed->sync(105.9, true);
        QCOMPARE(rig.bed->voices(), 2);
        rig.bed->sync(30, true, true);
        rig.settle();
        QCOMPARE(rig.bed->voices(), 1);
        QCOMPARE(rig.alive(), 1);
        rig.made[0]->pos = 107.9;
        rig.bed->sync(105.9, true);
        rig.bed->stop();
        rig.settle();
        QCOMPARE(rig.alive(), 0);
        QCOMPARE(rig.bed->voices(), 0);
    }

    void tailEndsNaturallyAndTheSiblingComesInEarly() {
        Rig rig(120);
        MusicCue a = plain(0, 214, QStringLiteral("a"), -10);
        a.audibleStart = 2;
        a.audibleEnd = 110;
        a.tail = true;
        MusicCue c = plain(214, 400, QStringLiteral("c"), -10);
        c.sibling = true;
        rig.bed->setCues({a, c}, -20, 0);
        rig.bed->sync(1, true);
        rig.settle();
        rig.made[0]->pos = 108;
        rig.bed->sync(107, true); // vòng trước: mở phần tử lặp
        QCOMPARE(rig.made.size(), 2);
        rig.settle();
        FakeOut *last = rig.made[1];
        last->pos = 108;
        rig.bed->sync(213 - 2 - 1, true); // vòng cuối: không mở gì nữa
        QCOMPARE(rig.made.size(), 2);
        QVERIFY(!last->loop);
        last->pos = 110;
        rig.bed->sync(213 - 2 - 1 + 2, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("c"));
        rig.bed->sync(213 - 2 - 1 + 2.25, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("c")); // không chuyển ngược trước đầu mốc của nó
        rig.bed->sync(100, true, true);
        QCOMPARE(rig.bed->activeLink(), QStringLiteral("a")); // tua thì theo mốc như thường
    }

    void newSongStaysSilentUntilItSounds() {
        Rig rig;
        rig.bed->setCues({plain(0, 120, QStringLiteral("a"), -10)}, -20);
        rig.bed->sync(10, true);
        rig.bed->tick(ticksFor(FADE_SECONDS)); // chưa có sự kiện "đang phát": giữ 0
        QCOMPARE(rig.made[0]->volume, 0.0);
        rig.bed->setVolume(0.8);
        QCOMPARE(rig.made[0]->volume, 0.0);
        rig.settle();
        rig.bed->tick(ticksFor(FADE_SECONDS) / 2);
        QVERIFY(rig.made[0]->volume > 0 && rig.made[0]->volume < db(-10) * 0.8);
        rig.bed->tick(ticksFor(FADE_SECONDS));
        QVERIFY(near(rig.made[0]->volume, db(-10) * 0.8, 1e-4));
    }

    void warmsTheNextCatalogueSongOnce() {
        Rig rig;
        MusicCue a = plain(0, 100, QStringLiteral("https://x/a"));
        MusicCue b = plain(100, 200, QStringLiteral("https://x/b"));
        MusicCue packed = plain(200, 300, QStringLiteral("https://x/p"));
        packed.src = QStringLiteral("/api/books/1/music/files/p.mp3");
        MusicCue local = plain(300, 400, QStringLiteral("file:///c"));
        rig.bed->setCues({a, b, packed, local}, -20);
        rig.bed->sync(10, true);
        rig.bed->sync(11, true);
        QCOMPARE(rig.warmed, QStringList({QStringLiteral("https://x/b")}));
        rig.bed->sync(150, true);
        rig.bed->sync(250, true);
        QCOMPARE(rig.warmed, QStringList({QStringLiteral("https://x/b")})); // bài nằm sẵn trong sách, bài trên máy: không xin
        rig.bed->sync(5, true, true);
        QCOMPARE(rig.warmed.size(), 1); // mỗi bài một lần
    }

    // ---- chữ (trùng từng chữ với bản web) ----

    void levelOptionsAddTheBookLevel() {
        QStringList names;
        for (const MusicText::Level &level : MusicText::levelOptions(-20))
            names << level.name;
        QCOMPARE(names, QStringList({QStringLiteral("To"), QStringLiteral("Hơi to"), QStringLiteral("Vừa (mặc định)"), QStringLiteral("Nhỏ"),
                                     QStringLiteral("Rất nhỏ")}));
        const QVector<MusicText::Level> book = MusicText::levelOptions(-18.5);
        QCOMPARE(book.size(), 6);
        QCOMPARE(book[2].name, QStringLiteral("-18,5 dB (của sách)"));
        QCOMPARE(book[2].value, -18.5);
        QCOMPARE(MusicText::levelNote(-28), QStringLiteral("dễ nghe lời nhất"));
        QCOMPARE(MusicText::levelNote(-24), QString());
    }

    void licenseAndCreditText() {
        QCOMPARE(MusicText::licenseLabel(QStringLiteral("by"), QStringLiteral("https://creativecommons.org/licenses/by-sa/4.0/")), QStringLiteral("CC BY-SA 4.0"));
        QCOMPARE(MusicText::licenseLabel(QStringLiteral("cc0"), QStringLiteral("https://creativecommons.org/publicdomain/zero/1.0/")), QStringLiteral("CC0 1.0"));
        QCOMPARE(MusicText::licenseLabel(QStringLiteral(" by-nc ")), QStringLiteral("CC BY-NC"));
        QCOMPARE(MusicText::licenseLabel(QStringLiteral("cc0")), QStringLiteral("CC0"));
        QCOMPARE(MusicText::licenseLabel(QStringLiteral("Riêng")), QStringLiteral("Riêng"));
        MusicCredit credit{QStringLiteral("Bài"), QStringLiteral("Tác giả"), QStringLiteral("Bài by Tác giả"), {}, QStringLiteral("by"), {}};
        QCOMPARE(MusicText::creditText(credit), QStringLiteral("Bài by Tác giả"));
        credit.creator.clear();
        QCOMPARE(MusicText::creditText(credit), QStringLiteral("Bài"));
        credit.creator = QStringLiteral("Tác giả");
        credit.attribution.clear();
        QCOMPARE(MusicText::creditText(credit), QStringLiteral("Bài - Tác giả"));
        QVERIFY(MusicText::needsModifiedNote(QStringLiteral("by")));
        QVERIFY(!MusicText::needsModifiedNote(QStringLiteral("CC0")));
        QVERIFY(!MusicText::needsModifiedNote(QString()));
    }

    // ---- NextChapterWarm ----

    void nextChapterWarmAsksOnceNearTheEnd() {
        qint64 clock = 1000000;
        QList<int> asked;
        QStringList warmed;
        std::optional<MusicCues> answer = MusicCues{};
        NextChapterWarm warm([&](int chapter, NextChapterWarm::Answer done) {
            asked << chapter;
            done(answer);
        }, [&](const QString &link) { warmed << link; }, [&] { return clock; });
        answer->cues = {plain(0, 50, QStringLiteral("https://x/2"))};
        warm.update(QStringLiteral("a:1"), 2, 300);
        warm.update(QStringLiteral("a:1"), 2, 0);
        warm.update(QStringLiteral("a:1"), std::nullopt, 50);
        QVERIFY(asked.isEmpty());
        warm.update(QStringLiteral("a:1"), 2, NEXT_CHAPTER_WARM_SECONDS);
        warm.update(QStringLiteral("a:1"), 2, 60);
        QCOMPARE(asked, QList<int>({2}));
        QCOMPARE(warmed, QStringList({QStringLiteral("https://x/2")}));
        // chương kế mang bài trong gói: không xin máy chủ tải gì
        answer->cues[0].src = QStringLiteral("/api/books/a/music/files/x.mp3");
        warm.update(QStringLiteral("a:2"), 3, 60);
        QCOMPARE(warmed.size(), 1);
    }

    void nextChapterWarmRetriesPendingAndStopsWithoutMusic() {
        qint64 clock = 1000000;
        QList<int> asked;
        std::optional<MusicCues> answer = std::nullopt;
        NextChapterWarm warm([&](int chapter, NextChapterWarm::Answer done) {
            asked << chapter;
            done(answer);
        }, [](const QString &) {}, [&] { return clock; });
        warm.update(QStringLiteral("a:1"), 2, 60); // hỏi hỏng
        warm.update(QStringLiteral("a:1"), 2, 59);
        QCOMPARE(asked.size(), 1);
        clock += NEXT_CHAPTER_RETRY_MS;
        answer = MusicCues{};
        answer->pending = true;
        warm.update(QStringLiteral("a:1"), 2, 50); // chưa dựng xong: hỏi lại sau
        clock += NEXT_CHAPTER_RETRY_MS;
        answer->pending = false;
        warm.update(QStringLiteral("a:1"), 2, 40); // không nhạc: thôi hẳn
        clock += NEXT_CHAPTER_RETRY_MS;
        warm.update(QStringLiteral("a:1"), 2, 30);
        QCOMPARE(asked.size(), 3);
    }

    // ---- Music: Player + MusicBed + máy chủ ----

    void musicFollowsTheChapterAndShowsTheCredit() {
        BookRig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QVERIFY(rig.player->playing());
        QVERIFY(rig.music->hasMusic());
        QVERIFY(rig.music->enabled());
        QVERIFY(!rig.music->project());
        QCOMPARE(rig.music->levelDb(), -18.0);
        QCOMPARE(rig.music->levels().size(), 6);
        QCOMPARE(rig.music->bed()->activeLink(), QStringLiteral("https://x/1"));
        QCOMPARE(rig.voices.size(), 1);
        QCOMPARE(rig.voices[0]->url, QUrl(QStringLiteral("/api/music/Bai1")));
        const QVariantMap credit = rig.music->credit();
        QCOMPARE(credit.value(QStringLiteral("label")).toString(), QStringLiteral("Bai1 · Kevin MacLeod"));
        QCOMPARE(credit.value(QStringLiteral("text")).toString(), QStringLiteral("Bai1 by Kevin MacLeod"));
        QCOMPARE(credit.value(QStringLiteral("license")).toString(), QStringLiteral("CC BY 4.0"));
        QVERIFY(credit.value(QStringLiteral("modified")).toBool());
        // chương 100 s, còn <= 120 s: bài mốc đầu chương kế được xin tải sẵn
        QCOMPARE(rig.warmed(), QStringList({QStringLiteral("https://x/2")}));
        rig.player->next();
        QCOMPARE(rig.player->chapterId(), 2);
        QCOMPARE(rig.music->bed()->activeLink(), QStringLiteral("https://x/2"));
        QCOMPARE(rig.music->credit().value(QStringLiteral("label")).toString(), QStringLiteral("Bai2 · Kevin MacLeod"));
        rig.player->close();
        QCOMPARE(rig.music->bed()->activeLink(), QString());
        QVERIFY(!rig.music->hasMusic());
    }

    void switchingOffAsksTheCuesAgain() {
        BookRig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QCOMPARE(rig.music->bed()->activeLink(), QStringLiteral("https://x/1"));
        rig.net.answers.insert(QStringLiteral("PUT /api/books/a/music"),
                               {{QStringLiteral("hasMusic"), true}, {QStringLiteral("enabled"), false}, {QStringLiteral("levelDb"), -18}});
        rig.net.answers.insert(QStringLiteral("GET /api/books/a/music/chapters/1"), {{QStringLiteral("cues"), QJsonArray()}, {QStringLiteral("levelDb"), -18}});
        rig.music->setEnabled(false);
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music"), "PUT").last().body.value(QStringLiteral("enabled")), QJsonValue(false));
        QVERIFY(!rig.music->enabled());
        QVERIFY(!rig.music->busy());
        QCOMPARE(rig.music->bed()->activeLink(), QString());
    }

    void reloadAsksTheSameChapterAgainWithoutDroppingTheSong() {
        BookRig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        QCOMPARE(rig.music->bed()->activeLink(), QStringLiteral("https://x/1"));
        const int views = rig.net.callsTo(QStringLiteral("/api/books/a/music"), "GET").size();
        const int cues = rig.net.callsTo(QStringLiteral("/api/books/a/music/chapters/1"), "GET").size();
        rig.music->reload(QStringLiteral("khác"));          // cuốn khác: không đụng cuốn đang nghe
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music/chapters/1"), "GET").size(), cues);
        // "Tự chọn nhạc nền" vừa tắt: máy chủ trả mốc rỗng cho chương này - bài tắt NGAY ở chương đang nghe, không đợi chương sau
        rig.net.answers.insert(QStringLiteral("GET /api/books/a/music/chapters/1"), {{QStringLiteral("cues"), QJsonArray()}, {QStringLiteral("levelDb"), -18}});
        rig.music->reload(QStringLiteral("*"));
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music"), "GET").size(), views + 1);
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music/chapters/1"), "GET").size(), cues + 1);
        QCOMPARE(rig.player->chapterId(), 1);
        QCOMPARE(rig.music->bed()->activeLink(), QString());
        rig.music->reload(QStringLiteral("a"));             // mã đúng cuốn đang nghe cũng nạp lại
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music/chapters/1"), "GET").size(), cues + 2);
        rig.player->close();
        rig.music->reload(QStringLiteral("*"));             // không có sách: không hỏi gì
        QCOMPARE(rig.net.callsTo(QStringLiteral("/api/books/a/music/chapters/1"), "GET").size(), cues + 2);
    }

    void failedChangeSaysSo() {
        BookRig rig;
        rig.player->open(QStringLiteral("a"), -1, -1, true);
        rig.net.answers.insert(QStringLiteral("PUT /api/books/a/music"), {});
        rig.net.statuses.insert(QStringLiteral("PUT /api/books/a/music"), 500);
        rig.music->setLevel(-24);
        QCOMPARE(rig.player->notice(), QStringLiteral("Chưa chỉnh được nhạc nền"));
        QCOMPARE(rig.music->levelDb(), -18.0);
        QVERIFY(!rig.music->busy());
    }

    void projectViewReadsPlanAndOverrides() {
        BookRig rig;
        rig.net.answers.insert(QStringLiteral("GET /api/books/a/music"),
                               {{QStringLiteral("plan"), QJsonObject{{QStringLiteral("levelDb"), -17}, {QStringLiteral("scenes"), QJsonArray{1}}}},
                                {QStringLiteral("overrides"), QJsonObject{{QStringLiteral("levelDb"), -24}}}});
        rig.player->open(QStringLiteral("a"), -1, -1, false);
        QVERIFY(rig.music->project());
        QVERIFY(rig.music->hasMusic());
        QVERIFY(rig.music->enabled());
        QCOMPARE(rig.music->levelDb(), -24.0);
    }
};

QTEST_GUILESS_MAIN(MusicTest)
#include "test_music.moc"
