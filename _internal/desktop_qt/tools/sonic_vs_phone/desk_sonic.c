// Same path as desktop TimeStretch: sonicCreateStream(rate, 2), float stereo, sonicSetSpeed only, 4096-frame blocks.
// desk_sonic <in.f32 mono> <speed> <out.f32 mono (left channel)> <rate>
#include "sonic.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END); long bytes = ftell(f); fseek(f, 0, SEEK_SET);
    long n = bytes / 4;
    float *mono = malloc(bytes); fread(mono, 4, n, f); fclose(f);
    float speed = (float)atof(argv[2]);
    int rate = atoi(argv[4]);
    sonicStream s = sonicCreateStream(rate, 2);
    sonicSetSpeed(s, speed);
    FILE *o = fopen(argv[3], "wb");
    float block[4096 * 2], out[8192 * 2], left[8192];
    for (long pos = 0; pos <= n; pos += 4096) {
        long m = pos + 4096 <= n ? 4096 : n - pos;
        if (m > 0) {
            for (long i = 0; i < m; ++i) block[2 * i] = block[2 * i + 1] = mono[pos + i];
            sonicWriteFloatToStream(s, block, (int)m);
        }
        if (pos + 4096 > n) sonicFlushStream(s);
        int got;
        while ((got = sonicReadFloatFromStream(s, out, 8192)) > 0) {
            for (int i = 0; i < got; ++i) left[i] = out[2 * i];
            fwrite(left, 4, got, o);
        }
        if (m < 4096) break;
    }
    fclose(o);
    sonicDestroyStream(s);
    return 0;
}
