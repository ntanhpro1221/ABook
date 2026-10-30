// Bộ thử "Đọc theo" và phần nghe của trang sách: kịch bản -> đoạn / câu / chữ, câu và chữ đang đọc ở một giây (chỉ phát tín hiệu khi đổi),
// luật cuộn theo, nhãn nút chính của trang sách.
#include "bookdetail.h"
#include "fakes.h"
#include "readalong.h"

#include <QSignalSpy>
#include <QTemporaryDir>
#include <QtTest>

using namespace ScriptLogic;

namespace {
qint64 g_now = 1'800'000'000'000;
qint64 fakeNow() { return g_now; }

QJsonObject segment(int paragraph, const QString &text, double start, double end, const QString &kind = QStringLiteral("narration"), const QString &speaker = QString(),
                    bool words = true) {
    QJsonObject item{{QStringLiteral("paragraph"), paragraph}, {QStringLiteral("text"), text}, {QStringLiteral("kind"), kind}, {QStringLiteral("speaker"), speaker},
                     {QStringLiteral("start"), start}, {QStringLiteral("end"), end}};
    if (words) {
        const QStringList tokens = text.split(QLatin1Char(' '), Qt::SkipEmptyParts);
        QJsonArray spans;
        const double step = (end - start) / double(qMax<qsizetype>(1, tokens.size())) * 1000.0;
        for (int i = 0; i < tokens.size(); ++i)
            spans.append(QJsonArray{start * 1000.0 + step * i, start * 1000.0 + step * (i + 1)});
        item.insert(QStringLiteral("words"), spans);
    }
    return item;
}

QJsonObject sampleScript(bool timed = true) {
    QJsonArray segments;
    segments.append(segment(0, QStringLiteral("Chương 1 - Mở đầu"), 0, 2, QStringLiteral("heading")));
    segments.append(segment(1, QStringLiteral("Một hai ba bốn."), 2.5, 6));
    segments.append(segment(1, QStringLiteral("Năm sáu bảy."), 6.5, 9));
    segments.append(segment(2, QStringLiteral("“Chào bạn.”"), 10, 12, QStringLiteral("dialogue"), QStringLiteral("Lan")));
    segments.append(segment(3, QStringLiteral("* * *"), 13, 13.5));
    segments.append(segment(4, QStringLiteral("Hết rồi nhé."), 14, 20, QStringLiteral("narration"), QString(), false));
    return QJsonObject{{QStringLiteral("chapterId"), 1}, {QStringLiteral("timed"), timed}, {QStringLiteral("segments"), segments}};
}
} // namespace

class ReadAlongTest : public QObject {
    Q_OBJECT

    struct Rig {
        QTemporaryDir dir;
        FakeOut out;
        FakeNet net;
        std::unique_ptr<Player> player;
        std::unique_ptr<ReadAlong> read;
        Rig() {
            net.serverNow = g_now;
            net.books.insert(QStringLiteral("a"), makeBook(QStringLiteral("a"), 3, true));
            net.scripts.insert(QStringLiteral("/api/books/a/chapters/1/script"), sampleScript());
            net.scripts.insert(QStringLiteral("/api/books/a/chapters/2/script"), sampleScript(false));
            player = std::make_unique<Player>(&out, &net, dir.filePath(QStringLiteral("outbox.json")), nullptr, fakeNow);
            player->setFreshSpotMs(0);
            read = std::make_unique<ReadAlong>(player.get(), &net);
            Player::setInstance(player.get());
        }
        ~Rig() { Player::setInstance(nullptr); }
        void openAndLoad(bool play = false) {
            player->open(QStringLiteral("a"), 1, 0, play);
            read->setActive(true);
            read->reload();
        }
    };

private slots:
    void init() { g_now = 1'800'000'000'000; }

