// Lõi trộn thuần của đường âm thanh qua một luồng WASAPI chung (native_desk_proto/music_wasapi_design.md): vòng đệm một-ghi-một-đọc
// giữa luồng giải mã và luồng trộn, bộ đổi tần số đa pha, âm lượng trượt theo khung. Không Qt, không Windows: bộ thử chạy trên số.
#pragma once

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <numeric>
#include <vector>

namespace MixCore {

/// Vòng đệm mẫu float: một luồng ghi (giải mã), một luồng đọc (trộn), không khoá.
class Ring {
public:
    explicit Ring(size_t capacity) : m_data(capacity + 1) {}

    size_t capacity() const { return m_data.size() - 1; }
    size_t readable() const {
        const size_t head = m_head.load(std::memory_order_acquire), tail = m_tail.load(std::memory_order_acquire);
        return head >= tail ? head - tail : head + m_data.size() - tail;
    }
    size_t writable() const { return capacity() - readable(); }

    /// Ghi tối đa `count` mẫu; trả số mẫu đã ghi.
    size_t write(const float *in, size_t count) {
        const size_t size = m_data.size(), tail = m_tail.load(std::memory_order_acquire);
        size_t head = m_head.load(std::memory_order_relaxed);
        const size_t room = (tail + size - head - 1) % size;
        const size_t n = std::min(count, room);
        for (size_t i = 0; i < n; ++i) {
            m_data[head] = in[i];
            head = head + 1 == size ? 0 : head + 1;
        }
        m_head.store(head, std::memory_order_release);
        return n;
    }

    /// Đọc tối đa `count` mẫu; trả số mẫu đã đọc.
    size_t read(float *out, size_t count) {
        const size_t size = m_data.size(), head = m_head.load(std::memory_order_acquire);
        size_t tail = m_tail.load(std::memory_order_relaxed);
        const size_t have = (head + size - tail) % size;
        const size_t n = std::min(count, have);
        for (size_t i = 0; i < n; ++i) {
            out[i] = m_data[tail];
            tail = tail + 1 == size ? 0 : tail + 1;
        }
        m_tail.store(tail, std::memory_order_release);
        return n;
    }

    /// Bỏ hết (tua). Chỉ gọi khi không luồng nào đang ghi hay đọc.
    void clear() {
        m_head.store(0, std::memory_order_relaxed);
        m_tail.store(0, std::memory_order_relaxed);
    }

private:
    std::vector<float> m_data;
    std::atomic<size_t> m_head{0}, m_tail{0};
};

/// Âm lượng trượt tuyến tính theo khung. Đổi đích giữa chừng thì đi tiếp từ chỗ đang đứng: không bậc, không tiếng tách.
class Ramp {
public:
    /// Tới `target` sau `frames` khung (0 = ngay).
    void set(float target, size_t frames) {
        m_target = target;
        m_left = frames;
        if (!frames)
            m_value = target;
        else
            m_step = (target - m_value) / double(frames);
    }
    float value() const { return float(m_value); }
    float target() const { return float(m_target); }
    void advance(size_t frames) {
        const size_t n = std::min(frames, m_left);
        m_left -= n;
        m_value = m_left ? m_value + m_step * double(n) : m_target;
    }

