cmake_minimum_required(VERSION 3.21)
project(DecodeProfile LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
find_package(Qt6 REQUIRED COMPONENTS Core Network)
set(APP "${CMAKE_CURRENT_SOURCE_DIR}/../..")
add_executable(DecodeProfile main.cpp raw_float.cpp raw_int16.cpp
    ${APP}/src/mp3source.cpp ${APP}/src/streamsource.cpp ${APP}/src/timestretch.cpp
    ${APP}/third_party/sonic/sonic.c)
target_include_directories(DecodeProfile PRIVATE ${APP}/src ${APP}/third_party)
target_link_libraries(DecodeProfile PRIVATE Qt6::Core Qt6::Network)
if(MSVC)
    target_compile_options(DecodeProfile PRIVATE /O2 /utf-8)
endif()
