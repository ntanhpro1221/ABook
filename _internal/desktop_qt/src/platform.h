// Những việc riêng của Windows mà QML cần: "giảm chuyển động" của hệ điều hành, đang dùng bàn phím hay chuột (để vẽ vòng tiêu điểm
// chỉ khi dùng bàn phím), lưu cài đặt giao diện nhỏ, mở thư mục nhật ký.
#pragma once

#include <QObject>
#include <QJSEngine>
#include <QQmlEngine>
#include <QtQml/qqmlregistration.h>

class Platform : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool reduceMotion READ reduceMotion NOTIFY reduceMotionChanged)
    Q_PROPERTY(bool keyboardNav READ keyboardNav NOTIFY keyboardNavChanged)

public:
    explicit Platform(QObject *parent);
    static Platform *create(QQmlEngine *, QJSEngine *);

    bool reduceMotion() const { return m_reduceMotion; }
    bool keyboardNav() const { return m_keyboardNav; }

    /// Đọc lại cài đặt hệ thống (gọi khi cửa sổ được kích hoạt lại).
    Q_INVOKABLE void refresh();
    Q_INVOKABLE QString setting(const QString &key, const QString &fallback = {}) const;
    Q_INVOKABLE void setSetting(const QString &key, const QString &value);
    Q_INVOKABLE void revealFile(const QString &path);

signals:
    void reduceMotionChanged();
    void keyboardNavChanged();

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    bool m_reduceMotion = false;
    bool m_keyboardNav = false;
};
