// Small Sonic output queue: decode-ahead remains at source speed, so speed changes stay responsive.
#pragma once
#include "mixcore.h"
#include <memory>

class TimeStretch {
public:
    explicit TimeStretch(int rate);
    ~TimeStretch();
    void setRate(double speed);
    size_t read(MixCore::Ring &input, float *stereo, size_t frames, bool eof);
    bool drained() const;
private:
    struct Impl;
    std::unique_ptr<Impl> d;
};
