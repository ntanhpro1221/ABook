// Nonblocking byte ranges. HTTP runs on the owning Qt thread; decoders only read cached bytes.
#pragma once
#include <QByteArray>
#include <QObject>
#include <QUrl>
#include <functional>
#include <memory>
#include <vector>

class ByteSource {
public:
    virtual ~ByteSource() = default;
    // Empty means not available yet, unless offset >= size() or error() is nonempty.
    virtual QByteArray read(qint64 offset, qint64 count) = 0;
    virtual qint64 size() const = 0; // -1 until response headers arrive
    virtual QString error() const = 0;
};

class RangeSource final : public QObject, public ByteSource {
public:
    RangeSource(const QUrl &url, std::function<void()> ready);
    ~RangeSource() override;
    QByteArray read(qint64 offset, qint64 count) override;
    qint64 size() const override;
    QString error() const override;
private:
    struct Impl;
    std::unique_ptr<Impl> d;
    void request(qint64 offset);
};

// All methods run on the decoder thread, never the WASAPI thread. Injectable in mixer tests.
class VoiceDecoder {
public:
    virtual ~VoiceDecoder() = default;
    virtual bool open() = 0; // false may mean awaiting bytes (error empty)
    virtual bool seek(double seconds) = 0;
    virtual size_t read(std::vector<float> &stereo, size_t frames) = 0;
    virtual double duration() const = 0;
    virtual bool atEnd() const = 0;
    virtual QString error() const = 0;
};

class StreamMp3 final : public VoiceDecoder {
public:
    StreamMp3(std::shared_ptr<ByteSource> bytes, int outputRate);
    ~StreamMp3() override;
    bool open() override;
    bool seek(double seconds) override;
    size_t read(std::vector<float> &stereo, size_t frames) override;
    double duration() const override;
    bool atEnd() const override;
    QString error() const override;
private:
    struct Impl;
    std::unique_ptr<Impl> d;
};
