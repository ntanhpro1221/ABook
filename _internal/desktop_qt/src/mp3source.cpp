#include "mp3source.h"
#include "streamsource.h"
#include <QByteArrayView>

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

// Streaming uses the same minimp3 frame parser and gapless rules as the cached music decoder.
// The index stores compressed frame offsets, not PCM; seeking primes ten frames for the MP3 bit reservoir.
struct StreamMp3::Impl {
    std::shared_ptr<ByteSource> bytes;
    int outputRate, hz = 0, channels = 0, samplesPerFrame = 0, delay = 0, padding = 0;
    bool opened = false, indexed = false, done = false, estimate = false, estimated = false;
    double frameBytes = 0; // mean bytes per frame at the first frame's bitrate; only for length estimates
    qint64 scanAt = 0, first = 0, windowAt = -1;
    QByteArray window;
    struct Frame { qint64 offset; quint64 sample; };
    std::vector<Frame> index;
    quint64 scannedSamples = 0, totalSamples = 0, skip = 0, fed = 0, given = 0, expected = 0, seekTarget = 0;
    size_t next = 0, pendingAt = 0;
    std::vector<float> pending;
    mp3dec_t decoder{};
    std::unique_ptr<MixCore::Resampler> resampler;
    QString failure;

    Impl(std::shared_ptr<ByteSource> source, int rate) : bytes(std::move(source)), outputRate(rate) { mp3dec_init(&decoder); }
    // Views live until the next window refill; every caller consumes a header/frame
    // before asking for another one. Do not allocate/copy two QByteArrays per frame.
    QByteArrayView at(qint64 offset, qint64 n) {
        if (offset >= windowAt && offset + n <= windowAt + window.size()) return QByteArrayView(window).sliced(offset - windowAt, n);
        window = bytes->read(offset, std::max<qint64>(16384, n)); windowAt = offset;
        if (window.size() < n) return {};
        return QByteArrayView(window).first(n);
    }
    bool extend(quint64 target) {
        while (!indexed && (index.empty() || scannedSamples <= target)) {
            const qint64 size = bytes->size();
            if (size >= 0 && scanAt + 4 > size) { indexed = true; break; }
            const auto h = at(scanAt, 4);
            if (h.isEmpty()) return false;
            const auto *hdr = reinterpret_cast<const uint8_t *>(h.constData());
            if (!hdr_valid(hdr) || HDR_GET_LAYER(hdr) != 1) {
                if (size >= 0 && size - scanAt < 16384) { indexed = true; break; }
                failure = QStringLiteral("Invalid MP3 frame in chapter"); return false;
            }
            const int count = hdr_frame_bytes(hdr, 0) + hdr_padding(hdr);
            if (count <= 4 || (size >= 0 && scanAt + count > size)) { indexed = true; break; }
            if (hdr_sample_rate_hz(hdr) != hz || (HDR_IS_MONO(hdr) ? 1 : 2) != channels) {
                failure = QStringLiteral("MP3 format changes inside chapter"); return false;
            }
            index.push_back({scanAt, scannedSamples}); scanAt += count; scannedSamples += hdr_frame_samples(hdr);
        }
        if (indexed) totalSamples = scannedSamples > quint64(delay + std::max(0, padding)) ? scannedSamples - delay - std::max(0, padding) : 0;
        if (indexed && estimated) { estimated = false; expected = resampler->outFramesFor(totalSamples - std::min(totalSamples, seekTarget)); }
        return indexed || scannedSamples > target;
    }
};

