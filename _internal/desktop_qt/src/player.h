// Bộ phát: MỘT đối tượng giữ cuốn đang nạp, hàng chương, chỗ nghe, tốc độ riêng từng cuốn, hẹn giờ, tự sang chương, dấu chương đã nghe xong và việc
// lưu chỗ nghe. Chuyển từ ui/src/listen/player.tsx (+ progressOutbox.ts, sleep.ts, model.ts); QML không có logic nào, chỉ đọc trạng thái và gọi lệnh.
//
// Trạng thái chia hai như PlayerRepo trên điện thoại:
//   - ẢNH CHỤP: các thuộc tính Q_PROPERTY dưới đây, mỗi cái chỉ phát NOTIFY khi giá trị THẬT SỰ đổi (sách, chương, đang phát, tốc độ, hẹn giờ, lỗi);
//   - ĐỒNG HỒ: `clock` (PlayerClock) giữ vị trí + thời gian hẹn giờ còn lại, đổi theo nhịp. CHỈ thanh tua và nhãn giờ đọc nó.
// Thử được không cần thiết bị âm thanh hay host: AudioOut và PlayerNet đưa vào qua hàm dựng.
#pragma once

#include "audioout.h"
#include "chaptersmodel.h"
#include "playerlogic.h"
#include "playernet.h"
#include "progressoutbox.h"

#include <QJsonArray>
#include <QJSEngine>
#include <QList>
#include <QObject>
#include <QQmlEngine>
#include <QTimer>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>

#include <functional>
#include <memory>
#include <optional>

class Player;

/// Vị trí + hẹn giờ còn lại. Chỉ chạy nhịp khi có người đang nhìn (`retain`) và đang phát; dừng thì cập nhật một lần ở mỗi sự kiện.
class PlayerClock : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("Có sẵn trong Player.clock")
    Q_PROPERTY(double position READ position NOTIFY positionChanged)
    Q_PROPERTY(double duration READ duration NOTIFY durationChanged)
    /// Giây hẹn giờ còn lại; -1 khi không hẹn giờ phút ("hết chương" đếm theo chương).
    Q_PROPERTY(double sleepLeft READ sleepLeft NOTIFY sleepLeftChanged)
    Q_PROPERTY(quint64 ticks READ ticks CONSTANT)
public:
    explicit PlayerClock(Player *owner);
    double position() const { return m_position; }
    double duration() const { return m_duration; }
    double sleepLeft() const { return m_sleepLeft; }
    /// Người nhìn (thanh tua, nhãn giờ) báo mình đang hiện / không còn hiện: không ai nhìn thì không có nhịp nào.
    Q_INVOKABLE void retain();
    Q_INVOKABLE void release();
    int watchers() const { return m_watchers; }
    /// Số lần đồng hồ đã cập nhật (đo: bench.cpp chứng minh chỉ đồng hồ đổi theo nhịp).
    quint64 ticks() const { return m_ticks; }

    void set(double position, double duration);
    void setSleepLeft(double seconds);
    /// Đọc lại từ bộ phát; phát tín hiệu cho cái nào thật sự đổi.
    void refresh();
    /// Bật / tắt nhịp theo (có người nhìn) và (đang phát).
    void restart();
    void setSuspended(bool suspended);

signals:
    void positionChanged();
    void durationChanged();
    void sleepLeftChanged();

private:
    Player *m_owner;
    QTimer m_timer;
    double m_position = 0;
    double m_duration = 0;
    double m_sleepLeft = -1;
    int m_watchers = 0;
    quint64 m_ticks = 0;
    bool m_suspended = false;
};

