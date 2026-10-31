// Đo bằng điểm ảnh biểu tượng tua 15 giây (qml/SkipGlyph.qml): mọi mực nằm trong ô 24 đơn vị, và giữa nét (cung + mũi tên) với số 15
// luôn còn ít nhất một hàng điểm ảnh trống ở 1x (chủ sách 24-10/26-10: số không được chạm vòng). Dựng bằng bộ vẽ phần mềm, không cần GPU.
#include <QFontDatabase>
#include <QGuiApplication>
#include <QImage>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QtTest>

namespace {
constexpr int kPad = 12;

struct Ink {
    int top = 1 << 20, bottom = -1, left = 1 << 20, right = -1;
    bool any() const { return bottom >= 0; }
};

bool isInk(const QImage &image, int x, int y) {
    const QColor c = image.pixelColor(x, y);
    return c.red() < 250 || c.green() < 250 || c.blue() < 250;   // kể cả viền khử răng cưa mờ: đo khắt khe
}

Ink measure(const QImage &image, const QRect &region = QRect()) {
    Ink ink;
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x) {
            if (!region.isNull() && !region.contains(x, y))
                continue;
            if (!isInk(image, x, y))
                continue;
            ink.top = qMin(ink.top, y);
            ink.bottom = qMax(ink.bottom, y);
            ink.left = qMin(ink.left, x);
            ink.right = qMax(ink.right, x);
        }
    return ink;
}
}  // namespace

class SkipGlyphTests : public QObject {
    Q_OBJECT
    QQmlEngine m_engine;

    QImage render(bool forward, int size, bool stroke, bool digits) {
        const QString dir = QStringLiteral(SKIPGLYPH_QML_DIR);
        const QByteArray source = QByteArray("import QtQuick\nimport \"file:///") + dir.toUtf8() + "\"\nSkipGlyph {}\n";
        QQmlComponent component(&m_engine);
        component.setData(source, QUrl());
        QObject *object = component.create();
        if (!object) {
            qWarning().noquote() << component.errorString();
            return {};
        }
        auto *item = qobject_cast<QQuickItem *>(object);
        item->setProperty("size", size);
        item->setProperty("forward", forward);
        item->setProperty("family", QStringLiteral("Be Vietnam Pro"));
        item->setProperty("showStroke", stroke);
        item->setProperty("showDigits", digits);
        item->setProperty("color", QColor(Qt::black));
        QQuickWindow window;
        window.setColor(Qt::white);
        window.resize(size + 2 * kPad, size + 2 * kPad);
        item->setParentItem(window.contentItem());
        item->setPosition(QPointF(kPad, kPad));
        window.show();
        QImage image;
        const bool rendered = QTest::qWaitFor([&] {
            window.requestUpdate();
            image = window.grabWindow().convertToFormat(QImage::Format_ARGB32);
            return !image.isNull()
                && (!stroke || measure(image, QRect(kPad, kPad, size, qCeil(10.5 * size / 24))).any())
                && (!digits || measure(image, QRect(kPad, kPad + qCeil(11.0 * size / 24), size, size / 2)).any());
        }, 5000);
        if (!rendered) image = {};
        delete item;
        return image;
    }

    void checkVariant(bool forward, int size) {
        const QImage strokeOnly = render(forward, size, true, false);
        const QImage digitsOnly = render(forward, size, false, true);
        const QImage both = render(forward, size, true, true);
        QVERIFY(!strokeOnly.isNull() && !digitsOnly.isNull() && !both.isNull());
        const Ink s = measure(strokeOnly), d = measure(digitsOnly), all = measure(both);
        QVERIFY2(s.any() && d.any(), "nét hoặc số không có mực");
        const qreal unit = size / 24.0;
        // khe giữa mép dưới của nét và mép trên của số, tính bằng điểm ảnh trống ở giữa
        const int gap = d.top - s.bottom - 1;
        qInfo().noquote() << QStringLiteral("%1 %2px: nét y %3..%4, số y %5..%6 (ô %7..%8), khe %9 điểm ảnh, ngang %10..%11")
                                 .arg(forward ? "tới" : "lùi").arg(size).arg(s.top - kPad).arg(s.bottom - kPad).arg(d.top - kPad).arg(d.bottom - kPad)
                                 .arg(0).arg(size - 1).arg(gap).arg(all.left - kPad).arg(all.right - kPad);
        QVERIFY2(gap >= qCeil(unit), qPrintable(QStringLiteral("khe %1 điểm ảnh < %2").arg(gap).arg(qCeil(unit))));
        // mọi mực nằm trong ô
        const QRect box(kPad, kPad, size, size);
        QVERIFY2(all.left >= box.left() && all.right <= box.right() && all.top >= box.top() && all.bottom <= box.bottom(), "mực ra ngoài ô");
        // số nằm giữa ô theo chiều ngang (lệch tối đa 1 điểm ảnh)
        QVERIFY2(qAbs((d.left + d.right) / 2.0 - (kPad + size / 2.0 - 0.5)) <= 1.5 * unit, "số lệch khỏi giữa ô");
    }

private slots:
    void initTestCase() {
        QQuickWindow::setGraphicsApi(QSGRendererInterface::Software);
        // nền offscreen không có phông hệ thống: nạp đúng phông của app để số đo giống app
        for (const char *weight : {"Regular", "Medium", "Bold"})
            QVERIFY(QFontDatabase::addApplicationFont(QStringLiteral(SKIPGLYPH_FONT_DIR "/BeVietnamPro-") + QLatin1String(weight) + QStringLiteral(".ttf")) >= 0);
    }
    void forwardOneX() { checkVariant(true, 24); }
    void backOneX() { checkVariant(false, 24); }
    void forwardTwoX() { checkVariant(true, 48); }
    void backInPlayerBarSize() { checkVariant(false, 28); }
};

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QSG_RHI_BACKEND", "software");
    QGuiApplication app(argc, argv);
    SkipGlyphTests tests;
    return QTest::qExec(&tests, argc, argv);
}

#include "test_skipglyph.moc"
