// Đo trễ vào bản lặp của nhạc nền máy tính (Corpus research/music PLAN_loop.md §48): MusicBed THẬT + MusicMixer THẬT trên
// FileSinkDevice (nhịp đồng hồ thật), ghi WAV stereo "người nghe nghe gì". Không phải test, không vào bản phát hành.
//   LoopQt.exe script.json
// script: {"out": "x.wav", "log": "x.json", "cache": "dir", "period_ms": 10, "seconds": 14, "mode": "hidden" | "visible",
//          "voice": "silence.mp3", "start": <giây chương lúc bắt đầu>, "levelDb": -20,
//          "a": "track_left.mp3", "b": "track_right.mp3",
//          "cue": {"start": 0, "end": 1000, "link": "...", "key": "...", "src": "...", "audibleStart": .., "audibleEnd": .., "loopStart": .., "loopEnd": ..}}
// Phần tử nhạc ĐẦU của mốc phát file `a`, mọi phần tử sau phát `b`: hai file là cùng một bài ở hai kênh khác nhau, nên kênh trái của
// bản ghi là bài cũ, kênh phải là bản lặp, chung một đồng hồ khung.
// Giờ chương = position() của một giọng phát im lặng; MusicBed được đồng bộ như Music::sync / Music::updateTicking (hẹn lần kế bằng
// nextSyncSeconds, QTimer chính xác), "visible" thêm nhịp 250 ms thô của PlayerClock khi cửa sổ đang hiện.
#include "filesinkdevice.h"
#include "musicbed.h"
#include "musicmixer.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QTimer>
#include <QUrl>

#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdio>
#include <memory>

