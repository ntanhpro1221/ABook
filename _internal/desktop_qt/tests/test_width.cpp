// Actual QML screens + actual player/book/read-along, fake HTTP/audio only.
#include "bookdetail.h"
#include "fakes.h"
#include "feedback.h"
#include "music.h"
#include "mediacontrols.h"
#include "readalong.h"
#include "glyphaudit.h"
#include "keep.h"
#include "smoothwheel.h"
#include "later.h"
#include "appfonts.h"
#include "visualready.h"
#include "animationclock.h"
#include "timing.h"
#include "uitree.h"
#include "shadowprovider.h"
#include "musicartprovider.h"
#include <QFontDatabase>
#include <QAbstractAnimation>
#include <QCoreApplication>
#include <QQmlEngine>
#include <QQmlContext>
#include <QtQml/private/qqmldata_p.h>
#include <QtQml/private/qqmlvmemetaobject_p.h>
#include <QtQml/private/qv4engine_p.h>
#include <QtQml/private/qv4mm_p.h>
#include <QFileInfo>
#include <QtCore/private/qhooks_p.h>
#include <QMutex>
#include <QSet>
#include <QThread>
#include <QQuickImageProvider>
#include <QPainter>
#include <QDir>
#include <QDirIterator>
#include <QRegularExpression>
#include <QTemporaryDir>
#include <QDateTime>
#include <QtQuickTest/quicktest.h>
#include <QQuickWindow>
#include <QGuiApplication>
#include <QPlatformSurfaceEvent>
#include <QWindow>
#include <QTimer>
#include <QtQuick/private/qquickwindow_p.h>
#include <qpa/qwindowsysteminterface_p.h>
#define NOMINMAX
#include <windows.h>
#include <QtQuick/private/qsgabstractsoftwarerenderer_p.h>

class WidthCovers : public QQuickImageProvider {
public:
    WidthCovers() : QQuickImageProvider(QQuickImageProvider::Image) {}
    // Bo góc theo bán kính ở cuối id như CoverProvider thật (src/coverprovider.cpp): bìa giả vuông làm ảnh d2shots lệch app thật
    // (0.4.173 soát tay: bìa quyển 1 vuông, quyển 2 bìa vẽ bo góc).
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override {
        if (size) *size = QSize(600, 900);
        const QSize box = requested.isValid() ? requested : QSize(60, 90);
        const int radius = id.section(QLatin1Char('/'), -1).toInt();
        QImage image(box, QImage::Format_ARGB32_Premultiplied);
        image.fill(Qt::transparent);
        QPainter painter(&image);
        painter.setRenderHint(QPainter::Antialiasing);
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(QStringLiteral("#9b562f")));
        painter.drawRoundedRect(QRectF(QPointF(0, 0), QSizeF(box)), radius, radius);
        return image;
    }
};

