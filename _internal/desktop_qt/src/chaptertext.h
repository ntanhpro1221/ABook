// Chữ của MỘT chương bất kỳ cho màn đọc "Đọc chương này" (ReaderScreen.tsx): nạp kịch bản (chương có audio) hay chữ thô (chương chỉ có chữ,
// textscript.h), và khi chương ấy đang ở trình phát thì câu / chữ đang nghe như ReadAlong. Cùng giao diện với ReadAlong nên ReadAlongView dàn được
// cả hai (property `source`): cùng mặt đọc, cùng cỡ chữ, cùng tô câu, cùng luật cuộn theo giọng. CHỈ phát tín hiệu khi câu / chữ thật sự đổi.
#pragma once

#include "readalong.h"

#include <QStringList>
#include <QVariantMap>

class ChapterText : public QObject {
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString bookId READ bookId WRITE setBookId NOTIFY sourceChanged)
    Q_PROPERTY(int chapterId READ chapterId WRITE setChapterId NOTIFY sourceChanged)
    /// Chương chỉ có chữ (state "text"): đọc chữ thô GET .../chapters/<n>/text, không phải kịch bản.
    Q_PROPERTY(bool textOnly READ textOnly WRITE setTextOnly NOTIFY sourceChanged)
    /// Tên chương (đoạn đầu trùng tên là tiêu đề của chương chữ) và các dòng người nghe bỏ khỏi phần đọc (`skip` của chương).
    Q_PROPERTY(QString title READ title WRITE setTitle NOTIFY sourceChanged)
    Q_PROPERTY(QStringList skip READ skip WRITE setSkip NOTIFY sourceChanged)
    /// Màn đang hiện chữ: chỉ khi true mới chạy nhịp theo giọng.
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY activeChanged)
    /// "idle" | "loading" | "ready" | "failed"
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    /// Mã HTTP và lời của máy chủ khi không mở được (503: máy giữ sách không trả lời).
    Q_PROPERTY(int errorStatus READ errorStatus NOTIFY statusChanged)
    Q_PROPERTY(QString errorMessage READ errorMessage NOTIFY statusChanged)
    Q_PROPERTY(bool timed READ timed NOTIFY statusChanged)
    Q_PROPERTY(int segmentCount READ segmentCount NOTIFY statusChanged)
    Q_PROPERTY(QString textHash READ textHash NOTIFY statusChanged)
    Q_PROPERTY(ScriptModel *paragraphs READ paragraphs CONSTANT)
    /// Chương này đang ở trình phát (cùng sách, cùng chương).
    Q_PROPERTY(bool listeningHere READ listeningHere NOTIFY listeningHereChanged)
    Q_PROPERTY(int currentPara READ currentPara NOTIFY currentParaChanged)
    Q_PROPERTY(int currentSegment READ currentSegment NOTIFY currentSegmentChanged)
    Q_PROPERTY(int currentWord READ currentWord NOTIFY currentWordChanged)
