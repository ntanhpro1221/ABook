#pragma once

#include <QAbstractEventDispatcher>
#include <QCoreApplication>
#include <QHash>
#include <QTimerEvent>
#include <cstdio>

// Diagnostic only. No timer, thread, repaint or per-event logging is added.
class IdleAudit final : public QObject {
public:
    IdleAudit() {
        if (!enabled) return;
        qApp->installEventFilter(this);
        connect(QAbstractEventDispatcher::instance(), &QAbstractEventDispatcher::awake, this, [this] { if (hidden) ++wakes; });
    }
    void setHidden(bool value) {
        if (!enabled) return;
        if (hidden && !value) {
            for (auto it = timers.cbegin(); it != timers.cend(); ++it)
                std::fprintf(stderr, "idle_timer %s count=%llu\n", qPrintable(it.key()), static_cast<unsigned long long>(it.value()));
            std::fprintf(stderr, "idle_main_dispatcher_wakes=%llu\n", static_cast<unsigned long long>(wakes));
            timers.clear(); wakes = 0;
        }
        hidden = value;
    }
protected:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (hidden && event->type() == QEvent::Timer)
            ++timers[QStringLiteral("%1:%2:id=%3").arg(QString::fromLatin1(object->metaObject()->className()), object->objectName())
                         .arg(static_cast<QTimerEvent *>(event)->timerId())];
        return false;
    }
private:
    const bool enabled = qEnvironmentVariableIntValue("ABOOK_IDLE_AUDIT");
    bool hidden = false;
    quint64 wakes = 0;
    QHash<QString, quint64> timers;
};
