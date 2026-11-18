@echo off
rem QWindowKit (Apache-2.0, https://github.com/stdware/qwindowkit) gives the app its own title bar with the native behaviour kept
rem (drag, double-click, Aero Snap, Windows 11 Snap Layouts, resize borders, shadow, rounded corners, Alt+Space menu).
rem Built STATIC (no extra DLL), Quick module only, from the pinned tag below, into %QWK_ROOT%\inst-%QT_VERSION%. build.bat calls this when %QWK_ROOT%\inst-%QT_VERSION% is missing.
rem Override with env vars: QWK_ROOT, QWK_TAG, QT_ROOT, CMAKE_BIN, NINJA_BIN, VCVARS, ABOOK_PYTHON, ABOOK_TOOLS_ROOT (defaults as in ..\build.bat).
setlocal
if not defined ABOOK_TOOLS_ROOT for %%I in ("%~dp0..\..\..\..") do set "ABOOK_TOOLS_ROOT=%%~fI"
if not defined ABOOK_PYTHON if exist "%~dp0..\..\runtime\.venv\Scripts\python.exe" for %%I in ("%~dp0..\..\runtime\.venv\Scripts\python.exe") do set "ABOOK_PYTHON=%%~fI"
if not defined ABOOK_PYTHON set ABOOK_PYTHON=%ABOOK_TOOLS_ROOT%\ABook\_internal\runtime\.venv\Scripts\python.exe
rem No Python found: say what to set instead of a bare "not recognized" from cmd (leftfix L6: a checkout not named ABook beside this one).
if not exist "%ABOOK_PYTHON%" echo ERROR: no Python at "%ABOOK_PYTHON%" - set ABOOK_PYTHON to runtime\.venv\Scripts\python.exe of an ABook checkout, or ABOOK_TOOLS_ROOT to the folder holding the main checkout named ABook 1>&2
if not exist "%ABOOK_PYTHON%" exit /b 1
if not defined QWK_ROOT set QWK_ROOT=%ABOOK_TOOLS_ROOT%\native_desk_proto\qwk
if not defined QWK_TAG set QWK_TAG=1.5.0
set "QT_VERSION="
set /p "QT_VERSION="=<"%~dp0..\QT_VERSION"
if not defined QT_VERSION exit /b 1
if not defined QT_ROOT set QT_ROOT=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt611\%QT_VERSION%\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS call "%~dp0find_vcvars.bat"
if not defined VCVARS exit /b 1
if not defined VSCMD_ARG_TGT_ARCH call "%VCVARS%" >nul
"%ABOOK_PYTHON%" -X utf8 "%~dp0qt_sdk.py" --check-root "%QT_ROOT%"
if errorlevel 1 exit /b 1
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%

if not exist "%QWK_ROOT%\src\CMakeLists.txt" (
  git clone --depth 1 --branch %QWK_TAG% --recurse-submodules --shallow-submodules https://github.com/stdware/qwindowkit.git "%QWK_ROOT%\src"
  if errorlevel 1 exit /b 1
)
"%ABOOK_PYTHON%" -X utf8 "%~dp0drop_stale_cmake_cache.py" "%QWK_ROOT%\build-%QT_VERSION%" --qt-root "%QT_ROOT%"
if errorlevel 1 exit /b 1
cmake -S "%QWK_ROOT%\src" -B "%QWK_ROOT%\build-%QT_VERSION%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe" -DCMAKE_INSTALL_PREFIX="%QWK_ROOT%\inst-%QT_VERSION%" -DQWINDOWKIT_BUILD_STATIC=ON -DQWINDOWKIT_BUILD_WIDGETS=OFF -DQWINDOWKIT_BUILD_QUICK=ON -DQWINDOWKIT_ENABLE_STYLE_AGENT=OFF -DQWINDOWKIT_BUILD_EXAMPLES=OFF -DQWINDOWKIT_BUILD_TESTS=OFF
if errorlevel 1 exit /b 1
cmake --build "%QWK_ROOT%\build-%QT_VERSION%"
if errorlevel 1 exit /b 1
cmake --install "%QWK_ROOT%\build-%QT_VERSION%"
if errorlevel 1 exit /b 1
echo OK: QWindowKit %QWK_TAG% in %QWK_ROOT%\inst-%QT_VERSION%
