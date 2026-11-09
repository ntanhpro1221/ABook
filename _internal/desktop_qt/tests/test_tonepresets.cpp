#ifdef _WIN32
#include <Windows.h>
#endif
#include "tonepresets.h"
#include "audiofx.h"
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
#include <QtTest>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <cstring>

class TonePresetTests:public QObject {
    Q_OBJECT
private slots:
    void editsSurviveAuditionAndReopen(){
        ToneLibrary l;l.select("clear");const auto id=l.save("First");l.edit(0,9);l.select("bright");QVERIFY(l.hasEdits());QVERIFY(!l.dirty());
        ToneLibrary copy;copy.read(l.json());QVERIFY(copy.prepareLeave());QCOMPARE(copy.selected().value("id").toString(),id);QCOMPARE(copy.selected().value("bands").toList()[0].toDouble(),9.);
        copy.discard();QVERIFY(!copy.hasEdits());QCOMPARE(copy.selected().value("bands").toList()[0].toDouble(),-4.);
    }
    void crudOrderAndUndo(){
        ToneLibrary l;l.select("clear");l.edit(0,7);QCOMPARE(l.selected().value("id").toString(),"draft");
        const auto id=l.save(" Mine ");l.rename(id,"Renamed");QCOMPARE(l.preset(id).value("name").toString(),"Renamed");
        l.duplicate(id,"Copy");const auto copy=l.mine[1].toMap().value("id").toString();l.move(copy,0);
        QCOMPARE(l.mine[0].toMap().value("id").toString(),copy);
        const auto token=l.remove(id);QCOMPARE(l.selected().value("id").toString(),"off");l.undo(token);
        QCOMPARE(l.selected().value("id").toString(),id);QCOMPARE(l.mine[1].toMap().value("id").toString(),id);
        QCOMPARE(ToneCatalog::presets[1].bands[0],-4.);
    }
    void scopePersistenceAndUndoPreservesLaterChoice(){
        ToneLibrary l;l.select("warm");l.book="a";l.scope(true);l.select("clear");const auto id=l.save("Book");
        l.book="b";QCOMPARE(l.selected().value("id").toString(),"warm");l.book="a";
        ToneLibrary copy;copy.read(l.json());copy.book="a";QCOMPARE(copy.selected().value("id").toString(),id);
        const auto token=copy.remove(id);copy.select("bright");copy.undo(token);QCOMPARE(copy.selected().value("id").toString(),"bright");
        copy.scope(false);QCOMPARE(copy.selected().value("id").toString(),"warm");
    }
    void saveDraftOverwriteAndNew(){
        ToneLibrary l;l.select("clear");l.save("First");l.edit(2,12);QVERIFY(l.dirty());QCOMPARE(l.preset(l.selected().value("id").toString()).value("bands").toList()[2].toDouble(),2.);
        l.save("First",true);QVERIFY(!l.dirty());QCOMPARE(l.mine.size(),1);l.edit(1,-12);l.save("Second");QCOMPARE(l.mine.size(),2);
        QCOMPARE(l.mine[0].toMap().value("bands").toList()[1].toDouble(),-2.);
    }
    void offIsBitExact(){
        AudioFx::Dsp dsp;AudioFx::Settings active;active.enabled=true;active.bands.fill(12);dsp.configure(active,48000);float f[]{1,-1};dsp.process(f,1);
        dsp.configure({},48000);
        for(int i=-32768;i<=32767;++i){float input[]{float(i/32768.),float(-i/32768.)};float copy[2];std::memcpy(copy,input,sizeof input);dsp.process(copy,1);QVERIFY(std::memcmp(copy,input,sizeof input)==0);}
    }
    void sharedResponseCases(){
        QFile file(QFileInfo(QString::fromUtf8(__FILE__)).dir().absoluteFilePath("../../abook/webui/assets/tone_response_cases.json"));QVERIFY(file.open(QIODevice::ReadOnly));
        const auto data=QJsonDocument::fromJson(file.readAll()).object();const auto frequencies=data["frequencies"].toArray();QCOMPARE(frequencies.size(),31);
        double worst=0;int count=0;
        for(const auto &v:data["cases"].toArray()){
            const auto c=v.toObject();const int rate=c["rate"].toInt();AudioFx::Settings s;s.enabled=c["id"].toString()!="off";
            const auto bands=c["bands"].toArray();for(int i=0;i<5;++i)s.bands[i]=bands[i].toDouble();
            const auto p=std::find_if(ToneCatalog::presets.begin(),ToneCatalog::presets.end(),[&](const auto &p){return c["id"].toString()==QString::fromLatin1(p.id);});QVERIFY(p!=ToneCatalog::presets.end());QVERIFY(p->bands==s.bands);
            for(int fi=0;fi<frequencies.size();++fi){
                const double frequency=frequencies[fi].toDouble();AudioFx::Dsp dsp;dsp.configure(s,rate);double energy=0,source=0;
                for(int i=0;i<rate;++i){const float x=float(.001*std::sin(2*std::numbers::pi*frequency*i/rate));float f[]{x,x};dsp.process(f,1);if(i>=rate/2){energy+=double(f[0])*f[0];source+=double(x)*x;}}
                const double error=std::abs(10*std::log10(energy/source)-c["db"].toArray()[fi].toDouble());worst=std::max(worst,error);++count;
                QVERIFY2(error<=data["toleranceDb"].toDouble(),qPrintable(QString("%1 %2 Hz %3 rate error=%4").arg(c["id"].toString()).arg(frequency).arg(rate).arg(error)));
            }
        }
        qInfo()<<"TONE_RESPONSE_QT measurements="<<count<<"worst_db="<<worst;
    }
};
QTEST_GUILESS_MAIN(TonePresetTests)
#include "test_tonepresets.moc"
