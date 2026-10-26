// Chế độ đo (ABOOK_BENCH=<file.json>): ghi thời điểm khung (frameSwapped) và các mốc (host sẵn sàng, thư viện về, bắt đầu / hết
// cuộn) rồi thoát. Không đặt biến môi trường thì mọi hàm là no-op. Script đo: tools/measure.py.
#pragma once

#include <QObject>
#include <QQuickWindow>
#include <QString>
#include <QJSEngine>
#include <QQmlEngine>
#include <QtQml/qqmlregistration.h>

class Bench : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool enabled READ enabled CONSTANT)

public:
    explicit Bench(QObject *parent);
    static Bench *create(QQmlEngine *, QJSEngine *);

    bool enabled() const;
    /// Gọi được từ mọi luồng.
    static void mark(const QString &name);

    Q_INVOKABLE void note(const QString &name) { mark(name); }
    /// Chỉ ghi lần đầu cho mỗi tên (ví dụ bìa đầu tiên hiện ra).
    Q_INVOKABLE void noteOnce(const QString &name);
    Q_INVOKABLE void attach(QQuickWindow *window);
    Q_INVOKABLE void finish();
};
