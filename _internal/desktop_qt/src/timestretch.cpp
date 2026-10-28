#include "timestretch.h"
#include "sonic/sonic.h"
#include <new>

struct TimeStretch::Impl {
    sonicStream stream = nullptr;
    int rate;
    bool flushed = false;
    bool bypass = true;
    explicit Impl(int rate) : rate(rate) {}
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
        written += size_t(sonicReadFloatFromStream(d->stream, stereo + written * 2, int(frames - written)));
        if (written == frames) break;
        const size_t available = input.readable() / 2;
        if (available) {
            const size_t n = std::min<size_t>(256, available);
            input.read(block, n * 2);
            if (!sonicWriteFloatToStream(d->stream, block, int(n))) throw std::bad_alloc();
        } else if (eof && !d->flushed) {
            if (!sonicFlushStream(d->stream)) throw std::bad_alloc();
            d->flushed = true;
        } else break;
    }
    return written;
}
bool TimeStretch::drained() const { return d->flushed && (d->bypass || sonicSamplesAvailable(d->stream) == 0); }
