#include "singleinstance.h"

#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDebug>
#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <memory>

#ifdef Q_OS_WIN
#include <windows.h>
#include <sddl.h>
#endif

namespace {

QString currentSid() {
#ifdef Q_OS_WIN
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token))
        return {};
    QString sid;
    DWORD size = 0;
    GetTokenInformation(token, TokenUser, nullptr, 0, &size);
    auto buffer = std::make_unique<char[]>(size);
    LPWSTR text = nullptr;
    if (size && GetTokenInformation(token, TokenUser, buffer.get(), size, &size)
        && ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER *>(buffer.get())->User.Sid, &text)) {
        sid = QString::fromWCharArray(text);
        LocalFree(text);
    }
    CloseHandle(token);
    return sid;
#else
    return qEnvironmentVariable("USER");
#endif
}

QByteArray readLine(QLocalSocket &socket, int timeoutMs) {
    while (!socket.canReadLine()) {
        if (!socket.waitForReadyRead(timeoutMs))
            return {};
    }
    return socket.readLine().trimmed();
}

} // namespace

SingleInstance::SingleInstance(const QString &name, QObject *parent)
    : QObject(parent), m_name(name.isEmpty() ? defaultName() : name) {}

SingleInstance::~SingleInstance() {
    delete m_server;
#ifdef Q_OS_WIN
    if (m_owner)
        CloseHandle(m_owner);
#endif
}

QString SingleInstance::defaultName() {
    return nameFor(currentSid(), qEnvironmentVariable("LOCALAPPDATA"));
}

QString SingleInstance::nameFor(const QString &sid, const QString &localAppData) {
    QString data = QDir::cleanPath(QDir::fromNativeSeparators(localAppData)).toLower();
    while (data.endsWith(QLatin1Char('/')))
        data.chop(1);
    const QByteArray digest = QCryptographicHash::hash((sid + QLatin1Char('|') + data).toUtf8(), QCryptographicHash::Sha256);
    return QStringLiteral("ABookDesk-") + QString::fromLatin1(digest.toHex().left(16));
}

bool SingleInstance::handOff(const QStringList &files, int timeoutMs) {
    QLocalSocket socket;
    socket.connectToServer(m_name);
    if (!socket.waitForConnected(timeoutMs))
        return false;
    // Có người nghe là có bản đang chạy: kể cả khi nó không đáp kịp, bản này vẫn thoát - hai bản cùng một hồ sơ là hai host
    // ghi cùng preferences.json.
    const QByteArray hello = readLine(socket, timeoutMs);
#ifdef Q_OS_WIN
    bool ok = false;
    const DWORD pid = hello.toULong(&ok);
    if (ok && pid)
        AllowSetForegroundWindow(pid);
#endif
    const QJsonObject message{{QStringLiteral("files"), QJsonArray::fromStringList(files)}};
    socket.write(QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n');
    socket.waitForBytesWritten(timeoutMs);
    if (readLine(socket, timeoutMs) != "ok")
        qWarning().noquote() << "bản ABook đang chạy không đáp lần mở mới" << m_name;
    socket.disconnectFromServer();
    return true;
}

bool SingleInstance::listen() {
    if (m_server)
        return true;
#ifdef Q_OS_WIN
    const std::wstring mutexName = (QStringLiteral("Local\\") + m_name).toStdWString();
    HANDLE owner = CreateMutexW(nullptr, FALSE, mutexName.c_str());
    if (!owner)
        return false;
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        CloseHandle(owner);
        return false;
    }
    m_owner = owner;
#endif
    auto *server = new QLocalServer(this);
    server->setSocketOptions(QLocalServer::UserAccessOption);
    if (!server->listen(m_name)) {
        qWarning().noquote() << "không giữ được kênh một bản:" << server->errorString();
        delete server;
        return false;
    }
    m_server = server;
    connect(server, &QLocalServer::newConnection, this, &SingleInstance::accept);
    return true;
}

void SingleInstance::accept() {
    while (QLocalSocket *socket = m_server->nextPendingConnection()) {
        connect(socket, &QLocalSocket::disconnected, socket, &QObject::deleteLater);
        socket->write(QByteArray::number(QCoreApplication::applicationPid()) + '\n');
        connect(socket, &QLocalSocket::readyRead, this, [this, socket] {
            if (!socket->canReadLine())
                return;
            const QJsonObject message = QJsonDocument::fromJson(socket->readLine()).object();
            QStringList files;
            for (const QJsonValue &file : message.value(QStringLiteral("files")).toArray()) {
                if (file.isString() && !file.toString().isEmpty())
                    files << file.toString();
            }
            socket->write("ok\n");
            socket->flush();
            socket->disconnectFromServer();
            emit launched(files);
        });
    }
}
