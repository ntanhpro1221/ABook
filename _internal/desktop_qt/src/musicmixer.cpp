#include "musicmixer.h"

#include "mixcore.h"
#include "mp3source.h"

#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QSaveFile>
#include <QtEndian>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>

#define NOMINMAX
#include <windows.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <ksmedia.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;
using Guard = std::lock_guard<std::mutex>;
using Clock = std::chrono::steady_clock;

namespace {
constexpr qint64 HEADER = 24;
constexpr qint64 CACHE_LIMIT = 300 * 1024 * 1024;
QByteArray header(int rate, quint64 frames) {
    QByteArray h(HEADER, '\0');
    std::copy_n("ABPCM001", 8, h.data());
    qToLittleEndian<quint32>(quint32(rate), h.data() + 8);
    qToLittleEndian<quint32>(2, h.data() + 12);
    qToLittleEndian<quint64>(frames, h.data() + 16);
    return h;
}
quint64 readHeader(QFile &f, int rate) {
    const QByteArray h = f.read(HEADER);
    if (h.size() != HEADER || h.first(8) != QByteArray("ABPCM001", 8) || qFromLittleEndian<quint32>(h.data() + 8) != quint32(rate)
        || qFromLittleEndian<quint32>(h.data() + 12) != 2)
        return 0;
    const quint64 n = qFromLittleEndian<quint64>(h.data() + 16);
    return n && n <= quint64((f.size() - HEADER) / 4) && quint64(f.size() - HEADER) == n * 4 ? n : 0;
}
double bounded(double seconds) { return std::isfinite(seconds) ? std::max(0.0, seconds) : 0; }
QString cacheName(const QString &dir, const QUrl &url, int rate) {
    const auto sha = QCryptographicHash::hash(url.toEncoded(), QCryptographicHash::Sha1).toHex();
    return QDir(dir).filePath(QString::fromLatin1(sha) + QString::number(rate) + QStringLiteral(".pcm"));
}
}

// Callback không giữ con trỏ chủ: Unregister có thể đụng một callback còn đang chạy.
struct DeviceNotice final : IMMNotificationClient {
    std::atomic<ULONG> refs{1};
    std::mutex mutex;
    std::function<void()> changed;
    std::atomic<bool> dirty{true};
    STDMETHODIMP QueryInterface(REFIID id, void **out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (id != __uuidof(IUnknown) && id != __uuidof(IMMNotificationClient)) return E_NOINTERFACE;
        *out = static_cast<IMMNotificationClient *>(this); AddRef(); return S_OK;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return ++refs; }
    STDMETHODIMP_(ULONG) Release() override { const ULONG n = --refs; if (!n) delete this; return n; }
    STDMETHODIMP OnDefaultDeviceChanged(EDataFlow flow, ERole role, LPCWSTR) override {
        if (flow == eRender && role == eMultimedia) {
            dirty = true;
            Guard guard(mutex);
            if (changed) changed();
        }
        return S_OK;
    }
    STDMETHODIMP OnDeviceAdded(LPCWSTR) override { return S_OK; }
    STDMETHODIMP OnDeviceRemoved(LPCWSTR) override { return S_OK; }
    STDMETHODIMP OnDeviceStateChanged(LPCWSTR, DWORD) override { return S_OK; }
    STDMETHODIMP OnPropertyValueChanged(LPCWSTR, const PROPERTYKEY) override { return S_OK; }
};

struct WasapiDevice::Impl {
    ComPtr<IMMDeviceEnumerator> enumerator;
    ComPtr<IAudioClient> client;
    ComPtr<IAudioRenderClient> render;
    ComPtr<DeviceNotice> notice;
    int rate = 48000, channels = 2;
    UINT32 capacity = 0;
    quint64 revision = 0;
    bool com = false;
    QString error;
};