    void scriptGroupsParagraphsAndOffsets() {
        const Script script = parseScript(sampleScript());
        QCOMPARE(script.segments.size(), 6);
        QCOMPARE(script.paragraphs.size(), 5);
        QCOMPARE(script.paragraphs[0].kind, QStringLiteral("heading"));
        QCOMPARE(script.paragraphs[1].text, QStringLiteral("Một hai ba bốn. Năm sáu bảy."));
        QCOMPARE(script.paragraphs[1].count, 2);
        QCOMPARE(script.segments[2].textStart, 16);                  // sau "Một hai ba bốn." (15) và một khoảng trắng
        QCOMPARE(script.segments[2].textEnd, 28);
        QCOMPARE(script.paragraphs[2].speaker, QStringLiteral("Lan")); // nhãn người nói trước câu thoại đầu
        QCOMPARE(script.paragraphs[3].kind, QStringLiteral("scene"));
        QCOMPARE(script.paragraphs[4].kind, QStringLiteral("body"));
        QCOMPARE(script.segments[1].wordChars.size(), 4);
        QCOMPARE(script.segments[1].wordChars[1], qMakePair(4, 7));
        QVERIFY(script.segments[5].words.isEmpty());                 // câu không có mốc chữ: chỉ sáng cả câu
    }

    void wordsWithWrongCountAreIgnored() {
        QJsonObject item = segment(0, QStringLiteral("a b c"), 0, 3);
        QJsonArray spans = item.value(QStringLiteral("words")).toArray();
        spans.removeLast();
        QVERIFY(usableWords(QStringLiteral("a b c"), spans).isEmpty());
        QVERIFY(usableWords(QStringLiteral("a b c"), item.value(QStringLiteral("words")).toArray()).size() == 3);
        // mốc đi lùi: bỏ
        QVERIFY(usableWords(QStringLiteral("a b"), QJsonArray{QJsonArray{500, 600}, QJsonArray{100, 200}}).isEmpty());
    }

    void sentenceAndWordLookup() {
        const Script script = parseScript(sampleScript());
        QCOMPARE(sentenceIndexAt(script.starts, 0.0), 0);
        QCOMPARE(sentenceIndexAt(script.starts, 2.46), 1);   // sớm 0,05 giây
        QCOMPARE(sentenceIndexAt(script.starts, 2.4), 0);
        QCOMPARE(sentenceIndexAt(script.starts, 100), 5);
        QCOMPARE(sentenceIndexAt({1.0, 2.0}, 0.5), -1);
        const auto &words = script.segments[1].words;          // 4 chữ trong 2,5..6 s
        QCOMPARE(wordIndexAt(words, 2460), 0);                 // sáng sớm 40 ms
        QCOMPARE(wordIndexAt(words, 2400), -1);
        QCOMPARE(wordIndexAt(words, 3500), 1);
        QCOMPARE(wordIndexAt(words, 6000), 3);
        QCOMPARE(wordIndexAt(words, 6000 + 500), -1);          // chữ cuối tắt sau 400 ms
    }

    void clickPositionToWord() {
        const Script script = parseScript(sampleScript());
        const Segment &item = script.segments[2];              // "Năm sáu bảy." ở 16..28 trong đoạn
        QCOMPARE(wordAtChar(item, 16), 0);
        QCOMPARE(wordAtChar(item, 20), 1);
        QCOMPARE(wordAtChar(item, 28), 2);
        QCOMPARE(excerpt(QStringLiteral("“Chào bạn.”")), QStringLiteral("Chào bạn."));
    }

    void followRules() {
        using namespace FollowLogic;
        QCOMPARE(placementOf(-50, -10, 0, 600), Placement::Above);
        QCOMPARE(placementOf(700, 740, 0, 600), Placement::Below);
        QCOMPARE(placementOf(100, 140, 0, 600), Placement::Inside);
        QVERIFY(needsFollowScroll(560, 600, 0, 600));          // quá 85 % khung
        QVERIFY(!needsFollowScroll(100, 140, 0, 600));
        QCOMPARE(followScrollTop(500, 0, 600, 1000), 1000 + 500 - 180.0);
        QCOMPARE(followScrollTop(10, 0, 600, 0), 0.0);         // không âm
    }