int main(int argc, char *argv[]) {
    QCoreApplication app(argc, argv);
    if (argc < 2) { std::fprintf(stderr, "usage: LoopQt script.json\n"); return 2; }
    QFile scriptFile(QString::fromLocal8Bit(argv[1]));
    if (!scriptFile.open(QIODevice::ReadOnly)) { std::fprintf(stderr, "cannot read script\n"); return 2; }
    const QJsonObject script = QJsonDocument::fromJson(scriptFile.readAll()).object();
    const auto text = [&](const char *name) { return script.value(QLatin1String(name)).toString(); };

    auto sinkOwned = std::make_unique<FileSinkDevice>(text("out"), 48000, 48000, script.value(QStringLiteral("period_ms")).toInt(10));
    FileSinkDevice *sink = sinkOwned.get(); // mixer sở hữu; chỉ đọc now() trước khi mixer bị huỷ
    auto mixer = std::make_unique<MusicMixer>(std::move(sinkOwned), text("cache"), true);

    QElapsedTimer clock; clock.start();
    QJsonArray events, samples;
    const auto stamp = [&](QJsonObject o) {
        o.insert(QStringLiteral("wall"), clock.nsecsElapsed() / 1e9);
        o.insert(QStringLiteral("frame"), qint64(sink->now()));
        o.insert(QStringLiteral("dec"), qint64(mixer->decodeCount()));
        return o;
    };

    MixVoice voice(mixer.get());
    QList<QPointer<MixVoice>> made;
    int urls = 0;
    const QUrl a = QUrl::fromLocalFile(text("a")), b = QUrl::fromLocalFile(text("b"));
    const auto positions = [&] {
        QJsonArray out;
        for (const QPointer<MixVoice> &element : made) out.append(element ? element->position() : -1);
        return out;
    };
    MusicBed bed(
        [&]() -> AudioOut * {
            auto *element = new MixVoice(mixer.get(), MixVoice::Bed);
            const int k = int(made.size());
            made.append(element);
            QObject::connect(element, &AudioOut::playingChanged, element, [&, k](bool playing) {
                events.append(stamp({{QStringLiteral("k"), k}, {QStringLiteral("event"), playing ? QStringLiteral("playing") : QStringLiteral("stopped")},
                                     {QStringLiteral("positions"), positions()}, {QStringLiteral("chapter"), voice.position()}}));
            });
            QObject::connect(element, &AudioOut::seeked, element, [&, k] {
                events.append(stamp({{QStringLiteral("k"), k}, {QStringLiteral("event"), QStringLiteral("seeked")}, {QStringLiteral("positions"), positions()}}));
            });
            QObject::connect(element, &AudioOut::failed, element, [&, k](const QString &error) {
                events.append(stamp({{QStringLiteral("k"), k}, {QStringLiteral("event"), QStringLiteral("failed")}, {QStringLiteral("error"), error}}));
            });
            events.append(stamp({{QStringLiteral("k"), k}, {QStringLiteral("event"), QStringLiteral("created")}, {QStringLiteral("positions"), positions()}}));
            return element;
        },
        [&](const QString &) { return urls++ == 0 ? a : b; });

    const QJsonObject c = script.value(QStringLiteral("cue")).toObject();
    MusicLogic::MusicCue cue;
    cue.start = c.value(QStringLiteral("start")).toDouble();
    cue.end = c.value(QStringLiteral("end")).toDouble();
    cue.link = c.value(QStringLiteral("link")).toString();
    cue.key = c.value(QStringLiteral("key")).toString();
    cue.src = c.value(QStringLiteral("src")).toString();
    cue.audibleStart = MusicLogic::optionalNumber(c, "audibleStart");
    cue.audibleEnd = MusicLogic::optionalNumber(c, "audibleEnd");
    cue.loopStart = MusicLogic::optionalNumber(c, "loopStart");
    cue.loopEnd = MusicLogic::optionalNumber(c, "loopEnd");

    // Music::sync + Music::updateTicking (bỏ phần tải sẵn chương sau và hệ số tốc độ: giọng ở 1x, chương dài)
    QTimer tick;
    tick.setSingleShot(true);
    tick.setTimerType(Qt::PreciseTimer);
    int syncs = 0;
    const auto sync = [&] {
        ++syncs;
        const double now = voice.position();
        bed.sync(now, voice.playing(), false);
        tick.stop();
        if (!voice.playing()) return;
        const double delay = bed.nextSyncSeconds(now, 1);
        events.append(stamp({{QStringLiteral("k"), -1}, {QStringLiteral("event"), QStringLiteral("sync")}, {QStringLiteral("chapter"), now},
                             {QStringLiteral("positions"), positions()}, {QStringLiteral("delay"), std::isfinite(delay) ? delay : -1}}));
        if (std::isfinite(delay)) tick.start(int(std::clamp(std::ceil(delay * 1000), 1.0, double(INT_MAX))));
    };
    QObject::connect(&tick, &QTimer::timeout, &app, sync);
    QObject::connect(&bed, &MusicBed::loadResult, &app, sync);
    QObject::connect(&voice, &AudioOut::playingChanged, &app, sync);
    QTimer uiClock; // PlayerClock: 250 ms thô khi có người xem
    uiClock.setInterval(250);
    uiClock.setTimerType(Qt::CoarseTimer);
    QObject::connect(&uiClock, &QTimer::timeout, &app, sync);
    const bool visible = text("mode") == QStringLiteral("visible");

    QTimer sampler;
    QObject::connect(&sampler, &QTimer::timeout, &app, [&] {
        samples.append(stamp({{QStringLiteral("chapter"), voice.position()}, {QStringLiteral("positions"), positions()}}));
    });
    quint64 startFrame = 0;
    int decodesAtBegin = -1;
    const auto begin = [&] {
        startFrame = sink->now();
        decodesAtBegin = int(mixer->decodeCount());
        voice.setVolume(1);
        voice.load(QUrl::fromLocalFile(text("voice")), script.value(QStringLiteral("start")).toDouble());
        voice.play();
        bed.setVolume(1);
        bed.setCues({cue}, script.value(QStringLiteral("levelDb")).toDouble(-20), script.value(QStringLiteral("start")).toDouble());
        sync();
        if (visible) uiClock.start();
        sampler.start(50);
        QTimer::singleShot(int(script.value(QStringLiteral("seconds")).toDouble(14) * 1000), &app, [&] {
            sampler.stop();
            uiClock.stop();
            tick.stop();
            bed.stop();
            voice.pause();
            QTimer::singleShot(300, &app, &QCoreApplication::quit);
        });
    };
    // App thật: tới lúc lặp (vài phút sau khi bài vào) mọi file đã giải mã xong vào bộ đệm, và phần tử lặp mở lại CHÍNH url của phần tử đầu.
    // Ở đây B là file khác: giải mã giọng, A và B vào bộ đệm TRƯỚC (bộ phát câm, không phát), rồi mới chạy giọng + nhạc, để lúc chuyển vòng
    // luồng đọc của bộ trộn không bận giải mã.
    const QList<QUrl> warmUrls{QUrl::fromLocalFile(text("voice")), a, b};
    std::vector<std::unique_ptr<MixVoice>> warm;
    QTimer warmPoll;
    QElapsedTimer waited;
    const auto cached = [&] {
        return std::all_of(warmUrls.begin(), warmUrls.end(), [&](const QUrl &url) { return QFile::exists(mixer->cachePath(url)); });
    };
    if (script.value(QStringLiteral("warm")).toBool()) {
        for (const QUrl &url : warmUrls) {
            warm.push_back(std::make_unique<MixVoice>(mixer.get()));
            warm.back()->setVolume(0);
            warm.back()->load(url, 0);
            warm.back()->preload();
        }
        waited.start();
        QObject::connect(&warmPoll, &QTimer::timeout, &app, [&] {
            if (!cached() && waited.elapsed() < 120000) return;
            warmPoll.stop();
            warm.clear();
            begin();
        });
        warmPoll.start(50);
    } else {
        begin();
    }
    const int code = app.exec();
    const quint64 total = sink->now();
    bed.disconnect();
    QCoreApplication::sendPostedEvents(nullptr, QEvent::DeferredDelete);
    voice.stop();
    QJsonObject log{{QStringLiteral("rate"), 48000}, {QStringLiteral("frames_seen"), qint64(total)}, {QStringLiteral("syncs"), syncs},
                    {QStringLiteral("start_frame"), qint64(startFrame)}, {QStringLiteral("warm_cached"), cached()},
                    {QStringLiteral("decodes_at_begin"), decodesAtBegin}, {QStringLiteral("decodes_end"), int(mixer->decodeCount())},
                    {QStringLiteral("elements"), int(made.size())}, {QStringLiteral("events"), events}, {QStringLiteral("samples"), samples}};
    QFile out(text("log"));
    if (out.open(QIODevice::WriteOnly)) out.write(QJsonDocument(log).toJson(QJsonDocument::Indented));
    return code;
}