// Đường mạng giả của Player / Music / BookDetail cho bộ thử QML: đếm lời gọi (FakeNet::callsTo).
class WidthNet : public QObject {
    Q_OBJECT
public:
    explicit WidthNet(FakeNet *net, FakeOut *out, Player *player, std::function<void(double)> advance)
        : m_net(net), m_out(out), m_player(player), m_advance(std::move(advance)), m_original(net->books) {}
    Q_INVOKABLE int count(const QString &method, const QString &suffix) const { return int(m_net->callsTo(suffix, method.toLatin1()).size()); }
    Q_INVOKABLE void setBook(const QVariantMap &book) { const auto json = QJsonObject::fromVariantMap(book); m_net->books.insert(json.value(QStringLiteral("id")).toString(), json); }
    Q_INVOKABLE void setScript(const QString &book, int chapter, const QVariantMap &script) {
        m_net->scripts.insert(QStringLiteral("/api/books/%1/chapters/%2/script").arg(book).arg(chapter), QJsonObject::fromVariantMap(script));
    }
    Q_INVOKABLE void setAnswer(const QString &key, const QVariantMap &value) { m_net->answers.insert(key, QJsonObject::fromVariantMap(value)); }
    Q_INVOKABLE void resetAnswers() { m_net->answers.clear(); }
    Q_INVOKABLE void finishChapter() { m_out->finish(); }
    Q_INVOKABLE void buffering(bool value) { emit m_out->buffering(value); }
    Q_INVOKABLE void fail(const QString &message) { m_out->fail(message); }
    Q_INVOKABLE void resetBooks() { m_net->books = m_original; }
    Q_INVOKABLE void setReadScript(const QString &script) {
        auto book = m_original.value(QStringLiteral("width"));
        book.insert(QStringLiteral("id"), QStringLiteral("wordglide"));
        m_net->books.insert(QStringLiteral("wordglide"), book);
        m_net->scripts.insert(QStringLiteral("/api/books/wordglide/chapters/1/script"), QJsonDocument::fromJson(script.toUtf8()).object());
    }
    Q_INVOKABLE void advance(double seconds) {
        for (int i = 0; i < qRound(seconds * 10); ++i) {
            m_advance(0.1);
            if (m_out->isPlaying) m_out->pos = qMin(m_out->dur, m_out->pos + 0.1 * m_out->rate);
            m_player->tick();
        }
        m_player->clock()->refresh();
    }
private:
    FakeNet *m_net;
    FakeOut *m_out;
    Player *m_player;
    std::function<void(double)> m_advance;
    QHash<QString, QJsonObject> m_original;
};

// Observe the actual SMTC adapter while QML operates the real shared Player.
class WidthMedia : public QObject, public MediaSink {
    Q_OBJECT
    Q_PROPERTY(bool playing READ playing NOTIFY changed)
    Q_PROPERTY(bool loaded READ loaded NOTIFY changed)
    Q_PROPERTY(bool canNext READ canNext NOTIFY changed)
    Q_PROPERTY(bool canPrevious READ canPrevious NOTIFY changed)
public:
    MediaControls *controls = nullptr;
    bool playing() const { return state.status == MediaState::Playing; }
    bool loaded() const { return state.loaded; }
    bool canNext() const { return state.canNext; }
    bool canPrevious() const { return state.canPrevious; }
    void display(const MediaState &s, const QByteArray &) override { state = s; emit changed(); }
    void playback(const MediaState &s) override { state = s; emit changed(); }
    void timeline(const MediaState &s) override { state = s; emit changed(); }
    Q_INVOKABLE void play() { controls->dispatch(MediaCommand::Play); }
    Q_INVOKABLE void pause() { controls->dispatch(MediaCommand::Pause); }
signals:
    void changed();
private:
    MediaState state;
};

// Bộ thử chạy Qt Quick bằng bộ vẽ phần mềm (nền offscreen), nó chỉ vẽ lại vùng bẩn và grabImage đọc thẳng bộ đệm ấy: phần một item vẽ
// ra ngoài khung của nó (tab "Thêm" bị cắt của trang hẹp 560 trong cửa sổ 1280) có thể nằm lại sau khi trang bị huỷ và lọt vào ảnh của
// test sau ("⌄" lạc ở 571,333). Mỗi khung vẽ lại cả cửa sổ: ảnh chụp chỉ có thứ đang thật sự hiện.
class FullRepaint : public QObject {
    Q_OBJECT
    int count = 0;
public:
    // số khung đã vẽ lại cả cửa sổ - tst_studio_music kiểm nó tăng
    Q_INVOKABLE int frames() const { return count; }
    bool eventFilter(QObject *target, QEvent *event) override {
        auto *window = qobject_cast<QQuickWindow *>(target);
        if (window && event->type() == QEvent::Expose && !window->property("abookFullRepaint").toBool()) {
            window->setProperty("abookFullRepaint", true);
            QObject::connect(window, &QQuickWindow::beforeSynchronizing, window, [this, window] {
                auto *renderer = QQuickWindowPrivate::get(window)->renderer;
                if (renderer && window->rendererInterface()->graphicsApi() == QSGRendererInterface::Software) {
                    static_cast<QSGAbstractSoftwareRenderer *>(renderer)->markDirty();
                    ++count;
                }
            }, Qt::DirectConnection);
        }
        return false;
    }
};

