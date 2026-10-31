#pragma once

#include <QFile>
#include <QFont>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRawFont>
#include <QSet>
#include <QTextDocument>
#include <QTextLayout>
#include <QGlyphRun>
#include <QTextBlock>
#include <QTimer>
#include <QtTest/QTest>

// Inspect the live visual tree, including nested delegates and overlays. Deliberately
// inspect shaped fallback glyphs too: bundled fonts must work in offscreen QPA.
class GlyphAudit : public QObject {
    Q_OBJECT
    QTimer timer;
    QSet<QString> seen;
    QJsonArray hits;
    qint64 texts = 0;
    QSet<QString> scenes;

    static QString path(QQuickItem *item) {
        QStringList parts;
        for (auto *at = item; at; at = at->parentItem())
            parts.prepend(at->objectName().isEmpty() ? QString::fromLatin1(at->metaObject()->className()) : at->objectName());
        return parts.join('/');
    }
    static bool exposed(QQuickItem *item) {
        if (!item->isVisible() || item->opacity() <= 0 || item->width() <= 0 || item->height() <= 0) return false;
        QRectF bounds = item->mapRectToScene(item->boundingRect());
        if (item->window()) bounds &= QRectF(QPointF(), item->window()->size());
        for (auto *at = item; at; at = at->parentItem()) {
            if (!at->isVisible() || at->opacity() <= 0 || at->scale() == 0) return false;
            if (at->clip()) bounds &= at->mapRectToScene(at->boundingRect());
        }
        return !bounds.isEmpty();
    }
    void inspect(QQuickItem *item) {
        if (!item->isVisible() || item->opacity() <= 0) return;
        if (exposed(item) && item->property("font").canConvert<QFont>() && item->property("text").isValid()) {
            const auto text = item->property("text").toString();
            const auto font = qvariant_cast<QFont>(item->property("font"));
            const auto type = QString::fromLatin1(item->metaObject()->className());
            // TextInput/TextEdit expose a placeholder separately from their text.
            const auto placeholder = item->property("placeholderText").toString();
            if (!text.isEmpty() || !placeholder.isEmpty()) {
                ++texts;
                const auto format = item->property("textFormat");
                QTextDocument doc;
                doc.setDefaultFont(font);
                if (format.isValid() && format.toInt() != Qt::PlainText && Qt::mightBeRichText(text)) doc.setHtml(text);
                else doc.setPlainText(text.isEmpty() ? placeholder : text);
                for (auto block = doc.begin(); block.isValid(); block = block.next()) {
                    for (auto it = block.begin(); !it.atEnd(); ++it) {
                        const auto fragment = it.fragment();
                        const auto raw = QRawFont::fromFont(fragment.charFormat().font().resolve(font));
                        for (const auto cp : fragment.text().toUcs4()) {
                            if (QChar::isSpace(cp) || QChar::category(cp) == QChar::Other_Control
                                || QChar::category(cp) == QChar::Other_Format) continue;
                            if (cp != 0xfffd) {
                                if (raw.isValid() && raw.supportsCharacter(cp)) continue;
                                // Shape using Qt's real fallback stack. Checking only the
                                // primary QRawFont falsely rejects bundled symbol fonts.
                                QTextLayout layout(QString::fromUcs4(&cp, 1), fragment.charFormat().font().resolve(font));
                                layout.beginLayout();
                                layout.createLine();
                                layout.endLayout();
                                bool drawn = false;
                                for (const auto &run : layout.glyphRuns())
                                    for (const auto glyph : run.glyphIndexes())
                                        drawn |= glyph != 0 && run.rawFont().supportsCharacter(cp);
                                if (drawn) continue;
                            }
                            const QString code = QStringLiteral("U+%1").arg(cp, 4, 16, QLatin1Char('0')).toUpper();
                            const auto where = path(item);
                            const auto key = where + '\n' + text + '\n' + code + '\n' + raw.familyName();
                            if (seen.contains(key)) continue;
                            seen.insert(key);
                            const auto *context = QQmlEngine::contextForObject(item);
                            QJsonObject hit{{"codepoint", code}, {"text", text}, {"font", raw.familyName()},
                                {"style", raw.styleName()}, {"path", where}, {"type", type},
                                {"source", context ? context->baseUrl().toString() : QString()},
                                {"test", QString::fromUtf8(QTest::currentTestFunction())},
                                {"data", QString::fromUtf8(QTest::currentDataTag())}};
                            hits.append(hit);
                            qWarning().noquote() << "GLYPH_MISSING" << QJsonDocument(hit).toJson(QJsonDocument::Compact);
                        }
                    }
                }
            }
        }
        for (auto *child : item->childItems()) inspect(child);
    }
public:
    explicit GlyphAudit(QObject *parent = nullptr) : QObject(parent) {
        timer.setInterval(25);
        connect(&timer, &QTimer::timeout, this, &GlyphAudit::scan);
        timer.start();
    }
    Q_INVOKABLE void scan() {
        scenes.insert(QString::fromUtf8(QTest::currentTestFunction()) + ':' + QString::fromUtf8(QTest::currentDataTag()));
        for (auto *window : QGuiApplication::allWindows())
            if (auto *quick = qobject_cast<QQuickWindow *>(window); quick && quick->isVisible()) inspect(quick->contentItem());
    }
    bool finish(const QString &file) {
        timer.stop();
        QFile output(file);
        if (!output.open(QIODevice::WriteOnly)) return false;
        QStringList sorted = scenes.values();
        sorted.sort();
        output.write(QJsonDocument(QJsonObject{{"text_observations", texts}, {"scenes", QJsonArray::fromStringList(sorted)},
            {"hits", hits}, {"hit_count", hits.size()}}).toJson());
        return hits.isEmpty() && texts > 0;
    }
};
