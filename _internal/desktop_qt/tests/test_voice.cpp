#include "filesinkdevice.h"
#include "musicmixer.h"
#include "streamsource.h"
#include "mp3source.h"
#include "timestretch.h"
#include <QtTest>
#include <QFile>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTemporaryDir>
#include <cmath>
#include <cstring>
#include <condition_variable>
#include <mutex>
#include <thread>
#define NOMINMAX
#include <windows.h>
using MixCore::Ring;

namespace {
QByteArray fixture(const QString &name) {
    QFile file(QStringLiteral(MIX_FIXTURES_DIR "/voice_stream/") + name + QStringLiteral(".mp3"));
    if (!file.open(QIODevice::ReadOnly)) qFatal("Missing voice fixture");
    return file.readAll();
}
struct Device : MixDevice {
    int hz = 48000, resets = 0, stops = 0;
    quint64 epoch = 0;
    size_t queued = 0;
    bool running = false;
    std::vector<float> output;
    int rate() const override { return hz; }
    bool start() override { running = true; return true; }
    void stop() override { ++stops; running = false; }
    void reset() override { ++resets; queued = 0; }
    size_t padding() override { return queued; }
    size_t bufferFrames() const override { return size_t(hz); }
    quint64 revision() const override { return epoch; }
    bool write(const float *samples, size_t n) override { output.insert(output.end(), samples, samples + n * 2); queued += n; return true; }
};
struct Control { bool starved = false, unavailable = false; double duration = 6; int seeks = 0; };
class Decoder : public VoiceDecoder {
    std::shared_ptr<Control> control;
    int hz;
    quint64 at = 0;
public:
    Decoder(std::shared_ptr<Control> control, int hz) : control(std::move(control)), hz(hz) {}
    bool open() override { return !control->unavailable; }
    bool seek(double seconds) override { at = quint64(std::llround(seconds * hz)); ++control->seeks; return !control->unavailable; }
    size_t read(std::vector<float> &out, size_t frames) override {
        if (control->starved) return 0;
        const auto end = quint64(std::llround(duration() * hz));
        frames = size_t(std::min<quint64>(frames, end - std::min(end, at)));
        for (size_t i = 0; i < frames; ++i, ++at) {
            const float x = float(0.25 * std::sin(2 * 3.141592653589793 * 440 * double(at) / hz));
            out.push_back(x); out.push_back(x);
        }
        return frames;
    }
    double duration() const override { return control->duration; }
    bool atEnd() const override { return at >= quint64(std::llround(duration() * hz)); }
    QString error() const override { return {}; }
};
struct Rig {
    QTemporaryDir dir;
    Device *device = new Device;
    MusicMixer mixer{std::unique_ptr<MixDevice>(device), dir.path()};
    std::shared_ptr<Control> control = std::make_shared<Control>();
    MixVoice voice{&mixer, [this](int hz) { return std::make_unique<Decoder>(control, hz); }};
    Rig() { voice.setVolume(1); voice.load(QUrl(QStringLiteral("fake:chapter")), 0); }
    void step(size_t n = 480, bool refill = true) {
        device->queued = 0; mixer.service(0);
        if (refill) mixer.serviceReader();
        mixer.service(n); QCoreApplication::processEvents();
    }
};
class Server : public QTcpServer {
public:
    QByteArray bytes;
    bool ranges = true, malformed = false;
    QVector<qint64> offsets;
    explicit Server(QByteArray data) : bytes(std::move(data)) {
        connect(this, &QTcpServer::newConnection, this, [this] {
            while (hasPendingConnections()) {
                auto *socket = nextPendingConnection(); auto request = std::make_shared<QByteArray>();
                connect(socket, &QTcpSocket::readyRead, socket, [this, socket, request] {
                    if (socket->property("done").toBool()) return;
                    request->append(socket->readAll()); if (!request->contains("\r\n\r\n")) return;
                    socket->setProperty("done", true);
                    qint64 start = 0;
                    for (const auto &line : request->split('\n')) if (line.toLower().startsWith("range:")) start = line.mid(line.indexOf('=') + 1).split('-').first().toLongLong();
                    offsets.append(start);
                    if (!ranges) { socket->write("HTTP/1.1 200 OK\r\nContent-Length: " + QByteArray::number(bytes.size()) + "\r\nConnection: close\r\n\r\n"); socket->write(bytes); }
                    else {
                        const qint64 end = std::min<qint64>(bytes.size(), start + 32768);
                        socket->write("HTTP/1.1 206 Partial Content\r\nContent-Length: " + QByteArray::number(end - start) +
                            "\r\nContent-Range: bytes " + QByteArray::number(start + (malformed ? 1 : 0)) + '-' + QByteArray::number(end - 1) + '/' + QByteArray::number(bytes.size()) + "\r\nConnection: close\r\n\r\n");
                        socket->write(bytes.mid(start, end - start));
                    }
                    socket->disconnectFromHost();
                });
                connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            }
        });
        if (!listen(QHostAddress::LocalHost)) qFatal("Cannot listen");
    }
    QUrl url() const { return QUrl(QStringLiteral("http://127.0.0.1:%1/chapter?t=test").arg(serverPort())); }
};
}

