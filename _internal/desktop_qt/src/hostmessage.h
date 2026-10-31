// Một dòng JSON host gửi lên vỏ qua stdout (webui/host.py Channel; vỏ Tauri đọc ở shell/src-tauri/src/main.rs). Tách khỏi Backend để thử
// được không cần tiến trình host:
//   {"ready": "http://127.0.0.1:PORT/?t=MÃ"}       host đã nghe
//   {"event": "<tên>", "detail": ...}               sự kiện chuyển tới giao diện ("abook-update": đọc lại /api/app, "abook-opened"...)
//   {"check_update": true}                          người dùng bấm "Kiểm tra bản mới": vỏ kiểm rồi báo "abook-update-checked"
//   {"install_update": true}                        người dùng bấm "Cập nhật ABook"
//   {"run_installer": "<exe>", "args": [...]}       host (--self-update, webui/updater.py) đã tải và kiểm chữ ký bộ cài: vỏ chạy nó rồi thoát
// Host chạy với --self-update thì tự trả lời "check_update"/"install_update" và báo "abook-update-checked" bằng {"event"}.
#pragma once

#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantMap>

namespace HostMessage {

enum class Kind { None, Ready, Event, CheckUpdate, InstallUpdate, RunInstaller };

struct Message {
    Kind kind = Kind::None;
    QString address; // Ready
    QString event;   // Event
    QVariant detail; // Event
    QString installer;      // RunInstaller
    QStringList arguments;  // RunInstaller
};

inline Message parse(const QByteArray &line) {
    Message out;
    const QJsonObject message = QJsonDocument::fromJson(line).object();
    const QString address = message.value(QStringLiteral("ready")).toString();
    if (!address.isEmpty()) {
        out.kind = Kind::Ready;
        out.address = address;
    } else if (message.value(QStringLiteral("event")).isString()) {
        out.kind = Kind::Event;
        out.event = message.value(QStringLiteral("event")).toString();
        out.detail = message.value(QStringLiteral("detail")).toVariant();
    } else if (message.value(QStringLiteral("run_installer")).isString()) {
        out.installer = message.value(QStringLiteral("run_installer")).toString();
        for (const QJsonValue &argument : message.value(QStringLiteral("args")).toArray())
            out.arguments << argument.toString();
        if (!out.installer.isEmpty())
            out.kind = Kind::RunInstaller;
    } else if (message.contains(QStringLiteral("install_update"))) {
        out.kind = Kind::InstallUpdate;
    } else if (message.contains(QStringLiteral("check_update"))) {
        out.kind = Kind::CheckUpdate;
    }
    return out;
}

/// Kết quả "Kiểm tra bản mới" khi host chạy KHÔNG có --self-update (bản dev, như vỏ Tauri bản dev không kiểm): nói thẳng bằng đúng câu máy chủ dùng cho bản không tự cập nhật (server.py check_for_update), không im để nút chờ
/// 45 giây rồi đổ cho mạng, cũng không nói "bản mới nhất" khi chưa hề kiểm.
inline QVariantMap updateCheckedWithoutUpdater() {
    return {{QStringLiteral("state"), QStringLiteral("failed")}, {QStringLiteral("message"), QStringLiteral("Bản chạy từ mã nguồn không tự cập nhật")}};
}

} // namespace HostMessage
