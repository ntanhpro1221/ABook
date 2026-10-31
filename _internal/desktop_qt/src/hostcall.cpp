#include "hostcall.h"

#include "hostwait.h"

#include <QNetworkAccessManager>
#include <QNetworkReply>

HostCall *HostCall::send(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent) {
    auto *call = new HostCall(net, std::move(request), method, body, std::move(done), parent);
    call->attempt();
    return call;
}

HostCall::HostCall(QNetworkAccessManager *net, QNetworkRequest request, const QByteArray &method, const QByteArray &body, Done done, QObject *parent)
    : QObject(parent), m_net(net), m_request(std::move(request)), m_method(method), m_body(body), m_done(std::move(done)) {
    m_request.setTransferTimeout(0);    // Qt's own limit cannot tell a silent host from the caller's abort: m_idle decides
    m_idle.setSingleShot(true);
    m_idle.setInterval(s_idleOverrideMs ? s_idleOverrideMs : HostWait::idleMs(m_request.url().path()));
    connect(&m_idle, &QTimer::timeout, this, [this] {
        QNetworkReply *silent = m_reply;
        m_reply = nullptr;
        if (silent) silent->abort();
        if (m_attempts < HostWait::kAttempts) attempt();
        else finish(0, {}, true);
    });
}

void HostCall::attempt() {
    ++m_attempts;
    QNetworkReply *reply = m_method == "GET" && m_body.isEmpty() ? m_net->get(m_request) : m_net->sendCustomRequest(m_request, m_method, m_body);
    m_reply = reply;
    // Bytes either way restart the limit. Qt reports nothing inside a half-received response head; the host sends its
    // head in one write, so the limit runs on the body.
    const auto alive = [this] { m_idle.start(); };
    connect(reply, &QNetworkReply::metaDataChanged, this, alive);
    connect(reply, &QNetworkReply::downloadProgress, this, alive);
    connect(reply, &QNetworkReply::uploadProgress, this, alive);
    connect(reply, &QNetworkReply::finished, this, [this, reply] {
        reply->deleteLater();
        if (reply != m_reply) return;    // aborted here: by the idle limit or by the caller
        m_reply = nullptr;
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        finish(status, status ? reply->readAll() : QByteArray(), false);
    });
    m_idle.start();
}

void HostCall::finish(int status, const QByteArray &body, bool timedOut) {
    m_idle.stop();
    const Done done = std::move(m_done);
    m_done = {};
    deleteLater();
    if (done) done(status, body, timedOut);
}

void HostCall::abort() {
    m_done = {};
    m_idle.stop();
    QNetworkReply *open = m_reply;
    m_reply = nullptr;
    if (open) open->abort();
    deleteLater();
}
