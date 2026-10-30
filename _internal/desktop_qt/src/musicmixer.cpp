#include "musicmixer.h"

#include "mixcore.h"
#include "mp3source.h"
#include "mfsource.h"
#include "streamsource.h"
#include "timestretch.h"

#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QSaveFile>
#include <QtEndian>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>

#define NOMINMAX
#include <windows.h>
#include <initguid.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <ksmedia.h>
#include <functiondiscoverykeys_devpkey.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;
using Guard = std::lock_guard<std::mutex>;
using Clock = std::chrono::steady_clock;

namespace {
constexpr qint64 HEADER = 24;
constexpr qint64 CACHE_LIMIT = 300 * 1024 * 1024;
enum class Format { Unknown, Mp3, Mf };
Format formatOf(const QByteArray &data) {
    // URL của host không có đuôi tệp; container phải được nhận trước khi dò sync MP3.
    if ((data.size() >= 12 && data.startsWith("RIFF") && data.mid(8, 4) == "WAVE") ||
        data.startsWith("fLaC") || data.startsWith("OggS") || (data.size() >= 8 && data.mid(4, 4) == "ftyp"))
        return Format::Mf;
    if (data.startsWith("ID3")) return Format::Mp3;
    for (qsizetype i = 0; i + 1 < std::min<qsizetype>(data.size(), 64); ++i)
        if (quint8(data[i]) == 0xff && (quint8(data[i + 1]) & 0xe0) == 0xe0) return Format::Mp3;
    return Format::Unknown;
}
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
    QString endpointId;
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
    void invalidate(LPCWSTR id) {
        Guard guard(mutex);
        if (endpointId != QString::fromWCharArray(id)) return;
        dirty = true; if (changed) changed();
    }
    STDMETHODIMP OnDeviceStateChanged(LPCWSTR id, DWORD) override { invalidate(id); return S_OK; }
    STDMETHODIMP OnPropertyValueChanged(LPCWSTR id, const PROPERTYKEY key) override {
        if (IsEqualPropertyKey(key, PKEY_AudioEngine_DeviceFormat)) invalidate(id);
        return S_OK;
    }
};

struct WasapiDevice::Impl {
    ComPtr<IMMDeviceEnumerator> enumerator;
    ComPtr<IAudioClient> client;
    ComPtr<IAudioRenderClient> render;
    ComPtr<DeviceNotice> notice;
    int rate = 48000, channels = 2;
    int bits = 32;
    bool floating = true;
    UINT32 capacity = 0;
    quint64 revision = 0;
    bool com = false;
    HANDLE pull = nullptr; // engine báo mỗi lần kéo một chu kỳ (luồng event-driven)
    QString error;
    QString selected;
};

