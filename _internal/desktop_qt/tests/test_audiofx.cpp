#include "audiofx.h"
#include "timestretch.h"
#include <QtTest>
#include <vector>
#include <cmath>

class AudioFxTests : public QObject {
    Q_OBJECT
private slots:
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
