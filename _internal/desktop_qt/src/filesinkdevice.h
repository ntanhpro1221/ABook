// Thiết bị giả cho công cụ kiểm tiếng: tiêu thụ theo đồng hồ thật như một endpoint WASAPI chia sẻ, nhưng ghi ra WAV
// thay vì phát loa. Thiếu dữ liệu thì ghi đúng khoảng lặng người nghe sẽ nghe, nên file là "tai" của phép kiểm.
#pragma once

#include "musicmixer.h"

#include <QFile>
#include <QtEndian>

#include <atomic>
#include <chrono>
#include <deque>
#include <vector>

class FileSinkDevice final : public MixDevice {
public:
    struct Gap { quint64 at, frames; };

    FileSinkDevice(const QString &path, int rate = 48000, size_t capacity = 48000) : m_file(path), m_rate(rate), m_capacity(capacity) {
        if (m_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) m_file.write(QByteArray(44, '\0'));
    }
    ~FileSinkDevice() override {
        advance();
        finish();
    }
    int rate() const override { return m_rate; }
    bool start() override {
        advance();
        if (!m_running) {
            const auto now = Clock::now();
            if (m_stopped) {
                // Endpoint chung vẫn chạy khi luồng này dừng: người nghe nghe im lặng suốt khoảng Stop -> Start.
                const auto frames = quint64(std::chrono::duration<double>(now - m_stoppedAt).count() * m_rate);
                m_stops.push_back({m_played.load(), frames});
                m_scratch.assign(size_t(frames * 2), 0.0f);
                emit_(m_scratch.data(), frames);
                m_stopped = false;
            }
            m_running = true; m_last = now; m_carry = 0; m_lastNs = m_last.time_since_epoch().count(); m_live = true;
        }
        return m_file.isOpen();
    }
    void stop() override {
        advance();
        if (m_running) { m_stopped = true; m_stoppedAt = Clock::now(); }
        m_running = false; m_live = false;
    }
    // Như IAudioClient::Reset: bỏ phần còn trong hàng đợi chưa ra loa.
    void reset() override { m_queue.clear(); }
    size_t padding() override { advance(); return m_queue.size() / 2; }
    size_t bufferFrames() const override { return m_capacity; }
    bool write(const float *stereo, size_t frames) override {
        advance();
        if (m_queue.size() / 2 + frames > m_capacity) return false;
        m_queue.insert(m_queue.end(), stereo, stereo + frames * 2);
        return true;
    }
    // Khung đã "ra loa" (kể cả khoảng lặng do thiếu dữ liệu); đọc được từ luồng khác để đánh mốc.
    quint64 played() const { return m_played.load(); }
    // Khung đang ra loa lúc này, gọi được từ luồng khác (mốc thao tác của công cụ): phần đã ghi + phần đồng hồ đã chạy từ lần ghi cuối.
    quint64 now() const {
        const quint64 base = m_played.load();
        if (!m_live.load()) return base;
        const double since = double(Clock::now().time_since_epoch().count() - m_lastNs.load()) * Clock::period::num / Clock::period::den;
        return base + quint64(std::max(0.0, since) * m_rate);
    }
    const std::vector<Gap> &gaps() const { return m_gaps; }

private:
    using Clock = std::chrono::steady_clock;
    QFile m_file;
    int m_rate;
    size_t m_capacity;
    bool m_running = false, m_stopped = false;
    Clock::time_point m_last, m_stoppedAt;
    std::vector<Gap> m_stops;
    double m_carry = 0;
    std::deque<float> m_queue;
    std::atomic<quint64> m_played{0};
    std::atomic<long long> m_lastNs{0};
    std::atomic<bool> m_live{false};
    std::vector<Gap> m_gaps;
    std::vector<float> m_scratch;

    void advance() {
        if (!m_running) return;
        const auto now = Clock::now();
        m_carry += std::chrono::duration<double>(now - m_last).count() * m_rate;
        m_last = now;
        const auto due = quint64(m_carry);
        if (!due) return;
        m_carry -= double(due);
        struct Stamp { FileSinkDevice *d; Clock::time_point t; ~Stamp() { d->m_lastNs = t.time_since_epoch().count() - (long long)(d->m_carry / d->m_rate * Clock::period::den / Clock::period::num); } } stamp{this, now};
        const quint64 have = std::min<quint64>(due, m_queue.size() / 2);
        m_scratch.assign(m_queue.begin(), m_queue.begin() + qsizetype(have * 2));
        m_queue.erase(m_queue.begin(), m_queue.begin() + qsizetype(have * 2));
        emit_(m_scratch.data(), have);
        if (due > have) {
            // Endpoint chạy mà không có dữ liệu: loa phát im lặng, người nghe nghe thấy một khoảng hụt.
            const quint64 missing = due - have;
            if (!m_gaps.empty() && m_gaps.back().at + m_gaps.back().frames == m_played.load()) m_gaps.back().frames += missing;
            else m_gaps.push_back({m_played.load(), missing});
            m_scratch.assign(size_t(missing * 2), 0.0f);
            emit_(m_scratch.data(), missing);
        }
    }
    void emit_(const float *data, quint64 frames) {
        if (!frames) return;
        if (m_file.isOpen()) m_file.write(reinterpret_cast<const char *>(data), qint64(frames * 8));
        m_played += frames;
    }
    void finish() {
        if (!m_file.isOpen()) return;
        const quint32 bytes = quint32(m_played.load() * 8);
        QByteArray h(44, '\0');
        auto put32 = [&](int at, quint32 v) { qToLittleEndian<quint32>(v, h.data() + at); };
        auto put16 = [&](int at, quint16 v) { qToLittleEndian<quint16>(v, h.data() + at); };
        std::copy_n("RIFF", 4, h.data()); put32(4, 36 + bytes); std::copy_n("WAVEfmt ", 8, h.data() + 8);
        put32(16, 16); put16(20, 3); put16(22, 2); put32(24, quint32(m_rate)); put32(28, quint32(m_rate) * 8); put16(32, 8); put16(34, 32);
        std::copy_n("data", 4, h.data() + 36); put32(40, bytes);
        m_file.seek(0); m_file.write(h); m_file.close();
        // Khoảng hụt (endpoint chạy mà không có dữ liệu) ghi cạnh file WAV: mỗi dòng "khung_bắt_đầu số_khung".
        QFile gaps(m_file.fileName() + QStringLiteral(".gaps"));
        if (gaps.open(QIODevice::WriteOnly | QIODevice::Truncate))
            for (const auto &g : m_gaps) gaps.write(QByteArray::number(g.at) + ' ' + QByteArray::number(g.frames) + '\n');
        // Khoảng luồng bị Stop (pause, hay Stop/Reset/Start khi tua, đổi tốc độ, đổi âm lượng): cùng định dạng.
        QFile stops(m_file.fileName() + QStringLiteral(".stops"));
        if (stops.open(QIODevice::WriteOnly | QIODevice::Truncate))
            for (const auto &g : m_stops) stops.write(QByteArray::number(g.at) + ' ' + QByteArray::number(g.frames) + '\n');
    }
};
