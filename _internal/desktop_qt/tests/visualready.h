#pragma once
#include <QObject>
#include <QQuickItem>
#include <QSet>
#include <QTextBlock>
#include <QTextDocument>
#include <QTextLayout>
#include <QVariant>
#include <QtQuick/private/qquicktext_p.h>
#include <QtQuick/private/qquicktext_p_p.h>

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
    // Các dòng Qt đã dàn của một Text (chữ thường / StyledText): hình chữ nhật mực từng dòng trong toạ độ của Text và chữ của
    // dòng ấy - cho máy dò chữ-đè-icon (mực khối chữ nhiều dòng không phải một hình chữ nhật) và máy dò dấu ngăn đầu dòng.
    // RichText dàn bằng QTextDocument: các dòng của từng khối (đoạn), `block` = số khối (chữ thường: 0, xuống dòng cứng là U+2028).
    Q_INVOKABLE QVariantList lines(QQuickItem *item) const {
        QVariantList out;
        auto *text = qobject_cast<QQuickText *>(item);
        if (!text) return out;
        auto *d = QQuickTextPrivate::get(text);
        const auto add = [&out](const QTextLine &line, const QString &plain, QPointF at, int block) {
            const QRectF ink = line.naturalTextRect().translated(at);
            out << QVariantMap{{QStringLiteral("x"), ink.x()}, {QStringLiteral("y"), ink.y()}, {QStringLiteral("w"), ink.width()},
                               {QStringLiteral("h"), ink.height()}, {QStringLiteral("text"), plain.mid(line.textStart(), line.textLength())},
                               {QStringLiteral("block"), block}};
        };
        if (d->richText) {
            // RichText lays out in a QTextDocument drawn at the padding: one QTextLayout per block (paragraph)
            if (!d->extra.isAllocated() || !d->extra->doc) return out;
            const QPointF padding(text->leftPadding(), text->topPadding());
            for (QTextBlock block = d->extra->doc->begin(); block.isValid(); block = block.next()) {
                const QTextLayout *layout = block.layout();
                for (int i = 0; layout && i < layout->lineCount(); ++i)
                    add(layout->lineAt(i), block.text(), padding + layout->position(), block.blockNumber());
            }
            return out;
        }
        for (int i = 0; i < d->layout.lineCount(); ++i) add(d->layout.lineAt(i), d->layout.text(), QPointF(), 0);
        return out;
    }
};
