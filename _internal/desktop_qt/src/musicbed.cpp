#include "musicbed.h"

#include "audioout.h"

#include <QDateTime>

#include <cmath>

using namespace MusicLogic;

// Một phần tử phát (thay cho một <audio> của bản web): AudioOut + những gì <audio> tự nhớ mà AudioOut không có.
struct MusicBed::Voice {
    AudioOut *out = nullptr;
    QString link;
    double volume = 0;
    bool wantPlay = false; // = !audio.paused
    bool loop = false;
    bool sounded = false;  // đã phát ra tiếng thật (playingChanged(true)) - trước đó bài mới giữ âm lượng 0
    bool ended = false;
    bool released = false;
    bool loaded = false;   // đã biết độ dài (= loadedmetadata)
    bool waiting = false;  // đang chờ dữ liệu (= readyState < 3)
    double fadeStep = -1;  // âm lượng bớt mỗi nhịp khi mờ đi
};

MusicBed::MusicBed(std::function<AudioOut *()> make, std::function<QUrl(const QString &)> url, std::function<void(const QString &)> warm,
                   std::function<qint64()> now, QObject *parent)
    : QObject(parent), m_make(std::move(make)), m_url(std::move(url)), m_warm(std::move(warm)), m_now(std::move(now)) {
    if (!m_now)
        m_now = [] { return QDateTime::currentMSecsSinceEpoch(); };
    m_timer.setInterval(STEP_MS);
    connect(&m_timer, &QTimer::timeout, this, &MusicBed::fadeTick);
    m_loopTicket.setSingleShot(true);
    connect(&m_loopTicket, &QTimer::timeout, this, [this] {
        const VoiceP audio = std::exchange(m_ticketAudio, nullptr);
        if (m_current && m_current->audio == audio)
            crossLoop(m_lastTime, true);
    });
}

MusicBed::~MusicBed() {
    stop();
}

// ---- thao tác trên một phần tử ----

double MusicBed::duration(const VoiceP &audio) {
    const double length = audio && audio->out ? audio->out->duration() : 0;
    return length > 0 ? length : std::nan("");
}

double MusicBed::currentTime(const VoiceP &audio) {
    return audio && audio->out ? audio->out->position() : 0;
}

void MusicBed::setCurrentTime(const VoiceP &audio, double seconds) {
    if (audio && audio->out)
        audio->out->seek(seconds);
}

void MusicBed::setVolumeOf(const VoiceP &audio, double volume) {
    audio->volume = std::clamp(volume, 0.0, 1.0);
    if (audio->out)
        audio->out->setVolume(audio->volume);
}

void MusicBed::setLoopOf(const VoiceP &audio, bool loop) {
    audio->loop = loop;
    if (audio->out)
        audio->out->setLoop(loop);
}

void MusicBed::play(const VoiceP &audio) {
    audio->wantPlay = true;
    audio->ended = false;
    if (audio->out)
        audio->out->play();
}

void MusicBed::pause(const VoiceP &audio) {
    audio->wantPlay = false;
    if (audio->out)
        audio->out->pause();
}

int MusicBed::voices() const {
    return (m_current ? 1 : 0) + int(m_fading.size()) + (m_standby ? 1 : 0);
}

// ---- NextChapterWarm ----

NextChapterWarm::NextChapterWarm(std::function<void(int, Answer)> ask, std::function<void(const QString &)> warm, std::function<qint64()> now)
    : m_ask(std::move(ask)), m_warm(std::move(warm)), m_now(std::move(now)) {
    if (!m_now)
        m_now = [] { return QDateTime::currentMSecsSinceEpoch(); };
}

