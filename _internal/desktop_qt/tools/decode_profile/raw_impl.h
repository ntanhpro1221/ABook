// Separate translation units keep each upstream decoder's sample type intact.
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <immintrin.h>
#define MINIMP3_IMPLEMENTATION
#define JOIN_IMPL(a,b) a##b
#define JOIN(a,b) JOIN_IMPL(a,b)
#define mp3dec_init JOIN(PROFILE_NAME,_init)
#define mp3dec_decode_frame JOIN(PROFILE_NAME,_frame)
#define mp3dec_f32_to_s16 JOIN(PROFILE_NAME,_convert)
namespace PROFILE_NS {
#include "minimp3/minimp3.h"
}
extern "C" void profileConsume(const float *, int);
extern "C" uint64_t PROFILE_NAME(const uint8_t *data, int size, int repeats, bool convert) {
    using namespace PROFILE_NS;
    uint64_t count = 0;
    volatile float sink = 0;
    for (int r = 0; r < repeats; ++r) {
        mp3dec_t dec{}; mp3dec_init(&dec);
        mp3d_sample_t pcm[MINIMP3_MAX_SAMPLES_PER_FRAME];
        float stereo[MINIMP3_MAX_SAMPLES_PER_FRAME*2];
        int offset = 0;
        while (offset < size) {
            mp3dec_frame_info_t info{};
            const int n = mp3dec_decode_frame(&dec, data + offset, size - offset, pcm, &info);
            if (!info.frame_bytes) break;
            offset += info.frame_bytes;
            if (n) {
                if(convert) {
                    for(int i=0;i<n;++i) for(int c=0;c<2;++c) {
#ifdef MINIMP3_FLOAT_OUTPUT
                        stereo[i*2+c]=pcm[i*info.channels+(info.channels==1 ? 0:c)];
#else
                        stereo[i*2+c]=pcm[i*info.channels+(info.channels==1 ? 0:c)]/32768.0f;
#endif
                    }
                    profileConsume(stereo,n*2);
                }
                sink = float(pcm[n - 1]); count += n;
            }
        }
    }
    return count + uint64_t(sink == 12345);
}
