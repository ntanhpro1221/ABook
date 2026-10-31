#include "appfonts.h"
#include "backend.h"
#include "desktopapi.h"
#include "bench.h"
#include "coverprovider.h"
#include "feedback.h"
#include "filesinkdevice.h"
#include "hostnet.h"
#include "music.h"
#include "musicmixer.h"
#include "musicwindowactivity.h"
#include "idleaudit.h"
#include "mediacontrols.h"
#include "platform.h"
#include "player.h"
#include "speechout.h"
#include "outputdevices.h"
#include "readalong.h"
#include "singleinstance.h"

#include <QDir>
#include <QFileInfo>
#include <QDirIterator>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlEngine>
#include <QQmlError>
#include <QQuickWindow>
#include <QEvent>
#include <QPlatformSurfaceEvent>
#include <QScopedValueRollback>
#include <QStandardPaths>
#include <QTimer>
#include <QJsonObject>
#include <memory>
#include <optional>
#include <qpa/qwindowsysteminterface_p.h>
#include <cstdio>
#include <cstdlib>
#include <string_view>

#define NOMINMAX
#include <windows.h>
#include <dwmapi.h>

// A never-switched desktop has no DWM exposure. Native benchmark probes must
// still exercise the real D3D scene graph, including its minimize/restore path.
// This only changes TEST exposure events, after verifying the private desktop.
class BenchExposure final : public QWindowSystemEventHandler {
    bool enabled;
public:
    explicit BenchExposure(bool enabled) : enabled(enabled) {
        if (!enabled) return;
        wchar_t name[256]{}; DWORD size=0;
        if (!GetUserObjectInformationW(GetThreadDesktop(GetCurrentThreadId()),UOI_NAME,name,sizeof(name),&size)
            || std::wstring_view(name).find(L"ABookBench-")!=0) {
            std::fputs("OWNER RULE: native exposure probe requires a verified private desktop\n",stderr);
            std::_Exit(6);
        }
        QWindowSystemInterfacePrivate::installWindowSystemEventHandler(this);
    }
    ~BenchExposure() { if(enabled) QWindowSystemInterfacePrivate::removeWindowSystemEventhandler(this); }
    bool sendEvent(QWindowSystemInterfacePrivate::WindowSystemEvent *event) override {
        if (event->type==QWindowSystemInterfacePrivate::Expose) {
            auto *expose=static_cast<QWindowSystemInterfacePrivate::ExposeEvent *>(event);
            if (auto *window=qobject_cast<QQuickWindow *>(expose->window.data()))
                expose->isExposed=window->isVisible() && window->visibility()!=QWindow::Minimized;
        }
        return QWindowSystemEventHandler::sendEvent(event);
    }
};

// ShowNormal của Qt dùng SW_SHOWNORMAL, bỏ qua WindowDoesNotAcceptFocus: chặn ở Win32 TRƯỚC khi Windows đổi focus.
class BenchActivationGuard final {
public:
    explicit BenchActivationGuard(bool enabled) {
        if (!enabled) return;
        m_hook = SetWindowsHookExW(WH_CBT, filter, nullptr, GetCurrentThreadId());
        if (!m_hook) std::_Exit(5);
    }
    ~BenchActivationGuard() { if (m_hook) UnhookWindowsHookEx(m_hook); }
private:
    static LRESULT CALLBACK filter(int code, WPARAM wparam, LPARAM lparam) {
        if (code == HCBT_ACTIVATE || code == HCBT_SETFOCUS) {
            std::fputs("bench_native_activation_blocked\n", stderr);
            return 1;
        }
        if (code == HCBT_CREATEWND) {
            auto *create = reinterpret_cast<CBT_CREATEWNDW *>(lparam)->lpcs;
            if (!(create->style & WS_CHILD) && create->hwndParent != HWND_MESSAGE) {
                create->x = create->y = -10000;
                create->dwExStyle |= WS_EX_NOACTIVATE;
            }
        }
        return CallNextHookEx(nullptr, code, wparam, lparam);
    }
    HHOOK m_hook = nullptr;
};

