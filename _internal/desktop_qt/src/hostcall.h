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
    /// Tests: no wall clock - the limit runs only on advanceIdle(), so what a test counts (requests, retries) follows the cause
    /// (a silent host, bytes that keep coming) and not how fast or busy the machine is.
    static inline bool s_manualClock = false;
    /// Tests, s_manualClock: body bytes every call has received so far (wait for the bytes sent before advancing the clock).
    static inline qint64 s_bytesHeard = 0;
    /// Tests, s_manualClock: `ms` of silence pass for every open call; one silent for its whole limit acts as on the wall clock.
    static void advanceIdle(int ms);
    static HostCall *send(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent);
    /// The caller dropped the call: the open request is aborted and `done` is never called.
    void abort();

private:
    HostCall(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent);
    void attempt();
    void restartIdle();
    void idleExpired();
    void finish(int status, const QByteArray &body, bool timedOut);

    QNetworkAccessManager *m_net;
    QNetworkRequest m_request;
    QByteArray m_method;
    QByteArray m_body;
    Done m_done;
    QPointer<QNetworkReply> m_reply;
    QTimer m_idle;
    int m_attempts = 0;
    int m_silentMs = 0;    // s_manualClock: silence since the last restart
};