class Player : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(int skipSeconds READ skipSeconds CONSTANT)
    // ---- ảnh chụp ----
    Q_PROPERTY(bool loaded READ loaded NOTIFY loadedChanged)
    Q_PROPERTY(QString bookId READ bookId NOTIFY bookChanged)
    Q_PROPERTY(QString bookTitle READ bookTitle NOTIFY bookChanged)
    Q_PROPERTY(QString narrator READ narrator NOTIFY bookChanged)
    Q_PROPERTY(QString coverKey READ coverKey NOTIFY bookChanged)
    Q_PROPERTY(int chapterId READ chapterId NOTIFY chapterChanged)
    Q_PROPERTY(int chapterNumber READ chapterNumber NOTIFY chapterChanged)
    Q_PROPERTY(QString chapterTitle READ chapterTitle NOTIFY chapterChanged)
    Q_PROPERTY(QString chapterSubtitle READ chapterSubtitle NOTIFY chapterChanged)
    Q_PROPERTY(bool playing READ playing NOTIFY playingChanged)
    Q_PROPERTY(bool buffering READ buffering NOTIFY bufferingChanged)
    Q_PROPERTY(bool speaking READ speaking NOTIFY chapterChanged)
    Q_PROPERTY(QString voiceId READ voiceId NOTIFY bookChanged)
    Q_PROPERTY(QString purpose READ purpose NOTIFY bookChanged)
    Q_PROPERTY(double rate READ rate NOTIFY rateChanged)
    Q_PROPERTY(double volume READ volume NOTIFY volumeChanged)       // 0..1 của giọng (phím M tắt / bật tiếng)
    Q_PROPERTY(QString sleepKind READ sleepKind NOTIFY sleepChanged)    // "off" | "minutes" | "chapter"
    Q_PROPERTY(int sleepMinutes READ sleepMinutes NOTIFY sleepChanged)
    Q_PROPERTY(int lastSleepMinutes READ lastSleepMinutes NOTIFY sleepChanged)
    Q_PROPERTY(QString sleepStoppedText READ sleepStoppedText NOTIFY sleepChanged) // "23:42" khi hẹn giờ vừa tắt tiếng, không thì ""
    Q_PROPERTY(bool fading READ fading NOTIFY fadingChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(QString notice READ notice NOTIFY noticeChanged)
    Q_PROPERTY(QString noticeAction READ noticeAction NOTIFY noticeChanged)   // nhãn nút của lời nhắn ("Quay lại", ...) hay ""
    Q_PROPERTY(QString atEnd READ atEnd NOTIFY atEndChanged)            // "none" | "caughtUp" | "finished"
    Q_PROPERTY(bool canPrevious READ canPrevious NOTIFY chapterChanged)
    Q_PROPERTY(bool canNext READ canNext NOTIFY chapterChanged)
    Q_PROPERTY(bool canGoBack READ canGoBack NOTIFY historyChanged)
    Q_PROPERTY(ChaptersModel *chapters READ chapters CONSTANT)
    Q_PROPERTY(PlayerClock *clock READ clock CONSTANT)
    Q_PROPERTY(QVariantList speeds READ speedsList CONSTANT)
    Q_PROPERTY(QVariantList sleepChoices READ sleepChoicesList CONSTANT)
    /// Đếm số lần ảnh chụp đổi (đo): đứng yên suốt lúc phát liền mạch.
    Q_PROPERTY(quint64 snapshotChanges READ snapshotChanges CONSTANT)

public:
    /// `out`, `net` do người gọi giữ (Player không sở hữu). `nowMs` đồng hồ tường (ms từ 1970), thay được khi thử.
    Player(AudioOut *out, PlayerNet *net, const QString &outboxPath, QObject *parent, std::function<qint64()> nowMs = {});
    ~Player() override;

    static Player *instance();
    static Player *create(QQmlEngine *, QJSEngine *);
    /// Gắn bản dùng chung cho QML (main.cpp dựng Player thật, create() trả lại đúng nó).
    static void setInstance(Player *player);
    int skipSeconds() const { return int(PlayerLogic::kSkipSeconds); }

    bool loaded() const { return m_loaded; }
    QString bookId() const { return m_book.id; }
    QString bookTitle() const { return m_book.title; }
    QString narrator() const { return m_book.narrator; }
    QString coverKey() const;
    int chapterId() const { return m_chapterId; }
    int chapterNumber() const;
    QString chapterTitle() const;
    QString chapterSubtitle() const;
    bool playing() const { return m_playing; }
    bool buffering() const { return m_buffering; }
    bool speaking() const { const auto *item = chapter(m_chapterId); return item && item->textOnly; }
    QString voiceId() const { return m_book.voice.isEmpty() ? m_defaultVoice : m_book.voice; }
    QString purpose() const { return m_purpose; }
    bool hasDefaultVoice() const { return !m_defaultVoice.isEmpty(); }
    Q_INVOKABLE void chooseVoice(const QString &voice, bool resumeAfter = false);
    Q_INVOKABLE void review(const QString &bookId, int chapterId);
    double rate() const { return m_rate; }
    double volume() const { return m_volume; }
    QString sleepKind() const;
    int sleepMinutes() const { return m_sleep.minutes; }
    int lastSleepMinutes() const { return m_lastSleepMinutes; }
    QString sleepStoppedText() const;
    bool fading() const { return m_fading; }
    QString error() const { return m_error; }
    QString notice() const { return m_notice; }
    QString noticeAction() const { return m_noticeAction; }
    QString atEnd() const { return m_atEnd; }
    bool canPrevious() const;
    bool canNext() const;
    bool canGoBack() const { return !m_history.isEmpty(); }
    ChaptersModel *chapters() { return &m_chapters; }
    PlayerNet *net() const { return m_net; }
    PlayerClock *clock() { return &m_clock; }
    void setUiActive(bool active) { m_uiActive = active; m_clock.setSuspended(!active); updateTicker(); }
    QVariantList speedsList() const;
    QVariantList sleepChoicesList() const;
    quint64 snapshotChanges() const { return m_snapshotChanges; }

    // ---- lệnh ----
    /// Nạp sách (hỏi máy chủ). `chapterId` < 0: ở chỗ nghe dở (resumePoint). `autoplay` false = đứng chờ (mở app: thanh có sẵn cuốn đang nghe dở).
    Q_INVOKABLE void open(const QString &bookId, int chapterId = -1, double at = -1, bool autoplay = true);
    /// Nút "Nghe" / "Nghe tiếp" ở trang sách: cuốn đang nạp thì phát tiếp, không thì nạp rồi phát.
    Q_INVOKABLE void playBook(const QString &bookId);
    /// Hàng chương ở trang sách: phát chương ấy (tiếp chỗ đã nghe dở của nó).
    Q_INVOKABLE void playChapter(const QString &bookId, int chapterId);
    Q_INVOKABLE void toggle();
    Q_INVOKABLE void resume();
    Q_INVOKABLE void pause();
    Q_INVOKABLE void seek(double seconds);
    Q_INVOKABLE void skip(double delta);
    Q_INVOKABLE void next();
    Q_INVOKABLE void previous();
    Q_INVOKABLE void jumpTo(int chapterId, double at = 0, const QString &note = QString());
    Q_INVOKABLE void goBack();
    Q_INVOKABLE void restart();
    Q_INVOKABLE void setRate(double rate);
    Q_INVOKABLE void stepRate(int direction);
    Q_INVOKABLE void setVolume(double volume);
    /// Phím M (player.tsx): đang có tiếng thì nhớ mức rồi tắt; đang tắt thì về mức đã nhớ (chưa nhớ gì: 0,9).
    Q_INVOKABLE void toggleMute();
    Q_INVOKABLE void setSleep(const QString &kind, int minutes = 0);
    Q_INVOKABLE void extendSleep(int minutes = 0);
    Q_INVOKABLE void configure(const QVariantMap &preferences);
    Q_INVOKABLE void retry();
    Q_INVOKABLE void dismissError();
    Q_INVOKABLE void dismissNotice();
    /// Nút trong lời nhắn đang hiện ("Quay lại", "Nghe lại từ đầu", "Vẫn đang nghe").
    Q_INVOKABLE void runNoticeAction();
    /// Đóng sách: lưu chỗ nghe, nhả bộ phát (thanh phát biến mất).
    Q_INVOKABLE void close();
    /// Tắt app: lưu chỗ nghe, gửi nốt hộp thư đi (chờ tối đa `waitMs`).
    void shutdown(int waitMs = 1500);

    /// Giờ cho người nghe: 3:07 / 1:02:05 và "45 phút" / "9 giờ 12 phút" (một công thức với bản web, playerlogic.h).
    Q_INVOKABLE QString clockText(double seconds) const { return PlayerLogic::formatClock(seconds); }
    Q_INVOKABLE QString lengthText(double seconds) const { return PlayerLogic::formatLength(seconds); }

    /// Cuốn nghe dở gần nhất trong thư viện (mở app): nạp ở trạng thái dừng. `library` = JSON GET /api/listen/library.
    void restoreLast(const QJsonArray &library);

    /// Nhịp: hẹn giờ, lưu định kỳ, gửi lại hộp thư đi. QTimer gọi; test gọi tay với đồng hồ giả.
    void tick();

    // Cho PlayerClock, bench và test
    double position() const;
    double duration() const;
    const PlayerLogic::Book &book() const { return m_book; }
    ProgressOutbox *outbox() { return m_outbox.get(); }
    double sleepLeftSeconds() const;
    void setFreshSpotMs(int ms) { m_freshMs = ms; }
    void setDefaultRate(double rate) { m_defaultRate = rate; }
    void setSafetyStopHours(int hours) { m_safetyHours = hours; }
    void setFadeSeconds(int seconds) { m_fadeSeconds = seconds; }
    QString lastFailure() const { return m_lastFailure; }
    bool wantsPlay() const { return m_wantsPlay; }
    /// Âm lượng đang ra loa của giọng (kể cả lúc hẹn giờ nhỏ dần): nhạc nền nhân theo (player.tsx: volume * sleepGain).
    double outputVolume() const { return m_volume * (m_fading ? m_gain : 1.0); }
    /// Lời nhắn ngắn ở thanh phát (nhạc nền: "Chưa chỉnh được nhạc nền").
    void showNotice(const QString &notice) { setNotice(notice); }
    /// Theo dõi phím / chuột của cả app: bằng chứng "còn thức" cho lưới an toàn ngủ quên, và "lắc máy" nghe thêm lúc đang nhỏ dần.
    void watchInput();

signals:
    void loadedChanged();
    void bookChanged();
    void chapterChanged();
    void playingChanged();
    void bufferingChanged();
    void rateChanged();
    void volumeChanged();
    void audioSeeked();
    void outputGainChanged();
    /// Hẹn giờ theo phút còn 30 giây (DESIGN 5.3): báo một lần; thêm giờ quá mốc thì báo lại được.
    void sleepWarning();
    void sleepChanged();
    void fadingChanged();
    void errorChanged();
    void noticeChanged();
    void atEndChanged();
    void historyChanged();
    /// Chỗ nghe vừa được máy chủ nhận (sau pause, đổi chương...): Thư viện làm mới tiến độ.
    void listeningChanged(const QString &bookId);

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;

private:
    struct Session {
        QString id;
        int revision = 0;
        int acked = 0;
        QString bookId;
        QString record;
        bool ready = false;
        bool starting = false;
        QList<std::function<void(int)>> waiting;
    };
    struct Sleep {
        enum Kind { Off, Minutes, Chapter } kind = Off;
        int minutes = 0;
        double leftMs = 0;
    };
    struct Spot {
        int chapterId = 0;
        double seconds = 0;
    };
    struct Listening {
        QString id;
        double startedAt = 0;
        Spot from;
        QString bookId;
        QString record;
        double listened = 0;
        qint64 mark = 0;
    };

    void openFor(const QString &bookId, int chapterId, double at, bool autoplay, const QString &purpose);
    void start(const PlayerLogic::Book &book, int chapterId, double at, bool autoplay, const QString &purpose);
    void adoptBook(const PlayerLogic::Book &book);
    void load(int chapterId, double at, bool autoplay);
    void resumeNow();
    void requestPlay();
    void save(bool force = false);
    void ensureSession(const std::shared_ptr<Session> &session, std::function<void(int)> then);
    void sendSpot(const ProgressSpot &spot, ProgressOutbox::Done done);
    void onAck(const ProgressSpot &spot);
    void onOutPlaying(bool playing);
    void onEnded();
    void onFailed(const QString &reason);
    void onSeeked();
    void onDuration(double seconds);
    void step(int direction);
    void tickSleep(qint64 now);
    void stopBySleep();
    void endFade();
    void applyRate(double rate);
    void remember(const Spot &from, const Spot &to, const QString &note);
    void openListening();
    void closeListening(bool leaving = false, std::optional<Spot> to = std::nullopt);
    void markPaused(bool saveNow);
    void resetSleepMark();
    void applySleepState(Sleep::Kind kind, int minutes, double leftMs);
    void setPlaying(bool playing);
    void setBuffering(bool buffering);
    void checkStall();
    void setError(const QString &error);
    void setNotice(const QString &notice, const QString &actionLabel = QString(), const QString &actionKey = QString());
    void setAtEnd(const QString &atEnd);
    void setFading(bool fading);
    void changed(); // một thay đổi ảnh chụp đã xảy ra (đếm)
    void updateTicker();
    const PlayerLogic::Chapter *chapter(int id) const;
    int rewindBy(qint64 pausedMs) const;
    std::shared_ptr<Session> newSession();

    AudioOut *m_out;
    PlayerNet *m_net;
    std::function<qint64()> m_now;
    PlayerClock m_clock;
    bool m_uiActive = true;
    ChaptersModel m_chapters;
    std::unique_ptr<ProgressOutbox> m_outbox;
    QTimer m_ticker;
    QTimer m_noticeTimer;
    QTimer m_stallTimer;           // last guard of every AudioOut (HostWait::kStallMs): buffering that never ends
    qint64 m_bufferingSince = 0;

    bool m_loaded = false;
    PlayerLogic::Book m_book;
    int m_chapterId = 0;
    bool m_playing = false;        // đã bấm phát (như sự kiện "play" của <audio>): nút chính hiện Tạm dừng
    bool m_audible = false;        // nguồn đã thật sự kêu
    bool m_buffering = false;
    bool m_wantsPlay = false;
    bool m_ended = false;
    bool m_loadingSource = false;  // đang gọi m_out->load: bỏ sự kiện dừng đồng bộ của nguồn cũ
    double m_rate = PlayerLogic::kDefaultRate;
    double m_defaultRate = PlayerLogic::kDefaultRate;
    double m_volume = 0.9;
    double m_muted = 0; // mức trước lần tắt tiếng gần nhất
    bool m_fading = false;
    QString m_error;
    QString m_notice;
    QString m_noticeAction;
    QString m_noticeKey;
    QString m_atEnd = QStringLiteral("none");
    Sleep m_sleep;
    int m_lastSleepMinutes = 30;
    qint64 m_sleepStoppedAt = 0;
    int m_fadeSeconds = PlayerLogic::kDefaultFadeSeconds;
    int m_safetyHours = 2;
    bool m_autoRewind = true;
    int m_extendMinutes = 10;
    QVariantMap m_schedule;
    QString m_scheduleOffFor;
    bool m_scheduleChecked = false;
    QString scheduleWindow() const;
    qint64 m_sleepMarkAt = 0;
    double m_sleepMarkSeconds = 0;
    bool m_sleepWarned = false;
    qint64 m_pausedAt = 0;
    qint64 m_lastAttempt = 0;
    qint64 m_lastFlush = 0;
    qint64 m_lastSaved = 0;
    qint64 m_stamp = 0;
    qint64 m_lastActivity = 0;
    std::optional<Spot> m_savedSpot;
    QList<Spot> m_history;
    std::shared_ptr<Session> m_session;
    QList<std::shared_ptr<Session>> m_sessions; // vài phiên gần nhất: bản chờ của phiên cũ vẫn bắt tay đúng phiên của nó
    QString m_trackBook;   // sách + hồ sơ của nguồn đang nạp (khác m_book trong lúc chuyển sách)
    QString m_trackRecord;
    int m_notifyRevision = 0;
    int m_postsInFlight = 0;
    double m_gain = 1;
    std::optional<Listening> m_listening;
    quint64 m_snapshotChanges = 0;
    quint64 m_intent = 0;  // mỗi lần bấm phát / dừng / nạp +1: lời đáp của lần trước không được làm gì nữa
    quint64 m_openSeq = 0;
    int m_freshMs = 1600;  // FRESH_SPOT_MS
    QString m_lastFailure;
    QString m_defaultVoice, m_purpose = QStringLiteral("listen");
};
