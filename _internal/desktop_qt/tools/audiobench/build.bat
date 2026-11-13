@echo off
rem Builds the two playback-core benchmarks into D:\Novels\native_desk_proto\audiobench (outside the repo).
setlocal
if not defined ABOOK_PYTHON set ABOOK_PYTHON=D:\Novels\ABook\_internal\runtime\.venv\Scripts\python.exe
set HERE=%~dp0
if not defined QT_ROOT set QT_ROOT=D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=D:\Novels\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=D:\Novels\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS call "%~dp0..\find_vcvars.bat"
if not defined VCVARS exit /b 1
set OUT=D:\Novels\native_desk_proto\audiobench
call "%VCVARS%" >nul
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%
"%ABOOK_PYTHON%" -X utf8 "%HERE%..\drop_stale_cmake_cache.py" "%OUT%\build"
if errorlevel 1 exit /b 1
cmake -S "%HERE%." -B "%OUT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe"
if errorlevel 1 exit /b 1
cmake --build "%OUT%\build"
