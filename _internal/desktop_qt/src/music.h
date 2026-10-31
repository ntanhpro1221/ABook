// Nhạc nền của trình phát: nối Player với MusicBed và máy chủ, như phần nhạc của ui/src/listen/player.tsx + nút "Nhạc nền" của
// PlayerViews.tsx (PackagedMusicMenu, MusicCreditLine) và useBookMusic (EditBook.tsx). App Qt chỉ phát chương có audio, nên chỉ có
// nhạc người làm sách gắn (không có danh sách phát / nhạc theo cảnh của sách chữ).
//   - GET  /api/books/<id>/music                 bật/tắt, mức, có nhạc không (sách đóng gói hay dự án Studio)
//   - PUT  /api/books/<id>/music {enabled|levelDb} đổi rồi hỏi lại mốc của chương
//   - GET  /api/books/<id>/music/chapters/<n>    mốc của chương (sang chương: bỏ mốc cũ ngay ở giây 0 rồi mới hỏi)
//   - POST /api/music/warm?link=                 tải sẵn bài kế / bài mốc đầu của chương kế
#pragma once
#include <QElapsedTimer>

#include "musicbed.h"
#include "musiclogic.h"

#include <QJSEngine>
#include <QObject>
#include <QQmlEngine>
#include <QTimer>
#include <QVariantList>
#include <QVariantMap>
#include <QtQml/qqmlregistration.h>

#include <functional>

class AudioOut;
class Player;
class PlayerNet;

class Music : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    /// Cuốn đang nạp có nhạc nền người làm sách gắn: nút "Nhạc nền" chỉ hiện khi có.
    Q_PROPERTY(bool hasMusic READ hasMusic NOTIFY viewChanged)
    Q_PROPERTY(bool enabled READ enabled NOTIFY viewChanged)
    Q_PROPERTY(double levelDb READ levelDb NOTIFY viewChanged)
    /// Dự án Studio (đổi ở đây là đổi luôn trong Studio) hay sách đóng gói (chỉ trên máy này).
    Q_PROPERTY(bool project READ project NOTIFY viewChanged)
    /// Lỗi máy chủ trả kèm (danh mục chưa tải được...), "" khi ổn.
    Q_PROPERTY(QString problem READ problem NOTIFY viewChanged)
    /// [{value, name, note}] - mức có sẵn + mức của sách nếu lệch.
    Q_PROPERTY(QVariantList levels READ levels NOTIFY viewChanged)
    /// Đang gửi một lần đổi.
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    /// Có bài của chương này không phát được (đoạn ấy im lặng, chờ thử lại).
    Q_PROPERTY(bool broken READ broken NOTIFY brokenChanged)
    /// Bài đang phát: {label, text, license, licenseUrl, modified, landing}; rỗng khi im lặng.
    Q_PROPERTY(QVariantMap credit READ credit NOTIFY creditChanged)

public:
    /// `make`: một AudioOut mới cho mỗi phần tử nhạc (MusicBed làm chủ).
    Music(Player *player, PlayerNet *net, std::function<AudioOut *()> make, QObject *parent = nullptr);
    ~Music() override;

    static Music *instance();
    static Music *create(QQmlEngine *, QJSEngine *);
    static void setInstance(Music *music);

    bool hasMusic() const { return m_hasMusic; }
    bool enabled() const { return m_enabled; }
    double levelDb() const { return m_levelDb; }
    bool project() const { return m_project; }
    QString problem() const { return m_problem; }
    QVariantList levels() const;
    bool busy() const { return m_busy; }
    bool broken() const { return m_broken; }
    QVariantMap credit() const { return m_credit; }

    Q_INVOKABLE void setEnabled(bool enabled);
    Q_INVOKABLE void setLevel(double levelDb);
    /// Nhạc của một cuốn (mã sách) hay cài đặt chung mọi cuốn ("*", "Tự chọn nhạc nền") vừa đổi: cuốn đang nghe hỏi lại nhạc và mốc của chương
    /// đang phát NGAY, không đợi chương sau (MUSIC_CHANGED_EVENT của player.tsx). Bài đang kêu không bị bỏ trước khi mốc mới về.
    Q_INVOKABLE void reload(const QString &bookId);

    MusicBed *bed() { return &m_bed; }

signals:
    void viewChanged();
    void busyChanged();
    void brokenChanged();
    void creditChanged();

private:
    void onBook();
    void onChapter();
    void askCues(int attempt, int misses);
    void askAgain(int misses);
    void applyView(const QJsonObject &raw);
    void change(const QJsonObject &body);
    void sync();
    void updateBroken();
    void updateCredit(const QString &link);
    void updateTicking();
    QString chapterKey() const;
    QString musicPath() const;

    Player *m_player;
    PlayerNet *m_net;
    MusicBed m_bed;
    NextChapterWarm m_nextWarm;
    QTimer m_tick;  // nhịp đồng bộ khi giọng đang chạy (bản web: sự kiện "time" ~4 lần mỗi giây)
    QTimer m_retry; // hỏi lại mốc (chương chưa dựng xong / danh mục chưa tải được)
    QElapsedTimer m_syncTime;
    bool m_wasPlaying = false;
    double m_lastRate = 1;

    QString m_bookId;
    QString m_cuesFor;  // chương mà mốc trong bed thuộc về: mốc của chương cũ không được mở ở nhịp đầu của chương mới
    int m_generation = 0;
    int m_viewGeneration = 0;
    double m_last = 0;
    double m_volume = -1;
    QHash<QString, MusicLogic::MusicCredit> m_credits;

    bool m_hasMusic = false;
    bool m_enabled = false;
    double m_levelDb = -20;
    bool m_project = false;
    QString m_problem;
    bool m_busy = false;
    bool m_broken = false;
    QVariantMap m_credit;
};
