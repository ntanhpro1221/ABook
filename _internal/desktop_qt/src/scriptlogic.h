// Luật thuần của "Đọc theo" (văn bản chạy theo giọng), chuyển từ ui/src/listen/words.ts + follow.ts + ReadAlongText.tsx sang C++: kịch bản chương
// -> đoạn / câu / chữ, câu và chữ đang đọc ở một giây, luật cuộn theo. Không đụng Qt Quick nên thử được riêng (tests/test_readalong.cpp).
#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QList>
#include <QPair>
#include <QRegularExpression>
#include <QString>
#include <QVector>

#include <algorithm>
#include <cmath>

namespace ScriptLogic {

/// Sáng sớm một chút (ms): mắt thấy chữ sáng trễ rõ hơn sáng sớm (words.ts WORD_LEAD_MS).
inline constexpr double kWordLeadMs = 40;
/// Chữ cuối của câu tắt sau chừng này (ms) kể từ lúc nó kết thúc nếu câu kế chưa bắt đầu (LAST_WORD_HOLD_MS).
inline constexpr double kLastWordHoldMs = 400;
/// Sáng sớm của câu (giây): cùng ý với 0,05 giây của sentenceIndexAt.
inline constexpr double kSentenceLeadSeconds = 0.05;

struct Segment {
    double start = -1;                     // giây từ đầu chương; < 0: chưa có mốc
    double end = -1;
    QString text;                          // đã đổi xuống dòng thành khoảng trắng: vị trí ký tự = vị trí trong văn bản đoạn
    QString kind;                          // "narration" | "dialogue" | "thought" | "heading" | ...
    QString speaker;
    bool sceneBreak = false;
    int paragraph = 0;                     // thứ tự đoạn trong danh sách đoạn
    int textStart = 0;                     // vị trí ký tự đầu / cuối trong văn bản của đoạn
    int textEnd = 0;
    QVector<QPair<double, double>> words;  // ms từ đầu chương; rỗng nếu không dùng được (words.ts usableWords)
    QVector<QPair<int, int>> wordChars;    // [đầu, cuối) của từng chữ \S+ trong văn bản ĐOẠN (cùng số với words khi dùng được)
    bool showSpeaker = false;              // nhãn người nói hiện trước câu này
};

struct Paragraph {
    QString text;
    QString kind;                          // "heading" | "scene" | "body"
    int first = 0;                         // câu đầu (thứ tự toàn chương)
    int count = 0;
    QString speaker;                       // nhãn hiện trên đoạn (người nói của câu thoại đầu đoạn mới đổi người) hay ""
};

struct Script {
    int chapterId = 0;
    bool timed = false;
    QVector<Segment> segments;
    QVector<Paragraph> paragraphs;
    QVector<double> starts;                // mốc bắt đầu từng câu, không giảm (câu thiếu mốc lấy mốc câu trước)
};

/// Số chữ hiện (\S+) của một câu.
inline QVector<QPair<int, int>> tokenRanges(const QString &text) {
    QVector<QPair<int, int>> ranges;
    int start = -1;
    for (int i = 0; i < text.size(); ++i) {
        if (text[i].isSpace()) {
            if (start >= 0)
                ranges.append({start, i});
            start = -1;
        } else if (start < 0) {
            start = i;
        }
    }
    if (start >= 0)
        ranges.append({start, int(text.size())});
    return ranges;
}

/// `words` của câu nếu dùng được (đúng hình, tăng dần, đúng số chữ hiện), không thì rỗng.
inline QVector<QPair<double, double>> usableWords(const QString &text, const QJsonArray &words) {
    QVector<QPair<double, double>> out;
    if (words.isEmpty() || words.size() != tokenRanges(text).size())
        return out;
    double last = 0;
    for (const QJsonValue &value : words) {
        const QJsonArray span = value.toArray();
        if (span.size() != 2 || !span[0].isDouble() || !span[1].isDouble())
            return {};
        const double begin = span[0].toDouble(), end = span[1].toDouble();
        if (!std::isfinite(begin) || !std::isfinite(end) || begin < last || end < begin)
            return {};
        last = begin;
        out.append({begin, end});
    }
    return out;
}

/// Dòng chỉ gồm dấu ngăn cảnh: "***", "* * *", "~~~", "---"...
inline bool isSceneBreak(const QString &text) {
    static const QRegularExpression pattern(QStringLiteral("^\\s*(?:[*·•~#=—–-]\\s*){3,}$"));
    return pattern.match(text).hasMatch();
}

inline bool isSpeech(const QString &kind) {
    return kind == QLatin1String("dialogue") || kind == QLatin1String("thought");
}

/// Kịch bản của GET /api/books/<id>/chapters/<n>/script.
inline Script parseScript(const QJsonObject &json) {
    Script script;
    script.chapterId = json.value(QStringLiteral("chapterId")).toInt();
    script.timed = json.value(QStringLiteral("timed")).toBool();
    const QJsonArray array = json.value(QStringLiteral("segments")).toArray();
    script.segments.reserve(array.size());
    script.starts.reserve(array.size());
    double lastStart = 0;
    int paragraphKey = std::numeric_limits<int>::min();
    for (int i = 0; i < array.size(); ++i) {
        const QJsonObject item = array[i].toObject();
        Segment segment;
        segment.text = item.value(QStringLiteral("text")).toString();
        segment.text.replace(QLatin1Char('\n'), QLatin1Char(' '));
        segment.text.replace(QLatin1Char('\r'), QLatin1Char(' '));
        segment.kind = item.value(QStringLiteral("kind")).toString();
        segment.speaker = item.value(QStringLiteral("speaker")).toString();
        segment.sceneBreak = item.value(QStringLiteral("sceneBreak")).toBool();
        if (item.value(QStringLiteral("start")).isDouble())
            segment.start = item.value(QStringLiteral("start")).toDouble();
        if (item.value(QStringLiteral("end")).isDouble())
            segment.end = item.value(QStringLiteral("end")).toDouble();
        segment.words = usableWords(segment.text, item.value(QStringLiteral("words")).toArray());
        lastStart = segment.start >= 0 ? std::max(lastStart, segment.start) : lastStart;
        script.starts.append(lastStart);

        const int key = item.value(QStringLiteral("paragraph")).toInt();
        const Segment *previous = i > 0 ? &script.segments.last() : nullptr;
        segment.showSpeaker = isSpeech(segment.kind) && (!previous || !isSpeech(previous->kind) || previous->speaker != segment.speaker);
        if (script.paragraphs.isEmpty() || key != paragraphKey) {
            Paragraph paragraph;
            paragraph.first = i;
            script.paragraphs.append(paragraph);
            paragraphKey = key;
        }
        Paragraph &paragraph = script.paragraphs.last();
        segment.paragraph = int(script.paragraphs.size()) - 1;
        if (paragraph.count > 0)
            paragraph.text += QLatin1Char(' ');
        segment.textStart = int(paragraph.text.size());
        paragraph.text += segment.text;
        segment.textEnd = int(paragraph.text.size());
        ++paragraph.count;
        for (const auto &range : tokenRanges(segment.text))
            segment.wordChars.append({segment.textStart + range.first, segment.textStart + range.second});
        script.segments.append(segment);
    }
    for (Paragraph &paragraph : script.paragraphs) {
        const Segment &first = script.segments[paragraph.first];
        if (first.kind == QLatin1String("heading"))
            paragraph.kind = QStringLiteral("heading");
        else if (paragraph.count == 1 && (first.sceneBreak || isSceneBreak(first.text)))
            paragraph.kind = QStringLiteral("scene");
        else
            paragraph.kind = QStringLiteral("body");
        if (first.showSpeaker && !first.speaker.isEmpty())
            paragraph.speaker = first.speaker;
    }
    return script;
}

/// Câu đang đọc ở giây `seconds` (tìm nhị phân trên mốc bắt đầu); -1 khi chưa tới câu đầu.
inline int sentenceIndexAt(const QVector<double> &starts, double seconds) {
    int low = 0, high = int(starts.size()) - 1, found = -1;
    while (low <= high) {
        const int middle = (low + high) / 2;
        if (starts[middle] <= seconds + kSentenceLeadSeconds) {
            found = middle;
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    return found;
}

/// Chữ đang đọc ở `ms` (từ đầu chương): chữ cuối cùng đã bắt đầu; -1 khi chưa tới chữ đầu hay chữ cuối đã qua lâu.
inline int wordIndexAt(const QVector<QPair<double, double>> &words, double ms) {
    if (words.isEmpty())
        return -1;
    const double at = ms + kWordLeadMs;
    int low = 0, high = int(words.size()) - 1, found = -1;
    while (low <= high) {
        const int middle = (low + high) / 2;
        if (words[middle].first <= at) {
            found = middle;
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    if (found == int(words.size()) - 1 && ms > words[found].second + kLastWordHoldMs)
        return -1;
    return found;
}

/// Chữ (đơn vị \S+) chứa vị trí con trỏ `offset` trong văn bản đoạn; rơi vào khoảng trắng thì chữ liền sau (chữ cuối nếu không còn); -1 nếu câu không có chữ
/// (wordTap.ts wordAtOffset, tính theo vị trí trong ĐOẠN).
inline int wordAtChar(const Segment &segment, int offset) {
    int last = -1;
    for (int i = 0; i < segment.wordChars.size(); ++i) {
        last = i;
        if (offset <= segment.wordChars[i].second)
            return i;
    }
    return last;
}

/// Đầu một câu để nhắc lại trong lời nhắn: bỏ ngoặc thoại hai đầu, cắt ở ranh giới chữ (shared/format.ts excerpt).
inline QString excerpt(const QString &text, int max = 48) {
    static const QRegularExpression spaces(QStringLiteral("\\s+"));
    static const QRegularExpression edge(QStringLiteral("^[\"“”'‘’«»『』「」—–\\-\\s]+|[\"“”'‘’«»『』「」\\s]+$"));
    QString clean = text;
    clean.replace(spaces, QStringLiteral(" "));
    clean = clean.trimmed();
    clean.remove(edge);
    if (clean.size() <= max)
        return clean;
    QString cut = clean.left(max);
    const int space = int(cut.lastIndexOf(QLatin1Char(' ')));
    QString head = space > max / 2 ? cut.left(space) : cut;
    static const QRegularExpression tail(QStringLiteral("[\\s,.;:!?…—–-]+$"));
    head.remove(tail);
    return head + QStringLiteral("…");
}

} // namespace ScriptLogic

// Luật cuộn theo giọng (follow.ts): giữ nguyên số.
namespace FollowLogic {

/// Người thôi cuộn chừng này (ms) mà câu đang nghe nằm trong khung: theo lại.
inline constexpr int kSettleMs = 1500;
/// Câu đang nghe xuống quá phần này của khung thì cuộn (khi đang theo).
inline constexpr double kLowEdge = 0.85;
/// Chỗ đặt câu đang nghe sau khi cuộn: phần này của chiều cao khung tính từ trên.
inline constexpr double kPlaceAt = 0.3;
/// Câu chỉ còn ló chừng này px ở mép thì không tính là "thấy".
inline constexpr double kSlack = 4;

enum class Placement { Above, Inside, Below };

inline Placement placementOf(double top, double bottom, double viewTop, double viewBottom) {
    if (bottom <= viewTop + kSlack)
        return Placement::Above;
    if (top >= viewBottom - kSlack)
        return Placement::Below;
    return Placement::Inside;
}

/// Đang theo mà câu đang nghe không còn nằm gọn trong vùng dễ đọc: cần cuộn.
inline bool needsFollowScroll(double top, double bottom, double viewTop, double viewBottom) {
    const double height = viewBottom - viewTop;
    return top < viewTop || bottom > viewTop + height * kLowEdge;
}

/// `scrollTop` mới để câu đứng ở khoảng một phần ba từ trên khung.
inline double followScrollTop(double top, double viewTop, double viewBottom, double scrollTop) {
    const double height = viewBottom - viewTop;
    return std::max(0.0, scrollTop + top - viewTop - height * kPlaceAt);
}

} // namespace FollowLogic
