#include "audioout.h"

double AudioOut::effectiveVolume(double volume) {
    static const bool muted = qEnvironmentVariableIntValue("ABOOK_MUTE") != 0;
    return muted ? 0.0 : qBound(0.0, volume, 1.0);
}
