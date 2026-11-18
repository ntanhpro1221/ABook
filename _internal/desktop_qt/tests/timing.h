#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QDebug>
#include <QtCore/qtenvironmentvariables.h>
#include <algorithm>
#include <cmath>

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
} // namespace TestTiming
