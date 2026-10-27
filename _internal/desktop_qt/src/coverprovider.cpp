#include "coverprovider.h"

#include "backend.h"

#include <QBuffer>
#include <QEventLoop>
#include <QImage>
#include <QImageReader>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QPainter>
#include <QPainterPath>
#include <QRegularExpression>
#include <QPointer>
#include <QQuickImageResponse>
#include <QQuickTextureFactory>
#include <QRunnable>
#include <QThreadPool>
#include <atomic>
#include <memory>

namespace {

QThreadPool &pool() {
    // Riêng cho bìa: tối đa 3 ảnh giải mã cùng lúc để cuộn nhanh không dồn bộ nhớ và không tranh luồng giao diện.
    static QThreadPool *p = [] {
        auto *created = new QThreadPool;
        created->setMaxThreadCount(3);
        created->setThreadPriority(QThread::LowPriority);
        return created;
    }();
    return *p;
}

class CoverResponse : public QQuickImageResponse {
public:
    CoverResponse(QString book, QString version, QSize box, int radius)
        : m_book(std::move(book)), m_version(std::move(version)), m_box(box), m_radius(radius) {
        m_cancelled = std::make_shared<std::atomic_bool>(false);
        QPointer<CoverResponse> self(this);
        auto cancelled = m_cancelled;
        const QString book2 = m_book, version2 = m_version;
        const QSize box2 = m_box;
        const int radius2 = m_radius;
        pool().start([self, cancelled, book2, version2, box2, radius2] {
            QImage image;
            QString error;
            if (!cancelled->load())
                image = fetchAndDecode(book2, version2, box2, radius2, cancelled.get(), &error);
            if (!self)
                return;
            QMetaObject::invokeMethod(self.data(), [self, image, error] {
                if (!self)
                    return;
                self->m_image = image;
                self->m_error = image.isNull() ? (error.isEmpty() ? QStringLiteral("không có ảnh bìa") : error) : QString();
                emit self->finished();
            }, Qt::QueuedConnection);
        });
    }

    QQuickTextureFactory *textureFactory() const override {
        return m_image.isNull() ? nullptr : QQuickTextureFactory::textureFactoryForImage(m_image);
    }
    QString errorString() const override { return m_error; }
    void cancel() override { m_cancelled->store(true); }

private:
    static QImage fetchAndDecode(const QString &book, const QString &version, QSize box, int radius, std::atomic_bool *cancelled, QString *error) {
        const auto endpoint = Backend::endpoint();
        if (endpoint.port <= 0) {
            *error = QStringLiteral("backend chưa sẵn sàng");
            return {};
        }
        // Mỗi luồng giải mã giữ một QNetworkAccessManager riêng (chờ trong vòng lặp cục bộ) - luồng giao diện không dính mạng bìa.
        thread_local QNetworkAccessManager nam;
        // Bìa sách của máy tính đang xem (Thư viện của máy kia, qml/LibraryBooks.js): "peer~<máy>~<mã>" đi qua cầu nối của máy chủ máy này
        static const QRegularExpression peerKey(QStringLiteral("^peer~([0-9a-f]{12})~(.+)$"));
        const QRegularExpressionMatch peer = peerKey.match(book);
        const QString path = peer.hasMatch()
            ? QStringLiteral("/api/peers/%1/studio/media/books/%2/cover?v=%3").arg(peer.captured(1), peer.captured(2), version)
            : QStringLiteral("/media/books/%1/cover?v=%2").arg(book, version);
        QNetworkRequest request(QUrl(QStringLiteral("http://127.0.0.1:%1%2").arg(endpoint.port).arg(path)));
        request.setRawHeader("X-Ebook-Token", endpoint.token);
        request.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
        request.setTransferTimeout(20000);
        std::unique_ptr<QNetworkReply> reply(nam.get(request));
        QEventLoop loop;
        QObject::connect(reply.get(), &QNetworkReply::finished, &loop, &QEventLoop::quit);
        loop.exec();
        if (cancelled->load())
            return {};
        if (reply->error() != QNetworkReply::NoError) {
            *error = reply->errorString();
            return {};
        }
        QByteArray raw = reply->readAll();
        QBuffer buffer(&raw);
        buffer.open(QIODevice::ReadOnly);
        QImageReader reader(&buffer);
        reader.setAutoTransform(true);
        const QSize source = reader.size();
        if (box.isEmpty())
            box = QSize(360, 540);
        if (source.isValid()) {
            // Cho bộ giải mã thu nhỏ ngay khi đọc (JPEG giải mã theo 1/2, 1/4, 1/8): bìa 600x900 -> cỡ ô, không giữ ảnh gốc.
            const double factor = qMax(double(box.width()) / source.width(), double(box.height()) / source.height());
            if (factor < 1.0)
                reader.setScaledSize(QSize(qCeil(source.width() * factor), qCeil(source.height() * factor)));
        }
        const QImage decoded = reader.read();
        if (decoded.isNull()) {
            *error = reader.errorString();
            return {};
        }
        if (cancelled->load())
            return {};
        QImage out(box, QImage::Format_ARGB32_Premultiplied);
        out.fill(Qt::transparent);
        QPainter painter(&out);
        painter.setRenderHints(QPainter::Antialiasing | QPainter::SmoothPixmapTransform);
        QPainterPath clip;
        clip.addRoundedRect(QRectF(QPointF(0, 0), QSizeF(box)), radius, radius);
        painter.setClipPath(clip);
        // Phủ kín khung theo tỉ lệ (cắt giữa nếu ảnh không đúng 2:3).
        const double scale = qMax(double(box.width()) / decoded.width(), double(box.height()) / decoded.height());
        const QSizeF drawn(decoded.width() * scale, decoded.height() * scale);
        painter.drawImage(QRectF((box.width() - drawn.width()) / 2, (box.height() - drawn.height()) / 2, drawn.width(), drawn.height()), decoded);
        painter.end();
        return out;
    }

    QString m_book, m_version;
    QSize m_box;
    int m_radius;
    QImage m_image;
    QString m_error;
    std::shared_ptr<std::atomic_bool> m_cancelled;
};

}  // namespace

QQuickImageResponse *CoverProvider::requestImageResponse(const QString &id, const QSize &requestedSize) {
    // id = <mã>/<phiên bản>/<bán kính>
    const QStringList parts = id.split(QLatin1Char('/'));
    const QString book = parts.value(0), version = parts.value(1, QStringLiteral("0"));
    const int radius = parts.value(2).toInt();
    return new CoverResponse(book, version, requestedSize, radius);
}
