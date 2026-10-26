// Cổng ra âm thanh của bộ phát: MỘT giao diện, Player (player.cpp) chỉ biết nó. Bản thật bọc một lõi của Windows (audioout_mf.cpp);
// bản giả trong tests/ cho phép thử Player không cần thiết bị âm thanh.
#pragma once

#include <QObject>
#include <QUrl>
#include <QtGlobal>

class AudioOut : public QObject {
    Q_OBJECT
public:
    explicit AudioOut(QObject *parent = nullptr) : QObject(parent) {}

    /// Nạp một nguồn (http hoặc file), đứng ở `startSeconds` ở trạng thái DỪNG. `play()` ngay sau đó là hợp lệ: phát khi nguồn sẵn sàng.
    virtual void load(const QUrl &url, double startSeconds) = 0;
    virtual void play() = 0;
    virtual void pause() = 0;
    /// Bỏ nguồn (đóng sách): nhả bộ giải mã và bộ đệm.
    virtual void stop() = 0;
    virtual void seek(double seconds) = 0;
    /// Tốc độ 0,5-4 với GIỮ cao độ.
    virtual void setRate(double rate) = 0;
    virtual void setVolume(double volume) = 0; // 0..1

    /// Giây hiện tại; sau `seek()` trả ngay đích tới khi nguồn đứng ở đó.
    virtual double position() const = 0;
    /// Giây; 0 khi chưa biết.
    virtual double duration() const = 0;
    virtual bool playing() const = 0;

/// ABOOK_MUTE=1 (thử máy, đo): âm lượng luôn 0, dù ai gọi gì - chạy thử không bao giờ ra loa.
    static double effectiveVolume(double volume);

signals:
    void durationChanged(double seconds);
    void playingChanged(bool playing);
    /// Tua xong (nguồn đã đứng ở chỗ mới).
    void seeked();
    /// Hết nguồn.
    void ended();
    void failed(const QString &reason);
    /// Đang chờ dữ liệu (mạng chậm).
    void buffering(bool on);
};
