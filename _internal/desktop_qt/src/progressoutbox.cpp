#include "progressoutbox.h"

#include <QFile>
#include <QJsonDocument>
#include <QSaveFile>
#include <QUuid>

QJsonObject ProgressSpot::toJson() const {
    QJsonObject json{{QStringLiteral("bookId"), bookId},       {QStringLiteral("chapterId"), chapterId}, {QStringLiteral("seconds"), seconds},
                     {QStringLiteral("duration"), duration},   {QStringLiteral("savedAt"), double(savedAt)}};
    if (!record.isEmpty())
        json.insert(QStringLiteral("record"), record);
    if (!sessionId.isEmpty())
        json.insert(QStringLiteral("sessionId"), sessionId);
    if (hasRevision)
        json.insert(QStringLiteral("revision"), revision);
    return json;
}

ProgressSpot ProgressSpot::fromJson(const QJsonObject &json) {
    ProgressSpot spot;
    spot.bookId = json.value(QStringLiteral("bookId")).toString();
    spot.chapterId = json.value(QStringLiteral("chapterId")).toInt();
    spot.seconds = json.value(QStringLiteral("seconds")).toDouble();
    spot.duration = json.value(QStringLiteral("duration")).toDouble();
    spot.record = json.value(QStringLiteral("record")).toString();
    spot.savedAt = qint64(json.value(QStringLiteral("savedAt")).toDouble());
    spot.sessionId = json.value(QStringLiteral("sessionId")).toString();
    spot.hasRevision = json.contains(QStringLiteral("revision"));
    spot.revision = json.value(QStringLiteral("revision")).toInt();
    return spot;
}

ProgressOutbox::ProgressOutbox(Send send, std::function<void(const ProgressSpot &)> ack, const QString &storagePath, QObject *parent)
    : QObject(parent), m_send(std::move(send)), m_ack(std::move(ack)), m_path(storagePath) {
    QFile file(m_path);
    if (!m_path.isEmpty() && file.open(QIODevice::ReadOnly)) {
        const QJsonObject saved = QJsonDocument::fromJson(file.readAll()).object();
        for (auto it = saved.begin(); it != saved.end(); ++it) {
            const QJsonObject item = it.value().toObject();
            if (item.value(QStringLiteral("bookId")).toString().isEmpty() || item.value(QStringLiteral("receipt")).toString().isEmpty())
                continue;
            m_pending.insert(it.key(), Pending{ProgressSpot::fromJson(item), item.value(QStringLiteral("receipt")).toString()});
        }
    }
}

void ProgressOutbox::persist() {
    if (m_path.isEmpty())
        return;
    QJsonObject all;
    for (auto it = m_pending.begin(); it != m_pending.end(); ++it) {
        QJsonObject item = it->spot.toJson();
        item.insert(QStringLiteral("receipt"), it->receipt);
        all.insert(it.key(), item);
    }
    QSaveFile file(m_path);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(QJsonDocument(all).toJson(QJsonDocument::Compact));
        file.commit();
    }
}

void ProgressOutbox::put(const ProgressSpot &spot) {
    const QString key = keyOf(spot);
    m_pending.insert(key, Pending{spot, QUuid::createUuid().toString(QUuid::WithoutBraces)});
    persist();
    deliver(key);
}

void ProgressOutbox::flush() {
    const QStringList keys = m_pending.keys();
    for (const QString &key : keys)
        if (!m_running.contains(key))
            deliver(key);
}

void ProgressOutbox::deliver(const QString &key) {
    auto found = m_pending.constFind(key);
    if (found == m_pending.constEnd())
        return;
    if (m_running.contains(key))
        return; // lượt đang gửi xong sẽ gửi tiếp bản mới nhất (tuần tự theo hồ sơ)
    m_running.insert(key, true);
    const Pending sending = *found;
    m_send(sending.spot, [this, key, sending](int status) {
        m_running.remove(key);
        const bool ok = status >= 200 && status < 300;
        auto now = m_pending.constFind(key);
        const bool same = now != m_pending.constEnd() && now->receipt == sending.receipt;
        if (status == 409 && same) {
            m_pending.remove(key);
            persist();
        } else if (ok) {
            if (same) {
                m_pending.remove(key);
                persist();
            }
            if (m_ack)
                m_ack(sending.spot);
        }
        // bản mới hơn đã chen vào trong lúc gửi: gửi nó ngay (kể cả sau lần gửi hỏng thì chờ flush)
        now = m_pending.constFind(key);
        if (now != m_pending.constEnd() && now->receipt != sending.receipt && (ok || status == 409))
            deliver(key);
    });
}
