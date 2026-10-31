// Backend Python của app: khởi chạy, giám sát và nói chuyện HTTP với nó.
// Làm đúng việc vỏ Tauri làm (shell/src-tauri/src/main.rs): chạy `python -m abook.webui.host`, đọc từng dòng JSON
// trên stdout (host báo {"ready": "http://127.0.0.1:PORT/?t=MÃ"}), gửi {"quit": true} khi thoát, ghi stderr vào
// %LOCALAPPDATA%\ABook\logs\host.log. Mọi dữ liệu đi qua HTTP API của host - cùng API với giao diện web.
#pragma once

#include "librarymodel.h"

#include <QElapsedTimer>
#include <QTimer>
#include <QJsonArray>
#include <QJsonValue>
#include <QNetworkAccessManager>
#include <QObject>
#include <QProcess>
#include <QUrl>
#include <QVariantMap>
#include <QJSEngine>
#include <QQmlEngine>
#include <QtQml/qqmlregistration.h>

class QNetworkReply;

class Backend : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(State state READ state NOTIFY stateChanged)
    Q_PROPERTY(QString message READ message NOTIFY stateChanged)
    Q_PROPERTY(int port READ port NOTIFY stateChanged)
    Q_PROPERTY(QString version READ version CONSTANT)
    Q_PROPERTY(int readyMs READ readyMs NOTIFY stateChanged)
    Q_PROPERTY(QString logPath READ logPath CONSTANT)
    Q_PROPERTY(LibraryModel *library READ library CONSTANT)
    Q_PROPERTY(bool libraryLoaded READ libraryLoaded NOTIFY libraryLoadedChanged)

public:
    enum State { Starting, Ready, Failed };
    Q_ENUM(State)

    // Không có tham số mặc định: Qt 6.10 ưu tiên hàm dựng mặc định hơn create(), sẽ tạo bản sao thứ hai cho QML.
    explicit Backend(QObject *parent);
    ~Backend() override;

    struct Endpoint {
        int port = 0;
        QByteArray token;
    };
    /// Địa chỉ + mã phiên hiện tại; đọc được từ mọi luồng (bộ giải mã bìa).
    static Endpoint endpoint();

    static Backend *instance();
    static Backend *create(QQmlEngine *, QJSEngine *);

    /// Starting longer than this (the host neither says Ready nor exits) is a failure with "Thử lại". Measured 31-10:
    /// Ready about 0.9 s after spawn; 60 s leaves room for a cold first start (antivirus scanning the runtime). Tests shorten it.
    static inline int s_startLimitMs = 60'000;

    State state() const { return m_state; }
    QString message() const { return m_message; }
    int port() const { return m_port; }
    QString version() const;
    int readyMs() const { return m_readyMs; }
    QString logPath() const;
    LibraryModel *library() const { return m_library; }
    bool libraryLoaded() const { return m_libraryLoaded; }

    Q_INVOKABLE void start();
    Q_INVOKABLE void restart();
    Q_INVOKABLE void refreshLibrary();
    /// Dừng host (gửi quit, chờ tối đa 5 giây như vỏ Tauri, rồi giết). Gọi lúc app thoát.
    void stop();

    /// GET tới host kèm mã phiên; gọi từ luồng giao diện. Trả về reply (người gọi nối `finished`).
    QNetworkReply *get(const QString &path);
    QNetworkAccessManager *network() { return &m_net; }
    bool ready() const { return m_state == Ready; }

signals:
    void stateChanged();
    void libraryLoadedChanged();
    /// Thư viện vừa tải xong (JSON thô): bộ phát tìm cuốn nghe dở gần nhất trong đó.
    void libraryFetched(const QJsonArray &books);
    /// Sự kiện host chuyển tới giao diện ({"event", "detail"}; vỏ Tauri phát thành sự kiện cửa sổ cùng tên): "abook-update" = vừa có bản mới.
    void hostEvent(const QString &name, const QVariant &detail);
    /// Kết quả "Kiểm tra bản mới" ("abook-update-checked" của vỏ Tauri): {state: "found" | "latest" | "failed", message?}.
    void updateChecked(const QVariantMap &detail);

private:
    struct Launch {
        QString python;
        QString folder;
        bool bundled = false;
    };
    bool resolveLaunch(Launch *out, QString *error) const;
    void onStdout();
    void onFinished(int code, QProcess::ExitStatus status);
    void fail(const QString &message);
    void parseReady(const QString &address);

    QProcess *m_proc = nullptr;
    QNetworkAccessManager m_net;
    LibraryModel *m_library;
    State m_state = Starting;
    QString m_message;
    QString m_token;
    int m_port = 0;
    int m_readyMs = 0;
    bool m_quitting = false;
    bool m_libraryLoaded = false;
    QByteArray m_buffer;
    QElapsedTimer m_since;
    QTimer m_startLimit;
    quint64 m_generation = 0;
};