void NextChapterWarm::update(const QString &key, std::optional<int> next, double remaining) {
    if (!next || !(remaining > 0) || remaining > NEXT_CHAPTER_WARM_SECONDS)
        return;
    const QString ticket = QStringLiteral("%1>%2").arg(key).arg(*next);
    if (m_done.contains(ticket) || !m_asking.isEmpty() || m_retryAt.value(ticket, 0) > m_now())
        return;
    m_asking = ticket;
    m_ask(*next, [this, ticket](const std::optional<MusicCues> &result) {
        if (m_asking == ticket)
            m_asking.clear();
        const MusicCue *first = result && !result->pending && !result->cues.isEmpty() ? &result->cues.first() : nullptr;
        if (first) {
            m_done.insert(ticket);
            if (!carriedByBook(*first))
                m_warm(first->link);
        } else if (!result || result->pending || !result->unavailable.isEmpty()) {
            m_retryAt.insert(ticket, m_now() + NEXT_CHAPTER_RETRY_MS);
        } else {
            m_done.insert(ticket); // chương kế không có nhạc
        }
    });
}

// ---- như musicBed.ts ----

void MusicBed::warmLink(const QString &link) {
    if (!m_warm || !link.startsWith(QLatin1String("https://")) || m_warmed.contains(link))
        return;
    m_warmed.insert(link);
    m_warm(link);
}

void MusicBed::warmNext(const MusicCue *sounding, double seconds) {
    for (const MusicCue &cue : m_cues) {
        if (cue.start > seconds && (!sounding || cue.link != sounding->link)) {
            if (!carriedByBook(cue))
                warmLink(cue.link);
            return;
        }
    }
}

void MusicBed::setCues(const QVector<MusicCue> &cues, std::optional<double> levelDb, std::optional<double> seconds) {
    m_cues = cues;
    if (levelDb)
        m_gain = std::pow(10.0, *levelDb / 20);
    m_lastTime = seconds.value_or(m_lastTime);
    switchTo(playableAt(m_lastTime), m_lastTime);
}

void MusicBed::setVolume(double volume) {
    m_userVolume = std::clamp(volume, 0.0, 1.0);
    if (!m_current)
        return;
    m_current->goal = target();
    if (awaitingSound(*m_current))
        m_current->perTick = (m_current->goal * STEP_MS) / 1000 / m_current->fadeSeconds; // chưa có tiếng: giữ 0
    else
        setVolumeOf(m_current->audio, m_current->goal);
}

/// Bài mới còn đang chờ tải (chưa có tiếng, hay đang chờ dữ liệu): chưa được nhích âm lượng lên - bài cũ mờ đi, im lặng bằng thời gian tải.
bool MusicBed::awaitingSound(const Playing &playing) const {
    return playing.entering && (!playing.audio->sounded || playing.audio->waiting);
}

void MusicBed::sync(double seconds, bool playing, bool seeked) {
    m_lastTime = seconds;
    m_playing = playing;
    std::optional<MusicCue> cue = playableAt(seconds);
    if (m_current && m_current->early) {
        // Bài vào sớm giữ chỗ tới đầu mốc của nó; tua thì theo mốc tại chỗ tua như thường.
        if (!seeked && seconds < m_current->cue.start)
            cue = m_current->cue;
        else
            m_current->early = false;
    }
    // Mốc anh em có thể cùng khoá đoạn với mốc trước: phân biệt bằng cả giây bắt đầu.
    const bool differs = bool(cue) != bool(m_current) || (cue && m_current && (cue->key != m_current->cue.key || cue->start != m_current->cue.start));
    if (differs || (seeked && cue))
        switchTo(cue, seconds, seeked);
    retarget(seeked);
    finishTail(seconds);
    crossLoop(seconds);
    // Chỉ bài đang kêu được chơi lại; bài đang mờ đi thì chỉ dừng cùng giọng.
    QVector<VoiceP> all = m_fading;
    if (m_current)
        all.prepend(m_current->audio);
    for (const VoiceP &audio : all) {
        if (playing && !audio->wantPlay && !audio->ended && m_current && audio == m_current->audio)
            play(audio);
        if (!playing)
            pause(audio);
    }
}

bool MusicBed::failing() const {
    const qint64 now = m_now();
    for (const MusicCue &cue : m_cues)
        if (m_failed.value(cue.link, 0) > now)
            return true;
    return false;
}

QString MusicBed::activeLink() const {
    return m_current ? m_current->cue.link : QString();
}

