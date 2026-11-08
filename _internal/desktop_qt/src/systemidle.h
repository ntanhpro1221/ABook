#pragma once
#include <QtGlobal>
#ifdef Q_OS_WIN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

// Unknown OS evidence disables automatic timers; app-window input alone is insufficient.
inline qint64 listenerSystemIdleMs() {
#ifdef Q_OS_WIN
    LASTINPUTINFO input{sizeof(LASTINPUTINFO), 0};
    if (GetLastInputInfo(&input)) return DWORD(GetTickCount() - input.dwTime);
#endif
    return -1;
}

inline bool automaticSleepAllowed(qint64 osIdle, qint64 appIdle, qint64 required) {
    return required > 0 && osIdle >= required && appIdle >= required;
}

namespace AutoSleepText {
inline constexpr auto Schedule = "Tự hẹn theo lịch đêm";
inline constexpr auto Continue = "Chạm để nghe tiếp";
}
