#include "hostnet.h"

#include "backend.h"
#include "hostcall.h"

#include <QJsonDocument>
#include <QNetworkAccessManager>
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
    if (method != "GET") request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    const QByteArray data = method != "GET" && hasBody ? QJsonDocument(body).toJson(QJsonDocument::Compact) : QByteArray();
    auto *call = HostCall::send(m_net, request, method, data, [done = std::move(done)](int status, const QByteArray &answer, bool timedOut) {
        QJsonObject json;
        if (status) {
            const QJsonDocument document = QJsonDocument::fromJson(answer);
            if (document.isObject())
                json = document.object();
        } else if (timedOut) {
            json.insert(QStringLiteral("reason"), QStringLiteral("timeout"));    // same reason as the host's own timeout: SpeechOut says the voice is not usable
        }
        done(status, json);
    }, this);
    return [call = QPointer<HostCall>(call)] { if (call) call->abort(); };
}
