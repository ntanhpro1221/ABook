// Bộ thử QML của thanh bên (tests/qml/tst_sidebar.qml): QtQuickTest trên nền offscreen, Platform / Backend giả ở tests/qml/stub.
#include <QtQuickTest/quicktest.h>
#include <QQmlContext>
#include <QQmlEngine>

#include "animationclock.h"
#include "timing.h"

#include "keep.h"
#include "later.h"
#include "fakes.h"
#include "player.h"
#include "smoothwheel.h"

#include <QByteArray>
#include <QTemporaryDir>
#include <memory>

// MusicPreviewBar also creates a SeekBar and ClockUser. Keep their real Player
// dependency available even when this suite only exercises pointer handling.
// Motion tests step a test clock (qtAnimationClock) instead of racing a real-time animation, as in WidthTests.
class SidebarSetup : public QObject {
    Q_OBJECT
    QTemporaryDir dir;
    FakeOut audio;
    FakeNet net;
    std::unique_ptr<Player> player;
public slots:
    void applicationAvailable() {
        player = std::make_unique<Player>(&audio, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr);
        Player::setInstance(player.get());
        qmlRegisterSingletonInstance("ABook", 1, 0, "Player", player.get());
    }
    void qmlEngineAvailable(QQmlEngine *engine) {
        engine->rootContext()->setContextProperty(QStringLiteral("qtAnimationClock"), new TestAnimationClock(engine));
    }
};

int main(int argc, char **argv) {
    TestTiming::promptObserver(); // the QML test thread is the app's UI thread: run it at the app's priority
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", QUICK_TEST_SOURCE_DIR "/stub");
    qmlRegisterSingletonType<Keep>("ABook", 1, 0, "Keep", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Keep; });
    qmlRegisterSingletonType<Later>("ABook", 1, 0, "Later", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Later; });
    qmlRegisterType<SmoothWheel>("ABook", 1, 0, "SmoothWheel");
    SidebarSetup setup;
    return quick_test_main_with_setup(argc, argv, "sidebar", QUICK_TEST_SOURCE_DIR, &setup);
}

#include "test_sidebar.moc"
