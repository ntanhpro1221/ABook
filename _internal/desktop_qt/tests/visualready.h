#pragma once
#include <QObject>
#include <QQuickItem>
#include <QSet>
#include <QVariant>

// Behavior interceptors are QObject children, not QQuickItem.resources. Walk
// both object and visual ownership so tests observe the animations Qt paints.
class VisualReady : public QObject {
    Q_OBJECT
    static bool inspect(QObject *object, QSet<QObject *> &seen) {
        if (seen.contains(object)) return true;
        seen.insert(object);
        const auto loops = object->property("loops");
        if (loops.isValid()) {
            if (loops.toInt() == -1) return true; // perpetual busy indicator
            if (object->property("running").toBool()) return false;
        }
        for (auto *child : object->children()) if (!inspect(child, seen)) return false;
        if (auto *item = qobject_cast<QQuickItem *>(object))
            for (auto *child : item->childItems()) if (!inspect(child, seen)) return false;
        return true;
    }
public:
    using QObject::QObject;
    Q_INVOKABLE bool settled(QObject *root) const {
        QSet<QObject *> seen;
        return root && inspect(root, seen);
    }
};
