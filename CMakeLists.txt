cmake_minimum_required(VERSION 2.8)
project(rwmem)

include(CheckCXXCompilerFlag)

IF(NOT CMAKE_BUILD_TYPE)
  SET(CMAKE_BUILD_TYPE Release CACHE STRING
      "Choose the type of build, options are: Debug, Release."
      FORCE)
ENDIF(NOT CMAKE_BUILD_TYPE)

string(TOUPPER "${CMAKE_BUILD_TYPE}" U_CMAKE_BUILD_TYPE)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wextra")

if (NOT ${U_CMAKE_BUILD_TYPE} MATCHES DEBUG)
	CHECK_CXX_COMPILER_FLAG("-flto" HAS_LTO_FLAG)

	if (HAS_LTO_FLAG)
		set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto")
		set(CMAKE_AR gcc-ar)
		set(CMAKE_RANLIB gcc-ranlib)
	endif()
endif()

set(SOURCES cmdline.cpp helpers.cpp rwmem.cpp rwmem.h regs.cpp regs.h helpers.h opts.cpp opts.h inifile.cpp)

set(SOURCES ${SOURCES} inireader.cpp inireader.h)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DINI_ALLOW_MULTILINE=0")
set(SOURCES ${SOURCES} inih/ini.c inih/ini.h)

add_executable (rwmem ${SOURCES})
