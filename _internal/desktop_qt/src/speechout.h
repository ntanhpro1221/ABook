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
#include <functional>

// Narration source: prerecorded audio or chapter paragraphs rendered by the
// same /script and /readaloud/clip API used by the desktop web source.
class SpeechOut final : public AudioOut {
    Q_OBJECT
    QML_NAMED_ELEMENT(Narration)
    QML_SINGLETON
public:
    static SpeechOut *create(QQmlEngine *, QJSEngine *) { QJSEngine::setObjectOwnership(s_instance, QJSEngine::CppOwnership); return s_instance; }
    static void setInstance(SpeechOut *speech) { s_instance = speech; }
    /// `nowMs`: clock for clip fetch times (tests pass a fake one).
    SpeechOut(AudioOut *audio, PlayerNet *net, QObject *parent = nullptr, std::function<qint64()> nowMs = {});
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
    /// Phần còn lại của đoạn đang nghe + các đoạn liền sau đã có clip; đoạn đang nghe chưa có: 0; cả phần còn lại của chương đã sẵn: vô hạn (không còn gì để nhường).
    double voiceAhead() const override;
    bool playing() const override { return m_text ? m_wants : m_audio->playing(); }
    Q_INVOKABLE void configure(const QVariantList &voices, const QStringList &allowed) { m_voices = voices; m_allowed = allowed; }
    Q_INVOKABLE void authorize(const QString &provider);
    Q_INVOKABLE void cancelConsent() { m_askedConsent = false; pause(); }
signals:
    void scriptReady(const QString &book, int chapter, const QJsonObject &script);
    void consentRequested(const QVariantMap &voice);
private:
    static inline SpeechOut *s_instance = nullptr;
    struct Paragraph { QString text; double seconds; QUrl url; double gain = 1; QJsonArray words; bool loading = false; qint64 sentAt = 0; };
    /// Read-ahead in seconds of audio, not paragraphs (same rule as readAheadCount in listen/readAloud.ts and the phone's ReadAheadPolicy):
    /// always MIN_BUFFER_SECONDS after the current paragraph, before any measurement and when the paragraphs ahead of a long one are all short
    /// (up to MAX_FILL_AHEAD paragraphs); a slow voice adds BUFFER_FACTOR x its p80 fetch time, up to MAX_BUFFER_SECONDS and MAX_READ_AHEAD
    /// paragraphs. At most MAX_PARALLEL requests at once (the paragraph the listener waits for always goes now); the host also queues by `rank`
    /// within its EDGE_CONNECTIONS slots.
    static constexpr double MIN_BUFFER_SECONDS = 20, MAX_BUFFER_SECONDS = 60, BUFFER_FACTOR = 2;
    static constexpr int MAX_READ_AHEAD = 8, MAX_FILL_AHEAD = 24, MAX_PARALLEL = 4, FETCH_SAMPLES = 8;
    static constexpr qint64 REAL_FETCH_MS = 250, STALL_MS = 3000;
    void prefetch();
    double bufferWanted() const;
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
    std::function<qint64()> m_now;
    QList<qint64> m_fetchMs; // real fetch times of the last few clips of the current voice
    int m_inflight = 0;
    double m_target = 0, m_rate = 1, m_volume = 0.9;
    bool m_text = false, m_ready = false, m_wants = false, m_seeking = false;
};