WasapiDevice::WasapiDevice(std::function<void()> changed) : d(new Impl) {
    d->com = SUCCEEDED(CoInitializeEx(nullptr, COINIT_MULTITHREADED));
    d->pull = CreateEventW(nullptr, FALSE, FALSE, nullptr);
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
    if (d->pull) CloseHandle(d->pull);
    if (d->com) CoUninitialize();
}
bool WasapiDevice::refresh() {
    if (!d->notice->dirty.exchange(false) && d->client) return true;
    if (openOutput(d->selected)) return true;
    if (!d->selected.isEmpty() && openOutput({})) return true;
    stop(); d->render.Reset(); d->client.Reset(); d->capacity = 0;
    return false;
}
bool WasapiDevice::selectOutput(const QString &id) {
    if (id == d->selected && d->client) return true;
    return openOutput(id); // Failure leaves the old client, cursor and selection intact.
}
QString WasapiDevice::outputId() const { return d->selected; }
QVariantList WasapiDevice::outputs() const {
    QVariantList result{QVariantMap{{QStringLiteral("id"), QString()}, {QStringLiteral("name"), QStringLiteral("Mặc định")}}};
    ComPtr<IMMDeviceCollection> endpoints;
    if (!d->enumerator || FAILED(d->enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &endpoints))) return result;
    UINT count = 0; endpoints->GetCount(&count);
    for (UINT i = 0; i < count; ++i) {
        ComPtr<IMMDevice> endpoint; ComPtr<IPropertyStore> properties;
        LPWSTR id = nullptr;
        if (FAILED(endpoints->Item(i, &endpoint)) || FAILED(endpoint->GetId(&id))) continue;
        const QString key = QString::fromWCharArray(id); CoTaskMemFree(id);
        PROPVARIANT name; PropVariantInit(&name);
        QString title = key;
        if (SUCCEEDED(endpoint->OpenPropertyStore(STGM_READ, &properties)) && SUCCEEDED(properties->GetValue(PKEY_Device_FriendlyName, &name)) && name.vt == VT_LPWSTR)
            title = QString::fromWCharArray(name.pwszVal);
        PropVariantClear(&name);
        result.append(QVariantMap{{QStringLiteral("id"), key}, {QStringLiteral("name"), title}});
    }
    return result;
}
bool WasapiDevice::openOutput(const QString &selected) {
    d->error.clear();
    ComPtr<IMMDevice> endpoint;
    ComPtr<IAudioClient> client;
    ComPtr<IAudioRenderClient> render;
    UINT32 capacity = 0;
    if (!d->enumerator || FAILED(selected.isEmpty() ? d->enumerator->GetDefaultAudioEndpoint(eRender, eMultimedia, &endpoint)
        : d->enumerator->GetDevice(reinterpret_cast<LPCWSTR>(selected.utf16()), &endpoint))
        || FAILED(endpoint->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void **>(client.GetAddressOf()))))
        return false;
    ComPtr<IAudioClient2> client2;
    AudioClientProperties props{};
    props.cbSize = sizeof(props); props.eCategory = AudioCategory_Media;
    if (FAILED(client.As(&client2)) || FAILED(client2->SetClientProperties(&props))) {
        return false;
    }
    WAVEFORMATEX *format = nullptr;
    if (FAILED(client->GetMixFormat(&format))) return false;
    // Đúng định dạng mix của endpoint; không âm thầm phát float như PCM nguyên.
    HRESULT hr = E_INVALIDARG;
    if (supportsFormat(*format)) {
        // Engine pull event belongs to the new client, before publishing the selected endpoint.
        hr = client->Initialize(AUDCLNT_SHAREMODE_SHARED, d->pull ? AUDCLNT_STREAMFLAGS_EVENTCALLBACK : 0, 10000000, 0, format, nullptr);
        if (SUCCEEDED(hr) && d->pull) hr = client->SetEventHandle(d->pull);
    } else d->error = QStringLiteral("Thiết bị cần định dạng float32 hoặc PCM16/32.");
    if (FAILED(hr) || FAILED(client->GetBufferSize(&capacity)) || FAILED(client->GetService(IID_PPV_ARGS(&render)))) {
        CoTaskMemFree(format); return false;
    }
    stop(); d->render = render; d->client = client; d->capacity = capacity;
    d->rate = int(format->nSamplesPerSec); d->channels = format->nChannels; d->bits = format->wBitsPerSample;
    d->floating = format->wFormatTag == WAVE_FORMAT_IEEE_FLOAT ||
        (format->wFormatTag == WAVE_FORMAT_EXTENSIBLE && reinterpret_cast<WAVEFORMATEXTENSIBLE *>(format)->SubFormat == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT);
    CoTaskMemFree(format);
    d->selected = selected;
    LPWSTR id = nullptr;
    if (SUCCEEDED(endpoint->GetId(&id))) {
        { Guard guard(d->notice->mutex); d->notice->endpointId = QString::fromWCharArray(id); }
        CoTaskMemFree(id);
    }
    d->notice->dirty = false;
    ++d->revision;
    return true;
}
bool WasapiDevice::supportsFormat(const tWAVEFORMATEX &format) {
    const bool floating = format.wFormatTag == WAVE_FORMAT_IEEE_FLOAT ||
        (format.wFormatTag == WAVE_FORMAT_EXTENSIBLE && format.cbSize >= 22 &&
         reinterpret_cast<const WAVEFORMATEXTENSIBLE &>(format).SubFormat == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT);
    const bool integer = format.wFormatTag == WAVE_FORMAT_PCM ||
        (format.wFormatTag == WAVE_FORMAT_EXTENSIBLE && format.cbSize >= 22 &&
         reinterpret_cast<const WAVEFORMATEXTENSIBLE &>(format).SubFormat == KSDATAFORMAT_SUBTYPE_PCM);
    return format.nChannels >= 1 && ((floating && format.wBitsPerSample == 32) ||
        (integer && (format.wBitsPerSample == 16 || format.wBitsPerSample == 32)));
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
void WasapiDevice::awaitPull(int maxMs) {
    if (!d->client || !d->pull) return;
    ResetEvent(d->pull);
    WaitForSingleObject(d->pull, DWORD(maxMs));
}
size_t WasapiDevice::bufferFrames() const { return d->capacity; }
size_t WasapiDevice::padding() {
    UINT32 n = 0;
    if (d->client && FAILED(d->client->GetCurrentPadding(&n))) d->notice->dirty = true;
    return n;
}
bool WasapiDevice::write(const float *stereo, size_t frames) {
    BYTE *bytes = nullptr;
    if (!d->render || FAILED(d->render->GetBuffer(UINT32(frames), &bytes))) { d->notice->dirty = true; return false; }
    if (d->floating && d->channels == 2) std::copy_n(stereo, frames * 2, reinterpret_cast<float *>(bytes));
    else {
        for (size_t i = 0; i < frames; ++i) for (int c = 0; c < d->channels; ++c) {
            const float sample = d->channels == 1 ? (stereo[i * 2] + stereo[i * 2 + 1]) * 0.5f : c < 2 ? stereo[i * 2 + c] : 0;
            const size_t at = i * d->channels + c;
            if (d->floating) reinterpret_cast<float *>(bytes)[at] = sample;
            else if (d->bits == 16) reinterpret_cast<qint16 *>(bytes)[at] = qint16(std::clamp(std::lround(sample * 32768.0), -32768L, 32767L));
            else reinterpret_cast<qint32 *>(bytes)[at] = qint32(std::clamp(double(sample), -1.0, 1.0) * 2147483647.0);
        }
    }
    const bool ok = SUCCEEDED(d->render->ReleaseBuffer(UINT32(frames), 0));
    if (!ok) d->notice->dirty = true;
    return ok;
}

struct MixVoiceState {
    std::mutex mutex;
    MixVoice *owner = nullptr;
    quint64 generation = 0;
    quint64 seekSerial = 0;
    QUrl url;
    QByteArray bytes;
    bool opening = false, fetching = false, haveBytes = false, ready = false;
    bool want = false, playing = false, loop = false, buffering = false, seeking = false, reposition = false, flush = false;
    bool eof = false, volumeDirty = true;
    double target = 0, volume = 0, duration = 0;
    int rate = 48000;
    quint64 length = 0, origin = 0, mixed = 0, heard = 0, limit = 0;
    // Một khúc đã xếp vào thiết bị. pcm là tiếng CHƯA nhân âm lượng: đổi âm lượng, dừng, nối giọng chỉ cần trộn lại
    // từ đây tại con trỏ nghe, không phải đọc lại nguồn (đọc lại để lại một lỗ im lặng trên cả endpoint).
    // inAt/inLen: mờ vào từ khung thiết bị inAt; outEnd/outLen: mờ ra, hết tiếng ở outEnd.
    struct Span {
        quint64 device, voice, frames; double media = 0, speed = 1; MixCore::Ramp gain; std::vector<float> pcm;
        quint64 inAt = 0, outEnd = 0; quint32 inLen = 0, outLen = 0;
    };
    std::deque<Span> spans;
    MixCore::Ramp ramp;
    std::unique_ptr<MixCore::Ring> ring;
    std::unique_ptr<QFile> file;
    bool streaming = false;
    double speed = 1, mediaMixed = 0, mediaHeard = 0;
    std::shared_ptr<ByteSource> source;
    std::function<std::unique_ptr<VoiceDecoder>(int)> decoderFactory;
    std::shared_ptr<VoiceDecoder> decoder; // reader keeps an epoch alive while stop/seek/device commands proceed
    std::unique_ptr<TimeStretch> stretch;
    float first[2] = {};
    // joining: nguồn vừa đặt lại chỗ, chưa góp khung nào; được nối vào tại con trỏ nghe (từ joinAt nếu đang bắc cầu).
    // fadeIn: tiếng trước đó bị cắt giữa chừng nên khúc đầu tiên mờ vào. speedDirty: đổi tốc độ khi đang phát.
    bool joining = false, fadeIn = false, speedDirty = false;
    quint64 joinAt = 0;
    // Bed: requested = có lời gọi play() / tua đang chờ nối vào, requestAt = con trỏ nghe lúc gọi.
    bool alignToRequest = false, requested = false;
    quint64 requestAt = 0;
    quint64 frameAt(quint64 consumed) const {
        quint64 frame = origin + consumed;
        if (loop && length) return frame % length;
        // Vừa thôi lặp ở vòng thứ hai trở đi: vẫn báo vị trí trong vòng cuối, không nhảy thẳng tới duration.
        const quint64 cycle = origin + limit > length ? origin + limit - length : 0;
        frame = frame >= cycle ? frame - cycle : (length ? frame % length : 0);
        return std::min(frame, length);
    }
};

namespace {
using Span = MixVoiceState::Span;
// Mờ cosin nâng: mờ ra của khúc cũ và mờ vào của khúc mới cùng độ dài, đặt kề nhau thì cộng đúng bằng 1.
float fadeWeight(const Span &span, quint64 at) {
    constexpr double pi = 3.14159265358979323846;
    double w = 1;
    if (span.inLen && at < span.inAt + span.inLen)
        w *= at < span.inAt ? 0.0 : 0.5 - 0.5 * std::cos(pi * (double(at - span.inAt) + 0.5) / span.inLen);
    if (span.outLen && at + span.outLen >= span.outEnd)
        w *= at >= span.outEnd ? 0.0 : 0.5 - 0.5 * std::cos(pi * (double(span.outEnd - at) - 0.5) / span.outLen);
    return float(w);
}
// CỘNG phần [from, to) (khung thiết bị) của khúc vào out, với out[0] là khung `base`.
void mixSpan(float *out, quint64 base, quint64 from, quint64 to, const Span &span, std::vector<float> &scratch) {
    from = std::max(from, span.device);
    to = std::min(to, span.device + span.frames);
    if (span.outLen) to = std::min(to, span.outEnd);
    if (from >= to || span.pcm.empty()) return;
    const size_t n = size_t(to - from), skip = size_t(from - span.device);
    MixCore::Ramp gain = span.gain;
    gain.advance(skip);
    const float *in = span.pcm.data() + skip * 2;
    if (span.inLen || span.outLen) {
        scratch.assign(in, in + n * 2);
        for (size_t i = 0; i < n; ++i) {
            const float w = fadeWeight(span, from + i);
            scratch[i * 2] *= w; scratch[i * 2 + 1] *= w;
        }
        in = scratch.data();
    }
    gain.mixInto(out + (from - base) * 2, in, n, 2);
}
// Bỏ các khúc đã nghe hết trước `at`, ghi lại vị trí đã nghe của giọng.
void dropHeard(MixVoiceState &s, quint64 at) {
    while (!s.spans.empty() && s.spans.front().device + s.spans.front().frames <= at) {
        const Span &span = s.spans.front();
        s.mediaHeard = span.media + double(span.frames) * span.speed / s.rate;
        s.heard = span.voice + span.frames;
        s.spans.pop_front();
    }
}
// Tách khúc vắt qua khung thiết bị `at` làm hai, để thay đổi (âm lượng, cắt) bắt đầu đúng `at`.
void splitAt(std::deque<Span> &spans, quint64 at, int rate) {
    for (size_t i = 0; i < spans.size(); ++i) {
        Span &span = spans[i];
        if (span.device >= at) return;
        if (span.device + span.frames <= at) continue;
        const quint64 k = at - span.device;
        Span rest = span;
        rest.gain.advance(size_t(k)); rest.device = at; rest.voice += k; rest.media += double(k) * span.speed / rate; rest.frames -= k;
        rest.pcm.erase(rest.pcm.begin(), rest.pcm.begin() + qsizetype(k * 2));
        span.frames = k; span.pcm.resize(size_t(k * 2));
        spans.insert(spans.begin() + qsizetype(i + 1), std::move(rest));
        return;
    }
}
// Chuyển các khúc còn lại sang đuôi tự mờ: hết tiếng ở outEnd, mờ trong len khung trước đó.
void cutInto(std::deque<Span> &from, std::deque<Span> &tails, quint64 outEnd, quint32 len) {
    for (auto &span : from) {
        if (span.device >= outEnd) break;
        span.frames = std::min(span.frames, outEnd - span.device);
        span.pcm.resize(size_t(span.frames * 2));
        span.outEnd = outEnd; span.outLen = len;
        tails.push_back(std::move(span));
    }
    from.clear();
}
}

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
    std::atomic<bool> resetQueued{false};
    std::mutex outputMutex;
    bool outputRequest = false, outputSelect = false;
    QString outputId;
    std::atomic<bool> joinSoon{false}; // nguồn vừa đặt lại chỗ: lượt trộn kế có thể trộn lại để nối nó vào
    int nextWakeMs = 250;
    std::atomic<bool> relaxed{false};
    Clock::time_point responsiveUntil{}; // engineMutex; controls never wait for a hidden refill deadline.
    std::atomic<int> rate{48000};
    std::atomic<quint64> decodes{0};
    quint64 written = 0, played = 0;
    quint64 deviceRevision = 0;
    Clock::time_point sampled = Clock::now();
    // engineMutex: tiếng của giọng vừa bị dừng/nạp lại (stopped, chờ con trỏ nghe) và đuôi đang mờ ra (tails).
    std::deque<Span> stopped, tails;

    Impl(MusicMixer *q, QString dir) : owner(q), cacheDir(std::move(dir)) {}
    void remix(const std::vector<std::shared_ptr<MixVoiceState>> &voices);
    size_t render(const std::shared_ptr<MixVoiceState> &s, float *out, quint64 device, size_t frames,
                  std::vector<std::pair<std::shared_ptr<MixVoiceState>, quint64>> &began);
    void forgetQueue() {
        written = played = 0; tails.clear(); stopped.clear();
        for (const auto &s : snapshot()) { Guard guard(s->mutex); s->spans.clear(); s->joinAt = 0; }
    }
    // Gọi khi giữ khoá của s. Số khung thiết bị giọng này trộn được ngay từ vòng đệm; SIZE_MAX khi không còn gì để chờ
    // (luồng đã tới cuối, hay phần còn lại của tệp không lặp đã nằm cả trong vòng đệm).
    size_t ahead(const MixVoiceState &s) const {
        if (!s.ring || s.eof) return SIZE_MAX;
        const size_t have = s.ring->readable() / 2;
        if (!s.streaming) return !s.loop && s.limit - std::min(s.limit, s.mixed) <= have ? SIZE_MAX : have;
        // Sonic giữ lại tới vài chu kỳ cao độ (~30 ms) trước khi nhả ra.
        const size_t can = size_t(double(have) / s.speed), margin = size_t(rate) / 25;
        return can > margin ? can - margin : 0;
    }
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
    double mediaHeard(MixVoiceState &s, quint64 cursor) const {
        double result = s.mediaHeard;
        for (const auto &span : s.spans) {
            if (cursor <= span.device) break;
            result = span.media + double(std::min(span.frames, cursor - span.device)) * span.speed / s.rate;
        }
        return s.loop ? result : std::min(result, s.duration);
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
            SetThreadDescription(GetCurrentThread(), L"ABook audio render");
            quint64 wakes = 0;
            const bool traceWakes = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE");
            auto traceAt = Clock::now();
            if (!device) device = std::make_unique<WasapiDevice>([this] { owner->wake(); });
            rate = device->rate();
            deviceRevision = device->revision();
            { Guard guard(waitMutex); initialized = true; } mixCv.notify_all();
            std::unique_lock<std::mutex> wait(waitMutex);
            while (!quit) {
                if (!active) mixCv.wait(wait, [this] { return quit || mixDirty; });
                else mixCv.wait_for(wait, std::chrono::milliseconds(nextWakeMs), [this] { return quit || mixDirty; });
                if (quit) break;
                ++wakes;
                if (traceWakes && Clock::now() - traceAt >= std::chrono::seconds(1)) {
                    const auto epoch = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                    std::fprintf(stderr, "mix_wakes epoch_ms=%lld count=%llu thread=%lu\n", static_cast<long long>(epoch), static_cast<unsigned long long>(wakes), GetCurrentThreadId());
                    traceAt = Clock::now();
                }
                mixDirty = false; wait.unlock();
                const size_t lead = size_t(rate) / 2;
                owner->service(lead); // service giới hạn theo padding; test truyền số khung chính xác.
                wait.lock();
            }
            wait.unlock();
            device->stop(); device->reset(); device.reset(); // COM được nhả trên chính luồng tạo nó.
        });
        { std::unique_lock<std::mutex> wait(waitMutex); mixCv.wait(wait, [this] { return initialized; }); }
        readerThread = std::thread([this] {
            SetThreadDescription(GetCurrentThread(), L"ABook audio decode");
            quint64 wakes = 0;
            const bool traceWakes = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE");
            auto traceAt = Clock::now();
            trim();
            std::unique_lock<std::mutex> wait(waitMutex);
            while (!quit) {
                readerCv.wait(wait, [this] { return quit || readerDirty; });
                if (quit) break;
                ++wakes;
                if (traceWakes && Clock::now() - traceAt >= std::chrono::seconds(1)) {
                    const auto epoch = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
                    std::fprintf(stderr, "reader_wakes epoch_ms=%lld count=%llu thread=%lu\n", static_cast<long long>(epoch), static_cast<unsigned long long>(wakes), GetCurrentThreadId());
                    traceAt = Clock::now();
                }
                readerDirty = false; wait.unlock(); owner->serviceReader(); wait.lock();
            }
            wait.unlock();
            MfSource::endThread();
        });
    }
};

