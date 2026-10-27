// Windows tự ngoại suy vị trí; chỉ gửi ảnh chụp ở các mốc, không giữ nhịp PlayerClock.
#pragma once

#include <QObject>
#include <QByteArray>
#include <QHash>
#include <QString>
#include <functional>
#include <memory>

class Player;
class AudioOut;
class QNetworkReply;

struct MediaState {
    enum Status { Stopped, Paused, Playing } status = Stopped;
    QString title, artist, album;
    bool loaded = false, canNext = false, canPrevious = false;
    double position = 0, duration = 0, rate = 1;
};
MediaState fromPlayer(const Player &player);
enum class MediaCommand { Play, Pause, Next, Previous, Seek };

// Cổng nhỏ để thử luật cập nhật mà không cần Windows hay thiết bị âm thanh.
class MediaSink {
public:
    virtual ~MediaSink() = default;
    virtual void display(const MediaState &, const QByteArray &cover) = 0;
    virtual void playback(const MediaState &) = 0;
    virtual void timeline(const MediaState &) = 0;
};

class MediaControls : public QObject {
    Q_OBJECT
public:
    using CoverRequest = std::function<QNetworkReply *(const QString &path)>;
    MediaControls(Player *player, AudioOut *out, std::unique_ptr<MediaSink> sink = {}, CoverRequest coverRequest = {}, QObject *parent = nullptr);
    ~MediaControls() override;
    bool attachWindow(quintptr hwnd);
    static void setAppId();
    // Cả WinRT và phép thử đều đi qua hàng đợi của đối tượng, không gọi Player từ luồng Windows.
    void dispatch(MediaCommand command, double seconds = 0);

signals:
    void commandExecuted(MediaCommand command);

private:
    struct Relay;
    void updateDisplay();
    void updatePlayback();
    void updateTimeline();
    Player *m_player;
    std::unique_ptr<MediaSink> m_sink;
    CoverRequest m_coverRequest;
    QString m_coverKey;
    QHash<QString, QByteArray> m_covers;
    std::shared_ptr<Relay> m_relay;
};
