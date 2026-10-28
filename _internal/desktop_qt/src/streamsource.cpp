#include "streamsource.h"
#include <QFile>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QRegularExpression>
#include <QTemporaryFile>
#include <algorithm>
#include <map>
#include <mutex>

namespace { constexpr qint64 PAGE = 128 * 1024; using Guard = std::lock_guard<std::mutex>; }
struct RangeSource::Impl {
    mutable std::mutex mutex;
    QUrl url;
    QFile local;
    QTemporaryFile spool;
    QNetworkAccessManager network;
    QNetworkReply *reply = nullptr;
    std::map<qint64, qint64> ranges; // disjoint [begin,end), compressed data stays on disk
    qint64 length = -1, pending = -1, responseAt = 0, responseEnd = -1, wanted = 0;
    bool ignored = false, headers = false;
    QString error;
    std::function<void()> ready;
    void insert(qint64 begin, qint64 end) {
        auto it = ranges.lower_bound(begin);
        if (it != ranges.begin() && std::prev(it)->second >= begin) --it;
        while (it != ranges.end() && it->first <= end) {
            begin = std::min(begin, it->first); end = std::max(end, it->second); it = ranges.erase(it);
        }
        ranges[begin] = end;
    }
};
RangeSource::RangeSource(const QUrl &url, std::function<void()> ready) : d(new Impl) {
    d->url = url; d->ready = std::move(ready);
    if (url.isLocalFile()) {
        d->local.setFileName(url.toLocalFile());
        if (!d->local.open(QIODevice::ReadOnly)) d->error = d->local.errorString();
        else d->length = d->local.size();
    } else if (!d->spool.open()) d->error = d->spool.errorString();
}
RangeSource::~RangeSource() {
    if (d->reply) { d->reply->disconnect(this); d->reply->abort(); }
}
qint64 RangeSource::size() const { Guard lock(d->mutex); return d->length; }
QString RangeSource::error() const { Guard lock(d->mutex); return d->error; }
QByteArray RangeSource::read(qint64 offset, qint64 count) {
    Guard lock(d->mutex);
    if (offset < 0 || count <= 0 || !d->error.isEmpty()) return {};
    if (d->length >= 0) count = std::min(count, std::max<qint64>(0, d->length - offset));
    if (!count) return {};
    if (d->local.isOpen()) {
        if (!d->local.seek(offset)) { d->error = d->local.errorString(); return {}; }
        auto bytes = d->local.read(count);
        if (bytes.size() != count) d->error = d->local.errorString().isEmpty() ? QStringLiteral("Truncated audio file") : d->local.errorString();
        return bytes;
    }
    auto it = d->ranges.upper_bound(offset);
    qint64 missingAt = offset;
    if (it != d->ranges.begin()) {
        --it;
        if (it->first <= offset && it->second >= offset + count) {
            d->spool.seek(offset); return d->spool.read(count);
        }
        if (it->first <= offset && it->second > offset) missingAt = it->second;
    }
    if (d->pending < 0) {
        d->pending = missingAt;
        QMetaObject::invokeMethod(this, [this, missingAt] { request(missingAt); }, Qt::QueuedConnection);
    }
    return {};
}
void RangeSource::request(qint64 offset) {
    {
        Guard lock(d->mutex);
        d->pending = -1;
        if (d->reply || !d->error.isEmpty()) return;
        d->headers = false; d->wanted = offset; d->responseAt = offset; d->responseEnd = -1;
    }
    QNetworkRequest request(d->url);
    request.setRawHeader("Range", "bytes=" + QByteArray::number(offset) + '-' + QByteArray::number(offset + PAGE - 1));
    request.setRawHeader("Accept-Encoding", "identity");
    request.setTransferTimeout(30000);
    auto *reply = d->network.get(request);
    d->reply = reply;
    reply->setReadBufferSize(PAGE);
    auto consume = [this, reply] {
        Guard lock(d->mutex);
        if (!d->headers) {
            const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            if (!status) return;
            d->headers = true;
            if (status == 206) {
                static const QRegularExpression pattern(QStringLiteral("^bytes (\\d+)-(\\d+)/(\\d+)$"));
                const auto match = pattern.match(QString::fromLatin1(reply->rawHeader("Content-Range")));
                if (!match.hasMatch() || match.captured(1).toLongLong() != d->wanted ||
                    match.captured(2).toLongLong() < d->wanted || match.captured(3).toLongLong() <= match.captured(2).toLongLong()) {
                    d->error = QStringLiteral("Invalid HTTP audio Content-Range"); return;
                }
                const qint64 total = match.captured(3).toLongLong();
                if (d->length >= 0 && d->length != total) { d->error = QStringLiteral("Audio changed during playback"); return; }
                d->length = total; d->responseEnd = match.captured(2).toLongLong() + 1;
            } else if (status == 200) {
                // A server ignoring Range sends the WHOLE object. Spool from zero, never append at the requested offset.
                d->ignored = true; d->responseAt = 0;
                bool ok = false; const auto total = reply->header(QNetworkRequest::ContentLengthHeader).toLongLong(&ok);
                if (ok) { d->length = total; d->responseEnd = total; }
            } else { d->error = QStringLiteral("HTTP audio error %1").arg(status); return; }
        }
        while (reply->bytesAvailable() && d->error.isEmpty()) {
            const auto bytes = reply->read(PAGE);
            if (d->responseEnd >= 0 && d->responseAt + bytes.size() > d->responseEnd) { d->error = QStringLiteral("HTTP audio exceeds range"); break; }
            if (!d->spool.seek(d->responseAt) || d->spool.write(bytes) != bytes.size()) { d->error = d->spool.errorString(); break; }
            d->insert(d->responseAt, d->responseAt + bytes.size()); d->responseAt += bytes.size();
        }
    };
    connect(reply, &QNetworkReply::readyRead, this, [this, consume] { consume(); d->ready(); });
    connect(reply, &QNetworkReply::finished, this, [this, reply, consume] {
        consume();
        {
            Guard lock(d->mutex);
            if (d->error.isEmpty() && reply->error() != QNetworkReply::NoError) d->error = reply->errorString();
            if (d->error.isEmpty() && d->responseEnd >= 0 && d->responseAt != d->responseEnd) d->error = QStringLiteral("Truncated HTTP audio range");
            if (d->ignored && d->length < 0) d->length = d->responseAt;
            d->reply = nullptr;
        }
        reply->deleteLater(); d->ready();
    });
}
