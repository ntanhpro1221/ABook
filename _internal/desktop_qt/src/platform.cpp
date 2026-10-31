#include "platform.h"

#include <QJSEngine>
#include <QGuiApplication>
#include <QCoreApplication>
#include <QDesktopServices>
#include <QDir>
#include <QEvent>
#include <QFileInfo>
#include <QKeyEvent>
#include <QPointer>
#include <QSettings>
#include <QScreen>
#include <QTimer>
#include <QUrl>
#include <QWindow>

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

QRect Platform::workArea(QWindow *window, const QPointF &position) const {
    // Vị trí mini có thể ở màn hình khác; màn hình đã tháo thì trở về màn hình cửa sổ đầy.
    if (qIsFinite(position.x()) && qIsFinite(position.y()))
        if (const auto *screen = QGuiApplication::screenAt(position.toPoint()))
            return screen->availableGeometry();
    return window && window->screen() ? window->screen()->availableGeometry() : QRect(0, 0, 1280, 800);
}

bool Platform::eventFilter(QObject *watched, QEvent *event) {
    switch (event->type()) {
    case QEvent::WindowStateChange:
    case QEvent::Hide:
        // Thu nhỏ hoặc ẩn vào khay quá 2 s: dùng cùng một đường trả working set về hệ điều hành;
        // mở lại thì trang về dần từ danh sách chờ (lỗi trang mềm), đo trong PROGRESS.md mục RAM.
        if (auto *window = qobject_cast<QWindow *>(watched); window && (!window->isVisible() || window->windowState() == Qt::WindowMinimized))
            QTimer::singleShot(2000, this, [window = QPointer<QWindow>(window)] {
                if (window && (!window->isVisible() || window->windowState() == Qt::WindowMinimized)) {
                    // Một cửa sổ phụ vừa ẩn không được trim khi cửa sổ chính hoặc mini vẫn đang hiện.
                    for (const auto *visible : QGuiApplication::topLevelWindows())
                        if (visible->isVisible() && visible->windowState() != Qt::WindowMinimized)
                            return;
#ifdef Q_OS_WIN
                    SetProcessWorkingSetSize(GetCurrentProcess(), SIZE_T(-1), SIZE_T(-1));
#endif
                }
            });
        break;
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
