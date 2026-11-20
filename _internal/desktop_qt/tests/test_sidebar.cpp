// Bộ thử QML của thanh bên (tests/qml/tst_sidebar.qml): QtQuickTest trên nền offscreen, Platform / Backend giả ở tests/qml/stub.
#include <QtQuickTest/quicktest.h>
#include <QQmlEngine>

#include "keep.h"
#include "smoothwheel.h"

#include <QByteArray>

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", QUICK_TEST_SOURCE_DIR "/stub");
    qmlRegisterSingletonType<Keep>("ABook", 1, 0, "Keep", [](QQmlEngine *, QJSEngine *) -> QObject * { return new Keep; });
    qmlRegisterType<SmoothWheel>("ABook", 1, 0, "SmoothWheel");
    return quick_test_main(argc, argv, "sidebar", QUICK_TEST_SOURCE_DIR);
}
