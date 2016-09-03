pkg_check_modules(PYTHON python3 REQUIRED)
include_directories(${PYTHON_INCLUDE_DIRS})

if (NOT ${U_CMAKE_BUILD_TYPE} MATCHES DEBUG)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fvisibility=hidden")
endif()

include_directories(${PROJECT_SOURCE_DIR}/ext/pybind11/include)

add_library(pyrwmem SHARED pyrwmem.cpp)
target_link_libraries(pyrwmem rwmem-lib)

# Don't add a 'lib' prefix to the shared library
set_target_properties(pyrwmem PROPERTIES PREFIX "")

file(GLOB PY_SRCS "*.py")
add_custom_target(pyextras SOURCES ${PY_SRCS})