public:
    explicit ChapterText(QObject *parent = nullptr);
    /// Thử: bộ phát và đường mạng riêng (bình thường Player::instance() và mạng của nó).
    ChapterText(Player *player, PlayerNet *net, QObject *parent = nullptr);

    QString bookId() const { return m_bookId; }
    void setBookId(const QString &id);
    int chapterId() const { return m_chapterId; }
    void setChapterId(int id);
    bool textOnly() const { return m_textOnly; }
    void setTextOnly(bool textOnly);
    QString title() const { return m_title; }
    void setTitle(const QString &title);
    QStringList skip() const { return m_skip; }
    void setSkip(const QStringList &skip);
    bool active() const { return m_active; }
    void setActive(bool active);
    QString status() const { return m_status; }
    int errorStatus() const { return m_errorStatus; }
    QString errorMessage() const { return m_errorMessage; }
    bool timed() const { return m_status == QLatin1String("ready") && m_model.script().timed && !m_model.script().segments.isEmpty(); }
    int segmentCount() const { return int(m_model.script().segments.size()); }
    QString textHash() const { return m_textHash; }
    ScriptModel *paragraphs() { return &m_model; }
    bool listeningHere() const;
    int currentPara() const { return m_para; }
    int currentSegment() const { return m_segment; }
    int currentWord() const { return m_word; }

    // ---- cùng giao diện với ReadAlong (ReadAlongView) ----
    Q_INVOKABLE QVariantList sentenceRects(QQuickTextDocument *document, int paragraph, int segment) const;
    Q_INVOKABLE QVariantList wordRects(QQuickTextDocument *document, int paragraph, int segment, int word) const;
    Q_INVOKABLE int segmentAt(int paragraph, int position) const;
    Q_INVOKABLE void setLineHeight(QQuickTextDocument *document, qreal pixels) const;
    Q_INVOKABLE void shade(QQuickTextDocument *document, int paragraph, const QColor &heard, const QColor &normal) const;
    /// Bấm vào ký tự `position` của đoạn: nghe từ chữ / câu ấy (cuốn đang ở trình phát thì nhảy trong trình phát, không thì nạp). false: không nghe được.
    Q_INVOKABLE bool listenFrom(int paragraph, int position);
    Q_INVOKABLE QString placement(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const;
    Q_INVOKABLE bool needsFollow(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const;
    Q_INVOKABLE qreal followTop(qreal top, qreal viewTop, qreal viewBottom, qreal scrollTop) const;
    Q_INVOKABLE int settleMs() const { return FollowLogic::kSettleMs; }

    // ---- riêng của màn đọc ----
    /// Nghe từ đầu câu `segment` (nút "Nghe từ đây").
    Q_INVOKABLE bool listenSegment(int segment);
    /// Câu nghe được (chương có mốc, câu có mốc).
    Q_INVOKABLE bool canListenAt(int segment) const;
    Q_INVOKABLE int paragraphOf(int segment) const;
    Q_INVOKABLE int firstOf(int paragraph) const;
    /// Mốc chỗ đọc của câu (readingAnchor.makeAnchor, chữ đầu) và 200 ký tự đầu của nó (quote của ReadingPosition).
    Q_INVOKABLE QVariantMap anchorOf(int segment) const;
    Q_INVOKABLE QString quoteOf(int segment) const;
    /// Câu của một chỗ đọc đã lưu {index, anchor, quote} (readingIndex).
    Q_INVOKABLE int restoreIndex(const QVariantMap &place) const;
    /// Nạp lại (sau lỗi).
    Q_INVOKABLE void reload();
    /// Tính lại câu / chữ đang nghe theo vị trí bộ phát (nhịp + tín hiệu đồng hồ gọi; thử gọi tay).
    void update();

signals:
    void sourceChanged();
    void activeChanged();
    void statusChanged();
    void listeningHereChanged();
    void currentParaChanged();
    void currentSegmentChanged();
    void currentWordChanged();
    /// Người vừa bấm một câu để nghe từ đó: màn đọc theo lại.
    void listened();

private:
    void connectPlayer();
    void scheduleLoad();
    void load();
    void apply(const QJsonObject &json);
    void fail(int status, const QString &message);
    void setStatus(const QString &status);
    void restartTicker();
    void playerMoved();
    bool listenAt(int segment, double at, const QString &note);

    Player *m_player = nullptr;
    PlayerNet *m_net = nullptr;
    ScriptModel m_model;
    QStringList m_texts;        // chữ gốc từng câu (vân tay chỗ đọc tính trên chữ này, như script.segments[i].text của web)
    QString m_textHash;
    QTimer m_ticker;
    QTimer m_load;
    QString m_bookId;
    int m_chapterId = 0;
    bool m_textOnly = false;
    QString m_title;
    QStringList m_skip;
    bool m_active = false;
    bool m_listening = false;
    QString m_status = QStringLiteral("idle");
    int m_errorStatus = 0;
    QString m_errorMessage;
    quint64 m_seq = 0;
    int m_para = -1;
    int m_segment = -1;
    int m_word = -1;
};
