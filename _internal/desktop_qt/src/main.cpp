#include "backend.h"
#include "bench.h"
#include "coverprovider.h"
#include "platform.h"

#include <QDirIterator>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlEngine>
#include <QQuickWindow>

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("ABook"));
    QGuiApplication::setOrganizationName(QStringLiteral("ABook"));
    Bench::mark(QStringLiteral("main"));

    // Backend Python chạy NGAY, song song với việc dựng giao diện (Python mất vài trăm ms để nạp).
    Backend backend(nullptr);
    backend.start();
    Bench bench(nullptr);
    Platform platform(nullptr);
    QObject::connect(&app, &QGuiApplication::aboutToQuit, &backend, &Backend::stop);

    const QStringList fonts = {QStringLiteral("Regular"), QStringLiteral("Medium"), QStringLiteral("Bold")};
    for (const QString &weight : fonts)
        QFontDatabase::addApplicationFont(QStringLiteral(":/qt/qml/ABook/fonts/BeVietnamPro-%1.ttf").arg(weight));
    QFont base(QStringLiteral("Be Vietnam Pro"));
    base.setPixelSize(16);
    QGuiApplication::setFont(base);

    QQmlApplicationEngine engine;
    engine.addImageProvider(QStringLiteral("cover"), new CoverProvider);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app, [] { QCoreApplication::exit(3); }, Qt::QueuedConnection);
    engine.loadFromModule("ABook", "Main");
    Bench::mark(QStringLiteral("qml_loaded"));
    return app.exec();
}
