#pragma once
#include <QObject>
#include <QJSValue>
#include <QVariantList>
#include <QNetworkAccessManager>
#include <QHash>
#include <QPointer>
#include <QtQml/qqmlregistration.h>

// JSON boundary shared by Settings and the book dialogs. Uses the existing host,
// including its session header; arrays and null remain arrays and null.
class DesktopApi : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString thirdParty READ thirdParty CONSTANT)
public:
    explicit DesktopApi(QObject *parent = nullptr);
    ~DesktopApi() override;
    Q_INVOKABLE int request(const QString &method, const QString &path, const QJSValue &body, const QJSValue &done);
    Q_INVOKABLE void cancel(int id);
    Q_INVOKABLE QString imageData(const QUrl &file) const;
    /// Ảnh đang nằm trong bộ nhớ tạm (Ctrl+V trên trang sách): data URL PNG như `imageData`, "" khi không có ảnh.
    Q_INVOKABLE QString clipboardImage() const;
    Q_INVOKABLE QString localPath(const QUrl &file) const;
    /// Studio ở máy khác (trình tạo sách): file lẻ hay cả thư mục chương người dùng chọn ở máy này, kể theo cách trình duyệt kể (name, size, path = "Truyện/Tập 1/001.txt"
    /// khi từ thư mục, "" khi file lẻ; local = đường thật) - tới tầng thư mục con thứ hai như `walk` của studio/upload.ts. `fileBase64` đọc nguyên byte để gửi lên.
    Q_INVOKABLE QVariantList sourceFiles(const QStringList &paths) const;
    Q_INVOKABLE QString fileBase64(const QString &local) const;
    Q_INVOKABLE QUrl mediaUrl(const QString &path) const;
    Q_INVOKABLE void refreshLibrary();
    Q_INVOKABLE void preview(const QString &path);
    Q_INVOKABLE void previewFrom(const QString &path, double startSeconds);    // một đoạn của file dài (câu trong file chương): bắt đầu từ giây `startSeconds`
    Q_INVOKABLE void stopPreview();
    static void setPreviewOut(class AudioOut *out);
    QString thirdParty() const;
signals:
    /// Nghe thử (câu mẫu của nhân vật, giọng): clip bắt đầu ra tiếng / hết / không phát được. Cùng ba mốc của thẻ audio trong clip.tsx.
    void previewStarted();
    void previewEnded();
    void previewFailed(const QString &reason);
private:
    QNetworkAccessManager m_net;
    int m_next = 0;
    QHash<int, QPointer<class HostCall>> m_pending;
};
