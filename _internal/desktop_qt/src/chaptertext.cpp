#include "chaptertext.h"
#include "textscript.h"

#include <QTextBlockFormat>
#include <QTextCursor>
#include <QTextDocument>

using namespace ScriptLogic;

namespace {
constexpr int kTickMs = 60;
}

ChapterText::ChapterText(QObject *parent) : ChapterText(Player::instance(), Player::instance() ? Player::instance()->net() : nullptr, parent) {}

ChapterText::ChapterText(Player *player, PlayerNet *net, QObject *parent) : QObject(parent), m_player(player), m_net(net), m_model(this) {
    m_ticker.setInterval(kTickMs);
    m_ticker.setTimerType(Qt::CoarseTimer);
    connect(&m_ticker, &QTimer::timeout, this, &ChapterText::update);
    m_load.setSingleShot(true);
    m_load.setInterval(0);
    connect(&m_load, &QTimer::timeout, this, &ChapterText::load);
    connectPlayer();
}

void ChapterText::connectPlayer() {
    if (!m_player)
        return;
    connect(m_player, &Player::chapterChanged, this, &ChapterText::playerMoved);
    connect(m_player, &Player::bookChanged, this, &ChapterText::playerMoved);
    connect(m_player, &Player::loadedChanged, this, &ChapterText::playerMoved);
    connect(m_player, &Player::playingChanged, this, &ChapterText::restartTicker);
    // Dừng mà tua / nhảy: đồng hồ báo vị trí đổi.
    connect(m_player->clock(), &PlayerClock::positionChanged, this, &ChapterText::update);
}

void ChapterText::setBookId(const QString &id) {
    if (m_bookId == id)
        return;
    m_bookId = id;
    emit sourceChanged();
    scheduleLoad();
    playerMoved();
}

void ChapterText::setChapterId(int id) {
    if (m_chapterId == id)
        return;
    m_chapterId = id;
    emit sourceChanged();
    scheduleLoad();
    playerMoved();
}

void ChapterText::setTextOnly(bool textOnly) {
    if (m_textOnly == textOnly)
        return;
    m_textOnly = textOnly;
    emit sourceChanged();
    scheduleLoad();
}

void ChapterText::setTitle(const QString &title) {
    if (m_title == title)
        return;
    m_title = title;
    emit sourceChanged();
    if (m_textOnly)
        scheduleLoad();
}

void ChapterText::setSkip(const QStringList &skip) {
    if (m_skip == skip)
        return;
    m_skip = skip;
    emit sourceChanged();
    if (m_textOnly)
        scheduleLoad();
}

void ChapterText::setActive(bool active) {
    if (m_active == active)
        return;
    m_active = active;
    if (m_player) {
        if (active)
            m_player->clock()->retain();
        else
            m_player->clock()->release();
    }
    restartTicker();
    emit activeChanged();
    if (active)
        update();
}

bool ChapterText::listeningHere() const {
    return m_player && m_player->loaded() && !m_bookId.isEmpty() && m_player->bookId() == m_bookId && m_player->chapterId() == m_chapterId;
}

void ChapterText::playerMoved() {
    const bool listening = listeningHere();
    if (listening != m_listening) {
        m_listening = listening;
        emit listeningHereChanged();
    }
    restartTicker();
    update();
}

void ChapterText::restartTicker() {
    const bool run = m_active && m_listening && m_player && m_player->playing() && timed();
    if (run && !m_ticker.isActive())
        m_ticker.start();
    else if (!run && m_ticker.isActive())
        m_ticker.stop();
}

void ChapterText::setStatus(const QString &status) {
    if (m_status == status)
        return;
    m_status = status;
    emit statusChanged();
    restartTicker();
}

void ChapterText::scheduleLoad() {
    if (!m_bookId.isEmpty() && m_chapterId > 0)
        m_load.start();
}

void ChapterText::reload() {
    m_load.stop();
    load();
}

