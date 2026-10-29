#include "speechout.h"
#include "textscript.h"
#include <QFile>
#include <QDataStream>
#include <QJsonArray>
#include <QPointer>
#include <QRegularExpression>
#include <cmath>

SpeechOut::SpeechOut(AudioOut *audio, PlayerNet *net, QObject *parent) : AudioOut(parent), m_audio(audio), m_net(net) {
    // A normal source on the same native mixer: scene pauses need no UI timer.
    const QString file = m_silence.filePath(QStringLiteral("scene.wav"));
    QFile silence(file);
    if (silence.open(QIODevice::WriteOnly)) {
        QDataStream wav(&silence); wav.setByteOrder(QDataStream::LittleEndian);
        wav.writeRawData("RIFF", 4); wav << quint32(36 + 48000 * 3);
        wav.writeRawData("WAVEfmt ", 8); wav << quint32(16) << quint16(1) << quint16(1) << quint32(48000) << quint32(96000) << quint16(2) << quint16(16);
        wav.writeRawData("data", 4); wav << quint32(48000 * 3);
        const QByteArray zeros(48000 * 3, '\0'); wav.writeRawData(zeros.constData(), zeros.size());
        m_gapUrl = QUrl::fromLocalFile(file);
    }
    connect(audio, &AudioOut::durationChanged, this, [this](double seconds) { if (!m_text) emit durationChanged(seconds); });
    connect(audio, &AudioOut::playingChanged, this, [this](bool playing) { if (!m_text || (m_ready && playing)) emit playingChanged(playing); });
    connect(audio, &AudioOut::buffering, this, [this](bool on) { if (!m_text || m_ready) emit buffering(on); });
    connect(audio, &AudioOut::failed, this, [this](const QString &reason) { fail(reason); });
    connect(audio, &AudioOut::seeked, this, &AudioOut::seeked);
    connect(audio, &AudioOut::ended, this, [this] {
        if (!m_text) { emit ended(); return; }
        if (m_index + 1 < m_paragraphs.size()) render(m_index + 1, 0);
        else { m_target = duration(); m_ready = false; m_wants = false; emit playingChanged(false); emit ended(); }
    });
}
void SpeechOut::load(const QUrl &url, double at) {
    stop(); m_text = false; m_audio->setVolume(m_volume); m_audio->load(url, at);
}
void SpeechOut::loadText(const QString &book, int chapter, double at, const QString &voice) {
    stop(); m_text = true; m_book = book; m_chapter = chapter; m_voice = voice; m_target = at;
    if (voice.isEmpty()) { fail(QStringLiteral("Máy này chưa có giọng đọc.")); return; }
    m_voiceGain = 1;
    for (const auto &value : m_voices) {
        const auto item = value.toMap();
        if (item.value(QStringLiteral("id")).toString() != voice) continue;
        m_voiceGain = std::pow(10.0, std::min(0.0, item.value(QStringLiteral("gain_db"), item.value(QStringLiteral("gainDb"), 0)).toDouble()) / 20.0);
        if (item.value(QStringLiteral("online")).toBool() && !m_allowed.contains(item.value(QStringLiteral("provider")).toString())) {
            m_pendingConsent = true; m_pendingVoice = item;
        }
    }
    const auto generation = m_generation;
    QPointer<SpeechOut> self(this);
    m_cancel.append(m_net->requestCancelable("GET", QStringLiteral("/api/listen/books/%1/chapters/%2/text").arg(book).arg(chapter), {},
        [self, generation](int status, const QJsonObject &body) {
            if (!self || generation != self->m_generation) return;
            if (status < 200 || status >= 300) { self->fail(body.value(QStringLiteral("error")).toString(QStringLiteral("Chưa tải được chữ của chương."))); return; }
            const auto lines = TextScript::paragraphs(body.value(QStringLiteral("text")).toString());
            bool spoken = false; int firstBreak = -1;
            for (int i = 0; i < lines.size(); ++i) {
                const auto &text = lines[i];
                const bool canSpeak = TextScript::speakable(text);
                self->m_paragraphs.append({text, canSpeak ? std::max(0.5, text.size() / 14.0) : 0, {}, 1});
                if (TextScript::scene(text, true)) {
                    if (spoken && firstBreak < 0) firstBreak = i;
                } else if (canSpeak) {
                    if (firstBreak >= 0) { self->m_paragraphs[firstBreak].seconds = 1.5; self->m_paragraphs[firstBreak].url = self->m_gapUrl; }
                    firstBreak = -1; spoken = true;
                }
            }
            if (self->m_paragraphs.isEmpty()) { self->fail(QStringLiteral("Chương này chưa có chữ để đọc.")); return; }
            self->publishScript(); emit self->durationChanged(self->duration());
            self->seek(self->m_target);
        }, false));
}
void SpeechOut::render(int index, double offset) {
    while (index < m_paragraphs.size() && m_paragraphs[index].seconds == 0) ++index;
    if (index >= m_paragraphs.size()) { m_ready = m_wants = false; emit playingChanged(false); emit ended(); return; }
    m_audio->stop(); m_ready = false; m_index = index; m_target = startOf(index) + offset;
    emit buffering(true);
    const auto request = ++m_request, generation = m_generation;
    auto start = [this, index, offset] {
        m_ready = true;
        m_audio->setRate(m_rate); m_audio->setVolume(m_volume * m_paragraphs[index].gain);
        m_audio->load(m_paragraphs[index].url, std::min(offset, std::max(0.0, m_paragraphs[index].seconds - 0.01)));
        emit durationChanged(duration()); emit buffering(false); emit seeked();
        if (m_wants) m_audio->play();
        if (index + 1 < m_paragraphs.size()) fetch(index + 1, {});
    };
    if (!m_paragraphs[index].url.isEmpty()) { start(); return; }
    fetch(index, [this, request, start] { if (request == m_request) start(); });
}
void SpeechOut::fetch(int index, std::function<void()> ready) {
    while (index < m_paragraphs.size() && !TextScript::speakable(m_paragraphs[index].text)) ++index;
    if (index >= m_paragraphs.size()) return;
    if (!m_paragraphs[index].url.isEmpty()) { if (ready) ready(); return; }
    // At most one current request + one lookahead; no polling while hidden.
    // If a lookahead is still running when reached, its completion starts it.
    if (m_paragraphs[index].loading) return;
    m_paragraphs[index].loading = true;
    const auto generation = m_generation;
    QPointer<SpeechOut> self(this);
    m_cancel.append(m_net->requestCancelable("POST", QStringLiteral("/api/readaloud/clip"), {{QStringLiteral("voice"), m_voice}, {QStringLiteral("text"), m_paragraphs[index].text}, {QStringLiteral("bookId"), m_book}, {QStringLiteral("rank"), std::max(0, index - m_index)}},
        [self, generation, index, ready](int status, const QJsonObject &body) {
            if (!self || generation != self->m_generation) return;
            self->m_paragraphs[index].loading = false;
            if (status < 200 || status >= 300 || body.value(QStringLiteral("url")).toString().isEmpty()) {
                if (index == self->m_index) {
                    const QString why = body.value(QStringLiteral("reason")).toString();
                    const QStringList trouble{QStringLiteral("timeout"), QStringLiteral("rejected"), QStringLiteral("service"), QStringLiteral("auth"), QStringLiteral("quota")};
                    const QString message = why == QLatin1String("offline") ? QStringLiteral("Không có mạng - giọng đang chọn cần mạng.")
                        : trouble.contains(why) ? QStringLiteral("Giọng đang chọn đang không dùng được.")
                        : body.value(QStringLiteral("error")).toString(body.value(QStringLiteral("message")).toString(QStringLiteral("Giọng đang chọn đang không dùng được.")));
                    self->fail(message);
                }
                return;
            }
            auto &paragraph = self->m_paragraphs[index];
            paragraph.url = self->m_net->mediaUrl(body.value(QStringLiteral("url")).toString());
            paragraph.seconds = std::max(0.01, body.value(QStringLiteral("duration_ms")).toDouble() / 1000.0);
            paragraph.gain = self->m_voiceGain;
            paragraph.words = body.value(QStringLiteral("words")).toArray();
            self->publishScript(); emit self->durationChanged(self->duration());
            if (ready) ready();
            if (index == self->m_index && !self->m_ready) self->render(index, self->m_target - self->startOf(index));
        }));
}
void SpeechOut::publishScript() {
    QJsonArray segments; double at = 0;
    for (int i = 0; i < m_paragraphs.size(); ++i) {
        const auto &p = m_paragraphs[i]; QJsonArray words;
        for (const auto &value : p.words) { auto pair = value.toArray(); if (pair.size() == 2) words.append(QJsonArray{pair[0].toDouble() + at * 1000, pair[1].toDouble() + at * 1000}); }
        segments.append(QJsonObject{{QStringLiteral("text"), p.text}, {QStringLiteral("paragraph"), i},
            {QStringLiteral("kind"), TextScript::speakable(p.text) ? QStringLiteral("narration") : QStringLiteral("scene")},
            {QStringLiteral("start"), at}, {QStringLiteral("end"), at + p.seconds}, {QStringLiteral("words"), words}});
        at += p.seconds;
    }
    emit scriptReady(m_book, m_chapter, QJsonObject{{QStringLiteral("timed"), true}, {QStringLiteral("segments"), segments}});
}
void SpeechOut::play() {
    if (!m_text) { m_audio->play(); return; }
    m_wants = true;
    if (m_pendingConsent) {
        if (!m_askedConsent) { m_askedConsent = true; emit consentRequested(m_pendingVoice); }
        return;
    }
    if (m_ready) m_audio->play();
    else { emit buffering(true); if (!m_paragraphs.isEmpty()) seek(m_target); }
}
void SpeechOut::pause() { m_wants = false; m_audio->pause(); if (m_text) emit playingChanged(false); }
void SpeechOut::stop() {
    ++m_generation; ++m_request;
    const auto cancel = std::move(m_cancel); m_cancel.clear();
    for (const auto &abort : cancel) if (abort) abort();
    m_wants = m_ready = m_pendingConsent = m_askedConsent = false;
    m_audio->stop(); m_paragraphs.clear(); m_target = 0;
}
void SpeechOut::authorize(const QString &provider) {
    if (!m_pendingConsent) return;
    bool matches = false;
    for (const auto &value : m_voices) { const auto v = value.toMap(); if (v.value(QStringLiteral("id")).toString() == m_voice && v.value(QStringLiteral("provider")).toString() == provider) matches = true; }
    if (!matches) return;
    m_allowed.append(provider);
    const auto book = m_book, voice = m_voice; const int chapter = m_chapter;
    const double at = m_target; const bool wants = m_wants;
    loadText(book, chapter, at, voice); if (wants) play();
}
void SpeechOut::seek(double at) {
    if (!m_text) { m_audio->seek(at); return; }
    m_target = std::max(0.0, at);
    if (m_paragraphs.isEmpty() || m_pendingConsent) return;
    if (!m_wants) { m_audio->stop(); m_ready = false; emit seeked(); return; }
    double offset = m_target; int index = 0;
    while (index + 1 < m_paragraphs.size() && offset >= m_paragraphs[index].seconds) offset -= m_paragraphs[index++].seconds;
    render(index, offset);
}
double SpeechOut::startOf(int index) const { double seconds = 0; for (int i = 0; i < index; ++i) seconds += m_paragraphs[i].seconds; return seconds; }
double SpeechOut::position() const { return !m_text ? m_audio->position() : m_ready ? startOf(m_index) + m_audio->position() : m_target; }
double SpeechOut::duration() const { return m_text ? startOf(m_paragraphs.size()) : m_audio->duration(); }
void SpeechOut::fail(const QString &reason) { m_wants = false; m_ready = false; emit buffering(false); emit playingChanged(false); emit failed(reason); }
