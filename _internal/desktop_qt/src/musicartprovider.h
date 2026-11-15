#pragma once
#include <QQuickAsyncImageProvider>

// Public artwork and canonical generated tiles, decoded on a three-thread pool.
class MusicArtProvider : public QQuickAsyncImageProvider {
public:
    QQuickImageResponse *requestImageResponse(const QString &id, const QSize &requestedSize) override;
};