void MusicBed::stop() {
    cancelLoopTicket();
    cancelStandby();
    if (m_current)
        release(m_current->audio);
    for (const VoiceP &audio : std::as_const(m_fading))
        release(audio);
    m_current.reset();
    m_fading.clear();
    m_cues.clear();
    m_failed.clear();
    m_timer.stop();
    emitActive();
}

std::optional<MusicCue> MusicBed::playableAt(double seconds) {
    const MusicCue *cue = cueAt(m_cues, seconds);
    if (!cue)
        return std::nullopt;
    const auto retry = m_failed.constFind(cue->link);
    if (retry == m_failed.constEnd())
        return *cue;
    if (*retry > m_now())
        return std::nullopt;
    m_failed.erase(retry);
    return *cue;
}

/// Bài `audio` của mốc `cue` không tải được: đoạn của nó im lặng, RETRY_MS sau mới thử lại.
void MusicBed::drop(const MusicCue &cue, const VoiceP &audio) {
    if (audio->released)
        return;
    m_failed.insert(cue.link, m_now() + RETRY_MS);
    const bool sounding = m_current && m_current->audio == audio;
    if (sounding) {
        cancelLoopTicket();
        cancelStandby();
    }
    release(audio);
    m_fading.removeAll(audio);
    if (sounding) {
        m_current.reset();
        emitActive();
    }
    emit loadResult(cue.link, false);
}

/// Phần tử đã hết dùng (mờ xong, bài hỏng, dừng): dừng rồi huỷ - nhả bộ giải mã và kết nối tải bài.
void MusicBed::release(const VoiceP &audio) {
    if (audio->released)
        return;
    pause(audio);
    audio->released = true;
    if (audio->out) {
        audio->out->disconnect(this);
        audio->out->stop();
        audio->out->deleteLater();
        audio->out = nullptr;
    }
}

void MusicBed::emitActive() {
    const QString link = activeLink();
    if (link == m_announced)
        return;
    m_announced = link;
    emit activeChanged(link);
}

/// Âm lượng mục tiêu: gainDb của chính mốc cộng bước đang hiệu lực; không có gainDb thì mức chung.
double MusicBed::target(const MusicCue *cue) const {
    const double step = cue ? stepDbAt(*cue, m_lastTime) : 0;
    const double gain = cue && cue->gainDb ? std::pow(10.0, std::min(0.0, *cue->gainDb + step) / 20) : m_gain * std::pow(10.0, step / 20);
    return std::min(1.0, gain * m_userVolume);
}

double MusicBed::target() const {
    return target(m_current ? &m_current->cue : nullptr);
}

/// Mức đích đổi (sang bước mới): trượt dần STEP_RAMP_SECONDS; vừa tua thì vào thẳng mức mới (trừ lúc bài đang mờ vào).
void MusicBed::retarget(bool seeked) {
    if (!m_current)
        return;
    Playing &playing = *m_current;
    const double goal = target();
    if (std::abs(goal - playing.goal) < 1e-6)
        return;
    playing.goal = goal;
    if (playing.entering) {
        playing.perTick = (goal * STEP_MS) / 1000 / playing.fadeSeconds;
    } else if (seeked) {
        setVolumeOf(playing.audio, goal);
        return;
    } else {
        playing.perTick = (std::abs(goal - playing.audio->volume) * STEP_MS) / 1000 / STEP_RAMP_SECONDS;
    }
    startFade();
}

/// Mốc `tail`: ở vòng cuối bài thôi lặp và kết tự nhiên ở E; bài đã kết trước hết mốc mà mốc kế bắt đầu đúng ở đó thì mốc kế vào ngay.
void MusicBed::finishTail(double seconds) {
    if (!m_current || !m_current->cue.tail)
        return;
    Playing &playing = *m_current;
    const LoopBounds bounds = loopBounds(playing.cue, duration(playing.audio));
    if (!playing.final && duration(playing.audio) > 0 && finalLoop(playing.cue, seconds, currentTime(playing.audio), bounds)) {
        playing.final = true;
        setLoopOf(playing.audio, false); // bài quá ngắn lặp thường: chơi nốt vòng này rồi thôi
    }
    const bool done = playing.final ? finished(bounds, currentTime(playing.audio), playing.audio->ended) : playing.audio->ended;
    if (!done || seconds >= playing.cue.end)
        return;
    const MusicCue was = playing.cue;
    const std::optional<MusicCue> next = playableAt(was.end);
    if (!next || next->start != was.end || next->link == was.link)
        return;
    switchTo(next, seconds);
    if (m_current && m_current->cue.key == next->key && m_current->cue.start == next->start)
        m_current->early = true;
}

