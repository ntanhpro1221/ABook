// Đường HTTP của bộ phát tới host Python. Một giao diện để Player thử được không cần host (tests/ có bản giả).
#pragma once

#include <QJsonObject>
#include <QObject>
#include <QUrl>

#include <functional>

class PlayerNet : public QObject {
    Q_OBJECT
public:
    explicit PlayerNet(QObject *parent = nullptr) : QObject(parent) {}

    /// `status`: mã HTTP, 0 khi không nối được. `body`: JSON đối tượng của lời đáp (rỗng nếu không có / không phải đối tượng).
    using Done = std::function<void(int status, const QJsonObject &body)>;

    /// Địa chỉ file audio của chương (đã kèm mã phiên): MF mở thẳng, có Range.
    virtual QUrl audioUrl(const QString &bookId, int chapterId) const = 0;
    /// `path` bắt đầu bằng "/api/...". Không có thân thì `body` rỗng và `hasBody` false.
    virtual void request(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool hasBody = true) = 0;
};
