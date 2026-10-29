#include "desktopapi.h"
#include "backend.h"
#include "audioout.h"
#include <QBuffer>
#include <QClipboard>
#include <QCoreApplication>
#include <QGuiApplication>
#include <QImage>
#include <QMimeData>
#include <QDir>
#include <QFileInfo>
#include <QFile>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonValue>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QQmlEngine>
#include <QPointer>

namespace {
AudioOut *sampleOut = nullptr;
DesktopApi *live = nullptr;     // bản đang chạy của QML (singleton): bộ phát nghe thử có trước nó
}
DesktopApi::DesktopApi(QObject *parent) : QObject(parent) { live = this; }
DesktopApi::~DesktopApi() { if (live == this) live = nullptr; }
void DesktopApi::setPreviewOut(AudioOut *out) {
    sampleOut = out;
    if (!out) return;
    QObject::connect(out, &AudioOut::playingChanged, out, [](bool on) { if (on && live) emit live->previewStarted(); });
    QObject::connect(out, &AudioOut::ended, out, [] { if (live) emit live->previewEnded(); });
    QObject::connect(out, &AudioOut::failed, out, [](const QString &reason) { if (live) emit live->previewFailed(reason); });
}
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
        // Qua QJsonValue (không qua QVariant): mảng về thành mảng JS thật, thân rỗng thành null.
        const QJsonValue data = document.isArray() ? QJsonValue(document.array()) : document.isObject() ? QJsonValue(document.object()) : QJsonValue();
        callback.call({QJSValue(status), engine->toScriptValue(data)});
    });
    return id;
}
QString DesktopApi::localPath(const QUrl &file) const { return file.isLocalFile() ? file.toLocalFile() : QString(); }
namespace {
void collect(const QFileInfo &entry, const QString &relative, int depth, QVariantList &out) {
    if (entry.isFile()) {
        QVariantMap file;
        file[QStringLiteral("name")] = entry.fileName();
        file[QStringLiteral("size")] = static_cast<double>(entry.size());
        file[QStringLiteral("path")] = relative;
        file[QStringLiteral("local")] = entry.absoluteFilePath();
        out.append(file);
        return;
    }
    if (!entry.isDir() || depth >= 2) return;      // sâu hơn hai tầng thư mục thì trình tạo sách không lấy
    const auto children = QDir(entry.absoluteFilePath()).entryInfoList(QDir::Files | QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    for (const QFileInfo &child : children) collect(child, relative + QLatin1Char('/') + child.fileName(), depth + 1, out);
}
}
QVariantList DesktopApi::sourceFiles(const QStringList &paths) const {
    QVariantList out;
    for (const QString &path : paths) {
        const QFileInfo info(path);
        if (info.isDir()) collect(info, info.fileName(), 0, out);
        else if (info.isFile()) collect(info, QString(), 0, out);
    }
    return out;
}
QString DesktopApi::fileBase64(const QString &local) const {
    QFile file(local);
    if (!file.open(QIODevice::ReadOnly)) return {};
    return QString::fromLatin1(file.readAll().toBase64());
}
namespace {
// Ảnh -> data URL PNG (cạnh dài tối đa 1600, máy chủ còn thu nhỏ thêm); dùng chung cho file và bộ nhớ tạm
QString pngDataUrl(const QImage &image) {
    if (image.isNull()) return {};
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    if (!image.save(&buffer, "PNG")) return {};
    return QStringLiteral("data:image/png;base64,") + QString::fromLatin1(bytes.toBase64());
}
}
QString DesktopApi::imageData(const QUrl &file) const {
    if (!file.isLocalFile()) return {};
    QImageReader reader(file.toLocalFile());
    reader.setAutoTransform(true);
    const QSize size = reader.size();
    if (size.width() > 1600 || size.height() > 1600) reader.setScaledSize(size.scaled(1600, 1600, Qt::KeepAspectRatio));
    return pngDataUrl(reader.read());
}
QString DesktopApi::clipboardImage() const {
    if (!qobject_cast<QGuiApplication *>(QCoreApplication::instance())) return {};     // bộ thử không cửa sổ: không có bộ nhớ tạm
    const QClipboard *clipboard = QGuiApplication::clipboard();
    if (!clipboard || !clipboard->mimeData() || !clipboard->mimeData()->hasImage()) return {};
    QImage image = qvariant_cast<QImage>(clipboard->mimeData()->imageData());
    if (image.width() > 1600 || image.height() > 1600) image = image.scaled(1600, 1600, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    return pngDataUrl(image);
}
QUrl DesktopApi::mediaUrl(const QString &path) const {
    if (!path.startsWith(QLatin1Char('/'))) return QUrl(path);
    const auto endpoint = Backend::endpoint();
    return QUrl(QStringLiteral("http://127.0.0.1:%1%2%3t=%4").arg(endpoint.port).arg(path,
        path.contains(QLatin1Char('?')) ? QStringLiteral("&") : QStringLiteral("?"), QString::fromLatin1(QUrl::toPercentEncoding(QString::fromLatin1(endpoint.token)))));
}
void DesktopApi::refreshLibrary() { if (Backend::instance()) Backend::instance()->refreshLibrary(); }
