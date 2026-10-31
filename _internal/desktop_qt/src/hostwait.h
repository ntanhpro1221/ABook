// One wait policy for every HTTP call from the app to its host: C++ (HostNet) and QML (DesktopApi) both send through HostCall.
// A call fails when NO BYTE arrives for idleMs(path), never after a total time, so a long answer that keeps arriving is not cut.
#pragma once

#include <QString>

namespace HostWait {
inline constexpr int kIdleMs = 30'000;
// Speech (narration clip, voice try): the host answers only after the whole text is read, so no byte arrives meanwhile.
// Its Edge deadline is TOTAL_TIMEOUT 90 s + 1 s (abook/readaloud/edge.py), so its own error, with the reason the player
// shows, always arrives first; a shorter limit (40 s) would cut a slow but healthy long paragraph.
inline constexpr int kSpeechIdleMs = 100'000;
// A host silent past the limit gets the same request once more (the abort frees it, abook/webui/server.py _peer_gone).
inline constexpr int kAttempts = 2;
// The player's last guard: buffering this long means every request above has already had its chance to report.
inline constexpr int kStallMs = kAttempts * kSpeechIdleMs + 15'000;

inline bool speech(const QString &path) {
    const qsizetype query = path.indexOf(QLatin1Char('?'));
    const QStringView route = QStringView(path).left(query < 0 ? path.size() : query);
    return route == u"/api/readaloud/clip" || (route.startsWith(u"/api/books/") && route.endsWith(u"/voice/preview"));
}
inline int idleMs(const QString &path) { return speech(path) ? kSpeechIdleMs : kIdleMs; }
}
