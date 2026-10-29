// Lõi trộn của đường âm thanh WASAPI (mixcore.h, mp3source.h): vòng đệm, âm lượng trượt, đổi tần số, giải mã mp3 - thử trên số và
// trên fixture mp3 chung, không cần thiết bị âm thanh.
#include "mixcore.h"
#include "mp3source.h"
#include "mfsource.h"
#include "musicmixer.h"
#include "musicbed.h"

#include <QFile>
#include <QTemporaryDir>
#include <QProcess>
#include <QProcessEnvironment>
#include <QtEndian>
#include <QtTest>

#include <cmath>
#include <random>
#include <vector>

#define NOMINMAX
#include <windows.h>
#include <mmreg.h>
#include <ks.h>
#include <ksmedia.h>

using namespace MixCore;

namespace {

class FakeDevice final : public MixDevice {
public:
    int hz = 48000, starts = 0, stops = 0, resets = 0;
    size_t queued = 0;
    quint64 epoch = 0;
    bool running = false;
    WAVEFORMATEXTENSIBLE format{};
    FakeDevice() {
        format.Format.wFormatTag = WAVE_FORMAT_IEEE_FLOAT;
        format.Format.wBitsPerSample = 32;
        format.Format.nChannels = 2;
    }
    bool refresh() override { return WasapiDevice::supportsFormat(format.Format); }
    QString error() const override {
        return WasapiDevice::supportsFormat(format.Format) ? QString() : QStringLiteral("Unsupported music device format");
    }
    std::vector<float> output;
    int rate() const override { return hz; }
    quint64 revision() const override { return epoch; }
    bool start() override { ++starts; running = true; return true; }
    void stop() override { ++stops; running = false; }
    void reset() override { ++resets; queued = 0; }
    size_t padding() override { return queued; }
    size_t bufferFrames() const override { return size_t(hz); }
    bool write(const float *in, size_t frames) override {
        output.insert(output.end(), in, in + frames * 2); queued += frames; return true;
    }
    void consume(size_t frames) { queued -= std::min(queued, frames); }
};

QUrl track() { return QUrl::fromLocalFile(QStringLiteral(MIX_FIXTURES_DIR "/music_student/stereo_44k.mp3")); }

struct MixerRig {
    QTemporaryDir dir;
    FakeDevice *device = new FakeDevice;
    MusicMixer mixer{std::unique_ptr<MixDevice>(device), dir.path()};
    bool ready(MixVoice &voice) {
        for (int i = 0; i < 200 && !voice.duration(); ++i) {
            QCoreApplication::processEvents(); mixer.service(0); mixer.serviceReader();
            if (!voice.duration()) QTest::qWait(1);
        }
        QCoreApplication::processEvents();
        return voice.duration() > 0;
    }
    void serve(size_t frames, bool refill = true) {
        device->consume(device->queued); mixer.service(0);
        if (refill) mixer.serviceReader();
        mixer.service(frames); QCoreApplication::processEvents();
    }
};

const double PI = 3.14159265358979323846;

std::vector<float> sine(double hz, int rate, size_t frames, int channels, double amplitude = 0.5) {
    std::vector<float> out(frames * channels);
    for (size_t i = 0; i < frames; ++i)
        for (int c = 0; c < channels; ++c)
            out[i * channels + c] = float(amplitude * std::sin(2 * PI * hz * double(i) / rate));
    return out;
}

QByteArray fixtureBytes(const QString &name) {
    QFile file(QStringLiteral(MIX_FIXTURES_DIR "/") + name);
    if (!file.open(QIODevice::ReadOnly))
        qFatal("không đọc được %s", qPrintable(name));
    return file.readAll();
}

double rms(const std::vector<float> &x, int channels, int channel, size_t from, size_t to) {
    double sum = 0;
    for (size_t i = from; i < to; ++i)
        sum += double(x[i * channels + channel]) * x[i * channels + channel];
    return std::sqrt(sum / double(to - from));
}

} // namespace

class MixTests : public QObject {
    Q_OBJECT
private slots:
    void musicFormats_data() {
        QTest::addColumn<QString>("name"); QTest::addColumn<int>("rate");
        QTest::addColumn<int>("channels"); QTest::addColumn<int>("outRate");
        const char *files[] = {"stereo_44k.wav", "stereo_44k.flac", "stereo_44k.m4a", "mono_22k.wav", "stereo_44k.ogg", "stereo_48k.opus"};
        for (const auto *file : files) for (int outRate : {44100, 48000, 32000}) {
            const QString name = QString::fromLatin1(file);
            const QByteArray row = name.toUtf8() + '-' + QByteArray::number(outRate);
            QTest::newRow(row.constData()) << name << (name.startsWith(QLatin1String("mono")) ? 22050 : name.endsWith(QLatin1String("opus")) ? 48000 : 44100)
                << (name.startsWith(QLatin1String("mono")) ? 1 : 2) << outRate;
        }
    }

