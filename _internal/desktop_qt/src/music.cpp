#include "music.h"

#include "musictext.h"
#include "player.h"
#include "playernet.h"

#include <QJsonArray>

#include <iterator>
#include <QUrl>

using namespace MusicLogic;

namespace {

Music *g_instance = nullptr;

/// Nhạc theo cảnh dựng nền: chương chưa xong thì máy chủ trả `pending` - hỏi lại chừng ấy lần, cách nhau chừng ấy (player.tsx).
constexpr int SCENE_POLLS = 80;
constexpr int SCENE_POLL_MS = 1500;
/// Mốc trả `unavailable` (danh mục chưa tải được) hay hỏi hỏng: hỏi lại sau quãng lùi dần, có hạn (sceneCues.ts SCENE_RETRY_MS).
constexpr int SCENE_RETRY_MS[] = {15000, 30000, 60000, 120000, 300000};
/// Giọng nhảy quá chừng này giây giữa hai nhịp = người nghe vừa tua (player.tsx).
constexpr double SEEK_JUMP_SECONDS = 3;

} // namespace

Music::Music(Player *player, PlayerNet *net, std::function<AudioOut *()> make, QObject *parent)
    : QObject(parent), m_player(player), m_net(net),
      m_bed(std::move(make), [net](const QString &src) { return net->mediaUrl(src); },
            [net](const QString &link) {
                net->request("POST", QStringLiteral("/api/music/warm?link=") + QString::fromLatin1(QUrl::toPercentEncoding(link)), {},
                             [](int, const QJsonObject &) {}, false);
            }),
      m_nextWarm(
          [this](int chapterId, NextChapterWarm::Answer done) {
              m_net->request("GET", QStringLiteral("/api/books/%1/music/chapters/%2").arg(m_bookId).arg(chapterId), {},
                             [done](int status, const QJsonObject &body) {
                                 done(status == 200 ? std::optional<MusicCues>(cuesFromJson(body)) : std::nullopt);
                             }, false);
          },
          [this](const QString &link) { m_bed.warmLink(link); }) {
    m_tick.setInterval(int(SYNC_TICK_SECONDS * 1000));
    connect(&m_tick, &QTimer::timeout, this, &Music::sync);
    m_retry.setSingleShot(true);
    connect(m_player, &Player::bookChanged, this, &Music::onBook);
    connect(m_player, &Player::chapterChanged, this, &Music::onChapter);
    connect(m_player, &Player::playingChanged, this, [this] {
        updateTicking();
        sync();
    });
    connect(&m_bed, &MusicBed::activeChanged, this, [this](const QString &link) {
        updateCredit(link);
        updateBroken();
    });
    connect(&m_bed, &MusicBed::loadResult, this, &Music::updateBroken);
}

Music::~Music() {
    m_bed.stop();
}

Music *Music::instance() {
    return g_instance;
}

void Music::setInstance(Music *music) {
    g_instance = music;
}

Music *Music::create(QQmlEngine *, QJSEngine *) {
    QJSEngine::setObjectOwnership(g_instance, QJSEngine::CppOwnership);
    return g_instance;
}

QVariantList Music::levels() const {
    QVariantList list;
    for (const MusicText::Level &level : MusicText::levelOptions(m_levelDb))
        list << QVariantMap{{QStringLiteral("value"), level.value}, {QStringLiteral("name"), level.name},
                            {QStringLiteral("note"), MusicText::levelNote(level.value)}};
    return list;
}

QString Music::chapterKey() const {
    return m_player->bookId().isEmpty() ? QString() : QStringLiteral("%1:%2").arg(m_player->bookId()).arg(m_player->chapterId());
}

QString Music::musicPath() const {
    return QStringLiteral("/api/books/%1/music").arg(m_bookId);
}

void Music::onBook() {
    if (m_player->bookId() == m_bookId)
        return;
    m_bookId = m_player->bookId();
    const int asked = ++m_viewGeneration;
    applyView({});
    if (!m_bookId.isEmpty()) {
        m_net->request("GET", musicPath(), {}, [this, asked](int status, const QJsonObject &body) {
            if (asked == m_viewGeneration && status == 200)
                applyView(body);
        }, false);
    }
    onChapter();
}

void Music::onChapter() {
    const QString key = chapterKey();
    if (key == m_cuesFor)
        return;
    // Sang chương khác: bỏ mốc chương cũ ngay, trước khi hỏi mốc mới - chương mới đã phát từ giây 0 thì không được mở lại bài đầu hay
    // chơi tiếp bài cuối của chương cũ trong lúc chờ (MIX_QA 3.3).
    m_cuesFor = key;
    m_retry.stop();
    ++m_generation;
    m_credits.clear();
    if (key.isEmpty()) {
        m_bed.stop();
        updateTicking();
        return;
    }
    m_bed.setCues({}, std::nullopt, 0);
    askCues(0, 0);
    updateTicking();
}

/// `misses`: số lần hỏi đã trả "chưa có" (unavailable / hỏng) - hỏi lại sau quãng lùi dần, không đợi tới chương sau.
void Music::askCues(int attempt, int misses) {
    const int asked = m_generation;
    const QString path = QStringLiteral("/api/books/%1/music/chapters/%2").arg(m_player->bookId()).arg(m_player->chapterId());
    m_net->request("GET", path, {}, [this, asked, attempt, misses](int status, const QJsonObject &body) {
        if (asked != m_generation)
            return;
        if (status != 200) {
            m_credits.clear();
            m_bed.setCues({}, -20);
            askAgain(misses);
            return;
        }
        const MusicCues result = cuesFromJson(body);
        m_credits = result.credits;
        if (result.pending && attempt < SCENE_POLLS) {
            m_retry.disconnect(this);
            connect(&m_retry, &QTimer::timeout, this, [this, attempt, misses] { askCues(attempt + 1, misses); });
            m_retry.start(SCENE_POLL_MS);
            return;
        }
        if (!result.unavailable.isEmpty())
            askAgain(misses);
        m_bed.setCues(result.cues, result.levelDb);
        updateCredit(m_bed.activeLink());
        updateBroken();
        sync();
    }, false);
}

