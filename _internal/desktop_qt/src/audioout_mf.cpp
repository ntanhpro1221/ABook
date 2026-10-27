#include "audioout_mf.h"
#include "mftrace.h"

#include <QDir>
#include <QMetaObject>
#include <QPointer>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <thread>

#include <windows.h>
#include <audiosessiontypes.h>
#include <mfapi.h>
#include <mfmediaengine.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

// Sự kiện của engine đến trên luồng của Media Foundation; chuyển về luồng giao diện bằng hàng đợi. Mỗi engine một Link: engine bị cho nghỉ
// (retire) hay chủ chết thì Link cắt chủ, sự kiện muộn của engine ấy bị bỏ.
struct MfLink {
    std::mutex lock;
    MfAudioOut *owner = nullptr;
};

struct MfAudioOut::Impl {
    ComPtr<IMFMediaEngine> engine;
    ComPtr<IMFMediaEngineEx> engineEx;
    std::shared_ptr<MfLink> link;
};

namespace {
// Chỉ những sự kiện onEvent dùng mới đánh thức luồng giao diện: TIMEUPDATE / PROGRESS tới vài lần mỗi giây mỗi engine
// không cần đánh thức giao diện nếu thời gian phát vẫn do đồng hồ của Player theo dõi.
bool wakesUi(DWORD event) {
    static const bool trace = qEnvironmentVariableIntValue("ABOOK_AUDIO_TRACE") != 0;
    switch (event) {
    case MF_MEDIA_ENGINE_EVENT_LOADEDMETADATA:
    case MF_MEDIA_ENGINE_EVENT_DURATIONCHANGE:
    case MF_MEDIA_ENGINE_EVENT_PLAYING:
    case MF_MEDIA_ENGINE_EVENT_PAUSE:
    case MF_MEDIA_ENGINE_EVENT_WAITING:
    case MF_MEDIA_ENGINE_EVENT_SEEKED:
    case MF_MEDIA_ENGINE_EVENT_ENDED:
    case MF_MEDIA_ENGINE_EVENT_ERROR:
        return true;
    default:
        return trace;
    }
}
}  // namespace

class MfAudioOut::Notify final : public IMFMediaEngineNotify {
public:
    explicit Notify(std::shared_ptr<MfLink> link) : m_link(std::move(link)) {}
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
        if (!wakesUi(event))
            return S_OK;
        std::lock_guard<std::mutex> guard(m_link->lock);
        MfAudioOut *owner = m_link->owner;
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
    std::shared_ptr<MfLink> m_link;
};

MfAudioOut::MfAudioOut(QObject *parent) : AudioOut(parent), d(new Impl) {}

bool MfAudioOut::ensureEngine() {
    if (d->engine)
        return true;
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
    d->link = std::make_shared<MfLink>();
    d->link->owner = this;
    ComPtr<Notify> notify;
    notify.Attach(new Notify(d->link));
    attributes->SetUnknown(MF_MEDIA_ENGINE_CALLBACK, notify.Get());
    attributes->SetUINT32(MF_MEDIA_ENGINE_AUDIO_CATEGORY, AudioCategory_Media);
    if (FAILED(factory->CreateInstance(MF_MEDIA_ENGINE_AUDIOONLY, attributes.Get(), &d->engine)))
        return false;
    d->engine.As(&d->engineEx);
    d->engine->SetPreload(MF_MEDIA_ENGINE_PRELOAD_AUTOMATIC);
    return true;
}

MfAudioOut::~MfAudioOut() {
    retire();
    if (m_started)
        MFShutdown();
}

