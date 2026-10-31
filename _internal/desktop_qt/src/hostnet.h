// PlayerNet thật: nói chuyện với host qua QNetworkAccessManager của Backend.
#pragma once

#include "playernet.h"

class QNetworkAccessManager;

class HostNet final : public PlayerNet {
    Q_OBJECT
public:
    explicit HostNet(QNetworkAccessManager *network, QObject *parent = nullptr);
    QUrl audioUrl(const QString &bookId, int chapterId) const override;
    QUrl mediaUrl(const QString &path) const override;
    void request(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool hasBody = true) override;
    std::function<void()> requestCancelable(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool hasBody = true) override;

private:
    QNetworkAccessManager *m_net;
};