WasapiDevice::WasapiDevice(std::function<void()> changed) : d(new Impl) {
    d->com = SUCCEEDED(CoInitializeEx(nullptr, COINIT_MULTITHREADED));
    d->notice.Attach(new DeviceNotice);
    d->notice->changed = std::move(changed);
    if (SUCCEEDED(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, IID_PPV_ARGS(&d->enumerator))))
        d->enumerator->RegisterEndpointNotificationCallback(d->notice.Get());
    refresh();
}
WasapiDevice::~WasapiDevice() {
    { Guard guard(d->notice->mutex); d->notice->changed = {}; }
    if (d->enumerator) d->enumerator->UnregisterEndpointNotificationCallback(d->notice.Get());
    stop();
    d->render.Reset(); d->client.Reset(); d->enumerator.Reset(); d->notice.Reset();
    if (d->com) CoUninitialize();
}
bool WasapiDevice::refresh() {
    if (!d->notice->dirty.exchange(false) && d->client) return true;
    d->error.clear();
    stop(); d->render.Reset(); d->client.Reset(); d->capacity = 0;
    ComPtr<IMMDevice> endpoint;
    if (!d->enumerator || FAILED(d->enumerator->GetDefaultAudioEndpoint(eRender, eMultimedia, &endpoint))
        || FAILED(endpoint->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void **>(d->client.GetAddressOf()))))
        return false;
    ComPtr<IAudioClient2> client2;
    AudioClientProperties props{};
    props.cbSize = sizeof(props); props.eCategory = AudioCategory_Media;
    if (FAILED(d->client.As(&client2)) || FAILED(client2->SetClientProperties(&props))) {
        d->client.Reset(); return false;
    }
    WAVEFORMATEX *format = nullptr;
    if (FAILED(d->client->GetMixFormat(&format))) { d->client.Reset(); return false; }
    // Đúng định dạng mix của endpoint; không âm thầm phát float như PCM nguyên.
    HRESULT hr = E_INVALIDARG;
    if (supportsFormat(*format)) {
        d->rate = int(format->nSamplesPerSec); d->channels = format->nChannels;
        hr = d->client->Initialize(AUDCLNT_SHAREMODE_SHARED, 0, 10000000, 0, format, nullptr);
    } else d->error = QStringLiteral("Thiết bị nhạc cần định dạng float32 với ít nhất 2 kênh.");
    CoTaskMemFree(format);
    if (FAILED(hr) || FAILED(d->client->GetBufferSize(&d->capacity)) || FAILED(d->client->GetService(IID_PPV_ARGS(&d->render)))) {
        d->render.Reset(); d->client.Reset(); d->capacity = 0; return false;
    }
    ++d->revision;
    return true;
}
bool WasapiDevice::supportsFormat(const tWAVEFORMATEX &format) {
    const bool floating = format.wFormatTag == WAVE_FORMAT_IEEE_FLOAT ||
        (format.wFormatTag == WAVE_FORMAT_EXTENSIBLE && format.cbSize >= 22 &&
         reinterpret_cast<const WAVEFORMATEXTENSIBLE &>(format).SubFormat == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT);
    return floating && format.wBitsPerSample == 32 && format.nChannels >= 2;
}
QString WasapiDevice::error() const { return d->error; }
int WasapiDevice::rate() const { return d->rate; }
quint64 WasapiDevice::revision() const { return d->revision; }
bool WasapiDevice::start() {
    const bool ok = d->client && SUCCEEDED(d->client->Start());
    if (!ok) d->notice->dirty = true;
    return ok;
}
void WasapiDevice::stop() { if (d->client) d->client->Stop(); }
void WasapiDevice::reset() { if (d->client) d->client->Reset(); }
size_t WasapiDevice::bufferFrames() const { return d->capacity; }
size_t WasapiDevice::padding() {
    UINT32 n = 0;
    if (d->client && FAILED(d->client->GetCurrentPadding(&n))) d->notice->dirty = true;
    return n;
}
bool WasapiDevice::write(const float *stereo, size_t frames) {
    BYTE *bytes = nullptr;
    if (!d->render || FAILED(d->render->GetBuffer(UINT32(frames), &bytes))) { d->notice->dirty = true; return false; }
    float *out = reinterpret_cast<float *>(bytes);
    if (d->channels == 2) std::copy_n(stereo, frames * 2, out);
    else {
        std::fill_n(out, frames * d->channels, 0.0f);
        for (size_t i = 0; i < frames; ++i) { out[i * d->channels] = stereo[i * 2]; out[i * d->channels + 1] = stereo[i * 2 + 1]; }
    }
    const bool ok = SUCCEEDED(d->render->ReleaseBuffer(UINT32(frames), 0));
    if (!ok) d->notice->dirty = true;
    return ok;
}

