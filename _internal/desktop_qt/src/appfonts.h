#pragma once
#include <QFontDatabase>
#include <QGuiApplication>

// One font stack for the application and the offscreen QML tests. The tiny OFL
// subset supplies UI symbols without changing words or relying on host fonts.
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
    QFont base(QStringLiteral("Be Vietnam Pro"));
    base.setPixelSize(16);
    QGuiApplication::setFont(base);
    return true;
}
