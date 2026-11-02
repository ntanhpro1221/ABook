#pragma once

#include <algorithm>
#include <deque>
#include <limits>
#include <utility>

// Lề chia tốc độ tải đo được của bài nhạc đang tải dở (musicmixer.cpp keepsUp): dự báo theo trung bình trượt `window` giây từng hụt tới đâu so với cái
// đã tới thật một cửa sổ sau, lấy lần tệ nhất, không quá `ceiling` (underrunMargin của music_mix.json). Chưa đo đủ 2 cửa sổ thì là `ceiling`. Đường đều
// co về ~1: bài vào sớm hơn; đường dao động mạnh giữ đúng lề trần - 76 vết HSDPA thật (Riiser 2013) mô phỏng đều chạm trần, nghe và hụt y như lề cố định
// (02-11). Cùng luật với musicBed.ts DownloadPace.margin và StreamPace.kt.
class DownloadForecast {
public:
    DownloadForecast(double window, double ceiling) : m_window(window), m_ceiling(ceiling) {}

    void reset() { m_samples.clear(); m_worst = -1; }

    // `bytes` đã tới lúc `seconds` (đồng hồ đơn điệu, giây).
    void add(double seconds, double bytes) {
        m_samples.push_back({seconds, bytes});
        // Giữ hai cửa sổ (một mẫu ngay trước làm mốc đầu): cửa sổ trước là dự báo, cửa sổ sau là thực tế của dự báo ấy.
        while (m_samples.size() > 2 && seconds - m_samples[1].first > 2 * m_window) m_samples.pop_front();
        if (m_samples.front().first > seconds - 2 * m_window) return;
        const auto at = [&](double t) {
            double got = m_samples.front().second;
            for (const auto &sample : m_samples) if (sample.first <= t) got = sample.second; else break;
            return got;
        };
        const double forecast = at(seconds - m_window) - at(seconds - 2 * m_window), real = bytes - at(seconds - m_window);
        const double ratio = real > 0 ? forecast / real : forecast > 0 ? std::numeric_limits<double>::infinity() : 1.0;
        m_worst = std::max({m_worst, 1.0, ratio});
    }

    double margin() const { return m_worst < 0 ? m_ceiling : std::min(m_ceiling, m_worst); }

private:
    double m_window, m_ceiling;
    std::deque<std::pair<double, double>> m_samples;
    double m_worst = -1; // dự báo / thực tế lớn nhất ở tầm một cửa sổ; -1 khi chưa đo đủ 2 cửa sổ
};