    void musicFormats() {
        QFETCH(QString, name); QFETCH(int, rate); QFETCH(int, channels); QFETCH(int, outRate);
        const QByteArray bytes = fixtureBytes(QStringLiteral("music_student/") + name);
        MfSource source(outRate), chunks(outRate);
        const bool opened = source.open(bytes);
        const bool optional = name.endsWith(QLatin1String("ogg")) || name.endsWith(QLatin1String("opus"));
        if (!opened) {
            QVERIFY2(optional, qPrintable(source.error()));
            QVERIFY(source.error().contains(QStringLiteral("Windows không giải mã")));
            QVERIFY(source.error().contains(QStringLiteral("Web Media Extensions")));
            qInfo().noquote() << name << source.error();
        }
        std::vector<float> pcm;
        if (opened) {
            QCOMPARE(source.sourceRate(), rate); QCOMPARE(source.sourceChannels(), channels);
            while (source.read(pcm, 4096)) {}
            QVERIFY2(source.error().isEmpty(), qPrintable(source.error())); QVERIFY(source.atEnd());
            const size_t expected = size_t(outRate * 2);
            // Một khung ra mỗi 10 ms nguồn: clip hai giây cho phép sai tối đa 200 khung.
            QVERIFY2(std::abs(double(pcm.size() / 2) - double(expected)) <= 200,
                qPrintable(QStringLiteral("frames=%1 expected=%2 duration=%3").arg(pcm.size() / 2).arg(expected).arg(source.duration())));
            QVERIFY(std::abs(double(pcm.size() / 2) - source.duration() * outRate) <= 1);
            QVERIFY2(chunks.open(bytes), qPrintable(chunks.error()));
            std::vector<float> other;
            for (size_t n = 1; chunks.read(other, n); n = n * 7 % 1500 + 1) {}
            QVERIFY(other == pcm); QVERIFY(chunks.atEnd());
            Mp3Source mp3(outRate); QVERIFY(mp3.open(fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"))));
            std::vector<float> reference; mp3.read(reference, expected);
            if (channels == 1) {
                for (size_t i = 0; i < reference.size(); i += 2)
                    reference[i] = reference[i + 1] = (reference[i] + reference[i + 1]) / 2;
                for (size_t i = 0; i < pcm.size(); i += 2) QCOMPARE(pcm[i], pcm[i + 1]);
            }
            for (int c = 0; c < 2; ++c) {
                const size_t to = std::min(reference.size(), pcm.size()) / 2 - 100;
                const double db = 20 * std::log10(rms(pcm, 2, c, 100, to) / rms(reference, 2, c, 100, to));
                QVERIFY2(std::isfinite(db) && std::abs(db) < (name.endsWith(QLatin1String("m4a")) ? 2 : 1), qPrintable(QString::number(db)));
            }
            qInfo().noquote() << name << "decoded" << source.sourceRate() << source.sourceChannels() << "frames" << pcm.size() / 2;
        }

        MixerRig rig; rig.device->hz = outRate; rig.mixer.service(0);
        // Cố ý đặt đuôi sai: host đổi URL không được đổi bộ giải mã.
        QFile input(rig.dir.filePath(QStringLiteral("misleading.mp3")));
        QVERIFY(input.open(QIODevice::WriteOnly)); QCOMPARE(input.write(bytes), qint64(bytes.size())); input.close();
        const QUrl url = QUrl::fromLocalFile(input.fileName());
        MixVoice voice(&rig.mixer); QSignalSpy failed(&voice, &AudioOut::failed);
        voice.load(url, 0); rig.ready(voice);
        if (!opened) {
            QCOMPARE(failed.size(), 1); QVERIFY(failed.first().first().toString().contains(QStringLiteral("Web Media Extensions")));
            QCOMPARE(voice.duration(), 0.0); QVERIFY(!QFile::exists(rig.mixer.cachePath(url)));
            rig.mixer.serviceReader(); rig.mixer.service(512); QCoreApplication::processEvents(); QCOMPARE(failed.size(), 1);
            return;
        }
        QCOMPARE(failed.size(), 0); QCOMPARE(rig.mixer.decodeCount(), quint64(1));
        QFile cache(rig.mixer.cachePath(url)); QVERIFY(cache.open(QIODevice::ReadOnly));
        const QByteArray contents = cache.readAll(); const auto frames = quint64(pcm.size() / 2);
        QCOMPARE(contents.first(8), QByteArray("ABPCM001", 8));
        QCOMPARE(qFromLittleEndian<quint32>(contents.constData() + 8), quint32(outRate));
        QCOMPARE(qFromLittleEndian<quint32>(contents.constData() + 12), quint32(2));
        QCOMPARE(qFromLittleEndian<quint64>(contents.constData() + 16), frames);
        QCOMPARE(contents.size(), qsizetype(24 + frames * 4));
        QCOMPARE(MusicMixer::cacheFrames(cache.fileName(), outRate), frames);
        for (size_t i = 0; i < pcm.size(); ++i)
            QCOMPARE(qFromLittleEndian<qint16>(contents.constData() + 24 + i * 2),
                qint16(std::clamp(std::lround(pcm[i] * 32768.0f), -32768L, 32767L)));
        cache.close();
        voice.stop(); voice.load(url, 0.5); QVERIFY(rig.ready(voice));
        QCOMPARE(rig.mixer.decodeCount(), quint64(1)); QCOMPARE(voice.position(), 0.5);
        voice.setVolume(1); voice.play(); rig.serve(size_t(outRate / 10)); QVERIFY(voice.playing());
        QVERIFY(rms(rig.device->output, 2, 0, size_t(outRate / 20), size_t(outRate / 10)) > 0.001);
        voice.stop(); voice.load(track(), 0); QVERIFY(rig.ready(voice));
        QFile mp3Cache(rig.mixer.cachePath(track())); QVERIFY(mp3Cache.open(QIODevice::ReadOnly));
        QCOMPARE(mp3Cache.read(16), contents.first(16));
    }

    void mfReaderThreadStartsAndStops() {
        for (int i = 0; i < 2; ++i) {
            QTemporaryDir dir;
            MusicMixer mixer(std::make_unique<FakeDevice>(), dir.path(), true);
            MixVoice voice(&mixer); QSignalSpy failed(&voice, &AudioOut::failed);
            voice.load(QUrl::fromLocalFile(QStringLiteral(MIX_FIXTURES_DIR "/music_student/stereo_44k.wav")), 0);
            QTRY_VERIFY_WITH_TIMEOUT(voice.duration() > 0, 3000);
            QCOMPARE(failed.size(), 0); QCOMPARE(mixer.decodeCount(), quint64(1));
        }
    }

    void mfSurroundKeepsFirstTwoChannels() {
        QByteArray wav(44, '\0');
        std::copy_n("RIFF", 4, wav.data()); qToLittleEndian<quint32>(36 + 1000 * 3 * 4, wav.data() + 4);
        std::copy_n("WAVEfmt ", 8, wav.data() + 8); qToLittleEndian<quint32>(16, wav.data() + 16);
        qToLittleEndian<quint16>(3, wav.data() + 20); qToLittleEndian<quint16>(3, wav.data() + 22);
        qToLittleEndian<quint32>(48000, wav.data() + 24); qToLittleEndian<quint32>(48000 * 12, wav.data() + 28);
        qToLittleEndian<quint16>(12, wav.data() + 32); qToLittleEndian<quint16>(32, wav.data() + 34);
        std::copy_n("data", 4, wav.data() + 36); qToLittleEndian<quint32>(1000 * 12, wav.data() + 40);
        const float channels[] = {0.125f, -0.25f, 0.75f};
        for (int i = 0; i < 1000; ++i) wav.append(reinterpret_cast<const char *>(channels), sizeof(channels));
        MfSource source(48000); QVERIFY2(source.open(wav), qPrintable(source.error())); QCOMPARE(source.sourceChannels(), 3);
        std::vector<float> pcm; while (source.read(pcm, 71)) {}
        QVERIFY2(source.error().isEmpty(), qPrintable(source.error())); QCOMPARE(pcm.size(), size_t(2000));
        for (size_t i = 0; i < pcm.size(); i += 2) { QCOMPARE(pcm[i], channels[0]); QCOMPARE(pcm[i + 1], channels[1]); }
    }

    void musicMagicRejectsBadInputOnce_data() {
        QTest::addColumn<QByteArray>("bytes");
        QTest::newRow("empty") << QByteArray();
        QTest::newRow("unknown") << QByteArray(1000, 'x');
        QTest::newRow("garbage-ID3") << QByteArray("ID3bad");
        QTest::newRow("garbage-sync") << (QByteArray::fromHex("ffe0") + QByteArray(1000, '\0'));
        QTest::newRow("garbage-WAV") << QByteArray("RIFFxxxxWAVEbad");
        QTest::newRow("garbage-FLAC") << QByteArray("fLaCbad");
        QTest::newRow("garbage-M4A") << QByteArray("xxxxftypbad");
        QTest::newRow("garbage-Ogg") << QByteArray("OggSbad");
    }

    void musicMagicRejectsBadInputOnce() {
        QFETCH(QByteArray, bytes);
        MixerRig rig; MixVoice voice(&rig.mixer); QSignalSpy failed(&voice, &AudioOut::failed);
        QFile input(rig.dir.filePath(QStringLiteral("no-extension")));
        QVERIFY(input.open(QIODevice::WriteOnly)); input.write(bytes); input.close();
        const QUrl url = QUrl::fromLocalFile(input.fileName());
        voice.load(url, 0); voice.play();
        for (int i = 0; i < 200 && failed.isEmpty(); ++i) { rig.mixer.serviceReader(); QTest::qWait(1); }
        QCOMPARE(failed.size(), 1); QVERIFY(!failed.first().first().toString().isEmpty());
        QVERIFY(!voice.duration()); QVERIFY(!voice.playing()); QVERIFY(!QFile::exists(rig.mixer.cachePath(url)));
        for (int i = 0; i < 3; ++i) { rig.mixer.serviceReader(); rig.mixer.service(512); QCoreApplication::processEvents(); }
        QCOMPARE(failed.size(), 1); QVERIFY(rig.device->output.empty());
    }

    void mp3MagicIgnoresExtension_data() {
        QTest::addColumn<bool>("stripTag");
        QTest::newRow("ID3") << false; QTest::newRow("frame-sync") << true;
    }

    void mp3MagicIgnoresExtension() {
        QFETCH(bool, stripTag);
        QByteArray bytes = fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"));
        if (stripTag && bytes.startsWith("ID3")) {
            const int size = ((quint8(bytes[6]) & 127) << 21) | ((quint8(bytes[7]) & 127) << 14) |
                ((quint8(bytes[8]) & 127) << 7) | (quint8(bytes[9]) & 127);
            bytes.remove(0, size + 10);
        }
        MixerRig rig; QFile input(rig.dir.filePath(QStringLiteral("actually-mp3.wav")));
        QVERIFY(input.open(QIODevice::WriteOnly)); input.write(bytes); input.close();
        MixVoice voice(&rig.mixer); voice.load(QUrl::fromLocalFile(input.fileName()), 0); QVERIFY(rig.ready(voice));
        Mp3Source source(48000); QVERIFY(source.open(bytes));
        std::vector<float> pcm; while (source.read(pcm, 8192)) {}
        QCOMPARE(MusicMixer::cacheFrames(rig.mixer.cachePath(QUrl::fromLocalFile(input.fileName())), 48000), quint64(pcm.size() / 2));
    }

    void wasapiFormats_data() {
        QTest::addColumn<int>("tag"); QTest::addColumn<int>("bits"); QTest::addColumn<int>("channels");
        QTest::addColumn<int>("extra"); QTest::addColumn<bool>("floatSubtype"); QTest::addColumn<bool>("accepted");
        QTest::newRow("float32-stereo") << int(WAVE_FORMAT_IEEE_FLOAT) << 32 << 2 << 0 << true << true;
        QTest::newRow("float32-surround") << int(WAVE_FORMAT_EXTENSIBLE) << 32 << 6 << 22 << true << true;
        QTest::newRow("pcm16") << int(WAVE_FORMAT_PCM) << 16 << 2 << 0 << false << true;
        QTest::newRow("pcm32-extensible") << int(WAVE_FORMAT_EXTENSIBLE) << 32 << 2 << 22 << false << true;
        QTest::newRow("hfp-pcm16-mono") << int(WAVE_FORMAT_PCM) << 16 << 1 << 0 << false << true;
        QTest::newRow("float64") << int(WAVE_FORMAT_IEEE_FLOAT) << 64 << 2 << 0 << true << false;
        QTest::newRow("mono") << int(WAVE_FORMAT_IEEE_FLOAT) << 32 << 1 << 0 << true << true;
        QTest::newRow("no-channels") << int(WAVE_FORMAT_IEEE_FLOAT) << 32 << 0 << 0 << true << false;
        QTest::newRow("pcm8") << int(WAVE_FORMAT_PCM) << 8 << 2 << 0 << false << false;
        QTest::newRow("short-extensible") << int(WAVE_FORMAT_EXTENSIBLE) << 32 << 2 << 0 << true << false;
    }

    void wasapiFormats() {
        QFETCH(int, tag); QFETCH(int, bits); QFETCH(int, channels); QFETCH(int, extra);
        QFETCH(bool, floatSubtype); QFETCH(bool, accepted);
        WAVEFORMATEXTENSIBLE format{};
        format.Format.wFormatTag = WORD(tag); format.Format.wBitsPerSample = WORD(bits);
        format.Format.nChannels = WORD(channels); format.Format.cbSize = WORD(extra);
        format.SubFormat = floatSubtype ? KSDATAFORMAT_SUBTYPE_IEEE_FLOAT : KSDATAFORMAT_SUBTYPE_PCM;
        QCOMPARE(WasapiDevice::supportsFormat(format.Format), accepted);
    }

    void unsupportedDeviceNotifiesVoices_data() {
        QTest::addColumn<bool>("loaded");
        QTest::newRow("initial-mono") << false;
        QTest::newRow("playing-switch-to-pcm16") << true;
    }

    void unsupportedDeviceNotifiesVoices() {
        QFETCH(bool, loaded);
        MixerRig rig; MixVoice a(&rig.mixer), b(&rig.mixer);
        a.load(track(), 0); b.load(track(), 0);
        if (loaded) {
            QVERIFY(rig.ready(a)); QVERIFY(rig.ready(b));
            a.play(); b.play(); rig.serve(4800); QVERIFY(a.playing()); QVERIFY(b.playing());
            rig.device->format.Format.wFormatTag = WAVE_FORMAT_PCM;
            rig.device->format.Format.wBitsPerSample = 8;
        } else rig.device->format.Format.nChannels = 0;
        QSignalSpy failedA(&a, &AudioOut::failed), failedB(&b, &AudioOut::failed);
        rig.mixer.service(4800); QCoreApplication::processEvents();
        QCOMPARE(failedA.size(), 1); QCOMPARE(failedB.size(), 1);
        QVERIFY(!failedA.first().first().toString().isEmpty());
        QVERIFY(!a.playing()); QVERIFY(!b.playing()); QVERIFY(!rig.device->running);
        const auto samples = rig.device->output.size();
        rig.mixer.serviceReader(); rig.mixer.service(4800); QCoreApplication::processEvents();
        QCOMPARE(failedA.size(), 1); QCOMPARE(failedB.size(), 1);
        QCOMPARE(rig.device->output.size(), samples);

        // A later valid endpoint/load may play again.
        rig.device->format.Format.wFormatTag = WAVE_FORMAT_IEEE_FLOAT;
        rig.device->format.Format.wBitsPerSample = 32; rig.device->format.Format.nChannels = 2;
        a.load(track(), 0); QVERIFY(rig.ready(a)); a.play(); rig.serve(4800); QVERIFY(a.playing());
    }

    void unsupportedDeviceMakesMusicBedSilent() {
        MixerRig rig;
        rig.device->format.Format.nChannels = 0;
        MusicBed bed([&rig]() -> AudioOut * { return new MixVoice(&rig.mixer); }, [](const QString &) { return track(); });
        QSignalSpy results(&bed, &MusicBed::loadResult);
        MusicLogic::MusicCue cue;
        cue.link = QStringLiteral("test-song"); cue.key = cue.src = cue.link; cue.start = 0; cue.end = 120;
        bed.setCues({cue}, -20); bed.sync(10, true);
        rig.mixer.service(4800);
        QTRY_VERIFY(bed.failing());
        QVERIFY(bed.activeLink().isEmpty()); QCOMPARE(bed.voices(), 0);
        QCOMPARE(results.size(), 1); QCOMPARE(results.first().at(1).toBool(), false);
        bed.sync(11, true); QCOMPARE(bed.voices(), 0);
    }

    void mixerCrossfadeRandomBlocks() {
        MixerRig rig;
        const auto render = [&rig](int mode) {
            MixVoice a(&rig.mixer), b(&rig.mixer);
            a.setVolume(mode == 2 ? 0 : 1); b.setVolume(0);
            a.load(track(), 0); b.load(track(), 0);
            if (!rig.ready(a) || !rig.ready(b)) return std::vector<float>{};
            a.play(); b.play(); rig.serve(2400);
            rig.device->output.clear();
            a.setVolume(0); b.setVolume(mode == 1 ? 0 : 1);
            std::mt19937 rng(43);
            size_t left = 2400;
            while (left) { const size_t n = std::min(left, size_t(rng() % 173 + 1)); rig.serve(n); left -= n; }
            const auto result = rig.device->output;
            a.stop(); b.stop(); rig.mixer.service(0);
            return result;
        };
        const auto sum = render(0), down = render(1), up = render(2);
        QCOMPARE(sum.size(), size_t(4800)); QCOMPARE(down.size(), sum.size()); QCOMPARE(up.size(), sum.size());
        QFile cache(rig.mixer.cachePath(track())); QVERIFY(cache.open(QIODevice::ReadOnly));
        QVERIFY(cache.seek(24 + 2400 * 4)); const auto pcm = cache.read(2400 * 4);
        for (size_t i = 0; i < 2400; ++i) {
            const float gain = float(i + 1) / 2400;
            for (size_t c = 0; c < 2; ++c) {
                const float sample = qFromLittleEndian<qint16>(pcm.constData() + (i * 2 + c) * 2) / 32768.0f;
                QVERIFY(std::abs(down[i * 2 + c] - sample * (1 - gain)) < 1e-6);
                QVERIFY(std::abs(up[i * 2 + c] - sample * gain) < 1e-6);
                QVERIFY(std::abs(sum[i * 2 + c] - sample) < 1e-6);
                if (std::abs(sample) > 0.01f)
                    QVERIFY(std::abs((down[i * 2 + c] + up[i * 2 + c]) / sample - 1) < 1e-6);
            }
        }
    }

    void mixerLoopSeamIsExact() {
        MixerRig rig;
        MixVoice voice(&rig.mixer);
        voice.setLoop(true); voice.setVolume(1); voice.load(track(), 0);
        QVERIFY(rig.ready(voice));
        QSignalSpy ended(&voice, &AudioOut::ended);
        const size_t length = size_t(MusicMixer::cacheFrames(rig.mixer.cachePath(track()), rig.mixer.rate()));
        voice.play();
        for (size_t at = 0; at < length + 4096;) {
            const size_t n = std::min<size_t>(997, length + 4096 - at); rig.serve(n); at += n;
        }
        const auto &out = rig.device->output;
        QFile f(rig.mixer.cachePath(track())); QVERIFY(f.open(QIODevice::ReadOnly)); f.seek(24);
        const QByteArray pcm = f.readAll();
        float largest = 0;
        for (size_t i = 1; i < length; ++i)
            for (size_t c = 0; c < 2; ++c)
                largest = std::max(largest, std::abs(out[i * 2 + c] - out[(i - 1) * 2 + c]));
        for (size_t i = 0; i < 4096 * 2; ++i)
            QCOMPARE(out[length * 2 + i], qFromLittleEndian<qint16>(pcm.constData() + i * 2) / 32768.0f);
        for (size_t c = 0; c < 2; ++c) QVERIFY2(std::abs(out[length * 2 + c] - out[(length - 1) * 2 + c]) <= largest,
            qPrintable(QStringLiteral("seam=%1, largest=%2, first=%3, last=%4").arg(std::abs(out[length * 2 + c] - out[(length - 1) * 2 + c])).arg(largest).arg(out[c]).arg(out[(length - 1) * 2 + c])));
        QCOMPARE(ended.size(), 0);
    }

    void mixerUnderrunWritesOnlySilenceAndReportsTransitions() {
        MixerRig rig;
        MixVoice voice(&rig.mixer); voice.setLoop(true); voice.setVolume(1); voice.load(track(), 0);
        QVERIFY(rig.ready(voice)); voice.play();
        QSignalSpy buffering(&voice, &AudioOut::buffering);
        // Không phục vụ reader: dùng hết đúng vòng đệm hai giây rồi để thiếu hai khối.
        for (int i = 0; i < 4; ++i) rig.serve(24000, false);
        rig.device->output.clear(); rig.serve(1024, false); rig.serve(701, false);
        QCOMPARE(buffering.size(), 1); QCOMPARE(buffering[0][0].toBool(), true);
        QVERIFY(std::all_of(rig.device->output.begin(), rig.device->output.end(), [](float x) { return x == 0; }));
        rig.serve(1000); rig.serve(500);
        QCOMPARE(buffering.size(), 2); QCOMPARE(buffering[1][0].toBool(), false);
    }

    void mixVoiceLoadPlayPositionSeekPauseEndStop() {
        MixerRig rig;
        MixVoice voice(&rig.mixer);
        QSignalSpy duration(&voice, &AudioOut::durationChanged), playing(&voice, &AudioOut::playingChanged);
        QSignalSpy seeked(&voice, &AudioOut::seeked), ended(&voice, &AudioOut::ended), failed(&voice, &AudioOut::failed);
        voice.load(track(), 0); voice.play();
        QVERIFY(rig.ready(voice)); QCOMPARE(duration.size(), 1); QVERIFY(std::abs(voice.duration() - 12) < 0.03);
        QCOMPARE(playing.size(), 0); rig.serve(4800); QCOMPARE(playing.size(), 1); QVERIFY(playing[0][0].toBool());
        QCOMPARE(voice.position(), 0.0);
        rig.device->consume(2400); rig.mixer.service(0); QCOMPARE(voice.position(), 0.05);
        rig.device->consume(2400); rig.mixer.service(0); QCOMPARE(voice.position(), 0.1);
        voice.seek(5); QCOMPARE(voice.position(), 5.0); QCOMPARE(seeked.size(), 0);
        rig.mixer.service(0); rig.mixer.serviceReader(); QCoreApplication::processEvents();
        QCOMPARE(seeked.size(), 1); QCOMPARE(voice.position(), 5.0);
        rig.serve(4800); rig.device->consume(2400); rig.mixer.service(0);
        QCOMPARE(voice.position(), 5.05);
        voice.pause(); const int resets = rig.device->resets; rig.mixer.service(0); QCoreApplication::processEvents();
        // Pause: tiếng cũ thêm 20 ms tới pivot rồi mờ ra 10 ms (không tắt phụt); thiết bị chỉ Stop khi đuôi đã phát hết.
        QVERIFY(rig.device->resets > resets); QCOMPARE(rig.device->queued, size_t(1440));
        QVERIFY(std::abs(rig.device->output.back()) < 1e-3);
        rig.device->consume(rig.device->queued); rig.mixer.service(0); QVERIFY(!rig.device->running);
        QCOMPARE(playing.size(), 2); QCOMPARE(playing[1][0].toBool(), false); QCOMPARE(voice.position(), 5.05);
        voice.play(); rig.mixer.serviceReader(); rig.serve(480); QCOMPARE(voice.position(), 5.05);
        voice.seek(voice.duration() - 0.01); rig.mixer.service(0); rig.mixer.serviceReader();
        rig.serve(1024); QCOMPARE(ended.size(), 0); // đuôi còn nằm trong thiết bị
        rig.device->consume(rig.device->queued); rig.mixer.service(0); QCoreApplication::processEvents();
        QCOMPARE(ended.size(), 1); QVERIFY(!voice.playing()); QCOMPARE(failed.size(), 0);
        duration.clear(); playing.clear(); seeked.clear(); ended.clear();
        voice.load(track(), 0); voice.play(); rig.mixer.serviceReader(); voice.stop();
        rig.mixer.serviceReader(); rig.mixer.service(512); QCoreApplication::processEvents();
        QCOMPARE(duration.size() + playing.size() + seeked.size() + ended.size() + failed.size(), 0);
    }

    void mixerCacheReusedAndHasExactFrameCount() {
        MixerRig rig;
        MixVoice first(&rig.mixer); first.load(track(), 0); first.preload(); QVERIFY(rig.ready(first));
        QCOMPARE(rig.mixer.decodeCount(), quint64(1));
        Mp3Source source(rig.mixer.rate()); QVERIFY(source.open(fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"))));
        std::vector<float> all; while (source.read(all, 8192)) {}
        QCOMPARE(MusicMixer::cacheFrames(rig.mixer.cachePath(track()), rig.mixer.rate()), quint64(all.size() / 2));
        first.stop(); MixVoice second(&rig.mixer); second.load(track(), 2); QVERIFY(rig.ready(second));
        QCOMPARE(rig.mixer.decodeCount(), quint64(1)); QCOMPARE(second.position(), 2.0); QVERIFY(!second.playing());
    }

    void mixerCacheSurvivesAnotherMixerAndRejectsTruncation() {
        QTemporaryDir dir;
        { MusicMixer mixer(std::make_unique<FakeDevice>(), dir.path()); MixVoice voice(&mixer); voice.load(track(), 0);
          for (int i = 0; i < 100 && !voice.duration(); ++i) { mixer.serviceReader(); QTest::qWait(1); }
          QVERIFY(voice.duration()); }
        MusicMixer mixer(std::make_unique<FakeDevice>(), dir.path()); MixVoice voice(&mixer); voice.load(track(), 0);
        mixer.serviceReader(); QCoreApplication::processEvents(); QVERIFY(voice.duration()); QCOMPARE(mixer.decodeCount(), quint64(0));
        voice.stop(); QFile cache(mixer.cachePath(track())); QVERIFY(cache.open(QIODevice::WriteOnly)); QVERIFY(cache.resize(30)); cache.close();
        voice.load(track(), 0);
        for (int i = 0; i < 100 && !voice.duration(); ++i) { mixer.serviceReader(); QTest::qWait(1); }
        QVERIFY(voice.duration()); QCOMPARE(mixer.decodeCount(), quint64(1));
    }

    void mixVoiceErrorsAreQueuedAndCancelledByStop() {
        MixerRig rig; MixVoice voice(&rig.mixer); QSignalSpy failed(&voice, &AudioOut::failed);
        voice.load(QUrl::fromLocalFile(rig.dir.filePath(QStringLiteral("missing.mp3"))), 0);
        for (int i = 0; i < 100 && failed.isEmpty(); ++i) { rig.mixer.serviceReader(); QTest::qWait(1); }
        QCOMPARE(failed.size(), 1);
        QFile junk(rig.dir.filePath(QStringLiteral("bad.mp3"))); QVERIFY(junk.open(QIODevice::WriteOnly)); junk.write(QByteArray(1000, 'x')); junk.close();
        voice.load(QUrl::fromLocalFile(junk.fileName()), 0);
        for (int i = 0; i < 100 && failed.size() < 2; ++i) { rig.mixer.serviceReader(); QTest::qWait(1); }
        QCOMPARE(failed.size(), 2);
        voice.load(track(), 0); voice.stop(); rig.mixer.serviceReader(); QTest::qWait(1); QCOMPARE(failed.size(), 2);
    }

    void mixerRebuildsAtSameAndDifferentRates() {
        MixerRig rig; MixVoice voice(&rig.mixer); voice.setLoop(true); voice.load(track(), 0); QVERIFY(rig.ready(voice)); voice.play();
        rig.serve(4800); rig.device->consume(2400); rig.mixer.service(0); QCOMPARE(voice.position(), 0.05);
        ++rig.device->epoch; rig.device->queued = 0; rig.mixer.service(0); rig.mixer.serviceReader(); QCOMPARE(voice.position(), 0.05);
        rig.serve(4800); rig.device->consume(2400); rig.mixer.service(0); QCOMPARE(voice.position(), 0.1);
        rig.device->hz = 44100; ++rig.device->epoch; rig.device->queued = 0; rig.mixer.service(0); QVERIFY(rig.ready(voice));
        for (int i = 0; i < 100 && rig.mixer.decodeCount() < 2; ++i) { rig.mixer.serviceReader(); QTest::qWait(1); }
        QCOMPARE(rig.mixer.rate(), 44100); QCOMPARE(voice.position(), 0.1); QCOMPARE(rig.mixer.decodeCount(), quint64(2));
    }

    void mixerThreadSleepsWhileIdleAndSwitchesLead() {
        struct CounterDevice final : MixDevice {
            std::atomic<int> polls{0}, lastWrite{0};
            std::atomic<bool> running{false};
            int rate() const override { return 48000; }
            bool start() override { running = true; return true; }
            void stop() override { running = false; }
            void reset() override {}
            size_t padding() override { ++polls; return 0; }
            size_t bufferFrames() const override { return 48000; }
            bool write(const float *, size_t n) override { lastWrite = int(n); return true; }
        };
        QTemporaryDir dir; auto *device = new CounterDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true);
        QTest::qWait(300); QCOMPARE(device->polls.load(), 0);
        MixVoice voice(&mixer); voice.load(track(), 0); QTRY_VERIFY_WITH_TIMEOUT(voice.duration() > 0, 3000);
        mixer.setRelaxed(true); voice.play(); QTRY_VERIFY(device->running.load()); QCOMPARE(device->lastWrite.load(), 24000);
        mixer.setRelaxed(false); QTRY_COMPARE(device->lastWrite.load(), 24000);
        voice.pause(); QTRY_VERIFY(!device->running.load());
        QTest::qWait(100); const int polls = device->polls; QTest::qWait(600); QCOMPARE(device->polls.load(), polls);
    }

    void mixerRateChangesWhileReaderOpensCache() {
        struct RateDevice final : MixDevice {
            std::atomic<int> hz{48000};
            std::atomic<quint64> epoch{0};
            int rate() const override { return hz; }
            quint64 revision() const override { return epoch; }
            bool start() override { return true; }
            void stop() override {}
            void reset() override {}
            size_t padding() override { return 0; }
            size_t bufferFrames() const override { return 48000; }
            bool write(const float *, size_t) override { return true; }
        };
        QTemporaryDir dir; auto *device = new RateDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true);
        MixVoice voice(&mixer); QSignalSpy ready(&voice, &AudioOut::durationChanged), failed(&voice, &AudioOut::failed);
        voice.load(track(), 0); voice.play();
        for (int i = 0; i < 10; ++i) {
            device->hz = i % 2 ? 48000 : 44100; ++device->epoch;
            mixer.setRelaxed(i % 2 == 0); QTest::qWait(5);
        }
        ready.clear(); device->hz = 44100; ++device->epoch; mixer.setRelaxed(true);
        QTRY_COMPARE(mixer.rate(), 44100); QTRY_VERIFY(!ready.isEmpty()); QTRY_VERIFY(voice.playing());
        QCOMPARE(failed.size(), 0);
        for (const auto &file : QDir(dir.path()).entryInfoList({QStringLiteral("*.pcm")}, QDir::Files)) {
            const int hz = file.fileName().endsWith(QStringLiteral("44100.pcm")) ? 44100 : 48000;
            QVERIFY(MusicMixer::cacheFrames(file.absoluteFilePath(), hz) > 0);
        }
    }

    void mixerLoopCanEndAfterSeveralWraps() {
        MixerRig rig; MixVoice voice(&rig.mixer); voice.setLoop(true); voice.load(track(), 0); QVERIFY(rig.ready(voice)); voice.play();
        QSignalSpy ended(&voice, &AudioOut::ended);
        const size_t length = MusicMixer::cacheFrames(rig.mixer.cachePath(track()), rig.mixer.rate());
        for (size_t at = 0; at < length + 4800;) {
            const size_t n = std::min<size_t>(12000, length + 4800 - at); rig.serve(n); at += n;
        }
        voice.setLoop(false);
        rig.device->consume(rig.device->queued); rig.mixer.service(0); QCOMPARE(voice.position(), 0.1);
        for (size_t at = 4800; at < length;) { const size_t n = std::min<size_t>(12000, length - at); rig.serve(n); at += n; }
        QCOMPARE(ended.size(), 0);
        rig.device->consume(rig.device->queued); rig.mixer.service(0); QCoreApplication::processEvents();
        QCOMPARE(ended.size(), 1); QVERIFY(!voice.playing());
    }

    void mixerTrimsCacheByOldestMtimeAtStartup() {
        QTemporaryDir dir;
        const auto create = [&dir](const QString &name, int age) {
            QFile file(dir.filePath(name));
            if (!file.open(QIODevice::WriteOnly) || !file.resize(160 * 1024 * 1024)) return false;
            return file.setFileTime(QDateTime::currentDateTimeUtc().addSecs(-age), QFileDevice::FileModificationTime);
        };
        QVERIFY(create(QStringLiteral("old.pcm"), 100)); QVERIFY(create(QStringLiteral("new.pcm"), 10));
        MusicMixer mixer(std::make_unique<FakeDevice>(), dir.path());
        QVERIFY(!QFile::exists(dir.filePath(QStringLiteral("old.pcm")))); QVERIFY(QFile::exists(dir.filePath(QStringLiteral("new.pcm"))));
    }

    void muteOutput() {
        if (qEnvironmentVariableIntValue("ABOOK_MUTE") != 1) {
            QProcess child; auto env = QProcessEnvironment::systemEnvironment(); env.insert(QStringLiteral("ABOOK_MUTE"), QStringLiteral("1"));
            env.insert(QStringLiteral("QT_QPA_PLATFORM"), QStringLiteral("offscreen")); child.setProcessEnvironment(env);
            child.start(QCoreApplication::applicationFilePath(), {QStringLiteral("muteOutput")});
            QVERIFY(child.waitForFinished(30000)); const auto output = child.readAllStandardOutput();
            QVERIFY2(!output.contains("FAIL!"), output.constData()); QCOMPARE(child.exitCode(), 0); return;
        }
        MixerRig rig; MixVoice voice(&rig.mixer); voice.setVolume(1); voice.load(track(), 0); QVERIFY(rig.ready(voice)); voice.play();
        rig.serve(4800); voice.setVolume(0.75); rig.serve(4800);
        QVERIFY(std::all_of(rig.device->output.begin(), rig.device->output.end(), [](float x) { return x == 0; }));
    }
    void ringWrapsAndReportsPartial() {
        Ring ring(8);
        QCOMPARE(ring.capacity(), size_t(8));
        const float a[6] = {1, 2, 3, 4, 5, 6};
        QCOMPARE(ring.write(a, 6), size_t(6));
        float b[8] = {};
        QCOMPARE(ring.read(b, 4), size_t(4));
        QCOMPARE(b[3], 4.0f);
        // qua mép cuối của mảng
        const float c[7] = {7, 8, 9, 10, 11, 12, 13};
        QCOMPARE(ring.write(c, 7), size_t(6)); // còn chỗ 6: 2 cũ + 6 mới = đầy
        QCOMPARE(ring.writable(), size_t(0));
        QCOMPARE(ring.readable(), size_t(8));
        float d[10] = {};
        QCOMPARE(ring.read(d, 10), size_t(8)); // thiếu: trả đúng số có
        const float want[8] = {5, 6, 7, 8, 9, 10, 11, 12};
        for (int i = 0; i < 8; ++i)
            QCOMPARE(d[i], want[i]);
        ring.write(a, 3);
        ring.clear();
        QCOMPARE(ring.readable(), size_t(0));
    }

    void rampIsLinearAndRetargetsFromWhereItStands() {
        Ramp ramp;
        ramp.set(1.0f, 4);
        const std::vector<float> ones(6, 1.0f);
        std::vector<float> out(6, 0.0f);
        ramp.mixInto(out.data(), ones.data(), 6, 1);
        const float want[6] = {0.25f, 0.5f, 0.75f, 1.0f, 1.0f, 1.0f};
        for (int i = 0; i < 6; ++i)
            QVERIFY(std::abs(out[i] - want[i]) < 1e-6f);
        // đổi đích giữa đường: đi tiếp từ 1 về 0 trong 2 khung, mỗi kênh cùng mức
        ramp.set(0.0f, 2);
        std::vector<float> stereo(4, 0.0f);
        const std::vector<float> in(4, 2.0f);
        ramp.mixInto(stereo.data(), in.data(), 2, 2);
        QVERIFY(std::abs(stereo[0] - 1.0f) < 1e-6f && std::abs(stereo[1] - 1.0f) < 1e-6f);
        QCOMPARE(stereo[2], 0.0f);
        QCOMPARE(ramp.value(), 0.0f);
        // cộng dồn chứ không ghi đè; nhảy ngay khi frames = 0
        ramp.set(0.5f, 0);
        std::vector<float> acc(2, 1.0f);
        ramp.mixInto(acc.data(), in.data(), 2, 1);
        QCOMPARE(acc[0], 2.0f);
    }

    void resamplerOutputDoesNotDependOnChunking() {
        std::mt19937 rng(7);
        std::uniform_real_distribution<float> noise(-1, 1);
        std::vector<float> in(20000 * 2);
        for (float &x : in)
            x = noise(rng);
        Resampler whole(44100, 48000, 2);
        std::vector<float> a;
        whole.push(in.data(), in.size() / 2, a);

        Resampler pieces(44100, 48000, 2);
        std::vector<float> b;
        std::uniform_int_distribution<size_t> size(1, 700);
        for (size_t at = 0; at < in.size() / 2;) {
            const size_t n = std::min(size(rng), in.size() / 2 - at);
            pieces.push(in.data() + at * 2, n, b);
            at += n;
        }
        QCOMPARE(b.size(), a.size());
        QVERIFY(a == b);
        // số khung ra: đủ phần đã có trọn cửa sổ
        const double want = 20000.0 * 48000 / 44100;
        QVERIFY(std::abs(double(a.size() / 2) - want) <= 24);
    }

    void resamplerKeepsLevelAndPitch_data() {
        QTest::addColumn<int>("inRate");
        QTest::addColumn<int>("outRate");
        QTest::addColumn<int>("channels");
        QTest::newRow("nhạc 44,1 -> 48") << 44100 << 48000 << 2;
        QTest::newRow("giọng 24 -> 48") << 24000 << 48000 << 1;
        QTest::newRow("thiết bị 44,1: 48 -> 44,1") << 48000 << 44100 << 2;
        QTest::newRow("cùng tần số") << 48000 << 48000 << 2;
    }
    void resamplerKeepsLevelAndPitch() {
        QFETCH(int, inRate);
        QFETCH(int, outRate);
        QFETCH(int, channels);
        const double hz = 1000;
        const std::vector<float> in = sine(hz, inRate, size_t(inRate), channels);
        Resampler resampler(inRate, outRate, channels);
        std::vector<float> out;
        resampler.push(in.data(), size_t(inRate), out);
        const size_t frames = out.size() / channels;
        QVERIFY(frames > size_t(outRate) - 30);
        // so với sin lý tưởng ở tần số ra, bỏ 100 khung đầu (đầu cửa sổ chạm vùng 0 trước nguồn)
        const std::vector<float> ideal = sine(hz, outRate, frames, channels);
        for (int c = 0; c < channels; ++c) {
            double err = 0;
            for (size_t i = 100; i < frames; ++i)
                err += std::pow(double(out[i * channels + c]) - ideal[i * channels + c], 2);
            err = std::sqrt(err / double(frames - 100));
            const double level = rms(out, channels, c, 100, frames);
            QVERIFY2(std::abs(20 * std::log10(level / (0.5 / std::sqrt(2.0)))) < 0.05, qPrintable(QString::number(level)));
            QVERIFY2(err < 1e-3, qPrintable(QString::number(err))); // đúng pha + đúng cao độ: không trễ, không lệch
        }
    }

    // Đáp tuyến đo 27-10 (24 hệ số): 44,1 <-> 48 phẳng tới 16 kHz (-0,04 / -0,09 dB), -1,2 / -1,4 dB ở 18 kHz, -6,7 dB ở 20 kHz;
    // 48 -> 44,1: 23 kHz (sẽ gập thành 21,1 kHz) còn -29 dB - phần gập luôn rơi trên 20 kHz.
    void resamplerResponse_data() {
        QTest::addColumn<int>("inRate");
        QTest::addColumn<int>("outRate");
        QTest::addColumn<double>("hz");
        QTest::addColumn<double>("minDb");
        QTest::addColumn<double>("maxDb");
        QTest::newRow("44,1 -> 48, 16 kHz phẳng") << 44100 << 48000 << 16000.0 << -0.1 << 0.1;
        QTest::newRow("44,1 -> 48, 18 kHz") << 44100 << 48000 << 18000.0 << -2.0 << 0.1;
        QTest::newRow("48 -> 44,1, 16 kHz phẳng") << 48000 << 44100 << 16000.0 << -0.15 << 0.1;
        QTest::newRow("48 -> 44,1, 23 kHz bị chặn") << 48000 << 44100 << 23000.0 << -200.0 << -25.0;
        QTest::newRow("24 -> 48, 5 kHz phẳng") << 24000 << 48000 << 5000.0 << -0.1 << 0.1;
    }
    void resamplerResponse() {
        QFETCH(int, inRate);
        QFETCH(int, outRate);
        QFETCH(double, hz);
        QFETCH(double, minDb);
        QFETCH(double, maxDb);
        const std::vector<float> in = sine(hz, inRate, size_t(inRate), 1);
        Resampler resampler(inRate, outRate, 1);
        std::vector<float> out;
        resampler.push(in.data(), size_t(inRate), out);
        const double db = 20 * std::log10(rms(out, 1, 0, 100, out.size()) / (0.5 / std::sqrt(2.0)));
        QVERIFY2(db >= minDb && db <= maxDb, qPrintable(QString::number(db)));
    }

    void mp3OpensWithLengthAndFormat_data() {
        QTest::addColumn<QString>("file");
        QTest::addColumn<int>("rate");
        QTest::addColumn<int>("channels");
        QTest::addColumn<double>("seconds");
        QTest::newRow("stereo 44,1k") << QStringLiteral("music_student/stereo_44k.mp3") << 44100 << 2 << 12.0;
        QTest::newRow("mono 22k") << QStringLiteral("music_student/mono_22k.mp3") << 22050 << 1 << 5.0;
    }
    void mp3OpensWithLengthAndFormat() {
        QFETCH(QString, file);
        QFETCH(int, rate);
        QFETCH(int, channels);
        QFETCH(double, seconds);
        Mp3Source source(48000);
        QVERIFY(source.open(fixtureBytes(file)));
        QCOMPARE(source.sourceRate(), rate);
        QCOMPARE(source.sourceChannels(), channels);
        QVERIFY2(std::abs(source.duration() - seconds) < 0.03, qPrintable(QString::number(source.duration())));
        // đọc hết: đúng số khung ra theo độ dài, kết thúc rõ ràng
        std::vector<float> out;
        while (source.read(out, 4096)) {
        }
        QVERIFY(source.atEnd());
        const double frames = double(out.size() / 2);
        QVERIFY2(std::abs(frames - source.duration() * 48000) <= 2, qPrintable(QString::number(frames)));
        QVERIFY2(std::abs(source.position() - source.duration()) < 1e-3, qPrintable(QString::number(source.position())));
        double peak = 0;
        for (float x : out)
            peak = std::max(peak, double(std::abs(x)));
        QVERIFY(peak > 0.01 && peak <= 1.05); // có tiếng, không vỡ
        if (channels == 1)
            for (size_t i = 0; i < out.size(); i += 2)
                QCOMPARE(out[i], out[i + 1]); // mono ra hai tai như nhau
    }

    void mp3ReadDoesNotDependOnChunkSize() {
        Mp3Source a(48000), b(48000);
        QVERIFY(a.open(fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"))));
        QVERIFY(b.open(fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"))));
        std::vector<float> x, y;
        while (a.read(x, 4096)) {
        }
        for (size_t n = 1; b.read(y, n); n = n * 7 % 1500 + 1) {
        }
        QVERIFY(x == y);
    }

    void mp3SeekLandsOnTheSameAudio() {
        const QByteArray bytes = fixtureBytes(QStringLiteral("music_student/stereo_44k.mp3"));
        Mp3Source whole(48000), sought(48000);
        QVERIFY(whole.open(bytes));
        QVERIFY(sought.open(bytes));
        std::vector<float> all, part;
        while (whole.read(all, 4096)) {
        }
        sought.seek(5.0);
        QCOMPARE(sought.position(), 5.0);
        sought.read(part, 48000);
        QVERIFY(std::abs(sought.position() - 6.0) < 1e-9);
        // sau 100 khung (cửa sổ bộ đổi tần số đã đầy mẫu thật) trùng bản đọc liền một mạch
        double worst = 0;
        for (size_t i = 100 * 2; i < part.size(); ++i)
            worst = std::max(worst, double(std::abs(part[i] - all[5 * 48000 * 2 + i])));
        QVERIFY2(worst < 1e-3, qPrintable(QString::number(worst)));
        // tua về 0 rồi đọc lại: y hệt lần đầu
        sought.seek(0);
        std::vector<float> again;
        sought.read(again, 4800);
        QVERIFY(std::equal(again.begin(), again.end(), all.begin()));
    }

    void mp3RejectsGarbage() {
        Mp3Source source(48000);
        QVERIFY(!source.open(QByteArray(4000, 'x')));
        std::vector<float> out;
        QCOMPARE(source.read(out, 100), size_t(0));
    }

    void resamplerResetStartsANewSource() {
        const std::vector<float> in = sine(440, 44100, 4410, 2);
        Resampler fresh(44100, 48000, 2), reused(44100, 48000, 2);
        std::vector<float> a, b, junk;
        reused.push(in.data() + 1000, 2000, junk);
        reused.reset();
        reused.push(in.data(), 4410, b);
        fresh.push(in.data(), 4410, a);
        QVERIFY(a == b);
    }
};

QTEST_GUILESS_MAIN(MixTests)
#include "test_mix.moc"
