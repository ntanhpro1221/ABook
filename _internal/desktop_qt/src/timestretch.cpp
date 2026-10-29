#include "timestretch.h"
#include "sonic/sonic.h"
#include <algorithm>
#include <new>

struct TimeStretch::Impl {
    sonicStream stream = nullptr;
    int rate;
    bool flushed = false;
    bool bypass = true;
    // Sonic C cắt cụt số mẫu mỗi chu kỳ cao độ: ghi từng khối 256 khung, 750 s ở 3x ra hụt 0,8 s (nội dung trôi 2,4 s
    // khỏi vị trí bộ trộn tính = khung ra x tốc độ). Đếm vào / ra từ lần đổi tốc độ, lệch quá 50 ms nội dung thì nắn
    // tốc độ Sonic tối đa 0,5 % cho lệch về trong ~10 s. Tốc độ 1 không nắn: Sonic chép thẳng, không trôi.
    double speed = 1, in = 0, out = 0;
    explicit Impl(int rate) : rate(rate) {}
    void steer() {
        if (speed == 1.0) return;
        const double deficit = in - (out + sonicSamplesAvailable(stream)) * speed, band = rate * 0.05;
        const double over = deficit > band ? deficit - band : deficit < -band ? deficit + band : 0;
        sonicSetSpeed(stream, float(speed / (1 + std::clamp(over / (rate * 10.0), -0.005, 0.005))));
    }
    ~Impl() { if (stream) sonicDestroyStream(stream); }
};
TimeStretch::TimeStretch(int rate) : d(new Impl(rate)) {}
TimeStretch::~TimeStretch() = default;
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
size_t TimeStretch::read(MixCore::Ring &input, float *stereo, size_t frames, bool eof) {
    if (d->bypass) {
        const size_t n = input.read(stereo, frames * 2) / 2;
        d->flushed = eof && !input.readable();
        return n;
    }
    size_t written = 0;
    float block[256 * 2];
    while (written < frames) {
        const auto got = size_t(sonicReadFloatFromStream(d->stream, stereo + written * 2, int(frames - written)));
        written += got; d->out += double(got);
        if (written == frames) break;
        const size_t available = input.readable() / 2;
        if (available) {
            const size_t n = std::min<size_t>(256, available);
            input.read(block, n * 2);
            d->steer();
            if (!sonicWriteFloatToStream(d->stream, block, int(n))) throw std::bad_alloc();
            d->in += double(n);
        } else if (eof && !d->flushed) {
            if (!sonicFlushStream(d->stream)) throw std::bad_alloc();
            d->flushed = true;
        } else break;
    }
    return written;
}
bool TimeStretch::drained() const { return d->flushed && (d->bypass || sonicSamplesAvailable(d->stream) == 0); }
