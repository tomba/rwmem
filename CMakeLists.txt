cmake_minimum_required(VERSION 2.8)
project(rwmem)

IF(NOT CMAKE_BUILD_TYPE)
  SET(CMAKE_BUILD_TYPE Release CACHE STRING
      "Choose the type of build, options are: Debug, Release."
      FORCE)
ENDIF(NOT CMAKE_BUILD_TYPE)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wextra")

set(SOURCES cmdline.cpp helpers.cpp rwmem.cpp rwmem.h regs.cpp regs.h helpers.h opts.cpp opts.h)

set(SOURCES ${SOURCES} inireader.cpp inireader.h)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DINI_ALLOW_MULTILINE=0")
set(SOURCES ${SOURCES} inih/ini.c inih/ini.h)

add_executable (rwmem ${SOURCES})
