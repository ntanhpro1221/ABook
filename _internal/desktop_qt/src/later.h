#pragma once

#include <QJSValue>
#include <QList>
#include <QObject>
#include <QPointer>
#include <QtQml/qqmlregistration.h>
#include <QtQml/private/qqmlcontextdata_p.h>
#include <QtQml/private/qqmldata_p.h>
#include <utility>

// Later.call(owner, fn) = Qt.callLater(fn) của app: chạy fn ở vòng sự kiện kế, gộp các lần gọi cùng một hàm (như callLater), NHƯNG bỏ
// qua khi màn chứa owner đã bị huỷ hay đang chờ xoá. Qt.callLater chỉ canh object của hàm chưa bị xoá, không canh ngữ cảnh QML:
// Loader / Repeater gỡ một màn thì ngữ cảnh của nó mất ngay (id thành null, "root is not defined") trong khi object còn sống chờ
// xoá sau - hàm hẹn vẫn chạy và
// báo TypeError (EditBookActions "children of null", NewChapters, NewProjectScreen; StudioRows từng phải tự rào "if (cell)").
// owner là object nằm trong CÙNG component với những id mà fn dùng (thường là root, trong delegate là chính ô).
// Máy dò tests/test_qt_call_later.py chặn Qt.callLater mới trong qml/.
class Later : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    using QObject::QObject;

    Q_INVOKABLE void call(QObject *owner, const QJSValue &fn) {
        // Ngữ cảnh RIÊNG của owner (ownContext: nơi có các id root/holder... của component) - data->context và qmlContext(owner) là
        // ngữ cảnh của file bên ngoài đã tạo ra nó, vẫn sống khi màn của owner đã mất.
        const QQmlData *data = owner ? QQmlData::get(owner) : nullptr;
        const QQmlRefPointer<QQmlContextData> context = !data ? nullptr : data->ownContext ? data->ownContext : QQmlRefPointer<QQmlContextData>(data->context);
        // Tín hiệu của con phát ra lúc màn đang bị gỡ: id owner đã null, hay tên hàm không còn tra được - màn không còn, bỏ.
        if (!context || !context->isValid() || QQmlData::wasDeleted(owner)) {
            ++dropped;
            return;
        }
        if (!fn.isCallable()) {
            qWarning("Later.call: fn không phải hàm");
            return;
        }
        for (qsizetype i = 0; i < pending.size(); ++i) {
            if (pending[i].fn.strictlyEquals(fn)) {
                pending.move(i, pending.size() - 1);
                return;
            }
        }
        pending.append({context, QPointer<QObject>(owner), fn});
        if (pending.size() == 1)
            QMetaObject::invokeMethod(this, &Later::flush, Qt::QueuedConnection);
    }
    // Số lần hẹn đã bỏ vì màn không còn (cho test).
    Q_INVOKABLE int skipped() const { return dropped; }

private:
    struct Call {
        QQmlRefPointer<QQmlContextData> context;
        QPointer<QObject> owner;
        QJSValue fn;
    };
    QList<Call> pending;
    int dropped = 0;

    void flush() {
        const QList<Call> calls = std::exchange(pending, {});
        for (const Call &call : calls) {
            if (QQmlData::wasDeleted(call.owner.data()) || !call.context || !call.context->isValid()) {
                ++dropped;
                continue;
            }
            const QJSValue result = call.fn.call();
            if (result.isError())
                qWarning("%s:%d: %s (Later.call)", qPrintable(result.property(QStringLiteral("fileName")).toString()),
                    result.property(QStringLiteral("lineNumber")).toInt(), qPrintable(result.toString()));
        }
    }
};
