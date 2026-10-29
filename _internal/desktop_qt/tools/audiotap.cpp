// Kiểm tiếng ra thiết bị mà không phát loa: chạy MusicMixer thật trên FileSinkDevice (nhịp đồng hồ thật), điều khiển
// giọng/nhạc theo kịch bản JSON, ghi WAV "người nghe nghe gì" + mốc từng thao tác + vị trí báo cáo mỗi 50 ms.
//   AudioTap.exe script.json
// script: {"out": "x.wav", "log": "x.json", "seconds": 60, "cache": "dir",
//          "voices": {"voice": {"file": "chapter.mp3", "stream": true}, "music": {"file": "track.mp3", "volume": 0.2}},
//          "steps": [{"at": 0.2, "voice": "voice", "op": "load", "value": 0}, {"at": 0.3, "voice": "voice", "op": "play"}, ...]}
// op: load (value = giây bắt đầu), play, pause, stop, seek, rate, volume, loop (value 0/1).
#include "filesinkdevice.h"
#include "musicmixer.h"
#include "streamsource.h"

#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <QUrl>

#include <cstdio>
#include <map>

namespace {
class FileBytes final : public ByteSource {
public:
    explicit FileBytes(QByteArray bytes) : m_bytes(std::move(bytes)) {}
    QByteArray read(qint64 offset, qint64 count) override { return offset >= m_bytes.size() ? QByteArray() : m_bytes.mid(offset, count); }
    qint64 size() const override { return m_bytes.size(); }
    QString error() const override { return {}; }
private:
    QByteArray m_bytes;
};
}

