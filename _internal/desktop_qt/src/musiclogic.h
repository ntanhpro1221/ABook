// Phần tính toán thuần của nhạc nền (không Qt Quick, không âm thanh): mốc nhạc của chương, bước âm lượng, vòng lặp mờ chéo. Chép
// đúng ui/src/listen/musicBed.ts (bản web máy tính) - cùng tên hàm, cùng quy tắc; Android: MusicBed.kt. Hằng số đọc từ
// abook/webui/assets/music_mix.json (CMakeLists.txt đưa vào thành ABOOK_MIX_*), một file cho cả ba bên.
#pragma once

#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QString>
#include <QVector>

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>

namespace MusicLogic {

inline constexpr double FADE_SECONDS = double(ABOOK_MIX_FADE_SECONDS);
inline constexpr double SIBLING_FADE_SECONDS = double(ABOOK_MIX_SIBLING_FADE_SECONDS);
inline constexpr double STEP_RAMP_SECONDS = double(ABOOK_MIX_STEP_RAMP_SECONDS);
inline constexpr double LOOP_CROSSFADE_SECONDS = double(ABOOK_MIX_LOOP_CROSSFADE_SECONDS);
/// Chu kỳ ngắn nhất (giây) để điểm vòng của danh mục được dùng (music_mix.loop_bounds).
inline constexpr double LOOP_MIN_PERIOD_SECONDS = double(ABOOK_MIX_LOOP_MIN_PERIOD_SECONDS);
inline constexpr int STEP_MS = 50;
/// Bài tải hỏng (mất mạng): đoạn của nó im lặng, chừng ấy sau mới thử lại.
inline constexpr qint64 RETRY_MS = 5 * 60000;
/// Chương còn chừng này giây thì xin máy chủ tải sẵn bài mốc đầu của chương kế.
inline constexpr double NEXT_CHAPTER_WARM_SECONDS = 120;
inline constexpr qint64 NEXT_CHAPTER_RETRY_MS = 15000;
/// Nhịp đồng bộ với giọng (bản web: `timeupdate` tới 250 ms; ở đây đồng hồ của Player cũng ~4 lần mỗi giây).
inline constexpr double SYNC_TICK_SECONDS = 0.25;
inline constexpr double LOOP_DRIFT_TOLERANCE_SECONDS = 0.005; // §48: 20 ms để lọt ε 20-40 ms
inline constexpr double LOOP_DRIFT_QUIET = 0.1;
inline constexpr double LOOP_STANDBY_SECONDS = 3;
/// Hẹn giờ nhỏ hơn mức này coi như đã tới (nextSyncSeconds), nên crossLoop cũng tính chừng ấy là đã tới giờ tạo phần tử chờ sẵn.
inline constexpr double SYNC_DUE_SECONDS = 0.001;
inline constexpr double LOOP_TIMER_SLACK_SECONDS = 0.05;

inline constexpr double INF = std::numeric_limits<double>::infinity();

struct MusicStep {
    double at = 0;
    double db = 0;
};

struct MusicCue {
    double start = 0;
    double end = 0;
    QString link;
    QString key;
    QString src;
    std::optional<double> gainDb;
    QVector<MusicStep> steps;
    bool sibling = false;
    bool tail = false;
    std::optional<double> audibleStart;
    std::optional<double> audibleEnd;
    std::optional<double> loopStart;
    std::optional<double> loopEnd;
};

struct MusicCredit {
    QString title;
    QString creator;
    QString attribution;
    QString landing;
    QString license;
    QString licenseUrl;
};

/// Lời đáp GET /api/books/<id>/music/chapters/<n>.
struct MusicCues {
    QVector<MusicCue> cues;
    double levelDb = -20;
    QHash<QString, MusicCredit> credits;
    bool pending = false;
    QString unavailable;
};

inline std::optional<double> optionalNumber(const QJsonObject &object, const char *name) {
    const QJsonValue value = object.value(QLatin1String(name));
    if (!value.isDouble() || !std::isfinite(value.toDouble()))
        return std::nullopt;
    return value.toDouble();
}

inline MusicCue cueFromJson(const QJsonObject &o) {
    MusicCue cue;
    cue.start = o.value(QLatin1String("start")).toDouble();
    cue.end = o.value(QLatin1String("end")).toDouble();
    cue.link = o.value(QLatin1String("link")).toString();
    cue.key = o.value(QLatin1String("key")).toString();
    cue.src = o.value(QLatin1String("src")).toString();
    cue.gainDb = optionalNumber(o, "gainDb");
    for (const QJsonValue &step : o.value(QLatin1String("steps")).toArray())
        cue.steps.append({step.toObject().value(QLatin1String("at")).toDouble(), step.toObject().value(QLatin1String("db")).toDouble()});
    cue.sibling = o.value(QLatin1String("sibling")).toBool();
    cue.tail = o.value(QLatin1String("tail")).toBool();
    cue.audibleStart = optionalNumber(o, "audibleStart");
    cue.audibleEnd = optionalNumber(o, "audibleEnd");
    cue.loopStart = optionalNumber(o, "loopStart");
    cue.loopEnd = optionalNumber(o, "loopEnd");
    return cue;
}

inline MusicCredit creditFromJson(const QJsonObject &o) {
    return {o.value(QLatin1String("title")).toString(), o.value(QLatin1String("creator")).toString(),
            o.value(QLatin1String("attribution")).toString(), o.value(QLatin1String("landing")).toString(),
            o.value(QLatin1String("license")).toString(), o.value(QLatin1String("licenseUrl")).toString()};
}

inline MusicCues cuesFromJson(const QJsonObject &o) {
    MusicCues result;
    for (const QJsonValue &cue : o.value(QLatin1String("cues")).toArray())
        result.cues.append(cueFromJson(cue.toObject()));
    result.levelDb = o.value(QLatin1String("levelDb")).toDouble(-20);
    const QJsonObject credits = o.value(QLatin1String("credits")).toObject();
    for (auto it = credits.begin(); it != credits.end(); ++it)
        result.credits.insert(it.key(), creditFromJson(it.value().toObject()));
    result.pending = o.value(QLatin1String("pending")).toBool();
    result.unavailable = o.value(QLatin1String("unavailable")).toString();
    return result;
}

inline const MusicCue *cueAt(const QVector<MusicCue> &cues, double seconds) {
    for (const MusicCue &cue : cues)
        if (seconds >= cue.start && seconds < cue.end)
            return &cue;
    return nullptr;
}

/// Mức bước (dB) của mốc tại giây `seconds` của chương: bước cuối cùng đã tới, chưa tới bước nào thì 0.
inline double stepDbAt(const MusicCue &cue, double seconds) {
    double db = 0;
    for (const MusicStep &step : cue.steps) {
        if (seconds < step.at)
            break;
        db = step.db;
    }
    return db;
}

/// Vòng lặp của một bài (webui/music_mix.py `loop_bounds`).
struct LoopBounds {
    double start = 0;
    double end = INF;
    double period = INF;
    bool crossfade = false;
    double loopStart = 0;
    double loopEnd = INF;
};

/// Vòng lặp của bài của mốc `cue`, độ dài thật `duration` (chưa biết: NaN hay <= 0).
inline LoopBounds loopBounds(const MusicCue &cue, double duration) {
    const std::optional<double> total = std::isfinite(duration) && duration > 0 ? std::optional<double>(duration) : std::nullopt;
    const double start = std::max(0.0, cue.audibleStart.value_or(0));
    std::optional<double> end = cue.audibleEnd && *cue.audibleEnd > 0 ? cue.audibleEnd : total;
    if (!end)
        return {0, INF, INF, false, 0, INF};
    if (total)
        end = std::min(*end, *total);
    if (*end - start < 3 * LOOP_CROSSFADE_SECONDS) {
        const double whole = total.value_or(*end);
        return {0, whole, whole, false, 0, whole};
    }
    const std::optional<double> restart = cue.loopStart;
    const std::optional<double> rawOut = cue.loopEnd;
    const std::optional<double> out = !rawOut || !total || *rawOut - LOOP_CROSSFADE_SECONDS > *end ? rawOut : std::optional<double>(std::min(*rawOut, *total));
    if (restart && out && start <= *restart && *restart < *out - LOOP_CROSSFADE_SECONDS && *out - LOOP_CROSSFADE_SECONDS <= *end
        && *out - *restart - LOOP_CROSSFADE_SECONDS >= LOOP_MIN_PERIOD_SECONDS)
        return {start, *end, *out - *restart - LOOP_CROSSFADE_SECONDS, true, *restart, *out};
    return {start, *end, *end - start - LOOP_CROSSFADE_SECONDS, true, start, *end};
}

/// Chỗ trong bài sau `t` >= 0 giây kể từ lúc bài vào từ A (music_mix.loop_position).
inline double loopPosition(const LoopBounds &b, double t) {
    if (!std::isfinite(b.period))
        return b.start + t;
    if (b.crossfade && t < b.loopEnd - LOOP_CROSSFADE_SECONDS - b.start)
        return b.start + t;
    return b.loopStart + std::fmod(t - (b.loopStart - b.start), b.period);
}

struct LoopSchedule {
    QVector<double> opens;
    double end = 0;
};

/// Lúc mở các phần tử lặp và lúc nhạc hết của một mốc dài `length` giây (music_mix.loop_schedule).
inline LoopSchedule loopSchedule(const LoopBounds &b, double length, bool tail = false) {
    double natural = b.end - b.start;
    const double lead = b.end - b.loopEnd + LOOP_CROSSFADE_SECONDS;
    LoopSchedule result;
    if (tail) {
        while (std::isfinite(natural) && length - natural >= b.period / 2) {
            if (b.crossfade)
                result.opens.append(natural - lead);
            natural += b.period;
        }
        result.end = natural;
        return result;
    }
    while (b.crossfade && natural - lead < length) {
        result.opens.append(natural - lead);
        natural += b.period;
    }
    result.end = length;
    return result;
}

/// Chỗ trong bài ứng với giây `seconds` của chương - vào giữa chương hay tua thì nhạc cũng ở giữa bài.
inline double alignedPosition(const MusicCue &cue, double seconds, const LoopBounds &b) {
    return loopPosition(b, std::max(0.0, seconds - cue.start));
}

/// Bài đang kêu ở `currentTime` đã tới loopEnd - X: lúc mở phần tử lặp mới từ loopStart.
inline bool loopDue(const LoopBounds &b, double currentTime) {
    return b.crossfade && currentTime >= b.loopEnd - LOOP_CROSSFADE_SECONDS;
}

/// Phần còn lại (giây) tới lúc phải mở bản lặp nếu nhỏ hơn 1,5 nhịp đồng bộ; 0 khi đã quá hạn; nullopt khi chưa cần hẹn.
inline std::optional<double> loopHandoffDelay(const LoopBounds &b, double oldPos, double tickSeconds) {
    if (!b.crossfade)
        return std::nullopt;
    const double rem = b.loopEnd - LOOP_CROSSFADE_SECONDS - oldPos;
    if (rem <= 0)
        return 0.0;
    return rem < 1.5 * tickSeconds ? std::optional<double>(rem) : std::nullopt;
}

/// Chỗ bản lặp mới phải vào khi bài cũ đang ở `oldPos` (bù độ trễ của lần đồng bộ).
inline double loopStartAt(const LoopBounds &b, double oldPos) {
    return b.loopStart + std::max(0.0, oldPos - (b.loopEnd - LOOP_CROSSFADE_SECONDS));
}

/// Bản mới đi chậm bao nhiêu giây so với bản cũ (dương = chậm).
inline double loopDrift(const LoopBounds &b, double oldPos, double newPos) {
    return (oldPos - (b.loopEnd - LOOP_CROSSFADE_SECONDS)) - (newPos - b.loopStart);
}

/// Mốc `tail` đang ở vòng cuối: thôi lặp, bài chơi tới E là hết.
inline bool finalLoop(const MusicCue &cue, double seconds, double currentTime, const LoopBounds &b) {
    return cue.tail && std::isfinite(b.end) && cue.end - seconds - (b.end - currentTime) < b.period / 2;
}

/// Bài đã hết: chơi tới E hay `ended`.
inline bool finished(const LoopBounds &b, double currentTime, bool ended) {
    return ended || currentTime >= b.end;
}

/// Nối bài anh em: bài cũ mờ ra trong SIBLING_FADE_SECONDS, hay trong phần còn lại thật của nó nếu ngắn hơn.
inline double siblingFadeSeconds(const LoopBounds &b, double currentTime) {
    return std::max(STEP_MS / 1000.0, std::min(SIBLING_FADE_SECONDS, b.end - currentTime));
}

/// Bài nằm sẵn trong sách (gói .abook): không có gì để xin máy chủ tải sẵn.
inline bool carriedByBook(const MusicCue &cue) {
    return cue.src.contains(QLatin1String("/music/files/"));
}

} // namespace MusicLogic
