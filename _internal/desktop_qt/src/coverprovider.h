// image://cover/<mã sách>/<phiên bản>/<bán kính góc px>  -  ảnh bìa tải từ host, giải mã NGOÀI luồng giao diện đúng cỡ hiển thị
// (sourceSize của Image, đã nhân tỉ lệ màn hình), cắt theo khung và bo góc ngay lúc giải mã: QML hiện thẳng, không phải
// cắt / che bo góc lúc vẽ.
#pragma once

#include <QQuickAsyncImageProvider>

class CoverProvider : public QQuickAsyncImageProvider {
public:
    QQuickImageResponse *requestImageResponse(const QString &id, const QSize &requestedSize) override;
};
