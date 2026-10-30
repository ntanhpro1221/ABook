#pragma once
#include "audioout.h"
#include "playernet.h"
#include <QJSEngine>
#include <QQmlEngine>
#include <QtQml/qqmlregistration.h>
#include <QVector>
#include <QTemporaryDir>
#include <QJsonArray>
#include <QVariantList>

// Narration source: prerecorded audio or chapter paragraphs rendered by the
// same /script and /readaloud/clip API used by the desktop web source.
class SpeechOut final : public AudioOut {
    Q_OBJECT
    QML_NAMED_ELEMENT(Narration)
    QML_SINGLETON
public:
    static SpeechOut *create(QQmlEngine *, QJSEngine *) { QJSEngine::setObjectOwnership(s_instance, QJSEngine::CppOwnership); return s_instance; }
    static void setInstance(SpeechOut *speech) { s_instance = speech; }
    SpeechOut(AudioOut *audio, PlayerNet *net, QObject *parent = nullptr);
    ~SpeechOut() override { stop(); }
    void load(const QUrl &url, double at) override;
    void loadText(const QString &book, int chapter, double at, const QString &voice) override;
    void play() override;
    void pause() override;
    void stop() override;
    void seek(double at) override;
    void setRate(double rate) override { m_rate = rate; m_audio->setRate(rate); }
    void setVolume(double volume) override { m_volume = volume; m_audio->setVolume(volume * (m_text && m_ready ? m_paragraphs[m_index].gain : 1)); }
    double position() const override;
    double duration() const override;
    bool playing() const override { return m_text ? m_wants : m_audio->playing(); }
    Q_INVOKABLE void configure(const QVariantList &voices, const QStringList &allowed) { m_voices = voices; m_allowed = allowed; }
    Q_INVOKABLE void authorize(const QString &provider);
    Q_INVOKABLE void cancelConsent() { m_askedConsent = false; pause(); }
signals:
    void scriptReady(const QString &book, int chapter, const QJsonObject &script);
    void consentRequested(const QVariantMap &voice);
private:
    static inline SpeechOut *s_instance = nullptr;
    struct Paragraph { QString text; double seconds; QUrl url; double gain = 1; QJsonArray words; bool loading = false; };
    void publishScript();
    void fetch(int index, std::function<void()> ready);
    void render(int index, double offset);
    void fail(const QString &reason);
    double startOf(int index) const;
    AudioOut *m_audio;
    PlayerNet *m_net;
    QVector<Paragraph> m_paragraphs;
    QString m_book, m_voice;
    quint64 m_generation = 0, m_request = 0;
    int m_index = 0;
    int m_chapter = 0;
    QTemporaryDir m_silence;
    QUrl m_gapUrl;
    QVariantList m_voices;
    QStringList m_allowed;
    bool m_pendingConsent = false;
    bool m_askedConsent = false;
    QVariantMap m_pendingVoice;
    double m_voiceGain = 1;
    QList<std::function<void()>> m_cancel;
    double m_target = 0, m_rate = 1, m_volume = 0.9;
    bool m_text = false, m_ready = false, m_wants = false;
};
