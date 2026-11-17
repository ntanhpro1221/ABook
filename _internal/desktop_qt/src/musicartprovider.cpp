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
#include <algorithm>
#include <memory>

namespace {
QThreadPool &pool() {
    static auto *p = [] { auto *p = new QThreadPool; p->setMaxThreadCount(3); return p; }();
    return *p;
}

// Keep the shared raster's exact integer pixels without building a data URL on the GUI thread.
QImage generatedImage(const QString &value, const std::shared_ptr<std::atomic_bool> &cancelled) {
    bool valid = false;
    const qlonglong input = value.toLongLong(&valid);
    const int seed = valid && input >= 0 ? int(input % 1638025) : 7;
    constexpr int palettes[5][3][3] = {
        {{24, 46, 48}, {73, 127, 125}, {226, 190, 132}},
        {{48, 37, 59}, {129, 103, 141}, {230, 190, 164}},
        {{48, 40, 30}, {159, 113, 64}, {236, 211, 165}},
        {{29, 42, 64}, {88, 124, 159}, {214, 203, 170}},
        {{46, 51, 38}, {115, 133, 90}, {223, 206, 152}}
    };
    const auto &palette = palettes[seed % 5];
    const int cx = 22 + seed % 51, cy = 20 + (seed / 53) % 39;
    const int radius = 20 + (4 - (seed / 5) % 5) * 3, rr = radius * radius;
    QImage image(96, 96, QImage::Format_RGB32);
    if (image.isNull()) return {};
    for (int y = 0; y < 96; ++y) {
        if (cancelled->load()) return {};
        auto *row = reinterpret_cast<QRgb *>(image.scanLine(y));
        for (int x = 0; x < 96; ++x) {
            const int d = (x - cx) * (x - cx) + (y - cy) * (y - cy);
            const int glow = std::max(0, 96 - d / 90);
            const int wave = 64 + (x - 48) * (x - 48) / 100 - seed % 13;
            int channels[3];
            for (int c = 0; c < 3; ++c) {
                int color = (palette[0][c] * (192 - glow) + palette[1][c] * glow) / 192;
                if (d <= rr) color = (palette[2][c] * 4 + color) / 5;
                if (d > rr + 130 && d < rr + 210) color = (palette[1][c] + color) / 2;
                if (y >= wave) color = (color * 3 + palette[1][c]) / 4;
                channels[c] = color;
            }
            row[x] = qRgb(channels[0], channels[1], channels[2]);
        }
    }
    return image;
}

QImage load(const QString &id, QSize box, const std::shared_ptr<std::atomic_bool> &cancelled) {
    if (cancelled->load()) return {};
    if (id.startsWith(QLatin1String("generated/"))) return generatedImage(id.mid(10), cancelled);
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
