#include "desktopapi.h"
#include "backend.h"
#include <QtTest>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QTcpServer>
#include <QTcpSocket>
#include <QJsonDocument>
#include <QSignalSpy>

namespace { Backend::Endpoint testEndpoint; }
Backend::Endpoint Backend::endpoint() { return testEndpoint; }
Backend *Backend::instance() { return nullptr; }
void Backend::refreshLibrary() {}

class DesktopApiTests : public QObject {
    Q_OBJECT
    QTcpServer host;
    QByteArray received;
    QByteArray answer;
    bool hold = false;
    QQmlEngine engine;
    std::unique_ptr<QObject> owner;
    DesktopApi *api = nullptr;
    QJSValue done() { return engine.evaluate(QStringLiteral("(function(status, data) { result = {status:status,data:data}; })")); }
    void clear() { received.clear(); engine.globalObject().setProperty(QStringLiteral("result"), QJSValue(QJSValue::NullValue)); }
private slots:
    void initTestCase() {
        QVERIFY(host.listen(QHostAddress::LocalHost));
        testEndpoint = {host.serverPort(), QByteArray("fixture-token")};
        connect(&host, &QTcpServer::newConnection, this, [this] {
            auto *socket = host.nextPendingConnection();
            auto bytes = std::make_shared<QByteArray>();
            connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            connect(socket, &QTcpSocket::readyRead, this, [this,socket,bytes] {
                *bytes += socket->readAll();
                const int header = bytes->indexOf("\r\n\r\n");
                if (header < 0) return;
                int length = 0;
                for (auto line : bytes->left(header).split('\n'))
                    if (line.toLower().startsWith("content-length:")) length = line.mid(15).trimmed().toInt();
                if (bytes->size() < header + 4 + length) return;
                received = *bytes;
                if (hold) return;
                socket->write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: " + QByteArray::number(answer.size()) + "\r\n\r\n" + answer);
                socket->disconnectFromHost();
            });
        });
        qmlRegisterType<DesktopApi>("ApiTest",1,0,"DesktopApi");
        QQmlComponent component(&engine);
        component.setData("import QtQml\nimport ApiTest 1.0\nQtObject { property DesktopApi api: DesktopApi {} }",QUrl());
        owner.reset(component.create());
        QVERIFY2(owner, qPrintable(component.errorString()));
        api = qobject_cast<DesktopApi *>(owner->property("api").value<QObject *>());
        QVERIFY(api);
        clear();
    }
    void jsonArrayAndHeader() {
        clear(); answer = "[{\"id\":\"voice\"}]";
        api->request(QStringLiteral("GET"),QStringLiteral("/api/readaloud/voices"),QJSValue(QJSValue::NullValue),done());
        QTRY_VERIFY(!engine.globalObject().property(QStringLiteral("result")).isNull());
        QVERIFY(received.startsWith("GET /api/readaloud/voices "));
        QVERIFY(received.toLower().contains("x-ebook-token: fixture-token"));
        QVERIFY(engine.globalObject().property(QStringLiteral("result")).property(QStringLiteral("data")).isArray());
    }
    void writes_data() {
        QTest::addColumn<QString>("path");
        QTest::addColumn<QByteArray>("method");
        QTest::addColumn<QString>("json");
        QTest::newRow("settings") << QStringLiteral("/api/preferences") << QByteArray("PUT") << QStringLiteral("{\"sleepSchedule\":{\"from\":\"22:00\",\"to\":\"06:00\",\"minutes\":30}}");
        QTest::newRow("add") << QStringLiteral("/api/listen/import") << QByteArray("POST") << QStringLiteral("{\"path\":\"D:/Sách/Truyện.epub\",\"title\":\"Tên không cắt\",\"sourceFingerprint\":\"fixture\",\"chapters\":[{\"index\":2}]}");
        QTest::newRow("edit") << QStringLiteral("/api/books/fixture/title") << QByteArray("PUT") << QStringLiteral("{\"title\":\"Tên sách dài không cắt\"}");
        QTest::newRow("cover") << QStringLiteral("/api/books/fixture/cover") << QByteArray("DELETE") << QStringLiteral("null");
    }
    void writes() {
        QFETCH(QString,path); QFETCH(QByteArray,method); QFETCH(QString,json);
        clear(); answer = "{\"saved\":true}";
        const auto body = engine.evaluate(QStringLiteral("(") + json + QStringLiteral(")"));
        api->request(QString::fromLatin1(method),path,body,done());
        QTRY_VERIFY(!engine.globalObject().property(QStringLiteral("result")).isNull());
        QVERIFY(received.startsWith(method + " " + path.toUtf8() + " "));
        const auto payload = received.mid(received.indexOf("\r\n\r\n") + 4);
        if (json != QStringLiteral("null")) QCOMPARE(QJsonDocument::fromJson(payload),QJsonDocument::fromJson(json.toUtf8()));
        else QVERIFY(payload.isEmpty());
    }
    void abortDoesNotDeliverLateReply() {
        clear(); hold = true;
        const int id = api->request(QStringLiteral("GET"),QStringLiteral("/api/books/fixture/cover/search?q=old"),QJSValue(QJSValue::NullValue),done());
        QTRY_VERIFY(!received.isEmpty());
        api->cancel(id);
        QTest::qWait(80);
        QVERIFY(engine.globalObject().property(QStringLiteral("result")).isNull());
        hold = false;
    }
};
QTEST_GUILESS_MAIN(DesktopApiTests)
#include "test_desktopapi.moc"
