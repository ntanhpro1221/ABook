#pragma once

#include <QEvent>
#include <QDateTime>
#include <QGuiApplication>
#include <QQuickWindow>
#include <QSet>
#include <QTimer>
#include <cstdio>

// QML state survives releaseResources(). Wait for Qt's actual obscurity event:
// on Windows visibility can become Minimized before the render loop is obscured.
// Calling only at that first transition merely drops caches, retaining the D3D device.
class GraphicsIdle final : public QObject {
public:
    explicit GraphicsIdle(QObject *parent = nullptr) : QObject(parent) {
        qGuiApp->installEventFilter(this);
        queueUpdate();
    }
    void update() {
        bool hidden = true;
        for (const QWindow *w : QGuiApplication::allWindows())
            if (w->isVisible() && w->visibility() != QWindow::Minimized) { hidden = false; break; }
        for (QWindow *base : QGuiApplication::allWindows()) {
            auto *w = qobject_cast<QQuickWindow *>(base);
            if (!w) continue;
            if (!observed.contains(w)) {
                observed.insert(w);
                connect(w, &QQuickWindow::sceneGraphInitialized, this, [this] { queueUpdate(); }, Qt::QueuedConnection);
                connect(w, &QObject::destroyed, this, [this, w] { observed.remove(w); });
            }
            w->setPersistentGraphics(!hidden);
            w->setPersistentSceneGraph(!hidden);
            if (hidden && !w->isExposed() && w->isSceneGraphInitialized()) {
                w->releaseResources();
                if (audit) std::fprintf(stderr, "graphics_idle_release epoch_ms=%lld window=%p initialized=%d\n",
                    static_cast<long long>(QDateTime::currentMSecsSinceEpoch()), static_cast<void *>(w), w->isSceneGraphInitialized());
            }
        }
    }
protected:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (qobject_cast<QWindow *>(object)) switch (event->type()) {
        case QEvent::Show: case QEvent::Hide: case QEvent::WindowStateChange:
        case QEvent::Expose: case QEvent::PlatformSurface:
            queueUpdate(); break;
        default: break;
        }
        return false;
    }
private:
    bool queued = false;
    const bool audit = qEnvironmentVariableIntValue("ABOOK_IDLE_AUDIT");
    QSet<QQuickWindow *> observed;
    void queueUpdate() {
        if (queued) return;
        queued = true;
        QTimer::singleShot(0, this, [this] { queued = false; update(); });
    }
};
