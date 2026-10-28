#include "player.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QEvent>
#include <QEventLoop>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QUuid>

#include <algorithm>
#include <cmath>

using namespace PlayerLogic;

namespace {
constexpr int kNoticeMs = 8000;
constexpr int kSessionsKept = 4;
constexpr int kHiddenSaveEveryMs = 30'000;
constexpr double kSafetyWarnMs = 30'000;
constexpr double kListenedMinimum = 20; // phiên nghe dưới 20 giây thật thì bỏ

const QString kPlayError = QStringLiteral("Không phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại.");

Player *g_instance = nullptr;

QString newId() {
    return QUuid::createUuid().toString(QUuid::WithoutBraces);
}
} // namespace

// ---------------------------------------------------------------------------------------------------------------- PlayerClock

PlayerClock::PlayerClock(Player *owner) : QObject(owner), m_owner(owner) {
    m_timer.setObjectName(QStringLiteral("UI position"));
    m_timer.setInterval(250);
    m_timer.setTimerType(Qt::CoarseTimer);
    connect(&m_timer, &QTimer::timeout, this, &PlayerClock::refresh);
}

void PlayerClock::retain() {
    ++m_watchers;
    refresh();
    restart();
}

void PlayerClock::release() {
    if (m_watchers > 0)
        --m_watchers;
    restart();
}

void PlayerClock::restart() {
    const bool run = !m_suspended && m_watchers > 0 && m_owner->playing();
    if (run && !m_timer.isActive())
        m_timer.start();
    else if (!run && m_timer.isActive())
        m_timer.stop();
}

void PlayerClock::set(double position, double duration) {
    if (!m_suspended && !qFuzzyCompare(1 + m_position, 1 + position)) {
        m_position = position;
        ++m_ticks;
        emit positionChanged();
    }
    if (!qFuzzyCompare(1 + m_duration, 1 + duration)) {
        m_duration = duration;
        emit durationChanged();
    }
    setSleepLeft(m_owner->sleepLeftSeconds());
}

void PlayerClock::setSleepLeft(double seconds) {
    if (m_suspended) return;
    if (qFuzzyCompare(1 + m_sleepLeft, 1 + seconds))
        return;
    m_sleepLeft = seconds;
    emit sleepLeftChanged();
}

void PlayerClock::refresh() {
    set(m_owner->position(), m_owner->duration());
}

void PlayerClock::setSuspended(bool suspended) {
    if (m_suspended == suspended) return;
    m_suspended = suspended;
    restart();
    if (!suspended) refresh(); // Restore synchronously, before the next frame.
}

// -------------------------------------------------------------------------------------------------------------------- Player

Player::Player(AudioOut *out, PlayerNet *net, const QString &outboxPath, QObject *parent, std::function<qint64()> nowMs)
    : QObject(parent), m_out(out), m_net(net), m_now(nowMs ? std::move(nowMs) : [] { return QDateTime::currentMSecsSinceEpoch(); }),
      m_clock(this), m_chapters(this) {
    m_lastActivity = m_now();
    m_outbox = std::make_unique<ProgressOutbox>([this](const ProgressSpot &spot, ProgressOutbox::Done done) { sendSpot(spot, std::move(done)); },
                                                [this](const ProgressSpot &spot) { onAck(spot); }, outboxPath);
    m_ticker.setTimerType(Qt::CoarseTimer);
    m_ticker.setObjectName(QStringLiteral("progress and sleep"));
    connect(&m_ticker, &QTimer::timeout, this, &Player::tick);
    m_noticeTimer.setSingleShot(true);
    m_noticeTimer.setInterval(kNoticeMs);
    connect(&m_noticeTimer, &QTimer::timeout, this, &Player::dismissNotice);

    connect(m_out, &AudioOut::playingChanged, this, &Player::onOutPlaying);
    connect(m_out, &AudioOut::buffering, this, [this](bool on) {
        if (m_loadingSource || !m_loaded)
            return;
        setBuffering(on && m_playing);
        if (on) {
            m_audible = false;
            resetSleepMark();
        }
    });
    connect(m_out, &AudioOut::seeked, this, &Player::onSeeked);
    connect(m_out, &AudioOut::ended, this, &Player::onEnded);
    connect(m_out, &AudioOut::failed, this, &Player::onFailed);
    connect(m_out, &AudioOut::durationChanged, this, &Player::onDuration);
    m_out->setVolume(m_volume);
}

Player::~Player() {
    if (g_instance == this)
        g_instance = nullptr;
}

Player *Player::instance() {
    return g_instance;
}

void Player::setInstance(Player *player) {
    g_instance = player;
}

Player *Player::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_instance, QJSEngine::CppOwnership);
    return g_instance;
}

void Player::watchInput() {
    if (QCoreApplication::instance())
        QCoreApplication::instance()->installEventFilter(this);
}

bool Player::eventFilter(QObject *, QEvent *event) {
    switch (event->type()) {
    case QEvent::KeyPress:
    case QEvent::MouseButtonPress:
    case QEvent::Wheel:
    case QEvent::TouchBegin:
        m_lastActivity = m_now();
        // Máy tính: chạm phím / chuột lúc đang nhỏ dần = "lắc máy" - nghe thêm. Phím ấy không làm gì khác.
        if (m_fading) {
            extendSleep();
            return event->type() == QEvent::KeyPress;
        }
        break;
    case QEvent::MouseMove:
        if (m_fading)
            extendSleep();
        break;
    default:
        break;
    }
    return false;
}

// ---- ảnh chụp ----

QString Player::coverKey() const {
    return m_book.coverKey;
}

const Chapter *Player::chapter(int id) const {
    for (const Chapter &item : m_book.chapters)
        if (item.id == id)
            return &item;
    return nullptr;
}

int Player::chapterNumber() const {
    const Chapter *item = chapter(m_chapterId);
    return item ? item->index : 0;
}

