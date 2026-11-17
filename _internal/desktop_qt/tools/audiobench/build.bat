@echo off
rem Builds the two playback-core benchmarks into %ABOOK_TOOLS_ROOT%\native_desk_proto\audiobench (outside the repo; defaults as in ..\..\build.bat).
setlocal
set HERE=%~dp0
if not defined ABOOK_TOOLS_ROOT for %%I in ("%HERE%..\..\..\..\..") do set "ABOOK_TOOLS_ROOT=%%~fI"
if not defined ABOOK_PYTHON if exist "%HERE%..\..\..\runtime\.venv\Scripts\python.exe" for %%I in ("%HERE%..\..\..\runtime\.venv\Scripts\python.exe") do set "ABOOK_PYTHON=%%~fI"
if not defined ABOOK_PYTHON set ABOOK_PYTHON=%ABOOK_TOOLS_ROOT%\ABook\_internal\runtime\.venv\Scripts\python.exe
set "QT_VERSION="
set /p "QT_VERSION="=<"%HERE%..\..\QT_VERSION"
if not defined QT_VERSION exit /b 1
if not defined QT_ROOT set QT_ROOT=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt611\%QT_VERSION%\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=%ABOOK_TOOLS_ROOT%\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS call "%~dp0..\find_vcvars.bat"
if not defined VCVARS exit /b 1
set OUT=%ABOOK_TOOLS_ROOT%\native_desk_proto\audiobench
call "%VCVARS%" >nul
"%ABOOK_PYTHON%" -X utf8 "%HERE%..\qt_sdk.py" --check-root "%QT_ROOT%"
if errorlevel 1 exit /b 1
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%
"%ABOOK_PYTHON%" -X utf8 "%HERE%..\drop_stale_cmake_cache.py" "%OUT%\build" --qt-root "%QT_ROOT%"
if errorlevel 1 exit /b 1
cmake -S "%HERE%." -B "%OUT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe"
if errorlevel 1 exit /b 1
cmake --build "%OUT%\build"
