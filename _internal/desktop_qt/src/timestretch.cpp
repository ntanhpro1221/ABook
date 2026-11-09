#include "timestretch.h"
#include "sonic/sonic.h"
#include <algorithm>
#include <new>
#include <cmath>

struct TimeStretch::Impl {
    sonicStream stream = nullptr;
    int rate;
    bool flushed = false;
    bool bypass = true;
    AudioFx::SilenceTrimmer silence;
    std::deque<std::array<float,2>> pending;
    bool silenceFlushed = false;
    size_t consumed = 0; // source frames taken from the ring during the current read()
    size_t readInput(MixCore::Ring &input, float *out, size_t frames, bool eof) {
        auto sink=[this](const auto &f) { pending.push_back(f); };
        while(pending.size()<frames && input.readable()>=2) {
            float block[512]; const size_t n=input.read(block,std::min<size_t>(256,frames)*2)/2;
            consumed+=n;
            for(size_t i=0;i<n;++i) silence.push({block[2*i],block[2*i+1]},sink);
        }
        if(eof && !input.readable() && !silenceFlushed) { silence.finish(sink); silenceFlushed=true; }
        const size_t n=std::min(frames,pending.size());
        for(size_t i=0;i<n;++i) { out[2*i]=pending.front()[0];out[2*i+1]=pending.front()[1];pending.pop_front(); }
        return n;
    }
    // Sonic C cắt cụt số mẫu mỗi chu kỳ cao độ: ghi từng khối 256 khung, 750 s ở 3x ra hụt 0,8 s (nội dung trôi 2,4 s
    // khỏi vị trí bộ trộn tính = khung ra x tốc độ). Đếm vào / ra từ lần đổi tốc độ, lệch quá 50 ms nội dung thì nắn
    // tốc độ Sonic tối đa 0,5 % cho lệch về trong ~10 s. Tốc độ 1 không nắn: Sonic chép thẳng, không trôi.
    double speed = 1, pitch = 0, in = 0, out = 0;
    explicit Impl(int rate) : rate(rate), silence(rate) {}
    void steer() {
        if (speed == 1.0 && pitch == 0) return;
        const double deficit = in - (out + sonicSamplesAvailable(stream)) * speed, band = rate * 0.05;
        const double over = deficit > band ? deficit - band : deficit < -band ? deficit + band : 0;
        sonicSetSpeed(stream, float(speed / (1 + std::clamp(over / (rate * 10.0), -0.005, 0.005))));
    }
    ~Impl() { if (stream) sonicDestroyStream(stream); }
};
TimeStretch::TimeStretch(int rate) : d(new Impl(rate)) {}
TimeStretch::~TimeStretch() = default;
void TimeStretch::setAudioFx(const AudioFx::Settings &settings) { d->silence.configure(settings,[this](const auto &f) { d->pending.push_back(f); }); }
double TimeStretch::sourceSeconds(double compressedSeconds) const { return d->silence.sourceSeconds(compressedSeconds); }
void TimeStretch::setRate(double speed) {
    speed = std::clamp(speed, 0.5, 4.0);
    if (speed == 1.0 && d->bypass) return;
    if (!d->stream) {
        d->stream = sonicCreateStream(d->rate, 2);
        if (!d->stream) throw std::bad_alloc();
        d->bypass = false;
    }
    if (speed == d->speed && d->in) return;
    d->speed = speed; d->in = d->out = 0;
    sonicSetSpeed(d->stream, float(speed));
}
void TimeStretch::setPitch(double semitones) {
    semitones = std::isfinite(semitones) ? std::clamp(semitones,-6.0,6.0) : 0;
    if (semitones == d->pitch) return;
    // Instantiate Sonic even at 1x; speed remains independent of pitch.
    if (!d->stream) {
        d->stream = sonicCreateStream(d->rate,2);
        if (!d->stream) throw std::bad_alloc();
        d->bypass = false;
        sonicSetSpeed(d->stream,float(d->speed));
    }
    d->pitch=semitones;
    sonicSetPitch(d->stream,float(std::pow(2,semitones/12)));
}
bool TimeStretch::lookingAhead() const { return d->consumed && d->silence.holding(); }
size_t TimeStretch::read(MixCore::Ring &input, float *stereo, size_t frames, bool eof) {
    d->consumed = 0;
    if (d->bypass) {
        const size_t n = d->readInput(input, stereo, frames, eof);
        d->flushed = eof && !input.readable() && d->pending.empty() && d->silenceFlushed;
        return n;
    }
    size_t written = 0;
    float block[256 * 2];
    while (written < frames) {
        const auto got = size_t(sonicReadFloatFromStream(d->stream, stereo + written * 2, int(frames - written)));
        written += got; d->out += double(got);
        if (written == frames) break;
        const size_t n = d->readInput(input, block, 256, eof);
        if (n) {
            d->steer();
            if (!sonicWriteFloatToStream(d->stream, block, int(n))) throw std::bad_alloc();
            d->in += double(n);
        } else if (eof && d->silenceFlushed && !d->flushed) {
            if (!sonicFlushStream(d->stream)) throw std::bad_alloc();
            d->flushed = true;
        } else break;
    }
    return written;
}
bool TimeStretch::drained() const { return d->flushed && (d->bypass || sonicSamplesAvailable(d->stream) == 0); }