struct MixVoiceState {
    std::mutex mutex;
    MixVoice *owner = nullptr;
    quint64 generation = 0;
    QUrl url;
    QByteArray bytes;
    bool opening = false, fetching = false, haveBytes = false, ready = false;
    bool want = false, playing = false, loop = false, buffering = false, seeking = false, reposition = false, flush = false;
    bool eof = false, volumeDirty = true;
    double target = 0, volume = 0, duration = 0;
    int rate = 48000;
    quint64 length = 0, origin = 0, mixed = 0, heard = 0, limit = 0;
    struct Span { quint64 device, voice, frames; };
    std::deque<Span> spans;
    MixCore::Ramp ramp;
    std::unique_ptr<MixCore::Ring> ring;
    std::unique_ptr<QFile> file;
    float first[2] = {};
    quint64 frameAt(quint64 consumed) const {
        quint64 frame = origin + consumed;
        if (loop && length) return frame % length;
        // Vừa thôi lặp ở vòng thứ hai trở đi: vẫn báo vị trí trong vòng cuối, không nhảy thẳng tới duration.
        const quint64 cycle = origin + limit > length ? origin + limit - length : 0;
        frame = frame >= cycle ? frame - cycle : (length ? frame % length : 0);
        return std::min(frame, length);
    }
};

struct MusicMixer::Impl {
    MusicMixer *owner;
    QString cacheDir;
    QNetworkAccessManager network;
    struct Download { QNetworkReply *reply; std::vector<std::pair<std::weak_ptr<MixVoiceState>, quint64>> waiters; };
    QHash<QUrl, Download> downloads;
    std::mutex voicesMutex, engineMutex, waitMutex;
    std::vector<std::shared_ptr<MixVoiceState>> voices;
    std::unique_ptr<MixDevice> device;
    std::thread mixerThread, readerThread;
    std::condition_variable mixCv, readerCv;
    bool quit = false, mixDirty = false, readerDirty = false, initialized = false;
    bool threaded = false, active = false, running = false;
    std::atomic<bool> relaxed{false};
    std::atomic<int> rate{48000};
    std::atomic<quint64> decodes{0};
    quint64 written = 0, played = 0;
    quint64 deviceRevision = 0;
    Clock::time_point sampled = Clock::now();

    Impl(MusicMixer *q, QString dir) : owner(q), cacheDir(std::move(dir)) {}
    std::vector<std::shared_ptr<MixVoiceState>> snapshot() { Guard guard(voicesMutex); return voices; }
    quint64 cursor() const {
        if (!threaded || !running) return played;
        const double elapsed = std::chrono::duration<double>(Clock::now() - sampled).count();
        return std::min(written, played + quint64(elapsed * rate));
    }
    quint64 heard(MixVoiceState &s, quint64 cursor) const {
        quint64 result = s.heard;
        for (const auto &span : s.spans) {
            if (cursor <= span.device) break;
            result = span.voice + std::min(span.frames, cursor - span.device);
        }
        return result;
    }
    void trim() {
        QDir dir(cacheDir); dir.mkpath(QStringLiteral("."));
        auto files = dir.entryInfoList({QStringLiteral("*.pcm")}, QDir::Files, QDir::Time | QDir::Reversed);
        qint64 total = 0;
        for (const auto &f : files) total += f.size();
        for (const auto &f : files) {
            if (total <= CACHE_LIMIT) break;
            if (QFile::remove(f.absoluteFilePath())) total -= f.size();
        }
    }
    void begin(bool threads) {
        threaded = threads;
        if (!threads) { rate = device->rate(); deviceRevision = device->revision(); initialized = true; trim(); return; }
        mixerThread = std::thread([this] {
            if (!device) device = std::make_unique<WasapiDevice>([this] { owner->wake(); });
            rate = device->rate();
            deviceRevision = device->revision();
            { Guard guard(waitMutex); initialized = true; } mixCv.notify_all();
            std::unique_lock<std::mutex> wait(waitMutex);
            while (!quit) {
                if (!active) mixCv.wait(wait, [this] { return quit || mixDirty; });
                else mixCv.wait_for(wait, std::chrono::milliseconds(relaxed ? 250 : 50), [this] { return quit || mixDirty; });
                if (quit) break;
                mixDirty = false; wait.unlock();
                const size_t lead = size_t(rate) * (relaxed ? 600 : 200) / 1000;
                owner->service(lead); // service giới hạn theo padding; test truyền số khung chính xác.
                wait.lock();
            }
            wait.unlock();
            device->stop(); device->reset(); device.reset(); // COM được nhả trên chính luồng tạo nó.
        });
        { std::unique_lock<std::mutex> wait(waitMutex); mixCv.wait(wait, [this] { return initialized; }); }
        readerThread = std::thread([this] {
            trim();
            std::unique_lock<std::mutex> wait(waitMutex);
            while (!quit) {
                readerCv.wait(wait, [this] { return quit || readerDirty; });
                if (quit) break;
                readerDirty = false; wait.unlock(); owner->serviceReader(); wait.lock();
            }
        });
    }
};

