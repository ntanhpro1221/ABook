// Luật thuần của bộ phát, chuyển từ ui/src/listen/model.ts + sleep.ts + player.tsx sang C++ (không đụng Qt Quick, thử được riêng).
// Mọi hằng số và công thức giữ ĐÚNG số của bản web: hai app phải nghe tiếp cùng một chỗ.
#pragma once

#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QList>
#include <QString>
#include <QVector>

#include <cmath>
#include <optional>

namespace PlayerLogic {

inline constexpr double kSkipSeconds = 15;
inline constexpr double kJumpSeconds = 30;      // nhảy xa hơn thế thì mời "quay lại"
inline constexpr int kHistory = 5;
inline constexpr qint64 kSaveEveryMs = 10'000;
inline constexpr double kNearEndSeconds = 15;   // model.ts NEAR_END_SECONDS
inline constexpr double kRestartAfterSeconds = 5; // Trước: quá 5 giây thì về đầu chương, không thì sang chương trước
inline constexpr double kDefaultRate = 1.0;
inline constexpr int kDefaultFadeSeconds = 30;
inline constexpr int kDefaultExtendMinutes = 10;
inline constexpr qint64 kRewindShortMs = 30'000;
inline constexpr qint64 kRewindLongMs = 10 * 60'000;
inline constexpr double kFadeFloorDb = -40;

inline const QList<double> &speeds() {
    static const QList<double> list = {0.75, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.75, 2.0, 2.5, 3.0};
    return list;
}
inline const QList<int> &sleepChoices() {
    static const QList<int> list = {5, 10, 15, 30, 45, 60};
    return list;
}

struct Chapter {
    int id = 0;
    int index = 0;
    QString title;
    QString subtitle;
    QString fullTitle;
    double duration = 0;
    bool available = false;
    bool textOnly = false; // state == "text": chỉ có chữ (đọc to là D1b)
};

inline bool canPlay(const Chapter &chapter) {
    return chapter.available; // chương chỉ-chữ có giọng đọc là D1b
}

struct ChapterState {
    double heard = 0;
    bool done = false;
    double duration = 0;
};

struct Book {
    QString id;
    QString title;
    QString author;
    QString narrator;
    bool complete = true;
    QString coverKey; // khoá ảnh bìa của CoverProvider ("mã/phiên bản"), cùng khoá với Thư viện
    QString record;   // hồ sơ nghe đang dùng ("" nếu không có)
    QVector<Chapter> chapters;
    // state
    std::optional<double> rate;
    bool hasLast = false;
    int lastChapter = 0;
    double lastSeconds = 0;
    double lastAt = 0; // giây Unix
    QHash<int, ChapterState> states;
    bool finished = false;
    bool producing = false;
};

/// Khoá ảnh bìa cho CoverProvider; rỗng khi sách chưa có bìa thật (vẽ bìa từ tên). MỘT công thức cho Thư viện và bộ phát.
inline QString coverKeyOf(const QString &id, const QJsonObject &cover) {
    if (cover.isEmpty())
        return {};
    return id + QLatin1Char('/') + QString::number(cover.value(QStringLiteral("version")).toInt());
}

/// Trạng thái nghe (GET book.state hay lời đáp của POST progress): tốc độ riêng, chỗ nghe cuối, dấu từng chương.
inline void applyState(Book &book, const QJsonObject &state) {
    if (state.contains(QStringLiteral("rate")) && state.value(QStringLiteral("rate")).isDouble())
        book.rate = state.value(QStringLiteral("rate")).toDouble();
    const QJsonObject last = state.value(QStringLiteral("last")).toObject();
    if (!last.isEmpty()) {
        book.hasLast = true;
        book.lastChapter = last.value(QStringLiteral("chapterId")).toInt();
        book.lastSeconds = last.value(QStringLiteral("seconds")).toDouble();
        book.lastAt = last.value(QStringLiteral("at")).toDouble();
    }
    const QJsonObject chapters = state.value(QStringLiteral("chapters")).toObject();
    for (auto it = chapters.begin(); it != chapters.end(); ++it) {
        const QJsonObject item = it.value().toObject();
        ChapterState entry;
        entry.heard = item.value(QStringLiteral("heard")).toDouble();
        entry.done = item.value(QStringLiteral("done")).toBool();
        entry.duration = item.value(QStringLiteral("duration")).toDouble();
        book.states.insert(it.key().toInt(), entry);
    }
}

inline Book parseBook(const QJsonObject &json) {
    Book book;
    book.id = json.value(QStringLiteral("id")).toString();
    book.title = json.value(QStringLiteral("title")).toString();
    book.author = json.value(QStringLiteral("author")).toString();
    book.narrator = json.value(QStringLiteral("narrator")).toString();
    book.complete = json.value(QStringLiteral("stage")).toString() == QLatin1String("text") || json.value(QStringLiteral("complete")).toBool(true);
    book.producing = json.value(QStringLiteral("producing")).toBool();
    book.coverKey = coverKeyOf(book.id, json.value(QStringLiteral("cover")).toObject());
    for (const QJsonValue &value : json.value(QStringLiteral("records")).toArray()) {
        const QJsonObject record = value.toObject();
        if (record.value(QStringLiteral("active")).toBool()) {
            book.record = record.value(QStringLiteral("id")).toString();
            break;
        }
    }
    for (const QJsonValue &value : json.value(QStringLiteral("chapters")).toArray()) {
        const QJsonObject item = value.toObject();
        Chapter chapter;
        chapter.id = item.value(QStringLiteral("id")).toInt();
        chapter.index = item.value(QStringLiteral("index")).toInt();
        chapter.title = item.value(QStringLiteral("title")).toString();
        chapter.subtitle = item.value(QStringLiteral("subtitle")).toString();
        chapter.fullTitle = item.value(QStringLiteral("fullTitle")).toString();
        chapter.duration = item.value(QStringLiteral("duration")).toDouble();
        chapter.available = item.value(QStringLiteral("available")).toBool();
        chapter.textOnly = item.value(QStringLiteral("state")).toString() == QLatin1String("text");
        book.chapters.append(chapter);
    }
    applyState(book, json.value(QStringLiteral("state")).toObject());
    book.finished = json.value(QStringLiteral("progress")).toObject().value(QStringLiteral("finished")).toBool();
    return book;
}

/// Độ dài chương: của gói sách, hay - chưa biết - độ dài trình phát đã ghi lúc nghe.
inline double knownDuration(const Book &book, const Chapter &chapter) {
    if (chapter.duration > 0)
        return chapter.duration;
    return book.states.value(chapter.id).duration;
}

/// Giây nghe tiếp trong một chương khi vào nó không qua chỗ nghe cuối (model.ts chapterResumeAt).
inline double chapterResumeAt(const Book &book, const Chapter &chapter) {
    if (!book.states.contains(chapter.id))
        return 0;
    const ChapterState state = book.states.value(chapter.id);
    if (state.done || !(state.heard > 0))
        return 0;
    const double length = knownDuration(book, chapter);
    return length > 0 && length - state.heard < kNearEndSeconds ? 0 : state.heard;
}

struct ResumePoint {
    int chapterId = 0;
    double at = 0;
};

/// Chương + giây nên phát khi bấm "Nghe" (model.ts resumePoint): chỗ nghe dở nếu chương ấy còn nghe được (gần hết thì sang chương kế), không thì
/// chương đầu chưa xong, cuối cùng chương đầu.
inline std::optional<ResumePoint> resumePoint(const Book &book) {
    QVector<const Chapter *> playable;
    for (const Chapter &chapter : book.chapters)
        if (canPlay(chapter))
            playable.append(&chapter);
    if (playable.isEmpty())
        return std::nullopt;
    if (book.hasLast) {
        for (int i = 0; i < playable.size(); ++i) {
            if (playable[i]->id != book.lastChapter)
                continue;
            const double length = knownDuration(book, *playable[i]);
            const bool nearEnd = length > 0 && length - book.lastSeconds < kNearEndSeconds;
            if (!nearEnd)
                return ResumePoint{playable[i]->id, book.lastSeconds};
            if (i + 1 < playable.size())
                return ResumePoint{playable[i + 1]->id, chapterResumeAt(book, *playable[i + 1])};
            if (!book.complete)
                return ResumePoint{playable[i]->id, book.lastSeconds};
            break;
        }
    }
    for (const Chapter *chapter : playable)
        if (!book.states.value(chapter->id).done)
            return ResumePoint{chapter->id, chapterResumeAt(book, *chapter)};
    return ResumePoint{playable.first()->id, 0};
}

/// Chương nghe được kế tiếp (step +1) / liền trước (-1), hay -1.
inline int availableAfter(const QVector<Chapter> &queue, int chapterId, int step) {
    int index = -1;
    for (int i = 0; i < queue.size(); ++i)
        if (queue[i].id == chapterId)
            index = i;
    if (index < 0 && step < 0)
        return -1;
    for (int cursor = index + step; cursor >= 0 && cursor < queue.size(); cursor += step)
        if (canPlay(queue[cursor]))
            return queue[cursor].id;
    return -1;
}

/// Tốc độ khi nạp một cuốn: riêng của nó, không thì mặc định.
inline double startingRate(const std::optional<double> &own) {
    return own.has_value() && *own > 0 ? *own : kDefaultRate;
}

/// Tự lùi khi nghe lại (giây) theo độ dài lần dừng: dưới nửa phút thì thôi; tới 10 phút lùi 5 giây; lâu hơn lùi 10 giây (sleep.ts rewindAfter).
inline int rewindAfter(qint64 pausedMs) {
    if (pausedMs < kRewindShortMs)
        return 0;
    return pausedMs <= kRewindLongMs ? 5 : 10;
}

/// Hệ số âm lượng khi còn `leftMs` trong đoạn nhỏ dần dài `fadeMs`: tuyến tính theo dB từ 0 xuống -40 dB (sleep.ts fadeGain).
inline double fadeGain(double leftMs, double fadeMs) {
    if (fadeMs <= 0 || leftMs >= fadeMs)
        return 1;
    const double progress = 1 - std::max(0.0, leftMs) / fadeMs;
    return std::pow(10.0, (kFadeFloorDb * progress) / 20.0);
}

/// Tốc độ gần nhất trong bảng (phím [ ]).
inline double nearestSpeed(double rate, int step) {
    const QList<double> &list = speeds();
    if (step > 0) {
        for (double speed : list)
            if (speed > rate + 1e-6)
                return speed;
        return list.last();
    }
    for (int i = list.size() - 1; i >= 0; --i)
        if (list[i] < rate - 1e-6)
            return list[i];
    return list.first();
}

/// Lệch (giây) từ đó chỗ nghe của thiết bị khác mới là "chỗ khác" - ít hơn là cùng chỗ (lưu chậm vài giây).
inline constexpr double kElsewhereSeconds = 30;

/// Chỗ nghe máy chủ đang giữ được ghi SAU lần cuối máy này nạp hay lưu (`stampMs`) - tức của thiết bị khác - và xa chỗ máy này đang đứng:
/// nghe tiếp ở đây phải đi tới chỗ ấy, đừng phát chỗ cũ rồi lưu đè chỗ mới hơn (model.ts newerElsewhere).
inline std::optional<ResumePoint> newerElsewhere(const Book &book, qint64 stampMs, int hereChapter, double hereSeconds) {
    if (!book.hasLast || !(book.lastAt * 1000 > double(stampMs) + 1000))
        return std::nullopt;
    if (book.lastChapter == hereChapter && std::fabs(book.lastSeconds - hereSeconds) < kElsewhereSeconds)
        return std::nullopt;
    return ResumePoint{book.lastChapter, book.lastSeconds};
}

/// Đồng hồ phát: 3:07, 13:05, 1:02:05 (shared/format.ts formatClock).
inline QString formatClock(double seconds) {
    if (!std::isfinite(seconds) || seconds < 0)
        seconds = 0;
    const qint64 whole = qint64(std::floor(seconds));
    const qint64 hours = whole / 3600, minutes = (whole % 3600) / 60, secs = whole % 60;
    const QString mm = hours ? QStringLiteral("%1").arg(minutes, 2, 10, QLatin1Char('0')) : QString::number(minutes);
    return (hours ? QString::number(hours) + QLatin1Char(':') : QString()) + mm + QStringLiteral(":%1").arg(secs, 2, 10, QLatin1Char('0'));
}

/// Thời lượng cho con người: "45 phút", "9 giờ 12 phút", "2 giờ" (formatLength).
inline QString formatLength(double seconds) {
    if (!std::isfinite(seconds) || seconds <= 0)
        return QStringLiteral("0 phút");
    const qint64 minutes = qint64(std::llround(seconds / 60));
    if (minutes < 1)
        return QStringLiteral("dưới 1 phút");
    const qint64 hours = minutes / 60, rest = minutes % 60;
    if (!hours)
        return QStringLiteral("%1 phút").arg(minutes);
    return rest ? QStringLiteral("%1 giờ %2 phút").arg(hours).arg(rest) : QStringLiteral("%1 giờ").arg(hours);
}

} // namespace PlayerLogic
