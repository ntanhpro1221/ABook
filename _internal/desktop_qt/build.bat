@echo off
rem Windows app, Qt Quick (D0). Release build into build\, copy + windeployqt into dist\.
rem   build.bat           build
rem   build.bat clean     remove build\ and dist\ (node fs.rmSync; the repo rules forbid rm/del/rmdir)
rem Override with env vars: QWK_ROOT (QWindowKit, built by tools\build_qwindowkit.bat when missing), QT_ROOT (Qt >= 6.10.3 msvc2022_64), CMAKE_BIN, NINJA_BIN, VCVARS, ABOOK_PYTHON.
setlocal
set HERE=%~dp0
if not defined QT_ROOT set QT_ROOT=D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=D:\Novels\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=D:\Novels\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
if not defined QWK_ROOT set QWK_ROOT=D:\Novels\native_desk_proto\qwk
if not defined ABOOK_PYTHON set ABOOK_PYTHON=D:\Novels\ABook\_internal\runtime\.venv\Scripts\python.exe

if /i "%1"=="clean" (
  node -e "for (const d of ['build','dist']) require('fs').rmSync(process.argv[1] + '/' + d, {recursive: true, force: true})" "%HERE%."
  exit /b 0
)

call "%VCVARS%" >nul
if errorlevel 1 exit /b 1
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%

rem Own title bar: QWindowKit (Apache-2.0, static). Built once into %QWK_ROOT%\inst
if not exist "%QWK_ROOT%\inst\lib\cmake\QWindowKit\QWindowKitConfig.cmake" (
  call "%HERE%tools\build_qwindowkit.bat"
  if errorlevel 1 exit /b 1
)

rem Design tokens: Theme.qml must match DESIGN.md (regenerate with tools\gen_theme.py)
"%ABOOK_PYTHON%" -X utf8 "%HERE%tools\gen_theme.py" --check
if errorlevel 1 exit /b 1

rem Owner rule: never cut the user's text (no elide / maximumLineCount / clip on Text)
"%ABOOK_PYTHON%" -X utf8 "%HERE%tools\check_text_cut.py"
if errorlevel 1 exit /b 1

cmake -S "%HERE%." -B "%HERE%build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%;%QWK_ROOT%\inst" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe"
if errorlevel 1 exit /b 1
cmake --build "%HERE%build"
if errorlevel 1 exit /b 1

rem Player unit tests (QtTest with fake audio/network): red stops the build before packaging
"%HERE%build\DesktopApiTests.exe" -o "%HERE%build\desktopapi-test.txt",txt
if errorlevel 1 exit /b 1
"%HERE%build\PlayerTests.exe"
if errorlevel 1 exit /b 1
"%HERE%build\ReadAlongTests.exe"
if errorlevel 1 exit /b 1
rem Background music: shared fixtures with the server / web / Android + MusicBed on fake audio
"%HERE%build\MusicTests.exe"
if errorlevel 1 exit /b 1
rem Skip-15 icon pixel check (gap between stroke and digits, ink inside the box)
"%HERE%build\SkipGlyphTests.exe"
if errorlevel 1 exit /b 1
rem Sidebar collapse / expand / hover overlay (QtQuickTest with a stubbed Platform)
"%HERE%build\sidebar_tests\SidebarTests.exe"
if errorlevel 1 exit /b 1
rem Width classes: actual Book/Library/NowPlaying/Settings QML with fake HTTP/audio
"%HERE%build\width_tests\WidthTests.exe"
if errorlevel 1 exit /b 1

if not exist "%HERE%dist" mkdir "%HERE%dist"
copy /y "%HERE%build\ABookDesk.exe" "%HERE%dist\ABookDesk.exe" >nul
if errorlevel 1 exit /b 1
rem Dynamic Qt DLLs (LGPL): windeployqt copies DLLs + plugins next to the exe
rem Trim: D3D11 backend only (no dxc / d3d compiler / software GL), no debugger plugins, no touch plugin, no 18 MB vc_redist installer
windeployqt --release --qmldir "%HERE%qml" --no-translations --no-system-d3d-compiler --no-system-dxc-compiler --no-opengl-sw --no-compiler-runtime --skip-plugin-types qmltooling,generic "%HERE%dist\ABookDesk.exe"
if errorlevel 1 exit /b 1
rem App-local VC runtime (about 1 MB of DLLs instead of the installer), so a PC without the redistributable still starts
copy /y "%VCToolsRedistDir%x64\Microsoft.VC145.CRT\*.dll" "%HERE%dist\" >nul
if errorlevel 1 exit /b 1
echo OK: %HERE%dist\ABookDesk.exe