MusicMixer::MusicMixer(const QString &cacheDir, QObject *parent) : QObject(parent), d(new Impl(this, cacheDir)) { d->begin(true); }
MusicMixer::MusicMixer(std::unique_ptr<MixDevice> device, const QString &cacheDir, bool threaded, QObject *parent)
    : QObject(parent), d(new Impl(this, cacheDir)) { d->device = std::move(device); d->begin(threaded); }
MusicMixer::~MusicMixer() {
    { Guard guard(d->waitMutex); d->quit = true; } d->mixCv.notify_all(); d->readerCv.notify_all();
    if (d->mixerThread.joinable()) d->mixerThread.join();
    if (d->readerThread.joinable()) d->readerThread.join();
    for (auto &download : d->downloads) { download.reply->disconnect(this); download.reply->abort(); }
}
int MusicMixer::rate() const { return d->rate; }
quint64 MusicMixer::decodeCount() const { return d->decodes; }
QString MusicMixer::cachePath(const QUrl &url) const {
    return cacheName(d->cacheDir, url, rate());
}
quint64 MusicMixer::cacheFrames(const QString &path, int rate) {
    QFile f(path); return f.open(QIODevice::ReadOnly) ? readHeader(f, rate) : 0;
}
void MusicMixer::setRelaxed(bool relaxed) { if (d->relaxed.exchange(relaxed) != relaxed) wake(); }
void MusicMixer::wake(bool reader) {
    { Guard guard(d->waitMutex); if (reader) d->readerDirty = true; else d->mixDirty = true; }
    if (reader) d->readerCv.notify_one(); else d->mixCv.notify_one();
}
void MusicMixer::post(const std::shared_ptr<MixVoiceState> &state, std::function<void(MixVoice *)> event) {
    const quint64 generation = state->generation; // caller giữ khoá voice
    QMetaObject::invokeMethod(this, [weak = std::weak_ptr<MixVoiceState>(state), generation, event = std::move(event)] {
        const auto s = weak.lock();
        if (!s) return;
        MixVoice *owner = nullptr;
        { Guard guard(s->mutex); if (s->generation == generation) owner = s->owner; }
        if (owner) event(owner);
    }, Qt::QueuedConnection);
}
void MusicMixer::fetch(const std::shared_ptr<MixVoiceState> &state, quint64 generation) {
    QUrl url;
    { Guard guard(state->mutex); if (state->generation != generation) return; url = state->url; }
    auto it = d->downloads.find(url);
    if (it != d->downloads.end()) { it->waiters.emplace_back(state, generation); return; }
    QNetworkRequest request(url);
    request.setTransferTimeout(30000);
    auto *reply = d->network.get(request);
    d->downloads.insert(url, {reply, {{state, generation}}});
    connect(reply, &QNetworkReply::finished, this, [this, reply, url] {
        const auto download = d->downloads.take(url);
        const QByteArray bytes = reply->readAll();
        const QString error = reply->error() == QNetworkReply::NoError ? QString() : reply->errorString();
        reply->deleteLater();
        for (const auto &waiter : download.waiters) {
            const auto s = waiter.first.lock(); if (!s) continue;
            Guard guard(s->mutex);
            if (s->generation != waiter.second) continue;
            if (!error.isEmpty()) {
                s->opening = s->want = false;
                post(s, [error](MixVoice *v) { emit v->failed(error); });
            } else { s->bytes = bytes; s->haveBytes = true; }
        }
        wake(true); wake();
    });
}

