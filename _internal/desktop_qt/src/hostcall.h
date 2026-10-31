// One HTTP call to the host under the HostWait policy: idle limit by path, the same request sent once more after a silent
// host, abort without a callback.
#pragma once

#include <QNetworkRequest>
#include <QObject>
#include <QPointer>
#include <QTimer>

#include <functional>

class QNetworkAccessManager;
class QNetworkReply;

class HostCall final : public QObject {
    Q_OBJECT
public:
    /// `status` 0: no answer (refused, or silent past the limit on every attempt: `timedOut`). `body`: the answer as sent.
    using Done = std::function<void(int status, const QByteArray &body, bool timedOut)>;
    /// Tests: this idle limit for every path instead of HostWait::idleMs (0 = the policy).
    static inline int s_idleOverrideMs = 0;
    static HostCall *send(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent);
    /// The caller dropped the call: the open request is aborted and `done` is never called.
    void abort();

private:
    HostCall(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent);
    void attempt();
    void finish(int status, const QByteArray &body, bool timedOut);

    QNetworkAccessManager *m_net;
    QNetworkRequest m_request;
    QByteArray m_method;
    QByteArray m_body;
    Done m_done;
    QPointer<QNetworkReply> m_reply;
    QTimer m_idle;
    int m_attempts = 0;
};