    void readAlongFollowsPositionAndEmitsOnlyOnChange() {
        Rig rig;
        rig.openAndLoad(false);
        QCOMPARE(rig.read->status(), QStringLiteral("ready"));
        QVERIFY(rig.read->timed());
        QCOMPARE(rig.read->paragraphs()->rowCount(), 5);
        QSignalSpy segments(rig.read.get(), &ReadAlong::currentSegmentChanged);
        QSignalSpy words(rig.read.get(), &ReadAlong::currentWordChanged);
        QSignalSpy paragraphs(rig.read.get(), &ReadAlong::currentParaChanged);
        rig.out.pos = 3.0;
        rig.read->update();
        QCOMPARE(rig.read->currentSegment(), 1);
        QCOMPARE(rig.read->currentPara(), 1);
        QCOMPARE(segments.size(), 1);
        QCOMPARE(paragraphs.size(), 1);
        const int firstWord = rig.read->currentWord();
        QVERIFY(firstWord >= 0);
        // Nhiều lần tính lại trong cùng một chữ: không tín hiệu nào.
        const int before = int(words.size());
        for (int i = 0; i < 5; ++i)
            rig.read->update();
        QCOMPARE(int(words.size()), before);
        QCOMPARE(segments.size(), 1);
        rig.out.pos = 7.0;
        rig.read->update();
        QCOMPARE(rig.read->currentSegment(), 2);
        QCOMPARE(rig.read->currentPara(), 1);                  // cùng đoạn: đoạn không báo đổi
        QCOMPARE(paragraphs.size(), 1);
        QCOMPARE(segments.size(), 2);
    }

    void readAlongSwitchesChapterAndHandlesUntimed() {
        Rig rig;
        rig.openAndLoad(false);
        QVERIFY(rig.read->timed());
        rig.player->jumpTo(2, 0);
        rig.read->reload();
        QCOMPARE(rig.read->status(), QStringLiteral("ready"));
        QVERIFY(!rig.read->timed());                           // chương chưa có mốc: cột phải hiện danh sách chương
        rig.player->jumpTo(3, 0);
        rig.read->reload();
        QCOMPARE(rig.read->status(), QStringLiteral("failed")); // không có kịch bản
    }

    void inactiveScriptIsDroppedAndComesBackOnReopen() {
        Rig rig;
        rig.read->setDropMs(50);
        rig.openAndLoad(false);
        QCOMPARE(rig.read->status(), QStringLiteral("ready"));
        QVERIFY(rig.read->paragraphs()->rowCount() > 0);
        rig.read->setActive(false);
        QTRY_COMPARE_WITH_TIMEOUT(rig.read->status(), QStringLiteral("idle"), 1000);
        QCOMPARE(rig.read->paragraphs()->rowCount(), 0);
        QCOMPARE(rig.read->currentSegment(), -1);
        rig.read->setActive(true);
        rig.read->reload();
        QCOMPARE(rig.read->status(), QStringLiteral("ready"));
        QVERIFY(rig.read->paragraphs()->rowCount() > 0);
        // bật lại trước hạn thì không bỏ
        rig.read->setActive(false);
        rig.read->setActive(true);
        QTest::qWait(150); // fixed: proves absence
        QCOMPARE(rig.read->status(), QStringLiteral("ready"));
    }