void MusicMixer::serviceReader() {
    for (const auto &s : d->snapshot()) {
        quint64 generation;
        bool opening, haveBytes;
        QByteArray bytes;
        QUrl url;
        int outRate;
        { Guard guard(s->mutex); outRate = s->rate; generation = s->generation; opening = s->opening; haveBytes = s->haveBytes; bytes = s->bytes; url = s->url; }
        if (opening) {
            const QString path = cacheName(d->cacheDir, url, outRate);
            auto file = std::make_unique<QFile>(path);
            quint64 frames = file->open(QIODevice::ReadOnly) ? readHeader(*file, outRate) : 0;
            QString error;
            if (!frames && !haveBytes) {
                Guard guard(s->mutex);
                if (s->generation == generation && !s->fetching) {
                    s->fetching = true;
                    QMetaObject::invokeMethod(this, [this, s, generation] { fetch(s, generation); }, Qt::QueuedConnection);
                }
                continue;
            }
            if (!frames) {
                file->close();
                Mp3Source source(outRate);
                QSaveFile cache(path);
                if (!source.open(bytes)) error = QStringLiteral("Không đọc được tệp nhạc mp3.");
                else if (!cache.open(QIODevice::WriteOnly) || cache.write(header(outRate, 0)) != HEADER) error = cache.errorString();
                else {
                    ++d->decodes;
                    std::vector<float> block;
                    for (;;) {
                        { Guard guard(s->mutex); if (s->generation != generation) break; }
                        block.clear();
                        const size_t n = source.read(block, 8192);
                        if (!n) break;
                        QByteArray pcm(qsizetype(n * 4), Qt::Uninitialized);
                        for (size_t i = 0; i < n * 2; ++i) {
                            const auto sample = qint16(std::clamp(std::lround(block[i] * 32768.0f), -32768L, 32767L));
                            qToLittleEndian<qint16>(sample, pcm.data() + i * 2);
                        }
                        if (cache.write(pcm) != pcm.size()) { error = cache.errorString(); break; }
                        frames += n;
                    }
                    bool current;
                    { Guard guard(s->mutex); current = s->generation == generation; }
                    if (!current) continue;
                    if (error.isEmpty() && (!frames || !cache.seek(0) || cache.write(header(outRate, frames)) != HEADER || !cache.commit()))
                        error = QStringLiteral("Không lưu được bộ đệm nhạc: ") + cache.errorString();
                }
                if (error.isEmpty() && (!file->open(QIODevice::ReadOnly) || readHeader(*file, outRate) != frames))
                    error = QStringLiteral("Bộ đệm nhạc bị thiếu dữ liệu.");
            }
            Guard guard(s->mutex);
            if (s->generation != generation || outRate != rate()) continue;
            s->bytes.clear(); s->haveBytes = s->opening = false;
            if (!error.isEmpty()) {
                s->want = false;
                post(s, [error](MixVoice *v) { emit v->failed(error); });
                wake(); continue;
            }
            s->file = std::move(file); s->length = frames; s->rate = outRate;
            s->file->seek(HEADER);
            const QByteArray first = s->file->read(4);
            for (int c = 0; c < 2; ++c) s->first[c] = qFromLittleEndian<qint16>(first.constData() + c * 2) / 32768.0f;
            s->duration = double(frames) / outRate;
            s->ring = std::make_unique<MixCore::Ring>(size_t(outRate) * 4);
            s->ready = true; s->reposition = true;
            post(s, [duration = s->duration](MixVoice *v) { emit v->durationChanged(duration); });
        }
        Guard guard(s->mutex);
        if (!s->ready || !s->file || !s->ring) continue;
        if (s->reposition) {
            s->origin = std::min(s->length, quint64(std::llround(bounded(s->target) * s->rate)));
            s->limit = s->length - s->origin;
            s->file->seek(HEADER + qint64(s->origin) * 4);
            s->ring->clear(); s->mixed = s->heard = 0; s->spans.clear(); s->eof = false; s->reposition = false;
            if (s->seeking) { s->seeking = false; post(s, [](MixVoice *v) { emit v->seeked(); }); }
        }
        // Đọc trước hai giây; việc lấp vòng đệm không đánh thức giao diện.
        while (s->ring->writable() >= 2) {
            const qint64 n = qint64(std::min<size_t>(s->ring->writable() / 2, 16384));
            const quint64 at = quint64((s->file->pos() - HEADER) / 4);
            const QByteArray pcm = s->file->read(n * 4);
            if (pcm.isEmpty()) {
                if (s->file->error() != QFileDevice::NoError) {
                    s->want = s->ready = false;
                    const QString error = s->file->errorString();
                    post(s, [error](MixVoice *v) { emit v->failed(error); }); break;
                }
                if (s->loop && s->length) { s->file->seek(HEADER); continue; }
                s->eof = true; break;
            }
            std::vector<float> block(size_t(pcm.size() / 2));
            for (size_t i = 0; i < block.size(); ++i) block[i] = qFromLittleEndian<qint16>(pcm.constData() + i * 2) / 32768.0f;
            // MP3 bỏ padding vẫn có thể khác biên (fixture: 0,078 > bước lớn nhất 0,049).
            // Vuốt 5 ms cuối về mẫu đầu khi lặp; đầu vòng sau vẫn đúng từng mẫu của cache, không chèn khung.
            const quint64 seam = std::min<quint64>(s->length, quint64(s->rate / 200));
            if (s->loop && seam > 1) {
                for (size_t i = 0; i < block.size() / 2; ++i) {
                    if (at + i < s->length - seam) continue;
                    const float w = float(0.5 - 0.5 * std::cos(3.14159265358979323846 * double(at + i - (s->length - seam)) / double(seam - 1)));
                    for (size_t c = 0; c < 2; ++c) block[i * 2 + c] += (s->first[c] - block[i * 2 + c]) * w;
                }
            }
            s->ring->write(block.data(), block.size());
        }
    }
    wake();
}

