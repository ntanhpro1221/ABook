#pragma once

#include <QHash>
#include <QJSValue>
#include <QObject>
#include <QtQml/qqmlregistration.h>

// Keep.hold(object): a strong reference to the JS wrapper of a QML object that lives outside the visual tree, for exactly as
// long as the QObject exists. The V4 collector marks a QML object's property storage only through its wrapper. A QQuickItem
// wrapper marks its VISUAL children; every other object (Reveal after `parent = null`, a pointer handler such as SmoothWheel,
// Connections) is kept only by the weak QObject-wrapper pass (qv4mm.cpp markWeakValues), and only while its topmost QObject
// ancestor is C++-owned or being created. Any gap in that weak path frees the storage of an object that is still alive:
// "Cannot find member data", properties read as 0, transitions that never finish (WidthTests 0.4.173, Studio2/Studio5).
// Only parented objects are held: their lifetime belongs to the parent, so holding the wrapper can never keep them alive
// longer; a parentless object's lifetime is the collector's decision. tests/test_qt_keep_anchor.py lists the shared types that
// must call hold() and rejects other ways out of the visual tree.
class Keep : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    using QObject::QObject;

    Q_INVOKABLE void hold(const QJSValue &wrapper) {
        QObject *object = wrapper.toQObject();
        if (!object || !object->parent() || held.contains(object))
            return;
        held.insert(object, wrapper);
        connect(object, &QObject::destroyed, this, [this](QObject *gone) { held.remove(gone); });
    }
    // Live objects held (tests).
    Q_INVOKABLE int count() const { return int(held.size()); }
    Q_INVOKABLE bool holds(QObject *object) const { return held.contains(object); }

private:
    QHash<QObject *, QJSValue> held;
};