StreamMp3::StreamMp3(std::shared_ptr<ByteSource> bytes, int outputRate, bool estimateLength) : d(new Impl(std::move(bytes), outputRate)) {
    d->estimate = estimateLength;
}
StreamMp3::~StreamMp3() = default;
QString StreamMp3::error() const { return !d->failure.isEmpty() ? d->failure : d->bytes->error(); }
double StreamMp3::duration() const { return d->hz ? double(d->totalSamples) / d->hz : 0; }
bool StreamMp3::atEnd() const { return d->done && d->pendingAt == d->pending.size(); }
bool StreamMp3::open() {
    if (d->opened) return true;
    if (!error().isEmpty()) return false;
    if (!d->hz) {
        auto start = d->at(0, 10);
        if (start.isEmpty()) {
            if (d->bytes->size() >= 0 && d->bytes->size() < 10) d->failure = QStringLiteral("Empty MP3 chapter");
            return false;
        }
        const auto *p = reinterpret_cast<const uint8_t *>(start.constData());
        d->first = qint64(mp3dec_skip_id3v2(p, size_t(start.size())));
        const qint64 size = d->bytes->size();
        if (size < 0) return false;
        const auto data = d->bytes->read(d->first, std::min<qint64>(16384, size - d->first));
        if (data.isEmpty()) return false;
        int freeBytes = 0, frameBytes = 0;
        const int skipBytes = mp3d_find_frame(reinterpret_cast<const uint8_t *>(data.constData()), int(data.size()), &freeBytes, &frameBytes);
        if (!frameBytes || freeBytes) { d->failure = QStringLiteral("Chapter is not a supported MP3 file"); return false; }
        d->first += skipBytes;
        const auto *hdr = reinterpret_cast<const uint8_t *>(data.constData() + skipBytes);
        if (HDR_GET_LAYER(hdr) != 1) { d->failure = QStringLiteral("Chapter must use MP3 Layer III"); return false; }
        d->hz = int(hdr_sample_rate_hz(hdr)); d->channels = HDR_IS_MONO(hdr) ? 1 : 2;
        d->samplesPerFrame = int(hdr_frame_samples(hdr));
        d->frameBytes = double(d->samplesPerFrame) * hdr_bitrate_kbps(hdr) * 125.0 / d->hz;
        uint32_t frames = 0;
        if (mp3dec_check_vbrtag(hdr, frameBytes, &frames, &d->delay, &d->padding) > 0) {
            d->first += frameBytes; // Xing/Info is metadata, not an audio frame
            const quint64 raw = quint64(frames) * d->samplesPerFrame;
            const quint64 trim = quint64(d->delay + std::max(0, d->padding));
            d->totalSamples = raw > trim ? raw - trim : 0;
        }
        d->scanAt = d->first;
        d->resampler = std::make_unique<MixCore::Resampler>(d->hz, d->outputRate, 2);
    }
    // Untagged CBR/VBR: header-only scan builds an exact sample index. It never decodes a whole chapter into RAM.
    if (!d->totalSamples && !d->extend(UINT64_MAX - 1)) {
        // A downloading track without a Xing tag (incompetech): scanning every header means waiting for the whole
        // download. Estimate from the bitrate (exact for CBR to a frame); the scan's end sets the real count.
        if (!d->estimate || !error().isEmpty() || d->index.empty()) return false;
        d->totalSamples = quint64(std::max<qint64>(1, std::llround(double(d->bytes->size() - d->first) / d->frameBytes))) * quint64(d->samplesPerFrame);
        d->estimated = true;
    }
    if (!d->totalSamples) { d->failure = QStringLiteral("No MP3 samples in chapter"); return false; }
    d->opened = true;
    return seek(0);
}
bool StreamMp3::seek(double seconds) {
    if (!d->opened) return false;
    const quint64 target = quint64(std::llround(std::clamp(seconds, 0.0, duration()) * d->hz));
    const quint64 raw = target + d->delay;
    if (!d->extend(raw)) return false;
    auto it = std::upper_bound(d->index.begin(), d->index.end(), raw, [](quint64 sample, const auto &frame) { return sample < frame.sample; });
    size_t frame = it == d->index.begin() ? 0 : size_t(it - d->index.begin() - 1);
    frame = frame > 10 ? frame - 10 : 0;
    d->next = frame; d->skip = raw - (d->index.empty() ? 0 : d->index[frame].sample);
    mp3dec_init(&d->decoder); d->resampler->reset();
    d->pending.clear(); d->pendingAt = 0; d->fed = d->given = 0;
    // While the length is an estimate, read to the end of the index; extend() sets the real count.
    d->seekTarget = target;
    d->expected = d->estimated ? UINT64_MAX / 4 : d->resampler->outFramesFor(d->totalSamples - std::min(d->totalSamples, target));
    d->done = false;
    return true;
}
size_t StreamMp3::read(std::vector<float> &out, size_t frames) {
    if (!d->opened || !error().isEmpty()) return 0;
    d->pending.reserve(d->pending.size() + frames * 2 + MINIMP3_MAX_SAMPLES_PER_FRAME);
    while ((d->pending.size() - d->pendingAt) / 2 < frames && !d->done) {
        if (d->next >= d->index.size() && !d->extend(d->scannedSamples)) break;
        if (d->next >= d->index.size() || d->given + (d->pending.size() - d->pendingAt) / 2 >= d->expected) {
            d->done = true;
            std::vector<float> silence(size_t(d->resampler->taps()) * 2, 0);
            d->resampler->push(silence.data(), size_t(d->resampler->taps()), d->pending);
            const size_t limit = size_t(d->expected - std::min(d->expected, d->given)) * 2 + d->pendingAt;
            if (d->pending.size() > limit) d->pending.resize(limit);
            break;
        }
        const auto offset = d->index[d->next].offset;
        const auto h = d->at(offset, 4);
        if (h.isEmpty()) break;
        const auto *hdr = reinterpret_cast<const uint8_t *>(h.constData());
        const int frameBytes = hdr_frame_bytes(hdr, 0) + hdr_padding(hdr);
        const auto data = d->at(offset, frameBytes);
        if (data.isEmpty()) break;
        mp3d_sample_t pcm[MINIMP3_MAX_SAMPLES_PER_FRAME]; mp3dec_frame_info_t info{};
        const int n = mp3dec_decode_frame(&d->decoder, reinterpret_cast<const uint8_t *>(data.constData()), int(data.size()), pcm, &info);
        ++d->next;
        // Reservoir priming may produce no samples, but still occupies its source timeline.
        const quint64 discard = std::min<quint64>(d->skip, d->samplesPerFrame);
        d->skip -= discard;
        if (!n || discard >= quint64(n)) continue;
        // Same-rate PCM needs no intermediate allocation or resampler copy.
        const size_t begin = d->pending.size();
        const bool direct = d->resampler->passthrough();
        std::vector<float> converted;
        if (direct) d->pending.resize(begin + size_t(n - discard) * 2);
        else converted.resize(size_t(n - discard) * 2);
        float *stereo = direct ? d->pending.data() + begin : converted.data();
        if (d->channels == 2) std::copy_n(pcm + discard * 2, size_t(n - discard) * 2, stereo);
        else for (size_t i = size_t(discard); i < size_t(n); ++i)
            stereo[(i - discard) * 2] = stereo[(i - discard) * 2 + 1] = pcm[i];
        if (!direct) d->resampler->push(stereo, converted.size() / 2, d->pending);
        d->fed += size_t(n - discard);
    }
    const size_t n = std::min<size_t>(std::min(frames, (d->pending.size() - d->pendingAt) / 2), size_t(d->expected - std::min(d->expected, d->given)));
    out.insert(out.end(), d->pending.begin() + d->pendingAt, d->pending.begin() + d->pendingAt + n * 2);
    d->pendingAt += n * 2; d->given += n;
    if (d->given >= d->expected) { d->done = true; d->pending.resize(d->pendingAt); }
    if (d->pendingAt > 32768) { d->pending.erase(d->pending.begin(), d->pending.begin() + d->pendingAt); d->pendingAt = 0; }
    return n;
}
