#include "shadowprovider.h"

#include <QImage>
#include <algorithm>
#include <cmath>
#include <vector>

namespace {

// Một lớp box-shadow CSS: 0 offsetY blur spread rgb(r g b / alpha).
struct Layer { double offsetY, blur, spread, alpha; };
struct Spec { std::vector<Layer> layers; QRgb color; };

// ui/src/styles.css: --shadow (card) và --shadow-lg (float), sáng / tối.
Spec spec(const QString &kind, bool dark) {
    if (kind == QLatin1String("card"))
        return dark ? Spec{{{1, 2, 0, 0.4}, {10, 30, -14, 0.7}}, qRgb(0, 0, 0)}
                    : Spec{{{1, 2, 0, 0.06}, {8, 24, -12, 0.16}}, qRgb(20, 24, 29)};
    return dark ? Spec{{{30, 80, -20, 0.75}}, qRgb(0, 0, 0)} : Spec{{{24, 64, -24, 0.35}}, qRgb(20, 24, 29)};
}

double phi(double z) { return 0.5 * std::erfc(-z / std::sqrt(2.0)); }

// Khoảng cách có dấu tới hình chữ nhật bo góc tâm (cx, cy), nửa cạnh (hx, hy), bán kính r.
double roundedDistance(double x, double y, double cx, double cy, double hx, double hy, double r) {
    const double qx = std::abs(x - cx) - (hx - r), qy = std::abs(y - cy) - (hy - r);
    const double ox = std::max(qx, 0.0), oy = std::max(qy, 0.0);
    return std::sqrt(ox * ox + oy * oy) + std::min(std::max(qx, qy), 0.0) - r;
}

}  // namespace

QImage ShadowProvider::requestImage(const QString &id, QSize *size, const QSize &) {
    const QStringList parts = id.split(QLatin1Char('/'));
    if (parts.size() != 6) return {};
    const Spec s = spec(parts[0], parts[1] == QLatin1String("1"));
    const double w = std::max(0.0, parts[2].toDouble()), h = std::max(0.0, parts[3].toDouble());
    const double radius = std::max(0.0, parts[4].toDouble()), pad = std::max(0.0, parts[5].toDouble());
    double smallest = 1e9;
    for (const Layer &layer : s.layers) smallest = std::min(smallest, layer.blur / 2);
    const int step = std::clamp(int(smallest / 4), 1, 4);               // sigma >= 16 thì 1/4 độ phân giải vẫn mượt
    const double fullW = w + 2 * pad, fullH = h + 2 * pad;
    const int iw = std::max(1, int(std::ceil(fullW / step))), ih = std::max(1, int(std::ceil(fullH / step)));
    QImage image(iw, ih, QImage::Format_ARGB32_Premultiplied);
    std::vector<double> clear(size_t(iw) * ih, 1.0);                     // phần KHÔNG bị che sau mọi lớp (CSS chồng lớp "over")
    for (const Layer &layer : s.layers) {
        const double sigma = layer.blur / 2;
        const double x0 = pad - layer.spread, x1 = pad + w + layer.spread;
        const double y0 = pad - layer.spread + layer.offsetY, y1 = pad + h + layer.spread + layer.offsetY;
        const double r = std::max(0.0, radius + layer.spread);
        const double hx = std::max(0.0, (x1 - x0) / 2), hy = std::max(0.0, (y1 - y0) / 2);
        const double cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, rr = std::min({r, hx, hy});
        std::vector<double> across(iw), down(ih);
        for (int i = 0; i < iw; ++i) { const double x = (i + 0.5) * fullW / iw; across[i] = std::max(0.0, phi((x - x0) / sigma) - phi((x - x1) / sigma)); }
        for (int j = 0; j < ih; ++j) { const double y = (j + 0.5) * fullH / ih; down[j] = std::max(0.0, phi((y - y0) / sigma) - phi((y - y1) / sigma)); }
        for (int j = 0; j < ih; ++j) {
            const double y = (j + 0.5) * fullH / ih;
            for (int i = 0; i < iw; ++i) {
                const double x = (i + 0.5) * fullW / iw;
                // Gauss của hình chữ nhật sắc tách được thành hai chiều (đúng cả khi khung hẹp hơn bóng); góc bo thì lấy theo
                // khoảng cách - đúng khi sigma nhỏ so với góc. Lấy giá trị nhỏ hơn: hình bo góc nằm trong hình chữ nhật sắc.
                const double rect = across[i] * down[j];
                const double rounded = phi(-roundedDistance(x, y, cx, cy, hx, hy, rr) / sigma);
                clear[size_t(j) * iw + i] *= 1.0 - layer.alpha * std::min(rect, rounded);
            }
        }
    }
    for (int j = 0; j < ih; ++j) {
        auto *row = reinterpret_cast<QRgb *>(image.scanLine(j));
        for (int i = 0; i < iw; ++i) {
            const double a = 1.0 - clear[size_t(j) * iw + i];
            row[i] = qRgba(int(qRed(s.color) * a + 0.5), int(qGreen(s.color) * a + 0.5), int(qBlue(s.color) * a + 0.5), int(255 * a + 0.5));
        }
    }
    if (size) *size = image.size();
    return image;
}
