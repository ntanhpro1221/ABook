// Lớp nhạc nền của bộ phát: một (hai, khi chuyển cảnh hay lặp mờ chéo) AudioOut chạy song song với giọng đọc, theo các MỐC nhạc của
// chương. Chép đúng lớp MusicBed của ui/src/listen/musicBed.ts (bản web máy tính) - cùng quy tắc mờ vào / mờ ra, bước âm lượng, lặp
// mờ chéo, nối bài anh em, mốc `tail`, bài hỏng thử lại sau, tải sẵn bài kế. Phép tính thuần ở musiclogic.h.
#pragma once

#include "musiclogic.h"

#include <QHash>
#include <QObject>
#include <QSet>
#include <QTimer>
#include <QUrl>

#include <functional>
#include <memory>
#include <optional>

class AudioOut;

/// Tải sẵn bài mốc đầu của chương kế khi chương này còn <= NEXT_CHAPTER_WARM_SECONDS (musicBed.ts NextChapterWarm): chương mới mở bằng bài
/// đã có trong bộ đệm máy chủ.
class NextChapterWarm {
public:
    /// `ask`: hỏi mốc của một chương, gọi `done` với lời đáp (nullopt = hỏi hỏng). `warm`: xin máy chủ tải sẵn một bài.
    using Answer = std::function<void(const std::optional<MusicLogic::MusicCues> &)>;
    NextChapterWarm(std::function<void(int chapterId, Answer done)> ask, std::function<void(const QString &)> warm, std::function<qint64()> now = {});

    /// Gọi mỗi nhịp thời gian. `key`: chương đang nghe (cuốn:chương); `next`: mã chương kế (nullopt = hết cuốn); `remaining`: giây còn
    /// lại của chương, <= 0 khi chưa biết.
    void update(const QString &key, std::optional<int> next, double remaining);

private:
    std::function<void(int, Answer)> m_ask;
    std::function<void(const QString &)> m_warm;
    std::function<qint64()> m_now;
    QSet<QString> m_done;
    QString m_asking;
    QHash<QString, qint64> m_retryAt;
};

class MusicBed : public QObject {
    Q_OBJECT
public:
    /// `make`: một AudioOut mới (bed làm chủ, huỷ khi xong). `url`: địa chỉ phát của `src` của mốc. `warm`: xin máy chủ tải sẵn một bài
    /// (POST /api/music/warm); rỗng thì không tải sẵn. `now`: đồng hồ ms (bộ thử thay được).
    MusicBed(std::function<AudioOut *()> make, std::function<QUrl(const QString &)> url, std::function<void(const QString &)> warm = {},
             std::function<qint64()> now = {}, QObject *parent = nullptr);
    ~MusicBed() override;

    /// Mốc mới (`levelDb` trống = giữ mức chung cũ). `seconds`: chỗ đang tới (trống = lần đồng bộ cuối).
    void setCues(const QVector<MusicLogic::MusicCue> &cues, std::optional<double> levelDb = std::nullopt, std::optional<double> seconds = std::nullopt);
    void setVolume(double volume);
    /// Gọi mỗi khi thời gian giọng đọc đổi (`seeked` = người nghe vừa tua).
    void sync(double seconds, bool playing, bool seeked = false);
    void stop();
    /// Xin máy chủ tải sẵn bài `link` (một lần mỗi phiên). Chỉ bài danh mục (https).
    void warmLink(const QString &link);

    /// Có bài của chương này đang bị bỏ vì không phát được (đoạn ấy im lặng, chờ thử lại).
    bool failing() const;
    /// Bài đang phát ("" = im lặng).
    QString activeLink() const;

    /// Bộ thử: số phần tử còn sống (đang kêu + đang mờ đi + tạo sẵn).
    int voices() const;
    /// Bộ thử: chạy ngay `count` nhịp mờ (STEP_MS mỗi nhịp) thay cho chờ đồng hồ.
    void tick(int count);

signals:
    /// Bài đang phát đổi (kể cả thành im lặng = "").
    void activeChanged(const QString &link);
    /// Một bài tải xong (`ok`) hay hỏng.
    void loadResult(const QString &link, bool ok);

private:
    struct Voice;
    using VoiceP = std::shared_ptr<Voice>;
    struct Handoff {
        VoiceP old;
        MusicLogic::LoopBounds bounds;
    };
    struct Playing {
        MusicLogic::MusicCue cue;
        VoiceP audio;
        double goal = 0;
        double perTick = 0;
        bool entering = true;
        double fadeSeconds = MusicLogic::FADE_SECONDS;
        bool early = false;
        bool final = false;
    };
    struct Standby {
        VoiceP audio;
        VoiceP owner;
        std::shared_ptr<double> place;
    };

    void warmNext(const MusicLogic::MusicCue *sounding, double seconds);
    bool awaitingSound(const Playing &playing) const;
    std::optional<MusicLogic::MusicCue> playableAt(double seconds);
    void drop(const MusicLogic::MusicCue &cue, const VoiceP &audio);
    void release(const VoiceP &audio);
    void emitActive();
    double target(const MusicLogic::MusicCue *cue) const;
    double target() const;
    void retarget(bool seeked);
    void finishTail(double seconds);
    void crossLoop(double seconds, bool fromTimer = false);
    void prepareStandby(const Playing &playing, const MusicLogic::LoopBounds &bounds);
    void cancelStandby();
    void cancelLoopTicket();
    void armLoopTicket(const VoiceP &audio, std::optional<double> delay);
    void fixHandoffDrift(const VoiceP &audio, const MusicLogic::MusicCue &cue, const Handoff &handoff);
    void align(const VoiceP &audio, const MusicLogic::MusicCue &cue, double seconds);
    VoiceP spawn(const MusicLogic::MusicCue &cue, double seconds, std::shared_ptr<double> place = {}, std::optional<Handoff> handoff = std::nullopt);
    Playing open(const MusicLogic::MusicCue &cue, double seconds, double fadeSeconds, std::optional<double> startAt = std::nullopt,
                 std::optional<Handoff> handoff = std::nullopt, std::optional<Standby> ready = std::nullopt);
    void switchTo(std::optional<MusicLogic::MusicCue> cue, double seconds, bool seeked = false);
    void startFade();
    void fadeTick();

    // thao tác trên một phần tử (thay cho thuộc tính của <audio>)
    static double duration(const VoiceP &audio);
    static double currentTime(const VoiceP &audio);
    static void setCurrentTime(const VoiceP &audio, double seconds);
    static void setVolumeOf(const VoiceP &audio, double volume);
    static void setLoopOf(const VoiceP &audio, bool loop);
    static void play(const VoiceP &audio);
    static void pause(const VoiceP &audio);

    std::function<AudioOut *()> m_make;
    std::function<QUrl(const QString &)> m_url;
    std::function<void(const QString &)> m_warm;
    std::function<qint64()> m_now;

    QVector<MusicLogic::MusicCue> m_cues;
    double m_gain = 0.1;
    double m_userVolume = 1;
    bool m_playing = false;
    std::optional<Playing> m_current;
    QVector<VoiceP> m_fading;
    QTimer m_timer;
    QTimer m_loopTicket;
    VoiceP m_ticketAudio;
    std::optional<Standby> m_standby;
    double m_lastTime = 0;
    QString m_announced;
    QHash<QString, qint64> m_failed;
    QSet<QString> m_warmed;
};
