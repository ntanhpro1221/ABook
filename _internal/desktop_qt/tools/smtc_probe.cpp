// GSMTC được đọc ở MTA; không cần UI hay PowerShell WinRT async.
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Media.Control.h>
#include <winrt/Windows.Storage.Streams.h>
#include <iostream>
#include <string>

int main(int argc, char **argv) {
    try {
        winrt::init_apartment();
        using namespace winrt::Windows::Media::Control;
        auto manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync().get();
        bool found = false;
        for (auto session : manager.GetSessions()) {
            const auto id = winrt::to_string(session.SourceAppUserModelId());
            if (id != "ABook.Desktop") continue;
            found = true;
            auto properties = session.TryGetMediaPropertiesAsync().get();
            std::cout << "SourceAppUserModelId=" << id << "\nTitle=" << winrt::to_string(properties.Title())
                      << "\nArtist=" << winrt::to_string(properties.Artist()) << "\nAlbumTitle=" << winrt::to_string(properties.AlbumTitle())
                      << "\nPlaybackStatus=" << int(session.GetPlaybackInfo().PlaybackStatus())
                      << "\nThumbnail=" << bool(properties.Thumbnail()) << std::endl;
            auto timeline = session.GetTimelineProperties();
            std::cout << "PositionSeconds=" << double(timeline.Position().count()) / 10'000'000.0
                      << "\nEndSeconds=" << double(timeline.EndTime().count()) / 10'000'000.0 << std::endl;
            if (properties.Thumbnail()) {
                auto stream = properties.Thumbnail().OpenReadAsync().get();
                std::cout << "ThumbnailBytes=" << stream.Size() << std::endl;
            }
            if (argc > 1 && std::string(argv[1]) == "--pause") {
                const bool accepted = session.TryPauseAsync().get();
                std::cout << "TryPauseAsync=" << accepted << std::endl;
                if (!accepted) return 3;
            }
            if (argc > 1) {
                std::string command(argv[1]);
                bool accepted = true;
                if (command == "--next") accepted = session.TrySkipNextAsync().get();
                else if (command == "--previous") accepted = session.TrySkipPreviousAsync().get();
                else if (command.starts_with("--seek="))
                    accepted = session.TryChangePlaybackPositionAsync(int64_t(std::stod(command.substr(7)) * 10'000'000)).get();
                else continue;
                std::cout << command << " accepted=" << accepted << std::endl;
                if (!accepted) return 3;
            }
        }
        if (!found) { std::cout << "ABook session absent\n"; return 2; }
        return 0;
    } catch (const winrt::hresult_error &e) {
        std::cout << "HRESULT=" << std::hex << uint32_t(e.code()) << " " << winrt::to_string(e.message()) << std::endl;
        return 1;
    }
}
