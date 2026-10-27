// Chữ của một chương CHỈ-CÓ-CHỮ thành kịch bản không mốc mà màn đọc dàn được: chép ui/src/listen/textScript.ts (textScript, splitParagraphs,
// withoutLines, isSceneBreakLine) và readingAnchor.ts (vân tay FNV-1a 64, mốc chỗ đọc) sang C++. Không đụng Qt Quick: thử riêng ở ReadAlongTests.
#pragma once

#include <QJsonArray>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QString>
#include <QStringList>
#include <QVariantMap>

#include <algorithm>
#include <cmath>

namespace TextScript {

inline constexpr int kCreditWindow = 6;        // CREDIT_WINDOW
inline constexpr int kCreditTailWindow = 12;   // CREDIT_TAIL_WINDOW
inline constexpr int kWholeLine = 200;         // WHOLE_LINE
inline constexpr int kSceneBreakMinRuleGlyphs = 3;
inline constexpr int kSceneBreakMaxGlyphs = 40;

inline const QString &ruleGlyphs() { static const QString s = QStringLiteral("*~-=_#+·•‧・—–―‒─━═┄┈╌"); return s; }
inline const QString &aloneGlyphs() { static const QString s = QStringLiteral("*~-=#"); return s; }
inline const QString &ornamentGlyphs() { static const QString s = QStringLiteral("◆◇◈○●◎□■▪▫▲△▽▼★☆✦✧✱✲✶✷✻✽❖❀✿❁※⁂⁕⋆◦♦♢◊⸻§"); return s; }

/// Mọi chuỗi khoảng trắng thành một dấu cách, bỏ hai đầu (squeeze).
inline QString squeeze(const QString &text) { return text.simplified(); }

/// Bỏ mã chú thích của trang web ("[note54360]").
inline QString withoutNoteMarkers(QString text) {
    static const QRegularExpression marker(QStringLiteral("\\[\\s*note\\d+\\s*\\]"), QRegularExpression::CaseInsensitiveOption);
    return text.remove(marker);
}

/// Các ký tự (theo code point, đã NFKC) của dòng trừ khoảng trắng.
inline QStringList glyphsOf(const QString &line) {
    QStringList out;
    const QString normal = line.normalized(QString::NormalizationForm_KC);
    for (int i = 0; i < normal.size(); ++i) {
        QString glyph(normal[i]);
        if (normal[i].isHighSurrogate() && i + 1 < normal.size()) glyph += normal[++i];
        if (glyph.size() == 1 && glyph[0].isSpace()) continue;
        out.append(glyph);
    }
    return out;
}

/// Dòng chỉ có ký hiệu ngăn cảnh; `alone`: dòng đứng riêng một đoạn (isSceneBreakLine).
inline bool isSceneBreakLine(const QString &line, bool alone = false) {
    const QStringList glyphs = glyphsOf(line);
    if (glyphs.isEmpty() || glyphs.size() > kSceneBreakMaxGlyphs) return false;
    int rule = 0, ornament = 0;
    for (const QString &glyph : glyphs) {
        if (ruleGlyphs().contains(glyph)) ++rule;
        else if (ornamentGlyphs().contains(glyph)) ++ornament;
    }
    if (rule + ornament != glyphs.size()) return false;
    if (rule == 0) return true;
    if (alone && std::all_of(glyphs.begin(), glyphs.end(), [](const QString &g) { return aloneGlyphs().contains(g); })) return true;
    return glyphs.size() >= kSceneBreakMinRuleGlyphs;
}

struct Paragraph {
    QString text;
    bool sceneBreak = false;
};

/// Dòng bị máy dàn trang bẻ giữa câu thì nối lại; file mỗi dòng một đoạn thì giữ từng dòng (textParagraphs).
inline QStringList textParagraphs(const QStringList &lines) {
    if (lines.size() < 2) return lines;
    static const QRegularExpression end(QStringLiteral("[.!?…\"”»’)」』】。！？~–—]$"));
    int ended = 0;
    bool whole = false;
    for (int i = 0; i < lines.size(); ++i) {
        if (i < lines.size() - 1 && end.match(lines[i]).hasMatch()) ++ended;
        if (lines[i].size() > kWholeLine) whole = true;
    }
    return ended * 2 > lines.size() - 1 || whole ? lines : QStringList{lines.join(QLatin1Char(' '))};
}

inline void appendPlain(QList<Paragraph> &out, const QStringList &texts) {
    for (const QString &text : texts) out.append({text, false});
}

inline QList<Paragraph> blockParagraphs(const QString &block) {
    QStringList lines;
    for (const QString &line : block.split(QLatin1Char('\n'))) {
        const QString clean = squeeze(line);
        if (!clean.isEmpty()) lines.append(clean);
    }
    QList<Paragraph> out;
    QStringList run;
    for (const QString &line : lines) {
        if (!isSceneBreakLine(line, lines.size() == 1)) {
            run.append(line);
            continue;
        }
        appendPlain(out, textParagraphs(run));
        out.append({line, true});
        run.clear();
    }
    appendPlain(out, textParagraphs(run));
    return out;
}

inline QString unixLines(QString text) {
    text.replace(QStringLiteral("\r\n"), QStringLiteral("\n"));
    text.replace(QLatin1Char('\r'), QLatin1Char('\n'));
    return text;
}

/// Các đoạn của chương (splitParagraphs).
inline QList<Paragraph> splitParagraphs(const QString &text) {
    static const QRegularExpression blank(QStringLiteral("\\n[ \\t\\x{00A0}]*\\n"));
    const QString clean = unixLines(withoutNoteMarkers(text));
    QList<Paragraph> out;
    if (blank.match(clean).hasMatch()) {
        for (const QString &block : clean.split(blank)) out.append(blockParagraphs(block));
        return out;
    }
    QStringList lines;
    for (const QString &line : clean.split(QLatin1Char('\n'))) {
        const QString squeezed = squeeze(line);
        if (!squeezed.isEmpty()) lines.append(squeezed);
    }
    for (const QString &line : lines) out.append({line, isSceneBreakLine(line, lines.size() == 1)});
    return out;
}

/// Chữ của chương trừ các dòng người nghe đã bỏ khỏi phần đọc, chỉ trong 6 dòng có chữ đầu và 12 dòng có chữ cuối (withoutLines).
inline QString withoutLines(const QString &text, const QStringList &skip) {
    if (skip.isEmpty()) return text;
    const QStringList lines = unixLines(text).split(QLatin1Char('\n'));
    QStringList shown;
    QList<int> filled;
    for (int i = 0; i < lines.size(); ++i) {
        shown.append(squeeze(withoutNoteMarkers(lines[i])));
        if (!shown.last().isEmpty()) filled.append(i);
    }
    QSet<int> window;
    for (int i = 0; i < filled.size(); ++i)
        if (i < kCreditWindow || i >= filled.size() - kCreditTailWindow) window.insert(filled[i]);
    QStringList kept;
    for (int i = 0; i < lines.size(); ++i)
        if (!(window.contains(i) && skip.contains(shown[i]))) kept.append(lines[i]);
    return kept.join(QLatin1Char('\n'));
}

/// Kịch bản (cùng hình với GET .../script) của một chương chỉ có chữ; đoạn đầu trùng tên chương là tiêu đề (textScript).
inline QJsonObject textScript(int chapterId, const QString &title, const QString &text, const QStringList &skip = {}) {
    const QList<Paragraph> paragraphs = splitParagraphs(withoutLines(text, skip));
    const QString heading = squeeze(title);
    QJsonArray segments;
    for (int i = 0; i < paragraphs.size(); ++i) {
        QJsonObject segment{{QStringLiteral("id"), i}, {QStringLiteral("paragraph"), i}, {QStringLiteral("text"), paragraphs[i].text},
            {QStringLiteral("kind"), i == 0 && paragraphs[i].text == heading ? QStringLiteral("heading") : QStringLiteral("narration")},
            {QStringLiteral("speaker"), QString()}, {QStringLiteral("start"), QJsonValue::Null}, {QStringLiteral("end"), QJsonValue::Null},
            {QStringLiteral("status"), QStringLiteral("text")}};
        if (paragraphs[i].sceneBreak) segment.insert(QStringLiteral("sceneBreak"), true);
        segments.append(segment);
    }
    return {{QStringLiteral("chapterId"), chapterId}, {QStringLiteral("title"), title}, {QStringLiteral("timed"), false},
        {QStringLiteral("duration"), 0}, {QStringLiteral("segments"), segments}};
}

// ---- mốc chỗ đọc (readingAnchor.ts) ----

/// "fnv1a64:<16 hex>" của các đoạn UTF-8 nối bằng LF (textFingerprint).
inline QString fingerprint(const QStringList &paragraphs) {
    quint64 hash = 0xcbf29ce484222325ULL;
    for (const char byte : paragraphs.join(QLatin1Char('\n')).toUtf8()) {
        hash ^= quint8(byte);
        hash *= 0x100000001b3ULL;
    }
    return QStringLiteral("fnv1a64:%1").arg(hash, 16, 16, QLatin1Char('0'));
}

/// Số code point của chuỗi.
inline int codePoints(const QString &text) { return int(text.toUcs4().size()); }

/// Đầu các chữ \S+ (vị trí UTF-16).
inline QList<QPair<int, int>> tokens(const QString &text) {
    QList<QPair<int, int>> out;
    int start = -1;
    for (int i = 0; i < text.size(); ++i) {
        if (text[i].isSpace()) {
            if (start >= 0) out.append({start, i});
            start = -1;
        } else if (start < 0) {
            start = i;
        }
    }
    if (start >= 0) out.append({start, int(text.size())});
    return out;
}

/// Mốc của chữ `word` trong đoạn `segment` (makeAnchor); rỗng khi đoạn không có.
inline QVariantMap makeAnchor(const QStringList &paragraphs, int segment, int word, const QString &textHash) {
    if (segment < 0 || segment >= paragraphs.size()) return {};
    const QString &text = paragraphs[segment];
    const auto list = tokens(text);
    const int start = list.isEmpty() ? 0 : list[std::max(0, std::min(int(list.size()) - 1, word))].first;
    return {{QStringLiteral("segment"), segment}, {QStringLiteral("charOffset"), codePoints(text.left(start))},
        {QStringLiteral("textHash"), textHash}, {QStringLiteral("paragraphHash"), fingerprint({text})}};
}

/// Đoạn mà mốc trỏ tới khi băm chương đã lệch: đoạn cũ còn nguyên, hay đoạn gần nhất có đúng băm đoạn (movedSegment); -1 nếu không có.
inline int movedSegment(const QStringList &paragraphs, int segment, const QString &wanted) {
    static const QRegularExpression hash(QStringLiteral("^fnv1a64:[0-9a-f]{16}$"));
    if (!hash.match(wanted).hasMatch()) return -1;
    const auto same = [&](int index) { return index >= 0 && index < paragraphs.size() && fingerprint({paragraphs[index]}) == wanted; };
    if (same(segment)) return segment;
    int best = -1;
    for (int index = 0; index < paragraphs.size(); ++index) {
        if (best >= 0 && std::abs(index - segment) >= std::abs(best - segment)) continue;
        if (same(index)) best = index;
    }
    return best;
}

/// Đoạn của mốc (restoreAnchor, chỉ phần đoạn); -1 khi mốc không dùng được.
inline int restoreAnchor(const QStringList &paragraphs, const QVariantMap &anchor, const QString &textHash) {
    if (anchor.isEmpty()) return -1;
    bool okSegment = false, okOffset = false;
    const qint64 segment = anchor.value(QStringLiteral("segment")).toLongLong(&okSegment);
    const qint64 offset = anchor.value(QStringLiteral("charOffset")).toLongLong(&okOffset);
    if (!okSegment || !okOffset || segment < 0 || offset < 0 || segment > 2147483647 || offset > 2147483647) return -1;
    const int found = anchor.value(QStringLiteral("textHash")).toString() == textHash ? int(segment)
        : movedSegment(paragraphs, int(segment), anchor.value(QStringLiteral("paragraphHash")).toString());
    if (found < 0 || found >= paragraphs.size() || offset > codePoints(paragraphs[found])) return -1;
    return found;
}

/// Đoạn của một chỗ đọc đã lưu: mốc thắng chỉ số, câu trích tìm đoạn gần chỉ số cũ nhất (readingIndex).
inline int readingIndex(const QStringList &paragraphs, const QVariantMap &place, const QString &textHash) {
    const int anchored = restoreAnchor(paragraphs, place.value(QStringLiteral("anchor")).toMap(), textHash);
    if (anchored >= 0) return anchored;
    const double index = place.value(QStringLiteral("index")).toDouble();
    const QString quoteRaw = place.value(QStringLiteral("quote")).toString();
    if (!quoteRaw.isEmpty()) {
        static const QRegularExpression ellipsis(QStringLiteral("…$"));
        const auto normal = [](const QString &text) { return text.normalized(QString::NormalizationForm_C).simplified(); };
        const QString quote = normal(quoteRaw).remove(ellipsis);
        int best = -1;
        if (!quote.isEmpty())
            for (int i = 0; i < paragraphs.size(); ++i)
                if (normal(paragraphs[i]).startsWith(quote) && (best < 0 || std::abs(i - index) < std::abs(best - index))) best = i;
        if (best >= 0) return best;
    }
    const int last = int(paragraphs.size()) - 1;
    return std::max(0, std::min(last, std::isfinite(index) ? int(index) : 0));
}

} // namespace TextScript
