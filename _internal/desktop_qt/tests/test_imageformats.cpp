// WebP must decode on the desktop: every voice portrait (qrc /voiceavatars) and every character avatar of a book is WebP.
// 0.4.173: the Qt 6.11.3 SDK had no qtimageformats, so qwebp.dll was missing and every portrait quietly showed its
// initial-letter fallback while all other tests stayed green. These checks fail on an SDK (or a dist) without the plugin.
#include <QDir>
#include <QGuiApplication>
#include <QImage>
#include <QImageReader>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QtTest>

class ImageFormatTests : public QObject {
    Q_OBJECT
private slots:
    void webpIsASupportedFormat() {
        const auto formats = QImageReader::supportedImageFormats();
        QVERIFY2(formats.contains("webp"), qPrintable(QStringLiteral("no WebP plugin (qtimageformats/qwebp.dll); formats: ")
                                                      + QString::fromLatin1(formats.join(' '))));
    }

    void everyBundledPortraitDecodes() {
        const QDir source(QStringLiteral(VOICE_AVATAR_DIR));
        const auto expected = source.entryList({QStringLiteral("*.webp")}, QDir::Files, QDir::Name);
        QVERIFY2(expected.size() > 0, "no voice portraits in the source tree");
        const QDir bundled(QStringLiteral(":/voiceavatars"));
        QCOMPARE(bundled.entryList({QStringLiteral("*.webp")}, QDir::Files, QDir::Name), expected);
        for (const auto &name : expected) {
            QImageReader reader(bundled.filePath(name));
            QCOMPARE(reader.format(), QByteArray("webp"));
            const QImage image = reader.read();
            QVERIFY2(!image.isNull(), qPrintable(name + QStringLiteral(": ") + reader.errorString()));
            QVERIFY2(image.width() >= 64 && image.height() >= 64, qPrintable(name));
        }
    }

    // The path the app takes: a QML Image on a qrc portrait (AvatarPortrait.qml) must reach Image.Ready, not Error.
    void qmlImageOfAPortraitIsReady() {
        const QDir bundled(QStringLiteral(":/voiceavatars"));
        const auto names = bundled.entryList({QStringLiteral("*.webp")}, QDir::Files, QDir::Name);
        QVERIFY(!names.isEmpty());
        QQmlEngine engine;
        QQmlComponent component(&engine);
        component.setData(QByteArrayLiteral("import QtQuick\nImage { sourceSize: Qt.size(256, 256); asynchronous: true }"),
                          QUrl(QStringLiteral("qrc:/imageformat_test.qml")));
        std::unique_ptr<QObject> object(component.create());
        QVERIFY2(object, qPrintable(component.errorString()));
        object->setProperty("source", QUrl(QStringLiteral("qrc:/voiceavatars/") + names.first()));
        // QQuickImage::Status: Null 0, Ready 1, Loading 2, Error 3
        QTRY_VERIFY_WITH_TIMEOUT(object->property("status").toInt() != 2 && object->property("status").toInt() != 0, 5000);
        QCOMPARE(object->property("status").toInt(), 1);
        QVERIFY(object->property("implicitWidth").toReal() > 0);
    }
};

QTEST_MAIN(ImageFormatTests)
#include "test_imageformats.moc"
