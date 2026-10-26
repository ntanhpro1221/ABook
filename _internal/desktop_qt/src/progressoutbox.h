// Hộp thư đi của chỗ nghe: chuyển từ ui/src/listen/progressOutbox.ts. Bản chờ sống qua lần tắt app (file JSON), chỉ lời đáp ĐÚNG bản mới gỡ được nó,
// mỗi hồ sơ gửi tuần tự, gửi hỏng thì giữ lại và `flush()` thử lại (Player gọi mỗi 10 giây). 409 (cửa sổ khác đã thay phiên nghe) thì bỏ bản chờ.
#pragma once

#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QString>

#include <functional>

struct ProgressSpot {
    QString bookId;
    int chapterId = 0;
    double seconds = 0;
    double duration = 0;
    QString record;
    qint64 savedAt = 0;
    QString sessionId;
    int revision = 0;
    bool hasRevision = false;

    QJsonObject toJson() const;
    static ProgressSpot fromJson(const QJsonObject &json);
};

class ProgressOutbox : public QObject {
    Q_OBJECT
public:
    /// `send(spot, done)` gửi MỘT bản; gọi `done(status)` (0 = không nối được, 2xx = xong, 409 = bị thay thế). `ack(spot)` sau lần gửi thành công.
    using Done = std::function<void(int status)>;
    using Send = std::function<void(const ProgressSpot &spot, Done done)>;
    ProgressOutbox(Send send, std::function<void(const ProgressSpot &)> ack, const QString &storagePath, QObject *parent = nullptr);

    void put(const ProgressSpot &spot);
    /// Gửi lại mọi bản chờ chưa có lượt gửi nào đang chạy.
    void flush();
    int pending() const { return m_pending.size(); }
    bool busy() const { return !m_running.isEmpty(); }
    /// Có bản chờ hay lượt gửi dở (khi tắt app: chờ thêm một chút).
    bool idle() const { return m_pending.isEmpty() && m_running.isEmpty(); }

private:
    struct Pending {
        ProgressSpot spot;
        QString receipt;
    };
    static QString keyOf(const ProgressSpot &spot) { return spot.bookId + QLatin1Char(':') + spot.record; }
    void persist();
    void deliver(const QString &key);

    Send m_send;
    std::function<void(const ProgressSpot &)> m_ack;
    QString m_path;
    QHash<QString, Pending> m_pending;
    QHash<QString, bool> m_running; // khoá đang có lượt gửi
};
