#pragma once
#include <QQuickAsyncImageProvider>

// Content-addressed public artwork, decoded on a three-thread pool.
class MusicArtProvider : public QQuickAsyncImageProvider {
public:
    QQuickImageResponse *requestImageResponse(const QString &id, const QSize &requestedSize) override;
};
