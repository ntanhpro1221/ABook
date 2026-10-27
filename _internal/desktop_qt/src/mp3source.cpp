#include "mp3source.h"

#include <algorithm>
#include <cmath>

#define NOMINMAX // minimp3_ex.h kéo windows.h vào
#define MINIMP3_IMPLEMENTATION
#define MINIMP3_FLOAT_OUTPUT
#ifdef _MSC_VER
#pragma warning(push, 0)
#endif
#include "minimp3/minimp3_ex.h"
#ifdef _MSC_VER
#pragma warning(pop)
#endif

struct Mp3Source::Decoder {
    mp3dec_ex_t dec{};
    bool open = false;
    ~Decoder() {
        if (open)
            mp3dec_ex_close(&dec);
    }
};

Mp3Source::Mp3Source(int outRate) : d(new Decoder), m_outRate(outRate) {}

Mp3Source::~Mp3Source() = default;

bool Mp3Source::open(const QByteArray &data) {
    d.reset(new Decoder);
    m_resampler.reset();
    m_rate = m_channels = 0;
    m_data = data; // minimp3 đọc thẳng trên vùng nhớ này
    if (mp3dec_ex_open_buf(&d->dec, reinterpret_cast<const uint8_t *>(m_data.constData()), size_t(m_data.size()), MP3D_SEEK_TO_SAMPLE))
        return false;
    d->open = true;
    if (d->dec.info.hz <= 0 || d->dec.info.channels <= 0)
        return false; // minimp3 nhận cả vùng không có khung nào
    m_rate = d->dec.info.hz;
    m_channels = d->dec.info.channels;
    m_resampler = std::make_unique<MixCore::Resampler>(m_rate, m_outRate, 2);
    seek(0);
    return true;
}

double Mp3Source::duration() const {
    return m_rate > 0 ? double(d->dec.samples / unsigned(m_channels)) / m_rate : 0;
}

double Mp3Source::position() const {
    return m_seekSeconds + double(m_given) / m_outRate;
}

bool Mp3Source::atEnd() const {
    return m_sourceDone && m_pendingAt >= m_pending.size();
}

void Mp3Source::seek(double seconds) {
    if (!m_resampler)
        return;
    const unsigned long long frame = (unsigned long long)std::llround(std::clamp(seconds, 0.0, duration()) * m_rate);
    mp3dec_ex_seek(&d->dec, frame * unsigned(m_channels));
    m_seekSeconds = double(frame) / m_rate;
    m_resampler->reset();
    m_pending.clear();
    m_pendingAt = 0;
    m_fed = 0;
    m_given = 0;
    m_sourceDone = false;
}

size_t Mp3Source::read(std::vector<float> &out, size_t frames) {
    if (!m_resampler)
        return 0;
    std::vector<float> stereo;
    mp3d_sample_t block[MINIMP3_MAX_SAMPLES_PER_FRAME];
    while ((m_pending.size() - m_pendingAt) / 2 < frames && !m_sourceDone) {
        const size_t got = mp3dec_ex_read(&d->dec, block, MINIMP3_MAX_SAMPLES_PER_FRAME / 2 / size_t(m_channels) * size_t(m_channels));
        const size_t inFrames = got / size_t(m_channels);
        if (!inFrames) {
            // Hết nguồn: đẩy một cửa sổ im lặng cho bộ đổi tần số tính nốt các khung cuối, rồi cắt đúng số khung ra của nguồn.
            m_sourceDone = true;
            const std::vector<float> silence(size_t(m_resampler->taps()) * 2, 0.0f);
            m_resampler->push(silence.data(), size_t(m_resampler->taps()), m_pending);
            const size_t want = size_t(m_resampler->outFramesFor(m_fed) - m_given) * 2 + m_pendingAt;
            if (m_pending.size() > want)
                m_pending.resize(want);
            break;
        }
        stereo.resize(inFrames * 2);
        for (size_t i = 0; i < inFrames; ++i) {
            const float left = block[i * m_channels];
            stereo[i * 2] = left;
            stereo[i * 2 + 1] = m_channels > 1 ? block[i * m_channels + 1] : left;
        }
        m_resampler->push(stereo.data(), inFrames, m_pending);
        m_fed += inFrames;
    }
    const size_t n = std::min(frames, (m_pending.size() - m_pendingAt) / 2);
    out.insert(out.end(), m_pending.begin() + m_pendingAt, m_pending.begin() + m_pendingAt + n * 2);
    m_pendingAt += n * 2;
    m_given += n;
    if (m_pendingAt > 1 << 16) {
        m_pending.erase(m_pending.begin(), m_pending.begin() + m_pendingAt);
        m_pendingAt = 0;
    }
    return n;
}
