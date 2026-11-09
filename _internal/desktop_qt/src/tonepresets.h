#pragma once
#include "tonecatalog.generated.h"
#include <QVariantMap>
#include <QVariantList>
#include <QUuid>
#include <cmath>
#include <algorithm>

class ToneLibrary {
    static QVariantList gains(const QVariant &v) {
        const auto input=v.toList();QVariantList result;
        for(int i=0;i<5;++i){bool ok=false;const double n=input.value(i).toDouble(&ok);result.append(ok&&std::isfinite(n)?std::clamp(n,-12.,12.):0.);}
        return result;
    }
    static QVariantMap off(){return {{QStringLiteral("id"),QStringLiteral("off")},{QStringLiteral("bands"),QVariantList{0.,0.,0.,0.,0.}}};}
    void put(const QVariantMap &s){if(scoped())books[book]=s;else shared=s;}
public:
    QVariantList mine;
    QVariantMap shared=off(),books,drafts;
    QString book;
    static QVariantList builtins(){QVariantList list;for(const auto &p:ToneCatalog::presets){QVariantList bands;for(double n:p.bands)bands.append(n);list.append(QVariantMap{{QStringLiteral("id"),QString::fromLatin1(p.id)},{QStringLiteral("label"),QString::fromLatin1(p.label)},{QStringLiteral("bands"),bands}});}return list;}
    QVariantMap preset(const QString &id) const {for(const auto &v:builtins()+mine){const auto p=v.toMap();if(p.value(QStringLiteral("id")).toString()==id)return p;}return {};}
    bool scoped() const{return !book.isEmpty()&&books.contains(book);}
    QVariantMap selected() const{return scoped()?books.value(book).toMap():shared;}
    bool dirty() const{const auto s=selected();return s.value(QStringLiteral("id")).toString().startsWith(QStringLiteral("user:"))&&s.value(QStringLiteral("bands"))!=preset(s.value(QStringLiteral("id")).toString()).value(QStringLiteral("bands"));}
    bool hasEdits() const{return !drafts.isEmpty();}
    bool prepareLeave(){if(drafts.isEmpty())return false;select(drafts.firstKey());return true;}
    void discard(){drafts.remove(selected().value(QStringLiteral("id")).toString());select(selected().value(QStringLiteral("id")).toString());}
    QVariantMap json() const{return {{QStringLiteral("mine"),mine},{QStringLiteral("shared"),shared},{QStringLiteral("books"),books},{QStringLiteral("drafts"),drafts}};}
    QVariantMap view() const {auto d=json();const auto s=selected();d.insert(QStringLiteral("selected"),s);d.insert(QStringLiteral("preset"),preset(s.value(QStringLiteral("id")).toString()));d.insert(QStringLiteral("dirty"),dirty());d.insert(QStringLiteral("hasEdits"),hasEdits());d.insert(QStringLiteral("scoped"),scoped());d.insert(QStringLiteral("builtins"),builtins());return d;}
    void read(const QVariantMap &d){
        mine.clear();for(const auto &v:d.value(QStringLiteral("mine")).toList()){auto p=v.toMap();const auto id=p.value(QStringLiteral("id")).toString(),name=p.value(QStringLiteral("name")).toString().trimmed().left(80);if(id.startsWith(QStringLiteral("user:"))&&!name.isEmpty()&&preset(id).isEmpty()){p[QStringLiteral("name")]=name;p[QStringLiteral("bands")]=gains(p.value(QStringLiteral("bands")));mine.append(p);}}
        auto selection=[this](const QVariant &v){auto s=v.toMap();const auto id=s.value(QStringLiteral("id")).toString();if(id!=QStringLiteral("draft")&&preset(id).isEmpty())return off();return QVariantMap{{QStringLiteral("id"),id},{QStringLiteral("bands"),gains(s.value(QStringLiteral("bands")))}};};
        drafts.clear();const auto edits=d.value(QStringLiteral("drafts")).toMap();for(auto i=edits.begin();i!=edits.end();++i)if(!preset(i.key()).isEmpty())drafts[i.key()]=gains(i.value());
        shared=selection(d.value(QStringLiteral("shared")));books.clear();const auto b=d.value(QStringLiteral("books")).toMap();for(auto i=b.begin();i!=b.end();++i)books[i.key()]=selection(i.value());
    }
    void scope(bool enabled){if(book.isEmpty()||enabled==scoped())return;if(enabled)books[book]=selected();else books.remove(book);}
    void select(const QString &id){const auto p=preset(id);if(!p.isEmpty())put({{QStringLiteral("id"),id},{QStringLiteral("bands"),drafts.value(id,p.value(QStringLiteral("bands")))}});}
    void edit(int i,double value){if(i<0||i>=5)return;auto s=selected();auto b=s.value(QStringLiteral("bands")).toList();b[i]=std::isfinite(value)?std::clamp(value,-12.,12.):0.;if(!s.value(QStringLiteral("id")).toString().startsWith(QStringLiteral("user:")))s[QStringLiteral("id")]=QStringLiteral("draft");s[QStringLiteral("bands")]=b;if(s.value(QStringLiteral("id")).toString().startsWith(QStringLiteral("user:"))){const auto id=s.value(QStringLiteral("id")).toString();if(preset(id).value(QStringLiteral("bands")).toList()==b)drafts.remove(id);else drafts[id]=b;}put(s);}
    QString save(const QString &name,bool overwrite=false){
        if(name.trimmed().isEmpty())return {};
        drafts.remove(selected().value(QStringLiteral("id")).toString());
        const auto s=selected();const auto old=s.value(QStringLiteral("id")).toString();const auto id=overwrite&&old.startsWith(QStringLiteral("user:"))?old:QStringLiteral("user:")+QUuid::createUuid().toString(QUuid::WithoutBraces);
        QVariantMap p{{QStringLiteral("id"),id},{QStringLiteral("name"),name.trimmed().left(80)},{QStringLiteral("bands"),s.value(QStringLiteral("bands"))}};int index=-1;for(int i=0;i<mine.size();++i)if(mine[i].toMap().value(QStringLiteral("id")).toString()==id)index=i;
        if(index<0)mine.append(p);else mine[index]=p;
        const QVariantMap selection{{QStringLiteral("id"),id},{QStringLiteral("bands"),s.value(QStringLiteral("bands"))}};
        if(shared.value(QStringLiteral("id")).toString()==id)shared=selection;
        for(auto i=books.begin();i!=books.end();++i)if(i.value().toMap().value(QStringLiteral("id")).toString()==id)i.value()=selection;
        put(selection);return id;
    }
    void rename(const QString &id,const QString &name){if(name.trimmed().isEmpty())return;for(auto &v:mine){auto p=v.toMap();if(p.value(QStringLiteral("id")).toString()==id){p[QStringLiteral("name")]=name.trimmed().left(80);v=p;}}}
    void duplicate(const QString &id,const QString &name){auto p=preset(id);if(!id.startsWith(QStringLiteral("user:"))||p.isEmpty()||name.trimmed().isEmpty())return;p[QStringLiteral("id")]=QStringLiteral("user:")+QUuid::createUuid().toString(QUuid::WithoutBraces);p[QStringLiteral("name")]=name.trimmed().left(80);mine.append(p);}
    void move(const QString &id,int to){for(qsizetype i=0;i<mine.size();++i)if(mine[i].toMap().value(QStringLiteral("id")).toString()==id){const auto p=mine.takeAt(i);mine.insert(std::clamp(to,0,int(mine.size())),p);return;}}
    QVariantMap remove(const QString &id){
        for(int i=0;i<mine.size();++i)if(mine[i].toMap().value(QStringLiteral("id")).toString()==id){
            QVariantMap token{{QStringLiteral("preset"),mine.takeAt(i)},{QStringLiteral("index"),i}},affected;
            if(shared.value(QStringLiteral("id")).toString()==id){token[QStringLiteral("shared")]=shared;shared=off();}
            for(auto b=books.begin();b!=books.end();++b)if(b.value().toMap().value(QStringLiteral("id")).toString()==id){affected[b.key()]=b.value();b.value()=off();}
            token[QStringLiteral("books")]=affected;token[QStringLiteral("draft")]=drafts.take(id);return token;
        }return {};
    }
    void undo(const QVariantMap &token){const auto p=token.value(QStringLiteral("preset")).toMap();if(p.isEmpty()||!preset(p.value(QStringLiteral("id")).toString()).isEmpty())return;mine.insert(std::clamp(token.value(QStringLiteral("index")).toInt(),0,int(mine.size())),p);if(token.value(QStringLiteral("draft")).isValid())drafts[p.value(QStringLiteral("id")).toString()]=token.value(QStringLiteral("draft"));if(token.contains(QStringLiteral("shared"))&&shared.value(QStringLiteral("id"))==QStringLiteral("off"))shared=token.value(QStringLiteral("shared")).toMap();const auto affected=token.value(QStringLiteral("books")).toMap();for(auto i=affected.begin();i!=affected.end();++i)if(books.value(i.key()).toMap().value(QStringLiteral("id"))==QStringLiteral("off"))books[i.key()]=i.value();}
};
