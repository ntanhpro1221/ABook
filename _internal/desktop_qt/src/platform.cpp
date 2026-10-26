#include "platform.h"

#include <QJSEngine>
#include <QCoreApplication>
#include <QDesktopServices>
#include <QDir>
#include <QEvent>
#include <QFileInfo>
#include <QFontDatabase>
#include <QKeyEvent>
#include <QSettings>
#include <QUrl>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

namespace {
Platform *g_platform = nullptr;

QSettings &settings() {
    // Cạnh dữ liệu của app (%LOCALAPPDATA%\ABook), không vào registry.
    static QSettings s(QDir(qEnvironmentVariable("LOCALAPPDATA")).filePath(QStringLiteral("ABook/desktop_qt.ini")), QSettings::IniFormat);
    return s;
}

bool systemReducesMotion() {
#ifdef Q_OS_WIN
    BOOL animations = TRUE;  // Cài đặt > Trợ năng > Hiệu ứng hình ảnh > Hiệu ứng động
    if (SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, &animations, 0))
        return !animations;
#endif
    return false;
}
}  // namespace

Platform::Platform(QObject *parent) : QObject(parent), m_reduceMotion(systemReducesMotion()) {
    g_platform = this;
    m_iconFamily = QFontDatabase::families().contains(QStringLiteral("Segoe Fluent Icons")) ? QStringLiteral("Segoe Fluent Icons")
                                                                                         : QStringLiteral("Segoe MDL2 Assets");
    qApp->installEventFilter(this);
}

Platform *Platform::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_platform, QJSEngine::CppOwnership);
    return g_platform;
}

void Platform::refresh() {
    const bool now = systemReducesMotion();
    if (now != m_reduceMotion) {
        m_reduceMotion = now;
        emit reduceMotionChanged();
    }
}

QString Platform::setting(const QString &key, const QString &fallback) const {
    return settings().value(key, fallback).toString();
}

void Platform::setSetting(const QString &key, const QString &value) {
    settings().setValue(key, value);
    settings().sync();
}

void Platform::revealFile(const QString &path) {
    // Mở thư mục chứa file (nhật ký); chưa có file thì mở thư mục cha nếu có.
    QFileInfo info(path);
    const QString folder = info.absolutePath();
    QDir().mkpath(folder);
    QDesktopServices::openUrl(QUrl::fromLocalFile(folder));
}

bool Platform::eventFilter(QObject *, QEvent *event) {
    switch (event->type()) {
    case QEvent::KeyPress: {
        const int key = static_cast<QKeyEvent *>(event)->key();
        if (key != Qt::Key_Control && key != Qt::Key_Shift && key != Qt::Key_Alt && key != Qt::Key_Meta && !m_keyboardNav) {
            m_keyboardNav = true;
            emit keyboardNavChanged();
        }
        break;
    }
    case QEvent::MouseButtonPress:
    case QEvent::TouchBegin:
        if (m_keyboardNav) {
            m_keyboardNav = false;
            emit keyboardNavChanged();
        }
        break;
    default:
        break;
    }
    return false;
}