/// Lặp mờ chéo: phần tử đang kêu tới loopEnd - X thì một phần tử MỚI của chính bài vào từ loopStart, mờ chéo LOOP_CROSSFADE_SECONDS.
void MusicBed::crossLoop(double seconds, bool fromTimer) {
    cancelLoopTicket();
    if (!m_current || m_current->final || seconds >= m_current->cue.end || !(duration(m_current->audio) > 0)) {
        cancelStandby();
        return;
    }
    Playing &playing = *m_current;
    const LoopBounds bounds = loopBounds(playing.cue, duration(playing.audio));
    const double at = currentTime(playing.audio);
    if (!loopDue(bounds, at) && !(fromTimer && playing.audio->wantPlay && at >= bounds.loopEnd - LOOP_CROSSFADE_SECONDS - LOOP_TIMER_SLACK_SECONDS)) {
        if (bounds.crossfade && bounds.loopEnd - LOOP_CROSSFADE_SECONDS - at < LOOP_STANDBY_SECONDS)
            prepareStandby(playing, bounds);
        else
            cancelStandby();
        // Vé nổ mà chưa tới hạn (bài đứng chờ tải): không hẹn lại, lần đồng bộ kế hẹn tiếp.
        if (!fromTimer && playing.audio->wantPlay)
            armLoopTicket(playing.audio, loopHandoffDelay(bounds, at, SYNC_TICK_SECONDS));
        return;
    }
    const VoiceP old = playing.audio;
    old->fadeStep = (std::max(old->volume, 0.01) * STEP_MS) / 1000 / LOOP_CROSSFADE_SECONDS;
    m_fading.append(old);
    std::optional<Standby> ready;
    if (m_standby && m_standby->owner == old)
        ready = m_standby;
    else
        cancelStandby();
    m_standby.reset(); // phần tử sẵn (nếu có) thành bản mới: từ đây là của m_current
    const bool early = playing.early;
    const MusicCue cue = playing.cue;
    m_current = open(cue, seconds, LOOP_CROSSFADE_SECONDS, loopStartAt(bounds, at), Handoff{old, bounds}, ready);
    m_current->early = early;
    startFade();
}

/// Tạo SẴN phần tử lặp của vòng hiện tại (một lần mỗi vòng) - đứng ở loopStart, âm lượng 0, chưa phát.
void MusicBed::prepareStandby(const Playing &playing, const LoopBounds &bounds) {
    if (m_standby && m_standby->owner == playing.audio)
        return;
    cancelStandby();
    auto place = std::make_shared<double>(bounds.loopStart);
    const VoiceP audio = spawn(playing.cue, m_lastTime, place, Handoff{playing.audio, bounds});
    m_standby = Standby{audio, playing.audio, place};
}

void MusicBed::cancelStandby() {
    if (!m_standby)
        return;
    const VoiceP audio = m_standby->audio;
    m_standby.reset();
    release(audio);
}

void MusicBed::cancelLoopTicket() {
    m_loopTicket.stop();
    m_ticketAudio.reset();
}

void MusicBed::armLoopTicket(const VoiceP &audio, std::optional<double> delay) {
    if (!delay)
        return;
    m_ticketAudio = audio;
    m_loopTicket.start(int(std::lround(*delay * 1000)));
}

/// Sửa pha một lần cho bản lặp mới khi nó vừa có tiếng (bù độ trễ mở bộ phát): bản mới còn gần như câm nên cú dời không nghe thấy.
void MusicBed::fixHandoffDrift(const VoiceP &audio, const MusicCue &cue, const Handoff &handoff) {
    const VoiceP &old = handoff.old;
    if (audio->released || old->released || !old->wantPlay || !m_fading.contains(old))
        return;
    if (audio->volume > LOOP_DRIFT_QUIET * target(&cue))
        return;
    const double drift = loopDrift(handoff.bounds, currentTime(old), currentTime(audio));
    if (std::abs(drift) > LOOP_DRIFT_TOLERANCE_SECONDS)
        setCurrentTime(audio, std::max(0.0, currentTime(audio) + drift));
}

