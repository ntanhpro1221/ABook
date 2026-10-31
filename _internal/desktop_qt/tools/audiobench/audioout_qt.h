// Ứng viên (b) của D1: QMediaPlayer (Qt Multimedia 6.10, bộ giải mã FFmpeg hay bộ của Windows tuỳ QT_MEDIA_BACKEND). Chỉ dùng để ĐO.
#pragma once

#include "audioout.h"

class QAudioOutput;
class QMediaPlayer;

class QtAudioOut final : public AudioOut {
    Q_OBJECT
public:
    explicit QtAudioOut(QObject *parent = nullptr);
    void load(const QUrl &url, double startSeconds) override;
    void play() override;
    void pause() override;
    void stop() override;
    void seek(double seconds) override;
    void setRate(double rate) override;
    void setVolume(double volume) override;
    double position() const override;
    double duration() const override;
    bool playing() const override { return m_playing; }

private:
    QMediaPlayer *m_player;
    QAudioOutput *m_out;
    bool m_playing = false;
    bool m_wantPlay = false;
    double m_target = 0;
    bool m_seeking = false;
    bool m_started = false;
    double m_duration = 0;
};