void ChapterText::load() {
    if (!m_net || m_bookId.isEmpty() || m_chapterId <= 0)
        return;
    const quint64 seq = ++m_seq;
    // Chữ của chương cũ không đứng lại dưới chương mới.
    m_model.set(Script());
    m_texts.clear();
    m_textHash.clear();
    m_errorStatus = 0;
    m_errorMessage.clear();
    m_para = m_segment = m_word = -1;
    emit currentParaChanged();
    emit currentSegmentChanged();
    emit currentWordChanged();
    m_status.clear();
    setStatus(QStringLiteral("loading"));
    const int chapterId = m_chapterId;
    if (m_textOnly) {
        const QString title = m_title;
        const QStringList skip = m_skip;
        m_net->request("GET", QStringLiteral("/api/listen/books/%1/chapters/%2/text").arg(m_bookId).arg(chapterId), {},
            [this, seq, chapterId, title, skip](int status, const QJsonObject &body) {
                if (seq != m_seq)
                    return;
                if (status < 200 || status >= 300 || !body.value(QStringLiteral("text")).isString()) {
                    fail(status, body.value(QStringLiteral("message")).toString());
                    return;
                }
                apply(TextScript::textScript(chapterId, title, body.value(QStringLiteral("text")).toString(), skip));
            }, false);
        return;
    }
    m_net->request("GET", QStringLiteral("/api/books/%1/chapters/%2/script").arg(m_bookId).arg(chapterId), {}, [this, seq](int status, const QJsonObject &body) {
        if (seq != m_seq)
            return;
        if (status < 200 || status >= 300 || body.isEmpty()) {
            fail(status, body.value(QStringLiteral("message")).toString());
            return;
        }
        apply(body);
    }, false);
}

void ChapterText::fail(int status, const QString &message) {
    m_errorStatus = status;
    m_errorMessage = message;
    m_status.clear();          // statusChanged phát cả khi lỗi lần nữa (lời có thể đổi)
    setStatus(QStringLiteral("failed"));
}

void ChapterText::apply(const QJsonObject &json) {
    Script script = parseScript(json);
    script.chapterId = m_chapterId;
    m_texts.clear();
    for (const QJsonValue &value : json.value(QStringLiteral("segments")).toArray())
        m_texts.append(value.toObject().value(QStringLiteral("text")).toString());
    m_textHash = TextScript::fingerprint(m_texts);
    m_model.set(std::move(script));
    m_para = m_segment = m_word = -1;
    m_status.clear();
    setStatus(QStringLiteral("ready"));
    emit currentParaChanged();
    emit currentSegmentChanged();
    emit currentWordChanged();
    restartTicker();
    update();
}

void ChapterText::update() {
    const Script &script = m_model.script();
    int segment = -1, word = -1;
    if (m_listening && m_status == QLatin1String("ready") && script.timed && !script.segments.isEmpty()) {
        const double position = m_player->position();
        segment = sentenceIndexAt(script.starts, position);
        if (segment >= 0 && !script.segments[segment].words.isEmpty())
            word = wordIndexAt(script.segments[segment].words, position * 1000.0);
    }
    const int paragraph = segment >= 0 ? script.segments[segment].paragraph : -1;
    const bool paragraphChanged = paragraph != m_para;
    const bool segmentChanged = segment != m_segment;
    const bool wordChanged = word != m_word;
    m_para = paragraph;
    m_segment = segment;
    m_word = word;
    // Đoạn rồi câu rồi chữ, như ReadAlong.
    if (paragraphChanged)
        emit currentParaChanged();
    if (segmentChanged)
        emit currentSegmentChanged();
    if (wordChanged)
        emit currentWordChanged();
}

// ---------------------------------------------------------------------------------------------------- hình học, cùng luật ReadAlong

QVariantList ChapterText::sentenceRects(QQuickTextDocument *document, int paragraph, int segment) const {
    const Script &script = m_model.script();
    if (!document || segment < 0 || segment >= script.segments.size())
        return {};
    const Segment &item = script.segments[segment];
    if (item.paragraph != paragraph)
        return {};
    return ReadAlongLayout::rangeRects(document->textDocument(), item.textStart, item.textEnd);
}

QVariantList ChapterText::wordRects(QQuickTextDocument *document, int paragraph, int segment, int word) const {
    const Script &script = m_model.script();
    if (!document || segment < 0 || segment >= script.segments.size())
        return {};
    const Segment &item = script.segments[segment];
    if (item.paragraph != paragraph || word < 0 || word >= item.wordChars.size() || item.words.isEmpty())
        return {};
    return ReadAlongLayout::rangeRects(document->textDocument(), item.wordChars[word].first, item.wordChars[word].second);
}

int ChapterText::segmentAt(int paragraph, int position) const {
    const Script &script = m_model.script();
    if (paragraph < 0 || paragraph >= script.paragraphs.size())
        return -1;
    const Paragraph &item = script.paragraphs[paragraph];
    int found = item.first;
    for (int i = item.first; i < item.first + item.count; ++i) {
        if (script.segments[i].textStart <= position)
            found = i;
        else
            break;
    }
    return found;
}

