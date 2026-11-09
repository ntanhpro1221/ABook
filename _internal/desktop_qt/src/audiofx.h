#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>
#include <deque>
#include <vector>
#include <cstdint>
#include "tonecatalog.generated.h"

namespace AudioFx {
inline constexpr auto frequencies = ToneCatalog::frequencies;
inline const auto presets = [] { std::array<std::array<double,5>,ToneCatalog::presets.size()> p{};for(size_t i=0;i<p.size();++i)p[i]=ToneCatalog::presets[i].bands;return p;}();
struct Settings {
    bool enabled = false;
    int preset = 0;
    std::array<double, 5> bands{};
    double bass = 0, boost = 0, pitch = 0;
    bool mono = false, skipSilence = false;
    double balance = 0, silenceDb = -60, silenceSeconds = 3, keepSeconds = 1.5;
    bool operator==(const Settings &) const = default;
};
struct Biquad {
    double b0=1,b1=0,b2=0,a1=0,a2=0;
    std::array<double,2> z1{}, z2{};
    double tick(double x, int ch) {
        const double y=b0*x+z1[ch]; z1[ch]=b1*x-a1*y+z2[ch]; z2[ch]=b2*x-a2*y; return y;
    }
    static Biquad make(int rate, double frequency, double db, bool shelf=false) {
        const double w=2*std::numbers::pi*(std::min)(frequency,rate*.45)/rate;
        const double a=std::pow(10,db/40), c=std::cos(w), s=std::sin(w), alpha=s/(2*ToneCatalog::q);
        if (!shelf) {
            const double a0=1+alpha/a;
            return {(1+alpha*a)/a0,-2*c/a0,(1-alpha*a)/a0,-2*c/a0,(1-alpha/a)/a0};
        }
        const double t=s*std::sqrt(2*a), a0=(a+1)+(a-1)*c+t;
        return {a*((a+1)-(a-1)*c+t)/a0,2*a*((a-1)-(a+1)*c)/a0,a*((a+1)-(a-1)*c-t)/a0,
            -2*((a-1)+(a+1)*c)/a0,((a+1)+(a-1)*c-t)/a0};
    }
};
class Dsp {
    Settings settings;
    std::array<Biquad,6> filters;
    int rate=0;
    double gain=1, envelope=1, release=0;
public:
    void configure(const Settings &s, int hz) {
        if (hz!=rate || s.enabled!=settings.enabled || s.bands!=settings.bands || s.bass!=settings.bass) {
            for (size_t i=0;i<5;++i) filters[i]=Biquad::make(hz,frequencies[i],s.enabled?s.bands[i]:0);
            filters[5]=Biquad::make(hz,120,s.enabled?s.bass:0,true);
        }
        settings=s; rate=hz; gain=std::pow(10,s.boost/20); release=std::exp(-1.0/(hz*.08));
    }
    void process(float *stereo, size_t frames) {
        if (!settings.enabled && settings.boost==0 && !settings.mono && settings.balance==0) { envelope=1; return; }
        constexpr double ceiling=.8912509381337456; // -1 dBFS
        for (size_t i=0;i<frames;++i) {
            if (settings.mono) { const float mid=(stereo[2*i]+stereo[2*i+1])*.5f; stereo[2*i]=stereo[2*i+1]=mid; }
            stereo[2*i]*=float(1-(std::max)(0.,settings.balance));
            stereo[2*i+1]*=float(1+(std::min)(0.,settings.balance));
            double x[2]; double peak=0;
            for (int ch=0;ch<2;++ch) {
                x[ch]=stereo[2*i+ch]; if (!std::isfinite(x[ch])) x[ch]=0;
                if (settings.enabled) for (auto &f:filters) x[ch]=f.tick(x[ch],ch);
                x[ch]*=gain; peak=(std::max)(peak,std::abs(x[ch]));
            }
            envelope=(std::min)(peak>ceiling?ceiling/peak:1.0,1-(1-envelope)*release);
            for (int ch=0;ch<2;++ch) stereo[2*i+ch]=float(std::clamp(x[ch]*envelope,-ceiling,ceiling));
        }
    }
};

// Source PCM lookahead, bounded by the trigger duration. Never trims a voiced
// frame or a short pause. The clock map is evaluated at the heard position.
class SilenceTrimmer {
    int rate;
    Settings settings;
    std::deque<std::array<float,2>> quiet;
    bool longPause=false;
    double floor=0;
    size_t keep=0,trigger=0;
    uint64_t inputFrames=0, outputFrames=0;
    std::vector<std::pair<uint64_t,uint64_t>> cuts;
    template<class Emit> void output(const std::array<float,2> &f, Emit sink) { sink(f); ++outputFrames; }
public:
    explicit SilenceTrimmer(int rate):rate(rate) {}
    // Quiet source frames held back until the pause is known to be short (played) or long (cut).
    bool holding() const { return !quiet.empty(); }
    template<class Emit> void finish(Emit sink) {
        if (longPause) cuts.emplace_back(outputFrames,inputFrames-outputFrames-quiet.size());
        while (!quiet.empty()) { output(quiet.front(),sink); quiet.pop_front(); }
        longPause=false;
    }
    template<class Emit> void configure(const Settings &s, Emit sink) {
        if(s.skipSilence!=settings.skipSilence || s.silenceDb!=settings.silenceDb || s.silenceSeconds!=settings.silenceSeconds || s.keepSeconds!=settings.keepSeconds) finish(sink);
        settings=s;
        floor=std::pow(10,s.silenceDb/20);keep=size_t(std::llround(s.keepSeconds*rate));trigger=size_t(std::llround(s.silenceSeconds*rate));
    }
    template<class Emit> void push(const std::array<float,2> &f, Emit sink) {
        const bool silent=settings.skipSilence && std::isfinite(f[0]) && std::isfinite(f[1]) && std::abs(f[0])<=floor && std::abs(f[1])<=floor;
        if(!silent) { finish(sink); ++inputFrames; output(f,sink); return; }
        ++inputFrames; quiet.push_back(f);
        if(!longPause && quiet.size()>trigger) {
            for(size_t i=0;i<keep/2;++i) { output(quiet.front(),sink); quiet.pop_front(); }
            longPause=true;
        }
        if(longPause) while(quiet.size()>keep-keep/2) quiet.pop_front();
    }
    double sourceSeconds(double seconds) const {
        const auto frame=uint64_t((std::max)(0.,seconds)*rate); uint64_t removed=0;
        for(const auto &cut:cuts) { if(cut.first>frame) break; removed=cut.second; }
        return seconds+double(removed)/rate;
    }
};
}