void MusicBed::align(const VoiceP &audio, const MusicCue &cue, double seconds) {
    if (duration(audio) > 0)
        setCurrentTime(audio, alignedPosition(cue, seconds, loopBounds(cue, duration(audio))));
}

/// Một phần tử của mốc `cue`, chưa phát, âm lượng 0, đang nạp. `place` (phần tử lặp): vào đúng chỗ ấy, đổi được tới lúc nạp xong.
MusicBed::VoiceP MusicBed::spawn(const MusicCue &cue, double seconds, std::shared_ptr<double> place, std::optional<Handoff> handoff) {
    auto audio = std::make_shared<Voice>();
    audio->link = cue.link;
    audio->out = m_make();
    audio->out->setParent(this);
    setLoopOf(audio, !loopBounds(cue, std::nan("")).crossfade);
    setVolumeOf(audio, 0);
    // Sự kiện của <audio> luôn tới SAU lời gọi đang chạy: nối kiểu hàng đợi (bộ phát giả báo ngay trong load()/play()).
    std::weak_ptr<Voice> weak = audio;
    connect(audio->out, &AudioOut::durationChanged, this, [this, weak, cue, seconds, place](double length) {
        const VoiceP audio = weak.lock();
        if (!audio || audio->released || audio->loaded || !(length > 0))
            return;
        audio->loaded = true;
        m_failed.remove(cue.link);
        const bool sounding = m_current && m_current->audio == audio;
        setLoopOf(audio, !loopBounds(cue, duration(audio)).crossfade && !(sounding && m_current->final));
        // Bài tải xong sau khi giọng đã chạy tiếp (hay vừa tua): theo giây mới nhất, không phải giây lúc tạo bài.
        if (!place)
            align(audio, cue, sounding ? m_lastTime : seconds);
        else if (std::abs(currentTime(audio) - *place) > 0.25)
            setCurrentTime(audio, *place);
        emit loadResult(cue.link, true);
    }, Qt::QueuedConnection);
    connect(audio->out, &AudioOut::failed, this, [this, weak, cue](const QString &) {
        const VoiceP audio = weak.lock();
        if (!audio || audio->released)
            return;
        // Phần tử tạo sẵn hỏng trước khi dùng: bỏ nó, tới hạn tạo cái mới - không tính là bài hỏng.
        if (m_standby && m_standby->audio == audio)
            cancelStandby();
        else
            drop(cue, audio);
    }, Qt::QueuedConnection);
    connect(audio->out, &AudioOut::playingChanged, this, [this, weak, cue, handoff](bool on) {
        const VoiceP audio = weak.lock();
        if (!on || !audio || audio->released || audio->sounded)
            return;
        audio->sounded = true;
        if (handoff)
            fixHandoffDrift(audio, cue, *handoff);
        if (m_current && m_current->audio == audio)
            startFade(); // phần tử đã chờ tiếng: bây giờ mới mờ vào
    }, Qt::QueuedConnection);
    connect(audio->out, &AudioOut::buffering, this, [weak](bool on) {
        if (const VoiceP audio = weak.lock())
            audio->waiting = on;
    }, Qt::QueuedConnection);
    connect(audio->out, &AudioOut::ended, this, [weak] {
        if (const VoiceP audio = weak.lock()) {
            audio->ended = true;
            audio->wantPlay = false;
        }
    }, Qt::QueuedConnection);
    audio->out->load(m_url(cue.src), place ? *place : 0);
    audio->out->preload();
    return audio;
}

