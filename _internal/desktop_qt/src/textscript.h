#pragma once
#include <QJsonArray>
#include <QJsonObject>
#include <QRegularExpression>
#include <QStringList>
#include <algorithm>

// textScript.ts: retain paragraph boundaries and source ranks, remove note
// markers, and keep scene separators in the timeline without sending them to TTS.
namespace TextScript {
inline bool speakable(const QString &text) {
    static const QRegularExpression p(QStringLiteral("[\\p{L}\\p{N}]"));
    return text.contains(p);
}
inline bool scene(const QString &text, bool alone) {
    const QString rule = QStringLiteral("*~-=_#+·•‧・—–―‒─━═┄┈╌");
    const QString ornaments = QStringLiteral("◆◇◈○●◎□■▪▫▲△▽▼★☆✦✧✱✲✶✷✻✽❖❀✿❁※⁂⁕⋆◦♦♢◊⸻§");
    QString glyphs;
    for (const auto c : text.normalized(QString::NormalizationForm_KC)) if (!c.isSpace()) glyphs += c;
    if (glyphs.isEmpty() || glyphs.size() > 40) return false;
    int rules = 0; bool allAlone = true;
    for (const auto c : glyphs) {
        if (!rule.contains(c) && !ornaments.contains(c)) return false;
        if (rule.contains(c)) ++rules;
        if (!QStringLiteral("*~-=#").contains(c)) allAlone = false;
    }
    return rules == 0 || glyphs.size() >= 3 || (alone && allAlone);
}
inline QStringList paragraphs(QString text) {
    text.remove(QRegularExpression(QStringLiteral("\\[\\s*note\\d+\\s*\\]"), QRegularExpression::CaseInsensitiveOption));
    text.replace(QStringLiteral("\r\n"), QStringLiteral("\n")); text.replace(QLatin1Char('\r'), QLatin1Char('\n'));
    const QRegularExpression blank(QStringLiteral("\n[ \\t\u00a0]*\n"));
    const bool blocks = text.contains(blank);
    QStringList out;
    for (const auto &block : text.split(blank)) {
        QStringList lines;
        for (const auto &line : block.split(QLatin1Char('\n'))) if (!line.simplified().isEmpty()) lines.append(line.simplified());
        QStringList run;
        auto flush = [&] {
            int ended = 0; bool longLine = false;
            static const QRegularExpression end(QStringLiteral("[.!?…\"”»’)」』】。！？~–—]$"));
            for (int i = 0; i < run.size(); ++i) { if (i + 1 < run.size() && run[i].contains(end)) ++ended; if (run[i].size() > 200) longLine = true; }
            if (!blocks || run.size() < 2 || ended * 2 > run.size() - 1 || longLine) out.append(run);
            else out.append(run.join(QLatin1Char(' ')));
            run.clear();
        };
        for (const auto &line : lines) { if (scene(line, lines.size() == 1)) { flush(); out.append(line); } else run.append(line); }
        flush();
    }
    return out;
}
inline QJsonObject script(const QString &text) {
    QJsonArray segments;
    double at = 0;
    const auto list = paragraphs(text);
    for (int i = 0; i < list.size(); ++i) {
        const bool spoken = speakable(list[i]);
        const double duration = spoken ? std::max(0.5, list[i].size() / 14.0) : 0;
        segments.append(QJsonObject{{QStringLiteral("text"), list[i]}, {QStringLiteral("paragraph"), i},
            {QStringLiteral("kind"), spoken ? QStringLiteral("narration") : QStringLiteral("scene")},
            {QStringLiteral("start"), at}, {QStringLiteral("end"), at + duration}});
        at += duration;
    }
    return QJsonObject{{QStringLiteral("timed"), true}, {QStringLiteral("segments"), segments}};
}
}