// Đặt trước lần show đầu, kể cả cửa sổ phụ: phép đo không được chen vào màn hình của chủ máy.
class BenchWindowGuard final : public QObject {
    bool m_handling = false;
    const bool m_cloak = qEnvironmentVariableIntValue("ABOOK_BENCH_CLOAK") == 1;
public:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (m_handling) return false;
        const bool created = event->type() == QEvent::PlatformSurface &&
            static_cast<QPlatformSurfaceEvent *>(event)->surfaceEventType() == QPlatformSurfaceEvent::SurfaceCreated;
        if (created || event->type() == QEvent::Show) {
            if (auto *window = qobject_cast<QWindow *>(object)) {
                if (!window->isTopLevel()) return false;
                QScopedValueRollback<bool> handling(m_handling, true);
                window->setProperty("_q_showWithoutActivating", true);
                window->setFlag(Qt::WindowDoesNotAcceptFocus, true);
                if (m_cloak) {
                    const HWND hwnd = reinterpret_cast<HWND>(window->winId());
                    const BOOL cloak = TRUE;
                    DWORD state = 0;
                    // Chỉ đưa vào vùng màn hình sau khi cloak đã được xác nhận, trước show.
                    if (FAILED(DwmSetWindowAttribute(hwnd, DWMWA_CLOAK, &cloak, sizeof(cloak))) ||
                        FAILED(DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, &state, sizeof(state))) || !state) {
                        std::fputs("OWNER RULE: khong xac nhan duoc DWM cloak truoc show\n", stderr);
                        std::_Exit(5);
                    }
                    window->setPosition(100, 100);
                    Bench::mark(QStringLiteral("bench_cloaked:%1:%2").arg(quintptr(hwnd)).arg(state));
                } else window->setPosition(-10000, -10000);
                if (event->type() == QEvent::Show)
                    Bench::mark(QStringLiteral("bench_show:%1:%2:focus=%3:noactivate=%4").arg(window->x()).arg(window->y())
                        .arg(window->flags().testFlag(Qt::WindowDoesNotAcceptFocus)).arg(window->property("_q_showWithoutActivating").toBool()));
            }
        }
        return false;
    }
};

