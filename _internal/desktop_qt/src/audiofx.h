#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>

namespace AudioFx {
inline constexpr std::array<double, 5> frequencies{80, 250, 1000, 4000, 12000};
inline constexpr std::array<std::array<double, 5>, 5> presets{{
    {0,0,0,0,0}, {-4,-2,2,3,-2}, {4,2,0,-1,-2}, {-2,-1,0,2,4}, {0,0,0,-3,-5}}};
struct Settings {
    bool enabled = false;
    int preset = 0;
    std::array<double, 5> bands{};
    double bass = 0, boost = 0, pitch = 0;
    bool operator==(const Settings &) const = default;
};
struct Biquad {
    double b0=1,b1=0,b2=0,a1=0,a2=0;
    std::array<double,2> z1{}, z2{};
    double tick(double x, int ch) {
        const double y=b0*x+z1[ch]; z1[ch]=b1*x-a1*y+z2[ch]; z2[ch]=b2*x-a2*y; return y;
    }
    static Biquad make(int rate, double frequency, double db, bool shelf=false) {
        const double w=2*std::numbers::pi*std::min(frequency,rate*.45)/rate;
        const double a=std::pow(10,db/40), c=std::cos(w), s=std::sin(w), alpha=s/(2*1.4);
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
        constexpr double ceiling=.8912509381337456; // -1 dBFS
        for (size_t i=0;i<frames;++i) {
            double x[2]; double peak=0;
            for (int ch=0;ch<2;++ch) {
                x[ch]=stereo[2*i+ch]; if (!std::isfinite(x[ch])) x[ch]=0;
                if (settings.enabled) for (auto &f:filters) x[ch]=f.tick(x[ch],ch);
                x[ch]*=gain; peak=std::max(peak,std::abs(x[ch]));
            }
            envelope=std::min(peak>ceiling?ceiling/peak:1.0,1-(1-envelope)*release);
            for (int ch=0;ch<2;++ch) stereo[2*i+ch]=float(std::clamp(x[ch]*envelope,-ceiling,ceiling));
        }
    }
};
}
