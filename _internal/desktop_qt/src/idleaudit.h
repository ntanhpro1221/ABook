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
            for (auto it = events.cbegin(); it != events.cend(); ++it)
                std::fprintf(stderr, "idle_event %s count=%llu\n", qPrintable(it.key()), static_cast<unsigned long long>(it.value()));
            std::fprintf(stderr, "idle_main_dispatcher_wakes=%llu\n", static_cast<unsigned long long>(wakes));
            timers.clear(); events.clear(); wakes = 0;
        }
        hidden = value;
    }
protected:
    bool eventFilter(QObject *object, QEvent *event) override {
        if (hidden && event->type() == QEvent::Timer)
            ++timers[QStringLiteral("%1:%2:id=%3").arg(QString::fromLatin1(object->metaObject()->className()), object->objectName())
                         .arg(static_cast<QTimerEvent *>(event)->timerId())];
        if (hidden && detailed && (event->type()==QEvent::Timer || event->type()==QEvent::MetaCall || event->type()==QEvent::SockAct ||
            event->type()==QEvent::DeferredDelete || event->type()==QEvent::UpdateRequest || event->type()==QEvent::Expose)) {
            QString owner;
            for (auto *p=object; p && owner.count(QLatin1Char('/'))<3; p=p->parent()) {
                if (!owner.isEmpty()) owner+=QLatin1Char('/');
                owner+=QString::fromLatin1(p->metaObject()->className())+QLatin1Char(':')+p->objectName();
            }
            ++events[QString::number(int(event->type()))+QLatin1Char(':')+owner];
        }
        return false;
    }
private:
    const bool enabled = qEnvironmentVariableIntValue("ABOOK_IDLE_AUDIT");
    const bool detailed = qEnvironmentVariableIntValue("ABOOK_IDLE_EVENTS");
    bool hidden = false;
    quint64 wakes = 0;
    QHash<QString, quint64> timers;
    QHash<QString, quint64> events;
};