class VoiceTests : public QObject {
    Q_OBJECT
private slots:
    void unityStretchIsBitIdenticalAcrossRingWrapAndEof() {
        Ring input(514);
        TimeStretch stretch(48000); stretch.setRate(1.0);
        // Include signed zero and finite floats that would lose bits through int16 Sonic.
        std::vector<float> source(48000*2), actual;
        for(size_t i=0;i<source.size();++i) source[i]=i%7==0 ? -0.0f : float(std::sin(double(i)*0.017)*0.8734567);
        float output[286]; size_t at=0;
        while(at<source.size() || input.readable()) {
            const auto n=input.write(source.data()+at,std::min<size_t>(314,source.size()-at));at+=n;
            stretch.setRate(1.0);
            const auto got=stretch.read(input,output,143,at==source.size());
            actual.insert(actual.end(),output,output+got*2);
        }
        QCOMPARE(actual.size(),source.size());
        QVERIFY(std::memcmp(actual.data(),source.data(),source.size()*sizeof(float))==0);
        QCOMPARE(stretch.read(input,output,143,true),size_t(0));QVERIFY(stretch.drained());
    }
    void stretchLengthAndPitch_data() {
        QTest::addColumn<double>("speed");
        for (double speed : {0.5, 1.0, 1.5, 4.0}) QTest::newRow(qPrintable(QString::number(speed))) << speed;
    }
    void stretchLengthAndPitch() {
        QFETCH(double, speed);
        Ring input(48000 * 16); std::vector<float> sine(48000 * 16);
        for (size_t i = 0; i < sine.size() / 2; ++i) sine[i * 2] = sine[i * 2 + 1] = float(0.25 * std::sin(2 * 3.141592653589793 * 440 * i / 48000));
        input.write(sine.data(), sine.size()); TimeStretch stretch(48000); stretch.setRate(speed);
        std::vector<float> out; float block[960];
        while (!stretch.drained()) { const size_t n = stretch.read(input, block, 480, true); out.insert(out.end(), block, block + n * 2); }
        const double length = double(out.size() / 2) / 48000;
        // Sonic's integer pitch periods at 4x have <=1% error on a pure 440 Hz tone.
        // The owner's 0.5% length check applies to chapter captures at 1x and 1.5x.
        QVERIFY2(std::abs(length / (8 / speed) - 1) < (speed == 4 ? 0.01 : 0.005), qPrintable(QString::number(length)));
        int crossings = 0; const size_t from = 4800, to = out.size() / 2 - 4800;
        for (size_t i = from + 1; i < to; ++i) if (out[(i - 1) * 2] <= 0 && out[i * 2] > 0) ++crossings;
        const double hz = double(crossings) * 48000 / double(to - from);
        QVERIFY(std::abs(hz - 440) < 8);
    }
    void rateChangeOnAnEmptyQueueKeepsSonicRunning() {
        Rig rig; rig.mixer.serviceReader(); rig.voice.play();
        for (int i = 0; i < 25; ++i) rig.step();
        const double before = rig.voice.position(); const auto seeks = rig.control->seeks;
        rig.voice.setRate(1.5);
        for (int i = 0; i < 20; ++i) rig.step();
        const double delta = rig.voice.position() - before;
        // Hàng đợi đã cạn lúc đổi: không có gì để trộn lại, Sonic đổi tốc độ ngay trên luồng đang chạy, không mở lại nguồn.
        QVERIFY(std::abs(delta - 0.3) < 0.02); QCOMPARE(rig.control->seeks, seeks);
        double jump = 0;
        for (size_t i = 1; i < rig.device->output.size() / 2; ++i) jump = std::max(jump, std::abs(double(rig.device->output[i * 2] - rig.device->output[(i - 1) * 2])));
        QVERIFY(jump < 0.04); // ordinary sine step is 0.0144; a discontinuity is much larger
    }
    void targetPersistsUntilSeekedAndStaleSeekIsSuppressed() {
        Rig rig; rig.mixer.serviceReader(); QSignalSpy seeked(&rig.voice, &AudioOut::seeked);
        rig.control->unavailable = true; rig.voice.seek(3.25); rig.mixer.serviceReader();
        QCOMPARE(rig.voice.position(), 3.25); QCOMPARE(seeked.size(), 0);
        rig.control->unavailable = false; rig.voice.seek(1.75); rig.mixer.serviceReader(); QCoreApplication::processEvents();
        QCOMPARE(seeked.size(), 1); QCOMPARE(rig.voice.position(), 1.75);
        rig.voice.seek(2); rig.mixer.serviceReader(); rig.voice.stop(); QCoreApplication::processEvents(); QCOMPARE(seeked.size(), 1);
    }
    void newerSeekSuppressesAnAlreadyQueuedSeeked() {
        Rig rig; rig.mixer.serviceReader(); QCoreApplication::processEvents();
        QSignalSpy seeked(&rig.voice, &AudioOut::seeked);
        rig.voice.seek(2); rig.mixer.service(0); rig.mixer.serviceReader(); rig.voice.seek(4); rig.mixer.service(0); rig.mixer.serviceReader();
        QCoreApplication::processEvents(); QCOMPARE(seeked.size(), 1); QCOMPARE(rig.voice.position(), 4.0);
    }
    void positionHoldsTargetUntilTheSeekedCallbackIsDelivered() {
        Rig rig; rig.mixer.serviceReader(); rig.voice.play(); QCoreApplication::processEvents();
        QSignalSpy seeked(&rig.voice, &AudioOut::seeked);
        rig.voice.seek(2); rig.mixer.service(0); rig.mixer.serviceReader(); rig.mixer.service(480);
        rig.device->queued = 0; rig.mixer.service(0);
        QCOMPARE(seeked.size(), 0); QCOMPARE(rig.voice.position(), 2.0);
        QCoreApplication::processEvents(); QCOMPARE(seeked.size(), 1); QCOMPARE(rig.voice.position(), 2.01);
    }
    void playingEventReturnsAfterUnderrunAndSeekForPlayerSleepAccounting() {
        Rig rig; rig.voice.play(); QSignalSpy playing(&rig.voice, &AudioOut::playingChanged);
        for (int i = 0; i < 20; ++i) rig.step();
        QCOMPARE(playing.size(), 1); QVERIFY(playing.last().first().toBool());
        rig.control->starved = true;
        for (int i = 0; i < 230; ++i) rig.step();
        QVERIFY(!rig.voice.playing()); QVERIFY(!playing.last().first().toBool());
        rig.control->starved = false; for (int i = 0; i < 10; ++i) rig.step();
        QVERIFY(rig.voice.playing()); QVERIFY(playing.last().first().toBool());
        const auto events = playing.size(); rig.voice.seek(4); rig.step();
        QVERIFY(playing.size() >= events + 2); QVERIFY(playing.last().first().toBool());
    }
    void allRateTransitionsKeepWaveformContinuous() {
        Rig rig; rig.control->duration = 30; rig.voice.play();
        for (double speed : {1.0, 1.5, 0.5, 4.0, 1.0}) {
            rig.voice.setRate(speed);
            for (int i = 0; i < 30; ++i) rig.step();
        }
        double jump = 0;
        for (size_t i = 1; i < rig.device->output.size() / 2; ++i) jump = std::max(jump, std::abs(double(rig.device->output[i * 2] - rig.device->output[(i - 1) * 2])));
        QVERIFY2(jump < 0.04, qPrintable(QString::number(jump)));
    }
    void mixerHttpSeek_data() { indexedHttpSeek_data(); }
    void mixerHttpSeek() {
        QFETCH(QString, name); QFETCH(bool, ranges);
        Server server(fixture(name)); server.ranges = ranges;
        QTemporaryDir dir; auto *device = new Device;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path()); MixVoice voice(&mixer, MixVoice::Voice);
        QSignalSpy failed(&voice, &AudioOut::failed), seeked(&voice, &AudioOut::seeked), buffering(&voice, &AudioOut::buffering);
        voice.load(server.url(), 0); voice.play();
        QTRY_VERIFY_WITH_TIMEOUT(([&] { mixer.serviceReader(); mixer.service(480); return voice.playing(); })(), 5000);
        QCOMPARE(failed.size(), 0); QVERIFY(!buffering.isEmpty());
        voice.seek(12.345); QCOMPARE(voice.position(), 12.345); QCOMPARE(seeked.size(), 0);
        QTRY_VERIFY_WITH_TIMEOUT(([&] { mixer.service(0); mixer.serviceReader(); return !seeked.isEmpty(); })(), 5000);
        QCOMPARE(voice.position(), 12.345); QCOMPARE(seeked.size(), 1); QCOMPARE(failed.size(), 0);
    }
    void underrunSilenceBufferingAndExactlyOneEnd() {
        Rig rig; rig.control->duration = 3; rig.control->starved = true;
        QSignalSpy buffering(&rig.voice, &AudioOut::buffering), ended(&rig.voice, &AudioOut::ended);
        rig.voice.play(); rig.step(); QVERIFY(!buffering.isEmpty()); QCOMPARE(buffering.last().first().toBool(), true);
        QVERIFY(std::all_of(rig.device->output.begin(), rig.device->output.end(), [](float f) { return f == 0; }));
        rig.control->starved = false;
        for (int i = 0; i < 320; ++i) rig.step();
        QCOMPARE(buffering.last().first().toBool(), false); QCOMPARE(ended.size(), 1); QVERIFY(!rig.voice.playing());
        for (int i = 0; i < 10; ++i) rig.step(); QCOMPARE(ended.size(), 1);
    }
    void pauseAllStopsAndResetsWithoutLosingPosition() {
        Rig rig; rig.mixer.serviceReader(); rig.voice.play(); rig.step(2400);
        rig.device->queued = 1200; rig.mixer.service(0); const double at = rig.voice.position();
        rig.voice.pause(); QElapsedTimer timer; timer.start(); rig.mixer.service(0);
        // Hàng đợi 25 ms: pivot lùi để đoạn mờ ra 10 ms vẫn nằm trong tiếng đã xếp; thiết bị Stop khi đuôi đã phát hết.
        QVERIFY(timer.elapsed() < 50); QCOMPARE(rig.device->queued, size_t(1200));
        QVERIFY(std::abs(rig.device->output.back()) < 1e-3);
        rig.device->queued = 0; rig.mixer.service(0); QVERIFY(!rig.device->running);
        QCOMPARE(rig.voice.position(), at); rig.voice.play(); rig.step(480); QCOMPARE(rig.voice.position(), at);
        rig.voice.stop(); rig.mixer.service(0); QCOMPARE(rig.device->queued, size_t(480));
        QVERIFY(std::abs(rig.device->output.back()) < 1e-3);
        rig.device->queued = 0; rig.mixer.service(0); QVERIFY(!rig.device->running); QVERIFY(rig.device->resets > 0);
    }
    void loopCanBeReleasedAfterSeveralWraps() {
        Rig rig; rig.control->duration = 0.25; rig.voice.setLoop(true); rig.voice.play();
        QSignalSpy ended(&rig.voice, &AudioOut::ended);
        for (int i = 0; i < 85; ++i) rig.step();
        QCOMPARE(ended.size(), 0); QVERIFY(rig.voice.position() < 0.25);
        const auto at = rig.voice.position(); rig.voice.setLoop(false); QCOMPARE(rig.voice.position(), at);
        for (int i = 0; i < 35; ++i) rig.step();
        QCOMPARE(ended.size(), 1); QVERIFY(!rig.voice.playing());
    }
    void threadedVoiceStartsWithLargeLeadAndPauseResets_data() {
        QTest::addColumn<bool>("musicFirst");
        QTest::newRow("voice-first") << false;
        QTest::newRow("resume-over-music") << true;
    }
    void threadedVoiceStartsWithLargeLeadAndPauseResets() {
        QFETCH(bool, musicFirst);
        struct QueueDevice : MixDevice {
            std::atomic<size_t> queued{0}, peakAfterReset{0}; std::atomic<int> resets{0};
            std::atomic<bool> running{false};
            std::chrono::steady_clock::time_point sampled = std::chrono::steady_clock::now();
            int rate() const override { return 48000; }
            bool start() override { running = true; return true; }
            void stop() override { running = false; }
            void reset() override { queued = peakAfterReset = 0; sampled = std::chrono::steady_clock::now(); ++resets; }
            size_t padding() override {
                const auto now = std::chrono::steady_clock::now();
                const size_t heard = size_t(std::chrono::duration<double>(now - sampled).count() * 48000);
                queued -= std::min(queued.load(), heard); sampled = now;
                return queued;
            }
            size_t bufferFrames() const override { return 48000; }
            bool write(const float *, size_t n) override { queued += n; peakAfterReset = std::max(peakAfterReset.load(), queued.load()); return true; }
        };
        QTemporaryDir dir; auto *device = new QueueDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true); mixer.setRelaxed(true);
        MixVoice music(&mixer);
        auto control = std::make_shared<Control>();
        MixVoice voice(&mixer, [control](int hz) { return std::make_unique<Decoder>(control, hz); });
        if (musicFirst) {
            music.load(QUrl::fromLocalFile(QStringLiteral(MIX_FIXTURES_DIR "/music_student/stereo_44k.mp3")), 0); music.play();
            QTRY_VERIFY_WITH_TIMEOUT(device->queued.load() >= size_t(12000), 3000);
        }
        voice.load(QUrl(QStringLiteral("fake:chapter")), 0); voice.play();
        QTRY_VERIFY_WITH_TIMEOUT(voice.playing(), 3000);
        QVERIFY(device->peakAfterReset.load() > size_t(1440));
        QVERIFY(device->peakAfterReset.load() <= size_t(24000));
        music.pause(); const int resets = device->resets;
        QElapsedTimer timer; timer.start(); voice.pause();
        while (device->resets == resets && timer.elapsed() < 100) QTest::qWait(1);
        QVERIFY2(timer.elapsed() < 50, qPrintable(QString::number(timer.elapsed())));
        // Sau đuôi mờ 10 ms thiết bị dừng hẳn.
        QTRY_VERIFY_WITH_TIMEOUT(!device->running && device->queued.load() == 0, 200);
    }
    void hiddenLeadPreservesPcmOnRestoreAndHandlesFourTimesSpeed() {
        struct QueueDevice : MixDevice {
            std::atomic<size_t> queued{0}, peak{0};
            std::atomic<int> resets{0}, empty{0};
            bool running = false;
            std::chrono::steady_clock::time_point sampled = std::chrono::steady_clock::now();
            int rate() const override { return 48000; }
            bool start() override { sampled = std::chrono::steady_clock::now(); running = true; return true; }
            void stop() override { padding(); running = false; }
            void reset() override { queued = peak = 0; ++resets; }
            size_t padding() override {
                const auto now = std::chrono::steady_clock::now();
                if (running) {
                    const auto n = size_t(std::chrono::duration<double>(now - sampled).count() * 48000);
                    if (n >= queued) ++empty;
                    queued -= std::min(queued.load(), n);
                }
                sampled = now; return queued;
            }
            size_t bufferFrames() const override { return 48000; }
            bool write(const float *, size_t n) override { queued += n; peak = std::max(peak.load(), queued.load()); return true; }
        };
        QTemporaryDir dir; auto *device = new QueueDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true);
        auto control = std::make_shared<Control>(); control->duration = 60;
        MixVoice voice(&mixer, [control](int hz) { return std::make_unique<Decoder>(control, hz); });
        mixer.setRelaxed(true); voice.load(QUrl(QStringLiteral("fake:hidden-lead")), 0); voice.play();
        QTRY_VERIFY_WITH_TIMEOUT(device->peak.load() >= size_t(43200), 4000);
        const double before = voice.position(); const int resets = device->resets;
        QElapsedTimer timer; timer.start(); mixer.setRelaxed(false);
        QVERIFY(timer.elapsed() < 50);
        QTest::qWait(250); QCOMPARE(device->resets.load(),resets);
        QVERIFY(std::abs(voice.position() - before - timer.elapsed()/1000.0) < 0.03);
        device->peak=0; QTest::qWait(650);
        QTRY_VERIFY(voice.playing()); QVERIFY(device->peak.load() <= size_t(24000));
        mixer.setRelaxed(true); voice.setRate(4.0);
        QTest::qWait(3100); QVERIFY(voice.playing()); QCOMPARE(device->empty.load(), 0);
        // Returning from 4x must also use the exact fresh unity path after reset.
        voice.setRate(1.0); QTest::qWait(100); QVERIFY(voice.playing());
    }
    void blockedDecoderCannotBlockMixerPauseOrStop() {
        struct Barrier { std::mutex mutex; std::condition_variable cv; std::atomic<bool> entered{false}; bool release = false; };
        struct BlockingDecoder : Decoder {
            std::shared_ptr<Barrier> barrier;
            BlockingDecoder(std::shared_ptr<Control> control, int hz, std::shared_ptr<Barrier> barrier)
                : Decoder(std::move(control), hz), barrier(std::move(barrier)) {}
            size_t read(std::vector<float> &out, size_t n) override {
                { std::unique_lock<std::mutex> lock(barrier->mutex); barrier->entered = true;
                  barrier->cv.wait(lock, [&] { return barrier->release; }); }
                return Decoder::read(out, n);
            }
        };
        struct CounterDevice : MixDevice {
            std::atomic<int> resets{0};
            int rate() const override { return 48000; }
            bool start() override { return true; }
            void stop() override {}
            void reset() override { ++resets; }
            size_t padding() override { return 0; }
            size_t bufferFrames() const override { return 48000; }
            bool write(const float *, size_t) override { return true; }
        };
        QTemporaryDir dir; auto *device = new CounterDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true);
        auto control = std::make_shared<Control>(); auto barrier = std::make_shared<Barrier>();
        MixVoice voice(&mixer, [control, barrier](int hz) { return std::make_unique<BlockingDecoder>(control, hz, barrier); });
        voice.load(QUrl(QStringLiteral("fake:slow-disk")), 0); voice.play();
        QTRY_VERIFY_WITH_TIMEOUT(barrier->entered.load(), 3000);
        std::jthread release([barrier] {
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
            { std::lock_guard<std::mutex> lock(barrier->mutex); barrier->release = true; }
            barrier->cv.notify_all();
        });
        QElapsedTimer timer; timer.start(); const int resets = device->resets;
        voice.pause(); QVERIFY(timer.elapsed() < 50);
        while (device->resets == resets && timer.elapsed() < 100) QTest::qWait(1);
        QVERIFY(timer.elapsed() < 50);
        timer.restart(); voice.stop(); QVERIFY(timer.elapsed() < 50);
    }
    void largeLeadTimerAndPauseControlWakeIndependently() {
        struct EventDevice : MixDevice {
            std::atomic<size_t> queued{0}; std::atomic<int> writes{0}, resets{0};
            std::chrono::steady_clock::time_point sampled = std::chrono::steady_clock::now();
            bool running = false;
            int rate() const override { return 48000; }
            bool start() override { sampled = std::chrono::steady_clock::now(); running = true; return true; }
            void stop() override { padding(); running = false; }
            void reset() override { queued = 0; ++resets; }
            size_t padding() override {
                const auto now = std::chrono::steady_clock::now();
                if (running) queued -= std::min(queued.load(), size_t(std::chrono::duration<double>(now - sampled).count() * 48000));
                sampled = now; return queued;
            }
            // Small endpoint capacity exercises the padding floor / early wake guard.
            size_t bufferFrames() const override { return 3840; }
            bool write(const float *, size_t n) override { queued += n; ++writes; return true; }
        };
        QTemporaryDir dir; auto *device = new EventDevice;
        MusicMixer mixer(std::unique_ptr<MixDevice>(device), dir.path(), true);
        auto control = std::make_shared<Control>();
        MixVoice voice(&mixer, [control](int hz) { return std::make_unique<Decoder>(control, hz); });
        voice.load(QUrl(QStringLiteral("fake:event-device")), 0); voice.play();
        QTRY_VERIFY_WITH_TIMEOUT(voice.playing(), 3000);
        const int writes = device->writes; QTest::qWait(180);
        QVERIFY(device->writes >= writes + 2);
        QElapsedTimer timer;
        const int resets = device->resets; timer.restart(); voice.pause();
        while (device->resets == resets && timer.elapsed() < 100) QTest::qWait(1);
        QVERIFY(timer.elapsed() < 50); QVERIFY(device->queued.load() <= size_t(1440)); // tới pivot 20 ms + mờ ra 10 ms
        QTRY_VERIFY_WITH_TIMEOUT(!device->running && device->queued.load() == 0, 200);
    }
    void controlsRemixAtTheCursorWithLargeLead_data() {
        QTest::addColumn<QString>("command");
        QTest::addColumn<int>("lead");
        for (const auto *command : {"rate", "volume", "pause", "seek", "stop"}) for (int lead : {24000, 43200})
            QTest::newRow(qPrintable(QString::fromLatin1(command) + QString::number(lead))) << QString::fromLatin1(command) << lead;
    }
    void controlsRemixAtTheCursorWithLargeLead() {
        QFETCH(QString, command);
        QFETCH(int, lead);
        Rig rig; auto otherControl = std::make_shared<Control>();
        MixVoice other(&rig.mixer, [otherControl](int hz) { return std::make_unique<Decoder>(otherControl, hz); });
        other.load(QUrl(QStringLiteral("fake:music")), 0); other.setVolume(0);
        rig.mixer.serviceReader(); rig.voice.play(); other.play(); rig.mixer.service(size_t(lead));
        QCOMPARE(rig.device->queued, size_t(lead));
        const std::vector<float> queued = rig.device->output;
        rig.device->queued = size_t(lead - 2400); rig.mixer.service(0);
        QCOMPARE(rig.voice.position(), 0.05); QCOMPARE(other.position(), 0.05);
        const int resets = rig.device->resets;
        if (command == QStringLiteral("rate")) rig.voice.setRate(1.5);
        if (command == QStringLiteral("volume")) rig.voice.setVolume(0);
        if (command == QStringLiteral("pause")) rig.voice.pause();
        if (command == QStringLiteral("seek")) rig.voice.seek(2);
        if (command == QStringLiteral("stop")) rig.voice.stop();
        // Reader gets a turn first: it must retain spans until the shared reset samples padding.
        rig.mixer.serviceReader(); rig.device->output.clear(); rig.mixer.service(0);
        // Một lần Stop/Reset/Write/Start tại con trỏ, ngay trong lượt này: giọng kia giữ nguyên hàng đợi của nó.
        QCOMPARE(rig.device->resets, resets + 1); QCOMPARE(rig.device->queued, size_t(lead - 2400));
        QVERIFY(rig.device->running); QCOMPARE(other.position(), 0.05);
        const std::vector<float> remix = rig.device->output;
        QCOMPARE(remix.size(), size_t(lead - 2400) * 2);
        // Viết lại bắt đầu đúng mẫu đang nghe, sóng liền (bước sin thường 0,0144), rồi im đúng sau đoạn mờ của từng lệnh.
        QVERIFY(std::abs(remix[0] - queued[2400 * 2]) < 0.001);
        double jump = std::abs(double(remix[0] - queued[2399 * 2]));
        for (size_t i = 1; i < remix.size() / 2; ++i) jump = std::max(jump, std::abs(double(remix[i * 2] - remix[(i - 1) * 2])));
        QVERIFY2(jump < 0.02, qPrintable(QString::number(jump)));
        // Mọi thay đổi bắt đầu ở pivot = con trỏ + 20 ms (960 khung); trước đó là đúng tiếng cũ.
        QVERIFY(std::equal(remix.begin(), remix.begin() + 960 * 2, queued.begin() + 2400 * 2));
        const size_t silentFrom = 960 + (command == QStringLiteral("volume") ? 2400 : command == QStringLiteral("rate") ? 2880 + 240 :
            command == QStringLiteral("seek") ? 240 : 480);
        QVERIFY(std::all_of(remix.begin() + qsizetype(silentFrom * 2), remix.end(), [](float f) { return f == 0; }));
        QVERIFY(std::abs(remix[(silentFrom - 1) * 2]) < 0.001);
        rig.mixer.serviceReader(); rig.device->output.clear(); rig.mixer.service(size_t(lead));
        rig.device->queued -= 4800; rig.mixer.service(0); QCoreApplication::processEvents();
        QVERIFY(std::abs(other.position() - 0.15) < 1e-8);
        // Tua: nối vào ở pivot (2 + 0,08). Tốc độ: 20 ms tới pivot + 60 ms cầu ở 1x, rồi 1,5x (0,13 + 0,02 * 1,5).
        const double want = command == QStringLiteral("stop") ? 0 : command == QStringLiteral("pause") ? 0.05 :
            command == QStringLiteral("seek") ? 2.08 : command == QStringLiteral("rate") ? 0.16 : 0.15;
        QVERIFY2(std::abs(rig.voice.position() - want) < 0.001, qPrintable(QString::number(rig.voice.position())));
    }
    // Tai giả (engine kéo 10 ms một chu kỳ như WASAPI chia sẻ): nhạc vào giữa lúc giọng đọc, mờ vào/ra từng 50 ms như
    // MusicBed, giọng đổi tốc độ, tua trong lúc phát không được để lại chu kỳ im lặng, khoảng hụt hay bậc nhảy nào trước
    // lúc pause; pause thì mờ về 0.
    void controlsLeaveNoHoleOrStepOnAPeriodicEngine() {
        QTemporaryDir dir;
        const QString wav = dir.filePath(QStringLiteral("tap.wav"));
        quint64 paused = 0;
        std::vector<std::pair<quint64, const char *>> marks;
        {
            auto *sink = new FileSinkDevice(wav);
            MusicMixer mixer(std::unique_ptr<MixDevice>(sink), dir.path(), true);
            auto control = std::make_shared<Control>(); control->duration = 30;
            MixVoice voice(&mixer, [control](int hz) { return std::make_unique<Decoder>(control, hz); });
            voice.setVolume(1); voice.load(QUrl(QStringLiteral("fake:tap")), 0); voice.play();
            QTRY_VERIFY_WITH_TIMEOUT(voice.playing(), 3000);
            QTest::qWait(300);
            MixVoice music(&mixer, [control](int hz) { return std::make_unique<Decoder>(control, hz); });
            marks.push_back({sink->now(), "music play"}); music.load(QUrl(QStringLiteral("fake:music")), 3); music.play();
            for (int i = 1; i <= 16; ++i) {
                marks.push_back({sink->now(), "volume"}); voice.setVolume(1.0 - i * 0.03); music.setVolume(i * 0.03); QTest::qWait(50);
            }
            marks.push_back({sink->now(), "rate 1.5"}); voice.setRate(1.5); QTest::qWait(250);
            marks.push_back({sink->now(), "seek"}); voice.seek(12); QTest::qWait(250);
            marks.push_back({sink->now(), "rate 1"}); voice.setRate(1.0); QTest::qWait(250);
            for (int i = 15; i >= 0; --i) { marks.push_back({sink->now(), "music volume"}); music.setVolume(i * 0.03); QTest::qWait(50); }
            paused = sink->now(); voice.pause(); music.pause();
            QTest::qWait(200);
        }
        QFile file(wav); QVERIFY(file.open(QIODevice::ReadOnly));
        const QByteArray bytes = file.readAll().mid(44);
        const auto *x = reinterpret_cast<const float *>(bytes.constData());
        const size_t frames = size_t(bytes.size()) / 8;
        QVERIFY(frames > paused + 4800);
        for (const QString suffix : {QStringLiteral(".stops"), QStringLiteral(".gaps")}) {
            QFile list(wav + suffix); QVERIFY(list.open(QIODevice::ReadOnly));
            for (const QByteArray &line : list.readAll().split('\n')) {
                if (line.isEmpty()) continue;
                const quint64 at = line.split(' ').value(0).toULongLong();
                QVERIFY2(at >= paused, qPrintable(suffix + QStringLiteral(" at ") + QString::number(at) + QStringLiteral(" before pause ") + QString::number(paused)));
            }
        }
        // Từ lúc có tiếng tới hết đuôi mờ của pause: hai sin 440 Hz biên 0,25 và <= 0,25 · 0,48² đổi tối đa 0,018 mỗi mẫu.
        size_t first = 0; while (first < frames && x[first * 2] == 0.0f) ++first;
        double jump = 0; size_t where = 0;
        for (size_t i = first + 1; i < frames; ++i)
            if (const double d = std::abs(double(x[i * 2] - x[(i - 1) * 2])); d > jump) { jump = d; where = i; }
        QString closest = QStringLiteral("pause");
        qint64 from = where >= paused ? qint64(where - paused) : std::numeric_limits<qint64>::max();
        for (const auto &[at, op] : marks) if (at <= where && qint64(where - at) < from) { from = qint64(where - at); closest = QString::fromLatin1(op); }
        QVERIFY2(jump < 0.04, qPrintable(QStringLiteral("%1 at %2 ms after %3 (%4)").arg(jump).arg(from / 48.0).arg(closest).arg(where)));
    }
    void formatRebuildPreservesRateAwarePosition() {
        Rig rig; rig.voice.setRate(1.5); rig.voice.play();
        for (int i = 0; i < 30; ++i) rig.step();
        rig.device->queued = 0; rig.mixer.service(0); const double at = rig.voice.position();
        rig.device->hz = 16000; ++rig.device->epoch; rig.mixer.service(0); rig.mixer.serviceReader();
        QCOMPARE(rig.mixer.rate(), 16000); QVERIFY(std::abs(rig.voice.position() - at) < 0.0001);
        rig.step(1600); rig.device->queued = 0; rig.mixer.service(0); QVERIFY(std::abs(rig.voice.position() - at - 0.15) < 0.005);
    }
    void indexedHttpSeek_data() {
        QTest::addColumn<QString>("name"); QTest::addColumn<bool>("ranges");
        for (const auto &name : {QStringLiteral("cbr"), QStringLiteral("vbr")}) for (bool ranges : {true, false})
            QTest::newRow(qPrintable(name + (ranges ? QStringLiteral("-206") : QStringLiteral("-200")))) << name << ranges;
    }
    void indexedHttpSeek() {
        QFETCH(QString, name); QFETCH(bool, ranges);
        const auto bytes = fixture(name); Server server(bytes); server.ranges = ranges;
        auto source = std::make_shared<RangeSource>(server.url(), [] {}); StreamMp3 decoder(source, 48000);
        QTRY_VERIFY_WITH_TIMEOUT(decoder.open(), 5000);
        Mp3Source reference(48000); QVERIFY(reference.open(bytes));
        QVERIFY(std::abs(decoder.duration() - reference.duration()) < 0.001);
        const double target = 12.345; QTRY_VERIFY_WITH_TIMEOUT(decoder.seek(target), 5000);
        std::vector<float> got; QTRY_VERIFY_WITH_TIMEOUT(decoder.read(got, 4800) > 0, 5000);
        reference.seek(target); std::vector<float> expected; reference.read(expected, 4800);
        QVERIFY(got.size() >= 4000); double error = 0;
        for (size_t i = 1000; i < std::min(got.size(), expected.size()); ++i) error += std::pow(got[i] - expected[i], 2);
        QVERIFY2(error / got.size() < 1e-8, qPrintable(QString::number(error / got.size(), 'g', 12)));
        QVERIFY(!server.offsets.isEmpty());
        if (ranges) QVERIFY(std::any_of(server.offsets.begin(), server.offsets.end(), [](qint64 at) { return at > 0; }));
        else QCOMPARE(server.offsets.size(), 1);
    }
    void malformedRangeFails() {
        Server server(fixture(QStringLiteral("cbr"))); server.malformed = true;
        auto source = std::make_shared<RangeSource>(server.url(), [] {}); StreamMp3 decoder(source, 48000);
        decoder.open(); QTRY_VERIFY(!decoder.error().isEmpty()); QVERIFY(!decoder.open());
    }
    void localStreamingMatchesCachedDecoder() {
        for (const auto &name : {QStringLiteral("cbr"), QStringLiteral("vbr")}) {
            const QUrl url = QUrl::fromLocalFile(QStringLiteral(MIX_FIXTURES_DIR "/voice_stream/") + name + QStringLiteral(".mp3"));
            auto source = std::make_shared<RangeSource>(url, [] {}); StreamMp3 decoder(source, 48000); QVERIFY(decoder.open());
            Mp3Source reference(48000); QVERIFY(reference.open(fixture(name))); std::vector<float> a, b;
            while (decoder.read(a, 8192)) {} while (reference.read(b, 8192)) {}
            QVERIFY(decoder.atEnd()); QCOMPARE(a.size(), b.size());
            double error = 0; for (size_t i = 0; i < a.size(); ++i) error += std::pow(a[i] - b[i], 2);
            QVERIFY2(error / a.size() < 1e-9, qPrintable(QString::number(error / a.size(), 'g', 12)));
        }
    }
    void refillChunkSizeDoesNotChangePcmOrSeeks() {
        for(const auto &name : {QStringLiteral("cbr"),QStringLiteral("vbr")}) {
            const QUrl url=QUrl::fromLocalFile(QStringLiteral(MIX_FIXTURES_DIR "/voice_stream/")+name+QStringLiteral(".mp3"));
            for(double seek : {0.0, 0.073, 12.345}) {
                std::vector<float> reference;
                for(size_t chunk : {size_t(257),size_t(8192),size_t(48000)}) {
                    auto source=std::make_shared<RangeSource>(url,[]{});StreamMp3 decoder(source,48000);
                    QVERIFY(decoder.open());QVERIFY(decoder.seek(seek));std::vector<float> pcm;
                    while(decoder.read(pcm,chunk)){}QVERIFY(decoder.atEnd());
                    if(reference.empty())reference=pcm;
                    else { QCOMPARE(pcm.size(),reference.size());QVERIFY(std::memcmp(pcm.data(),reference.data(),pcm.size()*sizeof(float))==0); }
                }
            }
        }
    }
};
QTEST_GUILESS_MAIN(VoiceTests)
#include "test_voice.moc"
