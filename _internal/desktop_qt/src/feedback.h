// Tiếng chạm của giao diện (shared/feedback.ts; DESIGN.md 5.3): MỘT chỗ cho mọi tiếng. Tiếng tự tổng hợp (không file thu âm), cùng âm sắc "đồng thau
// gõ nhẹ" như bản web (Web Audio: sóng tuần hoàn bậc 1-5 giảm dần, lên trong 4 ms rồi tắt theo hàm mũ), ngắn <= 250 ms, ~ -24 dB; ghi thành file
// WAV một lần mỗi loại rồi phát qua một AudioOut riêng (máy tính không rung). Cài đặt › Giao diện › "Âm thanh chạm" tắt hết; sách đang phát thì
// im - trừ nốt báo hẹn giờ ngủ sắp tắt. Chỉ gọi cho việc NGƯỜI DÙNG vừa làm.
#pragma once

#include <QHash>
#include <QJSEngine>
#include <QObject>
#include <QQmlEngine>
#include <QTemporaryDir>
#include <QVector>
#include <QtQml/qqmlregistration.h>

#include <functional>

class AudioOut;

class Feedback : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    /// "Âm thanh chạm" (tuỳ chọn touchSounds, mặc định bật).
    Q_PROPERTY(bool sounds READ sounds WRITE setSounds NOTIFY soundsChanged)
    /// Số tiếng đã phát thật (bộ thử đếm).
    Q_PROPERTY(int played READ played NOTIFY playedChanged)
    Q_PROPERTY(QString lastKind READ lastKind NOTIFY playedChanged)

public:
    struct Note {
        double pitch;  // Hz
        double at;     // giây kể từ lúc bấm
        double length; // giây tới khi tắt hẳn
        double level;  // dB so với mức đầy
    };

    /// `make`: một AudioOut mới (Feedback làm chủ, tạo lười ở tiếng đầu tiên).
    Feedback(std::function<AudioOut *()> make, QObject *parent);
    ~Feedback() override;

    static Feedback *instance();
    static Feedback *create(QQmlEngine *, QJSEngine *);
    static void setInstance(Feedback *feedback);

    bool sounds() const { return m_sounds; }
    void setSounds(bool sounds);
    int played() const { return m_played; }
    QString lastKind() const { return m_lastKind; }

    /// Bảng 5.3: "toggle" | "tick" | "confirm" | "done" | "sleepWarn" có tiếng; "tap", "playPause", "reject", "longPress" im.
    Q_INVOKABLE void play(const QString &kind);
    /// Bộ phát báo sách đang phát / đã dừng: đang phát thì tiếng chạm im.
    void setBookPlaying(bool playing) { m_bookPlaying = playing; }

    static QVector<Note> notes(const QString &kind);
    /// File WAV (PCM 16 bit, một kênh) của một chuỗi nốt, có 5 ms lặng đầu như `ctx.currentTime + 0.005` của bản web.
    static QByteArray wav(const QVector<Note> &notes, int sampleRate = 44100);

signals:
    void soundsChanged();
    void playedChanged();

private:
    std::function<AudioOut *()> m_make;
    AudioOut *m_out = nullptr;
    QTemporaryDir m_dir;
    QHash<QString, QString> m_files;
    bool m_sounds = true;
    bool m_bookPlaying = false;
    int m_played = 0;
    QString m_lastKind;
};