// ABOOK_WIDTH_REAL_BACKEND=1: chạy trên nền "windows" với bộ vẽ RHI thật (D3D11 như app) thay cho offscreen + bộ vẽ phần mềm, để
// so ảnh chụp với bộ vẽ của app (0.4.173: viền đen quanh hộp thoại chỉ có ở bộ vẽ phần mềm). Như bộ gác cửa sổ của chế độ đo
// (main.cpp BenchWindowGuard): mọi cửa sổ đặt ở -10000,-10000 trước lần hiện đầu, không nhận focus, hiện mà không kích hoạt -
// không bao giờ lên màn hình của chủ máy hay lấy bàn phím (móc CBT chặn kích hoạt ở Win32 như BenchActivationGuard). Windows không
// gửi "đã hiện" cho cửa sổ ngoài mọi màn hình nên QuickTest sẽ chờ mãi windowShown: cửa sổ Quick đang hiện được coi là đã hiện
// (như BenchExposure); D3D11 vẫn vẽ và grabWindow đọc lại bộ đệm. Test cần phím có thể trượt ở chế độ này; dùng nó để chụp ảnh.
class HiddenWindows : public QObject, public QWindowSystemEventHandler {
    bool handling = false;
    HHOOK hook = nullptr;
    static LRESULT CALLBACK filter(int code, WPARAM wparam, LPARAM lparam) {
        if (code == HCBT_ACTIVATE || code == HCBT_SETFOCUS) return 1;
        if (code == HCBT_CREATEWND) {
            auto *create = reinterpret_cast<CBT_CREATEWNDW *>(lparam)->lpcs;
            if (!(create->style & WS_CHILD) && create->hwndParent != HWND_MESSAGE) {
                create->x = create->y = -10000;
                create->dwExStyle |= WS_EX_NOACTIVATE;
            }
        }
        return CallNextHookEx(nullptr, code, wparam, lparam);
    }
public:
    void install() {
        hook = SetWindowsHookExW(WH_CBT, filter, nullptr, GetCurrentThreadId());
        if (!hook) qFatal("ABOOK_WIDTH_REAL_BACKEND: no CBT hook, refusing to show windows");
        QWindowSystemInterfacePrivate::installWindowSystemEventHandler(this);
        qApp->installEventFilter(this);
    }
    ~HiddenWindows() override {
        if (!hook) return;
        QWindowSystemInterfacePrivate::removeWindowSystemEventhandler(this);
        UnhookWindowsHookEx(hook);
    }
    bool sendEvent(QWindowSystemInterfacePrivate::WindowSystemEvent *event) override {
        if (event->type == QWindowSystemInterfacePrivate::Expose) {
            auto *expose = static_cast<QWindowSystemInterfacePrivate::ExposeEvent *>(event);
            if (auto *window = qobject_cast<QQuickWindow *>(expose->window.data()))
                expose->isExposed = window->isVisible() && window->visibility() != QWindow::Minimized;
        }
        return QWindowSystemEventHandler::sendEvent(event);
    }
    bool eventFilter(QObject *object, QEvent *event) override {
        if (handling) return false;
        const bool created = event->type() == QEvent::PlatformSurface &&
            static_cast<QPlatformSurfaceEvent *>(event)->surfaceEventType() == QPlatformSurfaceEvent::SurfaceCreated;
        auto *window = qobject_cast<QWindow *>(object);
        if ((created || event->type() == QEvent::Show) && window && window->isTopLevel()) {
            handling = true;
            window->setProperty("_q_showWithoutActivating", true);
            window->setFlag(Qt::WindowDoesNotAcceptFocus, true);
            window->setPosition(-10000, -10000);
            handling = false;
            // Windows không gửi WM_PAINT/expose cho cửa sổ ngoài mọi màn hình: tự báo một lần, sendEvent ở trên giữ nó là "đã hiện"
            if (event->type() == QEvent::Show && qobject_cast<QQuickWindow *>(window))
                QTimer::singleShot(0, window, [window] {
                    QWindowSystemInterface::handleExposeEvent<QWindowSystemInterface::SynchronousDelivery>(
                        window, QRegion(QRect(QPoint(), window->size())));
                });
        }
        return false;
    }
};

