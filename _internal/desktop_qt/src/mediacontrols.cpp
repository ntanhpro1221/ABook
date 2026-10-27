// WinRT phải đứng trước Qt: macro signals/slots/emit không thuộc cú pháp C++/WinRT.
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Media.h>
#include <winrt/Windows.Storage.Streams.h>
#include <systemmediatransportcontrolsinterop.h>
#include <shobjidl.h>

#include "mediacontrols.h"
#include "player.h"
#include <QDebug>
#include <QNetworkReply>
#include <algorithm>
#include <cmath>
#include <mutex>

using namespace winrt::Windows::Media;
using namespace winrt::Windows::Storage::Streams;
using winrt::Windows::Foundation::TimeSpan;

MediaState fromPlayer(const Player &player) {
    MediaState s;
    s.loaded = player.loaded();
    if (!s.loaded) return s;
    s.title = player.chapterTitle().isEmpty() ? QStringLiteral("Chương %1").arg(player.chapterNumber()) : player.chapterTitle();
    s.artist = s.album = player.bookTitle();
    s.status = player.playing() ? MediaState::Playing : MediaState::Paused;
    s.canNext = player.canNext();
    s.canPrevious = player.canPrevious();
    s.duration = std::max(0.0, player.duration());
    s.position = std::clamp(player.position(), 0.0, s.duration);
    s.rate = player.rate();
    return s;
}

namespace {
winrt::hstring text(const QString &s) { return winrt::hstring(reinterpret_cast<const wchar_t *>(s.utf16()), uint32_t(s.size())); }
TimeSpan timeSpan(double seconds) { return TimeSpan{qint64(seconds * 10'000'000)}; }

struct NativeState {
    SystemMediaTransportControls controls{nullptr};
    std::mutex lock;
    quint64 revision = 0;
    bool alive = true;
};

// StoreAsync có thể chờ I/O; hoàn tất ở luồng nền và bỏ lời đáp của sách/chương đã rời đi.
winrt::fire_and_forget thumbnail(std::shared_ptr<NativeState> state, quint64 revision, QByteArray bytes) {
    co_await winrt::resume_background();
    try {
        InMemoryRandomAccessStream stream;
        DataWriter writer(stream);
        writer.WriteBytes(winrt::array_view<const uint8_t>(reinterpret_cast<const uint8_t *>(bytes.constData()), uint32_t(bytes.size())));
        co_await writer.StoreAsync();
        writer.DetachStream();
        stream.Seek(0);
        auto reference = RandomAccessStreamReference::CreateFromStream(stream);
        std::lock_guard guard(state->lock);
        if (!state->alive || state->revision != revision) co_return;
        auto updater = state->controls.DisplayUpdater();
        updater.Thumbnail(reference);
        updater.Update();
    } catch (const winrt::hresult_error &e) {
        qWarning() << "SMTC cover:" << QString::fromWCharArray(e.message().c_str());
    }
}

class WindowsMediaSink final : public MediaSink {
public:
    WindowsMediaSink(quintptr hwnd, std::function<void(MediaCommand, double)> command) : m_state(std::make_shared<NativeState>()) {
        auto factory = winrt::get_activation_factory<SystemMediaTransportControls, ISystemMediaTransportControlsInterop>();
        winrt::check_hresult(factory->GetForWindow(reinterpret_cast<HWND>(hwnd), winrt::guid_of<SystemMediaTransportControls>(),
                                                    winrt::put_abi(m_state->controls)));
        auto controls = m_state->controls;
        m_button = controls.ButtonPressed([command](const auto &, const SystemMediaTransportControlsButtonPressedEventArgs &args) {
            switch (args.Button()) {
            case SystemMediaTransportControlsButton::Play: command(MediaCommand::Play, 0); break;
            case SystemMediaTransportControlsButton::Pause: command(MediaCommand::Pause, 0); break;
            case SystemMediaTransportControlsButton::Next: command(MediaCommand::Next, 0); break;
            case SystemMediaTransportControlsButton::Previous: command(MediaCommand::Previous, 0); break;
            default: break;
            }
        });
        m_seek = controls.PlaybackPositionChangeRequested([command](const auto &, const PlaybackPositionChangeRequestedEventArgs &args) {
            command(MediaCommand::Seek, double(args.RequestedPlaybackPosition().count()) / 10'000'000.0);
        });
    }
    ~WindowsMediaSink() override {
        std::lock_guard guard(m_state->lock);
        m_state->alive = false;
        try {
            auto c = m_state->controls;
            c.ButtonPressed(m_button);
            c.PlaybackPositionChangeRequested(m_seek);
            c.IsEnabled(false);
        } catch (const winrt::hresult_error &) {}
    }
    void display(const MediaState &s, const QByteArray &cover) override {
        std::lock_guard guard(m_state->lock);
        const auto revision = ++m_state->revision;
        auto updater = m_state->controls.DisplayUpdater();
        updater.ClearAll();
        updater.Type(MediaPlaybackType::Music);
        auto music = updater.MusicProperties();
        music.Title(text(s.title));
        music.Artist(text(s.artist));
        music.AlbumTitle(text(s.album));
        updater.Update();
        if (!cover.isEmpty()) thumbnail(m_state, revision, cover);
    }
    void playback(const MediaState &s) override {
        std::lock_guard guard(m_state->lock);
        auto c = m_state->controls;
        c.IsEnabled(s.loaded);
        c.IsPlayEnabled(s.loaded);
        c.IsPauseEnabled(s.loaded);
        c.IsNextEnabled(s.loaded && s.canNext);
        c.IsPreviousEnabled(s.loaded && s.canPrevious);
        c.PlaybackStatus(s.status == MediaState::Playing ? MediaPlaybackStatus::Playing :
                         s.status == MediaState::Paused ? MediaPlaybackStatus::Paused : MediaPlaybackStatus::Stopped);
        c.PlaybackRate(s.rate);
    }
    void timeline(const MediaState &s) override {
        std::lock_guard guard(m_state->lock);
        SystemMediaTransportControlsTimelineProperties timeline;
        timeline.StartTime(timeSpan(0));
        timeline.EndTime(timeSpan(s.duration));
        timeline.MinSeekTime(timeSpan(0));
        timeline.MaxSeekTime(timeSpan(s.duration));
        timeline.Position(timeSpan(s.position));
        m_state->controls.UpdateTimelineProperties(timeline);
    }
private:
    struct Apartment {
        Apartment() { winrt::init_apartment(winrt::apartment_type::single_threaded); }
        ~Apartment() { winrt::uninit_apartment(); }
    } m_apartment;
    std::shared_ptr<NativeState> m_state;
    winrt::event_token m_button{}, m_seek{};
};
} // namespace

