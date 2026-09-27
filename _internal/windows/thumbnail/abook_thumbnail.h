// Thumbnail của Explorer cho file ABook (.abook, .abookproj): hiện bìa sách thay cho icon.
// Dùng chung giữa DLL và chương trình thử (thumbnail_probe) - chương trình thử nạp DLL thẳng, không đụng registry.
#pragma once

#include <windows.h>

// {8464156A-A4BD-4FDE-9FDD-57CB16936684}
static const CLSID CLSID_AbookThumbnail = {
    0x8464156a, 0xa4bd, 0x4fde, {0x9f, 0xdd, 0x57, 0xcb, 0x16, 0x93, 0x66, 0x84}};

// IThumbnailProvider / IInitializeWithStream viết thẳng ra: bản build không phụ thuộc thư viện import của MinGW
// có mang sẵn IID nào hay không.
static const IID IID_AbookThumbnailProvider = {
    0xe357fccd, 0xa995, 0x4576, {0xb0, 0x1f, 0x23, 0x46, 0x30, 0x15, 0x4e, 0x96}};
static const IID IID_AbookInitializeWithStream = {
    0xb824b49d, 0x22ac, 0x4161, {0xac, 0x8a, 0x99, 0x16, 0xe8, 0xfa, 0x3f, 0x7f}};
