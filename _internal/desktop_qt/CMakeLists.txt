cmake_minimum_required(VERSION 3.21)

# Phiên bản app = phiên bản của ui/package.json (cũng là nguồn của tauri.conf.json), một chỗ duy nhất.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../ui/package.json" ABOOK_PACKAGE_JSON)
string(JSON ABOOK_VERSION GET "${ABOOK_PACKAGE_JSON}" version)

project(ABookDesk VERSION ${ABOOK_VERSION} LANGUAGES C CXX)
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
find_package(Qt6 6.10 REQUIRED COMPONENTS Quick Network Test QuickTest CorePrivate GuiPrivate QmlPrivate QuickPrivate)   # *Private: QWindowKit cần
qt_standard_project_setup(REQUIRES 6.10)

# App chỉ dựng trên Windows (Media Foundation, QWindowKit); máy khác (Linux CI, cloud) dựng và chạy mọi bộ thử.
if(WIN32)
# Khung cửa sổ tự vẽ (Apache-2.0, liên kết TĨNH, không thêm DLL): tools/build_qwindowkit.bat dựng vào QWK_ROOT/inst.
find_package(QWindowKit CONFIG REQUIRED)
endif()

# Theme.qml do tools/gen_theme.py sinh từ DESIGN.md; Nav.qml là singleton điều hướng.
set_source_files_properties(qml/Theme.qml qml/Nav.qml qml/Api.qml qml/Clip.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

# Lõi bộ phát (không đụng Qt Quick): app và bộ thử QtTest cùng biên dịch đúng các file này.
set(ABOOK_PLAYER_SOURCES
    src/audioout.cpp
    src/audioout.h
    src/chaptersmodel.cpp
    src/chaptersmodel.h
    src/speechout.cpp
    src/speechout.h
    src/outputdevices.h
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
set(ABOOK_MIXER_SOURCES src/musicmixer.cpp src/musicmixer.h src/mixcore.h src/mp3source.cpp src/mp3source.h src/mfsource.cpp src/mfsource.h
    src/streamsource.cpp src/streamsource.h src/timestretch.cpp src/timestretch.h third_party/sonic/sonic.c)

if(WIN32)
qt_add_executable(ABookDesk WIN32
    src/desktopapi.cpp
    src/later.h
    src/desktopapi.h
    src/main.cpp
    src/musicwindowactivity.h
    src/mediacontrols.cpp
    src/mediacontrols.h
    src/abookdesk.manifest
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
    src/feedback.cpp
    src/feedback.h
    src/hostmessage.h
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
    ${ABOOK_MIXER_SOURCES}
)
target_include_directories(ABookDesk PRIVATE src third_party)
qt_add_qml_module(ABookDesk
    URI ABook
    VERSION 1.0
    QML_FILES
        qml/Theme.qml
        qml/Nav.qml
        qml/Main.qml
        qml/WindowMode.qml
        qml/DesktopTray.qml
        qml/TrayMenuModel.qml
        qml/MiniPlayer.qml
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
        qml/LibraryContinue.qml
        qml/LibraryLogic.js
        qml/ChapterReader.qml
        qml/VolumeControl.qml
        qml/ReadingSuggestions.qml
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
        qml/DecisionButton.qml
        qml/StudioQuery.qml
        qml/WorkStore.qml
        qml/ReadingProblem.qml
        qml/TryReading.qml
        qml/TryButton.qml
        qml/TryNote.qml
        qml/WorkExample.qml
        qml/WorkField.qml
        qml/WorkRequested.qml
        qml/WorkPronunciation.qml
        qml/WorkSpeaker.qml
        qml/WorkNarrator.qml
        qml/WorkVoice.qml
        qml/WorkCard.qml
        qml/WorkBulkKeep.qml
        qml/WorkSection.qml
        qml/WorkInbox.qml
        qml/ReviewVerdict.qml
        qml/ReviewSpoken.qml
        qml/ReviewRow.qml
        qml/ReviewQueue.qml
        qml/NameEdit.qml
        qml/NameRow.qml
        qml/NameAddWord.qml
        qml/SharedOffer.qml
        qml/NameReadings.qml
        qml/PhoneEdits.qml
        qml/StudioPanels.qml
        qml/DecisionLogic.js
        qml/WorkLogic.js
        qml/ReviewLogic.js
        qml/NameLogic.js
        qml/StudioStore.qml
        qml/StudioSettings.qml
        qml/ProjectsScreen.qml
        qml/ProjectScreen.qml
        qml/ProjectRow.qml
        qml/ProjectMenu.qml
        qml/StudioMenuRow.qml
        qml/StudioBar.qml
        qml/StatusPill.qml
        qml/OnComputerPill.qml
        qml/StudioChapterRow.qml
        qml/StudioTabs.qml
        qml/TabLabel.qml
        qml/StudioConfirm.qml
        qml/StudioRename.qml
        qml/StudioDialogs.qml
        qml/StudioLogic.js
        qml/CoverPicker.qml
        qml/CoverEditor.qml
        qml/NewProjectScreen.qml
        qml/NewSource.qml
        qml/NewStartNotes.qml
        qml/StudioSetupNotice.qml
        qml/NewConfirm.qml
        qml/NewSwitchRow.qml
        qml/NewQuality.qml
        qml/NewVoice.qml
        qml/NewSeedBanner.qml
        qml/NewTemplateBar.qml
        qml/NewChapters.qml
        qml/NewCredits.qml
        qml/NewVolumes.qml
        qml/NewHints.qml
        qml/NumberBox.qml
        qml/NewProjectStore.qml
        qml/NewDrop.qml
        qml/NewPicker.qml
        qml/TextLink.qml
        qml/NewNote.qml
        qml/Prose.qml
        qml/UploadLogic.js
        qml/NewProjectLogic.js
        qml/TemplateLogic.js
        qml/StudioSetupLogic.js
        qml/StudioSetupCard.qml
        qml/StudioSetupState.qml
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
        qml/SizeFormat.js
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
        qml/VoiceLogic.js
        qml/VoiceFold.qml
        qml/VoiceCheck.qml
        qml/VoiceFlex.qml
        qml/VoiceBlock.qml
        qml/VoiceNote.qml
        qml/VoiceDetails.qml
        qml/VoiceRow.qml
        qml/VoiceModules.qml
        qml/VoiceSpeed.qml
        qml/ListenSave.qml
        qml/SleepWindow.qml
        qml/LookKbd.qml
        qml/LookShortcuts.qml
        qml/MyMusicBar.qml
        qml/MyMusicDetails.qml
        qml/MyMusicModule.qml
        qml/MyMusicTrack.qml
        qml/MyMusicState.qml
        qml/AdvancedUpdate.qml
        qml/AdvancedStorage.qml
        qml/AdvancedDiagnostics.qml
        qml/AdvancedAbout.qml
        qml/MyMusicText.js
        qml/EditBookLogic.js
        qml/EditBookActions.qml
        qml/EditBookSection.qml
        qml/EditBookSkeleton.qml
        qml/EditBookError.qml
        qml/EditBookSwap.qml
        qml/EditBookMyMusic.qml
        qml/StudioMusic.qml
        qml/StudioMusicScene.qml
        qml/StudioMusicSwap.qml
        qml/StudioMusicTrackRow.qml
        qml/StudioMusicMoods.qml
        qml/StudioMusicDetails.qml
        qml/StudioMyMusic.qml
        qml/StudioMusicLogic.js
        qml/EditBookReadings.qml
        qml/EditBookRename.qml
        qml/CastDialogs.qml
        qml/CastEngine.qml
        qml/CastGender.qml
        qml/CastList.qml
        qml/CastLogic.js
        qml/CastMerge.qml
        qml/CastModal.qml
        qml/CastPeople.qml
        qml/CastPerson.qml
        qml/CastRename.qml
        qml/CastSample.qml
        qml/CastVoice.qml
        qml/CastMenu.qml
        qml/CastUnmerge.qml
        qml/CastNote.qml
        qml/TellerMode.qml
        qml/TellerLogic.js
        qml/PrecastLogic.js
        qml/PrecastReview.qml
        qml/PrecastWait.qml
        qml/PrecastBanner.qml
        qml/CardFocus.qml
        qml/WorkCards.qml
        qml/HistoryList.qml
        qml/HistoryLogic.js
        qml/RecordChip.qml
        qml/RecordDialogs.qml
        qml/RecordLogic.js
        qml/RecordMenu.qml
        qml/Clip.qml
        qml/EditBookSaveAs.qml
        qml/EditBookItems.qml
        qml/Scrollbar.qml
        qml/ScrollEdges.qml
        qml/SmoothWheel.qml
        qml/ChapterList.qml
        qml/ChapterRow.qml
        qml/ChaptersPopover.qml
        qml/ChoiceChip.qml
        qml/ClockUser.qml
        qml/UiActivity.qml
        qml/ControlChip.qml
        qml/NowPlaying.qml
        qml/PageSwitch.qml
        qml/PlayButton.qml
        qml/PlayerBar.qml
        qml/PlayerLabels.js
        qml/PlayerConsent.qml
        qml/OutputPopover.qml
        qml/PlayerAlert.qml
        qml/PlayerFade.qml
        qml/PlayerSubtitle.qml
        qml/PlayerVoicePopover.qml
        qml/SidebarProgress.qml
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
        qml/Toast.qml
        qml/EmptyState.qml
        qml/PeerBar.qml
        qml/PeerStudio.js
        qml/PlayerKeys.qml
        qml/ShortcutsDialog.qml
        qml/BenchScenario.qml
    RESOURCES
        fonts/BeVietnamPro-Regular.ttf
        fonts/BeVietnamPro-Medium.ttf
        fonts/BeVietnamPro-Bold.ttf
)
target_compile_definitions(ABookDesk PRIVATE ABOOK_VERSION="${ABOOK_VERSION}" QT_NO_CAST_FROM_ASCII)
# Âm thanh: Media Foundation của Windows (đo ở docs/NATIVE_PHONE_UI.md 7.1), không thêm DLL nào vào bản phân phối.
target_link_libraries(ABookDesk PRIVATE Qt6::Quick Qt6::Network Qt6::GuiPrivate Qt6::QmlPrivate QWindowKit::Quick mfplat mf mfuuid mfreadwrite shlwapi ole32 ksuser propsys dwmapi windowsapp shell32)
qt_add_resources(ABookDesk legal PREFIX "/legal" BASE "../docs" FILES "../docs/THIRD_PARTY.md")
# Icon app máy tính = icon bo góc của Windows (scripts/make_icons.py -> abook/assets/app.ico, 16-256 px), KHÔNG phải
# icon vuông tràn viền của web (icon maskable cho điện thoại). Cửa sổ, khay và file exe dùng chung.
qt_add_resources(ABookDesk appicon PREFIX "/app" BASE "../abook/assets" FILES "../abook/assets/app.ico")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/appicon.rc" "IDI_ICON1 ICON \"${CMAKE_CURRENT_SOURCE_DIR}/../abook/assets/app.ico\"\n")
target_sources(ABookDesk PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/appicon.rc")
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
# Lõi trộn của đường âm thanh WASAPI: phép tính thuần, không Qt Quick, không thiết bị âm thanh
qt_add_executable(MixTests tests/test_mix.cpp src/audioout.cpp src/audioout.h ${ABOOK_MIXER_SOURCES} ${ABOOK_MUSIC_SOURCES})
target_include_directories(MixTests PRIVATE src third_party)
target_compile_definitions(MixTests PRIVATE QT_NO_CAST_FROM_ASCII MIX_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../tests/fixtures")
target_link_libraries(MixTests PRIVATE Qt6::Test Qt6::Network mfplat mf mfuuid mfreadwrite shlwapi ole32 ksuser propsys)
if(MSVC)
    target_compile_options(MixTests PRIVATE /W3 /utf-8)
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
qt_add_executable(PlayerNativeTests tests/test_playernative.cpp tests/fakes.h src/speechout.cpp src/speechout.h src/outputdevices.h src/audioout.cpp src/audioout.h src/playernet.h)
target_include_directories(PlayerNativeTests PRIVATE src tests)
target_compile_definitions(PlayerNativeTests PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(PlayerNativeTests PRIVATE Qt6::Test Qt6::Network)
if(MSVC)
    target_compile_options(PlayerNativeTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME PlayerNativeTests COMMAND PlayerNativeTests)
qt_add_executable(VoiceRender tools/voice_render.cpp src/mp3source.cpp src/mfsource.cpp src/streamsource.cpp src/timestretch.cpp third_party/sonic/sonic.c)
target_include_directories(VoiceRender PRIVATE src third_party)
target_compile_definitions(VoiceRender PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(VoiceRender PRIVATE Qt6::Network mfplat mf mfuuid mfreadwrite shlwapi ole32)
if(MSVC)
    target_compile_options(VoiceRender PRIVATE /W3 /utf-8)
endif()
qt_add_executable(VoiceTests tests/test_voice.cpp src/audioout.cpp src/audioout.h ${ABOOK_MIXER_SOURCES})
target_include_directories(VoiceTests PRIVATE src third_party)
target_compile_definitions(VoiceTests PRIVATE QT_NO_CAST_FROM_ASCII MIX_FIXTURES_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../tests/fixtures")
target_link_libraries(VoiceTests PRIVATE Qt6::Test Qt6::Network mfplat mf mfuuid mfreadwrite shlwapi ole32 ksuser propsys)
if(MSVC)
    target_compile_options(VoiceTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME VoiceTests COMMAND VoiceTests)
# Công cụ kiểm tiếng (không phải test, không vào bản phát hành): bộ trộn thật ghi ra WAV thay vì phát loa.
qt_add_executable(AudioTap tools/audiotap.cpp src/filesinkdevice.h src/audioout.cpp src/audioout.h ${ABOOK_MIXER_SOURCES})
target_include_directories(AudioTap PRIVATE src third_party)
target_compile_definitions(AudioTap PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(AudioTap PRIVATE Qt6::Network mfplat mf mfuuid mfreadwrite shlwapi ole32 ksuser propsys)
if(MSVC)
    target_compile_options(AudioTap PRIVATE /W3 /utf-8)
endif()
qt_add_executable(MediaControlsTests tests/test_mediacontrols.cpp tests/fakes.h src/mediacontrols.cpp src/mediacontrols.h ${ABOOK_PLAYER_SOURCES})
target_include_directories(MediaControlsTests PRIVATE src tests)
target_compile_definitions(MediaControlsTests PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(MediaControlsTests PRIVATE Qt6::Test Qt6::Qml Qt6::Network windowsapp shell32)
qt_add_executable(SmtcHost WIN32 tools/smtc_host.cpp tests/fakes.h src/mediacontrols.cpp src/mediacontrols.h ${ABOOK_PLAYER_SOURCES})
target_include_directories(SmtcHost PRIVATE src tests)
target_compile_definitions(SmtcHost PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(SmtcHost PRIVATE Qt6::Qml Qt6::Network windowsapp shell32)
add_executable(SmtcProbe tools/smtc_probe.cpp)
target_link_libraries(SmtcProbe PRIVATE windowsapp)
if(MSVC)
    foreach(target MediaControlsTests SmtcHost SmtcProbe)
        target_compile_options(${target} PRIVATE /W3 /utf-8)
    endforeach()
endif()
add_test(NAME MediaControlsTests COMMAND MediaControlsTests)
qt_add_executable(DesktopApiTests tests/test_desktopapi.cpp tests/fakes.h src/desktopapi.cpp src/desktopapi.h src/audioout.cpp src/audioout.h
    src/feedback.cpp src/feedback.h src/hostmessage.h src/playernet.h src/librarymodel.cpp src/librarymodel.h)
target_include_directories(DesktopApiTests PRIVATE tests)
target_include_directories(DesktopApiTests PRIVATE src)
target_link_libraries(DesktopApiTests PRIVATE Qt6::Test Qt6::Quick Qt6::Network)
if(MSVC)
    target_compile_options(DesktopApiTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME DesktopApiTests COMMAND DesktopApiTests)
qt_add_executable(WidthTests tests/test_width.cpp tests/glyphaudit.h tests/fakes.h src/later.h src/bookdetail.cpp src/bookdetail.h src/mediacontrols.cpp src/mediacontrols.h
    src/readalong.cpp src/readalong.h src/music.cpp src/music.h src/feedback.cpp src/feedback.h ${ABOOK_PLAYER_SOURCES} ${ABOOK_MUSIC_SOURCES})
target_include_directories(WidthTests PRIVATE src tests)
target_compile_definitions(WidthTests PRIVATE QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/tests/width"
    WIDTH_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(WidthTests PRIVATE Qt6::QuickTest Qt6::Quick Qt6::QuickPrivate Qt6::QmlPrivate Qt6::Network windowsapp shell32)   # QuickPrivate: FullRepaint, QmlPrivate: Later
set_target_properties(WidthTests PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/width_tests")
if(MSVC)
    target_compile_options(WidthTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME WidthTests COMMAND WidthTests)
add_test(NAME PlayerTests COMMAND PlayerTests)
add_test(NAME ReadAlongTests COMMAND ReadAlongTests)
add_test(NAME MusicTests COMMAND MusicTests)
add_test(NAME MixTests COMMAND MixTests)
add_test(NAME SkipGlyphTests COMMAND SkipGlyphTests)
add_test(NAME SidebarTests COMMAND SidebarTests)

qt_add_executable(MusicWindowActivityTests tests/test_musicwindowactivity.cpp src/musicwindowactivity.h)
target_include_directories(MusicWindowActivityTests PRIVATE src)
target_compile_definitions(MusicWindowActivityTests PRIVATE QT_NO_CAST_FROM_ASCII)
target_link_libraries(MusicWindowActivityTests PRIVATE Qt6::Test Qt6::Quick Qt6::GuiPrivate)
if(MSVC)
    target_compile_options(MusicWindowActivityTests PRIVATE /W3 /utf-8)
endif()
add_test(NAME MusicWindowActivityTests COMMAND MusicWindowActivityTests)