struct MediaControls::Relay {
    std::mutex lock;
    MediaControls *owner = nullptr;
};

MediaControls::MediaControls(Player *player, AudioOut *out, std::unique_ptr<MediaSink> sink, CoverRequest coverRequest, QObject *parent)
    : QObject(parent), m_player(player), m_sink(std::move(sink)), m_coverRequest(std::move(coverRequest)), m_relay(std::make_shared<Relay>()) {
    m_relay->owner = this;
    connect(player, &Player::bookChanged, this, &MediaControls::updateDisplay);
    connect(player, &Player::chapterChanged, this, &MediaControls::updateDisplay);
    for (auto signal : {&Player::loadedChanged, &Player::chapterChanged, &Player::playingChanged, &Player::rateChanged})
        connect(player, signal, this, [this] { updatePlayback(); updateTimeline(); });
    connect(out, &AudioOut::seeked, this, &MediaControls::updateTimeline);
    connect(player->clock(), &PlayerClock::durationChanged, this, &MediaControls::updateTimeline);
    updateDisplay(); updatePlayback(); updateTimeline();
}

MediaControls::~MediaControls() {
    // Thu hồi sự kiện không chờ callback đang chạy: chặn cửa trước khi huỷ sink.
    std::lock_guard guard(m_relay->lock);
    m_relay->owner = nullptr;
}

void MediaControls::setAppId() { SetCurrentProcessExplicitAppUserModelID(L"ABook.Desktop"); }

bool MediaControls::attachWindow(quintptr hwnd) {
    try {
        auto relay = m_relay;
        m_sink = std::make_unique<WindowsMediaSink>(hwnd, [relay](MediaCommand command, double seconds) {
            std::lock_guard guard(relay->lock);
            if (relay->owner) relay->owner->dispatch(command, seconds);
        });
        updateDisplay(); updatePlayback(); updateTimeline();
        return true;
    } catch (const winrt::hresult_error &e) {
        qWarning() << "SMTC:" << QString::fromWCharArray(e.message().c_str());
        m_sink.reset();
        return false;
    }
}

void MediaControls::dispatch(MediaCommand command, double seconds) {
    QMetaObject::invokeMethod(this, [this, command, seconds] {
        if (!m_player->loaded()) return;
        switch (command) {
        case MediaCommand::Play: m_player->resume(); break;
        case MediaCommand::Pause: m_player->pause(); break;
        case MediaCommand::Next: if (m_player->canNext()) m_player->next(); break;
        case MediaCommand::Previous: if (m_player->canPrevious()) m_player->previous(); break;
        case MediaCommand::Seek: if (std::isfinite(seconds)) m_player->seek(seconds); break;
        }
        emit commandExecuted(command);
    }, Qt::QueuedConnection);
}

void MediaControls::updateDisplay() {
    if (!m_sink) return;
    const QString key = m_player->loaded() ? m_player->coverKey() : QString();
    m_coverKey = key;
    try { m_sink->display(fromPlayer(*m_player), m_covers.value(key)); }
    catch (const winrt::hresult_error &e) { qWarning() << "SMTC display:" << QString::fromWCharArray(e.message().c_str()); }
    if (key.isEmpty() || m_covers.contains(key) || !m_coverRequest) return;
    m_covers.insert(key, {}); // Đổi chương lúc đang tải cũng không được gửi lại yêu cầu bìa.
    const auto parts = key.split(QLatin1Char('/'));
    auto *reply = m_coverRequest(QStringLiteral("/media/books/%1/cover?v=%2").arg(parts.value(0), parts.value(1)));
    if (!reply) return;
    connect(reply, &QNetworkReply::finished, this, [this, reply, key] {
        const QByteArray bytes = reply->error() == QNetworkReply::NoError ? reply->readAll() : QByteArray();
        reply->deleteLater();
        m_covers[key] = bytes;
        if (m_coverKey == key && m_sink) updateDisplay();
    });
}
void MediaControls::updatePlayback() {
    if (!m_sink) return;
    try { m_sink->playback(fromPlayer(*m_player)); }
    catch (const winrt::hresult_error &e) { qWarning() << "SMTC playback:" << QString::fromWCharArray(e.message().c_str()); }
}
void MediaControls::updateTimeline() {
    if (!m_sink) return;
    try { m_sink->timeline(fromPlayer(*m_player)); }
    catch (const winrt::hresult_error &e) { qWarning() << "SMTC timeline:" << QString::fromWCharArray(e.message().c_str()); }
}
