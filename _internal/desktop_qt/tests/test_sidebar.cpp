// Bộ thử QML của thanh bên (tests/qml/tst_sidebar.qml): QtQuickTest trên nền offscreen, Platform / Backend giả ở tests/qml/stub.
#include <QtQuickTest/quicktest.h>

#include <QByteArray>

int main(int argc, char **argv) {
    qputenv("QT_QPA_PLATFORM", "offscreen");
    qputenv("QML_IMPORT_PATH", QUICK_TEST_SOURCE_DIR "/stub");
    return quick_test_main(argc, argv, "sidebar", QUICK_TEST_SOURCE_DIR);
}
