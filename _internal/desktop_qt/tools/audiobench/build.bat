@echo off
rem Dựng hai file đo lõi phát vào D:\Novels\native_desk_proto\audiobench (ngoài repo).
setlocal
set HERE=%~dp0
if not defined QT_ROOT set QT_ROOT=D:\Novels\native_desk_proto\qt611\6.10.3\msvc2022_64
if not defined CMAKE_BIN set CMAKE_BIN=D:\Novels\native_desk_proto\qt\Tools\CMake_64\bin
if not defined NINJA_BIN set NINJA_BIN=D:\Novels\native_desk_proto\qt\Tools\Ninja
if not defined VCVARS set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat
set OUT=D:\Novels\native_desk_proto\audiobench
call "%VCVARS%" >nul
set PATH=%CMAKE_BIN%;%NINJA_BIN%;%QT_ROOT%\bin;%PATH%
cmake -S "%HERE%." -B "%OUT%\build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_ROOT%" -DCMAKE_MAKE_PROGRAM="%NINJA_BIN%\ninja.exe"
if errorlevel 1 exit /b 1
cmake --build "%OUT%\build"
