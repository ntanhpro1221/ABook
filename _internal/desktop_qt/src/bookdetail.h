// Phần nghe của trang sách: danh sách chương của MỘT cuốn (không cần cuốn ấy đang nạp trong bộ phát) và nút chính "Nghe" / "Nghe tiếp · {chương}" /
// "Tạm dừng" / "Nghe lại từ đầu" nói đúng như bản web (labels.ts primaryListenLabel). Các dòng chữ quanh nút (tình trạng, tiến độ) ở BookLogic.js. Lời đáp GET /api/listen/books/<id> cùng đường với Player::open.
#pragma once

#include "chaptersmodel.h"
#include "player.h"

#include <QObject>
#include <QVariantMap>
#include <QtQml/qqmlregistration.h>

class BookDetail : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString bookId READ bookId WRITE setBookId NOTIFY bookIdChanged)
    /// "loading" | "ready" | "failed"
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(ChaptersModel *chapters READ chapters CONSTANT)
    /// Nhãn nút chính: "Nghe" | "Nghe tiếp" | "Nghe tiếp · {chương sẽ nghe}" | "Tạm dừng" | "Nghe lại từ đầu".
    Q_PROPERTY(QString primaryText READ primaryText NOTIFY changed)
    /// Biểu tượng của nút chính (tên icon lucide).
    Q_PROPERTY(QString primaryIcon READ primaryIcon NOTIFY changed)
    /// Có chương nghe được ở máy này (có audio, hay chỉ có chữ mà máy có giọng đọc): nút chính là nghe; không thì nút chính là "Đọc".
    Q_PROPERTY(bool hasPoint READ hasPoint NOTIFY changed)
    /// Nút chính nghe được ngay: có chương nghe được và chưa "nghe hết phần đã có".
    Q_PROPERTY(bool canListen READ canListen NOTIFY changed)
    /// Sách chưa đủ chương mà đã nghe hết phần đã có (và không đang nạp): thay nút chính bằng một dòng.
    Q_PROPERTY(bool caughtUp READ caughtUp NOTIFY changed)
    /// Đã nghe tới đâu đó (giây đã nghe, chỗ nghe sau cùng, hay đang nạp trong bộ phát).
    Q_PROPERTY(bool started READ started NOTIFY changed)
    /// Hết cả cuốn (đang phát thì vẫn là "Tạm dừng").
    Q_PROPERTY(bool finished READ finished NOTIFY changed)
public:
    explicit BookDetail(QObject *parent = nullptr);

    QString bookId() const { return m_bookId; }
    void setBookId(const QString &bookId);
    QString status() const { return m_status; }
    ChaptersModel *chapters() { return &m_chapters; }
    QString primaryText() const { return m_primaryText; }
    QString primaryIcon() const { return m_primaryIcon; }
    bool hasPoint() const { return m_hasPoint; }
    bool canListen() const { return m_canListen; }
    bool caughtUp() const { return m_caughtUp; }
    bool started() const { return m_started; }
    bool finished() const { return m_finishedNow; }

    /// Nút chính: đang phát thì tạm dừng, đang nạp thì phát tiếp, hết sách thì từ chương đầu, không thì nạp rồi phát.
    Q_INVOKABLE void activate();
    /// Hàng chương: phát chương ấy.
    Q_INVOKABLE void playChapter(int chapterId);
    /// Chỗ "Nghe" sẽ phát: {chapterId, at} (đang nạp thì chỗ bộ phát đứng), rỗng khi không chương nào nghe được.
    Q_INVOKABLE QVariantMap point() const;
    /// Chương nghe được đầu tiên ("Từ đầu"), -1 khi không có.
    Q_INVOKABLE int firstPlayable() const;

    /// Nạp lại từ máy chủ (sau khi bộ phát lưu chỗ nghe mới).
    Q_INVOKABLE void reload();

signals:
    void bookIdChanged();
    void changed();

private:
    void recompute();
    bool playableHere(const PlayerLogic::Chapter &chapter) const;

    QString m_bookId;
    QString m_status = QStringLiteral("loading");
    PlayerLogic::Book m_book;
    bool m_hasBook = false;
    ChaptersModel m_chapters;
    quint64 m_seq = 0;
    QString m_primaryText;
    QString m_primaryIcon;
    bool m_hasPoint = false;
    bool m_canListen = false;
    bool m_caughtUp = false;
    bool m_started = false;
    bool m_finishedNow = false;
    bool m_finished = false;
};
