// Thiết bị giả cho công cụ kiểm tiếng: tiêu thụ theo đồng hồ thật như engine WASAPI chia sẻ, nhưng ghi ra WAV thay vì
// phát loa. Engine kéo dữ liệu từng chu kỳ (mặc định 10 ms) ở ranh chu kỳ: luồng đang dừng đúng lúc ấy thì cả chu kỳ là
// im lặng, thiếu dữ liệu thì phần thiếu là im lặng. File vì thế là "tai" của phép kiểm.
#pragma once

#include "musicmixer.h"

#include <QFile>
#include <QtEndian>

#include <atomic>
#include <chrono>
#include <cmath>
#include <deque>
#include <thread>
#include <vector>

class FileSinkDevice final : public MixDevice {
public:
    struct Gap { quint64 at, frames; };

    FileSinkDevice(const QString &path, int rate = 48000, size_t capacity = 48000, int periodMs = 10)
        : m_file(path), m_rate(rate), m_capacity(capacity), m_period(std::max<size_t>(1, size_t(rate) * size_t(periodMs) / 1000)) {
        if (m_file.open(QIODevice::WriteOnly | QIODevice::Truncate)) m_file.write(QByteArray(44, '\0'));
    }
    ~FileSinkDevice() override {
        advance();
        finish();
    }
    int rate() const override { return m_rate; }
    bool start() override {
        advance();
        if (!m_started) { m_started = true; m_epoch = Clock::now(); m_ticks = 0; m_epochNs = m_epoch.time_since_epoch().count(); }
        m_running = true;
        return m_file.isOpen();
    }
    void stop() override { advance(); m_running = false; }
    // Như IAudioClient::Reset: bỏ phần còn trong hàng đợi chưa được engine kéo.
    void reset() override { m_queue.clear(); }
    size_t padding() override { advance(); return m_queue.size() / 2; }
    size_t bufferFrames() const override { return m_capacity; }
    // Như sự kiện của WASAPI event-driven: trả về ngay sau ranh chu kỳ kế tiếp (chờ quay, sleep của Windows quá thô).
    void awaitPull(int maxMs) override {
        if (!m_started || !m_running) return;
        const auto period = std::chrono::duration<double>(double(m_period) / m_rate);
        const auto since = std::chrono::duration<double>(Clock::now() - m_epoch);
        const auto next = m_epoch + std::chrono::duration_cast<Clock::duration>(period * (std::floor(since / period) + 1));
        const auto until = std::min(next, Clock::now() + std::chrono::milliseconds(maxMs));
        while (Clock::now() < until) std::this_thread::yield();
        advance();
    }
    bool write(const float *stereo, size_t frames) override {
        advance();
        if (m_queue.size() / 2 + frames > m_capacity) return false;
        m_queue.insert(m_queue.end(), stereo, stereo + frames * 2);
        return true;
    }
    // Khung đang ra loa lúc này, gọi được từ luồng khác (mốc thao tác của công cụ): theo ranh chu kỳ của engine.
    quint64 now() const {
        const long long epoch = m_epochNs.load();
        if (!epoch) return 0;
        const double since = double(Clock::now().time_since_epoch().count() - epoch) * Clock::period::num / Clock::period::den;
        return quint64(std::max(0.0, since) * m_rate);
    }

private:
    using Clock = std::chrono::steady_clock;
    QFile m_file;
    int m_rate;
    size_t m_capacity, m_period;
    bool m_started = false, m_running = false;
    Clock::time_point m_epoch;
    quint64 m_ticks = 0, m_played = 0;
    std::atomic<long long> m_epochNs{0};
    std::deque<float> m_queue;
    std::vector<Gap> m_gaps, m_stops;
    std::vector<float> m_scratch;

    static void note(std::vector<Gap> &list, quint64 at, quint64 frames) {
        if (!list.empty() && list.back().at + list.back().frames == at) list.back().frames += frames;
        else list.push_back({at, frames});
    }
    // Mỗi ranh chu kỳ đã qua: engine kéo đúng một chu kỳ của luồng (đang dừng = im lặng cả chu kỳ).
    void advance() {
        if (!m_started) return;
        const auto due = quint64(std::chrono::duration<double>(Clock::now() - m_epoch).count() * m_rate / double(m_period));
        for (; m_ticks < due; ++m_ticks) {
            if (!m_running) {
                note(m_stops, m_played, m_period);
                m_scratch.assign(m_period * 2, 0.0f);
                emit_(m_scratch.data(), m_period);
                continue;
            }
            const size_t have = std::min(m_period, m_queue.size() / 2);
            m_scratch.assign(m_queue.begin(), m_queue.begin() + qsizetype(have * 2));
            m_queue.erase(m_queue.begin(), m_queue.begin() + qsizetype(have * 2));
            m_scratch.resize(m_period * 2, 0.0f);
            if (have < m_period) note(m_gaps, m_played + have, m_period - have);
            emit_(m_scratch.data(), m_period);
        }
    }
    void emit_(const float *data, quint64 frames) {
        if (m_file.isOpen()) m_file.write(reinterpret_cast<const char *>(data), qint64(frames * 8));
        m_played += frames;
    }
    void finish() {
        if (!m_file.isOpen()) return;
        const quint32 bytes = quint32(m_played * 8);
        QByteArray h(44, '\0');
        auto put32 = [&](int at, quint32 v) { qToLittleEndian<quint32>(v, h.data() + at); };
        auto put16 = [&](int at, quint16 v) { qToLittleEndian<quint16>(v, h.data() + at); };
        std::copy_n("RIFF", 4, h.data()); put32(4, 36 + bytes); std::copy_n("WAVEfmt ", 8, h.data() + 8);
        put32(16, 16); put16(20, 3); put16(22, 2); put32(24, quint32(m_rate)); put32(28, quint32(m_rate) * 8); put16(32, 8); put16(34, 32);
        std::copy_n("data", 4, h.data() + 36); put32(40, bytes);
        m_file.seek(0); m_file.write(h); m_file.close();
        // Ghi cạnh file WAV, mỗi dòng "khung_bắt_đầu số_khung": .gaps = engine kéo mà thiếu dữ liệu;
        // .stops = engine kéo đúng lúc luồng đang dừng (pause, hay Stop/Reset/Start khi trộn lại vắt qua ranh chu kỳ).
        for (const auto &[suffix, list] : {std::pair{QStringLiteral(".gaps"), &m_gaps}, std::pair{QStringLiteral(".stops"), &m_stops}}) {
            QFile f(m_file.fileName() + suffix);
            if (f.open(QIODevice::WriteOnly | QIODevice::Truncate))
                for (const auto &g : *list) f.write(QByteArray::number(g.at) + ' ' + QByteArray::number(g.frames) + '\n');
        }
    }
};
