// Đo hai ứng viên lõi phát (D1 bước 1): cùng giao diện AudioOut, cùng kịch bản, ra JSON một dòng.
//   audiobench --engine mf|qt --mode play|seek|gap|capture --url <http://...mp3> [--start s] [--rate r] [--seconds n] [--out file]
// Không cửa sổ: so lõi với lõi. Âm lượng luôn do ABOOK_MUTE=1 ép về 0 (trừ chế độ capture, xem docs trong báo cáo D1).
#include "audioout.h"
#include "audioout_mf.h"
#ifndef NO_QT_ENGINE
#include "audioout_qt.h"
#endif

#include <QCommandLineParser>
#include <QElapsedTimer>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonDocument>
#include <QTimer>

#include <atomic>
#include <functional>
#include <thread>
#include <vector>

#include <windows.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <psapi.h>

static double cpuSeconds() {
    FILETIME create, exit, kernel, user;
    GetProcessTimes(GetCurrentProcess(), &create, &exit, &kernel, &user);
    auto value = [](const FILETIME &t) { return ((quint64(t.dwHighDateTime) << 32) | t.dwLowDateTime) / 1e7; };
    return value(kernel) + value(user);
}

static double privateMb() {
    PROCESS_MEMORY_COUNTERS_EX counters{};
    counters.cb = sizeof(counters);
    GetProcessMemoryInfo(GetCurrentProcess(), reinterpret_cast<PROCESS_MEMORY_COUNTERS *>(&counters), sizeof(counters));
    return counters.PrivateUsage / 1048576.0;
}

// ---- WASAPI loopback: ghi cái đang ra thiết bị mặc định (float32 mono, đã trộn) vào WAV ---------------------------------------------------------
static void captureLoopback(const QString &path, double seconds, std::atomic<bool> *started) {
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    IMMDeviceEnumerator *enumerator = nullptr;
    IMMDevice *device = nullptr;
    IAudioClient *client = nullptr;
    IAudioCaptureClient *capture = nullptr;
    WAVEFORMATEX *format = nullptr;
    std::vector<float> samples;
    if (SUCCEEDED(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, IID_PPV_ARGS(&enumerator))) &&
        SUCCEEDED(enumerator->GetDefaultAudioEndpoint(eRender, eConsole, &device)) &&
        SUCCEEDED(device->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void **>(&client))) &&
        SUCCEEDED(client->GetMixFormat(&format)) &&
        SUCCEEDED(client->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 10000000, 0, format, nullptr)) &&
        SUCCEEDED(client->GetService(IID_PPV_ARGS(&capture)))) {
        client->Start();
        started->store(true);
        const int channels = format->nChannels;
        QElapsedTimer clock;
        clock.start();
        while (clock.elapsed() < seconds * 1000) {
            Sleep(10);
            UINT32 packet = 0;
            while (SUCCEEDED(capture->GetNextPacketSize(&packet)) && packet) {
                BYTE *data = nullptr;
                UINT32 frames = 0;
                DWORD flags = 0;
                capture->GetBuffer(&data, &frames, &flags, nullptr, nullptr);
                const float *in = reinterpret_cast<const float *>(data);
                for (UINT32 i = 0; i < frames; ++i) {
                    float sum = 0;
                    for (int c = 0; c < channels; ++c)
                        sum += (flags & AUDCLNT_BUFFERFLAGS_SILENT) ? 0.f : in[i * channels + c];
                    samples.push_back(sum / channels);
                }
                capture->ReleaseBuffer(frames);
            }
        }
        client->Stop();
        // WAV float32 mono
        QFile file(path);
        if (file.open(QIODevice::WriteOnly)) {
            const quint32 rate = format->nSamplesPerSec, bytes = quint32(samples.size() * 4);
            auto put32 = [&](quint32 v) { file.write(reinterpret_cast<const char *>(&v), 4); };
            auto put16 = [&](quint16 v) { file.write(reinterpret_cast<const char *>(&v), 2); };
            file.write("RIFF"); put32(36 + bytes); file.write("WAVEfmt "); put32(16); put16(3); put16(1); put32(rate); put32(rate * 4); put16(4); put16(32);
            file.write("data"); put32(bytes);
            file.write(reinterpret_cast<const char *>(samples.data()), bytes);
        }
    } else {
        started->store(true);
    }
    if (format) CoTaskMemFree(format);
    if (capture) capture->Release();
    if (client) client->Release();
    if (device) device->Release();
    if (enumerator) enumerator->Release();
    CoUninitialize();
}

