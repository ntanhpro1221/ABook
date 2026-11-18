// Bộ thử QML của thanh bên (tests/qml/tst_sidebar.qml): QtQuickTest trên nền offscreen, Platform / Backend giả ở tests/qml/stub.
#include <QtQuickTest/quicktest.h>
#include <QQmlEngine>

#include "keep.h"
#include "later.h"
#include "fakes.h"
#include "player.h"

#include <QByteArray>
#include <QTemporaryDir>
#include <memory>

// MusicPreviewBar also creates a SeekBar and ClockUser. Keep their real Player
// dependency available even when this suite only exercises pointer handling.
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
};

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", QUICK_TEST_SOURCE_DIR "/stub");
    qmlRegisterSingletonType<Keep>("ABook", 1, 0, "Keep", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Keep; });
    qmlRegisterSingletonType<Later>("ABook", 1, 0, "Later", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Later; });
    SidebarSetup setup;
    return quick_test_main_with_setup(argc, argv, "sidebar", QUICK_TEST_SOURCE_DIR, &setup);
}

#include "test_sidebar.moc"