    /// CỘNG `frames` khung (`channels` kênh, xen kênh) của `in`, nhân âm lượng đang trượt, vào `out`.
    void mixInto(float *out, const float *in, size_t frames, int channels) {
        size_t i = 0;
        for (; i < frames && m_left; ++i) {
            m_value = --m_left ? m_value + m_step : m_target;
            for (int c = 0; c < channels; ++c)
                out[i * channels + c] += in[i * channels + c] * float(m_value);
        }
        if (m_value == 0)
            return;
        for (size_t k = i * channels, end = frames * channels; k < end; ++k)
            out[k] += in[k] * float(m_value);
    }

private:
    // Tích luỹ bằng double để hai đường mờ bù nhau vẫn cộng thành 1 sau hàng nghìn khung.
    double m_value = 0, m_target = 0, m_step = 0;
    size_t m_left = 0;
};

/// Đổi tần số đa pha (sinc cửa sổ Kaiser), tỉ lệ hữu tỉ vào -> ra, giữ trạng thái giữa các khúc: cắt khúc kiểu nào ra cũng y hệt.
/// Không thêm trễ: khung ra thứ o ứng đúng vị trí o * vào / ra của nguồn (vị trí phát tính thẳng từ số khung ra).
class Resampler {
public:
    Resampler(int inRate, int outRate, int channels, int taps = 24) : m_channels(channels), m_taps(taps) {
        const int g = std::gcd(inRate, outRate);
        m_up = outRate / g;
        m_down = inRate / g;
        if (passthrough())
            return;
        // Cắt ở 0,45 tần số lấy mẫu của phía thấp hơn (đổi xuống thì theo tần số ra), đơn vị mẫu vào.
        const double cutoff = 0.45 * std::min(1.0, double(m_up) / m_down);
        const double beta = 8.0, half = taps / 2.0, pi = 3.14159265358979323846;
        m_table.resize(size_t(m_up) * taps);
        for (int phase = 0; phase < m_up; ++phase) {
            double sum = 0;
            for (int k = 0; k < taps; ++k) {
                const double x = (k - half + 1) - double(phase) / m_up;
                const double sinc = x == 0 ? 2 * cutoff : std::sin(2 * pi * cutoff * x) / (pi * x);
                const double r = x / half;
                const double window = besselI0(beta * std::sqrt(std::max(0.0, 1 - r * r))) / besselI0(beta);
                m_table[size_t(phase) * taps + k] = float(sinc * window);
                sum += sinc * window;
            }
            for (int k = 0; k < taps; ++k)
                m_table[size_t(phase) * taps + k] = float(m_table[size_t(phase) * taps + k] / sum); // một chiều giữ nguyên mức
        }
        reset();
    }

    bool passthrough() const { return m_up == m_down; }
    int taps() const { return m_taps; }
    /// Số khung ra ứng với `frames` khung vào (làm tròn lên).
    unsigned long long outFramesFor(unsigned long long frames) const { return (frames * m_up + m_down - 1) / m_down; }

    /// Bỏ trạng thái (tua): khung vào kế tiếp là đầu nguồn mới.
    void reset() {
        m_history.assign(size_t(m_taps / 2 - 1) * m_channels, 0.0f);
        m_position = 0;
    }

    /// Đưa `frames` khung vào; nối các khung ra tính được vào `out`.
    void push(const float *in, size_t frames, std::vector<float> &out) {
        if (passthrough()) {
            out.insert(out.end(), in, in + frames * m_channels);
            return;
        }
        m_history.insert(m_history.end(), in, in + frames * m_channels);
        const size_t have = m_history.size() / m_channels;
        for (;;) {
            const size_t base = size_t(m_position / m_up);
            if (base + m_taps > have)
                break;
            const float *h = &m_table[size_t(m_position % m_up) * m_taps];
            const float *x = &m_history[base * m_channels];
            for (int c = 0; c < m_channels; ++c) {
                float acc = 0;
                for (int k = 0; k < m_taps; ++k)
                    acc += h[k] * x[k * m_channels + c];
                out.push_back(acc);
            }
            m_position += m_down;
        }
        const size_t used = size_t(m_position / m_up);
        m_history.erase(m_history.begin(), m_history.begin() + used * m_channels);
        m_position -= (unsigned long long)used * m_up;
    }

private:
    static double besselI0(double x) {
        double sum = 1, term = 1;
        for (int k = 1; k < 32; ++k) {
            term *= (x / (2 * k)) * (x / (2 * k));
            sum += term;
        }
        return sum;
    }

    int m_channels, m_taps;
    int m_up = 1, m_down = 1;
    std::vector<float> m_table;     // [pha][hệ số]
    std::vector<float> m_history;   // khung vào chưa dùng hết, xen kênh
    unsigned long long m_position = 0; // vị trí khung ra kế, đơn vị 1/m_up khung vào, tính từ đầu m_history
};

} // namespace MixCore
