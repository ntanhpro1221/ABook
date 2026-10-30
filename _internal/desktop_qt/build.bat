@echo off
rem Windows app, Qt Quick (D0). Release build into build\, copy + windeployqt into dist\.
rem   build.bat           build
rem   build.bat clean     remove build\ and dist\ with Python shutil
rem Override with env vars: QWK_ROOT (QWindowKit, built by tools\build_qwindowkit.bat when missing), QT_ROOT (Qt >= 6.10.3 msvc2022_64), CMAKE_BIN, NINJA_BIN, VCVARS, ABOOK_PYTHON.
setlocal
set HERE=%~dp0
rem Owner 27-10: test windows never appear on the screen
set QT_QPA_PLATFORM=offscreen
if not defined QT_ROOT set QT_ROOT=D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=D:\Novels\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=D:\Novels\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
if not defined QWK_ROOT set QWK_ROOT=D:\Novels\native_desk_proto\qwk
if not defined ABOOK_PYTHON set ABOOK_PYTHON=D:\Novels\ABook\_internal\runtime\.venv\Scripts\python.exe

if /i "%1"=="clean" (
  "%ABOOK_PYTHON%" -X utf8 -c "import pathlib,shutil,sys; root=pathlib.Path(sys.argv[1]).resolve(); targets=[root/name for name in ('build','dist')]; assert all(p.resolve().parent==root for p in targets); [shutil.rmtree(p) for p in targets if p.exists()]" "%HERE%."
  exit /b 0
)

call "%VCVARS%" >nul
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%

rem Own title bar: QWindowKit (Apache-2.0, static). Built once into %QWK_ROOT%\inst
if not exist "%QWK_ROOT%\inst\lib\cmake\QWindowKit\QWindowKitConfig.cmake" (
  call "%HERE%tools\build_qwindowkit.bat"
  if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
)

rem Design tokens: Theme.qml must match DESIGN.md (regenerate with tools\gen_theme.py)
"%ABOOK_PYTHON%" -X utf8 "%HERE%tools\gen_theme.py" --check
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1

rem Owner rule: never cut the user's text (no elide / maximumLineCount / clip on Text)
"%ABOOK_PYTHON%" -X utf8 "%HERE%tools\check_text_cut.py"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1

cmake -S "%HERE%." -B "%HERE%build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%;%QWK_ROOT%\inst" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
cmake --build "%HERE%build"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1

rem Player unit tests (QtTest with fake audio/network): red stops the build before packaging
call :test "%HERE%build\PlayerNativeTests.exe" "%HERE%build\playernative-test.txt"
if errorlevel 1 exit /b 1
call :test "%HERE%build\MediaControlsTests.exe" "%HERE%build\mediacontrols-test.txt"
if errorlevel 1 exit /b 1
call :test "%HERE%build\DesktopApiTests.exe" "%HERE%build\desktopapi-test.txt"
if errorlevel 1 exit /b 1
call :test "%HERE%build\PlayerTests.exe" "%HERE%build\player-test.txt"
if errorlevel 1 exit /b 1
call :test "%HERE%build\ReadAlongTests.exe" "%HERE%build\readalong-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Background music: shared fixtures with the server / web / Android + MusicBed on fake audio
call :test "%HERE%build\MusicTests.exe" "%HERE%build\music-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem WASAPI mixing core: ring, volume ramp, resampler on numbers
call :test "%HERE%build\VoiceTests.exe" "%HERE%build\voice-test.txt"
if errorlevel 1 exit /b 1
call :test "%HERE%build\MixTests.exe" "%HERE%build\mix-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Music scheduling observes main, mini and any later application windows.
call :test "%HERE%build\MusicWindowActivityTests.exe" "%HERE%build\musicwindowactivity-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Skip-15 icon pixel check (gap between stroke and digits, ink inside the box)
call :test "%HERE%build\SkipGlyphTests.exe" "%HERE%build\skipglyph-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Sidebar collapse / expand / hover overlay (QtQuickTest with a stubbed Platform)
call :test "%HERE%build\sidebar_tests\SidebarTests.exe" "%HERE%build\sidebar-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Width classes: actual Book/Library/NowPlaying/Settings QML with fake HTTP/audio
call :test "%HERE%build\width_tests\WidthTests.exe" "%HERE%build\width-test.txt"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1

if not exist "%HERE%dist" mkdir "%HERE%dist"
rem copyfile writes the packaged file now, so its timestamp proves this build reached packaging
rem even when Ninja correctly leaves the unchanged executable alone on the second run.
"%ABOOK_PYTHON%" -X utf8 -c "import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])" "%HERE%build\ABookDesk.exe" "%HERE%dist\ABookDesk.exe"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Dynamic Qt DLLs (LGPL): windeployqt copies DLLs + plugins next to the exe
rem Trim: D3D11 backend only (no dxc / d3d compiler / software GL), no debugger plugins, no touch plugin, no 18 MB vc_redist installer
windeployqt --release --qmldir "%HERE%qml" --no-translations --no-system-d3d-compiler --no-system-dxc-compiler --no-opengl-sw --no-compiler-runtime --skip-plugin-types qmltooling,generic "%HERE%dist\ABookDesk.exe"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem App-local VC runtime (about 1 MB of DLLs instead of the installer), so a PC without the redistributable still starts
copy /y "%VCToolsRedistDir%x64\Microsoft.VC145.CRT\*.dll" "%HERE%dist\" >nul
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
rem Sonic is statically linked: ship its Apache-2.0 license and pinned provenance.
if not exist "%HERE%dist\licenses" mkdir "%HERE%dist\licenses"
copy /y "%HERE%third_party\sonic\LICENSE" "%HERE%dist\licenses\Sonic-LICENSE.txt" >nul
if errorlevel 1 exit /b 1
copy /y "%HERE%third_party\sonic\UPSTREAM" "%HERE%dist\licenses\Sonic-UPSTREAM.txt" >nul
if errorlevel 1 exit /b 1
echo OK: %HERE%dist\ABookDesk.exe
exit /b 0

rem Keep every QtTest result: GUI stderr alone can be empty even when tests fail.
:test
"%~1" -o "%~2",txt
set TEST_EXIT=%errorlevel%
type "%~2"
"%ABOOK_PYTHON%" -X utf8 "%HERE%tools\check_test_results.py" "%~2"
if errorlevel 1 (
  echo ERROR: Qt test or glyph audit failed: %~2
  exit /b 1
)
if not "%TEST_EXIT%"=="0" (
  echo ERROR: Qt test process exited %TEST_EXIT%: %~1
  exit /b 1
)
findstr /c:"FAIL!" "%~2" >nul
if not errorlevel 1 exit /b 1
exit /b 0
