#include "feedback.h"

#include "audioout.h"

#include <QFile>
#include <QUrl>
#include <QtEndian>

#include <algorithm>
#include <cmath>

namespace {
Feedback *g_instance = nullptr;

constexpr double C6 = 1046.5;
constexpr double E6 = 1318.5;
constexpr double G6 = 1568;
constexpr double A3 = 220;
constexpr double kPi = 3.14159265358979323846;
// Âm sắc "đồng thau gõ nhẹ": cơ bản + vài hoạ âm giảm dần (bậc 2-3 đậm như kèn đồng, bậc cao rất nhẹ cho khỏi chói) - phần ảo của PeriodicWave.
constexpr double kHarmonics[] = {0, 1, 0.55, 0.35, 0.18, 0.08};

double wave(double phase) {
    double sum = 0;
    for (int k = 1; k < int(std::size(kHarmonics)); ++k)
        sum += kHarmonics[k] * std::sin(k * phase);
    return sum;
}

/// Web Audio chuẩn hoá sóng tuần hoàn cho đỉnh = 1.
double wavePeak() {
    double peak = 0;
    for (int i = 0; i < 4096; ++i)
        peak = std::max(peak, std::abs(wave(2 * kPi * i / 4096)));
    return peak;
}

/// exponentialRampToValueAtTime: từ `from` ở t0 tới `to` ở t1.
double ramp(double from, double to, double t, double t0, double t1) {
    return from * std::pow(to / from, std::clamp((t - t0) / (t1 - t0), 0.0, 1.0));
}

void putLe16(QByteArray &out, quint16 value) {
    char bytes[2];
    qToLittleEndian(value, bytes);
    out.append(bytes, 2);
}
void putLe32(QByteArray &out, quint32 value) {
    char bytes[4];
    qToLittleEndian(value, bytes);
    out.append(bytes, 4);
}
} // namespace

Feedback::Feedback(std::function<AudioOut *()> make, QObject *parent) : QObject(parent), m_make(std::move(make)) {}

Feedback::~Feedback() {
    delete m_out;
    if (g_instance == this)
        g_instance = nullptr;
}

Feedback *Feedback::instance() { return g_instance; }

void Feedback::setInstance(Feedback *feedback) { g_instance = feedback; }

Feedback *Feedback::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_instance, QJSEngine::CppOwnership);
    return g_instance;
}

void Feedback::setSounds(bool sounds) {
    if (sounds == m_sounds)
        return;
    m_sounds = sounds;
    emit soundsChanged();
}

QVector<Feedback::Note> Feedback::notes(const QString &kind) {
    if (kind == QLatin1String("toggle"))
        return {{G6, 0, 0.06, -30}};
    if (kind == QLatin1String("tick"))
        return {{E6, 0, 0.04, -32}};
    if (kind == QLatin1String("confirm"))
        return {{C6, 0, 0.12, -24}, {E6, 0.09, 0.16, -24}};
    if (kind == QLatin1String("done"))
        return {{C6, 0, 0.1, -24}, {E6, 0.08, 0.1, -24}, {G6, 0.16, 0.09, -24}};
    if (kind == QLatin1String("sleepWarn"))
        return {{A3, 0, 0.25, -22}};
    return {}; // tap, playPause, reject, longPress: không tiếng
}

QByteArray Feedback::wav(const QVector<Note> &notes, int sampleRate) {
    constexpr double lead = 0.005;
    double end = 0;
    for (const Note &note : notes)
        end = std::max(end, note.at + note.length + 0.02);
    const int count = int(std::ceil((lead + end) * sampleRate));
    const double peakWave = wavePeak();
    QVector<double> mix(count, 0.0);
    for (const Note &note : notes) {
        const double peak = std::pow(10.0, note.level / 20.0);
        const double start = lead + note.at;
        const int first = int(start * sampleRate);
        const int last = std::min(count, int(std::ceil((start + note.length + 0.02) * sampleRate)));
        for (int i = first; i < last; ++i) {
            const double t = double(i) / sampleRate;
            const double local = t - start;
            // Gõ: lên trong 4 ms, tắt theo hàm mũ - không đuôi kéo dài, không nảy.
            const double gain = local < 0.004 ? ramp(0.0001, peak, local, 0, 0.004) : ramp(peak, 0.0001, local, 0.004, note.length);
            mix[i] += gain * wave(2 * kPi * note.pitch * local) / peakWave;
        }
    }
    QByteArray data;
    data.reserve(count * 2);
    for (double sample : mix)
        putLe16(data, quint16(qint16(std::lround(std::clamp(sample, -1.0, 1.0) * 32767))));
    QByteArray out;
    out.append("RIFF");
    putLe32(out, quint32(36 + data.size()));
    out.append("WAVEfmt ");
    putLe32(out, 16);
    putLe16(out, 1); // PCM
    putLe16(out, 1); // một kênh
    putLe32(out, quint32(sampleRate));
    putLe32(out, quint32(sampleRate * 2));
    putLe16(out, 2);
    putLe16(out, 16);
    out.append("data");
    putLe32(out, quint32(data.size()));
    out.append(data);
    return out;
}

void Feedback::play(const QString &kind) {
    const QVector<Note> chosen = notes(kind);
    if (chosen.isEmpty() || !m_sounds || (m_bookPlaying && kind != QLatin1String("sleepWarn")))
        return;
    QString path = m_files.value(kind);
    if (path.isEmpty()) {
        if (!m_dir.isValid())
            return;
        path = m_dir.filePath(kind + QStringLiteral(".wav"));
        QFile file(path);
        if (!file.open(QIODevice::WriteOnly) || file.write(wav(chosen)) < 0)
            return; // không ghi được thư mục tạm: im, giao diện vẫn chạy
        m_files.insert(kind, path);
    }
    if (!m_out) {
        m_out = m_make();
        if (!m_out)
            return;
    }
    m_out->setVolume(1.0); // mức đã nằm trong mẫu (-22 ... -32 dB)
    m_out->load(QUrl::fromLocalFile(path), 0);
    m_out->play();
    ++m_played;
    m_lastKind = kind;
    emit playedChanged();
}
