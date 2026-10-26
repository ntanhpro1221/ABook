#include "bench.h"
#include "audioout_mf.h"

#include <QDir>
#include <QMetaObject>
#include <QPointer>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <mutex>

#include <windows.h>
#include <audiosessiontypes.h>
#include <mfapi.h>
#include <mfmediaengine.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

// Sự kiện của engine đến trên luồng của Media Foundation; chuyển về luồng giao diện bằng hàng đợi. Chủ sở hữu có thể chết trước khi sự kiện
// cuối tới, nên giữ con trỏ sau một khoá, huỷ trong destructor.
struct MfAudioOut::Impl {
    ComPtr<IMFMediaEngine> engine;
    ComPtr<IMFMediaEngineEx> engineEx;
    std::mutex lock;
    MfAudioOut *owner = nullptr;
};

class MfAudioOut::Notify final : public IMFMediaEngineNotify {
public:
    explicit Notify(Impl *impl) : m_impl(impl) {}
    STDMETHODIMP QueryInterface(REFIID riid, void **out) override {
        if (riid == __uuidof(IMFMediaEngineNotify) || riid == __uuidof(IUnknown)) {
            *out = static_cast<IMFMediaEngineNotify *>(this);
            AddRef();
            return S_OK;
        }
        *out = nullptr;
        return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() override { return ++m_refs; }
    STDMETHODIMP_(ULONG) Release() override {
        const ULONG left = --m_refs;
        if (!left)
            delete this;
        return left;
    }
    STDMETHODIMP EventNotify(DWORD event, DWORD_PTR param1, DWORD param2) override {
        std::lock_guard<std::mutex> guard(m_impl->lock);
        MfAudioOut *owner = m_impl->owner;
        if (!owner)
            return S_OK;
        const quint64 serial = owner->m_serial;
        QMetaObject::invokeMethod(owner, [owner, event, param1, param2, serial] {
            if (owner->m_serial == serial)
                owner->onEvent(event, param1, param2);
        }, Qt::QueuedConnection);
        return S_OK;
    }

private:
    std::atomic<ULONG> m_refs{1};
    Impl *m_impl;
};

namespace {
/// Mốc cho tools/measure.py (ABOOK_BENCH): mỗi engine một mã, để đặt cú khựng khung cạnh lúc engine nào tạo / mở nguồn / phát / huỷ.
/// TIMEUPDATE và PROGRESS bỏ (vài lần mỗi giây, chỉ làm nhiễu).
void benchMark(const void *engine, const char *what) {
    static const bool on = qEnvironmentVariableIsSet("ABOOK_BENCH");
    if (on)
        Bench::mark(QStringLiteral("mf:%1:%2").arg(quintptr(engine) & 0xffffff, 0, 16).arg(QLatin1String(what)));
}
} // namespace

MfAudioOut::MfAudioOut(QObject *parent) : AudioOut(parent), d(new Impl) {
    d->owner = this;
}

bool MfAudioOut::ensureEngine() {
    if (d->engine)
        return true;
    benchMark(this, "create");
    if (!m_started) {
        MFStartup(MF_VERSION, MFSTARTUP_LITE);
        m_started = true;
    }
    ComPtr<IMFMediaEngineClassFactory> factory;
    if (FAILED(CoCreateInstance(CLSID_MFMediaEngineClassFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&factory))))
        return false;
    ComPtr<IMFAttributes> attributes;
    if (FAILED(MFCreateAttributes(&attributes, 2)))
        return false;
    ComPtr<Notify> notify;
    notify.Attach(new Notify(d.get()));
    attributes->SetUnknown(MF_MEDIA_ENGINE_CALLBACK, notify.Get());
    attributes->SetUINT32(MF_MEDIA_ENGINE_AUDIO_CATEGORY, AudioCategory_Media);
    if (FAILED(factory->CreateInstance(MF_MEDIA_ENGINE_AUDIOONLY, attributes.Get(), &d->engine)))
        return false;
    d->engine.As(&d->engineEx);
    d->engine->SetPreload(MF_MEDIA_ENGINE_PRELOAD_AUTOMATIC);
    return true;
}

MfAudioOut::~MfAudioOut() {
    benchMark(this, "destroy");
    {
        std::lock_guard<std::mutex> guard(d->lock);
        d->owner = nullptr;
    }
    if (d->engine) {
        d->engine->Pause();
        d->engine->Shutdown();
    }
    d->engine.Reset();
    d->engineEx.Reset();
    if (m_started)
        MFShutdown();
}

void MfAudioOut::load(const QUrl &url, double startSeconds) {
    ++m_serial;
    m_loaded = false;
    m_sourceOpen = false;
    m_seeking = false;
    m_wantPlay = false;
    m_target = startSeconds;
    m_duration = 0;
    m_url = url;
    if (d->engine)
        d->engine->Pause();
    if (m_playing) {
        m_playing = false;
        emit playingChanged(false);
    }
    // Nguồn mở muộn, ở lệnh phát đầu tiên (openSource).
}

