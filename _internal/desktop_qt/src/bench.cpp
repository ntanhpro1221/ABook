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
#include <cstdio>
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
// Nhịp của luồng giao diện (afterAnimating, mỗi khung một lần): khung trễ mà nhịp này đều = luồng render bị chặn; cả hai cùng trễ =
// luồng giao diện bị chặn.
std::vector<double> g_anim;
std::atomic<int> g_animCount{0};
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

#ifdef Q_OS_WIN
namespace {
// Chế độ đo: app chết thì ghi ngăn xếp (module + địa chỉ tương đối) cạnh file đo để biết chết ở đâu (bản Release không có ký hiệu).
LONG WINAPI crashTrace(EXCEPTION_POINTERS *info) {
    const QByteArray path = (outPath() + QStringLiteral(".crash")).toLocal8Bit();
    FILE *file = fopen(path.constData(), "w");
    if (!file)
        return EXCEPTION_CONTINUE_SEARCH;
    fprintf(file, "exception %08lx\n", info->ExceptionRecord->ExceptionCode);
    void *frames[48];
    const USHORT n = CaptureStackBackTrace(0, 48, frames, nullptr);
    for (USHORT i = 0; i < n; ++i) {
        HMODULE module = nullptr;
        char name[MAX_PATH] = "?";
        if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, static_cast<LPCSTR>(frames[i]), &module))
            GetModuleFileNameA(module, name, MAX_PATH);
        fprintf(file, "%2u %s +0x%llx\n", unsigned(i), name, (unsigned long long)(static_cast<char *>(frames[i]) - reinterpret_cast<char *>(module)));
    }
    fclose(file);
    return EXCEPTION_CONTINUE_SEARCH;
}
}  // namespace
#endif

Bench::Bench(QObject *parent) : QObject(parent) {
    g_bench = this;
    if (enabled()) {
        g_frames.resize(kMaxFrames);
        g_anim.resize(kMaxFrames);
#ifdef Q_OS_WIN
        SetUnhandledExceptionFilter(crashTrace);
#endif
    }
}

Bench *Bench::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_bench, QJSEngine::CppOwnership);
    return g_bench;
}

bool Bench::enabled() const {
    return !outPath().isEmpty();
}

QString Bench::scenario() const {
    const QString s = qEnvironmentVariable("ABOOK_BENCH_SCENARIO");
    return s.isEmpty() ? QStringLiteral("library") : s;
}

QString Bench::book() const {
    return qEnvironmentVariable("ABOOK_BENCH_BOOK");
}

void Bench::noteCounters(const QString &tag, QObject *player, QObject *readAlong) {
    if (!enabled() || !player || !readAlong)
        return;
    const auto clock = player->property("clock").value<QObject *>();
    const auto num = [](const QVariant &v) { return QString::number(v.toULongLong()); };
    mark(QStringLiteral("count:%1:%2:%3:%4:%5")
             .arg(tag, clock ? num(clock->property("ticks")) : QStringLiteral("0"), num(player->property("snapshotChanges")),
                  num(readAlong->property("evaluations")), num(readAlong->property("changes"))));
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
    connect(window, &QQuickWindow::afterAnimating, window, [] {
        const int i = g_animCount.fetch_add(1, std::memory_order_relaxed);
        if (i < kMaxFrames)
            g_anim[size_t(i)] = nowMs();
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
    json += "],\"anim\":[";
    const int a = qMin(g_animCount.load(), kMaxFrames);
    for (int i = 0; i < a; ++i) {
        if (i)
            json += ',';
        json += QByteArray::number(g_anim[size_t(i)], 'f', 3);
    }
    json += "]}\n";
    QFile file(outPath());
    if (file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        file.write(json);
        file.close();
    }
    QCoreApplication::quit();
}
