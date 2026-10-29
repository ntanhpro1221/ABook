// Nhạc nền dùng chung một thiết bị; tách thiết bị để thử đúng đường trộn mà không mở loa.
#pragma once

#include "audioout.h"

#include <functional>
#include <memory>
#include <QVariantList>

struct tWAVEFORMATEX;

class MixDevice {
public:
    virtual ~MixDevice() = default;
    virtual int rate() const = 0;
    virtual bool start() = 0;
    virtual void stop() = 0;
    virtual void reset() = 0;
    virtual size_t padding() = 0;
    virtual size_t bufferFrames() const = 0;
    virtual bool write(const float *stereo, size_t frames) = 0;
    // Chỉ luồng trộn gọi: thông báo Windows chỉ đánh dấu, không dựng COM ngay trong callback.
    virtual bool refresh() { return true; }
    // Nonempty only for a terminal device error; transient endpoint loss may retry.
    virtual QString error() const { return {}; }
    virtual quint64 revision() const { return 0; }
    virtual QVariantList outputs() const { return {}; }
    virtual QString outputId() const { return {}; }
    virtual bool selectOutput(const QString &id) { return id.isEmpty(); }
    // Chờ tối đa maxMs tới ngay sau lần engine kéo kế tiếp. Stop..Start vắt qua lúc kéo thì engine phát im lặng
    // trọn một chu kỳ (10 ms); trộn lại ngay sau lần kéo thì cả chu kỳ còn trống.
    virtual void awaitPull(int maxMs) { Q_UNUSED(maxMs); }
};

class WasapiDevice final : public MixDevice {
public:
    explicit WasapiDevice(std::function<void()> changed);
    ~WasapiDevice() override;
    int rate() const override;
    bool start() override;
    void stop() override;
    void reset() override;
    size_t padding() override;
    size_t bufferFrames() const override;
    bool write(const float *stereo, size_t frames) override;
    void awaitPull(int maxMs) override;
    bool refresh() override;
    QString error() const override;
    quint64 revision() const override;
    QVariantList outputs() const override;
    QString outputId() const override;
    bool selectOutput(const QString &id) override;
    static bool supportsFormat(const tWAVEFORMATEX &format);
private:
    bool openOutput(const QString &id);
    struct Impl;
    std::unique_ptr<Impl> d;
};

struct MixVoiceState;
class MixVoice;
class VoiceDecoder;

class MusicMixer : public QObject {
    Q_OBJECT
public:
    explicit MusicMixer(const QString &cacheDir, QObject *parent = nullptr);
    // threaded=false: bộ thử tự phục vụ cả reader lẫn mixer, không phụ thuộc lịch luồng/hardware.
    MusicMixer(std::unique_ptr<MixDevice> device, const QString &cacheDir, bool threaded = false, QObject *parent = nullptr);
    ~MusicMixer() override;
    int rate() const;
    void setRelaxed(bool relaxed);
    void service(size_t frames);
    void serviceReader();
    quint64 decodeCount() const;
    QString cachePath(const QUrl &url) const;
    static quint64 cacheFrames(const QString &path, int rate);
    void requestOutputs();
    void selectOutput(const QString &id);
signals:
    void outputsReady(const QVariantList &outputs, const QString &selected, bool accepted);

private:
    friend class MixVoice;
    struct Impl;
    std::unique_ptr<Impl> d;
    void wake(bool reader = false);
    void fetch(const std::shared_ptr<MixVoiceState> &state, quint64 generation);
    void post(const std::shared_ptr<MixVoiceState> &state, std::function<void(MixVoice *)> event);
    double position(const std::shared_ptr<MixVoiceState> &state) const;
    void serviceStream(const std::shared_ptr<MixVoiceState> &state);
    void postSeeked(const std::shared_ptr<MixVoiceState> &state);
};

class MixVoice final : public AudioOut {
    Q_OBJECT
public:
    explicit MixVoice(MusicMixer *mixer, QObject *parent = nullptr);
    enum Purpose { Music, Voice };
    MixVoice(MusicMixer *mixer, Purpose purpose, QObject *parent = nullptr);
    MixVoice(MusicMixer *mixer, std::function<std::unique_ptr<VoiceDecoder>(int)> decoder, QObject *parent = nullptr);
    ~MixVoice() override;
    void load(const QUrl &url, double startSeconds) override;
    void play() override;
    void pause() override;
    void stop() override;
    void seek(double seconds) override;
    void setRate(double rate) override;
    void setVolume(double volume) override;
    void preload() override;
    void setLoop(bool loop) override;
    double position() const override;
    double duration() const override;
    bool playing() const override;

private:
    MusicMixer *m_mixer;
    std::shared_ptr<MixVoiceState> m_state;
};
