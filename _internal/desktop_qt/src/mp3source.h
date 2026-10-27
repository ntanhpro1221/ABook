// Nguồn mp3 cho bộ trộn WASAPI: minimp3 (CC0, third_party/minimp3) giải mã cả tệp đã nạp vào bộ nhớ, ra float STEREO ở tần số trộn.
// Đo 27-10 (native_desk_proto/music_wasapi_design.md): minimp3 0,058 % một nhân cho nhạc 44,1k stereo, Media Foundation 0,22 (0,39 khi ra 48k).
// Bỏ khoảng lặng đầu / đệm cuối của bộ mã hoá (thẻ LAME) nên vòng lặp liền; tua chính xác tới mẫu.
#pragma once

#include "mixcore.h"

#include <QByteArray>

#include <memory>
#include <vector>

class Mp3Source {
public:
    explicit Mp3Source(int outRate);
    ~Mp3Source();
    Mp3Source(const Mp3Source &) = delete;
    Mp3Source &operator=(const Mp3Source &) = delete;

    /// Nhận cả tệp; false = không phải mp3 đọc được.
    bool open(const QByteArray &data);
    int sourceRate() const { return m_rate; }
    int sourceChannels() const { return m_channels; }
    /// Giây, đã trừ khoảng lặng của bộ mã hoá.
    double duration() const;
    /// Giây của khung ra kế tiếp.
    double position() const;
    void seek(double seconds);
    /// Thêm tối đa `frames` khung ra (stereo xen kênh) vào cuối `out`; trả số khung đã thêm, 0 = hết nguồn.
    size_t read(std::vector<float> &out, size_t frames);
    bool atEnd() const;

private:
    struct Decoder;
    std::unique_ptr<Decoder> d;
    QByteArray m_data;
    int m_outRate;
    int m_rate = 0, m_channels = 0;
    std::unique_ptr<MixCore::Resampler> m_resampler;
    std::vector<float> m_pending;   // khung ra đã tính, chưa đưa đi
    size_t m_pendingAt = 0;
    double m_seekSeconds = 0;       // chỗ tua cuối
    unsigned long long m_fed = 0;   // khung nguồn đã đưa vào bộ đổi tần số kể từ lần tua cuối
    unsigned long long m_given = 0; // khung ra đã trả kể từ lần tua cuối
    bool m_sourceDone = false;
};
