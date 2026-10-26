cmake_minimum_required(VERSION 3.21)

# Phiên bản app = phiên bản của ui/package.json (cũng là nguồn của tauri.conf.json), một chỗ duy nhất.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../ui/package.json" ABOOK_PACKAGE_JSON)
string(JSON ABOOK_VERSION GET "${ABOOK_PACKAGE_JSON}" version)

project(ABookDesk VERSION ${ABOOK_VERSION} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Hằng số trộn nhạc nền: MỘT file cho máy chủ, web, Android và app này (abook/webui/assets/music_mix.json) -> ABOOK_MIX_* (src/musiclogic.h).
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../abook/webui/assets/music_mix.json" ABOOK_MIX_JSON)
foreach(pair fadeSeconds:FADE_SECONDS siblingFadeSeconds:SIBLING_FADE_SECONDS stepRampSeconds:STEP_RAMP_SECONDS
        loopCrossfadeSeconds:LOOP_CROSSFADE_SECONDS loopMinPeriodSeconds:LOOP_MIN_PERIOD_SECONDS)
    string(REPLACE ":" ";" pair "${pair}")
    list(GET pair 0 key)
    list(GET pair 1 name)
    string(JSON value GET "${ABOOK_MIX_JSON}" ${key})
    add_compile_definitions(ABOOK_MIX_${name}=${value})
endforeach()

# Qt >= 6.10.3, liên kết ĐỘNG (LGPL): DLL Qt nằm cạnh file chạy do windeployqt chép, người dùng thay được.
find_package(Qt6 6.10 REQUIRED COMPONENTS Quick Network Test QuickTest CorePrivate GuiPrivate QuickPrivate)   # *Private: QWindowKit cần
qt_standard_project_setup(REQUIRES 6.10)

# App chỉ dựng trên Windows (Media Foundation, QWindowKit); máy khác (Linux CI, cloud) dựng và chạy mọi bộ thử.
if(WIN32)
# Khung cửa sổ tự vẽ (Apache-2.0, liên kết TĨNH, không thêm DLL): tools/build_qwindowkit.bat dựng vào QWK_ROOT/inst.
find_package(QWindowKit CONFIG REQUIRED)
endif()

# Theme.qml do tools/gen_theme.py sinh từ DESIGN.md; Nav.qml là singleton điều hướng.
set_source_files_properties(qml/Theme.qml qml/Nav.qml qml/Api.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

# Lõi bộ phát (không đụng Qt Quick): app và bộ thử QtTest cùng biên dịch đúng các file này.
set(ABOOK_PLAYER_SOURCES
    src/audioout.cpp
    src/audioout.h
    src/chaptersmodel.cpp
    src/chaptersmodel.h
    src/player.cpp
    src/player.h
    src/playerlogic.h
    src/playernet.h
    src/progressoutbox.cpp
    src/progressoutbox.h
)
# Nhạc nền (chép lớp MusicBed của bản web): app và bộ thử MusicTests cùng biên dịch.
set(ABOOK_MUSIC_SOURCES
    src/musicbed.cpp
    src/musicbed.h
    src/musiclogic.h
    src/musictext.h
)

if(WIN32)
qt_add_executable(ABookDesk WIN32
    src/desktopapi.cpp
    src/desktopapi.h
    src/main.cpp
    src/audioout_mf.cpp
    src/audioout_mf.h
    src/bookdetail.cpp
    src/bookdetail.h
    src/readalong.cpp
    src/readalong.h
    src/scriptlogic.h
    src/backend.cpp
    src/backend.h
    src/bench.cpp
    src/bench.h
    src/coverprovider.cpp
    src/coverprovider.h
    src/hostnet.cpp
    src/hostnet.h
    src/librarymodel.cpp
    src/librarymodel.h
    src/music.cpp
    src/music.h
    src/platform.cpp
    src/platform.h
    src/windowchrome.cpp
    src/windowchrome.h
    ${ABOOK_PLAYER_SOURCES}
    ${ABOOK_MUSIC_SOURCES}
)
target_include_directories(ABookDesk PRIVATE src)
qt_add_qml_module(ABookDesk
    URI ABook
    VERSION 1.0
    QML_FILES
        qml/Theme.qml
        qml/Nav.qml
        qml/Main.qml
        qml/Icon.qml
        qml/LucidePaths.js
        qml/Interactive.qml
        qml/Button.qml
        qml/IconButton.qml
        qml/NavItem.qml
        qml/TitleBar.qml
        qml/CaptionButton.qml
        qml/CaptionGlyph.qml
        qml/Sidebar.qml
        qml/ConnectionChip.qml
        qml/ConnectionPopover.qml
        qml/MenuRow.qml
        qml/ScreenStack.qml
        qml/ScreenHeader.qml
        qml/LibraryScreen.qml
        qml/BookCell.qml
        qml/CoverView.qml
        qml/GeneratedCover.qml
        qml/BookPage.qml
        qml/StudioScreen.qml
        qml/SettingsScreen.qml
        qml/Api.qml
        qml/FormLabel.qml
        qml/FormField.qml
        qml/SettingRow.qml
        qml/SettingChoices.qml
        qml/SectionBlock.qml
        qml/Modal.qml
        qml/SettingsBody.qml
        qml/SettingsVoice.qml
        qml/VoiceModule.qml
        qml/ProviderKey.qml
        qml/SettingsDevices.qml
        qml/SettingsStudio.qml
        qml/MyMusicSettings.qml
        qml/NativeFolders.qml
        qml/ThirdPartyText.qml
        qml/AddBook.qml
        qml/EditBook.qml
        qml/CoverSearch.qml
        qml/BookMusicSettings.qml
        qml/Collapse.qml
        qml/DisclosureRow.qml
        qml/SettingsItem.qml
        qml/ChoiceRow.qml
        qml/Select.qml
        qml/MoreInfo.qml
        qml/HintText.qml
        qml/SettingsListen.qml
        qml/SettingsSleep.qml
        qml/SettingsLook.qml
        qml/SettingsAdvanced.qml
        qml/StudioRows.qml
        qml/StudioSettings.qml
        qml/BookTemplates.qml
        qml/SharedReadingsSettings.qml
        qml/NewBookDefaults.qml
        qml/DevicesFold.qml
        qml/DevicesToggle.qml
        qml/DevicesRows.qml
        qml/DevicesError.qml
        qml/DevicesSkeleton.qml
        qml/DevicesUnpair.qml
        qml/DevicesLogBox.qml
        qml/PhoneSync.qml
        qml/PhoneSyncPairing.qml
        qml/PhoneSyncDevice.qml
        qml/PhoneDiagnostics.qml
        qml/OtherComputers.qml
        qml/OtherComputersRow.qml
        qml/OtherComputersBluetooth.qml
        qml/DevicesLogic.js
        qml/ImportQueue.js
        qml/ImportBox.qml
        qml/ImportCheck.qml
        qml/ImportSkeleton.qml
        qml/ImportError.qml
        qml/ImportFold.qml
        qml/ImportQueueList.qml
        qml/ImportChapters.qml
        qml/ImportSlot.qml
        qml/ImportActions.qml
        qml/ImportDrop.qml
        qml/Scrollbar.qml
        qml/ScrollEdges.qml
        qml/SmoothWheel.qml
        qml/ChapterList.qml
        qml/ChapterRow.qml
        qml/ChaptersPopover.qml
        qml/ChoiceChip.qml
        qml/ClockUser.qml
        qml/ControlChip.qml
        qml/NowPlaying.qml
        qml/PageSwitch.qml
        qml/PlayButton.qml
        qml/PlayerBar.qml
        qml/PlayerNotice.qml
        qml/Popover.qml
        qml/ReadAlongView.qml
        qml/SeekBar.qml
        qml/SkipButton.qml
        qml/SkipGlyph.qml
        qml/SleepPopover.qml
        qml/SpeedPopover.qml
        qml/Switch.qml
        qml/MusicPopover.qml
        qml/MusicCredit.qml
        qml/BenchScenario.qml
    RESOURCES
        fonts/BeVietnamPro-Regular.ttf
        fonts/BeVietnamPro-Medium.ttf
        fonts/BeVietnamPro-Bold.ttf
)
target_compile_definitions(ABookDesk PRIVATE ABOOK_VERSION="${ABOOK_VERSION}" QT_NO_CAST_FROM_ASCII)
# Âm thanh: Media Foundation của Windows (đo ở docs/NATIVE_PHONE_UI.md 7.1), không thêm DLL nào vào bản phân phối.
target_link_libraries(ABookDesk PRIVATE Qt6::Quick Qt6::Network QWindowKit::Quick mfplat mf mfuuid ole32 ksuser propsys)
qt_add_resources(ABookDesk legal PREFIX "/legal" BASE "../docs" FILES "../docs/THIRD_PARTY.md")
if(MSVC)
    target_compile_options(ABookDesk PRIVATE /W3 /utf-8)
endif()
endif()

# ---- bộ thử QtTest: bộ phát với AudioOut / PlayerNet giả, không cần thiết bị âm thanh hay host ----
qt_add_executable(PlayerTests tests/test_player.cpp tests/fakes.h ${ABOOK_PLAYER_SOURCES})
target_include_directories(PlayerTests PRIVATE src tests)
target_compile_definitions(PlayerTests PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(PlayerTests PRIVATE Qt6::Test Qt6::Qml Qt6::Network)
if(MSVC)
    target_compile_options(PlayerTests PRIVATE /W3 /utf-8)
endif()
# "Đọc theo" + trang sách: cần Qt Quick (QQuickTextDocument) nên là bộ thử riêng, vẫn không cần thiết bị âm thanh hay host
qt_add_executable(ReadAlongTests tests/test_readalong.cpp tests/fakes.h src/readalong.cpp src/readalong.h src/scriptlogic.h src/bookdetail.cpp src/bookdetail.h ${ABOOK_PLAYER_SOURCES})
target_include_directories(ReadAlongTests PRIVATE src tests)
target_compile_definitions(ReadAlongTests PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(ReadAlongTests PRIVATE Qt6::Test Qt6::Quick Qt6::Network)
if(MSVC)
    target_compile_options(ReadAlongTests PRIVATE /W3 /utf-8)
endif()
# Nhạc nền: phép tính thuần trên fixture chung với máy chủ / web / Android + MusicBed và Music (với Player) trên đồ giả
qt_add_executable(MusicTests tests/test_music.cpp tests/fakes.h src/music.cpp src/music.h ${ABOOK_PLAYER_SOURCES} ${ABOOK_MUSIC_SOURCES})
target_include_directories(MusicTests PRIVATE src tests)
target_compile_definitions(MusicTests PRIVATE QT_NO_CAST_FROM_ASCII MUSIC_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../tests/fixtures"
    MUSIC_MIX_JSON="${CMAKE_CURRENT_SOURCE_DIR}/../abook/webui/assets/music_mix.json")
target_link_libraries(MusicTests PRIVATE Qt6::Test Qt6::Qml Qt6::Network)
if(MSVC)
    target_compile_options(MusicTests PRIVATE /W3 /utf-8)
endif()
# Biểu tượng tua 15 giây đo bằng điểm ảnh (bộ vẽ phần mềm, nền offscreen)
qt_add_executable(SkipGlyphTests tests/test_skipglyph.cpp)
target_compile_definitions(SkipGlyphTests PRIVATE SKIPGLYPH_QML_DIR="${CMAKE_CURRENT_SOURCE_DIR}/qml" SKIPGLYPH_FONT_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fonts")
target_link_libraries(SkipGlyphTests PRIVATE Qt6::Test Qt6::Quick)
if(MSVC)
    target_compile_options(SkipGlyphTests PRIVATE /W3 /utf-8)
endif()
# Thanh bên thu gọn / mở rộng: QtQuickTest với Theme + Nav thật, Platform / Backend giả
qt_add_executable(SidebarTests tests/test_sidebar.cpp)
target_compile_definitions(SidebarTests PRIVATE QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/qml")
target_link_libraries(SidebarTests PRIVATE Qt6::QuickTest Qt6::Quick)
# Ở thư mục riêng: cạnh app thì Qt tìm thấy module ABook thật (trỏ vào qrc của app) trước bản dựng giả
set_target_properties(SidebarTests PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/sidebar_tests")
if(MSVC)
    target_compile_options(SidebarTests PRIVATE /W3 /utf-8)
endif()
enable_testing()
qt_add_executable(DesktopApiTests tests/test_desktopapi.cpp src/desktopapi.cpp src/desktopapi.h src/audioout.cpp src/audioout.h)
target_include_directories(DesktopApiTests PRIVATE src)
target_link_libraries(DesktopApiTests PRIVATE Qt6::Test Qt6::Quick Qt6::Network)
if(MSVC)
    target_compile_options(DesktopApiTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME DesktopApiTests COMMAND DesktopApiTests)
qt_add_executable(WidthTests tests/test_width.cpp tests/fakes.h src/bookdetail.cpp src/bookdetail.h
    src/readalong.cpp src/readalong.h src/music.cpp src/music.h ${ABOOK_PLAYER_SOURCES} ${ABOOK_MUSIC_SOURCES})
target_include_directories(WidthTests PRIVATE src tests)
target_compile_definitions(WidthTests PRIVATE QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/width"
    WIDTH_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(WidthTests PRIVATE Qt6::QuickTest Qt6::Quick Qt6::Network)
set_target_properties(WidthTests PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/width_tests")
if(MSVC)
    target_compile_options(WidthTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME WidthTests COMMAND WidthTests)
add_test(NAME PlayerTests COMMAND PlayerTests)
add_test(NAME ReadAlongTests COMMAND ReadAlongTests)
add_test(NAME MusicTests COMMAND MusicTests)
add_test(NAME SkipGlyphTests COMMAND SkipGlyphTests)
add_test(NAME SidebarTests COMMAND SidebarTests)
