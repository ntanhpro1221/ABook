cmake_minimum_required(VERSION 3.21)

# Phiên bản app = phiên bản của ui/package.json (cũng là nguồn của tauri.conf.json), một chỗ duy nhất.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../ui/package.json" ABOOK_PACKAGE_JSON)
string(JSON ABOOK_VERSION GET "${ABOOK_PACKAGE_JSON}" version)

project(ABookDesk VERSION ${ABOOK_VERSION} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Qt >= 6.10.3, liên kết ĐỘNG (LGPL): DLL Qt nằm cạnh file chạy do windeployqt chép, người dùng thay được.
find_package(Qt6 6.10 REQUIRED COMPONENTS Quick Network)
qt_standard_project_setup(REQUIRES 6.10)

# Theme.qml do tools/gen_theme.py sinh từ DESIGN.md; Nav.qml là singleton điều hướng.
set_source_files_properties(qml/Theme.qml qml/Nav.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)

qt_add_executable(ABookDesk WIN32
    src/main.cpp
    src/backend.cpp
    src/backend.h
    src/bench.cpp
    src/bench.h
    src/coverprovider.cpp
    src/coverprovider.h
    src/librarymodel.cpp
    src/librarymodel.h
    src/platform.cpp
    src/platform.h
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
        qml/Interactive.qml
        qml/Button.qml
        qml/IconButton.qml
        qml/NavItem.qml
        qml/Sidebar.qml
        qml/ConnectionChip.qml
        qml/ConnectionPopover.qml
        qml/ScreenStack.qml
        qml/ScreenHeader.qml
        qml/LibraryScreen.qml
        qml/BookCell.qml
        qml/CoverView.qml
        qml/GeneratedCover.qml
        qml/BookPage.qml
        qml/StudioScreen.qml
        qml/SettingsScreen.qml
        qml/Scrollbar.qml
        qml/SmoothWheel.qml
        qml/BenchScenario.qml
    RESOURCES
        fonts/BeVietnamPro-Regular.ttf
        fonts/BeVietnamPro-Medium.ttf
        fonts/BeVietnamPro-Bold.ttf
)
target_compile_definitions(ABookDesk PRIVATE ABOOK_VERSION="${ABOOK_VERSION}" QT_NO_CAST_FROM_ASCII)
target_link_libraries(ABookDesk PRIVATE Qt6::Quick Qt6::Network)
if(MSVC)
    target_compile_options(ABookDesk PRIVATE /W3 /utf-8)
endif()