struct Run {
    AudioOut *out = nullptr;
    QJsonObject result;
};

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QCommandLineParser parser;
    for (const char *name : {"engine", "mode", "url", "url2", "start", "rate", "seconds", "out", "targets", "volume"})
        parser.addOption(QCommandLineOption(QString::fromLatin1(name), QString(), QStringLiteral("v")));
    parser.process(app);
    const QString engine = parser.value(QStringLiteral("engine"));
    const QString mode = parser.value(QStringLiteral("mode"));
    const QUrl url(parser.value(QStringLiteral("url")));
    const QUrl url2(parser.value(QStringLiteral("url2")));
    const double start = parser.value(QStringLiteral("start")).toDouble();
    const double rate = parser.isSet(QStringLiteral("rate")) ? parser.value(QStringLiteral("rate")).toDouble() : 1.0;
    const double seconds = parser.isSet(QStringLiteral("seconds")) ? parser.value(QStringLiteral("seconds")).toDouble() : 20.0;
    const double volume = parser.isSet(QStringLiteral("volume")) ? parser.value(QStringLiteral("volume")).toDouble() : 1.0;

    #ifdef NO_QT_ENGINE
    AudioOut *out = new MfAudioOut;
#else
    AudioOut *out = engine == QLatin1String("mf") ? static_cast<AudioOut *>(new MfAudioOut) : static_cast<AudioOut *>(new QtAudioOut);
