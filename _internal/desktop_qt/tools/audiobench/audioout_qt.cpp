#include "audioout_qt.h"

#include <QAudioOutput>
#include <QMediaPlayer>

QtAudioOut::QtAudioOut(QObject *parent) : AudioOut(parent), m_player(new QMediaPlayer(this)), m_out(new QAudioOutput(this)) {
    m_player->setAudioOutput(m_out);
    m_player->setPitchCompensation(true);
    connect(m_player, &QMediaPlayer::durationChanged, this, [this](qint64 ms) {
        m_duration = ms / 1000.0;
        emit durationChanged(m_duration);
    });
    connect(m_player, &QMediaPlayer::playbackStateChanged, this, [this](QMediaPlayer::PlaybackState state) {
        const bool now = state == QMediaPlayer::PlayingState;
        if (now != m_playing) {
            m_playing = now;
            emit playingChanged(now);
        }
    });
    connect(m_player, &QMediaPlayer::mediaStatusChanged, this, [this](QMediaPlayer::MediaStatus status) {
        switch (status) {
        case QMediaPlayer::LoadedMedia:
            if (!m_started) {
                m_started = true;
                if (m_target > 0)
                    m_player->setPosition(qint64(m_target * 1000));
            }
            emit buffering(false);
            break;
        case QMediaPlayer::StalledMedia:
        case QMediaPlayer::BufferingMedia:
            emit buffering(status == QMediaPlayer::StalledMedia);
            break;
        case QMediaPlayer::EndOfMedia:
            emit ended();
            break;
        default:
            break;
        }
    });
    connect(m_player, &QMediaPlayer::positionChanged, this, [this](qint64) {
        if (m_seeking) {
            m_seeking = false;
            emit seeked();
        }
    });
    connect(m_player, &QMediaPlayer::errorOccurred, this, [this](QMediaPlayer::Error, const QString &text) { emit failed(text); });
}

void QtAudioOut::load(const QUrl &url, double startSeconds) {
    m_wantPlay = false;
    m_started = false;
    m_target = startSeconds;
    m_seeking = false;
    m_duration = 0;
    m_player->setSource(url);
    m_player->setPlaybackRate(1.0);
}

void QtAudioOut::play() {
    m_wantPlay = true;
    m_player->play();
}

void QtAudioOut::pause() {
    m_wantPlay = false;
    m_player->pause();
}

void QtAudioOut::stop() {
    m_wantPlay = false;
    m_player->stop();
    m_player->setSource(QUrl());
}

void QtAudioOut::seek(double seconds) {
    m_target = qMax(0.0, seconds);
    m_seeking = true;
    m_player->setPosition(qint64(m_target * 1000));
}

void QtAudioOut::setRate(double rate) {
    m_player->setPlaybackRate(rate);
}

void QtAudioOut::setVolume(double volume) {
    m_out->setVolume(float(effectiveVolume(volume)));
}

double QtAudioOut::position() const {
    return m_seeking || !m_started ? m_target : m_player->position() / 1000.0;
}

double QtAudioOut::duration() const {
    return m_duration;
}
