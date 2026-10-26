// Đồ giả cho bộ thử: bộ phát âm thanh và đường HTTP không cần thiết bị hay host.
#pragma once

#include "audioout.h"
#include "playernet.h"

#include <QHash>
#include <QJsonArray>
#include <QJsonObject>
#include <QUrl>

#include <functional>

class FakeOut final : public AudioOut {
    Q_OBJECT
public:
    explicit FakeOut(QObject *parent = nullptr) : AudioOut(parent) {}
    void load(const QUrl &source, double startSeconds) override {
        url = source;
        pos = startSeconds;
        isPlaying = false;
        ++loads;
        log << QStringLiteral("load");
        emit durationChanged(dur);
    }
    void play() override {
        isPlaying = true;
        log << QStringLiteral("play");
        emit playingChanged(true);
    }
    void pause() override {
        isPlaying = false;
        log << QStringLiteral("pause");
        emit playingChanged(false);
    }
    void stop() override {
        isPlaying = false;
        log << QStringLiteral("stop");
    }
    void seek(double seconds) override {
        pos = seconds;
        log << QStringLiteral("seek");
        emit seeked();
    }
    void setRate(double value) override { rate = value; }
    void setVolume(double value) override { volume = value; }
    double position() const override { return pos; }
    double duration() const override { return dur; }
    bool playing() const override { return isPlaying; }

    /// Hết nguồn như bộ phát thật: dừng rồi báo ended.
    void finish() {
        pos = dur;
        isPlaying = false;
        emit playingChanged(false);
        emit ended();
    }
    void fail(const QString &reason) { emit failed(reason); }

    QUrl url;
    double pos = 0;
    double dur = 100;
    double rate = 1;
    double volume = 1;
    bool isPlaying = false;
    int loads = 0;
    QStringList log;
};

class FakeNet final : public PlayerNet {
    Q_OBJECT
public:
    struct Call {
        QByteArray method;
        QString path;
        QJsonObject body;
    };
    explicit FakeNet(QObject *parent = nullptr) : PlayerNet(parent) {}

    QUrl audioUrl(const QString &bookId, int chapterId) const override {
        return QUrl(QStringLiteral("http://fake/media/books/%1/chapters/%2").arg(bookId).arg(chapterId));
    }
    void request(const QByteArray &method, const QString &path, const QJsonObject &body, Done done, bool) override {
        calls.append({method, path, body});
        if (offline) {
            done(0, {});
            return;
        }
        if (hold) {
            held.append([done, method, path, body, this] { reply(method, path, body, done); });
            return;
        }
        reply(method, path, body, done);
    }
    void releaseHeld() {
        auto list = held;
        held.clear();
        for (const auto &item : list)
            item();
    }

    QList<Call> callsTo(const QString &suffix, const QByteArray &method = "POST") const {
        QList<Call> list;
        for (const Call &call : calls)
            if (call.method == method && call.path.endsWith(suffix))
                list.append(call);
        return list;
    }

    QHash<QString, QJsonObject> books;   // mã -> JSON của GET /api/listen/books/<id>
    QHash<QString, QJsonObject> scripts; // đường dẫn đầy đủ -> JSON của GET /api/books/<id>/chapters/<n>/script
    int progressStatus = 200;
    double doneTail = 15;                // như DONE_TAIL_SECONDS của máy chủ (đủ cho phép thử)
    bool offline = false;
    bool hold = false;
    QList<Call> calls;

private:
    void reply(const QByteArray &method, const QString &path, const QJsonObject &body, const Done &done) {
        if (method == "GET" && path.startsWith(QStringLiteral("/api/listen/books/"))) {
            const auto found = books.constFind(path.mid(int(QStringLiteral("/api/listen/books/").size())));
            if (found == books.constEnd())
                done(404, {});
            else
                done(200, *found);
            return;
        }
        if (method == "GET" && path.endsWith(QStringLiteral("/script"))) {
            const auto found = scripts.constFind(path);
            if (found == scripts.constEnd())
                done(404, {});
            else
                done(200, *found);
            return;
        }
        if (method == "POST" && path.endsWith(QStringLiteral("/progress"))) {
            if (progressStatus != 200) {
                done(progressStatus, {});
                return;
            }
            const int chapter = body.value(QStringLiteral("chapterId")).toInt();
            const double seconds = body.value(QStringLiteral("seconds")).toDouble();
            const double duration = body.value(QStringLiteral("duration")).toDouble();
            QJsonObject chapters{{QString::number(chapter), QJsonObject{{QStringLiteral("heard"), seconds},
                                                                       {QStringLiteral("done"), duration - seconds <= doneTail},
                                                                       {QStringLiteral("duration"), duration}}}};
            done(200, QJsonObject{{QStringLiteral("chapters"), chapters},
                                  {QStringLiteral("last"), QJsonObject{{QStringLiteral("chapterId"), chapter}, {QStringLiteral("seconds"), seconds},
                                                                       {QStringLiteral("at"), double(serverNow) / 1000.0}}}});
            return;
        }
        done(200, {});
    }
    QList<std::function<void()>> held;

public:
    qint64 serverNow = 0;
};

/// JSON của một cuốn như GET /api/listen/books/<id>.
inline QJsonObject makeBook(const QString &id, int chapterCount = 4, bool complete = true, int lastChapter = 0, double lastSeconds = 0,
                            double lastAtSeconds = 0, double rate = 0, const QString &record = QStringLiteral("r1")) {
    QJsonArray chapters;
    for (int i = 1; i <= chapterCount; ++i)
        chapters.append(QJsonObject{{QStringLiteral("id"), i},
                                    {QStringLiteral("index"), i},
                                    {QStringLiteral("title"), QStringLiteral("Chương %1").arg(i)},
                                    {QStringLiteral("subtitle"), QStringLiteral("Tên %1").arg(i)},
                                    {QStringLiteral("fullTitle"), QStringLiteral("Chương %1 · Tên %1").arg(i)},
                                    {QStringLiteral("duration"), 100.0},
                                    {QStringLiteral("available"), true},
                                    {QStringLiteral("state"), QJsonValue::Null}});
    QJsonObject state{{QStringLiteral("chapters"), QJsonObject()}};
    if (lastChapter > 0) {
        state.insert(QStringLiteral("last"), QJsonObject{{QStringLiteral("chapterId"), lastChapter}, {QStringLiteral("seconds"), lastSeconds}, {QStringLiteral("at"), lastAtSeconds}});
        state.insert(QStringLiteral("chapters"), QJsonObject{{QString::number(lastChapter), QJsonObject{{QStringLiteral("heard"), lastSeconds}, {QStringLiteral("done"), false}, {QStringLiteral("duration"), 100.0}}}});
    }
    if (rate > 0)
        state.insert(QStringLiteral("rate"), rate);
    return QJsonObject{{QStringLiteral("id"), id},
                       {QStringLiteral("title"), QStringLiteral("Sách %1").arg(id)},
                       {QStringLiteral("narrator"), QStringLiteral("Người kể")},
                       {QStringLiteral("complete"), complete},
                       {QStringLiteral("producing"), false},
                       {QStringLiteral("chapters"), chapters},
                       {QStringLiteral("records"), QJsonArray{QJsonObject{{QStringLiteral("id"), record}, {QStringLiteral("active"), true}}}},
                       {QStringLiteral("cover"), QJsonObject{{QStringLiteral("version"), 7}}},
                       {QStringLiteral("state"), state}};
}
