#include "mfsource.h"

#include <algorithm>
#include <cstring>
#include <limits>

#define NOMINMAX
#include <windows.h>
#include <shlwapi.h>
#include <mfapi.h>
#include <mferror.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

namespace {
// Giữ COM/MF tới MfSource::endThread() ở cuối luồng reader, không khởi động lại cho từng bài. Không nhả trong hàm huỷ
// thread_local: nó chạy dưới loader lock lúc luồng thoát, và MFShutdown cuối cùng ở đó chờ mãi các luồng hàng đợi MF
// (chúng cũng cần loader lock để thoát) - huỷ bộ trộn, tức thoát app, treo.
struct ReaderRuntime {
    bool started = false;
    HRESULT com = E_FAIL, mf = E_FAIL;
};
thread_local ReaderRuntime runtime;
}

void MfSource::endThread() {
    if (SUCCEEDED(runtime.mf)) MFShutdown();
    if (SUCCEEDED(runtime.com)) CoUninitialize();
    runtime = {};
}

struct MfSource::Decoder {
    ComPtr<IStream> stream;
    ComPtr<IMFByteStream> bytes;
    ComPtr<IMFSourceReader> reader;
};

MfSource::MfSource(int outRate) : d(new Decoder), m_outRate(outRate) {}
MfSource::~MfSource() = default;

bool MfSource::fail(long hr) {
    m_error = QStringLiteral("Windows không giải mã được tệp nhạc (0x%1).")
        .arg(quint32(hr), 8, 16, QLatin1Char('0'));
    if (m_ogg)
        m_error += QStringLiteral(" Ogg/Opus cần bộ giải mã Web Media Extensions của Windows; hãy kiểm tra bộ giải mã hoặc tệp nhạc.");
    return false;
}

bool MfSource::open(const QByteArray &data) {
    d.reset(new Decoder);
    m_resampler.reset(); m_pending.clear(); m_pendingAt = 0;
    m_rate = m_channels = 0; m_duration = 0; m_fed = m_given = m_length = 0; m_done = false;
    m_error.clear(); m_ogg = data.startsWith("OggS");
    if (!runtime.started) {
        runtime.started = true;
        runtime.com = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        runtime.mf = SUCCEEDED(runtime.com) ? MFStartup(MF_VERSION) : runtime.com;
    }
    if (FAILED(runtime.mf)) return fail(runtime.mf);
    if (data.isEmpty() || quint64(data.size()) > std::numeric_limits<UINT>::max()) return fail(E_INVALIDARG);
    d->stream.Attach(SHCreateMemStream(reinterpret_cast<const BYTE *>(data.constData()), UINT(data.size())));
    if (!d->stream) return fail(E_OUTOFMEMORY);
    HRESULT hr = MFCreateMFByteStreamOnStream(d->stream.Get(), &d->bytes);
    if (FAILED(hr)) return fail(hr);
    if (m_ogg) {
        // Handler Ogg của Windows cần MIME khi luồng nhớ không có tên tệp.
        ComPtr<IMFAttributes> attributes;
        if (FAILED(hr = d->bytes.As(&attributes)) || FAILED(hr = attributes->SetString(MF_BYTESTREAM_CONTENT_TYPE, L"audio/ogg")))
            return fail(hr);
    }
    hr = MFCreateSourceReaderFromByteStream(d->bytes.Get(), nullptr, &d->reader);
    if (FAILED(hr)) return fail(hr);
    hr = d->reader->SetStreamSelection(MF_SOURCE_READER_ALL_STREAMS, FALSE);
    if (FAILED(hr)) return fail(hr);
    hr = d->reader->SetStreamSelection(MF_SOURCE_READER_FIRST_AUDIO_STREAM, TRUE);
    if (FAILED(hr)) return fail(hr);

    ComPtr<IMFMediaType> native, type, actual;
    hr = d->reader->GetNativeMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM, 0, &native);
    if (FAILED(hr)) return fail(hr);
    UINT32 rate = 0, nativeChannels = 0;
    hr = native->GetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, &rate);
    if (FAILED(hr) || !rate || rate > INT_MAX || m_outRate <= 0) return fail(E_INVALIDARG);
    if (FAILED(native->GetUINT32(MF_MT_AUDIO_NUM_CHANNELS, &nativeChannels)) || !nativeChannels || nativeChannels > 64)
        return fail(MF_E_INVALIDMEDIATYPE);
    hr = MFCreateMediaType(&type);
    if (FAILED(hr)) return fail(hr);
    if (FAILED(hr = type->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio)) ||
        FAILED(hr = type->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_Float)) ||
        FAILED(hr = type->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 32)) ||
        FAILED(hr = type->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, nativeChannels)) ||
        FAILED(hr = type->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, rate)) ||
        FAILED(hr = d->reader->SetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM, nullptr, type.Get())) ||
        FAILED(hr = d->reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_AUDIO_STREAM, &actual)))
        return fail(hr);
    UINT32 channels = 0, bits = 0, actualRate = 0;
    GUID subtype{};
    if (FAILED(actual->GetUINT32(MF_MT_AUDIO_NUM_CHANNELS, &channels)) || channels != nativeChannels ||
        FAILED(actual->GetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, &bits)) || bits != 32 ||
        FAILED(actual->GetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, &actualRate)) || actualRate != rate ||
        FAILED(actual->GetGUID(MF_MT_SUBTYPE, &subtype)) || subtype != MFAudioFormat_Float)
        return fail(MF_E_INVALIDMEDIATYPE);
    m_rate = int(rate); m_channels = int(channels);
    PROPVARIANT length;
    PropVariantInit(&length);
    if (SUCCEEDED(d->reader->GetPresentationAttribute(MF_SOURCE_READER_MEDIASOURCE, MF_PD_DURATION, &length)) && length.vt == VT_UI8) {
        m_duration = double(length.uhVal.QuadPart) / 10000000;
        m_length = quint64(std::llround(m_duration * m_rate));
    }
    PropVariantClear(&length);
    m_resampler = std::make_unique<MixCore::Resampler>(m_rate, m_outRate, 2);
    return true;
}

