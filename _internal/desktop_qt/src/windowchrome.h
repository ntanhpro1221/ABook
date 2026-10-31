#pragma once

#include <QObject>
#include <QtQml/qqmlregistration.h>

class QQuickItem;
class QQuickWindow;
namespace QWK { class QuickWindowAgent; }

// Khung cửa sổ tự vẽ: bỏ thanh tiêu đề hệ thống nhưng giữ hành vi gốc của Windows (kéo, nhấp đúp phóng to, Aero Snap, Snap Layouts của
// Windows 11 khi rê vào nút phóng to, viền đổi cỡ, bóng, bo góc, Alt+Space). Phần việc nặng do QWindowKit (Apache-2.0) làm; lớp này chỉ
// gói nó cho QML: dải tiêu đề là chỗ kéo cửa sổ, ba nút là "nút hệ thống" (Windows biết vùng của chúng), phần tử khác nằm trong dải
// mà vẫn phải bấm được thì khai bằng keepClickable().
class WindowChrome : public QObject {
    Q_OBJECT
    QML_ELEMENT
public:
    explicit WindowChrome(QObject *parent = nullptr);

    // Gọi một lần, TRƯỚC khi cửa sổ hiện.
    Q_INVOKABLE bool attach(QQuickWindow *window, QQuickItem *titleBar, QQuickItem *minimize, QQuickItem *maximize, QQuickItem *close);
    Q_INVOKABLE void keepClickable(QQuickItem *item);
    Q_INVOKABLE void setMini(bool mini);
    // Con trỏ thật còn nằm trên mục này không (Qt không còn nhận tin rê chuột khi Windows mở Snap Layouts trên nút phóng to).
    Q_INVOKABLE bool cursorInside(QQuickItem *item) const;

private:
    QWK::QuickWindowAgent *m_agent = nullptr;
    QQuickItem *m_titleBar = nullptr;
};
