// Thumbnail của Explorer cho .abook / .abookproj: bìa sách (mục `cover.jpg` trong gói ZIP).
//
// Explorer đưa một IStream của file; ta chỉ đọc MỤC LỤC ZIP ở cuối file rồi đúng đoạn byte của bìa - không bao giờ
// lướt qua hàng trăm MB audio. Gói của app luôn cất bìa KHÔNG NÉN (abook/webui/bookfile.py: _STORED), nên không
// cần zlib: bìa nén (gói lạ) hay không có bìa thì trả lỗi và Explorer hiện icon loại file như thường.
// Giải mã JPEG, thu nhỏ bằng WIC của Windows. Icon nhỏ ở góc thumbnail là TypeOverlay trong registry (trình cài đặt).
//
// Build: scripts/build_thumbnail_handler.py (MinGW-w64). Thử không cần registry: thumbnail_probe.cpp.

#include "abook_thumbnail.h"

#include <objbase.h>
#include <propsys.h>
#include <shlwapi.h>
#include <thumbcache.h>
#include <wincodec.h>

#include <cstdint>
#include <cstring>
#include <new>
#include <vector>

namespace {

long g_objects = 0;  // số đối tượng còn sống + số lần khoá: DllCanUnloadNow

// WIC: viết thẳng GUID như abook_thumbnail.h
const CLSID kWicFactory = {0xcacaf262, 0x9370, 0x4615, {0xa1, 0x3b, 0x9f, 0x55, 0x39, 0xda, 0x4c, 0x0a}};
const IID kIWicFactory = {0xec5ec8a9, 0xc395, 0x4314, {0x9c, 0x77, 0x54, 0xd7, 0xa9, 0x35, 0xff, 0x70}};
const GUID kPbgra32 = {0x6fddc324, 0x4e03, 0x4bfe, {0xb1, 0x85, 0x3d, 0x77, 0x76, 0x8d, 0xc9, 0x10}};

constexpr ULONGLONG kMaxCentralDirectory = 64ull << 20;  // mục lục ZIP lớn hơn thế là gói lạ
constexpr ULONGLONG kMaxCover = 32ull << 20;

uint16_t le16(const BYTE* p) { return uint16_t(p[0] | (p[1] << 8)); }
uint32_t le32(const BYTE* p) { return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24); }
uint64_t le64(const BYTE* p) { return uint64_t(le32(p)) | (uint64_t(le32(p + 4)) << 32); }

bool read_at(IStream* stream, ULONGLONG offset, void* buffer, ULONGLONG size) {
    LARGE_INTEGER position;
    position.QuadPart = LONGLONG(offset);
    if (FAILED(stream->Seek(position, STREAM_SEEK_SET, nullptr))) return false;
    auto* out = static_cast<BYTE*>(buffer);
    ULONGLONG done = 0;
    while (done < size) {
        ULONG chunk = ULONG(size - done > 0x40000000ull ? 0x40000000ull : size - done);
        ULONG got = 0;
        HRESULT hr = stream->Read(out + done, chunk, &got);
        if (FAILED(hr) || got == 0) return false;
        done += got;
    }
    return true;
}