// ABOOK_QML_LIFETIME_DIAGNOSTICS: at each "Cannot find member data" warning, list every live QML object whose
// property storage is gone, with the QObject parent chain and the flags the V4 collector reads (qv4mm.cpp markWeakValues).
namespace LifetimeProbe {
// Never destroyed: static QObjects still call the RemoveQObject hook during process exit.
QMutex &mutex = *new QMutex;
QSet<QObject *> &live = *new QSet<QObject *>;
QSet<QObject *> &reported = *new QSet<QObject *>;
QtMessageHandler previous = nullptr;
QHooks::AddQObjectCallback previousAdd = nullptr;
QHooks::RemoveQObjectCallback previousRemove = nullptr;
bool scanning = false;
void reinstallHandler();
void add(QObject *object) {
    // QtTest installs its logger when each file starts; stay in front of it without a timer (a 1 ms timer changed the timing
    // enough to hide the warning in gate 22's diagnostics run).
    if (auto *app = QCoreApplication::instance(); app && object->thread() == app->thread()) reinstallHandler();
    { QMutexLocker lock(&mutex); live.insert(object); }
    if (previousAdd) previousAdd(object);
}
void remove(QObject *object) {
    { QMutexLocker lock(&mutex); live.remove(object); reported.remove(object); }
    if (previousRemove) previousRemove(object);
}
QString describe(QObject *object) {
    QString text;
    QDebug out(&text);
    out.nospace() << object;
    const auto *data = QQmlData::get(object);
    out << " indestructible=" << (data && data->indestructible) << " explicit=" << (data && data->explicitIndestructibleSet)
        << " queued=" << (data && data->isQueuedForDeletion) << " deleted=" << QQmlData::wasDeleted(object)
        << " creating=" << (data && data->rootObjectInCreation) << " wrapper=" << (data && !data->jsWrapper.isNullOrUndefined())
        << " tainted=" << (data && data->hasTaintedV4Object) << " keepAlive=" << QQmlData::keepAliveDuringGarbageCollection(object);
    if (auto *vme = QQmlVMEMetaObject::get(object)) out << " storage=" << bool(vme->propertyAndMethodStorageAsMemberData());
    if (auto *item = qobject_cast<QQuickItem *>(object)) out << " parentItem=" << item->parentItem() << " window=" << item->window();
    if (data) out << " line=" << data->lineNumber;
    if (auto *context = qmlContext(object)) out << " url=" << context->baseUrl().fileName();
    return text;
}
void scan() {
    QList<QObject *> objects;
    { QMutexLocker lock(&mutex); objects = live.values(); }
    int lost = 0;
    for (QObject *object : objects) {
        {
            QMutexLocker lock(&mutex);
            if (!live.contains(object) || reported.contains(object)) continue;
        }
        if (object->thread() != QThread::currentThread()) continue;
        auto *vme = QQmlVMEMetaObject::get(object);
        if (!vme || vme->propertyAndMethodStorageAsMemberData()) continue;
        { QMutexLocker lock(&mutex); reported.insert(object); }
        ++lost;
        qWarning().noquote() << "QML_LOST" << describe(object);
        for (QObject *parent = object->parent(); parent; parent = parent->parent())
            qWarning().noquote() << "QML_LOST_PARENT" << describe(parent);
    }
    qWarning() << "QML_LOST_SCAN" << objects.size() << "objects" << lost << "new";
}
QQmlEngine *probeEngine = nullptr;
// At the warning: collector state, JS stack (empty = the access came from C++), C++ frames.
void stacks() {
    if (probeEngine) {
        QV4::ExecutionEngine *v4 = probeEngine->handle();
        qWarning().noquote() << "QML_LOST_GC state=" << int(v4->memoryManager->gcStateMachine->state) << "ongoing=" << int(v4->isGCOngoing);
        const auto trace = v4->stackTrace(12);
        qWarning().noquote() << "QML_LOST_JS frames=" << trace.size();
        for (const auto &frame : trace)
            qWarning().noquote() << "QML_LOST_JS" << frame.function << frame.source << frame.line;
    }
    // C++ frames as module + offset (no PDBs for Qt): resolve against the DLL export table offline.
    void *frames[48];
    const USHORT count = CaptureStackBackTrace(0, 48, frames, nullptr);
    for (USHORT i = 0; i < count; ++i) {
        HMODULE module = nullptr;
        wchar_t path[MAX_PATH] = L"";
        if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(frames[i]), &module))
            GetModuleFileNameW(module, path, MAX_PATH);
        qWarning().noquote() << "QML_LOST_CPP" << i << QFileInfo(QString::fromWCharArray(path)).fileName()
                             << QStringLiteral("+0x") + QString::number(quintptr(frames[i]) - quintptr(module), 16);
    }
}
void handler(QtMsgType type, const QMessageLogContext &context, const QString &message) {
    if (previous) previous(type, context, message);
    if (scanning || !message.contains(QStringLiteral("Cannot find member data"))) return;
    scanning = true;
    stacks();
    scan();
    scanning = false;
}
void installHooks() {
    previousAdd = reinterpret_cast<QHooks::AddQObjectCallback>(qtHookData[QHooks::AddQObject]);
    previousRemove = reinterpret_cast<QHooks::RemoveQObjectCallback>(qtHookData[QHooks::RemoveQObject]);
    qtHookData[QHooks::AddQObject] = reinterpret_cast<quintptr>(&add);
    qtHookData[QHooks::RemoveQObject] = reinterpret_cast<quintptr>(&remove);
}
void removeHooks() {
    qtHookData[QHooks::AddQObject] = reinterpret_cast<quintptr>(previousAdd);
    qtHookData[QHooks::RemoveQObject] = reinterpret_cast<quintptr>(previousRemove);
}
// QtTest installs its own logger when each file starts (after qmlEngineAvailable), which replaced this handler for good:
// the probe printed nothing in gate 22. Put it back in front of whatever logger is current, on every engine and turn.
void reinstallHandler() {
    const QtMessageHandler current = qInstallMessageHandler(handler);
    if (current != handler) previous = current;
}
void installHandler() {
    reinstallHandler();
}
}