void MusicMixer::service(size_t frames) {
    Guard engine(d->engineMutex);
    const auto voices = d->snapshot();
    const int oldRate = rate();
    const quint64 oldCursor = d->cursor();
    if (!d->device->refresh()) {
        d->running = false;
        const QString error = d->device->error();
        if (!error.isEmpty()) {
            d->device->stop(); d->device->reset();
            d->written = d->played = 0;
            for (const auto &s : voices) {
                Guard guard(s->mutex);
                if (!s->opening && !s->ready && !s->want && !s->playing) continue;
                ++s->generation; // Discard queued readiness and in-flight reader results.
                const bool playing = s->playing, buffering = s->buffering;
                s->opening = s->fetching = s->haveBytes = s->ready = s->want = s->playing = s->buffering = false;
                s->bytes.clear(); s->ring.reset(); s->file.reset(); s->spans.clear();
                post(s, [error, playing, buffering](MixVoice *v) {
                    if (playing) emit v->playingChanged(false);
                    if (buffering) emit v->buffering(false);
                    emit v->failed(error);
                });
            }
            d->active = false; return;
        }
        bool wants = false;
        for (const auto &s : voices) { Guard guard(s->mutex); wants |= s->want && s->ready; }
        d->active = wants; return;
    }
    if (d->deviceRevision != d->device->revision() || oldRate != d->device->rate()) {
        // Công bố tần số trước generation mới; reader chụp cả hai dưới khoá voice, không ghép nhầm cache cũ với tần số mới.
        d->rate = d->device->rate();
        // Chuyển tai nghe có thể đổi tần số: cache/ring cũ tuyệt đối không được đọc ở tần số mới.
        for (const auto &s : voices) {
            Guard guard(s->mutex);
            if (s->url.isEmpty()) continue;
            const quint64 heard = d->heard(*s, oldCursor);
            if (!s->reposition && s->ready) {
                s->target = double(s->frameAt(heard)) / oldRate;
            }
            s->reposition = true; s->spans.clear();
            if (oldRate != d->device->rate()) {
                ++s->generation; s->ready = false; s->opening = true; s->fetching = s->haveBytes = false;
                s->rate = rate();
                s->ring.reset(); s->file.reset();
            }
        }
        d->deviceRevision = d->device->revision();
        d->rate = d->device->rate(); d->written = d->played = 0; d->running = false; wake(true);
    }
    size_t padding = d->device->padding();
    d->played = d->written - std::min<quint64>(padding, d->written); d->sampled = Clock::now();
    bool any = false, flush = false;
    int wants = 0;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        while (!s->spans.empty() && s->spans.front().device + s->spans.front().frames <= d->played) {
            s->heard = s->spans.front().voice + s->spans.front().frames; s->spans.pop_front();
        }
        if (s->want && s->ready) { ++wants; flush |= s->flush; }
        s->flush = false;
        if (s->want && s->ready && !s->reposition && !s->loop && s->mixed >= s->limit && s->spans.empty()) {
            s->want = s->playing = false;
            post(s, [](MixVoice *v) { emit v->playingChanged(false); emit v->ended(); });
        }
        any |= s->want && s->ready;
    }
    if (!any || (flush && wants == 1)) {
        const quint64 resetCursor = d->cursor();
        d->device->stop(); d->device->reset(); d->running = false;
        d->written = d->played = 0;
        for (const auto &s : voices) {
            Guard guard(s->mutex);
            if (!s->spans.empty()) {
                // Reset bỏ tiếng chưa ra loa: lần phát sau đọc lại từ chỗ đã nghe, không nhảy 600 ms.
                if (!s->reposition) {
                    s->target = double(s->frameAt(d->heard(*s, resetCursor))) / s->rate;
                    s->reposition = true;
                }
                s->spans.clear(); wake(true);
            }
        }
        padding = 0;
        if (!any) { d->active = false; return; }
    }
    d->active = any;
    // Luồng thật truyền lead, bộ thử truyền đúng số khung cần trộn.
    if (d->threaded) frames = frames > padding ? frames - padding : 0;
    frames = std::min(frames, d->device->bufferFrames() - std::min(padding, d->device->bufferFrames()));
    if (!frames) return;
    std::vector<float> out(frames * 2, 0), block(frames * 2, 0);
    std::vector<std::pair<std::shared_ptr<MixVoiceState>, quint64>> began;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        if (!s->want || !s->ready || s->reposition) continue;
        if (s->volumeDirty) { s->ramp.set(float(AudioOut::effectiveVolume(s->volume)), size_t(rate()) / 20); s->volumeDirty = false; }
        size_t n = frames;
        if (!s->loop) n = size_t(std::min<quint64>(n, s->limit - std::min(s->limit, s->mixed)));
        std::fill(block.begin(), block.end(), 0.0f);
        const size_t got = s->ring->read(block.data(), n * 2) / 2;
        const bool buffering = got < n && !s->eof;
        if (s->buffering != buffering) { s->buffering = buffering; post(s, [buffering](MixVoice *v) { emit v->buffering(buffering); }); }
        s->ramp.mixInto(out.data(), block.data(), frames, 2);
        if (got) {
            s->spans.push_back({d->written, s->mixed, got}); s->mixed += got;
            if (!s->playing) began.emplace_back(s, s->generation);
        }
        if (s->ring->readable() < size_t(rate()) * 2 && !s->eof) wake(true);
    }
    if (!d->device->write(out.data(), frames)) { d->running = false; return; }
    d->written += frames;
    if (!d->running) d->running = d->device->start();
    if (d->running) for (const auto &entry : began) {
        const auto &s = entry.first;
        Guard guard(s->mutex);
        if (s->generation == entry.second && s->want && !s->playing) {
            s->playing = true; post(s, [](MixVoice *v) { emit v->playingChanged(true); });
        }
    }
}

