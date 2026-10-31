// Một bản ABook chạy cho mỗi hồ sơ người dùng (docs/QT_INSTALLER.md, Q4). Lần mở thứ hai (bấm đúp file .abook khi app đang mở,
// hay bấm lối tắt lần nữa) gửi danh sách đường file cho bản đang chạy rồi thoát; bản đang chạy hiện cửa sổ rồi mở file.
//
// Tên kênh theo SID người dùng + %LOCALAPPDATA%: hai hồ sơ dữ liệu khác nhau (hồ sơ giả của test, bộ cài thử) là hai bản riêng,
// không bao giờ gửi file sang app thật của chủ máy.
// Giao thức một dòng mỗi chiều: bản đang chạy chào "<pid>\n" (bản mới cho nó quyền đưa cửa sổ lên trước, AllowSetForegroundWindow),
// bản mới gửi {"files": [...]}\n, bản đang chạy đáp "ok\n".
#pragma once

#include <QObject>
#include <QString>
#include <QStringList>

class QLocalServer;

class SingleInstance : public QObject {
    Q_OBJECT
public:
    /// `name` rỗng: kênh của hồ sơ này (`defaultName`).
    explicit SingleInstance(const QString &name = {}, QObject *parent = nullptr);
    ~SingleInstance() override;

    static QString defaultName();
    /// Tên kênh của người dùng `sid` với dữ liệu ở `localAppData` (không phân biệt hoa thường, dấu gạch cuối).
    static QString nameFor(const QString &sid, const QString &localAppData);

    QString name() const { return m_name; }
    /// Có bản đang chạy: gửi `files` cho nó, trả true (bản này nên thoát). Không có ai nghe: false.
    bool handOff(const QStringList &files, int timeoutMs = 2000);
    /// Làm bản đang chạy. false khi tên đã có người giữ (vừa có bản khác mở cùng lúc). Quyền giữ là một mutex có tên, không phải
    /// ống: Windows cho nhiều QLocalServer nghe cùng một tên ống (SingleInstanceTests bắt được).
    bool listen();

signals:
    /// Một lần mở khác của app vừa tới, kèm các đường file của nó (có thể rỗng).
    void launched(const QStringList &files);

private:
    void accept();

    QString m_name;
    QLocalServer *m_server = nullptr;
    void *m_owner = nullptr;  // HANDLE của mutex; tiến trình chết thì Windows tự nhả
};
