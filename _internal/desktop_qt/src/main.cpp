#include "backend.h"
#include "bench.h"
#include "audioout_mf.h"
#include "coverprovider.h"
#include "hostnet.h"
#include "music.h"
#include "musicmixer.h"
#include "musicwindowactivity.h"
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
#include <QEvent>
#include <QStandardPaths>
#include <QTimer>
#include <cstdio>
#include <cstdlib>

// Đặt trước lần show đầu, kể cả cửa sổ phụ: phép đo không được chen vào màn hình của chủ máy.
class BenchWindowGuard final : public QObject {
public:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (event->type() == QEvent::PlatformSurface || event->type() == QEvent::Show) {
            if (auto *window = qobject_cast<QWindow *>(object)) {
                window->setProperty("_q_showWithoutActivating", true);
                window->setFlag(Qt::WindowDoesNotAcceptFocus, true);
                window->setPosition(-10000, -10000);
                if (event->type() == QEvent::Show)
                    Bench::mark(QStringLiteral("bench_show:%1:%2:focus=%3:noactivate=%4").arg(window->x()).arg(window->y())
                        .arg(window->flags().testFlag(Qt::WindowDoesNotAcceptFocus)).arg(window->property("_q_showWithoutActivating").toBool()));
            }
        }
        return false;
    }
};

int main(int argc, char *argv[]) {
    const bool benchMode = qEnvironmentVariableIsSet("ABOOK_BENCH");
    if (benchMode) {
        // Qt mở MessageBox khi thiếu plugin NGAY trong QGuiApplication, trước cả bộ gác cửa sổ.
        // Thoát ở thông báo nạp plugin đầu tiên, ghi lỗi cho launcher thay vì hiện hộp lỗi của Qt.
        qInstallMessageHandler([](QtMsgType type, const QMessageLogContext &context, const QString &message) {
            const QByteArray text = qFormatLogMessage(type, context, message).toUtf8();
            std::fwrite(text.constData(), 1, size_t(text.size()), stderr); std::fputc('\n', stderr); std::fflush(stderr);
            if (type == QtFatalMsg || (QByteArray(context.category) == "qt.qpa.plugin" && message.startsWith(QStringLiteral("Could not "))))
                std::_Exit(4);
        });
    }
    // Luồng vblank của Qt (QDxgiVSyncService: WaitForVBlank theo tần số quét, 180 lần/s ở màn 180 Hz) thức cả khi cửa sổ thu nhỏ hay
    // đứng yên: ~0,2 % một nhân lúc phát nền, nghỉ 0,3 -> 0,1 %. Tắt thì Qt hẹn khung bằng đồng hồ; nhịp khung lúc chữ chạy không đổi
    // (PROGRESS.md mục CPU). Đặt sẵn trong môi trường thì giữ giá trị đó (đo so sánh: =0).
    if (!qEnvironmentVariableIsSet("QT_D3D_NO_VBLANK_THREAD"))
        qputenv("QT_D3D_NO_VBLANK_THREAD", "1");
    QGuiApplication app(argc, argv);
    BenchWindowGuard benchWindowGuard;
    if (benchMode) app.installEventFilter(&benchWindowGuard);
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
    HostNet hostNet(backend.network(), nullptr);
    const QString outbox = QDir(qEnvironmentVariable("LOCALAPPDATA")).filePath(QStringLiteral("ABook/pending-progress.json"));
    QDir().mkpath(QFileInfo(outbox).absolutePath());
    Player player(&audio, &hostNet, outbox, nullptr);
    Player::setInstance(&player);
    player.watchInput();
    // Cờ chỉ để đo A/B; nhạc dùng một thiết bị chung, giọng vẫn giữ engine riêng.
    std::unique_ptr<MusicMixer> mixer;
    if (qEnvironmentVariableIntValue("ABOOK_MUSIC_MIX") == 1)
        mixer = std::make_unique<MusicMixer>(QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + QStringLiteral("/music_pcm"));
    Music music(&player, &hostNet, [&mixer, benchMode]() -> AudioOut * {
        if (!mixer) return new MfAudioOut(nullptr);
        auto *voice = new MixVoice(mixer.get());
        if (benchMode) {
            QObject::connect(voice, &AudioOut::durationChanged, voice, [&mixer](double seconds) {
                Bench::mark(QStringLiteral("mix_ready:%1:%2:decodes=%3").arg(mixer->rate()).arg(seconds).arg(mixer->decodeCount()));
            });
            QObject::connect(voice, &AudioOut::playingChanged, voice, [](bool playing) {
                Bench::mark(playing ? QStringLiteral("mix_playing") : QStringLiteral("mix_paused"));
            });
            QObject::connect(voice, &AudioOut::failed, voice, [](const QString &) { Bench::mark(QStringLiteral("mix_failed")); });
        }
        return voice;
    }, nullptr);
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
    std::unique_ptr<MusicWindowActivity> musicWindowActivity;
    if (mixer)
        musicWindowActivity = std::make_unique<MusicWindowActivity>([&mixer](bool relaxed) { mixer->setRelaxed(relaxed); });
    if (benchMode)
        engine.setInitialProperties({{QStringLiteral("x"), -10000}, {QStringLiteral("y"), -10000},
            {QStringLiteral("flags"), int(Qt::Window | Qt::WindowDoesNotAcceptFocus)}});
    engine.addImageProvider(QStringLiteral("cover"), new CoverProvider);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app, [] { QCoreApplication::exit(3); }, Qt::QueuedConnection);
    engine.loadFromModule("ABook", "Main");
    if (musicWindowActivity) musicWindowActivity->update();
    Bench::mark(QStringLiteral("qml_loaded"));
    return app.exec();
}
