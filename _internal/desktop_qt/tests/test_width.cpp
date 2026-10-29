// Actual QML screens + actual player/book/read-along, fake HTTP/audio only.
#include "bookdetail.h"
#include "fakes.h"
#include "feedback.h"
#include "music.h"
#include "mediacontrols.h"
#include "readalong.h"
#include "glyphaudit.h"
#include <QFontDatabase>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QDir>
#include <QTemporaryDir>
#include <QDateTime>
#include <QtQuickTest/quicktest.h>
#include <QQuickWindow>
#include <QtQuick/private/qquickwindow_p.h>
#include <QtQuick/private/qsgabstractsoftwarerenderer_p.h>

class WidthCovers : public QQuickImageProvider {
public:
    WidthCovers() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &, QSize *size, const QSize &requested) override {
        if (size) *size = QSize(600, 900);
        QImage image(requested.isValid() ? requested : QSize(60, 90), QImage::Format_RGB32);
        image.fill(QColor(QStringLiteral("#9b562f")));
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
    Q_INVOKABLE void finishChapter() { m_out->finish(); }
    Q_INVOKABLE void buffering(bool value) { emit m_out->buffering(value); }
    Q_INVOKABLE void fail(const QString &message) { m_out->fail(message); }
    Q_INVOKABLE void resetBooks() { m_net->books = m_original; }
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
public slots:
    void qmlEngineAvailable(QQmlEngine *engine) {
        engine->rootContext()->setContextProperty(QStringLiteral("qtGlyphAudit"), audit.get());
        engine->rootContext()->setContextProperty(QStringLiteral("qtGlyphProbe"), qEnvironmentVariableIsSet("ABOOK_GLYPH_PROBE"));
        engine->rootContext()->setContextProperty(QStringLiteral("qtWideShotDir"), qEnvironmentVariable("ABOOK_WIDE_SHOTS"));
        engine->rootContext()->setContextProperty(QStringLiteral("qtFullRepaint"), &repaint);
        engine->addImageProvider(QStringLiteral("cover"), new WidthCovers);
    }
    void applicationAvailable() {
        audit = std::make_unique<GlyphAudit>();
        qApp->installEventFilter(&repaint);
        for (const auto &weight : {"Regular", "Medium", "Bold"})
            QFontDatabase::addApplicationFont(QStringLiteral(WIDTH_SOURCE_DIR "/fonts/BeVietnamPro-%1.ttf").arg(QString::fromLatin1(weight)));
        QGuiApplication::setFont(QFont(QStringLiteral("Be Vietnam Pro")));
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
        qmlRegisterType<BookDetail>("ABook", 1, 0, "BookDetail");
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

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", WIDTH_SOURCE_DIR "/tests/qml/stub");
    qputenv("QT_QPA_FONTDIR", WIDTH_SOURCE_DIR "/fonts");
    QDir().mkpath(QStringLiteral(WIDTH_SOURCE_DIR "/build/d2shots"));     // ảnh của tst_d2_*.qml
    WidthSetup setup;
    const int result = quick_test_main_with_setup(argc, argv, "width", QUICK_TEST_SOURCE_DIR, &setup);
    const auto file = qEnvironmentVariable("ABOOK_GLYPH_AUDIT", QStringLiteral(WIDTH_SOURCE_DIR "/build/glyph-audit.json"));
    const bool glyphs = setup.audit && setup.audit->finish(file);
    return result ? result : glyphs ? 0 : 1;
}

#include "test_width.moc"
