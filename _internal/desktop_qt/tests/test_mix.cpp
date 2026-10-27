// Lõi trộn của đường âm thanh WASAPI (mixcore.h, mp3source.h): vòng đệm, âm lượng trượt, đổi tần số, giải mã mp3 - thử trên số và
// trên fixture mp3 chung, không cần thiết bị âm thanh.
#include "mixcore.h"
#include "mp3source.h"

#include <QFile>
#include <QtTest>

#include <cmath>
#include <random>
#include <vector>

using namespace MixCore;

namespace {

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