double MusicMixer::position(const std::shared_ptr<MixVoiceState> &s) const {
    Guard engine(d->engineMutex); Guard guard(s->mutex);
    if (s->seeking || s->reposition || !s->ready) return s->target;
    return double(s->frameAt(d->heard(*s, d->cursor()))) / s->rate;
}

MixVoice::MixVoice(MusicMixer *mixer, QObject *parent) : AudioOut(parent), m_mixer(mixer), m_state(std::make_shared<MixVoiceState>()) {
    m_state->owner = this;
    m_state->rate = mixer->rate();
    Guard guard(mixer->d->voicesMutex); mixer->d->voices.push_back(m_state);
}
MixVoice::~MixVoice() {
    stop();
    { Guard guard(m_state->mutex); m_state->owner = nullptr; }
    Guard guard(m_mixer->d->voicesMutex);
    auto &voices = m_mixer->d->voices; voices.erase(std::remove(voices.begin(), voices.end(), m_state), voices.end());
}
void MixVoice::load(const QUrl &url, double startSeconds) {
    stop();
    { Guard guard(m_state->mutex); m_state->url = url; m_state->rate = m_mixer->rate(); m_state->target = bounded(startSeconds); m_state->opening = true; }
    m_mixer->wake(true);
}
void MixVoice::play() { { Guard guard(m_state->mutex); if (!m_state->url.isEmpty()) m_state->want = true; } m_mixer->wake(true); m_mixer->wake(); }
void MixVoice::pause() {
    const double at = position();
    { Guard guard(m_state->mutex);
      m_state->want = false;
      m_state->target = at; m_state->reposition = true;
      if (m_state->playing) { m_state->playing = false; m_mixer->post(m_state, [](MixVoice *v) { emit v->playingChanged(false); }); }
    }
    m_mixer->wake();
}
void MixVoice::stop() {
    { Guard guard(m_state->mutex);
      ++m_state->generation; m_state->url.clear(); m_state->bytes.clear();
      m_state->opening = m_state->fetching = m_state->haveBytes = m_state->ready = m_state->want = m_state->playing = false;
      m_state->buffering = m_state->seeking = m_state->reposition = m_state->eof = m_state->flush = false;
      m_state->ring.reset(); m_state->file.reset(); m_state->spans.clear();
      m_state->duration = m_state->target = 0; m_state->mixed = m_state->heard = m_state->origin = m_state->length = 0;
    }
    // Huỷ tải khi không phần tử nào còn chờ; nguồn chung vẫn được giữ cho phần tử khác.
    for (auto it = m_mixer->d->downloads.begin(); it != m_mixer->d->downloads.end();) {
        auto &waiters = it->waiters;
        waiters.erase(std::remove_if(waiters.begin(), waiters.end(), [this](const auto &w) {
            const auto s = w.first.lock(); return !s || s == m_state;
        }), waiters.end());
        if (waiters.empty()) {
            auto *reply = it->reply; it = m_mixer->d->downloads.erase(it);
            reply->disconnect(m_mixer); reply->abort(); reply->deleteLater();
        } else ++it;
    }
    m_mixer->wake();
}
void MixVoice::seek(double seconds) {
    { Guard guard(m_state->mutex); m_state->target = bounded(seconds); m_state->seeking = m_state->reposition = m_state->flush = true; }
    m_mixer->wake(true); m_mixer->wake();
}
void MixVoice::setVolume(double volume) { Guard guard(m_state->mutex); m_state->volume = effectiveVolume(volume); m_state->volumeDirty = true; }
void MixVoice::preload() { m_mixer->wake(true); }
void MixVoice::setLoop(bool loop) {
    { Guard guard(m_state->mutex);
      if (!loop && m_state->loop && m_state->length) {
          const quint64 at = (m_state->origin + m_state->mixed) % m_state->length;
          m_state->limit = m_state->mixed + (at || !m_state->mixed ? m_state->length - at : 0);
      }
      m_state->loop = loop; if (loop) m_state->eof = false;
    }
    m_mixer->wake(true);
}
double MixVoice::position() const { return m_mixer->position(m_state); }
double MixVoice::duration() const { Guard guard(m_state->mutex); return m_state->duration; }
bool MixVoice::playing() const { Guard guard(m_state->mutex); return m_state->playing; }