void ChapterText::setLineHeight(QQuickTextDocument *document, qreal pixels) const {
    if (!document || !document->textDocument())
        return;
    QTextCursor cursor(document->textDocument());
    cursor.select(QTextCursor::Document);
    QTextBlockFormat format;
    format.setLineHeight(pixels, QTextBlockFormat::FixedHeight);
    cursor.mergeBlockFormat(format);
}

void ChapterText::shade(QQuickTextDocument *document, int paragraph, const QColor &heard, const QColor &normal) const {
    if (!document || !document->textDocument())
        return;
    const Script &script = m_model.script();
    QTextDocument *doc = document->textDocument();
    int heardEnd = 0;
    if (m_segment >= 0 && paragraph >= 0 && paragraph < script.paragraphs.size()) {
        if (paragraph < m_para)
            heardEnd = doc->characterCount() - 1;
        else if (paragraph == m_para)
            heardEnd = script.segments[m_segment].textStart;
    }
    ReadAlongLayout::shadeRange(doc, heardEnd, heard, normal);
}

bool ChapterText::canListenAt(int segment) const {
    const Script &script = m_model.script();
    return m_player && timed() && segment >= 0 && segment < script.segments.size() && script.segments[segment].start >= 0;
}

bool ChapterText::listenAt(int segment, double at, const QString &note) {
    if (!canListenAt(segment))
        return false;
    // Cuốn đang ở trình phát: nhảy trong trình phát; không thì nạp cuốn ở đúng chỗ (useListenFrom của web).
    if (m_player->loaded() && m_player->bookId() == m_bookId)
        m_player->jumpTo(m_chapterId, at, note);
    else
        m_player->open(m_bookId, m_chapterId, at, true);
    playerMoved();
    emit listened();
    return true;
}

bool ChapterText::listenFrom(int paragraph, int position) {
    const Script &script = m_model.script();
    const int index = segmentAt(paragraph, position);
    if (!canListenAt(index))
        return false;
    const Segment &segment = script.segments[index];
    double at = segment.start;
    int offset = 0;
    if (!segment.words.isEmpty() && position >= segment.textStart && position <= segment.textEnd) {
        const int word = wordAtChar(segment, position);
        if (word >= 0) {
            at = segment.words[word].first / 1000.0;
            offset = segment.wordChars[word].first - segment.textStart;
        }
    }
    return listenAt(index, at, QStringLiteral("Nghe từ “%1”").arg(excerpt(segment.text.mid(offset))));
}

bool ChapterText::listenSegment(int segment) {
    if (!canListenAt(segment))
        return false;
    const Segment &item = m_model.script().segments[segment];
    return listenAt(segment, item.start, QStringLiteral("Nghe từ “%1”").arg(excerpt(item.text)));
}

QString ChapterText::placement(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const {
    switch (FollowLogic::placementOf(top, bottom, viewTop, viewBottom)) {
    case FollowLogic::Placement::Above: return QStringLiteral("above");
    case FollowLogic::Placement::Below: return QStringLiteral("below");
    default: return QStringLiteral("inside");
    }
}

bool ChapterText::needsFollow(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const {
    return FollowLogic::needsFollowScroll(top, bottom, viewTop, viewBottom);
}

qreal ChapterText::followTop(qreal top, qreal viewTop, qreal viewBottom, qreal scrollTop) const {
    return FollowLogic::followScrollTop(top, viewTop, viewBottom, scrollTop);
}

// ---------------------------------------------------------------------------------------------------------------- chỗ đọc

int ChapterText::paragraphOf(int segment) const {
    const Script &script = m_model.script();
    return segment >= 0 && segment < script.segments.size() ? script.segments[segment].paragraph : -1;
}

int ChapterText::firstOf(int paragraph) const {
    const Script &script = m_model.script();
    return paragraph >= 0 && paragraph < script.paragraphs.size() ? script.paragraphs[paragraph].first : -1;
}

QVariantMap ChapterText::anchorOf(int segment) const {
    return TextScript::makeAnchor(m_texts, segment, 0, m_textHash);
}

QString ChapterText::quoteOf(int segment) const {
    if (segment < 0 || segment >= m_texts.size())
        return {};
    // slice(0, 200) của web: 200 đơn vị UTF-16
    return m_texts[segment].left(200);
}

int ChapterText::restoreIndex(const QVariantMap &place) const {
    if (m_texts.isEmpty())
        return 0;
    return TextScript::readingIndex(m_texts, place, m_textHash);
}
