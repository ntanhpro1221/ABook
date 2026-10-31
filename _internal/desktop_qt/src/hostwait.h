// One wait policy for every HTTP call from the app to its host: C++ (HostNet) and QML (DesktopApi) both send through HostCall.
// A call fails when NO BYTE arrives for idleMs(path), never after a total time, so a long answer that keeps arriving is not cut.
#pragma once

#include <array>
#include <QList>
#include <QString>
#include <QStringView>

namespace HostWait {
inline constexpr int kIdleMs = 30'000;
// Long work: the host answers only after the whole job is done, so no byte arrives meanwhile - speech (its Edge deadline is
// TOTAL_TIMEOUT 90 s + 1 s, abook/readaloud/edge.py, so its own error with the reason always arrives first), scanning or
// splitting a source, first-person narration, making a book, a pronunciation try, and every call that rebuilds the music
// track while it answers (rebuild, change, first look, edits folded in from a file or sent back by a phone).
inline constexpr int kLongIdleMs = 100'000;
// A host silent past the limit gets the same request once more (the abort frees it, abook/webui/server.py _peer_gone).
inline constexpr int kAttempts = 2;
// The player's last guard: buffering this long means every request above has already had its chance to report.
inline constexpr int kStallMs = kAttempts * kLongIdleMs + 15'000;

// The long-work routes, word for word and in the same order as the web list in ui/src/shared/hostWait.ts and the phone
// list in net/HostWait.kt - tests/test_host_wait_parity.py compares them. `*` is exactly one path segment.
inline constexpr std::array<QStringView, 11> kLongWork = {
    u"/api/readaloud/clip",
    u"/api/books/*/voice/preview",
    u"/api/books/*/pronunciation/preview",
    u"/api/books/*/music/rebuild",
    u"/api/books/*/music",
    u"/api/books/*/edits/fold",
    u"/api/scan",
    u"/api/sources/split",
    u"/api/first-person",
    u"/api/books",
    u"/sync/v1/books/*/edits",
};

// The path (without its ?query) matches one entry of kLongWork, segment by segment.
inline bool longWork(const QString &path) {
    const qsizetype query = path.indexOf(QLatin1Char('?'));
    const QList<QStringView> parts = QStringView(path).left(query < 0 ? path.size() : query).split(u'/');
    for (const QStringView pattern : kLongWork) {
        const QList<QStringView> want = pattern.split(u'/');
        if (want.size() != parts.size())
            continue;
        bool same = true;
        for (qsizetype at = 0; same && at < want.size(); ++at)
            same = want[at] == u"*" || want[at] == parts[at];
        if (same)
            return true;
    }
    return false;
}
inline int idleMs(const QString &path) { return longWork(path) ? kLongIdleMs : kIdleMs; }
}