int main(int argc, char *argv[]) {
    QCoreApplication app(argc, argv);
    if (argc < 2) { std::fprintf(stderr, "usage: AudioTap script.json\n"); return 2; }
    QFile scriptFile(QString::fromLocal8Bit(argv[1]));
    if (!scriptFile.open(QIODevice::ReadOnly)) { std::fprintf(stderr, "cannot read script\n"); return 2; }
    const QJsonObject script = QJsonDocument::fromJson(scriptFile.readAll()).object();

    // period_ms: chu kỳ kéo của engine chia sẻ (Windows mặc định 10 ms; 1 = gần như liên tục, bi quan nhất với Stop..Start).
    auto sinkOwned = std::make_unique<FileSinkDevice>(script.value(QStringLiteral("out")).toString(), 48000, 48000,
                                                      script.value(QStringLiteral("period_ms")).toInt(10));
    FileSinkDevice *sink = sinkOwned.get(); // mixer sở hữu; chỉ đọc now() trước khi mixer bị huỷ
    auto mixer = std::make_unique<MusicMixer>(std::move(sinkOwned), script.value(QStringLiteral("cache")).toString(), true);

    std::map<QString, std::unique_ptr<MixVoice>> voices;
    std::map<QString, QUrl> urls;
    const QJsonObject defs = script.value(QStringLiteral("voices")).toObject();
    for (auto it = defs.begin(); it != defs.end(); ++it) {
        const QJsonObject def = it.value().toObject();
        const QString path = def.value(QStringLiteral("file")).toString();
        urls[it.key()] = QUrl::fromLocalFile(path);
        if (def.value(QStringLiteral("stream")).toBool()) {
            QFile f(path);
            if (!f.open(QIODevice::ReadOnly)) { std::fprintf(stderr, "cannot read %s\n", qPrintable(path)); return 2; }
            auto bytes = std::make_shared<FileBytes>(f.readAll());
            voices[it.key()] = std::make_unique<MixVoice>(mixer.get(), [bytes](int rate) { return std::make_unique<StreamMp3>(bytes, rate); });
        } else {
            voices[it.key()] = std::make_unique<MixVoice>(mixer.get());
        }
        // MixVoice khởi tạo ở âm lượng 0 (app tự đặt); kịch bản không ghi thì nghe ở mức đầy.
        voices[it.key()]->setVolume(def.value(QStringLiteral("volume")).toDouble(1.0));
    }

    QJsonArray marks, samples, events;
    QElapsedTimer clock; clock.start();
    const auto stamp = [&](QJsonObject o) { o.insert(QStringLiteral("wall"), clock.nsecsElapsed() / 1e9); o.insert(QStringLiteral("frame"), qint64(sink->now())); return o; };
    for (auto &[name, voice] : voices) {
        const QString key = name;
        QObject::connect(voice.get(), &AudioOut::playingChanged, [&, key](bool p) { events.append(stamp({{QStringLiteral("voice"), key}, {QStringLiteral("event"), p ? QStringLiteral("playing") : QStringLiteral("stopped")}})); });
        QObject::connect(voice.get(), &AudioOut::buffering, [&, key](bool b) { events.append(stamp({{QStringLiteral("voice"), key}, {QStringLiteral("event"), b ? QStringLiteral("buffering") : QStringLiteral("buffered")}})); });
        QObject::connect(voice.get(), &AudioOut::seeked, [&, key] { events.append(stamp({{QStringLiteral("voice"), key}, {QStringLiteral("event"), QStringLiteral("seeked")}})); });
        QObject::connect(voice.get(), &AudioOut::ended, [&, key] { events.append(stamp({{QStringLiteral("voice"), key}, {QStringLiteral("event"), QStringLiteral("ended")}})); });
        QObject::connect(voice.get(), &AudioOut::failed, [&, key](const QString &e) { events.append(stamp({{QStringLiteral("voice"), key}, {QStringLiteral("event"), QStringLiteral("failed")}, {QStringLiteral("error"), e}})); });
    }

    for (const auto &value : script.value(QStringLiteral("steps")).toArray()) {
        const QJsonObject step = value.toObject();
        QTimer::singleShot(int(step.value(QStringLiteral("at")).toDouble() * 1000), &app, [&, step] {
            const QString name = step.value(QStringLiteral("voice")).toString(), op = step.value(QStringLiteral("op")).toString();
            const double v = step.value(QStringLiteral("value")).toDouble();
            auto it = voices.find(name);
            if (it == voices.end()) { std::fprintf(stderr, "unknown voice %s\n", qPrintable(name)); return; }
            MixVoice *voice = it->second.get();
            QJsonObject mark = step;
            mark.insert(QStringLiteral("position_before"), voice->position());
            if (op == QStringLiteral("load")) voice->load(urls[name], v);
            else if (op == QStringLiteral("play")) voice->play();
            else if (op == QStringLiteral("pause")) voice->pause();
            else if (op == QStringLiteral("stop")) voice->stop();
            else if (op == QStringLiteral("seek")) voice->seek(v);
            else if (op == QStringLiteral("rate")) voice->setRate(v);
            else if (op == QStringLiteral("volume")) voice->setVolume(v);
            else if (op == QStringLiteral("loop")) voice->setLoop(v != 0);
            else std::fprintf(stderr, "unknown op %s\n", qPrintable(op));
            marks.append(stamp(mark));
        });
    }

    QTimer sampler;
    QObject::connect(&sampler, &QTimer::timeout, [&] {
        QJsonObject o;
        for (auto &[name, voice] : voices) o.insert(name, voice->position());
        samples.append(stamp(o));
    });
    sampler.start(50);

    QTimer::singleShot(int(script.value(QStringLiteral("seconds")).toDouble(30) * 1000), &app, [&] {
        sampler.stop();
        for (auto &[name, voice] : voices) voice->pause();
        QTimer::singleShot(300, &app, &QCoreApplication::quit);
    });
    const int code = app.exec();
    const quint64 total = sink->now();
    voices.clear();
    mixer.reset(); // sink ghi header WAV khi luồng trộn dừng; không đọc sink sau dòng này

    QJsonObject log{{QStringLiteral("rate"), 48000}, {QStringLiteral("frames_seen"), qint64(total)},
                    {QStringLiteral("marks"), marks}, {QStringLiteral("events"), events}, {QStringLiteral("samples"), samples}};
    QFile out(script.value(QStringLiteral("log")).toString());
    if (out.open(QIODevice::WriteOnly)) out.write(QJsonDocument(log).toJson(QJsonDocument::Indented));
    return code;
}
