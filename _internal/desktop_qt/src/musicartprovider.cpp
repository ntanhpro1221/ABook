#include "musicartprovider.h"
#include <QCryptographicHash>
#include <QDir>
#include <QEventLoop>
#include <QFile>
#include <QImageReader>
#include <QBuffer>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QPointer>
#include <QQuickTextureFactory>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <QThreadPool>
#include <QTimer>
#include <atomic>
#include <memory>

namespace {
QThreadPool &pool() {
    static auto *p = [] { auto *p = new QThreadPool; p->setMaxThreadCount(3); return p; }();
    return *p;
}
QImage load(const QString &id, QSize box, const std::shared_ptr<std::atomic_bool> &cancelled) {
    if (cancelled->load()) return {};
    const int slash = id.indexOf(QLatin1Char('/'));
    const QByteArray sha = id.left(slash).toLatin1();
    const QUrl url(QUrl::fromPercentEncoding(id.mid(slash + 1).toUtf8()));
    if (slash != 40 || !QRegularExpression(QStringLiteral("^[0-9a-f]{40}$")).match(QString::fromLatin1(sha)).hasMatch()
        || url.scheme() != QStringLiteral("https")) return {};
    const QString folder = QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + QStringLiteral("/music-art");
    const QString path = folder + QLatin1Char('/') + QString::fromLatin1(sha) + QStringLiteral(".jpg");
    auto valid = [&](const QByteArray &bytes) {
        return !bytes.isEmpty() && bytes.size() <= 512 * 1024 && QCryptographicHash::hash(bytes, QCryptographicHash::Sha1).toHex() == sha;
    };
    QByteArray bytes;
    QFile file(path);
    if (file.open(QIODevice::ReadOnly) && file.size() <= 512 * 1024) bytes = file.readAll();
    if (!valid(bytes)) {
        if (cancelled->load()) return {};
        QNetworkAccessManager nam;
        QNetworkRequest request(url);
        request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
        request.setTransferTimeout(6000);
        auto *reply = nam.get(request);
        QEventLoop loop;
        QTimer timer;
        timer.setSingleShot(true);
        bytes.clear();
        QObject::connect(reply, &QNetworkReply::readyRead, &loop, [&] {
            bytes += reply->readAll();
            if (bytes.size() > 512 * 1024) reply->abort();
        });
        QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
        QObject::connect(&timer, &QTimer::timeout, &loop, [&] { reply->abort(); loop.quit(); });
        timer.start(12000);
        loop.exec();
        bytes += reply->readAll();
        if (reply->error() != QNetworkReply::NoError || !valid(bytes)) return {};
        QDir().mkpath(folder);
        QSaveFile output(path);
        if (output.open(QIODevice::WriteOnly)) { output.write(bytes); output.commit(); }
    }
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::ReadOnly);
    QImageReader reader(&buffer);
    const QSize dimensions = reader.size();
    if (dimensions.width() < 1 || dimensions.height() < 1 || dimensions.width() > 512 || dimensions.height() > 512) return {};
    if (box.isValid()) reader.setScaledSize(dimensions.scaled(box.boundedTo(QSize(512, 512)), Qt::KeepAspectRatio));
    return reader.read();
}

class Response : public QQuickImageResponse {
public:
    Response(QString id, QSize box) {
        QPointer<Response> self(this);
        auto flag = cancelled;
        pool().start([self, id, box, flag] {
            const QImage result = load(id, box, flag);
            if (self) QMetaObject::invokeMethod(self, [self, result] {
                if (self) { self->image = result; emit self->finished(); }
            }, Qt::QueuedConnection);
        });
    }
    QQuickTextureFactory *textureFactory() const override { return image.isNull() ? nullptr : QQuickTextureFactory::textureFactoryForImage(image); }
    void cancel() override { cancelled->store(true); }
private:
    QImage image;
    std::shared_ptr<std::atomic_bool> cancelled = std::make_shared<std::atomic_bool>(false);
};
}

QQuickImageResponse *MusicArtProvider::requestImageResponse(const QString &id, const QSize &size) { return new Response(id, size); }
