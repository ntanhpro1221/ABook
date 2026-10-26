#include "bench.h"

#include <QJSEngine>
#include <QCoreApplication>
#include <QDateTime>
#include <QFile>
#include <QMutex>
#include <QMutexLocker>
#include <QQuickWindow>
#include <QVector>

#include <atomic>
#include <chrono>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

namespace {
using Clock = std::chrono::steady_clock;

double nowMs() {
    return std::chrono::duration<double, std::milli>(Clock::now().time_since_epoch()).count();
}

QString outPath() {
    static const QString path = qEnvironmentVariable("ABOOK_BENCH");
    return path;
}

QMutex g_lock;
QVector<QPair<double, QString>> g_events;
// Khung ghi từ luồng render: mảng dựng sẵn + chỉ số nguyên tử, không khoá, không cấp phát trong lúc đo.
constexpr int kMaxFrames = 200000;
std::vector<double> g_frames;
std::atomic<int> g_frameCount{0};
Bench *g_bench = nullptr;

// Mốc epoch của tiến trình (GetProcessTimes) - để script đo tính "từ lúc tạo tiến trình tới khung đầu".
double processStartEpochMs() {
#ifdef Q_OS_WIN
    FILETIME create, exit, kernel, user;
    if (GetProcessTimes(GetCurrentProcess(), &create, &exit, &kernel, &user)) {
        const quint64 ticks = (quint64(create.dwHighDateTime) << 32) | create.dwLowDateTime;  // 100 ns từ 1601
        return double(ticks) / 10000.0 - 11644473600000.0;
    }
#endif
    return 0;
}
}  // namespace

Bench::Bench(QObject *parent) : QObject(parent) {
    g_bench = this;
    if (enabled())
        g_frames.resize(kMaxFrames);
}

Bench *Bench::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_bench, QJSEngine::CppOwnership);
    return g_bench;
}

bool Bench::enabled() const {
    return !outPath().isEmpty();
}

void Bench::mark(const QString &name) {
    if (outPath().isEmpty())
        return;
    QMutexLocker lock(&g_lock);
    g_events.append({nowMs(), name});
}

void Bench::noteOnce(const QString &name) {
    if (outPath().isEmpty())
        return;
    {
        QMutexLocker lock(&g_lock);
        for (const auto &e : std::as_const(g_events))
            if (e.second == name)
                return;
    }
    mark(name);
}

void Bench::attach(QQuickWindow *window) {
    if (!enabled() || !window)
        return;
    // frameSwapped phát ở luồng render; nối trực tiếp, chỉ ghi một số vào mảng dựng sẵn.
    connect(window, &QQuickWindow::frameSwapped, window, [] {
        const int i = g_frameCount.fetch_add(1, std::memory_order_relaxed);
        if (i < kMaxFrames)
            g_frames[size_t(i)] = nowMs();
        if (i == 0)
            mark(QStringLiteral("first_frame"));
    }, Qt::DirectConnection);
}

void Bench::finish() {
    if (!enabled())
        return;
    QByteArray json;
    json.reserve(1 << 20);
    const double epochOffset = double(QDateTime::currentMSecsSinceEpoch()) - nowMs();
    json += "{\"process_start_epoch_ms\":" + QByteArray::number(processStartEpochMs(), 'f', 1);
    json += ",\"epoch_offset_ms\":" + QByteArray::number(epochOffset, 'f', 1);
    json += ",\"events\":[";
    {
        QMutexLocker lock(&g_lock);
        for (int i = 0; i < g_events.size(); ++i) {
            if (i)
                json += ',';
            json += "[" + QByteArray::number(g_events[i].first, 'f', 3) + ",\"" + g_events[i].second.toUtf8() + "\"]";
        }
    }
    json += "],\"frames\":[";
    const int n = qMin(g_frameCount.load(), kMaxFrames);
    for (int i = 0; i < n; ++i) {
        if (i)
            json += ',';
        json += QByteArray::number(g_frames[size_t(i)], 'f', 3);
    }
    json += "]}\n";
    QFile file(outPath());
    if (file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        file.write(json);
        file.close();
    }
    QCoreApplication::quit();
}
