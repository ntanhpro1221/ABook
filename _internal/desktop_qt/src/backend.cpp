#include "backend.h"

#include <QJSEngine>
#include "bench.h"
#include "librarymodel.h"

#include <QCoreApplication>
#include <QDebug>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QStandardPaths>
#include <QTimer>
#include <QUrlQuery>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

namespace {
Backend *g_instance = nullptr;
QMutex g_endpointLock;
Backend::Endpoint g_endpoint;

void publishEndpoint(int port, const QByteArray &token) {
    QMutexLocker lock(&g_endpointLock);
    g_endpoint = {port, token};
}
constexpr int kStopGraceMs = 5000;  // như HOST_STOP_GRACE của vỏ Tauri

QString localAppData() {
    return qEnvironmentVariable("LOCALAPPDATA");
}

QString abookVersion() {
#ifdef ABOOK_VERSION
    return QStringLiteral(ABOOK_VERSION);
#else
    return {};
#endif
}
}  // namespace

Backend::Backend(QObject *parent) : QObject(parent), m_library(new LibraryModel(this)) {
    g_instance = this;
    m_since.start();
}

Backend::~Backend() {
    stop();
    if (g_instance == this)
        g_instance = nullptr;
}

Backend::Endpoint Backend::endpoint() {
    QMutexLocker lock(&g_endpointLock);
    return g_endpoint;
}

Backend *Backend::instance() {
    return g_instance;
}

Backend *Backend::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_instance, QJSEngine::CppOwnership);
    return g_instance;
}

QString Backend::version() const {
    return abookVersion();
}

QString Backend::logPath() const {
    const QString base = localAppData();
    return base.isEmpty() ? QString() : QDir(base).filePath(QStringLiteral("ABook/logs/host.log"));
}

// Cách tìm Python giống host_command() của vỏ Tauri:
//  1. ABOOK_HOST_PYTHON (+ ABOOK_HOST_APP = thư mục chứa `abook`)  2. bản dev: thư mục mã nguồn tìm ngược từ file chạy,
//     python của runtime cạnh mã  3. bản cài: resources/python + resources/app cạnh file chạy.
bool Backend::resolveLaunch(Launch *out, QString *error) const {
    const QString envPython = qEnvironmentVariable("ABOOK_HOST_PYTHON");
    const QString envApp = qEnvironmentVariable("ABOOK_HOST_APP");
    QString sourceRoot;
    for (QDir dir(QCoreApplication::applicationDirPath()); ; ) {
        if (QFileInfo::exists(dir.filePath(QStringLiteral("abook/webui/host.py")))) {
            sourceRoot = dir.absolutePath();
            break;
        }
        if (!dir.cdUp())
            break;
    }
    if (!envPython.isEmpty()) {
        out->python = envPython;
        out->folder = envApp.isEmpty() ? sourceRoot : envApp;
        out->bundled = false;
    } else if (!sourceRoot.isEmpty()) {
        out->python = QDir(sourceRoot).filePath(QStringLiteral("runtime/.venv/Scripts/pythonw.exe"));
        out->folder = sourceRoot;
        out->bundled = false;
    } else {
        const QDir resources(QDir(QCoreApplication::applicationDirPath()).filePath(QStringLiteral("resources")));
        out->python = resources.filePath(QStringLiteral("python/pythonw.exe"));
        out->folder = resources.filePath(QStringLiteral("app"));
        out->bundled = true;
    }
    if (!QFileInfo(out->python).isFile()) {
        qWarning().noquote() << "thiếu Python của host:" << QDir::toNativeSeparators(out->python);
        *error = QStringLiteral("ABook thiếu một phần để chạy. Bạn cài lại ABook rồi thử lại.");
        return false;
    }
    if (out->folder.isEmpty() || !QFileInfo::exists(QDir(out->folder).filePath(QStringLiteral("abook/webui/host.py")))) {
        qWarning().noquote() << "thiếu mã host:" << QDir::toNativeSeparators(out->folder);
        *error = QStringLiteral("ABook thiếu một phần để chạy. Bạn cài lại ABook rồi thử lại.");
        return false;
    }
    return true;
}

void Backend::start() {
    if (m_proc)
        return;
    ++m_generation;
    m_quitting = false;
    m_state = Starting;
    m_message.clear();
    m_port = 0;
    m_token.clear();
    publishEndpoint(0, {});
    m_buffer.clear();
    emit stateChanged();

    Launch launch;
    QString error;
    if (!resolveLaunch(&launch, &error)) {
        fail(error);
        return;
    }
    auto *proc = new QProcess(this);
    m_proc = proc;
    proc->setProgram(launch.python);
    proc->setArguments({QStringLiteral("-m"), QStringLiteral("abook.webui.host"), QStringLiteral("--version"), abookVersion()});
    proc->setWorkingDirectory(launch.folder);
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
    // Bản cài: Studio tải thêm vào %LOCALAPPDATA%\ABook\Studio, runtime phải nằm ở đó (như vỏ Tauri).
    QString studio = qEnvironmentVariable("ABOOK_STUDIO_ROOT");
    if (studio.isEmpty() && launch.bundled && !localAppData().isEmpty())
        studio = QDir(localAppData()).filePath(QStringLiteral("ABook/Studio"));
    if (!studio.isEmpty()) {
        proc->setArguments(proc->arguments() << QStringLiteral("--studio") << studio);
        env.insert(QStringLiteral("ABOOK_RUNTIME"), QDir(studio).filePath(QStringLiteral("runtime")));
    }
    proc->setProcessEnvironment(env);
    const QString log = logPath();
    if (!log.isEmpty()) {
        QDir().mkpath(QFileInfo(log).absolutePath());
        proc->setStandardErrorFile(log, QIODevice::Append);
    }
#ifdef Q_OS_WIN
    proc->setCreateProcessArgumentsModifier([](QProcess::CreateProcessArguments *args) { args->flags |= CREATE_NO_WINDOW; });
#endif
    const quint64 generation = m_generation;
    connect(proc, &QProcess::readyReadStandardOutput, this, [this, generation] {
        if (generation == m_generation)
            onStdout();
    });
    connect(proc, &QProcess::finished, this, [this, generation](int code, QProcess::ExitStatus status) {
        if (generation == m_generation)
            onFinished(code, status);
    });
    connect(proc, &QProcess::errorOccurred, this, [this, generation, proc](QProcess::ProcessError e) {
        if (generation != m_generation || e != QProcess::FailedToStart)
            return;
        qWarning().noquote() << "host không chạy được:" << proc->errorString();
        fail(QStringLiteral("ABook chưa mở được. Bạn thử lại; nếu vẫn lỗi, xem nhật ký trong Cài đặt."));
    });
    m_since.restart();
    proc->start();
    Bench::mark(QStringLiteral("host_spawned"));
}