#endif
    QJsonObject result{{"engine", engine}, {"mode", mode}, {"rate", rate}};
    QElapsedTimer wall;
    QElapsedTimer lap;
    std::atomic<bool> captureStarted{false};
    std::thread captureThread;

    auto finish = [&] {
        static bool done = false;
        if (done)
            return;
        done = true;
        result["private_mb_end"] = privateMb();
        const QByteArray line = QJsonDocument(result).toJson(QJsonDocument::Compact) + "\n";
        const QString path = parser.value(QStringLiteral("out"));
        if (!path.isEmpty()) {
            QFile file(path);
            if (file.open(QIODevice::WriteOnly | QIODevice::Append))
                file.write(line);
        }
        fputs(line.constData(), stdout);
        fflush(stdout);
        out->stop();
        QTimer::singleShot(100, &app, &QGuiApplication::quit);
    };

    QObject::connect(out, &AudioOut::failed, &app, [&](const QString &reason) {
        result["error"] = reason;
        finish();
    });

    double startedCpu = 0, firstPosition = -1, lastPosition = 0, maxMb = 0;
    std::function<void()> beginClock, nextSeek;
    if (mode == QLatin1String("play") || mode == QLatin1String("capture")) {
        // Phát `seconds` giây tường ở tốc độ `rate`; đo CPU, RAM riêng, và tốc độ tiến thật của vị trí.
        beginClock = [&] {
            wall.start();
            startedCpu = cpuSeconds();
            firstPosition = out->position();
            result["private_mb_start"] = privateMb();
            result["load_to_playing_ms"] = double(lap.elapsed());
        };
        QObject::connect(out, &AudioOut::playingChanged, &app, [&](bool playing) {
            if (playing && firstPosition < 0) {
                beginClock();
                if (mode == QLatin1String("capture")) {
                    captureThread = std::thread(captureLoopback, parser.value(QStringLiteral("out")) + QStringLiteral(".wav"), seconds - 1.0, &captureStarted);
                }
            }
        });
        auto *sample = new QTimer(&app);
        sample->setInterval(250);
        QObject::connect(sample, &QTimer::timeout, &app, [&] {
            if (firstPosition < 0)
                return;
            lastPosition = out->position();
            maxMb = qMax(maxMb, privateMb());
            if (wall.elapsed() >= seconds * 1000) {
                sample->stop();
                const double elapsed = wall.elapsed() / 1000.0;
                result["wall_s"] = elapsed;
                result["cpu_percent"] = (cpuSeconds() - startedCpu) / elapsed * 100.0;
                result["position_advance_s"] = lastPosition - firstPosition;
                result["effective_rate"] = (lastPosition - firstPosition) / elapsed;
                result["private_mb_max"] = maxMb;
                if (captureThread.joinable())
                    captureThread.join();
                finish();
            }
        });
        sample->start();
        lap.start();
        out->setVolume(volume);
        out->load(url, start);
        out->setRate(rate);
        out->play();
    } else if (mode == QLatin1String("seek")) {
        // Phát 2 giây rồi tua tới từng mốc: độ trễ tới sự kiện "đã tua" và tới lúc vị trí thật sự tiến qua mốc (có tiếng).
        static QList<double> targets;
        for (const QString &t : parser.value(QStringLiteral("targets")).split(QLatin1Char(','), Qt::SkipEmptyParts))
            targets.append(t.toDouble());
        auto *state = new int(0);
        auto *pending = new double(-1);
        auto *latencies = new QJsonArray;
        auto *audible = new QJsonArray;
        auto *seekedAt = new double(-1);
        nextSeek = [&, state] {
            if (*state >= targets.size()) {
                result["seeked_ms"] = *latencies;
                result["audible_ms"] = *audible;
                finish();
                return;
            }
            *pending = targets[*state];
            *seekedAt = -1;
            lap.restart();
            out->seek(*pending);
        };
        QObject::connect(out, &AudioOut::seeked, &app, [&, seekedAt] {
            if (*pending >= 0 && *seekedAt < 0) {
                *seekedAt = lap.elapsed();
                latencies->append(*seekedAt);
            }
        });
        auto *poll = new QTimer(&app);
        poll->setInterval(5);
        QObject::connect(poll, &QTimer::timeout, &app, [&, state, pending, seekedAt, poll] {
            if (*pending < 0)
                return;
            static const bool trace = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE") != 0;
            if (trace && lap.elapsed() % 50 < 5)
                fprintf(stderr, "  t=%lld target=%.1f pos=%.3f playing=%d seekedAt=%.0f\n", (long long)lap.elapsed(), *pending, out->position(), int(out->playing()), *seekedAt);
            if (*seekedAt >= 0 && out->playing() && out->position() > *pending + 0.04) {
                audible->append(double(lap.elapsed()));
                *pending = -1;
                ++*state;
                QTimer::singleShot(600, &app, nextSeek);
            } else if (lap.elapsed() > 5000) {
                audible->append(-1.0);
                *pending = -1;
                ++*state;
                QTimer::singleShot(100, &app, nextSeek);
            }
        });
        poll->start();
        QObject::connect(out, &AudioOut::playingChanged, &app, [&, state](bool playing) {
            if (playing && *state == 0 && *pending < 0) {
                QTimer::singleShot(2000, &app, nextSeek);
            }
        });
        out->setVolume(volume);
        out->load(url, start);
        out->setRate(rate);
        out->play();
    } else if (mode == QLatin1String("gap")) {
        // Cuối chương: từ sự kiện "hết" tới lúc chương kế (nạp lại + phát) thật sự chạy (vị trí > 0,05 s).
        auto *endedAt = new double(-1);
        auto *phase = new int(0);
        QObject::connect(out, &AudioOut::ended, &app, [&, endedAt, phase] {
            if (*phase != 0)
                return;
            *phase = 1;
            *endedAt = 0;
            lap.restart();
            out->load(url2, 0);
            out->play();
        });
        auto *poll = new QTimer(&app);
        poll->setInterval(2);
        QObject::connect(poll, &QTimer::timeout, &app, [&, phase, poll] {
            if (*phase == 1 && out->playing() && out->position() > 0.05) {
                result["gap_ms"] = double(lap.elapsed());
                poll->stop();
                finish();
            } else if (*phase == 1 && lap.elapsed() > 8000) {
                result["gap_ms"] = -1.0;
                poll->stop();
                finish();
            }
        });
        poll->start();
        QTimer::singleShot(40000, &app, [&] {
            if (!result.contains("gap_ms")) {
                result["gap_ms"] = -2.0;
                finish();
            }
        });
        out->setVolume(volume);
        out->load(url, start);
        out->setRate(rate);
        out->play();
    }
    return app.exec();
}
