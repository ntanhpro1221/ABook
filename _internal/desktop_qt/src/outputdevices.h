#pragma once
#include <QObject>
#include <QVariantList>
#include <functional>

// Event-driven adapter. COM enumeration and switching stay on the audio thread.
class OutputDevices : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList devices READ devices NOTIFY changed)
    Q_PROPERTY(QString selected READ selected NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
    using Request = std::function<void(bool, const QString &)>;
    explicit OutputDevices(Request request, QObject *parent = nullptr) : QObject(parent), m_request(std::move(request)) {}
    QVariantList devices() const { return m_devices; }
    QString selected() const { return m_selected; }
    QString error() const { return m_error; }
    bool busy() const { return m_busy; }
    Q_INVOKABLE void refresh() { if (m_busy) return; m_busy = true; m_error.clear(); emit changed(); m_request(false, {}); }
    Q_INVOKABLE void select(const QString &id) { if (m_busy) return; m_busy = true; m_error.clear(); emit changed(); m_request(true, id); }
    void complete(const QVariantList &devices, const QString &selected, bool accepted) {
        m_devices = devices; m_selected = selected; m_busy = false;
        m_error = accepted ? QString() : QStringLiteral("Chưa đổi được thiết bị phát. Vẫn dùng thiết bị trước.");
        emit changed();
    }
signals:
    void changed();
private:
    Request m_request;
    QVariantList m_devices;
    QString m_selected, m_error;
    bool m_busy = false;
};
