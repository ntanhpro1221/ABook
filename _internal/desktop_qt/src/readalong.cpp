#include "readalong.h"

#include <QAbstractTextDocumentLayout>
#include <QRectF>
#include <QTextBlock>
#include <QTextCursor>
#include <QTextDocument>
#include <QTextLayout>
#include <QTextLine>

using namespace ScriptLogic;

namespace {
ReadAlong *g_instance = nullptr;
constexpr int kTickMs = 60;
constexpr int kDropMs = 8000;
constexpr double kPrefetchSeconds = 30;
} // namespace

/// Một hình chữ nhật cho mỗi dòng chữ mà đoạn [start, end) của tài liệu đi qua (toạ độ tài liệu = toạ độ TextEdit).
QVariantList ReadAlongLayout::rangeRects(QTextDocument *doc, int start, int end) {
    QVariantList out;
    if (!doc || start >= end)
        return out;
    QAbstractTextDocumentLayout *layout = doc->documentLayout();
    for (QTextBlock block = doc->findBlock(start); block.isValid() && block.position() < end; block = block.next()) {
        QTextLayout *textLayout = block.layout();
        if (!textLayout)
            continue;
        const QPointF origin = layout->blockBoundingRect(block).topLeft();
        for (int i = 0; i < textLayout->lineCount(); ++i) {
            const QTextLine line = textLayout->lineAt(i);
            const int lineStart = block.position() + line.textStart();
            int lineEnd = lineStart + line.textLength();
            // khoảng trắng cuối dòng (ở lại dòng bị ngắt) không tô
            while (lineEnd > lineStart && doc->characterAt(lineEnd - 1).isSpace())
                --lineEnd;
            const int from = qMax(start, lineStart), to = qMin(end, lineEnd);
            if (from >= to)
                continue;
            const qreal x1 = line.cursorToX(from - block.position()), x2 = line.cursorToX(to - block.position());
            out.push_back(QRectF(origin.x() + qMin(x1, x2), origin.y() + line.y(), qAbs(x2 - x1), line.height()));
        }
    }
    return out;
}

void ReadAlongLayout::shadeRange(QTextDocument *doc, int heardEnd, const QColor &heard, const QColor &normal) {
    if (!doc)
        return;
    const int length = doc->characterCount() - 1;
    heardEnd = qBound(0, heardEnd, length);
    QTextCursor cursor(doc);
    cursor.beginEditBlock();
    cursor.setPosition(0);
    cursor.setPosition(heardEnd, QTextCursor::KeepAnchor);
    QTextCharFormat dim;
    dim.setForeground(heard);
    cursor.mergeCharFormat(dim);
    cursor.setPosition(heardEnd);
    cursor.setPosition(length, QTextCursor::KeepAnchor);
    QTextCharFormat plain;
    plain.setForeground(normal);
    cursor.mergeCharFormat(plain);
    cursor.endEditBlock();
}

// ------------------------------------------------------------------------------------------------------------------ ScriptModel

QVariant ScriptModel::data(const QModelIndex &index, int role) const {
    if (!index.isValid() || index.row() < 0 || index.row() >= m_script.paragraphs.size())
        return {};
    const Paragraph &paragraph = m_script.paragraphs[index.row()];
    switch (role) {
    case TextRole: return paragraph.text;
    case KindRole: return paragraph.kind;
    case SpeakerRole: return paragraph.speaker;
    case FirstRole: return paragraph.first;
    case CountRole: return paragraph.count;
    default: return {};
    }
}

QHash<int, QByteArray> ScriptModel::roleNames() const {
    return {{TextRole, "text"}, {KindRole, "kind"}, {SpeakerRole, "speaker"}, {FirstRole, "first"}, {CountRole, "count"}};
}

void ScriptModel::set(Script script) {
    beginResetModel();
    m_script = std::move(script);
    endResetModel();
}

// ------------------------------------------------------------------------------------------------------------------- ReadAlong

ReadAlong::ReadAlong(Player *player, PlayerNet *net, QObject *parent) : QObject(parent), m_player(player), m_net(net), m_model(this) {
    m_ticker.setInterval(kTickMs);
    m_ticker.setTimerType(Qt::CoarseTimer);
    connect(&m_ticker, &QTimer::timeout, this, &ReadAlong::update);
    m_drop.setSingleShot(true);
    m_drop.setInterval(kDropMs);
    connect(&m_drop, &QTimer::timeout, this, &ReadAlong::dropScript);
    m_reload.setSingleShot(true);
    m_reload.setInterval(0);
    connect(&m_reload, &QTimer::timeout, this, &ReadAlong::reload);
    connect(player, &Player::chapterChanged, this, &ReadAlong::scheduleReload);
    connect(player, &Player::bookChanged, this, &ReadAlong::scheduleReload);
    connect(player, &Player::playingChanged, this, &ReadAlong::restartTicker);
    // Dừng mà tua / nhảy: đồng hồ báo vị trí đổi.
    connect(player->clock(), &PlayerClock::positionChanged, this, &ReadAlong::update);
}

