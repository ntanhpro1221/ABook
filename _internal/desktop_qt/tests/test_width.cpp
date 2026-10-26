// Actual QML screens + actual player/book/read-along, fake HTTP/audio only.
#include "bookdetail.h"
#include "fakes.h"
#include "feedback.h"
#include "music.h"
#include "readalong.h"
#include <QFontDatabase>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QDir>
#include <QTemporaryDir>
#include <QtQuickTest/quicktest.h>

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
    explicit WidthNet(FakeNet *net) : m_net(net) {}
    Q_INVOKABLE int count(const QString &method, const QString &suffix) const { return int(m_net->callsTo(suffix, method.toLatin1()).size()); }
private:
    FakeNet *m_net;
};

class WidthSetup : public QObject {
    Q_OBJECT
    QTemporaryDir dir;
    FakeOut audio;
    FakeNet net;
    std::unique_ptr<Player> player;
    std::unique_ptr<ReadAlong> read;
    std::unique_ptr<Music> music;
    std::unique_ptr<Feedback> feedback;
    std::unique_ptr<WidthNet> netView;
public slots:
    void qmlEngineAvailable(QQmlEngine *engine) {
        engine->addImageProvider(QStringLiteral("cover"), new WidthCovers);
    }
    void applicationAvailable() {
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
        player = std::make_unique<Player>(&audio, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        Player::setInstance(player.get());
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
        netView = std::make_unique<WidthNet>(&net);
        qmlRegisterSingletonInstance("ABook", 1, 0, "WidthNet", netView.get());
        player->open(QStringLiteral("width"), 1, 0, false);
    }
};

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", WIDTH_SOURCE_DIR "/tests/qml/stub");
    qputenv("QT_QPA_FONTDIR", WIDTH_SOURCE_DIR "/fonts");
    QDir().mkpath(QStringLiteral(WIDTH_SOURCE_DIR "/build/d2shots"));     // ảnh của tst_d2_*.qml
    WidthSetup setup;
    return quick_test_main_with_setup(argc, argv, "width", QUICK_TEST_SOURCE_DIR, &setup);
}

#include "test_width.moc"
