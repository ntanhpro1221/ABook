#pragma once

#include <QEasingCurve>
#include <QPointer>
#include <QPropertyAnimation>
#include <QQmlEngine>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>
#include <QtQuick/private/qquickevents_p_p.h>
#include <QtQuick/private/qquickflickable_p.h>
#include <QtQuick/private/qquickwheelhandler_p.h>

// Mouse-wheel scrolling with a short glide (one notch ~110 px over 160 ms) instead of jumping a notch at a time. Precise
// touchpads (pixelDelta) stay with Flickable.
//
// All state lives in C++ members. As a QML component (SmoothWheel.qml) the flick/glide/target/step properties lived in the
// handler's QML property storage, which the V4 collector reaches only through the handler's JS wrapper; when that storage
// went away while the handler still lived, every later read or write of `flick`/`glide` printed "QML SmoothWheel: Cannot
// find member data" (gates 22 and 23, NowPlaying.qml:225). This type has no QML-declared property, so it has no such
// storage to lose and needs no Keep.hold. tests/width/tst_guard_teardown.qml drops the storage of the old component and
// shows the warning; tests/test_qt_keep_anchor.py keeps declared properties off pointer handlers.
class SmoothWheel : public QQuickWheelHandler {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QQuickFlickable *flick READ flick WRITE setFlick NOTIFY flickChanged REQUIRED)
    Q_PROPERTY(qreal step READ step WRITE setStep NOTIFY stepChanged)
public:
    explicit SmoothWheel(QQuickItem *parent = nullptr) : QQuickWheelHandler(parent) {
        setAcceptedDevices(QInputDevice::DeviceType::Mouse);
        setBlocking(true);
        m_glide.setPropertyName("contentY");
        m_glide.setDuration(160);
        connect(this, &QQuickWheelHandler::wheel, this, &SmoothWheel::turn);
    }

    QQuickFlickable *flick() const { return m_flick; }
    void setFlick(QQuickFlickable *flick) {
        if (m_flick == flick) return;
        m_glide.stop();
        m_flick = flick;
        emit flickChanged();
    }
    qreal step() const { return m_step; }
    void setStep(qreal step) {
        if (qFuzzyCompare(m_step, step)) return;
        m_step = step;
        emit stepChanged();
    }
    // Tests: the glide in flight (QML no longer sees an animation object).
    Q_INVOKABLE bool gliding() const { return m_glide.state() == QAbstractAnimation::Running; }

signals:
    void flickChanged();
    void stepChanged();
    void scrolled();   // the reader just turned the wheel (the reading view stops following the voice)

private:
    qreal clampY(qreal y) const {
        const qreal top = m_flick->originY() - m_flick->topMargin();
        const qreal bottom = m_flick->originY() + m_flick->contentHeight() - m_flick->height() + m_flick->bottomMargin();
        return qMax(top, qMin(qMax(top, bottom), y));
    }
    QObject *theme() const {
        QQmlEngine *engine = qmlEngine(this);
        return engine ? engine->singletonInstance<QObject *>(QStringLiteral("ABook"), QStringLiteral("Theme")) : nullptr;
    }
    void turn(QQuickWheelEvent *event) {
        emit scrolled();
        if (!m_flick) return;
        const bool running = gliding();
        m_target = clampY((running ? m_target : m_flick->contentY()) - event->angleDelta().y() / 120.0 * m_step);
        QObject *design = theme();
        m_glide.stop();
        if (design && design->property("reduceMotion").toBool()) {
            m_flick->setContentY(m_target);
            return;
        }
        // Theme.easeDecelerate: one cubic segment [c1x, c1y, c2x, c2y, 1, 1], the same curve the QML glide used.
        QEasingCurve curve(QEasingCurve::BezierSpline);
        const QVariantList points = design ? design->property("easeDecelerate").toList() : QVariantList();
        for (qsizetype i = 0; i + 5 < points.size(); i += 6)
            curve.addCubicBezierSegment(QPointF(points[i].toReal(), points[i + 1].toReal()),
                                        QPointF(points[i + 2].toReal(), points[i + 3].toReal()),
                                        QPointF(points[i + 4].toReal(), points[i + 5].toReal()));
        m_glide.setEasingCurve(points.size() >= 6 ? curve : QEasingCurve(QEasingCurve::OutCubic));
        m_glide.setTargetObject(m_flick);
        m_glide.setStartValue(m_flick->contentY());
        m_glide.setEndValue(m_target);
        m_glide.start();
    }

    QPointer<QQuickFlickable> m_flick;
    qreal m_step = 110;
    qreal m_target = 0;
    QPropertyAnimation m_glide;
};