// Tìm `cover.jpg` KHÔNG NÉN: trả vị trí + cỡ dữ liệu trong file. Hỗ trợ ZIP64 (gói > 4 GB hay > 65 535 mục).
bool find_cover(IStream* stream, ULONGLONG* data_offset, ULONGLONG* data_size) {
    STATSTG stat = {};
    if (FAILED(stream->Stat(&stat, STATFLAG_NONAME))) return false;
    const ULONGLONG file_size = stat.cbSize.QuadPart;
    if (file_size < 22) return false;
    const ULONGLONG tail = file_size < 65557 ? file_size : 65557;  // bản ghi cuối (22) + chú thích tối đa 65 535
    std::vector<BYTE> end(size_t(tail), 0);
    if (!read_at(stream, file_size - tail, end.data(), tail)) return false;
    long eocd = -1;
    for (long i = long(tail) - 22; i >= 0; --i) {
        if (le32(&end[size_t(i)]) == 0x06054b50) {
            eocd = i;
            break;
        }
    }
    if (eocd < 0) return false;
    const BYTE* record = &end[size_t(eocd)];
    ULONGLONG entries = le16(record + 10), directory_size = le32(record + 12), directory_offset = le32(record + 16);
    if (entries == 0xffff || directory_size == 0xffffffffull || directory_offset == 0xffffffffull) {
        if (eocd < 20 || le32(record - 20) != 0x07064b50) return false;  // thiếu bộ định vị ZIP64
        BYTE zip64[56];
        if (!read_at(stream, le64(record - 20 + 8), zip64, sizeof zip64) || le32(zip64) != 0x06064b50) return false;
        entries = le64(zip64 + 32);
        directory_size = le64(zip64 + 40);
        directory_offset = le64(zip64 + 48);
    }
    if (directory_size > kMaxCentralDirectory || directory_offset + directory_size > file_size) return false;
    std::vector<BYTE> directory(size_t(directory_size), 0);
    if (!read_at(stream, directory_offset, directory.data(), directory_size)) return false;
    size_t at = 0;
    for (ULONGLONG n = 0; n < entries && at + 46 <= directory.size(); ++n) {
        const BYTE* entry = &directory[at];
        if (le32(entry) != 0x02014b50) return false;
        const uint16_t method = le16(entry + 10), name_length = le16(entry + 28), extra_length = le16(entry + 30),
                       comment_length = le16(entry + 32);
        ULONGLONG compressed = le32(entry + 20), size = le32(entry + 24), local = le32(entry + 42);
        const size_t next = at + 46 + name_length + extra_length + comment_length;
        if (next > directory.size()) return false;
        if (name_length == 9 && std::memcmp(entry + 46, "cover.jpg", 9) == 0) {
            // Trường ZIP64 (id 1): chỉ mang những giá trị bị đặt 0xFFFFFFFF, theo đúng thứ tự cỡ, cỡ nén, vị trí.
            size_t field = at + 46 + name_length;
            const size_t fields_end = field + extra_length;
            while (field + 4 <= fields_end) {
                const uint16_t id = le16(&directory[field]), length = le16(&directory[field + 2]);
                size_t value = field + 4;
                if (id == 1) {
                    if (size == 0xffffffffull && value + 8 <= fields_end) { size = le64(&directory[value]); value += 8; }
                    if (compressed == 0xffffffffull && value + 8 <= fields_end) { compressed = le64(&directory[value]); value += 8; }
                    if (local == 0xffffffffull && value + 8 <= fields_end) { local = le64(&directory[value]); }
                    break;
                }
                field += 4 + length;
            }
            if (method != 0 || compressed != size || size == 0 || size > kMaxCover) return false;
            BYTE header[30];
            if (!read_at(stream, local, header, sizeof header) || le32(header) != 0x04034b50) return false;
            *data_offset = local + 30 + le16(header + 26) + le16(header + 28);
            *data_size = size;
            return *data_offset + size <= file_size;
        }
        at = next;
    }
    return false;
}

template <typename T>
void release(T*& pointer) {
    if (pointer) {
        pointer->Release();
        pointer = nullptr;
    }
}

// Giải mã JPEG trong bộ nhớ, thu vừa khung cx x cx (giữ tỉ lệ), trả HBITMAP 32 bit.
HRESULT decode(const std::vector<BYTE>& jpeg, UINT cx, HBITMAP* bitmap) {
    IWICImagingFactory* factory = nullptr;
    IWICStream* input = nullptr;
    IWICBitmapDecoder* decoder = nullptr;
    IWICBitmapFrameDecode* frame = nullptr;
    IWICBitmapScaler* scaler = nullptr;
    IWICFormatConverter* converter = nullptr;
    HRESULT hr = CoCreateInstance(kWicFactory, nullptr, CLSCTX_INPROC_SERVER, kIWicFactory,
                                  reinterpret_cast<void**>(&factory));
    UINT width = 0, height = 0, fit_width = 0, fit_height = 0;
    if (SUCCEEDED(hr)) hr = factory->CreateStream(&input);
    if (SUCCEEDED(hr)) hr = input->InitializeFromMemory(const_cast<BYTE*>(jpeg.data()), DWORD(jpeg.size()));
    if (SUCCEEDED(hr)) hr = factory->CreateDecoderFromStream(input, nullptr, WICDecodeMetadataCacheOnDemand, &decoder);
    if (SUCCEEDED(hr)) hr = decoder->GetFrame(0, &frame);
    if (SUCCEEDED(hr)) hr = frame->GetSize(&width, &height);
    if (SUCCEEDED(hr) && (width == 0 || height == 0)) hr = E_FAIL;
    if (SUCCEEDED(hr)) {
        const double scale = double(cx) / double(width > height ? width : height);
        fit_width = UINT(double(width) * scale + 0.5);
        fit_height = UINT(double(height) * scale + 0.5);
        if (fit_width == 0) fit_width = 1;
        if (fit_height == 0) fit_height = 1;
        hr = factory->CreateBitmapScaler(&scaler);
    }
    if (SUCCEEDED(hr)) hr = scaler->Initialize(frame, fit_width, fit_height, WICBitmapInterpolationModeFant);
    if (SUCCEEDED(hr)) hr = factory->CreateFormatConverter(&converter);
    if (SUCCEEDED(hr)) {
        hr = converter->Initialize(scaler, kPbgra32, WICBitmapDitherTypeNone, nullptr, 0.0,
                                   WICBitmapPaletteTypeCustom);
    }
    if (SUCCEEDED(hr)) {
        BITMAPINFO info = {};
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = LONG(fit_width);
        info.bmiHeader.biHeight = -LONG(fit_height);  // từ trên xuống
        info.bmiHeader.biPlanes = 1;
        info.bmiHeader.biBitCount = 32;
        info.bmiHeader.biCompression = BI_RGB;
        void* pixels = nullptr;
        HBITMAP result = CreateDIBSection(nullptr, &info, DIB_RGB_COLORS, &pixels, nullptr, 0);
        if (!result) {
            hr = E_OUTOFMEMORY;
        } else {
            hr = converter->CopyPixels(nullptr, fit_width * 4, fit_width * 4 * fit_height, static_cast<BYTE*>(pixels));
            if (SUCCEEDED(hr)) {
                *bitmap = result;
            } else {
                DeleteObject(result);
            }
        }
    }
    release(converter);
    release(scaler);
    release(frame);
    release(decoder);
    release(input);
    release(factory);
    return hr;
}

