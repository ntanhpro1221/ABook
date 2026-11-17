#include <QCryptographicHash>
#include <QFile>
#include <QJSEngine>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QtTest>
#include "../src/musicartprovider.h"
#include <QBuffer>
#include <QDir>
#include <QImage>
#include <QQuickTextureFactory>
#include <QStandardPaths>

class MusicArtTests : public QObject {
    Q_OBJECT
private slots:
    void generatedTilesMatchCanonicalPixels() {
        QFile file(QStringLiteral(MUSICART_DIR "/../tests/fixtures/music_art/cases.json"));
        QVERIFY(file.open(QIODevice::ReadOnly));
        const auto cases = QJsonDocument::fromJson(file.readAll()).array();
        QCOMPARE(cases.size(), 8);
        MusicArtProvider provider;
        for (const auto &entry : cases) {
            const auto item = entry.toObject();
            std::unique_ptr<QQuickImageResponse> response(provider.requestImageResponse(
                QStringLiteral("generated/%1").arg(item.value("seed").toInt()), QSize(40, 40)));
            QSignalSpy ready(response.get(), &QQuickImageResponse::finished);
            QTRY_COMPARE_WITH_TIMEOUT(ready.count(), 1, 3000);
            std::unique_ptr<QQuickTextureFactory> texture(response->textureFactory());
            QVERIFY(texture);
            const auto image = texture->image();
            QCOMPARE(image.size(), QSize(96, 96));
            QByteArray rgb;
            rgb.reserve(96 * 96 * 3);
            for (int y = 0; y < image.height(); ++y) {
                for (int x = 0; x < image.width(); ++x) {
                    const auto pixel = image.pixel(x, y);
                    QCOMPARE(qAlpha(pixel), 255);
                    rgb.append(char(qRed(pixel))); rgb.append(char(qGreen(pixel))); rgb.append(char(qBlue(pixel)));
                }
            }
            QCOMPARE(QString::fromLatin1(QCryptographicHash::hash(rgb, QCryptographicHash::Sha256).toHex()),
                     item.value("rgbSha256").toString());
        }
    }
    void verifiedDiskImageWorksWithoutASourceConnection() {
        QStandardPaths::setTestModeEnabled(true);
        QImage image(96, 96, QImage::Format_RGB32);
        image.fill(QColor(73, 127, 125));
        QByteArray bytes;
        QBuffer buffer(&bytes);
        QVERIFY(buffer.open(QIODevice::WriteOnly));
        QVERIFY(image.save(&buffer, "JPEG"));
        const auto sha = QCryptographicHash::hash(bytes, QCryptographicHash::Sha1).toHex();
        const auto folder = QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + QStringLiteral("/music-art");
        QVERIFY(QDir().mkpath(folder));
        QFile file(folder + QLatin1Char('/') + QString::fromLatin1(sha) + QStringLiteral(".jpg"));
        QVERIFY(file.open(QIODevice::WriteOnly));
        QCOMPARE(file.write(bytes), bytes.size()); file.close();
        MusicArtProvider provider;
        std::unique_ptr<QQuickImageResponse> response(provider.requestImageResponse(QString::fromLatin1(sha) + QLatin1Char('/') + QString::fromLatin1(QUrl::toPercentEncoding(QStringLiteral("https://artwork.invalid/cover.jpg"))), QSize(40, 40)));
        QSignalSpy ready(response.get(), &QQuickImageResponse::finished);
        QTRY_COMPARE_WITH_TIMEOUT(ready.count(), 1, 3000);
        std::unique_ptr<QQuickTextureFactory> texture(response->textureFactory());
        QVERIFY(texture);
        QCOMPARE(texture->image().size(), QSize(40, 40));
    }
    void canonicalRgbAndBmp() {
        QFile source(QStringLiteral(MUSICART_DIR "/qml/MusicArtRaster.mjs"));
        QVERIFY(source.open(QIODevice::ReadOnly));
        QJSEngine engine;
        QString js = QString::fromUtf8(source.readAll());
        js.replace(QStringLiteral("export function"), QStringLiteral("function"));
        QVERIFY(!engine.evaluate(js).isError());
        QFile file(QStringLiteral(MUSICART_DIR "/../tests/fixtures/music_art/cases.json"));
        QVERIFY(file.open(QIODevice::ReadOnly));
        const auto cases = QJsonDocument::fromJson(file.readAll()).array();
        QCOMPARE(cases.size(), 8);
        for (const auto &entry : cases) {
            const auto item = entry.toObject();
            const auto encoded = engine.globalObject().property(QStringLiteral("base64")).call({item.value("seed").toInt()}).toString().toLatin1();
            QCOMPARE(QString::fromLatin1(QCryptographicHash::hash(QByteArray::fromBase64(encoded), QCryptographicHash::Sha256).toHex()), item.value("bmpSha256").toString());
            QCOMPARE(engine.globalObject().property(QStringLiteral("seedOf")).call({item.value("link").toString(), engine.toScriptValue(item.value("info").toObject().toVariantMap())}).toInt(), item.value("seed").toInt());
            for (const auto &kind : {QStringLiteral("rgb"), QStringLiteral("bmp")}) {
                const QJSValue result = engine.globalObject().property(kind).call({item.value("seed").toInt()});
                QVERIFY2(!result.isError(), qPrintable(result.toString()));
                QByteArray bytes;
                const int length = result.property(QStringLiteral("length")).toInt();
                for (int at = 0; at < length; ++at) bytes.append(char(result.property(at).toInt()));
                QCOMPARE(QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex()), item.value(kind + QStringLiteral("Sha256")).toString());
            }
        }
    }
};
QTEST_MAIN(MusicArtTests)
#include "test_musicart.moc"
