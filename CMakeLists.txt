cmake_minimum_required(VERSION 2.8)
project(rwmem)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

include(CheckCXXCompilerFlag)

IF(NOT CMAKE_BUILD_TYPE)
    message(STATUS "Setting build type to 'Release' as none was specified.")
    SET(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
    set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
ENDIF()

string(TOUPPER "${CMAKE_BUILD_TYPE}" U_CMAKE_BUILD_TYPE)

option(BUILD_SHARED_LIBS "Build shared libs" FALSE)
set(RWMEM_ENABLE_PYTHON ON CACHE BOOL "Enable Python wrappers")

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wextra")

if (NOT ${U_CMAKE_BUILD_TYPE} MATCHES DEBUG)
	CHECK_CXX_COMPILER_FLAG("-flto" HAS_LTO_FLAG)

	if (HAS_LTO_FLAG)
		set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto")
		set(CMAKE_AR gcc-ar)
		set(CMAKE_RANLIB gcc-ranlib)
	endif()
endif()

find_package(PkgConfig REQUIRED)

add_subdirectory(librwmem)
#add_subdirectory(rwmem)

if(RWMEM_ENABLE_PYTHON)
        add_subdirectory(py)
endif()
