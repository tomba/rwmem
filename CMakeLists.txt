cmake_minimum_required(VERSION 3.0)
project(rwmem)

enable_testing()

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

option(BUILD_STATIC_EXES "Build static executables" FALSE)
option(BUILD_SHARED_LIBS "Build shared libs" FALSE)
option(TREAT_WARNINGS_AS_ERRORS "Treat warnings as errors" FALSE)

set(RWMEM_ENABLE_PYTHON ON CACHE BOOL "Enable Python wrappers")

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -Wno-unused-parameter")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wextra -Wno-unused-parameter")

if (CMAKE_COMPILER_IS_GNUCC)
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS 5.0)
        # GCC 4.x seems to warn too much
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-missing-field-initializers")
    endif()
endif()

# HACK: cmake always adds "-rdynamic", this removes it
SET(CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "")
SET(CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS "")

set(CMAKE_POSITION_INDEPENDENT_CODE TRUE)

if (TREAT_WARNINGS_AS_ERRORS)
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Werror")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Werror")
endif()

if (NOT ${U_CMAKE_BUILD_TYPE} MATCHES DEBUG)
	CHECK_CXX_COMPILER_FLAG("-flto" HAS_LTO_FLAG)

	if (HAS_LTO_FLAG)
		set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -flto")
		set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -flto")
		set(CMAKE_AR ${CMAKE_CXX_COMPILER_AR})
		set(CMAKE_RANLIB ${CMAKE_CXX_COMPILER_RANLIB})
	endif()
endif()

if (BUILD_STATIC_EXES)
	set(CMAKE_EXE_LINKER_FLAGS "-static")
endif()

find_package(PkgConfig REQUIRED)

add_subdirectory(librwmem)
add_subdirectory(rwmem)

if(RWMEM_ENABLE_PYTHON)
        add_subdirectory(py)
endif()

add_custom_target(readme SOURCES README.md)
