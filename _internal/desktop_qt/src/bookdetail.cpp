#include "bookdetail.h"

using namespace PlayerLogic;

namespace {
// Tên icon lucide (qml/LucidePaths.js)
const QString kPlay = QStringLiteral("play");
const QString kPause = QStringLiteral("pause");
const QString kRestart = QStringLiteral("rotate-ccw");
} // namespace

BookDetail::BookDetail(QObject *parent) : QObject(parent), m_chapters(this) {
    if (Player *player = Player::instance()) {
        connect(player, &Player::playingChanged, this, &BookDetail::recompute);
        connect(player, &Player::bookChanged, this, &BookDetail::recompute);
        connect(player, &Player::chapterChanged, this, &BookDetail::recompute);
        // Chỗ nghe vừa được lưu: dấu từng chương và "nghe tiếp từ đâu" đổi theo.
        connect(player, &Player::listeningChanged, this, [this](const QString &bookId) {
            if (bookId == m_bookId)
                reload();
        });
    }
}

void BookDetail::setBookId(const QString &bookId) {
    if (bookId == m_bookId)
        return;
    m_bookId = bookId;
    m_hasBook = false;
    m_status = QStringLiteral("loading");
    emit bookIdChanged();
    reload();
}

void BookDetail::reload() {
    Player *player = Player::instance();
    if (!player || m_bookId.isEmpty())
        return;
    const quint64 seq = ++m_seq;
    player->net()->request("GET", QStringLiteral("/api/listen/books/%1").arg(m_bookId), {}, [this, seq](int status, const QJsonObject &body) {
        if (seq != m_seq)
            return;
        if (status < 200 || status >= 300 || body.isEmpty()) {
            if (!m_hasBook) {
                m_status = QStringLiteral("failed");
                emit changed();
            }
            return;
        }
        m_book = parseBook(body);
        m_finished = m_book.finished;
        if (!m_hasBook)
            m_chapters.setBook(m_book);
        else
            m_chapters.refreshStates(m_book);
        m_hasBook = true;
        m_status = QStringLiteral("ready");
        recompute();
    }, false);
}

void BookDetail::recompute() {
    if (!m_hasBook)
        return;
    Player *player = Player::instance();
    const bool here = player && player->loaded() && player->bookId() == m_bookId;
    const bool playing = here && player->playing();
    m_chapters.setCurrent(here ? player->chapterId() : -1);

    int playable = 0, textOnly = 0, doneCount = 0;
    double heard = 0;
    for (const Chapter &chapter : m_book.chapters) {
        if (chapter.available || (chapter.textOnly && player && (player->hasDefaultVoice() || !m_book.voice.isEmpty()))) {
            ++playable;
            if (m_book.states.value(chapter.id).done)
                ++doneCount;
        } else if (chapter.textOnly) {
            ++textOnly;
        }
        heard += m_book.states.value(chapter.id).heard;
    }
    const bool started = heard > 0 || m_book.hasLast || here;
    const bool caughtUp = !m_book.complete && playable > 0 && doneCount == playable && !here;
    const bool finished = (m_finished || (m_book.complete && playable > 0 && doneCount == playable)) && !playing;
    const std::optional<ResumePoint> point = resumePoint(m_book);

    QString text, caption, icon = kPlay;
    if (playing) {
        text = QStringLiteral("Tạm dừng");
        icon = kPause;
    } else if (finished && !here) {
        text = QStringLiteral("Nghe lại từ đầu");
        icon = kRestart;
    } else {
        text = started ? QStringLiteral("Nghe tiếp") : QStringLiteral("Nghe");
        // Chương nghe tiếp: đang nạp ở bộ phát thì đúng chương đang đứng, không thì điểm nghe tiếp của cuốn.
        if (here) {
            caption = player->chapterTitle();
        } else if (point && (point->at > 0 || started)) {
            for (const Chapter &chapter : m_book.chapters)
                if (chapter.id == point->chapterId)
                    caption = chapter.title;
        }
    }
    QString message;
    if (playable == 0) {
        if (textOnly > 0 && textOnly == m_book.chapters.size())
            message = QStringLiteral("Chỉ có chữ · máy này chưa có giọng đọc");
        else if (m_book.producing)
            message = QStringLiteral("Đang thu; chương mới tự hiện khi xong.");
        else
            message = QStringLiteral("Chưa chương nào có audio.");
    } else if (caughtUp) {
        message = QStringLiteral("Đã nghe hết phần đã có. Chương mới sẽ hiện ở đây khi làm xong.");
    } else if (!m_book.complete && m_book.producing) {
        message = QStringLiteral("Đang thu; chương mới tự hiện khi xong.");
    }
    const bool listen = playable > 0 && !caughtUp;
    if (text == m_primaryText && caption == m_primaryCaption && icon == m_primaryIcon && listen == m_canListen && message == m_message && !m_primaryText.isEmpty()) {
        emit changed(); // trạng thái tải đổi (loading -> ready)
        return;
    }
    m_primaryText = text;
    m_primaryCaption = caption;
    m_primaryIcon = icon;
    m_canListen = listen;
    m_message = message;
    emit changed();
}

void BookDetail::activate() {
    Player *player = Player::instance();
    if (!player || !m_hasBook || !m_canListen)
        return;
    const bool here = player->loaded() && player->bookId() == m_bookId;
    if (here && player->playing()) {
        player->pause();
        return;
    }
    if (m_primaryIcon == kRestart) {
        for (const Chapter &chapter : m_book.chapters) {
            if (canPlay(chapter)) {
                if (here)
                    player->jumpTo(chapter.id, 0);
                else
                    player->open(m_bookId, chapter.id, 0, true);
                return;
            }
        }
        return;
    }
    player->playBook(m_bookId);
}

void BookDetail::playChapter(int chapterId) {
    if (Player *player = Player::instance())
        player->playChapter(m_bookId, chapterId);
}
