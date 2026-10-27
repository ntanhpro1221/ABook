#pragma once

#include <QEvent>
#include <QGuiApplication>
#include <QTimer>
#include <QWindow>

#include <functional>
#include <utility>

// Observe all application windows, including windows created after QML startup.
// Mini-player merge hook: its QWindow is included automatically; do not bind
// scheduling to the main window or application focus (visible inactive windows count).
class MusicWindowActivity final : public QObject {
public:
    explicit MusicWindowActivity(std::function<void(bool)> setRelaxed, QObject *parent = nullptr)
        : QObject(parent), m_setRelaxed(std::move(setRelaxed)) {
        qGuiApp->installEventFilter(this);
        update();
    }

    void update() {
        for (const QWindow *window : QGuiApplication::allWindows()) {
            if (window->isVisible() && window->visibility() != QWindow::Minimized) {
                m_setRelaxed(false);
                return;
            }
        }
        m_setRelaxed(true);
    }

protected:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (qobject_cast<QWindow *>(object) &&
            (event->type() == QEvent::Show || event->type() == QEvent::Hide ||
             event->type() == QEvent::WindowStateChange || event->type() == QEvent::PlatformSurface)) {
            // Visibility/state and allWindows() settle after delivery of the event.
            if (!m_updateQueued) {
                m_updateQueued = true;
                QTimer::singleShot(0, this, [this] { m_updateQueued = false; update(); });
            }
        }
        return false;
    }

private:
    std::function<void(bool)> m_setRelaxed;
    bool m_updateQueued = false;
};
