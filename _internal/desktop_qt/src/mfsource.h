// MF chỉ giải mã lúc dựng cache; luồng phát nhạc luôn đọc PCM qua mixer chung.
#pragma once

#include "mixcore.h"

#include <QByteArray>
#include <QString>

#include <memory>
#include <vector>

class MfSource {
public:
    explicit MfSource(int outRate);
    ~MfSource();
    MfSource(const MfSource &) = delete;
    MfSource &operator=(const MfSource &) = delete;

    bool open(const QByteArray &data);
    int sourceRate() const { return m_rate; }
    int sourceChannels() const { return m_channels; }
    double duration() const { return m_duration; }
    size_t read(std::vector<float> &out, size_t frames);
    bool atEnd() const { return m_done && m_pendingAt == m_pending.size(); }
    QString error() const { return m_error; }

private:
    struct Decoder;
    std::unique_ptr<Decoder> d;
    int m_outRate, m_rate = 0, m_channels = 0;
    double m_duration = 0;
    QString m_error;
    bool m_ogg = false, m_done = false;
    std::unique_ptr<MixCore::Resampler> m_resampler;
    std::vector<float> m_pending;
    size_t m_pendingAt = 0;
    quint64 m_fed = 0, m_given = 0, m_length = 0;
    bool fail(long hr);
};
