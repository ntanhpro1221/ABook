// Small Sonic output queue: decode-ahead remains at source speed, so speed changes stay responsive.
#pragma once
#include "mixcore.h"
#include "audiofx.h"
#include <memory>

class TimeStretch {
public:
    explicit TimeStretch(int rate);
    ~TimeStretch();
    void setRate(double speed);
    void setPitch(double semitones);
    void setAudioFx(const AudioFx::Settings &settings);
    double sourceSeconds(double compressedSeconds) const;
    size_t read(MixCore::Ring &input, float *stereo, size_t frames, bool eof);
    // The last read came up short only because the silence trimmer took source frames it is still holding (its
    // lookahead may be longer than the input ring): the source kept up, so this is no underrun.
    bool lookingAhead() const;
    bool drained() const;
private:
    struct Impl;
    std::unique_ptr<Impl> d;
};