// qtStorage: the QML property storage (MemberData) of one object. drop() does what a collection of that storage does while
// the object lives; tst_guard_teardown.qml uses it to show that SmoothWheel has no QML storage left to lose (gates 22/23).
class StorageProbe : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    Q_INVOKABLE bool has(QObject *object) const {
        auto *vme = object ? QQmlVMEMetaObject::get(object) : nullptr;
        return vme && vme->propertyAndMethodStorageAsMemberData();
    }
    Q_INVOKABLE void drop(QObject *object) {
        if (auto *vme = object ? QQmlVMEMetaObject::get(object) : nullptr)
            vme->propertyAndMethodStorage.set(vme->engine, QV4::Value::undefinedValue());
    }
};

class WidthSetup : public QObject {
    Q_OBJECT
    QTemporaryDir dir;
    FakeOut audio;
    FakeNet net;
    qint64 timeOffset = 0;
    std::unique_ptr<Player> player;
    std::unique_ptr<ReadAlong> read;
    std::unique_ptr<Music> music;
    std::unique_ptr<Feedback> feedback;
    std::unique_ptr<WidthNet> netView;
    std::unique_ptr<MediaControls> media;
    FullRepaint repaint;
    HiddenWindows hidden;
public slots:
    void qmlEngineAvailable(QQmlEngine *engine) {
        if (qEnvironmentVariableIsSet("ABOOK_QML_LIFETIME_DIAGNOSTICS")) { LifetimeProbe::probeEngine = engine; LifetimeProbe::installHandler(); }
        engine->rootContext()->setContextProperty(QStringLiteral("qtStorage"), new StorageProbe(engine));
        engine->rootContext()->setContextProperty(QStringLiteral("qtVisualReady"), new VisualReady(engine));
        engine->rootContext()->setContextProperty(QStringLiteral("qtAnimationClock"), new TestAnimationClock(engine));
        engine->rootContext()->setContextProperty(QStringLiteral("qtGlyphAudit"), audit.get());
        engine->rootContext()->setContextProperty(QStringLiteral("qtUiTree"), new UiTree(engine));   // cây UI cạnh ảnh (design_lint)
        engine->rootContext()->setContextProperty(QStringLiteral("qtGlyphProbe"), qEnvironmentVariableIsSet("ABOOK_GLYPH_PROBE"));
        engine->rootContext()->setContextProperty(QStringLiteral("qtWideShotDir"), qEnvironmentVariable("ABOOK_WIDE_SHOTS"));
        // Bộ ảnh soát phát hành chụp thêm khổ khác (vd "1280,960"); rỗng = bốn khổ của test.
        engine->rootContext()->setContextProperty(QStringLiteral("qtWideWidths"), qEnvironmentVariable("ABOOK_WIDE_WIDTHS"));
        engine->rootContext()->setContextProperty(QStringLiteral("qtFullRepaint"), &repaint);
        // Bộ ca chung của bộ chọn giá trị (web vitest, Android JVM, Qt tst_value_picker chạy cùng file).
        QFile cases(QStringLiteral(WIDTH_SOURCE_DIR "/../tests/fixtures/value_picker/cases.json"));
        engine->rootContext()->setContextProperty(QStringLiteral("qtValuePickerCases"),
            cases.open(QIODevice::ReadOnly) ? QString::fromUtf8(cases.readAll()) : QString());
        engine->addImageProvider(QStringLiteral("cover"), new WidthCovers);
        engine->addImageProvider(QStringLiteral("shadow"), new ShadowProvider);
        engine->addImageProvider(QStringLiteral("musicart"), new MusicArtProvider);
    }
    void applicationAvailable() {
        audit = std::make_unique<GlyphAudit>();
        qApp->installEventFilter(&repaint);
        if (qEnvironmentVariableIntValue("ABOOK_WIDTH_REAL_BACKEND") == 1) {
            if (QGuiApplication::platformName() != QStringLiteral("windows")) qFatal("ABOOK_WIDTH_REAL_BACKEND needs the windows platform");
            hidden.install();
        }
        if (!loadAppFonts(QStringLiteral(WIDTH_SOURCE_DIR "/fonts")))
            qFatal("Could not load application fonts");
        net.books.insert(QStringLiteral("width"), makeBook(QStringLiteral("width"), 32));
        QJsonArray segments;
        for (int i = 0; i < 40; ++i)
            segments.append(QJsonObject{{QStringLiteral("paragraph"), i},
                {QStringLiteral("text"), QStringLiteral("Buổi sáng ấy, chúng tôi đi qua con đường nhỏ bên bờ sông.")},
                {QStringLiteral("start"), i * 2.0}, {QStringLiteral("end"), i * 2.0 + 2}});
        net.scripts.insert(QStringLiteral("/api/books/width/chapters/1/script"),
            QJsonObject{{QStringLiteral("timed"), true}, {QStringLiteral("segments"), segments}});
        player = std::make_unique<Player>(&audio, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr,
            [this] { return QDateTime::currentMSecsSinceEpoch() + timeOffset; });
        Player::setInstance(player.get());
        auto mediaSink = std::make_unique<WidthMedia>();
        auto *mediaView = mediaSink.get();
        media = std::make_unique<MediaControls>(player.get(), &audio, std::move(mediaSink));
        mediaView->controls = media.get();
        qmlRegisterSingletonInstance("ABook", 1, 0, "WidthMedia", mediaView);
        read = std::make_unique<ReadAlong>(player.get(), &net);
        music = std::make_unique<Music>(player.get(), &net, [] { return new FakeOut; });
        feedback = std::make_unique<Feedback>([] { return new FakeOut; }, nullptr);
        Feedback::setInstance(feedback.get());
        QObject::connect(player.get(), &Player::playingChanged, feedback.get(), [this] { feedback->setBookPlaying(player->playing()); });
        QObject::connect(player.get(), &Player::sleepWarning, feedback.get(), [this] { feedback->play(QStringLiteral("sleepWarn")); });
        QObject::connect(player.get(), &Player::sleepExtended, feedback.get(), [this] { feedback->play(QStringLiteral("sleepExtend")); });
        qmlRegisterType<BookDetail>("ABook", 1, 0, "BookDetail");
        qmlRegisterSingletonType<Later>("ABook", 1, 0, "Later", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Later; });
        qmlRegisterSingletonType<Keep>("ABook", 1, 0, "Keep", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Keep; });
        qmlRegisterType<SmoothWheel>("ABook", 1, 0, "SmoothWheel");
        qmlRegisterSingletonInstance("ABook", 1, 0, "Player", player.get());
        qmlRegisterSingletonInstance("ABook", 1, 0, "ReadAlong", read.get());
        qmlRegisterSingletonInstance("ABook", 1, 0, "Music", music.get());
        qmlRegisterSingletonInstance("ABook", 1, 0, "Feedback", feedback.get());
        netView = std::make_unique<WidthNet>(&net, &audio, player.get(), [this](double seconds) { timeOffset += qint64(seconds * 1000); });
        qmlRegisterSingletonInstance("ABook", 1, 0, "WidthNet", netView.get());
        player->open(QStringLiteral("width"), 1, 0, false);
    }