void MfAudioOut::openSource() {
    if (m_sourceOpen)
        return;
    if (!ensureEngine()) {
        emit failed(QStringLiteral("Windows không mở được bộ phát âm thanh."));
        return;
    }
    m_sourceOpen = true;
    benchMark(this, "source");
    const QString text = m_url.isLocalFile() ? QDir::toNativeSeparators(m_url.toLocalFile()) : m_url.toString(QUrl::FullyEncoded);
    BSTR source = SysAllocStringLen(reinterpret_cast<const OLECHAR *>(text.utf16()), static_cast<UINT>(text.size()));
    d->engine->SetSource(source);
    SysFreeString(source);
    d->engine->SetPlaybackRate(m_rate);
    d->engine->SetVolume(effectiveVolume(m_volume));
    d->engine->SetLoop(m_loop);
}

void MfAudioOut::play() {
    benchMark(this, "play");
    m_wantPlay = true;
    if (m_url.isEmpty())
        return;
    openSource();
    if (m_loaded && d->engine)
        d->engine->Play();
}

void MfAudioOut::preload() {
    if (!m_url.isEmpty())
        openSource();
}

void MfAudioOut::setLoop(bool loop) {
    m_loop = loop;
    if (d->engine)
        d->engine->SetLoop(loop);
}

void MfAudioOut::pause() {
    m_wantPlay = false;
    if (d->engine)
        d->engine->Pause();
}

void MfAudioOut::stop() {
    benchMark(this, "stop");
    ++m_serial;
    m_loaded = false;
    m_wantPlay = false;
    m_seeking = false;
    m_duration = 0;
    if (d->engine) {
        d->engine->Pause();
        BSTR empty = SysAllocString(L"");
        d->engine->SetSource(empty);
        SysFreeString(empty);
    }
    m_sourceOpen = false;
    m_url.clear();
    if (m_playing) {
        m_playing = false;
        emit playingChanged(false);
    }
}

void MfAudioOut::seek(double seconds) {
    benchMark(this, "seek");
    m_target = qMax(0.0, seconds);
    if (!m_loaded || !d->engine)
        return; // chưa mở nguồn / chưa nạp xong: onEvent(LOADEDMETADATA) tua tới m_target
    m_seeking = true;
    d->engine->SetCurrentTime(m_target);
}

void MfAudioOut::setRate(double rate) {
    m_rate = rate;
    if (d->engine) {
        d->engine->SetDefaultPlaybackRate(rate);
        d->engine->SetPlaybackRate(rate);
    }
}

void MfAudioOut::setVolume(double volume) {
    m_volume = volume;
    if (d->engine)
        d->engine->SetVolume(effectiveVolume(volume));
}

double MfAudioOut::position() const {
    if (!m_sourceOpen || !m_loaded || m_seeking || !d->engine)
        return m_target;
    return d->engine->GetCurrentTime();
}

double MfAudioOut::duration() const {
    return m_duration;
}

void MfAudioOut::onEvent(unsigned long event, quint64 p1, unsigned long p2) {
    static const bool trace = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE") != 0;
    if (trace)
        fprintf(stderr, "mf event %lu p1=%llu p2=%lu pos=%.3f\n", event, (unsigned long long)p1, p2, d->engine ? d->engine->GetCurrentTime() : -1.0);
    if (event != MF_MEDIA_ENGINE_EVENT_TIMEUPDATE && event != MF_MEDIA_ENGINE_EVENT_PROGRESS)
        benchMark(this, QByteArray::number(qulonglong(event)).constData());
    switch (event) {
    case MF_MEDIA_ENGINE_EVENT_LOADEDMETADATA:
    case MF_MEDIA_ENGINE_EVENT_DURATIONCHANGE: {
        const double length = d->engine->GetDuration();
        if (std::isfinite(length) && length > 0 && length != m_duration) {
            m_duration = length;
            emit durationChanged(length);
        }
        if (event == MF_MEDIA_ENGINE_EVENT_LOADEDMETADATA && !m_loaded) {
            m_loaded = true;
            if (m_target > 0) {
                m_seeking = true;
                d->engine->SetCurrentTime(m_target);
            }
            if (m_wantPlay)
                d->engine->Play();
        }
        break;
    }
    case MF_MEDIA_ENGINE_EVENT_PLAYING:
        emit buffering(false);
        if (!m_playing) {
            m_playing = true;
            emit playingChanged(true);
        }
        break;
    case MF_MEDIA_ENGINE_EVENT_PAUSE:
        if (m_playing) {
            m_playing = false;
            emit playingChanged(false);
        }
        break;
    case MF_MEDIA_ENGINE_EVENT_WAITING:
        emit buffering(true);
        break;
    case MF_MEDIA_ENGINE_EVENT_SEEKED:
        m_seeking = false;
        m_target = d->engine->GetCurrentTime();
        emit seeked();
        break;
    case MF_MEDIA_ENGINE_EVENT_ENDED:
        if (m_playing) {
            m_playing = false;
            emit playingChanged(false);
        }
        emit ended();
        break;
    case MF_MEDIA_ENGINE_EVENT_ERROR: {
        if (p1 == MF_MEDIA_ENGINE_ERR_NOERROR || p1 == MF_MEDIA_ENGINE_ERR_ABORTED)
            break; // nguồn bị thay / bỏ có chủ ý (stop, load nguồn mới)
        m_wantPlay = false;
        const QString reason = QStringLiteral("0x%1").arg(static_cast<quint32>(p2), 8, 16, QLatin1Char('0'));
        emit failed(reason);
        break;
    }
    default:
        break;
    }
}