ReadAlong *ReadAlong::create(QQmlEngine *, QJSEngine *) {
    QQmlEngine::setObjectOwnership(g_instance, QQmlEngine::CppOwnership);
    return g_instance;
}

void ReadAlong::setInstance(ReadAlong *instance) {
    g_instance = instance;
}

void ReadAlong::setActive(bool active) {
    if (m_active == active)
        return;
    m_active = active;
    if (active)
        m_drop.stop();
    else
        m_drop.start();
    if (active) {
        m_player->clock()->retain();
        scheduleReload();
    } else {
        m_player->clock()->release();
    }
    restartTicker();
    emit activeChanged();
}

void ReadAlong::restartTicker() {
    const bool run = m_active && m_player->playing() && timed();
    if (run && !m_ticker.isActive())
        m_ticker.start();
    else if (!run && m_ticker.isActive())
        m_ticker.stop();
}

void ReadAlong::setStatus(const QString &status) {
    if (m_status == status)
        return;
    m_status = status;
    emit statusChanged();
    restartTicker();
}

// Màn chữ tắt đủ lâu: bỏ chữ + mốc của chương (có thể hàng nghìn câu) và kịch bản chương kế tải sẵn; mở lại thì tải lại.
void ReadAlong::dropScript() {
    if (m_active)
        return;
    ++m_seq;                                   // trả lời đang bay về sau không còn chỗ đặt
    m_model.set(Script());
    m_prefetched = Script();
    m_prefetchChapter = 0;
    m_prefetchBook.clear();
    m_loadedBook.clear();
    m_loadedChapter = 0;
    m_prefetching = false;
    const bool had = m_para >= 0 || m_segment >= 0 || m_word >= 0;
    m_para = m_segment = m_word = -1;
    if (had) {
        emit currentParaChanged();
        emit currentSegmentChanged();
        emit currentWordChanged();
    }
    setStatus(QStringLiteral("idle"));
}

void ReadAlong::scheduleReload() {
    if (m_active)
        m_reload.start();
}

void ReadAlong::reload() {
    if (!m_active || !m_player->loaded())
        return;
    const QString bookId = m_player->bookId();
    const int chapterId = m_player->chapterId();
    if (m_status == QLatin1String("ready") && bookId == m_loadedBook && chapterId == m_loadedChapter)
        return;
    const quint64 seq = ++m_seq;
    m_loadedBook = bookId;
    m_loadedChapter = chapterId;
    if (m_prefetchChapter == chapterId && m_prefetchBook == bookId && !m_prefetched.segments.isEmpty()) {
        Script script = std::move(m_prefetched);
        m_prefetchChapter = 0;
        m_prefetched = Script();
        apply(std::move(script));
        return;
    }
    // Chữ của chương cũ không đứng lại dưới chương mới.
    m_model.set(Script());
    m_para = m_segment = m_word = -1;
    emit currentParaChanged();
    emit currentSegmentChanged();
    emit currentWordChanged();
    setStatus(QStringLiteral("loading"));
    m_net->request("GET", QStringLiteral("/api/books/%1/chapters/%2/script").arg(bookId).arg(chapterId), {}, [this, seq](int status, const QJsonObject &body) {
        if (seq != m_seq)
            return;
        if (status < 200 || status >= 300 || body.isEmpty()) {
            setStatus(QStringLiteral("failed"));
            return;
        }
        apply(parseScript(body));
    }, false);
}

void ReadAlong::apply(Script script) {
    script.chapterId = m_loadedChapter;
    m_model.set(std::move(script));
    m_para = m_segment = m_word = -1;
    setStatus(QStringLiteral("ready"));
    emit currentParaChanged();
    emit currentSegmentChanged();
    emit currentWordChanged();
    restartTicker();
    update();
}