MusicMixer::MusicMixer(const QString &cacheDir, QObject *parent) : QObject(parent), d(new Impl(this, cacheDir)) { setObjectName(QStringLiteral("audio mixer")); d->begin(true); }
MusicMixer::MusicMixer(std::unique_ptr<MixDevice> device, const QString &cacheDir, bool threaded, QObject *parent)
    : QObject(parent), d(new Impl(this, cacheDir)) { setObjectName(QStringLiteral("audio mixer")); d->device = std::move(device); d->begin(threaded); }
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
void MusicMixer::setRelaxed(bool relaxed) {
    Guard engine(d->engineMutex);
    if (d->relaxed.exchange(relaxed) == relaxed) return;
    if (!relaxed) {
        d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
        // Drain the old lead naturally. UI restore must not reset Sonic's phase
        // or discard queued PCM; actual audio controls still reset immediately.
    }
    wake();
}
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
void MusicMixer::postSeeked(const std::shared_ptr<MixVoiceState> &state) {
    const quint64 serial = state->seekSerial;
    post(state, [weak = std::weak_ptr<MixVoiceState>(state), serial](MixVoice *voice) {
        const auto s = weak.lock(); if (!s) return;
        { Guard guard(s->mutex); if (s->seekSerial != serial) return; s->seeking = false; }
        emit voice->seeked();
    });
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
    // The render thread must sample the audible cursor before any reader drops spans.
    if (d->resetQueued) { wake(); return; }
    bool renderNeeded = false;
    for (const auto &s : d->snapshot()) {
        { Guard guard(s->mutex);
          renderNeeded |= s->want && (!s->ready || s->reposition || s->buffering || !s->playing);
        }
        if (s->streaming) { serviceStream(s); continue; }
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
            if (frames) {
                // Ghi lần dùng: trim() bỏ tệp có mtime cũ nhất trước, nên bài vừa nghe lại được giữ, không theo giờ giải mã.
                QFile used(path);
                if (used.open(QIODevice::ReadWrite)) used.setFileTime(QDateTime::currentDateTime(), QFileDevice::FileModificationTime);
            }
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
                const Format format = formatOf(bytes);
                Mp3Source mp3(outRate);
                MfSource mf(outRate);
                QSaveFile cache(path);
                if (format == Format::Unknown) error = QStringLiteral("Không nhận ra định dạng tệp nhạc (MP3, WAV, FLAC, M4A, Ogg/Opus).");
                else if (format == Format::Mp3 && !mp3.open(bytes)) error = QStringLiteral("Không đọc được tệp nhạc mp3.");
                else if (format == Format::Mf && !mf.open(bytes)) error = mf.error();
                else if (!cache.open(QIODevice::WriteOnly) || cache.write(header(outRate, 0)) != HEADER) error = cache.errorString();
                else {
                    ++d->decodes;
                    std::vector<float> block;
                    for (;;) {
                        { Guard guard(s->mutex); if (s->generation != generation) break; }
                        block.clear();
                        const size_t n = format == Format::Mp3 ? mp3.read(block, 8192) : mf.read(block, 8192);
                        if (format == Format::Mf && !mf.error().isEmpty()) { error = mf.error(); break; }
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
        if (!s->ready || !s->file || !s->ring || s->flush || d->resetQueued) continue;
        if (s->reposition) {
            s->origin = std::min(s->length, quint64(std::llround(bounded(s->target) * s->rate)));
            s->limit = s->length - s->origin;
            s->file->seek(HEADER + qint64(s->origin) * 4);
            s->ring->clear(); s->mixed = s->heard = 0; s->spans.clear(); s->eof = false; s->reposition = false; s->joining = true; d->joinSoon = true;
            if (s->seeking) postSeeked(s);
        }
        // Đọc trước hai giây; việc lấp vòng đệm không đánh thức giao diện.
        while (s->ring->writable() >= 2) {
            const qint64 n = qint64(std::min<size_t>(s->ring->writable() / 2, 16384));
            const quint64 at = quint64((s->file->pos() - HEADER) / 4);
            const QByteArray pcm = s->file->read(n * 4);
            if (pcm.isEmpty()) {
                if (s->file->error() != QFileDevice::NoError) {
                    s->want = s->ready = false;
                    renderNeeded = true;
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
    // A normal top-up has no control/readiness event to deliver. The output
    // deadline already covers it; waking here adds an empty padding poll.
    if (renderNeeded) wake();
}

void MusicMixer::serviceStream(const std::shared_ptr<MixVoiceState> &s) {
    quint64 generation;
    int outputRate;
    std::shared_ptr<VoiceDecoder> decoder;
    std::shared_ptr<ByteSource> source;
    std::function<std::unique_ptr<VoiceDecoder>(int)> factory;
    { Guard guard(s->mutex);
      if (s->url.isEmpty() || s->flush || d->resetQueued) return;
      generation = s->generation; outputRate = s->rate; decoder = s->decoder; source = s->source; factory = s->decoderFactory;
    }
    if (!decoder) {
        if (factory) decoder = factory(outputRate);
        else if (source) decoder = std::make_shared<StreamMp3>(source, outputRate);
        if (!decoder) return;
        Guard guard(s->mutex);
        if (s->generation != generation) return;
        s->decoder = decoder;
    }
    auto fail = [&] {
        const auto error = decoder->error();
        if (error.isEmpty()) return false;
        Guard guard(s->mutex);
        if (s->generation != generation) return true;
        ++s->generation;
        const bool wasPlaying = s->playing, wasBuffering = s->buffering;
        s->ready = s->opening = s->want = s->playing = s->buffering = false;
        s->ring.reset(); s->stretch.reset(); s->spans.clear();
        post(s, [error, wasPlaying, wasBuffering](MixVoice *v) {
            if (wasPlaying) emit v->playingChanged(false);
            if (wasBuffering) emit v->buffering(false);
            emit v->failed(error);
        });
        s->decoder.reset(); s->source.reset(); s->url.clear();
        return true;
    };
    bool opening;
    { Guard guard(s->mutex); if (s->generation != generation) return; opening = s->opening; }
    if (opening) {
        if (!decoder->open()) { fail(); return; }
        Guard guard(s->mutex);
        if (s->generation != generation) return;
        s->duration = decoder->duration();
        s->length = quint64(std::llround(s->duration * s->rate));
        s->ring = std::make_unique<MixCore::Ring>(size_t(s->rate) * 4);
        s->opening = false; s->ready = true; s->reposition = true;
        ++d->decodes;
        post(s, [duration = s->duration](MixVoice *v) { emit v->durationChanged(duration); });
    }
    bool reposition;
    double target;
    quint64 seekSerial;
    { Guard guard(s->mutex);
      if (s->generation != generation || !s->ready || !s->ring || s->flush || d->resetQueued) return;
      reposition = s->reposition; target = s->target; seekSerial = s->seekSerial;
    }
    if (reposition) {
        if (!decoder->seek(target)) { fail(); return; }
        Guard guard(s->mutex);
        if (s->generation != generation) return;
        if (s->target != target || s->seekSerial != seekSerial || s->flush || d->resetQueued) { wake(true); return; }
        s->target = std::clamp(s->target, 0.0, s->duration);
        s->ring->clear(); s->stretch = std::make_unique<TimeStretch>(s->rate); s->stretch->setRate(s->speed);
        s->mediaMixed = s->mediaHeard = s->target; s->mixed = s->heard = 0; s->spans.clear();
        s->eof = false; s->reposition = false; s->joining = true; d->joinSoon = true;
        if (s->seeking) postSeeked(s);
    }
    std::vector<float> block; // Reuse capacity through this bounded refill, not once per 8192 frames.
    for (;;) {
        size_t frames;
        { Guard guard(s->mutex);
          if (s->generation != generation || !s->ready || s->reposition || s->flush || d->resetQueued || !s->ring) return;
          frames = std::min<size_t>(d->relaxed ? size_t(s->rate) : 8192, s->ring->writable() / 2);
        }
        if (!frames) return;
        // Disk reads, frame-index scans and decoding must NEVER hold the mutex used by the mixer/UI.
        block.clear();
        const size_t got = decoder->read(block, frames);
        if (fail()) return;
        const bool end = decoder->atEnd();
        bool again;
        { Guard guard(s->mutex);
          // Bộ giải mã đã đi qua khối này: chỉ vứt khi nguồn sẽ đặt lại chỗ. Lệnh đang chờ trộn lại (giọng khác tua,
          // âm lượng) không làm vòng đệm sai; vứt ở đây là tiếng nhảy cóc một khối.
          if (s->generation != generation || !s->ready || s->reposition) return;
          if (got) s->ring->write(block.data(), got * 2);
          again = end && s->loop && s->duration > 0;
          if (end && !again) s->eof = true;
        }
        if (again) { if (!decoder->seek(0)) { fail(); return; } }
        else if (!got || end) return;
    }
}

void MusicMixer::requestOutputs() {
    { Guard guard(d->outputMutex); d->outputRequest = true; d->outputSelect = false; }
    wake();
}
void MusicMixer::selectOutput(const QString &id) {
    { Guard guard(d->outputMutex); d->outputRequest = d->outputSelect = true; d->outputId = id; }
    wake();
}
void MusicMixer::service(size_t frames) {
    // Trộn lại sắp xảy ra: chờ ngay sau một lần engine kéo, ngoài khoá để giao diện không phải đợi.
    const bool aligned = d->running && (d->resetQueued || d->joinSoon);
    if (aligned) d->device->awaitPull(12);
    Guard engine(d->engineMutex);
    const auto voices = d->snapshot();
    const int oldRate = rate();
    const quint64 oldCursor = d->cursor();
    bool requested = false, select = false; QString outputId;
    { Guard guard(d->outputMutex); requested = d->outputRequest; select = d->outputSelect; outputId = d->outputId; d->outputRequest = false; }
    if (requested) {
        const bool accepted = !select || d->device->selectOutput(outputId);
        const auto outputs = d->device->outputs(); const auto selected = d->device->outputId();
        QMetaObject::invokeMethod(this, [this, outputs, selected, accepted] { emit outputsReady(outputs, selected, accepted); }, Qt::QueuedConnection);
    }
    if (!d->device->refresh()) {
        // Endpoint loss must freeze at the last audible cursor, including the interpolation
        // since the last padding sample; reconnect then rebuilds from precisely this point.
        d->played = oldCursor;
        d->running = false;
        const QString error = d->device->error();
        if (!error.isEmpty()) {
            d->device->stop(); d->device->reset();
            d->forgetQueue();
            for (const auto &s : voices) {
                Guard guard(s->mutex);
                if (!s->opening && !s->ready && !s->want && !s->playing) continue;
                ++s->generation; // Discard queued readiness and in-flight reader results.
                const bool playing = s->playing, buffering = s->buffering;
                s->opening = s->fetching = s->haveBytes = s->ready = s->want = s->playing = s->buffering = false;
                s->bytes.clear(); s->ring.reset(); s->file.reset(); s->spans.clear();
                s->decoder.reset(); s->source.reset(); s->stretch.reset();
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
        if (!requested) {
            const auto outputs = d->device->outputs(); const auto selected = d->device->outputId();
            QMetaObject::invokeMethod(this, [this, outputs, selected] { emit outputsReady(outputs, selected, true); }, Qt::QueuedConnection);
        }
        // Công bố tần số trước generation mới; reader chụp cả hai dưới khoá voice, không ghép nhầm cache cũ với tần số mới.
        d->rate = d->device->rate();
        // Chuyển tai nghe có thể đổi tần số: cache/ring cũ tuyệt đối không được đọc ở tần số mới.
        for (const auto &s : voices) {
            Guard guard(s->mutex);
            if (s->url.isEmpty()) continue;
            const quint64 heard = d->heard(*s, oldCursor);
            if (!s->reposition && s->ready) {
                s->target = s->streaming ? d->mediaHeard(*s, oldCursor) : double(s->frameAt(heard)) / oldRate;
            }
            s->reposition = true; s->spans.clear();
            if (oldRate != d->device->rate()) {
                ++s->generation; s->ready = false; s->opening = true; s->fetching = s->haveBytes = false;
                s->rate = rate();
                s->ring.reset(); s->file.reset();
                s->decoder.reset(); s->stretch.reset();
            }
        }
        d->deviceRevision = d->device->revision();
        d->rate = d->device->rate(); d->forgetQueue(); d->running = false; wake(true);
    }
    size_t padding = d->device->padding();
    d->played = d->written - std::min<quint64>(padding, d->written); d->sampled = Clock::now();
    bool any = false, join = false;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        dropHeard(*s, d->played);
        const bool exhausted = s->streaming ? s->eof && s->stretch && s->stretch->drained() : s->mixed >= s->limit;
        if (s->want && s->ready && !s->reposition && !s->loop && exhausted && s->spans.empty()) {
            if (s->streaming) s->mediaHeard = s->mediaMixed = s->duration;
            s->want = s->playing = false;
            post(s, [](MixVoice *v) { emit v->playingChanged(false); emit v->ended(); });
        }
        any |= s->want && s->ready;
        // Nối vào giữa hàng đợi chỉ khi vòng đệm đã đủ phủ tới đầu ghi; chưa đủ thì chờ luồng đọc lấp tiếp
        // (hay hàng đợi cạn: lượt trộn thường nối ở đầu ghi, đúng phần đã có).
        const quint64 from = std::max(d->played, s->joinAt);
        join |= s->want && s->ready && !s->reposition && s->joining && from < d->written && d->ahead(*s) >= d->written - from;
    }
    // Endpoint cạn trong lúc còn giọng phát = thiếu dữ liệu. Đuôi mờ của pause / stop phát hết rồi mới cạn là đúng ý, không ghi.
    if (any && d->running && !padding && d->written && qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE"))
        std::fprintf(stderr, "mix_device_empty written=%llu\n", static_cast<unsigned long long>(d->written));
    d->tails.erase(std::remove_if(d->tails.begin(), d->tails.end(), [&](const Span &span) {
        return std::min(span.device + span.frames, span.outEnd) <= d->played;
    }), d->tails.end());
    // Thao tác (tua, dừng, âm lượng, tốc độ) hay giọng vừa sẵn sàng giữa lúc thiết bị còn hàng đợi:
    // trộn lại ngay tại con trỏ nghe. Không bao giờ để endpoint chạy rỗng trong lúc chờ nguồn đọc lại.
    const bool remix = d->resetQueued || (join && d->written > d->played);
    if (remix && d->running && !aligned) {
        // Thao tác tới sau lúc chờ engine kéo: lượt kế (ngay sau đây) chờ rồi mới trộn lại.
        d->joinSoon = true; wake();
    } else {
        if (remix) { d->resetQueued = false; d->remix(voices); padding = size_t(d->written - d->played); }
        d->joinSoon = false;
    }
    if (!any) {
        // Đuôi mờ ra còn trong thiết bị: để nó phát hết rồi mới Stop, Stop giữa chừng là một tiếng tách.
        if (d->running && padding) { d->active = true; d->nextWakeMs = std::clamp(int(padding * 1000 / size_t(rate())) + 1, 1, 250); return; }
        d->device->stop(); d->device->reset(); d->running = false;
        d->forgetQueue(); d->active = false; return;
    }
    d->active = true;
    const bool quiet = d->relaxed && Clock::now() >= d->responsiveUntil;
    size_t lead = size_t(rate()) * (quiet ? 9 : 5) / 10;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        // At 4x the two-second source ring is only 500 ms of output.
        // Leave half a source second for Sonic lookahead and reader scheduling.
        if (s->want && s->streaming) lead = std::min(lead, size_t(rate() * 1.5 / s->speed));
    }
    const int maxWaitMs = quiet ? 750 : 250;
    // Luồng thật truyền lead, bộ thử truyền đúng số khung cần trộn.
    if (d->threaded) {
        frames = lead;
        frames = frames > padding ? frames - padding : 0;
    }
    frames = std::min(frames, d->device->bufferFrames() - std::min(padding, d->device->bufferFrames()));
    // Starvation guard: with a short-capacity endpoint, shorten the next wait so
    // at least 100 ms remains. No device event or MMCSS task is needed.
    const auto schedule = [&](size_t queued) {
        const int remainingMs = int(queued * 1000 / size_t(rate()));
        const int floorMs = std::min(100, int(d->device->bufferFrames() * 1000 / size_t(rate())) / 3);
        d->nextWakeMs = std::clamp(remainingMs - floorMs, 1, maxWaitMs);
    };
    if (!frames) { schedule(padding); return; }
    // Không xếp im lặng khi chưa giọng nào góp được tiếng (đang mở hay đang tua): giọng ấy sẽ được nối vào tại con trỏ nghe.
    // Giọng vừa nối mà hàng đợi còn tiếng (luồng đọc đặt lại chỗ ngay trong lượt này): lượt kế trộn lại, sau một lần
    // engine kéo, đưa nó vào đúng con trỏ hay chỗ cầu để đan chéo, không nối đuôi sau khúc đã mờ hẳn.
    std::vector<std::shared_ptr<MixVoiceState>> mixing;
    bool joinLater = false;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        if (!s->want || !s->ready || s->reposition) continue;
        if (s->joining && padding && s->joinAt < d->written) joinLater = true; else mixing.push_back(s);
    }
    if (joinLater) d->joinSoon = true;
    if (mixing.empty()) { d->nextWakeMs = joinLater ? 1 : padding ? std::clamp(int(padding * 1000 / size_t(rate())), 1, 250) : 250; return; }
    // Chỉ xếp phần mọi giọng đã có sẵn: giọng vừa tua hay vừa nối mà luồng đọc chưa lấp xong thì không chèn im lặng
    // giữa câu. Thật sự cạn và hàng đợi sắp hết mới xếp im lặng, từng đoạn 20 ms để tiếng về là nghe ngay.
    bool starved = false;
    for (const auto &s : mixing) {
        Guard guard(s->mutex);
        if (const size_t can = d->ahead(*s)) frames = std::min(frames, can); else starved = true;
    }
    if (starved || frames < size_t(rate()) / 100) {
        const size_t floor = size_t(rate()) * 3 / 100;
        if (padding >= floor) { wake(true); d->nextWakeMs = std::clamp(int((padding - floor) * 1000 / size_t(rate())), 1, 20); return; }
        if (starved) frames = std::min(frames, size_t(rate()) / 50);
    }
    std::vector<float> out(frames * 2, 0);
    std::vector<std::pair<std::shared_ptr<MixVoiceState>, quint64>> began;
    bool refill = false;
    for (const auto &s : mixing) {
        Guard guard(s->mutex);
        d->render(s, out.data(), d->written, frames, began);
        const double refillSeconds = quiet ? std::min(maxWaitMs / 1000.0, double(lead) / rate() - 0.1) * s->speed + 0.15 : 1.0;
        refill |= s->ring->readable() < size_t(rate() * refillSeconds) * 2 && !s->eof;
    }
    if (refill) wake(true); // One request for all contributors, after consuming their PCM.
    if (!d->device->write(out.data(), frames)) { d->running = false; return; }
    d->written += frames;
    schedule(padding + frames);
    if (!d->running) d->running = d->device->start();
    if (d->running) for (const auto &entry : began) {
        const auto &s = entry.first;
        Guard guard(s->mutex);
        if (s->generation == entry.second && s->want && !s->playing) {
            s->playing = true; post(s, [](MixVoice *v) { emit v->playingChanged(true); });
        }
    }
}

// Gọi khi giữ engineMutex và khoá của s. Trộn `frames` khung mới của giọng vào out (out[0] = khung thiết bị `device`).
size_t MusicMixer::Impl::render(const std::shared_ptr<MixVoiceState> &s, float *out, quint64 device, size_t frames,
                                std::vector<std::pair<std::shared_ptr<MixVoiceState>, quint64>> &began) {
    if (s->volumeDirty) { s->ramp.set(float(AudioOut::effectiveVolume(s->volume)), size_t(rate) / 20); s->volumeDirty = false; }
    if (s->joining && s->requested && !s->streaming) {
        // Bed nối vào ở khung `device`, muộn hơn lời gọi: bỏ qua phần đã trôi (tối đa phần vòng đệm có dư sau khúc này).
        s->requested = false;
        const size_t have = s->ring->readable() / 2;
        quint64 skip = std::min<quint64>(device > s->requestAt ? device - s->requestAt : 0, have > frames ? have - frames : 0);
        if (!s->loop) skip = std::min(skip, s->limit - std::min(s->limit, s->mixed));
        if (skip) {
            std::vector<float> drop(size_t(skip) * 2);
            s->ring->read(drop.data(), drop.size());
            s->mixed += skip; s->heard = s->mixed;
        }
    }
    size_t n = frames;
    if (!s->streaming && !s->loop) n = size_t(std::min<quint64>(n, s->limit - std::min(s->limit, s->mixed)));
    std::vector<float> block(frames * 2, 0.0f), scratch;
    if (s->streaming) s->stretch->setRate(s->speed);
    const size_t got = s->streaming ? s->stretch->read(*s->ring, block.data(), n, s->eof) : s->ring->read(block.data(), n * 2) / 2;
    const bool buffering = got < n && !s->eof;
    if (s->buffering != buffering) { s->buffering = buffering; owner->post(s, [buffering](MixVoice *v) { emit v->buffering(buffering); }); }
    if (s->streaming && buffering && s->playing) {
        s->playing = false; owner->post(s, [](MixVoice *v) { emit v->playingChanged(false); });
    }
    if (got) {
        block.resize(got * 2);
        Span span{device, s->mixed, got, s->mediaMixed, s->speed, s->ramp, std::move(block)};
        if (s->fadeIn) { span.inAt = device; span.inLen = quint32(rate / 200); s->fadeIn = false; }
        mixSpan(out, device, device, device + got, span, scratch);
        s->spans.push_back(std::move(span)); s->mixed += got;
        if (s->streaming) s->mediaMixed += double(got) * s->speed / s->rate;
        if (!s->playing) began.emplace_back(s, s->generation);
    }
    s->ramp.advance(frames);
    s->joining = false; s->joinAt = 0;
    return got;
}

// Gọi khi giữ engineMutex. Viết lại [con trỏ nghe, written) từ PCM còn giữ của từng khúc với trạng thái mới (âm lượng,
// mờ ra khi dừng/tua/đổi tốc độ, giọng mới nối vào) rồi Stop/Reset/Write/Start liền một mạch: không chờ nguồn nào.
void MusicMixer::Impl::remix(const std::vector<std::shared_ptr<MixVoiceState>> &voices) {
    // Trộn sẵn khi engine còn chạy, Stop..Start chỉ còn chép bộ đệm. Engine có thể kéo thêm một chu kỳ trong lúc trộn,
    // nên mọi thay đổi bắt đầu ở pivot = con trỏ + 20 ms; trước pivot là đúng tiếng cũ, kéo kịp hay không vẫn liền.
    // Hàng đợi ngắn thì lùi pivot để đoạn mờ ra vẫn nằm trong tiếng đã xếp.
    const quint32 cross = quint32(rate / 200), fade = quint32(rate / 100);
    const quint64 end = written, at = end - std::min<quint64>(device->padding(), end);
    const quint64 pivot = std::max(at, std::min(at + quint64(rate) / 50, end > fade ? end - fade : 0));
    // Giọng bị dừng hay nạp chương khác: phần đã xếp mờ ra 10 ms thay vì tắt phụt.
    cutInto(stopped, tails, pivot + fade, fade);
    std::vector<float> out(size_t(end - at) * 2, 0.0f), scratch;
    quint64 last = at;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        dropHeard(*s, at);
        splitAt(s->spans, pivot, s->rate);
        if (s->flush) {
            const bool pausing = !s->want, seeking = s->want && (s->seeking || s->reposition);
            if (pausing || seeking) {
                // Vị trí dừng là lúc bấm (con trỏ nghe); 30 ms đã mờ ra được phát lại khi nghe tiếp.
                if (pausing && !s->seeking)
                    s->target = s->streaming ? mediaHeard(*s, at) : double(s->frameAt(heard(*s, at))) / s->rate;
                cutInto(s->spans, tails, pivot + (pausing ? fade : cross), pausing ? fade : cross);
                s->reposition = s->fadeIn = true; s->joining = false; s->joinAt = 0;
            } else if (s->speedDirty && s->streaming && !s->spans.empty()) {
                // Bắc cầu: tiếng cũ chạy thêm tối đa 60 ms trong lúc Sonic mới mồi từ đúng chỗ ấy, rồi đan chéo 5 ms.
                const quint64 room = end - pivot, bridge = std::min<quint64>(quint64(rate) * 6 / 100, room > cross ? room - cross : 0);
                s->joinAt = pivot + bridge;
                s->target = mediaHeard(*s, s->joinAt);
                cutInto(s->spans, tails, s->joinAt + cross, cross);
                s->reposition = s->fadeIn = true; s->joining = false;
            }
        }
        // Không còn gì xếp để bắc cầu: tốc độ mới áp ngay ở đầu ghi, Sonic đổi tốc độ liền mạch.
        s->flush = s->speedDirty = false;
        if (s->spans.empty()) continue;
        if (s->volumeDirty) {
            // Âm lượng mới trượt 50 ms từ đúng mức đang nghe ở pivot; trước pivot giữ nguyên.
            auto first = std::find_if(s->spans.begin(), s->spans.end(), [&](const Span &span) { return span.device >= pivot; });
            if (first != s->spans.end()) {
                const quint64 base = first->device;
                MixCore::Ramp ramp = first->gain;
                ramp.set(float(AudioOut::effectiveVolume(s->volume)), size_t(rate) / 20);
                for (auto it = first; it != s->spans.end(); ++it) { MixCore::Ramp g = ramp; g.advance(size_t(it->device - base)); it->gain = g; }
                ramp.advance(size_t(end - base)); s->ramp = ramp; s->volumeDirty = false;
            }
        }
        for (const auto &span : s->spans) {
            mixSpan(out.data(), at, at, end, span, scratch);
            last = std::max(last, span.device + span.frames);
        }
    }
    for (const auto &span : tails) {
        mixSpan(out.data(), at, at, end, span, scratch);
        last = std::max(last, std::min(span.device + span.frames, span.outEnd));
    }
    // Giọng vừa sẵn sàng (play, tua xong, đổi tốc độ xong) vào ngay pivot (hay đúng chỗ cầu), không chờ hàng đợi cũ cạn.
    std::vector<std::pair<std::shared_ptr<MixVoiceState>, quint64>> began;
    for (const auto &s : voices) {
        Guard guard(s->mutex);
        if (!s->want || !s->ready || s->reposition || !s->joining) continue;
        const quint64 from = std::max(pivot, s->joinAt);
        // Hàng đợi đã cạn tới đó: lượt trộn thường nối giọng này ở đầu ghi. Vòng đệm chưa phủ tới đầu ghi: chờ thêm,
        // không để im lặng giữa câu.
        if (from >= end || ahead(*s) < end - from) continue;
        render(s, out.data() + (from - at) * 2, from, size_t(end - from), began);
        last = end;
    }
    // Nguồn bị cắt cần đặt lại chỗ, giọng vừa nối cần lấp lại vòng đệm: luồng đọc chạy ngay.
    owner->wake(true);
    // Không giữ im lặng thừa sau tiếng cuối: thiết bị cạn đúng lúc hết đuôi mờ.
    device->stop();
    const quint64 now = std::max(at, end - std::min<quint64>(device->padding(), end));
    device->reset(); running = false;
    played = now; sampled = Clock::now();
    written = std::max(last, now);
    if (last > now) {
        if (!device->write(out.data() + (now - at) * 2, size_t(last - now))) return;
        running = device->start();
    }
    if (running) for (const auto &entry : began) {
        const auto &s = entry.first;
        Guard guard(s->mutex);
        if (s->generation == entry.second && s->want && !s->playing) {
            s->playing = true; owner->post(s, [](MixVoice *v) { emit v->playingChanged(true); });
        }
    }
}

double MusicMixer::position(const std::shared_ptr<MixVoiceState> &s) const {
    Guard engine(d->engineMutex); Guard guard(s->mutex);
    if (s->seeking || s->reposition || !s->ready) return s->target;
    if (s->streaming) {
        const double at = d->mediaHeard(*s, d->cursor());
        return s->loop && s->duration > 0 ? std::fmod(at, s->duration) : at;
    }
    const quint64 cursor = d->cursor();
    if (!s->spans.empty() && cursor < s->spans.front().device) {
        // Đã nối vào nhưng chưa ra loa: khung nghe lúc này là khúc đầu lùi lại đúng chừng ấy (liền mạch với lúc có tiếng).
        const Span &first = s->spans.front();
        const quint64 back = first.device - cursor;
        return double(s->frameAt(first.voice > back ? first.voice - back : 0)) / s->rate;
    }
    return double(s->frameAt(d->heard(*s, cursor))) / s->rate;
}

MixVoice::MixVoice(MusicMixer *mixer, QObject *parent) : AudioOut(parent), m_mixer(mixer), m_state(std::make_shared<MixVoiceState>()) {
    m_state->owner = this;
    m_state->rate = mixer->rate();
    Guard guard(mixer->d->voicesMutex); mixer->d->voices.push_back(m_state);
}
MixVoice::MixVoice(MusicMixer *mixer, Purpose purpose, QObject *parent) : MixVoice(mixer, parent) {
    m_state->streaming = purpose == Voice; m_state->alignToRequest = purpose == Bed;
}
MixVoice::MixVoice(MusicMixer *mixer, std::function<std::unique_ptr<VoiceDecoder>(int)> decoder, QObject *parent) : MixVoice(mixer, Voice, parent) {
    m_state->decoderFactory = std::move(decoder);
}
MixVoice::~MixVoice() {
    stop();
    { Guard guard(m_state->mutex); m_state->owner = nullptr; }
    Guard guard(m_mixer->d->voicesMutex);
    auto &voices = m_mixer->d->voices; voices.erase(std::remove(voices.begin(), voices.end(), m_state), voices.end());
}
void MixVoice::load(const QUrl &url, double startSeconds) {
    stop();
    { Guard guard(m_state->mutex); m_state->url = url; m_state->rate = m_mixer->rate(); m_state->target = bounded(startSeconds); m_state->opening = true;
      if (m_state->streaming && !m_state->decoderFactory) {
          // Only decoded PCM can unblock rendering. serviceReader() signals the
          // mixer after publishing it; compressed socket chunks need no second wake.
          auto *source = new RangeSource(url, [mixer = m_mixer] { mixer->wake(true); });
          source->setObjectName(QStringLiteral("compressed audio source"));
          source->setParent(m_mixer);
          m_state->source = std::shared_ptr<ByteSource>(source, [source](ByteSource *) { source->deleteLater(); });
      }
    }
    m_mixer->wake(true);
}
void MixVoice::play() {
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      if (!m_state->url.isEmpty()) {
          if (m_state->alignToRequest && !m_state->want) { m_state->requestAt = m_mixer->d->cursor(); m_state->requested = true; }
          // Không flush: giọng được nối vào tại con trỏ nghe ngay khi nguồn sẵn (MusicMixer::service, joining).
          m_state->want = true;
          if (m_state->streaming && !m_state->ready && !m_state->buffering) {
              m_state->buffering = true; m_mixer->post(m_state, [](MixVoice *v) { emit v->buffering(true); });
          }
      }
    }
    m_mixer->wake(true); m_mixer->wake();
}
void MixVoice::pause() {
    const double at = position();
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      if (m_mixer->d->written) m_mixer->d->resetQueued = m_state->flush = true;
      m_state->want = m_state->requested = false;
      if (m_state->buffering) { m_state->buffering = false; m_mixer->post(m_state, [](MixVoice *v) { emit v->buffering(false); }); }
      m_state->target = at; m_state->reposition = true;
      if (m_state->playing) { m_state->playing = false; m_mixer->post(m_state, [](MixVoice *v) { emit v->playingChanged(false); }); }
    }
    m_mixer->wake();
}
void MixVoice::stop() {
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      if (m_mixer->d->written && (m_state->want || !m_state->spans.empty())) m_mixer->d->resetQueued = true;
      // Phần đã xếp vào thiết bị thuộc về luồng trộn: nó mờ ra từ con trỏ nghe, không tắt phụt.
      for (auto &span : m_state->spans) m_mixer->d->stopped.push_back(std::move(span));
      ++m_state->generation; m_state->url.clear(); m_state->bytes.clear();
      const bool wasPlaying = m_state->playing, wasBuffering = m_state->buffering;
      if (wasPlaying || wasBuffering) m_mixer->post(m_state, [wasPlaying, wasBuffering](MixVoice *v) {
          if (wasPlaying) emit v->playingChanged(false);
          if (wasBuffering) emit v->buffering(false);
      });
      m_state->opening = m_state->fetching = m_state->haveBytes = m_state->ready = m_state->want = m_state->playing = false;
      m_state->buffering = m_state->seeking = m_state->reposition = m_state->eof = m_state->flush = false;
      m_state->ring.reset(); m_state->file.reset(); m_state->spans.clear();
      m_state->source.reset(); m_state->decoder.reset(); m_state->stretch.reset(); m_state->mediaHeard = m_state->mediaMixed = 0;
      m_state->joining = m_state->fadeIn = m_state->speedDirty = m_state->requested = false; m_state->joinAt = 0;
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
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      if (m_mixer->d->written) m_mixer->d->resetQueued = m_state->flush = true;
      ++m_state->seekSerial; m_state->target = bounded(seconds); m_state->seeking = m_state->reposition = true;
      if (m_state->alignToRequest && m_state->want) { m_state->requestAt = m_mixer->d->cursor(); m_state->requested = true; }
      if (m_state->streaming && m_state->want && !m_state->buffering) {
          m_state->buffering = true; m_mixer->post(m_state, [](MixVoice *v) { emit v->buffering(true); });
      }
      if (m_state->streaming && m_state->playing) {
          m_state->playing = false; m_mixer->post(m_state, [](MixVoice *v) { emit v->playingChanged(false); });
      }
    }
    m_mixer->wake(true); m_mixer->wake();
}
void MixVoice::setVolume(double volume) {
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      volume = effectiveVolume(volume);
      if (m_state->volume == volume) return;
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      m_state->volume = volume; m_state->volumeDirty = true;
      // Trộn lại phần đã xếp từ PCM còn giữ: nguồn không đọc lại, không flush, không lỗ.
      if (!m_state->spans.empty()) m_mixer->d->resetQueued = true;
    }
    m_mixer->wake();
}
void MixVoice::setRate(double speed) {
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      if (!std::isfinite(speed)) return;
      speed = std::clamp(speed, 0.5, 4.0);
      if (m_state->speed == speed) return;
      m_mixer->d->responsiveUntil = Clock::now() + std::chrono::seconds(2);
      m_state->speed = speed;
      // Đang phát: bắc cầu sang Sonic mới (remix). Chưa xếp gì thì tốc độ mới áp ngay ở lượt trộn tới.
      if (m_state->streaming && m_state->want && !m_state->spans.empty()) m_mixer->d->resetQueued = m_state->flush = m_state->speedDirty = true;
    }
    m_mixer->wake();
}
void MixVoice::preload() { m_mixer->wake(true); }
void MixVoice::setLoop(bool loop) {
    const double at = m_state->streaming && !loop ? position() : 0;
    { Guard engine(m_mixer->d->engineMutex); Guard guard(m_state->mutex);
      if (m_state->streaming && m_state->loop != loop) {
          if (!loop) {
              m_state->target = at; m_state->reposition = true;
              if (m_mixer->d->written) m_mixer->d->resetQueued = m_state->flush = true;
          }
          else if (m_state->stretch && m_state->stretch->drained()) { m_state->target = 0; m_state->reposition = true; }
      }
      if (!loop && m_state->loop && m_state->length) {
          const quint64 at = (m_state->origin + m_state->mixed) % m_state->length;
          m_state->limit = m_state->mixed + (at || !m_state->mixed ? m_state->length - at : 0);
      }
      m_state->loop = loop; if (loop) m_state->eof = false;
    }
    m_mixer->wake(true); m_mixer->wake();
}
double MixVoice::position() const { return m_mixer->position(m_state); }
double MixVoice::duration() const { Guard guard(m_state->mutex); return m_state->duration; }
bool MixVoice::playing() const { Guard guard(m_state->mutex); return m_state->playing; }