class ThumbnailProvider final : public IInitializeWithStream, public IThumbnailProvider {
public:
    ThumbnailProvider() { InterlockedIncrement(&g_objects); }

    IFACEMETHODIMP QueryInterface(REFIID riid, void** out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_AbookInitializeWithStream)) {
            *out = static_cast<IInitializeWithStream*>(this);
        } else if (IsEqualIID(riid, IID_AbookThumbnailProvider)) {
            *out = static_cast<IThumbnailProvider*>(this);
        } else {
            *out = nullptr;
            return E_NOINTERFACE;
        }
        AddRef();
        return S_OK;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return ULONG(InterlockedIncrement(&references_)); }
    IFACEMETHODIMP_(ULONG) Release() override {
        const long left = InterlockedDecrement(&references_);
        if (left == 0) delete this;
        return ULONG(left);
    }

    IFACEMETHODIMP Initialize(IStream* stream, DWORD) override {
        if (!stream) return E_INVALIDARG;
        if (stream_) return HRESULT_FROM_WIN32(ERROR_ALREADY_INITIALIZED);
        stream_ = stream;
        stream_->AddRef();
        return S_OK;
    }

    IFACEMETHODIMP GetThumbnail(UINT cx, HBITMAP* bitmap, WTS_ALPHATYPE* alpha) override {
        if (!bitmap || !alpha) return E_POINTER;
        *bitmap = nullptr;
        *alpha = WTSAT_UNKNOWN;
        if (!stream_ || cx == 0) return E_UNEXPECTED;
        ULONGLONG offset = 0, size = 0;
        if (!find_cover(stream_, &offset, &size)) return E_FAIL;
        std::vector<BYTE> jpeg;
        try {
            jpeg.resize(size_t(size));
        } catch (const std::bad_alloc&) {
            return E_OUTOFMEMORY;
        }
        if (!read_at(stream_, offset, jpeg.data(), size)) return E_FAIL;
        const HRESULT hr = decode(jpeg, cx, bitmap);
        if (SUCCEEDED(hr)) *alpha = WTSAT_RGB;  // bìa JPEG, không có vùng trong suốt
        return hr;
    }

private:
    ~ThumbnailProvider() {
        release(stream_);
        InterlockedDecrement(&g_objects);
    }

    long references_ = 1;
    IStream* stream_ = nullptr;
};

class Factory final : public IClassFactory {
public:
    IFACEMETHODIMP QueryInterface(REFIID riid, void** out) override {
        if (!out) return E_POINTER;
        if (IsEqualIID(riid, IID_IUnknown) || IsEqualIID(riid, IID_IClassFactory)) {
            *out = static_cast<IClassFactory*>(this);
            AddRef();
            return S_OK;
        }
        *out = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return 2; }  // đối tượng tĩnh
    IFACEMETHODIMP_(ULONG) Release() override { return 1; }

    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (outer) return CLASS_E_NOAGGREGATION;
        auto* provider = new (std::nothrow) ThumbnailProvider();
        if (!provider) return E_OUTOFMEMORY;
        const HRESULT hr = provider->QueryInterface(riid, out);
        provider->Release();
        return hr;
    }
    IFACEMETHODIMP LockServer(BOOL lock) override {
        if (lock) {
            InterlockedIncrement(&g_objects);
        } else {
            InterlockedDecrement(&g_objects);
        }
        return S_OK;
    }
};

Factory g_factory;

}  // namespace

extern "C" HRESULT __stdcall DllGetClassObject(REFCLSID clsid, REFIID riid, void** out) {
    if (!out) return E_POINTER;
    *out = nullptr;
    if (!IsEqualCLSID(clsid, CLSID_AbookThumbnail)) return CLASS_E_CLASSNOTAVAILABLE;
    return g_factory.QueryInterface(riid, out);
}

extern "C" HRESULT __stdcall DllCanUnloadNow() { return g_objects == 0 ? S_OK : S_FALSE; }
