// image://shadow/<kind>/<dark 0|1>/<rộng>/<cao>/<bán kính>/<lề>  -  bóng mềm của lớp nổi, đúng token --shadow / --shadow-lg
// của bản web (ui/src/styles.css), tính bằng Gauss cho ĐÚNG cỡ khung: không còn các dải Rectangle chồng thành bậc thang.
// Ảnh gồm khung ở giữa và `lề` px mỗi phía; Shadow.qml đặt nó dưới khung. Bóng rộng (lg) tính ở 1/4 độ phân giải rồi kéo
// giãn mượt - Gauss sigma 32 không có chi tiết nào mất - nên mở một hộp thoại tốn dưới 1 ms.
#pragma once

#include <QQuickImageProvider>

class ShadowProvider : public QQuickImageProvider {
public:
    ShadowProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requestedSize) override;
};