public:
    std::unique_ptr<GlyphAudit> audit;
};

/** QML cannot create folders: every "build/<name>/" a test writes into (d2shots, surface_frames...) is created
 *  before the run, read from every test source (tests/width and the -input suites such as tests/bookmeta) so a new
 *  folder never fails on a clean checkout. */
static void createShotFolders() {
    static const QRegularExpression folder(QStringLiteral("build/([A-Za-z0-9_-]+)/"));
    QDirIterator files(QStringLiteral(WIDTH_SOURCE_DIR "/tests"), {QStringLiteral("*.qml"), QStringLiteral("*.js")}, QDir::Files, QDirIterator::Subdirectories);
    while (files.hasNext()) {
        QFile source(files.next());
        if (!source.open(QIODevice::ReadOnly)) continue;
        const QString text = QString::fromUtf8(source.readAll());
        for (auto match = folder.globalMatch(text); match.hasNext();)
            QDir().mkpath(QStringLiteral(WIDTH_SOURCE_DIR "/build/") + match.next().captured(1));
    }
}

int main(int argc, char **argv) {
    TestTiming::promptObserver(); // the QML test thread is the app's UI thread: run it at the app's priority
    const bool realBackend = qEnvironmentVariableIntValue("ABOOK_WIDTH_REAL_BACKEND") == 1;
    qputenv("QT_QPA_PLATFORM", realBackend ? "windows" : "offscreen");
    if (realBackend) qunsetenv("QT_QUICK_BACKEND");
    qputenv("QML_IMPORT_PATH", WIDTH_SOURCE_DIR "/tests/qml/stub");
    qputenv("QT_QPA_FONTDIR", WIDTH_SOURCE_DIR "/fonts");
    qputenv("QML_XHR_ALLOW_FILE_READ", "1");   // tst_uitree reads back the tree file it just wrote
    createShotFolders();
    if (qEnvironmentVariableIsSet("ABOOK_QML_LIFETIME_DIAGNOSTICS")) LifetimeProbe::installHooks();
    WidthSetup setup;
    const int result = quick_test_main_with_setup(argc, argv, "width", QUICK_TEST_SOURCE_DIR, &setup);
    if (qEnvironmentVariableIsSet("ABOOK_QML_LIFETIME_DIAGNOSTICS")) LifetimeProbe::removeHooks();
    const auto file = qEnvironmentVariable("ABOOK_GLYPH_AUDIT", QStringLiteral(WIDTH_SOURCE_DIR "/build/glyph-audit.json"));
    const bool glyphs = setup.audit && setup.audit->finish(file);
    return result ? result : glyphs ? 0 : 1;
}

#include "test_width.moc"
