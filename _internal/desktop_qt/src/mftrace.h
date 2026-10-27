#pragma once

#include <QtGlobal>
#include <chrono>
#include <cstdio>

// Steady-clock milliseconds, shared by callbacks and UI state lines; no wall-clock jumps.
inline long long mfTraceMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

inline bool mfTraceEnabled() {
    static const bool enabled = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE") != 0;
    return enabled;
}

inline void mfTraceState(const void *out, const char *state, double position = -1) {
    if (mfTraceEnabled())
        std::fprintf(stderr, "mf t_ms=%lld out=%p state=%s pos=%.3f\n", mfTraceMs(), out, state, position);
}
