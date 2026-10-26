#pragma once
#include <QObject>
#include <QJSValue>
#include <QNetworkAccessManager>
#include <QHash>
#include <QtQml/qqmlregistration.h>

// JSON boundary shared by Settings and the book dialogs. Uses the existing host,
// including its session header; arrays and null remain arrays and null.
class DesktopApi : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString thirdParty READ thirdParty CONSTANT)
public:
    explicit DesktopApi(QObject *parent = nullptr);
    Q_INVOKABLE int request(const QString &method, const QString &path, const QJSValue &body, const QJSValue &done);
    Q_INVOKABLE void cancel(int id);
    Q_INVOKABLE QString imageData(const QUrl &file) const;
    Q_INVOKABLE QString localPath(const QUrl &file) const;
    Q_INVOKABLE QUrl mediaUrl(const QString &path) const;
    Q_INVOKABLE void refreshLibrary();
    Q_INVOKABLE void preview(const QString &path);
    Q_INVOKABLE void stopPreview();
    static void setPreviewOut(class AudioOut *out);
    QString thirdParty() const;
private:
    QNetworkAccessManager m_net;
    int m_next = 0;
    QHash<int, class QNetworkReply *> m_pending;
};
