#pragma once
#include <QAbstractAnimation>
#include <QCoreApplication>
#include <QJSValue>
#include <QObject>
#include <QThread>

// Only motion-contract tests opt into this clock. Real scheduler delays must
// not decide whether an intermediate animation value can be observed.
class TestAnimationClock : public QAnimationDriver {
    Q_OBJECT
    qint64 m_elapsed = 0;
    bool m_installed = false;
public:
    using QAnimationDriver::QAnimationDriver;
    ~TestAnimationClock() override { end(); }
    qint64 elapsed() const override { return m_elapsed; }
    Q_INVOKABLE void begin() {
        Q_ASSERT(!m_installed);
        QCoreApplication::processEvents();
        m_elapsed = 0;
        install();
        m_installed = true;
        advanceAnimation();
        QCoreApplication::processEvents();
    }
    Q_INVOKABLE void step(int milliseconds) {
        Q_ASSERT(m_installed && milliseconds > 0);
        // Start queued animations before advancing their clock. Rendering and
        // queued application responses still use Qt's actual event loop.
        QCoreApplication::processEvents();
        m_elapsed += milliseconds;
        advanceAnimation();
        QCoreApplication::processEvents();
    }
    // Step the clock until predicate() holds, at most maxMs of animation time. A motion test observes an intermediate
    // value this way: under load the test thread may get its turn only after a real-time animation has finished.
    // Each step also lets 1 ms of real time pass, so work that is not an animation (a frame for grabToImage, a posted
    // timer) still completes; only the animation's own time is the test's.
    Q_INVOKABLE bool advanceUntil(const QJSValue &predicate, int maxMs, int stepMs = 16) {
        Q_ASSERT(m_installed && stepMs > 0);
        QJSValue test = predicate;
        for (int spent = 0; !test.call().toBool(); spent += stepMs) {
            if (spent >= maxMs) return false;
            QThread::msleep(1);
            step(stepMs);
        }
        return true;
    }
    Q_INVOKABLE void end() {
        if (!m_installed) return;
        uninstall();
        m_installed = false;
    }
};
