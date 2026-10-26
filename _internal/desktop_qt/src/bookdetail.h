// Phần nghe của trang sách: danh sách chương của MỘT cuốn (không cần cuốn ấy đang nạp trong bộ phát) và nút chính "Nghe" / "Nghe tiếp" /
// "Tạm dừng" / "Nghe lại từ đầu" nói đúng như bản web (labels.ts primaryListenLabel). Lời đáp GET /api/listen/books/<id> cùng đường với Player::open.
#pragma once

#include "chaptersmodel.h"
#include "player.h"

#include <QObject>
#include <QtQml/qqmlregistration.h>

class BookDetail : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString bookId READ bookId WRITE setBookId NOTIFY bookIdChanged)
    /// "loading" | "ready" | "failed"
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(ChaptersModel *chapters READ chapters CONSTANT)
    /// Nhãn nút chính: "Nghe" | "Nghe tiếp" | "Tạm dừng" | "Nghe lại từ đầu".
    Q_PROPERTY(QString primaryText READ primaryText NOTIFY changed)
    /// Chỗ sẽ nghe tiếp ("Chương 4"), hay "" khi nhãn đã đủ.
    Q_PROPERTY(QString primaryCaption READ primaryCaption NOTIFY changed)
    /// Biểu tượng của nút chính (tên icon lucide).
    Q_PROPERTY(QString primaryIcon READ primaryIcon NOTIFY changed)
    /// Có chương nào nghe được ngay (có audio).
    Q_PROPERTY(bool canListen READ canListen NOTIFY changed)
    /// Một dòng nói vì sao chưa nghe được / đã nghe hết phần đã có; "" khi không cần.
    Q_PROPERTY(QString message READ message NOTIFY changed)
public:
    explicit BookDetail(QObject *parent = nullptr);

    QString bookId() const { return m_bookId; }
    void setBookId(const QString &bookId);
    QString status() const { return m_status; }
    ChaptersModel *chapters() { return &m_chapters; }
    QString primaryText() const { return m_primaryText; }
    QString primaryCaption() const { return m_primaryCaption; }
    QString primaryIcon() const { return m_primaryIcon; }
    bool canListen() const { return m_canListen; }
    QString message() const { return m_message; }

    /// Nút chính: đang phát thì tạm dừng, đang nạp thì phát tiếp, hết sách thì từ chương đầu, không thì nạp rồi phát.
    Q_INVOKABLE void activate();
    /// Hàng chương: phát chương ấy.
    Q_INVOKABLE void playChapter(int chapterId);

    /// Nạp lại từ máy chủ (sau khi bộ phát lưu chỗ nghe mới).
    Q_INVOKABLE void reload();

signals:
    void bookIdChanged();
    void changed();

private:
    void recompute();

    QString m_bookId;
    QString m_status = QStringLiteral("loading");
    PlayerLogic::Book m_book;
    bool m_hasBook = false;
    ChaptersModel m_chapters;
    quint64 m_seq = 0;
    QString m_primaryText;
    QString m_primaryCaption;
    QString m_primaryIcon;
    bool m_canListen = false;
    bool m_finished = false;
    QString m_message;
};
