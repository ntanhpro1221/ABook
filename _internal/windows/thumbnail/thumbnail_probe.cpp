// Thử thumbnail handler KHÔNG cần registry: nạp DLL thẳng, dựng đối tượng qua DllGetClassObject, đưa stream của file
// như Explorer làm, rồi ghi thumbnail ra PNG.
//
//   thumbnail_probe <abook_thumbnail.dll> <file .abook> <cỡ> <ra.png>
//
// In "rộng cao alpha" khi có thumbnail (mã thoát 0); handler trả lỗi (không có bìa, gói lạ) thì in mã lỗi, thoát 2.

#include "abook_thumbnail.h"

#include <objbase.h>
#include <propsys.h>
#include <shlwapi.h>
#include <thumbcache.h>
#include <wincodec.h>

#include <cstdio>
#include <cwchar>
#include <initializer_list>

namespace {

const CLSID kWicFactory = {0xcacaf262, 0x9370, 0x4615, {0xa1, 0x3b, 0x9f, 0x55, 0x39, 0xda, 0x4c, 0x0a}};
const IID kIWicFactory = {0xec5ec8a9, 0xc395, 0x4314, {0x9c, 0x77, 0x54, 0xd7, 0xa9, 0x35, 0xff, 0x70}};
const GUID kPng = {0x1b7cfaf4, 0x713f, 0x473c, {0xbb, 0xcd, 0x61, 0x37, 0x42, 0x5f, 0xae, 0xaf}};
const GUID kBgra32 = {0x6fddc324, 0x4e03, 0x4bfe, {0xb1, 0x85, 0x3d, 0x77, 0x76, 0x8d, 0xc9, 0x0f}};

using GetClassObject = HRESULT(__stdcall*)(REFCLSID, REFIID, void**);

bool save_png(HBITMAP bitmap, const wchar_t* path, UINT* width, UINT* height) {
    IWICImagingFactory* factory = nullptr;
    IWICBitmap* source = nullptr;
    IWICStream* output = nullptr;
    IWICBitmapEncoder* encoder = nullptr;
    IWICBitmapFrameEncode* frame = nullptr;
    IPropertyBag2* options = nullptr;
    WICPixelFormatGUID format = kBgra32;
    HRESULT hr = CoCreateInstance(kWicFactory, nullptr, CLSCTX_INPROC_SERVER, kIWicFactory,
                                  reinterpret_cast<void**>(&factory));
    if (SUCCEEDED(hr)) hr = factory->CreateBitmapFromHBITMAP(bitmap, nullptr, WICBitmapIgnoreAlpha, &source);
    if (SUCCEEDED(hr)) hr = source->GetSize(width, height);
    if (SUCCEEDED(hr)) hr = factory->CreateStream(&output);
    if (SUCCEEDED(hr)) hr = output->InitializeFromFilename(path, GENERIC_WRITE);
    if (SUCCEEDED(hr)) hr = factory->CreateEncoder(kPng, nullptr, &encoder);
    if (SUCCEEDED(hr)) hr = encoder->Initialize(output, WICBitmapEncoderNoCache);
    if (SUCCEEDED(hr)) hr = encoder->CreateNewFrame(&frame, &options);
    if (SUCCEEDED(hr)) hr = frame->Initialize(options);
    if (SUCCEEDED(hr)) hr = frame->SetSize(*width, *height);
    if (SUCCEEDED(hr)) hr = frame->SetPixelFormat(&format);
    if (SUCCEEDED(hr)) hr = frame->WriteSource(source, nullptr);
    if (SUCCEEDED(hr)) hr = frame->Commit();
    if (SUCCEEDED(hr)) hr = encoder->Commit();
    for (IUnknown* object : {static_cast<IUnknown*>(options), static_cast<IUnknown*>(frame),
                             static_cast<IUnknown*>(encoder), static_cast<IUnknown*>(output),
                             static_cast<IUnknown*>(source), static_cast<IUnknown*>(factory)}) {
        if (object) object->Release();
    }
    return SUCCEEDED(hr);
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc != 5) {
        std::fwprintf(stderr, L"dùng: thumbnail_probe <dll> <file> <cỡ> <ra.png>\n");
        return 64;
    }
    if (FAILED(CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED))) return 70;
    HMODULE module = LoadLibraryW(argv[1]);
    if (!module) {
        std::fwprintf(stderr, L"không nạp được DLL (%lu)\n", GetLastError());
        return 70;
    }
    auto get = reinterpret_cast<GetClassObject>(reinterpret_cast<void*>(GetProcAddress(module, "DllGetClassObject")));
    IClassFactory* factory = nullptr;
    IInitializeWithStream* initialize = nullptr;
    IThumbnailProvider* provider = nullptr;
    IStream* stream = nullptr;
    HBITMAP bitmap = nullptr;
    WTS_ALPHATYPE alpha = WTSAT_UNKNOWN;
    HRESULT hr = get ? get(CLSID_AbookThumbnail, IID_IClassFactory, reinterpret_cast<void**>(&factory)) : E_NOINTERFACE;
    if (SUCCEEDED(hr)) {
        hr = factory->CreateInstance(nullptr, IID_AbookInitializeWithStream, reinterpret_cast<void**>(&initialize));
    }
    if (SUCCEEDED(hr)) hr = SHCreateStreamOnFileEx(argv[2], STGM_READ | STGM_SHARE_DENY_NONE, 0, FALSE, nullptr, &stream);
    if (SUCCEEDED(hr)) hr = initialize->Initialize(stream, STGM_READ);
    if (SUCCEEDED(hr)) hr = initialize->QueryInterface(IID_AbookThumbnailProvider, reinterpret_cast<void**>(&provider));
    if (FAILED(hr)) {
        std::fwprintf(stderr, L"dựng handler lỗi 0x%08lx\n", static_cast<unsigned long>(hr));
        return 70;
    }
    hr = provider->GetThumbnail(static_cast<UINT>(_wtoi(argv[3])), &bitmap, &alpha);
    int code = 0;
    if (FAILED(hr)) {
        std::printf("no-thumbnail 0x%08lx\n", static_cast<unsigned long>(hr));
        code = 2;
    } else {
        UINT width = 0, height = 0;
        if (!save_png(bitmap, argv[4], &width, &height)) {
            code = 70;
        } else {
            std::printf("%u %u %d\n", width, height, static_cast<int>(alpha));
        }
        DeleteObject(bitmap);
    }
    provider->Release();
    initialize->Release();
    stream->Release();
    factory->Release();
    CoUninitialize();
    return code;
}