void ReadAlong::update() {
    if (!m_active || m_status != QLatin1String("ready"))
        return;
    const Script &script = m_model.script();
    if (!script.timed || script.segments.isEmpty())
        return;
    ++m_evaluations;
    const double position = m_player->position();
    const int segment = sentenceIndexAt(script.starts, position);
    int word = -1;
    if (segment >= 0 && !script.segments[segment].words.isEmpty())
        word = wordIndexAt(script.segments[segment].words, position * 1000.0);
    const int paragraph = segment >= 0 ? script.segments[segment].paragraph : -1;
    const bool paragraphChanged = paragraph != m_para;
    const bool segmentChanged = segment != m_segment;
    const bool wordChanged = word != m_word;
    m_para = paragraph;
    m_segment = segment;
    m_word = word;
    m_changes += (paragraphChanged || segmentChanged || wordChanged) ? 1 : 0;
    // Đoạn rồi câu rồi chữ: đoạn đổi trước để người nghe tín hiệu thấy trạng thái nhất quán.
    if (paragraphChanged)
        emit currentParaChanged();
    if (segmentChanged)
        emit currentSegmentChanged();
    if (wordChanged)
        emit currentWordChanged();
    const double length = m_player->duration();
    if (length > 0 && length - position < kPrefetchSeconds)
        prefetchNext();
}

void ReadAlong::prefetchNext() {
    if (m_prefetching)
        return;
    const int next = PlayerLogic::availableAfter(m_player->book().chapters, m_loadedChapter, 1);
    if (next < 0 || (m_prefetchChapter == next && m_prefetchBook == m_loadedBook))
        return;
    m_prefetching = true;
    const QString bookId = m_loadedBook;
    m_net->request("GET", QStringLiteral("/api/books/%1/chapters/%2/script").arg(bookId).arg(next), {}, [this, bookId, next](int status, const QJsonObject &body) {
        m_prefetching = false;
        if (status < 200 || status >= 300 || body.isEmpty())
            return;
        m_prefetched = parseScript(body);
        m_prefetchChapter = next;
        m_prefetchBook = bookId;
    }, false);
}

QVariantList ReadAlong::sentenceRects(QQuickTextDocument *document, int paragraph, int segment) const {
    const Script &script = m_model.script();
    if (!document || segment < 0 || segment >= script.segments.size())
        return {};
    const Segment &item = script.segments[segment];
    if (item.paragraph != paragraph)
        return {};
    return ReadAlongLayout::rangeRects(document->textDocument(), item.textStart, item.textEnd);
}

QVariantList ReadAlong::wordRects(QQuickTextDocument *document, int paragraph, int segment, int word) const {
    const Script &script = m_model.script();
    if (!document || segment < 0 || segment >= script.segments.size())
        return {};
    const Segment &item = script.segments[segment];
    if (item.paragraph != paragraph || word < 0 || word >= item.wordChars.size() || item.words.isEmpty())
        return {};
    return ReadAlongLayout::rangeRects(document->textDocument(), item.wordChars[word].first, item.wordChars[word].second);
}

int ReadAlong::segmentAt(int paragraph, int position) const {
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

void ReadAlong::setLineHeight(QQuickTextDocument *document, qreal pixels) const {
    if (!document || !document->textDocument())
        return;
    QTextCursor cursor(document->textDocument());
    cursor.select(QTextCursor::Document);
    QTextBlockFormat format;
    format.setLineHeight(pixels, QTextBlockFormat::FixedHeight);
    cursor.mergeBlockFormat(format);
}

void ReadAlong::shade(QQuickTextDocument *document, int paragraph, const QColor &heard, const QColor &normal) const {
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

bool ReadAlong::listenFrom(int paragraph, int position) {
    const Script &script = m_model.script();
    const int index = segmentAt(paragraph, position);
    if (index < 0 || !m_player->loaded() || script.chapterId != m_player->chapterId())
        return false;
    const Segment &segment = script.segments[index];
    if (segment.start < 0)
        return false;
    double at = segment.start;
    int offset = 0;
    if (!segment.words.isEmpty() && position >= segment.textStart && position <= segment.textEnd) {
        const int word = wordAtChar(segment, position);
        if (word >= 0) {
            at = segment.words[word].first / 1000.0;
            offset = segment.wordChars[word].first - segment.textStart;
        }
    }
    m_player->jumpTo(m_player->chapterId(), at, QStringLiteral("Nghe từ “%1”").arg(excerpt(segment.text.mid(offset))));
    update();
    emit listened();
    return true;
}

QString ReadAlong::placement(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const {
    switch (FollowLogic::placementOf(top, bottom, viewTop, viewBottom)) {
    case FollowLogic::Placement::Above: return QStringLiteral("above");
    case FollowLogic::Placement::Below: return QStringLiteral("below");
    default: return QStringLiteral("inside");
    }
}

bool ReadAlong::needsFollow(qreal top, qreal bottom, qreal viewTop, qreal viewBottom) const {
    return FollowLogic::needsFollowScroll(top, bottom, viewTop, viewBottom);
}

qreal ReadAlong::followTop(qreal top, qreal viewTop, qreal viewBottom, qreal scrollTop) const {
    return FollowLogic::followScrollTop(top, viewTop, viewBottom, scrollTop);
}