size_t MfSource::read(std::vector<float> &out, size_t frames) {
    if (!m_resampler || !m_error.isEmpty()) return 0;
    while ((m_pending.size() - m_pendingAt) / 2 < frames && !m_done) {
        DWORD flags = 0;
        LONGLONG timestamp = 0;
        ComPtr<IMFSample> sample;
        HRESULT hr = d->reader->ReadSample(MF_SOURCE_READER_FIRST_AUDIO_STREAM, 0, nullptr, &flags, &timestamp, &sample);
        if (FAILED(hr)) { fail(hr); return 0; }
        if (flags & (MF_SOURCE_READERF_ERROR | MF_SOURCE_READERF_CURRENTMEDIATYPECHANGED)) {
            fail(MF_E_INVALIDMEDIATYPE); return 0;
        }
        if (sample) {
            ComPtr<IMFMediaBuffer> buffer;
            hr = sample->ConvertToContiguousBuffer(&buffer);
            if (FAILED(hr)) { fail(hr); return 0; }
            BYTE *bytes = nullptr;
            DWORD size = 0;
            hr = buffer->Lock(&bytes, nullptr, &size);
            if (FAILED(hr)) { fail(hr); return 0; }
            const size_t frameBytes = size_t(m_channels) * sizeof(float);
            if (size % frameBytes) { buffer->Unlock(); fail(MF_E_INVALIDMEDIATYPE); return 0; }
            // AAC có khung mồi/đệm: cache chỉ chứa khoảng trình bày, không kéo dài vòng nhạc.
            const size_t skip = timestamp < 0 ? size_t(std::min<quint64>(size / frameBytes, quint64(std::llround(-double(timestamp) * m_rate / 10000000)))) : 0;
            size_t count = size / frameBytes - skip;
            if (m_length) count = size_t(std::min<quint64>(count, m_length - std::min(m_length, m_fed)));
            std::vector<float> stereo(count * 2);
            // Không nhờ MF đổi số kênh: mono nhân đôi, đa kênh lấy hai kênh đầu.
            for (size_t i = 0; i < count; ++i) {
                float left, right;
                std::memcpy(&left, bytes + (i + skip) * frameBytes, sizeof(float));
                std::memcpy(&right, bytes + (i + skip) * frameBytes + (m_channels > 1 ? sizeof(float) : 0), sizeof(float));
                if (!std::isfinite(left) || !std::isfinite(right)) {
                    buffer->Unlock(); fail(MF_E_INVALIDMEDIATYPE); return 0;
                }
                stereo[i * 2] = left; stereo[i * 2 + 1] = right;
            }
            buffer->Unlock();
            if (count) m_resampler->push(stereo.data(), count, m_pending);
            m_fed += count;
        }
        if (flags & MF_SOURCE_READERF_ENDOFSTREAM) {
            m_done = true; m_duration = double(m_fed) / m_rate;
            const std::vector<float> silence(size_t(m_resampler->taps()) * 2, 0.0f);
            m_resampler->push(silence.data(), size_t(m_resampler->taps()), m_pending);
            const size_t want = size_t(m_resampler->outFramesFor(m_fed) - m_given) * 2 + m_pendingAt;
            if (m_pending.size() > want) m_pending.resize(want);
        }
    }
    const size_t n = std::min(frames, (m_pending.size() - m_pendingAt) / 2);
    out.insert(out.end(), m_pending.begin() + m_pendingAt, m_pending.begin() + m_pendingAt + n * 2);
    m_pendingAt += n * 2; m_given += n;
    if (m_pendingAt > 1 << 16) {
        m_pending.erase(m_pending.begin(), m_pending.begin() + m_pendingAt); m_pendingAt = 0;
    }
    return n;
}
