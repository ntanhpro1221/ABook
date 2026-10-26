// Bộ phát bằng Windows Media Foundation (IMFMediaEngine, chế độ chỉ-âm-thanh): có sẵn trong Windows, không thêm DLL nào vào bộ cài,
// đổi tốc độ giữ cao độ do chính Windows làm.
// Lười: bộ máy chỉ dựng và nguồn chỉ mở khi có lệnh phát đầu tiên - mở app với cuốn nghe dở đang dừng không tốn gì (RAM, thời gian khởi động).
#pragma once

#include "audioout.h"

#include <QUrl>

#include <memory>

class MfAudioOut final : public AudioOut {
    Q_OBJECT
public:
    explicit MfAudioOut(QObject *parent = nullptr);
    ~MfAudioOut() override;

    void load(const QUrl &url, double startSeconds) override;
    void play() override;
    void pause() override;
    void stop() override;
    void seek(double seconds) override;
    void setRate(double rate) override;
    void setVolume(double volume) override;
    double position() const override;
    double duration() const override;
    bool playing() const override { return m_playing; }

private:
    struct Impl;
    class Notify;
    void onEvent(unsigned long event, quint64 p1, unsigned long p2);
    bool ensureEngine();
    void openSource();

    std::unique_ptr<Impl> d;
    bool m_playing = false;
    bool m_wantPlay = false;
    bool m_loaded = false;      // đã có LOADEDMETADATA
    bool m_sourceOpen = false;  // đã đưa nguồn cho bộ máy (SetSource)
    QUrl m_url;
    bool m_started = false;     // MFStartup đã gọi
    bool m_seeking = false;
    double m_target = 0;        // đích tua / chỗ bắt đầu khi chưa nạp xong
    double m_rate = 1;
    double m_volume = 1;
    double m_duration = 0;
    quint64 m_serial = 0;       // mỗi lần load() +1: sự kiện của nguồn cũ bị bỏ
};
