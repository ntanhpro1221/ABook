#pragma once
#include <QAccessible>
#include <QColor>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QFont>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QObject>
#include <QQuickItem>
#include <QRegularExpression>
#include <QtQuick/private/qquickaccessibleattached_p.h>
#include "visualready.h"

// Cây UI cạnh ảnh chụp cho scripts/design_lint.py (bước 2, soát thiết kế 10-11): sau khi một tst_*.qml lưu
// build/d2shots/<tên>.png, gọi qtUiTree.save(path, item) để ghi <tên>.tree.json cùng thư mục. Hộp tính bằng px logic
// so với item đã chụp; `bounds` = hộp đầy đủ, `visible` = phần còn thấy sau các cha có clip. Vai lấy từ Accessible.role.
class UiTree : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;

    Q_INVOKABLE bool save(const QString &png, QQuickItem *root) const {
        if (!root)
            return false;
        QJsonArray nodes;
        const QRectF all(0, 0, root->width(), root->height());
        walk(root, root, -1, all, nodes);
        QFile image(png);
        if (!image.open(QIODevice::ReadOnly)) return false;
        const QJsonObject doc{{QStringLiteral("schema"), 1}, {QStringLiteral("platform"), QStringLiteral("qt")},
            {QStringLiteral("image_sha256"), QString::fromLatin1(QCryptographicHash::hash(image.readAll(), QCryptographicHash::Sha256).toHex())},
            {QStringLiteral("image"), QFileInfo(png).fileName()}, {QStringLiteral("unit"), QStringLiteral("px")},
            {QStringLiteral("width"), root->width()}, {QStringLiteral("height"), root->height()},
            {QStringLiteral("nodes"), nodes}};
        QString path = png;
        path.replace(QRegularExpression(QStringLiteral("\\.png$")), QStringLiteral(".tree.json"));
        QFile file(path);
        if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate))
            return false;
        file.write(QJsonDocument(doc).toJson(QJsonDocument::Compact));
        return true;
    }

private:
    static QString role(QAccessible::Role value) {
        switch (value) {
        case QAccessible::Button: return QStringLiteral("button");
        case QAccessible::PageTab: return QStringLiteral("tab");
        case QAccessible::RadioButton: return QStringLiteral("radiobutton");
        case QAccessible::CheckBox: return QStringLiteral("checkbox");
        case QAccessible::ComboBox: return QStringLiteral("dropdownlist");
        case QAccessible::ListItem: return QStringLiteral("listitem");
        case QAccessible::MenuItem: return QStringLiteral("menuitem");
        case QAccessible::Slider: return QStringLiteral("slider");
        case QAccessible::StaticText: return QStringLiteral("text");
        case QAccessible::Heading: return QStringLiteral("heading");
        case QAccessible::EditableText: return QStringLiteral("textfield");
        case QAccessible::Dialog: return QStringLiteral("dialog");
        default: return QString();
        }
    }

    static QJsonArray box(const QRectF &r) {
        return QJsonArray{qRound(r.left() * 100) / 100.0, qRound(r.top() * 100) / 100.0,
                          qRound(r.right() * 100) / 100.0, qRound(r.bottom() * 100) / 100.0};
    }

    static void walk(QQuickItem *item, QQuickItem *root, int parent, const QRectF &clip, QJsonArray &out) {
        if (!item->isVisible() || item->opacity() <= 0)
            return;
        const QRectF bounds = item->mapRectToItem(root, QRectF(0, 0, item->width(), item->height()));
        const QRectF visible = bounds.intersected(clip);
        const int id = out.size();
        QJsonObject node{{QStringLiteral("id"), id}, {QStringLiteral("parent"), parent},
            {QStringLiteral("type"), QString::fromUtf8(item->metaObject()->className()).remove(QRegularExpression(QStringLiteral("_QMLTYPE_\\d+$|_QML_\\d+$")))},
            {QStringLiteral("bounds"), box(bounds)}, {QStringLiteral("visible"), box(visible)}};
        if (auto *attached = qobject_cast<QQuickAccessibleAttached *>(qmlAttachedPropertiesObject<QQuickAccessibleAttached>(item, false))) {
            const QString name = role(attached->role());
            if (!name.isEmpty())
                node.insert(QStringLiteral("role"), name);
            if (!attached->name().isEmpty())
                node.insert(QStringLiteral("description"), attached->name());
        }
        const QVariant text = item->property("text");
        if (text.typeId() == QMetaType::QString && !text.toString().isEmpty()) {
            node.insert(QStringLiteral("text"), text.toString());
            const QVariant font = item->property("font");
            if (font.canConvert<QFont>()) {
                const QFont f = font.value<QFont>();
                node.insert(QStringLiteral("font_size"), f.pixelSize() > 0 ? double(f.pixelSize()) : f.pointSizeF() * 96.0 / 72.0);
                node.insert(QStringLiteral("font_weight"), f.weight());
            }
            const QVariant lines = item->property("lineCount");
            if (lines.isValid())
                node.insert(QStringLiteral("line_count"), lines.toInt());
            const QVariant color = item->property("color");
            if (color.canConvert<QColor>())
                node.insert(QStringLiteral("color"), color.value<QColor>().name());
            QJsonArray linesOut;
            const VisualReady visual;
            for (const QVariant &value : visual.lines(item)) {
                const auto line = value.toMap();
                const auto at = item->mapRectToItem(root, QRectF(line["x"].toDouble(), line["y"].toDouble(),
                    line["w"].toDouble(), line["h"].toDouble()));
                linesOut.append(QJsonObject{{QStringLiteral("bounds"), box(at)}, {QStringLiteral("text"), line["text"].toString()}});
            }
            node.insert(QStringLiteral("lines"), linesOut);
        } else {
            const QVariant color = item->property("color");
            if (color.canConvert<QColor>())
                node.insert(QStringLiteral("background_color"), color.value<QColor>().name(QColor::HexArgb));
        }
        if (!item->objectName().isEmpty()) node.insert(QStringLiteral("tag"), item->objectName());
        for (const char *flag : {"checked", "selected", "current", "highlighted"}) {
            const QVariant value = item->property(flag);
            if (value.typeId() == QMetaType::Bool && (QByteArray(flag) != "checked" || item->property("checkable").toBool())) {
                node.insert(QStringLiteral("selected"), value.toBool());
                break;
            }
        }
        if (item->acceptedMouseButtons() != Qt::NoButton)
            node.insert(QStringLiteral("clickable"), true);
        out.append(node);
        const QRectF inner = item->clip() ? visible : clip;
        for (QQuickItem *child : item->childItems())
            walk(child, root, id, inner, out);
    }
};
