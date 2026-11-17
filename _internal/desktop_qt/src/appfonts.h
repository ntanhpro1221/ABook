#pragma once
#include <QDir>
#include <QFile>
#include <QFontDatabase>
#include <QGuiApplication>

// CJK names (books, authors, characters, music artists) fall back to the fonts every Windows 10/11
// install ships, so the installer stays small. Han goes to the Simplified Chinese face first (most
// CJK titles here come from Chinese novels), kana to the Japanese one, Hangul to the Korean one; each
// list continues so a character missing from the first face still finds a glyph in the next.
struct CjkFallback { const char *family; const char *files[2]; };
static constexpr CjkFallback cjkFallbacks[] = {
    {"Microsoft YaHei UI", {"msyh.ttc", "msyhbd.ttc"}},
    {"Yu Gothic UI", {"YuGothR.ttc", "YuGothB.ttc"}},
    {"Malgun Gothic", {"malgun.ttf", "malgunbd.ttf"}},
};

inline QStringList cjkFallbackOrder(QChar::Script script) {
    switch (script) {
    case QChar::Script_Hiragana:
    case QChar::Script_Katakana: return {QStringLiteral("Yu Gothic UI"), QStringLiteral("Microsoft YaHei UI")};
    case QChar::Script_Hangul: return {QStringLiteral("Malgun Gothic")};
    default: return {QStringLiteral("Microsoft YaHei UI"), QStringLiteral("Yu Gothic UI"), QStringLiteral("Malgun Gothic")};
    }
}

// The Windows platform plugin already sees these system families. The offscreen plugin used by
// the tests only sees QT_QPA_FONTDIR, so there the same system files are registered by path; no
// font data is copied or bundled either way.
inline void addCjkFallbacks() {
    const QString fonts = QDir(qEnvironmentVariable("WINDIR", QStringLiteral("C:/Windows"))).filePath(QStringLiteral("Fonts"));
    QStringList available;
    for (const auto &face : cjkFallbacks) {
        const QString family = QString::fromLatin1(face.family);
        if (!QFontDatabase::hasFamily(family))
            for (const char *file : face.files)
                if (const QString path = QDir(fonts).filePath(QString::fromLatin1(file)); QFile::exists(path))
                    QFontDatabase::addApplicationFont(path);
        if (QFontDatabase::hasFamily(family)) available << family;
    }
    // Not Script_Common: CJK punctuation takes the script of the name around it, and symbols keep
    // the bundled symbol fonts and the system's own emoji fallback.
    for (const auto script : {QChar::Script_Han, QChar::Script_Bopomofo, QChar::Script_Hiragana, QChar::Script_Katakana, QChar::Script_Hangul})
        for (const auto &family : cjkFallbackOrder(script))
            if (available.contains(family)) QFontDatabase::addApplicationFallbackFontFamily(script, family);
}

// One font stack for the application and the offscreen QML tests. The tiny OFL
// subset supplies UI symbols without changing words; only CJK names use host fonts.
inline bool loadAppFonts(const QString &directory) {
    for (const auto &weight : {"Regular", "Medium", "Bold"})
        if (QFontDatabase::addApplicationFont(directory + QStringLiteral("/BeVietnamPro-%1.ttf").arg(QLatin1String(weight))) < 0)
            return false;
    for (const auto &kind : {"Arrows", "Shapes"}) {
        const int symbols = QFontDatabase::addApplicationFont(directory + QStringLiteral("/ABookUI%1.ttf").arg(QLatin1String(kind)));
        if (symbols < 0) return false;
        for (const auto &family : QFontDatabase::applicationFontFamilies(symbols))
            QFontDatabase::addApplicationFallbackFontFamily(QChar::Script_Common, family);
    }
    addCjkFallbacks();
    QFont base(QStringLiteral("Be Vietnam Pro"));
    base.setPixelSize(16);
    QGuiApplication::setFont(base);
    return true;
}
