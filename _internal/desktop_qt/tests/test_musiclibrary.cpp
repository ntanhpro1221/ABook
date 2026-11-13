// Kho nhạc của app máy tính (qml/MusicLibraryLogic.js): lọc / tìm chạy ở máy chủ (GET /api/music/library, abook/webui/music_library.py) - bảng
// ca chung tests/fixtures/music_library/cases.json được test_music_library.py kiểm KẾT QUẢ. Ở đây: mọi bộ lọc của bảng đi qua chuỗi truy vấn
// nguyên vẹn (máy chủ nhận đúng bộ lọc ấy), cộng các phép tính của dòng / sheet chi tiết (phần trăm tải, năng lượng, thời lượng). Đo: dựng chuỗi
// truy vấn cho cả bảng nhiều lần dưới 50 ms.
#include <QElapsedTimer>
#include <QFile>
#include <QJSEngine>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QtTest>

namespace {
QString readText(const QString &path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) return {};
    return QString::fromUtf8(file.readAll());
}
}  // namespace

class MusicLibraryTests : public QObject {
    Q_OBJECT
    QJSEngine engine;
    QJsonObject fixture;

    QJSValue call(const QString &name, const QJSValueList &args) {
        const QJSValue result = engine.globalObject().property(name).call(args);
        if (result.isError()) qWarning() << result.toString();
        return result;
    }

private slots:
    void initTestCase() {
        // `.pragma library` là chỉ thị của QML, không phải JS: bỏ trước khi chạy file trong QJSEngine trần.
        QString source = readText(QStringLiteral(MUSICLIBRARY_QML_DIR "/MusicLibraryLogic.js"));
        QVERIFY2(!source.isEmpty(), "không đọc được MusicLibraryLogic.js");
        source.replace(QStringLiteral(".pragma library"), QString());
        const QJSValue loaded = engine.evaluate(source, QStringLiteral("MusicLibraryLogic.js"));
        QVERIFY2(!loaded.isError(), qPrintable(loaded.toString()));
        fixture = QJsonDocument::fromJson(readText(QStringLiteral(MUSICLIBRARY_FIXTURE)).toUtf8()).object();
        QVERIFY2(fixture.value("cases").toArray().size() >= 20, "bảng ca chung quá ít");
    }

    void everySharedCaseReachesTheServerUnchanged() {
        const QJsonArray cases = fixture.value("cases").toArray();
        for (const QJsonValue &item : cases) {
            const QJsonObject theCase = item.toObject();
            const QJsonObject filter = theCase.value("filter").toObject();
            QJSValue filters = call("noFilters", {});
            for (auto it = filter.begin(); it != filter.end(); ++it) filters.setProperty(it.key(), engine.toScriptValue(it.value().toVariant()));
            const QString query = call("libraryQuery", {filters, false}).toString();
            const QVariantMap sent = call("parseQuery", {query}).toVariant().toMap();
            QVariantMap expected;
            for (auto it = filter.begin(); it != filter.end(); ++it) {
                if (it.value().isString() && !it.value().toString().trimmed().isEmpty()) expected.insert(it.key(), it.value().toString().trimmed());
                if (it.value().isBool() && it.value().toBool()) expected.insert(it.key(), true);
            }
            QCOMPARE(sent, expected);
            if (expected.isEmpty()) QCOMPARE(query, QString());
        }
    }

    void savedPartAsksForSavedTracksOnly() {
        QCOMPARE(call("libraryQuery", {call("noFilters", {}), true}).toString(), QStringLiteral("?saved=1"));
    }

    void filteringIgnoresTheSearchWords() {
        QJSValue filters = call("noFilters", {});
        filters.setProperty("q", QStringLiteral("mưa"));
        QVERIFY(!call("filtering", {filters}).toBool());
        filters.setProperty("tempo", QStringLiteral("slow"));
        QVERIFY(call("filtering", {filters}).toBool());
    }

    void downloadStateOfARow() {
        const QJSValue track = engine.toScriptValue(QVariantMap{{"link", "https://a"}, {"downloaded", false}});
        auto downloads = [&](const QVariantMap &active, const QVariantMap &failed) { return engine.toScriptValue(QVariantMap{{"active", active}, {"failed", failed}}); };
        QJSValue state = call("loadOf", {track, downloads({{"https://a", QVariantMap{{"done", 50}, {"total", 200}}}}, {})});
        QCOMPARE(state.property("kind").toString(), QStringLiteral("loading"));
        QCOMPARE(state.property("percent").toInt(), 25);
        state = call("loadOf", {track, downloads({{"https://a", QVariantMap{{"done", 199}, {"total", 200}}}}, {})});
        QCOMPARE(state.property("percent").toInt(), 99);
        state = call("loadOf", {track, downloads({{"https://a", QVariantMap{{"done", 5}, {"total", QVariant()}}}}, {})});
        QVERIFY(state.property("percent").isNull());
        QCOMPARE(call("loadOf", {track, downloads({}, {{"https://a", "mất mạng"}})}).property("kind").toString(), QStringLiteral("failed"));
        QCOMPARE(call("loadOf", {track, QJSValue()}).property("kind").toString(), QStringLiteral("none"));
    }

    void savedLineNeedsADownloadedSong() {
        // formatSize(0) = "1 KB": 0 bài không được thành "Đã tải 0 bài · 1 KB" (cùng luật web savedSummary, Android savedSummaryText).
        auto saved = [&](int count, double bytes) { return engine.toScriptValue(QVariantMap{{"count", count}, {"bytes", bytes}}); };
        QVERIFY(!call("showsSavedSize", {saved(0, 0)}).toBool());
        QVERIFY(!call("showsSavedSize", {saved(0, 512)}).toBool());
        QVERIFY(!call("showsSavedSize", {QJSValue()}).toBool());
        QVERIFY(call("showsSavedSize", {saved(1, 400)}).toBool());
    }

    void energyPercentAndClock() {
        QCOMPARE(call("energyPercent", {-1.0}).toInt(), 0);
        QCOMPARE(call("energyPercent", {0.0}).toInt(), 50);
        QCOMPARE(call("energyPercent", {0.582}).toInt(), 79);
        QVERIFY(call("energyPercent", {QJSValue()}).isNull());
        QCOMPARE(call("percent", {0.946}).toInt(), 95);
        QCOMPARE(call("clock", {187}).toString(), QStringLiteral("3:07"));
        QCOMPARE(call("previewPath", {QStringLiteral("https://a/b c.mp3")}).toString(), QStringLiteral("/api/music/track?link=https%3A%2F%2Fa%2Fb%20c.mp3"));
    }

    void buildingQueriesIsInstant() {
        const QJsonArray cases = fixture.value("cases").toArray();
        QElapsedTimer timer;
        timer.start();
        for (int round = 0; round < 50; ++round)
            for (const QJsonValue &item : cases) {
                QJSValue filters = call("noFilters", {});
                const QJsonObject filter = item.toObject().value("filter").toObject();
                for (auto it = filter.begin(); it != filter.end(); ++it) filters.setProperty(it.key(), engine.toScriptValue(it.value().toVariant()));
                call("libraryQuery", {filters, false});
            }
        const double perRound = timer.nsecsElapsed() / 1e6 / 50;
        qInfo("MusicLibraryLogic.libraryQuery: %.3f ms cho %d ca", perRound, int(cases.size()));
        QVERIFY2(perRound < 50.0, qPrintable(QString::number(perRound)));
    }
};

QTEST_GUILESS_MAIN(MusicLibraryTests)
#include "test_musiclibrary.moc"
