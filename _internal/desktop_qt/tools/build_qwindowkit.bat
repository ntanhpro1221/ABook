@echo off
rem QWindowKit (Apache-2.0, https://github.com/stdware/qwindowkit) gives the app its own title bar with the native behaviour kept
rem (drag, double-click, Aero Snap, Windows 11 Snap Layouts, resize borders, shadow, rounded corners, Alt+Space menu).
rem Built STATIC (no extra DLL), Quick module only, from the pinned tag below, into %QWK_ROOT%\inst. build.bat calls this when %QWK_ROOT%\inst is missing.
rem Override with env vars: QWK_ROOT, QWK_TAG, QT_ROOT, CMAKE_BIN, NINJA_BIN, VCVARS.
setlocal
if not defined QWK_ROOT set QWK_ROOT=D:\Novels\native_desk_proto\qwk
if not defined QWK_TAG set QWK_TAG=1.5.0
if not defined QT_ROOT set QT_ROOT=D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=D:\Novels\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=D:\Novels\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
if not defined VSCMD_ARG_TGT_ARCH call "%VCVARS%" >nul
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%

if not exist "%QWK_ROOT%\src\CMakeLists.txt" (
  git clone --depth 1 --branch %QWK_TAG% --recurse-submodules --shallow-submodules https://github.com/stdware/qwindowkit.git "%QWK_ROOT%\src"
  if errorlevel 1 exit /b 1
)
cmake -S "%QWK_ROOT%\src" -B "%QWK_ROOT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe" -DCMAKE_INSTALL_PREFIX="%QWK_ROOT%\inst" -DQWINDOWKIT_BUILD_STATIC=ON -DQWINDOWKIT_BUILD_WIDGETS=OFF -DQWINDOWKIT_BUILD_QUICK=ON -DQWINDOWKIT_ENABLE_STYLE_AGENT=OFF -DQWINDOWKIT_BUILD_EXAMPLES=OFF -DQWINDOWKIT_BUILD_TESTS=OFF
if errorlevel 1 exit /b 1
cmake --build "%QWK_ROOT%\build"
if errorlevel 1 exit /b 1
cmake --install "%QWK_ROOT%\build"
if errorlevel 1 exit /b 1
echo OK: QWindowKit %QWK_TAG% in %QWK_ROOT%\inst