void MfAudioOut::retire() {
    if (mfTraceEnabled())
        mfTraceState(this, "retire", position());
    // Tháo đường ống của nguồn cũ (Pause / SetSource / Shutdown) chờ luồng mạng đóng - đo được 0,3 tới vài giây đứng luồng giao diện
    // lúc sang chương (PROGRESS.md mục CPU). Engine cũ được tháo ở luồng riêng; lần phát kế dựng engine mới.
    if (!d->engine)
        return;
    {
        std::lock_guard<std::mutex> guard(d->link->lock);
        d->link->owner = nullptr;
    }
    d->link.reset();
    MFStartup(MF_VERSION, MFSTARTUP_LITE); // phần của luồng tháo, trả ở cuối luồng
    std::thread([engine = std::move(d->engine), engineEx = std::move(d->engineEx),
                 traceOut = static_cast<const void *>(this)]() mutable {
        mfTraceState(traceOut, "retire_thread_begin");
        CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        mfTraceState(traceOut, "retire_worker_begin");
        engine->Pause();
        engine->Shutdown();
        engineEx.Reset();
        engine.Reset();
        MFShutdown();
        CoUninitialize();
        mfTraceState(traceOut, "retire_worker_done");
    }).detach();
    m_sourceOpen = false;
}

void MfAudioOut::load(const QUrl &url, double startSeconds) {
    if (mfTraceEnabled())
        mfTraceState(this, "load", position());
    ++m_serial;
    if (m_sourceOpen)
        retire(); // engine đã có nguồn: đổi nguồn trên nó sẽ chờ tháo nguồn cũ ngay trên luồng này
    m_loaded = false;
    m_seeking = false;
    m_wantPlay = false;
    m_target = startSeconds;
    m_duration = 0;
    m_url = url;
    if (m_playing) {
        m_playing = false;
        emit playingChanged(false);
    }
    // Nguồn mở muộn, ở lệnh phát đầu tiên (openSource).
}

void MfAudioOut::openSource() {
    if (mfTraceEnabled())
        mfTraceState(this, "openSource", position());
    if (m_sourceOpen)
        return;
    if (!ensureEngine()) {
        emit failed(QStringLiteral("Windows không mở được bộ phát âm thanh."));
        return;
    }
    m_sourceOpen = true;
    const QString text = m_url.isLocalFile() ? QDir::toNativeSeparators(m_url.toLocalFile()) : m_url.toString(QUrl::FullyEncoded);
    BSTR source = SysAllocStringLen(reinterpret_cast<const OLECHAR *>(text.utf16()), static_cast<UINT>(text.size()));
    d->engine->SetSource(source);
    SysFreeString(source);
    d->engine->SetPlaybackRate(m_rate);
    d->engine->SetVolume(effectiveVolume(m_volume));
}

void MfAudioOut::play() {
    if (mfTraceEnabled())
        mfTraceState(this, "play", position());
    m_wantPlay = true;
    if (m_url.isEmpty())
        return;
    openSource();
    if (m_loaded && d->engine)
        d->engine->Play();
}

void MfAudioOut::pause() {
    if (mfTraceEnabled())
        mfTraceState(this, "pause", position());
    m_wantPlay = false;
    if (d->engine)
        d->engine->Pause();
}

void MfAudioOut::stop() {
    if (mfTraceEnabled())
        mfTraceState(this, "stop", position());
    ++m_serial;
    m_loaded = false;
    m_wantPlay = false;
    m_seeking = false;
    m_duration = 0;
    retire();
    m_url.clear();
    if (m_playing) {
        m_playing = false;
        emit playingChanged(false);
    }
}

void MfAudioOut::seek(double seconds) {
    if (mfTraceEnabled())
        mfTraceState(this, "seek", position());
    m_target = qMax(0.0, seconds);
    if (!m_loaded || !d->engine)
        return; // chưa mở nguồn / chưa nạp xong: onEvent(LOADEDMETADATA) tua tới m_target
    m_seeking = true;
    d->engine->SetCurrentTime(m_target);
}

void MfAudioOut::setRate(double rate) {
    if (mfTraceEnabled())
        mfTraceState(this, "setRate", position());
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
        fprintf(stderr, "mf t_ms=%lld out=%p event=%lu p1=%llu p2=%lu pos=%.3f\n", mfTraceMs(), static_cast<void *>(this), event, (unsigned long long)p1, p2, d->engine ? d->engine->GetCurrentTime() : -1.0);
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
