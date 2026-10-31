// Chữ của nhạc nền trên trình phát: mức nhạc (ui/src/shared/musicLevels.ts), giấy phép và ghi công (ui/src/shared/format.ts). Chép đúng
// từng chữ của bản web - luật đồng nhất giao diện giữa các nền tảng.
#pragma once

#include "musiclogic.h"

#include <QRegularExpression>
#include <QString>
#include <QVector>

#include <algorithm>

namespace MusicText {

struct Level {
    double value = 0;
    QString name;
};

/// Mức nhạc nền dưới giọng đọc (dB) người nghe chọn được; -20 là mặc định của máy (music_plan.DEFAULT_LEVEL_DB).
inline QVector<Level> musicLevels() {
    return {{-14, QStringLiteral("To")},
            {-17, QStringLiteral("Hơi to")},
            {-20, QStringLiteral("Vừa (mặc định)")},
            {-24, QStringLiteral("Nhỏ")},
            {-28, QStringLiteral("Rất nhỏ")}};
}

/// Lời kèm vài mức: -28 là mức nhạc khó che lời đọc nhất (MIX_QA mục 7.1).
inline QString levelNote(double value) {
    return value == -28 ? QStringLiteral("dễ nghe lời nhất") : QString();
}

/// Các mức có sẵn, thêm mức hiện tại của sách nếu nó không trùng mức nào (sách đóng gói ở -18 dB).
inline QVector<Level> levelOptions(double current) {
    QVector<Level> levels = musicLevels();
    if (std::any_of(levels.begin(), levels.end(), [current](const Level &level) { return level.value == current; }))
        return levels;
    levels.append({current, QString::number(current, 'g', 15).replace(QLatin1Char('.'), QLatin1Char(',')) + QStringLiteral(" dB (của sách)")});
    std::sort(levels.begin(), levels.end(), [](const Level &a, const Level &b) { return a.value > b.value; });
    return levels;
}

/// Giấy phép đọc được: "CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0". Phiên bản lấy từ liên kết giấy phép nếu có, mã lạ thì giữ nguyên.
inline QString licenseLabel(const QString &code, const QString &url = QString()) {
    static const QRegularExpression link(QStringLiteral("creativecommons\\.org/(licenses|publicdomain)/([a-z-]+)/(\\d+(?:\\.\\d+)?)"),
                                         QRegularExpression::CaseInsensitiveOption);
    const QRegularExpressionMatch match = link.match(url);
    if (match.hasMatch()) {
        if (match.captured(1).toLower() == QLatin1String("licenses"))
            return QStringLiteral("CC %1 %2").arg(match.captured(2).toUpper(), match.captured(3));
        if (match.captured(2).toLower() == QLatin1String("zero"))
            return QStringLiteral("CC0 %1").arg(match.captured(3));
    }
    static const QRegularExpression by(QStringLiteral("^by(-(nc|nd|sa))*$"));
    const QString raw = code.trimmed();
    const QString lower = raw.toLower();
    if (lower == QLatin1String("cc0"))
        return QStringLiteral("CC0");
    if (by.match(lower).hasMatch())
        return QStringLiteral("CC ") + lower.toUpper();
    return raw;
}

/// Dòng ghi công: `attribution` của danh mục khi bài có tác giả; không có tác giả thì chỉ tên bài - không bao giờ in "by" rỗng.
inline QString creditText(const MusicLogic::MusicCredit &credit) {
    const QString creator = credit.creator.trimmed();
    const QString attribution = credit.attribution.trimmed();
    if (!attribution.isEmpty() && !creator.isEmpty())
        return attribution;
    QStringList parts;
    for (const QString &part : {credit.title.trimmed(), creator})
        if (!part.isEmpty())
            parts << part;
    return parts.join(QStringLiteral(" - "));
}

/// Nhạc có giấy phép đòi ghi công (khác cc0; nhạc người dùng nhập không có giấy phép): kèm lời "đã chỉnh sửa".
inline bool needsModifiedNote(const QString &license) {
    const QString code = license.trimmed().toLower();
    return !code.isEmpty() && code != QLatin1String("cc0");
}

inline QString modifiedNote() {
    return QStringLiteral("Đã chỉnh sửa: các bài nhạc được cắt vòng, trộn nhỏ dưới giọng đọc và chỉnh âm lượng cho vừa sách.");
}

} // namespace MusicText
