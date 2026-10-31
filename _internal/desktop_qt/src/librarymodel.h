// Danh sách sách của Thư viện: đọc từ GET /api/listen/library (hình dạng `ListenBook`, ui/src/listen/model.ts).
#pragma once

#include <QAbstractListModel>
#include <QJsonArray>
#include <QJsonObject>
#include <QVariantMap>
#include <QtQml/qqmlregistration.h>
#include <vector>

class LibraryModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Có sẵn trong Backend.library")
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    /// Tăng mỗi lần danh sách được nạp lại: ô sách đọc theo hàng (book(row)) gắn vào đây để cập nhật.
    Q_PROPERTY(int revision READ revision NOTIFY revisionChanged)

public:
    enum Role {
        IdRole = Qt::UserRole + 1,
        TitleRole,
        SubtitleRole,   // tác giả; không có thì dòng chi tiết
        CoverKeyRole,   // "<mã>/<phiên bản>" cho image://cover; rỗng khi sách chưa có ảnh bìa
        ProgressRole,   // 0..1 phần đã nghe; 0 = chưa nghe
        SourceRole,     // "" nếu file trên máy này, hay tên máy chứa sách
    };

    explicit LibraryModel(QObject *parent = nullptr);

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    void setBooks(const QJsonArray &books);
    void setError(const QString &message);
    QString error() const { return m_error; }
    int revision() const { return m_revision; }

    /// Mọi trường cho trang sách (QML đọc một lần khi mở).
    Q_INVOKABLE QVariantMap book(int row) const;

signals:
    void countChanged();
    void errorChanged();
    void revisionChanged();

private:
    struct Book {
        QJsonObject raw;
        QString id, title, author, narrator, subtitle, detail, coverKey, source, lastChapter;
        double progress = 0, duration = 0;
        int chaptersTotal = 0, chaptersAvailable = 0;
        bool producing = false, complete = false;
        bool sameShelf(const Book &o) const { return id == o.id; }
    };
    static QString durationText(double seconds);
    std::vector<Book> m_books;
    QString m_error;
    int m_revision = 0;
};