int main(int argc, char *argv[]) {
    SetThreadDescription(GetCurrentThread(), L"ABook main");
    MediaControls::setAppId();
    QQuickWindow::setDefaultAlphaBuffer(true);
    const bool benchMode = qEnvironmentVariableIsSet("ABOOK_BENCH");
    BenchActivationGuard activationGuard(benchMode);
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
    // Mọi màn hình import QtQuick.Controls.Basic. Hộp thoại dự phòng của QtQuick.Dialogs (khi hộp thoại của Windows không mở
    // được) import QtQuick.Controls trần, mà Qt 6.8+ chọn FluentWinUI3 trên Windows 11 - bản đóng gói chỉ mang Basic
    // (tools/trim_dist.py), nên style cố định là Basic.
    qputenv("QT_QUICK_CONTROLS_STYLE", "Basic");
    QGuiApplication app(argc, argv);
    BenchExposure benchExposure(benchMode && qEnvironmentVariableIntValue("ABOOK_BENCH_HIDDEN_DESKTOP")==1 && QGuiApplication::platformName()==QStringLiteral("windows"));
    BenchWindowGuard benchWindowGuard;
    if (benchMode) app.installEventFilter(&benchWindowGuard);
    QGuiApplication::setApplicationName(QStringLiteral("ABook"));
    QGuiApplication::setOrganizationName(QStringLiteral("ABook"));
    app.setQuitOnLastWindowClosed(false);
    app.setWindowIcon(QIcon(QStringLiteral(":/app/app.ico")));
    Bench::mark(QStringLiteral("main"));

    // Một bản chạy cho mỗi hồ sơ (Q4, src/singleinstance.h): đã có bản đang chạy thì gửi nó các file trên dòng lệnh rồi thoát,
    // trước khi tốn công khởi động host. Hồ sơ giả của test / bộ cài thử có kênh riêng, không gửi sang app thật.
    QStringList launchFiles;
    for (const QString &argument : app.arguments().mid(1)) {
        if (!argument.startsWith(QLatin1Char('-')))
            launchFiles << argument;
    }
    SingleInstance instance;
    // Hai lần mở cùng lúc: cả hai chưa thấy ai, một bên giữ được quyền, bên kia gửi sang nó.
    if (instance.handOff(launchFiles) || (!instance.listen() && instance.handOff(launchFiles)))
        return 0;

    // Backend Python chạy NGAY, song song với việc dựng giao diện (Python mất vài trăm ms để nạp).
    Backend backend(nullptr);
    backend.start();
    Bench bench(nullptr);
    Platform platform(nullptr);
    // One output client for chapters, music, previews and touch feedback. Outlive every voice.
    // ABOOK_AUDIO_SINK=<wav>: tai của phép kiểm tiếng (tools/audio_sink.py). Không mở loa; đúng những khung đáng lẽ ra WASAPI
    // được ghi vào WAV theo nhịp đồng hồ thật, kèm .gaps/.stops/.clock để đối chiếu với mốc của bench.
    const QString musicCache = QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + QStringLiteral("/music_pcm");
    const QString audioSink = qEnvironmentVariable("ABOOK_AUDIO_SINK");
    auto mixer = audioSink.isEmpty() ? std::make_unique<MusicMixer>(musicCache)
                                     : std::make_unique<MusicMixer>(std::make_unique<FileSinkDevice>(audioSink), musicCache, true);
    MixVoice audio(mixer.get(), MixVoice::Voice);
    MixVoice sampleAudio(mixer.get());
    sampleAudio.setVolume(1.0);
    if (benchMode) {
        QObject::connect(&audio, &AudioOut::durationChanged, &audio, [](double seconds) { Bench::mark(QStringLiteral("voice_ready:%1").arg(seconds)); });
        QObject::connect(&audio, &AudioOut::failed, &audio, [](const QString &error) { Bench::mark(QStringLiteral("voice_failed:%1").arg(error)); });
        QObject::connect(&audio, &AudioOut::buffering, &audio, [](bool on) { Bench::mark(QStringLiteral("voice_buffering:%1").arg(on)); });
    }
    DesktopApi::setPreviewOut(&sampleAudio);
    HostNet hostNet(backend.network(), nullptr);
    const QString outbox = QDir(qEnvironmentVariable("LOCALAPPDATA")).filePath(QStringLiteral("ABook/pending-progress.json"));
    QDir().mkpath(QFileInfo(outbox).absolutePath());
    SpeechOut speech(&audio, &hostNet);
    SpeechOut::setInstance(&speech);
    OutputDevices outputs([&mixer](bool select, const QString &id) {
        if (select) mixer->selectOutput(id); else mixer->requestOutputs();
    });
    QObject::connect(mixer.get(), &MusicMixer::outputsReady, &outputs, &OutputDevices::complete);
    OutputDevices::setInstance(&outputs);
    Player player(&speech, &hostNet, outbox, nullptr);
    Player::setInstance(&player);
    player.watchInput();
    Music music(&player, &hostNet, [&mixer, benchMode]() -> AudioOut * {
        auto *voice = new MixVoice(mixer.get(), MixVoice::Bed);
        if (benchMode) {
            QObject::connect(voice, &AudioOut::durationChanged, voice, [&mixer](double seconds) {
                Bench::mark(QStringLiteral("mix_ready:%1:%2:decodes=%3").arg(mixer->rate()).arg(seconds).arg(mixer->decodeCount()));
            });
            QObject::connect(voice, &AudioOut::playingChanged, voice, [](bool playing) {
                Bench::mark(playing ? QStringLiteral("mix_playing") : QStringLiteral("mix_paused"));
            });
            QObject::connect(voice, &AudioOut::failed, voice, [](const QString &) { Bench::mark(QStringLiteral("mix_failed")); });
            // Soát nghe §19: vị trí trong bài của từng phần tử nhạc, để so với vị trí giọng (bài trôi chậm đúng bằng quãng hở giữa clip).
            const quintptr tag = quintptr(voice);
            QObject::connect(voice, &AudioOut::seeked, voice, [voice, tag] {
                Bench::mark(QStringLiteral("mix_seeked:%1:%2").arg(tag, 0, 16).arg(voice->position(), 0, 'f', 3));
            });
            auto *pos = new QTimer(voice);
            QObject::connect(pos, &QTimer::timeout, voice, [voice, tag] {
                if (voice->playing()) Bench::mark(QStringLiteral("mix_pos:%1:%2").arg(tag, 0, 16).arg(voice->position(), 0, 'f', 3));
            });
            pos->start(250);
        }
        return voice;
    }, nullptr);
    Music::setInstance(&music);
    Feedback feedback([&mixer] { return new MixVoice(mixer.get()); }, nullptr);
    Feedback::setInstance(&feedback);
    QObject::connect(&player, &Player::playingChanged, &feedback, [&player, &feedback] { feedback.setBookPlaying(player.playing()); });
    QObject::connect(&player, &Player::sleepWarning, &feedback, [&feedback] { feedback.play(QStringLiteral("sleepWarn")); });
    ReadAlong readAlong(&player, &hostNet, nullptr);
    QObject::connect(&speech, &SpeechOut::scriptReady, &readAlong, &ReadAlong::narrationScript);
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
    bool uiHidden = false, libraryDirty = false;
    libraryRefresh.setSingleShot(true);
    libraryRefresh.setInterval(1500);
    QObject::connect(&libraryRefresh, &QTimer::timeout, &backend, [&] { libraryDirty = false; backend.refreshLibrary(); });

    if (!loadAppFonts(QStringLiteral(":/qt/qml/ABook/fonts")))
        qFatal("Could not load application fonts");

    QQmlApplicationEngine engine;
    IdleAudit idleAudit;
    QObject::connect(&player, &Player::listeningChanged, &libraryRefresh, [&] {
        libraryDirty = true;
        if (!uiHidden) libraryRefresh.start();
    });
    MusicWindowActivity musicWindowActivity([&](bool relaxed) {
        mixer->setRelaxed(relaxed);
        idleAudit.setHidden(relaxed);
        player.setUiActive(!relaxed);
        uiHidden = relaxed;
        if (relaxed) libraryRefresh.stop();
        else if (libraryDirty) { libraryDirty = false; backend.refreshLibrary(); }
    });
    std::unique_ptr<MediaControls> media;
    if (qEnvironmentVariable("ABOOK_SMTC") != QStringLiteral("0"))
        media = std::make_unique<MediaControls>(&player, &speech, nullptr, [&backend](const QString &path) { return backend.get(path); });
    if (benchMode && media)
        QObject::connect(media.get(), &MediaControls::commandExecuted, &bench, [&player](MediaCommand command) {
            Bench::mark(QStringLiteral("smtc_command:%1:playing=%2").arg(int(command)).arg(player.playing()));
        });
    if (benchMode)
        engine.setInitialProperties({{QStringLiteral("x"), -10000}, {QStringLiteral("y"), -10000},
            {QStringLiteral("flags"), int(Qt::Window | Qt::WindowDoesNotAcceptFocus)}});
    engine.addImageProvider(QStringLiteral("cover"), new CoverProvider);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app, [] { QCoreApplication::exit(3); }, Qt::QueuedConnection);
    // ABOOK_SMOKE_EXIT=1 (build.bat, tools/smoke_dist.py): quit shortly after the first frame, 0 only when the
    // engine reported no warning, so a package whose QML does not load fails the build. Tests use stub singletons.
    // ABOOK_SMOKE_EXIT=host (tools/smoke_packaged.py): the same, but only once the host is Ready too; 5 when it failed.
    // ABOOK_SMOKE_EXIT=play (tools/smoke_packaged.py + smoke_play.py): host Ready, the Library fetched with at least one
    // book (7 when empty), then the first book plays; 0 once the voice has played PLAYED_S seconds, 6 when playing failed.
    const QString smoke = qEnvironmentVariable("ABOOK_SMOKE_EXIT");
    const bool smokePlay = smoke == QStringLiteral("play");
    const bool smokeExit = smoke == QStringLiteral("1") || smoke == QStringLiteral("host") || smokePlay;
    int engineWarnings = 0;
    if (smokeExit)
        QObject::connect(&engine, &QQmlEngine::warnings, &app, [&engineWarnings](const QList<QQmlError> &list) { engineWarnings += list.size(); });
    engine.loadFromModule("ABook", "Main");
    if (smokeExit) {
        auto *window = engine.rootObjects().isEmpty() ? nullptr : qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
        if (!window) return 3;
        const bool waitHost = smoke != QStringLiteral("1");
        auto framed = std::make_shared<bool>(false), done = std::make_shared<bool>(false);
        auto books = std::make_shared<std::optional<QJsonArray>>();
        auto quit = [&engineWarnings](int delayMs) {
            QTimer::singleShot(delayMs, qApp, [&engineWarnings] { QCoreApplication::exit(engineWarnings ? 4 : 0); });
        };
        auto check = [&backend, &player, waitHost, smokePlay, framed, done, books, quit] {
            if (*done || !*framed) return;
            if (waitHost && backend.state() == Backend::Failed) {
                *done = true;
                qWarning("SMOKE_HOST_FAILED %s", qUtf8Printable(backend.message()));
                QCoreApplication::exit(5);
                return;
            }
            if (waitHost && backend.state() != Backend::Ready) return;
            if (smokePlay && !books->has_value()) return;
            *done = true;
            if (!smokePlay) {
                quit(1500);
                return;
            }
            const QJsonArray list = **books;
            if (list.isEmpty()) {
                qWarning("SMOKE_LIBRARY_EMPTY");
                QCoreApplication::exit(7);
                return;
            }
            const QString id = list.first().toObject().value(QStringLiteral("id")).toString();
            qWarning("SMOKE_LIBRARY %lld book(s), %d row(s); playing %s", qlonglong(list.size()), backend.library()->rowCount(), qUtf8Printable(id));
            player.playBook(id);
        };
        QObject::connect(window, &QQuickWindow::frameSwapped, &app, [framed, check] { *framed = true; check(); }, Qt::SingleShotConnection);
        if (waitHost) QObject::connect(&backend, &Backend::stateChanged, &app, check);
        if (smokePlay) {
            QObject::connect(&backend, &Backend::libraryFetched, &app, [books, check](const QJsonArray &list) {
                if (!books->has_value()) *books = list;
                check();
            });
            auto played = std::make_shared<bool>(false);
            QObject::connect(&audio, &AudioOut::failed, &app, [played](const QString &reason) {
                if (*played) return;
                *played = true;
                qWarning("SMOKE_PLAY_FAILED %s", qUtf8Printable(reason));
                QCoreApplication::exit(6);
            });
            auto *poll = new QTimer(&app);
            QObject::connect(poll, &QTimer::timeout, &app, [&audio, &player, played, quit] {
                if (*played) return;
                if (!player.error().isEmpty()) {
                    *played = true;
                    qWarning("SMOKE_PLAY_FAILED %s", qUtf8Printable(player.error()));
                    QCoreApplication::exit(6);
                } else if (audio.playing() && audio.position() >= 2.0 /* smoke_play.PLAYED_S */) {
                    *played = true;
                    qWarning("SMOKE_PLAYED %.2f s", audio.position());
                    quit(300);
                }
            });
            poll->start(100);
        }
    }
    musicWindowActivity.update();
    // Lần mở khác của app: hiện cửa sổ (Main.qml otherLaunch). Đo đạc (ABOOK_BENCH) không bao giờ đưa cửa sổ lên.
    if (!engine.rootObjects().isEmpty() && !benchMode) {
        QObject *root = engine.rootObjects().constFirst();
        QObject::connect(&instance, &SingleInstance::launched, root, [root](const QStringList &files) {
            QMetaObject::invokeMethod(root, "otherLaunch", Q_ARG(QVariant, QVariant(files)));
        });
    }
    for (QObject *root : engine.rootObjects()) {
        if (auto *window = qobject_cast<QQuickWindow *>(root); window && media) media->attachWindow(window->winId());
    }
    Bench::mark(QStringLiteral("qml_loaded"));
    return app.exec();
}
