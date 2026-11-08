#include "audiofx.h"
#include "timestretch.h"
#include <QtTest>
#include <vector>
#include <cmath>

class AudioFxTests : public QObject {
    Q_OBJECT
private slots:
    void monoBalance() {
        for(bool mono:{false,true}) for(double balance:{-1.,-.5,0.,.5,1.}) {
            AudioFx::Settings s;s.mono=mono;s.balance=balance;AudioFx::Dsp dsp;dsp.configure(s,48000);
            float f[]{.2f,.6f};dsp.process(f,1);
            QVERIFY(std::abs(f[0]-(mono?.4:.2)*(1-std::max(0.,balance)))<1e-7);
            QVERIFY(std::abs(f[1]-(mono?.4:.6)*(1+std::min(0.,balance)))<1e-7);
        }
    }
    void silenceAndClock() {
        AudioFx::Settings s;s.skipSilence=true;AudioFx::SilenceTrimmer trim(1000);std::vector<std::array<float,2>> out;
        auto sink=[&](const auto &f){out.push_back(f);};trim.configure(s,sink);
        auto push=[&](int n,std::array<float,2> f){for(int i=0;i<n;++i)trim.push(f,sink);};
        push(100,{.1f,.2f});push(1500,{0,0});push(100,{.1f,.2f});push(5000,{0,0});push(100,{.1f,.2f});trim.finish(sink);
        QCOMPARE(out.size(),size_t(3300));
        QCOMPARE(std::count_if(out.begin(),out.end(),[](auto f){return f[0]==.1f && f[1]==.2f;}),300);
        QVERIFY(std::abs(trim.sourceSeconds(2.449)-2.449)<1e-9);
        QVERIFY(std::abs(trim.sourceSeconds(3.2)-6.7)<1e-9);
        QVERIFY(std::abs(trim.sourceSeconds(3.3)-6.8)<1e-9);
    }
    void silenceBoundariesAndChannels() {
        for(int length:{1500,3000,3001,5000}) {
            AudioFx::Settings s;s.skipSilence=true;AudioFx::SilenceTrimmer trim(1000);int count=0;
            auto sink=[&](const auto &){++count;};trim.configure(s,sink);
            for(int i=0;i<length;++i)trim.push({0,0},sink);trim.finish(sink);
            QCOMPARE(count,length>3000?1500:length);
        }
        AudioFx::Settings s;s.skipSilence=true;AudioFx::SilenceTrimmer trim(1000);int count=0;
        auto sink=[&](const auto &){++count;};trim.configure(s,sink);
        for(int i=0;i<5000;++i)trim.push({0,.01f},sink);trim.finish(sink);QCOMPARE(count,5000);
    }
    void silenceThroughSonicKeepsSourceClock() {
        constexpr int rate=48000;
        for(double speed:{1.,1.5}) {
            std::vector<float> source(size_t(rate*7)*2);
            for(size_t i=0;i<source.size()/2;++i) if(i<size_t(rate) || i>=size_t(rate*6)) source[2*i]=source[2*i+1]=float(.2*std::sin(2*std::numbers::pi*220*(i+.5)/rate));
            MixCore::Ring input(source.size());input.write(source.data(),source.size());
            TimeStretch stretch(rate);AudioFx::Settings s;s.skipSilence=true;stretch.setAudioFx(s);stretch.setRate(speed);
            float block[512];size_t count=0;
            while(!stretch.drained())count+=stretch.read(input,block,256,true);
            QVERIFY(std::abs(double(count)/rate-3.5/speed)<.025);
            QVERIFY(std::abs(stretch.sourceSeconds(2.5)-6.0)<1e-9);
        }
    }
    void presetResponse() {
        double worst=0;
        for (int rate:{24000,44100,48000}) for (size_t p=0;p<5;++p) for (size_t b=0;b<5;++b) {
            AudioFx::Settings s; s.enabled=true;s.bands=AudioFx::presets[p];
            AudioFx::Dsp dsp;dsp.configure(s,rate);
            const double hz=std::min(AudioFx::frequencies[b],rate*.45);
            double sum=0,source=0;float frame[2];
            for(int i=0;i<rate;++i) {
                const double x=.001*std::sin(2*std::numbers::pi*hz*i/rate);frame[0]=frame[1]=float(x);dsp.process(frame,1);
                if(i>=rate/4){sum+=frame[0]*frame[0];source+=x*x;}
            }
            const double db=10*std::log10(sum/source),error=std::abs(db-s.bands[b]);worst=std::max(worst,error);
            QVERIFY2(error<=1,qPrintable(QString("rate=%1 preset=%2 band=%3 gain=%4").arg(rate).arg(p).arg(b).arg(db)));
        }
        qInfo()<<"AUDIOFX EQ worst_error_db"<<worst;
    }
    void limiter() {
        AudioFx::Settings s;s.enabled=true;s.bands.fill(12);s.bass=s.boost=12;
        AudioFx::Dsp dsp;dsp.configure(s,48000);double peak=0;
        for(int i=0;i<48000;++i) {
            const float x=i?float(std::sin(2*std::numbers::pi*1000*i/48000)):10;
            float frame[]{x,x*.5f};dsp.process(frame,1);peak=std::max(peak,double(std::abs(frame[0])));
            QVERIFY(std::abs(frame[0])<=.891251f);QVERIFY(std::abs(frame[1]-frame[0]*.5f)<1e-7);
        }
        qInfo()<<"AUDIOFX limiter_peak"<<peak;
    }
    void independentPitch_data() {
        QTest::addColumn<double>("pitch");QTest::addColumn<double>("speed");
        for(double p:{-6.,-3.,3.,6.}) for(double speed:{1.,1.5}) QTest::newRow(qPrintable(QString("%1_%2").arg(p).arg(speed)))<<p<<speed;
    }
    void independentPitch() {
        QFETCH(double,pitch);QFETCH(double,speed);
        constexpr size_t frames=48000*4;
        MixCore::Ring input(frames*2);std::vector<float> sine(frames*2);
        for(size_t i=0;i<frames;++i)sine[2*i]=sine[2*i+1]=float(.2*std::sin(2*std::numbers::pi*220*i/48000));
        input.write(sine.data(),sine.size());TimeStretch sonic(48000);sonic.setRate(speed);sonic.setPitch(pitch);
        std::vector<float> output;float block[960];
        while(!sonic.drained()){auto n=sonic.read(input,block,480,true);output.insert(output.end(),block,block+n*2);}
        const size_t from=4800,to=output.size()/2-4800;int crossings=0;
        for(size_t i=from+1;i<to;++i)if(output[(i-1)*2]<=0&&output[i*2]>0)++crossings;
        const double hz=crossings*48000.0/(to-from),expected=220*std::pow(2,pitch/12),duration=output.size()/2./48000;
        QVERIFY2(std::abs(hz/expected-1)<.03,qPrintable(QString::number(hz)));
        QVERIFY2(std::abs(duration/(4/speed)-1)<.005,qPrintable(QString::number(duration)));
        qInfo()<<"AUDIOFX pitch"<<pitch<<"speed"<<speed<<"f0"<<hz<<"seconds"<<duration;
    }
};
QTEST_GUILESS_MAIN(AudioFxTests)
#include "test_audiofx.moc"
