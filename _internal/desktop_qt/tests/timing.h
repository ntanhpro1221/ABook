#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QDebug>
#include <QtCore/qtenvironmentvariables.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#ifdef Q_OS_WIN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

// Match tests/timing.py: upper bounds only, ABOOK_TEST_TIME_SCALE, default 5, minimum 1.
namespace TestTiming {
inline double scale() {
    static const double value = [] {
        bool ok = false;
        const auto raw = qgetenv("ABOOK_TEST_TIME_SCALE");
        if (!qEnvironmentVariableIsSet("ABOOK_TEST_TIME_SCALE")) return 5.0;
        const double parsed = raw.toDouble(&ok);
        if (!ok || !std::isfinite(parsed)) qFatal("ABOOK_TEST_TIME_SCALE must be a finite number");
        return std::max(1.0, parsed);
    }();
    return value;
}
inline double upper(double limitMs, double blockedMs = 0) {
    const double bound = limitMs * scale();
    return std::max(limitMs, blockedMs > 0 ? std::min(bound, 0.8 * blockedMs) : bound);
}
inline int ms(int limitMs) { return int(std::ceil(upper(limitMs))); }
inline bool within(double tookMs, double limitMs, double blockedMs = 0) {
    const double bound = upper(limitMs, blockedMs);
    qInfo("test_timing: took_ms=%.3f limit_ms=%.3f scale=%.2f bound_ms=%.3f", tookMs, limitMs, scale(), bound);
    return tookMs < bound;
}
// A fake device stamps the instant the engine acted on it (reset, write). A bound on that instant measures the engine;
// timing the test's own QTRY loop would add its 50 ms poll step and any wait for the test thread's turn.
struct Mark {
    std::atomic<long long> ns{0};
    void stamp() { ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
    double msAfter(std::chrono::steady_clock::time_point from) const {
        return double(ns.load() - std::chrono::duration_cast<std::chrono::nanoseconds>(from.time_since_epoch()).count()) / 1e6;
    }
};
// The release gate starts every test process BELOW_NORMAL so it never competes with the owner's work; under all-core
// load such a thread waits for Windows' anti-starvation boost (~1 s). A suite whose test thread measures real time
// (elapsed bounds, a device clock, a paced local server) calls this in initTestCase: the observer then runs at the
// priority the app's own thread has (normal), so a bound measures the code under test, not the observer's turn.
inline void promptObserver() {
#ifdef Q_OS_WIN
    if (GetPriorityClass(GetCurrentProcess()) == BELOW_NORMAL_PRIORITY_CLASS)
        SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
#endif
}
} // namespace TestTiming