void Music::askAgain(int misses) {
    if (misses >= int(std::size(SCENE_RETRY_MS)))
        return;
    m_retry.disconnect(this);
    connect(&m_retry, &QTimer::timeout, this, [this, misses] { askCues(0, misses + 1); });
    m_retry.start(SCENE_RETRY_MS[misses]);
}

/// Màn nhạc của cuốn dưới một hình (EditBook.tsx musicEditView): sách đóng gói giữ nguyên, dự án Studio đọc `plan` / `overrides`.
void Music::applyView(const QJsonObject &raw) {
    if (raw.contains(QLatin1String("hasMusic"))) {
        m_project = raw.value(QLatin1String("project")).toBool();
        m_hasMusic = raw.value(QLatin1String("hasMusic")).toBool();
        m_enabled = raw.value(QLatin1String("enabled")).toBool();
        m_levelDb = raw.value(QLatin1String("levelDb")).toDouble(-20);
    } else {
        const QJsonObject plan = raw.value(QLatin1String("plan")).toObject();
        const QJsonObject overrides = raw.value(QLatin1String("overrides")).toObject();
        m_project = !raw.isEmpty();
        m_hasMusic = !plan.value(QLatin1String("scenes")).toArray().isEmpty();
        m_enabled = overrides.value(QLatin1String("enabled")).toBool(true);
        m_levelDb = overrides.contains(QLatin1String("levelDb")) ? overrides.value(QLatin1String("levelDb")).toDouble()
                                                                 : plan.value(QLatin1String("levelDb")).toDouble(-20);
    }
    m_problem = raw.value(QLatin1String("error")).toString();
    emit viewChanged();
}

void Music::setEnabled(bool enabled) {
    change({{QStringLiteral("enabled"), enabled}});
}

void Music::setLevel(double levelDb) {
    change({{QStringLiteral("levelDb"), levelDb}});
}

/// Một lệnh PUT (chung với hộp "Sửa sách"): xong thì hỏi lại mốc của chương đang nghe - nhạc theo lựa chọn mới ngay.
void Music::change(const QJsonObject &body) {
    if (m_bookId.isEmpty() || m_busy)
        return;
    m_busy = true;
    emit busyChanged();
    const int asked = m_viewGeneration;
    m_net->request("PUT", musicPath(), body, [this, asked](int status, const QJsonObject &next) {
        if (asked != m_viewGeneration)
            return;
        m_busy = false;
        emit busyChanged();
        if (status != 200) {
            m_player->showNotice(QStringLiteral("Chưa chỉnh được nhạc nền"));
            return;
        }
        applyView(next);
        if (!m_cuesFor.isEmpty()) {
            m_retry.stop();
            ++m_generation;
            askCues(0, 0);
        }
    });
}

void Music::sync() {
    const QString key = chapterKey();
    if (key.isEmpty() || key != m_cuesFor)
        return; // mốc trong bed còn của chương cũ
    const double now = m_player->position();
    const bool seeked = std::abs(now - m_last) > SEEK_JUMP_SECONDS;
    const double volume = m_player->outputVolume();
    if (volume != m_volume) {
        m_volume = volume;
        m_bed.setVolume(volume);
    }
    m_bed.sync(now, m_player->playing(), seeked);
    const int next = PlayerLogic::availableAfter(m_player->book().chapters, m_player->chapterId(), 1);
    m_nextWarm.update(key, next >= 0 ? std::optional<int>(next) : std::nullopt, m_player->duration() - now);
    m_last = now;
}

void Music::updateTicking() {
    if (m_player->playing() && !m_cuesFor.isEmpty())
        m_tick.start();
    else
        m_tick.stop();
}

void Music::updateBroken() {
    const bool broken = m_bed.failing();
    if (broken == m_broken)
        return;
    m_broken = broken;
    emit brokenChanged();
}

void Music::updateCredit(const QString &link) {
    QVariantMap credit;
    const auto found = m_credits.constFind(link);
    if (!link.isEmpty() && found != m_credits.constEnd()) {
        const MusicCredit &c = *found;
        QStringList label;
        for (const QString &part : {c.title, c.creator})
            if (!part.isEmpty())
                label << part;
        if (!label.isEmpty()) {
            credit = {{QStringLiteral("label"), label.join(QStringLiteral(" · "))},
                      {QStringLiteral("text"), MusicText::creditText(c)},
                      {QStringLiteral("license"), c.license.isEmpty() ? QString() : MusicText::licenseLabel(c.license, c.licenseUrl)},
                      {QStringLiteral("licenseUrl"), c.licenseUrl},
                      {QStringLiteral("modified"), MusicText::needsModifiedNote(c.license)},
                      {QStringLiteral("modifiedNote"), MusicText::modifiedNote()},
                      {QStringLiteral("landing"), c.landing}};
        }
    }
    if (credit == m_credit)
        return;
    m_credit = credit;
    emit creditChanged();
}
