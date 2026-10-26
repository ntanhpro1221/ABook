#include "desktopapi.h"
#include "backend.h"
#include "audioout.h"
#include <QBuffer>
#include <QFile>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QQmlEngine>
#include <QPointer>

DesktopApi::DesktopApi(QObject *parent) : QObject(parent) {}
namespace { AudioOut *sampleOut = nullptr; }
void DesktopApi::setPreviewOut(AudioOut *out) { sampleOut = out; }
void DesktopApi::preview(const QString &path) { if (sampleOut) { sampleOut->stop(); sampleOut->load(mediaUrl(path), 0); sampleOut->play(); } }
void DesktopApi::stopPreview() { if (sampleOut) sampleOut->stop(); }
QString DesktopApi::thirdParty() const {
    QFile file(QStringLiteral(":/legal/THIRD_PARTY.md"));
    if (!file.open(QIODevice::ReadOnly)) return {};
    QStringList shown;
    bool skip = false;
    for (const auto &line : QString::fromUtf8(file.readAll()).split(QLatin1Char('\n'))) {
        if (line.startsWith(QStringLiteral("## "))) skip = line.contains(QStringLiteral("Ghi chú cho người bảo trì"));
        if (!skip && !line.startsWith(QStringLiteral("# "))) shown.append(line);
    }
    return shown.join(QLatin1Char('\n'));
}
void DesktopApi::cancel(int id) { if (auto *reply = m_pending.take(id)) reply->abort(); }
int DesktopApi::request(const QString &method, const QString &path, const QJSValue &body, const QJSValue &done) {
    const auto endpoint = Backend::endpoint();
    if (!path.startsWith(QStringLiteral("/api/")) || !endpoint.port) {
        QJSValue callback = done;
        callback.call({QJSValue(0), QJSValue(QJSValue::NullValue)});
        return 0;
    }
    QNetworkRequest request(QUrl(QStringLiteral("http://127.0.0.1:%1%2").arg(endpoint.port).arg(path)));
    request.setRawHeader("X-Ebook-Token", endpoint.token);
    request.setTransferTimeout(30000);
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    const QByteArray bytes = body.isNull() || body.isUndefined() ? QByteArray() : QJsonDocument::fromVariant(body.toVariant()).toJson(QJsonDocument::Compact);
    auto *reply = m_net.sendCustomRequest(request, method.toLatin1(), bytes);
    const int id = ++m_next;
    m_pending.insert(id, reply);
    const QPointer<QJSEngine> engine = qjsEngine(this);
    connect(reply, &QNetworkReply::finished, this, [this, id, reply, engine, done]() mutable {
        const bool active = m_pending.remove(id) > 0;
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const auto document = QJsonDocument::fromJson(reply->readAll());
        reply->deleteLater();
        if (!active || !engine || !done.isCallable()) return;
        QJSValue callback = done;
        callback.call({QJSValue(status), engine->toScriptValue(document.toVariant())});
    });
    return id;
}
QString DesktopApi::localPath(const QUrl &file) const { return file.isLocalFile() ? file.toLocalFile() : QString(); }
QString DesktopApi::imageData(const QUrl &file) const {
    if (!file.isLocalFile()) return {};
    QImageReader reader(file.toLocalFile());
    reader.setAutoTransform(true);
    const QSize size = reader.size();
    if (size.width() > 1600 || size.height() > 1600) reader.setScaledSize(size.scaled(1600, 1600, Qt::KeepAspectRatio));
    QImage image = reader.read();
    if (image.isNull()) return {};
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    if (!image.save(&buffer, "PNG")) return {};
    return QStringLiteral("data:image/png;base64,") + QString::fromLatin1(bytes.toBase64());
}
QUrl DesktopApi::mediaUrl(const QString &path) const {
    if (!path.startsWith(QLatin1Char('/'))) return QUrl(path);
    const auto endpoint = Backend::endpoint();
    return QUrl(QStringLiteral("http://127.0.0.1:%1%2%3t=%4").arg(endpoint.port).arg(path,
        path.contains(QLatin1Char('?')) ? QStringLiteral("&") : QStringLiteral("?"), QString::fromLatin1(QUrl::toPercentEncoding(QString::fromLatin1(endpoint.token)))));
}
void DesktopApi::refreshLibrary() { if (Backend::instance()) Backend::instance()->refreshLibrary(); }
