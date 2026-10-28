// Offline signal evidence only. No render client or sound device is opened, even with nonzero samples.
// This supplements, and must never be described as, a WASAPI loopback/MFMediaEngine capture.
#include "streamsource.h"
#include "mp3source.h"
#include "mfsource.h"
#include "timestretch.h"
#include "musiclogic.h"
#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QtEndian>
#include <cstdio>

namespace {
constexpr int RATE = 48000;
class Wave {
    QFile file;
    quint32 bytes = 0;
public:
    explicit Wave(const QString &path) : file(path) {
        if (!file.open(QIODevice::WriteOnly)) qFatal("Cannot create capture");
        file.write(QByteArray(44, '\0'));
    }
    void write(const std::vector<float> &pcm) {
        const auto n = qint64(pcm.size() * sizeof(float));
        if (file.write(reinterpret_cast<const char *>(pcm.data()), n) != n) qFatal("Capture write failed");
        bytes += quint32(n);
    }
    ~Wave() {
        QByteArray h(44, '\0'); std::copy_n("RIFF", 4, h.data()); std::copy_n("WAVEfmt ", 8, h.data() + 8);
        qToLittleEndian<quint32>(bytes + 36, h.data() + 4); qToLittleEndian<quint32>(16, h.data() + 16);
        qToLittleEndian<quint16>(3, h.data() + 20); qToLittleEndian<quint16>(2, h.data() + 22);
        qToLittleEndian<quint32>(RATE, h.data() + 24); qToLittleEndian<quint32>(RATE * 8, h.data() + 28);
        qToLittleEndian<quint16>(8, h.data() + 32); qToLittleEndian<quint16>(32, h.data() + 34);
        std::copy_n("data", 4, h.data() + 36); qToLittleEndian<quint32>(bytes, h.data() + 40);
        file.seek(0); file.write(h);
    }
};
QByteArray read(const QString &path) { QFile f(path); if (!f.open(QIODevice::ReadOnly)) qFatal("Missing input"); return f.readAll(); }
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    if (app.arguments().size() != 4 || qEnvironmentVariableIntValue("ABOOK_MUTE") != 1) return 2;
    const auto args = app.arguments();
    Mp3Source music(RATE); if (!music.open(read(args[2]))) return 3;
    std::vector<float> song; while (music.read(song, 8192)) {}
    const double musicSeconds = double(song.size() / 2) / RATE;
    MusicLogic::MusicCue cue; const auto bounds = MusicLogic::loopBounds(cue, musicSeconds);
    QJsonArray rows;
    for (double speed : {1.0, 1.5}) {
        auto bytes = std::make_shared<RangeSource>(QUrl::fromLocalFile(args[1]), [] {});
        StreamMp3 decoder(bytes, RATE); if (!decoder.open()) return 4;
        MixCore::Ring ring(size_t(RATE) * 4); TimeStretch stretch(RATE); stretch.setRate(speed);
        const QString suffix = QString::number(speed, 'f', 1);
        Wave capture(args[3] + QStringLiteral("-mix-") + suffix + QStringLiteral(".wav"));
        Wave dry(args[3] + QStringLiteral("-voice-") + suffix + QStringLiteral(".wav"));
        const auto schedule = MusicLogic::loopSchedule(bounds, decoder.duration() / speed);
        QVector<double> opens{0}; opens += schedule.opens;
        quint64 written = 0, sourceFrames = 0;
        size_t wanted = 997;
        double sum = 0, peak = 0, boundary = 0, last = 0;
        while (!stretch.drained()) {
            while (ring.writable() >= 2 && !decoder.atEnd()) {
                std::vector<float> block;
                const auto n = decoder.read(block, std::min<size_t>(8192, ring.writable() / 2));
                if (!n) break;
                sourceFrames += n; ring.write(block.data(), n * 2);
            }
            std::vector<float> block(wanted * 2);
            const size_t n = stretch.read(ring, block.data(), wanted, decoder.atEnd()); block.resize(n * 2);
            if (!decoder.error().isEmpty()) qFatal("Streaming decode error");
            dry.write(block);
            for (size_t i = 0; i < n; ++i) {
                const double t = double(written + i) / RATE;
                for (int c = 0; c < 2; ++c) {
                    double bed = 0;
                    for (double open : opens) {
                        const double at = t - open;
                        if (at < 0 || at >= musicSeconds) continue;
                        const double gain = std::min({1.0, at / MusicLogic::LOOP_CROSSFADE_SECONDS, (musicSeconds - at) / MusicLogic::LOOP_CROSSFADE_SECONDS});
                        const size_t frame = std::min(song.size() / 2 - 1, size_t(at * RATE));
                        bed += song[frame * 2 + c] * gain * 0.1; // -20 dB, complementary linear crossfade
                    }
                    block[i * 2 + c] += float(bed);
                    sum += double(block[i * 2 + c]) * block[i * 2 + c]; peak = std::max(peak, std::abs(double(block[i * 2 + c])));
                }
            }
            if (n && written) boundary = std::max(boundary, std::abs(double(block[0]) - last));
            if (n) last = block[(n - 1) * 2];
            capture.write(block); written += n; wanted = wanted * 7 % 4096 + 1;
        }
        rows.append(QJsonObject{{QStringLiteral("rate"), speed}, {QStringLiteral("source_s"), decoder.duration()},
            {QStringLiteral("output_s"), double(written) / RATE}, {QStringLiteral("length_error_pct"), (double(written) / RATE / (decoder.duration() / speed) - 1) * 100},
            {QStringLiteral("rms_dbfs"), 10 * std::log10(sum / double(written * 2))}, {QStringLiteral("peak"), peak},
            {QStringLiteral("max_boundary_step"), boundary}, {QStringLiteral("crossfades"), schedule.opens.size()},
            {QStringLiteral("decoded_frames"), qint64(sourceFrames)}});
    }
    MfSource mf(RATE); if (!mf.open(read(args[1]))) return 5;
    { Wave baseline(args[3] + QStringLiteral("-source-reader.wav")); std::vector<float> block;
      while (mf.read(block, 8192)) { baseline.write(block); block.clear(); }
    }
    QFile json(args[3] + QStringLiteral(".json")); if (!json.open(QIODevice::WriteOnly)) return 6;
    json.write(QJsonDocument(rows).toJson());
    return 0;
}
