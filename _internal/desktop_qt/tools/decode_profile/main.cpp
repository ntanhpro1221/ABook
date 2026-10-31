// Offline component profile. No GUI, no device, no mute shortcut. Not deployed CPU evidence.
#include "streamsource.h"
#include "timestretch.h"
#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QCryptographicHash>
#include <chrono>
#define NOMINMAX
#include <windows.h>
extern "C" uint64_t rawFloat(const uint8_t *, int, int, bool);
extern "C" uint64_t rawInt16(const uint8_t *, int, int, bool);
volatile float consumed=0;
extern "C" void profileConsume(const float *p,int n) { consumed=p[n-1]; }
struct Memory : ByteSource {
    QByteArray data;
    explicit Memory(QByteArray bytes) : data(std::move(bytes)) {}
    QByteArray read(qint64 at, qint64 n) override { return data.mid(at, n); }
    qint64 size() const override { return data.size(); }
    QString error() const override { return {}; }
};
double cpu() {
    FILETIME c,e,k,u; GetThreadTimes(GetCurrentThread(), &c,&e,&k,&u);
    return double((quint64(k.dwHighDateTime)<<32 | k.dwLowDateTime) + (quint64(u.dwHighDateTime)<<32 | u.dwLowDateTime)) / 1e7;
}
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point start) { return std::chrono::duration<double>(Clock::now()-start).count(); }
int main(int argc, char **argv) {
    QCoreApplication app(argc,argv);
    if (argc != 3) return 2;
    QFile file(QString::fromLocal8Bit(argv[1])); if (!file.open(QIODevice::ReadOnly)) return 3;
    const auto bytes = file.readAll();
    QJsonArray results;
    const int repeats = 6;
    for (double speed : {1.0,1.5}) {
        auto source = std::make_shared<Memory>(bytes);
        StreamMp3 decoder(source,48000); if (!decoder.open()) return 4;
        double decodeSeconds=0,ringSeconds=0,stretchSeconds=0;
        quint64 total=0; std::vector<float> block,output(24000*2);
        QCryptographicHash hash(QCryptographicHash::Sha256);
        const auto started = Clock::now(); const double before = cpu();
        double used=0, wall=0;
        for(int r=0;r<=repeats;++r) {
            if(r==repeats) { used=cpu()-before; wall=elapsed(started); }
            decoder.seek(0); MixCore::Ring ring(48000*4); TimeStretch stretch(48000); stretch.setRate(speed);
            while(!stretch.drained()) {
                if(ring.readable()<48000*2 && !decoder.atEnd()) {
                    auto t=Clock::now(); block.clear(); const size_t n=decoder.read(block, std::min<size_t>(8192,ring.writable()/2)); if(r<repeats)decodeSeconds+=elapsed(t);
                    t=Clock::now(); ring.write(block.data(),n*2); if(r<repeats)ringSeconds+=elapsed(t);
                    if(!n && !decoder.atEnd()) return 5;
                    continue;
                }
                auto t=Clock::now(); const auto n=stretch.read(ring,output.data(),24000,decoder.atEnd()); if(r<repeats)stretchSeconds+=elapsed(t);
                if(r<repeats)total+=n;
                else hash.addData(QByteArrayView(reinterpret_cast<const char *>(output.data()),qsizetype(n*2*sizeof(float))));
            }
        }
        results.append(QJsonObject{{"speed",speed},{"thread_cpu_s",used},{"wall_s",wall},
            {"media_s",decoder.duration()*repeats/speed},{"cpu_core_pct_per_media",used/(decoder.duration()*repeats/speed)*100},
            {"decoder_wall_s",decodeSeconds},{"ring_write_wall_s",ringSeconds},{"stretch_wall_s",stretchSeconds},
            {"output_frames",double(total)},{"first_pass_pcm_sha256",QString::fromLatin1(hash.result().toHex())}});
    }
    for(bool convert : {false,true}) for(auto [name,fn] : {std::pair{"float",rawFloat},std::pair{"int16",rawInt16}}) {
        const auto t=Clock::now();const auto before=cpu(); const auto count=fn(reinterpret_cast<const uint8_t *>(bytes.constData()),int(bytes.size()),repeats,convert);
        results.append(QJsonObject{{"raw_type",name},{"stereo_float_conversion",convert},{"thread_cpu_s",cpu()-before},{"wall_s",elapsed(t)},{"source_frames",double(count)}});
    }
    QFile out(QString::fromLocal8Bit(argv[2]));if(!out.open(QIODevice::WriteOnly))return 6;
    out.write(QJsonDocument(QJsonObject{{"source_sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},{"repeats",repeats},{"results",results}}).toJson());
}