    void clickingSentenceJumpsThere() {
        Rig rig;
        rig.openAndLoad(false);
        // đoạn 1, ký tự 20 = chữ "sáu" của câu 2 ("Năm sáu bảy.")
        QVERIFY(rig.read->listenFrom(1, 20));
        QVERIFY(qAbs(rig.out.pos - 7.333) < 0.05); // mốc chữ thứ hai của câu
        QVERIFY(rig.player->playing());
        QCOMPARE(rig.read->currentSegment(), 2);
        QVERIFY(rig.player->notice().isEmpty());                // nhảy gần (< 30 giây): không có lời nhắn "Quay lại"
        rig.out.pos = 60;
        QVERIFY(rig.read->listenFrom(1, 20));                   // nhảy xa: có lời nhắn và "Quay lại"
        QCOMPARE(rig.player->notice(), QStringLiteral("Nghe từ “sáu bảy.”"));
    }

    void bookDetailSaysWhereToContinue() {
        Rig rig;
        rig.net.books.insert(QStringLiteral("n"), makeBook(QStringLiteral("n"), 3, true));
        rig.net.books.insert(QStringLiteral("d"), makeBook(QStringLiteral("d"), 3, true, 2, 40, double(g_now) / 1000 - 60));
        BookDetail fresh;
        fresh.setBookId(QStringLiteral("n"));
        QCOMPARE(fresh.status(), QStringLiteral("ready"));
        QCOMPARE(fresh.primaryText(), QStringLiteral("Nghe"));
        QVERIFY(fresh.canListen());
        QVERIFY(fresh.hasPoint());
        QVERIFY(!fresh.started());
        QCOMPARE(fresh.firstPlayable(), 1);
        QCOMPARE(fresh.chapters()->count(), 3);

        BookDetail resumed;
        resumed.setBookId(QStringLiteral("d"));
        QCOMPARE(resumed.primaryText(), QStringLiteral("Nghe tiếp · Chương 2"));
        QVERIFY(resumed.started());
        QCOMPARE(resumed.point().value(QStringLiteral("chapterId")).toInt(), 2);
        QVERIFY(resumed.point().value(QStringLiteral("at")).toDouble() > 0);
        resumed.activate();
        QVERIFY(rig.player->loaded());
        QCOMPARE(rig.player->bookId(), QStringLiteral("d"));
        QVERIFY(rig.player->playing());
        QCOMPARE(resumed.primaryText(), QStringLiteral("Tạm dừng"));
        resumed.activate();
        QVERIFY(!rig.player->playing());
        QCOMPARE(resumed.primaryText(), QStringLiteral("Nghe tiếp · Chương 2"));
    }

    void bookDetailTextOnlyBookSaysWhatIsMissing() {
        Rig rig;
        QJsonObject book = makeBook(QStringLiteral("t"), 2, true);
        QJsonArray chapters = book.value(QStringLiteral("chapters")).toArray();
        for (int i = 0; i < chapters.size(); ++i) {
            QJsonObject item = chapters.at(i).toObject();
            item.insert(QStringLiteral("available"), false);
            item.insert(QStringLiteral("state"), QStringLiteral("text"));
            chapters.replace(i, item);
        }
        book.insert(QStringLiteral("chapters"), chapters);
        rig.net.books.insert(QStringLiteral("t"), book);
        BookDetail detail;
        detail.setBookId(QStringLiteral("t"));
        QVERIFY(!detail.canListen());
        QVERIFY(!detail.hasPoint());              // nút chính là "Đọc" (dòng "Chỉ có chữ · máy này chưa có giọng đọc" ở BookLogic.js)
        QVERIFY(detail.point().isEmpty());
        QCOMPARE(detail.firstPlayable(), -1);
        detail.activate();
        QVERIFY(!rig.player->loaded());
    }

    void bookDetailChapterRowPlaysThatChapter() {
        Rig rig;
        BookDetail detail;
        detail.setBookId(QStringLiteral("a"));
        detail.playChapter(3);
        QCOMPARE(rig.player->chapterId(), 3);
        QVERIFY(rig.player->playing());
        QCOMPARE(detail.chapters()->data(detail.chapters()->index(2), ChaptersModel::CurrentRole).toBool(), true);
    }
};

QTEST_GUILESS_MAIN(ReadAlongTest)
#include "test_readalong.moc"