QString Player::chapterTitle() const {
    const Chapter *item = chapter(m_chapterId);
    return item ? item->title : QString();
}

QString Player::chapterSubtitle() const {
    const Chapter *item = chapter(m_chapterId);
    return item ? item->subtitle : QString();
}

QString Player::sleepKind() const {
    switch (m_sleep.kind) {
    case Sleep::Minutes: return QStringLiteral("minutes");
    case Sleep::Chapter: return QStringLiteral("chapter");
    default: return QStringLiteral("off");
    }
}

QString Player::sleepStoppedText() const {
    if (m_sleep.kind != Sleep::Off || !m_sleepStoppedAt)
        return {};
    // Chỉ đáng nhắc trong nửa giờ sau khi hẹn giờ tắt tiếng.
    if (m_now() - m_sleepStoppedAt >= 30 * 60'000)
        return {};
    return QDateTime::fromMSecsSinceEpoch(m_sleepStoppedAt).toString(QStringLiteral("HH:mm"));
}

bool Player::canPrevious() const {
    return m_loaded;
}

bool Player::canNext() const {
    return m_loaded && availableAfter(m_book.chapters, m_chapterId, 1) >= 0;
}

QVariantList Player::speedsList() const {
    QVariantList list;
    for (double speed : speeds())
        list.append(speed);
    return list;
}

QVariantList Player::sleepChoicesList() const {
    QVariantList list;
    for (int minutes : sleepChoices())
        list.append(minutes);
    return list;
}

double Player::position() const {
    return m_loaded ? std::max(0.0, m_out->position()) : 0.0;
}

double Player::duration() const {
    if (!m_loaded)
        return 0;
    const double length = m_out->duration();
    if (length > 0)
        return length;
    const Chapter *item = chapter(m_chapterId);
    return item ? knownDuration(m_book, *item) : 0.0;
}

double Player::sleepLeftSeconds() const {
    if (m_sleep.kind == Sleep::Minutes)
        return std::ceil(m_sleep.leftMs / 1000.0);
    return -1;
}

void Player::changed() {
    ++m_snapshotChanges;
}

void Player::setPlaying(bool playing) {
    if (m_playing == playing)
        return;
    m_playing = playing;
    m_scheduleChecked = false; // phụ thuộc `playing` của useEffect lịch đêm: bắt đầu nghe lại thì xét lại
    changed();
    emit playingChanged();
    m_clock.restart();
    updateTicker();
}

void Player::setBuffering(bool buffering) {
    if (m_buffering == buffering)
        return;
    m_buffering = buffering;
    changed();
    emit bufferingChanged();
}

void Player::setError(const QString &error) {
    if (m_error == error)
        return;
    m_error = error;
    changed();
    emit errorChanged();
}

void Player::setNotice(const QString &notice, const QString &actionLabel, const QString &actionKey) {
    m_noticeTimer.stop();
    if (!notice.isEmpty())
        m_noticeTimer.start();
    if (m_notice == notice && m_noticeAction == actionLabel && m_noticeKey == actionKey)
        return;
    m_notice = notice;
    m_noticeAction = actionLabel;
    m_noticeKey = actionKey;
    changed();
    emit noticeChanged();
}

void Player::setAtEnd(const QString &atEnd) {
    if (m_atEnd == atEnd)
        return;
    m_atEnd = atEnd;
    changed();
    emit atEndChanged();
}

void Player::setFading(bool fading) {
    if (m_fading == fading)
        return;
    m_fading = fading;
    changed();
    emit fadingChanged();
}

void Player::updateTicker() {
    const bool run = m_loaded || m_outbox->pending() > 0;
    int interval = m_playing && m_sleep.kind != Sleep::Off ? 100 : m_uiActive ? 1000 : kHiddenSaveEveryMs;
    if (!m_uiActive && m_sleep.kind == Sleep::Off) {
        const auto until = [&](qint64 deadline) { return int(std::clamp<qint64>(deadline - m_now(), 1, kHiddenSaveEveryMs)); };
        if (m_loaded && m_playing) {
            // The first tick still checks the night schedule immediately.
            if (!m_scheduleChecked) interval = 1;
            else if (m_now() < m_lastAttempt + kHiddenSaveEveryMs)
                interval = std::min(interval, until(m_lastAttempt + kHiddenSaveEveryMs));
            if (m_safetyHours > 0) interval = std::min(interval, until(m_lastActivity + qint64(m_safetyHours) * 3'600'000));
        }
        if (m_outbox->pending() > 0) interval = std::min(interval, until(m_lastFlush + kSaveEveryMs));
    }
    if (!run) {
        m_ticker.stop();
        return;
    }
    const auto timerType = m_uiActive ? Qt::CoarseTimer : Qt::PreciseTimer;
    if (m_ticker.timerType() != timerType) { m_ticker.stop(); m_ticker.setTimerType(timerType); }
    if (m_ticker.interval() != interval)
        m_ticker.setInterval(interval);
    if (!m_ticker.isActive())
        m_ticker.start();
}

int Player::rewindBy(qint64 pausedMs) const {
    return m_autoRewind ? rewindAfter(pausedMs) : 0;
}

void Player::configure(const QVariantMap &p) {
    m_autoRewind = p.value(QStringLiteral("autoRewind"), true).toBool();
    m_safetyHours = std::clamp(p.value(QStringLiteral("safetyStopHours"), 2).toInt(), 0, 3);
    m_fadeSeconds = std::clamp(p.value(QStringLiteral("sleepFadeSeconds"), 30).toInt(), 10, 60);
    m_extendMinutes = std::clamp(p.value(QStringLiteral("sleepExtendMinutes"), 10).toInt(), 5, 15);
    // Lịch sai cấu trúc coi như chưa có lịch (cleanSleepSchedule của listen/sleep.ts): "HH:mm" hai đầu, số phút trong các mức giao diện đưa ra.
    const QVariantMap given = p.value(QStringLiteral("sleepSchedule")).toMap();
    static const QRegularExpression clock(QStringLiteral("^([01]\\d|2[0-3]):[0-5]\\d$"));
    const int minutes = given.value(QStringLiteral("minutes")).toInt();
    const bool fits = clock.match(given.value(QStringLiteral("from")).toString()).hasMatch()
        && clock.match(given.value(QStringLiteral("to")).toString()).hasMatch()
        && (minutes == 15 || minutes == 30 || minutes == 45 || minutes == 60);
    const QVariantMap schedule = fits ? given : QVariantMap();
    if (schedule != m_schedule)
        m_scheduleChecked = false; // đổi lịch = chạy lại kiểm tra như phụ thuộc [options.schedule] của useEffect bản web
    m_schedule = schedule;
}
QString Player::scheduleWindow() const {
    const QTime from = QTime::fromString(m_schedule.value(QStringLiteral("from")).toString(), QStringLiteral("HH:mm"));
    const QTime to = QTime::fromString(m_schedule.value(QStringLiteral("to")).toString(), QStringLiteral("HH:mm"));
    const QDateTime now = QDateTime::fromMSecsSinceEpoch(m_now());
    const QTime current = now.time();
    if (!from.isValid() || !to.isValid() || from == to) return {};
    const bool overnight = from > to;
    if (!(overnight ? current >= from || current < to : current >= from && current < to)) return {};
    // Khoá của đêm ấy = ngày bắt đầu khung (start.toDateString() của bản web): đổi giờ lịch giữa đêm không bật lại hẹn giờ đã tắt.
    const QDate start = overnight && current < to ? now.date().addDays(-1) : now.date();
    return start.toString(Qt::ISODate);
}

// ---- nạp sách ----

void Player::open(const QString &bookId, int chapterId, double at, bool autoplay) {
    const quint64 seq = ++m_openSeq;
    ++m_intent;
    if (autoplay)
        m_wantsPlay = true;
    m_net->request("GET", QStringLiteral("/api/listen/books/%1").arg(bookId), {}, [this, seq, chapterId, at, autoplay](int status, const QJsonObject &body) {
        if (seq != m_openSeq)
            return;
        if (status < 200 || status >= 300 || body.isEmpty()) {
            setNotice(QStringLiteral("Chưa mở được cuốn này. Bạn thử lại."));
            return;
        }
        start(parseBook(body), chapterId, at, autoplay);
    }, false);
}

void Player::playBook(const QString &bookId) {
    if (m_loaded && m_trackBook == bookId) {
        resume();
        return;
    }
    open(bookId, -1, -1, true);
}

void Player::playChapter(const QString &bookId, int chapterId) {
    if (m_loaded && m_trackBook == bookId && m_chapterId == chapterId) {
        resume();
        return;
    }
    open(bookId, chapterId, -2, true);
}

void Player::restoreLast(const QJsonArray &library) {
    m_outbox->flush(); // bản chờ của lần chạy trước đi trước phiên mới
    updateTicker();
    if (m_loaded)
        return;
    QString best;
    double bestAt = 0;
    for (const QJsonValue &value : library) {
        const QJsonObject item = value.toObject();
        if (item.value(QStringLiteral("remote")).isObject() || item.value(QStringLiteral("chaptersAvailable")).toInt() <= 0)
            continue;
        const double at = item.value(QStringLiteral("state")).toObject().value(QStringLiteral("last")).toObject().value(QStringLiteral("at")).toDouble();
        if (at > bestAt) {
            bestAt = at;
            best = item.value(QStringLiteral("id")).toString();
        }
    }
    if (!best.isEmpty())
        open(best, -1, -1, false);
}

void Player::start(const Book &book, int chapterId, double at, bool autoplay) {
    // `at` < 0: chưa nói chỗ nào. -2: chỗ nghe dở riêng của chương (hàng chương ở trang sách).
    bool atGiven = at >= 0;
    if (chapterId < 0) {
        const std::optional<ResumePoint> point = resumePoint(book);
        if (!point) {
            setNotice(QStringLiteral("Cuốn này chưa có chương nào để nghe."));
            return;
        }
        chapterId = point->chapterId;
        at = point->at;
        atGiven = true;
    }
    const auto found = std::find_if(book.chapters.begin(), book.chapters.end(), [chapterId](const Chapter &item) { return item.id == chapterId; });
    if (found == book.chapters.end() || !canPlay(*found)) {
        setNotice(QStringLiteral("Chương này chưa có audio."));
        return;
    }
    if (at == -2) {
        at = chapterResumeAt(book, *found);
        atGiven = true;
    }
    if (!autoplay) {
        if (m_loaded)
            return; // thanh đã có sách: không đè
        adoptBook(book);
        const double back = book.hasLast ? rewindBy(m_now() - qint64(book.lastAt * 1000)) : 0;
        m_pausedAt = 0;
        load(chapterId, std::max(0.0, at - back), false);
        return;
    }
    ++m_intent;
    m_wantsPlay = true;
    const bool sameSpot = m_loaded && book.id == m_trackBook && chapterId == m_chapterId && !atGiven;
    adoptBook(book);
    if (sameSpot) {
        resume();
        return;
    }
    // Nghe tiếp đúng chỗ đã lưu: lùi theo độ dài lần dừng (mở lại app sáng hôm sau thì lùi hẳn 10 giây).
    double startAt = atGiven ? at : 0;
    if (atGiven && book.hasLast && book.lastChapter == chapterId && std::fabs(book.lastSeconds - at) < 1)
        startAt = std::max(0.0, at - rewindBy(m_now() - qint64(book.lastAt * 1000)));
    load(chapterId, startAt, true);
}

void Player::adoptBook(const Book &book) {
    if (m_loaded && (m_trackBook != book.id || m_trackRecord != book.record)) {
        if (!m_history.isEmpty()) {
            m_history.clear();
            emit historyChanged();
        }
        if (m_noticeKey == QLatin1String("back"))
            setNotice(QString());
    }
    m_book = book;
    m_chapters.setBook(book);
    const double bookRate = startingRate(book.rate.has_value() ? book.rate : std::optional<double>(m_defaultRate));
    if (!qFuzzyCompare(bookRate, m_rate))
        applyRate(bookRate);
    changed();
    emit bookChanged();
}

std::shared_ptr<Player::Session> Player::newSession() {
    auto session = std::make_shared<Session>();
    session->id = newId();
    session->bookId = m_book.id;
    session->record = m_book.record;
    m_sessions.prepend(session);
    while (m_sessions.size() > kSessionsKept)
        m_sessions.removeLast();
    return session;
}

void Player::load(int chapterId, double at, bool autoplay) {
    const Chapter *item = chapter(chapterId);
    if (!item)
        return;
    const bool sameTrack = m_loaded && m_trackBook == m_book.id && m_trackRecord == m_book.record;
    const bool moved = sameTrack && m_chapterId != chapterId;
    // Chỗ cũ lưu TRƯỚC khi bộ phát chuyển sang chương mới (m_trackBook/m_chapterId còn là của chương cũ).
    save(true);
    if (m_loaded && !sameTrack)
        closeListening();
    // Phiên lưu chỗ nghe: mỗi lần nạp cuốn / hồ sơ khác là một phiên mới, bắt tay trước lần lưu đầu.
    if (!m_session || m_session->bookId != m_book.id || m_session->record != m_book.record) {
        m_session = newSession();
        ensureSession(m_session, [](int) {});
    }
    setError(QString());
    setAtEnd(QStringLiteral("none"));
    const bool wasLoaded = m_loaded;
    m_trackBook = m_book.id;
    m_trackRecord = m_book.record;
    m_chapterId = chapterId;
    m_loaded = true;
    m_savedSpot = moved ? std::nullopt : std::optional<Spot>(Spot{chapterId, at});
    m_stamp = m_now();
    m_lastAttempt = m_stamp; // vừa nạp ở chỗ đã lưu (hay vừa lưu chỗ cũ): lần lưu định kỳ đầu tiên là 10 giây sau
    m_ended = false;
    m_audible = false;
    setBuffering(false);
    m_chapters.setCurrent(chapterId);
    m_clock.set(at, 0);
    m_out->setRate(m_rate);
    m_out->setVolume(m_volume * (m_fading ? m_gain : 1.0));
    m_loadingSource = true;
    m_out->load(m_net->audioUrl(m_book.id, chapterId), at);
    m_loadingSource = false;
    if (autoplay) {
        requestPlay();
    } else if (m_playing) {
        m_out->pause();
        setPlaying(false);
        closeListening();
        m_audible = false;
    }
    if (!autoplay)
        m_pausedAt = 0;
    changed();
    if (!wasLoaded)
        emit loadedChanged();
    emit chapterChanged();
    m_clock.refresh();
    updateTicker();
}

// ---- phát / dừng ----

void Player::requestPlay() {
    m_pausedAt = 0;
    setError(QString());
    if (!m_playing) {
        m_audible = false;
        setPlaying(true);
        openListening();
        resetSleepMark();
    }
    m_out->play();
}

void Player::resume() {
    if (!m_loaded)
        return;
    const quint64 intent = ++m_intent;
    m_wantsPlay = true;
    // Nguồn đã hỏng: bấm phát ở đâu cũng là nạp lại đúng chỗ - phát lại nguồn hỏng chỉ ra lỗi cũ.
    if (!m_error.isEmpty()) {
        retry();
        return;
    }
    if (m_playing || m_ended) {
        resumeNow();
        return;
    }
    // Thiết bị khác đã nghe xa hơn SAU lần cuối máy này nạp / lưu: tới chỗ ấy, đừng phát chỗ cũ rồi lưu đè. Hỏi lại máy chủ (nó tự đổi chỗ
    // nghe với máy kia), chờ tối đa m_freshMs rồi mới quyết.
    auto decided = std::make_shared<bool>(false);
    const QString bookId = m_trackBook;
    const QString record = m_trackRecord;
    auto decide = [this, intent, decided, bookId](const std::optional<QJsonObject> &fresh) {
        if (*decided)
            return;
        *decided = true;
        if (intent != m_intent || !m_wantsPlay || !m_loaded || m_trackBook != bookId || m_playing)
            return;
        if (fresh) {
            Book latest = parseBook(*fresh);
            if (latest.record == m_trackRecord)
                applyState(m_book, fresh->value(QStringLiteral("state")).toObject());
            else
                m_book.hasLast = false; // hồ sơ nghe đã đổi ở máy khác: không có chỗ nào để nhảy tới
        }
        const std::optional<ResumePoint> away = newerElsewhere(m_book, m_stamp, m_chapterId, position());
        const Chapter *target = away ? chapter(away->chapterId) : nullptr;
        if (away && target && canPlay(*target)) {
            jumpTo(away->chapterId, away->at, QStringLiteral("Nghe tiếp từ chỗ thiết bị khác đã nghe tới (%1)").arg(formatClock(away->at)));
            return;
        }
        resumeNow();
    };
    Q_UNUSED(record);
    m_net->request("GET", QStringLiteral("/api/listen/books/%1").arg(bookId), {}, [decide](int status, const QJsonObject &body) {
        decide(status >= 200 && status < 300 && !body.isEmpty() ? std::optional<QJsonObject>(body) : std::nullopt);
    }, false);
    QPointer<Player> self(this);
    QTimer::singleShot(m_freshMs, this, [decide] { decide(std::nullopt); });
}

void Player::resumeNow() {
    if (!m_loaded)
        return;
    if (m_ended) {
        const int target = availableAfter(m_book.chapters, m_chapterId, 1);
        if (target >= 0) {
            load(target, 0, true);
        } else if (!m_book.complete) {
            setNotice(QStringLiteral("Đã nghe hết phần đã có - %1").arg(m_book.producing ? QStringLiteral("chương tiếp theo sẽ nghe được khi máy làm xong chương ấy")
                                                                                         : QStringLiteral("các chương sau chưa có audio")));
        } else {
            setNotice(QStringLiteral("Đã nghe hết sách"), QStringLiteral("Nghe lại từ đầu"), QStringLiteral("restart"));
        }
        return;
    }
    const int back = m_pausedAt ? rewindBy(m_now() - m_pausedAt) : 0;
    if (back)
        m_out->seek(std::max(0.0, position() - back));
    requestPlay();
}

void Player::pause() {
    ++m_intent;
    m_wantsPlay = false;
    if (!m_loaded)
        return;
    m_out->pause();
    markPaused(true);
}

void Player::markPaused(bool saveNow) {
    const bool was = m_playing;
    setPlaying(false);
    setBuffering(false);
    closeListening();
    m_clock.refresh();
    m_pausedAt = m_now();
    m_audible = false;
    if (was)
        resetSleepMark();
    if (saveNow)
        save(true);
}

void Player::toggle() {
    if (!m_loaded)
        return;
    if (m_playing)
        pause();
    else
        resume();
}

void Player::seek(double seconds) {
    if (!m_loaded)
        return;
    const double from = position();
    setAtEnd(QStringLiteral("none"));
    const double length = duration();
    const double target = std::max(0.0, length > 0 ? std::min(seconds, length) : seconds);
    m_ended = false;
    m_out->seek(target);
    m_clock.set(target, length);
    resetSleepMark();
    if (std::fabs(target - from) > kJumpSeconds)
        remember({m_chapterId, from}, {m_chapterId, target}, QString());
}

void Player::skip(double delta) {
    if (!m_loaded)
        return;
    const double length = duration();
    double target = std::max(0.0, position() + delta);
    if (length > 0)
        target = std::min(target, length);
    if (delta < 0)
        setAtEnd(QStringLiteral("none"));
    m_ended = false;
    m_out->seek(target);
    m_clock.set(target, length);
    resetSleepMark();
}

void Player::jumpTo(int chapterId, double at, const QString &note) {
    const Chapter *target = chapter(chapterId);
    if (!m_loaded || !target || !canPlay(*target))
        return;
    setAtEnd(QStringLiteral("none"));
    const Spot from{m_chapterId, position()};
    if (chapterId != m_chapterId || std::fabs(at - from.seconds) > kJumpSeconds)
        remember(from, {chapterId, at}, note);
    m_wantsPlay = true;
    ++m_intent;
    if (chapterId == m_chapterId) {
        m_ended = false;
        m_out->seek(at);
        m_clock.set(at, duration());
        resetSleepMark();
        requestPlay();
        return;
    }
    load(chapterId, at, true);
}

void Player::remember(const Spot &from, const Spot &to, const QString &note) {
    // Nhảy xa là một đoạn nghe khác: phiên cũ kết thúc ở chỗ trước khi nhảy.
    const bool wasPlaying = m_playing;
    closeListening(false, from);
    if (wasPlaying)
        openListening();
    m_history.append(from);
    while (m_history.size() > kHistory)
        m_history.removeFirst();
    emit historyChanged();
    changed();
    const bool sameChapter = from.chapterId == to.chapterId;
    setNotice(!note.isEmpty() ? note : QStringLiteral("Đã tới %1").arg(sameChapter ? formatClock(to.seconds) : QStringLiteral("chương mới")),
              QStringLiteral("Quay lại"), QStringLiteral("back"));
}

void Player::goBack() {
    if (m_history.isEmpty() || !m_loaded)
        return;
    const Spot target = m_history.takeLast();
    emit historyChanged();
    if (m_noticeKey == QLatin1String("back"))
        setNotice(QString());
    if (target.chapterId == m_chapterId) {
        m_out->seek(target.seconds);
        m_clock.set(target.seconds, duration());
        resetSleepMark();
        return;
    }
    if (chapter(target.chapterId))
        load(target.chapterId, target.seconds, m_playing);
}

void Player::step(int direction) {
    if (!m_loaded)
        return;
    if (direction < 0 && position() > kRestartAfterSeconds) {
        m_out->seek(0);
        m_ended = false;
        m_clock.set(0, duration());
        resetSleepMark();
        return;
    }
    const int target = availableAfter(m_book.chapters, m_chapterId, direction);
    if (target < 0) {
        // Chương sau có mà chưa có audio: nói ra - nút không im lặng.
        if (direction > 0) {
            for (int i = 0; i < m_book.chapters.size(); ++i) {
                if (m_book.chapters[i].id == m_chapterId && i + 1 < m_book.chapters.size() && !canPlay(m_book.chapters[i + 1])) {
                    setNotice(QStringLiteral("Chương sau chưa có audio"));
                    break;
                }
            }
        }
        return;
    }
    remember({m_chapterId, position()}, {target, 0}, QString());
    load(target, 0, m_playing || m_ended);
}

void Player::next() {
    step(1);
}

void Player::previous() {
    step(-1);
}

void Player::restart() {
    for (const Chapter &item : m_book.chapters) {
        if (canPlay(item)) {
            jumpTo(item.id, 0);
            return;
        }
    }
}

void Player::retry() {
    if (!m_loaded)
        return;
    ++m_intent;
    m_wantsPlay = true;
    const double at = position();
    load(m_chapterId, at, true);
}

void Player::dismissError() {
    setError(QString());
}

void Player::dismissNotice() {
    setNotice(QString());
}

void Player::runNoticeAction() {
    const QString key = m_noticeKey;
    setNotice(QString());
    if (key == QLatin1String("back"))
        goBack();
    else if (key == QLatin1String("restart"))
        restart();
    else if (key == QLatin1String("stay"))
        setSleep(QStringLiteral("off"));
}

// ---- tốc độ ----

void Player::applyRate(double rate) {
    m_rate = rate;
    m_out->setRate(rate);
    changed();
    emit rateChanged();
}

void Player::setRate(double rate) {
    if (rate <= 0)
        return;
    applyRate(rate);
    if (!m_loaded)
        return;
    // Tốc độ nhớ riêng của cuốn: cũng nằm trong bộ nhớ của trang sách (state.rate) - nghe lại không đè tốc độ cũ lên.
    m_book.rate = rate;
    QJsonObject body{{QStringLiteral("rate"), rate}};
    if (!m_trackRecord.isEmpty())
        body.insert(QStringLiteral("record"), m_trackRecord);
    m_net->request("POST", QStringLiteral("/api/listen/books/%1/rate").arg(m_trackBook), body, [](int, const QJsonObject &) {});
}

void Player::stepRate(int direction) {
    setRate(nearestSpeed(m_rate, direction));
}

void Player::setVolume(double volume) {
    volume = std::clamp(volume, 0.0, 1.0);
    if (volume == m_volume)
        return;
    m_volume = volume;
    m_out->setVolume(outputVolume());
    emit volumeChanged();
}

void Player::toggleMute() {
    if (m_volume > 0) {
        m_muted = m_volume;
        setVolume(0);
    } else {
        setVolume(m_muted > 0 ? m_muted : 0.9);
    }
}

// ---- hẹn giờ ----

void Player::resetSleepMark() {
    m_sleepMarkAt = m_now();
    m_sleepMarkSeconds = position();
}

void Player::applySleepState(Sleep::Kind kind, int minutes, double leftMs) {
    m_scheduleChecked = false; // phụ thuộc `sleep.kind` của useEffect lịch đêm
    m_sleep.kind = kind;
    m_sleep.minutes = minutes;
    m_sleep.leftMs = leftMs;
    m_sleepWarned = false;
    changed();
    emit sleepChanged();
    m_clock.setSleepLeft(sleepLeftSeconds());
    updateTicker();
}

void Player::setSleep(const QString &kind, int minutes) {
    endFade();
    resetSleepMark();
    if (kind == QLatin1String("minutes") && minutes > 0) {
        m_lastSleepMinutes = minutes;
        m_sleepStoppedAt = 0;
        applySleepState(Sleep::Minutes, minutes, minutes * 60'000.0);
    } else if (kind == QLatin1String("chapter")) {
        m_sleepStoppedAt = 0;
        applySleepState(Sleep::Chapter, 0, 0);
    } else {
        m_scheduleOffFor = scheduleWindow();
        applySleepState(Sleep::Off, 0, 0);
    }
}

void Player::extendSleep(int minutes) {
    if (minutes <= 0)
        minutes = m_extendMinutes;
    if (m_sleep.kind == Sleep::Off)
        return;
    endFade();
    const double left = m_sleep.kind == Sleep::Minutes ? m_sleep.leftMs : 0;
    resetSleepMark();
    applySleepState(Sleep::Minutes, m_sleep.kind == Sleep::Minutes ? m_sleep.minutes : minutes, left + minutes * 60'000.0);
    setNotice(QStringLiteral("Nghe thêm %1 phút").arg(minutes));
}

void Player::endFade() {
    m_gain = 1;
    setFading(false);
    m_out->setVolume(m_volume);
    emit outputGainChanged();
}

void Player::tickSleep(qint64 now) {
    const qint64 wall = now - m_sleepMarkAt;
    const double pos = position();
    const double sound = ((pos - m_sleepMarkSeconds) / std::max(0.25, m_rate)) * 1000.0;
    m_sleepMarkAt = now;
    m_sleepMarkSeconds = pos;
    double left = -1;
    if (m_sleep.kind == Sleep::Minutes) {
        // Chỉ tính thời gian tiếng thật tiến lên. Khoảng mất nhịp > 2 giây (máy ngủ, giao diện treo) không phải bằng chứng có tiếng.
        const double heard = m_audible && m_playing && wall >= 0 && wall <= 2000 ? std::max(0.0, std::min(double(wall), sound)) : 0.0;
        m_sleep.leftMs = std::max(0.0, m_sleep.leftMs - heard);
        left = m_sleep.leftMs;
        m_clock.setSleepLeft(sleepLeftSeconds());
    } else if (m_sleep.kind == Sleep::Chapter && duration() > 0) {
        left = ((duration() - pos) / std::max(0.25, m_rate)) * 1000.0;
    }
    if (left < 0)
        return;
    if (m_sleep.kind == Sleep::Minutes && left <= 0) {
        stopBySleep();
        return;
    }
    if (m_sleep.kind == Sleep::Minutes) {
        if (left <= kSafetyWarnMs && !m_sleepWarned) {
            m_sleepWarned = true;
            emit sleepWarning(); // 30 giây trước khi tắt: nốt trầm của lớp tiếng chạm (Feedback), tiếng duy nhất kêu cả khi đang phát
        } else if (left > kSafetyWarnMs)
            m_sleepWarned = false;
    }
    const double fadeMs = m_fadeSeconds * 1000.0;
    if (left < fadeMs) {
        m_gain = fadeGain(left, fadeMs);
        m_out->setVolume(m_volume * m_gain);
        emit outputGainChanged();
        setFading(true);
    } else if (m_fading) {
        endFade();
    }
}

void Player::stopBySleep() {
    ++m_intent;
    m_wantsPlay = false;
    m_out->pause();
    markPaused(false);
    endFade();
    applySleepState(Sleep::Off, 0, 0);
    m_sleepStoppedAt = m_now();
    emit sleepChanged();
    save(true);
}

// ---- lưu chỗ nghe ----

void Player::save(bool force) {
    if (!m_loaded)
        return;
    const double pos = position();
    if (m_savedSpot && m_savedSpot->chapterId == m_chapterId && std::fabs(m_savedSpot->seconds - pos) < 0.05)
        return;
    const qint64 now = m_now();
    if (!force && now - m_lastAttempt < (m_uiActive ? kSaveEveryMs : kHiddenSaveEveryMs))
        return;
    m_lastAttempt = now;
    ProgressSpot spot;
    spot.bookId = m_trackBook;
    spot.chapterId = m_chapterId;
    spot.seconds = pos;
    spot.duration = duration();
    spot.record = m_trackRecord;
    spot.savedAt = now;
    if (m_session) {
        spot.sessionId = m_session->id;
        spot.revision = ++m_session->revision;
        spot.hasRevision = true;
    }
    if (force)
        m_notifyRevision = spot.revision;
    m_outbox->put(spot);
    updateTicker();
}

void Player::ensureSession(const std::shared_ptr<Session> &session, std::function<void(int)> then) {
    if (session->ready) {
        then(200);
        return;
    }
    session->waiting.append(std::move(then));
    if (session->starting)
        return;
    session->starting = true;
    QJsonObject body{{QStringLiteral("sessionId"), session->id}};
    if (!session->record.isEmpty())
        body.insert(QStringLiteral("record"), session->record);
    m_net->request("POST", QStringLiteral("/api/listen/books/%1/progress/session").arg(session->bookId), body, [session](int status, const QJsonObject &) {
        session->starting = false;
        session->ready = status >= 200 && status < 300;
        const auto waiting = std::exchange(session->waiting, {});
        for (const auto &callback : waiting)
            callback(status);
    });
}

void Player::sendSpot(const ProgressSpot &spot, ProgressOutbox::Done done) {
    std::shared_ptr<Session> session;
    for (const auto &item : std::as_const(m_sessions)) {
        if (item->id == spot.sessionId) {
            session = item;
            break;
        }
    }
    auto post = [this, spot, done] {
        QJsonObject body{{QStringLiteral("chapterId"), spot.chapterId}, {QStringLiteral("seconds"), spot.seconds}, {QStringLiteral("duration"), spot.duration}};
        if (!spot.record.isEmpty())
            body.insert(QStringLiteral("record"), spot.record);
        if (!spot.sessionId.isEmpty()) {
            body.insert(QStringLiteral("sessionId"), spot.sessionId);
            body.insert(QStringLiteral("revision"), spot.revision);
        }
        m_net->request("POST", QStringLiteral("/api/listen/books/%1/progress").arg(spot.bookId), body, [this, spot, done](int status, const QJsonObject &reply) {
            if (status >= 200 && status < 300 && spot.bookId == m_book.id && !reply.isEmpty()) {
                applyState(m_book, reply);
                m_chapters.refreshStates(m_book);
            }
            done(status);
        });
    };
    if (!session) {
        post();
        return;
    }
    ensureSession(session, [post, done](int status) {
        if (status >= 200 && status < 300)
            post();
        else
            done(status);
    });
}

void Player::onAck(const ProgressSpot &spot) {
    if (spot.bookId != m_trackBook || spot.record != m_trackRecord)
        return;
    if (!m_session || spot.sessionId != m_session->id)
        return;
    if (spot.revision < m_session->acked)
        return;
    m_session->acked = spot.revision;
    if (m_notifyRevision > 0 && spot.revision >= m_notifyRevision) {
        m_notifyRevision = 0;
        emit listeningChanged(spot.bookId);
    }
    if (spot.savedAt < m_lastSaved)
        return;
    m_lastSaved = spot.savedAt;
    m_stamp = m_lastSaved;
    m_savedSpot = Spot{spot.chapterId, spot.seconds};
}

// ---- phiên nghe (lịch sử) ----

void Player::openListening() {
    if (!m_loaded)
        return;
    if (m_listening && m_listening->bookId == m_trackBook && m_listening->record == m_trackRecord) {
        m_listening->mark = m_now();
        return;
    }
    Listening listening;
    listening.id = newId().left(12);
    listening.startedAt = m_now() / 1000.0;
    listening.from = {m_chapterId, position()};
    listening.bookId = m_trackBook;
    listening.record = m_trackRecord;
    listening.mark = m_now();
    m_listening = listening;
}

void Player::closeListening(bool leaving, std::optional<Spot> to) {
    if (!m_listening || !m_loaded)
        return;
    Listening session = *m_listening;
    session.listened += (m_now() - session.mark) / 1000.0;
    m_listening.reset();
    if (session.listened < kListenedMinimum || session.bookId != m_trackBook)
        return;
    QJsonObject body{{QStringLiteral("id"), session.id},
                     {QStringLiteral("device"), QStringLiteral("desktop")},
                     {QStringLiteral("startedAt"), session.startedAt},
                     {QStringLiteral("endedAt"), m_now() / 1000.0},
                     {QStringLiteral("listened"), session.listened},
                     {QStringLiteral("from"), QJsonObject{{QStringLiteral("chapterId"), session.from.chapterId}, {QStringLiteral("seconds"), session.from.seconds}}},
                     {QStringLiteral("to"), QJsonObject{{QStringLiteral("chapterId"), to ? to->chapterId : m_chapterId}, {QStringLiteral("seconds"), to ? to->seconds : position()}}}};
    if (!session.record.isEmpty())
        body.insert(QStringLiteral("record"), session.record);
    ++m_postsInFlight;
    Q_UNUSED(leaving);
    m_net->request("POST", QStringLiteral("/api/listen/books/%1/sessions").arg(session.bookId), body, [this](int, const QJsonObject &) {
        if (m_postsInFlight > 0)
            --m_postsInFlight;
    });
}

// ---- sự kiện của bộ phát âm ----

void Player::onOutPlaying(bool playing) {
    if (m_loadingSource || !m_loaded)
        return;
    if (playing && m_playing) {
        m_audible = true;
        setBuffering(false);
        resetSleepMark();
        m_clock.refresh();
    }
    // playing = false: lệnh dừng của mình đã xử lý ngay lúc bấm; sự kiện dừng muộn của nguồn cũ không được lật lại một lệnh phát mới.
}

void Player::onSeeked() {
    if (!m_loaded)
        return;
    resetSleepMark();
    m_clock.refresh();
    emit audioSeeked();
    save(true);
}

void Player::onDuration(double seconds) {
    Q_UNUSED(seconds);
    if (!m_loaded)
        return;
    m_clock.refresh();
    if (!m_playing && !m_savedSpot)
        save(true);
}

void Player::onFailed(const QString &reason) {
    if (!m_loaded)
        return;
    m_lastFailure = reason;
    setError(kPlayError);
    setBuffering(false);
    m_out->pause();
    markPaused(false);
}

void Player::onEnded() {
    if (!m_loaded)
        return;
    const int target = availableAfter(m_book.chapters, m_chapterId, 1);
    m_ended = true;
    markPaused(false);
    m_pausedAt = 0;
    save(true);
    if (m_sleep.kind == Sleep::Chapter) {
        // Hẹn "hết chương": dừng ở đây, nhưng nạp sẵn chương kế ở 0:00 và lưu nó làm chỗ nghe tiếp - sáng mai bấm Tiếp tục là vào chương mới.
        stopBySleep();
        if (target >= 0) {
            load(target, 0, false);
            m_savedSpot = std::nullopt;
            save(true);
        }
        return;
    }
    if (target >= 0) {
        load(target, 0, true);
        return;
    }
    const bool caughtUp = !m_book.complete;
    setAtEnd(caughtUp ? QStringLiteral("caughtUp") : QStringLiteral("finished"));
    if (caughtUp)
        setNotice(QStringLiteral("Đã nghe hết phần đã có - %1").arg(m_book.producing ? QStringLiteral("chương tiếp theo sẽ nghe được khi máy làm xong chương ấy")
                                                                                     : QStringLiteral("các chương sau chưa có audio")));
    else
        setNotice(QStringLiteral("Đã nghe hết sách"), QStringLiteral("Nghe lại từ đầu"), QStringLiteral("restart"));
}

// ---- nhịp ----

void Player::tick() {
    const qint64 now = m_now();
    if (now - m_lastFlush >= kSaveEveryMs) {
        m_lastFlush = now;
        m_outbox->flush();
    }
    // Lịch đêm chỉ xét lúc BẮT ĐẦU nghe (đang phát + hẹn giờ tắt): useEffect [schedule, playing, sleep.kind] của bản web, không xét lại mỗi nhịp -
    // đang nghe qua giờ bắt đầu khung thì không tự hẹn giữa chừng.
    const bool listening = m_loaded && m_playing && m_sleep.kind == Sleep::Off;
    if (!listening)
        m_scheduleChecked = false;
    if (!m_loaded) {
        updateTicker();
        return;
    }
    if (!m_playing) {
        updateTicker();
        return;
    }
    if (listening && !m_scheduleChecked) {
        m_scheduleChecked = true;
        const QString night = scheduleWindow();
        if (!night.isEmpty() && night != m_scheduleOffFor) {
            const int minutes = m_schedule.value(QStringLiteral("minutes")).toInt();
            setSleep(QStringLiteral("minutes"), minutes);
            setNotice(QStringLiteral("Lịch đêm %1-%2: đã tự hẹn giờ %3 phút")
                .arg(m_schedule.value(QStringLiteral("from")).toString(), m_schedule.value(QStringLiteral("to")).toString()).arg(minutes));
        }
    }
    save();
    if (m_sleep.kind != Sleep::Off) {
        tickSleep(now);
    } else if (m_safetyHours > 0 && now - m_lastActivity >= qint64(m_safetyHours) * 3'600'000) {
        // Lưới an toàn: phát liên tục quá lâu mà không ai chạm máy (ngủ quên, quên hẹn giờ) thì tự hẹn 1 phút - nhỏ dần rồi dừng như hẹn giờ thường.
        const int lastMinutes = m_lastSleepMinutes; // lưới an toàn không đổi "lần hẹn gần nhất" của nút hẹn giờ (bản web không gọi setLastSleepMinutes)
        setSleep(QStringLiteral("minutes"), 1);
        m_lastSleepMinutes = lastMinutes;
        setNotice(QStringLiteral("Không thấy ai chạm máy suốt %1 giờ - sẽ tắt sau 1 phút").arg(m_safetyHours), QStringLiteral("Vẫn đang nghe"), QStringLiteral("stay"));
    }
    updateTicker();
}

// ---- đóng / tắt app ----

void Player::close() {
    ++m_intent;
    ++m_openSeq;
    m_wantsPlay = false;
    if (!m_loaded)
        return;
    save(true);
    closeListening();
    m_out->stop();
    m_loaded = false;
    m_trackBook.clear();
    m_trackRecord.clear();
    m_book = Book();
    m_chapterId = 0;
    m_session.reset();
    m_savedSpot.reset();
    m_ended = false;
    m_audible = false;
    setPlaying(false);
    setBuffering(false);
    setError(QString());
    setNotice(QString());
    setAtEnd(QStringLiteral("none"));
    endFade();
    applySleepState(Sleep::Off, 0, 0);
    if (!m_history.isEmpty()) {
        m_history.clear();
        emit historyChanged();
    }
    m_chapters.setBook(m_book);
    m_clock.set(0, 0);
    changed();
    emit bookChanged();
    emit chapterChanged();
    emit loadedChanged();
    updateTicker();
}

void Player::shutdown(int waitMs) {
    if (m_loaded) {
        save(true);
        closeListening(true);
    }
    if (m_outbox->idle() && m_postsInFlight == 0)
        return;
    QEventLoop loop;
    QTimer limit;
    limit.setSingleShot(true);
    connect(&limit, &QTimer::timeout, &loop, &QEventLoop::quit);
    QTimer poll;
    connect(&poll, &QTimer::timeout, &loop, [&] {
        if (m_outbox->idle() && m_postsInFlight == 0)
            loop.quit();
    });
    limit.start(waitMs);
    poll.start(20);
    loop.exec();
}
