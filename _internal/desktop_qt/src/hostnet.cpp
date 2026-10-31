#include "hostnet.h"

#include "backend.h"

#include <QJsonDocument>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPointer>

HostNet::HostNet(QNetworkAccessManager *network, QObject *parent) : PlayerNet(parent), m_net(network) {}

QUrl HostNet::audioUrl(const QString &bookId, int chapterId) const {
    const Backend::Endpoint endpoint = Backend::endpoint();
    return QUrl(QStringLiteral("http://127.0.0.1:%1/media/books/%2/chapters/%3?t=%4")
                    .arg(endpoint.port)
                    .arg(bookId)
                    .arg(chapterId)
                    .arg(QString::fromLatin1(endpoint.token)));
}

QUrl HostNet::mediaUrl(const QString &path) const {
    const Backend::Endpoint endpoint = Backend::endpoint();
    return QUrl(QStringLiteral("http://127.0.0.1:%1%2%3t=%4")
                    .arg(endpoint.port)
                    .arg(path, path.contains(QLatin1Char('?')) ? QStringLiteral("&") : QStringLiteral("?"),
                         QString::fromLatin1(QUrl::toPercentEncoding(QString::fromLatin1(endpoint.token)))));
}

void HostNet::request(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool hasBody) {
    requestCancelable(method, path, body, std::move(done), hasBody);
}
std::function<void()> HostNet::requestCancelable(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool hasBody) {
    const Backend::Endpoint endpoint = Backend::endpoint();
    if (!endpoint.port) {
        done(0, {});
        return {};
    }
    QNetworkRequest request(QUrl(QStringLiteral("http://127.0.0.1:%1%2").arg(endpoint.port).arg(path)));
    request.setRawHeader("X-Ebook-Token", endpoint.token);
    request.setTransferTimeout(path == QLatin1String("/api/readaloud/clip") ? 0 : 30'000);
    QNetworkReply *reply = nullptr;
    if (method == "GET") {
        reply = m_net->get(request);
    } else {
        request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
        const QByteArray data = hasBody ? QJsonDocument(body).toJson(QJsonDocument::Compact) : QByteArray();
        reply = m_net->sendCustomRequest(request, method, data);
    }
    connect(reply, &QNetworkReply::finished, this, [reply, done = std::move(done)] {
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        QJsonObject json;
        if (status) {
            const QJsonDocument document = QJsonDocument::fromJson(reply->readAll());
            if (document.isObject())
                json = document.object();
        }
        reply->deleteLater();
        done(status, json);
    });
    return [reply = QPointer<QNetworkReply>(reply)] { if (reply && !reply->isFinished()) reply->abort(); };
}