/// Một phần tử mới của mốc `cue` (hay `ready`: phần tử lặp đã tạo sẵn, vào muộn thì đặt lại tới `startAt`), mờ vào trong `fadeSeconds` giây.
MusicBed::Playing MusicBed::open(const MusicCue &cue, double seconds, double fadeSeconds, std::optional<double> startAt, std::optional<Handoff> handoff,
                                 std::optional<Standby> ready) {
    VoiceP audio;
    if (ready && startAt) {
        audio = ready->audio;
        *ready->place = *startAt;
        if (std::abs(currentTime(audio) - *startAt) > 0.001)
            setCurrentTime(audio, *startAt);
    } else {
        audio = spawn(cue, seconds, startAt ? std::make_shared<double>(*startAt) : nullptr, handoff);
    }
    const double goal = target(&cue);
    if (m_playing)
        play(audio);
    Playing playing;
    playing.cue = cue;
    playing.audio = audio;
    playing.goal = goal;
    playing.perTick = (goal * STEP_MS) / 1000 / fadeSeconds;
    playing.entering = true;
    playing.fadeSeconds = fadeSeconds;
    return playing;
}

void MusicBed::switchTo(std::optional<MusicCue> cue, double seconds, bool seeked) {
    warmNext(cue ? &*cue : nullptr, seconds);
    const bool sameSong = m_current && cue && m_current->cue.link == cue->link;
    if (seeked || !sameSong) {
        cancelLoopTicket();
        cancelStandby();
    }
    if (sameSong) {
        // Cùng bài (đoạn kề): chơi tiếp, không bắt đầu lại. Vừa tua: dời nhạc theo chỗ mới.
        m_current->cue = *cue;
        if (seeked) {
            m_current->final = false;
            setLoopOf(m_current->audio, !loopBounds(*cue, duration(m_current->audio)).crossfade);
            align(m_current->audio, *cue, seconds);
        }
        return;
    }
    const double fadeSeconds = cue && cue->sibling ? SIBLING_FADE_SECONDS : FADE_SECONDS;
    if (m_current) {
        const VoiceP old = m_current->audio;
        double fade = fadeSeconds;
        if (cue && cue->sibling) {
            setLoopOf(old, false); // bài cũ vừa hết vòng: chơi nốt rồi thôi, không quay lại đầu bài
            if (duration(old) > 0)
                fade = siblingFadeSeconds(loopBounds(m_current->cue, duration(old)), currentTime(old));
        }
        old->fadeStep = (std::max(old->volume, 0.01) * STEP_MS) / 1000 / fade;
        m_fading.append(old);
        m_current.reset();
    }
    if (cue)
        m_current = open(*cue, seconds, fadeSeconds);
    emitActive();
    startFade();
}

void MusicBed::tick(int count) {
    for (int i = 0; i < count && m_timer.isActive(); ++i)
        fadeTick();
}

void MusicBed::startFade() {
    if (!m_timer.isActive())
        m_timer.start();
}

void MusicBed::fadeTick() {
    bool busy = false;
    if (m_current) {
        Playing &playing = *m_current;
        const VoiceP &audio = playing.audio;
        const double goal = playing.goal;
        const double move = std::max(playing.perTick, 1e-5);
        if (audio->volume < goal && awaitingSound(playing)) {
            // Bài chưa có tiếng: giữ 0. Đang chạy mà chưa đủ dữ liệu thì canh tiếp; còn tạm dừng thì chờ tiếng gọi lại.
            if (audio->wantPlay)
                busy = true;
        } else {
            if (audio->volume < goal)
                setVolumeOf(audio, std::min(goal, audio->volume + move));
            else if (audio->volume > goal)
                setVolumeOf(audio, std::max(goal, audio->volume - move));
            if (std::abs(audio->volume - goal) < 1e-4)
                playing.entering = false;
            else
                busy = true;
        }
    }
    QVector<VoiceP> still;
    for (const VoiceP &audio : std::as_const(m_fading)) {
        const double step = audio->fadeStep >= 0 ? audio->fadeStep : (0.1 * STEP_MS) / 1000 / FADE_SECONDS;
        setVolumeOf(audio, std::max(0.0, audio->volume - step));
        if (audio->volume <= 0.001) {
            release(audio);
            continue;
        }
        busy = true;
        still.append(audio);
    }
    m_fading = still;
    if (!busy)
        m_timer.stop();
}
