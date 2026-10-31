// Một dòng JSON host gửi lên vỏ qua stdout (webui/host.py Channel; vỏ Tauri đọc ở shell/src-tauri/src/main.rs). Tách khỏi Backend để thử
// được không cần tiến trình host:
//   {"ready": "http://127.0.0.1:PORT/?t=MÃ"}       host đã nghe
//   {"event": "<tên>", "detail": ...}               sự kiện chuyển tới giao diện ("abook-update": đọc lại /api/app, "abook-opened"...)
//   {"check_update": true}                          người dùng bấm "Kiểm tra bản mới": vỏ kiểm rồi báo "abook-update-checked"
//   {"install_update": true}                        người dùng bấm "Cập nhật ABook"
#pragma once

#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <QVariant>
#include <QVariantMap>

namespace HostMessage {

enum class Kind { None, Ready, Event, CheckUpdate, InstallUpdate };

struct Message {
    Kind kind = Kind::None;
    QString address; // Ready
    QString event;   // Event
    QVariant detail; // Event
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
    } else if (message.contains(QStringLiteral("install_update"))) {
        out.kind = Kind::InstallUpdate;
    } else if (message.contains(QStringLiteral("check_update"))) {
        out.kind = Kind::CheckUpdate;
    }
    return out;
}

/// Kết quả "Kiểm tra bản mới" của vỏ Qt (sự kiện "abook-update-checked": {state, message?}). Vỏ Qt chưa có bộ cập nhật gói đã ký như vỏ Tauri
/// (tauri-plugin-updater): nói thẳng bằng đúng câu máy chủ dùng cho bản không tự cập nhật (server.py check_for_update), không im để nút chờ
/// 45 giây rồi đổ cho mạng, cũng không nói "bản mới nhất" khi chưa hề kiểm.
inline QVariantMap updateCheckedWithoutUpdater() {
    return {{QStringLiteral("state"), QStringLiteral("failed")}, {QStringLiteral("message"), QStringLiteral("Bản chạy từ mã nguồn không tự cập nhật")}};
}

} // namespace HostMessage