void Backend::onStdout() {
    m_buffer += m_proc->readAllStandardOutput();
    int nl;
    while ((nl = m_buffer.indexOf('\n')) >= 0) {
        const QByteArray line = m_buffer.left(nl).trimmed();
        m_buffer.remove(0, nl + 1);
        if (line.isEmpty())
            continue;
        const QJsonObject message = QJsonDocument::fromJson(line).object();
        const QString address = message.value(QStringLiteral("ready")).toString();
        if (!address.isEmpty())
            parseReady(address);
        // Các thông điệp khác của host (hộp thoại, sự kiện) thuộc các bước sau (D2: thêm sách, chọn file).
    }
}

void Backend::parseReady(const QString &address) {
    const QUrl url(address);
    m_port = url.port();
    m_token = QUrlQuery(url).queryItemValue(QStringLiteral("t"));
    if (m_port <= 0) {
        fail(QStringLiteral("ABook chưa mở được. Bạn thử lại; nếu vẫn lỗi, xem nhật ký trong Cài đặt."));
        return;
    }
    publishEndpoint(m_port, m_token.toUtf8());
    m_readyMs = int(m_since.elapsed());
    m_state = Ready;
    m_message.clear();
    emit stateChanged();
    Bench::mark(QStringLiteral("host_ready"));
    refreshLibrary();
}

void Backend::onFinished(int, QProcess::ExitStatus) {
    if (m_quitting)
        return;
    m_proc->deleteLater();
    m_proc = nullptr;
    fail(QStringLiteral("ABook dừng bất ngờ. Bạn thử lại; nếu vẫn lỗi, xem nhật ký trong Cài đặt."));
}

void Backend::fail(const QString &message) {
    m_state = Failed;
    m_message = message;
    emit stateChanged();
}

QNetworkReply *Backend::get(const QString &path) {
    QNetworkRequest request(QUrl(QStringLiteral("http://127.0.0.1:%1%2").arg(m_port).arg(path)));
    request.setRawHeader("X-Ebook-Token", m_token.toUtf8());
    request.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
    request.setTransferTimeout(30000);
    return m_net.get(request);
}

void Backend::refreshLibrary() {
    if (m_state != Ready)
        return;
    const quint64 generation = m_generation;
    QNetworkReply *reply = get(QStringLiteral("/api/listen/library"));
    connect(reply, &QNetworkReply::finished, this, [this, reply, generation] {
        reply->deleteLater();
        if (generation != m_generation)
            return;
        if (reply->error() != QNetworkReply::NoError) {
            m_library->setError(QStringLiteral("Chưa lấy được thư viện. Bạn thử lại."));
            return;
        }
        const QJsonDocument doc = QJsonDocument::fromJson(reply->readAll());
        m_library->setBooks(doc.array());
        if (!m_libraryLoaded) {
            m_libraryLoaded = true;
            emit libraryLoadedChanged();
            Bench::mark(QStringLiteral("library_loaded"));
        }
    });
}

void Backend::restart() {
    if (!m_proc) {
        start();
        return;
    }
    ++m_generation;  // mọi tín hiệu của tiến trình cũ bị bỏ qua
    m_quitting = true;
    m_state = Starting;
    m_message.clear();
    m_libraryLoaded = false;
    emit stateChanged();
    emit libraryLoadedChanged();
    QProcess *old = m_proc;
    m_proc = nullptr;
    old->disconnect(this);
    connect(old, &QProcess::finished, this, [this, old] {
        old->deleteLater();
        start();
    });
    old->write("{\"quit\": true}\n");
    old->closeWriteChannel();
    QTimer::singleShot(kStopGraceMs, old, [old] {
        if (old->state() != QProcess::NotRunning)
            old->kill();
    });
}

void Backend::stop() {
    m_quitting = true;
    if (!m_proc)
        return;
    QProcess *proc = m_proc;
    m_proc = nullptr;
    proc->disconnect(this);
    if (proc->state() != QProcess::NotRunning) {
        proc->write("{\"quit\": true}\n");
        proc->closeWriteChannel();
        if (!proc->waitForFinished(kStopGraceMs)) {
            proc->kill();
            proc->waitForFinished(2000);
        }
    }
    delete proc;
}
