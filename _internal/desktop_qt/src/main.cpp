#include "backend.h"
#include "desktopapi.h"
#include "bench.h"
#include "audioout_mf.h"
#include "coverprovider.h"
#include "hostnet.h"
#include "music.h"
#include "platform.h"
#include "player.h"
#include "readalong.h"

#include <QDir>
#include <QFileInfo>
#include <QDirIterator>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlEngine>
#include <QQuickWindow>
#include <QTimer>

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
    // Bộ phát: Media Foundation (mở lười, tới lệnh phát đầu tiên) + đường HTTP tới host. Phải tắt TRƯỚC host để lưu nốt chỗ nghe.
    MfAudioOut audio(nullptr);
    MfAudioOut sampleAudio(nullptr);
    DesktopApi::setPreviewOut(&sampleAudio);
    HostNet hostNet(backend.network(), nullptr);
    const QString outbox = QDir(qEnvironmentVariable("LOCALAPPDATA")).filePath(QStringLiteral("ABook/pending-progress.json"));
    QDir().mkpath(QFileInfo(outbox).absolutePath());
    Player player(&audio, &hostNet, outbox, nullptr);
    Player::setInstance(&player);
    player.watchInput();
    // Nhạc nền: mỗi phần tử nhạc một bộ phát Media Foundation riêng (mở lười), theo giọng của Player.
    Music music(&player, &hostNet, [] { return new MfAudioOut(nullptr); }, nullptr);
    Music::setInstance(&music);
    ReadAlong readAlong(&player, &hostNet, nullptr);
    ReadAlong::setInstance(&readAlong);
    QObject::connect(&app, &QGuiApplication::aboutToQuit, &player, [&player] { player.shutdown(); });
    QObject::connect(&app, &QGuiApplication::aboutToQuit, &backend, &Backend::stop);
    // Mở app: thanh phát có sẵn cuốn nghe dở gần nhất ở trạng thái dừng (một lần, không nạp lại sau khi người nghe đóng nó).
    bool restored = false;
    QObject::connect(&backend, &Backend::libraryFetched, &player, [&player, &restored](const QJsonArray &books) {
        if (restored)
            return;
        restored = true;
        player.restoreLast(books);
    });
    // Chỗ nghe vừa lưu xong thì tiến độ trên Thư viện làm mới (gộp các lần liền nhau).
    QTimer libraryRefresh;
    libraryRefresh.setSingleShot(true);
    libraryRefresh.setInterval(1500);
    QObject::connect(&libraryRefresh, &QTimer::timeout, &backend, &Backend::refreshLibrary);
    QObject::connect(&player, &Player::listeningChanged, &libraryRefresh, qOverload<>(&QTimer::start));

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
